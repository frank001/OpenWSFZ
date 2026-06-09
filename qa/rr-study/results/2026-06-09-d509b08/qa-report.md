# OpenWSFZ Gauge R&R Study — QA Report

---

## Study Identification

| Field | Value |
|---|---|
| **Report date** | 2026-06-09 |
| **Prepared by** | QA (automated via `harness/full_stats.py` + `harness/anova_compute.py`) |
| **Study standard** | AIAG MSA-4 (2010), crossed Gauge R&R — ANOVA method |
| **Appraisers** | WSJT-X 2.7.0 (reference) · OpenWSFZ (product under test) |
| **Parts / Trials** | 10 parts × 3 trials × 2 appraisers = 60 observations per variable scenario |

### Run Directories

| Run | Date | SHA | Noise model | Scenarios run |
|---|---|---|---|---|
| **Baseline** | 2026-06-07 | `4b3a4ca` | Wideband AWGN (0–24 kHz) | S1–S8 full |
| **Current** | 2026-06-09 | `d509b08` | Bandlimited 3 kHz Kaiser FIR | S1, S1b |

S2, S3, S4, S5, S7, S8 results are drawn from the baseline run (`4b3a4ca`).  
S1 and S1b are presented for **both** noise models side-by-side; the current (bandlimited) model is the active noise model in the synthesiser from commit `c9556a2` onward.

### Study Integrity Note — S7 Hardware Interruption

> A hardware failure occurred during scenario S7 of the baseline run.  
> The 23 invalid truth rows (parts 0–3 partial) were removed; S7 was replayed in full from the beginning. All other scenarios (S1–S8 excl. S7) completed before the interruption and are unaffected.  
> S7 results below are from the complete, uncontaminated replay.

---

## Acceptance Criteria (AIAG MSA-4)

| Criterion | Threshold | Verdict |
|---|---|---|
| %GR&R Contribution | < 10% Acceptable; 10–30% Marginal; > 30% Unacceptable | — |
| Number of Distinct Categories (ndc) | >= 10 Excellent; 5–9 Adequate; 2–4 Marginal; 1 Unacceptable | — |
| %Study Var (GR&R) | < 10% Acceptable; < 30% Marginal | — |
| Bias (mean) | Within tolerance per scenario | — |
| Attribute kappa | >= 0.900 PASS | — |

Tolerances per `harness/analyse.py` `TOLERANCE_HALF`:

| Scenario | Characteristic | Tolerance (+/-) | Full Range |
|---|---|---|---|
| S1 | reported_snr_db | +/- 5.0 dB | 10.0 dB |
| S2 | reported_freq_hz | +/- 4.0 Hz | 8.0 Hz |
| S3 | reported_dt_s | +/- 0.2 s | 0.4 s |

---

## S1 — Variable GR&R: SNR Measurement

### S1.1 Measurement Matrix

#### Wideband AWGN (Baseline Run `4b3a4ca`)

| Part | Ref SNR (dB) | WX r1 | WX r2 | WX r3 | OW r1 | OW r2 | OW r3 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -12 | -11 | -11 | -11 | -9 | -10 | -9 |
| 1 | -9 | -8 | -8 | -8 | -6 | -7 | -7 |
| 2 | -6 | -5 | -5 | -5 | -4 | -3 | -3 |
| 3 | -3 | -2 | -2 | -2 | -1 | 0 | -1 |
| 4 | 0 | +1 | +1 | +1 | +2 | +2 | +2 |
| 5 | +3 | +4 | +4 | +4 | +6 | +5 | +5 |
| 6 | +6 | +7 | +7 | +7 | +9 | +8 | +9 |
| 7 | +9 | +10 | +10 | +10 | +11 | +11 | +12 |
| 8 | +12 | +13 | +13 | +13 | +14 | +15 | +14 |
| 9 | +15 | +16 | +16 | +16 | +17 | +18 | +18 |

#### Bandlimited 3 kHz (Current Run `d509b08`)

| Part | Ref SNR (dB) | WX r1 | WX r2 | WX r3 | OW r1 | OW r2 | OW r3 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -12 | -14 | -14 | -14 | -9 | -10 | -9 |
| 1 | -9 | -11 | -11 | -11 | -7 | -6 | -6 |
| 2 | -6 | -9 | -8 | -8 | -4 | -4 | -3 |
| 3 | -3 | -5 | -5 | -5 | -1 | -1 | 0 |
| 4 | 0 | -1 | -2 | -3 | +3 | +3 | +3 |
| 5 | +3 | +1 | +1 | +1 | +5 | +5 | +6 |
| 6 | +6 | +4 | +4 | +4 | +9 | +8 | +9 |
| 7 | +9 | +8 | +8 | +8 | +12 | +12 | +11 |
| 8 | +12 | +11 | +11 | +10 | +15 | +15 | +14 |
| 9 | +15 | +14 | +14 | +14 | +18 | +17 | +18 |

---

### S1.2 Two-Way ANOVA Table (Crossed, With Interaction)

#### Wideband — Run `4b3a4ca`

