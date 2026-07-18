## ADDED Requirements

### Requirement: Jump-in to SendRr73 writes an ADIF record with a real RstRcvd

The service SHALL, when executing a mid-exchange jump-in (`EngageAtAsync`) for
`EngagePoint.SendRr73`, build and write a `QsoRecord` after transmitting RR73, using
the same confirmation-gated path as a normally-completed QSO (`ExecuteTx73Async`): if
`tx.QsoConfirmation` is enabled, publish the record via the QSO-review event for the browser to
confirm and log; otherwise write it directly to the ADIF log. This SHALL apply exactly once per
jump-in, mirroring `ExecuteTx73Async`'s existing double-entry prevention. `RstRcvd` on this record
SHALL be derived from the actual decoded payload that triggered the jump-in (stripping a leading
`R` from a roger report such as `R-05`, or used as-is for a bare `RRR`) rather than a fixed
placeholder value. `PartnerGrid` on this record SHALL remain `null` — a mid-exchange jump-in
never observed the original CQ and cannot recover a grid square; this SHALL NOT be treated as a
defect.

#### Scenario: Jump-in to SendRr73 writes ADIF with a numeric roger report

- **WHEN** a `SendRr73` jump-in fires for partner `Q2NOISE` in response to a decoded payload of
  `"R-05"`, and `tx.QsoConfirmation` is `false`
- **THEN** after transmitting RR73, the service SHALL write a `QsoRecord` via the ADIF log with
  `PartnerCallsign = "Q2NOISE"`, `RstRcvd = "-05"`, and `PartnerGrid = null`

#### Scenario: Jump-in to SendRr73 writes ADIF for a bare RRR

- **WHEN** a `SendRr73` jump-in fires in response to a decoded payload of `"RRR"` (no numeric
  report), and `tx.QsoConfirmation` is `false`
- **THEN** the written `QsoRecord` SHALL have `RstRcvd = "RRR"` — the service SHALL NOT fabricate
  a numeric placeholder value

#### Scenario: Jump-in to SendRr73 respects the QSO-confirmation gate

- **WHEN** a `SendRr73` jump-in fires and `tx.QsoConfirmation` is `true`
- **THEN** the service SHALL publish the built `QsoRecord` via the QSO-review event and SHALL NOT
  also write it directly to the ADIF log, matching `ExecuteTx73Async`'s existing behaviour for
  this gate
