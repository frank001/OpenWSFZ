## ADDED Requirements

### Requirement: Graceful stop returns the caller to Idle without interrupting TX

`QsoCallerService.GracefulStopAsync` SHALL request that the state machine return to `Idle` at its
next natural wait point, without cancelling any in-progress transmission. If `_callerState` is
already `Idle`, the call SHALL be a no-op.

Unlike `AbortAsync` (which cancels `_txCts` and calls `IPttController.KeyUpAsync` to kill audio
immediately), a graceful stop SHALL let any TX sample already playing finish naturally. The state
machine SHALL transition to `Idle` via the existing `SafeAbortToIdleAsync` path (reason: `"Operator
stop"`) once it next reaches a point where it would otherwise read the next decode batch.

To ensure a stop requested while the state machine is waiting (rather than transmitting) is
honoured within the current 15 s cycle rather than the next one, `WaitRr73` SHALL be added to the
set of states eligible for the existing wakeup-channel mechanism, alongside the already-eligible
`Idle` and `WaitAnswer`.

Requesting a graceful stop more than once before it takes effect SHALL be idempotent — a second
call SHALL NOT error, double-transition, or otherwise change the outcome versus a single call.

#### Scenario: Graceful stop while transmitting lets the sample finish

- **WHEN** `GracefulStopAsync` is called while `_callerState` is `TxCq` (a CQ sample is currently
  being transmitted)
- **THEN** `IPttController.KeyUpAsync` SHALL NOT be called as a result of this request
- **AND** the in-progress transmission SHALL complete normally
- **AND** the state machine SHALL transition to `Idle` after the transmission completes, without
  transmitting again

#### Scenario: Graceful stop while waiting for an answer completes within the current cycle

- **WHEN** `GracefulStopAsync` is called while `_callerState` is `WaitAnswer`
- **THEN** the state machine SHALL transition to `Idle` within the current decode cycle (it SHALL
  NOT wait for the next scheduled 15 s batch)

#### Scenario: Graceful stop while waiting for RR73 completes within the current cycle

- **WHEN** `GracefulStopAsync` is called while `_callerState` is `WaitRr73`
- **THEN** the state machine SHALL transition to `Idle` within the current decode cycle, consistent
  with the `WaitAnswer` case

#### Scenario: Graceful stop when already Idle is a no-op

- **WHEN** `GracefulStopAsync` is called while `_callerState` is already `Idle`
- **THEN** no state transition, log entry, or PTT call SHALL result

#### Scenario: Two graceful-stop requests in quick succession are idempotent

- **WHEN** `GracefulStopAsync` is called twice in immediate succession while the service is
  transitioning towards `Idle` in response to the first call
- **THEN** neither call SHALL raise an error
- **AND** the service SHALL reach `Idle` exactly once, at the same point it would have reached from
  a single request