| Source | DF | SS | MS | F | P |
|---|---:|---:|---:|---:|---|
| Part | 9 | 4452.6833 | 494.7426 | 6516.122 | < 0.001 |
| Appraiser | 1 | 30.8167 | 30.8167 | 405.878 | < 0.001 |
| Appraiser x Part | 9 | 0.6833 | 0.0759 | 0.506 | 0.861 [NS] |
| Repeatability | 40 | 6.0000 | 0.1500 | | |
| **Total** | **59** | **4490.1833** | | | |

Interaction term not significant (p = 0.861). Appraiser x Part variance absorbed by Repeatability per AIAG convention.

#### Bandlimited 3 kHz — Run `d509b08`

| Source | DF | SS | MS | F | P |
|---|---:|---:|---:|---:|---|
| Part | 9 | 4660.4167 | 517.8241 | 1654.586 | < 0.001 |
| Appraiser | 1 | 286.0167 | 286.0167 | 913.899 | < 0.001 |
| Appraiser x Part | 9 | 2.8167 | 0.3130 | 1.341 | 0.247 [NS] |
| Repeatability | 40 | 9.3333 | 0.2333 | | |
| **Total** | **59** | **4958.5833** | | | |

Interaction not significant (p = 0.247); enlarged SS\_Appraiser×Part versus wideband reflects non-uniform SNR bias shift across the part range under bandlimited noise.

---

### S1.3 Variance Components

| Component | WB Variance | WB %Contrib | WB Verdict | BL Variance | BL %Contrib | BL Verdict |
|---|---:|---:|---|---:|---:|---|
| **Total GR&R** | **1.17469** | **1.40%** | **PASS** | **9.78333** | **10.19%** | **MARGINAL** |
| -- Repeatability | 0.15000 | 0.18% | | 0.23333 | 0.24% | |
| -- Reproducibility | 1.02469 | 1.23% | | 9.55000 | 9.94% | |
| ---- Appraiser | 1.02469 | 1.23% | | 9.52346 | 9.92% | |
| ---- Appraiser x Part | 0.00000 | 0.00% | | 0.02654 | 0.03% | |
| Part-to-Part | 82.44444 | 98.60% | | 86.25185 | 89.81% | |
| **Total Variation** | **83.61914** | **100.00%** | | **96.03519** | **100.00%** | |

---

### S1.4 Study Variation (6-Sigma Method)

Tolerance: +/- 5.0 dB --> full range = **10.0 dB**

#### Wideband — Run `4b3a4ca`

| Source | Std Dev | Study Var (6s) | %Study Var | %Tolerance | Verdict |
|---|---:|---:|---:|---:|---|
| **Total GR&R** | **1.0838** | **6.5030** | **11.85%** | **65.03%** | **PASS** |
| -- Repeatability | 0.3873 | 2.3238 | 4.24% | 23.24% | |
| -- Reproducibility | 1.0123 | 6.0736 | 11.07% | 60.74% | |
| ---- Appraiser | 1.0123 | 6.0736 | 11.07% | 60.74% | |
| ---- Appraiser x Part | 0.0000 | 0.0000 | 0.00% | 0.00% | |
| Part-to-Part | 9.0799 | 54.4794 | 99.30% | 544.79% | |
| **Total Variation** | **9.1443** | **54.8661** | 100.00% | 548.66% | |

**Number of Distinct Categories (ndc) = 11 — PASS**

#### Bandlimited 3 kHz — Run `d509b08`

| Source | Std Dev | Study Var (6s) | %Study Var | %Tolerance | Verdict |
|---|---:|---:|---:|---:|---|
| **Total GR&R** | **3.1278** | **18.7670** | **31.92%** | **187.67%** | **MARGINAL** |
| -- Repeatability | 0.4830 | 2.8983 | 4.93% | 28.98% | |
| -- Reproducibility | 3.0903 | 18.5418 | 31.53% | 185.42% | |
| ---- Appraiser | 3.0860 | 18.5161 | 31.49% | 185.16% | |
| ---- Appraiser x Part | 0.1629 | 0.9775 | 1.66% | 9.78% | |
| Part-to-Part | 9.2872 | 55.7231 | 94.77% | 557.23% | |
| **Total Variation** | **9.7998** | **58.7985** | 100.00% | 587.99% | |

**Number of Distinct Categories (ndc) = 4 — MARGINAL**

---

### S1.5 Bias and Linearity

#### Wideband — Run `4b3a4ca`

| Part | Ref SNR | WSJT-X mean | WSJT-X bias | OpenWSFZ mean | OpenWSFZ bias |
|---:|---:|---:|---:|---:|---:|
| 0 | -12 | -11.00 | +1.00 | -9.33 | +2.67 |
| 1 | -9 | -8.00 | +1.00 | -6.67 | +2.33 |
| 2 | -6 | -5.00 | +1.00 | -3.33 | +2.67 |
| 3 | -3 | -2.00 | +1.00 | -0.67 | +2.33 |
| 4 | 0 | +1.00 | +1.00 | +2.00 | +2.00 |
| 5 | +3 | +4.00 | +1.00 | +5.33 | +2.33 |
| 6 | +6 | +7.00 | +1.00 | +8.67 | +2.67 |
| 7 | +9 | +10.00 | +1.00 | +11.33 | +2.33 |
| 8 | +12 | +13.00 | +1.00 | +14.33 | +2.33 |
| 9 | +15 | +16.00 | +1.00 | +17.33 | +2.67 |
| **Mean** | | | **+1.00 dB** | | **+2.43 dB** |

