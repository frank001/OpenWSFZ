## Purpose

Define the behavioural requirements for `harness/matcher.py` — the decode log joiner that
reads injected-truth metadata and the `ALL.TXT` decode logs from both WSJT-X and OpenWSFZ,
normalises timestamps to the FT8 15-second cycle slot, matches truth against reported decodes,
and emits a tidy long-format matched CSV for downstream analysis.

---

## ADDED Requirements

### Requirement: Input file loading
The matcher SHALL accept three CLI arguments: `--truth <path>` (truth.csv from the generator),
`--wsjt <path>` (WSJT-X ALL.TXT), and `--owsfz <path>` (OpenWSFZ ALL.TXT). All three files
MUST exist; if any is absent the matcher SHALL exit 1 with a specific error naming the missing
file. The matcher SHALL also accept `--run-dir <path>` as a shorthand that resolves all three
paths from a run directory, expecting `truth.csv`, `wsjt-all.txt`, and `owsfz-all.txt` therein.

#### Scenario: All three paths resolved
- **WHEN** `--run-dir results/2026-06-06-abc1234/` is supplied
- **THEN** the matcher reads `results/2026-06-06-abc1234/truth.csv`, `wsjt-all.txt`, and `owsfz-all.txt`

#### Scenario: Missing WSJT-X log exits with error
- **WHEN** `--wsjt` path does not exist
- **THEN** the matcher prints `ERROR: WSJT-X ALL.TXT not found: <path>` and exits 1

---

### Requirement: ALL.TXT line parsing
The matcher SHALL parse each line of both ALL.TXT files using the format:
`YYYYMMDD_HHMMSS   UTC  <freq_hz>  <dt_s>  <snr_db>  <mode>  <message>`
where fields are separated by two or more spaces. Lines that do not match this pattern
(e.g. blank lines, header lines beginning with `UTC`) SHALL be silently skipped. Only lines
with `<mode>` equal to `FT8` (case-insensitive) SHALL be processed.

#### Scenario: Standard WSJT-X line parsed
- **WHEN** a line reads `20260606_123500   UTC  1502  0.2  -07  FT8  CQ Q1ABC FN42`
- **THEN** the matcher extracts freq=1502 Hz, dt=0.2 s, snr=-7 dB, text=`CQ Q1ABC FN42`, utc=`2026-06-06T12:35:00Z`

#### Scenario: Non-FT8 lines skipped
- **WHEN** a line contains mode `JT9`
- **THEN** the line is not included in the match candidates

#### Scenario: Malformed lines skipped silently
- **WHEN** a line does not conform to the expected pattern
- **THEN** it is skipped and a count of skipped lines is reported at the end

---

### Requirement: Cycle slot normalisation
The matcher SHALL normalise every timestamp (from truth.csv and from ALL.TXT lines) to the
FT8 15-second UTC slot start by flooring to the nearest second that is a multiple of 15.
A timestamp within ±1 second of a slot boundary SHALL be accepted as belonging to that slot
(i.e. floor after applying ±1 s correction if `second % 15 ∈ {14, 0, 1}`).

#### Scenario: Timestamp on slot boundary
- **WHEN** a line timestamp is `123500` (second = 0)
- **THEN** the normalised slot is `12:35:00`

#### Scenario: Timestamp 1 second late
- **WHEN** a line timestamp is `123501` (second = 1)
- **THEN** the normalised slot is still `12:35:00` (within ±1 s tolerance)

#### Scenario: Timestamp mid-slot
- **WHEN** a line timestamp is `123507` (second = 7)
- **THEN** the normalised slot is `12:35:00`

---

### Requirement: Truth-to-decode matching
For each truth row the matcher SHALL search both appraisers' log candidates for the same
15-second cycle slot. A candidate decode is considered a **match** when:
1. Its normalised cycle slot equals the truth cycle slot, AND
2. Its message text (whitespace-normalised) equals the truth message text, AND
3. Its reported audio frequency is within ±4 Hz of the truth `true_freq_hz`.

If a matching candidate is found, the reported `snr_db`, `dt_s`, and `freq_hz` are recorded.
If no candidate matches, the row is recorded as a miss (`matched = False`, reported columns = NaN).

#### Scenario: Exact match on all three keys
- **WHEN** truth row has freq=1500 Hz, text=`CQ Q1ABC FN42`, cycle=12:35:00
- **AND** WSJT-X log has freq=1502 Hz (within ±4 Hz), same text, same cycle slot
- **THEN** the row is matched for appraiser WSJT-X with reported freq=1502

#### Scenario: Frequency outside tolerance is not matched
- **WHEN** the reported frequency differs by 5 Hz from truth
- **THEN** the candidate is not matched; the truth row is recorded as a miss for that appraiser

#### Scenario: Miss recorded correctly
- **WHEN** no candidate matches a truth row for OpenWSFZ
- **THEN** the output row has `matched=False` and all reported columns set to NaN for appraiser OpenWSFZ

---

### Requirement: False positive detection
Any ALL.TXT line that does NOT match any truth row in the same cycle slot SHALL be recorded
as a false positive: `matched = False`, `false_positive = True`, with `truth_*` columns set
to NaN. False positives from both appraisers are included in the output CSV so the analyser
can compute the false-positive rate for S5.

#### Scenario: Decode with no matching truth row recorded as false positive
- **WHEN** WSJT-X reports `CQ Q9ZZZ EN61` in a slot where the synthesiser injected only `CQ Q1ABC FN42`
- **THEN** a false-positive row is written for appraiser WSJT-X with `false_positive=True`

---

### Requirement: Matched CSV output
The matcher SHALL write `<run_dir>/<scenario_id>_matched.csv` with one row per
(scenario_id, part_index, trial_index, appraiser, message_text) combination, including both
matched and miss rows from truth and false-positive rows from app logs. Columns SHALL be:

`scenario_id, part_index, trial_index, seed, appraiser, message_text,
 true_snr_db, true_dt_s, true_freq_hz,
 reported_snr_db, reported_dt_s, reported_freq_hz,
 matched, false_positive, cycle_utc`

#### Scenario: Output CSV structure correct
- **WHEN** S1 with 10 parts × 3 trials × 2 appraisers is matched
- **THEN** the output has at least 60 rows (one per truth × appraiser), plus any false-positive rows

#### Scenario: Output written to run directory
- **WHEN** `--run-dir results/2026-06-06-abc1234/` and scenario S1
- **THEN** the output file is `results/2026-06-06-abc1234/S1_matched.csv`

---

### Requirement: Completion summary
On completion the matcher SHALL print the counts of matched rows, miss rows, and false-positive
rows per appraiser, and the overall match rate per appraiser.

#### Scenario: Summary printed after matching
- **WHEN** matching completes for S1
- **THEN** stdout contains e.g. `WSJT-X: 28/30 matched (93.3%);  2 misses;  0 FP` and an equivalent line for OpenWSFZ
