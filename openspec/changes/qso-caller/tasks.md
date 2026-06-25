## 1. Abstractions — new types

- [x] 1.1 Create `src/OpenWSFZ.Abstractions/CallerState.cs` — `CallerState` enum with values `Idle`, `TxCq`, `WaitAnswer`, `TxReport`, `WaitRr73`, `TxRr73`, `QsoComplete`
- [x] 1.2 Create `src/OpenWSFZ.Abstractions/TxRole.cs` — `TxRole` enum with values `Answerer = 0`, `Caller = 1`
- [x] 1.3 Create `src/OpenWSFZ.Abstractions/CallerPartnerSelectMode.cs` — `CallerPartnerSelectMode` enum with values `First = 0`, `None = 1`
- [x] 1.4 Create `src/OpenWSFZ.Abstractions/QsoRole.cs` — `QsoRole` enum with values `Answerer`, `Caller`
- [x] 1.5 Update `src/OpenWSFZ.Abstractions/IQsoController.cs`: add `QsoRole Role { get; }` property and `Task SelectResponderAsync(string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)` method
- [x] 1.6 Update `src/OpenWSFZ.Abstractions/TxConfig.cs`: add `Role` (`TxRole`, default `Answerer`) and `CallerPartnerSelect` (`CallerPartnerSelectMode`, default `First`) properties; extend `[JsonConstructor]` with default parameters for both new fields

## 2. Abstractions — QsoAnswererService stubs

