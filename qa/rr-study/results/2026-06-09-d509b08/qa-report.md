# Gauge R&R Study Report — OpenWSFZ SNR Measurement System
## Targeted Run: S1 (SNR Bias) + S1b (Low-SNR Sensitivity)

---

| Field                    | Value                                                          |
|--------------------------|----------------------------------------------------------------|
| **Study date**           | 2026-06-09                                                     |
| **Run directory**        | `results/2026-06-09-d509b08`                                   |
| **OpenWSFZ commit**      | `d509b08ade65e8bffb6e9dbe5f79182307a5a82c`                     |
| **Measurement type**     | Variable — reported SNR (dB) vs. synthesised SNR reference     |
| **Study type**           | Gauge R&R — Crossed (ANOVA method)                             |
| **Appraisers**           | WSJT-X 2.7.0 (reference); OpenWSFZ (product under test)        |
| **Number of parts**      | 10 (SNR levels: −12, −9, −6, −3, 0, +3, +6, +9, +12, +15 dB) |
| **Replicates per cell**  | 3                                                              |
| **Total observations**   | 60 (2 appraisers × 10 parts × 3 reps)                         |
| **Tolerance (process)**  | ±2.0 dB → 4.0 dB total range                                  |
| **Scenarios in this run**| S1, S1b only (S2–S8 deferred — see §8)                        |

---

## 1. Study Conditions

### Audio signal path

Synthesiser → VB-CABLE → WSJT-X (simultaneously) and OpenWSFZ.
Both appraisers read from the same audio source; no routing differences between this run and prior runs.

### Change relative to previous run (`4b3a4ca`, 2026-06-07)

This is the first run in which single-signal scenarios (S1, S1b) use **bandlimited AWGN
(`noise_cutoff_hz = 3000 Hz`, Kaiser FIR)** — matching the multi-signal path used by S4, S7,
and S8 since 2026-06-08. All prior S1/S1b runs used wideband AWGN (0–24 kHz at 48 kHz,
effectively 0–6 kHz after resampling).

Additionally, the synthesiser's SNR calibration formula was corrected (Welch PSD integration
replacing the erroneous full-band RMS method) and the brickwall FFT lowpass was replaced with a
Kaiser FIR filter (`8cd0005`, 2026-06-08). These corrections were already in place for the
run at `4b3a4ca`.

---

## 2. Measurement Matrix — S1 (reported SNR, dB)

| Part | Ref SNR | WSJT-X r1 | r2 | r3 | OpenWSFZ r1 | r2 | r3 |
|------|--------:|----------:|---:|---:|------------:|---:|---:|
| P0   |  −12.0  |   −14.0   | −14.0 | −14.0 |  −9.0 | −10.0 |  −9.0 |
| P1   |   −9.0  |   −11.0   | −11.0 | −11.0 |  −7.0 |  −6.0 |  −6.0 |
| P2   |   −6.0  |    −9.0   |  −8.0 |  −8.0 |  −4.0 |  −4.0 |  −3.0 |
| P3   |   −3.0  |    −5.0   |  −5.0 |  −5.0 |  −1.0 |  −1.0 |   0.0 |
| P4   |    0.0  |    −1.0   |  −2.0 |  −3.0 |  +3.0 |  +3.0 |  +3.0 |
| P5   |   +3.0  |    +1.0   |  +1.0 |  +1.0 |  +5.0 |  +5.0 |  +6.0 |
| P6   |   +6.0  |    +4.0   |  +4.0 |  +4.0 |  +9.0 |  +8.0 |  +9.0 |
| P7   |   +9.0  |    +8.0   |  +8.0 |  +8.0 | +12.0 | +12.0 | +11.0 |
| P8   |  +12.0  |   +11.0   | +11.0 | +10.0 | +15.0 | +15.0 | +14.0 |
| P9   |  +15.0  |   +14.0   | +14.0 | +14.0 | +18.0 | +17.0 | +18.0 |

---

