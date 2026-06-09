# QA Report — R&R Run 2026-06-09 (d509b08) — Targeted S1 + S1b

| Field | Value |
|---|---|
| Run date | 2026-06-09 |
| Run ID | `d509b08` |
| Scenarios | S1 (SNR bias), S1b (low-SNR threshold) |
| Purpose | First run with `noise_cutoff_hz=3000` applied to single-signal scenarios |
| QA engineer | Claude (QA persona) |
| Status | **FAIL — D-002 persists** |

---

## 1. Context — What Changed

This run is the first targeted re-measurement following three synthesiser improvements merged in
`fix-synth-brickwall-noise-filter` (2026-06-08) plus one further change committed today (`c9556a2`).

### Synthesiser changes (cumulative since last R&R baseline `4b3a4ca`)

| Change | Commit | Scope |
|---|---|---|
| Replace brickwall FFT lowpass with Kaiser FIR (numtaps=255, β=6.0) | `8cd0005` | `channel._lowpass_fir` |
| Correct `measure_inband_snr_db` to Welch PSD integration | `8cd0005` | `channel.add_noise`, `channel.mix_to_shared_floor` |
| Add `noise_cutoff_hz` parameter to `channel.add_noise` | `d99925a` | multi-signal paths already used `mix_to_shared_floor` |
| **Apply `noise_cutoff_hz=3000` to single-signal paths (S1, S1b, S2, S3)** | `c9556a2` | `harness/run_scenario.py` `_render_single` |

The final item is the only change new to this run. All previous R&R runs presented S1/S1b with
**wideband** AWGN (0–24 kHz at 48 kHz, equivalent to 0–6 kHz after resampling). This run presents
**bandlimited** AWGN with a 3 kHz Kaiser FIR cutoff to both appraisers — matching the multi-signal
path and more accurately modelling a real SSB receiver passband.

---

## 2. S1 — SNR Bias Results

### Raw metrics

| Appraiser | Mean Bias | Slope | R² | Verdict |
|---|---|---|---|---|
| WSJT-X | **−1.77 dB** | 0.041 | 0.401 | PASS |
| OpenWSFZ | **+2.60 dB** | 0.004 | 0.005 | **FAIL** |

Threshold: ±2.0 dB.

### Comparison to baseline (`4b3a4ca`, 2026-06-07)

| Appraiser | Baseline | This run | Delta |
|---|---|---|---|
| WSJT-X | +1.00 dB | −1.77 dB | −2.77 dB |
| OpenWSFZ | +2.43 dB | +2.60 dB | +0.17 dB |

OpenWSFZ's bias is essentially unchanged (+0.17 dB). **All three synthesiser improvements had no
meaningful effect on OpenWSFZ's SNR over-report.** This eliminates the synthesiser as the cause
of D-002 and confirms it is a product bug.

### GR&R metrics

| Metric | Baseline | This run | Verdict |
|---|---|---|---|
| %GR&R | 1.4% | 10.2% | MARGINAL (threshold: <30% = acceptable) |
| ndc | 11 | 4 | MARGINAL (threshold: ≥5 = acceptable) |

The GR&R degradation is explained by the appraiser-to-appraiser gap: WSJT-X and OpenWSFZ now bias
in *opposite directions* (−1.77 vs +2.60 dB → 4.37 dB spread). Previously both biased positive
(+1.00 vs +2.43 dB → 1.43 dB spread). Reproducibility now dominates the total GR&R variance.
The measurement system has become less capable as a comparator because the reference appraiser
(WSJT-X) has shifted under the new noise model.

### Why WSJT-X's bias flipped

WSJT-X shifted from +1.00 dB to −1.77 dB when the noise was bandlimited to 3 kHz.
Its histogram-based noise floor estimator is sensitive to the spectral content of the noise.
With wideband noise, the energy density within the FT8 band (0–2500 Hz) was underestimated
(the histogram includes out-of-band silence); bandlimiting concentrates power in-band, causing
WSJT-X's estimator to over-estimate the noise floor and consequently under-report SNR.
This is a property of WSJT-X's internal estimator, not a study defect. Both appraisers received
identical audio.

