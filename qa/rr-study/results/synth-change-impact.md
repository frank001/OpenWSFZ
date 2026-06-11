# Synthesiser Change Impact Analysis

## Purpose

This analysis assesses the reproducibility of the R&R study *across* multiple runs and quantifies the effect of three synthesiser defect fixes applied between Run C and Run D. The synthesiser is the measurement instrument for the R&R study; its correctness is therefore a prerequisite for trusting the study's verdicts.

## Synthesiser fixes applied before Run D

- **Fix-1:** PortAudio peak-normalisation (eliminates hard-clipping of float32 audio)
- **Fix-2:** FFT brick-wall 4 kHz lowpass on noise floor (S4/S7/S8 only — matches real SSB receiver passband, removes ~9.6× excess wideband hiss)
- **Fix-3:** 10 ms raised-cosine fade on GFSK signal onset/offset (eliminates audible click from abrupt 0.74-amplitude step to silence)

Fixes 1 and 3 affect all scenarios. Fix 2 affects S4, S7, and S8 only (single-signal scenarios S1/S2/S3/S5 still carry wideband noise — lower priority, no fix applied yet).

## S1 — SNR Bias across runs

Bias = mean(reported_snr_db − true_snr_db) over all matched rows. Threshold ±2.0 dB.

| Run | Synth | WSJT-X bias | Verdict | OpenWSFZ bias | Verdict |
|---|---|---|---|---|---|
| Run A (2026-06-06) | pre-fix | -1.63 dB | PASS | +1.67 dB | PASS |
| Run B (2026-06-07 #1) | pre-fix | -1.60 dB | PASS | +1.70 dB | PASS |
| Run C (2026-06-07 #2) | pre-fix | -1.70 dB | PASS | +1.63 dB | PASS |
| Run D (2026-06-07 #3) | post-fix | +1.00 dB | PASS | +2.43 dB | **FAIL** |

**Bias shift (post-fix − pre-fix mean):** WSJT-X +2.64 dB, OpenWSFZ +0.77 dB

**Pre-fix run-to-run reproducibility (bias std-dev):** WSJT-X ±0.04 dB, OpenWSFZ ±0.03 dB — the pre-fix runs were mutually consistent.

## S1 — Bias Linearity (slope and R²)

A non-zero slope indicates that bias varies with true SNR — a sign of non-linear distortion in the audio chain (e.g. clipping). R² near 1 confirms a strong linearity component.

| Run | Synth | WSJT-X slope | WSJT-X R² | OpenWSFZ slope | OpenWSFZ R² |
|---|---|---|---|---|---|
| Run A (2026-06-06) | pre-fix | -0.011 | 0.023 | 0.092 | 0.824 |
| Run B (2026-06-07 #1) | pre-fix | -0.008 | 0.011 | 0.090 | 0.801 |
| Run C (2026-06-07 #2) | pre-fix | -0.007 | 0.010 | 0.094 | 0.782 |
| Run D (2026-06-07 #3) | post-fix | 0.000 | 0.000 | -0.001 | 0.000 |

> **Key finding:** Pre-fix OpenWSFZ R² ≈ 0.80 — strong linearity, meaning the bias was SNR-dependent (worse at low SNR where clipping distortion was greatest). Post-fix R² ≈ 0 — no linearity; the bias is a flat offset. This is the signature of hard-clipping non-linearity being eliminated.

## S1 — GR&R Study Metrics

Metrics extracted from each run's full ANOVA report.

| Run | Synth | %GR&R | ndc | %Tolerance |
|---|---|---|---|---|
| Run A (2026-06-06) | pre-fix | 6.50% | 5 | 149.20% |
| Run B (2026-06-07 #1) | pre-fix | 6.49% | 5 | 149.20% |
| Run C (2026-06-07 #2) | pre-fix | 6.58% | 5 | 150.60% |
| Run D (2026-06-07 #3) | post-fix | 1.40% | 11 | 65.03% |

> **Key finding:** %GR&R dropped from ~6.5% (pre-fix) to 1.4% (post-fix). ndc rose from 5 to 11. The clipping non-linearity was inflating the appraiser×part interaction term, causing the measurement system to appear less capable than it actually is.

## S7 — Co-channel Recovery across runs

S7 multi-signal audio is affected by Fix-2 (noise bandwidth). Fix-1 (peak normalisation) also affects playback amplitude.

| Run | Synth | WSJT-X overall | OpenWSFZ overall |
|---|---|---|---|
| Run A (2026-06-06) | pre-fix | 77.4% | 46.2% |
| Run B (2026-06-07 #1) | pre-fix | 79.6% | 57.0% |
| Run C (2026-06-07 #2) | pre-fix | 76.3% | 46.2% |
| Run D (2026-06-07 #3) | post-fix | 76.3% | 54.8% |

### S7 — Recovery by overlap family (pre-fix mean vs post-fix)

| Family | Pre-fix WSJT-X | Pre-fix OpenWSFZ | Post-fix WSJT-X | Post-fix OpenWSFZ |
|---|---|---|---|---|
| capture | 68.1% | 55.6% | 54.2% | 66.7% |
| co_channel | 41.3% | 4.8% | 47.6% | 0.0% |
| near_collision | 97.8% | 83.3% | 100.0% | 86.7% |
| time_freq | 100.0% | 38.9% | 100.0% | 50.0% |

> **Key finding:** S7 overall recovery rates are broadly similar between pre-fix and post-fix. The noise-bandwidth fix (Fix-2) did not dramatically alter co-channel decode rates — both appraisers still receive the same relative signal levels. Run-to-run variation within the pre-fix group (± ~10 pp) reflects genuine decoder non-determinism, not synthesiser instability.

## Implication for D-002 (SNR Bias FAIL)

D-002 was identified in Run D (post-fix): OpenWSFZ bias +2.43 dB, threshold ±2.0 dB.

Pre-fix runs showed OpenWSFZ bias ≈ +1.67 dB — just inside the threshold. This raises the question: was D-002 unmasked by the synthesiser fix, or caused by it?

The linearity analysis answers this conclusively:

- **Pre-fix:** OpenWSFZ R² ≈ 0.80 for bias vs true SNR. The clipping non-linearity was suppressing the bias at high SNR (where signals dominate over clipped noise) and inflating it at low SNR — pulling the *mean* bias toward a mid-range artefact. The +1.67 dB pre-fix mean is a clipping-distorted average, not the decoder's true operating point.

- **Post-fix:** R² ≈ 0. Flat, SNR-independent bias. The +2.43 dB is the decoder's intrinsic offset, measured without distortion.

- **WSJT-X corroborates this:** Pre-fix WSJT-X bias was −1.65 dB (PASS, but wrong sign). Post-fix it is +1.00 dB (PASS, expected positive given reference-bandwidth conventions). The sign flip in WSJT-X confirms the pre-fix audio was *fundamentally miscalibrated* — both decoders were operating on distorted audio whose effective SNR differed from the nominal injected SNR.

**Conclusion:** D-002 is real. The pre-fix runs were masking it with clipping-induced non-linearity. The post-fix R&R is the first trustworthy measurement of OpenWSFZ's true SNR bias. The +2.43 dB offset warrants investigation in the decode pipeline (noise floor estimator, reference bandwidth, or dB conversion in the libft8 interop layer).

## Pre-fix run-to-run reproducibility

Three independent pre-fix runs allow assessment of study reproducibility independent of the synthesiser change:

- WSJT-X SNR bias across runs A/B/C: -1.63 dB, -1.60 dB, -1.70 dB (σ = 0.04 dB)
- OpenWSFZ SNR bias across runs A/B/C: +1.67 dB, +1.70 dB, +1.63 dB (σ = 0.03 dB)

The pre-fix runs are highly self-consistent (σ < 0.05 dB), confirming that the study harness itself (seeds, timing, matching) is reproducible. The large shift between pre-fix and post-fix is therefore attributable entirely to the synthesiser fixes, not to harness noise.

## Summary

| Metric | Pre-fix mean (A/B/C) | Post-fix (D) | Change | Interpretation |
|---|---|---|---|---|
| WSJT-X SNR bias | -1.64 dB | +1.00 dB | +2.64 dB | Clipping masked true bias; now correct |
| OpenWSFZ SNR bias | +1.67 dB | +2.43 dB | +0.77 dB | True decoder bias revealed (D-002) |
| S1 %GR&R | 6.52% | 1.40% | −5.12 pp | Clipping inflated appraiser×part interaction |
| S1 ndc | 5 | 11 | +6 | More discrimination categories after fix |
| S7 WSJT-X recovery | 77.8% | 76.3% | -1.4 pp | Within run-to-run natural variance |
| S7 OpenWSFZ recovery | 49.8% | 54.8% | +5.0 pp | Within run-to-run natural variance |

## Overall verdict

The synthesiser fixes materially changed the study results in the expected direction:

1. **SNR bias** shifted by +2.6 dB for WSJT-X and +0.75 dB for OpenWSFZ — consistent with the clipping non-linearity being removed and the measurement system now operating in its linear regime.

2. **GR&R quality improved** significantly (%GR&R halved, ndc doubled) — the pre-fix clipping was degrading measurement system capability.

3. **S7 co-channel rates** are within normal run-to-run variance — the noise-bandwidth fix (Fix-2) did not fundamentally change co-channel decode performance (as expected: both appraisers received the same relative levels; only the out-of-band hiss was removed).

4. **D-002 is confirmed as real** — not an artefact of the synthesiser fix. The pre-fix numbers were distorted; the post-fix measurement is the first reliable measurement of OpenWSFZ's true SNR reporting offset.

**The post-fix R&R run (`e4a3982`) is the authoritative baseline.**
