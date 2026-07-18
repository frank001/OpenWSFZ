## 1. IQsoController — LastTxMessage contract

- [ ] 1.1 Add `string? LastTxMessage { get; }` to `IQsoController`
  (`src/OpenWSFZ.Abstractions/IQsoController.cs`), documented analogously to the existing
  `State`/`Partner`/`Keying` properties.
- [ ] 1.2 Add `public string? LastTxMessage => ActiveController.LastTxMessage;` to
  `QsoControllerRouter` (`src/OpenWSFZ.Daemon/QsoControllerRouter.cs`), placed alongside the
  existing `State`/`Partner`/`Keying` delegating properties.

## 2. QsoCallerService — persist the real transmitted text

- [ ] 2.1 Add `private string? _lastTxMessage;` field, mirroring `QsoAnswererService`'s existing
  one; implement `public string? LastTxMessage => _lastTxMessage;`.
- [ ] 2.2 Set `_lastTxMessage` in `ExecuteTxReportAsync` to the composed `reportMessage` (same
  string passed to `TransmitAsync`).
- [ ] 2.3 Set `_lastTxMessage` in `RetryOrAbortAsync`'s `WaitAnswer` retry branch (CQ
  retransmission) and its `WaitRr73` retry branch (report retransmission), each to the exact
  string passed to `TransmitAsync` in that branch.
- [ ] 2.4 Set `_lastTxMessage` in `ExecuteTxRr73Async` to the composed `rr73Message`.
- [ ] 2.5 Reset `_lastTxMessage = null` in `HandleIdleAsync`'s session-init block, alongside the
  existing `_rstRcvd`/`_rstSent` resets.

## 3. QsoAnswererService — expose the existing LastTxMessage

- [ ] 3.1 Implement `public string? LastTxMessage => _lastTxMessage;` — the field itself already
  exists and is already set at every TX-composition site; no change to its assignment sites.

## 4. TxStatusResponse and txState WebSocket event

- [ ] 4.1 Add `string? LastTxMessage = null` to the `TxStatusResponse` record
  (`src/OpenWSFZ.Web/AppJsonContext.cs`).
- [ ] 4.2 Update every `TxStatusResponse` construction site in `WebApp.cs` (`GET /api/v1/tx/status`,
  `POST /api/v1/tx/enable`, `POST /api/v1/tx/disable`, `POST /api/v1/tx/abort`,
  `POST /api/v1/tx/select-responder`) to pass the resolved controller's `LastTxMessage`, matching
  how `Role`/`Keying` are already threaded through each of these sites.
- [ ] 4.3 Add `string? LastTxMessage = null` to `WsTxStateMessage`
  (`src/OpenWSFZ.Web/AppJsonContext.cs`), with `[property: JsonIgnore(Condition =
  JsonIgnoreCondition.WhenWritingNull)]` matching the existing `AbortReason` field's treatment —
  confirm whether omitting `null` vs explicit `"lastTxMessage": null` matches what the qso-controller
  delta spec's scenario expects; adjust the delta spec's wire-format example instead of the code if
  the existing `AbortReason` precedent (omit-when-null) turns out to be the more consistent choice.
- [ ] 4.4 Update `WebSocketHub.BroadcastTxState`'s signature and its single call site to pass
  `lastTxMessage` through into the constructed `WsTxStateMessage`.

## 5. Frontend — renderMessageRows prefers real text

- [ ] 5.1 In `web/js/main.js`, add module-level state `let realRowText = [null, null, null];`
  (or equivalent), alongside the existing `currentTxPartner`/`currentTxRole` module state.
- [ ] 5.2 In `renderMessageRows`, when `hasEnteredNewActiveTxState(prevState, state, activeStates)`
  is true and `lastTxMessage` is non-null, set `realRowText[activeStates.indexOf(state)] =
  lastTxMessage` before computing row text.
- [ ] 5.3 Change each row's rendered text from `texts[i]` to `realRowText[i] ?? texts[i]`.
- [ ] 5.4 Update the transcript logging call (currently `appendTranscriptEntry('sent',
  texts[activeIndex], currentTxPartner)`) to use `realRowText[activeIndex] ?? texts[activeIndex]`
  (the same value now driving the row's own display) instead of the unconditional template.
- [ ] 5.5 Reset `realRowText = [null, null, null]` wherever `currentTxPartner` is updated to a new
  non-null value different from the previous one, and wherever `state` becomes `Idle` — find the
  existing reset points for `currentTxPartner` itself and mirror them exactly.
- [ ] 5.6 Thread the new `lastTxMessage` field from the `txState` WebSocket payload and from the
  initial `GET /api/v1/tx/status` response (page-load seeding) into `renderMessageRows`'s call
  sites, matching how `autoAnswerEnabled`/`role` are already threaded from both sources.

## 6. Regression tests

- [ ] 6.1 `QsoCallerServiceTests.cs`: assert `LastTxMessage` reflects the real composed report
  message after `ExecuteTxReportAsync`, is `null` before any transmission, and reflects the
  retransmitted value after a `WaitRr73` retry.
- [ ] 6.2 `QsoAnswererServiceTests.cs`: assert `LastTxMessage` reflects the real composed report
  reply after `HandleWaitReportAsync`'s signal-report branch, and after an
  `EngagePoint.SendReport` jump-in.
- [ ] 6.3 `tests/OpenWSFZ.Web.Tests/*`: assert `GET /api/v1/tx/status` (and the other endpoints
  listed in task 4.2) includes `lastTxMessage` reflecting the active controller's value, using a
  fake `IQsoController`.
- [ ] 6.4 `tests/OpenWSFZ.Web.Tests/*` (WebSocket): assert a broadcast `txState` frame includes
  `lastTxMessage`.
- [ ] 6.5 `web/js/main.test.js` (or wherever `renderMessageRows` is already covered, if anywhere —
  check first; add a new test file if none exists): assert a row shows the real `lastTxMessage`
  once received, falls back to the template for a row not yet reached, keeps showing real text
  after the state advances past that row, and clears on partner-change/Idle.
- [ ] 6.6 `web/js/qsoTranscript.test.js`: check for any existing assertion pinned to the old
  always-template `sent` entry text (flagged as unconfirmed in the source dev-task); update if
  found. No change expected to `shouldCaptureDecode`/`pushTranscriptEntry`/`hasEnteredNewActiveTxState`
  themselves.

## 7. Verification

- [ ] 7.1 Run `python3 tools/pre_merge_check.py` (HK-006) before declaring this ready for merge.
- [ ] 7.2 Manually verify end-to-end against a real (or synthesised) QSO exchange: confirm the TX
  message rows and QSO Transcript both show the real transmitted report value, not `+00`/`R+00` —
  this is the exact scenario the Captain originally reported; a screenshot comparison against the
  original report is the most direct confirmation.