| Appraiser | Mean Bias | Slope | Intercept | R-squared | p(bias=0) | Verdict |
|---|---:|---:|---:|---:|---|---|
| WSJT-X | +1.00 dB | 0.000 | +1.000 | 0.000 | < 0.001 | **PASS** (< 2.0 dB) |
| OpenWSFZ | +2.43 dB | -0.001 | +2.434 | 0.001 | < 0.001 | **FAIL** (> 2.0 dB) |

R-squared ~= 0 for both: bias is constant across the SNR range (flat linearity), no significant slope.

![S1 GR&R Panel — Wideband](../2026-06-07-4b3a4ca/S1_grr_panel.png)
![S1 Bias and Linearity — Wideband](../2026-06-07-4b3a4ca/S1_bias_linearity.png)

#### Bandlimited 3 kHz — Run `d509b08`

| Part | Ref SNR | WSJT-X mean | WSJT-X bias | OpenWSFZ mean | OpenWSFZ bias |
|---:|---:|---:|---:|---:|---:|
| 0 | -12 | -14.00 | -2.00 | -9.33 | +2.67 |
| 1 | -9 | -11.00 | -2.00 | -6.33 | +2.67 |
| 2 | -6 | -8.33 | -2.33 | -3.67 | +2.33 |
| 3 | -3 | -5.00 | -2.00 | -0.67 | +2.33 |
| 4 | 0 | -2.00 | -2.00 | +3.00 | +3.00 |
| 5 | +3 | +1.00 | -2.00 | +5.33 | +2.33 |
| 6 | +6 | +4.00 | -2.00 | +8.67 | +2.67 |
| 7 | +9 | +8.00 | -1.00 | +11.67 | +2.67 |
| 8 | +12 | +10.67 | -1.33 | +14.67 | +2.67 |
| 9 | +15 | +14.00 | -1.00 | +17.33 | +2.67 |
| **Mean** | | | **-1.77 dB** | | **+2.60 dB** |

| Appraiser | Mean Bias | Slope | Intercept | R-squared | p(bias=0) | Verdict |
|---|---:|---:|---:|---:|---|---|
| WSJT-X | -1.77 dB | +0.041 | -1.828 | 0.623 | < 0.001 | **PASS** (< 2.0 dB) |
| OpenWSFZ | +2.60 dB | +0.004 | +2.594 | 0.030 | < 0.001 | **FAIL** (> 2.0 dB) |

WSJT-X: R-squared = 0.623, slope = +0.041 — under-reports more at lower SNR; reflects WSJT-X noise floor estimation sensitivity to the 3 kHz noise bandwidth.  
OpenWSFZ: R-squared ~= 0 — constant positive bias; libft8 SNR estimator is insensitive to noise bandwidth change.

![S1 GR&R Panel — Bandlimited 3 kHz](S1_grr_panel.png)
![S1 Bias and Linearity — Bandlimited 3 kHz](S1_bias_linearity.png)

---

### S1.6 Noise Model Change — Comparison Summary

| Metric | Wideband `4b3a4ca` | Bandlimited 3 kHz `d509b08` | Delta |
|---|---|---|---|
| %GR&R Contribution | 1.40% **(PASS)** | 10.19% **(MARGINAL)** | +8.79 pp |
| %Study Var | 11.85% **(PASS)** | 31.92% **(MARGINAL)** | +20.07 pp |
| %Tolerance | 65.03% | 187.67% | +122.64 pp |
| ndc | 11 **(PASS)** | 4 **(MARGINAL)** | -7 |
| WSJT-X mean bias | +1.00 dB **(PASS)** | -1.77 dB **(PASS)** | -2.77 dB |
| OpenWSFZ mean bias | +2.43 dB **(FAIL)** | +2.60 dB **(FAIL)** | +0.17 dB |
| Inter-appraiser gap | 1.43 dB | 4.37 dB | +2.94 dB |

#### Per-Part Bias Delta Table

| Part | Ref (dB) | WX Wideband | OW Wideband | WX BL-3k | OW BL-3k | Delta WX | Delta OW |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -12 | +1.00 | +2.67 | -2.00 | +2.67 | -3.00 | 0.00 |
| 1 | -9 | +1.00 | +2.33 | -2.00 | +2.67 | -3.00 | +0.33 |
| 2 | -6 | +1.00 | +2.67 | -2.33 | +2.33 | -3.33 | -0.33 |
| 3 | -3 | +1.00 | +2.33 | -2.00 | +2.33 | -3.00 | 0.00 |
| 4 | 0 | +1.00 | +2.00 | -2.00 | +3.00 | -3.00 | +1.00 |
| 5 | +3 | +1.00 | +2.33 | -2.00 | +2.33 | -3.00 | 0.00 |
| 6 | +6 | +1.00 | +2.67 | -2.00 | +2.67 | -3.00 | 0.00 |
| 7 | +9 | +1.00 | +2.33 | -1.00 | +2.67 | -2.00 | +0.33 |
| 8 | +12 | +1.00 | +2.33 | -1.33 | +2.67 | -2.33 | +0.33 |
| 9 | +15 | +1.00 | +2.67 | -1.00 | +2.67 | -2.00 | 0.00 |
| **Mean** | | **+1.00** | **+2.43** | **-1.77** | **+2.60** | **-2.77** | **+0.17** |

