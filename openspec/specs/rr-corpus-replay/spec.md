# rr-corpus-replay Specification

## Purpose
TBD - created by archiving change rr-corpus-replay. Update Purpose after archive.
## Requirements
### Requirement: Corpus replay harness plays WAVs in randomised order through shared audio device

The R&R study SHALL include a corpus replay harness (`qa/rr-study/harness/corpus_replay.py`) that reads the local off-air WAV corpus, plays each WAV through the configured shared audio device (VB-CABLE) aligned to the 15-second UTC cycle boundary, and repeats for K=3 independent runs. Within each run the WAV presentation order SHALL be independently randomised using a deterministic seed derived from `hash("S6", run_index)`. Both appraisers (WSJT-X and OpenWSFZ) SHALL capture from the shared device simultaneously for every WAV (crossed design). Raw `ALL.TXT` snapshots SHALL be saved locally and SHALL NOT be committed to VCS.

#### Scenario: WAVs are played in randomised order each run

- **WHEN** the corpus replay harness executes run index R
- **THEN** the 42 WAVs SHALL be presented in an order determined by `seed = hash("S6", R)`, independently of any other run's order

#### Scenario: Each WAV is aligned to the UTC 15-second cycle boundary

- **WHEN** the harness is about to play WAV file N
- **THEN** it SHALL wait until the next UTC 15-second boundary before starting playback, so that both appraisers' decode windows are fully aligned to the audio content

#### Scenario: Both appraisers hear each WAV simultaneously

- **WHEN** a WAV file is played into the shared audio device
- **THEN** both WSJT-X and OpenWSFZ SHALL be capturing from that device's output endpoint during the same 15-second window, producing decode results for the same audio instance

#### Scenario: Raw logs are never committed

- **WHEN** a corpus replay run completes and raw `ALL.TXT` snapshots are written
- **THEN** those files SHALL reside only in the local results directory, which is listed in `.gitignore`, and SHALL NOT appear in any `git add` or `git commit` operation

---

### Requirement: Corpus replay analysis computes within-appraiser consistency

The analysis script (`qa/rr-study/harness/analyse_corpus.py`) SHALL compute within-appraiser consistency for each appraiser as the fraction of (WAV, signal) pairs for which the appraiser produced identical decode decisions (decoded / not-decoded) across all K runs. A signal is identified by `(normalised_message_text, freq_bin_50hz)`. Consistency SHALL be reported per-appraiser as a percentage and as a count of consistent vs. inconsistent (WAV, signal) pairs.

#### Scenario: Perfect consistency for a deterministic decoder

- **WHEN** an appraiser produces identical decode lists for WAV_i in all K runs
- **THEN** all signals from WAV_i SHALL be counted as consistent for that appraiser, contributing to a 100% consistency score for those instances

#### Scenario: Inconsistency detected across runs

- **WHEN** an appraiser decodes signal S from WAV_i in run 1 but not in run 2
- **THEN** signal S from WAV_i SHALL be counted as inconsistent for that appraiser and flagged in the per-WAV consistency report

---

### Requirement: Corpus replay analysis computes between-appraiser Cohen's κ

The analysis script SHALL compute Cohen's κ for decode agreement between WSJT-X and OpenWSFZ across all (WAV, run, signal) instances. The confusion matrix SHALL be constructed per signal instance: both decoded = TP, neither decoded = TN, one decoded and not the other = FP or FN. The signal universe for each WAV SHALL be the union of all signals decoded by either appraiser in any run of that WAV. κ SHALL be reported with a 95% confidence interval.

#### Scenario: κ computed over all matched instances

- **WHEN** analysis completes across all 42 WAVs and K runs
- **THEN** the report SHALL include overall κ, 95% CI, and a breakdown by WAV file count showing the distribution of per-WAV agreement rates

#### Scenario: Signal universe is the union of both appraisers

- **WHEN** appraiser A decodes signal S from WAV_i but appraiser B does not
- **THEN** signal S SHALL still appear in the confusion matrix as a disagreement instance (FP for A or FN for A), not be silently excluded

---

### Requirement: Corpus replay analysis computes SNR delta for matched decodes

For every (WAV, run) instance where both appraisers decoded the same signal (same `(text, freq_bin_50hz)` key), the analysis script SHALL compute `SNR_delta = SNR(OpenWSFZ) − SNR(WSJT-X)`. The report SHALL include: mean SNR delta, standard deviation, and a scatter plot of OpenWSFZ-reported SNR vs WSJT-X-reported SNR for all matched pairs.

#### Scenario: SNR delta computed only for cross-appraiser matches

