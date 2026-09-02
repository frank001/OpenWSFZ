# ft8lib-interop Specification

## Purpose
Specifies the P/Invoke binding layer between managed C# code and the `kgoba/ft8_lib` native decode library. This layer is implemented in `OpenWSFZ.Ft8/Interop/` and was introduced in p12. The ft8-decoder spec depends on this capability for its decode implementation.

Per **NFR-001**, the library SHALL function on all three reference platforms: Windows x64, Linux x64, and macOS ARM64.
## Requirements
### Requirement: Single decode entry point via P/Invoke on all three platforms

The `Ft8LibInterop` class in `OpenWSFZ.Ft8` SHALL expose a single managed method `DecodeAll(float[] pcm)` that calls the native `ft8_decode_all` function via P/Invoke and returns a managed array of decoded results. The native library SHALL be loaded once per process lifetime via `NativeLibrary.Load`, selecting the platform-appropriate file name:

| Platform | File name |
|---|---|
| Windows x64 | `libft8.dll` |
| Linux x64 | `libft8.so` |
| macOS ARM64 | `libft8.dylib` |

The load path SHALL be `AppContext.BaseDirectory`. A `NativeLibrary.SetDllImportResolver` SHALL be registered on the assembly before the first P/Invoke call to map the `"libft8.dll"` import token to the platform-appropriate file name. A platform-guard that returns empty on non-Windows without loading the library is a violation of this requirement.

#### Scenario: DecodeAll returns results for a real-signal buffer (Windows)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on Windows with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns results for a real-signal buffer (Linux)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on Linux x64 with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns results for a real-signal buffer (macOS)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on macOS ARM64 with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns empty array for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with 180 000 samples of silence
- **THEN** the method SHALL return an empty array without throwing

#### Scenario: DecodeAll raises on wrong sample count

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a buffer that is not exactly 180 000 samples
- **THEN** the method SHALL throw `ArgumentException` before calling the native function

