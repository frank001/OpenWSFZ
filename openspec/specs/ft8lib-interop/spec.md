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

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260042`** (n1-extract-llrs-at-position: the shim gains a new diagnostic-only native export, `ft8_extract_llrs_at`, that runs the existing `ft8_extract_likelihood()` extraction path at a caller-supplied `(freq_hz, time_offset_s)` position instead of a candidate `ftx_find_candidates()` already located — no existing production entry point's ABI, struct layout, or decode behaviour changes; `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and `RefineCandidate` all remain byte-for-byte unchanged; the constant is bumped purely so the startup ABI check catches a binary built without the new export; version history: 20260041 = r1b-sync-refiner-instrument-correction (`ft8_refine_candidate` gains its coarse/fine time-search decomposition out-parameters), 20260040 = r1-sync-refiner-instrument-validation (diagnostic-only per-candidate coherent sync-refinement export added, no production call site), 20260039 = r0-reproducible-native-build (shim rebuilt from a fully vendored, version-controlled source tree with byte-identical decode behaviour to the prior `20260038` build), 20260038 = g2-hash-table-sizing-and-candidate-passband, 20260031 = f-001-hashed-callsign-resolution, 20260030 = decoder-settings-page runtime-configurable OSD gate parameters, 20260029 = D-009 K_MIN_SCORE_PASS2 raised 1→10, 20260028 = D-009 OSD nhard gate, 20260025 = OSD fallback + 50-iter BP, 20260021 = H6 AP decode hiscall offset fix; ⚠️ the intermediate bumps between `20260032` and `20260037` remain undocumented here, an existing tracked spec-sync backlog item, not introduced or expanded by this change). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260042`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

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

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, SNR formula, and the pass count (**2**). `BUILD.md` SHALL document the exact compiler commands required to reproduce each binary. The binaries SHALL be built from the **`FT8_SHIM_VERSION = 20260030`** shim (decoder-settings-page: `ft8_set_decode_params` entry point for runtime-configurable OSD gate parameters).

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

