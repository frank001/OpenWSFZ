# ft8-sync-refiner Specification

## Purpose
TBD - created by archiving change r1-sync-refiner-instrument-validation. Update Purpose after archive.
## Requirements
### Requirement: Per-candidate coherent sync refinement stage, diagnostic-only

The native shim SHALL expose a diagnostic entry point (e.g. `ft8_refine_candidate`) that, given the cycle's retained PCM (12 kHz, 180 000 samples) and a candidate's coarse `(freq_hz, time_offset)` from `ftx_find_candidates()`, returns a refined `(Δf, Δt)` relative to that coarse position plus a sync quality score, computed by (1) downconverting the PCM to complex baseband at the candidate frequency with phase retained (not the existing `uint8_t` magnitude-only waterfall), low-passing and decimating to a working rate on the order of 200 Hz; (2) correlating the complex baseband coherently — summing complex values across the three Costas 7×7 sync arrays (pattern `3,1,4,0,6,5,2` at symbol offsets 0, 36, 72) and taking the magnitude of the sum last, never magnitude-then-sum, and never reusing `ft8_decode_multi_symbols()` as a model since that dead code sums dB magnitudes and would defeat the purpose of retaining phase; and (3) searching two-dimensionally, coarse time then frequency then fine time, re-deriving the baseband at the refined frequency before the fine time pass. This entry point SHALL be reachable only from a diagnostic/validation harness in this change — no production decode call site SHALL invoke it, and `ftx_decode_candidate()` SHALL remain byte-for-byte unchanged by this change.

#### Scenario: Refiner is callable as a standalone diagnostic export

- **WHEN** the validation harness calls `ft8_refine_candidate` with a cycle's PCM and a coarse candidate position
- **THEN** the function SHALL return a refined `(Δf, Δt)` and a sync quality score without requiring any other decode-path call in the same process

#### Scenario: Production decode path is unchanged

- **WHEN** `Ft8LibInterop.DecodeAll` is called on any of the three reference platforms after this change ships
- **THEN** the returned decode results SHALL be byte-for-byte identical to the pre-change `20260039` baseline for the same input PCM, on the same corpus used by R0's AC-1/AC-2 replay

---

### Requirement: Refinement accuracy meets a lattice-derived RMS bar (AC-1)

Against the synthetic validation oracle at SNR ≥ −10 dB, the refiner's RMS error versus the truth offset injected by construction SHALL satisfy `RMS(Δf) ≤ 0.30 Hz` and `RMS(Δt) ≤ 7.7 ms` — at least 3× better than the uniform-quantisation RMS of the lattice cell it replaces (`3.125/√12 = 0.902 Hz`, `0.08/√12 = 0.0231 s`). A FAIL on this criterion SHALL be treated as an implementation defect in the refiner to be fixed and re-measured, and SHALL NOT be reported as a finding about D-001 or about whether sync refinement helps recovery.

#### Scenario: AC-1 passes

- **WHEN** the validation harness measures RMS(Δf) and RMS(Δt) across the full SNR ≥ −10 dB population
- **THEN** both measured values SHALL be at or below their respective bars, and the report SHALL record the measured RMS values against the bars

#### Scenario: AC-1 fails

- **WHEN** either measured RMS value exceeds its bar
- **THEN** the report SHALL state AC-1 FAILED with the measured value, SHALL NOT proceed to arm R2, and SHALL NOT characterise the failure as evidence about D-001

---

### Requirement: Systematic bias is bounded separately from RMS (AC-2)

At SNR ≥ −10 dB, the mean signed error SHALL satisfy `|mean(Δf error)| ≤ 0.10 Hz` and `|mean(Δt error)| ≤ 2 ms`, evaluated independently of AC-1's RMS bar specifically to catch a sign-convention defect in the downconversion mixer — the highest-probability defect class in this build, which would still converge and still report plausible-looking offsets while moving every candidate in the wrong direction, inflating RMS only modestly while driving mean error hard away from zero. This criterion, like AC-1, is a statement about the implementation, not about D-001, when it fails.

#### Scenario: AC-2 passes

- **WHEN** the validation harness measures mean(Δf error) and mean(Δt error) across the full SNR ≥ −10 dB population
- **THEN** both measured absolute values SHALL be at or below their respective bars

#### Scenario: AC-2 fails, consistent with a mixer sign error

- **WHEN** the measured mean error is large relative to the measured RMS in the same direction across strata (the signature named in advance for this defect class)
- **THEN** the report SHALL flag a suspected sign-convention defect in the downconversion mixer specifically, name it as the first thing to check, and SHALL NOT proceed to arm R2 until resolved

---

### Requirement: Noise-only control gates the programme, not just this change (AC-3)

