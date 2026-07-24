# Developer handoff: fix `CycleFramer`'s drift-correction sizing (persistence gate fires correctly, but under-corrects)

**Status:** Ready for a Developer session. QA-scoped investigation and live re-test are done;
this document hands off the remaining `src/OpenWSFZ.Ft8/CycleFramer.cs` work per HK-011 — QA does
not implement this itself.

**Blocks:** `fix-cycle-boundary-clock-drift` (`openspec/changes/fix-cycle-boundary-clock-drift/`,
PR #108). `tasks.md` item 6.6 is annotated but left unchecked pending this fix. Do not consider
the merge hold lifted until a revised build has been re-validated (see Validation plan below).

## Context — what's already built and what's already wrong with it

`CycleFramer.RunAsync` gates its drift correction on persistence (`design.md` Decision 4,
implemented 2026-07-23 in response to
`dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md`):
`RequiredConsecutiveReadings = 3` consecutive same-sign, non-decreasing readings past
`DriftThresholdSamples` (24) must occur before a correction fires, and the fired correction is
capped at `MaxCorrectionSamples = 48`:

```csharp
if (driftStreakCount >= RequiredConsecutiveReadings)
{
    int correction = (int)Math.Clamp(
        Math.Round(deviationSamples),
        -MaxCorrectionSamples, MaxCorrectionSamples);
    // ... applies `correction`, re-anchors cycleStart, resets nominalCycleStart to match
}
```

**This persistence gate works correctly** — a fresh live endurance re-test
(`qa/endurance/2026-07-24-ce13e30/report.md`) confirms zero corrections fired during the first
~9 minutes despite every single reading exceeding threshold, because the readings (recurring
pipeline-scheduling latency, ~500–2400 samples) bounced around rather than persisting in one
direction. That part of the fix is sound; do not change the persistence-gating logic itself.

**The problem is what happens once persistence *does* confirm genuine drift.** Over the same
7h54m21s session, 20 corrections fired — every single one saturating the 48-sample cap — while
the underlying deviation climbed essentially unbounded:

| | Value |
|---|---|
| Deviation at session start | 964 samples |
| Deviation at last check before operator stop | 17,119 samples (1,426.55 ms) |
| Net growth over the session | +16,155 samples |
| Total removed by all 20 corrections (20 × 48) | 960 samples (~6% of the growth) |
| Net residual drift rate | ≈0.171 s/hour — same order of magnitude as the original, unfixed D-001 figure this whole change exists to eliminate |

Full per-correction data is in the report (`qa/endurance/2026-07-24-ce13e30/report.md` §3.2). The
mechanism fires at the right times, on the right readings — it just doesn't remove enough each
time to matter.

## Root cause

`MaxCorrectionSamples = 48` was sized (design.md Decision 4) as "a modestly larger cap [than the
original 32] to resolve [a threshold crossing] in fewer follow-on slew events" — reasoning about
the persistence gate's *delay* before a single crossing gets acted on, not about how large the
*confirmed, accumulated* deviation will actually be by the time three consecutive non-decreasing
readings satisfy the gate. In this run, deviation-at-fire-time ranged from ~1,700 to ~17,400
samples — the cap absorbed as little as 0.3% of what had already been confirmed as genuine.

Put differently: the cap's original job (design.md's Risks section) was protecting against a
**single, unconfirmed, possibly-implausible reading**. Once `RequiredConsecutiveReadings` has
already confirmed three consecutive same-sign, non-decreasing readings, that protection has
already been served by the persistence gate itself — capping the correction at that point no
longer guards against anything; it just throttles the fix's own remedy below the rate it needs
to keep up with confirmed reality.

## Proposed fix — absorb the confirmed deviation, don't cap it to a fixed quantum

**Once the persistence gate fires, correct by the (rounded) full accumulated deviation, not a
small fixed sample count.** Concretely, in the `if (driftStreakCount >= RequiredConsecutiveReadings)`
block, replace the `Math.Clamp(..., -MaxCorrectionSamples, MaxCorrectionSamples)` cap with either:

- **(a) No cap at all** — `int correction = (int)Math.Round(deviationSamples);` — simplest, and
  arguably correct: by definition, if the gate fired, the deviation has already been confirmed
  genuine and persistent, not a single anomalous reading. A large one-off host clock step
  (`StepClock`-style, `dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`)
  would now be fully absorbed the first time it satisfies persistence (3 cycles after the step)
  rather than chipped away over weeks — which is arguably the *correct* behaviour for a
  confirmed step, not a regression. Discarding/replaying samples for the correction never
  corrupts any window's content (see `design.md`'s existing discard/replay mechanism) — a large
  correction just means one unusually long (or short) real-time gap before the next window
  completes, not corrupted audio.