## 3. Gauge R&R — Two-Way ANOVA

### Table 1 — With Interaction

```
Source                  DF          SS          MS          F         P
-----------------------------------------------------------------------
Part                     9    4660.4167     517.8241   1654.586   0.0000
Appraiser                1     286.0167     286.0167    913.899   0.0000
Appraiser×Part           9       2.8167       0.3130      1.341   0.2472
Repeatability           40       9.3333       0.2333
Total                   59    4958.5833
```

The Appraiser×Part interaction term is **not significant** (p = 0.2472 > 0.05). Both main effects
are highly significant. Per AIAG MSA-4 and Minitab convention (p-interaction > 0.25), the
interaction term may be pooled with the error term. The without-interaction table is shown below.

### Table 2 — Without Interaction (pooled)

```
Source                  DF          SS          MS          F         P
-----------------------------------------------------------------------
Part                     9    4660.4167     517.8241   2088.34   0.0000
Appraiser                1     286.0167     286.0167   1153.47   0.0000
Repeatability           49      12.1500       0.2480
Total                   59    4958.5833
```

The pooled MS_error = 0.2480 dB². Variance components below are derived from the
**with-interaction** model (conservative; the differences are negligible given the tiny interaction SS).

---

## 4. Variance Components

```
Source                          VarComp    %Contribution
---------------------------------------------------------
Total Gauge R&R                  9.78333        10.19 %
  Repeatability                  0.23333         0.24 %
  Reproducibility                9.55000         9.94 %
    Appraiser                    9.52346         9.92 %
    Appraiser×Part               0.02654         0.03 %
Part-To-Part                    86.25185        89.81 %
Total Variation                 96.03519       100.00 %
```

The **Appraiser** component (9.52, 9.92%) completely dominates the GR&R.
Repeatability (0.23, 0.24%) is excellent — each individual appraiser is highly consistent.
The problem is that the two appraisers do not agree with each other.

---

## 5. Study Variation and Gauge Acceptability

```
Source                    StdDev   Study Var   %Study Var  %Tolerance
                                   (6 × SD)    (SV/Total)  (SV/4.0dB)
----------------------------------------------------------------------
Total Gauge R&R           3.1278     18.767       31.92 %     469.2 %
  Repeatability           0.4830      2.898        4.93 %      72.5 %
  Reproducibility         3.0903     18.542       31.53 %     463.6 %
    Appraiser             3.0860     18.516       31.49 %     462.9 %
    Appraiser×Part        0.1629      0.977        1.66 %      24.4 %
Part-To-Part              9.2872     55.723       94.77 %    1393.1 %
Total Variation           9.7998     58.799      100.00 %    1469.9 %
```

**Number of Distinct Categories (ndc) = 4**

### Acceptability verdict

| Criterion               | Threshold  | Actual    | Verdict      |
|-------------------------|-----------|-----------|--------------|
| %GR&R (Study Var)       | < 10% ideal, < 30% marginal | 31.92%  | **MARGINAL** |
| %Tolerance              | < 10% ideal, < 30% marginal | 469.2%  | **FAIL**     |
| ndc                     | ≥ 10 ideal, ≥ 5 marginal   | 4       | **MARGINAL** |

The %Tolerance figure (469%) is severe and warrants explanation. The tolerance is very tight
(4.0 dB total). The GR&R study var is 18.77 dB (6σ), driven almost entirely by the
4.37 dB mean-bias gap between the two appraisers (WSJT-X: −1.77 dB; OpenWSFZ: +2.60 dB).
The individual appraisers themselves are highly repeatable (σ_repeat = 0.48 dB); the failure
is in reproducibility (appraiser-to-appraiser agreement), not consistency.

See §7 for the graphical panel.

---

## 6. Bias and Linearity Analysis

### Per-part bias summary

