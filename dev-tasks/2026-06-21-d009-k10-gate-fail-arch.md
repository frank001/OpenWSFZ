# D-009 — Architect Review: K=10 Gate Failure

**Date:** 2026-06-21
**Raised by:** QA (post-confirmation gate)
**Defect ID:** D-009 — OSD false-positive manufacture in noise
**Branch:** `fix/d009-fp-callsign-filter`
**Gate commit:** `11b8823` (shim 20260029)

---

## 0. Executive summary

The K=10 confirmation gate (`dev-tasks/2026-06-21-d009-k10-confirm-dev.md`) ran to
completion. **Gate G-A fails.** K_MIN_SCORE_PASS2=10 regresses co_channel_sweep
by −5.5 pp (86.67% vs 92.14% reference), with P15 (Δ5 Hz) dropping 30 pp and
P16 (Δ7 Hz) dropping 15 pp. K=10 does not merge.

Gate G-B (S5 FP rate) passed comfortably at 0.042 FP/slot (−94% vs baseline), but
is academic — G-A is the blocking gate.

**Architect decision requested:** select the next operating point. Three options are
presented below, each with supporting data.

---

## 1. What the confirmation run measured

### Shim 20260029 — what changed

```
K_MIN_SCORE_PASS2   1  →  10     (pass-1 score floor = pass-0 floor)
FT8_SHIM_VERSION    20260028  →  20260029
All other 20260028 values unchanged: OSD_NHARD_MAX=60, OSD_CORR_THRESHOLD=0.10,
text Rules A/B/C, K_MIN_SCORE=10, K_MAX_CANDIDATES_PASS2=200.
```

### Gate G-A — Full 21-part S7 (K=5 trials/part)

**Criterion:** co_channel_sweep ≥ 89% (AD4; ref 92.14% at shim 20260025/K=1).

| Overlap family | Shim 20260025 (K=1) | Shim 20260029 (K=10) | Δ |
|---|---|---|---|
| co_channel | 48.57% | 34.29% | −14.3 pp |
| **co_channel_sweep** | **92.14%** | **86.67%** | **−5.5 pp ❌** |
| near_collision | 91.00% | 84.00% | −7.0 pp |
| time_freq | 93.33% | 100.00% | +6.7 pp |
| capture | 63.75% | 60.00% | −3.8 pp |

#### co_channel_sweep per-part breakdown

| Part | Condition | K=1 ref (d70aad5) | K=10 (this run) | Δ |
|---|---|---|---|---|
| P15 | Δ5 Hz, 2-stack equal 0 dB | 16/20 = 80% | 5/10 = **50%** | **−30 pp** |
| P16 | Δ7 Hz, 2-stack equal 0 dB | 34/40 = 85% | 7/10 = **70%** | **−15 pp** |
| P17 | Δ10 Hz | 20/20 = 100% | 10/10 = 100% | 0 pp |
| P18 | Δ15 Hz | 20/20 = 100% | 10/10 = 100% | 0 pp |
| P19 | Δ8 Hz | 19/20 = 95% | 10/10 = 100% | +5 pp |
| P20 | Δ9 Hz | 20/20 = 100% | 10/10 = 100% | 0 pp |
| **Total** | | **92.14%** | **86.67%** | **−5.5 pp ❌** |

#### Root cause

After pass-0 decodes one co_channel partner and applies spectrogram SIC, the
residual signal at Δ5–7 Hz has degraded tile alignment (heavy tile overlap at
tight offsets). Its sync score falls below 10, and `K_MIN_SCORE_PASS2=10` rejects
it from pass-1. At K=1 (or ≤7) the residual is admitted and decoded via OSD.

The regressions are concentrated at the two tightest co_channel_sweep offsets;
all others (Δ8 Hz and above) are unaffected or improved.

### Gate G-B — Widened S5 FP rate (120 slots, clean sequential run)

| Metric | K=1 baseline | K=10 (this run) | Sweep K=10 |
|---|---|---|---|
| FP/slot | 0.675 | **0.042** | 0.042 |
| Total FPs | 81/120 | 5/120 | 5/120 |
| FP reduction | — | **−94%** | −94% |
| 95% UB (Wilson) | — | ~9.4%/slot | — |

The sweep K=10 and gate K=10 FP rates are identical (5/120) — confirming
measurement consistency. Per AD3 a non-zero rate is "report-and-discuss"; at 0.042
FP/slot the absolute rate is low. This would be acceptable if G-A had passed.

---

## 2. Pass-1 sweep recap (context for option trade-offs)

From `qa/rr-study/results/diag-pass1-sweep-2026-06-21/pass1_sweep.md` (shim 20260028):

| K | S5 FP/slot | FP reduction vs K=1 | S7 hard co_ch (P0–P2) |
|---|---|---|---|
| 1 (baseline) | 0.675 | — | 28.6% |
| 3 | 0.525 | −22% | 31.4% |
| 5 | 0.533 | **−21%** | **45.7% (peak)** |
| 7 | 0.558 | −17% | 42.9% |
| 10 | **0.042** | **−94%** | 37.1% |

Key observations:
- **FP reduction** is essentially flat K=1–7 (0.525–0.675, ~17–22% reduction), then
  **step-changes to 94% reduction at K=10**. The jump is non-linear and abrupt.
- **Hard co_channel recovery** peaks at K=5 and degrades at K=10. The sweep only
  measured P0–P2 (hard equal-SNR 2/3-stack), not P15/P16 (tight-offset sweep).
