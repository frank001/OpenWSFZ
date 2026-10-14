## ADDED Requirements

### Requirement: A compound `PREFIX/CALL` token SHALL be shape-valid when its right half is the base callsign

For a callsign-position token containing exactly one `/` (left half L, right half R), the decoder SHALL treat the token as
shape-valid if **either** (a) L parses as a callsign shape (today's rule, R unchanged), **or** (b) R parses as a callsign
shape **and** L is a prefix shape: 1 to 4 alphanumeric characters containing at least one letter. The half that parsed is the
base call: the total-length ceiling and the reserved-prefix exclusion SHALL apply to it, and under (b) the exclusion check
SHALL also apply to L. Tokens with two or more `/` SHALL keep today's behaviour.

#### Scenario: Prefix-first compound call is accepted

- **WHEN** a callsign-position token is `QA4/Q1ABC` (a prefix with a letter, then a Q-prefix synthetic call)
- **THEN** the decoder SHALL treat the token as shape-valid
- **AND** `Q2ABC QA4/Q1ABC RR73` and `CQ QA4/Q1ABC` SHALL be plausible

#### Scenario: Prefix without a letter stays rejected

- **WHEN** a callsign-position token is `12/Q1ABC`
- **THEN** the decoder SHALL treat it as shape-invalid

#### Scenario: Right half that is not a callsign stays rejected

- **WHEN** a callsign-position token is `QA4/3AG9672ATCH`
- **THEN** the decoder SHALL treat it as shape-invalid

#### Scenario: Reserved prefix in the left position stays rejected

- **WHEN** a callsign-position token has a reserved, never-allocated, non-carved-out prefix as L and a valid callsign as R
- **THEN** the decoder SHALL treat the token as shape-invalid

---

### Requirement: `CQ <modifier> <call>` without a grid SHALL be plausible

The decoder SHALL treat a 3-token message as plausible when token 0 is `CQ`, token 1 is a CQ modifier (1 to 4 letters A-Z,
or exactly 3 digits) and token 2 is shape-valid. Token 1 SHALL be exempt from the callsign-shape check in this case only.
Every other 3-token rule SHALL be unchanged.

#### Scenario: Modifier forms are accepted

- **WHEN** the message is `CQ DX Q1ABC`, `CQ POTA Q1ABC` or `CQ 123 Q1ABC`
- **THEN** the decoder SHALL treat it as plausible

#### Scenario: Modifier too long, or call shape-invalid, stays rejected

- **WHEN** the message is `CQ DXDXD Q1ABC` or `CQ DX 3AG9672ATCH`
- **THEN** the decoder SHALL treat it as implausible

---

### Requirement: `CALL CALL R GRID` SHALL be plausible

The decoder SHALL treat a non-`CQ` 4-token message as plausible when token 2 is exactly `R`, token 3 matches
`[A-R]{2}[0-9]{2}`, and tokens 0 and 1 are each a hash reference or shape-valid. Every other non-`CQ` 4-token message
SHALL stay implausible.

#### Scenario: Reply with an acknowledged grid is accepted

- **WHEN** the message is `Q1ABC Q2XYZ R FN42` or `<...> Q2XYZ R FN42`
- **THEN** the decoder SHALL treat it as plausible

#### Scenario: Bad grid letters or a non-`R` third token stays rejected

- **WHEN** the message is `Q1ABC Q2XYZ R SS42` or `Q1ABC Q2XYZ X FN42`
- **THEN** the decoder SHALL treat it as implausible

---

### Requirement: The plausibility changes SHALL be acceptance-only

No message text that the pre-change `IsPlausibleMessage` accepts SHALL be rejected by the post-change filter. This SHALL be
demonstrated mechanically (acceptance row PV-0b) over every WSJT-X and OpenWSFZ text of the validation night, not argued
from the code. Every existing `IsPlausibleMessage` and `IsCallsignShapeInvalid` test SHALL pass with its expectation
unchanged.

#### Scenario: Old acceptance implies new acceptance

- **WHEN** the old and new filters are applied to every message text of night `20261009_1752` (about 125,000 texts)
- **THEN** the number of texts the old filter accepts and the new filter rejects SHALL be 0
