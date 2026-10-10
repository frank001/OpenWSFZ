## ADDED Requirements

### Requirement: A CQ modifier SHALL NOT be treated as the caller

The QSO answerer's CQ parser SHALL return the third token as the caller callsign when a CQ message has a CQ modifier
(1 to 4 letters A-Z, or exactly 3 digits) as its second token and its third token parses as a callsign shape (the decoder
filter's own parser, including the `PREFIX/CALL` rule). The grid SHALL be the fourth token when it matches
`[A-R]{2}[0-9]{2}`, otherwise absent. In every other case the parser SHALL keep its previous behaviour.

#### Scenario: Modifier is skipped

- **WHEN** the message is `CQ DX Q1ABC FN42`, `CQ POTA Q1ABC` or `CQ 123 Q1ABC`
- **THEN** the parser SHALL return callsign `Q1ABC` (grid `FN42` for the first, absent for the others)

#### Scenario: Compound call is returned whole

- **WHEN** the message is `CQ QA4/Q1ABC`
- **THEN** the parser SHALL return callsign `QA4/Q1ABC`

#### Scenario: No modifier, or no callsign after it, keeps today's behaviour

- **WHEN** the message is `CQ Q1ABC FN42` or `CQ POTA 73`
- **THEN** the parser SHALL return callsign `Q1ABC` (grid `FN42`) and callsign `POTA` respectively, as before
