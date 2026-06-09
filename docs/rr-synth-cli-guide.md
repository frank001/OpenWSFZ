# R&R Synthesiser — CLI Reference

**Applies to:** `qa/rr-study/` Python tools  
**Requires:** Python venv at `qa/rr-study/.venv/` (run `pip install -r requirements.txt` to set up)

All commands below are run from the `qa/rr-study/` directory using the venv interpreter.
On Windows: `.venv\Scripts\python <script>`. On Linux/macOS: `.venv/bin/python <script>`.

---

## Overview

The R&R synthesiser is a pure-Python QA instrument that encodes FT8 messages to audio
and drives the R&R study. It has four entry points:

| Script | Purpose |
|---|---|
| `run_study.py` | Full R&R study run (all scenarios, end-to-end) |
| `harness/run_scenario.py` | Single scenario |
| `resume_study.py` | Resume an interrupted run from a given scenario |
| `gen_decoder_fixtures.py` | Regenerate the C# unit-test WAV fixtures |
| `synth_wav.py` | **One-shot WAV synthesis** — any message, any parameters |
| `siggen.py` | **General-purpose signal generator** — arbitrary signal types, JSONL scenes |

See the dedicated **[siggen.py reference guide](siggen-reference.md)** for full
documentation of the general-purpose signal generator (`siggen.py`), including the
JSONL scene file format, all signal types (sine, square, sawtooth, triangle, chirp,
noise, ft8), batch mode, and R&R scenario improvement recipes.

The synthesiser is completely isolated from the .NET solution. Nothing here can
affect the product build or test suite unless you explicitly re-run
`gen_decoder_fixtures.py` and rebuild the C# test project.

---

## synth_wav.py — Standalone WAV Generator

The most useful tool for ad-hoc work: encode any single FT8 message to a WAV file
without running a full scenario.

### Basic usage

```
python synth_wav.py "CQ Q1ABC FN42"
```

Writes `cq_q1abc_fn42.wav` in the current directory (filename derived from the message
text) and prints a one-line summary:

```
Wrote cq_q1abc_fn42.wav (720000 samples @ 48000 Hz, SNR=+0.0 dB)
```

### All flags

```
python synth_wav.py MESSAGE [options]
```

| Flag | Default | Description |
|---|---|---|
| `MESSAGE` | *(required)* | FT8 message text, e.g. `"CQ Q1ABC FN42"` |
| `--freq HZ` | `1500.0` | Base audio frequency (Hz) |
| `--snr DB` | `0.0` | In-band SNR (dB, 2500 Hz reference). Use `none` or `clean` for a noise-free render |
| `--dt S` | `0.0` | Time offset applied to the signal start (s) |
| `--seed N` | `0` | RNG seed for the noise realisation |
| `--rate HZ` | `48000` | Sample rate (Hz) |
| `--cutoff HZ` | *(none)* | Noise lowpass cutoff (Hz). If omitted, noise is wideband. Has no effect when `--snr` is `clean` |
| `--out PATH` | *(auto)* | Output WAV path. Default derived from MESSAGE text |

### Examples

**Waterfall / perceptual check** — bandlimited noise, −5 dB SNR, 3 kHz cutoff
(matches the R&R study channel model):

```
python synth_wav.py "CQ Q1ABC FN42" --snr -5 --cutoff 3000
```

**Clean render** — no noise, for decoder smoke-testing:

```
python synth_wav.py "CQ Q1ABC FN42" --snr none --out clean_cq.wav
```

**Off-centre frequency, time-shifted:**

```
python synth_wav.py "Q1ABC Q9XYZ -10" --freq 1200 --dt 0.5
```

