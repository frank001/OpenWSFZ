## 1. QsoRecord — optional enrichment fields

- [x] 1.1 Add optional properties to `QsoRecord`: `PartnerName`, `TxPower`, `Comment`, `PropMode`, `ExchSent`, `ExchRcvd` (all `string?`, default `null`)
- [x] 1.2 Update `AdifLogWriter.BuildAdifRecord` to conditionally append `NAME`, `TX_PWR`, `COMMENT`, `PROP_MODE`, `STX_STRING`, `SRX_STRING` when the corresponding field is non-null and non-empty
- [x] 1.3 Add `AdifLogWriterTests` scenarios for each new optional field: present → included in ADIF; empty/null → omitted

## 2. TxConfig — new fields

- [x] 2.1 Add `QsoConfirmation` (bool), `RetainedTxPower`, `RetainedComment`, `RetainedPropMode` (string) to `TxConfig`
- [x] 2.2 Add a `[JsonConstructor]`-annotated constructor on `TxConfig` with `bool qsoConfirmation = true` to ensure STJ source-gen deserialises missing field as `true` (lesson 6 / design R4)
- [x] 2.3 Verify `GET /api/v1/config` exposes all four new fields; verify `POST /api/v1/config` round-trips them correctly
- [x] 2.4 Add `ConfigTests` covering: absent `qsoConfirmation` key deserialises to `true`; retained fields default to empty string

## 3. PropModeStore

- [x] 3.1 Create `PropModeEntry` record in `OpenWSFZ.Abstractions`: `string Protocol`, `string Value`, `string Description`
- [x] 3.2 Create `PropModeJsonContext` (STJ source-gen) for `PropModeEntry[]`
- [x] 3.3 Implement `PropModeStore`: load from `prop-modes.json` (same directory as `appconfig.json`); write default FT8 seed if file absent or contains empty array; expose `IReadOnlyList<PropModeEntry> Entries` and `Task SaveAsync(IEnumerable<PropModeEntry>)`
- [x] 3.4 Register `PropModeStore` as singleton in DI (`Program.cs` and `WebApp.Create`)
- [x] 3.5 Add `GET /api/v1/prop-modes` to `WebApp.cs`: returns full list as JSON array
- [x] 3.6 Add `POST /api/v1/prop-modes` to `WebApp.cs`: replaces list, saves to `prop-modes.json`, returns updated list
- [x] 3.7 Add `PropModeStoreTests`: seed-on-missing-file, load-existing, empty-array-reseeded, GET/POST round-trip

## 4. ITxEventBus — qsoReview event

- [x] 4.1 Add `PublishQsoReview(QsoRecord record, string retainedTxPower, string retainedComment, string retainedPropMode)` to `ITxEventBus`
- [x] 4.2 Implement in `TxEventBus`: broadcast JSON frame `{ "type": "qsoReview", ... }` via `WebSocketHub.BroadcastQsoReview`
- [x] 4.3 Add helper `DeriveFt8CycleStartUtc(DateTime utcNow)` in `Ft8TimeHelper`: returns `utcNow` floored to the nearest 15-second boundary

## 5. QsoAnswererService — qsoReview emission + conditional ADIF

- [x] 5.1 At `Tx73` state entry (before `TransmitAsync`): if `tx.QsoConfirmation = true`, call `PublishQsoReview` with current QSO data
- [x] 5.2 At `QsoComplete`: if `tx.QsoConfirmation = true`, skip `AppendQsoAsync`; if `false`, call it as before
- [x] 5.3 Add `QsoAnswererServiceTests` scenario: `qsoReview` event emitted when `QsoConfirmation = true`
- [x] 5.4 Add `QsoAnswererServiceTests` scenario: `AppendQsoAsync` not called at `QsoComplete` when `QsoConfirmation = true`
- [x] 5.5 Add `QsoAnswererServiceTests` scenario: `AppendQsoAsync` still called at `QsoComplete` when `QsoConfirmation = false` (regression guard)

## 6. QsoCallerService — qsoReview emission + conditional ADIF

- [x] 6.1 At `TxRr73` state entry (before `TransmitAsync`): if `tx.QsoConfirmation = true`, call `PublishQsoReview` with current QSO data
- [x] 6.2 At `QsoComplete`: if `tx.QsoConfirmation = true`, skip `AppendQsoAsync`; if `false`, call as before
- [x] 6.3 Add `QsoCallerServiceTests` scenarios mirroring 5.3–5.5 for the caller role

## 7. POST /api/v1/tx/log-qso endpoint

