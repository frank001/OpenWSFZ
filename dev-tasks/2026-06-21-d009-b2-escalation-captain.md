# D-009 B2 Escalation — Product Trade-off Decision (for the Captain)

**Date:** 2026-06-21
**Author:** Architect
**Audience:** Captain (product owner)
**Defect:** D-009 — OSD false-positive callsign manufacture in noise
**Triggered by:** R6 nhard/sync diagnostic — Branch **B2** (neither axis separates)
**Decision needed:** product trade-off, not an engineering choice. See §4.

---

## 0. UPDATE 2026-06-21 (post pass-1 sweep) — the trade is far better than feared

The §4a measurement has run
(`qa/rr-study/results/diag-pass1-sweep-2026-06-21/pass1_sweep.md`). It **substantially
softens** the trade-off framed below. Headline:

| `K_MIN_SCORE_PASS2` | FP/slot (D-009 cost) | S7 co-channel (D-001 benefit) |
|---|---|---|
| **1 — shipped today** | 0.675 | 28.6% |
| 5 | 0.533 | 45.7% |
| **10** | **0.042 (−94%)** | 37.1% (**+8.5pp vs today**) |

**Two findings overturn the "agonising dial" framing:**

1. **The currently shipped setting (K=1) is the worst point on the curve.** K=10
   beats it on *both* axes — 94% fewer false decodes **and** higher co-channel
   recovery. We should move off K=1 regardless of posture.
2. **A near-trust-first FP rate (0.04/slot ≈ WSJT-X) is achievable at K=10 without
   giving back the D-001 gain.** The sensitivity it gives up versus the K=5 peak
   (37.1% vs 45.7%) is a 3-decode difference on 35 observations — within measurement
   noise, i.e. possibly not real.

**Revised recommendation: adopt K=10**, pending one confirmation run (full 21-part
S7 + widened S5) before merge — because the absolute S7 numbers above are the *hard*
P0–P2 subset measured post-gating, **not** the 92.1% co_channel_sweep headline, and
the K=5/K=10 sensitivity gap is statistically thin. The confirmation handoff is
`dev-tasks/2026-06-21-d009-k10-confirm-dev.md`.

The decision below is no longer "trust vs sensitivity"; it is **"approve K=10 +
confirmation run."** The original analysis is retained for the record.

> Note: the "~5 false decodes per slot" figure in §1/§3 below was the *raw OSD-CRC*
> count (and double-counted across both OSD sites). The user-visible output rate,
> after text Rules A/B/C, is ~0.7/slot at K=1 → 0.04/slot at K=10.

---

## 1. One-paragraph summary

OSD (added in shim 20260025) closed most of the D-001 co-channel decode gap —
S7 went 51.6% → 80.2%, and `co_channel_sweep` reached 92.1%, near WSJT-X's 92.9%.
The same OSD path also manufactures **structurally valid false callsigns from pure
noise** (D-009): ~5 false decodes per 15-second slot of pure AWGN. Six rounds of
filtering (R1–R6) and a definitive measurement study have now established that
**the false positives and the genuine co-channel decodes are the same kind of
event and cannot be told apart by any cheap signal-level test.** The remaining
choices all trade decode sensitivity against false-decode rate. That trade is a
product decision and is the reason this is on your desk.

---

## 2. How we got here (the short version)

| Round | Approach | Outcome |
|---|---|---|
| R1–R4 | Tune the `corr/norm` output gate | Ceilinged: 0 FP needs ≥0.40, but that regresses S7 co-channel (needs ≤0.35). No single value works. |
| R5 | Add `nhard` (Hamming-distance) output gate | Shipped an **uncalibrated** threshold (60) with a false calibration claim; failed S5 noise gate immediately. |
| R6 diag | Measure nhard **and** sync on FP vs genuine populations | **Branch B2:** neither separates. The cheap-fix avenue is exhausted by measurement. |

Full data: `qa/rr-study/results/diag-nhard-2026-06-20/nhard_observations.md`.

---

## 3. Why no cheap fix exists (the root finding)

The R6 study measured 205 false positives (pure AWGN) against 92 genuine
co-channel decodes. The two populations are **nearly identical**:

| Axis | False positives | Genuine decodes |
|---|---|---|
| nhard (codeword vs channel) | mean 51.8, median 52 | mean 51.4, median 52 |
| sync (candidate quality) | mean 8.1, median 8 | mean 8.6, median 8 |