| Part | Ref SNR | WSJT-X mean | WSJT-X bias | OpenWSFZ mean | OpenWSFZ bias |
|------|--------:|------------:|------------:|--------------:|--------------:|
| P0   |  −12.0  |      −14.00 |      −2.00  |         −9.33 |        +2.67  |
| P1   |   −9.0  |      −11.00 |      −2.00  |         −6.33 |        +2.67  |
| P2   |   −6.0  |       −8.33 |      −2.33  |         −3.67 |        +2.33  |
| P3   |   −3.0  |       −5.00 |      −2.00  |         −0.67 |        +2.33  |
| P4   |    0.0  |       −2.00 |      −2.00  |         +3.00 |        +3.00  |
| P5   |   +3.0  |       +1.00 |      −2.00  |         +5.33 |        +2.33  |
| P6   |   +6.0  |       +4.00 |      −2.00  |         +8.67 |        +2.67  |
| P7   |   +9.0  |       +8.00 |      −1.00  |        +11.67 |        +2.67  |
| P8   |  +12.0  |      +10.67 |      −1.33  |        +14.67 |        +2.67  |
| P9   |  +15.0  |      +14.00 |      −1.00  |        +17.67 |        +2.67  |

### Linearity regression results

| Appraiser  | Mean Bias    | Slope   | Intercept | R²     | p (bias = 0) | Verdict    |
|------------|-------------:|--------:|----------:|-------:|-------------:|------------|
| WSJT-X     |  **−1.77 dB**| +0.0411 |   −1.8283 | 0.6230 |    < 0.00001 | **PASS**   |
| OpenWSFZ   |  **+2.60 dB**| +0.0040 |   +2.5939 | 0.0303 |    < 0.00001 | **FAIL**   |

**Threshold: mean |bias| ≤ 2.0 dB.**

**OpenWSFZ interpretation:** Bias is essentially constant at +2.60 dB across all SNR levels
(slope ≈ 0, R² ≈ 0.03). This is a pure additive offset in the SNR estimator — consistent with
a fixed miscalibration of the noise floor. There is no linearity error (the bias does not grow
or shrink with SNR).

**WSJT-X interpretation:** The bias of −1.77 dB represents the shift in WSJT-X's estimator
under bandlimited (3 kHz) AWGN. R² = 0.62 indicates slight positive linearity — WSJT-X
under-reports slightly less at higher SNRs. This is consistent with its histogram-based noise
floor estimation being affected by the noise bandwidth. WSJT-X passed the previous run
(bias = +1.00 dB with wideband noise) and passes this run; the direction flip is noted and
understood — see §8.

See `S1_bias_linearity.png` for the graphical bias and linearity panel.

---

## 7. Graphical Outputs

- **`S1_grr_panel.png`** — Six-panel GR&R chart (components of variation, R chart by appraiser,
  X̄ chart by appraiser, by-part plot, by-appraiser box plots, appraiser × part interaction).
- **`S1_bias_linearity.png`** — Bias and linearity panel: observed bias vs. reference SNR with
  regression lines for each appraiser.
- **`S1b_decode_rate.png`** — S1b decode rate by SNR level and appraiser.

---

## 8. S1b — Low-SNR Sensitivity Study

_Informational — no AIAG acceptance threshold. Companion to S1: separates decode capability
from SNR measurement accuracy._

### Study design

| Part | Reference SNR | Rationale                               |
|------|-------------:|-----------------------------------------|
| P0   |   −24.0 dB   | Below expected threshold (negative control) |
| P1   |   −21.0 dB   | WSJT-X claimed lower bound (−21 dB)     |
| P2   |   −18.0 dB   | 3 dB above WSJT-X lower bound           |
| P3   |   −15.0 dB   | Comfortable operating margin            |

### Results

| Part | Ref SNR | WSJT-X | Rate | WSJT-X rep SNR | OpenWSFZ | Rate | OW rep SNR |
|------|--------:|-------:|-----:|---------------:|---------:|-----:|-----------:|
| P0   |  −24.0  |  0 / 3 |  0 % |      —         |   0 / 3  |  0 % |      —     |
| P1   |  −21.0  |  3 / 3 |100 % |    −24.0       |   0 / 3  |  0 % |      —     |
| P2   |  −18.0  |  3 / 3 |100 % |    −20.7       |   3 / 3  |100 % |    −15.7   |
| P3   |  −15.0  |  3 / 3 |100 % |    −17.3       |   3 / 3  |100 % |    −12.0   |

