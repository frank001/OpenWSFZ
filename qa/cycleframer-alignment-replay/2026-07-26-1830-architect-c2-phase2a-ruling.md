# D-001: Architect ruling on C.2 Phase 2a — Phase 2b declined, item 4 is next, and what it must be scoped as

**Author:** Architect, 2026-07-26 (18:30). **For:** the Captain and QA.
**Answers:** `2026-07-26-1650-qa-to-architect-c2-phase2a-notification.md` §4, the option 1 / option 2 fork.
**Revises:** `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §4 (item 3's status only)
and §5 (sequencing). The §2/§3 verification tables and the §4 entries for items 1, 2 and 4 are untouched.

QA was right to route this back rather than pick a side, and right that this is exactly the fork my
§5 anticipated. Phase 2a is a clean piece of work — the self-check in particular, which found a
real audio-source baseline confound and drove the discrepancy to exactly +0 rather than settling
for "close enough," is the standard I want this thread held to.

The verdict I reach is option 2's direction. But neither option is scoped correctly as written, and
two things in the notification need correcting for the record before the decision rests on them.

---

## 1. Short answer

**Phase 2b is declined. Item 4 becomes the active avenue.**

Not "deferred," not "held" — declined on this evidence, with a stated condition (§5) under which it
reopens. Carrying it as perpetually-scoped-but-unstarted is the sprawl the consolidation doc's §2
was written to stop.

But item 4 does **not** start as §6.3 is currently written. §6.3 asks "how much of WSJT-X's decoder
are we willing to reimplement," and I am not putting that question to the Captain in that form,
because we now have enough evidence to decompose it and I would be asking for an open-ended
commitment against a question we can narrow cheaply first. §6 below names the one measurement that
narrows it.

## 2. Two corrections to the record

Both matter because the decision rests on them, and one of them cuts *against* the conclusion I
reach — which is why it goes first.

### 2.1 The yield figure is wrong, and wrong in Phase 2b's disfavour

The notification's §4 option 1 states the 135-message yield is "≈2.4% of the original 793-message
gap on this corpus." It is **17.0%**. 135/793 = 0.170, and both C.2 Phase 1 §1 and C.3 §5 state
17% explicitly ("82% of the missed-message population (648) versus 17% (135, C.2's own Phase 1
target)"). I cannot reconstruct where 2.4% comes from.

This is a factor-of-seven understatement of option 1's own case, in a paragraph arguing option 1 is
expensive for what it buys. I am flagging it rather than quietly using the better number because it
is the same class of error I called out in C.4's §2 — a figure carried forward into a decision
paragraph without being re-derived — and the fact that this one happens to favour the conclusion I
was already heading toward is precisely why it needed checking.

**The conclusion survives the correction.** §3 explains why 17% does not change it. But the record
should say 17%.

### 2.2 "Reversal of Phase 1's direction" is stronger than the data supports

The notification's §2 describes `postnorm_mean_abs_llr` being higher for matched-missed as "a
reversal of Phase 1's direction, not an attenuated version of it," and the findings doc's §1 says
"the opposite of C.2 Phase 1's original direction."

The two populations barely overlap in sync score. Phase 1's 135 sit entirely at score ≥10; the
expanded 567 sit at 5–9 for 96% of their mass, reachable only because C.4 lowered the floor to 4.
There is no score band where both populations are meaningfully present, so this is not a replication
attempt that failed — it is a *different score regime* showing a different signature. The findings
doc's own §8 second bullet is honest about this ("the finer-grained read is only as informative as
the lowest handful of scores"); the summary compresses it into a stronger claim than §8 licenses.

The correct statement is: **the LLR-weakness signature does not extend below the score regime it was
found in.** That is not evidence that Phase 1's effect is illusory, and nothing here impeaches
Phase 1. It is evidence that the effect is confined, which is all the ceiling question needed.

The decision is the same either way — the ceiling is not revised. But an overclaimed reversal would
sit in the record as an argument against Phase 1 itself, and it is not one.

## 3. Ruling 1 — why Phase 2b is declined at 17%

Even at the corrected 17%, the arithmetic does not close.

**135 is a ceiling on the population that could conceivably benefit, not an expected yield.** C.2
Phase 1 established a *correlation* between weak LLRs and failure to decode. It did not establish
that correcting the LLRs makes those candidates decode. C.2 §6 says so in its own words: whether
shrinkage "improves LDPC/OSD convergence for these specific candidates, or simply under-drives
already-marginal signals into non-convergence a different way, is exactly the kind of question that
can only be answered empirically by re-decoding." So the honest expected value of Phase 2b is *an
unknown fraction of 17%, with a real possibility that the fraction is zero and a non-trivial one
that it is negative.*

Against that, the cost is not one session. From the dev-task's own §3 and §4:

| cost | why it is not reducible |
|---|---|
| Production hot-path change, no flag | `ftx_normalize_logl` runs on every `bp_decode`/OSD attempt, every candidate, both passes. It ships fully or not at all (dev-task §3.6). |
| Control-flow restructure of the pass-0 loop | A per-pass median needs a prelim pass over all candidates before any decodes; that loop already carries AP-decode, dedup and suppression-accumulator logic (C.2 §6). |
| D-009 OSD calibration invalidated | `OSD_CORR_THRESHOLD`/`OSD_NHARD_MAX` were calibrated against the current LLR distribution's shape. Changing the shape voids the calibration until re-verified (dev-task §3.5). |
| Held-out-corpus weight sweep | Required, and correctly so — the discovery corpus cannot also be the tuning corpus (dev-task §3.2). |
| Full R&R S1–S8 rerun | Required before any shipped-constant decision (dev-task §3.5). |

That is a multi-session change with a regression surface that reaches D-009's calibration and the
R&R gate suite, bought against an unquantified expectation.

**The second reason is sharper than the arithmetic.** Phase 2a did not merely fail to enlarge the
ceiling; it found that on 567 candidates — four times Phase 1's sample — the metric the fix most
directly targets runs the *other way*. Shrinkage's entire mechanism is to pull low-variance
candidates' effective variance up so their LLRs are scaled less aggressively. On the expanded
population, per §2.2, that is at best a no-op and at worst the wrong sign. We would be shipping an
unflagged hot-path change tuned on 135 candidates in one score regime, which acts on every candidate
in every regime, including 567 where its own target metric points the other way. Even granting that
the two populations are genuinely different, we have no mechanism that explains both, and shipping a
correction without one is how a regression gets shipped.

**Item 3's status becomes: Closed — bounded at 135-message ceiling, no mechanism supported below
score 10, declined on cost/benefit.** §5 states the reopening condition.

## 4. What Phase 2a actually bought us

It should not be recorded as a null result. Combined with C.3 and C.4, it closes a real box:

- C.3: the 648 gap messages sit at median **−8 dB** (vs +1 dB for shared hits), p = 1.1×10⁻⁷⁴ —
  the largest effect measured anywhere in this thread.
- C.3: **co-channel masking is refuted.** Gap messages sit *farther* from decoded neighbours, not
  closer (p = 5.4×10⁻⁵²). The SIC hypothesis §6.3 originally named is not what the data shows.
- C.4 + my §2: at K=4 we place a candidate at the right frequency and time for these messages and
  **+2 decode**. Candidate generation is not the constraint.
- Phase 2a: those candidates' LLRs are **not weak**. `postnorm_mean_abs_llr` is normal-to-higher
  than the decoding population's at 98.6% of the sample.

Read together that is a much narrower statement than "the decoder is structurally different":

> For a −8 dB signal we have correctly located in frequency and time, with no co-channel
> interference explaining it, we produce LLRs of normal magnitude that do not decode.

LLRs of normal magnitude that do not decode are **wrong, not small**. That is a different defect
class from anything C.2 was ever testing, and it is why I am not sending §6.3 up as written.

## 5. The condition under which Phase 2b reopens

Stated so "declined" is falsifiable rather than a preference:

If a future measurement shows our LLRs for the missed population are *directionally correct but
under-confident* — i.e. the hard decisions are mostly right and the decoder is failing on
magnitude — then LLR scaling is back on the table and Phase 2b's design is the right one to
revive. §6's measurement is what would show that.

If instead the hard decisions are substantially wrong, no rescaling of a wrong sign helps, and
Phase 2b is not merely poor value but addressing the wrong stage. My expectation is the latter, from
§4's chain — but that is an expectation, not a result, and §6 is what settles it.

## 6. Ruling 2 — item 4 opens with one measurement, not a product decision

**Recommended next step, for QA to scope (per HK-015 this is a recommendation, not a task):
measure the hard-decision bit error rate of our 174 LLRs against the true codeword.**

For a message WSJT-X reported and we missed, we know the correct answer. Re-encoding WSJT-X's own
reported text yields the true 174-bit codeword. Comparing it against the hard decision of our LLRs
for the candidate sitting at that frequency and time gives one number that discriminates between
every remaining hypothesis:

| BER vs. true codeword | reading | where the residue is |
|---|---|---|
| ≈50% | we are demodulating noise; the candidate is at the right freq/dt but symbol extraction never locks | sync/demodulation front-end. Kills *all* LLR-scaling avenues at once, including Phase 2b permanently. |
| ~15–25% | close, and LDPC/OSD is running out of correction power | decode effort — BP iteration count, OSD depth/gate. Cheap constants, not a reimplementation. |
| low, with correct signs | LLRs directionally right but under-confident | LLR magnitude after all — reopens Phase 2b per §5. |

Three fundamentally different projects, separated by one offline number. That is a better
sequencing decision than any amount of further reasoning from aggregates, and it is the framing
§6.3 needs before it goes to the Captain — because "how much of WSJT-X's decoder do we reimplement"
is unanswerable, while "our front-end does not lock on −8 dB signals; here is the measured evidence"
is a decision a Captain can actually take.

**On feasibility, and where I am uncertain:**

- The reference side needs no new native work that I can see. `ft8_encode_message` is already
  exported (`ft8_shim.h:542`) and returns 79 tone indices; stripping the 21 sync symbols and Gray-
  decoding the remaining 58 × 3 bits should recover the 174-bit codeword. **I have not verified this
  end to end** — QA should confirm the Gray/sync extraction round-trips against a known message
  before building anything on it. If it does not, the fallback is a small opt-in export of the
  codeword array from inside `ft8_encode`.
- The measured side **does** need a native diagnostic change: `candidate_diag.csv` currently carries
  only aggregates (`prenorm_var`, `postnorm_mean_abs_llr`), not the 174 values. That is a Developer
  session under HK-011 — but it is an **opt-in, default-disabled diagnostic**, the same shape as
  C.2 Phase 1's `ft8_get_last_candidate_diag`, which was verified a behavioural no-op when disabled.
  That is a categorically lower-risk session than Phase 2b's unflagged hot-path change, and it needs
  no R&R rerun and no OSD re-calibration.
- Population: the 135 (score ≥10) and the 567 (score 5–9) should be measured **separately**, with
  the matched-hit control as a third arm. If the two missed populations return different BERs, that
  is the mechanism distinguishing them that §3 says we currently lack.

**§6.3 as a product decision stays parked until this number exists.** My 17:00 §5.2 said I wanted
Phase 2's number before framing it. I have Phase 2's number; it turns out to point at a cheaper
question first. That is a re-sequencing, not a reversal — the structural avenue is still where this
is heading, and §4's chain is stronger evidence for it than anything we had at 17:00.

## 7. What this does not overturn

- **C.2 Phase 1's verdict stands**, per §2.2. Its 135-message result is unimpeached; it is bounded,
  not wrong. Declining Phase 2b is a cost/benefit call plus §3's wrong-sign concern, not a finding
  against Phase 1.
- **Phase 2a's ceiling verdict stands and is accepted in full.** §2's corrections are to the
  notification's framing and one arithmetic figure, not to the analysis, whose self-check I regard
  as the strongest methodological work in this thread.
- **C.3's population split and statistics stand**, including the −8 dB and co-channel-masking
  results §4 leans on.
- **C.4's verdict stands** (score floor closed, +2). Phase 2a's self-check independently reproduces
  it, which corroborates it.
- **The floor/clamp-infeasibility conclusion (C.2 §6) is re-confirmed** at n=567, not revised.
- **Items 1 and 2 of the §4 decomposition stay closed.** Nothing here reopens them.
- **`K_MIN_SCORE` stays at 10.** No change proposed, unchanged from the 17:00 ruling.
- **The §7 false-decode question stays held** at the Captain's instruction, unscoped.

## 8. Revised decomposition table

Replaces §4 of the 17:00 ruling. Only item 3's status changes.

| # | mechanism | status | measured decode yield |
|---|---|---|---|
| 1 | Candidate-array truncation (`K_MAX_CANDIDATES`) | **Closed** — C.1 | +12 decodes, +1.6% of gap. Real, small, plateaus. |
| 2 | Sync score-floor rejection (`K_MIN_SCORE`) | **Closed** — C.3/C.4 + 17:00 ruling | +2 decodes while false decodes rise 61 → 376. |
| 3 | LDPC survival / LLR quality | **Closed — declined** | Ceiling held at 135 (17.0% of gap) and unquantified within it; no mechanism below score 10; hot-path cost disproportionate. Reopens per §5. |
| 4 | Structural decoder difference vs WSJT-X | **Open — active** | Unmeasured. Opens with §6's BER measurement, not with §6.3's product question. |

## 9. Honest caveats

- One 21-minute session, one device, one band. Same single-sample caveat as every prior note in
  this thread, applied to my conclusions exactly as to QA's.
- §6's BER table's thresholds (≈50% / 15–25% / low) are illustrative bands for reading the result,
  not calibrated decision boundaries. What LDPC+OSD can actually correct at this code rate should be
  derived or measured, not taken from my table, before the number is interpreted against it.
- I have not verified the Gray/sync extraction path in §6, and say so there. If it does not
  round-trip, §6's cost estimate rises by one small native export — it does not invalidate the
  approach.
- Declining Phase 2b forecloses a real avenue on cost/benefit reasoning, not on proof that it would
  fail. If the Captain reads 17% of the gap as worth a multi-session hot-path change with an
  uncertain hit rate, that is a legitimate product call and it overrides this ruling. I have stated
  my concern once, here, and it is the wrong-sign point in §3, not the arithmetic.
- §4's chain is joint evidence across three separate experiments, each with its own caveats. It is
  a strong localisation, not a proof, which is exactly why §6 measures rather than assumes.

## 10. Cross-references

- `2026-07-26-1650-qa-to-architect-c2-phase2a-notification.md` — the notification this answers.
- `2026-07-26-c2-phase2a-ceiling-rederivation-findings.md` §1, §4.1, §8 — the analysis accepted here;
  §8's second bullet is the honest version of §2.2's correction.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §4, §5 — table replaced by §8
  above, sequencing revised by §6.
- `2026-07-26-c2-llr-normalization-findings.md` §1, §6 — Phase 1's 17.0% figure and its own
  "can only be answered by re-decoding" caveat, which §3 relies on.
- `2026-07-26-c3-candidate-generation-gap-findings.md` §3, §5 — the −8 dB and co-channel-masking
  results §4 leans on, and its own note that SIC "is not what the data shows."
- `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §3, §4 — Phase 2b's cost, tabulated in §3
  above. Its Phase 2b half is now closed unstarted rather than gated.
- `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §6.3 — parked per §6, not scoped.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:542` (`ft8_encode_message`) — §6's reference-side entry point.
- `native/ft8_lib_build/patched/ft8/decode.c:380-399` (`ftx_normalize_logl`) — unchanged; Phase 2b
  would have changed it.

---

*Per HK-014 nothing is pushed or merged. Per HK-015 this is Architect → QA material; `tasks.md` and
`dev-tasks/` remain QA's to author, and §6 is a recommendation for QA to scope into a dev-task, not
a task. The §6.3 product decision remains the Captain's and is not being put to them yet.*
