## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260040`** (r1-sync-refiner-instrument-validation: the shim adds a new diagnostic-only per-candidate sync-refinement export (`ft8_refine_candidate`) alongside R0's fully vendored source tree; no existing production entry point's ABI, struct layout, or decode behaviour changes — `DecodeAll`, `GetLastPassCounts`, and `SetDecodeParams` all remain byte-for-byte unchanged; the constant is bumped purely so the startup ABI check catches a binary built without the new export; version history: 20260039 = r0-reproducible-native-build (shim rebuilt from a fully vendored, version-controlled source tree with byte-identical decode behaviour to the prior `20260038` build — no ABI, struct layout, or decode-behaviour change), 20260038 = g2-hash-table-sizing-and-candidate-passband (`HASH_TABLE_SIZE` 256→4096; candidate passband `[200,3000)`→`[140,3030)`, held pending Captain's re-sequencing ruling — only the hash-table-sizing half is shipped as of `20260038`), 20260031 = f-001-hashed-callsign-resolution, 20260030 = decoder-settings-page runtime-configurable OSD gate parameters, 20260029 = D-009 K_MIN_SCORE_PASS2 raised 1→10, 20260028 = D-009 OSD nhard gate, 20260025 = OSD fallback + 50-iter BP, 20260021 = H6 AP decode hiscall offset fix; ⚠️ the intermediate bumps between `20260032` and `20260037` are not documented here — out of scope for this change, tracked as a separate spec-sync backlog item, not backfilled retroactively). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260040`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

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

### Requirement: Diagnostic refine-candidate P/Invoke entry point

`Ft8LibInterop` SHALL expose a managed method (e.g. `RefineCandidate`) that calls the native `ft8_refine_candidate` function via P/Invoke, taking the cycle's PCM buffer and a coarse `(freq_hz, time_offset)` candidate position and returning the refined `(Δf, Δt)` and sync quality score. `IFt8NativeInterop` SHALL add a corresponding method so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL, matching the existing pattern used for `SetDecodeParams`. This method SHALL be reachable only from test code and the validation harness introduced by this change — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it.

#### Scenario: RefineCandidate is exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_refine_candidate` SHALL be resolvable via the `DllImport` / `NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: RefineCandidate returns a refined offset for a known-truth signal

- **WHEN** `Ft8LibInterop.RefineCandidate` is called with a synthetic-oracle-generated PCM buffer and the coarse candidate position `ftx_find_candidates()` would report for it
- **THEN** the method SHALL return a refined `(Δf, Δt)` and a sync quality score without throwing

#### Scenario: IFt8NativeInterop.RefineCandidate is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `RefineCandidate` calls
- **THEN** calling it with a representative PCM buffer and coarse position SHALL record the arguments without loading the native DLL

#### Scenario: No production call site invokes RefineCandidate

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this change lands
- **THEN** it SHALL contain no call to `RefineCandidate` or `ft8_refine_candidate` outside of test code and the validation harness
