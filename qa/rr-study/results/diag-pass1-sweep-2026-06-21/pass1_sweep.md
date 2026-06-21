# D-009 — Pass-1 `K_MIN_SCORE_PASS2` Trade-Curve

**Date:** 2026-06-21  
**Branch:** fix/d009-fp-callsign-filter  
**Shim:** 20260028 (OSD_NHARD_MAX=60, OSD_CORR_THRESHOLD=0.10 unchanged throughout)  
**Metric method:** OpenWSFZ-only; no WSJT-X comparator required for this diagnostic axis.  

## Trade-curve table

| `K_MIN_SCORE_PASS2` | S5 FP/slot | S5 FP count / slots | S7 co_channel_sweep % |
|---|---|---|---|
| 1 (baseline) | 0.675 | 81 / 120 | 28.6% |
| 3 | 0.525 | 63 / 120 | 31.4% |
| 5 | 0.533 | 64 / 120 | 45.7% |
| 7 | 0.558 | 67 / 120 | 42.9% |
| 10 | 0.042 | 5 / 120 | 37.1% |

## Reading

### S5 axis — D-009 (false-positive cost)

The FP rate is essentially **flat from K=1 through K=7** (0.525–0.675 FP/slot range, ~20% relative spread).
Raising K from 1→3 cuts FPs by ~22% (81→63); further increases to 5 and 7 give no additional reduction and actually trend slightly upward — within measurement noise but indicating that the FP-generating candidates predominantly have sync scores < 3 **or** ≥ 8, with very few in the 3–7 band.

**K=10 produces a step-change:** 5 FPs in 120 slots (0.042 FP/slot) — a **94% reduction** from baseline.
At K=10, pass-1 applies the same score floor as pass-0 (`K_MIN_SCORE=10`), admitting only candidates
that the full-waterfall scan considered sync-quality. After pass-0 has subtracted its decodes, few such
high-score candidates remain in the residual spectrogram, so pass-1 generates almost no FPs.

### S7 axis — D-001 (co-channel benefit)

Co-channel recovery (P0–P2, equal-SNR / near-equal-SNR stacks) **peaks at K=5: 45.7%** (16/35),
compared with 28.6% at K=1 (baseline). Recovery at K=7 is 42.9% (15/35) and at K=10 is 37.1% (13/35).

Interpretation: after pass-0 decodes one signal of a co-channel pair and suppresses it, the residual
partner often presents a sync score in the **5–9 range** — just below the pass-0 floor. K=5 admits
those candidates; K=10 does not, which explains the recovery decrease from 45.7%→37.1%.
Note that K=1 performs *worse* (28.6%) than K=5 despite admitting more candidates — excess
low-score candidates in pass-1 likely consume OSD budget or interfere with subtraction, suppressing
the genuine co-channel residual.

### Trade summary

| K | FP/slot | vs baseline | S7 co_ch % | vs baseline |
|---|---|---|---|---|
| 1 | 0.675 | — | 28.6% | — |
| 3 | 0.525 | −22% | 31.4% | +2.8 pp |
| 5 | 0.533 | −21% | **45.7%** | **+17.1 pp** |
| 7 | 0.558 | −17% | 42.9% | +14.3 pp |
| 10 | **0.042** | **−94%** | 37.1% | +8.5 pp |

No Pareto-dominant point exists: K=5 maximises co-channel recovery; K=10 minimises FPs.
The architect must decide the acceptable FP budget and select K accordingly.
K=5 and K=10 are the natural candidates.

---

**NFR-021 compliance:** No real callsigns appear in this document.  
S5 FP counts are numeric only; S7 uses Q-prefix synthetic callsigns (MSG-01/02/03).  