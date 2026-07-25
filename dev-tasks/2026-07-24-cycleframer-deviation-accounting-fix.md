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

- [x] `src/OpenWSFZ.Ft8/CycleFramer.cs` — implement the above (`tasks.md` 9.1). Update the doc
      comment at the top of the class (the "Over a long-running session..." paragraph) to mention
      that the deviation baseline itself now accounts for a correction's own real-time cost, not
      just that a correction fires and re-anchors `cycleStart`.
      Implemented as specified — `pendingNominalAdjustSeconds` declared alongside the other
      per-window state, set inside the `driftStreakCount >= RequiredConsecutiveReadings` branch
      right after `correction` is computed, consumed at the top of the next window-close's
      `nominalCycleStart.AddSeconds(...)` line, then zeroed. Class doc comment got a new closing
      paragraph explaining the mechanism.
- [x] Confirm the no-correction-fires path is unchanged (`tasks.md` 9.2) — the existing
      `RunAsync_NoClockDeviation_NoCorrectionFires` and similar tests asserting `cycleStart`
      advances by exactly 15 seconds absent drift must continue to pass with zero modification.
      `pendingNominalAdjustSeconds` must be exactly 0 whenever no correction has just fired.
      Confirmed unmodified for the true no-correction-fires tests. One *repeated*-correction test
      (`RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`, which
      exercises ~8 corrections over a 24-window session) needed its tolerance updated — that's a
      correction-*fires* scenario, outside this task's "no behaviour change" guarantee. See
      `tasks.md` 9.2's own note for the full explanation; short version: 9.1 legitimately shifts
      subsequent-correction timing/sizing over a long multi-correction session (nominalCycleStart's
      trajectory feeds into when/how large the *next* correction is), and the residual that test
      measures settles into a new, still-bounded, still-non-growing steady-state plateau (~80
      samples higher than before) rather than growing unboundedly — not a regression.
      > **CORRECTION (Architect, 2026-07-25 — design.md Decision 9, Finding 5): this call was
      > wrong, and it was the earliest available warning of why 9.5 later failed live.** The ~80-
      > sample residual shift was *not* a benign new plateau — it is the `c_prev` re-injection
      > caused by `nominalCycleStart = cycleStart` discarding the very divergence 9.1 creates.
      > This is the only existing test that fires *many* corrections in sequence, so it is the only
      > one positioned to see the defect at all, and its tolerance was widened rather than the
      > shift being root-caused. Restoring the original tolerance is now an acceptance criterion
      > for the fix (`tasks.md` 10.4). Lesson for future rounds: when the *only* multi-event test
      > in the suite moves under a change whose whole subject is multi-event accounting, that is
      > signal, not tolerance noise.
