# Developer handoff: fix `CycleFramer`'s deviation baseline for a correction's own real-time cost

**Status:** Ready for a Developer session. Design decision is made (`design.md` Decision 8,
Captain-approved 2026-07-24 evening); this document hands off the `src/OpenWSFZ.Ft8/CycleFramer.cs`
implementation and its tests per HK-011 — QA does not implement this itself. `tasks.md` section 9
tracks this work item-by-item; this document is the narrative companion.

**Blocks:** `fix-cycle-boundary-clock-drift` (`openspec/changes/fix-cycle-boundary-clock-drift/`,
PR #108). `tasks.md` items 6.6/7.6/8.6 are annotated but left unchecked — this is a *new* fix
attempt, not a continuation of any of those three; do not consider the merge hold lifted until
9.5's own live re-confirmation passes.

## Context — what's already confirmed, and what the fix needs to do

Three prior fix attempts against this change (fixed-cap, persistence-gated, size-to-confirmed-
deviation) were each defeated by live endurance testing — the correction fires exactly as designed
every time, but the underlying deviation never converges. `tasks.md` 8.7 (already implemented,
confirmed) isolated why, via two controlled unit tests in `CycleFramerTests.cs`
(`RunAsync_DiscardCorrectionOnRateLimitedSource_CostsProportionalRealTime`,
`RunAsync_ReplayCorrectionOnRateLimitedSource_DoesNotCostExtraRealTime`): a discard correction
genuinely costs real wall-clock time (waiting for extra raw samples to arrive from the real,
rate-limited capture source), while a replay correction genuinely costs *less* real time (reusing
already-buffered samples). Both confirmed against a controlled rate-limited source, no live
hardware needed, no flake across 5 consecutive runs.

**The specific bug, traced to exact code in `CycleFramer.RunAsync` (as of `f57fa4d`):**

```csharp
window         = new float[SamplesPerCycle];
filled         = 0;
cycleStart     = cycleStart.AddSeconds(CycleDurationSecs);
nominalCycleStart = nominalCycleStart.AddSeconds(CycleDurationSecs);   // <-- always flat 15.000s

// ... drift check computes: deviation = (_clock.UtcNow - nominalCycleStart)
```

`nominalCycleStart` — the purely-arithmetic baseline deviation is measured against — advances by a
flat `CycleDurationSecs` (15.000 s) every window, with no exception for the window immediately
following a correction. But that window's *actual* real-world fill time is not 15.000 s by
construction: a discard (`pendingSkipSamples > 0`, set when `correction > 0`) must wait to receive
`correction` extra raw samples from the real, rate-limited source before it can even start
accumulating; a replay (`correction < 0`) pre-fills `filled = replay` samples from the already-
captured previous window's tail, so it needs fewer new raw samples and completes sooner. The very
next deviation check therefore measures the correction's own necessary real-time cost as fresh,
apparently-genuine drift — reproducing almost exactly the size of the correction that supposedly
just fixed it. This is precisely what 8.7's isolated tests measured (discard window ≈1.10-1.60x an
ordinary window's real time, replay ≈0.55-0.95x) and what every live endurance run's "next
reading" data has shown since `1cebf81`.

## The fix (design.md Decision 8)

At the moment a correction fires (inside the `if (driftStreakCount >= RequiredConsecutiveReadings)`
block), record a one-shot pending time adjustment:

```csharp
double pendingNominalAdjustSeconds = correction / (double)SampleRate;
```

representing the genuine extra-or-reduced real time the *next* window will take to fill because of
this correction (positive for discard/lengthen, negative for replay/shorten — same sign convention
as `correction` itself). Apply it to `nominalCycleStart`'s *next* advance only:

```csharp
nominalCycleStart = nominalCycleStart.AddSeconds(CycleDurationSecs + pendingNominalAdjustSeconds);
pendingNominalAdjustSeconds = 0; // one-shot — must not persist past this single window
```

`cycleStart` (the reported, decoder-facing timestamp passed to `Ft8Decoder`) is **unaffected** —
this only changes the internal reference `nominalCycleStart` is compared against for the deviation
calculation, not what gets reported or which raw samples land in which window. The existing
discard/replay sample-routing logic (`pendingSkipSamples`, the `Array.Copy` replay tail-fill) does
not need to change at all.

**Implementation note on ordering:** `pendingNominalAdjustSeconds` needs to be declared outside the
`await foreach` loop (alongside `pendingSkipSamples`, `driftStreakCount`, etc.), set at the bottom
of the correction-fires branch (where `cycleStart`/`nominalCycleStart` are currently re-anchored),
and consumed at the top of the *next* iteration's window-close handling — i.e., the read-then-reset
of `pendingNominalAdjustSeconds` needs to happen at the `nominalCycleStart.AddSeconds(...)` line
itself, which runs once per window regardless of whether a correction is pending. Take care that a
correction firing on window N's close sets the pending value that must be consumed on window
*N+1*'s close (the very next iteration through that line), not window N's own advance (which has
already executed earlier in the same iteration, before the drift check that decides whether to
correct).

## What needs to change

- [ ] `src/OpenWSFZ.Ft8/CycleFramer.cs` — implement the above (`tasks.md` 9.1). Update the doc
      comment at the top of the class (the "Over a long-running session..." paragraph) to mention
      that the deviation baseline itself now accounts for a correction's own real-time cost, not
      just that a correction fires and re-anchors `cycleStart`.
- [ ] Confirm the no-correction-fires path is unchanged (`tasks.md` 9.2) — the existing
      `RunAsync_NoClockDeviation_NoCorrectionFires` and similar tests asserting `cycleStart`
      advances by exactly 15 seconds absent drift must continue to pass with zero modification.
      `pendingNominalAdjustSeconds` must be exactly 0 whenever no correction has just fired.
- [ ] `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — new tests (`tasks.md` 9.3), extending 8.7's
      `FeedSamplesAtRealRate` rate-limited-source harness (do **not** use the existing zero-delay
      feed helpers for these — they cannot exercise the real-time-cost mechanism this fix targets,
      same reasoning as 8.7's own tests). For both a discard-triggering and a replay-triggering
      `RateClock` offset: after the correction fires, assert the **deviation reading** on the
      window immediately following the corrected one is near the noise floor (e.g., within
      `DriftThresholdSamples` or a small multiple, not a hardcoded absolute — keep the relative-
      ratio/self-calibrating discipline 8.7 established, per `test-delay-debt.md`/Gate G10), not
      near the correction's own magnitude. This is the direct falsification test for whether this
      fix actually resolves non-convergence — if it passes, that's strong evidence before ever
      needing another live run; if it fails, the mechanism trace above has an error worth finding
      now rather than after another multi-hour endurance session.
- [ ] `design.md` — Decision 8 is already written; no further changes expected unless
      implementation surfaces a detail the decision got wrong (in which case, amend it in place
      per this change's established pattern, don't silently diverge from what's documented).
- [ ] `specs/ft8-decoder/spec.md` — check whether the existing "Correction fires once accumulated
      deviation persists above the threshold" scenario needs updating. Likely not (this fix changes
      *how* deviation is computed post-correction, not the correction/firing behaviour itself,
      which the spec already describes correctly) — but verify rather than assume.
- [ ] `tasks.md` — mark 9.1-9.4 done as they land; this document does not need updating unless
      implementation deviates from what's written here (in which case, note the deviation here for
      the record, same convention as every other dev-task in this investigation).

## Validation plan

1. Unit tests first (fast, no live hardware; `tasks.md` 9.3) — this is the actual novelty here:
   for the first time in this investigation, the specific property every live endurance run has
   checked for ("does the post-correction reading drop toward the noise floor?") is directly
   testable in an isolated, deterministic unit test, not something that requires hours of live
   capture to observe. Confirm it passes before touching live hardware at all.
2. Re-run `python3 tools/pre_merge_check.py` (HK-006) before considering this ready for review
   (`tasks.md` 9.4).
3. **Do not skip straight to a multi-hour live run.** Per this investigation's established
   "short-first" discipline (confirmed repeatedly by the Captain across 7.6/8.6's rounds): a short
   live session first (30-60 min), explicit checkpoint to decide stop-vs-extend from evidence.
   Same device/setup as `ce13e30`/`1cebf81`/`29041f7`/`f57fa4d` for comparability
   (`'Microphone (2- USB Audio CODEC )'`, WASAPI, 20 m).
4. Only after that live re-confirmation (`tasks.md` 9.5) actually shows the post-correction
   reading settling near the noise floor — not the oscillating-but-climbing pattern every prior
   round has shown — should the HK-011 merge hold be reconsidered with the Captain (`tasks.md`
   9.6). If it still doesn't converge, escalate to one of the two fallback fix shapes recorded in
   design.md Decision 8 (continuous rate-tracking, or reopening Decision 1's scope boundary) rather
   than re-tuning this fix's own constants in isolation — there aren't any tunable constants in
   this fix to begin with, which is itself a signal that a non-convergent result here would mean
   the mechanism trace has a gap, not that a parameter needs adjusting.

## Cross-references

- `openspec/changes/fix-cycle-boundary-clock-drift/design.md` Decision 8 — the full mechanism
  trace, the fix rationale, and the two fallback shapes if this one doesn't converge.
- `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — 8.7's `RunAsync_DiscardCorrectionOnRateLimitedSource_CostsProportionalRealTime`/
  `RunAsync_ReplayCorrectionOnRateLimitedSource_DoesNotCostExtraRealTime` and the `FeedSamplesAtRealRate`
  helper this fix's own tests (9.3) should extend, not duplicate.
- `qa/endurance/2026-07-24-f57fa4d/report.md` — the most recent live run (evening of the same day
  this decision was made), including the cross-run rate-consistency finding (≈31-35 samples/min
  across four independent sessions) that motivated treating this as one stable, fixable mechanism
  rather than session-specific noise.
- `qa/endurance/2026-07-24-1cebf81/report.md`, `qa/endurance/2026-07-24-ce13e30/report.md`,
  `qa/endurance/2026-07-24-29041f7/report.md` — the three prior live runs against this change; all
  showed the same qualitative non-convergence this fix targets.
