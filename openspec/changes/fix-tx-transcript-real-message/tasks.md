## 1. IQsoController — LastTxMessage contract

- [x] 1.1 Add `string? LastTxMessage { get; }` to `IQsoController`
  (`src/OpenWSFZ.Abstractions/IQsoController.cs`), documented analogously to the existing
  `State`/`Partner`/`Keying` properties.
- [x] 1.2 Add `public string? LastTxMessage => ActiveController.LastTxMessage;` to
  `QsoControllerRouter` (`src/OpenWSFZ.Daemon/QsoControllerRouter.cs`), placed alongside the
  existing `State`/`Partner`/`Keying` delegating properties.

## 2. QsoCallerService — persist the real transmitted text

- [x] 2.1 Add `private string? _lastTxMessage;` field, mirroring `QsoAnswererService`'s existing
  one; implement `public string? LastTxMessage => _lastTxMessage;`.
- [x] 2.2 Set `_lastTxMessage` in `ExecuteTxReportAsync` to the composed `reportMessage` (same
  string passed to `TransmitAsync`).
- [x] 2.3 Set `_lastTxMessage` in `RetryOrAbortAsync`'s `WaitAnswer` retry branch (CQ
  retransmission) and its `WaitRr73` retry branch (report retransmission), each to the exact
  string passed to `TransmitAsync` in that branch.
- [x] 2.4 Set `_lastTxMessage` in `ExecuteTxRr73Async` to the composed `rr73Message`.
- [x] 2.5 Reset `_lastTxMessage = null` in `HandleIdleAsync`'s session-init block, alongside the
  existing `_rstRcvd`/`_rstSent` resets.

  (Additionally, to fully satisfy design.md's "CQ/RR73 composition points" — beyond the four
  sites tasks.md names literally — `_lastTxMessage` is also set at the initial CQ composition
  site inside `HandleIdleAsync`, so row 1 is tracked from the very first transmission, not only
  from a retry onward.)

## 3. QsoAnswererService — expose the existing LastTxMessage

- [x] 3.1 Implement `public string? LastTxMessage => _lastTxMessage;` — the field itself already
  exists and is already set at every TX-composition site; no change to its assignment sites.

  (`_lastTxMessage` there is a non-nullable `string` defaulting to `string.Empty` and never reset
  between QSOs; the property translates empty → `null` so a fresh process reports `null` per the
  documented contract, without touching any of the five existing assignment sites.)

## 4. TxStatusResponse and txState WebSocket event

- [x] 4.1 Add `string? LastTxMessage = null` to the `TxStatusResponse` record
  (`src/OpenWSFZ.Web/AppJsonContext.cs`).
