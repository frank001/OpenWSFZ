## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260041`** (r1b-sync-refiner-instrument-correction: the shim's diagnostic-only `ft8_refine_candidate` export gains two new out-parameters exposing its internal coarse/fine time-search decomposition — no existing production entry point's ABI, struct layout, or decode behaviour changes; `DecodeAll`, `GetLastPassCounts`, and `SetDecodeParams` all remain byte-for-byte unchanged; the constant is bumped purely so the startup ABI check catches a binary built without the two new out-parameters; version history: 20260040 = r1-sync-refiner-instrument-validation (diagnostic-only per-candidate coherent sync-refinement export added, no production call site, no ABI change to any existing entry point), 20260039 = r0-reproducible-native-build (shim rebuilt from a fully vendored, version-controlled source tree with byte-identical decode behaviour to the prior `20260038` build — no ABI, struct layout, or decode-behaviour change), 20260038 = g2-hash-table-sizing-and-candidate-passband (`HASH_TABLE_SIZE` 256→4096; candidate passband `[200,3000)`→`[140,3030)`, held pending Captain's re-sequencing ruling — only the hash-table-sizing half is shipped as of `20260038`), 20260031 = f-001-hashed-callsign-resolution, 20260030 = decoder-settings-page runtime-configurable OSD gate parameters, 20260029 = D-009 K_MIN_SCORE_PASS2 raised 1→10, 20260028 = D-009 OSD nhard gate, 20260025 = OSD fallback + 50-iter BP, 20260021 = H6 AP decode hiscall offset fix; ⚠️ the intermediate bumps between `20260032` and `20260037` are not documented here — out of scope, tracked as a separate spec-sync backlog item, not backfilled retroactively). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260041`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

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
