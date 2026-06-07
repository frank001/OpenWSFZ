# QA Findings — D001 Real-Signal Assessment — `fix/d001-pcm-sic`

**Raised:** 2026-06-07
**Raised by:** QA
**Status:** Partial — baseline decode pending (action items below)
**Related defect:** D-001 (frank001/OpenWSFZ#3)
**Session corpus:** `D001-pcm-sic_items/` (git-ignored — NFR-021)

---

## Background

`fix/d001-pcm-sic` implemented PCM-domain successive interference cancellation (SIC)
in the native shim (`FT8_SHIM_VERSION` 20260002 → 20260003): three decode passes
(previously two), with carrier-estimation-based waveform synthesis and subtraction
between passes. The branch was reviewed, merged to `main` at commit `497996f`, and
an R&R study run was completed.

The synthetic S7 scenario (the R&R study's co-channel test) showed **no net improvement**
(46.24% → 46.24% overall). To determine whether the fix has a meaningful effect on
real propagation conditions, a live session (`D001-pcm-sic_items/`) was collected and
partially analysed before a stack-overflow crash (P1 bug — fixed separately on
`fix/native-stack-overflow-pcm-residual`) interrupted the run.

This document records the partial findings and identifies the remaining action needed
to complete the assessment.

---

## RS-001 — Real-signal recall: fix version (partial, baseline pending)

### Session details

| Field | Value |
|---|---|
| Collection date | 2026-06-07 |
| Duration | 11:55:45 → 12:41:45 UTC (46 min, 185 × 15-second slots) |
| Frequency | 14.074 MHz (20 m FT8) |
| OpenWSFZ version | `fix/d001-pcm-sic` tip (`15b108b`) merged to `main` at `497996f` |
| Shim version | 20260003 (PCM-domain SIC, K_MAX_PASSES = 3) |
| Corpus path | `D001-pcm-sic_items/save/` (git-ignored, NFR-021) |
| WSJT-X ALL.TXT | `D001-pcm-sic_items/WSJT-X ALL.TXT` (git-ignored) |
| OpenWSFZ ALL.TXT | `D001-pcm-sic_items/OpenWSFZ ALL.TXT` (git-ignored) |

### Decode summary

| Metric | Value |
|---|---|
| WSJT-X total slots | 185 |
| OpenWSFZ slots with data | 176 (9 lost to stack-overflow crash — now fixed) |
| WSJT-X decodes in common slots | 5,493 |
| OpenWSFZ decodes in common slots | 3,192 |
| Exact message matches | 3,006 |
| **OpenWSFZ recall of WSJT-X** | **54.7%** |
| OpenWSFZ-only decodes (not in WSJT-X) | 186 |

### Interpretation

**54.7% recall** is the fix version's real-signal figure over 176 overlapping slots.

The **186 OpenWSFZ-only decodes** are candidates for SIC-pass bonus recoveries —
messages the second or third decode pass extracted from the residual PCM after the
first pass's signals were subtracted. Without an independent oracle these cannot be
distinguished from false positives; however their existence is consistent with the
PCM-SIC design goal.

**This figure cannot yet be compared to the pre-fix baseline** because no equivalent
live session was run under the same propagation conditions using shim 20260002. The
`batch_decode.py` tool (added in the same commit as this document) closes that gap —
see the action items below.

---

## RS-002 — Synthetic S7 results (for context)

The R&R study run at `497996f` (PCM-SIC fix merged to `main`) produced the
following S7 results against the pre-fix baseline run at `6bab388`:

| Family | Pre-fix (`6bab388`) | Fix (`497996f`) | Δ |
|---|---|---|---|
| co_channel | 4.76% | 0.00% | −4.76% |
| near_collision | 76.67% | 83.33% | +6.66% |
| time_freq | 38.89% | 33.33% | −5.56% |
| capture | 50.00% | 50.00% | 0% |
| **all** | **46.24%** | **46.24%** | **0%** |

### Per-part detail

| Part | Family | Condition | Pre-fix WSJT-X | Pre-fix OpenWSFZ | Fix WSJT-X | Fix OpenWSFZ | Δ OpenWSFZ |
|---|---|---|---|---|---|---|---|
| P0 | co_channel | 2-stack, equal 0 dB | 4/6 | 0/6 | 4/6 | 0/6 | 0 |
| P1 | co_channel | 2-stack, equal −5 dB | 4/6 | 1/6 | 4/6 | 0/6 | −1 |
| P2 | co_channel | 3-stack, equal 0 dB | 0/9 | 0/9 | 0/9 | 0/9 | 0 |
| P3 | near_collision | delta 3 Hz | 6/6 | 6/6 | 6/6 | 6/6 | 0 |
| P4 | near_collision | delta 6 Hz | 6/6 | 2/6 | 6/6 | 2/6 | 0 |
| P5 | near_collision | delta 12 Hz | 6/6 | 3/6 | 4/6 | 5/6 | +2 |
| P6 | near_collision | delta 25 Hz | 6/6 | 6/6 | 6/6 | 6/6 | 0 |
| P7 | near_collision | delta 50 Hz | 6/6 | 6/6 | 6/6 | 6/6 | 0 |
| P8 | time_freq | co-freq, dt 0.5 s | 6/6 | 0/6 | 6/6 | 0/6 | 0 |
| P9 | time_freq | co-freq, dt 1.0 s | 6/6 | 3/6 | 6/6 | 2/6 | −1 |
| P10 | time_freq | co-freq, dt 2.0 s | 6/6 | 4/6 | 6/6 | 4/6 | 0 |
| P11 | capture | 0 / −3 dB | 4/6 | 3/6 | 4/6 | 3/6 | 0 |
| P12 | capture | 0 / −6 dB | 4/6 | 3/6 | 5/6 | 3/6 | 0 |
| P13 | capture | 0 / −10 dB | 4/6 | 3/6 | 4/6 | 3/6 | 0 |
| P14 | capture | +3 / −10 dB | 4/6 | 3/6 | 4/6 | 3/6 | 0 |

### Interpretation

With only 6 trials per part, the per-part variance is high (one decode = ±16.7 pp).
The net-zero overall result and mixed sub-family movements (−1, +2, −1 across 15
parts) are within the noise of the study design. No statistically meaningful
improvement or regression can be claimed from the synthetic data alone.

The co_channel sub-family (P0, P1, P2) remains at or near 0% for OpenWSFZ regardless
of the fix — consistent with the known limitation that the synthetic test injects
equal-SNR co-channel signals, where SIC convergence is theoretically constrained even
with PCM-domain subtraction.

---

## RS-003 — Baseline comparison result

**Run date:** 2026-06-07
**Method:** `batch_decode.py` with pre-fix DLL (`879ec46`, shim 20260002) over the same
185 WAV files captured during the live session. One slot (260607_123945) crashed
in the pre-fix DLL on a specific audio frame (unrelated latent fault in 20260002);
184 of 185 baseline slots completed. Full comparison report:
`qa/rr-study/QA-FINDINGS-D001-real-signal-comparison.md`

### Three-way comparison (176 slots common to all three logs)

| Metric | Baseline (20260002) | Fix (20260003) | Δ |
|---|---|---|---|
| WSJT-X decodes | 5,493 | 5,493 | — |
| Matched (TP) | 3,010 | 3,006 | −4 |
| **Recall of WSJT-X** | **54.8%** | **54.7%** | **−0.1 pp** |
| Fix-only TPs (SIC found, baseline missed, WSJT-X confirms) | — | 106 | — |
| Decoder-only (not in WSJT-X) | 243 | 186 | −57 |

### Verdict

**−0.1 pp** — within the verdict band "No improvement within measurement noise."

Per the pre-agreed criteria:

| Recall Δ (pp) | QA verdict |
|---|---|
| ≥ +5 pp | Genuine improvement — D-001 can be downgraded |
| +1 to +4 pp | Marginal — D-001 remains Open |
| **−4 to 0 pp** | **No improvement — D-001 remains Open** ← **this result** |
| ≤ −5 pp | Regression |

The PCM-SIC fix (shim 20260003, three-pass decode with carrier subtraction) produced
**no measurable improvement** to real-signal decode rate on 20 m FT8 off-air audio.
This is consistent with the synthetic S7 finding (46.24% → 46.24%).

The 106 fix-only TPs indicate the extra pass *is* finding some additional signals that
WSJT-X confirms, but these are offset by an approximately equal number of signals the
baseline found that the fix did not. The net effect on recall is zero.

The 57-fewer decoder-only decodes (186 vs 243) suggests the fix may slightly reduce
false positives, but this is a secondary metric and the difference is small.

### D-001 status

**D-001 remains Open.** The PCM-SIC approach as implemented did not close the gap.
The fundamental limitation is likely that the synthetic carrier estimation in the shim
is insufficiently precise for coherent subtraction of real-world signals with Doppler
spread, multipath, and amplitude flutter. See GitHub issue frank001/OpenWSFZ#3.

---

## Summary

| ID | Status | Description |
|---|---|---|
| RS-001 | **Complete** | Fix-version recall 54.7% (176 slots) |
| RS-002 | **No net improvement** | Synthetic S7: 46.24% both runs |
| RS-003 | **No net improvement** | Real-signal Δ = −0.1 pp; D-001 remains Open |
