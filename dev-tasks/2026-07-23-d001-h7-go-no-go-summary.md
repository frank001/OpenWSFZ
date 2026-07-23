# D-001 — H7 (MMSE Joint Demodulation) Go/No-Go: Summary for the Captain

**Date:** 2026-07-23
**Author:** QA
**Audience:** Captain (Architect cc'd)
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Supersedes/updates:** `dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md` (the original scoping
decision, which recommended **Option B: resolve the caveat first**)
**Status:** All three groundwork passes Option B called for are now complete and merged to
`main`. This document synthesises them into a single decision brief. **This is a decision
point, not a handoff — no code, no OpenSpec proposal, no H7 commitment is made here.**

---

## 0. Executive summary

On 2026-07-07 the Architect-facing scoping document concluded that the evidentiary gate for
"is H6+OSD insufficient" was satisfied (three independent live sessions, ~40 hours combined,
stable 23–32% recall at < −15 dB with no directional trend), but flagged one open caveat before
committing 3–6 months to H7: **is the observed gap actually co-channel-attributable** — the
specific failure mode MMSE joint demodulation targets — or partly something else? QA
recommended **Option B: resolve the caveat first**, using existing retained logs, before the
Captain decided between commissioning H7 (Option A) or continuing to defer (Option C).

That caveat-resolution work is now done, in three parts:

| Pass | PR (merged) | One-line finding |
|---|---|---|
| Co-channel attribution (Option B) | pre-existing, `b4bdf88` | F = 29.6% (mixed, straddles the 0.30 threshold) |
| Δf histogram + extended sweep | #102 | Partial-class capture-effect (40.3%) *exceeds* Tight's (36.4%) — F′ (75.5%) is a more honest ceiling read than the raw F |
| Runtime-parameter recall/FP sweep | #101 | **0 of 45 operating points recover any recall** — the cheap/zero-rebuild alternative is exhausted, not merely untried |
| Isolated-miss pipeline diagnosis | #103 | **32.2% (44.4% in the higher-SNR stratum) of "Isolated" misses decode on replay** — points at a live-path/gain-staging issue, independent of and cheaper than H7 |

**Net effect on the H7 decision itself: F is still mixed, still nowhere near the 0.60
"recommend H7" threshold, and never was — this work does not manufacture a clean go/no-go
where the data doesn't support one.** What it *does* deliver is (a) a firmer read that the true
co-channel fraction likely sits above the raw 29.6%, (b) proof that no cheap tuning alternative
exists for the co-channel portion, and (c) a **new, cheaper, independent lead** — the live-path
finding — that did not exist when the original scoping document was written and arguably
deserves attention before or alongside the H7 decision itself.

---

## 1. Recap: the gate and the caveat (from the 2026-07-07 scoping doc)

- **The gate** ("is H6+OSD insufficient in real on-air use?") was already satisfied: three live
  endurance sessions (06-22, 07-06, 07-07, shims 20260029/31/33) all showed a stable, structural
  23–32% recall at < −15 dB with no improvement from intervening work (D-009, D-012, F-005).
- **The caveat:** H7 is *specifically* a co-channel/multi-signal remedy. The endurance figure is
  a general SNR-stratified recall number that does not distinguish "missed because of a nearby
  interferer" (H7's target) from "missed because it was simply weak and isolated" (a different,
  sensitivity-class problem H7 would not fix).
- **QA's 2026-07-07 recommendation: Option B** — resolve the caveat via bounded log-analysis
  before scoping H7, rather than committing 3–6 months against a possibly-mis-attributed root
  cause.

---

## 2. What the three completed passes actually found

### 2.1 Co-channel-attributable fraction (F) — the caveat's direct answer

Combined across all three sessions, low-SNR bands `< −15 dB` and `−15..−10 dB`, 33,620 pooled
WSJT-X-only misses classified by nearest same-slot-neighbour Δf:

| Class | Count | Share |
|---|---:|---:|
| Tight (≤ 15 Hz — H7's clean target) | 9,956 | 29.6% |
| Partial (15–50 Hz) | 15,428 | 45.9% |
| Isolated (no neighbour ≤ 50 Hz — not H7's target) | 8,236 | 24.5% |

**F = 29.6%**, straddling the pre-committed 0.30 "do not scope" threshold both in the window
sweep (22.1%–44.7% across 10–25 Hz cutoffs) and per-session (28.0% / 32.0% / 29.0%) — this is
why the original pass called it **mixed**, not a clean "do not scope." **F never approaches the
0.60 "recommend H7" threshold at any cutoff tested, including the extended sweep to 45 Hz.**

The follow-up histogram pass (PR #102) added resolution *underneath* this same F, without
reopening it, and found something the coarse three-bucket view couldn't show: the
**Partial-class capture-effect signature (40.3% of Partial misses show a ≥10 dB stronger
same-slot neighbour) is higher than Tight's own (36.4%)**, consistently across all three
sessions. Per that pass's own pre-registered reading, a *falling* capture-effect fraction from
Tight to Partial would have been the physically boring default (rejection gets easier with
distance); what was found instead — flat-or-rising — is evidence the same mechanism extends
past the 15 Hz cutoff. That argues **F′ (75.5%, the Tight+Partial optimistic bound) is closer
to the honest picture of how much of the gap plausibly shares Tight's mechanism than the raw
29.6% F conveys alone.**

**What this changes, and what it doesn't:** it does not move F itself, and the Captain-locked
0.30/0.60 thresholds were never reopened. But it firms up the "mixed" read in one direction:
the true co-channel-attributable fraction is probably meaningfully above 29.6%, not below it.
*(Illustrative only, not a measured figure: scaling the 18.39 pp Tight-only recoverable-recall
ceiling — Section 2.3 below — by F′/F instead of using F alone would suggest a ceiling
approaching ~47 pp if the Partial bucket's mechanism is genuinely the same as Tight's. This is
extrapolation, not a direct measurement, and should be read with real caution.)*

### 2.2 Is there a cheap alternative to H7? — No, and now provably not

The runtime-parameter sweep (PR #101) tested every combination of the three decode knobs
OpenWSFZ already exposes without a rebuild (`k_min_score_pass2` × `osd_corr_threshold` ×
`osd_nhard_max`, 45 points, ~106,000 offline decodes against the real 07-07 recall corpus and
the D-009 synthetic FP scenarios):

- **Zero of 45 points beat the shipped baseline.** The recall surface is flat to within 0.25 pp
  and already peaks at the shipped `k=10`; the two OSD gates move only false positives, never a
  single additional true low-SNR decode.
- Lowering candidate-admission (`k`) all the way to 5 recovered **≈0%** of that corpus's own
  Isolated-class misses (2 of 2,131) — empirically refuting candidate-generation as the
  bottleneck for the Isolated class specifically, on this data.

**This means the runtime lever is not merely unexplored — it is exhausted.** Whatever remains
of the D-001 gap after this sweep is, by elimination, a compile-time (native shim rebuild,
out of scope here) or an H7 question. There is no cheap settings change hiding in the runtime
parameters that would make an H7 decision moot.

### 2.3 The Isolated class — a new, independent, cheaper lead

Isolated misses (8,236 combined, 24.5% of the pooled miss set) are, by construction, not
something H7 can address — MMSE joint demodulation targets multi-signal interference, not a
single weak signal against a clean floor. The isolated-miss pipeline diagnosis (PR #103) asked
what *does* explain them, live-replaying 40 reproduced misses (20 per SNR band) from the 07-07
session through a clean VB-CABLE loopback:

- **32.2% of tried misses (44.4% in the `-15..-10 dB` stratum) decoded successfully on replay**
  — i.e., Option B's own classification correctly called these Isolated from the text logs, but
  replaying the *identical* historical audio, isolated from whatever the original live
  capture's AGC/timing/adjacent-cycle state was doing, recovered the message anyway in a
  substantial fraction of cases.
- Of the 40 misses that *did* still reproduce as genuine misses, **100% landed Ambiguous** in
  the candidate-generation-vs-LDPC-convergence split — the existing pass-level diagnostic
  cannot resolve that narrower question on a real, busy passband (several cycles saturated the
  native shim's hard 340-candidate buffer). A decisive answer to *that* would require the
  previously-scoped, bounded, instrumentation-only per-candidate-frequency shim (§4.5 of that
  pass's spec) — but that shim answers a different question than the one raised below.

**This was not part of the original H7 caveat, and it does not move F.** But it is arguably the
single most actionable finding across all three passes: a meaningful slice of what has been
counted, correctly, as "not H7's problem" may not be a decoder-sensitivity problem at all — it
may be a **live-capture pipeline artifact** (gain staging, AGC warm-up, cycle-boundary timing),
which would be far cheaper to fix than either H7 or a compile-time sensitivity change, and whose
fix would be additive to whatever the Captain decides about H7.

---

## 3. Updated options for the Captain

| Option | What it means | Effort | Evidence since 2026-07-07 |
|---|---|---|---|
| **A. Commission H7 now** | Open an OpenSpec proposal to scope MMSE joint demodulation. | 3–6 months (unchanged estimate); ≤18.39 pp ceiling at F, more if F′'s extension genuinely holds (Section 2.1) | F still mixed, still nowhere near 0.60; runtime alternative now provably exhausted (2.2); Partial capture-effect strengthens the case that a real, larger-than-raw-F co-channel mechanism exists (2.1) |
| **C. Continue deferring H7** | Treat the current recall profile as an accepted, disclosed limitation for the co-channel portion. | None | Still defensible — F never clears 0.60, and the per-session/sweep straddle around 0.30 was the original reason this stayed "mixed," not a clean rejection either |
| **D. NEW — investigate the live-path/gain-staging lead first** | A bounded follow-up (scope TBD, but expected cheap — days, not months) to determine why 32–44% of Isolated misses decode on isolated replay but not live, before or independent of the H7 decision. | Almost certainly well under 3–6 months; ceiling not yet quantified | New finding this session (2.3) — did not exist at the time of the original scoping document |

Option D is not a substitute for the H7 decision (it targets the Isolated class, which H7
cannot address regardless), but it is a genuinely new, low-cost, high-plausibility lead that
the Captain did not have on 2026-07-07 and that does not require resolving A vs. C first.

---

## 4. QA recommendation

**On H7 itself (A vs. C): the evidence has shifted slightly toward A being more defensible than
it looked on 2026-07-07, but has not produced a clean trigger.** F is unchanged at 29.6% and the
Captain-locked thresholds were never reopened; the new histogram evidence (Partial's
capture-effect matching/exceeding Tight's) argues the true co-channel-attributable fraction is
probably higher than the raw number suggests, and the runtime-sweep result removes "try tuning
first" as a reason to delay a decision either way. This remains fundamentally the cost/benefit
call the 2026-07-07 document already framed: a 3–6 month build against an ≤18.4 pp ceiling
(realistically lower), now with slightly firmer reason to believe the ceiling understates the
true opportunity, but still a product-priority call this analysis cannot make for the Captain.

**Independent of that decision: QA recommends scoping a bounded live-path/gain-staging
investigation (Option D) as the next concrete step**, since it is cheap, new, well-evidenced,
and orthogonal to whatever the Captain decides about H7 — it is the only one of the three
follow-ups that surfaced a lead nobody was previously looking for.

---

## 5. What remains open / explicitly not answered here

- The live-path/gain-staging hypothesis (2.3) is diagnosed as a *symptom*, not yet a
  *root cause* — no specific mechanism (AGC state, boundary alignment, etc.) has been isolated,
  and no fix has been scoped or estimated.
- The CG-vs-LDPC question for genuinely-reproducing Isolated misses remains unresolved
  (100% Ambiguous) and would need the previously-scoped per-candidate-frequency shim for a
  decisive read — orthogonal to, and lower-priority than, the live-path lead above.
- The illustrative ~47 pp extrapolated ceiling in Section 2.1 is exactly that — illustrative,
  not measured. F′ was always reported as an optimistic secondary bound, not the decision
  metric, and nothing in this document changes that.
- All three passes are single-session-limited on their live-replay/live-data components (07-07
  only, the one session with retained WAV audio) — none of this is a multi-session confirmation
  in the way the original three endurance reports were.

---

## 6. References

| Reference | Content |
|---|---|
| `dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md` | The original gate/caveat framing and Option A/B/C decision this document updates |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` | Option B — F=29.6%, mixed verdict, locked thresholds |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/delta-histogram-addendum.md` | Fine-grained histogram + extended sweep; Partial capture-effect exceeds Tight's |
| `qa/rr-study/results/2026-07-22-ea88d12-d001-param-sweep/report.md` | Runtime-parameter sweep — 0/45 points beat baseline, runtime lever exhausted |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/report.md` | Isolated-miss pipeline diagnosis — 32.2%/44.4% decode-on-replay, live-path lead |
| `qa/rr-study/results/d009-investigation-2026-06-21/report.md` §5.2 | Original 3–6 month H7 cost estimate, Option D there (different lettering — MMSE) |
| Issue #3 | D-001 tracking issue |