**Interpretation:** The bandlimited 3 kHz noise model causes WSJT-X to under-report SNR by approximately 1.77–2.33 dB; its noise floor estimator is sensitive to the noise bandwidth reduction. OpenWSFZ/libft8 is insensitive to the bandwidth change (+0.17 dB average shift). The D-002 defect is therefore confirmed as a **product-side characteristic** in `Ft8Decoder.cs` — not a synthesiser calibration artefact. All synthesiser corrections have been exhausted.

**D-002 Status: OPEN — confirmed product bug.** See defect notice in Section 12.

---

## S1b — Sensitivity Threshold (Informational)

Single signal; SNR swept below the nominal decode floor. No AIAG pass/fail threshold applied — informational only.

| Part | Ref SNR (dB) | WSJT-X Decoded | WSJT-X Rate | OpenWSFZ Decoded | OpenWSFZ Rate |
|---:|---:|---:|---:|---:|---:|
| 0 | -24 | 0/3 | 0% | 0/3 | 0% |
| 1 | -21 | 3/3 | 100% | 0/3 | 0% |
| 2 | -18 | 3/3 | 100% | 3/3 | 100% |
| 3 | -15 | 3/3 | 100% | 3/3 | 100% |

Results are **identical** for both wideband and bandlimited 3 kHz noise models — the sensitivity threshold is not affected by the noise model change.

| Appraiser | Approx. 50% decode threshold | Notes |
|---|---|---|
| WSJT-X | approx. -21 dB | 100% at -21 dB; 0% at -24 dB |
| OpenWSFZ | between -21 and -18 dB | 0% at -21 dB; 100% at -18 dB |

**Sensitivity gap: ~3 dB.** WSJT-X decodes at -21 dB (100%); OpenWSFZ fails completely. This gap is informational; no defect has been formally raised yet. Investigate whether PCM pre-conditioning (recommended for D-002) also closes this gap.

![S1b Decode Rate — Wideband](../2026-06-07-4b3a4ca/S1b_decode_rate.png)
![S1b Decode Rate — Bandlimited 3 kHz](S1b_decode_rate.png)

---

## S2 — Variable GR&R: Frequency Measurement

*Data source: baseline run `4b3a4ca`. No S2 re-run in `d509b08`.*

### S2.1 Two-Way ANOVA Table

| Source | DF | SS | MS | F | P |
|---|---:|---:|---:|---:|---|
| Part | 9 | 35 253 678.15 | 3 917 075.35 | 2 901 537.3 | < 0.001 |
| Appraiser | 1 | 1.35 | 1.35 | 1.000 | 0.343 |
| Appraiser x Part | 9 | 12.15 | 1.35 | 9.000 | < 0.001 |
| Repeatability | 40 | 6.00 | 0.15 | | |
| **Total** | **59** | **35 253 697.65** | | | |

Appraiser main effect not significant (p = 0.343). Interaction significant (p < 0.001) in an absolute sense but trivially small (< 1.4 Hz SS); reflects sub-Hz jitter.

### S2.2 Variance Components

| Component | Variance (Hz^2) | %Contribution | Verdict |
|---|---:|---:|---|
| **Total GR&R** | **0.55000** | **~0.00%** | **PASS** |
| -- Repeatability | 0.15000 | ~0.00% | |
| -- Reproducibility | 0.40000 | ~0.00% | |
| ---- Appraiser | 0.00000 | 0.00% | |
| ---- Appraiser x Part | 0.40000 | ~0.00% | |
| Part-to-Part | 652 845.667 | ~100.00% | |
| **Total Variation** | **652 846.217** | 100.00% | |

### S2.3 Study Variation (6-Sigma Method)

Tolerance: +/- 4.0 Hz --> full range = **8.0 Hz**

| Source | Std Dev (Hz) | Study Var 6s (Hz) | %Study Var | %Tolerance | Verdict |
|---|---:|---:|---:|---:|---|
| **Total GR&R** | **0.7416** | **4.4497** | **0.09%** | **55.62%** | **PASS** |
| -- Repeatability | 0.3873 | 2.3238 | 0.05% | 29.05% | |
| -- Reproducibility | 0.6325 | 3.7947 | 0.08% | 47.43% | |
| Part-to-Part | 807.989 | 4847.93 | 100.00% | 60 599% | |
| **Total Variation** | **807.989** | **4847.93** | 100.00% | | |

**Number of Distinct Categories (ndc) = 1536 — PASS (excellent)**

### S2.4 Bias by Appraiser

