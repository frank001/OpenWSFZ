# Follow-up: `CycleFramer` drift correction has no fast-path for an implausible one-off clock step

**Status:** deferred, not blocking `fix-cycle-boundary-clock-drift`. Captain sign-off (2026-07-23):
ship the correction as implemented; track this for later.

## Context

`fix-cycle-boundary-clock-drift` (`openspec/changes/fix-cycle-boundary-clock-drift/`) adds a
threshold-gated, capped correction to `CycleFramer.RunAsync` (`src/OpenWSFZ.Ft8/CycleFramer.cs`)
so the decode-cycle boundary tracks true UTC over long sessions instead of drifting unboundedly.

`design.md`'s risk section for this change proposed two mitigations for a large, one-time system
clock step being misread as accumulated device drift:

1. Cap the per-event correction to a small bounded sample count — **implemented**
   (`MaxCorrectionSamples = 32`).
2. *Optionally* detect an implausibly large single-reading deviation and skip correction that
   cycle with a logged warning, deferring to the next check — **not implemented** (design.md
   marked this optional).

## The gap

Only mitigation 1 was built. Traced by hand during QA review of the implementation: a genuine
large one-off host clock step (NTP stepping a clock that was very wrong at boot, a VM resume, a
host with no battery-backed RTC) is not detected as anomalous and skipped — it is chipped away at
exactly `MaxCorrectionSamples` (32 samples, ~2.7 ms) per 15 s cycle, monotonically, until fully
absorbed. For a 5-minute step this is on the order of **~19 days** of continuous per-cycle
corrections, each logged at Information level (per tasks.md 1.2, "rare, operationally
significant"). Under this scenario the log line is neither rare nor especially informative — it's
roughly a fortnight of one Information-level line every 15 seconds.

This does not violate any written spec scenario in `specs/ft8-decoder/spec.md` — no single
correction ever exceeds the documented cap — and the correction does provably converge (verified
by hand-tracing the arithmetic: each cycle's residual deviation shrinks by exactly the correction
applied, no oscillation or divergence). It is a gap between the design's stated intent ("no-op
until genuine, sustained drift... leave short/typical sessions unchanged") and actual behaviour
following a plausible, if uncommon, real-world event.

## Possible future work

- Implement design.md's optional mitigation: if a single-reading deviation exceeds some
  implausibly-large bound (e.g., a few seconds — clearly beyond anything a ~42 ppm-class device
  clock-rate error could produce even over many hours), skip correction for that cycle, log a
  distinct warning ("implausible clock deviation, skipping"), and re-check next cycle rather than
  slow-walking it.
- Consider rate-limiting or de-duplicating the resync Information log line if repeated
  corrections fire in a tight sequence, independent of the above.
- Add a unit test simulating a large one-off step followed by many subsequent cycles, asserting
  monotonic convergence (current tests only cover a single correction event, not the sequence).

## Addendum (2026-07-24): the persistence-gate fix makes this ~2x worse

`dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md` (a separate,
blocking live-evidence finding — the correction was firing every single cycle in production,
driven by pipeline latency, not this file's scenario) was fixed by requiring
`RequiredConsecutiveReadings` (3) consecutive same-sign, non-decreasing readings before a
correction fires, and raising `MaxCorrectionSamples` 32 → 48 (`design.md` Decision 4).

That change interacts with *this* file's scenario for the worse: after a correction fires, the
persistence streak resets to 0 (per Decision 4), so for a genuine large one-off step (whose
residual stays roughly constant every cycle after each tiny 48-sample chip), the mechanism must
*rebuild* a fresh 3-reading streak before firing again — one correction event every 3 cycles
instead of every cycle. Hand-computed for the same 5-minute-step scenario this file used
(`step_samples / cap * cycles_per_event * 15s / 86400`):

- Old (this file's original estimate): 32-sample cap, 1 correction/cycle → **~19.5 days**.
- New (post-persistence-gate): 48-sample cap, 1 correction per 3 cycles → **~39.1 days** — a
  **~2x slowdown**, not an improvement.

This does not change the "why deferred" reasoning below (still not a written-spec violation,
still a low-likelihood event, still provably convergent, no oscillation) — but it is new,
concrete information: the two dev-tasks' original cross-reference note ("the two should probably
be resolved together") turned out to be directionally right for a different reason than
expected — fixing one made the other's known gap measurably worse, not just "still open."
Flagging for the Captain's awareness before merge; not fixed here — implementing design.md's
optional "detect an implausible deviation and treat it differently from ordinary threshold-scale
readings" mitigation was outside what this implementation pass was scoped to do (see the
live-evidence dev-task's implementation notes), and remains deferred pending an explicit
decision, same as before.

## Why deferred rather than blocking

- Not a defect against any written acceptance criterion.
- Real-world likelihood of a multi-minute-scale step (as opposed to millisecond-scale NTP slew)
  is low.
- Fixing it now would mean returning to the Developer session for additional design + tests on a
  change already fully verified against its own spec; Captain elected to ship as-is and track
  this separately.
