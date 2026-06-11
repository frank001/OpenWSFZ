# OpenWSFZ R&R Study Report

| Field | Value |
|---|---|
| Run date | 2026-06-11 |
| OpenWSFZ SHA | `068210692666c3865a994c378f86718a9e1ca908` |
| WSJT-X version | WSJT-X 2.7.0 (inferred from binary date 2025-02-04) |

## S1 — reported_snr_db

### Variance Components

| Component | σ² | %Contribution |
|---|---|---|
| Repeatability | 0.13 | 0.16% |
| Reproducibility | 0.32 | 0.39% |
| Part-to-Part | 83.03 | 99.45% |
| Total GR&R | 0.46 | 0.55% |
| Total | 83.49 | 100.00% |

### Study Metrics

| Metric | Value | Verdict |
|---|---|---|
| %Tolerance (GR&R) | 40.50% | PASS |
| %Study Var (GR&R) | 7.39% | — |
| ndc | 19 | PASS |

![S1 GR&R panel](S1_grr_panel.png)

### Bias & Linearity (S1)

| Appraiser | Mean Bias (dB) | Slope | Intercept | R² | Verdict |
|---|---|---|---|---|---|
| WSJT-X | +0.98 | 0.000 | 0.983 | 0.000 | PASS |
| OpenWSFZ | +1.78 | 0.003 | 1.778 | 0.003 | PASS |

![S1 Bias & Linearity](S1_bias_linearity.png)

## Summary

| Metric | Scope | Value | Verdict |
|---|---|---|---|
| %GR&R | S1 | 0.5% | PASS |
| ndc | S1 | 19 | PASS |
| SNR bias | S1/WSJT-X | +0.98 dB | PASS |
| SNR bias | S1/OpenWSFZ | +1.78 dB | PASS |

**Overall verdict: PASS**
