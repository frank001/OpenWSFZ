# qso-answerer Specification

## Purpose

Specifies `QsoAnswererService`'s state machine: auto-answering a decoded CQ, retry-on-no-
response behaviour, ignoring decodes not addressed to us, aborting when the caller works
another station, RRR/RR73 handling, watchdog abort, operator abort, and the TX state
WebSocket event.

## Requirements

### Requirement: Answerer state machine

A new component `QsoAnswererService` SHALL implement the FT8 QSO answerer protocol as a finite state machine with the following states:

| State | Description |
|---|---|
| `Idle` | Listening; ready to answer a CQ |
| `TxAnswer` | Transmitting answer: `CALLER  OURS  GRID` |
| `WaitReport` | Waiting for caller's signal report |
| `TxReport` | Transmitting: `CALLER  OURS  R+00` |
| `WaitRr73` | Waiting for caller's RR73 or RRR |
| `Tx73` | Transmitting: `CALLER  OURS  73` |
| `QsoComplete` | Signalling completion; writing ADIF; returning to Idle |

The service SHALL be registered as an `IHostedService` singleton and SHALL subscribe to a `Channel<IReadOnlyList<DecodeResult>>` fed one batch per decode cycle by the existing decode pipeline.

The service SHALL expose its current state and active partner callsign for consumption by `GET /api/v1/tx/status`.

The service SHALL only activate auto-answer behaviour when `tx.autoAnswer` is `true`. When `false` (the default), the state machine SHALL remain in `Idle` regardless of decoded CQs and no transmission SHALL occur.

#### Scenario: Service starts in Idle state

- **WHEN** `QsoAnswererService` is started via `IHostedService.StartAsync`
- **THEN** the current state SHALL be `Idle` and the active partner SHALL be `null`

#### Scenario: AutoAnswer disabled — CQ ignored

- **WHEN** `tx.autoAnswer` is `false` and a decode batch contains `CQ Q1TST JO22`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit

---

### Requirement: Auto-answer first decoded CQ

While in `Idle` with `tx.autoAnswer = true`, the service SHALL inspect each decode batch for FT8 messages matching the CQ pattern (`CQ <callsign> <grid>`), skipping any CQ whose callsign is not currently visible/engageable under the active `DecodeFilterState` (`decode-panel-filtering` capability). On the first matching, non-filtered-out CQ, the service SHALL:

1. Record the caller callsign and audio frequency
2. Generate the answer message: `<caller>  <ours>  <grid>` where `<ours>` and `<grid>` come from `tx.callsign` and `tx.grid`
3. Encode and synthesise the TX audio at the caller's audio frequency
4. Call `IPttController.KeyDownAsync` to begin transmission
5. Advance to `TxAnswer`; after playback completes, advance to `WaitReport`

If multiple CQs are decoded in the same cycle, the first non-filtered-out one in the decoded list SHALL be selected — a filtered-out CQ SHALL be skipped entirely for this cycle's selection, not merely deprioritised. If every decoded CQ in a cycle is filtered out, the service SHALL remain in `Idle` and SHALL NOT transmit, exactly as if no CQ had been decoded at all. If `tx.callsign` or `tx.grid` is empty or whitespace-only, the CQ SHALL be ignored and a Warning logged.

