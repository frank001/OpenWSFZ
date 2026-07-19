## ADDED Requirements

### Requirement: QsoAnswererService exposes its last transmitted message via IQsoController

`QsoAnswererService` SHALL expose its existing internal `_lastTxMessage` field externally through
`IQsoController.LastTxMessage`, with no change to how or when the field itself is set. That field
is already set at every TX-composition site: the initial answer, the signal report reply (both the
normal `WaitReport` reply and the `SendReport` mid-exchange jump-in case), and the final `73`.

#### Scenario: LastTxMessage reflects the real transmitted report reply

- **WHEN** `HandleWaitReportAsync` transmits `"Q1ABC PD2FZ R-13"` (the real measured report, per
  `fix-tx-report-real-snr`)
- **THEN** `LastTxMessage` SHALL be `"Q1ABC PD2FZ R-13"`

#### Scenario: LastTxMessage is null before any transmission

- **WHEN** `QsoAnswererService` has just started and has not yet transmitted anything
- **THEN** `LastTxMessage` SHALL be `null`
