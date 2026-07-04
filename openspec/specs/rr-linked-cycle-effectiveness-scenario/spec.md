# rr-linked-cycle-effectiveness-scenario Specification

## Purpose
Specifies R&R harness support for linked two-cycle scenarios, in which a Type 4
nonstandard-callsign announcement is played in one FT8 cycle and a corresponding
hash-reference message is played in a later cycle. This lets the study measure a
"resolved" outcome for the cross-cycle hashed-callsign resolution mechanism
(`f-001-hashed-callsign-resolution`) under realistic live-audio decode conditions, distinct
from — and in addition to — the existing independent per-slot decoded/not-decoded scoring
used by S1–S8. Existing `parts`-based scenarios are unaffected.

## Requirements
### Requirement: Harness supports a linked-pair scenario schema
The R&R harness (`qa/rr-study/harness/run_scenario.py`) SHALL support a scenario JSON file
containing a top-level `pairs` array, where each entry explicitly names an `announce` signal and
a `reference` signal (each with its own `msg_id`/`freq_hz`/`snr_db`) plus a `gap_cycles` integer,
without requiring any change to how existing `parts`-based scenarios (S1–S8) are defined or
scored.

#### Scenario: Existing part-based scenarios are unaffected
- **WHEN** the harness loads a scenario file containing a `parts` array and no `pairs` key
  (e.g. any existing S1–S8 scenario file)
- **THEN** it plays and scores that scenario exactly as before this capability was added

#### Scenario: A pairs-based scenario file is recognised
- **WHEN** the harness loads a scenario file containing a `pairs` array
- **THEN** it plays each pair via the new linked-pair path described below, rather than the
  existing independent-part path

### Requirement: Harness plays a linked pair across two cycles with an explicit gap
For each entry in a scenario's `pairs` array, the harness SHALL play the `announce` signal at one
FT8 cycle boundary, wait exactly `gap_cycles` further cycle boundaries (playing silence in any
intervening cycle), then play the `reference` signal at the next cycle boundary — using the same
cycle-boundary alignment mechanism (`_next_cycle_boundary`/`_wait_for_cycle`) already used by
existing scenarios.

#### Scenario: gap_cycles=1 plays reference in the immediately following cycle
- **WHEN** a pair specifies `gap_cycles: 1`
- **THEN** the `announce` signal is played at cycle boundary *N* and the `reference` signal is
  played at cycle boundary *N+1*, with no intervening cycle

#### Scenario: gap_cycles > 1 inserts silent intervening cycles
- **WHEN** a pair specifies `gap_cycles: k` for `k > 1`
- **THEN** the harness plays silence at each of the `k - 1` intervening cycle boundaries before
  playing the `reference` signal

### Requirement: Harness writes one truth row per pair, not one per part
For each played pair, the harness SHALL write a single truth row (distinct from the existing
per-part truth-row schema) recording both the `announce` and `reference` messages' truth data
(text, frequency, cycle timestamps for both plays) and an explicit expected-resolution flag, so
that scoring does not need to infer pairing from part-index adjacency.

#### Scenario: Truth row links both halves of a pair
- **WHEN** a pair is played
- **THEN** the truth CSV contains one row for that pair, with both the announce and reference
  message truth fields populated and a `resolved_expected=true` flag

### Requirement: Analysis reports a "resolved" outcome conditional on the announcement having decoded
`qa/rr-study/harness/analyse.py` SHALL provide a dedicated analyser for linked-pair scenarios
(following the existing convention of one analyser function per scenario type) that reports two
distinct rates: the announce-cycle decode rate, and the reference-cycle resolution rate
*conditional on* the announce cycle having decoded, so that a low resolution rate cannot be
conflated with a low announcement-decode rate.

#### Scenario: Resolution is scored only among pairs where the announcement decoded
- **WHEN** a linked-pair scenario run includes some pairs where the `announce` signal was not
  successfully decoded
- **THEN** the reported resolution rate's denominator excludes those pairs, and the report states
  the announce-decode rate separately

#### Scenario: A resolved reference is distinguished from an unresolved placeholder
- **WHEN** the `reference` cycle's decoded text is checked against the pair's truth
- **THEN** the analyser reports "resolved" if the decoded text contains the full nonstandard
  callsign, and "not resolved" if it contains the unresolved-hash placeholder or the message was
  not decoded at all — these two failure modes SHALL be distinguishable in the report
