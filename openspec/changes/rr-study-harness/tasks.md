## 1. Setup & dependencies

- [ ] 1.1 Create `qa/rr-study/harness/__init__.py` (empty) and `qa/rr-study/harness/common.py` with shared utilities: seed computation (`compute_seed(scenario_id, part_index, trial_index) → int` with `PYTHONHASHSEED=0`), UTC slot normalisation (`normalise_slot(dt: datetime) → datetime`), and run directory resolution (`make_run_dir(results_root) → Path`)
- [ ] 1.2 Create `qa/rr-study/harness/requirements.txt` listing: `sounddevice`, `numpy`, `scipy`, `pandas`, `matplotlib`, `scikit-learn`
- [ ] 1.3 Install harness dependencies into the existing `.venv`: `pip install -r harness/requirements.txt`

## 2. Generator driver — run_scenario.py

- [ ] 2.1 Implement scenario file loading: read `id`, `parts`, `trials`, `fixed`, `message_ids` from JSON; look up message texts from `scenarios/study-messages.json`; validate required fields; exit 1 with descriptive message on any failure
- [ ] 2.2 Implement run directory creation: `results/<YYYY-MM-DD>-<git-sha7>/` (fall back to `"unknown"` if `git` unavailable); create if absent; print path on startup
- [ ] 2.3 Implement `common.compute_seed()`: `abs(hash(f"{scenario_id},{part_index},{trial_index}")) % (2**31)` — call `os.environ.setdefault("PYTHONHASHSEED", "0")` **before** importing `synth` so the seed is stable across sessions
- [ ] 2.4 Implement FT8 cycle boundary alignment: given current `time.time()`, compute the next UTC second divisible by 15; sleep until `boundary − 0.5 s`; record actual `cycle_utc` as the boundary timestamp (ISO-8601 UTC)
- [ ] 2.5 Implement device selection: parse `--device <substring>` CLI argument; match case-insensitively against `sounddevice.query_devices()` output device names; exit 1 with a list of available devices if no match
- [ ] 2.6 Implement PCM rendering: call `synth.encoder.encode_message(text, base_freq_hz=..., dt_s=..., snr_db=..., seed=..., sample_rate_hz=48000)` for each (part, trial); store float32 numpy array in memory (no WAV file written)
- [ ] 2.7 Implement blocking playback: `sounddevice.play(samples, samplerate=48000, device=<selected>); sounddevice.wait()`; wrap in try/except to catch `sounddevice.PortAudioError` and exit 1 with device diagnostics
- [ ] 2.8 Implement truth.csv logging: after each successful playback append one row to `<run_dir>/truth.csv` — columns: `scenario_id, part_index, trial_index, seed, true_snr_db, true_dt_s, true_freq_hz, message_text, cycle_utc`; write CSV header only when creating the file for the first time
- [ ] 2.9 Implement `--dry-run` flag: renders audio and writes truth.csv but skips `sounddevice.play()` (outputs `[DRY RUN] would play <n> samples at 48 kHz`); useful for verifying scenario loading and seed computation without audio hardware
- [ ] 2.10 Wire CLI: `python run_scenario.py <scenario_json> [--device <name>] [--dry-run]`; print per-trial one-liner (`[S1] Part 4/10  Trial 2/3  SNR=-12 dB  seed=<n>  cycle=<utc>  … done`) and completion summary

## 3. Decode matcher — matcher.py

- [ ] 3.1 Implement ALL.TXT line parser in `common.py`: regex `^(\d{8}_\d{6})\s+UTC\s+(\d+)\s+([-\d.]+)\s+([-\d]+)\s+(\w+)\s+(.+)$`; extract `utc_str, freq_hz, dt_s, snr_db, mode, message`; skip lines that do not match or have mode ≠ `FT8` (case-insensitive); return `SkippedLineCount` alongside records
- [ ] 3.2 Implement `common.normalise_slot()`: parse timestamp to UTC datetime; if `second % 15` is 0 or 1 floor to current 15 s boundary; if `second % 15` is 14 floor to next 15 s boundary (i.e. add 1 s then floor); otherwise floor `second` to nearest lower multiple of 15
- [ ] 3.3 Implement truth.csv reader: load into pandas DataFrame; validate required columns; group by `cycle_utc` for efficient slot lookup
- [ ] 3.4 Implement truth-to-decode matching loop: for each truth row, scan the matching appraiser's slot bucket for candidates satisfying (text match after `str.split()` normalisation) AND (`abs(candidate_freq − true_freq) ≤ 4`); record first match; mark candidate as consumed (prevent double-counting)
- [ ] 3.5 Implement miss recording: truth rows with no match produce an output row with `matched=False`, `false_positive=False`, reported columns `NaN`
- [ ] 3.6 Implement false-positive recording: app log rows not consumed by any truth match produce output rows with `matched=False`, `false_positive=True`, truth columns `NaN`
- [ ] 3.7 Write matched CSV: `<run_dir>/<scenario_id>_matched.csv` with columns `scenario_id, part_index, trial_index, seed, appraiser, message_text, true_snr_db, true_dt_s, true_freq_hz, reported_snr_db, reported_dt_s, reported_freq_hz, matched, false_positive, cycle_utc`
- [ ] 3.8 Wire CLI: `python matcher.py --run-dir <dir> --scenario <id> --wsjt <path> --owsfz <path>` (explicit paths override run-dir defaults `wsjt-all.txt` / `owsfz-all.txt`); print skipped-line count and per-appraiser match/miss/FP summary on completion

