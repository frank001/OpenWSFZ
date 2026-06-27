## ADDED Requirements

### Requirement: qsoReview WebSocket event emitted at last-TX state entry

When `tx.qsoConfirmation` is `true`, the daemon SHALL emit a `qsoReview` WebSocket event immediately upon entering `QsoState.Tx73` (answerer role) or `CallerState.TxRr73` (caller role), before `TransmitAsync` is awaited. The event SHALL carry the complete QSO data known at that moment, plus the current retained fields from `TxConfig`.

The `qsoEndUtc` field SHALL be calculated as the start of the current FT8 15-second cycle: `floor(DateTime.UtcNow.TimeOfDay.TotalSeconds / 15) * 15` seconds past midnight UTC, on today's UTC date.

The event payload SHALL include:

| Field | Value |
|---|---|
| `type` | `"qsoReview"` |
| `callsign` | Partner callsign |
| `grid` | Partner grid locator (null if unknown) |
| `rstSent` | RST sent string (e.g. `"+00"`, `"R+00"`) |
| `rstRcvd` | RST received string (e.g. `"+05"`) |
| `startUtc` | QSO start UTC as ISO 8601 string |
| `endUtc` | Current FT8 cycle start UTC as ISO 8601 string |
| `mode` | `"FT8"` |
| `band` | ITU band name (e.g. `"40m"`), null if unknown |
| `freqMHz` | Dial frequency in MHz (0.0 if unknown) |
| `operatorCallsign` | `tx.callsign` |
| `retainedTxPower` | `TxConfig.RetainedTxPower` (empty string if unset) |
| `retainedComment` | `TxConfig.RetainedComment` (empty string if unset) |
| `retainedPropMode` | `TxConfig.RetainedPropMode` (empty string if unset) |

When `tx.qsoConfirmation` is `false`, no `qsoReview` event SHALL be emitted and behaviour is unchanged from the pre-change build.

#### Scenario: qsoReview event emitted on Tx73 entry (answerer)

- **WHEN** `QsoAnswererService` enters state `Tx73` and `tx.qsoConfirmation = true`
- **THEN** a `qsoReview` WebSocket event SHALL be broadcast to all connected clients before any audio transmission begins, containing the partner callsign, RST values, start/end UTC, mode, freq, operator callsign, and retained field values

#### Scenario: qsoReview event emitted on TxRr73 entry (caller)

- **WHEN** `QsoCallerService` enters state `TxRr73` and `tx.qsoConfirmation = true`
- **THEN** a `qsoReview` WebSocket event SHALL be broadcast to all connected clients before any audio transmission begins

#### Scenario: qsoEndUtc is cycle-start floor

- **WHEN** the `qsoReview` event is emitted at UTC time 11:08:37
- **THEN** the `endUtc` field SHALL be `"2026-06-27T11:08:30Z"` (floored to the 15-second boundary at 11:08:30)

#### Scenario: No qsoReview event when qsoConfirmation is false

- **WHEN** `QsoAnswererService` enters state `Tx73` and `tx.qsoConfirmation = false`
- **THEN** no `qsoReview` event SHALL be emitted and `AppendQsoAsync` SHALL be called at `QsoComplete` as before

---

### Requirement: ADIF auto-write suppressed when qsoConfirmation is enabled

When `tx.qsoConfirmation` is `true`, `QsoAnswererService` and `QsoCallerService` SHALL NOT call `AdifLogWriter.AppendQsoAsync` at `QsoComplete`. The ADIF write is deferred to `POST /api/v1/tx/log-qso`.

#### Scenario: AppendQsoAsync not called at QsoComplete when confirmation enabled

- **WHEN** a QSO completes and `tx.qsoConfirmation = true`
- **THEN** `AdifLogWriter.AppendQsoAsync` SHALL NOT be called by the state machine during that QSO lifecycle

#### Scenario: AppendQsoAsync still called at QsoComplete when confirmation disabled

- **WHEN** a QSO completes and `tx.qsoConfirmation = false`
- **THEN** `AdifLogWriter.AppendQsoAsync` SHALL be called exactly once at `QsoComplete`, as in the pre-change build

---

### Requirement: POST /api/v1/tx/log-qso writes enriched ADIF record

A new endpoint `POST /api/v1/tx/log-qso` SHALL accept a JSON body containing the complete QSO record (all fields from the `qsoReview` event) plus optional enrichment fields and retain flags. It SHALL construct a `QsoRecord`, call `AdifLogWriter.AppendQsoAsync`, and update the three retained fields in `TxConfig` for any field whose corresponding retain flag is `true`, then call `IConfigStore.SaveAsync`.

The endpoint SHALL return HTTP 200 with a JSON body `{ "logged": true }` on success.

The endpoint SHALL be protected by the existing auth middleware (passphrase / loopback trust).

**Request body fields:**

| Field | Type | Description |
|---|---|---|
| `callsign` | string | Partner callsign |
| `grid` | string? | Partner grid (null if unknown) |
| `rstSent` | string | RST sent |
| `rstRcvd` | string | RST received |
| `startUtc` | string | ISO 8601 UTC QSO start |
| `endUtc` | string | ISO 8601 UTC QSO end (cycle-start floor) |
| `freqMHz` | double | Dial frequency |
| `operatorCallsign` | string | Operator callsign (may differ from tx.callsign if edited) |
| `name` | string? | Partner name (ADIF NAME) |
| `txPower` | string? | TX power (ADIF TX_PWR) |
| `comment` | string? | Comment (ADIF COMMENT) |
| `propMode` | string? | Propagation mode value (ADIF PROP_MODE); empty → omit field |
| `exchSent` | string? | Exchange sent (ADIF STX_STRING) |
| `exchRcvd` | string? | Exchange received (ADIF SRX_STRING) |
| `retainTxPower` | bool | If true, save txPower to TxConfig.RetainedTxPower |
| `retainComment` | bool | If true, save comment to TxConfig.RetainedComment |
| `retainPropMode` | bool | If true, save propMode to TxConfig.RetainedPropMode |

