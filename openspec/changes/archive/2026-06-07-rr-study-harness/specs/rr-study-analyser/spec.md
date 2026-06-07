## Purpose

Define the behavioural requirements for `harness/analyse.py` — the Gage R&R analysis and
report generator that reads the matched CSV produced by the matcher and writes Minitab-style
variance component tables, six-panel charts, bias/linearity analysis, Kappa statistics, and
a `report.md` summarising all results with PASS/MARGINAL/FAIL verdicts against the STUDY-SPEC
§10 thresholds.

---

## ADDED Requirements

### Requirement: Matched CSV loading
The analyser SHALL accept `--run-dir <path>` and discover all `*_matched.csv` files within
it. It SHALL load and validate each CSV: required columns must be present, `appraiser` values
must be `WSJT-X` and `OpenWSFZ`, and numeric columns must be parseable. Missing or malformed
files SHALL cause the analyser to exit 1 with a specific error message before producing any
output.

#### Scenario: Matched CSVs loaded from run directory
- **WHEN** `--run-dir results/2026-06-06-abc1234/` contains `S1_matched.csv` and `S2_matched.csv`
- **THEN** both files are loaded and analysed

#### Scenario: Missing required column causes error
- **WHEN** a matched CSV lacks the `reported_snr_db` column
- **THEN** the analyser exits 1: `ERROR: S1_matched.csv missing required column: reported_snr_db`

---

### Requirement: Continuous Gage R&R — ANOVA method (S1, S2, S3)
For each continuous scenario (S1, S2, S3) the analyser SHALL compute variance components
using the two-way crossed ANOVA method (Part × Appraiser with interaction) following AIAG
MSA Reference Manual (4th ed.) formulae:

- MS_Part, MS_Appraiser, MS_Interaction, MS_Error from two-way ANOVA SS decomposition
- σ²_Repeatability = MS_Error
- σ²_Reproducibility = max(0, (MS_Appraiser − MS_Interaction) / (n_parts × n_trials))
- σ²_Interaction = max(0, (MS_Interaction − MS_Error) / n_trials) (included in Reproducibility)
- σ²_Part = max(0, (MS_Part − MS_Interaction) / (n_appraisers × n_trials))
- σ²_Total = σ²_Repeatability + σ²_Reproducibility + σ²_Part
- σ²_GR&R = σ²_Repeatability + σ²_Reproducibility

Reported metrics per response: `%Contribution` (= σ²_x / σ²_Total × 100),
`%Study Var` (= 6σ_x / 6σ_Total × 100), `%Tolerance` (= 6σ_GR&R / (2 × tolerance_half_width) × 100),
`ndc` = floor(1.41 × σ_Part / σ_GR&R) clamped to ≥ 1.

Only rows where `matched = True` are used for continuous analysis. Scenarios with fewer than
2 matched rows per cell SHALL emit a warning and skip that metric.

#### Scenario: Variance components computed for S1 matched rows
- **WHEN** S1 matched.csv contains 30 matched rows (10 parts × 3 trials × 2 appraisers... but variance computed only on matched)
- **THEN** the analyser outputs a 5-row variance component table (Repeatability, Reproducibility, Interaction, Part-to-Part, Total Gage R&R)

#### Scenario: %Tolerance computed against STUDY-SPEC §7 bands
- **WHEN** the response is SNR and tolerance half-width is 2 dB
- **THEN** `%Tolerance = 6 × σ_GR&R / 4 × 100`

#### Scenario: Insufficient data emits warning
- **WHEN** a cell has fewer than 2 matched observations
- **THEN** the analyser prints `WARNING: S2 — insufficient matched data for Gage R&R; skipping.` and omits that scenario from the report

---

### Requirement: Six-panel chart (S1, S2, S3)
For each continuous scenario the analyser SHALL produce a matplotlib figure with six panels
saved as `<scenario_id>_grr_panel.png` in the run directory:
1. Components of Variation (bar chart: %Contribution for each component)
2. R-chart by Appraiser (control chart of within-appraiser ranges per part)
3. Xbar-chart by Appraiser (control chart of appraiser means per part)
4. Measurement by Part (scatter/box: all measurements grouped by part)
5. Measurement by Appraiser (box: measurements grouped by appraiser)
6. Appraiser × Part Interaction (line plot: mean per part per appraiser)

#### Scenario: Six-panel PNG saved to run directory
- **WHEN** S1 analysis completes
- **THEN** `results/2026-06-06-abc1234/S1_grr_panel.png` exists and contains a 6-panel figure

---

