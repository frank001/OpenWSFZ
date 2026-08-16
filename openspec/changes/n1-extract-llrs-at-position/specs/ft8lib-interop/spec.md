## MODIFIED Requirements

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

## ADDED Requirements

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