#### Scenario: POST writes ADIF and returns 200

- **WHEN** `POST /api/v1/tx/log-qso` is called with valid required fields
- **THEN** the endpoint SHALL call `AdifLogWriter.AppendQsoAsync` and return HTTP 200 with `{ "logged": true }`

#### Scenario: Optional fields included in ADIF when non-empty

- **WHEN** the POST body includes non-empty values for `name`, `txPower`, `comment`, `propMode`, `exchSent`, `exchRcvd`
- **THEN** the written ADIF record SHALL include the corresponding fields: `NAME`, `TX_PWR`, `COMMENT`, `PROP_MODE`, `STX_STRING`, `SRX_STRING`

#### Scenario: Empty optional fields omitted from ADIF

- **WHEN** the POST body includes empty or null values for optional fields
- **THEN** the corresponding ADIF fields SHALL be omitted from the record

#### Scenario: Retain flag persists value to config

- **WHEN** the POST body has `txPower = "100"` and `retainTxPower = true`
- **THEN** `TxConfig.RetainedTxPower` SHALL be set to `"100"` and `IConfigStore.SaveAsync` SHALL be called

#### Scenario: Non-retained field not persisted

- **WHEN** the POST body has `txPower = "100"` and `retainTxPower = false`
- **THEN** `TxConfig.RetainedTxPower` SHALL remain unchanged

#### Scenario: operatorCallsign override honoured in ADIF

- **WHEN** the POST body has `operatorCallsign = "PD2FZ/P"` and `tx.callsign = "PD2FZ"`
- **THEN** the ADIF `OPERATOR` field SHALL contain `PD2FZ/P`

---

### Requirement: Browser displays modal confirmation dialog on qsoReview event

When the browser receives a `qsoReview` WebSocket event, it SHALL open a `<dialog>` element using `.showModal()`. The dialog SHALL be truly modal: the close (`×`) button SHALL be hidden, and the `cancel` event (triggered by Escape key) SHALL have `preventDefault()` called to suppress keyboard dismissal.

The dialog SHALL pre-fill all auto-filled fields as read-only display and all optional fields as editable inputs. Fields with corresponding retained values SHALL be pre-populated from the event's `retainedTxPower`, `retainedComment`, and `retainedPropMode` values.

The Prop Mode `<select>` element SHALL be populated from `GET /api/v1/prop-modes`, filtered to entries with `protocol === 'FT8'` (using `activeProtocol`). An initial blank option (value `""`, label "Not specified") SHALL always be present.

The dialog SHALL remain open indefinitely until the operator presses OK or Cancel. No timeout or auto-close mechanism SHALL be implemented.

#### Scenario: Dialog opens on qsoReview event

- **WHEN** the browser receives a WebSocket event with `type === "qsoReview"`
- **THEN** the `<dialog>` element SHALL be opened via `.showModal()` with all auto-filled fields populated from the event payload

#### Scenario: Escape key does not close dialog

- **WHEN** the `qsoReview` dialog is open and the operator presses Escape
- **THEN** the dialog SHALL remain open (the `cancel` event SHALL be prevented)

#### Scenario: Retained fields pre-populate inputs

- **WHEN** the `qsoReview` event contains `retainedTxPower = "100"`
- **THEN** the Tx Power input field SHALL be pre-filled with `"100"` on dialog open

#### Scenario: OK triggers POST and closes dialog

- **WHEN** the operator clicks Log QSO (OK)
- **THEN** the browser SHALL call `POST /api/v1/tx/log-qso` with the full record and close the dialog on success

#### Scenario: Cancel closes dialog without POST

- **WHEN** the operator clicks Cancel
- **THEN** the dialog SHALL close and no POST SHALL be made to `/api/v1/tx/log-qso`

#### Scenario: Prop Mode dropdown populated from prop-modes API

- **WHEN** the dialog opens
- **THEN** the Prop Mode `<select>` SHALL contain options from `GET /api/v1/prop-modes` filtered to `protocol === "FT8"`, plus a leading blank option

#### Scenario: Guard against double-open

- **WHEN** a second `qsoReview` event is received while the dialog is already open
- **THEN** `showModal()` SHALL NOT be called again; a console warning SHALL be logged

---

### Requirement: QSO confirmation toggle in Settings

The Settings page SHALL expose a checkbox labelled "Show QSO confirmation dialog" bound to `tx.qsoConfirmation`. The checkbox SHALL be included in the TX settings save payload. When unchecked, the value `false` is persisted to `TxConfig.QsoConfirmation`.

#### Scenario: Toggle saved to config

- **WHEN** the operator unchecks "Show QSO confirmation dialog" and saves TX settings
- **THEN** `tx.qsoConfirmation` SHALL be persisted as `false` in `appconfig.json`

#### Scenario: Toggle pre-filled from config

- **WHEN** the Settings page loads
- **THEN** the "Show QSO confirmation dialog" checkbox SHALL reflect the current value of `tx.qsoConfirmation`