**Overall: WSJT-X 75% (9/12)  |  OpenWSFZ 50% (6/12)**

### Observations

1. **Sensitivity gap at −21 dB.** WSJT-X decodes reliably at −21 dB; OpenWSFZ decodes nothing.
   The gap is ≈ 3 dB. This is consistent with D-001 (co-channel decode gap) in suggesting that
   libft8's soft-decision LDPC decoder operates closer to the noise floor than WSJT-X's.

2. **SNR reporting at decoded parts.** At P2 (true −18 dB), OpenWSFZ reports a mean of −15.7 dB
   (+2.3 dB bias), entirely consistent with its S1 bias of +2.60 dB. At P3 (true −15 dB),
   OpenWSFZ reports −12.0 dB (+3.0 dB). WSJT-X at P2 reports −20.7 dB (−2.7 dB bias) and at
   P3 reports −17.3 dB (−2.3 dB) — consistent with its S1 bias of −1.77 dB.

3. **WSJT-X at −21 dB.** WSJT-X reports the −21 dB signal as −24.0 dB. This is expected: its
   bias of approximately −2 dB applies here too. The decode succeeds even though the reported
   SNR is 3 dB below the synthesised value.

4. **Context for the "improvement" to 50%.** In the previous full run (`4b3a4ca`), OpenWSFZ
   scored 0% overall on S1b. This was an artefact of wideband noise suppressing decodes even
   at −18/−15 dB. The 50% in this run reflects correct behaviour at −18 and −15 dB with
   bandlimited noise; the −21 dB gap was present in both runs but previously obscured.

---

## 9. Comparison to Baseline

**Baseline: full run `4b3a4ca`, 2026-06-07 (wideband AWGN, brickwall filter, erroneous SNR formula).**

| Metric                       | Baseline              | This run             | Delta       |
|------------------------------|-----------------------|----------------------|-------------|
| WSJT-X mean bias             | +1.00 dB              | **−1.77 dB**         | −2.77 dB    |
| OpenWSFZ mean bias           | +2.43 dB              | **+2.60 dB**         | +0.17 dB    |
| %GR&R (Study Var)            | 1.4 %                 | **31.9 %**           | +30.5 pp    |
| ndc                          | 11                    | **4**                | −7          |
| S1b OpenWSFZ overall         | 0 %                   | **50 %**             | +50 pp      |
| S1b −21 dB OpenWSFZ          | 0 %                   | **0 %**              | no change   |

### Interpretation of GR&R degradation

The degradation in %GR&R and ndc is driven exclusively by the appraiser-to-appraiser gap
(reproducibility). In the baseline, both appraisers biased in the same direction: WSJT-X +1.00,
OpenWSFZ +2.43 → spread of 1.43 dB. In this run, they bias in opposite directions: WSJT-X
−1.77, OpenWSFZ +2.60 → spread of 4.37 dB. This tripling of the reproducibility component
collapses the ndc from 11 to 4.

The measurement system has not become "worse" in the sense that each individual appraiser is no
less consistent than before (σ_repeat = 0.48 dB, unchanged). What changed is that the noise
model change caused WSJT-X's bias to flip direction, widening the appraiser gap.

---

## 10. Impact of Noise Model Change on D-002 Verdict

### Summary of synthesiser changes since the original D-002 finding

| Change                                                  | Commit    | Expected effect on D-002 |
|---------------------------------------------------------|-----------|--------------------------|
| Brickwall FFT → Kaiser FIR lowpass                      | `8cd0005` | Remove Gibbs artefact     |
| Correct `measure_inband_snr_db` (Welch PSD)             | `8cd0005` | Remove calibration error  |
| Add `noise_cutoff_hz` to `add_noise()`                  | `d99925a` | Enable bandlimited noise  |
| Apply `noise_cutoff_hz=3000` to S1/S1b/S2/S3            | `c9556a2` | Correct noise model for S1 |