Once a CQ has been selected and the service has advanced past `Idle`, the active filter state SHALL NOT be re-evaluated for the remainder of that QSO — a filter change while a QSO is in progress SHALL NOT abort it (the operator's existing Abort/Stop controls are the only mechanism for that).

**TX frequency selection:** When the service answers a CQ and `tx.holdTxFreq` is `false`, the TX frequency SHALL be the caller's decoded `freqHz` (existing behaviour). The service SHALL additionally update `tx.txAudioOffsetHz` in `IConfigStore` to match and push an `audioOffset` WebSocket event so the waterfall cursor reflects the actual transmission frequency.

When `tx.holdTxFreq` is `true`, the TX frequency SHALL be `tx.txAudioOffsetHz` from the current config. The service SHALL NOT modify `txAudioOffsetHz` or push an `audioOffset` event in this case.

This TX frequency selection logic applies to all transmitted messages in a session (answer, report, Tx73, retries). The TX frequency is fixed at the start of each CQ answer and does not change mid-session regardless of `holdTxFreq`.

#### Scenario: CQ triggers auto-answer

- **WHEN** the service is in `Idle`, `tx.autoAnswer` is `true`, and a decode batch contains `CQ Q1TST JO22`
- **THEN** the service SHALL advance to `TxAnswer`, begin transmitting `Q1TST Q1OFZ JO33`, and advance to `WaitReport` after the TX slot completes

#### Scenario: Multiple CQs in one cycle — first selected

- **WHEN** a decode batch contains `CQ Q1TST JO22` and `CQ Q2ABC KP20`
- **THEN** the service SHALL answer `Q1TST` (first in list) and ignore `Q2ABC`

#### Scenario: Non-CQ decodes in Idle are ignored

- **WHEN** the service is in `Idle` and the decode batch contains only `Q2ABC Q3DEF +05`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit

#### Scenario: Empty callsign or grid prevents auto-answer

- **WHEN** `tx.callsign` is empty and a CQ is decoded
- **THEN** the service SHALL ignore the CQ, log a Warning, and remain in `Idle`

#### Scenario: Filtered-out CQ is skipped, next non-filtered CQ engaged instead

- **WHEN** a decode batch contains `CQ Q1TST JO22` (filtered out under the active
  `DecodeFilterState`) followed by `CQ Q2ABC KP20` (not filtered out)
- **THEN** the service SHALL skip `Q1TST` entirely and answer `Q2ABC`

#### Scenario: All CQs in a cycle filtered out — no engagement

- **WHEN** every CQ in a decode batch is filtered out under the active `DecodeFilterState`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit, identical to a cycle with no
  CQs at all

#### Scenario: Filter change mid-QSO does not abort an already-engaged QSO

- **WHEN** the service has already advanced past `Idle` for a given partner, and the operator then
  changes the filter such that the active partner would now be filtered out
- **THEN** the in-progress QSO SHALL continue unaffected — the filter is not re-checked once
  engagement has begun

#### Scenario: Hold TX Freq false — TX at caller's frequency, cursor updated

- **WHEN** the service answers a CQ from `Q1TST` at 1234 Hz and `tx.holdTxFreq` is `false`
- **THEN** the service SHALL transmit at 1234 Hz
- **AND** `IConfigStore.Current.Tx.TxAudioOffsetHz` SHALL be updated to 1234
- **AND** an `audioOffset` WebSocket event SHALL be pushed with `txHz = 1234`

#### Scenario: Hold TX Freq true — TX at operator-set frequency, cursor unchanged

- **WHEN** the service answers a CQ from `Q1TST` at 1234 Hz and `tx.holdTxFreq` is `true` and `tx.txAudioOffsetHz` is 1500
- **THEN** the service SHALL transmit at 1500 Hz
- **AND** `IConfigStore.Current.Tx.TxAudioOffsetHz` SHALL remain 1500
- **AND** no `audioOffset` WebSocket event SHALL be pushed by the answerer

---

### Requirement: External reply engages a specific decoded CQ

`QsoAnswererService` SHALL expose `Task<bool> TryEngageExternal(string callsign, CancellationToken
ct = default)`, callable in-process by the `external-reporting` capability's inbound Reply handler
(via `IExternalReplyTarget`, implemented by `QsoControllerRouter`). When called while the service is
in `Idle` and `callsign` matches the source callsign of a CQ present in the most recent decode batch
that is not filtered out under the active `DecodeFilterState`, the service SHALL engage exactly as it
would for that CQ under its existing auto-answer path (Requirement: "Auto-answer first decoded CQ"),
advancing to `TxAnswer` and returning `true`. This SHALL apply regardless of the value of
`tx.autoAnswer` — an explicit external reply is a one-shot manual instruction, not automatic
behaviour, so it is not gated by the auto-answer toggle.

If `callsign` does not match any currently decoded, non-filtered-out CQ, or the service is not in
`Idle`, or `tx.callsign`/`tx.grid` is empty, the call SHALL take no action and return `false`; a
matching Information-level log entry SHALL record the reason.

#### Scenario: External reply engages a matching decoded CQ

- **WHEN** the service is in `Idle`, the most recent decode batch contains `CQ Q1TST JO22` (not
  filtered out), and `TryEngageExternal("Q1TST")` is called
- **THEN** the service SHALL advance to `TxAnswer`, begin transmitting the answer to `Q1TST`, and the
  call SHALL return `true`

#### Scenario: External reply works even when autoAnswer is disabled

- **WHEN** `tx.autoAnswer` is `false`, the service is `Idle`, and `TryEngageExternal("Q1TST")` is
  called for a callsign present as a CQ in the current decode batch
- **THEN** the service SHALL engage `Q1TST` exactly as in the enabled case, unaffected by
  `tx.autoAnswer`

#### Scenario: External reply to an unknown callsign is a no-op

- **WHEN** `TryEngageExternal("Q9ZZZ")` is called and no CQ from `Q9ZZZ` is present in the most
  recent decode batch
- **THEN** the service SHALL remain `Idle`, SHALL NOT transmit, and the call SHALL return `false`

#### Scenario: External reply to a filtered-out callsign is a no-op

- **WHEN** `TryEngageExternal("Q1TST")` is called and `Q1TST`'s CQ is present but filtered out under
  the active `DecodeFilterState`
- **THEN** the service SHALL remain `Idle`, SHALL NOT transmit, and the call SHALL return `false`

#### Scenario: External reply while already engaged is a no-op

- **WHEN** the service is not in `Idle` (already mid-QSO with a different partner) and
  `TryEngageExternal` is called for any callsign
- **THEN** the in-progress QSO SHALL continue unaffected, no new engagement SHALL occur, and the call
  SHALL return `false`

---

### Requirement: H6 AP decode constraint arming

The service SHALL arm H6 directed AP decode constraints for the active `(callsign, partner)` pair after transmitting the answer (`"{partner} {callsign} {grid}"`) and advancing from `TxAnswer` to `WaitReport`, using the callsign packer's full encoding support (standard basecalls, special tokens, and nonstandard/compound callsigns via `ihashcall`). AP decode-assist SHALL be disabled for the QSO only when the packer genuinely cannot encode one of the two callsigns (an unsupported form — see `ap-assist-callsign-packing`'s "Unsupported forms" requirement), not merely because either callsign is nonstandard.