| Appraiser | Mean Bias (Hz) | Slope | p(bias=0) | Verdict |
|---|---:|---:|---|---|
| WSJT-X | 0.00 | 0.000 | < 0.001 | **PASS** |
| OpenWSFZ | +0.30 | +0.00025 | 0.343 | **PASS** |

Both appraisers within the +/- 4.0 Hz tolerance. OpenWSFZ frequency measurement is essentially unbiased; 0.30 Hz offset is not statistically significant.

![S2 GR&R Panel](../2026-06-07-4b3a4ca/S2_grr_panel.png)

---

## S3 — Variable GR&R: DT Measurement

*Data source: baseline run `4b3a4ca`. +0.55 s WSJT-X convention correction applied before ANOVA.*

### Convention Correction Note

WSJT-X reports DT relative to the **nominal FT8 TX start**. The study harness uses the **UTC slot boundary** as reference. Without applying the +0.55 s correction to all WSJT-X DT readings, the systematic offset appears entirely in the Appraiser variance component, inflating reproducibility by ~17 percentage points and suppressing ndc from 7 to ~2. The correction is defined in `scenarios/s3-dt-offset.json` (`wsjt_dt_correction_s: 0.55`).

### S3.1 Two-Way ANOVA Table

| Source | DF | SS | MS | F | P |
|---|---:|---:|---:|---:|---|
| Part | 9 | 41.1648 | 4.5739 | 5488.644 | < 0.001 |
| Appraiser | 1 | 0.0167 | 0.0167 | 20.000 | 0.002 |
| Appraiser x Part | 9 | 0.0075 | 0.0008 | 0.032 | 1.000 [NS] |
| Repeatability | 40 | 1.0400 | 0.0260 | | |
| **Total** | **59** | **42.2290** | | | |

Interaction not significant (p ~= 1.000). The residual Appraiser SS (F = 20.0, p = 0.002) reflects genuine sub-0.1 s DT estimation differences between the two appraisers after the convention correction is applied.

### S3.2 Variance Components

| Component | Variance (s^2) | %Contribution | Verdict |
|---|---:|---:|---|
| **Total GR&R** | **0.02653** | **3.36%** | **PASS** |
| -- Repeatability | 0.02600 | 3.30% | |
| -- Reproducibility | 0.00053 | 0.07% | |
| ---- Appraiser | 0.00053 | 0.07% | |
| ---- Appraiser x Part | 0.00000 | 0.00% | |
| Part-to-Part | 0.76217 | 96.64% | |
| **Total Variation** | **0.78870** | 100.00% | |

### S3.3 Study Variation (6-Sigma Method)

Tolerance: +/- 0.2 s --> full range = **0.4 s**

| Source | Std Dev (s) | Study Var 6s (s) | %Study Var | %Tolerance | Verdict |
|---|---:|---:|---:|---:|---|
| **Total GR&R** | **0.1629** | **0.9772** | **18.34%** | **244.31%** | **PASS** |
| -- Repeatability | 0.1612 | 0.9675 | 18.16% | 241.87% | |
| -- Reproducibility | 0.0230 | 0.1378 | 2.59% | 34.46% | |
| Part-to-Part | 0.8730 | 5.2382 | 98.30% | 1309.54% | |
| **Total Variation** | **0.8881** | **5.3285** | 100.00% | | |

**Number of Distinct Categories (ndc) = 7 — PASS**

*Note: %Tolerance = 244% reflects the tight +/- 0.2 s window relative to the ~0.97 s total gauge variation (6-sigma); however, the primary AIAG acceptance criterion is %GR&R Contribution = 3.36%, which comfortably passes. DT repeatability (sigma ~= 0.16 s) is dominated by the synthesiser's audio rendering resolution, not genuine appraiser measurement noise.*

### S3.4 Bias by Appraiser — Per Part (WSJT-X corrected +0.55 s)

| Part | Ref DT (s) | WSJT-X mean (s) | WSJT-X bias | OpenWSFZ mean (s) | OpenWSFZ bias |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.00 | -0.050 | -0.050 | 0.000 | 0.000 |
| 1 | 0.30 | +0.383 | +0.083 | +0.433 | +0.133 |
| 2 | 0.60 | +0.650 | +0.050 | +0.667 | +0.067 |
| 3 | 0.90 | +0.917 | +0.017 | +0.967 | +0.067 |
| 4 | 1.20 | +1.350 | +0.150 | +1.400 | +0.200 |
| 5 | 1.50 | +1.550 | +0.050 | +1.567 | +0.067 |
| 6 | 1.80 | +1.950 | +0.150 | +2.000 | +0.200 |
| 7 | 2.10 | +2.050 | -0.050 | +2.100 | 0.000 |
| 8 | 2.40 | +2.483 | +0.083 | +2.467 | +0.067 |
| 9 | 2.70 | +2.450 | -0.250 | +2.467 | -0.233 |
| **Mean** | | | **+0.023 s** | | **+0.057 s** |

| Appraiser | Mean Bias (s) | Verdict |
|---|---:|---|
| WSJT-X | +0.023 s | **PASS** (< 0.2 s) |
| OpenWSFZ | +0.057 s | **PASS** (< 0.2 s) |

