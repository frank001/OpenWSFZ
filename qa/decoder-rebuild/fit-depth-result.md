# FIT-DEPTH: result note (INCONCLUSIVE; ended by the Architect's rule of amendment 1b)

**Date:** 2026-11-27 · **By:** QA · **Spec:** `docs/decoder-rebuild/spec-fit-depth.md` (`1782cb4a`, amendment 1 `224b614e`, amendment 1b as relayed by the Architect) · **Tooling:** `qa/decoder-rebuild/fit_depth.py`, `fit_depth_report.py`, a `smooth` switch in `qa/rr-study/sub-feas/fitter.py` and `qa/rr-study/synth/modulator.py` (default unchanged, byte-identical phase checked)
**Data:** S40 only, the first 20 cycles (566 WSJT-X decodes of −15 dB or stronger fitted, 2 fit failures), seed 20261127, records `_qa-scratch\fit-depth\{pilot,pilot2}` (kept). Aggregates only; no message text in this note (HK-037).

## The ending rule (written by the Architect before the isolated read)

Run k = 5 on all three slices only if the **isolated** SC median F is within ±1.5 dB **and** the **isolated** S0–S2 pooled median F is ≥ 2 dB. Otherwise the measurement ends inconclusive (the noise-spot reference fails on these recordings); no further amendment.

## The read (pilot2, F at W = 0.32 s, GFSK, isolated signals only, no re-fit)

| Group | n | median F (dB) | Q1 | Q3 |
|---|---:|---:|---:|---:|
| SC (−15 to −11) | 17 | **+0.67** | −0.97 | +2.84 |
| S0–S2 pooled | 80 | **+1.58** | +0.08 | +4.20 |
| S0 | 38 | +1.56 | −0.25 | +3.09 |
| S1 | 24 | +3.44 | +1.03 | +6.37 |
| S2 | 18 | +0.97 | −0.69 | +1.70 |

SC passes (|0.67| ≤ 1.5). **S0–S2 pooled is 1.58 dB, under the 2 dB bar: the rule fires, the measurement ends INCONCLUSIVE.** All-signal figures (crowded neighbours inside the footprint, not read): SC +6.99, S0–S2 +7.83 dB.

## The checks, as recorded

| Check | Result |
|---|---|
| C1′ (Python − native SUB suppression, clean signals) | **FAIL −2.16 dB** (n = 295, Q1 −4.08, Q3 −0.58; all-signal −2.36, n = 416). Not re-cut. Absolute F may overstate production's room by up to about 2 dB; the paired §6 condition is unaffected. |
| C2′ (all signals) | FAIL, SC median F +6.99 dB |
| C3′ (all signals) | pass, +7.83 dB (not separating strength: SC reads +7) |
| C4 | complete; no injection spot for S0 103 of 148 crowded vs 6 of 39 isolated, S1 85/115 vs 3/24, S2 77/103 vs 2/18 (injection is only run for S0-S2; SC has none); no noise spot: 0 in every band |
| Earlier own-cell D (amendment 0) | blind by construction (HK-026): C2 passes at −0.44, C3 fails at +0.28 |

## Cause check for C1′ (records only, no re-fit; 295 clean signals)

- Native time minus Python start: median **0.156 s**, Q1 0.14, Q3 0.17 (a constant convention offset; the spread is ±15 ms).
- Native frequency minus Python frequency: median **+0.14 Hz**, Q1 −0.59, Q3 +0.95.
- The suppression difference does not follow the time deviation: −1.97 dB where it is small (n = 154), −2.18 dB where it is large (n = 141).

So the −2 dB is not a position mismatch. What is left is the definitions: native sums a waterfall (Hann-windowed, oversampled) over the round's input and residual, the Python grid sums one DFT bin per cell on the fitted grid.

## What the result says, and does not

- Isolated strong signals are removed close to the noise by the Python fit (F ≈ 1.6 dB over the noise spot at 0.32 s, within the up to 2 dB by which F may overstate production's room): **no 4–6 dB shortfall is visible on isolated signals** in this measurement.
- It does **not** say anything about window length, pulse shape, or L_T / retention: none of the variants was read, and the §6 rows were never part of the decision (the rows printed in the first pilot were void).
- Crowded signals cannot be read in absolute terms: neighbours inside the footprint raise F by about 7 dB. Only paired changes between variants would cancel them; that run was not made.
- Standing caveat for any later use of the tooling: the start-time seed (`TAU0_S = −0.16 s` of SUB-FEAS) does not hold on these recordings (signals start about 0.52 s after the WSJT-X DT); the tool calibrates it per slice. Run cost: about 470 s per cycle at 14 workers (full 650 cycles ≈ 6.9 h; k = 5 ≈ 82 min).

## Not run (by the ending rule)

The k = 5 run on S40, H40 and H20, and the two finer views of §8.6 (half-bin frequency profile; symbol edge against centre).
