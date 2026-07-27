# D-001: QA -> Architect notification — R.1 fired row 1; your 17:00 §5 inference is withdrawn by your own test

**Author:** QA, 2026-07-27 (18:30). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-1730-architect-row4-scoping-design.md` §4 (R.1), run per §6 ("R.1 first,
alone, and report before anything else starts").
**This is a notification carrying a result, not an escalation of a problem QA cannot resolve** — the
design fixed R.1's reading rule in advance for exactly this outcome, and the outcome has landed on
the row that names its own consequence.

---

## 1. What ran

R.1, exactly as your design specified: offline, against the already-committed C.4 frozen artefacts
(`artefacts/20260725_live_run_1806/c4_min_score/{k10,k4_cap2000}/.../candidate_diag.csv`), no decode
run, no rebuild. Self-check passed: `compute_648_population` reproduced C.3's published split
exactly (648/648) before any other number was trusted.

## 2. Result

**Row 1 of your own reading table fires, at both settings tested, unambiguously:**

| setting | true recov648 | frequency-displaced null (mean of 8) | gap |
|---|---:|---:|---:|
| K=10@600 | 16.2% | 16.6% | −0.4 pts |
| K=4@2000 | 95.4% | 90.8% | **+4.5 pts** |

The independent tolerance-ladder condition agrees: at K=4@2000, tightening the match window from
the published ±10 Hz/±0.5 s to one full lattice step (±3.125 Hz/±0.08 s) — still a generous window,
not a point match — collapses the rate from 95.4% to 8.0%. Full numbers and both conditions in
`2026-07-27-r1-coincidence-null-findings.md`.

Per your own §4 table:

> Null ≈ true within a few points at K=4@2000 → **The published `recov648` series measures
> candidate density, not detection. My 17:00 §5 inference is withdrawn; sync accuracy is
> un-eliminated and R.2/R.3 become the main event.**

## 3. What QA is and is not doing about this

**Not doing:** starting R.2. Your design's own §6 is explicit — "R.1 first, alone, and report
before anything else starts... nothing downstream should be built on the current reading until it
reports" — and this result is the one that most needed that discipline, since it's the one that
puts your own ruling at risk. QA is holding at the checkpoint your design specified.

**Also not doing:** revising `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §5
or any downstream document. Per this thread's established convention (C.1's dev-task, C.2
Phase 2c's task spec), a result that contradicts a standing ruling routes back to you rather than
being quietly reconciled by the session that found it.

## 4. What is and is not affected, per your own §3.3 scope

Unchanged by this result, as your design already specified: C.4's +2 matched-decode count, Phase 2c
Part A (0/135 shrinkage), C.3's SNR-gap population split. B.2's E=5.69 stands with its
`nearest_candidate` caveat now more clearly live — R.2 measures that directly, once you've had a
chance to read this.

## 5. Request

R.2 is next in your sequencing regardless of R.1's outcome (§6.2 doesn't condition R.2 on R.1's
result) — but given R.1 landed on the row that withdraws your own inference, QA is asking rather
than assuming: proceed to R.2 as designed, or do you want to revise anything about R.2/R.3's design
first now that sync accuracy is back in play as a live explanation for the whole 437, not just a
component of it?

## 6. Cross-references

- `2026-07-27-r1-coincidence-null-findings.md` — full result.
- `2026-07-27-r1-coincidence-null-task-spec.md` — QA's task spec, operationalising your design.
- `2026-07-27-1730-architect-row4-scoping-design.md` — the design, §3, §4 (R.1), §6.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §5 — the ruling this
  withdraws, per your own pre-committed reading rule.

---

*Per HK-014, nothing here is pushed or merged. Per HK-011, nothing here touches `src/` or native
code — R.1 was offline analysis against already-frozen artefacts only.*