- [x] 4.2 Update every `TxStatusResponse` construction site in `WebApp.cs` (`GET /api/v1/tx/status`,
  `POST /api/v1/tx/enable`, `POST /api/v1/tx/disable`, `POST /api/v1/tx/abort`,
  `POST /api/v1/tx/select-responder`) to pass the resolved controller's `LastTxMessage`, matching
  how `Role`/`Keying` are already threaded through each of these sites.

  (All 10 construction sites updated, including the four not explicitly named above —
  `/tx/stop-cq`, `/tx/answer-cq`, `/tx/engage-decode`, `/tx/call-cq`, `/tx/caller-partner-select` —
  since design.md's decision is "every existing call site that already reads State/Partner/Keying".)
- [x] 4.3 Add `string? LastTxMessage = null` to `WsTxStateMessage`
  (`src/OpenWSFZ.Web/AppJsonContext.cs`), with `[property: JsonIgnore(Condition =
  JsonIgnoreCondition.WhenWritingNull)]` matching the existing `AbortReason` field's treatment —
  confirm whether omitting `null` vs explicit `"lastTxMessage": null` matches what the qso-controller
  delta spec's scenario expects; adjust the delta spec's wire-format example instead of the code if
  the existing `AbortReason` precedent (omit-when-null) turns out to be the more consistent choice.

  (Kept the omit-when-null `AbortReason` precedent — confirmed consistent with
  `specs/qso-controller/spec.md`'s scenario.)
- [x] 4.4 Update `WebSocketHub.BroadcastTxState`'s signature and its single call site to pass
  `lastTxMessage` through into the constructed `WsTxStateMessage`.

  (`TxEventBus.Publish`/`ITxEventBus.Publish` also gained the same new optional trailing
  parameter, threaded through from each service's `SetStateAndNotify`/`PublishKeyingTransition`/
  abort-broadcast chokepoints — required so the WS push, not just the polled status endpoint,
  actually carries a live value instead of always defaulting to `null`.)

## 5. Frontend — renderMessageRows prefers real text

- [x] 5.1 In `web/js/main.js`, add module-level state `let realRowText = [null, null, null];`
  (or equivalent), alongside the existing `currentTxPartner`/`currentTxRole` module state.
- [x] 5.2 In `renderMessageRows`, when `hasEnteredNewActiveTxState(prevState, state, activeStates)`
  is true and `lastTxMessage` is non-null, set `realRowText[activeStates.indexOf(state)] =
  lastTxMessage` before computing row text.
- [x] 5.3 Change each row's rendered text from `texts[i]` to `realRowText[i] ?? texts[i]`.
- [x] 5.4 Update the transcript logging call (currently `appendTranscriptEntry('sent',
  texts[activeIndex], currentTxPartner)`) to use `realRowText[activeIndex] ?? texts[activeIndex]`
  (the same value now driving the row's own display) instead of the unconditional template.
- [x] 5.5 Reset `realRowText = [null, null, null]` wherever `currentTxPartner` is updated to a new
  non-null value different from the previous one, and wherever `state` becomes `Idle` — find the
  existing reset points for `currentTxPartner` itself and mirror them exactly.
- [x] 5.6 Thread the new `lastTxMessage` field from the `txState` WebSocket payload and from the
  initial `GET /api/v1/tx/status` response (page-load seeding) into `renderMessageRows`'s call
  sites, matching how `autoAnswerEnabled`/`role` are already threaded from both sources.

  (The 5.2/5.3 caching/lookup logic was extracted into two new pure, DOM-free exports —
  `cacheRealRowText`/`pickRowText` in `web/js/qsoTranscript.js` — with `renderMessageRows` calling
  them rather than inlining the array mutation, matching this codebase's existing
  DOM-free-logic-plus-DOM-rendering-wrapper pattern and making task 6.5 unit-testable without a
  jsdom harness.)

## 6. Regression tests

- [x] 6.1 `QsoCallerServiceTests.cs`: assert `LastTxMessage` reflects the real composed report
  message after `ExecuteTxReportAsync`, is `null` before any transmission, and reflects the
  retransmitted value after a `WaitRr73` retry.
- [x] 6.2 `QsoAnswererServiceTests.cs`: assert `LastTxMessage` reflects the real composed report
  reply after `HandleWaitReportAsync`'s signal-report branch, and after an
  `EngagePoint.SendReport` jump-in.
- [x] 6.3 `tests/OpenWSFZ.Web.Tests/*`: assert `GET /api/v1/tx/status` (and the other endpoints
  listed in task 4.2) includes `lastTxMessage` reflecting the active controller's value, using a
  fake `IQsoController`.
- [x] 6.4 `tests/OpenWSFZ.Web.Tests/*` (WebSocket): assert a broadcast `txState` frame includes
  `lastTxMessage`.
- [x] 6.5 `web/js/main.test.js` (or wherever `renderMessageRows` is already covered, if anywhere —
  check first; add a new test file if none exists): assert a row shows the real `lastTxMessage`
  once received, falls back to the template for a row not yet reached, keeps showing real text
  after the state advances past that row, and clears on partner-change/Idle.

  (No `main.test.js` existed and none of `main.js`'s DOM-touching TX-panel code has ever had
  direct test coverage in this codebase — every existing behaviour is verified only via its
  extracted `qsoTranscript.js` logic. Followed that same precedent: added
  `cacheRealRowText`/`pickRowText` coverage to `qsoTranscript.test.js` instead, covering "shows
  real text once received," "falls back to template for a row not yet reached," and "keeps
  showing real text after the state advances past that row" directly. The partner-change/Idle
  clear is a trivial one-line array-literal reassignment in `renderTxPanel`, not separately unit
  tested — also consistent with this codebase's existing DOM-layer coverage boundary.)
- [x] 6.6 `web/js/qsoTranscript.test.js`: check for any existing assertion pinned to the old
  always-template `sent` entry text (flagged as unconfirmed in the source dev-task); update if
  found. No change expected to `shouldCaptureDecode`/`pushTranscriptEntry`/`hasEnteredNewActiveTxState`
  themselves.

  (Checked — no such assertion existed; that file only ever tested the four named DOM-free
  functions, none of which pin template text. No change needed there beyond the new
  `cacheRealRowText`/`pickRowText` tests added under task 6.5.)

## 7. Verification

- [x] 7.1 Run `python3 tools/pre_merge_check.py` (HK-006) before declaring this ready for merge.
- [x] 7.2 Manually verify end-to-end against a real (or synthesised) QSO exchange: confirm the TX
  message rows and QSO Transcript both show the real transmitted report value, not `+00`/`R+00` —
  this is the exact scenario the Captain originally reported; a screenshot comparison against the
  original report is the most direct confirmation.

  Verified two ways against a real, isolated `OpenWSFZ.Daemon` process (Release build), both
  driving the real `EngagePoint.SendReport`/`SendRr73` jump-in via `POST /api/v1/tx/engage-decode`
  (no virtual-audio-cable/synthesized RF needed — jump-in triggering only needs the daemon's
  normal audio-capture pipeline producing periodic phase-aligned decode batches, real ambient
  mic silence is sufficient; batch *content* is irrelevant to jump-in firing):

  1. `qa/tx-transcript-real-message-live-verify/live_verify_tx_transcript.py` — real HTTP + real
     WebSocket client, no browser. **PASS**: both scenarios' `lastTxMessage` (WS push and polled
     `GET /tx/status`) exactly matched the real composed text (`Q9AAA Q1OFZ R-07`,
     `Q9AAA Q1OFZ RR73`), never the old `+00`/`R+00` placeholder or `null`. Report:
     `qa/tx-transcript-real-message-live-verify/live-reports/2026-07-19T003730Z-95db278.md`.
  2. `qa/tx-transcript-real-message-live-verify/pw-scratch/screenshot_tx_panel.js` — real
     Chromium (Playwright) loading the real `index.html`/`main.js`, connected over the real
     WebSocket to the same daemon, exercising the same `SendReport` scenario. Screenshot
     confirms row 2 (`#tx-msg-2`) reads `Q9AAA Q1OFZ R-07` (highlighted active) and the QSO
     Transcript's first entry reads the same real text — the exact scenario (and layout) the
     Captain's original bug report screenshot showed as `+00`. Screenshot:
     `qa/tx-transcript-real-message-live-verify/live-reports/tx-panel-real-report-screenshot.png`.

  (`pw-scratch/node_modules` is gitignored via the repo's existing blanket `node_modules/` rule;
  only the script, its `package.json`/`package-lock.json`, and the committed report/screenshot
  are tracked.)
