## Purpose

This capability defines the QSO Caller role — the FT8 state machine that originates
a CQ call, waits for a responding station, exchanges signal reports, and completes the
QSO with RR73. The Caller role is the counterpart to the QSO Answerer role and is
implemented by `QsoCallerService`. Only one role may be active at a time; the active
role is selected by `TxConfig.Role` and takes effect after a daemon restart.

## Requirements

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

While in `Idle` with `tx.autoAnswer = true`, on the first decode batch received the service SHALL:

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
their callsign and grid), skipping any responder whose callsign is not currently
visible/engageable under the active `DecodeFilterState` (`decode-panel-filtering` capability).

**`CallerPartnerSelect = First`:** The first matching, non-filtered-out response found in the
batch SHALL be selected automatically. The service SHALL immediately advance to `TxReport`. If
every matching response in a cycle is filtered out, the service SHALL remain in `WaitAnswer` for
that cycle, exactly as if no response had been decoded — subject to the same retry/watchdog
budget as a genuinely empty cycle (the filter does not grant an exemption from retry counting).

**`CallerPartnerSelect = None`:** No automatic selection. The service SHALL apply the
CSS class `decode-responder` signal by broadcasting a `txState` event (state
`"WaitAnswer"`, partner `null`). The operator selects a responder by double-clicking a
highlighted row; `POST /api/v1/tx/select-responder` calls `SelectResponderAsync`.
A responder callsign that is currently filtered out under the active `DecodeFilterState` SHALL
NOT be highlighted as `decode-responder` and a `SelectResponderAsync` call naming a filtered-out
callsign SHALL be rejected (no state transition) — the filter applies uniformly regardless of
partner-selection mode, not only to the automatic `First` path.
`SelectResponderAsync` stores a `_pendingResponder` (callsign, frequency, answer
phase) and writes a wakeup batch. On the next cycle at the correct answer phase, the
service fires `TxReport` for the pending responder.

If no response arrives within the retry/watchdog budget, the service retransmits the CQ
(see Retry requirement below).

The A-01 skip guard is applied: the first cycle after entering `WaitAnswer` is the
CQ station's own TX window; silence there does not count as a missed response.

Once a responder has been selected and the service has advanced past `WaitAnswer`, the active
filter state SHALL NOT be re-evaluated for the remainder of that QSO — a filter change while a
QSO is in progress SHALL NOT abort it (the operator's existing Abort/Stop controls are the only
mechanism for that).

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

#### Scenario: First mode skips a filtered-out responder in favour of the next one

- **WHEN** `CallerPartnerSelect = First`, the service is in `WaitAnswer`, and a decode batch
  contains a response from `Q1TST` (filtered out under the active `DecodeFilterState`) followed
  by a response from `Q2ABC` (not filtered out)
- **THEN** the service SHALL skip `Q1TST` entirely and select `Q2ABC` as partner

#### Scenario: First mode — all responses filtered out — cycle treated as empty

- **WHEN** `CallerPartnerSelect = First` and every response in a decode batch is filtered out
  under the active `DecodeFilterState`
- **THEN** the service SHALL remain in `WaitAnswer` for that cycle, subject to the same
  retry/watchdog accounting as a genuinely empty cycle

#### Scenario: None mode — SelectResponderAsync rejects a filtered-out callsign

- **WHEN** `CallerPartnerSelect = None` and `SelectResponderAsync` is called naming a callsign
  currently filtered out under the active `DecodeFilterState`
- **THEN** the call SHALL be rejected — no `_pendingResponder` SHALL be stored and no state
  transition SHALL occur

#### Scenario: Filter change mid-QSO does not abort an already-engaged QSO

- **WHEN** the service has already advanced past `WaitAnswer` for a given partner, and the
  operator then changes the filter such that the active partner would now be filtered out
- **THEN** the in-progress QSO SHALL continue unaffected — the filter is not re-checked once
  engagement has begun

---

### Requirement: TxReport — transmitting the signal report

When the service has selected a partner (via `First` auto-selection or `None` operator click), it SHALL:

1. Set `_partner = selectedCallsign`.
2. Compose: `{partner} {callsign} {report}`, where `{report}` is the real measured `Snr` of the
   triggering decode (the matched `DecodeResult` for `First` mode; the re-derived responder decode
   for `None` mode), formatted as a two-digit signed FT8 report clamped to `±30` (e.g. `+07`,
   `-13`, `+00`) — never a fixed placeholder.
3. Persist `{report}` as `_rstSent` for reuse by the `WaitRr73` retry retransmission and the ADIF
   `RstSent` field, so a subsequent retry resends the exact value chosen here rather than a freshly
   (and potentially unavailable) recomputed one.
