## ADDED Requirements

### Requirement: CallerState enum

A `CallerState` enum SHALL be defined in `OpenWSFZ.Abstractions` representing the
states of the FT8 QSO caller state machine.

| State        | Description                                             |
|--------------|---------------------------------------------------------|
| `Idle`       | Listening; not calling CQ                               |
| `TxCq`       | Transmitting: `CQ {callsign} {grid}`                    |
| `WaitAnswer` | Waiting for a station to respond to the CQ              |
| `TxReport`   | Transmitting signal report: `{partner} {callsign} +00`  |
| `WaitRr73`   | Waiting for partner's `R+{report}` (to send RR73)       |
| `TxRr73`     | Transmitting: `{partner} {callsign} RR73`               |
| `QsoComplete`| QSO complete; writing ADIF; transitioning back to Idle  |

#### Scenario: CallerState values cover the full caller exchange

- **WHEN** `QsoCallerService` completes a full QSO (CQ → answer → report → RR73)
- **THEN** the service SHALL have transitioned through `TxCq`, `WaitAnswer`,
  `TxReport`, `WaitRr73`, `TxRr73`, `QsoComplete`, and back to `Idle` in that order

---

### Requirement: QsoCallerService state machine

A new component `QsoCallerService` SHALL implement `IQsoController` and
`IHostedService` (via `BackgroundService`) for the FT8 QSO caller role. It SHALL
subscribe to the same `Channel<DecodeBatch>` as `QsoAnswererService`.

The service SHALL only transmit when `tx.autoAnswer` is `true`. When `false` (the
default), the state machine SHALL remain in `Idle` and no transmission SHALL occur.

The service SHALL expose its state via `IQsoController.State` (mapped to the nearest
`QsoState` equivalent per design.md D8) and its active partner via
`IQsoController.Partner`.

`QsoCallerService` SHALL be registered in the DI container and hosted service list
**only** when `TxConfig.Role == TxRole.Caller`. When `Role == TxRole.Answerer` (the
default), `QsoCallerService` SHALL NOT be instantiated.

#### Scenario: Service starts in Idle state

- **WHEN** `QsoCallerService` is started via `IHostedService.StartAsync`
- **THEN** the current `CallerState` SHALL be `Idle` and `Partner` SHALL be `null`

#### Scenario: AutoAnswer disabled — no CQ transmitted

- **WHEN** `tx.autoAnswer` is `false` and the service is in `Idle`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit regardless of
  the `CallerPartnerSelect` setting

#### Scenario: AutoAnswer enabled — CQ is transmitted

- **WHEN** `tx.autoAnswer` is `true` and the service is in `Idle` and a decode batch
  arrives
- **THEN** the service SHALL advance to `TxCq` and transmit `CQ {callsign} {grid}`

---

### Requirement: TxCq — transmitting the CQ call

While in `Idle` with `tx.autoAnswer = true`, on the first decode batch received the
service SHALL:

1. Validate that `tx.callsign` and `tx.grid` are non-empty; if not, log a Warning and
   remain in `Idle`.
2. Set `_partner = null`; record `_qsoStartUtc`; start the watchdog.
3. Apply the TX frequency from `TxAudioOffsetHz` (HoldTxFreq semantics are identical
   to `QsoAnswererService`).
4. Compose: `CQ {callsign} {grid}`; encode; synthesise; transmit.
5. Advance to `WaitAnswer` after playback completes.
6. Set `_skipNextRetry = true` (A-01: next cycle is the answer window — do not count
   as a missed response).

#### Scenario: CQ message is correctly formatted

- **WHEN** `tx.callsign = "PD2FZ"` and `tx.grid = "JO33"` and the service transitions
  to `TxCq`
- **THEN** the transmitted message SHALL be `"CQ PD2FZ JO33"`

#### Scenario: Missing callsign suppresses CQ

- **WHEN** `tx.callsign` is empty or whitespace
- **THEN** the service SHALL remain in `Idle` and log a Warning

---

### Requirement: WaitAnswer — waiting for a CQ response

While in `WaitAnswer`, the service SHALL scan each decode batch for messages matching
`{our_callsign} {any_callsign} {any_grid}` (i.e., a station answering our CQ with
their callsign and grid).

**`CallerPartnerSelect = First`:** The first matching response found in the batch SHALL
be selected automatically. The service SHALL immediately advance to `TxReport`.

