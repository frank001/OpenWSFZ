# Developer handoff: fix `nominalCycleStart`'s reset-to-`cycleStart` conflation (design.md Decision 9)

**Status:** Ready for a Developer session. Design decision is made (`design.md` Decision 9,
Architect-authored 2026-07-25, re-analysing `qa/endurance/2026-07-25-40m-band-9.5-fail/`'s own raw
artefacts); this document hands off the `src/OpenWSFZ.Ft8/CycleFramer.cs` one-line fix and its test
changes per HK-011 — QA does not implement this itself. `tasks.md` section 10 (10.1-10.9) tracks
this work item-by-item; this document is the narrative companion, same convention as the four prior
rounds' dev-task files in this investigation.

**Blocks:** `fix-cycle-boundary-clock-drift` (`openspec/changes/fix-cycle-boundary-clock-drift/`,
PR #108). `tasks.md` 9.6 is marked superseded by this section — **do not revert 9.1** (the
deviation-accounting mechanism from Decision 8). Section 10 builds on 9.1, it does not replace it.
The HK-011 merge hold stands until 10.8 (this fix's own live re-confirmation) passes.

**Working-tree state as of this handoff:** `src/OpenWSFZ.Ft8/CycleFramer.cs` and
`tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` are currently **uncommitted** on
`docs/propose-fix-cycle-boundary-clock-drift`, containing 9.1's implementation only (confirmed:
the buggy line is still present at `nominalCycleStart = cycleStart;`, `CycleFramer.cs` line 483 as
of this handoff — inside the `driftStreakCount >= RequiredConsecutiveReadings` branch). This fix
applies on top of that uncommitted state, not on top of a clean `HEAD`.

## Context — why 9.1 (Decision 8) only half-worked

Four fix attempts against this change's correction mechanism have now been built and live-tested;
attempt #4 (9.1, Decision 8) was meant to stop a correction's own real-time cost from being
re-measured as fresh drift. `qa/endurance/2026-07-25-40m-band-9.5-fail/report.md` found it still
non-convergent over an 11h51m session (correction magnitude grew ~8x hour-over-hour). Re-analysing
that report's own raw artefacts (not a new live run) found the recommendation to escalate to a new
correction architecture was wrong — **9.1's mechanism works exactly as designed; a separate,
pre-existing line of code discards its result one step later.**

**The two clocks now advance unequally, by design (9.1):**

```csharp
cycleStart        += CycleDurationSecs;                                // unchanged
nominalCycleStart += CycleDurationSecs + pendingNominalAdjustSeconds;  // 9.1's one-shot adjustment
```

For every window following a correction, `nominalCycleStart` legitimately sits ahead of `cycleStart`
by that correction's own adjustment — that gap *is* 9.1 doing its job. But the correction-fires
branch then executes:

```csharp
cycleStart        = cycleStart.AddSeconds(correction / (double)SampleRate);
nominalCycleStart = cycleStart;   // <-- BUG: throws away the gap 9.1 just created
```

`nominalCycleStart = cycleStart` was **correct before Decision 8 existed** — with no one-shot
adjustment the two clocks never diverged, so re-anchoring one to the other and shifting it were the
same operation. Decision 8 made them diverge on purpose; this line was never revisited to match.

**Quantitative confirmation (design.md Decision 9, Findings 1 and 3 — not re-derived here, see
design.md for the full working):**
- Each post-correction deviation reading correlates with the *previous* correction at r=0.9931
  (slope 0.977, sign match 135/135) — an identity, not noise. The `9.5` report scored against a
  correction's *own* magnitude (corr=0.764) and concluded non-convergence; scored against the
  *previous* correction, the fix's real behaviour is visible.
- Energy balance over the 9.5 session: 68.9 s measured excess real time, of which 66.8 s was the
  corrections' own discard cost (self-inflicted, chasing this bug) and 2.1 s was unexplained residual
  against a predicted 1.81 s of genuine device drift. The actual defect this whole change targets is
  ~4 s over 11.8 h; this bug alone generated 67 s of chasing it.

## The fix (design.md Decision 9)

One statement, `CycleFramer.cs` line 483 (as of this handoff's working-tree state — re-locate by the
`driftStreakCount >= RequiredConsecutiveReadings` branch's re-anchoring block if the line number has
shifted by the time this is picked up):

```csharp
// was:
nominalCycleStart = cycleStart;

// now:
nominalCycleStart = nominalCycleStart.AddSeconds(correction / (double)SampleRate);
```

