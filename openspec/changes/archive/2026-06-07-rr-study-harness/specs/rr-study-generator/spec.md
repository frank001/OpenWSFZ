## Purpose

Define the behavioural requirements for `harness/run_scenario.py` — the generator driver
that renders FT8 signals from scenario parameter files, plays them into VB-CABLE aligned to
the FT8 15-second UTC cycle boundary, and writes an injected-truth CSV to the run directory.

---

## ADDED Requirements

### Requirement: Scenario file loading
The generator SHALL accept a path to a scenario JSON file (e.g. `scenarios/s1-snr-ladder.json`)
and load its `parts`, `trials`, `fixed`, `message_ids`, and `seed_formula` fields. If the
file is absent or malformed the generator SHALL exit with a non-zero return code and a
human-readable error before touching the audio device.

#### Scenario: Valid scenario file loads successfully
- **WHEN** the operator supplies a valid `scenarios/s1-snr-ladder.json` path
- **THEN** the generator reads all 10 parts and 3 trials without error

#### Scenario: Missing file exits with error
- **WHEN** the supplied path does not exist
- **THEN** the generator prints `ERROR: scenario file not found: <path>` and exits 1

#### Scenario: Malformed JSON exits with error
- **WHEN** the scenario file contains invalid JSON
- **THEN** the generator prints `ERROR: cannot parse scenario file: <path>` and exits 1

---

### Requirement: Deterministic seed computation
For each (part, trial) pair the generator SHALL compute `seed = abs(hash(f"{scenario_id},{part_index},{trial_index}")) % (2**31)` with `PYTHONHASHSEED` set to `"0"` in the process environment before any hash call, producing byte-identical audio across sessions for identical inputs.

#### Scenario: Same inputs produce same seed
- **WHEN** scenario `S1`, part index `0`, trial index `0` are supplied
- **THEN** the computed seed is identical on every run regardless of Python session

#### Scenario: Different part indices produce different seeds
- **WHEN** part index `0` and part index `1` are supplied for the same scenario and trial
- **THEN** the two seeds differ

---

### Requirement: Audio rendering via synthesiser
For each (part, trial) the generator SHALL call `synth.encoder.encode_message()` with the
part's `snr_db`, `base_freq_hz`, `dt_s`, the resolved message text, and the computed seed,
at `sample_rate_hz = 48000`. The returned float32 numpy array SHALL be used directly for
playback without re-encoding or file I/O.

#### Scenario: Correct synthesiser parameters forwarded
- **WHEN** part index `4` of S1 has `snr_db = -12`, `base_freq_hz = 1500`, `dt_s = 0.2`
- **THEN** `encode_message` is called with those exact values and seed derived from `S1,4,<trial>`

---

### Requirement: FT8 cycle boundary alignment
The generator SHALL align the start of each PCM playback to the nearest future UTC second
that is a multiple of 15 (i.e. 0, 15, 30, 45 seconds past the minute). It SHALL begin the
`sounddevice.play()` call at `cycle_start − 500 ms` so that the audio device buffer is primed
and the first sample is presented to the device at or before the cycle boundary. The placement
error (measured as the difference between `time.time()` at call return and `cycle_start`)
SHALL NOT exceed 200 ms under normal system load.

#### Scenario: Playback starts on cycle boundary
- **WHEN** the current UTC time is 12:34:47 (2 s before next boundary at :00)
- **THEN** the generator sleeps until 12:34:59.5 and begins playback so audio starts at or before 12:35:00

#### Scenario: Back-to-back trials advance to next boundary
- **WHEN** a trial has completed and the next cycle boundary is the next 15 s slot
- **THEN** the generator waits for that boundary before playing the next trial

---

### Requirement: PCM playback via sounddevice
The generator SHALL play the rendered float32 numpy array through the operator-selected audio
output device using `sounddevice.play(samples, samplerate=48000, device=<selected>, blocking=True)`.
Playback SHALL be blocking: the generator does not advance to the next trial until `sd.wait()`
returns, ensuring the full 15-second slot is occupied before truth is logged.

#### Scenario: Blocking playback completes before next trial
- **WHEN** a 15-second WAV finishes playback
- **THEN** the generator does not begin cycle alignment for the next trial until playback is complete

#### Scenario: Device selection by name substring
- **WHEN** `--device "CABLE Input"` is supplied
- **THEN** the generator selects the first `sounddevice` output device whose name contains the supplied string (case-insensitive); exits 1 if no match

---

### Requirement: Injected-truth CSV logging
After each successful playback the generator SHALL append one row to `<run_dir>/truth.csv`
with columns: `scenario_id`, `part_index`, `trial_index`, `seed`, `true_snr_db`,
`true_dt_s`, `true_freq_hz`, `message_text`, `cycle_utc` (ISO-8601 UTC timestamp of the
slot start, e.g. `2026-06-06T12:35:00Z`). The CSV header SHALL be written once when the
file is first created; subsequent runs append without re-writing the header.

#### Scenario: Truth row written after each trial
- **WHEN** trial 2 of part 5 of S1 completes
- **THEN** one row is appended to `truth.csv` with correct scenario/part/trial values and the actual cycle UTC

#### Scenario: CSV header present exactly once
- **WHEN** `truth.csv` is created fresh
- **THEN** the first line is the column header; subsequent rows are data

---

### Requirement: Run directory creation
The generator SHALL create `qa/rr-study/results/<YYYY-MM-DD>-<git-sha7>/` at startup if it
does not already exist, where `<git-sha7>` is the first 7 characters of the current
`git rev-parse HEAD` output. If `git` is unavailable the SHA SHALL fall back to `"unknown"`.

#### Scenario: Run directory created on first run
- **WHEN** no matching run directory exists
- **THEN** the generator creates it and logs `Run directory: results/<name>/`

#### Scenario: Existing run directory reused
- **WHEN** a run directory for today's date and SHA already exists
- **THEN** the generator reuses it and appends to any existing `truth.csv`

---

### Requirement: Progress reporting
The generator SHALL print a one-line status for each trial to stdout:
`[S1] Part 4/10  Trial 2/3  SNR=-12 dB  seed=<n>  cycle=2026-06-06T12:35:00Z … done`
and a summary on completion: `Scenario S1 complete — 30 trials injected. Truth: results/<dir>/truth.csv`.

#### Scenario: Per-trial status printed
- **WHEN** trial 1 of part 0 begins playback
- **THEN** a status line is printed before playback begins and `… done` appended on completion
