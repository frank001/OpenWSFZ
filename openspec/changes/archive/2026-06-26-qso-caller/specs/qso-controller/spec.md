## ADDED Requirements

### Requirement: IQsoController exposes QsoRole

`IQsoController` SHALL expose a read-only property:

```csharp
QsoRole Role { get; }
```

`QsoRole` is a new enum in `OpenWSFZ.Abstractions`:

```csharp
public enum QsoRole { Answerer, Caller }
```

`QsoAnswererService.Role` SHALL return `QsoRole.Answerer`.
`QsoCallerService.Role` SHALL return `QsoRole.Caller`.

#### Scenario: Answerer role reported correctly

- **WHEN** `app.Services.GetService<IQsoController>()` resolves `QsoAnswererService`
- **THEN** `controller.Role` SHALL return `QsoRole.Answerer`

#### Scenario: Caller role reported correctly

- **WHEN** `app.Services.GetService<IQsoController>()` resolves `QsoCallerService`
- **THEN** `controller.Role` SHALL return `QsoRole.Caller`

---

### Requirement: IQsoController exposes SelectResponderAsync

`IQsoController` SHALL expose:

```csharp
Task SelectResponderAsync(
    string callsign,
    double frequencyHz,
    DateTimeOffset responseCycleStart,
    CancellationToken ct);
```

`QsoAnswererService.SelectResponderAsync` SHALL return `Task.CompletedTask` immediately
(no-op). `QsoCallerService` SHALL implement the method per the `qso-caller` capability
spec.

#### Scenario: SelectResponderAsync is a no-op on QsoAnswererService

- **WHEN** `SelectResponderAsync` is called on the answerer implementation
- **THEN** the method SHALL return without throwing and without changing state

---

### Requirement: POST /api/v1/tx/select-responder endpoint

A new endpoint `POST /api/v1/tx/select-responder` SHALL call
`IQsoController.SelectResponderAsync(callsign, frequencyHz, responseCycleStart, ct)`.

**Request body** (JSON):
```json
{
  "callsign": "Q1ABC",
  "frequencyHz": 1500.0,
  "responseCycleStartUtc": "2026-06-25T14:29:15Z"
}
```

**Response:**
- HTTP 200 with `TxStatusResponse` when the active role is `Caller` and the state is
  `WaitAnswer`.
- HTTP 405 Method Not Allowed when the active role is `Answerer` (wrong role).
- HTTP 409 Conflict when the role is `Caller` but the state is not `WaitAnswer`.

#### Scenario: Select responder returns 200 when caller is in WaitAnswer

- **WHEN** the active role is `Caller`, the state is `WaitAnswer`, and
  `POST /api/v1/tx/select-responder` is called with a valid body
- **THEN** the response SHALL be HTTP 200

#### Scenario: Select responder returns 405 when role is Answerer

- **WHEN** the active role is `Answerer` and
  `POST /api/v1/tx/select-responder` is called
- **THEN** the response SHALL be HTTP 405 Method Not Allowed

#### Scenario: Select responder returns 409 when caller is not in WaitAnswer

- **WHEN** the active role is `Caller`, the state is `TxCq` (not `WaitAnswer`), and
  `POST /api/v1/tx/select-responder` is called
- **THEN** the response SHALL be HTTP 409 Conflict

---

### Requirement: txState WebSocket event carries role field

The `txState` WebSocket event payload SHALL include a `role` string field indicating
the active QSO controller role.

Wire format (caller role):
```json
{
  "type": "txState",
  "role": "caller",
  "state": "TxCq",
  "partner": null,
  "autoAnswerEnabled": true
}
```

Wire format (answerer role, backward-compatible):
```json
{
  "type": "txState",
  "role": "answerer",
  "state": "TxAnswer",
  "partner": "Q2XYZ",
  "autoAnswerEnabled": true
}
```

`TxEventBus.Publish` and `WebSocketHub.BroadcastTxState` SHALL include the `role`
field in every `txState` broadcast. Consumers that do not recognise the `role` field
SHALL default to `"answerer"` behaviour (forward-compatibility).

The `state` field SHALL carry the raw enum value name of the active role's state enum
(`CallerState` string for the caller; `QsoState` string for the answerer).

#### Scenario: txState event includes role field for answerer

- **WHEN** `QsoAnswererService` transitions to `TxAnswer`
- **THEN** the `txState` event SHALL contain `"role": "answerer"` and
  `"state": "TxAnswer"`

#### Scenario: txState event includes role field for caller

- **WHEN** `QsoCallerService` transitions to `TxCq`
- **THEN** the `txState` event SHALL contain `"role": "caller"` and `"state": "TxCq"`

---

### Requirement: TxStatusResponse carries Role field

The `TxStatusResponse` record SHALL include a `string Role` property (`"answerer"` or
`"caller"`) reflecting `IQsoController.Role`. This field SHALL be included in responses
from `GET /api/v1/tx/status`, `POST /api/v1/tx/enable`, `POST /api/v1/tx/disable`,
`POST /api/v1/tx/abort`, and `POST /api/v1/tx/select-responder`.

#### Scenario: GET /api/v1/tx/status returns role when answerer active

- **WHEN** `TxConfig.Role = Answerer` and `GET /api/v1/tx/status` is called
- **THEN** the response body SHALL contain `"role": "answerer"`

#### Scenario: GET /api/v1/tx/status returns role when caller active

- **WHEN** `TxConfig.Role = Caller` and `GET /api/v1/tx/status` is called
- **THEN** the response body SHALL contain `"role": "caller"`