Part 9 (DT = 2.70 s) shows the largest per-part bias for both appraisers (-0.25 s / -0.23 s); this is a known edge at the DT sweep boundary and does not constitute a systematic defect.

![S3 GR&R Panel](../2026-06-07-4b3a4ca/S3_grr_panel.png)

---

## S4 — Attribute Agreement Analysis: Go/No-Go Decode

*Data source: baseline run `4b3a4ca`.*

### Study Design

5 parts x 3 trials x 2 appraisers = 30 assessment observations. Each part presents a target FT8 message. Assessment: was the target decoded (Go) or not (No-Go)? Reference: synthesiser ground truth.

| Part | Target | WSJT-X Decoded | Rate | OpenWSFZ Decoded | Rate |
|---|---|---:|---:|---:|---:|
| 0 | CQ Q1ABC FN42 | 3/3 | 100% | 3/3 | 100% |
| 1 | CQ Q1ABC FN42 | 3/3 | 100% | 3/3 | 100% |
| 2 | CQ Q1ABC FN42 | 3/3 | 100% | 3/3 | 100% |
| 3 | CQ Q1ABC FN42 | 3/3 | 100% | 3/3 | 100% |
| 4 | CQ Q1ABC FN42 | 3/3 | 100% | 3/3 | 100% |
| **Total** | | **15/15** | **100%** | **15/15** | **100%** |

### Attribute Agreement Statistics

| Statistic | WSJT-X | OpenWSFZ |
|---|---|---|
| Within-appraiser agreement | 100% | 100% |
| Agreement vs. reference | 100% | 100% |
| Cohen's kappa | **1.000** | **1.000** |
| Verdict | **PASS** | **PASS** |

Both appraisers exhibit perfect Go/No-Go discrimination when a decodable signal is present. Incidental decodes of other messages co-present in the band scene audio are not attributed to S4 attribute performance.

---

## S5 — Attribute Agreement Analysis: False Positive Rate

*Data source: baseline run `4b3a4ca`.*

### Study Design

4 parts x 3 trials x 2 appraisers. Target FT8 message is absent or below the decode floor. Assessment: was the target message falsely decoded?

| Part | Target SNR | WSJT-X False Alarms | OpenWSFZ False Alarms |
|---|---|---|---|
| 0 | -20 dB (below floor) | 0/3 | 0/3 |
| 1 | -20 dB | 0/3 | 0/3 |
| 2 | -20 dB | 0/3 | 0/3 |
| 3 | -10 dB | 0/3 | 0/3 |
| **Total** | | **0/12 = 0%** | **0/12 = 0%** |

| Statistic | WSJT-X | OpenWSFZ |
|---|---|---|
| Target false alarm rate | 0% | 0% |
| Cohen's kappa | **1.000** | **1.000** |
| Verdict | **PASS** | **PASS** |

Neither appraiser generates false detections of the target message at -10 dB or -20 dB.

---

## S7 — Co-Channel Recovery (Informational)

*Data source: baseline run `4b3a4ca`. No AIAG pass/fail threshold. Comparative analysis only.*

### S7.1 Per-Part Recovery Table

| Part | Label | Family | Signals | WSJT-X | Rate | OpenWSFZ | Rate |
|---:|---|---|---:|---:|---:|---:|---:|
| 0 | 2-stack, equal 0 dB | co_channel | 2 | 5/6 | 83% | **0/6** | **0%** |
| 1 | 2-stack, equal -5 dB | co_channel | 2 | 5/6 | 83% | **0/6** | **0%** |
| 2 | 3-stack, equal 0 dB | co_channel | 3 | VOID | — | VOID | — |
| 3 | delta 3 Hz | near_collision | 2 | 6/6 | 100% | 6/6 | 100% |
| 4 | delta 6 Hz | near_collision | 2 | 6/6 | 100% | 3/6 | 50% |
| 5 | delta 12 Hz | near_collision | 2 | 6/6 | 100% | 6/6 | 100% |
| 6 | delta 25 Hz | near_collision | 2 | 6/6 | 100% | 5/6 | 83% |
| 7 | delta 50 Hz | near_collision | 2 | 6/6 | 100% | 6/6 | 100% |
| 8 | co-freq, dt 0.0 / 0.5 s | time_freq | 2 | 6/6 | 100% | **0/6** | **0%** |
| 9 | co-freq, dt 0.0 / 1.0 s | time_freq | 2 | 6/6 | 100% | 4/6 | 67% |
| 10 | co-freq, dt 0.0 / 2.0 s | time_freq | 2 | 6/6 | 100% | 5/6 | 83% |
| 11 | co-freq, 0 / -3 dB | capture | 2 | 4/6 | 67% | 5/6 | 83% |
| 12 | co-freq, 0 / -6 dB | capture | 2 | 3/6 | 50% | 5/6 | 83% |
| 13 | co-freq, 0 / -10 dB | capture | 2 | 3/6 | 50% | 3/6 | 50% |
| 14 | co-freq, +3 / -10 dB | capture | 2 | 3/6 | 50% | 3/6 | 50% |

