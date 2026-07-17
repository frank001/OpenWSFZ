## ADDED Requirements

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
