## 1. Requirements & Documentation

- [ ] 1.1 Add **FR-056** (PTT-over-CAT and serial RTS/DTR keying) to `REQUIREMENTS.md`, amending the FR-045/`IRadioConnection` "no PTT" note; add the corresponding version-history row (FR-052–FR-055 were claimed by `gridtracker-udp-reporting`, merged 2026-07-12 — FR-056 is the next free number as of this correction)
- [ ] 1.2 Update `IRadioConnection`'s XML doc comment (currently states "No mode-set, PTT, or other rig-altering commands are defined here") to reflect the amendment

## 2. Abstractions

- [ ] 2.1 Add `Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default)` to `IRadioConnection` in `OpenWSFZ.Abstractions`
- [ ] 2.2 Add `ICatPttGate` interface to `OpenWSFZ.Abstractions` with a single member `Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default)`
- [ ] 2.3 Add `PttConfig` record to `OpenWSFZ.Abstractions` (`Method`, `SerialPort`, `SerialLine`, `LeadTimeMs`, `TailTimeMs`, `WatchdogTimeoutMs`, defaults per design.md Decision 6)
- [ ] 2.4 Add `Ptt` property of type `PttConfig` (defaulting to a disabled/VOX instance) to `AppConfig`, as a sibling of `Cat`, not nested inside it
- [ ] 2.5 Verify round-trip: existing config files without a `ptt` key deserialise without error and `Ptt.Method` is `"AudioVox"`

## 3. Serial Port RTS/DTR Support

- [ ] 3.1 Add `bool RtsEnable { get; set; }` and `bool DtrEnable { get; set; }` to `ISerialPort` in `OpenWSFZ.Rig.Internal`
- [ ] 3.2 Implement both properties as pass-throughs in `SerialPortWrapper` (mirroring `System.IO.Ports.SerialPort.RtsEnable`/`DtrEnable`)
- [ ] 3.3 Add a fake `ISerialPort` test double exposing settable/observable `RtsEnable`/`DtrEnable` state (extending or alongside whatever fake already backs the existing `SerialCatConnection` unit tests)

## 4. SerialCatConnection — PTT commands

- [ ] 4.1 Implement `SetPttAsync(true)` — writes `TX;\r` to the serial port, no read-back
- [ ] 4.2 Implement `SetPttAsync(false)` — writes `RX;\r` to the serial port, no read-back
- [ ] 4.3 Update the class's XML doc comment to document the new PTT commands alongside the existing frequency commands

## 5. RigctldConnection — PTT commands

- [ ] 5.1 Implement `SetPttAsync(true)` — sends `\set_ptt 1\n`, reads and validates the `RPRT 0` acknowledgement, throws `InvalidOperationException` (with raw response) on any other reply
- [ ] 5.2 Implement `SetPttAsync(false)` — sends `\set_ptt 0\n`, same acknowledgement handling
- [ ] 5.3 Update the class's XML doc comment to document the new PTT commands

## 6. CatPollingService — wire serialization

- [ ] 6.1 Add a private `SemaphoreSlim(1,1)` gate to `CatPollingService` guarding every call the poll loop makes to the shared `IRadioConnection`
- [ ] 6.2 Implement `CatPollingService`'s `ICatPttGate.SetPttAsync` by acquiring the same gate before calling `IRadioConnection.SetPttAsync`
- [ ] 6.3 `ICatPttGate.SetPttAsync` throws `InvalidOperationException` when `AppConfig.Cat.Enabled` is `false` or no connection has ever been established
- [ ] 6.4 Register `CatPollingService` as `ICatPttGate` in `Program.cs` DI wiring (alongside its existing `ICatTuner`/`ICatController` registrations)
- [ ] 6.5 Audit `OpenWSFZ.Daemon` and `OpenWSFZ.Rig` for any other holder of the shared `IRadioConnection` reference and remove/refactor it so `CatPollingService` remains the sole holder

## 7. Shared WASAPI playback extraction

- [ ] 7.1 Extract the WASAPI device-open/play/stop/dispose logic from `AudioOnlyPttController` into an internal `WasapiTxPlayer` helper (`WASAPI_SUPPORTED`-gated) exposing an async play-to-completion method and a stop method
- [ ] 7.2 Refactor `AudioOnlyPttController` to use `WasapiTxPlayer` internally
- [ ] 7.3 Run the full existing `AudioOnlyPttController` unit test suite unmodified against the refactored implementation — zero assertion changes permitted; any failure blocks proceeding to section 8

## 8. CatPttController

- [ ] 8.1 Implement `CatPttController : IPttController` in `OpenWSFZ.Daemon`, constructed with `ICatPttGate`, `IConfigStore`, and a logger
- [ ] 8.2 Implement `LoadAudio` (same contract as `AudioOnlyPttController`)
- [ ] 8.3 Implement `KeyDownAsync`: `ICatPttGate.SetPttAsync(true)` → wait `LeadTimeMs` → play via `WasapiTxPlayer` → await completion
- [ ] 8.4 Implement `KeyUpAsync`: stop playback → wait `TailTimeMs` → `ICatPttGate.SetPttAsync(false)`
- [ ] 8.5 Wrap the key-down/play/key-up sequence in a watchdog per section 10, and in try/finally so any exception still releases PTT
- [ ] 8.6 Implement `DisposeAsync` — force PTT release if asserted, release any audio device handle

## 9. SerialRtsDtrPttController