#### Scenario: AP constraints arm after transmitting the answer

- **WHEN** the service transmits the answer message and advances to `WaitReport`
- **THEN** it SHALL arm H6 AP decode constraints for `(tx.Callsign, partner)` before notifying
  the state change

#### Scenario: AP decode constraints arm successfully for a nonstandard partner callsign

- **WHEN** `partner` is a nonstandard/compound callsign (e.g. `"PJ4/K1ABC"`) and `tx.Callsign`
  is a standard basecall
- **THEN** AP decode constraints SHALL arm using the extended packer's nonstandard-callsign
  encoding for `partner`, rather than disabling AP decode-assist for the QSO

#### Scenario: AP decode constraints disabled when a callsign is genuinely unpackable

- **WHEN** either `tx.Callsign` or `partner` is a form the callsign packer does not support
  (e.g. a directed CQ with a non-numeric suffix, or malformed input)
- **THEN** AP decode-assist SHALL be disabled for the QSO, and a warning SHALL be logged naming
  which callsign failed to pack

---

### Requirement: Retry on no-response in waiting states

In `WaitReport` and `WaitRr73`, if a decode cycle produces no message addressed to `tx.callsign` from the active partner, the service SHALL retransmit the last transmitted message. The retry counter SHALL increment. After `tx.retryCount` consecutive retransmits without a matching response, the service SHALL abort to `Idle` without writing an ADIF record.

The service SHALL NOT count the first empty cycle after entering `WaitReport` or `WaitRr73` as a missed response. This first cycle coincides with the service's own prior TX window; the capture RMS will be suppressed by the silence guard and there is no opportunity for the partner to have responded. The retry logic SHALL only activate from the second consecutive empty cycle onward.

#### Scenario: No decode in WaitReport triggers retransmit

- **WHEN** the service is in `WaitReport`, no decode is addressed to `tx.callsign`, and the retry counter is below `tx.retryCount`
- **THEN** the service SHALL retransmit the answer message and increment the retry counter

#### Scenario: Retry exhaustion in WaitReport aborts to Idle

- **WHEN** the retry counter reaches `tx.retryCount` without a matching response
- **THEN** the service SHALL abort to `Idle`, log the abort at Information level, and SHALL NOT write an ADIF record

#### Scenario: Retry counter resets on state advance

- **WHEN** the service advances from `WaitReport` to `TxReport`
- **THEN** the retry counter SHALL reset to zero for the `WaitRr73` waiting state

#### Scenario: First empty cycle after entering WaitReport is not a retry trigger

- **WHEN** the service enters `WaitReport` and the immediately following decode cycle is empty (silence guard or zero decodes)
- **THEN** the service SHALL NOT retransmit and SHALL NOT increment the retry counter; it SHALL wait for the next cycle before applying retry logic