## 4. Analyser & report generator — analyse.py

- [ ] 4.1 Implement matched CSV loader: discover all `*_matched.csv` in run dir; validate required columns; split into continuous scenarios (S1, S2, S3) and attribute scenarios (S4, S5) by reading scenario metadata from `scenarios/*.json`
- [ ] 4.2 Implement two-way crossed ANOVA: for each continuous scenario and response variable (`reported_snr_db` for S1, `reported_freq_hz` for S2, `reported_dt_s` for S3) compute SS_Part, SS_Appraiser, SS_Interaction, SS_Error using standard two-way ANOVA formulae; derive MS values; compute σ²_Repeatability, σ²_Reproducibility, σ²_Part, σ²_GR&R following AIAG MSA 4th ed.
- [ ] 4.3 Compute derived metrics: `%Contribution = σ²_x / σ²_Total × 100`; `%Study Var = 6σ_x / 6σ_Total × 100`; `%Tolerance = 6σ_GR&R / (2 × tolerance_half_width) × 100` (half-widths: SNR=2, freq=4, DT=0.2); `ndc = max(1, floor(1.41 × σ_Part / σ_GR&R))`; emit warning and skip scenario if any cell has < 2 observations
- [ ] 4.4 Implement six-panel matplotlib figure (2×3 grid, 12×10 in): (1) Components of Variation horizontal bar chart; (2) R-chart by Appraiser (range per part, UCL line); (3) Xbar-chart by Appraiser (mean per part, grand-mean line); (4) Measurement by Part scatter; (5) Measurement by Appraiser box; (6) App×Part Interaction line plot — save as `<scenario_id>_grr_panel.png`
- [ ] 4.5 Implement S1 bias & linearity: per appraiser compute `bias[i] = reported_snr[i] − true_snr[i]`; fit OLS `bias ~ true_snr_db` (numpy polyfit degree 1); report slope, intercept, R²; save scatter + regression line as `S1_bias_linearity.png`
- [ ] 4.6 Implement Kappa for attribute scenarios: for each appraiser vs truth, compute Cohen's κ via `sklearn.metrics.cohen_kappa_score(truth_labels, app_labels)`; compute 95% CI via bootstrap (1000 resamples, `numpy.random.default_rng(seed=42)`); compute between-appraiser κ
- [ ] 4.7 Implement false-positive rate: `n_false_positive / n_total_app_log_rows_in_signal_free_cycles × 100` for S5; handle zero-denominator with warning
- [ ] 4.8 Implement verdict engine: for each metric apply §10 thresholds; return `"PASS"`, `"MARGINAL"`, or `"FAIL"`; collect all FAIL verdicts and print a formatted defect notice block to stdout after the report is written
- [ ] 4.9 Write `report.md`: header (run_date, git_sha, WSJT-X version from `wsjt-version.txt` or `"unknown"`, OpenWSFZ SHA); per-scenario section with variance-component table, %Tolerance/%Study Var/ndc table, embedded PNG reference, verdicts; summary section with all verdicts consolidated and overall PASS/MARGINAL/FAIL
- [ ] 4.10 Append trend row: open `qa/rr-study/trend.csv` in append mode; write header if file is new; append one row: `run_date, git_sha, pct_grr_snr, ndc_snr, bias_snr_owsfz, kappa_s4, fp_rate_s5` (empty string for metrics not computed in this run)
- [ ] 4.11 Wire CLI: `python analyse.py --run-dir <dir> [--scenario S1,S2]`; default is all scenarios found in run dir

## 5. Verification

- [ ] 5.1 Dry-run gate: `python harness/run_scenario.py scenarios/s1-snr-ladder.json --dry-run` — confirm exit 0, 30 truth rows in `truth.csv`, all seeds distinct, no audio device required
- [ ] 5.2 Matcher unit check: create a hand-crafted `truth.csv` (3 rows) and matching stub ALL.TXT files; run `matcher.py`; confirm matched.csv contains 6 rows (3 truth × 2 appraisers), correct match/miss flags, and FP rows for any stub extras
- [ ] 5.3 Analyser smoke check: supply the hand-crafted matched.csv to `analyse.py --run-dir <tmp>`; confirm `report.md` and PNG files are created, `trend.csv` row appended, and no Python exception
- [ ] 5.4 Live S1 gate: with both WSJT-X and OpenWSFZ running and monitoring VB-CABLE, run `run_scenario.py scenarios/s1-snr-ladder.json --device "CABLE Input"`; confirm 30 trials complete, truth.csv written, no PortAudio errors; run matcher and analyser; confirm `report.md` contains S1 Gage R&R table and verdict
- [ ] 5.5 Commit results: confirm `report.md` + PNG files render on GitHub; confirm `trend.csv` has exactly one new row; commit `results/<dir>/` and updated `trend.csv` to `main`