- [ ] 9.1 Implement `SerialRtsDtrPttController : IPttController` in `OpenWSFZ.Daemon`, opening its own `ISerialPort` from `AppConfig.Ptt.SerialPort`, independent of any `CatPollingService`/`ICatPttGate` instance
- [ ] 9.2 Implement `LoadAudio` (same contract)
- [ ] 9.3 Implement `KeyDownAsync`: assert the configured line (`RtsEnable`/`DtrEnable` per `AppConfig.Ptt.SerialLine`) → wait `LeadTimeMs` → play via `WasapiTxPlayer` → await completion
- [ ] 9.4 Implement `KeyUpAsync`: stop playback → wait `TailTimeMs` → de-assert the configured line
- [ ] 9.5 Port-open failure in `KeyDownAsync` throws rather than silently skipping PTT assertion
- [ ] 9.6 Wrap the sequence in a watchdog per section 10, and in try/finally so any exception still de-asserts the line
- [ ] 9.7 Implement `DisposeAsync` — force line de-assertion if asserted, close and dispose the serial port

## 10. Failsafe watchdog

- [ ] 10.1 Implement a small shared watchdog helper (timer + forced-release callback) usable by both `CatPttController` and `SerialRtsDtrPttController`, parameterised by `WatchdogTimeoutMs`
- [ ] 10.2 Watchdog logs at Error (including elapsed hold duration) and forces release, bypassing `TailTimeMs`, when it fires
- [ ] 10.3 Watchdog is cancelled the instant `KeyUpAsync` begins its release step

## 11. DI Wiring

- [ ] 11.1 In `Program.cs`, replace the current `#if WASAPI_SUPPORTED` / `#else` two-way `IPttController` registration with a three-way switch on `configStore.Current.Ptt.Method` (falling back to `AudioOnlyPttController`/`NullPttController` per existing platform gating when the method is unrecognised or when `WASAPI_SUPPORTED` is undefined)
- [ ] 11.2 Register `CatPollingService` as `ICatPttGate` (see 6.4)
- [ ] 11.3 Verify `QsoAnswererService`/`QsoCallerService` construction is unaffected (they already resolve `IPttController` by interface, not concrete type)

## 12. Tests

- [ ] 12.1 `SerialCatConnection` PTT unit tests: `SetPttAsync(true)` writes `TX;\r`, `SetPttAsync(false)` writes `RX;\r` — prefix `CatTx-Ptt:`
- [ ] 12.2 `RigctldConnection` PTT unit tests: `SetPttAsync(true/false)` sends the right command and validates the RPRT ack, non-`RPRT 0` ack throws — prefix `CatTx-Ptt:`
- [ ] 12.3 `CatPollingService` gate unit tests (mock `IRadioConnection`): concurrent poll + PTT calls never overlap on the mock (assert via a re-entrancy guard in the mock), `ICatPttGate.SetPttAsync` throws when CAT disabled — prefix `CatTx-Ptt:`
- [ ] 12.4 `PttConfig`/`AppConfig` schema tests: missing `ptt` key defaults correctly, unknown `Method`/`SerialLine` fall back with a logged Warning — prefix `CatTx-Ptt:`
- [ ] 12.5 `ISerialPort`/`SerialPortWrapper` RTS/DTR unit tests using the fake serial port — prefix `CatTx-Ptt:`
- [ ] 12.6 `CatPttController` unit tests (mock `ICatPttGate` + injected playback override, same seam pattern as `AudioOnlyPttController`'s test constructor): key order (PTT before audio, audio-stop before PTT release), lead/tail timing honoured, PTT released on playback exception, `DisposeAsync` releases if asserted — prefix `CatTx-Ptt:`
- [ ] 12.7 `SerialRtsDtrPttController` unit tests (fake `ISerialPort` + injected playback override): same key-order/timing/exception/dispose coverage as 12.6, plus Rts-vs-Dtr line selection and port-open-failure-throws — prefix `CatTx-Ptt:`
- [ ] 12.8 Watchdog unit tests: forces release and logs Error when `KeyUpAsync` never arrives; does not fire when release happens in time; fires even when playback itself hangs — prefix `CatTx-Ptt:`
- [ ] 12.9 DI wiring test: each `Ptt.Method` value resolves the expected concrete `IPttController` — prefix `CatTx-Ptt:`

## 13. Documentation

- [ ] 13.1 Author `hardware-acceptance.md` in this change directory, modelled on `openspec/changes/archive/2026-06-03-p16-cat-control/hardware-acceptance.md`, covering CAT-command PTT, serial RTS/DTR PTT, the failsafe watchdog, and a confirmed two-way QSO (see section 14)
- [ ] 13.2 Update `docs/cat-control-operator-guide.md` with the new `ptt` config block and a short explanation of when to choose each method

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

- [ ] 16.1 With either PTT method configured and `QsoAnswererService` or `QsoCallerService` active, complete one full, genuine over-the-air FT8 QSO with another station
- [ ] 16.2 Confirm the completed QSO is written correctly to `ADIF.log`
- [ ] 16.3 Document the confirmed QSO (date, band, partner call — Q-prefix or otherwise per NFR-021) in `hardware-acceptance.md` as the R3 evidence artefact

## 17. Housekeeping

- [ ] 17.1 Commit all changes with `feat(cat-tx-ptt): key the transmitter via CAT command or serial RTS/DTR`
- [ ] 17.2 Push and confirm CI green (all quality gates, including G9 version governance — this is user-facing, VERSION bump required)
- [ ] 17.3 Open PR to `main`; request QA gate review
