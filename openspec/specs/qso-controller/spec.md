# qso-controller Specification

## Purpose

This capability defines the `IQsoController` abstraction — the common interface
implemented by all QSO role services — and the HTTP endpoints that expose TX control
to the web frontend. Currently implemented by `QsoAnswererService`; `QsoCallerService`
will implement it in future.

## Requirements

---

### Requirement: IQsoController interface replaces IQsoAnswerer

A new interface `IQsoController` SHALL be defined in `OpenWSFZ.Abstractions` in place of
the retired `IQsoAnswerer` interface. `IQsoController` is the common contract implemented
by all QSO role services (currently `QsoAnswererService`; `QsoCallerService` in future).

`IQsoController` SHALL expose:
- `QsoState State { get; }` — current state machine state
- `string? Partner { get; }` — active partner callsign, `null` when `State == Idle`
- `Task AbortAsync(CancellationToken ct)` — immediate halt and return to `Idle`

`IQsoAnswerer.cs` SHALL be deleted from `OpenWSFZ.Abstractions`. `QsoAnswererService`
SHALL be updated to implement `IQsoController`. All DI registrations and consumers in
`OpenWSFZ.Web` and `OpenWSFZ.Daemon` SHALL reference `IQsoController` in place of
`IQsoAnswerer`.

QSO roles are exclusive: at any given time only one `IQsoController` implementation SHALL
be active. No two role services SHALL transmit concurrently.

#### Scenario: QsoAnswererService resolves as IQsoController

- **WHEN** `WebApp.Create` is called with a fully-wired `QsoAnswererService` registered
  in the DI container
- **THEN** `app.Services.GetService<IQsoController>()` SHALL return the
  `QsoAnswererService` instance (not null)

#### Scenario: IQsoAnswerer no longer resolvable

- **WHEN** `WebApp.Create` is called with the updated DI registrations
- **THEN** `app.Services.GetService<IQsoAnswerer>()` SHALL return `null` (interface
  removed from the container)

---

### Requirement: TxStatusResponse includes autoAnswerEnabled

The `TxStatusResponse` record (returned by `GET /api/v1/tx/status`, `POST /api/v1/tx/enable`, `POST /api/v1/tx/disable`, and `POST /api/v1/tx/abort`) SHALL include a boolean field `AutoAnswerEnabled` reflecting the current value of `tx.autoAnswer` in `IConfigStore` at the time of the response.

`POST /api/v1/tx/abort` SHALL always return `AutoAnswerEnabled: false` in its response,
since abort unconditionally disarms the system (supervised single-QSO model,
D-TX-UI-001 — UAT decision 2026-06-22).

#### Scenario: GET /api/v1/tx/status reflects enabled state

- **WHEN** `GET /api/v1/tx/status` is called and `config.Tx.AutoAnswer` is `true`
- **THEN** the response SHALL be HTTP 200 with JSON `{ "state": "…", "partner": …, "autoAnswerEnabled": true }`

#### Scenario: GET /api/v1/tx/status reflects disabled state

- **WHEN** `GET /api/v1/tx/status` is called and `config.Tx.AutoAnswer` is `false`
- **THEN** the response body SHALL contain `"autoAnswerEnabled": false`

---

### Requirement: POST /api/v1/tx/enable endpoint

A new endpoint `POST /api/v1/tx/enable` SHALL set `tx.autoAnswer = true` in the
persisted config and return a `TxStatusResponse`. No request body is required.

The endpoint SHALL resolve `IQsoController` from the container to populate the `state`
and `partner` fields of the response.

#### Scenario: Enable sets autoAnswer and returns status

- **WHEN** `POST /api/v1/tx/enable` is called
- **THEN** the response SHALL be HTTP 200
- **AND** the response body SHALL contain `"autoAnswerEnabled": true`
- **AND** subsequent calls to `GET /api/v1/config` SHALL return `tx.autoAnswer = true`

#### Scenario: Enable is idempotent

- **WHEN** `POST /api/v1/tx/enable` is called twice in succession
- **THEN** both responses SHALL be HTTP 200 with `"autoAnswerEnabled": true`
- **AND** no error SHALL be returned

#### Scenario: Enable returns current QSO state

- **WHEN** `POST /api/v1/tx/enable` is called while the answerer is in `WaitReport`
  with partner `"Q2XYZ"`
- **THEN** the response body SHALL contain `"state": "WaitReport"` and
  `"partner": "Q2XYZ"`

---

### Requirement: POST /api/v1/tx/disable endpoint

A new endpoint `POST /api/v1/tx/disable` SHALL set `tx.autoAnswer = false` in the
persisted config and return a `TxStatusResponse`. No request body is required.