---

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260049`** (`f001-h12-unique-match-suppression` — see below; the description immediately following is of `20260046`, an earlier version this entry advanced from, preserved verbatim). 🔴 **Unlike the two bumps immediately preceding it (`20260047`/`20260048`, both MEASURE-ONLY), `20260049` is behaviour-bearing on the decode output path** — it implements the Option A decision ("NO NAME BEATS A WRONG NAME"): a 12-bit callsign-hash lookup whose probe chain holds two or more matching entries now renders the existing `<...>` placeholder instead of a (possibly wrong) name. No existing production entry point's ABI or struct layout changes: `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and every other existing exported symbol remain byte-for-byte unchanged in signature, and the `FT8Result` struct layout is untouched — this is a behaviour-bearing rebuild, not an ABI break. `20260046` was fix-negative-time-offset-snr-collapse: `ft8_decode_all`'s `signal_db` loop derives the waterfall-block-to-symbol-index mapping from a candidate's `time_offset` **clamped** to a non-negative floor, instead of the true, unclamped value — for any candidate whose sync position precedes the decode window (`time_offset < 0`, an ordinary outcome of `ftx_find_candidates()`'s `-10..+19` search range), every one of the 79 averaged samples is read from the wrong tone bin, under-reporting SNR by roughly 15–20 dB; confirmed mechanically (`qa/rr-study/2026-08-22-1454-...-b-dt-c3-results.md`, a 17.4 dB step co-located exactly with the sign change, ~210× the largest deficit a benign "signal partly outside the window" explanation could produce there). The fix derives the symbol index from the unclamped `time_offset`, matching `ft8_lib`'s own out-of-range convention (`patched/ft8/decode.c:160,226`), and correspondingly narrows the loop's own upper bound so no symbol index can run past `FT8_NN`; `DecodeAll`'s ABI, `FT8Result` struct layout, and every other existing exported symbol remain byte-for-byte unchanged — this is a behaviour-bearing rebuild, not an ABI break. Two further bumps shipped between `20260046` and `20260049`, both MEASURE-ONLY (no production decode output changed at either): `20260047` = `f001-sup-b-instrumented-suppression-sizing` Phase 1 — three process-lifetime 12-bit hash-path sizing getters (`ft8_get_h12_displaying_count`/`_ambiguous_count`/`_divergent_count`), diagnostic-only, no existing entry point's ABI or behaviour altered; `20260048` = the same change's Phase 2 (Amendment 2) — one further diagnostic-only export, `ft8_get_h12_by_code`, a per-code (12-bit code space, 4,096 values) cluster breakdown of the same three counts, deliberately given no managed `IFt8NativeInterop`/`Ft8LibInterop` binding (its only intended consumer is a measurement harness driving the native library directly). ⚠️ Version history immediately prior to this entry is **repaired here, not merely extended**: the base spec this text was copied from still read `20260042` despite `main`'s actual `FT8_SHIM_VERSION` already standing at `20260045` at the time this change was drafted (the pre-existing "spec-sync backlog" this same paragraph has flagged since `20260042`) — bumps `20260043` = r2-coherent-llr-instrument Phase 1 (diagnostic-only `ft8_coherent_llr_at`, no production call site), `20260044` = r2-coherent-llr-instrument Phase B + Amendment 1 (B1 origin-conversion fix and B2 fusion-scale fix to `ft8_coherent_llr_at`, both diagnostic-only; B4 adds diagnostic-only `ft8_ldpc_decode_llrs`), `20260045` = r2-coherent-llr-instrument Amendment 2 corrected by Amendment 3 (widens `ftx_ldpc_decode_llrs`'s degenerate-variance guard; adds the diagnostic-only `ft8_get_last_snr_terms` getter) are now recorded rather than left undocumented. Full prior history (`20260041` and earlier) is unchanged and carries forward from the version this text supersedes: 20260041 = r1b-sync-refiner-instrument-correction (`ft8_refine_candidate` gains its coarse/fine time-search decomposition out-parameters), 20260040 = r1-sync-refiner-instrument-validation (diagnostic-only per-candidate coherent sync-refinement export added, no production call site), 20260039 = r0-reproducible-native-build (shim rebuilt from a fully vendored, version-controlled source tree with byte-identical decode behaviour to the prior `20260038` build), 20260038 = g2-hash-table-sizing-and-candidate-passband, 20260031 = f-001-hashed-callsign-resolution, 20260030 = decoder-settings-page runtime-configurable OSD gate parameters, 20260029 = D-009 K_MIN_SCORE_PASS2 raised 1→10, 20260028 = D-009 OSD nhard gate, 20260025 = OSD fallback + 50-iter BP, 20260021 = H6 AP decode hiscall offset fix; ⚠️ the intermediate bumps between `20260032` and `20260037` remain undocumented, an existing tracked spec-sync backlog item, not introduced or expanded by this change. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260049`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Previous library (20260048) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260048` (`f001-sup-b-instrumented-suppression-sizing` Phase 2 — the measure-only pin, which still displays a callsign resolved from an ambiguous probe chain) after `f001-h12-unique-match-suppression`'s managed code expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260047) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260047` (`f001-sup-b-instrumented-suppression-sizing` Phase 1 — the three sizing getters exist but the per-code cluster table export does not) after Phase 2's managed code expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260046) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260046` (fix-negative-time-offset-snr-collapse, pre-`f001-sup-b-instrumented-suppression-sizing`) after Phase 1's managed code expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260045) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260045` (r2-coherent-llr-instrument Amendment 2/3 — pre-fix, still carries the negative-`time_offset` SNR defect)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260041) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260041` (r1b-sync-refiner-instrument-correction)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260040) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260040` (r1-sync-refiner-instrument-validation)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260039) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260039` (r0-reproducible-native-build)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260038) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260038` (g2-hash-table-sizing-and-candidate-passband)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260030) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260030` (decoder-settings-page)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260029) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260029` (D-009 K=10)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260016) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260016` (fix-d006-cleanup)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

### Requirement: Per-pass decode counts are accessible from managed code

`Ft8LibInterop` SHALL expose a method `GetLastPassCounts(int maxPasses)` that calls the native `ft8_get_last_pass_counts` function via P/Invoke and returns a managed `int[]` of length equal to the number of passes actually executed (**now 2**). The managed constant `MaxDecodePasses` SHALL be **2**.

#### Scenario: GetLastPassCounts returns correct two-pass breakdown

- **WHEN** `Ft8LibInterop.DecodeAll` is called and then `GetLastPassCounts(2)` is called on the same thread
- **THEN** `GetLastPassCounts` SHALL return an array of length **2** whose sum equals the total number of decoded messages returned by `DecodeAll`

#### Scenario: GetLastPassCounts returns zeros for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a silent buffer (0 decodes) and then `GetLastPassCounts(2)` is called
- **THEN** `GetLastPassCounts` SHALL return `[0, 0]`

---

### Requirement: Native result struct is layout-compatible with the C shim

The `Ft8NativeResult` struct in managed code SHALL be decorated with `[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]` and SHALL declare fields matching the C `FT8Result` struct in the shim: `int FreqHz`, `float Dt`, `int Snr`, and a fixed-length `char[36]` message buffer. The managed struct size SHALL equal the C struct size (48 bytes, verifiable via `Marshal.SizeOf`). This layout constraint applies identically on all three reference platforms — the C shim MUST be compiled with identical struct packing on each.

#### Scenario: Struct size matches between managed and native

- **WHEN** `Marshal.SizeOf<Ft8NativeResult>()` is called
- **THEN** the returned size SHALL equal the value of `sizeof(FT8Result)` as compiled into the shim (48 bytes, documented in `Ft8LibInterop.cs` as a compile-time constant)

---

### Requirement: ft8_set_decode_params native entry point (shim 20260030)

The native shim SHALL expose a new function `ft8_set_decode_params(int k_min_score_pass2, float osd_corr_threshold, int osd_nhard_max)` that writes three module-level `static` variables read by `ft8_decode_all` on every invocation. The function SHALL be callable from any thread (module-level statics, not TLS). The three variables SHALL be initialised at compilation time to the D-009 calibrated defaults (`K_MIN_SCORE_PASS2 = 10`, `OSD_CORR_THRESHOLD = 0.10f`, `OSD_NHARD_MAX = 60`), so that the shim behaves identically to v20260029 if `ft8_set_decode_params` is never called.

The shim version constant `FT8_SHIM_VERSION` SHALL be advanced to `20260030`. All three platform binaries (Windows x64, Linux x64, macOS ARM64) SHALL be rebuilt from this shim version and committed.

#### Scenario: ft8_set_decode_params is exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_set_decode_params` SHALL be resolvable via the `DllImport` / `NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: Updated parameters are used on the next decode call

- **WHEN** `ft8_set_decode_params(5, 0.20f, 50)` is called and then `ft8_decode_all` is invoked
- **THEN** the native shim SHALL use `K_MIN_SCORE_PASS2 = 5`, `OSD_CORR_THRESHOLD = 0.20f`, and `OSD_NHARD_MAX = 50` for that decode cycle

#### Scenario: Default parameter values match shim 20260029 behaviour

- **WHEN** `ft8_set_decode_params` is never called
- **THEN** `ft8_decode_all` SHALL behave identically to shim v20260029: `K_MIN_SCORE_PASS2 = 10`, `OSD_CORR_THRESHOLD = 0.10f`, `OSD_NHARD_MAX = 60`

---

### Requirement: SetDecodeParams P/Invoke and IFt8NativeInterop method

`Ft8LibInterop` SHALL expose a `public static void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)` method that calls `EnsureInitialized()` and then invokes the native `ft8_set_decode_params` function via P/Invoke. `IFt8NativeInterop` SHALL add a corresponding `void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)` method so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL.

#### Scenario: SetDecodeParams calls EnsureInitialized before P/Invoke

- **WHEN** `Ft8LibInterop.SetDecodeParams` is called before any `DecodeAll` invocation (native library not yet loaded)
- **THEN** the native library SHALL be loaded and the ABI version check SHALL pass before the `ft8_set_decode_params` function is called

#### Scenario: IFt8NativeInterop.SetDecodeParams is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `SetDecodeParams` calls
- **THEN** calling `SetDecodeParams(8, 0.12f, 55)` on the fake SHALL record the arguments without loading the native DLL

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib` submodule at the pinned commit, SHALL be committed for all three reference platforms:

| Platform | Path | Declared in csproj |
|---|---|---|
| Windows x64 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `<Content CopyToOutputDirectory="Always" Link="libft8.dll" />` |
| Linux x64 | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | `<Content CopyToOutputDirectory="Always" Link="libft8.so" />` |
| macOS ARM64 | `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` | `<Content CopyToOutputDirectory="Always" Link="libft8.dylib" />` |

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, SNR formula, and the pass count (**2**). `BUILD.md` SHALL document the exact compiler commands required to reproduce each binary. The binaries SHALL be built from the **`FT8_SHIM_VERSION = 20260049`** shim (`f001-h12-unique-match-suppression` — the 12-bit unique-match suppression rule, the first bump in this family that changes decode OUTPUT, not just diagnostics; see the ABI self-test requirement above for the full history this advances from, including the `20260046` fix-negative-time-offset-snr-collapse rebuild and `f001-sup-b-instrumented-suppression-sizing`'s measure-only `20260047`/`20260048` — this requirement's own version reference was found several versions stale at drafting time, `20260030`, and is repaired here as part of the same edit).

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output directory alongside the daemon executable

### Requirement: Diagnostic refine-candidate P/Invoke entry point

`Ft8LibInterop` SHALL expose a managed method (`RefineCandidate`) that calls the native `ft8_refine_candidate` function via P/Invoke, taking the cycle's PCM buffer and a coarse `(freq_hz, time_offset)` candidate position and returning the refined `(Δf, Δt)`, sync quality score, AND the two new coarse/fine time-search selections (`coarseDtSamp`, `fineDtSamp`) exposed by this change's native-side out-parameters. `IFt8NativeInterop` SHALL add a corresponding method signature (extended with the two new `out int` parameters) so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL, matching the existing pattern used for `SetDecodeParams`. This method SHALL be reachable only from test code and the validation harness — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it. This requirement REPLACES r1-sync-refiner-instrument-validation's requirement of the same name, extended with the two new parameters; every scenario from that requirement continues to hold and is restated here with the extended signature.

