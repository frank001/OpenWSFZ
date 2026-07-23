# D-001 — H7 (MMSE Joint Demodulation) Go/No-Go: Summary for the Captain

**Date:** 2026-07-23
**Author:** QA
**Audience:** Captain (Architect cc'd)
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Supersedes/updates:** `dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md` (the original scoping
decision, which recommended **Option B: resolve the caveat first**)
**Status:** Option B and the three follow-up groundwork passes it prompted are now complete and
merged to `main`. This document synthesises them into a single decision brief. **This is a decision
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

That caveat-resolution work is now done, in four parts — Option B itself, plus the three
follow-up passes it prompted:

| Pass | Landed as | One-line finding |
|---|---|---|
| Co-channel attribution (Option B) | `3980ebc` (pre-existing) | F = 29.6% (mixed, straddles the 0.30 threshold) |
| Δf histogram + extended sweep | PR #102 (`d9ab692`) | Partial-class capture-effect (40.3%) matches-or-exceeds Tight's (36.4%) — F′ (75.5%) is a more honest ceiling read than the raw F |
| Runtime-parameter recall/FP sweep | PR #101 (`be7e799`) | **0 of 45 operating points recover any recall** — the cheap/zero-rebuild alternative is exhausted, not merely untried |
| Isolated-miss pipeline diagnosis | PR #103 (`2bdf547`) | **44.4% (`-15..-10 dB`) / 13.0% (`< -15 dB`) of sampled "Isolated" misses decode on replay**, ≈23% population-weighted — points at a live-path/gain-staging issue, cheaper than H7 |

**Net effect on the H7 decision itself: F is unchanged at 29.6% and still does not clear the
0.60 "recommend H7" threshold at any cutoff defensible as a co-channel definition — this work
does not manufacture a clean go/no-go where the data doesn't support one.**

What it *does* deliver is (a) a firmer read that the true co-channel fraction likely sits above
the raw 29.6%, (b) proof that no cheap tuning alternative exists for the co-channel portion,
and (c) a **new and much cheaper lead** — the live-path finding — that did not exist when the
original scoping document was written. That third item is not purely orthogonal to the H7
decision: because the mechanism it implicates is not class-specific, it may also *lower* the
recall ceiling H7 is being priced against, which is why §3.1 argues it should be investigated
**before** Option A is committed rather than merely alongside it.

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

## 2. What the completed passes actually found

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
why the original pass called it **mixed**, not a clean "do not scope."

**On the 0.60 threshold, stated precisely.** F does not reach 0.60 at any cutoff defensible as
a *co-channel* definition — across 10–25 Hz it stays in the 22.1%–44.7% range. The extended
sweep (PR #102) *does* show F rising above 0.60 at wider cutoffs — 50.9% @ 30 Hz, 57.9% @
35 Hz, **64.9% @ 40 Hz, 70.9% @ 45 Hz**, 75.5% @ 50 Hz — so the earlier framing that "F never
approaches 0.60 at any cutoff tested" is not accurate once the sweep is extended past 25 Hz.
But those wide-cutoff values are **not** independent evidence that the H7-recommend bar is met:
past ~25 Hz the cutoff is simply reclassifying Partial-bucket mass as Tight, converging on F′
by construction at 50 Hz. The addendum makes this point itself — the sweep "is the cumulative
integral of §2's histogram; it is not independent evidence of anything the histogram doesn't
already show." The honest reading is that **whether the 0.60 bar is cleared depends entirely on
how wide a Δf still counts as co-channel** — which is precisely the question the capture-effect
finding below bears on, and not one the sweep can settle by itself.

The follow-up histogram pass (PR #102) added resolution *underneath* this same F, without
reopening it, and found something the coarse three-bucket view couldn't show: the
**Partial-class capture-effect signature (40.3% of Partial misses show a ≥10 dB stronger
same-slot neighbour) matches or exceeds Tight's own (36.4%)** in all three sessions — 07-07
36.2%→40.8%, 06-22 36.7%→44.2%, and 07-06 36.4%→36.9% (a clear rise in two, essentially flat
in the third). Per that pass's own pre-registered reading, a *falling* capture-effect fraction from
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
what *does* explain them, replaying **59 sampled 07-07 Isolated misses** through a clean
VB-CABLE loopback — a stratified sample, drawn per band until 20 had reproduced as genuine
misses:

- **A large fraction decoded successfully on replay: 44.4% in the `-15..-10 dB` stratum,
  13.0% in the `< -15 dB` stratum** — i.e., Option B's own classification correctly called
  these Isolated from the text logs, but replaying the *identical* historical audio, isolated
  from whatever the original live capture's AGC/timing/adjacent-cycle state was doing,
  recovered the message anyway in a substantial fraction of cases.

  *Read the two strata separately.* The source report's pooled **32.2%** headline is a sample
  rate, not a population estimate, and should not be quoted as one. The pilot drew until 20
  misses per stratum reproduced, so **more tries were needed in the `-15..-10 dB` stratum
  precisely because more of them decoded** — leaving a sample mix (39% / 61%) inverted relative
  to the population mix (67% / 33%, i.e. 2,477 vs 1,211 of the 3,688 07-07 Isolated misses).
  Weighting each stratum by its true population share gives **≈23.4%**. The effect is
  first-order either way and the finding stands, but 32.2% overstates it by ~9 pp, and the
  combined Wilson CI quoted upstream assumes a simple binomial this design does not satisfy.
- Of the 40 misses that *did* still reproduce as genuine misses, **100% landed Ambiguous** in
  the candidate-generation-vs-LDPC-convergence split — the existing pass-level diagnostic
  cannot resolve that narrower question on a real, busy passband (several cycles saturated the
  native shim's hard 340-candidate buffer). A decisive answer to *that* would require the
  previously-scoped, bounded, instrumentation-only per-candidate-frequency shim (§4.5 of that
  pass's spec) — but that shim answers a different question than the one raised below.

**This was not part of the original H7 caveat, and it does not move F.** But it is arguably the
single most actionable finding across all four passes: a meaningful slice of what has been
counted, correctly, as "not H7's problem" may not be a decoder-sensitivity problem at all — it
may be a **live-capture pipeline artifact** (gain staging, AGC warm-up, cycle-boundary timing),
which would be far cheaper to fix than either H7 or a compile-time sensitivity change.

**It may also be less independent of the H7 decision than it first appears — see §3.1.**

---

## 3. Updated options for the Captain

| Option | What it means | Effort | Evidence since 2026-07-07 |
|---|---|---|---|
| **A. Commission H7 now** | Open an OpenSpec proposal to scope MMSE joint demodulation. | 3–6 months (unchanged estimate); ≤18.39 pp ceiling at F — more if F′'s extension holds (2.1), **less** if the live-path effect is class-independent (3.1) | F still mixed at the primary cutoff and does not clear 0.60 at any defensible co-channel width; runtime alternative now provably exhausted (2.2); Partial capture-effect strengthens the case that a real, larger-than-raw-F co-channel mechanism exists (2.1) |
| **C. Continue deferring H7** | Treat the current recall profile as an accepted, disclosed limitation for the co-channel portion. | None | Still defensible — F does not clear 0.60 at any defensible co-channel width, and the per-session/sweep straddle around 0.30 was the original reason this stayed "mixed," not a clean rejection either |
| **D. NEW — investigate the live-path/gain-staging lead first** | A bounded follow-up (scope TBD, but expected cheap — days, not months) to determine why 13–44% of sampled Isolated misses (≈23% population-weighted) decode on isolated replay but not live. | Almost certainly well under 3–6 months; ceiling not yet quantified | New finding this session (2.3) — did not exist at the time of the original scoping document |

Option D is not a substitute for the H7 decision (it targets the Isolated class, which H7
cannot address regardless), but it is a genuinely new, low-cost, high-plausibility lead that
the Captain did not have on 2026-07-07.

### 3.1 Option D is *less* independent of the H7 decision than it first looks

Both §2.3 above and PR #103's own report frame the live-path finding as orthogonal to H7, on
the grounds that it targets the Isolated class. That framing understates its relevance, in a
direction the Captain should hear **before** pricing Option A.

The replay pilot sampled **only Isolated misses**. But nothing about AGC warm-up, gain staging,
or cycle-boundary/sample-clock alignment is *class-specific* — those mechanisms act on the
whole passband, not on signals selected by whether they happen to have a neighbour within
50 Hz. The null expectation is therefore that the same live-path handicap costs decodes in the
**Tight and Partial classes too**, and nothing measured so far excludes that.

If that holds, some fraction of the 9,956 Tight-class misses underpinning the **18.39 pp "H7
ceiling" are not H7's to recover at all** — they would be recovered by the far cheaper
live-path fix. Option D would then not merely sit alongside the H7 decision; it would **lower
the ceiling against which that decision is priced**. The ≤18.4 pp figure in the Option A row
should be read as an upper bound not yet corrected for this effect.

This argues for sequencing D **before** committing to A, and it suggests a cheap extension to
any Option D scope: **replay a matched sample of Tight-class misses alongside the Isolated
ones**, to measure directly whether the live-path effect is class-independent. If it is, the H7
cost/benefit changes materially. If it is not, the current ceiling stands and Option D reverts
to the orthogonal, additive lead described above. Either result is worth having before a 3–6
month commitment.

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

**QA recommends scoping a bounded live-path/gain-staging investigation (Option D) as the next
concrete step**, since it is cheap, new and well-evidenced — it is the only one of the three
follow-ups that surfaced a lead nobody was previously looking for. Per §3.1, QA further
recommends that this investigation **include a matched Tight-class replay sample**, because the
answer to "is the live-path effect class-independent?" feeds directly back into the ≤18.4 pp
ceiling the A-vs-C decision is priced against. That makes D worth doing *before* A is
committed, not merely alongside it.

---

## 5. What remains open / explicitly not answered here

- The live-path/gain-staging hypothesis (2.3) is diagnosed as a *symptom*, not yet a
  *root cause* — no specific mechanism (AGC state, boundary alignment, etc.) has been isolated,
  and no fix has been scoped or estimated.
- **The live-path effect size is a pilot estimate from a stratified sample, and its
  class-independence is entirely unmeasured.** The per-stratum rates (13.0% / 44.4%, n=59
  tried) carry wide confidence intervals and the ≈23.4% population-weighted figure inherits
  them; the upstream report's pooled 32.2% should not be quoted as a population rate (2.3). No
  Tight- or Partial-class miss has ever been replay-tested, which is the gap §3.1 turns on.
- The CG-vs-LDPC question for genuinely-reproducing Isolated misses remains unresolved
  (100% Ambiguous) and would need the previously-scoped per-candidate-frequency shim for a
  decisive read — orthogonal to, and lower-priority than, the live-path lead above.
- The illustrative ~47 pp extrapolated ceiling in Section 2.1 is exactly that — illustrative,
  not measured. F′ was always reported as an optimistic secondary bound, not the decision
  metric, and nothing in this document changes that.
- **Session coverage is uneven across the four passes, and the two most decision-relevant new
  findings are the single-session ones.** Option B (F = 29.6%) and the Δf histogram both draw on
  all three sessions' `ALL.TXT` logs and are genuinely multi-session. But the runtime-parameter
  sweep (PR #101) and the isolated-miss replay pilot (PR #103) are **07-07 only** — that being
  the sole session with retained per-slot WAV audio — so neither the "runtime knobs are
  exhausted" result nor the live-path lead has the multi-session corroboration the original
  three endurance reports had. Both should be read as strong single-session results pending
  confirmation, not as established across band conditions.

---

## 6. References

| Reference | Content |
|---|---|
| `dev-tasks/2026-07-07-d001-h7-mmse-scoping-arch.md` | The original gate/caveat framing and Option A/B/C decision this document updates |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` | Option B — F=29.6%, mixed verdict, locked thresholds |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/delta-histogram-addendum.md` | Fine-grained histogram + extended sweep; Partial capture-effect exceeds Tight's |
| `qa/rr-study/results/2026-07-22-ea88d12-d001-param-sweep/report.md` | Runtime-parameter sweep — 0/45 points beat baseline, runtime lever exhausted |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/report.md` | Isolated-miss pipeline diagnosis — 44.4%/13.0% decode-on-replay (≈23.4% population-weighted), live-path lead. **See its §3.1 CORRECTION** re: the superseded pooled 32.2% figure |
| `qa/rr-study/results/d009-investigation-2026-06-21/report.md` §5.2 | Original 3–6 month H7 cost estimate, Option D there (different lettering — MMSE) |
| Issue #3 | D-001 tracking issue |