**`CallerPartnerSelect = None`:** No automatic selection. The service SHALL apply the
CSS class `decode-responder` signal by broadcasting a `txState` event (state
`"WaitAnswer"`, partner `null`). The operator selects a responder by double-clicking a
highlighted row; `POST /api/v1/tx/select-responder` calls `SelectResponderAsync`.
`SelectResponderAsync` stores a `_pendingResponder` (callsign, frequency, answer
phase) and writes a wakeup batch. On the next cycle at the correct answer phase, the
service fires `TxReport` for the pending responder.

If no response arrives within the retry/watchdog budget, the service retransmits the CQ
(see Retry requirement below).

The A-01 skip guard is applied: the first cycle after entering `WaitAnswer` is the
CQ station's own TX window; silence there does not count as a missed response.

#### Scenario: First mode auto-engages on first response

- **WHEN** `CallerPartnerSelect = First`, the service is in `WaitAnswer`, and a
  decode batch contains `"PD2FZ Q1ABC JO22"`  (where `PD2FZ` is our callsign)
- **THEN** the service SHALL select `Q1ABC` as partner and advance to `TxReport`

#### Scenario: None mode does not auto-engage

- **WHEN** `CallerPartnerSelect = None`, the service is in `WaitAnswer`, and a
  decode batch contains `"PD2FZ Q1ABC JO22"`
- **THEN** the service SHALL remain in `WaitAnswer` and SHALL NOT transmit

#### Scenario: None mode advances after SelectResponderAsync

- **WHEN** `CallerPartnerSelect = None` and `SelectResponderAsync("Q1ABC", 1500.0,
  cycleStart, ct)` is called while the service is in `WaitAnswer`
- **THEN** the service SHALL store `Q1ABC` as the pending responder and SHALL fire
  `TxReport` at the next cycle boundary of the correct answer phase

#### Scenario: A-01 guard — first empty cycle is skipped

- **WHEN** the service enters `WaitAnswer` and the first subsequent batch is empty
  (no response)
- **THEN** the service SHALL NOT count this as a missed response (it was our own TX
  window); `_skipNextRetry` SHALL be cleared and no retry SHALL be triggered

---

### Requirement: TxReport — transmitting the signal report

When the service has selected a partner (via `First` auto-selection or `None` operator
click), it SHALL:

1. Set `_partner = selectedCallsign`.
2. Compose: `{partner} {callsign} +00` (fixed report; TX-D04 deferred).
3. Encode; synthesise at `_lastTxFreqHz`; transmit.
4. Advance to `WaitRr73`.
5. Set `_skipNextRetry = true` (A-01).
6. Arm H6 AP decode constraints for `(callsign, partner)`.
7. Reset watchdog.

#### Scenario: Signal report message is correctly formatted

- **WHEN** `callsign = "PD2FZ"`, `partner = "Q1ABC"`, and the service transmits from
  `TxReport`
- **THEN** the transmitted message SHALL be `"Q1ABC PD2FZ +00"`

---

### Requirement: WaitRr73 — waiting for partner's R+report