The endpoint SHALL NOT abort any in-progress QSO; stopping an active session is a
separate action performed via `POST /api/v1/tx/abort`. This mirrors the WSJT-X model
where disarming TX does not immediately halt an in-progress exchange.

#### Scenario: Disable sets autoAnswer and returns status

- **WHEN** `POST /api/v1/tx/disable` is called
- **THEN** the response SHALL be HTTP 200
- **AND** the response body SHALL contain `"autoAnswerEnabled": false`
- **AND** subsequent calls to `GET /api/v1/config` SHALL return `tx.autoAnswer = false`

#### Scenario: Disable does not abort an active QSO

- **WHEN** `POST /api/v1/tx/disable` is called while a QSO exchange is in progress
  (state ≠ `Idle`)
- **THEN** `IQsoController.State` SHALL remain unchanged (the active exchange continues)
- **AND** no transmission SHALL be interrupted by the disable call alone

#### Scenario: Disable is idempotent

- **WHEN** `POST /api/v1/tx/disable` is called twice in succession
- **THEN** both responses SHALL be HTTP 200 with `"autoAnswerEnabled": false`

---

### Requirement: AnswerCqAsync — phase-aware targeted QSO answering (TX-D01)

`IQsoController` SHALL expose a method:

```csharp
Task AnswerCqAsync(string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct);
```

`cqCycleStart` is the UTC start time of the FT8 decode window in which the CQ was
received (the cycle boundary at which the 15-second receive window began).

`QsoAnswererService.AnswerCqAsync` SHALL:
1. Return without action if the current state is not `Idle`.
2. Derive the required TX answer phase from `cqCycleStart.Second % 30`:
   - `== 0` → CQ was A-phase (:00/:30) → answer on B-phase (:15/:45)
   - `== 15` → CQ was B-phase (:15/:45) → answer on A-phase (:00/:30)
3. Store callsign, frequency, answer phase, and a "pending-set-at" timestamp as pending-target
   fields (`_pendingTargetCallsign`, `_pendingTargetFrequencyHz`,
   `_pendingTargetAnswerPhase`, `_pendingTargetSetAt`).
4. Save `tx.autoAnswer = true` in `IConfigStore`.
5. Return — TX is NOT initiated immediately.

`HandleIdleAsync` (called once per cycle boundary) SHALL apply, in order: a timeout guard,
a phase-match check, a phase-mismatch skip, and — if no pending target is held — the normal
`autoAnswer` CQ-detection path. The phase-mismatch skip ensures the system never transmits in
the same phase as the CQ station (which would produce a TX collision at the remote end).
`AbortAsync` / `SafeAbortToIdleAsync` SHALL clear all pending-target fields.

#### Scenario: Timeout guard clears a stale pending target

- **WHEN** `HandleIdleAsync` is called, a pending target is held, and
  `utcNow - _pendingTargetSetAt > 60s`
- **THEN** all pending-target fields SHALL be cleared, a warning SHALL be logged, and the
  call SHALL return without transmitting

#### Scenario: Phase match fires TX for the pending target

- **WHEN** `HandleIdleAsync` is called, a pending target is held, and the current cycle's
  phase (`batch.CycleStart.Second % 30`) matches `_pendingTargetAnswerPhase`
- **THEN** the pending-target fields SHALL be cleared and TX SHALL execute for the pending
  callsign/frequency, whether or not the originating CQ is present in the current batch

#### Scenario: Phase mismatch retains the pending target without answering

- **WHEN** `HandleIdleAsync` is called, a pending target is held, and the current cycle's
  phase does not match `_pendingTargetAnswerPhase`
- **THEN** the call SHALL return immediately without answering any CQ from the batch, and
  the pending target SHALL be retained for the next cycle

#### Scenario: Normal path applies standard CQ detection when no pending target is held

- **WHEN** `HandleIdleAsync` is called and no pending target is held
- **THEN** the standard `autoAnswer` CQ-detection logic SHALL apply

---

### Requirement: POST /api/v1/tx/answer-cq endpoint

A new endpoint `POST /api/v1/tx/answer-cq` SHALL call
`IQsoController.AnswerCqAsync(callsign, frequencyHz, cqCycleStart, ct)`.

**Request body** (JSON):
```json
{ "callsign": "Q1ABC", "frequencyHz": 1500.0, "cqCycleStartUtc": "2026-06-22T17:29:15Z" }
```

`cqCycleStartUtc` is the UTC cycle-start timestamp from the decode row (ISO 8601).

**Response:** HTTP 200 with `TxStatusResponse`. Since TX has not yet fired, the returned
`state` will be `"Idle"`, `partner` will be `null`, and `autoAnswerEnabled` will be `true`.

If the controller is not in `Idle` state at the time of the call, the endpoint SHALL
return HTTP 409 Conflict with no body.