**Shift by `correction`, not by `deviationSeconds`.** In the ordinary unclamped case they're equal,
so this zeroes the current deviation exactly, same as before. But if `CorrectionSanityCeilingSamples`
ever clamps `correction` below the full confirmed `deviationSamples`, shifting by `correction`
correctly carries the residual `(deviation − correction)` forward as a slew to be chipped away on
subsequent cycles (Decision 5's intended behaviour); shifting by `deviationSeconds` would silently
swallow that residual instead. `cycleStart` keeps its own separate advance, unchanged — the whole
point of this fix is that `cycleStart` and `nominalCycleStart` are not interchangeable, and the old
line's premise (that re-anchoring one to the other is safe) is exactly what Decision 8 invalidated.

## What needs to change

- [ ] `src/OpenWSFZ.Ft8/CycleFramer.cs` — apply the one-line fix above (`tasks.md` 10.1).
- [ ] Same file: the declaration-site comment on `nominalCycleStart` (currently, near line 220:
      *"Reset to match cycleStart whenever a correction fires, so deviation starts accumulating
      fresh from that point"*) states the now-false pre-Decision-8 invariant — this comment is part
      of the defect and must be corrected alongside the code, not left stale (`tasks.md` 10.2).
      State instead that `nominalCycleStart` is a pure arithmetic measurement reference that
      legitimately diverges from `cycleStart` by the accumulated history of one-shot adjustments,
      and must never be re-anchored to it. Also update the correction-fires block's own comment
      (currently, near line 473: *"reset the nominal reference to match so deviation starts
      accumulating fresh from this point"*) and the class-level `<summary>` paragraph describing
      Decision 8 (added under 9.1) to match the corrected mechanism.
- [ ] `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — change the 9.3 acceptance metric in
      `RunAsync_DiscardCorrectionDeviationAccounting_NextReadingNearNoiseFloor` and
      `RunAsync_ReplayCorrectionDeviationAccounting_NextReadingNearNoiseFloor` to regress the
      post-correction reading against **both** its own magnitude and the *preceding* correction's
      magnitude (`tasks.md` 10.3). These two tests each fire exactly one correction, so there is no
      "preceding correction" within a single test to compare against for the *first* correction —
      the practical implementation is a new test (next bullet) rather than a retrofit of these two;
      treat this bullet as "confirm these two still pass and their bound still means what it claims
      once 10.1 lands" plus updating any comment that describes the bound in terms that implicitly
      assumed no preceding correction exists.
- [ ] New test, `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — fire **two or more consecutive**
      corrections under the deterministic `SampleCountClock` + `FeedSamplesAtRealRate`/
      `FeedSamplesAtRealRateTrackingDelivery` harness (extend, don't duplicate — these helpers
      already exist from 8.7/9.3) and assert the *second* correction's post-reading does not
      reproduce the *first* correction's magnitude (`tasks.md` 10.4). This is the direct
      falsification test for Finding 1/2 above — every existing 9.3 test fires exactly one
      correction, which is precisely why the reset-conflation bug escaped them.
- [ ] Restore `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`
      (the one existing test that fires *many* corrections in sequence) to its **pre-9.1
      tolerance** (`tasks.md` 10.4). Its tolerance was widened under 9.1 when its residual settled
      "~80 samples higher than before," rationalised at the time as a benign new plateau — per
      Decision 9 Finding 5, that was the `c_prev` re-injection this fix removes, visible in the
      test suite before the 9.5 overnight run was ever started. If this fix is correct, the original
      tolerance must pass again without re-widening. Treat a need to re-widen it as evidence the fix
      is incomplete, not as a reason to accept a new plateau a second time.
- [ ] Re-derive and record the drift constants against the ~101 ppm correction-free-cycle figure
      (95% CI [46, 156] ppm — QA independently spot-checked this against the underlying ppm-to-
      samples-per-cycle arithmetic and it is internally consistent, both with itself and with
      D-001's original 42.41 ppm at the low end of the CI) rather than continuing to cite only
      D-001's 42.41 ppm (`tasks.md` 10.5). Document explicitly whether `DriftThresholdSamples = 24`
      and `RequiredConsecutiveReadings = 3` (derived from 7.6 samples/cycle) still hold at ~18
      samples/cycle — expected finding is "unchanged, correction fires ~2.4x more often, not itself
      a defect," but this must be written down, not left as a silent discrepancy.
- [ ] `specs/ft8-decoder/spec.md` — check whether the existing correction-behaviour scenarios need
      updating. Likely not, by the same reasoning as the 9.1 dev-task's own check (the spec
      describes the *observable* contract — threshold, persistence gate, correction sizing/
      re-anchoring, sanity ceiling — not the internal formula for how `nominalCycleStart` advances)
      — but **verify, don't assume**; this file's own established convention (every prior round in
      this investigation has an explicit "verified, not assumed" note) applies here too. Not listed
      as its own `tasks.md` 10.x item — flagged here so it isn't silently skipped.
- [ ] Re-run `python3 tools/pre_merge_check.py` (HK-006) against all of the above before calling
      this ready for review (`tasks.md` 10.7).

## Validation plan

1. Unit tests first (`tasks.md` 10.3/10.4) — the multi-correction test (10.4's new test, plus the
   restored-tolerance sustained-drift test) is the fast, no-live-hardware falsification check for
   whether this fix actually closes the gap 9.1 left open. Confirm both before touching live
   hardware.
2. Re-run `pre_merge_check.py` (`tasks.md` 10.7).
3. Live re-confirmation (`tasks.md` 10.8) replaces 9.5 as this change's live acceptance gate. Reuse
   the HK-013 supervisor (`qa/endurance/2026-07-24-supervisor.sh`) — it is sound infrastructure,
   already live-validated, and two of its edge-case bugs are already recorded for anyone re-arming
   it. **All three required:**
   - (a) post-correction readings land near the noise floor against **both** their own and the
     preceding correction's magnitude (10.3/10.4's metric);
   - (b) correction magnitude reaches a plateau rather than climbing hour over hour;
   - (c) the pipeline-timing figure for **correction-free** windows sits at nominal 15.000 s —
     tested against nominal directly, not merely for absence of a trend (Decision 9's correction to
     how `H₀-3` was read in the 9.5 report: a flat *offset* is exactly what an accumulating-drift
     source looks like when read only as "flat = no trend").
   With this fix in place, corrections should be roughly two orders of magnitude smaller than 9.5's,
   so a plateau should be visible within 2-3 hours — no need to default straight to another
   multi-hour overnight round; extend only if the short round's evidence motivates it, same
   short-first discipline this investigation has used throughout.
4. Only after 10.8 passes should the HK-011 merge hold be reconsidered with the Captain
   (`tasks.md` 10.9). If 10.8 still fails, root-cause it from that run's own artefacts first (the
   way Decision 9 itself was derived) before reaching for a different correction architecture —
   Decision 9's diagnosis here is quantitative and closed, so a further failure would mean a
   *distinct* mechanism, not a reason to doubt this one.

## Not part of this handoff (tracked separately in `tasks.md`, no `src/` changes)

- **10.6** — offline, no-live-time session-wide DT-offset comparison against WSJT-X using the
  preserved WAV archive (`artefacts/20260724_live_run_2227/wav/`, 2,827 files) to close Decision 9
  Finding 4 (the `f57fa4d`/9.5 DT-offset observation). This is a data-analysis task against
  already-captured audio, not a code change — it can run independently of (and does not block) the
  `src/` fix above, and is QA-scoped rather than Developer-scoped. Falsifiable prediction recorded
  in `tasks.md`: the offset should track the cumulative signed correction sum, not sit flat.

## Cross-references

- `openspec/changes/fix-cycle-boundary-clock-drift/design.md` Decision 9 — the full five-finding
  derivation (correlation analysis, energy balance, the H₀-3 inversion, the DT-offset connection,
  the test-suite-already-caught-this finding), the fix, and the three recorded risks/trade-offs.
- `openspec/changes/fix-cycle-boundary-clock-drift/tasks.md` section 10 (10.1-10.9) — the checklist
  this document narrates.
- `qa/endurance/2026-07-25-40m-band-9.5-fail/report.md` — the 11h51m live round whose own raw
  artefacts (`artefacts/20260724_live_run_2227/corrections_table.csv`, both sub-session daemon logs)
  Decision 9 was derived from, without needing a new live run.
- `dev-tasks/2026-07-24-cycleframer-deviation-accounting-fix.md` — the 9.1/Decision 8 handoff this
  fix builds on (not replaces); its "Confirm the no-correction-fires path is unchanged" item carries
  the correction note explaining how its own ~80-sample tolerance widening was the earliest visible
  symptom of the bug this document fixes.
