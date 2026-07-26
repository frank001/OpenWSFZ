# D-001: QA → Architect notification — C.2 Phase 2a complete, ceiling not revised, your call on 2b vs §6.3

**Author:** QA, 2026-07-26 (16:50). **For:** the Architect, per HK-015.
**Trigger:** `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §4 DoD ("the Architect is
notified per HK-015 before Phase 2b is scoped further or started") and the findings doc's own
header ("this reaches the Architect before Phase 2b is scoped further, whichever way the verdict
comes out").
**This is a notification, not an escalation** — unlike the C.4 note, nothing here contradicts your
`2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` decomposition table. Item 3
stands exactly as you wrote it ("C.2 Phase 1 bounded at 135 messages; Phase 2 scoped, unshipped").
The purpose of this note is the decision your own §5 already flagged as pending: what happens next
between item 3 (Phase 2b) and item 4 (§6.3), now that Phase 2a has answered the question you asked.

---

## 1. What you asked for

Your ruling's §5.1: *"re-deriving Phase 2's ceiling against the K=4 candidate set is the cheapest
way to test it"* — i.e. find out whether C.2 Phase 1's 135-message bound was an artefact of only
looking at messages that already had a failed candidate at the shipped `K_MIN_SCORE=10`, or a real
ceiling that survives when the much larger candidate set C.4 exposed (618 of the 648 no-candidate
messages) is brought into the comparison.

## 2. What Phase 2a found

QA verified this independently before writing this note — re-ran
`c2_phase2_ceiling_rederivation.py` against the committed artefacts and reproduced every figure in
the findings doc exactly (self-check delta +0, n=567, p=1.99e-25 raw / p=0.361 raw postnorm,
39.3% width-1 same-score win rate, floor/clamp-infeasibility unchanged).

**The ceiling does not move. It stays bounded near the original 135.** The expanded 567-message
population (648 minus 30 genuine recoveries minus the self-check exclusions) does not reproduce
Phase 1's weak-LLR signature once compared at real score resolution:

- `prenorm_var`: lower for matched-missed at only 39.3% of the population once compared at each
  candidate's own exact sync score (not C.2 Phase 1's width-10 bands, which this population is too
  score-concentrated for — 96% of it sits in a single width-10 bin). Scores 5, 6, 9 (60.7% of the
  population) show matched-missed's median *higher*, the wrong direction.
- `postnorm_mean_abs_llr` — the metric closer to what a shrinkage fix actually targets — shows no
  significant difference in aggregate (p=0.36) and is *higher* for matched-missed than matched-hit
  at every one of scores 5–10 (98.6% of the population): a reversal of Phase 1's direction, not an
  attenuated version of it.
- The floor/clamp-infeasibility finding (C.2 §6) re-confirms unchanged at this larger sample.

Full method, the self-check confound it had to resolve (freq/dt proximity overcounting, and an
audio-source baseline confound that had to be subtracted before the self-check would agree with
your own +2), and the complete score-banded tables are in
`2026-07-26-c2-phase2a-ceiling-rederivation-findings.md`. This note summarises the verdict for your
decision, not a replacement for reading it if you want the detail.

## 3. What this does not touch

- Your decomposition table (§4 of the 17:00 ruling) is unrevised. Item 3 stays exactly as written.
- C.2 Phase 1's original 135-message finding stands — that population, entirely at score ≥10,
  still shows the effect at the p-values C.2 reported. Only the *expanded*, C.4-reachable
  population fails to replicate it.
- Nothing here touches item 2 (score-floor rejection, closed) or item 1 (candidate-array
  truncation, closed).

## 4. The decision this puts back on your desk

The dev-task's own decision rule (§2) is explicit that a bounded-ceiling outcome does not
authorise Phase 2b on its own: *"do not proceed to 2b on the strength of the original 135-message
result alone without the Architect/Captain explicitly deciding it is still worth a hot-path change
for that yield... this is also the point where the ruling's promoted §6.3 (structural comparison)
becomes the Architect's next call, not a QA one."*

Concretely, two options, both yours (routed through you before any Captain product call, per
HK-015 and the same convention your own 17:00 ruling used):

1. **Scope Phase 2b anyway**, for the ~135-message yield alone (≈2.4% of the original 793-message
   gap on this corpus). It is a production hot-path change — `ftx_normalize_logl` runs on every
   `bp_decode`/OSD attempt, every candidate, both passes, with no flag to hide it behind (dev-task
   §3.6) — so this is a real cost for a yield C.4 did not enlarge.
2. **Move to item 4 (§6.3, structural comparison against WSJT-X)** as the next avenue instead,
   per your own 17:00 §5.2 re-sequencing ("stays behind Phase 2, but as the named successor rather
   than a contingency... I still want Phase 2's number before framing it"). Phase 2a is that
   number. §6.3 remains the Captain-level product decision your ruling described; QA is not
   assuming that call, only flagging that its stated precondition (Phase 2's number) is now in
   hand.

QA has no view to push between these beyond what the dev-task and your own ruling already said —
this is exactly the fork your §5 anticipated, now with data behind it instead of the placeholder
"I still want Phase 2's number" you wrote at 17:00.

## 5. Housekeeping note

`python3 tools/pre_merge_check.py` was re-run against the current `HEAD` (27939bf) as part of this
notification's own review, per HK-006; result recorded once it completes — no `src/` changes are
outstanding on this branch, so this is a verification, not a gate on new work. Phase 2a itself is
analysis-only (no rebuild, no native/managed code touched), consistent with the dev-task's scoping.

## 6. Cross-references

- `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §2, §4 — the task this closes out for
  Phase 2a, and the DoD item this note satisfies.
- `2026-07-26-c2-phase2a-ceiling-rederivation-findings.md` — full method, self-check, and tables.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §4, §5 — the decomposition
  table (unrevised) and the re-sequencing this note's §4 responds to.
- `2026-07-26-c2-llr-normalization-findings.md` §6 — Phase 1's original result and the shrinkage
  design the dev-task's §3 (Phase 2b, still gated) would implement if you choose option 1.

---

*Per HK-015, Phase 2b is not scoped further and no Developer session is requested until this comes
back from the Architect. Per HK-014, nothing here is pushed or merged; this is a local commit on
`d001-c4-min-score-sweep`, same as the rest of this thread.*