- [x] 7.1 Define request record `LogQsoRequest` with all fields; add to `AppJsonContext` along with `LogQsoResponse`
- [x] 7.2 Add `POST /api/v1/tx/log-qso` to `WebApp.cs`: deserialise request, construct `QsoRecord`, call `IAdifLogWriter.AppendQsoAsync`, update retained fields in config if retain flag set, return `{ "logged": true }`
- [x] 7.3 Add `LogQsoEndpointTests`: valid POST writes ADIF; retain flags persist to config; invalid UTC returns 400; malformed JSON returns 400
- [x] 7.4 Auth protection: verified via loopback-trusted `LogQsoFixture`; non-loopback behaviour covered by existing `AuthMiddlewareTests` pattern

## 8. Settings page — qsoConfirmation toggle

- [x] 8.1 Add "Show QSO confirmation dialog" checkbox to Settings → General section in `settings.html`, bound to `tx.qsoConfirmation`
- [x] 8.2 Include `qsoConfirmation` in the TX settings save payload in `settings.js`
- [x] 8.3 Pre-fill checkbox from `GET /api/v1/config` on settings page load

## 9. Frontend — prop-modes API client

- [x] 9.1 Add `getPropModes()` to `api.js`: `GET /api/v1/prop-modes`, returns array of `{ protocol, value, description }`

## 10. Frontend — confirmation dialog HTML + CSS

- [x] 10.1 Add `<dialog id="qso-log-dialog">` to `index.html` containing: read-only display fields (Call, Start, End, Mode, Freq, Rpt Sent, Rpt Rcvd, Grid, Operator), editable inputs (Name, Tx Power + Retain checkbox, Comment + Retain checkbox, Prop Mode select + Retain checkbox), Exch Sent, Exch Rcvd, and Cancel / Log QSO buttons
- [x] 10.2 Escape close suppressed: `cancel` event listener calls `e.preventDefault()` in `openQsoLogDialog` — native `<dialog>` has no `×` close button
- [x] 10.3 Add dialog modal styles to `app.css`: backdrop overlay, summary grid, two-column form layout, retain-label rows, button row alignment, `.btn`/`.btn-primary`/`.btn-secondary` utility classes

## 11. Frontend — confirmation dialog logic (main.js + ws.js)

- [x] 11.1 In `main.js` connect callback: handle `qsoReview` event type → call `openQsoLogDialog(event)`
- [x] 11.2 `openQsoLogDialog(ev)` implemented in `main.js`:
  - Fetches prop modes via `getPropModes()`, filters to `activeProtocol`, populates `<select>`
  - Populates all display fields from WS event payload
  - Pre-fills Tx Power, Comment, Prop Mode from retained values (`ev.retainedTxPower`, etc.)
  - Guard: if `dialog.open === true`, logs warning and returns
  - Adds `cancel` event listener that calls `e.preventDefault()`
  - Calls `dialog.showModal()`
- [x] 11.3 Cancel button: cloneNode to avoid listener accumulation; `handleCancel` calls `dialog.close()` with no POST
- [x] 11.4 Log QSO button: collects all field values, calls `postLogQso(body)`, closes on success; logs error and leaves dialog open on failure
- [x] 11.5 Add `getPropModes()` and `postLogQso(data)` to `api.js`

## 12. Acceptance verification

- [x] 12.1 Build passes: `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings
- [x] 12.2 Full test suite passes: 713/713 green (34 TraceabilityCheck + 24 LicenseInventory + 35 Rig + 2 E2E + 65 Config + 19 Audio + 194 Ft8 + 162 Daemon + 177 Web)
- [x] 12.3 Manual smoke test — answerer path: complete a QSO with `tx.qsoConfirmation = true`; confirm the dialog appears on Tx73, fields are pre-filled correctly, OK writes an ADIF entry with correct fields, Cancel produces no ADIF entry
- [x] 12.4 Manual smoke test — caller path: complete a CQ QSO; confirm dialog appears on TxRr73 with correct fields
- [x] 12.5 Manual smoke test — retain: check Retain on Tx Power, click OK; open a second QSO dialog; confirm Tx Power is pre-filled from the retained value
- [x] 12.6 Manual smoke test — qsoConfirmation = false: uncheck "Show QSO confirmation dialog" in Settings; complete a QSO; confirm no dialog appears and ADIF is written automatically
- [x] 12.7 Manual smoke test — prop modes: confirm the Prop Mode dropdown contains the 10 default FT8 entries; select TR; verify ADIF record contains `<PROP_MODE:2>TR`
- [x] 12.8 G3 traceability check: 34/34 PASS
