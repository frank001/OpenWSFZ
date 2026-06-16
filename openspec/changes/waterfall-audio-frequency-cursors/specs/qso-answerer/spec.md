## MODIFIED Requirements

### Requirement: Auto-answer first decoded CQ

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

**TX frequency selection (modified):** When the service answers a CQ and `tx.holdTxFreq` is `false`, the TX frequency SHALL be the caller's decoded `freqHz` (existing behaviour). The service SHALL additionally update `tx.txAudioOffsetHz` in `IConfigStore` to match and push an `audioOffset` WebSocket event so the waterfall cursor reflects the actual transmission frequency.

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

#### Scenario: Service starts in Idle state

- **WHEN** `QsoAnswererService` is started via `IHostedService.StartAsync`
- **THEN** the current state SHALL be `Idle` and the active partner SHALL be `null`

#### Scenario: AutoAnswer disabled — CQ ignored

- **WHEN** `tx.autoAnswer` is `false` and a decode batch contains `CQ Q1TST JO22`
- **THEN** the service SHALL remain in `Idle` and SHALL NOT transmit
