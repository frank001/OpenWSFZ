## Why

Four independent gaps surfaced during an operator-focused GUI review: (1) the native FT8 decoder
shim's ABI version is checked at startup but never exposed, so diagnosing a shim mismatch requires
reading daemon logs; (2) the existing TX/Call-CQ button styling collapses "armed but idle" and
"actually transmitting right now" into a single flat colour, so it is not always clear when the
station is on the air; (3) the waterfall canvas lets a single unmodified click change the RX or TX
frequency — including a bare right-click silently retuning TX with zero confirmation — which is too
easy to trigger by accident during a live session; (4) there is no way to inspect the daemon's own
operational log from the browser, so diagnosing a problem on a headless or remote install requires
filesystem access. None of the four require new architecture — each is grounded in an existing,
already-wired data path or page.

## What Changes

- Add the native shim's actual loaded ABI version (`Ft8LibInterop.NativeVersionCheck()`, currently
  read once at startup and discarded) as a new field on `DaemonStatus` / `GET /api/v1/status`, and
  display it read-only in the Advanced settings tab.
- Replace `#tx-enable-btn`'s single flat "armed" red state with two distinct states — dark red
  (armed, not currently transmitting) vs. bright red (armed and the QSO/Caller state machine is in
  one of its `Tx*` sub-states) — computed entirely from data already on the existing `txState`
  WebSocket payload (`state`, `autoAnswerEnabled`). Give `#tx-call-cq-btn` a steady bright-green
  state whenever Call-CQ mode is engaged (`role === 'caller' && autoAnswerEnabled`), independent of
  the literal transmitting sub-state, and background colour otherwise.
- **BREAKING (UI behaviour + new backend capability)**: `#tx-call-cq-btn` currently disables itself
  for the whole non-`Idle` duration of a caller session, with no way to end a session short of the
  immediate-kill `Abort TX` button. Per the Captain's ruling (2026-07-05, "the operator is in
  control"), this changes to a Call CQ / Stop CQ toggle: while engaged (`role === 'caller' && state
  !== 'Idle'`) the button stays enabled, reads "Stop CQ", and clicking it requests a **graceful
  stop** — any in-progress TX sample completes normally, then the service returns to `Idle` — via a
  new `IQsoController.GracefulStopAsync` method and `POST /api/v1/tx/stop-cq` endpoint. This is a
  revival of a previously-drafted-but-never-implemented handoff,
  `dev-tasks/2026-06-26-caller-cq-stop.md` (FR-CQ-STOP-001); see design.md Decision 2b for the full
  design and what was/wasn't carried forward from it.
- Replace the waterfall canvas's current click scheme (plain left-click = RX, Shift+left-click =
  RX+TX, plain right-click = TX, no confirmation, no tooltip) with a modifier-gated scheme: only
  Ctrl+left-click (RX), Ctrl+right-click (TX), and Shift+left-click (RX+TX) change anything;
  Shift+right-click and any unmodified click are a no-op. **BREAKING (UI behaviour)**: existing
  muscle memory (plain click, plain right-click) stops working by design — this is the point of the
  change. Add a tooltip documenting the new scheme.
- Add a new "Logs" tab to the settings page that polls the last 150 lines of the daemon's active
  log file on an interval, plus a separate standalone full-log page (fetched once, no auto-refresh,
  manual browser reload to see new content).

## Capabilities

### New Capabilities
- `daemon-status-visibility`: exposes the native shim's actual loaded ABI version on the status
  endpoint and in the Advanced settings tab.
- `tx-state-indicators`: defines the TX-armed/transmitting and Call-CQ-engaged visual states for
  the TX control buttons, derived from the existing `txState` WebSocket payload.
- `log-viewer`: a settings-page "Logs" tab (polled tail, last 150 lines) and a standalone full-log
  page (single fetch, manual refresh), both reading the daemon's currently active rotated log file.

### Modified Capabilities
- `waterfall-cursors`: the click-to-QSY interaction requirements change from
  `{plain-left→RX, plain-right→TX, shift-left→RX+TX}` to
  `{ctrl-left→RX, ctrl-right→TX, shift-left→RX+TX, shift-right→no-op, unmodified→no-op}`, plus a
  new tooltip requirement on the waterfall canvas.
- `web-frontend`: the existing "TX panel — Enable TX toggle button" requirement is narrowed from
  "armed ⇒ a single `tx-btn-armed` style, unconditionally" to "armed ⇒ some armed style, with the
  specific dark-red/bright-red choice governed by the new `tx-state-indicators` capability" — this
  removes the direct conflict between the two capabilities' descriptions of the same button. A new
  "TX panel — Call CQ button" requirement is also added, formalising (and superseding) the
  previously undocumented `disabled = (state !== 'Idle')` behaviour with the Call CQ / Stop CQ
  toggle described above.
- `qso-controller`: adds `IQsoController.GracefulStopAsync` (default no-op) and the
  `POST /api/v1/tx/stop-cq` endpoint.
- `qso-caller`: adds `QsoCallerService`'s graceful-stop behaviour — completes any in-progress TX,
  extends wakeup-channel eligibility to `WaitRr73`, idempotent on repeated requests.

## Impact

- **Web/API**: `src/OpenWSFZ.Web/DaemonStatus.cs` (new `ShimVersion` field), `src/OpenWSFZ.Web/WebApp.cs`
  (`GET /api/v1/status` populates it; new `GET /api/v1/logs/tail` and `GET /api/v1/logs/full`-style
  endpoints for the log viewer).
- **Native interop**: `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — the already-computed `actual`
  version from `NativeVersionCheck()` needs to be retained (not just compared and discarded) so it
  can be read back out.
- **Frontend**: `web/settings.html` / `web/js/settings.js` (Advanced tab shim-version display, new
  Logs tab), `web/index.html` / `web/js/main.js` (`renderTxPanel`'s button-class logic, Call CQ
  button's disabled/label/click-routing logic, waterfall canvas click/contextmenu handlers and
  tooltip), `web/js/api.js` (new `postTxStopCq()`), new `web/logs.html` + a new small JS module
  mirroring the existing `settings.html`/`login.html` standalone-page pattern.
- **Backend (Call CQ graceful stop)**: `src/OpenWSFZ.Abstractions/IQsoController.cs` (new
  `GracefulStopAsync` method, default no-op), `src/OpenWSFZ.Daemon/QsoCallerService.cs`
  (`GracefulStopAsync` implementation, `_gracefulStopRequested` flag, `WaitRr73` added to
  wakeup-eligible states), `src/OpenWSFZ.Daemon/QsoControllerRouter.cs` (delegation),
  `src/OpenWSFZ.Web/WebApp.cs` (new `POST /api/v1/tx/stop-cq` route).
- **Configuration**: none — this change reads existing `logging.directory`/rotation settings
  (`AppConfig`/`DecodeLogConfig`) rather than adding new config surface.
- **Non-goals**: a remote-restart capability was raised in the same discovery conversation but is
  explicitly deferred by the Captain to a later, separate change — not addressed here.
