## ADDED Requirements

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

#### Scenario: Service starts in Idle state

- **WHEN** `QsoAnswererService` is started via `IHostedService.StartAsync`
- **THEN** the current state SHALL be `Idle` and the active partner SHALL be `null`

---

### Requirement: Auto-answer first decoded CQ

While in `Idle`, the service SHALL inspect each decode batch for FT8 messages matching the CQ pattern (`CQ <callsign> <grid>`). On the first matching CQ, the service SHALL:

1. Record the caller callsign and audio frequency
2. Generate the answer message: `<caller>  <ours>  <grid>` where `<ours>` and `<grid>` come from `tx.callsign` and `tx.grid`
3. Encode and synthesise the TX audio at the caller's audio frequency
4. Call `IPttController.KeyDownAsync` to begin transmission
5. Advance to `TxAnswer`; after playback completes, advance to `WaitReport`

If multiple CQs are decoded in the same cycle, the first in the decoded list SHALL be selected.

#### Scenario: CQ triggers auto-answer

- **WHEN** the service is in `Idle` and a decode batch contains `CQ Q1TST JO22`
- **THEN** the service SHALL advance to `TxAnswer`, begin transmitting `Q1TST Q1OFZ JO33`, and advance to `WaitReport` after the TX slot completes

#### Scenario: Multiple CQs in one cycle — first selected

- **WHEN** a decode batch contains `CQ Q1TST JO22` and `CQ Q2ABC KP20`
- **THEN** the service SHALL answer `Q1TST` (first in list) and ignore `Q2ABC`

#### Scenario: Non-CQ decodes in Idle are ignored

- **WHEN** the service is in `Idle` and the decode batch contains only `Q2ABC Q3DEF +05`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit

---

### Requirement: Retry on no-response in waiting states

In `WaitReport` and `WaitRr73`, if a decode cycle produces no message addressed to `tx.callsign` from the active partner, the service SHALL retransmit the last transmitted message. The retry counter SHALL increment. After `tx.retryCount` consecutive retransmits without a matching response, the service SHALL abort to `Idle` without writing an ADIF record.

#### Scenario: No decode in WaitReport triggers retransmit

- **WHEN** the service is in `WaitReport`, no decode is addressed to `tx.callsign`, and the retry counter is below `tx.retryCount`
- **THEN** the service SHALL retransmit the answer message and increment the retry counter

#### Scenario: Retry exhaustion in WaitReport aborts to Idle

- **WHEN** the retry counter reaches `tx.retryCount` without a matching response
- **THEN** the service SHALL abort to `Idle`, log the abort at Information level, and SHALL NOT write an ADIF record

#### Scenario: Retry counter resets on state advance

- **WHEN** the service advances from `WaitReport` to `TxReport`
- **THEN** the retry counter SHALL reset to zero for the `WaitRr73` waiting state

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