The architectural reason: both arise from the **same decode pass** — the
"spectrogram-suppressed" pass-1 (SIC residual) that lets in very weak candidates
(`min_score = 1`) so it can dig co-channel signals out of a suppressed waterfall.
When that pass runs blind OSD, it digs out genuine weak signals **and** forces
random noise to valid-looking codewords with equal facility. There is no
signal-level feature that distinguishes "weak real signal we rescued" from "noise
we hallucinated," because at that layer they are the same operation. Text
filtering is also exhausted — the residual FPs are structurally perfect
`CALL CALL GRID` messages indistinguishable from real traffic.

**Plain terms:** the thing that makes OpenWSFZ good at hard co-channel decodes is
*exactly* the thing that makes it invent callsigns in noise. We cannot keep all of
one and none of the other for free.

---

## 4. The decision

This is a position on a dial between two products:

- **Sensitivity-first** — best-in-class co-channel/weak-signal decoding (the D-001
  win), at the cost of a measurable false-decode rate in low-signal / noise
  conditions. Risk: a logged QSO with a station that never transmitted.
- **Trust-first** — near-zero false decodes (WSJT-X-like behaviour), at the cost
  of giving back part of the co-channel gain OSD was introduced to deliver.

For an amateur-radio logging product, a **false QSO entry is a serious defect** —
it corrupts the log and could be transmitted/confirmed. My architectural lean is
**trust-first by default, with sensitivity as an opt-in**, but the weighting is
yours.

### 4a. Recommended next step before you commit (cheap, ~½ day)

Do **not** pick a heavyweight implementation blind. The pass-1 finding gives us a
single tunable — `K_MIN_SCORE_PASS2` (currently 1) — that moves us continuously
along the dial. I've handed the developer a sweep
(`2026-06-21-d009-pass1-sweep-dev.md`) that measures **both** the S5 false-positive
rate **and** the S7 `co_channel_sweep` rate at several pass-1 settings. That
produces the actual trade curve — numbers, not intuition — so you choose a point
on the dial with the cost of each side in front of you. No ABI change, no
production commit; it's a measurement.

### 4b. The implementation menu (chosen *after* the sweep)

| Option | What it does | Keeps D-001 gain? | FP outcome | Cost |
|---|---|---|---|---|
| **A. Tune pass-1 `min_score`** | Move along the dial via one constant | Partially (tunable) | Reduced, not zero | Trivial (`#define`) |
| **B. Blind OSD off; AP-OSD on** | OSD fires only with QSO context (pass-0 AP); blind co-channel digging disabled | QSO-directed yes; blind no | Near-zero | Low |
| **C. ABI origin flag + strict OSD text profile** | Tag OSD decodes, filter them harder | Yes | Cuts Cat A–D; **leaves Cat E** → won't reach 0 | Medium (ABI break); **likely insufficient** |
| **D. Reduce OSD depth/iterations** | Globally less aggressive OSD | Partially | Reduced | Low; blunt |

My read: **C is the weakest** (cannot reach S5 FP = 0 because the residuals are
structurally perfect). The real contest is **A** (accept a documented, tuned FP
rate for the sensitivity) vs **B** (keep only QSO-directed OSD, accept loss of
*blind* co-channel reach). The sweep in 4a tells us how much sensitivity A costs
at each FP level, and how much B gives back — which is the information you need to
choose between them.

---

## 5. What I need from you

1. **Default posture:** trust-first or sensitivity-first? (Sets where on the dial
   we aim.)
2. **Approve the pass-1 sweep** (4a) as the next action — it's measurement only and
   makes the rest of the decision data-driven.
3. After the sweep returns, **pick the implementation** (A/B/D, or A+B combined)
   from the trade curve.

Nothing is implemented or merged until you've set the posture and seen the curve.

---

## 6. References

- `qa/rr-study/results/diag-nhard-2026-06-20/nhard_observations.md` — R6 study, B2 verdict
- `dev-tasks/2026-06-20-d009-r6-decision-fork.md` — pre-committed A/B1/B2 fork (this is the B2 leaf)
- `dev-tasks/2026-06-21-d009-pass1-sweep-dev.md` — the §4a measurement handoff
- `dev-tasks/2026-06-20-d009-fp-filter-arch-design.md` / `-arch-review.md` — Categories A–E, calibration ceiling
- GitHub Issue #3 (D-001) — the co-channel gain OSD was introduced to deliver
- MEMORY: D-001 history (S7 51.6%→80.2%; co_channel_sweep 92.1% vs WSJT-X 92.9%)
