## 1. Backend — IQsoController interface rename

- [x] 1.1 Create `src/OpenWSFZ.Abstractions/IQsoController.cs` with members `State`, `Partner`, `AbortAsync` (identical contract to the retired `IQsoAnswerer`)
- [x] 1.2 Delete `src/OpenWSFZ.Abstractions/IQsoAnswerer.cs`
- [x] 1.3 Update `QsoAnswererService` to implement `IQsoController` (replace `IQsoAnswerer` in the class declaration)
- [x] 1.4 Update `OpenWSFZ.Daemon/Program.cs` DI registration: replace `services.AddSingleton<IQsoAnswerer, QsoAnswererService>()` with `IQsoController`
- [x] 1.5 Update `OpenWSFZ.Web/WebApp.cs`: replace `app.Services.GetService<IQsoAnswerer>()` capture with `IQsoController`; update `qsoAnswerer` local variable name and type throughout
- [x] 1.6 Update all test files that reference `IQsoAnswerer` (mocks, type names) to `IQsoController`
- [x] 1.7 Verify `dotnet build OpenWSFZ.slnx -c Release` produces zero errors and zero warnings

## 2. Backend — TxStatusResponse and new endpoints

- [x] 2.1 Add `bool AutoAnswerEnabled` property to `TxStatusResponse` record in `OpenWSFZ.Web`; add to `AppJsonContext` source-gen registration
- [x] 2.2 Update the existing `GET /api/v1/tx/status` handler to populate `AutoAnswerEnabled` from `store.Current.Tx?.AutoAnswer ?? false`
- [x] 2.3 Add `POST /api/v1/tx/enable` route handler: read current config, set `tx.autoAnswer = true`, save, return `TxStatusResponse` with `AutoAnswerEnabled = true`
- [x] 2.4 Add `POST /api/v1/tx/disable` route handler: read current config, set `tx.autoAnswer = false`, save, return `TxStatusResponse` with `AutoAnswerEnabled = false`
- [x] 2.5 Add integration tests for `POST /api/v1/tx/enable`: 200 response, `autoAnswerEnabled: true` in body, config persisted
- [x] 2.6 Add integration tests for `POST /api/v1/tx/disable`: 200 response, `autoAnswerEnabled: false` in body, does not abort active QSO
- [x] 2.7 Add integration test for `GET /api/v1/tx/status`: `AutoAnswerEnabled` reflects current config value
- [x] 2.8 Verify `dotnet test OpenWSFZ.slnx -c Release` — all tests green

## 3. Frontend — JS API client

- [x] 3.1 Add `getTxStatus()` function to `web/js/api.js` — `GET /api/v1/tx/status` returning parsed JSON
- [x] 3.2 Add `postTxEnable()` function to `web/js/api.js` — `POST /api/v1/tx/enable`
- [x] 3.3 Add `postTxDisable()` function to `web/js/api.js` — `POST /api/v1/tx/disable`
- [x] 3.4 Add `postTxAbort()` function to `web/js/api.js` — `POST /api/v1/tx/abort`

## 4. Frontend — HTML layout restructure

- [x] 4.1 Wrap `#decodes-panel` in a new `<div id="content-row">` flex container inside `#app`
- [x] 4.2 Add `<section id="tx-panel">` as the second child of `#content-row`
- [x] 4.3 Add `<button id="tx-enable-btn">Enable TX</button>` and `<button id="tx-abort-btn">Abort TX</button>` inside a controls row in `#tx-panel`
- [x] 4.4 Add `<span id="tx-state-display">Idle</span>` below the controls row
- [x] 4.5 Add three message row elements: `<div id="tx-msg-1">`, `<div id="tx-msg-2">`, `<div id="tx-msg-3">` with monospace text spans and `Tx N` labels

## 5. Frontend — CSS

- [x] 5.1 Update `#app` flex layout: `#content-row` is the new `flex: 1 1 0` child that fills the remaining height
- [x] 5.2 Style `#content-row` as `display: flex; flex-direction: row; overflow: hidden`
- [x] 5.3 `#decodes-panel` inside `#content-row`: `flex: 1 1 0; overflow-y: auto`
- [x] 5.4 `#tx-panel`: `flex: 0 0 320px; border-left: 1px solid var(--color-border); display: flex; flex-direction: column; padding: 0.75rem; gap: 0.5rem; overflow-y: auto`
- [x] 5.5 `button#tx-enable-btn.tx-btn-armed`: red/danger background (`var(--color-danger)`), white text, bold weight — unmistakable armed state
- [x] 5.6 `.tx-msg-row`: monospace font, font-size 0.82rem, padding 0.3rem 0; label chip (`Tx N`) right-aligned in muted colour
- [x] 5.7 `.tx-msg-active`: accent colour text (`var(--color-accent)`), left border accent stripe
- [x] 5.8 `.tx-msg-muted`: opacity 0.4 or `color: var(--color-muted)` on the message text

## 6. Frontend — main.js logic

- [x] 6.1 On `DOMContentLoaded`: call `getTxStatus()` to seed the TX panel; handle failure gracefully (log to console, panel stays in default disarmed/Idle state)
- [x] 6.2 Read `config.tx.callsign` and `config.tx.grid` from the existing `getConfig()` call (already made for `showCycleCountdown`); store in module-level variables for message row rendering
- [x] 6.3 Implement `renderTxPanel(state, partner, autoAnswerEnabled)`: updates `#tx-enable-btn` label and CSS class, updates `#tx-state-display`, re-renders all three message rows
- [x] 6.4 Implement `renderMessageRows(partner, state)`: computes the three message strings from partner (or `———` when null) + callsign + grid; applies `tx-msg-active` to the correct row based on `state`; applies `tx-msg-muted` to all rows when `autoAnswerEnabled` is false
- [x] 6.5 Add `txState` branch in the WebSocket event handler: call `renderTxPanel` with the new state and partner; preserve the current `autoAnswerEnabled` value
- [x] 6.6 Wire `#tx-enable-btn` click handler: if armed → call `postTxDisable()`, else → call `postTxEnable()`; disable button during request; call `renderTxPanel` on success; re-enable button on error
- [x] 6.7 Wire `#tx-abort-btn` click handler: call `postTxAbort()`; log errors to console
- [x] 6.8 Update the existing `getConfig()` `.then()` callback to extract and store `config.tx?.callsign` and `config.tx?.grid`; call `renderMessageRows` to refresh rows with real callsign/grid once config is available

## 7. Verification

- [x] 7.1 Build and run the application (`dotnet run --project src/OpenWSFZ.Daemon`); confirm TX panel is visible alongside the decoded-messages table
- [x] 7.2 Confirm Enable TX button turns red with "TX Armed" label after click; confirm it returns to neutral "Enable TX" after a second click
- [x] 7.3 Confirm message rows show `——— Q1OFZ JO33 / ——— Q1OFZ R+00 / ——— Q1OFZ 73` when Idle, and populate with a real partner callsign when a `txState` event fires (can be triggered manually via the QSO answerer in a test setup)
- [x] 7.4 Confirm Abort TX button calls `/api/v1/tx/abort` (check browser DevTools Network tab)
- [x] 7.5 Confirm message rows are greyed out when TX is disarmed and normal when armed
- [x] 7.6 Run `dotnet test OpenWSFZ.slnx -c Release` — 388+ tests green, zero failures