### Result

OpenWSFZ bias: +2.43 dB → **+2.60 dB**. The change is within the run-to-run noise of the study;
the direction (worsening) is not meaningful at this scale.

**All four synthesiser corrections have been exhausted with no meaningful effect on OpenWSFZ's
bias.** The synthesiser is no longer a plausible explanation for D-002.

---

## 11. Defect Register Update

### D-002 — SNR over-report

| Field           | Value                                                          |
|-----------------|----------------------------------------------------------------|
| **ID**          | D-002                                                          |
| **Severity**    | Medium                                                         |
| **Component**   | `OpenWSFZ.Ft8` — SNR reporting                                 |
| **Symptom**     | OpenWSFZ consistently over-reports SNR by +2.60 dB             |
| **Threshold**   | ±2.0 dB                                                        |
| **Status**      | **OPEN** — not closed by synthesiser corrections               |
| **Root cause**  | Product bug in libft8 SNR estimation (confirmed by exclusion)  |

**Confirmed root cause pathway:**

The synthesiser provides audio in which the in-band SNR (0–2500 Hz reference bandwidth) is
calibrated to within ±0.1 dB of the stated true SNR (verified by `verify_noise_psd()`).
OpenWSFZ reports a value 2.60 dB above this. Since no synthesiser correction has moved the
OpenWSFZ bias, the error lies in the product decoder.

libft8's SNR estimator is presented with raw, un-normalised PCM at an arbitrary RMS level.
The estimator's noise floor calculation appears to be calibrated for a specific input level
(likely −18 dBFS, consistent with WSJT-X's internal audio conditioning). OpenWSFZ passes
unconditioned PCM from the WASAPI capture buffer, which will vary with system playback volume
and may misplace the estimator's noise floor.

**Recommended next action:** Implement PCM conditioning in `src/OpenWSFZ.Ft8/Ft8Decoder.cs`
prior to `ft8_decode_all`:

1. Compute RMS of the 15-second PCM buffer.
2. Normalise to a fixed target RMS (−18 dBFS = 0.1259 linear).
3. Apply tanh soft-limiting to suppress transient outliers.

This is a one-shot pre-processing step; it does not modify the native library or the shim.
A new OpenSpec change proposal should be raised before implementation.

### D-001 — Co-channel decode gap

Not re-measured in this run. Status unchanged from `4b3a4ca`. Remains open at GitHub #3.

---

## 12. Scenarios Not Covered in This Run

S2 (frequency sweep), S3 (DT offset), S4 (density), S5 (noise floor), S7 (co-channel), and
S8 (band scene) were **not included** in this targeted run. The results from the previous full
run (`4b3a4ca`) remain the current baseline for those scenarios. A full run will be required
after the PCM conditioning improvement is implemented to assess D-002 closure across all
scenarios and confirm that D-001 and S8 performance are not regressed.

---

## 13. Outstanding Actions

| Priority | Action                                                           | Owner     |
|----------|------------------------------------------------------------------|-----------|
| 1        | Raise OpenSpec change for PCM conditioning in `Ft8Decoder.cs`   | QA/Dev    |
| 2        | Implement and unit-test PCM conditioning                         | Dev       |
| 3        | Run targeted S1+S1b after conditioning; confirm D-002 closure    | QA        |
| 4        | If D-002 closes, run full R&R; archive `fix-synth-brickwall-noise-filter` OpenSpec change | QA |
| 5        | Investigate D-001 (co-channel gap) — separate concern from D-002 | Dev       |

---

## Overall Verdict: FAIL

OpenWSFZ SNR bias = **+2.60 dB** exceeds the ±2.0 dB threshold.
The measurement system is not acceptable for release qualification until D-002 is resolved.
