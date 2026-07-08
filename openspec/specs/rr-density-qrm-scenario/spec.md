# rr-density-qrm-scenario Specification

## Purpose
Specifies the S4 Density/QRM scenario's per-message truth generation and matching contract
for the OpenWSFZ R&R study harness. S4 measures decode recovery and pooled attribute-Kappa
agreement (STUDY-SPEC.md §9.3) when multiple FT8 signals occupy a cycle simultaneously. Prior
to `rr-study-s4-per-message-matching` (R&R-007, GitHub #59), S4 pooled every message in a
cycle into a single truth row and scored a match as "decoded any one of N" — a ceiling effect
that made it structurally incapable of distinguishing good QRM handling from bad (confirmed on
live data: both appraisers scored a degenerate perfect κ=1.000). This capability requires one
truth row per individually injected message, each scored independently, mirroring the S7 and
S8 scenarios' already-correct per-signal pattern.

## Requirements
### Requirement: S4 truth generation records one row per injected message
The R&R harness (`qa/rr-study/harness/run_scenario.py`) SHALL, for the S4 Density/QRM
scenario, emit one `truth.csv` row per individually injected message within a
(part, trial) cycle — not one pooled row per cycle. Each row SHALL carry that specific
message's own `true_snr_db` and `true_freq_hz`, following the same per-signal
truth-row pattern already used by the S7 and S8 scenarios.

#### Scenario: Single-signal S4 part still yields one truth row
- **WHEN** S4 part 0 (`n_signals: 1`) trial T is played
- **THEN** exactly one truth row is written for that (part, trial), carrying the one
  signal's own `true_snr_db` and `true_freq_hz`

#### Scenario: Multi-signal S4 part yields one truth row per signal
- **WHEN** S4 part 4 (`n_signals: 30`) trial T is played
- **THEN** exactly 30 truth rows are written for that (part, trial), one per injected
  message, each carrying that message's own `true_snr_db` (drawn from the part's
  `snr_db_set`, round-robin) and its own spread `true_freq_hz`

#### Scenario: Truth row message text is a single message, not a pooled string
- **WHEN** any S4 truth row is inspected
- **THEN** its `message_text` field SHALL contain exactly one FT8 message, never a
  `"; "`-joined concatenation of multiple messages

### Requirement: Each S4 message is matched and scored independently
The matcher (`qa/rr-study/harness/matcher.py`) SHALL score each S4 truth row as an
independent match/miss outcome against that row's own message text and frequency,
using the same generic per-row matching path already used for S1–S3, S7, and S8. No
S4-specific "match if any one of a pooled set decodes" branch SHALL remain.

#### Scenario: Partial recovery in a busy cycle is measured accurately
- **WHEN** an appraiser decodes 10 of 30 messages injected in one S4 part-4 trial
- **THEN** the matched output SHALL record 10 matched rows and 20 missed rows for
  that appraiser in that trial — not a single aggregate "matched" outcome for the
  whole cycle

#### Scenario: A correctly decoded secondary signal is not miscounted as a false positive
- **WHEN** an appraiser correctly decodes more than one message from the same S4 cycle
- **THEN** each correctly decoded message SHALL be recorded as its own matched row,
  and none of them SHALL be recorded as a false positive

#### Scenario: No signal decoded in a cycle yields misses, not a false silence
- **WHEN** an appraiser decodes none of the messages injected in an S4 cycle
- **THEN** every truth row for that cycle SHALL be recorded as a miss for that
  appraiser

### Requirement: Pooled attribute-Kappa reflects true per-message S4 outcomes
`analyse.py` SHALL compute the pooled attribute-agreement analysis (S4 positives + S5
negatives) from the per-message S4 truth/match rows, without requiring the pooled
method itself (which scenario supplies positives, which supplies negatives) to
change. The advisory, non-gating status of the attribute-Kappa row in the report
SHALL be unaffected by this change.

#### Scenario: Confusion matrix counts scale with message count, not cycle count
- **WHEN** the pooled attribute-agreement analysis runs against a re-recorded S4 run
- **THEN** the total S4-derived positive count (`TP + FN`) SHALL equal the sum of
  `n_signals` across all S4 parts, multiplied by the trial count — not the count of
  (part, trial) cycles

#### Scenario: Kappa gate remains advisory
- **WHEN** the report is rendered after this change
- **THEN** the attribute-Kappa row SHALL still be marked advisory and SHALL still be
  excluded from the overall PASS/FAIL verdict, exactly as before this change

### Requirement: Informational decodable-SNR-restricted Kappa is reported
The report SHALL include an additional, clearly-labelled **informational** Kappa
figure computed over only those S4 positives whose `true_snr_db` is at or above the
established decodable floor (−12 dB, per R&R-005), alongside — not replacing — the
existing full-population pooled Kappa. This figure SHALL NOT participate in any
PASS/FAIL gate.

#### Scenario: Restricted-population Kappa is shown alongside the full figure
- **WHEN** the report's Attribute Agreement section is rendered
- **THEN** it SHALL show both the full-population pooled Kappa and the
  decodable-SNR-restricted Kappa, each clearly labelled, both marked informational/advisory

#### Scenario: Restricted-population Kappa does not affect the overall verdict
- **WHEN** the overall run verdict is computed
- **THEN** the decodable-SNR-restricted Kappa figure SHALL NOT be included in that
  computation, identical in effect to the existing full-population Kappa's advisory status

### Requirement: Existing S1, S2, S3, S5, S7, S8 scenarios are unaffected
This change SHALL NOT alter the truth generation, matching, or analysis behavior of
any scenario other than S4.

#### Scenario: S7's existing per-signal matching is unchanged
- **WHEN** an S7 scenario run is played and matched after this change
- **THEN** its truth rows, matching outcomes, and report output SHALL be identical to
  its behavior before this change, given identical inputs and seeds

#### Scenario: S1/S2/S3/S5 single-row-per-slot behavior is unchanged
- **WHEN** S1, S2, S3, or S5 are played and matched after this change
- **THEN** each continues to write exactly one truth row per (part, trial), unchanged
  from its behavior before this change

