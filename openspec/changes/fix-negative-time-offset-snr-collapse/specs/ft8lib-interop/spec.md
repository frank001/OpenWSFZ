## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260046`** (fix-negative-time-offset-snr-collapse: `ft8_decode_all`'s `signal_db` loop derives the waterfall-block-to-symbol-index mapping from a candidate's `time_offset` **clamped** to a non-negative floor, instead of the true, unclamped value — for any candidate whose sync position precedes the decode window (`time_offset < 0`, an ordinary outcome of `ftx_find_candidates()`'s `-10..+19` search range), every one of the 79 averaged samples is read from the wrong tone bin, under-reporting SNR by roughly 15–20 dB; confirmed mechanically (`qa/rr-study/2026-08-22-1454-...-b-dt-c3-results.md`, a 17.4 dB step co-located exactly with the sign change, ~210× the largest deficit a benign "signal partly outside the window" explanation could produce there). The fix derives the symbol index from the unclamped `time_offset`, matching `ft8_lib`'s own out-of-range convention (`patched/ft8/decode.c:160,226`), and correspondingly narrows the loop's own upper bound so no symbol index can run past `FT8_NN`; `DecodeAll`'s ABI, `FT8Result` struct layout, and every other existing exported symbol remain byte-for-byte unchanged — this is a behaviour-bearing rebuild, not an ABI break. ⚠️ Version history immediately prior to this entry is **repaired here, not merely extended**: the base spec this text was copied from still read `20260042` despite `main`'s actual `FT8_SHIM_VERSION` already standing at `20260045` at the time this change was drafted (the pre-existing "spec-sync backlog" this same paragraph has flagged since `20260042`) — bumps `20260043` = r2-coherent-llr-instrument Phase 1 (diagnostic-only `ft8_coherent_llr_at`, no production call site), `20260044` = r2-coherent-llr-instrument Phase B + Amendment 1 (B1 origin-conversion fix and B2 fusion-scale fix to `ft8_coherent_llr_at`, both diagnostic-only; B4 adds diagnostic-only `ft8_ldpc_decode_llrs`), `20260045` = r2-coherent-llr-instrument Amendment 2 corrected by Amendment 3 (widens `ftx_ldpc_decode_llrs`'s degenerate-variance guard; adds the diagnostic-only `ft8_get_last_snr_terms` getter) are now recorded rather than left undocumented. Full prior history (`20260041` and earlier) is unchanged and carries forward from the version this text supersedes: 20260041 = r1b-sync-refiner-instrument-correction (`ft8_refine_candidate` gains its coarse/fine time-search decomposition out-parameters), 20260040 = r1-sync-refiner-instrument-validation (diagnostic-only per-candidate coherent sync-refinement export added, no production call site), 20260039 = r0-reproducible-native-build (shim rebuilt from a fully vendored, version-controlled source tree with byte-identical decode behaviour to the prior `20260038` build), 20260038 = g2-hash-table-sizing-and-candidate-passband, 20260031 = f-001-hashed-callsign-resolution, 20260030 = decoder-settings-page runtime-configurable OSD gate parameters, 20260029 = D-009 K_MIN_SCORE_PASS2 raised 1→10, 20260028 = D-009 OSD nhard gate, 20260025 = OSD fallback + 50-iter BP, 20260021 = H6 AP decode hiscall offset fix; ⚠️ the intermediate bumps between `20260032` and `20260037` remain undocumented, an existing tracked spec-sync backlog item, not introduced or expanded by this change. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260046`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

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

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib` submodule at the pinned commit, SHALL be committed for all three reference platforms:

| Platform | Path | Declared in csproj |
|---|---|---|
| Windows x64 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `<Content CopyToOutputDirectory="Always" Link="libft8.dll" />` |
| Linux x64 | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | `<Content CopyToOutputDirectory="Always" Link="libft8.so" />` |
| macOS ARM64 | `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` | `<Content CopyToOutputDirectory="Always" Link="libft8.dylib" />` |

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, SNR formula, and the pass count (**2**). `BUILD.md` SHALL document the exact compiler commands required to reproduce each binary. The binaries SHALL be built from the **`FT8_SHIM_VERSION = 20260046`** shim (fix-negative-time-offset-snr-collapse: corrects the `signal_db` loop's symbol-index derivation for candidates with `time_offset < 0`; see the ABI self-test requirement above for the full history this advances from — this requirement's own version reference was found several versions stale at drafting time, `20260030`, and is repaired here as part of the same edit).

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output directory alongside the daemon executable
