## ADDED Requirements

### Requirement: Per-candidate coherent sync refinement stage exports its (coarse, fine) time decomposition, diagnostic-only

The native shim's diagnostic entry point (`ft8_refine_candidate`) SHALL export the two intermediate time-search selections that its two-dimensional search already computes internally but did not, prior to this change, make observable: the Stage A+B coarse-time selection (`best_dt_samp`, sample index at the ~200 Hz working rate, range `[-12, 12]`) and the Stage C fine-time selection (`best_fine_samp`, sample index at the ~2000 Hz working rate, range `[-20, 20]`), via two new out-parameters appended to the existing signature. The existing `out_delta_freq_hz` (Stage A+B's frequency selection, unchanged — no fine-frequency stage exists) and `out_delta_time_s` (the sum of the two time-stage contributions, unchanged) SHALL continue to be populated exactly as before, so every existing caller that reads only those three original out-parameters observes identical behaviour to the pre-change `20260040` build. This entry point SHALL remain reachable only from diagnostic/validation code — no production decode call site SHALL invoke it, matching the boundary established by r1-sync-refiner-instrument-validation.

#### Scenario: Decomposition sums to the previously-reported total

- **WHEN** the validation harness calls `ft8_refine_candidate` with a coarse candidate position and reads all five out-parameters (`out_delta_freq_hz`, `out_delta_time_s`, `out_sync_score`, `out_coarse_dt_samp`, `out_fine_dt_samp`)
- **THEN** `out_coarse_dt_samp / 200.0 + out_fine_dt_samp / 2000.0` SHALL equal `out_delta_time_s` to within float32 rounding tolerance

#### Scenario: Pre-change out-parameters are unaffected

- **WHEN** `Ft8LibInterop.RefineCandidate` is called against the new `20260041` binary and only the three original out-parameters (`out_delta_freq_hz`, `out_delta_time_s`, `out_sync_score`) are compared against a value produced by the `20260040` binary for the same input
- **THEN** all three values SHALL be identical (this change instruments the existing search, it does not alter it)

---

### Requirement: Noise-only null uses a reflection-symmetry test, evaluated combined and per search stage (successor to AC-3's time sub-check)

On pure-noise input containing no injected signal, across the pre-registered `n = 1,200` trial population, the recovered time offset SHALL be tested for symmetry about zero using a two-sample Kolmogorov–Smirnov test between the observed sample and its own negation — evaluated three times: on the combined `Δt` (`out_delta_time_s`), on the Stage A+B coarse selection alone (`out_coarse_dt_samp`), and on the Stage C fine selection alone (`out_fine_dt_samp`). Each of the three sub-tests SHALL use a Bonferroni-corrected significance level of `α = 0.01 / 3` so the family-wise false-positive rate across all three stays at the pre-registered `0.01`. This test SHALL NOT assume independence between the two search stages and SHALL NOT be derived from any modelled null distribution of the refiner's own output (HK-026) — only from the search grids' own symmetry about zero, which is a property of the fixed search-range constants, verifiable independently of any refiner run. If any of the three sub-populations has zero variance, that sub-test SHALL be reported as an instrument failure (undefined, not a PASS) rather than silently passing. This requirement REPLACES r1-sync-refiner-instrument-validation's "Noise-only control gates the programme, not just this change (AC-3)" requirement's time-dimension evaluation; that requirement's frequency-dimension evaluation (χ² goodness-of-fit against the discrete grid null, `p = 0.94` on R1's own data) is UNCHANGED and continues to gate as before.

#### Scenario: All three reflection-symmetry sub-tests pass

- **WHEN** the validation harness runs the three reflection-symmetry sub-tests against the noise population's combined, coarse-only, and fine-only time values
- **THEN** each sub-test's p-value SHALL be at or above `0.01/3`, the overall time sub-check SHALL be reported PASS, and the report SHALL include each sub-test's KS statistic and p-value individually

#### Scenario: One or more reflection-symmetry sub-tests fail

- **WHEN** any of the three sub-tests' p-value falls below `0.01/3`
- **THEN** the report SHALL name which sub-test(s) failed (combined, coarse-stage, and/or fine-stage) with their statistics, SHALL state that the asymmetry is localised to those stage(s), and SHALL NOT proceed to unblock R2 until resolved — matching AC-3's original escalate-rather-than-locally-retry disposition (r1-sync-refiner-instrument-validation design.md D5)

