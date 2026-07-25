# QA review: `dev-tasks/2026-07-25-cycleframer-nominal-reset-conflation-fix.md` (tasks.md §10, design.md Decision 9)

**Reviewer:** QA session, 2026-07-25. **Scope:** code review of the Developer session's partial
implementation of Decision 9 (10.1-10.4), per HK-011 (QA reviews `src/` before the Captain's
pre-push sign-off; QA does not implement). **Escalation raised here:** an Architect-level design
question surfaced during review, blocking 10.4. Routed to the Architect per the Captain's explicit
direction (2026-07-25 review conversation) rather than resolved ad hoc in this QA session or left
for a Developer session to decide unilaterally.

## Verdict on what's implemented (10.1-10.3, and 10.4's new test)

Approved. Independently re-derived, not merely re-read:

- **10.1** — `nominalCycleStart = nominalCycleStart.AddSeconds(correction / (double)SampleRate);`
  is the exact prescribed statement, in the correct branch (`CycleFramer.cs` line 509 as of this
  review). Confirmed by hand that this, combined with the pre-existing `pendingNominalAdjustSeconds`
  one-shot bump (Decision 8, consumed one window later at line 373), produces a total adjustment of
  `2 x correction/SampleRate` spread over two window advances per correction — matching design.md
  Decision 9's own derivation, `(2*c_now - c_prev)/SampleRate` (design.md line 448), not an
  independently-invented shape.
- **10.2** — declaration comment, correction-fires block comment, and class `<summary>` all now
  state the corrected invariant; no trace of the false pre-Decision-8 premise remains.
- **10.3** — the decision not to retrofit the two 9.3 tests is correct, not a shortcut: on a
  session's *first* correction, `nominalCycleStart` and `cycleStart` are provably equal beforehand
  (nothing has diverged them yet), so the bug and the fix are numerically indistinguishable there.
  Verified this algebraically myself; matches the developer's hand-derivation.
- **10.4's new test** (`RunAsync_TwoConsecutiveDiscardCorrections_SecondPostReadingDoesNotReproduceFirstCorrection`)
  — sound falsification test; fires two corrections and checks the second post-reading against both
  its own and the first correction's magnitude. Passes against the current fix. The developer's
  claim to have hand-confirmed it fails without 10.1 (ratio 1.33x vs the 0.6x bound) is consistent
  with the mechanism as I traced it, though I did not personally re-run that specific reversion.

Ran the full `CycleFramer` test suite myself (not just read the developer's notes):

```
dotnet test tests/OpenWSFZ.Ft8.Tests/OpenWSFZ.Ft8.Tests.csproj --filter "FullyQualifiedName~CycleFramerTests"
...
Failed!  - Failed: 1, Passed: 22, Skipped: 0, Total: 23
```

22 of 23 pass, confirming the above. The one failure is the subject of this escalation.

## The escalation: `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`

This test currently fails, exactly as the developer's `tasks.md` 10.4 addendum predicts:

```
At index 19: Expected r to be less than or equal to 220.0, but found 660.0 (difference of 440)
```

Reverting its tolerance to the pre-9.1 value of 220 (already the value on disk; 9.1's earlier
widening to 305 is not currently present in the working tree) does not merely need a bigger
constant — the developer reports residual climbing *linearly without bound* out to windowCount=60
(reaches 1740, no plateau). I independently re-derived why, rather than accepting the claim at
face value:

This test's `RateClock` returns `start + n * perRead` on its `n`-th read — a fixed function of
**read count alone**, with zero dependency on whether a correction just fired or how much real
time it cost. Decision 8's `pendingNominalAdjustSeconds` mechanism, and Decision 9's own derivation
(`2*c_now/SampleRate` total per correction), both assume a correction has a genuine next-window
real-time cost that the clock's own reading will reflect back (this holds for `SampleCountClock`,
which derives its reading from actually-delivered sample counts — the two 9.3 tests and the new
10.4 test, all `SampleCountClock`-based, pass cleanly). Under `RateClock` that assumption is
structurally false: the one-shot bump has nothing in the clock's reading to reconcile against, so
each correction leaves an un-cancelled bias that compounds indefinitely. The old buggy
`nominalCycleStart = cycleStart` reset happened to act as a periodic release valve for exactly this
synthetic mismatch — which is a coincidence of the bug (per Decision 9's own Finding 2 argument
that the reset was wrong), not a property this test should be preserved to exercise.

**This is a design-level question, not an implementation defect in 10.1**: the fix is verbatim
correct per Decision 9, and all real-cost-consistent tests pass. The question is what
`RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections` should model going
forward, now that its `RateClock` premise is provably incompatible with Decision 8/9's mechanism.

## Routed to the Architect (Captain's direction, 2026-07-25)

Options surfaced during this review, for the Architect's Decision 9 addendum — not decided here:

1. Rebuild the test on `SampleCountClock` (the same real-cost-consistent model 9.3/10.4 already
   use) so it can represent many corrections under Decision 8/9's actual assumptions, rather than
   retiring the many-corrections scenario outright.
2. Retire/supersede it, on the grounds that 10.4's new multi-correction `SampleCountClock` test
   already covers the reset-conflation falsification this one was never designed to catch, and a
   `RateClock`-based many-corrections scenario cannot be made meaningful without contradicting
   Decision 8's own real-cost premise.
3. Some other shape the Architect prefers — flagged here as an open design question, same
   convention as design.md's own `## Open Questions` section.

## Status

- `tasks.md` 10.1-10.3 remain checked (approved above); 10.4 remains **unchecked and blocked**,
  correctly so — do not mark it done, re-widen the tolerance, or run `pre_merge_check.py` (10.7)
  until the Architect resolves the above and a Developer session applies whatever follow-up it
  implies.
- 10.5-10.9 untouched, as expected — they were correctly not attempted ahead of this blocker.
- Not independently verified in this review: the dev-task's own instruction to check whether
  `specs/ft8-decoder/spec.md` needs updating ("verify, don't assume") — no evidence in the diff
  that this was done. Flag for whoever picks this back up next; likely no change needed (same
  reasoning as every prior round: the spec describes the observable contract, not the internal
  formula), but per this investigation's own convention, state it explicitly rather than leaving it
  silent.
- HK-011 merge hold (`src/` not pushed without the Captain's sign-off) and HK-006 (no
  `pre_merge_check.py` claim of "ready") both remain in force, independent of this escalation.

## Cross-references

- `dev-tasks/2026-07-25-cycleframer-nominal-reset-conflation-fix.md` — the handoff this reviews.
- `openspec/changes/fix-cycle-boundary-clock-drift/tasks.md` §10 — the checklist item (10.4)
  this escalation blocks.
- `openspec/changes/fix-cycle-boundary-clock-drift/design.md` Decision 9 — the design basis this
  review confirmed the implementation against.