#### Scenario: Answer CQ queues a phase-aware pending target and returns 200

- **WHEN** the controller is `Idle` and `POST /api/v1/tx/answer-cq` is called with
  `{ "callsign": "Q1ABC", "frequencyHz": 1500, "cqCycleStartUtc": "2026-06-22T17:29:15Z" }`
- **THEN** the response SHALL be HTTP 200
- **AND** `autoAnswerEnabled` SHALL be `true` in the response body
- **AND** `state` SHALL be `"Idle"` (TX has not fired yet)
- **AND** `config.Tx.AutoAnswer` SHALL be `true` in `IConfigStore`
- **AND** the pending answer phase SHALL be A-phase (since :15 → B-phase CQ → A-phase answer)

#### Scenario: HandleIdleAsync fires TX only on the correct answer phase

- **GIVEN** a pending target with answer phase A-phase
- **WHEN** `HandleIdleAsync` is called with a B-phase batch (cycle at :15)
- **THEN** no TX SHALL be executed and the pending target SHALL remain set

- **WHEN** `HandleIdleAsync` is called next with an A-phase batch (cycle at :30)
- **THEN** TX SHALL be executed for the pending callsign and the pending target SHALL be cleared

#### Scenario: Pending target times out after 60 seconds

- **GIVEN** a pending target set at time T
- **WHEN** `HandleIdleAsync` is called at time T + 61s
- **THEN** the pending target SHALL be cleared
- **AND** no TX SHALL be executed
- **AND** a warning SHALL be logged

#### Scenario: Answer CQ rejected when not Idle

- **WHEN** the controller state is `TxAnswer` (or any non-Idle state) and
  `POST /api/v1/tx/answer-cq` is called
- **THEN** the response SHALL be HTTP 409 Conflict

#### Scenario: Pending target is cleared on abort

- **WHEN** a pending target callsign is set and `POST /api/v1/tx/abort` is called
- **THEN** all pending-target fields SHALL be cleared
- **AND** no TX SHALL occur for the pending callsign after the abort

---

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

---

### Requirement: IQsoController exposes GracefulStopAsync

`IQsoController` SHALL expose `Task GracefulStopAsync(CancellationToken ct = default)`, defaulting
to a no-op implementation so role services with no graceful-stop concept (currently
`QsoAnswererService`) require no change. `QsoCallerService` SHALL override it with the behaviour
specified in the `qso-caller` capability. `QsoControllerRouter` SHALL delegate
`GracefulStopAsync` to `ActiveController`, matching its existing `AbortAsync` delegation.

A graceful stop is distinct from `AbortAsync`: it SHALL NOT invoke `IPttController.KeyUpAsync` or
otherwise interrupt any TX sample already in progress. The active controller SHALL return to
`Idle` only once it reaches its next natural wait point.

#### Scenario: QsoAnswererService's GracefulStopAsync is a no-op

- **WHEN** `GracefulStopAsync` is called on a `QsoAnswererService` instance
- **THEN** it SHALL return a completed task without altering `State` or `Partner`
- **AND** it SHALL NOT invoke `IPttController.KeyUpAsync`

#### Scenario: QsoControllerRouter delegates to the active controller

- **WHEN** `QsoControllerRouter.GracefulStopAsync` is called while `QsoCallerService` is the
  active controller
- **THEN** the call SHALL be forwarded to `QsoCallerService.GracefulStopAsync`

---

### Requirement: POST /api/v1/tx/stop-cq endpoint

A new endpoint `POST /api/v1/tx/stop-cq` SHALL call `IQsoController.GracefulStopAsync` on the
resolved controller and return a `TxStatusResponse` reflecting the state at the time of the
call (which may still be a non-`Idle`, mid-TX state — the request does not wait for the stop to
complete). No request body is required.

Unlike `POST /api/v1/tx/abort`, this endpoint SHALL NOT hardcode `AutoAnswerEnabled: false` in its
response, since the service may still be completing an in-progress TX at the time of the response.

#### Scenario: Stop-cq requests a graceful stop and returns current state

- **WHEN** `POST /api/v1/tx/stop-cq` is called while `QsoCallerService` is active and in
  `WaitAnswer`
- **THEN** the response SHALL be HTTP 200
- **AND** `GracefulStopAsync` SHALL have been called on the active controller

#### Scenario: Stop-cq is unavailable when no controller is registered

- **WHEN** `POST /api/v1/tx/stop-cq` is called and no `IQsoController` is registered in the
  container
- **THEN** the response SHALL be HTTP 503 with a problem body (`"TX controller not available."`),
  matching the existing convention used by `/api/v1/tx/answer-cq` and `/api/v1/tx/select-responder`
  — not an unhandled exception
