# Verification Notes — fix-synth-brickwall-noise-filter

**Verified by:** QA  
**Date:** 2026-06-09  
**Branch merged:** `d54a4b0` (main)  
**Overall verdict:** ✅ Task 6.2 PASS — Gibbs artefact eliminated. Post-verification corrections applied (noise cutoff, docstring).

---

## Task 6.2 — WSJT-X Waterfall Check

**Procedure:** `s8-preview.wav` (S8 band scene, trial 0, seed 0) played via VB-CABLE into WSJT-X Wide Graph. Waterfall and spectrum analyser observed for spectral ridges or anomalous energy concentrations at the filter cutoff frequency.

### Pass 1 — 4 kHz cutoff (post-merge state)

**Observation:** No spectral ridge at 4 kHz. The Gibbs build-up that characterised the former brickwall FFT lowpass was not present. Noise floor flat within the passband. Signals visible at expected frequencies (450–2550 Hz per S8 scenario). Noise filled 0–4 kHz and was absent above 4 kHz.

**Finding:** Noise bandwidth (0–4 kHz) was broader than necessary. The FT8 operating range in all R&R scenarios is 300–2700 Hz. The SSB receiver that the synthesiser models has an audio bandwidth of ~3 kHz; a 4 kHz cutoff overshoots by 1 kHz and produces a visually wide noise band in the waterfall with no benefit to the study.

**Action:** `noise_cutoff_hz` lowered from 4000 → 3000 Hz (see §Post-Verification Corrections below).

---

### Pass 2 — 3 kHz cutoff (after correction)

**Observation:** Noise fills 0–3 kHz; above 3 kHz the waterfall is black. No spectral ridge anywhere in the spectrum. Signals remain visible at their expected frequencies. Sharp noise boundary at ~3 kHz is visually apparent.

**Note on the sharp boundary:** The FIR filter produces a well-attenuated transition band (~720 Hz wide, −6 dB at 3000 Hz, −60 dB above ~3360 Hz). The abrupt disappearance of noise at 3 kHz looks synthetic compared to a real SSB receiver (which has a cosine-shaped skirt rather than a Kaiser-windowed FIR). This is cosmetically imperfect but mechanically correct: the SNR calibration operates on the 0–2500 Hz reference band, which is unaffected regardless of the cutoff value, and both WSJT-X and OpenWSFZ process only the audio they receive — they do not see the filter's shape.

**Task 6.2 verdict: PASS.** The Gibbs artefact at the cutoff frequency is absent. Noise bandwidth is within the SSB receiver model. No further waterfall verification is required for this change.

---

## Post-Verification Corrections

The following corrections were applied to `main` directly after the waterfall check, as they were discovered during verification rather than during the original implementation.

### C-1 — `noise_cutoff_hz` 4000 → 3000 Hz in `run_scenario.py`

**Files changed:** `qa/rr-study/harness/run_scenario.py` (3 occurrences: S4 density render, S8 band-scene render, S7 compound render)

**Rationale:**
- Highest signal frequency in any scenario: 2700 Hz (S4 density, evenly spread 300–2700 Hz)
- A 4 kHz noise cutoff provides ~1300 Hz of unnecessary headroom above the highest signal, fills the waterfall with out-of-band noise, and does not model a real SSB receiver (typical audio bandwidth 300–3000 Hz)
- At 3 kHz cutoff, the Kaiser FIR's passband edge is ~2640 Hz (3000 − 360 Hz half-transition). All scenario signals (max 2700 Hz) sit at or near the passband edge; the SNR calibration uses a 0–2500 Hz reference band, which is entirely within the flat passband at either cutoff value. Effect on measured SNR: negligible (<0.5 dB at 2700 Hz)
- S1/S2/S3/S5 single-signal paths do not pass `noise_cutoff_hz` (they use wideband noise); this correction does not affect them

**SNR calibration impact:** None. `noise_sigma_for_snr` computes sigma against the 2500 Hz reference band before filtering. The FIR filter removes noise above 3 kHz but does not alter the noise PSD within 0–2500 Hz. `measure_inband_snr_db` (Welch integration, 0–2500 Hz) confirms the in-band SNR is preserved.

**Test suite:** 98/98 passed after correction. No test changes required (the existing `test_fir_passband_flat_3khz` and `test_snr_preserved_with_cutoff` already exercise this path).

**`s8-preview.wav`** regenerated locally (git-ignored) with 3 kHz cutoff, peak-normalised to 0.9.

---

### C-2 — Docstring correction: transition band figure "~94 Hz" → "~720 Hz"

**Files changed:** `qa/rr-study/synth/channel.py` (module docstring and `_lowpass_fir` docstring), `openspec/changes/fix-synth-brickwall-noise-filter/design.md` (Decision 1)

**Error:** The original implementation stated the Kaiser FIR transition band as "~94 Hz at 48 kHz." This is incorrect by approximately one order of magnitude.

**Correct value:** The Kaiser window design formula gives:

```
Δf = (A − 8) · fs / (2.285 · 2π · M)
   = (63 − 8) · 48000 / (2.285 · 2π · 254)
   ≈ 720 Hz
```

where A ≈ 63 dB (from β = 6.0 via A = 8.7 + β / 0.1102), M = 254 (filter order = numtaps − 1), fs = 48000 Hz.

Consequence: the passband edge sits at approximately 3000 − 360 = 2640 Hz and the stopband edge at approximately 3000 + 360 = 3360 Hz. This is still adequate for the application (all scenario signals are ≤ 2700 Hz; the reference band is 0–2500 Hz), but the original "94 Hz" figure was misleading — it implied a nearly brick-wall FIR at 255 taps, which is not achievable.

---

### C-3 — PR #5 branch deleted

**Branch:** `fix/native-stack-overflow-pcm-residual` (local and `origin`)

**Rationale:** PR #5 was correctly closed without merging on 2026-06-07. The `pcm_residual` stack-overflow fix it contained was superseded by the full revert of PCM-domain SIC (`efc0920`): `pcm_residual` was removed from `ft8_shim.c` entirely. Verified — `grep pcm_residual src/OpenWSFZ.Ft8/Native/ft8_shim.c` returns no matches in current `main`.

---

## Key Observation for Future Reference — Noise in Synthetic Audio

The noise in the synthesised WAVs is **not a defect to be removed** — it is the study variable. The WSJT-X waterfall will always show noise when playing R&R audio, because the SNR calibration requires a noise floor of specific power relative to each signal. "Zero noise" would mean infinite SNR and would invalidate every S1–S8 measurement.

What the `noise_cutoff_hz` parameter controls is the *bandwidth* of that noise — i.e., how far up the spectrum the noise floor extends. 3 kHz is the correct value because:
1. It matches a real SSB receiver's audio bandwidth
2. It covers the R&R scenario signal range (max 2700 Hz)
3. It keeps the WSJT-X waterfall noise floor visually contained within the active FT8 band

The cosmetic distinction from a real radio is that the noise boundary is sharper (FIR rolloff) than a real SSB filter. This is acceptable for the purposes of the R&R study; both appraisers receive identically shaped audio so relative comparisons remain valid.