#### Scenario: RefineCandidate is exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_refine_candidate` SHALL be resolvable via the `DllImport` / `NativeLibrary` mechanism on Windows, Linux, and macOS without error, and its exported signature SHALL include the two new out-parameters

#### Scenario: RefineCandidate returns a refined offset and its decomposition for a known-truth signal

- **WHEN** `Ft8LibInterop.RefineCandidate` is called with a synthetic-oracle-generated PCM buffer and the coarse candidate position `ftx_find_candidates()` would report for it
- **THEN** the method SHALL return a refined `(Δf, Δt)`, a sync quality score, and the two coarse/fine time-search selections, without throwing, and `coarseDtSamp / 200.0 + fineDtSamp / 2000.0` SHALL equal the returned `Δt` to within float32 rounding tolerance

#### Scenario: IFt8NativeInterop.RefineCandidate is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `RefineCandidate` calls
- **THEN** calling it with a representative PCM buffer and coarse position SHALL record the arguments, including the two new out-parameters, without loading the native DLL

#### Scenario: No production call site invokes RefineCandidate

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this change lands
- **THEN** it SHALL contain no call to `RefineCandidate` or `ft8_refine_candidate` outside of test code and the validation harness

### Requirement: Diagnostic extract-LLRs-at-position native export

The shim SHALL export a native function, `ft8_extract_llrs_at(pcm, pcm_len, freq_hz, time_offset_s, out_llr174)`, that builds a waterfall from the supplied PCM buffer exactly as `ft8_decode_all` does, locates the nearest point on the existing candidate frequency/time lattice (`K_FREQ_OSR`/`K_TIME_OSR`, unchanged) to the caller-supplied `(freq_hz, time_offset_s)`, and runs the existing, unmodified `ft8_extract_likelihood()` extraction path at that position. It SHALL return the raw, pre-normalisation 174 log-likelihoods (`ftx_normalize_logl` SHALL NOT be applied). It SHALL return `0` on success, `-1` if `pcm_len` does not equal the expected sample count or `out_llr174` is `NULL`, `-2` if an internal fault is caught by the same SEH containment `ft8_decode_all` already uses, and `-3` if the resolved frequency bin falls outside the waterfall's valid range. This export SHALL be reachable only from test code and QA harnesses invoking it directly via the platform's native-library loading mechanism (e.g. Python `ctypes`) — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it, and no managed `Ft8LibInterop`/`IFt8NativeInterop` surface is required for it.

#### Scenario: Export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_extract_llrs_at` SHALL be resolvable via the platform's native-library loading mechanism on Windows, Linux, and macOS without error

#### Scenario: Extraction at a real candidate's own grid position round-trips

- **WHEN** `ft8_extract_llrs_at` is called with a real capture's PCM and the `(freq_hz, dt)` `ft8_decode_all` itself reported for one of that capture's candidates
- **THEN** it SHALL return `0` and 174 finite log-likelihood values, and the resolved lattice position SHALL be the same `(freq_offset, freq_sub, time_offset, time_sub)` quadruple that candidate already occupies

#### Scenario: A malformed PCM buffer is rejected

- **WHEN** `ft8_extract_llrs_at` is called with `pcm_len` not equal to the expected sample count
- **THEN** it SHALL return `-1` without writing to `out_llr174`

#### Scenario: A position outside the valid passband is rejected, not silently clamped

- **WHEN** `ft8_extract_llrs_at` is called with a `freq_hz` that resolves to a frequency bin outside `[0, num_bins)` for the waterfall built from the supplied PCM
- **THEN** it SHALL return `-3` without writing to `out_llr174`, rather than clamping to the nearest in-range bin

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this change lands
- **THEN** it SHALL contain no call to `ft8_extract_llrs_at` outside of test code and QA harnesses

#### Scenario: Existing exports are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260041` build
- **THEN** every previously-exported symbol SHALL be present with an unchanged signature, and `ft8_extract_llrs_at` SHALL be the only addition

---

### Requirement: Diagnostic coherent-LLR P/Invoke entry point (Phase 1 — shipped 2026-08-21, shim `20260043`; underlying native behaviour corrected under Phase B, shim `20260044`, no signature change)

