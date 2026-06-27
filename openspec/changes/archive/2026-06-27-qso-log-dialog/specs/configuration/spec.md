## ADDED Requirements

### Requirement: TxConfig QSO confirmation and retained log fields

The `TxConfig` section of `AppConfig` SHALL include four new fields governing the QSO confirmation dialog and retained log values:

| JSON key | C# property | Type | Default | Description |
|---|---|---|---|---|
| `qsoConfirmation` | `QsoConfirmation` | bool | `true` | When true, the confirmation dialog is shown; ADIF written only on OK. When false, auto-log at QsoComplete. |
| `retainedTxPower` | `RetainedTxPower` | string | `""` | Last TX power value marked Retain; pre-fills the Tx Power field in the next dialog. |
| `retainedComment` | `RetainedComment` | string | `""` | Last comment value marked Retain; pre-fills the Comments field in the next dialog. |
| `retainedPropMode` | `RetainedPropMode` | string | `""` | Last propagation mode value marked Retain; pre-fills the Prop Mode dropdown in the next dialog. |

**STJ default-field hazard (lesson 6):** `QsoConfirmation` defaults to `true`. Because STJ source-gen deserialises missing JSON `bool` fields as `false`, a `[JsonConstructor]`-annotated constructor with parameter default `bool qsoConfirmation = true` SHALL be provided on `TxConfig` to ensure the correct default on first-run and on upgrade of existing config files that lack this field.

All four fields SHALL round-trip correctly through `GET /api/v1/config` / `POST /api/v1/config` and SHALL survive unknown-field preservation on config save.

#### Scenario: QsoConfirmation defaults to true when field absent from config

- **WHEN** the daemon loads an `appconfig.json` that has a `tx` section but no `qsoConfirmation` key
- **THEN** `TxConfig.QsoConfirmation` SHALL be `true`

#### Scenario: QsoConfirmation = false persists and is read back

- **WHEN** `POST /api/v1/config` is called with `tx.qsoConfirmation = false` and the daemon is restarted
- **THEN** `TxConfig.QsoConfirmation` SHALL be `false` after restart

#### Scenario: Retained fields default to empty string when absent

- **WHEN** the daemon loads an `appconfig.json` that has no `retainedTxPower`, `retainedComment`, or `retainedPropMode` keys
- **THEN** all three SHALL be empty strings (not null)

#### Scenario: Retained fields updated by POST /api/v1/tx/log-qso

- **WHEN** `POST /api/v1/tx/log-qso` is called with `txPower = "100"` and `retainTxPower = true`
- **THEN** `TxConfig.RetainedTxPower` SHALL be `"100"` and the updated value SHALL be present in the next `GET /api/v1/config` response

#### Scenario: Retained fields included in qsoReview WS event

- **WHEN** the `qsoReview` WebSocket event is emitted and `TxConfig.RetainedTxPower = "100"`
- **THEN** the event payload SHALL include `"retainedTxPower": "100"`