4. Encode; synthesise at `_lastTxFreqHz`; transmit.
5. Advance to `WaitRr73`.
6. Set `_skipNextRetry = true` (A-01).
7. Arm H6 AP decode constraints for `(callsign, partner)`.
8. Reset watchdog.

#### Scenario: Signal report message reflects the real measured SNR

- **WHEN** `callsign = "PD2FZ"`, `partner = "Q1ABC"`, the triggering decode's `Snr = -7`, and the
  service transmits from `TxReport`
- **THEN** the transmitted message SHALL be `"Q1ABC PD2FZ -07"`, not `"Q1ABC PD2FZ +00"`

#### Scenario: Signal report is clamped to the FT8 ±30 range

- **WHEN** the triggering decode's `Snr` is `+42` (outside the standard FT8 report range)
- **THEN** the transmitted report SHALL be clamped to `"+30"`

#### Scenario: WaitRr73 retry resends the same report value, not a recomputed one

- **WHEN** the service transmitted `TxReport` with a report of `"-07"` and then times out waiting
  for a roger report, triggering `RetryOrAbortAsync`'s `WaitRr73` retry branch
- **THEN** the retransmitted message SHALL again contain `"-07"` — the persisted `_rstSent` value —
  regardless of whether a fresh decode of the partner is available in the retry cycle

#### Scenario: ADIF RstSent reflects the real transmitted report

- **WHEN** a QSO completes after a `TxReport` transmission whose report was `"-07"`
- **THEN** the written `QsoRecord.RstSent` SHALL be `"-07"`, not the fixed `"+00"` placeholder

#### Scenario: AP decode constraints arm successfully for a nonstandard partner callsign

- **WHEN** the service transmits from `TxReport` with `partner` a nonstandard/compound
  callsign (e.g. `"PJ4/K1ABC"`) and `callsign` a standard basecall
- **THEN** step 7 SHALL arm H6 AP decode constraints using the extended callsign packer's
  nonstandard-callsign encoding for `partner`, rather than disabling AP decode-assist for the
  QSO (previously: either callsign failing to pack under the standard-basecall-only packer
  disabled AP entirely)

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

### Requirement: Partner grid capture for ADIF logging

The service SHALL determine whether the third token of a matched `WaitAnswer` CQ-answer message (`{our_callsign} {their_callsign} {their_grid_or_report}`) is a Maidenhead grid locator, as already validated to select/reject the match, and SHALL capture it so it is available on the `QsoRecord` written when the QSO reaches `QsoComplete` via `TxRr73` — for both `CallerPartnerSelect = First` (automatic selection) and `CallerPartnerSelect = None` (manual selection via `SelectResponderAsync`). If the third token is a signal report rather than a grid, the captured grid SHALL be `null`; the service SHALL NOT fabricate a grid value when none was sent.

#### Scenario: Grid captured under CallerPartnerSelect = First

- **WHEN** `CallerPartnerSelect = First` and a decode batch contains `"Q1OFZ Q2NOISE IO91"`
  (a valid CQ-answer to our CQ from `Q2NOISE`, including their grid `IO91`)
- **THEN** the service SHALL advance to `TxReport` and the QSO record written at
  `QsoComplete` SHALL have `PartnerGrid = "IO91"`

#### Scenario: Grid captured under CallerPartnerSelect = None (manual select)

- **WHEN** `CallerPartnerSelect = None`, a decode batch contains `"Q1OFZ Q2NOISE IO91"`, and the
  operator subsequently selects `Q2NOISE` via `SelectResponderAsync`
- **THEN** the QSO record written at `QsoComplete` SHALL have `PartnerGrid = "IO91"`, matching
  the grid from the original CQ-answer message

#### Scenario: No grid sent yields a null PartnerGrid, not a fabricated value

- **WHEN** a decode batch contains `"Q1OFZ Q2NOISE -05"` (a valid CQ-answer using a bare signal
  report instead of a grid, per existing FT8 behaviour)
- **THEN** the service SHALL still advance/select normally and the QSO record written at
  `QsoComplete` SHALL have `PartnerGrid = null`

---

### Requirement: QsoCallerService persists the text of its last transmitted message

`QsoCallerService` SHALL persist the literal text of the most recently transmitted FT8 message
(the CQ call, the signal report, or the RR73) in a field exposed via `IQsoController.LastTxMessage`,
mirroring the pattern `QsoAnswererService` already uses for its own `_lastTxMessage` field. The
persisted value SHALL be the exact string passed to `TransmitAsync` at each TX-composition site —
`ExecuteTxReportAsync`'s CQ/report messages, `RetryOrAbortAsync`'s CQ/report retransmissions — not
a value reconstructed from other fields after the fact.

`LastTxMessage` SHALL be `null` before the service has transmitted anything this process lifetime.

#### Scenario: LastTxMessage reflects the real transmitted report