#### Scenario: First empty cycle after entering WaitRr73 is not a retry trigger

- **WHEN** the service enters `WaitRr73` and the immediately following decode cycle is empty (silence guard or zero decodes)
- **THEN** the service SHALL NOT retransmit and SHALL NOT increment the retry counter; it SHALL wait for the next cycle before applying retry logic

#### Scenario: Second consecutive empty cycle in WaitReport triggers retry

- **WHEN** the service is in `WaitReport`, the first empty cycle was already skipped, a second consecutive empty cycle occurs, and the retry counter is below `tx.retryCount`
- **THEN** the service SHALL retransmit the answer message and increment the retry counter

---

### Requirement: Ignore decodes not addressed to our callsign

In any waiting state, decodes addressed to a different callsign SHALL be silently ignored. Only messages where the destination callsign field matches `tx.callsign` (case-insensitive) AND the source callsign field matches the active partner SHALL advance or retransmit.

#### Scenario: Message addressed to wrong callsign is ignored

- **WHEN** the service is in `WaitReport` and decodes `Q2WRONG Q1TST +05` (destination is `Q2WRONG`, not our callsign)
- **THEN** the service SHALL ignore the decode and take no state transition

#### Scenario: Message from wrong partner is ignored

- **WHEN** the service is in `WaitReport` awaiting `Q1TST` and decodes `Q1OFZ Q2OTHER +05`
- **THEN** the service SHALL ignore the decode (source is `Q2OTHER`, not the active partner)

---

### Requirement: Caller works another station — abort

In `WaitReport`, if a decode cycle contains a message from the active partner that addresses a third callsign (not `tx.callsign`), the caller has moved on. The service SHALL abort to `Idle`.

#### Scenario: Caller works another station detected

- **WHEN** the service is in `WaitReport` awaiting `Q1TST` and decodes `Q2OTHER Q1TST +05`
- **THEN** the service SHALL abort to `Idle` and log at Information level

---

### Requirement: RRR accepted as equivalent to RR73

In `WaitRr73`, both `<ours> <partner> RR73` and `<ours> <partner> RRR` SHALL advance the state machine to `Tx73`. No distinction between the two is made.

#### Scenario: RR73 advances to Tx73

- **WHEN** the service is in `WaitRr73` and decodes `Q1OFZ Q1TST RR73`
- **THEN** the service SHALL advance to `Tx73`

#### Scenario: RRR advances to Tx73

- **WHEN** the service is in `WaitRr73` and decodes `Q1OFZ Q1TST RRR`
- **THEN** the service SHALL advance to `Tx73`

---

### Requirement: Out-of-sequence RR73 in WaitReport accepted

If `<ours> <partner> RR73` or `<ours> <partner> RRR` is decoded while in `WaitReport` (skipping the signal report exchange), the service SHALL accept it, skip directly to `Tx73`, and transmit `<partner> <ours> 73`.

#### Scenario: Early RR73 in WaitReport skips to Tx73

- **WHEN** the service is in `WaitReport` and decodes `Q1OFZ Q1TST RR73`
- **THEN** the service SHALL advance directly to `Tx73` without entering `TxReport` or `WaitRr73`

---

### Requirement: Watchdog abort

A watchdog timer SHALL be started when the service leaves `Idle`. The timer duration is `tx.watchdogMinutes`. If the timer fires before `QsoComplete` is reached, the service SHALL:

1. Cancel any active TX immediately via `IPttController.KeyUpAsync`
2. Abort to `Idle`
3. Log the abort at Warning level including the active partner callsign
4. NOT write an ADIF record

The watchdog timer SHALL reset on every successful state transition.

#### Scenario: Watchdog fires during WaitReport

- **WHEN** the watchdog timer expires while the service is in `WaitReport`
- **THEN** the service SHALL abort to `Idle`, call `KeyUpAsync`, and log a Warning

#### Scenario: Watchdog reset on state transition

- **WHEN** the service advances from `WaitReport` to `TxReport`
- **THEN** the watchdog timer SHALL be reset to `tx.watchdogMinutes` from the transition time

---

### Requirement: Operator abort via POST /api/v1/tx/abort

On receipt of `POST /api/v1/tx/abort`, the service SHALL:

1. Set a cancellation flag
2. Call `IPttController.KeyUpAsync` to immediately cease any active transmission
3. Abort to `Idle`
4. NOT write an ADIF record