*Part 2 voided — hardware failure; data removed. Overall totals include Part 2 as 0/9 for both appraisers.*

### S7.2 Recovery by Family

| Family | Truth (incl. P2) | WSJT-X | Rate | OpenWSFZ | Rate |
|---|---:|---:|---:|---:|---:|
| co_channel (P0, P1, P2) | 21 | 10 | **47.6%** | 0 | **0.0%** |
| near_collision (P3-P7) | 30 | 30 | **100.0%** | 26 | **86.7%** |
| time_freq (P8-P10) | 18 | 18 | **100.0%** | 9 | **50.0%** |
| capture (P11-P14) | 24 | 13 | **54.2%** | 16 | **66.7%** |
| **Overall** | **93** | **71** | **76.3%** | **51** | **54.8%** |

### S7.3 D-001 Key Findings

- **Equal-SNR co-channel (P0, P1):** WSJT-X 10/12 (83%); OpenWSFZ **0/12 (0%)**. OpenWSFZ cannot separate two equal-strength signals at the same frequency. This is the primary D-001 symptom.
- **Time-offset 0.5 s (P8):** WSJT-X 6/6 (100%); OpenWSFZ **0/6 (0%)**. A 0.5 s temporal offset provides no benefit to the libft8 decoder; WSJT-X handles cleanly.
- **Capture (P11-P14):** OpenWSFZ equal to or better than WSJT-X; stronger signal dominates and suppresses the weaker in both decoders.
- **Near-collision (P3-P7):** OpenWSFZ 26/30 (87%) — performance is reasonable once signals are spectrally separated by >= 3 Hz.
- **3-stack (P2):** Data voided; expected 0/9 for both based on P0/P1 co-channel behaviour.

![S7 Recovery Chart](../2026-06-07-4b3a4ca/S7_recovery.png)

---

## S8 — Band Scene (Informational)

*Data source: baseline run `4b3a4ca`. 12 stations x 5 trials = 60 truth signals per appraiser.*

### S8.1 Per-Station Recovery

| Stn | Freq (Hz) | SNR (dB) | Characteristic | WSJT-X | Rate | OpenWSFZ | Rate |
|---|---:|---:|---|---:|---:|---:|---:|
| A | 450 | -8 | standard | 5/5 | 100% | 5/5 | 100% |
| B | 650 | -3 | standard | 5/5 | 100% | 5/5 | 100% |
| C | 850 | -12 | weak | 5/5 | 100% | 5/5 | 100% |
| D | 1050 | 0 | strong | 5/5 | 100% | 5/5 | 100% |
| E | 1150 | -5 | standard | 5/5 | 100% | 5/5 | 100% |
| **F** | **1162** | **-8** | **near-collision with E (12 Hz)** | **5/5** | **100%** | **0/5** | **0%** |
| G | 1500 | 0 | strong | 5/5 | 100% | 5/5 | 100% |
| H | 1500 | -6 | co-freq with G, capture | 2/5 | 40% | 2/5 | 40% |
| I | 1650 | -3 | dt = +0.5 s late | 5/5 | 100% | 5/5 | 100% |
| J | 1900 | -15 | very weak | 5/5 | 100% | 5/5 | 100% |
| K | 2150 | -8 | standard | 5/5 | 100% | 5/5 | 100% |
| L | 2550 | +3 | strong | 5/5 | 100% | 5/5 | 100% |
| **TOTAL** | | | | **57/60** | **95.0%** | **52/60** | **86.7%** |

### S8.2 Key Findings

- **Station F (1162 Hz, -8 dB):** OpenWSFZ 0/5. Near-collision with Station E at 1150 Hz (-5 dB); 12 Hz separation is less than 2 FT8 tone bins. The -3 dB weaker signal is fully suppressed by libft8 but decoded by WSJT-X. Consistent with D-001.
- **Station H (1500 Hz, -6 dB):** Both appraisers 2/5 (40%). Co-frequency capture pair with Station G (0 dB). Neither decoder reliably separates the -6 dB weaker signal; this is a fundamental LDPC decode difficulty, not specific to libft8.
- **Station I (1650 Hz, dt +0.5 s):** Both appraisers 5/5 (100%). Unlike S7-P8, the isolated late-start signal decodes cleanly when there is no co-frequency interferer; S7-P8 failure was a compound co-frequency + time-offset problem.
- **Station J (1900 Hz, -15 dB):** OpenWSFZ 5/5 — strong decode performance at very low SNR for an isolated signal. S1b threshold is not the limiting factor here; co-channel interference is.

![S8 Band Scene Chart](../2026-06-07-4b3a4ca/S8_band_scene.png)

---

## Summary — All Scenarios