- **(b) A much larger, generous sanity ceiling** (e.g., a few seconds' worth of samples, or some
  fraction of `SamplesPerCycle`) purely to guard against a truly pathological `IClock` reading
  (a `DateTime` overflow, a multi-day misconfigured system clock) stalling the pipeline for an
  absurd length of real time. This keeps a safety net without reintroducing the sizing problem
  this document exists to fix — the ceiling should be sized so it is *never* expected to bind for
  any plausible device-drift or host-clock-step scenario, only for genuinely broken input.

**Recommend (b)** — it preserves a deliberate safety backstop (consistent with design.md's
original Risks-section intent) while being large enough that it doesn't reintroduce the same
under-correction problem this document is about. A concrete starting point to discuss in the
Developer session: something on the order of one full cycle's worth of samples (180,000) or a
fixed multi-second bound — several orders of magnitude above anything seen in this run's data
(max observed: 17,438 samples) or in the large-step scenario (5 minutes = 3,600,000 samples,
which would still exceed almost any sane ceiling and thus still slew — which is fine, see below).

**Interaction with the large-clock-step slow-convergence gap
(`dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`):** this fix should
substantially improve that scenario too, without being designed specifically for it. Under
option (a) or a generous (b), a confirmed 5-minute step would either be absorbed in far fewer
follow-on slew events than today's ~39 days, or (under (a)) in a single event. Worth re-checking
that dev-task's math against whatever ceiling is chosen, and updating its "deferred" status if
this fix resolves it as a side effect.

## What needs to change

- [ ] `design.md` — revise Decision 4 (or add a Decision 5) documenting the corrected sizing
      rationale: the persistence gate's confirmation, not a fixed quantum, should determine how
      much is corrected; a cap (if kept) exists only as a sanity ceiling against pathological
      input, not as a "slow slew" mechanism for confirmed drift.
- [ ] `specs/ft8-decoder/spec.md` — the "Bounded correction fires once accumulated deviation
      persists above the threshold" scenario currently asserts the correction is "no larger than
      the documented cap." Update to reflect that the correction now matches the confirmed
      deviation (bounded only by the revised sanity ceiling, not a small fixed quantum).
- [ ] `src/OpenWSFZ.Ft8/CycleFramer.cs` — change the correction-sizing line in the
      `driftStreakCount >= RequiredConsecutiveReadings` block per the Proposed fix above. Update
      the constant-derivation comment block above `DriftThresholdSamples`/`MaxCorrectionSamples`
      accordingly (it currently documents the *old* rationale for 48).
- [ ] `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — the existing
      `RunAsync_ConstantRateOffset_BoundedCorrectionFiresAtThreshold` and
      `RunAsync_OneOffLargeClockStep_CorrectionStaysWithinCap` tests assert the fired correction
      is `<= MaxCorrectionSamples` — these assertions need to change to match the new sizing
      (full-absorption, bounded only by the new sanity ceiling). Consider adding a new test that
      simulates many hours of continuous constant-rate drift (a loop of `RateClock`-style
      readings well beyond a handful of cycles) and asserts the *residual* deviation stays
      bounded near the noise floor after each correction, rather than growing session-over-session
      — this is the property this run's live data showed failing and unit tests didn't catch,
      precisely because the original tests only exercised a handful of cycles around a single
      correction event, not a long session.
- [ ] `tasks.md` — add a new section (7, following the existing numbering convention) tracking
      this fix, referencing this document and the endurance report.

## Validation plan

1. Unit tests first (fast, no live hardware) — confirm the revised sizing against the existing
   `RateClock`/`StepClock`/`BouncingClock` doubles, plus the new long-session-simulation test
   above.
2. Re-run `python3 tools/pre_merge_check.py` (HK-006) before considering this ready for review.
3. **Do not immediately jump to another 8-hour live endurance run.** Once the unit tests confirm
   bounded residual behaviour over a simulated long session, a shorter live re-confirmation (an
   hour or two, enough to observe several correction events at the new sizing) should be
   sufficient to confirm real-hardware behaviour matches the simulation, before committing to
   another full overnight/multi-hour session. Use the same device/setup as
   `qa/endurance/2026-07-24-ce13e30/report.md` for comparability.
4. Only after that re-validation should `tasks.md` 6.6 be checked off and the HK-011 merge hold
   be reconsidered.

## Cross-references

- `qa/endurance/2026-07-24-ce13e30/report.md` — the live endurance run and analysis this
  document is the direct follow-up to (§3.2, §5).
- `dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md` — the
  live-evidence finding that produced the persistence gate this fix builds on top of (that part
  is confirmed working; do not revisit it here).
- `dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md` — the related, already
  Captain-accepted-as-deferred one-off-step gap this fix likely also resolves as a side effect;
  revisit its status once this fix lands.
- `openspec/changes/fix-cycle-boundary-clock-drift/design.md` Decision 4 and Risks section — the
  design language this fix needs to reconcile (the "small, bounded... slew, not a step" framing
  needs updating to explain why full-absorption-once-confirmed is still consistent with the
  change's Goal of *bounding* drift, even though individual corrections may now be materially
  larger than 48 samples).