If the service is already in `Idle`, the request SHALL be a no-op returning HTTP 200.

#### Scenario: Abort during TxAnswer stops transmission

- **WHEN** `POST /api/v1/tx/abort` is received while the service is in `TxAnswer`
- **THEN** audio playback SHALL stop, the service SHALL move to `Idle`, and HTTP 200 SHALL be returned

---

### Requirement: TX state WebSocket event

When the QSO answerer state changes, the daemon SHALL push a WebSocket event to all connected clients containing the new state and active partner callsign, so that the UI can reflect TX activity.

#### Scenario: State change event pushed on transition to TxAnswer

- **WHEN** the service transitions from `Idle` to `TxAnswer`
- **THEN** a WebSocket event SHALL be pushed with `{ "type": "txState", "state": "TxAnswer", "partner": "<callsign>" }`

#### Scenario: State change event pushed on return to Idle

- **WHEN** the service transitions to `Idle` (completion or abort)
- **THEN** a WebSocket event SHALL be pushed with `{ "type": "txState", "state": "Idle", "partner": null }`

---

### Requirement: Manual engage fires unconditionally within a correct-phase window

When `QsoAnswererService` consumes an armed manual-engage target — a pending target set by `AnswerCqAsync` (CQ click) or a jump-in target set by `EngageAtAsync` (double-click) — it SHALL fire the transmission in the first decode cycle whose phase matches the armed target's expected phase, regardless of how many seconds into that window the consumption occurs. There SHALL be no lateness-based rejection or deferral: the only gating conditions are the phase check (fire only when `nextCycleIsAPhase` matches the armed `pendingIsAPhase`/`jumpIsAPhase`) and the existing 60-second stale-target expiry. A target whose phase does not match the current cycle SHALL continue to be retained and re-evaluated on the next cycle, unchanged from prior behaviour.

#### Scenario: Pending target fires immediately even when armed late in its window

- **WHEN** a pending target (from `AnswerCqAsync`) is armed for the A phase, and the decode cycle
  in which its phase check first passes is consumed 5 s into that A-phase window
- **THEN** the service SHALL clear the pending target and begin transmitting in that same cycle —
  it SHALL NOT defer to the next A-phase occurrence

#### Scenario: Jump-in fires immediately even when armed late in its window

- **WHEN** a jump-in target (from `EngageAtAsync`) is armed for the B phase, and the decode cycle
  in which its phase check first passes is consumed 6 s into that B-phase window
- **THEN** the service SHALL clear the jump-in target and begin transmitting in that same cycle —
  it SHALL NOT defer to the next B-phase occurrence

#### Scenario: Wrong-phase cycle still waits for the next matching-phase window

- **WHEN** a pending target is armed for the A phase and the current decode cycle is B phase
- **THEN** the service SHALL retain the pending target unfired and re-evaluate it on the next cycle,
  exactly as before this change

#### Scenario: Stale target still expires after 60 seconds regardless of lateness

- **WHEN** a pending or jump-in target has been armed for more than 60 seconds without its phase
  check passing
- **THEN** the service SHALL discard it and log a Warning, unaffected by the removal of the
  lateness guard

---

### Requirement: Transmission never keys past the current window's boundary

`TransmitAsync` (used by every transmission the service sends — manual-engage answers, retries, report/RR73/73 continuations) SHALL, immediately before loading audio into the `IPttController`, compute the time remaining in the current 15-second cycle window from the moment of the call and truncate the synthesised sample buffer so that playback cannot extend past that window's boundary. A transmission that begins early enough to play in full SHALL be unaffected — truncation SHALL only shorten the buffer when the full 12.64 s clip would otherwise overrun the window. If the computed remaining time is zero or negative at the moment `TransmitAsync` is entered, the service SHALL skip `LoadAudio`/`KeyDownAsync` entirely for that call and log at Debug level, rather than keying PTT with an empty buffer.

A transmission shortened by this requirement SHALL be treated identically to a full-length transmission for `_retryCount` accounting, watchdog reset, and ADIF logging purposes — there is no distinct "truncated" state tracked elsewhere in the state machine.

#### Scenario: Late-armed transmission is truncated to fit the remaining window

- **WHEN** `TransmitAsync` is called 8 s into its 15 s window (7 s remaining)
- **THEN** the synthesised audio buffer SHALL be truncated to at most 7 s of playback before
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