- **WHEN** `ExecuteTxReportAsync` transmits `"Q1ABC PD2FZ -07"` (the real measured report, per
  `fix-tx-report-real-snr`)
- **THEN** `LastTxMessage` SHALL be `"Q1ABC PD2FZ -07"`

#### Scenario: LastTxMessage is null before any transmission

- **WHEN** `QsoCallerService` has just started and has not yet transmitted anything
- **THEN** `LastTxMessage` SHALL be `null`

#### Scenario: A retried transmission updates LastTxMessage to the same resent value

- **WHEN** `RetryOrAbortAsync` retransmits the persisted `_rstSent` report value after a timeout
- **THEN** `LastTxMessage` SHALL reflect that retransmitted message text

---

### Requirement: Repeat-CQ retry logic

While in `WaitAnswer`, if no response arrives within the retry budget, the service SHALL retransmit the CQ. The retry mechanism follows the same `RetryCount` and `WatchdogMinutes` parameters as `QsoAnswererService`.

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

`QsoCallerService.SelectResponderAsync(callsign, frequencyHz, responseCycleStart, ct)` SHALL:

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


---

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

---

### Requirement: Pending responder fires unconditionally within a correct-phase window

When `QsoCallerService` consumes an armed pending responder (set by `SelectResponderAsync` in `CallerPartnerSelect = None` mode), it SHALL fire the transmission in the first decode cycle whose phase matches the pending responder's expected phase, regardless of how many seconds into that window the consumption occurs. There SHALL be no lateness-based rejection or deferral: the only gating conditions are the phase check and the existing 60-second stale-responder expiry. This formalises behaviour already present in `HandleWaitAnswerAsync`'s pending-responder path — no code change is required by this requirement, only regression protection against a future lateness guard being added by analogy with `QsoAnswererService`'s (now-removed) one.

#### Scenario: Pending responder fires immediately even when consumed late in its window

- **WHEN** a pending responder is armed for the A phase, and the decode cycle in which its phase
  check first passes is consumed 6 s into that A-phase window
- **THEN** the service SHALL clear the pending responder and begin transmitting the report in that
  same cycle — it SHALL NOT defer to the next A-phase occurrence

#### Scenario: Wrong-phase cycle still waits for the next matching-phase window

- **WHEN** a pending responder is armed for the B phase and the current decode cycle is A phase
- **THEN** the service SHALL retain the pending responder unfired and re-evaluate it on the next
  cycle, unchanged from today

#### Scenario: Stale pending responder still expires after 60 seconds regardless of lateness

- **WHEN** a pending responder has been armed for more than 60 seconds without its phase check
  passing
- **THEN** the service SHALL discard it and log a Warning

---

### Requirement: Transmission never keys past the current window's boundary

`TransmitAsync` (used by every transmission `QsoCallerService` sends — CQ, report, RR73/73 retries and continuations) SHALL, immediately before loading audio into the `IPttController`, compute the time remaining in the current 15-second cycle window from the moment of the call and truncate the synthesised sample buffer so that playback cannot extend past that window's boundary. A transmission that begins early enough to play in full SHALL be unaffected. If the computed remaining time is zero or negative at the moment `TransmitAsync` is entered, the service SHALL skip `LoadAudio`/`KeyDownAsync` entirely for that call and log at Debug level, rather than keying PTT with an empty buffer.

A transmission shortened by this requirement SHALL be treated identically to a full-length transmission for retry-counter accounting, watchdog reset, and ADIF logging purposes.

#### Scenario: Late-armed transmission is truncated to fit the remaining window

- **WHEN** `TransmitAsync` is called 9 s into its 15 s window (6 s remaining)
- **THEN** the synthesised audio buffer SHALL be truncated to at most 6 s of playback before
  `LoadAudio` is called, and the resulting `KeyDownAsync` call SHALL NOT extend transmission past
  the window boundary

#### Scenario: On-time transmission is not truncated

- **WHEN** `TransmitAsync` is called at the start of its window (0 s in, full 15 s remaining)
- **THEN** the full synthesised 12.64 s buffer SHALL be passed to `LoadAudio` unmodified, exactly as
  before this change

#### Scenario: Zero remaining time skips transmission rather than keying an empty buffer

- **WHEN** `TransmitAsync` is entered at or after the window's boundary (zero or negative time
  remaining)
- **THEN** the service SHALL NOT call `LoadAudio` or `KeyDownAsync`, SHALL log at Debug level, and
  SHALL return without transmitting

#### Scenario: Truncated transmission counts toward retry/watchdog like a full one

- **WHEN** a transmission is truncated by this requirement and receives no matching response in the
  following decode cycle
- **THEN** the retry counter SHALL increment exactly as it would for a full-length transmission
  that went unanswered
