# D-009 — Final Captain Decision: OSD False-Positive Trade (post-ablation)

**Date:** 2026-06-21  
**Author:** QA / Architect  
**Audience:** Captain (product owner)  
**Defect:** D-009 — OSD false-positive callsign manufacture in noise  
**Branch:** `fix/d009-fp-callsign-filter`  
**Previous escalation:** `2026-06-21-d009-b2-escalation-captain.md` (superseded)  
**Full investigation report:** `qa/rr-study/results/d009-investigation-2026-06-21/report.md`  

---

## 0. Status

The investigation is complete. Eight measurement sessions, four de-confounded configurations.
**No configuration satisfies all three acceptance criteria simultaneously.** The pre-committed
decision rule declares the trade irreducible and escalates to you.

This document presents **two clean options** with de-confounded numbers. There is no "round 9
of tuning" — the ablation exhausted the single-axis K and gating space. The decision is a
product posture choice: trust versus sensitivity.

---

## 1. The problem (unchanged from prior escalation)

OSD (shim 20260025) closed the D-001 co-channel decode gap: S7 went 51.6% → 80.2%,
`co_channel_sweep` reached 92.1% ≈ WSJT-X. The same mechanism also manufactures
structurally perfect FT8 messages from pure AWGN: ~0.7 false decodes per 15-second slot.
A logged false QSO could corrupt the operator's log, be submitted to a contest, or be
confirmed as a real contact.

---

## 2. What the investigation established

The investigation ran through 8 rounds, including:
- A definitive population study (R6): 205 FPs vs 92 genuine decodes — **identical nhard and sync distributions**. No cheap filter separates them.
- A 5-point K sweep: the pass-1 score floor (`K_MIN_SCORE_PASS2`) is the only lever that changes the FP rate meaningfully.
- A K=10 confirmation gate: K=10 suppresses FPs by 94% but regresses co_channel_sweep from 92.14% to 86.67% (G-A FAIL, P15/P16 drop 15–30 pp).
- A 2×2 ablation: isolated K floor from corr/nhard gates across 4 configs.

**Three confirmed findings from the ablation:**

1. **The K floor — not the corr/nhard gates — suppresses FPs.** FP/slot collapses at K=10 regardless of whether the gates are active. Six rounds of corr/nhard tuning achieved essentially nothing on the FP axis.

2. **The corr/nhard gates are not removable without destroying sweep recovery.** Removing gates at K=10 drops co_channel_sweep from 87% to 44%. The gates earn their keep on the sensitivity axis, even if they contribute nothing to FP suppression.

3. **The architect's hypothesis (K=10 with gates OFF was the answer) is refuted.** Config 2 (K=10, gates OFF) produced the worst co-channel recovery of all four configs.

---

## 3. The two options

### Option A — Trust-first: ship Config 3 (K=10, gates ON)

> Accept a co-channel sensitivity reduction in exchange for near-zero false positives.

| Metric | Value | Notes |
|---|---|---|
| S5 FP/slot | **0.042** | ~1 false decode per 24 slots ≈ WSJT-X parity |
| co_channel_sweep | **86.7%** | −5.5 pp vs 92.14% reference; P15 (Δ5 Hz) halved (50%), P16 (Δ7 Hz) reduced to 70% |
| co_channel P0–P2 | **34.3%** | −14 pp vs 48.57% pre-D-009 baseline; equal-SNR co-channel decoding meaningfully reduced |

**What changes in practice:**
- False callsigns in the decode log: essentially eliminated
- Tight-offset co-channel recovery (Δ5 Hz, Δ7 Hz): the hardest co-channel cases, now at 50% and 70% vs the pre-D-009 80% and 85%. These were already borderline before OSD.
- Equal-SNR co-channel recovery (the "heart of D-001"): falls to 34% vs 48% pre-D-009. OSD still helps here vs WSJT-X (0%), but gives back part of the D-001 gain.

**QA note:** To ship this, the co_channel ≥ 45% criterion must be **formally waived** or adjusted. The engineer cannot sign off on a criterion breach without explicit product approval. If you approve Option A, state which criterion is waived and why.

---

### Option B — Sensitivity-first: ship Config 4 (K=5, gates OFF)

> Accept a disclosed false-positive rate in exchange for maximum co-channel recovery.

| Metric | Value | Notes |
|---|---|---|
| S5 FP/slot | **0.700** | ~1 false decode per 1.4 slots — the original D-009 problem, minimally improved |
| co_channel_sweep | **75.0%** | −17 pp vs 92.14% reference; sweep below 89% gate |
| co_channel P0–P2 | **48.6%** | Best of all configs; near pre-D-009 baseline |

**What changes in practice:**
- The decoder is simpler (corr/nhard gates removed)
- Best co-channel recovery of any option
- The FP problem is essentially un-fixed: if you operate in noise or on a busy band with strong non-FT8 interference, false callsigns will appear regularly
- Requires explicit user disclosure that OSD decode results should be cross-checked

**QA note:** Option B requires a criterion change: the FP ≤ 0.10/slot gate would need to be formally waived, and the product's QSO log integrity would carry a documented caveat. This is within the Captain's authority to approve but cannot be waved silently.

---

## 4. What we need from you

Two decisions:

1. **Default posture: Trust-first (Option A) or Sensitivity-first (Option B)?**

2. **Criterion treatment:** For the chosen option, do you formally accept the
   criterion breach(es), or do you want the criteria revised? Specify:
   - Option A: waive co_channel ≥ 45% (accept 34.3%), accept sweep at 86.7% (2.3 pp below 89%)
   - Option B: waive FP ≤ 0.10/slot (accept 0.700), waive sweep ≥ 89% (accept 75%)

Once you provide posture + criterion treatment, the architect will issue the developer
handoff for the chosen config and QA will gate and merge. No further measurement runs
are needed — the data is complete.

---

## 5. References

| Document | Content |
|---|---|
| `qa/rr-study/results/d009-investigation-2026-06-21/report.md` | Full investigation report (8 rounds, all data, charts) |
| `qa/rr-study/results/d009-ablation-2026-06-21/ablation.md` | 2×2 factorial results and decision-rule evaluation |
| `qa/rr-study/results/d009-k10-confirm-s7-clean/confirm_summary.md` | K=10 gate failure detail (G-A, G-B) |
| `dev-tasks/2026-06-21-d009-ablation-decision-arch.md` | Architect decision ordering the ablation; pre-committed §3 rule |
| `dev-tasks/2026-06-21-d009-k10-gate-fail-arch.md` | QA gate-fail report to architect |
| `dev-tasks/2026-06-21-d009-b2-escalation-captain.md` | Prior Captain escalation (B2 branch, now superseded) |
