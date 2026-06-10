# siggen Test Session — Resume Notes
**Date:** 2026-06-10  
**Status:** CLOSED — investigation complete

---

## What was done this session

1. **`feat/siggen` merged to `main`** (`b4b6172`) and pushed to GitHub.  
   All 5 review findings (RC-1–RC-5) verified in code before merge.

2. **Test directory created:** `qa/rr-study/tests/siggen/`

3. **Test files created:**

   | File | Description |
   |---|---|
   | `sine_1500hz.jsonl` | Single 1500 Hz sine, 5 s (original smoke test — superseded) |
   | `a_chord.jsonl` | A major chord: 6 sines (110, 164.81, 220, 277.18, 329.63, 440 Hz) at amplitude 0.15; sine version (0–5 s) followed by sawtooth version (5–10 s) for comparison |
   | `tone_cutoff_test.jsonl` | 6-segment, 90-second cutoff comparison test (see layout below) |

4. **`sounddevice` installed** (was missing from environment).

5. **Voicemeeter device confirmed:** `"Voicemeeter Input"` (device [35]) is the correct target for routing to the Voicemeeter mixer. "Out B1" is a Voicemeeter bus, not a Windows audio device — audio must be sent to a virtual input strip and B1 assigned in Voicemeeter GUI.

---

## `tone_cutoff_test.jsonl` layout

| Segment | Time (s) | Content |
|---|---|---|
| 1 | 0–15 | 1500 Hz sine, no noise |
| 2 | 15–30 | 1500 Hz sine + noise, cutoff 4000 Hz |
| 3 | 30–45 | 1500 Hz sine + noise, cutoff 3000 Hz |
| 4 | 45–60 | 1200 Hz + 1657 Hz sine, no noise |
| 5 | 60–75 | 1200 Hz + 1657 Hz sine + noise, cutoff 4000 Hz |
| 6 | 75–90 | 1200 Hz + 1657 Hz sine + noise, cutoff 3000 Hz |

Noise amplitude: 0.08. Tone amplitudes: 0.5 (single tone) / 0.35 (two tones).

**Play command (from repo root):**
```bash
python qa/rr-study/siggen.py qa/rr-study/tests/siggen/tone_cutoff_test.jsonl --device "Voicemeeter Input"
```

---

## Resolved issue — spectral bands when cutoff is active

**Captain reported:** Visible spectral bands appearing in the WSJT-X waterfall whenever a noise segment with `cutoff_hz` is active.

**Screenshot:** `D:\OneDrive\Pictures\Screenshots\Screenshot 2026-06-10 013550.png`

**Resolution (2026-06-10):** No defect. Expected behaviour. Closed.

### Investigation summary

`diagnose_noise_psd.py` was run against 10-second Kaiser FIR-filtered noise buffers at both cutoff frequencies. Results:

| Metric | 4 kHz cutoff | 3 kHz cutoff | Threshold |
|---|---|---|---|
| Passband peak deviation | 0.970 dB | 0.910 dB | <= 1.0 dB |
| Stopband attenuation @ 1.2x cutoff | 71.2 dB | 81.1 dB | >= 30 dB |
| Verdict | PASS | PASS | — |

`synth/channel.py` was also reviewed in full. No logic errors, no resource issues, no threading concerns. The in-band SNR preservation argument (docstring, lines 119–124) is mathematically correct: the FIR cutoff (3–4 kHz) lies above the 2500 Hz reference band, so in-band noise PSD is untouched by the filter.

**Root cause of visual "bands":** The stopband attenuation is 71–81 dB. The region above the cutoff frequency is effectively silent. The waterfall contrast between a lit noise floor below the cutoff and a near-black region above it is the noise bandwidth boundary rendered visually — exactly the intended behaviour of the `noise_cutoff_hz` parameter. Hypothesis 1 confirmed.

**All other hypotheses ruled out:**
- H2 (FIR passband ripple): passband deviation 0.91–0.97 dB, within ±1 dB tolerance. Sub-dB ripple is not the primary visual feature.
- H3 (transition band artefact): attenuation at 1.2× cutoff is 71+ dB, confirming the transition is well-managed.
- H4 (renormalisation interaction): `add_awgn` does not renorm post-filter; spectral shape is not elevated by renorm.
- H5 (boundary transients): `mode='same'` zero-pads first/last 127 samples (~2.6 ms at 48 kHz); negligible in a 10+ second buffer.

### Minor observation (not a defect)

`_lowpass_fir` docstring (line 95) states `mode='same'` means "no boundary transients are introduced." This is slightly imprecise — boundary effects do exist in the first/last 127 samples; they are merely inconsequential at typical buffer lengths. No code change required.

---

## General play command reference

```bash
# From repo root:
python qa/rr-study/siggen.py <scene_file> --device "Voicemeeter Input"

# From qa/rr-study/:
python siggen.py <scene_file> --device "Voicemeeter Input"
```