- [x] `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — new tests (`tasks.md` 9.3), extending 8.7's
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
      Implemented, with two deviations from this plan worth recording:
      1. **`RateClock` cannot be used at all for this specific test.** `RateClock`'s reading is a
         pure function of read-count, completely decoupled from real elapsed time — hand-deriving
         the numbers before writing any code showed that applying the fix against a `RateClock`
         actually makes the post-correction reading *larger*, not smaller (confirmed empirically
         too: the pre-existing sustained-drift test, which does use `RateClock`, needed a *looser*
         tolerance post-fix, not a tighter one — see the 9.2 note above). This fix is only
         meaningful against a clock whose reading genuinely reflects the correction's real-time
         cost, which `RateClock` never does by construction.
      2. **A real-elapsed-time-based clock (the natural first choice) was fatally flaky and had to
         be replaced.** First attempt scaled actually-measured `DateTime.UtcNow` deltas ~35x (to
         compress a 15 s nominal cycle into a sub-second test window) — correct in principle, but
         any OS-scheduler/thread-pool hiccup anywhere in the test process got amplified by that
         same 35x factor into thousands of spurious samples, swamping the intended ~30-45k-sample
         signal (observed directly: a 247 000-sample reading where ~45 000 was expected on one
         run). Replaced with a deterministic `SampleCountClock`: true UTC derived from the exact,
         test-controlled count of raw samples delivered by the still-genuinely-rate-limited feed,
         divided by an assumed true device sample rate — physically equivalent to a real device
         clock-rate error, but immune to scheduler jitter since the count is advanced by this
         test's own code rather than by re-measuring wall time. 5/5 clean repeated local runs.
      Also note: the "near the noise floor" bound in the implemented tests is deliberately NOT
      near-zero (used `< 60%` of the correction's own magnitude, not `< DriftThresholdSamples` or
      a small multiple of it as this plan originally suggested) — hand-deriving the exact numbers
      showed this fix only ever cancels the correction's own real-time cost, not the window's
      ordinary ongoing per-cycle device-rate contribution (structurally ~1/3 of the correction's
      magnitude, given the 3-consecutive-checks persistence gate) — see the tests' own inline
      comments and the 9.2 note above for the same residual showing up in the sustained-drift
      test. The bound still clearly separates the fixed case (~25-42%, empirically) from the
      unfixed case (~125-142%, hand-derived, not re-tested against old code).
- [x] `design.md` — Decision 8 is already written; no further changes expected unless
      implementation surfaces a detail the decision got wrong (in which case, amend it in place
      per this change's established pattern, don't silently diverge from what's documented).
      No amendment needed — Decision 8's mechanism trace and fix description held up exactly as
      written; the two deviations above are test-construction details, not corrections to the
      decision's own reasoning.
- [x] `specs/ft8-decoder/spec.md` — check whether the existing "Correction fires once accumulated
      deviation persists above the threshold" scenario needs updating. Likely not (this fix changes
      *how* deviation is computed post-correction, not the correction/firing behaviour itself,
      which the spec already describes correctly) — but verify rather than assume.
      Verified, not assumed: the spec describes the observable contract (threshold, persistence
      gate, correction sizing/re-anchoring, sanity ceiling) entirely in terms of "the accumulated
      deviation between the nominal cycle-boundary sequence and the injected IClock's wall-clock
      reading" — it never specifies the internal formula for how that nominal sequence advances,
      so 9.1's fix (an internal-bookkeeping-only change) doesn't contradict anything written. No
      spec change made.
- [x] `tasks.md` — mark 9.1-9.4 done as they land; this document does not need updating unless
      implementation deviates from what's written here (in which case, note the deviation here for
      the record, same convention as every other dev-task in this investigation).
      9.1-9.4 marked done in `tasks.md`, each with a short outcome note. 9.4
      (`pre_merge_check.py`) result: READY, every gate passed. 9.5 (live re-confirmation) and 9.6
      (Captain sign-off on the HK-011 merge hold) are explicitly NOT done — 9.5 needs real
      hardware and this session's Validation Plan (below) already says not to skip straight to a
      live run without a checkpoint; 9.6 is the Captain's call either way.

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

## QA review follow-ups (2026-07-24, non-blocking — TODO before/at next Developer session touching this test file)

Raised during QA review of the implementation above; approved with these noted, not required
before the short live re-confirmation run (9.5):

- [ ] **`SampleCountClock`/`FeedSamplesAtRealRateTrackingDelivery` producer/consumer race
      (`CycleFramerTests.cs`, tasks.md 9.3 tests).** `RecordSamplesDelivered` is called on the
      producer side immediately before `writer.WriteAsync(chunk)`, on a separate task from the
      consumer that actually processes that chunk. In principle the producer could race a chunk
      ahead of what the consumer has processed by the moment a deviation reading is taken,
      understating "delivered so far." In practice the 10ms `RealRateChunkDelay` per chunk dwarfs
      the trivial in-loop `Array.Copy` cost, which is presumably why this hasn't flaked across
      repeated local runs (4/4 in QA review, 5/5 per the implementer). Low priority — only worth
      fixing if this test ever flakes on a loaded CI runner. Fix would be moving the
      `RecordSamplesDelivered` call to the consumer side (after the sample actually lands in
      `window`) rather than the producer side.
- [ ] **Bare `0.6` ratio literal in the two 9.3 assertions, not a named constant.** Consistent with
      this file's existing style (8.7's tests use bare `1.10`/`1.60`/`0.55`/`0.95` the same way), so
      not a real inconsistency — but worth considering a named constant (e.g.
      `MaxPostCorrectionRatioOfOwnMagnitude`) with the derivation comment attached to the constant
      rather than duplicated at each call site, next time this file's magic-number style is
      revisited as a whole (not worth a one-off change just for this).

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
