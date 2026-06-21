# D-009 K=10 Confirmation Gate — Summary

**Date:** 2026-06-21
**Branch:** fix/d009-fp-callsign-filter
**Shim:** 20260029 (`K_MIN_SCORE_PASS2 = 10`)
**Developer:** Claude (automated)
**Handoff:** dev-tasks/2026-06-21-d009-k10-confirm-dev.md

---

## Pre-merge gates (AC1–AC5)

| AC | Criterion | Result | Verdict |
|---|---|---|---|
| AC1 | `K_MIN_SCORE_PASS2 = 10`; all other 20260028 values unchanged | Confirmed in ft8_shim.c | ✅ PASS |
| AC2 | Version 20260029; `check_native_version.py` green | Binary reports 20260029 ✅ | ✅ PASS |
| AC5 | `dotnet build` 0/0; `dotnet test` all pass | 0 errors, 497 tests passed | ✅ PASS |

---

## Gate G-A — Full 21-part S7 co_channel_sweep

**Run directory:** `results/d009-k10-confirm-s7-clean`
**Shim:** 20260029 (K_MIN_SCORE_PASS2=10) | **Study K:** 5 trials/part
**Cycle window:** 2026-06-21T15:38:00Z – 16:10:45Z
**Note:** First run (15:38–15:29) was contaminated by simultaneous S5 playback
(both routes through VB-CABLE; OS mixer combined streams). This is the clean
sequential re-run with no simultaneous S5 playback.

### Recovery by family

| Overlap family | Reference (d70aad5, K=1, K=10 trials) | K=10 (this run, K=5 trials) | Δ |
|---|---|---|---|
| co_channel | 48.57% | 34.29% | −14.3 pp |
| co_channel_sweep | 92.14% | **86.67%** | **−5.47 pp** |
| near_collision | 91.00% | 84.00% | −7.0 pp |
| time_freq | 93.33% | 100.00% | +6.67 pp |
| capture | 63.75% | 60.00% | −3.75 pp |
| **all** | **80.22%** | **74.42%** | −5.80 pp |

### co_channel_sweep per-part detail (P15–P20)

| Part | Condition | Reference (d70aad5) | K=10 (this run) | Δ |
|---|---|---|---|---|
| P15 | offset-sweep Δ5 Hz | 16/20 = 80% | 5/10 = 50% | **−30 pp ⚠️** |
| P16 | offset-sweep Δ7 Hz | 34/40 = 85% | 7/10 = 70% | **−15 pp ⚠️** |
| P17 | offset-sweep Δ10 Hz | 20/20 = 100% | 10/10 = 100% | 0 pp |
| P18 | offset-sweep Δ15 Hz | 20/20 = 100% | 10/10 = 100% | 0 pp |
| P19 | offset-sweep Δ8 Hz | 19/20 = 95% | 10/10 = 100% | +5 pp |
| P20 | offset-sweep Δ9 Hz | 20/20 = 100% | 10/10 = 100% | 0 pp |
| **Total** | | **129/140 = 92.14%** | **52/60 = 86.67%** | **−5.47 pp** |

### Verdict

**AC3 (G-A): FAIL — co_channel_sweep 86.67% < 89% criterion.**

Per-part flags (> 5pp regression):
- **P15 (Δ5 Hz): −30 pp** (50% vs 80% reference) — FAIL
- **P16 (Δ7 Hz): −15 pp** (70% vs 85% reference) — FAIL

### Root-cause assessment

After pass-0 decodes one co_channel signal and applies spectrogram suppression, the
residual partner at Δ5–7 Hz has degraded sync-score alignment. At `K_MIN_SCORE_PASS2=10`
(= K_MIN_SCORE, the pass-0 floor), these residual candidates are rejected from pass-1.
At K=1 (old default), they are admitted and decoded via OSD.

The tight-offset cases (Δ5 Hz, Δ7 Hz) are the most damage-prone under spectrogram SIC
because the suppressed tiles overlap heavily with the residual signal's tiles. The
higher K cuts FP rate but also cuts the residual signal's admission to pass-1.

This is a **genuine regression, not statistical noise.** Both P15 and P16 are 15–30 pp
below reference — well outside the ±5 pp noise band for K=5 vs K=10 study trials.

---

## Gate G-B — Widened S5 FP rate

**Run directory:** `results/d009-k10-confirm-s5-clean`
**Shim:** 20260029 (K_MIN_SCORE_PASS2=10) | **Slots:** 120 | **Sequential, clean**
**Cycle window:** 2026-06-21T16:11:30Z – 16:44:45Z (no S7 overlap)

### FP count

| Metric | Value |
|---|---|
| Total slots | 120 |
| FP decodes | **5** |
| FP rate | **0.042 FP/slot** |
| 95% upper bound (Wilson) | ~9.4% per slot |
| vs K=1 baseline (0.675/slot) | **−94%** |
| vs sweep K=10 measurement | **0.042** (identical ✓) |

### Verdict

Per AD3: a non-zero rate is "report-and-discuss", not an automatic pass.
**AC4 (G-B): MARGINAL** — 5/120 FPs = 0.042/slot; consistent with sweep; non-zero
but small (94% reduction from baseline). Would be acceptable if G-A passed.

Note: AC7 (NFR-021) — the 5 FP messages are OSD CRC coincidences on pure AWGN;
the ALL.TXT is NOT committed (text may contain randomly-structured callsign strings).

Gate G-A failure makes G-B academic for this merge decision — **K=10 does not merge
regardless of G-B outcome.**

---

## Overall outcome: DO NOT MERGE

**Reason:** Gate G-A fails. co_channel_sweep 86.67% < 89% criterion. P15 and P16
regress > 5 pp vs the d70aad5 baseline (−30 pp and −15 pp respectively).

**Per handoff §2 Action 5:**
> If G-A fails (S7 headline regresses) → K=10 trades too much sensitivity on the
> easy parts. Stop, report. The fallback operating point is K=5.

**Recommendations for architect:**

1. **Fallback K=5** — sweep showed K=5 peaks co_channel P0–P2 recovery (45.7% vs
   37.1% for K=10) and presumably preserves tighter-offset parts (P15/P16). FP
   reduction only 21% vs baseline (0.533 FP/slot), which may be insufficient.

2. **Explore K=8 or K=9** — the FP step-change between K=7 (0.558) and K=10 (0.042)
   is steep. No sweep data exists between 7 and 10; a targeted K=8 or K=9 point
   might cut FP meaningfully while preserving P15/P16 sensitivity.

3. **Architectural alternative** — apply K_MIN_SCORE_PASS2=10 only when the pass-0
   suppressed tile overlap with the residual is below a threshold, preserving
   tight-offset residuals. This is a more complex native change.

4. **Accept the regression** (not recommended) — 86.67% vs 92.14% is a 5.5 pp drop.
   If FP reduction (94%) outweighs the tight-offset sensitivity loss, the architect
   may choose to ship and accept the co_channel_sweep regression as a known trade-off.
   This requires explicit sign-off on the P15/P16 regressions.

---

## Files committed (source changes only — no merge)

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — K_MIN_SCORE_PASS2 1→10, changelog entry
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — version 20260028→20260029, changelog entry
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — ExpectedShimVersion 20260028→20260029
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` — rebuilt at shim 20260029