While in `WaitRr73`, the service SHALL scan each decode batch for:
- A message from `partner` to `us` matching `R+{nn}` or `R-{nn}` in the payload
  (the partner's roger report) → advance to `TxRr73`.
- A message from `partner` to another station → abort ("Partner {partner} is working
  another station").

If no matching message is found: apply A-01 skip guard then retry.

#### Scenario: R+report triggers TxRr73

- **WHEN** the service is in `WaitRr73` and a batch contains `"PD2FZ Q1ABC R-07"`
  (from partner `Q1ABC` to us `PD2FZ`)
- **THEN** the service SHALL advance to `TxRr73`

#### Scenario: Partner working another station aborts

- **WHEN** the service is in `WaitRr73` and a batch contains a message from `Q1ABC`
  addressed to a callsign other than `PD2FZ`
- **THEN** the service SHALL abort to `Idle` with reason
  `"Partner Q1ABC is working another station"`

---

### Requirement: TxRr73 — transmitting RR73 to complete the QSO

When a valid R+report is received, the service SHALL:

1. Compose: `{partner} {callsign} RR73`.
2. Transmit.
3. Advance to `QsoComplete`.
4. Write an ADIF record (same fields as `QsoAnswererService`: partner callsign, grid,
   RST sent `+00`, RST received (from the R+{nn} payload), QSO start/end UTC,
   operator callsign, grid, dial frequency).
5. Call `SafeAbortToIdleAsync` (which saves `autoAnswer = false`, clears state, and
   broadcasts a disarmed `txState` event).

#### Scenario: RR73 message is correctly formatted

- **WHEN** `callsign = "PD2FZ"` and `partner = "Q1ABC"` and the service transitions
  to `TxRr73`
- **THEN** the transmitted message SHALL be `"Q1ABC PD2FZ RR73"`

#### Scenario: ADIF record written after QSO complete

- **WHEN** `QsoCallerService` completes a QSO with partner `Q1ABC`
- **THEN** an ADIF record SHALL be appended with `CALL = Q1ABC`, `RST_SENT = +00`,
  `RST_RCVD` from the received R+{nn} payload, and the correct start/end UTC

#### Scenario: System disarms after QSO complete (supervised model)

- **WHEN** `TxRr73` completes and ADIF is logged
- **THEN** `tx.autoAnswer` SHALL be saved as `false` in `IConfigStore`
- **AND** a `txState` event SHALL be broadcast with `state = "Idle"` and
  `autoAnswerEnabled = false`

---

### Requirement: Repeat-CQ retry logic

While in `WaitAnswer`, if no response arrives within the retry budget, the service
SHALL retransmit the CQ. The retry mechanism follows the same `RetryCount` and
`WatchdogMinutes` parameters as `QsoAnswererService`.

`RetryCount = 0` means unlimited (watchdog is the backstop). Retries do NOT reset the
watchdog.

When `RetryCount > 0` and the retry count is exhausted, the service SHALL abort to
`Idle` with reason `"No response after {RetryCount} CQ retries"` and disarm.

On retry: the service re-enters `TxCq`, retransmits `CQ {callsign} {grid}`, returns
to `WaitAnswer`, and sets `_skipNextRetry = true`.

#### Scenario: No response triggers CQ retry

- **WHEN** the service is in `WaitAnswer`, `_skipNextRetry` is `false`, and the
  decode batch is empty or contains no response to our CQ
- **THEN** the service SHALL increment `_retryCount` and retransmit the CQ

#### Scenario: Retry count exhausted aborts to Idle

- **WHEN** `RetryCount = 2` and the service has retried twice with no response
- **THEN** the service SHALL abort to `Idle` with reason
  `"No response after 2 CQ retries"` and `tx.autoAnswer` SHALL be saved as `false`

#### Scenario: Unlimited retries — watchdog fires

- **WHEN** `RetryCount = 0` and the watchdog duration elapses with no response
- **THEN** the service SHALL abort to `Idle` with reason `"Watchdog timeout"`

---

### Requirement: SelectResponderAsync — operator-driven partner selection (None mode)

`QsoCallerService.SelectResponderAsync(callsign, frequencyHz, responseCycleStart, ct)`
SHALL:

1. Return without action if `_callerState != WaitAnswer`.
2. Derive the TX answer phase from `responseCycleStart.Second % 30` (same phase
   logic as `AnswerCqAsync`: response was on phase P → we reply on the opposite phase).
3. Store `_pendingResponderCallsign`, `_pendingResponderFrequencyHz`,
   `_pendingResponderIsAPhase`, `_pendingResponderSetAt` under `_stateLock`.
4. Write a wakeup batch to `_wakeupChannel`.
5. Return — TX is not fired immediately.

The pending responder is subject to a 60-second timeout (same as `AnswerCqAsync`
pending target). If the timeout elapses, the responder is discarded and a Warning is
logged.

`SafeAbortToIdleAsync` SHALL clear all pending-responder fields.

#### Scenario: SelectResponderAsync stores pending responder and fires on correct phase

- **WHEN** `WaitAnswer` state and `SelectResponderAsync("Q1ABC", 1500.0,
  "2026-06-25T14:29:15Z", ct)` is called (B-phase response → A-phase answer)
- **THEN** the pending responder IS set with `_pendingResponderIsAPhase = true`
- **AND** when `HandleWaitAnswerAsync` is next called with an A-phase batch
- **THEN** the service SHALL fire `TxReport` for `Q1ABC`

#### Scenario: SelectResponderAsync ignored when not in WaitAnswer

- **WHEN** `_callerState` is `TxCq` (not `WaitAnswer`) and `SelectResponderAsync`
  is called
- **THEN** the call SHALL return immediately without modifying state

#### Scenario: Pending responder cleared on abort

- **WHEN** a pending responder is set and `AbortAsync` is called
- **THEN** `_pendingResponderCallsign` SHALL be `null`
- **AND** no TX SHALL occur for that responder after the abort