### Requirement: Bias and linearity analysis (S1)
For S1 only, the analyser SHALL compute per-appraiser bias as `mean(reported_snr_db − true_snr_db)`
across all matched rows, and linearity as the slope of `(reported − true)` regressed on
`true_snr_db` (OLS). Both metrics SHALL be reported for WSJT-X and OpenWSFZ separately.
A bias plot SHALL be saved as `S1_bias_linearity.png`.

#### Scenario: Per-appraiser bias computed
- **WHEN** OpenWSFZ consistently reports 1 dB higher than truth across all parts
- **THEN** the table shows `OpenWSFZ bias = +1.0 dB`

#### Scenario: Linearity slope computed
- **WHEN** the bias grows with true SNR (drift pattern)
- **THEN** the slope is non-zero and flagged as `non-constant bias`

---

### Requirement: Attribute Agreement Analysis (S4, S5)
For attribute scenarios S4 and S5 the analyser SHALL compute:
- **Within-appraiser agreement:** proportion of (part × trial) pairs where the decode
  decision (matched / not) is consistent across all trials, per appraiser.
- **Each-appraiser-vs-truth Kappa:** Cohen's κ with 95% CI (bootstrap, 1000 resamples)
  for the binary decoded/not decision.
- **Between-appraiser Kappa:** Cohen's κ for WSJT-X vs OpenWSFZ on the same binary decision.
- **False-positive rate (S5):** `n_false_positive_rows / n_total_signal_free_cycles × 100` per appraiser.

#### Scenario: Kappa computed for S4 each-vs-truth
- **WHEN** S4_matched.csv is loaded
- **THEN** the report contains a Kappa table with rows for WSJT-X vs truth, OpenWSFZ vs truth, and WSJT-X vs OpenWSFZ, each with κ and 95% CI

#### Scenario: False-positive rate computed for S5
- **WHEN** S5_matched.csv contains 20 false-positive rows across 50 signal-free cycles
- **THEN** the report shows `FP rate = 40.0%`

---

### Requirement: PASS/MARGINAL/FAIL verdict against §10 thresholds
For each metric the analyser SHALL print and embed in `report.md` a verdict using the
STUDY-SPEC §10 thresholds:

| Metric | Acceptable | Marginal | Unacceptable |
|---|---|---|---|
| %GR&R per response | < 10% | 10–30% | > 30% |
| ndc | ≥ 5 | — | < 2 |
| Attribute Kappa | ≥ 0.90 | 0.70–0.90 | < 0.70 |
| False-positive rate | ≤ 6% | — | > 6% |
| SNR bias (OpenWSFZ vs truth) | ≤ ±2 dB | — | > ±2 dB |

A metric outside the Acceptable band but within Marginal SHALL emit `MARGINAL`. A metric in
the Unacceptable band SHALL emit `FAIL` and print a prominently formatted defect notice
identifying the metric, the measured value, and the threshold breached.

#### Scenario: All metrics acceptable — PASS printed
- **WHEN** all computed metrics fall within their Acceptable bands
- **THEN** the report summary section reads `Overall verdict: PASS`

#### Scenario: %GR&R_SNR unacceptable — FAIL printed
- **WHEN** %GR&R for SNR is 35%
- **THEN** the report includes `FAIL — %GR&R_SNR = 35.0% (threshold: < 10% Acceptable)`
- **AND** a defect notice is printed to stdout

---

### Requirement: report.md generation
The analyser SHALL write `<run_dir>/report.md` containing:
- Header: run date, git SHA, WSJT-X version (read from `<run_dir>/wsjt-version.txt` if present,
  otherwise `"unknown"`), OpenWSFZ git SHA.
- One section per scenario: variance-component table, %Tolerance/%Study Var/ndc table,
  embedded PNG reference (`![S1 GR&R panel](S1_grr_panel.png)`), verdicts.
- Summary section: all verdicts consolidated, overall PASS/MARGINAL/FAIL.

#### Scenario: report.md written to run directory
- **WHEN** analysis of S1 and S4 completes
- **THEN** `results/2026-06-06-abc1234/report.md` exists with sections for both scenarios

---

### Requirement: trend.csv append
After a successful run the analyser SHALL append one row to `qa/rr-study/trend.csv` with
columns: `run_date`, `git_sha`, `pct_grr_snr`, `ndc_snr`, `bias_snr_owsfz`, `kappa_s4`,
`fp_rate_s5`. If a metric was not computed (scenario not run) the column SHALL be empty.
The header row SHALL be written only if the file does not already exist.

#### Scenario: Row appended after first run
- **WHEN** trend.csv does not exist and a full suite completes
- **THEN** trend.csv is created with a header row and one data row

#### Scenario: Row appended on subsequent runs
- **WHEN** trend.csv already contains 3 rows
- **THEN** a fourth row is appended without modifying existing rows
