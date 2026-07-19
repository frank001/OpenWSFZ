## ADDED Requirements

### Requirement: IQsoController exposes LastTxMessage

`IQsoController` SHALL expose `string? LastTxMessage { get; }`, following the same read-only
property pattern as the existing `State`, `Partner`, and `Keying` properties. `null` when the
controller has not transmitted anything this process lifetime. `QsoControllerRouter` SHALL
delegate `LastTxMessage` to `ActiveController.LastTxMessage`, matching its existing
`State`/`Partner`/`Keying` delegation exactly.

#### Scenario: QsoControllerRouter delegates LastTxMessage to the active controller

- **WHEN** `QsoControllerRouter.LastTxMessage` is read while `QsoCallerService` is the active
  controller and its own `LastTxMessage` is `"Q1ABC PD2FZ -07"`
- **THEN** the router SHALL return `"Q1ABC PD2FZ -07"`

### Requirement: TxStatusResponse carries LastTxMessage field

The `TxStatusResponse` record SHALL include a nullable `string? LastTxMessage` property
reflecting `IQsoController.LastTxMessage`. This field SHALL be included in responses from
`GET /api/v1/tx/status`, `POST /api/v1/tx/enable`, `POST /api/v1/tx/disable`,
`POST /api/v1/tx/abort`, and `POST /api/v1/tx/select-responder`, matching the existing `Role`
field's inclusion list.

#### Scenario: GET /api/v1/tx/status returns the real last transmitted message

- **WHEN** the active controller's `LastTxMessage` is `"Q1ABC PD2FZ R-13"` and
  `GET /api/v1/tx/status` is called
- **THEN** the response body SHALL contain `"lastTxMessage": "Q1ABC PD2FZ R-13"`

#### Scenario: GET /api/v1/tx/status omits/nulls the field before any transmission

- **WHEN** the active controller's `LastTxMessage` is `null` and `GET /api/v1/tx/status` is called
- **THEN** the response body SHALL contain `"lastTxMessage": null`

### Requirement: txState WebSocket event carries lastTxMessage field

The `txState` WebSocket push (`WsTxStateMessage`) SHALL include a nullable `lastTxMessage` field
alongside its existing `state`, `partner`, `autoAnswerEnabled`, `role`, and `keying` fields,
reflecting the active controller's `LastTxMessage` at the moment the event is broadcast
(`WebSocketHub.BroadcastTxState`).

#### Scenario: txState event includes the real last transmitted message

- **WHEN** `BroadcastTxState` fires immediately after the active controller transmitted
  `"Q1ABC PD2FZ RR73"`
- **THEN** the broadcast `txState` frame SHALL contain `"lastTxMessage": "Q1ABC PD2FZ RR73"`

#### Scenario: Older frontend bundle ignoring the new field is unaffected

- **WHEN** a `txState` frame containing `lastTxMessage` is received by frontend code that does not
  read that field
- **THEN** all other existing `txState` handling SHALL proceed exactly as before — the new field is
  purely additive and SHALL NOT alter any existing field's meaning or presence
