## 1. Requirements & Documentation

- [x] 1.1 Add **FR-056** (PTT-over-CAT and serial RTS/DTR keying) to `REQUIREMENTS.md`, amending the FR-045/`IRadioConnection` "no PTT" note; add the corresponding version-history row (FR-052–FR-055 were claimed by `gridtracker-udp-reporting`, merged 2026-07-12 — FR-056 is the next free number as of this correction)
- [x] 1.2 Update `IRadioConnection`'s XML doc comment (currently states "No mode-set, PTT, or other rig-altering commands are defined here") to reflect the amendment

## 2. Abstractions

- [x] 2.1 Add `Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default)` to `IRadioConnection` in `OpenWSFZ.Abstractions`
- [x] 2.2 Add `ICatPttGate` interface to `OpenWSFZ.Abstractions` with a single member `Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default)`
- [x] 2.3 Add `PttConfig` record to `OpenWSFZ.Abstractions` (`Method`, `SerialPort`, `SerialLine`, `LeadTimeMs`, `TailTimeMs`, `WatchdogTimeoutMs`, defaults per design.md Decision 6)
- [x] 2.4 Add `Ptt` property of type `PttConfig` (defaulting to a disabled/VOX instance) to `AppConfig`, as a sibling of `Cat`, not nested inside it
- [x] 2.5 Verify round-trip: existing config files without a `ptt` key deserialise without error and `Ptt.Method` is `"AudioVox"`

## 3. Serial Port RTS/DTR Support

- [x] 3.1 Add `bool RtsEnable { get; set; }` and `bool DtrEnable { get; set; }` to `ISerialPort` in `OpenWSFZ.Rig.Internal`
- [x] 3.2 Implement both properties as pass-throughs in `SerialPortWrapper` (mirroring `System.IO.Ports.SerialPort.RtsEnable`/`DtrEnable`)
- [x] 3.3 Add a fake `ISerialPort` test double exposing settable/observable `RtsEnable`/`DtrEnable` state (extending or alongside whatever fake already backs the existing `SerialCatConnection` unit tests)

## 4. SerialCatConnection — PTT commands