`Ft8LibInterop` SHALL expose a managed method (e.g. `CoherentLlrAt`) that calls the native `ft8_coherent_llr_at` function via P/Invoke, taking the cycle's PCM buffer and a candidate's *existing, unrefined* grid `(freq_idx, time_idx)` and returning 174 coherent LLRs. `IFt8NativeInterop` SHALL add a corresponding method so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL, matching the existing pattern used for `RefineCandidate` and `ExtractLlrsAt`. This method SHALL be reachable only from test code and the Phase 1 gate harness (`r2_ber_grid.py`) — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it, and it SHALL NOT itself call `RefineCandidate`/`ft8_refine_candidate` (design.md D1). Phase B changes the values this method's underlying native call returns (design.md D8/D9's origin and fusion corrections) but not this method's signature, its `IFt8NativeInterop` surface, or any of the scenarios below.

#### Scenario: CoherentLlrAt is exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_coherent_llr_at` SHALL be resolvable via the `DllImport` / `NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: CoherentLlrAt returns 174 LLRs for a known-truth signal at its existing grid position

- **WHEN** `Ft8LibInterop.CoherentLlrAt` is called with a PCM buffer and the existing grid `(freq_idx, time_idx)` for a known candidate — no refinement step involved
- **THEN** the method SHALL return 174 coherent LLRs without throwing, and without any internal call to `RefineCandidate`

#### Scenario: IFt8NativeInterop.CoherentLlrAt is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `CoherentLlrAt` calls
- **THEN** calling it with a representative PCM buffer and grid position SHALL record the arguments without loading the native DLL

#### Scenario: No production call site invokes CoherentLlrAt

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after Phase 1 lands
- **THEN** it SHALL contain no call to `CoherentLlrAt` or `ft8_coherent_llr_at` outside of test code and the Phase 1 gate harness

---

### Requirement: Diagnostic LDPC-decode-from-LLRs native export (Phase B, Amendment 1 — shipped 2026-08-22, shim `20260044`)

