## MODIFIED Requirements

### Requirement: Answerer state machine

A new component `QsoAnswererService` SHALL implement the FT8 QSO answerer protocol as a finite state machine with the following states:

| State | Description |
|---|---|
| `Idle` | Listening; ready to answer a CQ |
| `TxAnswer` | Transmitting answer: `CALLER  OURS  GRID` |
| `WaitReport` | Waiting for caller's signal report |
| `TxReport` | Transmitting: `CALLER  OURS  R±NN` (real measured SNR, not a fixed placeholder) |
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

## ADDED Requirements

### Requirement: TxReport uses the real measured SNR, not a fixed placeholder

When the service composes a signal report reply — either the normal `WaitReport` reply to a partner's signal report, or a mid-exchange jump-in's `EngagePoint.SendReport` case — the numeric value SHALL be the real measured `Snr` of the decode that triggered the reply, formatted as a two-digit signed FT8 report clamped to `±30` (e.g. `R+07`, `R-13`, `R+00`), prefixed with `R` per the existing protocol-position logic (unchanged by this requirement). The composed value SHALL be persisted as `_rstSent` so the written `QsoRecord.RstSent` on QSO completion reflects the same real value, on both the normal-completion and jump-in-`SendReport` paths.

For the `EngagePoint.SendRr73` and `EngagePoint.Send73` jump-in cases — which never compose a
report of their own this session, having entered mid-exchange — `RstSent` SHALL remain the
existing `"R+00"` placeholder, explicitly and documented as such: there is no real value to report,
the same rationale that already governs `PartnerGrid` remaining `null` on jump-in. This is not a
regression and SHALL NOT be treated as one.

#### Scenario: Normal WaitReport reply reflects the real measured SNR

- **WHEN** the service is in `WaitReport`, the caller's decode payload is a signal report, and
  that decode's `Snr = -13`
- **THEN** the transmitted reply SHALL be `"{caller} {ours} R-13"`, not `"{caller} {ours} R+00"`

#### Scenario: Jump-in to SendReport reflects the real measured SNR

- **WHEN** a mid-exchange jump-in fires `EngagePoint.SendReport` for a decode whose `Snr = +09`
- **THEN** the transmitted reply SHALL be `"{partner} {ours} R+09"`, not `"{partner} {ours} R+00"`

#### Scenario: ADIF RstSent reflects the real transmitted report on normal completion

- **WHEN** a QSO completes normally after a `WaitReport` reply whose report was `"R-13"`
- **THEN** the written `QsoRecord.RstSent` SHALL be `"R-13"`, not the fixed `"R+00"` placeholder

#### Scenario: ADIF RstSent reflects the real transmitted report on a SendReport jump-in

- **WHEN** a QSO completes after a mid-exchange `EngagePoint.SendReport` jump-in whose report was
  `"R+09"`
- **THEN** the written `QsoRecord.RstSent` SHALL be `"R+09"`

#### Scenario: SendRr73/Send73 jump-ins keep the existing RstSent placeholder

- **WHEN** a QSO completes via an `EngagePoint.SendRr73` or `EngagePoint.Send73` jump-in that never
  composed a report this session
- **THEN** the written `QsoRecord.RstSent` SHALL remain `"R+00"` — this is an accepted, documented
  placeholder, not a defect

#### Scenario: Signal report is clamped to the FT8 ±30 range

- **WHEN** the triggering decode's `Snr` is `-42` (outside the standard FT8 report range)
- **THEN** the transmitted report SHALL be clamped to `"R-30"`
