# Continuous Gage R&R ANOVA -- matched-decode SNR

Two-way crossed ANOVA with interaction (AIAG Gage R&R method), computed on the
subset of signals both appraisers decoded in every trial (a balanced part x
appraiser x trial cube is required for the sum-of-squares formulas below).

- Candidate parts (decoded by either appraiser in any run): **1090**
- Balanced parts (decoded by both appraisers in all 3 runs, used in this ANOVA): **515** (47.2% of candidates)

## ANOVA table

| Source | SS | df | MS |
|---|---|---|---|
| Part | 284728.8201 | 514 | 553.9471 |
| Appraiser | 9496.4042 | 1 | 9496.4042 |
| Part x Appraiser | 19774.4291 | 514 | 38.4717 |
| Repeatability (error) | 578.6667 | 2060 | 0.2809 |
| Total | 314578.3201 | 3089 | |

## Gage R&R variance components

| Component | SD (dB) | %Contribution (variance) | %Study Variation |
|---|---|---|---|
| Repeatability (EV) -- appraiser vs itself across trials | 0.530 | 0.27% | 5.17% |
| Reproducibility (AV) -- appraiser vs appraiser | 2.474 | 5.83% | 24.14% |
| Part x Appraiser interaction | 3.568 | 12.12% | 34.81% |
| Reproducibility (total, AV+INT) | 4.342 | 17.95% | 42.36% |
| **R&R (EV+Reproducibility combined)** | **4.374** | **18.21%** | **42.68%** |
| Part-to-part (PV) | 9.269 | 81.79% | 90.44% |
| Total variation (TV) | 10.249 | 100.00% | 100.00% |

ndc (number of distinct categories) = **2.99**

## Appraiser means (matched-decode SNR, dB)

- WSJT-X mean: 0.783 dB
- OpenWSFZ mean: -2.724 dB
- Grand mean: -0.971 dB

## Interpretation guide (AIAG convention, informational -- not a pass/fail gate on real off-air data)

- %Study Var(RR) < 10%: measurement system acceptable.
- %Study Var(RR) 10-30%: may be acceptable depending on application.
- %Study Var(RR) > 30%: measurement system needs improvement.
- These AIAG thresholds were designed for manufacturing gauges, not radio decoders on a live
  band; reported here for a standardised reference point, not as a formal acceptance gate.