The shim SHALL export a native function, `ft8_ldpc_decode_llrs(llr174, max_iters, osd_depth, out_a91, out_ldpc_errors, out_path, out_crc_ok)`, that decodes a caller-supplied 174-element raw (pre-normalisation) LLR vector through production's own decode sequence and reports whether it yields a CRC-valid message, so that a diagnostic LLR vector (from `ft8_extract_llrs_at` or `ft8_coherent_llr_at`) can be converted into a CRC-verified decode count rather than a modelled BER-threshold crossing. It SHALL, in order: (1) copy the caller's vector into a local buffer, and SHALL NOT modify the caller's own buffer, since `bp_decode` writes through its argument; (2) apply the same zero-variance degenerate guard `ftx_normalize_logl` itself requires, returning a negative code without normalising if the guard trips; (3) apply `ftx_normalize_logl` to the copy — mandatory, since without this step the export would measure LLR scale rather than LLR quality and any comparison between two differently-scaled extractions would be void; (4) save the normalised vector for the OSD fallback, exactly as the production sequence does; (5) run `bp_decode`; (6) pack to a 91-bit payload+CRC and compare the extracted and computed CRC-14; (7) if and only if the CRC fails and `osd_depth >= 0`, run the OSD fallback exactly as production does (including its existing two-feature accept/reject gate) and re-check the CRC, reporting via `out_path` which of BP or OSD produced the accepted result, or that neither did. The function SHALL NOT un-`static` `ftx_normalize_logl` or `osd_decode`, SHALL NOT move `osd_decode`, and SHALL NOT duplicate the CRC or normalisation arithmetic anywhere outside `decode.c` — it SHALL call the existing `static` functions from within `decode.c`, with only a thin wrapper in `ft8_shim.c`, the same two-file pattern `ftx_extract_likelihood_at`/`ft8_extract_llrs_at` already established. It SHALL be reachable only from test code and QA harnesses invoking it directly via the platform's native-library loading mechanism (e.g. Python `ctypes`) — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it, and no managed `Ft8LibInterop`/`IFt8NativeInterop` surface is required for it (design.md D10, following `n1-extract-llrs-at-position`'s own precedent for a diagnostic-only, test/harness-only export).

#### Scenario: Export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_ldpc_decode_llrs` SHALL be resolvable via the platform's native-library loading mechanism on Windows, Linux, and macOS without error

#### Scenario: A known-good codeword decodes cleanly (B4-a, positive control)

- **WHEN** `ft8_ldpc_decode_llrs` is called with the exact codeword LLRs (`+1`/`-1` scaled, no noise) for a known encoded message
- **THEN** `out_crc_ok` SHALL be `1` and the recovered `out_a91` payload SHALL match the encoded message bit-for-bit

#### Scenario: Pure Gaussian noise never decodes (B4-b, negative control)

- **WHEN** `ft8_ldpc_decode_llrs` is called with pure Gaussian-noise LLRs, fixed seed, across 20 independent trials
- **THEN** `out_crc_ok` SHALL be `0` on all 20 trials — a probe that reports success on noise reports success on anything, so this bar is load-bearing, not advisory

#### Scenario: The caller's LLR buffer is never modified (B4-c)

- **WHEN** `ft8_ldpc_decode_llrs` is called and returns
- **THEN** the caller's `llr174` buffer SHALL be byte-identical to its value immediately before the call, since `bp_decode` writes through its argument and this export copies before calling it

#### Scenario: A zero-variance input is rejected, not crashed on (B4-d)

- **WHEN** `ft8_ldpc_decode_llrs` is called with an `llr174` vector of zero variance
- **THEN** it SHALL return a negative code, SHALL NOT call `ftx_normalize_logl` (which would divide by zero), and SHALL NOT crash or produce NaN output

#### Scenario: Agreement with the production decoder on real audio meets the floor (B4-e, the only scenario with known ground truth)

- **WHEN** `ft8_ldpc_decode_llrs` is fed the `ft8_extract_llrs_at` output, at the grid candidate's own position, for rows that `ft8_decode_all` itself decoded live on real audio
- **THEN** `out_crc_ok == 1` SHALL hold for at least 90% of those rows, and the recovered message text SHALL match production's own decode for every row where it does — this bar is a floor (production searches candidates; this export is handed one position, so 100% agreement is not expected), and a result below the floor SHALL be reported as a stop condition, not averaged away

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this change lands
- **THEN** it SHALL contain no call to `ft8_ldpc_decode_llrs` outside of test code and QA harnesses

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260043` build, and `decode.c`'s existing functions are diffed against their pre-change source
- **THEN** every previously-exported symbol SHALL be present with an unchanged signature, `ft8_ldpc_decode_llrs` SHALL be the only new export this Requirement adds, and the diff on every existing `decode.c` function SHALL be zero

---

### Requirement: Diagnostic SNR-terms native export and P/Invoke entry point (Amendment 2, corrected in full by Amendment 3 — shipped 2026-08-22, shim `20260045`, following arm B-dt-A's ROW 2 firing)

The shim SHALL export a native function, `ft8_get_last_snr_terms(out_signal_db, out_local_noise_db, capacity)`, that returns the two per-decode terms of the SNR formula `snr = signal_db - local_noise_db - 26.5f` (`ft8_shim.c:1473-1474`) for every decode returned by the most recent `ft8_decode_all` call on the calling thread, so that a measured collapse in reported SNR (mean reported-minus-true SNR of `-11.9..-14.6 dB` on affected decodes, stable `+0.5..+1.0 dB` on WSJT-X across the same audio) can be localised to one of its two otherwise-unobservable terms rather than remaining an assertion. `out_signal_db[i]`/`out_local_noise_db[i]` SHALL correspond to `results[i]` from that same `ft8_decode_all` call — index-aligned, same order, same count. Either output pointer MAY be `NULL` to request only the other array; if both are `NULL`, the function SHALL write nothing and SHALL return the count it would have written. The function SHALL return `-1` if `capacity < 0`. The export SHALL be read-only: it SHALL NOT alter control flow, ordering, or any value already computed for `FT8Result` — it exposes the `signal_db`/`local_noise_db` locals already computed at `ft8_shim.c:1450-1474`, it does not add a second, independent computation of them. `Ft8LibInterop` SHALL expose a corresponding managed method (e.g. `GetLastSnrTerms`) via P/Invoke, matching the existing `GetLastCandidateCounts`/`GetLastLlrStats` parallel-array diagnostic-getter pattern (unlike `ft8_ldpc_decode_llrs`, which per design.md D10 gets no C# binding — this export does, per the amendment's own §4). `IFt8NativeInterop` SHALL add a corresponding method so a `FakeInterop` implementation can record the call without loading the native DLL, matching the existing pattern for `GetLastCandidateCounts`/`GetLastLlrStats`/`CoherentLlrAt`.

#### Scenario: Export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_get_last_snr_terms` SHALL be resolvable via the `DllImport`/`NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: Arrays are index-aligned with the decode results from the same call (AC-N3)

- **WHEN** `ft8_get_last_snr_terms` is called immediately after an `ft8_decode_all` call that returned `n` decodes, with `capacity >= n`
- **THEN** the function SHALL return exactly `n`, and `out_signal_db[i]`/`out_local_noise_db[i]` SHALL correspond to `results[i]` for every `i` in `[0, n)`

#### Scenario: The two terms reconstruct the reported SNR within the int-rounding quantum (AC-N2)

- **WHEN** `ft8_get_last_snr_terms` is called after a decode and its two arrays are compared against the corresponding `FT8Result.snr` value
- **THEN** `abs((signal_db[i] - local_noise_db[i] - 26.5) - snr[i])` SHALL be `<= 0.5 + 1e-3` for every decode `i` — the `+1e-3` is a float-representation allowance for the `(int)roundf` quantum, not a loosening of the criterion (resolved against the readout quantum, HK-021(o))

#### Scenario: Capacity is honoured exactly, including the both-NULL and negative-capacity cases (AC-N4)

- **WHEN** `ft8_get_last_snr_terms` is called with `capacity` values of `0`, `1`, and `count-1` (on a cycle with `count >= 3`, since `count-1` is degenerate below that), with both pointers non-`NULL`, with one pointer `NULL`, with both pointers `NULL`, and with a negative `capacity`
- **THEN** the function SHALL write exactly `capacity` entries and return `capacity` for each non-negative case with no overrun; SHALL write nothing and return the count it would have written when both output pointers are `NULL`; and SHALL return `-1` without writing anything when `capacity < 0`

#### Scenario: The export is read-only and changes no decode-path value (AC-N1)

- **WHEN** a binary built with this export is replayed against the same audio as the pre-Amendment-2 archived Phase B binary (`a3d32b78...` win / `13d9799d...` linux, or the equivalent committed working-tree binary, `7ed8b0c`), for at least 200 contiguous cycles on every platform rebuilt
- **THEN** every decode-output field SHALL be byte-for-byte identical between the two binaries — zero differences — since this export only reads values `ft8_decode_all` already computed and writes them to TLS storage, it does not participate in decode control flow

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this Amendment lands
- **THEN** it SHALL contain no call to `GetLastSnrTerms`/`ft8_get_last_snr_terms` outside of test code and QA harnesses

#### Scenario: `IFt8NativeInterop.GetLastSnrTerms` is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `GetLastSnrTerms` calls
- **THEN** calling it with a representative `maxDecoded` value SHALL record the call and return a deterministic fake result without loading the native DLL

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260044` build, and `ft8_shim.c`'s existing decode-path logic (beyond the two-line TLS write this export adds) is diffed against its pre-change source
- **THEN** every previously-exported symbol (all fifteen) SHALL be present with an unchanged signature, `ft8_get_last_snr_terms` SHALL be the only new export this Requirement adds, and the diff on every existing decode-path computation SHALL be zero

---

### Requirement: Diagnostic 12-bit hash-path sizing getters and P/Invoke entry points (Phase 1 — shipped 2026-08-30, shim `20260047`)

The shim SHALL export three native functions — `ft8_get_h12_displaying_count()`,
`ft8_get_h12_ambiguous_count()`, `ft8_get_h12_divergent_count()` — each returning the corresponding
process-lifetime cumulative count defined by the `hashed-callsign-resolution` capability's
"Observable 12-bit hash-path unique-match sizing" Requirement. `Ft8LibInterop` SHALL expose
corresponding managed methods (`GetH12DisplayingCount`, `GetH12AmbiguousCount`,
`GetH12DivergentCount`) via P/Invoke, matching the existing `GetHashTableRejectCount` diagnostic-
getter pattern. `IFt8NativeInterop` SHALL add corresponding methods so that test doubles can supply
deterministic fixed values without loading the native DLL.

#### Scenario: All three getters are exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbols `ft8_get_h12_displaying_count`, `ft8_get_h12_ambiguous_count`, and
  `ft8_get_h12_divergent_count` SHALL each be resolvable via the platform's native-library loading
  mechanism on Windows, Linux, and macOS without error

#### Scenario: Reading the counts has no side effects

- **WHEN** any of the three managed getters is called, at any point during or after a session
- **THEN** the call SHALL return the current cumulative value
- **AND** SHALL NOT reset any count, alter the hash table's contents, or affect subsequent decode
  behaviour in any way

#### Scenario: A per-cycle log line records all three counts together

- **WHEN** a decode cycle completes
- **THEN** the daemon's per-cycle log line SHALL record all three counts' current cumulative
  values, labelled `h12Displaying`, `h12Ambiguous`, and `h12Divergent`, explicitly as
  process-lifetime cumulative (not per-cycle deltas), even when all three are zero

#### Scenario: IFt8NativeInterop's three methods are callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that returns fixed values for the
  three new methods
- **THEN** calling each SHALL return its configured fixed value without loading the native DLL

---

### Requirement: Diagnostic 12-bit hash-path per-code cluster table native export (Phase 2 — Amendment 2, shipped 2026-08-30, shim `20260048`)

The shim SHALL export one native function, `ft8_get_h12_by_code(displaying, ambiguous, divergent,
capacity, out_of_range)`, copying the complete 4,096-row per-code table defined by the
`hashed-callsign-resolution` capability's "Observable 12-bit hash-path per-code cluster identity"
Requirement into caller-supplied buffers, and writing the code-width-violation count into
`out_of_range`. It SHALL return the code-space size (4,096) on success, and `-1` if `capacity` is
less than the code-space size or if any pointer argument, `out_of_range` included, is `NULL` — a
caller MUST check for `-1` rather than assume success. **This export SHALL NOT be added to
`IFt8NativeInterop`, and SHALL get no `Ft8LibInterop` P/Invoke binding, no `Ft8NativeInteropAdapter`
method, no `Ft8Decoder` wrapper, and no test-double stub in any existing `IFt8NativeInterop`
implementer** — its only intended consumer is a measurement harness driving the native library
directly (e.g. via Python `ctypes`), following the precedent this capability already established
for `ft8_ldpc_decode_llrs` (a diagnostic-only export with no managed binding, `r2-coherent-llr-
instrument` Decision D10).

#### Scenario: The export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_get_h12_by_code` SHALL be resolvable via the platform's native-library
  loading mechanism on Windows, Linux, and macOS without error

#### Scenario: A capacity smaller than the code space is rejected, not partially filled

- **WHEN** `ft8_get_h12_by_code` is called with `capacity` less than 4,096
- **THEN** the function SHALL return `-1` and SHALL NOT write to any output buffer

#### Scenario: A NULL pointer argument, including out_of_range, is rejected

- **WHEN** `ft8_get_h12_by_code` is called with any of its five pointer arguments `NULL`
- **THEN** the function SHALL return `-1` and SHALL NOT write to any output buffer

#### Scenario: A successful call copies the full table and the violation count

- **WHEN** `ft8_get_h12_by_code` is called with `capacity >= 4096` and all five pointers non-`NULL`
- **THEN** the function SHALL return `4096`, SHALL write exactly 4,096 entries to each of the three
  count buffers, and SHALL write the current code-width-violation count to `out_of_range`

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable
  from `DecodeAll`) is inspected after Phase 2 lands
