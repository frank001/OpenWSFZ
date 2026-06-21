# D-009 — Architect Decision: Gate-Isolation Ablation (responds to K=10 gate failure)

**Date:** 2026-06-21
**Author:** Architect
**Responds to:** `dev-tasks/2026-06-21-d009-k10-gate-fail-arch.md` (QA gate-fail handoff)
**Defect:** D-009 — OSD false-positive manufacture in noise
**Branch:** `fix/d009-fp-callsign-filter`

---

## 1. Decision

**K=10 does not merge** — Gate G-A correctly failed (co_channel_sweep 86.67% < 89%).
The confirmation gate did its job: it caught a regression the pass-1 sweep's hard
P0–P2 subset never measured.

**QA's three options (A: fall back to K=5; B: probe K=8/9; C: accept K=10) are all
declined for now.** They each pick a point on a curve we have now confirmed — three
independent times (R6 histograms, the sweep, this gate) — to be an **inseparable**
single-axis trade. Probing more K values (Option B) cannot escape it: noise FPs and
genuine tight-offset residuals both occupy sync 7–9, so K=8/9 only land at
intermediate points on the same curve.

**Instead: run one bounded ablation that isolates what each gate actually buys**,
because the existing data exposes a confound that makes the current K debate
premature. Handoff: `dev-tasks/2026-06-21-d009-ablation-dev.md`.

---

## 2. Why the gate-fail comparison is confounded

QA attributes the co-channel regressions to K=10. The G-A comparison changes **two
variables at once**:

- **"K=1 reference" = shim 20260025** (`d70aad5`) — OSD merge, **no D-009 gating**.
- **"K=10" = shim 20260029** — **full D-009 gating** (corr 0.10 + nhard 60 + text
  Rules A/B/C) **plus** the K floor change.

De-confounding with the sweep (which holds gating fixed at 20260028, varies only K)
on the **co_channel** (P0–P2 equal-stack) family:

| State | Shim | K | co_channel |
|---|---|---|---|
| pre-D-009 baseline | 20260025 | 1 | **48.57%** |
| full D-009 gating | 20260028 | 1 | **28.6%** |
| full D-009 gating | 20260029 | 10 | 37.1% |

**The D-009 gating stack itself cost ~20 pp on the core equal-SNR co-channel family
(48.6% → 28.6%) at K=1 — before any floor change.** Raising K to 10 then *recovered*
+8.5 pp. So on this family K=10 is not the villain; the corr/nhard/text gating is.

We also have a **measurement gap**: co_channel_sweep (P15–P20) was never run at
20260028/K=1. So the −5.5 pp sweep regression cannot be cleanly assigned to K versus
gating. The headline number QA is asking us to act on is not isolated.

## 3. The buried finding: the K-floor does the FP work; corr/nhard may be all cost

From the sweep, with nhard-60 + corr-0.10 + text rules **all active**, FP/slot at
K=1 is still **0.675**. FP only collapses (→0.042) when the **K floor** reaches 10.

> **The pass-1 score floor — not the corr or nhard gates — is what actually
> suppresses false positives.** corr/nhard may be contributing little to FP control
> while costing ~20 pp of genuine co-channel recovery.

If true, six rounds of corr/nhard tuning bought almost nothing on the axis they were
built for and damaged the one that matters. The ablation tests exactly this, and
opens the possibility of **deleting** corr/nhard (simpler decoder, recovered
sensitivity) rather than tuning them further.

## 4. On Option C specifically

Weaker than QA frames it. They justify accepting K=10 as "only the two tightest
offsets regress," but the co_channel **equal-SNR** family also fell to 34.3% — the
heart of D-001, not an edge case — and that drop is mostly the *gating stack*, not K.
Accepting 20260029 would ship a config that gives back D-001's core gain for FP
suppression the K-floor can deliver on its own. Do not accept C until the ablation
shows the gating earns its keep.

---

## 5. The ablation (replaces Options A/B/C)

A 2×-lever factorial isolating **K floor** from **statistical gates** (corr+nhard).
Text Rules A/B/C (C# layer, zero-FN structural) stay ON in all configs.

| Config | `K_MIN_SCORE_PASS2` | corr+nhard gates | Question it answers |
|---|---|---|---|
| 1 | 1 | OFF | OSD's true co-channel ceiling + raw FP rate |
| 2 | 10 | OFF | **does the floor alone give low FP AND keep co-channel?** ← key hypothesis |
| 3 | 10 | ON | = current 20260029 (reference; already measured) |
| 4 | 5 | OFF | sensitivity-leaning floor without the gating tax |

Gates OFF = `OSD_NHARD_MAX 174` + `OSD_CORR_THRESHOLD -1.1f` (both become no-ops; no
logic change). Each config measured on **full 21-part S7** (report **both**
co_channel and co_channel_sweep families) **+ widened S5** (≥100 slots) FP rate.

### Pre-committed decision rule (no post-hoc goalpost moving)

- **SHIP** the simplest config (fewest active gates, then lowest K) that satisfies
  **all three**:
  - co_channel_sweep ≥ **89%**
  - co_channel (P0–P2) ≥ **45%** (within ~3 pp of the pre-D-009 48.57%)
  - S5 FP ≤ **0.10 /slot**
- **Strong prior:** Config 2 wins — the floor carries FP, dropping corr/nhard
  recovers co-channel.
- **If no config clears all three → the trade is irreducible.** Escalate to the
  Captain as a clean sensitivity-vs-trust decision with **de-confounded** per-config
  numbers (Config 4 = sensitivity end; Config 2 or 3 = trust end). No further K
  probing.

---

## 6. Why this is the right move, not Round 8 of tuning

- It is **one** bounded run (4 builds, already-scripted S7/S5 harness), not an
  open-ended search.
- It **isolates a confound** that currently makes every option a guess.
- It can **remove** code (corr/nhard) rather than add another tuned constant —
  reducing the decoder's surface, not growing it.
- It ends with a **pre-committed rule**: the data ships a config or declares the
  trade irreducible and hands the Captain clean numbers. Either way D-009 closes
  after this round.

---

## 7. References

- `dev-tasks/2026-06-21-d009-k10-gate-fail-arch.md` — QA gate-fail handoff (Options A/B/C)
- `dev-tasks/2026-06-21-d009-ablation-dev.md` — developer handoff for this ablation
- `qa/rr-study/results/d009-k10-confirm-s7-clean/` — G-A/G-B confirmation results (Config 3 reference)
- `qa/rr-study/results/diag-pass1-sweep-2026-06-21/pass1_sweep.md` — K sweep (gating fixed at 20260028)
- `qa/rr-study/results/diag-nhard-2026-06-20/nhard_observations.md` — R6 sync/nhard overlap (inseparability)
- `native/ft8_lib_build/patched/ft8/decode.c` — `OSD_CORR_THRESHOLD`/`OSD_NHARD_MAX` (~55–56), OSD gate sites (~640, ~823)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `K_MIN_SCORE_PASS2` (~385)
- MEMORY: D-001 reference (`d70aad5`, 20260025); D-009 round history
