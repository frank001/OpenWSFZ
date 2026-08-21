## ADDED Requirements

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

### Requirement: RMS error is monotone non-increasing in SNR (AC-4)

Across the six pre-registered SNR strata (`{+5, 0, −5, −10, −15, −20} dB`), the measured RMS error (both Δf and Δt) SHALL NOT increase as SNR increases. A non-monotone curve indicates a defect in the refiner or the harness, not a physics result, and is evaluated as an implementation finding like AC-1/AC-2/AC-4, not a statement about D-001.

#### Scenario: AC-4 passes

- **WHEN** the validation harness computes RMS error for each of the six SNR strata
- **THEN** each successive stratum's RMS error, ordered by increasing SNR, SHALL be less than or equal to the previous stratum's

#### Scenario: AC-4 fails

- **WHEN** RMS error increases at any point moving from a lower-SNR stratum to a higher-SNR stratum
- **THEN** the report SHALL name the specific stratum pair where monotonicity broke and SHALL treat it as an implementation defect, not a D-001 finding

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