#### Scenario: A sub-population is degenerate

- **WHEN** any of the three sub-populations (combined, coarse-only, fine-only) has zero variance across all 1,200 trials
- **THEN** that specific sub-test SHALL be reported as an instrument failure with the reason stated, SHALL NOT be counted as a PASS, and the overall time sub-check SHALL NOT be reported PASS while any sub-test is in this state

---

### Requirement: Noise population is stratified by its own recorded coarse position, reported only, never gated

The validation harness or a companion analysis script SHALL compute, from the noise population's already-recorded `coarse_time_offset_s` and `coarse_freq_hz` fields, the linear correlation between each field (and `coarse_time_offset_s`'s fractional position within its own 5 ms coarse search cell) and the recovered `Δt`, plus a decile table of mean `Δt` grouped by that fractional cell position. This SHALL run against any already-committed results file with no new capture required, SHALL be included in the report for informational/localisation purposes, and SHALL NOT itself gate any acceptance criterion's PASS/FAIL disposition — it exists to distinguish a position-dependent cause (e.g. a boundary/edge artefact) from a pervasive one, not to pass or fail the refiner.

#### Scenario: Stratification report is produced from existing data

- **WHEN** the stratification analysis is run against a previously committed noise-population results file (e.g. `run_a.json`)
- **THEN** the report SHALL include the two correlation coefficients, the decile table, and SHALL state explicitly that this section does not affect the change's overall PASS/FAIL verdict

---

## RENAMED Requirements

- FROM: `### Requirement: RMS error is monotone non-increasing in SNR (AC-4)`
- TO: `### Requirement: RMS error is monotone non-increasing in SNR, time dimension only, via a pooled trend test (successor to AC-4)`

---

## MODIFIED Requirements

### Requirement: RMS error is monotone non-increasing in SNR, time dimension only, via a pooled trend test (successor to AC-4)

Across the six pre-registered SNR strata (`{+5, 0, −5, −10, −15, −20} dB`), the per-trial absolute time error SHALL be pooled across all strata (not collapsed to one RMS value per stratum first) and tested via a one-sided Spearman rank-correlation test between SNR (dB) and absolute time error, at a pre-registered significance level of `α = 0.01`, expecting a significant negative correlation (error decreases as SNR increases). Any SNR stratum whose trial count falls below the standing power floor of `n = 200` SHALL be excluded from the pooled test and reported by name as underpowered, rather than silently diluting the pooled result. This requirement evaluates the TIME dimension only. The FREQUENCY dimension's monotonicity is retired permanently and SHALL NOT be re-pre-registered under this or any other requirement — RMS(Δf) is a flat function of the 0.5 Hz search-grid quantisation, not of SNR, and is therefore unidentifiable as a monotonicity target (r1-sync-refiner-instrument-validation ruling R-1); RMS(Δf) per stratum continues to be reported for information only, exactly as under the prior requirement, but no longer participates in any PASS/FAIL decision. This requirement REPLACES r1-sync-refiner-instrument-validation's "RMS error is monotone non-increasing in SNR (AC-4)" requirement in its entirety — that requirement's per-stratum-comparison method is retired for both dimensions, per the ruling's finding that it had a ~99.9% probability of failing a flawless refiner (void by construction, not a defect finding).

#### Scenario: Pooled trend test passes

- **WHEN** the validation harness pools all in-power SNR strata's absolute time errors and computes the one-sided Spearman test against SNR
- **THEN** the correlation SHALL be negative and its one-sided p-value SHALL be below `0.01`, and the report SHALL state the pass and include the correlation coefficient and p-value

#### Scenario: Pooled trend test fails

- **WHEN** the correlation is non-negative, or its one-sided p-value is at or above `0.01`
- **THEN** the report SHALL state the failure with the measured correlation and p-value, and SHALL treat it as an implementation finding to investigate (not a D-001 finding), consistent with the disposition of every other criterion in this family except the noise-only null

#### Scenario: A stratum is underpowered

- **WHEN** any of the six SNR strata has fewer than 200 trials
- **THEN** that stratum SHALL be named explicitly as underpowered and excluded from the pooled test, and the report SHALL state which strata (if any) were excluded rather than omitting the fact
