## ADDED Requirements

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