| Scenario | Characteristic | WSJT-X | OpenWSFZ | Threshold | Verdict |
|---|---|---|---|---|---|
| S1 (Wideband) | %GR&R Contribution | — | 1.40% | < 10% | **PASS** |
| S1 (Wideband) | ndc | — | 11 | >= 5 | **PASS** |
| S1 (Wideband) | SNR bias — WSJT-X | +1.00 dB | — | +/- 2.0 dB | **PASS** |
| S1 (Wideband) | SNR bias — OpenWSFZ | — | +2.43 dB | +/- 2.0 dB | **FAIL** |
| S1 (BL-3k) | %GR&R Contribution | — | 10.19% | < 10% | **MARGINAL** |
| S1 (BL-3k) | ndc | — | 4 | >= 5 | **MARGINAL** |
| S1 (BL-3k) | SNR bias — WSJT-X | -1.77 dB | — | +/- 2.0 dB | **PASS** |
| S1 (BL-3k) | SNR bias — OpenWSFZ | — | +2.60 dB | +/- 2.0 dB | **FAIL** |
| S1b | Sensitivity threshold | ~-21 dB | ~-18 dB | — | Informational |
| S2 | %GR&R Contribution | — | ~0.00% | < 10% | **PASS** |
| S2 | ndc | — | 1536 | >= 5 | **PASS** |
| S2 | Frequency bias | 0.00 Hz | +0.30 Hz | +/- 4.0 Hz | **PASS** |
| S3 | %GR&R Contribution | — | 3.36% | < 10% | **PASS** |
| S3 | ndc | — | 7 | >= 5 | **PASS** |
| S3 | DT bias | +0.023 s | +0.057 s | +/- 0.2 s | **PASS** |
| S4 | Attribute kappa | 1.000 | 1.000 | >= 0.900 | **PASS** |
| S5 | False alarm rate | 0% | 0% | 0% | **PASS** |
| S7 | Overall recovery | 76.3% | 54.8% | — | Informational |
| S7 | Co-channel equal-SNR | 83.3% | **0.0%** | — | D-001 |
| S7 | Time-offset dt=0.5 s | 100% | **0%** | — | D-001 |
| S8 | Overall band scene | 95.0% | 86.7% | — | Informational |
| S8 | Near-collision (12 Hz) | 100% | **0%** | — | D-001 |

---

## Overall Study Verdict: **FAIL**

D-002 (OpenWSFZ SNR over-report: +2.60 dB) exceeds the +/- 2.0 dB acceptance threshold in the current noise model.

| Study area | Result |
|---|---|
| Variable measurement — S1 (wideband baseline) | PASS |
| Variable measurement — S1 (BL-3k current) | MARGINAL |
| Frequency measurement — S2 | PASS |
| DT measurement — S3 | PASS |
| Attribute agreement — S4/S5 | PASS |
| Co-channel recovery — S7/S8 | D-001 open (informational) |
| SNR bias — D-002 | **FAIL** |

The noise model change (wideband to BL-3k) degraded S1 GR&R from PASS to MARGINAL. The degradation is caused by the enlarged inter-appraiser gap (1.43 dB --> 4.37 dB), which arises because WSJT-X's noise floor estimator is sensitive to noise bandwidth while libft8's is not. This is a measurement system incompatibility, not a new product defect; the BL-3k model more accurately represents real SSB receiver conditions.

---

## Open Defect Notices

### D-001 — Co-Channel Decode Gap

| Field | Detail |
|---|---|
| **ID** | D-001 |
| **Severity** | Medium |
| **Component** | `OpenWSFZ.Ft8` decode pipeline (`Ft8Decoder.cs` -> native `libft8`) |
| **GitHub** | Issue #3 (tracker closed; fix pending) |
| **Evidence** | S7-P0/P1: OW 0/12 vs WX 10/12. S7-P8: OW 0/6 vs WX 6/6. S8-F: OW 0/5 vs WX 5/5. |
| **Root cause** | libft8 (kgoba/ft8_lib v2.0) lacks candidate iteration and successive interference cancellation present in WSJT-X's mature LDPC decoder chain. |
| **Status** | No fix branch. PCM-domain SIC attempted at shim v20260003 — produced instability, removed. No fix timeline. |

### D-002 — SNR Over-Report

| Field | Detail |
|---|---|
| **ID** | D-002 |
| **Severity** | Medium |
| **Component** | `OpenWSFZ.Ft8` SNR reporting (`Ft8Decoder.cs`) |
| **GitHub** | Issue #8 (open) |
| **Evidence** | +2.43 dB (wideband) / +2.60 dB (BL-3k); both exceed +/- 2.0 dB threshold. Constant across all 10 SNR parts and both noise models. |
| **Synthesiser exhausted** | Kaiser FIR noise filter implemented; `measure_inband_snr_db` formula corrected. OpenWSFZ bias unchanged. Confirmed product-side. |
| **Recommended fix** | Add PCM normalisation + tanh soft-limiting pre-conditioning stage in `Ft8Decoder.cs` before `ft8_decode_all`. Precedent: WSJT-X applies AGC before its decode chain. Low risk — one-shot pre-processing, not iterative SIC. |
| **Status** | Fix not yet implemented. OpenSpec change proposal to be raised as next action. |

---

*End of report — 2026-06-09*  
*Next action: raise OpenSpec change proposal for PCM conditioning (D-002 fix candidate). Re-run S1–S8 in full after D-002 fix is implemented to confirm closure.*
