## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. **Phase 1 of this change (native `ft8_coherent_llr_at`, not yet implemented — see this change's `tasks.md` §1-2/§5) SHALL advance the expected constant past the value in production use at the time this change was proposed (`20260042`, r0-reproducible-native-build lineage through `n1-extract-llrs-at-position`'s `ft8_extract_llrs_at` diagnostic export).** The exact new integer SHALL be assigned and recorded by the Developer session that implements Phase 1, per this project's own D4 discipline (assert a leg's binary against a pre-registered manifest, never infer it from a label) — no existing production entry point's ABI, struct layout, or decode behaviour SHALL change; `DecodeAll`, `GetLastPassCounts`, and `SetDecodeParams` all remain byte-for-byte unchanged. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms. **This change's own Phase 0 (shipped now) does not touch this requirement at all** — it calls only the pre-existing `ft8_extract_llrs_at` export at shim `20260042`, re-verified from disk (not merely inferred from a label) immediately before every run.

#### Scenario: Correct library passes the ABI self-test (Phase 1, once shipped)

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at Phase 1's own newly-assigned `FT8_SHIM_VERSION`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-Phase-1 library (20260042) fails fast with a clear error, once Phase 1 ships

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260042` (the pin this change's own Phase 0 harness ran against) after Phase 1's managed code expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

## ADDED Requirements

### Requirement: Diagnostic coherent-LLR P/Invoke entry point (Phase 1 — not yet implemented)

`Ft8LibInterop` SHALL expose a managed method (e.g. `CoherentLlrAt`) that calls the native `ft8_coherent_llr_at` function via P/Invoke, taking the cycle's PCM buffer and a candidate's *existing, unrefined* grid `(freq_idx, time_idx)` and returning 174 coherent LLRs. `IFt8NativeInterop` SHALL add a corresponding method so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL, matching the existing pattern used for `RefineCandidate` and `ExtractLlrsAt`. This method SHALL be reachable only from test code and the Phase 1 gate harness (the extension of this change's own `r2_ber_grid.py`) — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it, and it SHALL NOT itself call `RefineCandidate`/`ft8_refine_candidate` (design.md D1).

#### Scenario: CoherentLlrAt is exported by all three platform binaries, once Phase 1 ships

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