- [x] 2.1 Update `QsoAnswererService`: add `QsoRole Role => QsoRole.Answerer;` property implementation
- [x] 2.2 Update `QsoAnswererService`: add `SelectResponderAsync` no-op implementation returning `Task.CompletedTask`
- [x] 2.3 Verify `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings

## 3. Backend — QsoCallerService

- [x] 3.1 Create `src/OpenWSFZ.Daemon/QsoCallerService.cs` implementing `BackgroundService, IQsoController` with `QsoRole Role => QsoRole.Caller;`
- [x] 3.2 Implement `QsoCallerService` constructor accepting the same DI dependencies as `QsoAnswererService` (plus the `ChannelReader<DecodeBatch>`, `IConfigStore`, `IPttController`, `ITxEventBus`, `AdifLogWriter`, `AudioOffsetEventBus`, `ILogger<QsoCallerService>`, `IApConstraintSink?`) plus an internal test constructor with `watchdogDurationOverride`
- [x] 3.3 Implement `ExecuteAsync`: loop over `ReadNextBatchAsync` (same dual-channel wakeup logic as answerer); dispatch to `ProcessBatchAsync`
- [x] 3.4 Implement `ProcessBatchAsync`: switch on `_callerState` dispatching to `HandleIdleAsync`, `HandleWaitAnswerAsync`, `HandleWaitRr73Async`
- [x] 3.5 Implement `HandleIdleAsync`: guard on `tx.AutoAnswer`, callsign/grid validation, transmit `CQ {callsign} {grid}`, advance to `WaitAnswer`; apply HoldTxFreq TX frequency logic (identical to answerer's `ExecuteTxAnswerAsync` frequency block)
- [x] 3.6 Implement `HandleWaitAnswerAsync` — `First` path: scan batch for `{our_callsign} {any_callsign} {grid}`, auto-select first match, call `ExecuteTxReportAsync`; `None` path: check pending-responder fields (phase + timeout guards), fire or skip; A-01 skip guard; retry/abort path
- [x] 3.7 Implement `ExecuteTxReportAsync(string partner, double frequencyHz, TxConfig tx, CancellationToken ct)`: set `_partner`, compose `{partner} {callsign} +00`, transmit, advance to `WaitRr73`, arm H6 AP constraints, reset watchdog
- [x] 3.8 Implement `HandleWaitRr73Async`: scan batch for `R+{nn}` or `R-{nn}` from partner to us → `ExecuteTxRr73Async`; detect partner working another station → abort; A-01 guard; retry path
- [x] 3.9 Implement `ExecuteTxRr73Async`: compose `{partner} {callsign} RR73`, transmit, advance to `QsoComplete`, write ADIF record, call `SafeAbortToIdleAsync`
- [x] 3.10 Implement `RetryOrAbortAsync` for `WaitAnswer` (retransmit CQ, not last message) — increment `_retryCount`, check against `tx.RetryCount`, retransmit CQ or abort with `"No response after {n} CQ retries"`
- [x] 3.11 Implement `SelectResponderAsync`: check state is `WaitAnswer`; lock and store `_pendingResponderCallsign` / `_pendingResponderFrequencyHz` / `_pendingResponderIsAPhase` / `_pendingResponderSetAt`; write wakeup batch; return
- [x] 3.12 Implement `AbortAsync`: cancel `_txCts`; call `KeyUpAsync`; set `_operatorAbortRequested`
- [x] 3.13 Implement `SafeAbortToIdleAsync`: clear pending-responder fields under lock, reset `_partner`, clear AP constraints, replace `_txCts`, call `KeyUpAsync`, save `AutoAnswer = false`, broadcast `txState` with `autoAnswerEnabled: false`
- [x] 3.14 Implement `IQsoController.State` property: map `CallerState` to nearest `QsoState` proxy per design.md D8; add XML comment referencing the rename deferred task
- [x] 3.15 Verify internal static helpers: `IsAPhase`, `RoundDownTo15s`, `TryParseMessage`, `IsSignalReport` — copy/reuse from answerer; `TryParseResponder(string msg, string ourCallsign, out string partner, out double freqHz)` is new

## 4. Backend — DI registration and txState wire protocol

- [x] 4.1 Update `src/OpenWSFZ.Web/ITxEventBus.cs`: add `role` parameter to `Publish` signature
- [x] 4.2 Update `src/OpenWSFZ.Web/TxEventBus.cs`: implement `role` parameter; pass role string (`"answerer"` / `"caller"`) to `WebSocketHub.BroadcastTxState`
- [x] 4.3 Update `src/OpenWSFZ.Web/WebSocketHub.cs` `BroadcastTxState`: add `role` parameter; include `"role"` field in the JSON payload
- [x] 4.4 Update all `_txEventBus.Publish(...)` call sites in `QsoAnswererService` to pass `role: "answerer"`
- [x] 4.5 Add `string Role` property to `TxStatusResponse` record in `OpenWSFZ.Web`; add to `AppJsonContext`
- [x] 4.6 Update all `TxStatusResponse` constructors / initialisers in `WebApp.cs` to populate `Role` from `controller.Role.ToString().ToLowerInvariant()`
- [x] 4.7 Add `SelectResponderRequest(Callsign, FrequencyHz, ResponseCycleStartUtc)` DTO to `AppJsonContext`
- [x] 4.8 Add `POST /api/v1/tx/select-responder` route handler in `WebApp.cs`: check role (405), check state (409), call `SelectResponderAsync`, return `TxStatusResponse`
- [x] 4.9 Update `OpenWSFZ.Daemon/Program.cs`: read `config.Tx?.Role` before DI build; conditionally register `QsoCallerService` (role = Caller) or `QsoAnswererService` (role = Answerer) as both `IQsoController` singleton and `IHostedService`
- [x] 4.10 Verify `dotnet build OpenWSFZ.slnx -c Release` — zero errors, zero warnings

## 5. Backend — tests

- [x] 5.1 Create `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` with `BuildIsolatedSut` helper (same pattern as `QsoAnswererServiceTests`)
- [x] 5.2 Test `TxCq`: armed service transmits `CQ {callsign} {grid}` on first batch and advances to `WaitAnswer`
- [x] 5.3 Test `WaitAnswer` — `First` mode: batch containing `{our_callsign} {partner} {grid}` triggers `TxReport`
- [x] 5.4 Test `WaitAnswer` — `None` mode: matching response in batch does NOT auto-advance
- [x] 5.5 Test `SelectResponderAsync` — correct phase fires on next A-phase batch; wrong phase skips; fires on correct phase following wrong-phase skip
- [x] 5.6 Test `SelectResponderAsync` — 60s timeout discards pending responder and logs warning
- [x] 5.7 Test `SelectResponderAsync` — abort clears pending responder, no TX fires after abort
- [x] 5.8 Test `HandleWaitRr73Async`: R+report triggers `TxRr73`
- [x] 5.9 Test `HandleWaitRr73Async`: partner working another station aborts with correct reason
- [x] 5.10 Test retry — `WaitAnswer`: no response → retransmit CQ; retry count exhausted → abort with `"No response after N CQ retries"`
- [x] 5.11 Test `WaitAnswer` A-01 guard: first empty cycle after entering `WaitAnswer` does not trigger retry
- [x] 5.12 Test supervised disarm: `SafeAbortToIdleAsync` saves `AutoAnswer = false`; `txState` event carries `autoAnswerEnabled: false`
- [x] 5.13 Test `IQsoController.Role == QsoRole.Caller` on the service instance
- [x] 5.14 Test `SelectResponderAsync` no-op on `QsoAnswererService`
- [x] 5.15 Add integration tests in `OpenWSFZ.Web.Tests`: `POST /tx/select-responder` → 200 (Caller, WaitAnswer); 405 (Answerer role); 409 (Caller but not WaitAnswer)
- [x] 5.16 Add Web.Tests: `GET /api/v1/tx/status` returns `role: "answerer"` when answerer is active; `role: "caller"` when caller is active
- [x] 5.17 Run `dotnet test OpenWSFZ.slnx -c Release` — all tests green

## 6. Frontend — JS API

- [ ] 6.1 Add `postTxSelectResponder(callsign, frequencyHz, responseCycleStartUtc)` function to `web/js/api.js`

## 7. Frontend — main.js logic

- [ ] 7.1 Update module-level state in `main.js`: add `currentTxRole = "answerer"` variable; update from `txState` events and initial `getTxStatus()` response
- [ ] 7.2 Update `renderMessageRows(partner, state, autoAnswerEnabled, role)`: branch on `role`; use caller templates (`CQ / +00 / RR73`) when `role === "caller"`, answerer templates otherwise
- [ ] 7.3 Update active-row state mapping in `renderMessageRows`: caller states `TxCq` → row 1, `TxReport` → row 2, `TxRr73` → row 3
- [ ] 7.4 Update `renderTxPanel(state, partner, autoAnswerEnabled, role)` signature; pass `role` from `txState` events and `getTxStatus()` response; fall back to `currentTxRole` when `role` absent
- [ ] 7.5 Add `decode-responder` class application in the decode-row render path: when `currentTxRole === "caller"` and the current state is `"WaitAnswer"` and `callerPartnerSelect === "None"`, apply `decode-responder` to rows matching `{our_callsign} {any_callsign} {grid}` pattern (first token === `txCallsign`)
- [ ] 7.6 Add `currentCallerPartnerSelect` module variable; populate from `getConfig()` response (`config.tx?.callerPartnerSelect ?? "First"`)
- [ ] 7.7 Add click handler on `decode-responder` rows: extract callsign (second token), `offsetHz`, `cqCycleStartUtc` from `row.dataset`; call `postTxSelectResponder`; apply 400 ms `inFlight` guard; call `renderTxPanel` on HTTP 200; swallow 409/405 with `console.warn`

## 8. Frontend — settings.js

- [ ] 8.1 Add `<select id="general-tx-role">` with options `Answerer` / `Caller` to the General tab in `web/index.html` (settings.html)
- [ ] 8.2 Add `<select id="general-caller-partner-select">` with options `First` / `None` inside a conditionally-shown fieldset below the TX Mode selector
- [ ] 8.3 Update `settings.js`: pre-fill `#general-tx-role` from `config.tx.role`; pre-fill `#general-caller-partner-select` from `config.tx.callerPartnerSelect`
- [ ] 8.4 Add show/hide logic in `settings.js`: `#general-caller-partner-select` and its label are hidden when `#general-tx-role = "Answerer"`; shown when `"Caller"` — applies on page load and on change event
- [ ] 8.5 Include `tx.role` and `tx.callerPartnerSelect` in the `POST /api/v1/config` save payload in `settings.js`
- [ ] 8.6 Add dirty-state tracking for `#general-tx-role` and `#general-caller-partner-select`
- [ ] 8.7 After a successful save where `tx.role` differs from the pre-load value, display a visible restart notice: "TX mode change saved. Restart the application for the change to take effect."

## 9. Frontend — CSS

- [ ] 9.1 Add `.decode-responder` rule to `web/css/app.css` — a warm green or teal accent colour; legible on the dark theme; clearly distinct from `.decode-cq` (amber) and `.decode-partner` (subdued red)

## 10. Verification

- [ ] 10.1 Build and run the application in Caller mode (`tx.role = "Caller"` in config); confirm TX panel shows caller message row templates
- [ ] 10.2 Confirm `#tx-msg-1` shows `"CQ {callsign} {grid}"` in Idle state; row 1 highlights on `TxCq` event
- [ ] 10.3 Confirm Settings → General shows TX Mode selector; Partner Selection appears only when Caller is selected; restart notice appears after saving a role change
- [ ] 10.4 Confirm Answerer mode is unaffected: run in Answerer mode, verify existing message rows and behaviour unchanged (regression check)
- [ ] 10.5 Run `dotnet test OpenWSFZ.slnx -c Release` — all tests green (expected: ~650+ passed including new qso-caller tests)
