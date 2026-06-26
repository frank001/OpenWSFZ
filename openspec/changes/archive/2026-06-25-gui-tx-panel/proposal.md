## Why

The main UI has no TX control surface: the operator cannot enable, disable, or monitor
transmissions from the primary page. TX is activated only by toggling `tx.autoAnswer` in
Settings and confirmed only by watching application logs. This makes the TX state invisible
during a live QSO and the workflow needlessly opaque compared to WSJT-X.

## What Changes

- **BREAKING** `IQsoAnswerer` (in `OpenWSFZ.Abstractions`) is renamed to `IQsoController`.
  `QsoAnswererService` implements `IQsoController`. All DI registrations and HTTP-layer
  consumers are updated accordingly. `IQsoAnswerer.cs` is removed.
- Two new API endpoints are added:
  - `POST /api/v1/tx/enable`  — sets `tx.autoAnswer = true` and saves config
  - `POST /api/v1/tx/disable` — sets `tx.autoAnswer = false` and saves config
- The main page layout is restructured: the area below the waterfall controls becomes a
  horizontal row containing the decoded-messages panel (~65 % width) and a new TX panel
  (~35 % width) side by side.
- The TX panel contains:
  - An **Enable TX** toggle button (neutral when disarmed; red background when armed —
    label does not change; see D-TX-UI-002 in design.md) — the permanent master TX safety interlock
  - An **Abort TX** button — calls the existing `POST /api/v1/tx/abort`
  - A state/partner status line (`Idle` or `Working <callsign>`)
  - Three standard-message rows (Tx 1 Answer, Tx 2 Report, Tx 3 73) computed client-side
    from the operator's configured callsign/grid and the active partner received via
    `txState` WebSocket events; the currently-transmitting row is highlighted; rows are
    greyed out when TX is disarmed
- The frontend begins handling `txState` WebSocket events (previously received but dropped)
  to update the panel in real time.

**Out of scope (explicit deferrals):**
- `QsoCallerService` / Tx 6 CQ row (UI visibility rule applies)
- `QsoRole` on `IQsoController` (not needed until QsoCaller exists)
- Tune button (requires continuous-carrier audio + CAT integration; deferred)

## Capabilities

### New Capabilities

- `qso-controller`: The `IQsoController` abstraction — the common interface implemented by
  both `QsoAnswererService` now and `QsoCallerService` in future. Covers the interface
  contract, the role-exclusive model, the two new `POST /api/v1/tx/enable` /
  `/tx/disable` API endpoints, and `POST /api/v1/tx/answer-cq` for targeted CQ answering.

### Modified Capabilities

- `web-frontend`: New TX panel layout (side-by-side with decodes), armed-state button,
  standard-message rows, `txState` WebSocket event handling. Decode table gains CQ row
  highlighting, clickable CQ rows (targeted QSO start), and partner interaction highlighting.

## Impact

- `OpenWSFZ.Abstractions`: `IQsoAnswerer.cs` → `IQsoController.cs` (rename); `AnswerCqAsync` added
- `OpenWSFZ.Daemon`: `QsoAnswererService` implements `IQsoController` with new `AnswerCqAsync`
- `OpenWSFZ.Web`: `WebApp.cs` resolves `IQsoController`; three new route handlers added
- `OpenWSFZ.Web.Tests`: existing `IQsoAnswerer` mock references updated; endpoint/WS tests added
- `web/index.html`: layout restructured; TX panel markup added
- `web/js/api.js`: new `postTxAnswerCq` function
- `web/js/main.js`: `txState` WS handler; Enable/Disable TX; Abort TX; message-row render; CQ highlighting; click-on-CQ handler; partner highlighting
- `web/css/app.css`: TX panel styles; armed-button state; message-row states; `decode-cq`; `decode-partner`
