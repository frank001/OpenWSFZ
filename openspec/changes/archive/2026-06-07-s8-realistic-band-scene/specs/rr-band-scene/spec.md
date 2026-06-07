## ADDED Requirements

### Requirement: S8 band scene scenario definition
The R&R study SHALL include a scenario file `qa/rr-study/scenarios/s8-band-scene.json` with `id = "S8"` and `name = "Realistic Band Scene"`. The file SHALL define a `signals` array of exactly 12 entries, each carrying `message_text`, `freq_hz`, `snr_db`, and `dt_s` fields. The scenario SHALL specify `trials: 5`. No `parts` array is used; the entire signal list is treated as a single part rendered in every trial.

#### Scenario: Scenario file is well-formed
- **WHEN** `s8-band-scene.json` is parsed by the harness
- **THEN** it yields exactly 12 signal entries, each with numeric `freq_hz`, `snr_db`, `dt_s`, and non-empty `message_text`

#### Scenario: Scenario file contains all required Q-prefix callsigns
- **WHEN** all `message_text` values in the scenario are inspected
- **THEN** no real (ITU-assignable) callsign appears; only Q-prefix example callsigns (`Q1ABC`, `Q9XYZ`, `Q1AW`) are used, in accordance with NFR-021

#### Scenario: Band profile covers the passband
- **WHEN** `freq_hz` values of all 12 signals are read
- **THEN** at least one signal has `freq_hz < 700` Hz and at least one has `freq_hz > 2000` Hz, confirming passband-wide coverage

### Requirement: S8 PCM rendering via shared noise floor
The harness SHALL render S8 by encoding each signal clean (no noise), scaling by its `snr_db` (relative strength), summing all 12 into one PCM buffer, and adding a single seeded AWGN floor using `channel.mix_to_shared_floor()`. Rendering SHALL use 48 kHz sample rate. The seed SHALL be derived from the trial index using the same `compute_seed("S8", 0, trial_index)` formula used by S7.

#### Scenario: Shared noise floor is used
- **WHEN** S8 is rendered for trial index T
- **THEN** exactly one AWGN noise realisation is added (not one per station), matching the behaviour of `mix_to_shared_floor()`

#### Scenario: Seed determinism
- **WHEN** S8 trial T is rendered twice with the same seed
- **THEN** the resulting PCM buffers are bit-for-bit identical

#### Scenario: Station SNR scaling produces level differences
- **WHEN** two stations share the same `freq_hz` (capture pair G/H)
- **THEN** station G (0 dB) has 6 dB higher amplitude than station H (−6 dB) in the clean mix before noise is added

### Requirement: S8 truth logging per signal
The harness SHALL write one truth CSV row per signal per trial into `truth.csv`, carrying `scenario_id = "S8"`, `part_index = 0`, `trial_index`, `seed`, `true_freq_hz`, `true_snr_db`, `true_dt_s`, and `message_text`. This is the same per-signal truth pattern used by S7.

#### Scenario: Truth rows are written
- **WHEN** S8 completes 5 trials
- **THEN** `truth.csv` contains exactly 60 rows with `scenario_id = "S8"` (12 signals × 5 trials)

#### Scenario: Truth row fields are populated
- **WHEN** a truth row for S8 is inspected
- **THEN** `true_freq_hz`, `true_snr_db`, `true_dt_s`, and `message_text` all match the corresponding entry in the scenario's `signals` array

### Requirement: S8 is optional and prompted before the study starts
`run_study.py` SHALL prompt the operator with `"Run S8 realistic band scene first? [Y/n]"` at startup before any scenario playback begins. If the operator confirms (or presses Enter, accepting the default Y), S8 SHALL run first before the controlled scenarios. If the operator declines, S8 SHALL be skipped entirely for that run. Passing `--skip-s8` on the command line SHALL suppress the prompt and skip S8 unconditionally (for automated or unattended runs).

#### Scenario: Operator confirms S8
- **WHEN** `run_study.py` starts and the operator enters `Y` or presses Enter at the prompt
- **THEN** `s8-band-scene.json` is the first scenario executed, before `s1-snr-ladder.json`

#### Scenario: Operator declines S8
- **WHEN** `run_study.py` starts and the operator enters `N` at the prompt
- **THEN** S8 is not played and the study proceeds directly with `s1-snr-ladder.json`

#### Scenario: Skip flag suppresses prompt
- **WHEN** `run_study.py` is invoked with `--skip-s8`
- **THEN** no prompt is shown and S8 is not included in the run

### Requirement: S8 analyser section — holistic decode rate
The study analyser SHALL produce an S8-specific summary section in `report.md` reporting, for each appraiser (WSJT-X and OpenWSFZ):

- Total messages injected (60: 12 signals × 5 trials)
- Messages decoded (count and percentage)
- Between-appraiser delta in percentage points

The section SHALL carry a note that S8 is an **informational benchmark** with no PASS/FAIL gate. The per-signal breakdown (which of the 12 stations each app decoded across trials) SHOULD be included as a table.

#### Scenario: Report section is generated
- **WHEN** the analyser runs after a full S8 study
- **THEN** `report.md` contains an "S8 — Realistic Band Scene" section with decode counts for both appraisers

#### Scenario: No gate verdict is emitted for S8
- **WHEN** the analyser processes S8 results
- **THEN** no PASS or FAIL verdict line is written for S8 (unlike S1–S5 which each carry a PASS/FAIL line)

#### Scenario: Per-station breakdown is included
- **WHEN** the S8 section of the report is read
- **THEN** a table lists each of the 12 stations with its decode rate (trials decoded / 5) for both appraisers
