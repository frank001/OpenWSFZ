## 1. Design finalisation

- [x] 1.1 Finalise the drift-detection threshold and per-event correction cap (`design.md` Open
      Questions) — derive concrete constants from the ~42 ppm-scale error QA measured
      (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/phase3_clockrate_results_usbcodec.json`),
      with a short written rationale in code comments (mirrors the existing `CycleFramer`
      documentation style — see the class-level `<summary>` and `R3`-style inline notes already
      present).
      **Done:** `DriftThresholdSamples = 24` (~2.0 ms, ~3 cycles at the measured -42.41 ppm
      rate), `MaxCorrectionSamples = 32` (~2.7 ms, absorbs a full threshold crossing in one
      event). Rationale documented in `CycleFramer.cs` as a code comment above the constants.
- [x] 1.2 Decide and document whether a resync event is logged (Debug or Information level) —
      design.md leans yes; confirm and pick the level/format consistent with existing
      `CycleFramer` log lines (`CycleFramer started; ...`, `Window emitted ...`).
      **Done:** Information level (rare, operationally significant — matches "CycleFramer
      started", not per-cycle "Window emitted" which is Debug). Format: "Cycle boundary resync:
      accumulated deviation = ... samples (... ms); applying ... sample correction; cycleStart
      re-anchored to ...".

## 2. Implementation

- [x] 2.1 Add the accumulated-deviation tracking to `CycleFramer.RunAsync` (nominal
      arithmetic cycle-boundary sequence vs. `_clock.UtcNow`), threshold-gated per design.md
      Decision 3.
- [x] 2.2 Implement the bounded correction: adjust the next window's target sample count by a
      small, capped amount and re-anchor `cycleStart` to the corrected wall-clock value at that
      boundary, per design.md Decision 2. Ensure the correction can be either sign (window
      slightly shorter or longer) since drift direction is device-dependent, not assumed
      negative.
      **Implementation note (resolves a design/code gap found during implementation):**
      `Ft8Decoder.DecodeAsync` hard-throws `ArgumentException` unless `pcm.Length` is exactly
      180 000 (`ExpectedSampleCount`), and proposal.md's stated Impact scopes this change to
      `CycleFramer.cs` only — so the emitted window array can never vary in length. "Target
      sample count" is therefore implemented as the count of *raw* incoming samples mapped into
      the next window, not the emitted array size: a "lengthen" correction (device running slow)
      discards a few incoming raw samples between windows (a leap-sample deletion, never assigned
      to any window); a "shorten" correction (device running fast) replays the last few real
      samples from the tail of the window just emitted as the lead-in of the next window (a
      bounded overlap of real audio, never synthetic silence). Every emitted window remains
      exactly 180 000 samples always — zero downstream/decoder changes required.
- [x] 2.3 Cap a single correction event's magnitude so one anomalous/implausible `IClock`
      reading (e.g. a host clock step) cannot produce an unbounded jump — per design.md's risk
      mitigation.
- [x] 2.4 Add the resync log line decided in 1.2, if any.

## 3. Tests

- [x] 3.1 Unit test: no correction fires when `IClock.UtcNow` advances in exact lock-step with
      the nominal cycle-boundary sequence across many emitted windows (spec scenario "No
      correction fires for a session with no clock deviation").
      **Done:** `RunAsync_ClockInLockStep_NoCorrectionFires`, using a deterministic `RateClock`
      test double (advances by a fixed amount per read — avoids racing `FakeClock.Advance()`
      calls against RunAsync's internal async scheduling).
- [x] 3.2 Unit test: a bounded correction fires once accumulated deviation (simulated via a
      fake `IClock` advancing at a constant rate offset from nominal) exceeds the threshold —
      assert the correction is within the documented cap and `cycleStart` is re-anchored, not
      just arithmetically advanced (spec scenario "Bounded correction fires once accumulated
      deviation exceeds the threshold").
      **Done:** `RunAsync_ConstantRateOffset_BoundedCorrectionFiresAtThreshold`.
- [x] 3.3 Unit test: a single implausibly large one-off `IClock` deviation does not produce a
      correction exceeding the documented per-event bound (spec scenario "A single implausibly
      large clock deviation does not trigger a single large correction").
      **Done:** `RunAsync_OneOffLargeClockStep_CorrectionStaysWithinCap`, using a `StepClock`
      test double (permanent +5 min step simulating an operator/NTP host clock step).
- [x] 3.4 Confirm existing `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` coverage (leading-
      silence alignment, window emission, cancellation) still passes unmodified — the
      correction must be provably inert for every existing test's `IClock` usage.
      **Done:** all 15 tests in the file pass (12 pre-existing + 3 new). Note: the pre-existing
      tests all use a `FakeClock` that is never advanced during `RunAsync`, so the correction
      does engage on windows after the first (the fixed clock legitimately diverges from the
      ever-advancing nominal sequence) — but its effects are provably inert with respect to what
      those tests actually assert: every emitted window's length invariant (exactly
      `SamplesPerCycle`), and every dial-frequency/cycleStart assertion, are unaffected because
      corrections only ever change which raw samples land in windows *after* the one being
      checked (window 0's own content/cycleStart, which is all several existing tests assert on,
      is never touched).
      **Updated (see section 6):** re-confirmed with the persistence-gate mechanism in place —
      all 16 tests in the file pass: the 12 original pre-existing tests (unmodified) + the
      lock-step fix-cycle test (unmodified, no deviation ever) + 2 revised fix-cycle tests
      (now persistence-gate-aware) + 1 new live-evidence reproduction test.

## 4. Verification

- [x] 4.1 Run `python3 tools/pre_merge_check.py` — full gate (G9a, Release build+tests, G3
      traceability, G8 openspec validate, G9b, AOT publish) before calling this ready for merge,
      per HK-006.
      **Done (pre-live-evidence-fix run):** all gates PASS — G9a doc/VERSION, Release build,
      UDP-margin lint, G10 lint, full test suite (all projects, incl. 297/297
      `OpenWSFZ.Ft8.Tests`), G3 traceability, WSL Debian compile+test, G8 openspec strict
      validation, self-contained publish, AOT publish. Result: READY.
      **Superseded by section 6** — `CycleFramer.cs`/`CycleFramerTests.cs` changed again to
      address the live-evidence finding below; this gate must be re-run against that code before
      the change is ready for merge again (see 6.4).
- [x] 4.2 openspec archive workflow: confirm `openspec validate --strict` passes for this
      change before archiving.
      **Done:** confirmed as part of 4.1's G8 run — `✓ change/fix-cycle-boundary-clock-drift`
      (57/57 items passed, 0 failed). Re-confirm as part of 6.4's re-run.

## 5. Suggested follow-up validation (not blocking merge)

- [ ] 5.1 Once merged, re-run the Tight-class and Isolated-class replay pilots
      (`qa/rr-study/results/2026-07-23-d001-tight-class-replay/`,
      `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/` harnesses)
      against a corrected build to measure how much of the ~23.4% Isolated-class
      Decoded-on-replay gap this fix actually recovers. Needs live audio hardware and session
      time — explicitly not a merge gate for this change; track as a separate QA follow-up.

## 6. Live-evidence fix: correction fired every cycle in production (dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md)

A live pre-merge validation run (before this section's work) found the correction engaging on
every single 15 s cycle from cycle 1, driven by a real capture pipeline's own recurring
scheduling latency (WASAPI callback jitter / `Channel<float[]>` backpressure / thread-pool
contention with concurrent native decode), not the ~42 ppm-scale device clock-rate error this
change targets. See the dev-task for full evidence; see `design.md` Decision 4 for the chosen
mechanism.

- [x] 6.1 Persistence-gate the correction: require `RequiredConsecutiveReadings` (3) consecutive
      drift-check readings — same sign, non-decreasing magnitude, each clearing
      `DriftThresholdSamples` — before a correction actually applies, instead of reacting to any
      single reading. **Done:** `CycleFramer.RunAsync`, new `driftStreakCount`/`driftStreakSign`/
      `driftStreakMagnitude` local state; `RequiredConsecutiveReadings = 3` constant.
- [x] 6.2 Re-derive the correction cap for the new mechanism: `MaxCorrectionSamples` raised
      32 → 48, reasoned from persistence-gating's delayed-reaction effect (accumulated deviation
      at fire time is typically larger than a single-cycle crossing), not from the noisy live
      trace directly. `DriftThresholdSamples` intentionally left at 24 — raising it to clear the
      observed pipeline noise ceiling (~500-2400 samples) would make genuine drift take ~80+
      minutes to become a threshold candidate at all without improving noise rejection, since the
      persistence gate already does that job. **Done**, see `CycleFramer.cs` constant comments
      and `design.md` Decision 4.
- [x] 6.3 Add Debug-level per-check instrumentation (deviation samples/ms, persistence streak
      count) within `CycleFramer.cs`, so a future live run has the data to further isolate or
      tune this without needing a code change first. **Done.**
      **Explicitly deferred, not done here:** stage-by-stage timestamps in `WasapiAudioSource.cs`
      (WASAPI `DataAvailable` firing time, `Channel<float[]>` enqueue/dequeue instants) to isolate
      the recurring latency's proximate cause — this change's `proposal.md` Impact section scopes
      `Code:` to `src/OpenWSFZ.Ft8/CycleFramer.cs` only; instrumenting the capture layer is a
      scope expansion that needs its own decision (a proposal.md amendment or a follow-on change),
      not something to fold in silently. Flagged for the Captain/Architect as a separate
      follow-up, not done in this pass.
- [x] 6.4 Tests: revise `RunAsync_ConstantRateOffset_BoundedCorrectionFiresAtThreshold` and
      `RunAsync_OneOffLargeClockStep_CorrectionStaysWithinCap` for persistence-gated timing; add
      `RunAsync_RecurringNonMonotonicDeviation_NeverFiresCorrection`, replaying the dev-task's
      logged second-session sample sequence verbatim (1162.5, 814.1, 1326.1, 1181.4, 772.2,
      547.7, 1016.1 samples) through a new `BouncingClock` test double, asserting zero corrections
      fire across it. **Done** — see `CycleFramerTests.cs`.
- [x] 6.5 Re-run `python3 tools/pre_merge_check.py` (full gate, per HK-006) against this section's
      changes before calling the change ready for merge again.
      **Done:** all gates PASS — G9a doc/VERSION, Release build, UDP-margin lint, G10 lint, full
      test suite (all projects, incl. 298/298 `OpenWSFZ.Ft8.Tests` — up one from the
      pre-live-evidence-fix run), G3 traceability, WSL Debian compile+test, G8 openspec strict
      validation (57/57, incl. this change's revised spec.md), self-contained publish, AOT
      publish. Result: READY.
- [ ] 6.6 Re-run the same live setup used to surface this finding (same device, same log-capture
      technique — see the dev-task's "Recommended next steps" 1 and 3) against the revised
      implementation, to confirm the correction goes quiet during ordinary operation and only
      engages for genuine, sustained, multi-cycle drift. Needs live audio hardware and session
      time; the Captain's HK-011 pre-push sign-off should treat this as a precondition for
      un-holding the merge, consistent with the dev-task's own "Disposition" section.
      **Attempted 2026-07-24 — BLOCKING finding, still open, remains unchecked:**
      `qa/endurance/2026-07-24-ce13e30/report.md` (7h54m live session, same device). The
      persistence gate correctly rejected pipeline-latency false positives (0 corrections in the
      first ~9 min despite every reading exceeding threshold), but over the full session the
      accumulated deviation climbed from 964 to 17,119 samples (net +16,155) while 20 corrections
      removed only 960 samples total (~6% of the growth) — the mechanism fires correctly but does
      not bound cumulative drift, contradicting design.md's Goal #1. Net residual rate ≈0.171 s/hr,
      order-of-magnitude matching the original unfixed D-001 figure this change exists to
      eliminate. See the report's §3.2/§5 for the full analysis and a proposed design direction
      (size the correction to the confirmed deviation once persistence fires, not a small flat
      cap). Do not un-hold the merge on this run's evidence.