- **WHEN** both appraisers decoded signal S from WAV_i in run R
- **THEN** `SNR(OpenWSFZ) − SNR(WSJT-X)` for that instance SHALL be included in the SNR delta dataset

#### Scenario: SNR delta not computed for unmatched signals

- **WHEN** only one appraiser decoded signal S from WAV_i in run R
- **THEN** no SNR delta SHALL be computed for that instance; the signal contributes to the κ confusion matrix only

---

### Requirement: Corpus replay analysis tests for order effects

The analysis script SHALL test whether decode results for a given WAV correlate with its position in the randomised presentation sequence. For each appraiser, a Spearman rank correlation SHALL be computed between presentation order rank and per-WAV decode count across all K runs. A p-value < 0.05 on this correlation SHALL be flagged as a potential order effect and noted in the report.

#### Scenario: No order effect detected

- **WHEN** Spearman correlation between presentation rank and decode count is not significant (p ≥ 0.05) for both appraisers
- **THEN** the report SHALL state "No order effect detected" for each appraiser

#### Scenario: Order effect flagged

- **WHEN** Spearman correlation p < 0.05 for an appraiser
- **THEN** the report SHALL flag "Potential order effect — session-state carryover suspected" for that appraiser and include the ρ and p-value

---

### Requirement: Corpus replay report SHALL follow the NFR-023 five-section structure

The analysis script (`qa/rr-study/harness/analyse_corpus.py`) SHALL produce a `report.md` that
follows the mandatory five-section structure defined by NFR-023 and STUDY-SPEC §9.0:

1. **Study hypothesis** — stating that the corpus replay validates whether OpenWSFZ and WSJT-X
   agree on decode decisions across a representative real off-air band scene, and whether the D-002
   SNR bias correction (or any subsequent calibration) holds under field conditions.
2. **Data summary** — OpenWSFZ git SHA (stored in `run_manifest.json` as `owsfz_sha`), WSJT-X
   version, number of WAV files, number of runs (K), total observations, and variables measured
   (decode decision and SNR delta for matched pairs).
3. **Results with graphs** — per-metric sections for within-appraiser consistency, between-appraiser
   κ, decode gap, SNR reporting accuracy, and order-effect test. Every chart produced
   (`consistency.png`, `kappa.png`, `decode_gap.png`, `snr_delta.png`) SHALL be embedded with a
   Markdown image reference in the section where its metric is discussed.
4. **Summary verdict table** — all metrics with measured values, thresholds, and
   PASS / MARGINAL / FAIL verdicts; overall verdict on the final line.
5. **Recommendations** — for each FAIL or MARGINAL finding, the further investigations required
   and the defect ID(s) under which they are tracked.

#### Scenario: All five sections present in committed report

- **WHEN** `analyse_corpus.py` writes `report.md` to the committed results directory
- **THEN** the file SHALL contain all five sections with the headings "Study hypothesis",
  "Data summary" (or equivalent), "Results", "Summary", and "Recommendations"

#### Scenario: Every generated chart is embedded in the report

- **WHEN** `analyse_corpus.py` generates `consistency.png`, `kappa.png`, `decode_gap.png`,
  and `snr_delta.png`
- **THEN** each of these four filenames SHALL appear as a Markdown image reference
  (`![...](filename.png)`) in the corresponding results section of `report.md`

#### Scenario: Recommendations section present when findings exist

- **WHEN** any metric in the summary verdict table carries a FAIL or MARGINAL verdict
- **THEN** the Recommendations section SHALL reference the corresponding defect ID(s) and
  describe the next diagnostic or remediation step

#### Scenario: Recommendations section acknowledges clean result

- **WHEN** all metrics in the summary verdict table carry a PASS verdict
- **THEN** the Recommendations section SHALL state "No further investigation required"

---

### Requirement: Committed report artifacts contain no real callsigns (NFR-021)

Before any analysis artifact is written to the committable results directory, the analysis script SHALL apply a callsign scrub pass that replaces any string matching the ITU callsign pattern (1–2 letter prefix + digits + 1–3 letter suffix) with the placeholder `[CALL]`. If the scrub pass detects a pattern it cannot confidently classify, the commit step SHALL abort and print a warning for manual review. Aggregate statistics (counts, percentages, κ, SNR delta values) SHALL be emitted without modification as they contain no personal data.

#### Scenario: Committed report contains no real callsigns

- **WHEN** `report.md` is written to the committable results path
- **THEN** no string matching the ITU callsign pattern SHALL appear anywhere in the file

#### Scenario: Scrub aborts on unclassifiable pattern

- **WHEN** the scrub pass encounters a token it cannot confidently classify as a callsign or non-callsign
- **THEN** the script SHALL print a warning, write no committed artifact, and exit with a non-zero return code

