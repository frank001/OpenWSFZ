## ADDED Requirements

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
