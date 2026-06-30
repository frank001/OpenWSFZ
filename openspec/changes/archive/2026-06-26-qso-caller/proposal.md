## Why

The TX subsystem supports only the QSO answerer role — the station can respond to
incoming CQ calls but cannot originate them. FT8 operation requires both roles: calling
CQ when no suitable partner is on-air, and answering when one is. Adding
`QsoCallerService` completes the TX feature set and brings the operator experience in
line with WSJT-X.

## What Changes

- A new `QsoCallerService` BackgroundService implements `IQsoController` for the caller
  role. It calls CQ, waits for a response, completes the exchange, and logs to ADIF.
- A new `CallerState` enum covers the caller state machine. The existing `QsoState`
  enum (answerer states) is unchanged in this change; renaming it to `AnswererState` is
  deferred to limit blast radius.
- **BREAKING** `IQsoController` gains a `QsoRole Role { get; }` property and a new
  `SelectResponderAsync` method for operator-driven partner selection.
- `TxConfig` gains two new fields: `Role` (`TxRole` enum: `Answerer` / `Caller`,
  default `Answerer`) and `CallerPartnerSelect` (`CallerPartnerSelectMode` enum:
  `None` / `First`, default `First`).
- `Program.cs` selects and registers the appropriate `IQsoController` implementation
  at startup based on `TxConfig.Role`. Role switching requires an application restart.
- The `txState` WebSocket event gains a `role` field so the frontend knows which
  message row templates to render.
- The TX panel on the main page becomes role-aware: message rows show caller-role
  content (`CQ / Report / RR73`) when `Role = Caller` and answerer-role content
  (`Grid / R+report / 73`) when `Role = Answerer`.
- `CallerPartnerSelect = None` adds clickable responder rows in the decode table (the
  inverse of the existing CQ-click feature): while in `WaitAnswer`, rows matching
  `{our_callsign} {any_callsign} {grid}` are highlighted and clickable;
  a double-click calls `POST /api/v1/tx/select-responder`.
- The Settings page General tab gains a **TX Mode** selector (Answerer / Caller) and,
  when Caller is selected, a **Partner selection** radio group (None / First).

**Out of scope (explicit deferrals):**
- `MaxDistance` partner selection (requires grid-to-distance computation and sorting)
- SNR-derived signal reports (TX-D04; placeholder `+00` used for caller's report)
- Runtime role switching without restart
- Rename of `QsoState` → `AnswererState`
- CQ DX / directional CQ (`CQ DX {callsign} {grid}`)

## Capabilities

### New Capabilities

- `qso-caller`: The `QsoCallerService` state machine, `CallerState` enum, `TxRole`
  enum, `CallerPartnerSelectMode` enum, and the `POST /api/v1/tx/select-responder`
  endpoint.

### Modified Capabilities

- `qso-controller`: `IQsoController` gains `QsoRole Role { get; }` and
  `SelectResponderAsync`. `TxStatusResponse` and `txState` wire events gain a `role`
  field. DI registration becomes role-conditional in `Program.cs`.
- `web-frontend`: TX panel message rows become role-aware. Settings page General tab
  gains TX Mode and Partner Selection controls. Decode table gains `decode-responder`
  class and click handler for None-mode partner selection.
- `configuration`: `TxConfig` gains `Role` and `CallerPartnerSelect` fields with
  backward-compatible defaults.

## Impact

- `OpenWSFZ.Abstractions`: new `CallerState.cs`, `TxRole.cs`, `CallerPartnerSelectMode.cs`;
  `IQsoController.cs` updated; `TxConfig.cs` updated
- `OpenWSFZ.Daemon`: new `QsoCallerService.cs`; `Program.cs` updated for
  role-conditional DI
- `OpenWSFZ.Web`: `WebApp.cs` gains `POST /api/v1/tx/select-responder`; `ITxEventBus`
  and `TxEventBus` gain `role` parameter; `TxStatusResponse` gains `Role` field;
  `AppJsonContext` updated
- `OpenWSFZ.Daemon.Tests`: new `QsoCallerServiceTests.cs`
- `OpenWSFZ.Web.Tests`: new endpoint tests for `select-responder`
- `web/js/main.js`: role-aware `renderMessageRows`; responder-click handler
- `web/js/settings.js`: TX Mode selector; CallerPartnerSelect radio group
- `web/js/api.js`: `postTxSelectResponder` function
- `web/css/app.css`: `.decode-responder` class
