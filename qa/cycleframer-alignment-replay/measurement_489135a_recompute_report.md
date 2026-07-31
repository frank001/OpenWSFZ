# Task 4 -- 489135a recompute: RESULT

**Generated:** 2026-07-31T11:09:23Z (`date -u`, HK-017)
**Session t0:** 2026-07-28 23:54:00 UTC
**Method:** `2026-07-31-1030-...-dt-derived-drift.md`, corrected by `2026-07-31-1044-...-drift-definition-corrected.md`.

## Self-checks (mandatory, before any reading)

All pass.

- WAV cycles: 3575 (expected 3575)
- Our decodes in window: 44223 (expected 44223)
- jt9 decodes in window: 70822 (expected 70822)
- Unrestricted matched pairs: 42668 (expected 42668)
- WSJT-X DT control: 0.60 ppm -- FLAT, holds

## DT-drift regression (full session -- valid, this corpus never crossed the cliff)

- OpenWSFZ: DT ~= +0.6183 + (-0.1636)*elapsed_h
- WSJT-X (control): DT ~= +0.1350 + (-0.0021)*elapsed_h (0.60 ppm)
- Calibration constant C = 0.7251 s (from the 8080 sibling session's pre-cliff cross-correlation calibration, per 1044 S1 -- not re-derived here, cited)

## Parity as a function of drift (the durable output, per 1030 S3 item 3)

| h | matched | ref (jt9) | parity | 95% CI | drift (corrected, C=0.7251) | drift (slope-only) |
|---:|---:|---:|---:|---|---:|---:|
| 0 | 4188 | 7131 | 58.7% | [57.6%,59.9%] | -0.107 | -0.000 |
| 1 | 4785 | 8564 | 55.9% | [54.8%,56.9%] | -0.270 | -0.164 |
| 2 | 4839 | 8685 | 55.7% | [54.7%,56.8%] | -0.434 | -0.327 |
| 3 | 4908 | 8627 | 56.9% | [55.8%,57.9%] | -0.597 | -0.491 |
| 4 | 4426 | 7602 | 58.2% | [57.1%,59.3%] | -0.761 | -0.654 |
| 5 | 4338 | 7283 | 59.6% | [58.4%,60.7%] | -0.925 | -0.818 |
| 6 | 3704 | 5622 | 65.9% | [64.6%,67.1%] | -1.088 | -0.981 |
| 7 | 3210 | 4412 | 72.8% | [71.4%,74.0%] | -1.252 | -1.145 |
| 8 | 2754 | 3782 | 72.8% | [71.4%,74.2%] | -1.415 | -1.309 |
| 9 | 1856 | 2414 | 76.9% | [75.2%,78.5%] | -1.579 | -1.472 |
| 10 | 1207 | 1578 | 76.5% | [74.3%,78.5%] | -1.742 | -1.636 |
| 11 | 752 | 915 | 82.2% | [79.6%,84.5%] | -1.906 | -1.799 |
| 12 | 569 | 717 | 79.4% | [76.2%,82.2%] | -2.070 | -1.963 |
| 13 | 716 | 1467 | 48.8% | [46.3%,51.4%] | -2.233 | -2.126 |
| 14 | 416 | 2023 | 20.6% | [18.9%,22.4%] | -2.397 | -2.290 |

## Headline: restricted parity at both candidate cutoffs (1044 S3)

- **h_2p40_corrected_definition** (h < 2.4): matched=10952, ref=19342, parity=56.6%, 95% CI=[55.9%,57.3%]
- **h_3p06_slope_only_candidate** (h < 3.06): matched=14107, ref=24900, parity=56.7%, 95% CI=[56.0%,57.3%]

**Agreement check (1044 S3 added requirement):** if the two cutoffs select different rows of the pre-registered reading rule, this must be escalated, not resolved by picking one. See the QA write-up for the applied reading rule and its outcome under each.

## Reference-method by-product (descriptive only -- NOT subject to the reading rule)

- jt9 decodes: 70822
- Live WSJT-X decodes (same audio): 67418
- Matched: 66173 (93.4% of jt9's, 98.2% of WSJT-X's)

Answers: does a live-WSJT-X reference and a jt9 re-decode give materially different parity on identical audio? Descriptive; must not be pooled with the parity recompute above.