- The gate run confirms K=10 also regresses P15/P16 (the tightest sweep offsets),
  suggesting the mechanism generalises: any residual with sync score 1–9 is cut.
- **No sweep data between K=7 and K=10.** Whether there is a value in that range
  that preserves P15/P16 while materially cutting FP rate is unknown.

---

## 3. Options

### Option A — Fall back to K=5 (sweep-recommended co_channel peak)

**Change:** Revert `K_MIN_SCORE_PASS2` to 5 (shim 20260030).

| Dimension | K=5 projection |
|---|---|
| S5 FP/slot | ~0.533 (sweep measured) — only −21% vs baseline |
| S5 FP/slot absolute | ~64/120 slots would still fire |
| S7 hard co_channel (P0–P2) | 45.7% (best in sweep) |
| S7 co_channel_sweep (P15/P16) | Likely ≥ K=1 baseline (~80–85%) — not yet measured |
| co_channel_sweep headline | Expected ≥ 92.14% (K=1 reference) |

**Trade-off:** Co_channel recovery is maximised, but FP suppression is weak (only
21% reduction). The D-009 FP problem is substantially un-fixed at K=5 — most of
the 81 FP events/120 slots would remain.

**Verdict:** Good for sensitivity; poor for D-009 FP suppression. Unlikely to close
D-009 to an acceptable level.

---

### Option B — Probe K=8 or K=9 (unexplored sweet-spot range)

**Change:** Run a targeted 2-point sweep (K=8, K=9) on shim 20260028 to measure
both S5 FP rate and S7 co_channel_sweep (including P15/P16).

**Hypothesis:** The FP step-change between K=7 (0.558/slot) and K=10 (0.042/slot)
may have an intermediate inflection. A value in the K=8–9 range might cut FP
meaningfully (perhaps 50–80% reduction) while admitting Δ5–7 Hz residuals
(sync scores 8–9) that K=10 currently rejects.

**Evidence for / against:**
- *For:* The sweep shows a non-monotone relationship — K=5 outperforms K=7 on
  hard co_channel despite higher K. The relationship is complex, not simply
  "more K = worse recovery." There may be a window between 8 and 10 that is
  better on both axes than K=10.
- *Against:* At K=8 and K=9, whether residual Δ5–7 Hz signals score ≥ 8 after
  SIC suppression is unknown — their scores might still be below 8, making K=8
  and K=9 equivalent to K=10 for P15/P16.

**Effort:** ~2 R&R study runs (~90 min total wall-clock); can be structured as a
mini-sweep with the existing `analyse_sweep.py` framework.

**Verdict:** Recommended diagnostic step if Option C is not chosen. Low cost, high
information value.

---

### Option C — Accept K=10 regression as a deliberate trade-off

**Change:** Merge shim 20260029 as-is, with the P15/P16 regression formally
accepted and documented.

**Rationale:** The co_channel_sweep regression is at the two tightest offsets
(Δ5 Hz, Δ7 Hz). In practice, co_channel interferers at Δ5–7 Hz are the hardest
cases and were already borderline in the reference run (P15 was 80%, P16 was 85%).
The FP suppression benefit (−94%) is concrete and observed daily in operation.
The sensitivity loss at these two parts may be acceptable if on-air experience
confirms they are rare operating conditions.

**Implications:**
- G-A formally fails the 89% criterion (86.67% vs 89%)
- Requires explicit architect sign-off on the P15 (−30 pp) and P16 (−15 pp)
  per-part regressions
- The criterion in the handoff must be relaxed (to ≥ 85%, for example) or waived
- Update `MEMORY.md` D-001 section: co_channel_sweep headline drops from 92.14%
  to 86.67% as the new reference point

**Verdict:** Acceptable only if the architect judges the FP win clearly outweighs
the tight-offset sensitivity loss and is willing to formally accept the regression.

---

## 4. Recommended next step

**QA recommendation: Option B first, then A or C.**

Run a targeted K=8 and K=9 sweep on shim 20260028 (no rebuild needed — same binary,
different diagnostic configuration). Measure S5 FP/slot and S7 P15/P16 rates at
each point. This produces the data needed to decide between Option A and C, and
might reveal a genuinely better operating point that closes both problems cleanly.

If K=8 or K=9 gives P15/P16 ≥ 85% AND S5 FP ≤ 0.1/slot, that is a clear win.
If neither does, the trade-off between A and C becomes a product/policy decision.

---

## 5. References

| Reference | Description |
|---|---|
| `qa/rr-study/results/d009-k10-confirm-s7-clean/confirm_summary.md` | Full gate summary (G-A, G-B, root cause) |
| `qa/rr-study/results/d009-k10-confirm-s7-clean/report.md` | S7 per-part recovery report |
| `qa/rr-study/results/diag-pass1-sweep-2026-06-21/pass1_sweep.md` | K sweep trade-curve (K=1,3,5,7,10) |
| `dev-tasks/2026-06-21-d009-b2-escalation-captain.md` | B2 escalation that selected K=10 |
| `dev-tasks/2026-06-21-d009-k10-confirm-dev.md` | Confirmation gate handoff (developer instructions) |
| `dev-tasks/2026-06-20-d009-fp-filter-arch-design.md` | AD3 (S5 confidence bound), AD4 (S7 ≥89%) |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` | K_MIN_SCORE_PASS2 definition |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | FT8_SHIM_VERSION, changelog |