**12 kHz fixture-compatible render** (same rate the C# tests use):

```
python synth_wav.py "CQ Q1ABC FN42" --rate 12000 --snr 15 --out fx_test.wav
```

**Output filename default rule:** MESSAGE text is lowercased, spaces become underscores,
non-alphanumeric characters are stripped, the result is truncated to 40 characters, and
`.wav` is appended. Example: `"CQ Q1ABC FN42"` → `cq_q1abc_fn42.wav`.

---

## gen_decoder_fixtures.py — C# Test Fixture Generator

Regenerates the synthetic WAV files used by `RealSignalFixtureTests` in the .NET test
suite. Re-run this only if you change the message sets inside the script, then rebuild
`OpenWSFZ.Ft8.Tests`.

### Basic usage (no arguments — reproduces committed fixtures exactly)

```
python gen_decoder_fixtures.py
```

### All flags

| Flag | Default | Description |
|---|---|---|
| `--snr-db DB` | `15.0` | In-band SNR for the composite fixture (dB) |
| `--seed N` | `20260606` | Base RNG seed; each fixture uses `seed + i` |
| `--dt S` | `0.2` | Time offset applied to each signal render (s) |
| `--sample-rate HZ` | `12000` | Sample rate (Hz). Do not change unless ft8_lib / WavReader is updated |
| `--output-dir PATH` | `tests/OpenWSFZ.Ft8.Tests/Fixtures/` | Directory to write WAV and `.expected.txt` files |

### Example — write to a scratch directory without touching committed fixtures

```
python gen_decoder_fixtures.py --output-dir C:\Temp\fx_scratch
```

---

## resume_study.py — Resume an Interrupted Run

Use when a full R&R run was interrupted *after* S1 completed. Replays the remaining
scenarios from a given point, collects the decode logs, runs the matcher for all
scenarios from S1 onwards, and runs the analyser.

### Basic usage (resume from S2, the most common case)

```
python resume_study.py
```

### All flags

| Flag | Default | Description |
|---|---|---|
| `--from-scenario ID` | `S2` | First scenario not yet played (the resume point). Valid: `S2 S3 S4 S5 S7` |
| `--device NAME` | `CABLE Input` | Audio output device name substring (matched case-insensitively) |

### How the scenario sets are derived

Given `--from-scenario S4`:

- **Played:** S4, S5, S7 (from resume point to end of controlled set)
- **Matched:** S1, S4, S5, S7 (S1 was already injected before the resume)

S8 (the realistic band scene) is never included in a resume run; it is handled
separately by `run_study.py`.

### Example — resume from S4 into a different audio device

```
python resume_study.py --from-scenario S4 --device "Line 1 (Virtual Audio Cable)"
```

---

## run_study.py — Full Study Run

Runs all controlled scenarios end-to-end, collects logs, matches, and analyses.

```
python run_study.py                          # full run, prompts for S8
python run_study.py --skip-s8               # skip S8, no prompt
python run_study.py --scenarios S1,S1b      # targeted run
```

| Flag | Default | Description |
|---|---|---|
| `--device NAME` | `CABLE Input` | Audio output device name substring |
| `--skip-s8` | off | Skip the S8 realistic band scene without prompting |
| `--scenarios ID[,ID...]` | *(all)* | Comma-separated subset to run. Valid: `S1 S1b S2 S3 S4 S5 S7 S8` |

---

## harness/run_scenario.py — Single Scenario

Renders and plays one scenario file into the audio output device.

```
python harness/run_scenario.py scenarios/s1-snr-ladder.json
python harness/run_scenario.py scenarios/s1-snr-ladder.json --dry-run
```

| Flag | Default | Description |
|---|---|---|
| `scenario_json` | *(required)* | Path to a scenario JSON file |
| `--device NAME` | `CABLE Input` | Audio output device name substring |
| `--dry-run` | off | Render + write `truth.csv` but skip PortAudio playback |

`--dry-run` is useful for smoke-testing the render pipeline without a VB-CABLE rig.

---

## Quick-reference cheat-sheet

```
# Generate one WAV for listening / perceptual check
python synth_wav.py "CQ Q1ABC FN42" --snr -5 --cutoff 3000

# Regenerate committed C# test fixtures (default params)
python gen_decoder_fixtures.py

# Full R&R run (skipping S8)
python run_study.py --skip-s8

# Targeted run — S1 and S1b only
python run_study.py --scenarios S1,S1b

# Resume from S3 after an interruption
python resume_study.py --from-scenario S3

# Dry-run a single scenario (no audio hardware needed)
python harness/run_scenario.py scenarios/s4-density.json --dry-run
```
