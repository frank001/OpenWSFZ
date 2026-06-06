## Why

The clean-room FT8 synthesiser (`qa/rr-study/synth/`) is complete and its §5 self-validation gate
has passed (WSJT-X decodes every rendered vector). The scenarios are parameterised and committed.
The next and final piece required to run the Gage R&R study is the **harness** itself — the
Python tooling that orchestrates scenario runs, captures decode logs from both applications,
matches truth against those logs, and produces the Minitab-style analysis report.
Without the harness the study cannot produce a single measurement.

## What Changes

- Add `qa/rr-study/harness/` — a new Python package containing three cooperating modules:
  - **Generator driver** (`run_scenario.py`) — reads a `scenarios/*.json` file, renders each
    (part × trial) signal via the synthesiser, plays PCM into VB-CABLE aligned to the FT8
    15-second UTC cycle boundary, and writes an injected-truth CSV per run.
  - **Decode matcher** (`matcher.py`) — joins truth CSV with WSJT-X `ALL.TXT` and OpenWSFZ
    `ALL.TXT` per 15 s cycle slot; emits a tidy long-format matched CSV (one row per
    scenario / part / trial / appraiser / truth-message).
  - **Analyser & report generator** (`analyse.py`) — ANOVA-method Gage R&R variance
    components, %Tolerance, ndc, six-panel charts; Kappa for attribute scenarios S4/S5;
    bias & linearity for S1; writes `results/<date>-<sha>/report.md` + CSV + PNG artefacts
    and appends one row to `trend.csv`.
- Add `qa/rr-study/harness/requirements.txt` — Python dependency manifest
  (`sounddevice`, `numpy`, `pandas`, `scipy`, `matplotlib`, `scikit-learn`).
- No product source files are touched. The harness is excluded from `OpenWSFZ.slnx` and
  interacts only with (a) the audio device and (b) the two applications' `ALL.TXT` log files.

## Capabilities

### New Capabilities

- `rr-study-generator`: Generator driver — scenario orchestration, PCM playback into
  VB-CABLE aligned to FT8 cycle boundaries, and injected-truth CSV logging.
- `rr-study-matcher`: Decode log joiner — cycle-normalised matching of truth against
  WSJT-X and OpenWSFZ `ALL.TXT` output; tidy long-format matched CSV.
- `rr-study-analyser`: Gage R&R analysis and report generator — ANOVA variance components,
  %Tolerance/%Study Var/ndc, six-panel charts, Kappa, bias/linearity, `report.md` + `trend.csv`.

### Modified Capabilities

_(none — this change adds QA harness tooling only; no product requirement changes)_

## Impact

- **New files only** under `qa/rr-study/harness/` — no existing source modified.
- New Python runtime dependency on `sounddevice` (PortAudio wrapper) for WASAPI shared-mode
  playback; all other dependencies are already standard scientific-Python stack.
- Operator must have Python ≥ 3.11, the `.venv` activated, and VB-CABLE installed (see
  `RUNBOOK.md`) before running the harness.
- The harness is not wired into the .NET CI pipeline; it is run on-demand by QA before and
  after decoder-affecting changes, and as a release gate.