- [x] 4.1 Implement `SetPttAsync(true)` — writes `TX;` to the serial port, no read-back (matches spec.md's literal scenario and the existing no-`\r` `SetDialFrequencyMhzAsync` set convention — see note below)
- [x] 4.2 Implement `SetPttAsync(false)` — writes `RX;` to the serial port, no read-back
- [x] 4.3 Update the class's XML doc comment to document the new PTT commands alongside the existing frequency commands

  > Note: this task's original wording said `TX;\r`/`RX;\r`, but `specs/cat-control/spec.md`'s scenario text (the authoritative contract) says exactly `TX;`/`RX;` with no `\r` — matching the existing no-`\r` convention already used by `SetDialFrequencyMhzAsync`'s `FA<Hz>;` (the `\r` is only used by the `FA;` read/probe command). Implemented per spec.md.

## 5. RigctldConnection — PTT commands

- [x] 5.1 Implement `SetPttAsync(true)` — sends `\set_ptt 1\n`, reads and validates the `RPRT 0` acknowledgement, throws `InvalidOperationException` (with raw response) on any other reply
- [x] 5.2 Implement `SetPttAsync(false)` — sends `\set_ptt 0\n`, same acknowledgement handling
- [x] 5.3 Update the class's XML doc comment to document the new PTT commands

## 6. CatPollingService — wire serialization

- [x] 6.1 Add a private `SemaphoreSlim(1,1)` gate to `CatPollingService` guarding every call the poll loop makes to the shared `IRadioConnection` (already existed as `_connectionLock`, added by the earlier frequency-management change for the same poll-vs-tune serialization purpose — reused rather than duplicated, per design.md Decision 1)
- [x] 6.2 Implement `CatPollingService`'s `ICatPttGate.SetPttAsync` by acquiring the same gate before calling `IRadioConnection.SetPttAsync`
- [x] 6.3 `ICatPttGate.SetPttAsync` throws `InvalidOperationException` when `AppConfig.Cat.Enabled` is `false` or no connection has ever been established
- [x] 6.4 Register `CatPollingService` as `ICatPttGate` in `Program.cs` DI wiring (alongside its existing `ICatTuner`/`ICatController` registrations)
- [x] 6.5 Audit `OpenWSFZ.Daemon` and `OpenWSFZ.Rig` for any other holder of the shared `IRadioConnection` reference and remove/refactor it so `CatPollingService` remains the sole holder — audited (grep for `IRadioConnection` across both assemblies): only `CatPollingService.cs` (owner), `SerialCatConnection.cs`/`RigctldConnection.cs` (implementers), and `RigModelFactory.cs` (factory, returns an unconnected instance to `CatPollingService` only) reference it; no other consumer exists, so no refactor was needed

## 7. Shared WASAPI playback extraction

- [x] 7.1 Extract the WASAPI device-open/play/stop/dispose logic from `AudioOnlyPttController` into an internal `WasapiTxPlayer` helper (`WASAPI_SUPPORTED`-gated) exposing an async play-to-completion method and a stop method
- [x] 7.2 Refactor `AudioOnlyPttController` to use `WasapiTxPlayer` internally
- [x] 7.3 Run the full existing `AudioOnlyPttController` unit test suite unmodified against the refactored implementation — zero assertion changes permitted; any failure blocks proceeding to section 8

  > **Defect found and fixed while establishing the pre-refactor baseline:** `tests/OpenWSFZ.Daemon.Tests/OpenWSFZ.Daemon.Tests.csproj` never defined the `WASAPI_SUPPORTED` conditional-compilation symbol that `AudioOnlyPttControllerTests.cs` (and its host class) require — the whole `#if WASAPI_SUPPORTED` test file silently compiled to 0 tests, on every platform including Windows CI, since it was authored. Added the same OS-conditional `DefineConstants` block `OpenWSFZ.Daemon.csproj` already has. With the suite actually running for the first time, `DisposeAsync_CalledTwice_SecondCallIsNoOp` genuinely failed (`ObjectDisposedException` from a disposed `SemaphoreSlim`) — a real, pre-existing, previously-invisible bug, not a regression from this change. Fixed via the same `Interlocked.Exchange` double-dispose guard `CatPollingService` already uses (see `WasapiTxPlayer.DisposeAsync`). Suite now runs 7/7 green against the refactored implementation with zero assertion changes.

## 8. CatPttController

- [x] 8.1 Implement `CatPttController : IPttController` in `OpenWSFZ.Daemon`, constructed with `ICatPttGate`, `IConfigStore`, and a logger
- [x] 8.2 Implement `LoadAudio` (same contract as `AudioOnlyPttController`)
- [x] 8.3 Implement `KeyDownAsync`: `ICatPttGate.SetPttAsync(true)` → wait `LeadTimeMs` → play via `WasapiTxPlayer` → await completion
- [x] 8.4 Implement `KeyUpAsync`: stop playback → wait `TailTimeMs` → `ICatPttGate.SetPttAsync(false)`
- [x] 8.5 Wrap the key-down/play/key-up sequence in a watchdog per section 10, and in try/finally so any exception still releases PTT (implemented as try/catch-release-rethrow around the lead-wait+play steps, since a plain finally would incorrectly release on the normal-completion path too — the invariant "any exception releases PTT" holds either way)
- [x] 8.6 Implement `DisposeAsync` — force PTT release if asserted, release any audio device handle

## 9. SerialRtsDtrPttController

- [x] 9.1 Implement `SerialRtsDtrPttController : IPttController` in `OpenWSFZ.Daemon`, opening its own `ISerialPort` from `AppConfig.Ptt.SerialPort`, independent of any `CatPollingService`/`ICatPttGate` instance (opened lazily on first `KeyDownAsync`, kept open for the controller's lifetime; baud rate is a hardcoded conventional default since RTS/DTR-only keying exchanges no data and `PttConfig` has no `baudRate` field)
- [x] 9.2 Implement `LoadAudio` (same contract)
- [x] 9.3 Implement `KeyDownAsync`: assert the configured line (`RtsEnable`/`DtrEnable` per `AppConfig.Ptt.SerialLine`) → wait `LeadTimeMs` → play via `WasapiTxPlayer` → await completion
- [x] 9.4 Implement `KeyUpAsync`: stop playback → wait `TailTimeMs` → de-assert the configured line (the exact line that was asserted at key-down time, remembered separately, so a mid-transmission config change can never de-assert the wrong line and leave the real one stuck high)
- [x] 9.5 Port-open failure in `KeyDownAsync` throws rather than silently skipping PTT assertion
- [x] 9.6 Wrap the sequence in a watchdog per section 10, and in try/finally so any exception still de-asserts the line
- [x] 9.7 Implement `DisposeAsync` — force line de-assertion if asserted, close and dispose the serial port

## 10. Failsafe watchdog

- [x] 10.1 Implement a small shared watchdog helper (timer + forced-release callback) usable by both `CatPttController` and `SerialRtsDtrPttController`, parameterised by `WatchdogTimeoutMs` (`PttWatchdog`, built ahead of sections 8/9 since both depend on it; deliberately has no WASAPI dependency so it is unit-testable standalone)
- [x] 10.2 Watchdog logs at Error (including elapsed hold duration) and forces release, bypassing `TailTimeMs`, when it fires
- [x] 10.3 Watchdog is cancelled the instant `KeyUpAsync` begins its release step (`Disarm()`, called first thing in both controllers' `KeyUpAsync`)

## 11. DI Wiring

- [x] 11.1 In `Program.cs`, replace the current `#if WASAPI_SUPPORTED` / `#else` two-way `IPttController` registration with a three-way switch on `configStore.Current.Ptt.Method` (falling back to `AudioOnlyPttController`/`NullPttController` per existing platform gating when the method is unrecognised or when `WASAPI_SUPPORTED` is undefined)
- [x] 11.2 Register `CatPollingService` as `ICatPttGate` (see 6.4 — already done there)
- [x] 11.3 Verify `QsoAnswererService`/`QsoCallerService` construction is unaffected (they already resolve `IPttController` by interface, not concrete type) — confirmed by inspection, no changes needed; `dotnet build` of `OpenWSFZ.Daemon` succeeds with 0 warnings/errors

## 12. Tests

- [x] 12.1 `SerialCatConnection` PTT unit tests: `SetPttAsync(true)` writes `TX;`, `SetPttAsync(false)` writes `RX;` (no `\r` — see the section 4 implementation note) — prefix `CatTx-Ptt:`. 41/41 `OpenWSFZ.Rig.Tests` green.
- [x] 12.2 `RigctldConnection` PTT unit tests: `SetPttAsync(true/false)` sends the right command and validates the RPRT ack, non-`RPRT 0` ack throws — prefix `CatTx-Ptt:`
- [x] 12.3 `CatPollingService` gate unit tests (mock `IRadioConnection`): concurrent poll + PTT calls never overlap on the mock (assert via a re-entrancy guard in the mock), `ICatPttGate.SetPttAsync` throws when CAT disabled or no connection established, dispatches once connected — prefix `CatTx-Ptt:`. 10/10 `CatPollingServiceTests` green.
- [x] 12.4 `PttConfig`/`AppConfig` schema tests: missing `ptt` key defaults correctly (`PttConfigTests.cs`, task 2.5) — prefix `CatTx-Ptt:` used where FR-number-style prefixes aren't already established. Unknown-`Method`/`SerialLine`-fallback-with-Warning coverage lives where that logic actually runs: `Method` in `PttControllerSelectorTests` (12.9, since selection is DI-time behaviour, not a config-schema concern) and `SerialLine` in `SerialRtsDtrPttControllerTests` (12.7, since only the controller knows which physical line was requested).
- [x] 12.5 `ISerialPort`/`SerialPortWrapper` RTS/DTR unit tests using the fake serial port — `FakeSerialPortTests.cs` (8/8 green), validating the double's independent, observable Rts/Dtr state that `SerialRtsDtrPttControllerTests` builds on. `SerialPortWrapper` itself wraps real hardware and has no dedicated test, consistent with the project's existing pattern (no test file exists for it today either) — prefix `CatTx-Ptt:`
- [x] 12.6 `CatPttController` unit tests (mock `ICatPttGate` + injected playback override, same seam pattern as `AudioOnlyPttController`'s test constructor): key order (PTT before audio), lead/tail timing honoured, PTT released before an exception from playback propagates, `DisposeAsync` releases if asserted, watchdog force-release integration — prefix `CatTx-Ptt:`. 10/10 green.
- [x] 12.7 `SerialRtsDtrPttController` unit tests (fake `ISerialPort` + injected playback override): same key-order/timing/exception/dispose coverage as 12.6, plus Rts-vs-Dtr line selection, unrecognised-`SerialLine`-falls-back-to-Rts-with-Warning, port-open-failure-throws, and CAT-independence — prefix `CatTx-Ptt:`. 13/13 green.
- [x] 12.8 Watchdog unit tests (`PttWatchdogTests.cs`, no WASAPI/Windows dependency — pure timer logic): forces release and logs Error when `KeyUpAsync` never arrives; does not fire when `Disarm()` happens in time; fires even when the guarded operation hangs; re-arming replaces the pending timer — prefix `CatTx-Ptt:`. 4/4 green.
- [x] 12.9 DI wiring test: each `Ptt.Method` value resolves the expected concrete `IPttController` — extracted the selection logic from `Program.cs`'s inline switch into a new pure, directly-testable `PttControllerSelector.Resolve(method, logger)` (returns `PttControllerKind`) so this doesn't require spinning up the whole daemon host via `WebApplicationFactory`; `PttControllerSelectorTests.cs`, 5/5 green — prefix `CatTx-Ptt:`

## 13. Documentation

- [x] 13.1 Author `hardware-acceptance.md` in this change directory, modelled on `openspec/changes/archive/2026-06-03-p16-cat-control/hardware-acceptance.md`, covering CAT-command PTT, serial RTS/DTR PTT, the failsafe watchdog, and a confirmed two-way QSO (see section 14) — already drafted during proposal generation; verified against the final implementation (log line text, config field names/defaults) with no discrepancies found, so no edits were needed
- [x] 13.2 Update `docs/cat-control-operator-guide.md` with the new `ptt` config block and a short explanation of when to choose each method — added a "PTT (Transmit Keying) Configuration" section (method comparison table, field reference, JSON examples, watchdog safety note), corrected the now-stale "never sends frequency-set... or PTT commands" claim, and updated "Known Limitations"

## 14. Acceptance Gate — CAT-command PTT (manual, hardware required)

- [ ] 14.1 Set `ptt.method = "CatCommand"`; confirm the rig keys (TX LED / RF output) within `leadTimeMs` of a transmission starting and unkeys within `tailTimeMs` of it ending
- [ ] 14.2 Confirm the CAT status badge and frequency polling continue to update correctly during and immediately after a TX cycle (proves Decision 1's serialization works under real load, not just in mocks)
- [ ] 14.3 Force a watchdog trip (e.g. inject a stalled playback build or a very small `watchdogTimeoutMs`) and confirm the rig unkeys automatically and an Error is logged
- [ ] 14.4 Confirm no unexpected mode-set, frequency-set, or other rig-altering command appears in the log or on the rig display during the session

## 15. Acceptance Gate — Serial RTS/DTR PTT (manual, hardware required)

- [ ] 15.1 Set `ptt.method = "SerialRtsDtr"` with `ptt.serialPort` on a different port than any CAT connection in use; confirm the rig keys/unkeys correctly via the RTS line
- [ ] 15.2 Repeat 15.1 with `ptt.serialLine = "Dtr"` on hardware wired for DTR PTT (or confirm the line-selection logic behaves correctly if only one line is available to test)
- [ ] 15.3 Confirm PTT keys/unkeys correctly with `cat.enabled = false` (proves independence from any CAT connection)
- [ ] 15.4 Force a watchdog trip and confirm the line de-asserts automatically

## 16. Acceptance Gate — Confirmed two-way QSO (release gate R3)

- [x] 16.1 With either PTT method configured and `QsoAnswererService` or `QsoCallerService` active, complete one full, genuine over-the-air FT8 QSO with another station — two completed 2026-07-12 with `SerialRtsDtr`; see `hardware-acceptance.md` §16.1/16.3
- [x] 16.2 Confirm the completed QSO is written correctly to `ADIF.log` — confirmed for both QSOs; one pre-existing, non-blocking `GRIDSQUARE`/`TIME_ON` gap noted and traced (not caused by this change) — see `hardware-acceptance.md` §16.2
- [x] 16.3 Document the confirmed QSO (date, band, partner call — Q-prefix or otherwise per NFR-021) in `hardware-acceptance.md` as the R3 evidence artefact — done, real callsigns withheld per NFR-021 (see file)

## 17. Settings UI for PTT Configuration

Added 2026-07-12 (design.md's Decision 6 amendment) — the Captain hit a wall during hardware
acceptance: no way to see or change `ptt.method` without hand-editing `config.json`, which is also
how the null-`ptt` guard defect went undiagnosed for a full session. See design.md's amendment note
for the full safety analysis behind the semaphore requirement in 17.5/17.6 — do not skip it.

- [x] 17.1 Add **FR-057** (Settings-page PTT configuration UI) to `REQUIREMENTS.md`, following the
  FR-056 entry's format; add the corresponding version-history row
- [x] 17.2 **Safety fix first, before any UI work**: add a private `SemaphoreSlim(1,1)` to
  `CatPttController` and `SerialRtsDtrPttController`, acquired for the entire `KeyDownAsync` →
  `KeyUpAsync` critical section of each (design.md amendment note, safety-critical finding). Add a
  test to each controller's existing suite proving two concurrent `KeyDownAsync` callers serialise
  (the second's PTT-assert does not begin until the first's `KeyUpAsync` completes) rather than
  interleave. Run the full existing `CatPttControllerTests.cs`/`SerialRtsDtrPttControllerTests.cs`
  suites unmodified afterward — zero assertion changes permitted, matching the discipline task 7.3
  already established for the `WasapiTxPlayer` extraction
- [x] 17.3 `WebApp.cs`: add `POST /api/v1/ptt/test`. Resolve the currently-running `IPttController`
  and `IQsoController` from DI (same pattern as the existing `/api/v1/tx/*` endpoints). Reject with
  409 Conflict (clear message: "a QSO is currently transmitting") if `IQsoController.Keying` is
  `true`. Reject with 409 if the running `Ptt.Method` is `"AudioVox"` (nothing to test — OpenWSFZ
  never asserts PTT itself in that mode; message should say so, not just "cannot test"). Otherwise:
  call `LoadAudio` with a short (~200–300 ms) buffer of silence (zero-amplitude samples — a real
  audible test tone was explicitly rejected, see design.md), then `KeyDownAsync` immediately
  followed by `KeyUpAsync`. Return `{ "result": "pass" }` on success; on any exception, return
  `{ "result": "error", "message": "<exception message>" }` with HTTP 200 (this is an expected,
  handleable outcome, not a server error) — do not let the exception propagate as a 500
- [x] 17.4 `web/css/app.css`: add a layout rule so `#cat-settings` and the new PTT fieldset (17.5)
  sit side-by-side on wide viewports and stack vertically on narrow ones — reuse whatever breakpoint
  the rest of `settings.html` already uses for responsive stacking (check existing media queries in
  `app.css` before inventing a new breakpoint value). Add `.ptt-test-badge` with three modifier
  classes — `.ptt-test-pass` (reuse `--color-success`, same visual treatment as `.cat-connected`),
  `.ptt-test-error` (reuse `--color-danger`, same as `.cat-error`), `.ptt-test-idle` (default/empty
  state, shown before Test has been clicked) — mirroring `.cat-status-badge`'s existing structure
  exactly rather than inventing a new badge pattern
- [x] 17.5 `web/settings.html`: split the current single `#cat-settings` fieldset's visual container
  so "CAT rig connection" (existing markup, unchanged) and a new "PTT Config" fieldset sit side by
  side per the Captain's layout sketch. New fieldset fields: `ptt-method` (select: AudioVox /
  CatCommand / SerialRtsDtr), `ptt-serial-port` + `ptt-serial-line` (shown only when method =
  SerialRtsDtr — reuse the existing generic `/api/v1/serial/ports` list and the `input-with-action` +
  "↺ Refresh" pattern `cat-serial-port`/`cat-serial-refresh` already establish), `ptt-lead-time-ms`,
  `ptt-tail-time-ms`, `ptt-watchdog-timeout-ms` (shown for CatCommand and SerialRtsDtr, hidden for
  AudioVox — nothing to configure), and a `ptt-test-btn` ("Test") + `ptt-test-badge` result badge
  pair using the `input-with-action` layout. Disable/hide the Test button when the *live* (last
  GET-loaded, not the currently-selected-but-unsaved) method is AudioVox, with a hint explaining a
  Save + daemon restart is required before Test reflects a newly-selected CAT/serial method (`ptt`
  is not hot-reloaded — see the already-corrected operator-guide.md note)
- [x] 17.6 `web/js/settings.js`: element refs for all new controls (17.5); show/hide handler on
  `ptt-method`'s `change` event mirroring `cat-rig-model`'s existing SerialCat/RigCtld show/hide
  logic exactly; `load()` populates the new fields from `GET /api/v1/config`'s `ptt` object; the
  `postConfig({...})` payload (currently omits `ptt` entirely per the now-superseded part of
  design.md Decision 6) now includes a `ptt` key built from the form; `ptt-test-btn` click handler
  POSTs to `/api/v1/ptt/test`, shows a transient "Testing…" badge state, then renders
  `.ptt-test-pass`/`.ptt-test-error` with the result (and the error message, if any) on response
- [x] 17.7 Web/UI test coverage (this project's established pattern for `settings.js`/`settings.html`
  — check for existing Playwright/JS test scaffolding before deciding the mechanism; if none exists,
  a `WebApplicationFactory`-based integration test against `POST /api/v1/ptt/test` covering the
  409-while-keying case, the 409-on-AudioVox case, and the pass/error response shape is the minimum
  bar, matching `ConfigApiNullGuardTests.cs`'s style)
- [x] 17.8 Update `docs/cat-control-operator-guide.md`'s new PTT section (added by task 13.2) to
  state a Settings-page UI now exists, remove/replace the now-stale "no Settings-page UI for `ptt`"
  line, and add a short paragraph on the Test button's exact semantics (software-only pulse, does
  not confirm physical keying, requires Save + restart to reflect a changed method)
- [x] 17.9 Before/after screenshots of the Radio hardware tab (per this project's standing
  before/after screenshot ordering rule — capture "before" against the current single-fieldset
  layout *first*, then implement, then capture "after")

## 18. Defect fix — `KeyUpAsync` never called after a normal transmission

Added 2026-07-12 (dev-task `dev-tasks/2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md`) —
found during the first real hardware-acceptance attempt (Gate 16): `QsoCallerService.TransmitAsync`
and `QsoAnswererService`'s equivalent transmit helper called `KeyDownAsync` but never followed it
with `KeyUpAsync` on the normal-completion path — only the four abort paths called it. Every real TX
cycle therefore relied entirely on `PttWatchdog`'s 20 s failsafe to ever release PTT, holding the rig
keyed (and the daemon's own receiver blind) ~7+ seconds into the next FT8 RX slot on every single
transmission — critical, merge-blocking, and the direct cause of the failed HB9HYO QSO logged in
`logs/openswfz-20260712T152156Z.log`. No spec text changes required — this is a caller-side
implementation defect, not a behaviour change to `qso-caller`/`qso-answerer`.

- [x] 18.1 `QsoCallerService.TransmitAsync` (`:930-990`): call `_pttController.KeyUpAsync(CancellationToken.None)`
  inside the existing `finally` block, immediately after `KeyDownAsync`, before `_keying = false` /
  `PublishKeyingTransition()` — release happens on every exit path (normal return, exception, or
  cancellation), and the keying broadcast still reflects "still keyed" for the brief `TailTimeMs`
  window while release is in progress
- [x] 18.2 `QsoAnswererService`'s equivalent transmit helper (`:1166-1225`): identical fix, same
  ordering, same `CancellationToken.None` rationale (release must still happen even when the token
  that was passed to `KeyDownAsync` is already cancelled — both controllers' `KeyUpAsync` bodies
  already tolerate being called when nothing is asserted, so this is safe unconditionally)
- [x] 18.3 `IPttController.cs`: rewrote the stale doc comment (previously described the contract in
  purely `AudioOnlyPttController`/WASAPI terms) to state plainly that every `KeyDownAsync` call MUST
  be paired with a `KeyUpAsync` call in the caller's normal-completion path, not only on abort, and to
  explain why the two controllers this change added do not share `AudioOnlyPttController`'s
  "skipping `KeyUpAsync` is harmless" property
- [x] 18.4 Regression tests, both call order and cancellation-path coverage:
  - `QsoCallerServiceTests.cs`: `TransmitAsync_NormalCompletion_KeyUpImmediatelyFollowsKeyDown_NoInterveningStateTransition`
    (asserts `KeyUpAsync` immediately follows `KeyDownAsync` in a hand-rolled cross-substitute call-order
    recorder — NSubstitute's `Received.InOrder` does not reliably interleave calls across two different
    substitute instances, confirmed empirically — and that the `WaitAnswer` state broadcast comes after
    both) and `TransmitAsync_CancelledMidKeyDown_StillCallsKeyUpAsync` (a `KeyDownAsync` that only
    completes on cancellation still reaches the `finally` block and calls `KeyUpAsync` exactly once,
    isolated from `AbortAsync`'s own separate cleanup call by cancelling the token `ExecuteAsync` was
    started with directly rather than going through the abort API)
  - `QsoAnswererServiceTests.cs`: the same two cases, adapted to the shared-fixture (`IAsyncLifetime`)
    pattern already used throughout that file
  - Updated the pre-existing `GracefulStopAsync_WhileTransmittingCq_DoesNotInterruptThenReturnsToIdle`
    assertion from `Received(1).KeyUpAsync` to `Received(2)` — one call now comes from
    `TransmitAsync`'s own finally block (the fix), a second from `SafeAbortToIdleAsync`'s pre-existing
    unconditional cleanup call; both are individually safe no-ops on a controller with nothing
    asserted, so two calls is the correct total, not a regression
  - `PttWatchdogTests.cs`, `CatPttControllerTests.cs`, `SerialRtsDtrPttControllerTests.cs` re-run
    unmodified, zero assertion changes — this fix is entirely on the `QsoCallerService`/
    `QsoAnswererService` caller side
- [x] 18.5 Full suite green: `OpenWSFZ.Daemon.Tests` 448/448 (run twice standalone to rule out an
  unrelated pre-existing timing flake in `PendingTarget_LateStart_IsDeferred_ThenFiresNextCycle`,
  which fails only under full-solution parallel load and passes in isolation — not touched by this
  fix); full solution `dotnet test` otherwise green. `openspec validate --strict --all`: 54/54,
  unchanged
- [ ] 18.6 **Hardware acceptance Gates 14–16 (section 14/15/16 above) must be re-attempted from
  scratch** — none of the keying observed before this fix is valid evidence for those gates, Gate 16
  specifically (the HB9HYO session was the discovery evidence for this defect, not a pass).
  **Partially re-attempted 2026-07-12:** Gate 16 (16.1–16.3) now ticked with two real, completed,
  post-fix QSOs as evidence; Gate 15.1's key/unkey claim is evidenced too (port-distinctness half
  still needs operator confirmation). **Still fully outstanding:** Gate 14 (CAT-command PTT — not
  exercised at all on this day) and Gates 15.2–15.4 (DTR line, CAT-disabled independence, forced
  watchdog trip post-fix). See `hardware-acceptance.md`'s 2026-07-12 evidence note for the full
  breakdown. This item stays unchecked until Gate 14 and the rest of Gate 15 are actually run.

## 19. Housekeeping

- [x] 19.1 Commit all changes with `feat(cat-tx-ptt): key the transmitter via CAT command or serial RTS/DTR`
- [x] 19.2 Push and confirm CI green (all quality gates, including G9 version governance)
- [x] 19.3 Open PR to `main`; request QA gate review

**Status as of 2026-07-12: 19.1–19.3 complete.** `PR #71` merged to `main` at `1ab245b`
(`feat(cat-tx-ptt): key the transmitter via CAT command or serial RTS/DTR`, branch
`feat/cat-tx-ptt`). All three platforms (`ubuntu-latest`, `windows-latest`, `macos-latest`)
passed `Build & Test`; `Gate G9 — Version governance` passed without requiring a `VERSION`
bump at merge time — per this project's established convention (see `REQUIREMENTS.md`
changelog rows 1.27–1.31), the mandatory bump for a user-facing change is enforced at
**archive**, not at merge, and `cat-tx-ptt` has not been archived (correctly — §14/§15/§18.6
below remain outstanding real-hardware gates). QA independently re-verified the merged fix
for `dev-tasks/2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md` post-merge: full suite
1174/1174 (after clearing an unrelated stray daemon process contaminating 3 tests),
`openspec validate --strict --all` 54/54, and the raw session logs
(`openswfz-20260712T162611Z.log`, `...T164315Z.log`) directly confirm every `KeyDown` is
followed by a `KeyUp` with zero watchdog-forced releases. **Do not tick §18.6 or archive this
change until Gate 14 and Gates 15.2–15.4 are genuinely run on real hardware** — merging this
PR closed out the code-review/regression-test side of the defect, not the hardware-acceptance
side.