On pure-noise input containing no injected signal, the refiner's recovered offsets across repeated trials SHALL be statistically indistinguishable from a uniform distribution over the search range, evaluated by a named statistical test whose statistic and p-value are reported. Unlike AC-1/AC-2/AC-4, an AC-3 FAIL SHALL NOT be treated merely as an implementation defect to fix and re-run locally — it means the refiner can lock onto noise, which would inflate the false-positive rate in any decode-path use, making a subsequent measurement uninterpretable. An AC-3 FAIL SHALL stop this change short of a PASS report and SHALL be escalated for explicit resolution before any proposal to wire refinement into the decode path is written.

#### Scenario: AC-3 passes

- **WHEN** the validation harness runs the refiner against pure-noise input with no injected signal, across the pre-registered trial count
- **THEN** the reported statistical test SHALL find the recovered offsets statistically indistinguishable from uniform, and the report SHALL include the test name, statistic, and p-value

#### Scenario: AC-3 fails and the change stops

- **WHEN** the statistical test rejects the uniform-null hypothesis at the pre-registered significance level
- **THEN** the report SHALL record AC-3 FAILED with the test statistic and p-value, SHALL recommend against proceeding to any decode-path change, and SHALL be escalated rather than resolved by a local retry

---

### Requirement: Determinism is mechanically verified across independent runs (AC-5)

Three independent process runs of the full validation harness against the same input population SHALL produce byte-identical results files, verified by a mechanical byte-diff — never asserted from a single run or from reasoning about the code. This requirement depends on R0's `p23_common.py` hash-randomised-set-iteration determinism fix already being in place.

#### Scenario: AC-5 passes

- **WHEN** the validation harness is run three times independently against the same input population and the three results files are byte-diffed pairwise
- **THEN** all three files SHALL be byte-identical, and the report SHALL include the byte-diff evidence, not merely a claim of determinism

#### Scenario: AC-5 fails

- **WHEN** any pairwise byte-diff among the three runs finds a difference
- **THEN** the report SHALL name the first differing artefact and byte offset, SHALL treat it as an implementation defect (most likely an un-seeded or hash-order-dependent code path), and SHALL NOT report any other AC's numeric result as trustworthy until resolved

---

### Requirement: Cost is measured and reported, never used as a pass/fail bar (AC-6)

The validation harness SHALL report per-candidate wall-clock cost and a projected full-corpus runtime, computed from measured per-candidate cost and the existing corpus's candidate volume. This criterion SHALL NOT gate the change's PASS/FAIL outcome. If the projected full-corpus runtime exceeds approximately 8 hours, this SHALL be escalated for an explicit decision rather than addressed by ad hoc optimisation or by narrowing the corpus unilaterally.

#### Scenario: Cost is reported regardless of magnitude

- **WHEN** the validation harness completes its full run
- **THEN** the report SHALL include measured per-candidate wall-clock cost and a projected full-corpus runtime figure, and this figure alone SHALL NOT change the change's PASS/FAIL disposition

#### Scenario: Projected cost exceeds the escalation threshold

- **WHEN** the projected full-corpus runtime exceeds approximately 8 hours
- **THEN** the report SHALL flag this explicitly for escalation rather than silently proceeding, optimising ad hoc, or narrowing corpus scope without sign-off

---

### Requirement: Validation population is generated from a pre-registered, adequately powered grid

The validation harness SHALL generate its test population from the existing QA synth (`qa/rr-study/synth/`, an encoder-only oracle where truth is known by construction and the decoder side is never involved) using strata fixed globally before generation begins: frequency offsets including at minimum `{0, ±0.4, ±0.8, ±1.2, ±1.5} Hz` relative to a lattice point plus uniform-random draws; time offsets including at minimum `{0, ±0.01, ±0.02, ±0.03, ±0.039} s` plus uniform-random draws; the six SNR strata `{+5, 0, −5, −10, −15, −20} dB`; distinct messages per generated buffer (standing synth requirement); and a minimum of `n = 200` signals per SNR-times-offset-class cell. Any cell falling short of `n = 200` SHALL be reported as an underpowered instrument failure for that cell specifically, not silently averaged into an aggregate PASS.

#### Scenario: All cells meet the power floor

- **WHEN** the validation population is generated per the pre-registered strata
- **THEN** every SNR-times-offset-class cell SHALL contain at least 200 signals, and the report SHALL include the per-cell `n` table

#### Scenario: A cell falls short of the power floor

- **WHEN** any cell's generated signal count is below 200
- **THEN** the report SHALL name that specific cell and state it as underpowered — an instrument failure, not a null result for that cell — rather than omitting it or folding it into a passing aggregate

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

