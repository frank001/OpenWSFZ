## Why

QSOs logged by OpenWSFZ are written to ADIF automatically and silently at completion, with no opportunity to add supplementary data (operator name, TX power, comments, propagation mode, contest exchanges) or to decline logging an unintended QSO. WSJT-X presents a confirmation dialog the moment the final transmission begins, giving the operator a ~15-second window to review, enrich, and confirm (or discard) the log entry. Bringing this workflow to OpenWSFZ closes the last significant gap in operator experience for the TX role.

## What Changes

- **New modal confirmation dialog** shown in the browser when the state machine enters `Tx73` (answerer) or `TxRr73` (caller). The dialog is truly modal — the `<dialog>` element is opened with `.showModal()`, the X button is hidden, and no other UI interaction is possible until OK or Cancel is pressed.
- **Enrichment fields** available for operator entry: Name, Tx Power, Comments, Prop Mode (dropdown), Exch Sent, Exch Rcvd, and an editable Operator callsign (pre-filled from `tx.callsign`).
- **Retain support** for Tx Power, Comments, and Prop Mode: values marked Retain are persisted to `appconfig.json` via `TxConfig` and pre-filled in subsequent dialogs.
- **ADIF write on demand**: when `tx.qsoConfirmation = true`, the daemon does NOT auto-write ADIF at `QsoComplete`. Instead a `qsoReview` WebSocket event carries the full QSO data to the browser; the operator's OK press triggers `POST /api/v1/tx/log-qso`, which writes the enriched ADIF record. Cancel produces no log entry.
- **Feature toggle**: `tx.qsoConfirmation` (bool, default `true`). When `false`, the existing auto-log behaviour is preserved (backward-compatible off path).
- **PropModeStore**: protocol-aware list of propagation modes, same architectural pattern as `FrequencyStore`. Seeded with the FT8 subset on first run; extensible per-protocol as new modes are added. Exposed via `GET /POST /api/v1/prop-modes`.
- **Enriched ADIF fields**: `QsoRecord` gains optional fields (`PartnerName`, `TxPower`, `Comment`, `PropMode`, `ExchSent`, `ExchRcvd`); `AdifLogWriter.BuildAdifRecord` appends them conditionally (ADIF: `NAME`, `TX_PWR`, `COMMENT`, `PROP_MODE`, `STX_STRING`, `SRX_STRING`).
- **End-time convention** aligned with WSJT-X: `QsoEndUtc` is set to the start of the current 15-second FT8 cycle (floor of UTC now to nearest 15 s) when entering the last-TX state, not at `QsoComplete`.

## Capabilities

### New Capabilities

- `qso-log-dialog`: Modal QSO confirmation dialog shown at last-TX state entry; operator-enrichable; confirms ADIF write or discards. Includes the `qsoReview` WS event, `POST /api/v1/tx/log-qso` endpoint, and all frontend dialog logic.
- `prop-mode-store`: Protocol-aware propagation mode list (same pattern as `frequency-management`). `PropModeEntry { Protocol, Value, Description }`. Seeded with FT8 subset. `GET/POST /api/v1/prop-modes`.

### Modified Capabilities

- `adif-log`: New optional ADIF fields (`NAME`, `TX_PWR`, `COMMENT`, `PROP_MODE`, `STX_STRING`, `SRX_STRING`); end-time now calculated at last-TX entry as cycle-start floor rather than at `QsoComplete`. Auto-write behaviour is gated by `tx.qsoConfirmation`.
- `configuration`: New `TxConfig` fields: `QsoConfirmation` (bool, default `true`), `RetainedTxPower` (string), `RetainedComment` (string), `RetainedPropMode` (string).

## Impact

- **`OpenWSFZ.Daemon`**: `QsoRecord` (new optional fields), `AdifLogWriter` (new ADIF fields + conditional write path), `QsoAnswererService` (emit `qsoReview` at `Tx73`; skip auto-ADIF when confirmation enabled), `QsoCallerService` (same at `TxRr73`), `TxConfig` (four new fields), new `PropModeStore` + `PropModeEntry` classes, new `PropModeJsonContext`.
- **`OpenWSFZ.Abstractions`**: `ITxEventBus` — new `PublishQsoReview(...)` overload.
- **`OpenWSFZ.Web`**: `WebApp.cs` — new `POST /api/v1/tx/log-qso` and `GET/POST /api/v1/prop-modes` endpoints; `TxEventBus` gains `PublishQsoReview` implementation.
- **`web/js/`**: `main.js` (handle `qsoReview` WS event, show/close dialog, populate fields, wire OK/Cancel), `api.js` (add `postLogQso` and `getPropModes`), `settings.js` (QsoConfirmation toggle). Note: `ws.js` is unchanged — the qsoReview event dispatch is handled inside the existing `main.js` WS message handler.
- **`web/`**: `index.html` (new `<dialog>` element), `css/app.css` (modal dialog styles).
- **`web/settings.html`**: toggle for `tx.qsoConfirmation`. Note: Settings UI for managing the prop-modes list was explicitly deferred in the design (non-goal); `GET/POST /api/v1/prop-modes` are available to client tooling, but no settings table is provided in this change.
- **Tests**: `AdifLogWriterTests` (new optional-field scenarios), `QsoAnswererServiceTests` / `QsoCallerServiceTests` (qsoReview event emission, skip-auto-ADIF path), new `PropModeStoreTests`.
- **No breaking changes** to existing API surface; `tx.qsoConfirmation = false` restores the pre-change behaviour exactly.