- **THEN** it SHALL contain no call to `ft8_get_h12_by_code` outside of QA measurement harnesses

#### Scenario: No managed binding exists for the export

- **WHEN** `IFt8NativeInterop.cs`, `Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`,
  and every existing `IFt8NativeInterop` implementer are inspected after Phase 2 lands
- **THEN** none of them SHALL reference `ft8_get_h12_by_code`, `GetH12ByCode`, or any equivalent
  managed name — this is a deliberate scope boundary (design.md Decision D5), not an omission to be
  filled in later

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260047` build,
  and `ft8_shim.c`'s existing decode-path logic (beyond the additive table-write inside the
  existing, unchanged emission-site guard) is diffed against its pre-Phase-2 source
- **THEN** every previously-exported symbol (all nineteen) SHALL be present with an unchanged
  signature, `ft8_get_h12_by_code` SHALL be the only new export this Requirement adds, and the diff
  on every existing decode-path computation SHALL be zero

---

### Requirement: Diagnostic 12-bit suppression-count native export and P/Invoke entry point (shipped 2026-09-01, shim `20260049`)

The shim SHALL export a read-only getter, `ft8_get_h12_suppressed_count`, returning the
process-lifetime count of decodes whose 12-bit-hash-resolved callsign was withheld because its
probe chain held two or more matching entries. It SHALL be bound in managed code as
`IFt8NativeInterop.GetH12SuppressedCount()`, following the three existing 12-bit sizing getters'
own pattern.

Reading the count SHALL have no side effects on decode behaviour, on the hash table, or on any
other counter.

#### Scenario: The getter is exported by all three platform binaries

- **WHEN** the shim is built for Windows x64, Linux x64 and macOS ARM64
- **THEN** `ft8_get_h12_suppressed_count` SHALL be present and resolvable in each binary

⚠️ The Windows build carries an explicit export list; the Linux build relies on default symbol
visibility. A symbol omitted from that list builds and links clean on Linux and fails only on
Windows, only at runtime, on `P/Invoke` resolution. This scenario is not satisfied by a successful
Linux build.

#### Scenario: Reading the count has no side effects

- **WHEN** `GetH12SuppressedCount()` is called any number of times between decode cycles
- **THEN** subsequent decode results SHALL be identical to those produced without the calls
- **AND** the returned value SHALL be unchanged by the act of reading it

#### Scenario: The method is callable on a fake implementation

- **WHEN** a test double implements `IFt8NativeInterop`
- **THEN** it SHALL be able to satisfy `GetH12SuppressedCount()` with a fixed value, without
  loading the native library

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the shim is rebuilt at `20260049`
- **THEN** every previously exported symbol SHALL remain present with an unchanged signature
- **AND** the only decode-output difference from `20260048` SHALL be the callsign token of messages
  whose 12-bit hash reference resolved against an ambiguous probe chain