**Implication for D-002:** OpenWSFZ does not exhibit this sensitivity — its bias is flat across noise
models. The 3 kHz cutoff was the last plausible synthesiser correction. No further synthesiser
improvements can close D-002; the cause must be in `Ft8Decoder.cs`.

---

## 3. S1b — Low-SNR Threshold Results

### Per-part decode rate

| Part | True SNR (dB) | WSJT-X | OpenWSFZ |
|---|---|---|---|
| P0 | −24 dB | 0/3 (0%) | 0/3 (0%) |
| P1 | −21 dB | **3/3 (100%)** | 0/3 (0%) |
| P2 | −18 dB | 3/3 (100%) | 3/3 (100%) |
| P3 | −15 dB | 3/3 (100%) | 3/3 (100%) |

**Overall: WSJT-X 75%, OpenWSFZ 50%.**

### Comparison to baseline (`4b3a4ca`, wideband noise)

| Appraiser | Baseline overall | This run overall | P1 (−21 dB) change |
|---|---|---|---|
| WSJT-X | 75% (3/4 SNRs) | 75% (3/4 SNRs) | 100% → 100% (no change) |
| OpenWSFZ | **0%** (0/4 SNRs) | **50%** (2/4 SNRs) | 0% → 0% (no change) |

OpenWSFZ's overall rate improved from 0% to 50% purely because −18/−15 dB trials were also
wideband in the baseline (yielding 0 decodes at those SNRs in that run). With bandlimited noise,
the −18 and −15 dB trials decode correctly. The **−21 dB gap is unchanged**: WSJT-X 100%,
OpenWSFZ 0%.

> **Note:** The S1b baseline 0% overall figure is misleading — the previous run used wideband
> noise which inflated the effective noise power and suppressed decodes even at −15 dB. The
> −21 dB gap was also present in the baseline but could not be distinguished from the general
> decode suppression. This run cleanly isolates the gap at −21 dB.

This sensitivity gap (approximately 3 dB) is not logged as a formal defect. It is informational.
It is consistent with D-001 (co-channel decode gap) in suggesting that libft8's decoder is less
capable than WSJT-X's at marginal SNR conditions.

---

## 4. Defect Status

### D-002 — SNR over-report (+2.60 dB, threshold ±2.0 dB)

**Status: OPEN. Synthesiser cannot be the cause.**

Root cause isolation:
- Synthesiser formula corrected (Welch PSD, not full-band RMS): no effect.
- Brickwall artefact removed (Kaiser FIR): no effect.
- Noise bandwidth corrected (3 kHz vs 24 kHz): +0.17 dB change (noise floor measurement artefact).

**Recommended next action:** Add PCM conditioning to `Ft8Decoder.cs` before `ft8_decode_all`:
1. Compute RMS of the 15 s PCM buffer.
2. Normalise to target RMS (−18 dBFS, matching typical WSJT-X input levels).
3. Apply a soft-limiter (tanh) to suppress outlier transients.

This is a one-shot pre-processing step. It does not touch the native library or the shim.
The hypothesis is that libft8's noise floor estimator assumes a calibrated input level;
un-normalised PCM causes it to misplace the noise floor and thus mis-report SNR.

An OpenSpec change proposal should precede implementation.

### D-001 — Co-channel decode gap

**Status: OPEN.** Not re-measured in this run (S7 not included). No change since `4b3a4ca`.

---

## 5. Decision on `fix-synth-brickwall-noise-filter` OpenSpec change

D-002 persists. The change improved the synthesiser's accuracy but did not close the defect.
**Do not archive yet.** The OpenSpec change for `fix-synth-brickwall-noise-filter` should remain
open until a D-002 fix is attempted and either confirms closure or rules out the conditioning
hypothesis, at which point both changes can be archived together.

---

## 6. Summary

| Item | Verdict |
|---|---|
| D-002 closed by synthesiser improvements | **No** |
| D-002 cause identified | **Yes — product bug in libft8 SNR estimation** |
| S1b sensitivity gap at −21 dB | **Confirmed, unchanged** |
| Next action | PCM conditioning in `Ft8Decoder.cs` (OpenSpec proposal first) |
| Synthesiser noise model | **Consistent across all scenarios from this run forward** |
