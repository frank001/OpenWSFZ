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
      cap). Do not un-hold the merge on this run's evidence. **Superseded by section 7's sizing
      fix below** — 6.6's live re-run must be repeated against that revised code before this item
      can be checked off.

## 7. Correction-sizing fix: persistence gate confirms correctly but under-corrects (dev-tasks/2026-07-24-cycleframer-correction-sizing-fix.md)

Follow-up to 6.6's endurance re-test finding above. Full root cause, options, and rationale are in
the dev-task; chosen approach and full rationale are recorded as `design.md` Decision 5.

- [x] 7.1 `design.md`: add Decision 5 documenting the corrected sizing rationale — the
      persistence gate's confirmation, not a fixed quantum, now determines how much is corrected;
      the renamed `CorrectionSanityCeilingSamples` exists only as a backstop against pathological
      input, not as a slow-slew mechanism for confirmed drift. **Done.**
- [x] 7.2 `specs/ft8-decoder/spec.md`: update the "correction fires once accumulated deviation
      persists above threshold" and "single implausibly large deviation" scenarios to reflect
      that the correction now matches the confirmed deviation, bounded only by the revised sanity
      ceiling. **Done.**
- [x] 7.3 `src/OpenWSFZ.Ft8/CycleFramer.cs`: replace the `Math.Clamp(..., -MaxCorrectionSamples,
      MaxCorrectionSamples)` cap in the `driftStreakCount >= RequiredConsecutiveReadings` block
      with a clamp against a renamed `CorrectionSanityCeilingSamples` constant, sized to one full
      15 s cycle (180,000 samples @ 12 kHz) — roughly an order of magnitude above the endurance
      run's max observed deviation-at-fire (17,438 samples) and well below the ~3,600,000 samples
      a 5-minute host clock step would produce, so genuine drift/step scenarios are unaffected by
      the ceiling while a truly pathological reading still cannot produce an unbounded jump.
      Updated the class-level `<summary>` and the constant-derivation comment block to match.
      **Done.**
- [x] 7.4 `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs`: updated
      `RunAsync_ConstantRateOffset_BoundedCorrectionFiresAtThreshold` (wording only — the test's
      48-sample scenario stays well under the new ceiling, so it still fully absorbs and the
      numeric assertion is unchanged) and renamed/revised
      `RunAsync_OneOffLargeClockStep_CorrectionStaysWithinCap` →
      `RunAsync_OneOffLargeClockStep_CorrectionStaysWithinSanityCeiling` (now asserts against the
      much larger `CorrectionSanityCeilingSamples`, still well below the simulated 5-minute step).
      Added `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`: a
      24-window simulated session (~8 correction events at an exaggerated 5 ms/cycle offset)
      asserting residual deviation from the true `IClock`-derived boundary stays bounded near the
      noise floor after every firing, and that the late-session peak residual is not meaningfully
      larger than the early-session peak — the property the endurance run found failing and the
      earlier single-correction-event tests could not have caught. **Done** — all 17 tests in the
      file pass (16 pre-existing + 1 new).
- [x] 7.5 Re-run `python3 tools/pre_merge_check.py` (HK-006) against this section's changes
      before calling the change ready for merge again.
      **Done:** all gates PASS — G9a doc/VERSION, Release build, UDP-margin lint, G10 lint, full
      test suite (all projects, incl. 299/299 `OpenWSFZ.Ft8.Tests` — up one from section 6's run),
      G3 traceability, WSL Debian compile+test, G8 openspec strict validation, self-contained
      publish, AOT publish. Result: READY.
- [ ] 7.6 Live re-confirmation: per the dev-task's Validation plan, a shorter (1-2 hour) live
      re-run against the same device/setup as `qa/endurance/2026-07-24-ce13e30/report.md`, to
      confirm real-hardware behaviour matches the simulated long-session test above, before
      committing to another full overnight/multi-hour session. Only after that re-validation
      should 6.6 be checked off and the HK-011 merge hold be reconsidered.
      **Run 2026-07-24 — BLOCKING finding, still open, remains unchecked:**
      `qa/endurance/2026-07-24-1cebf81/report.md` (6h16m live session, same device family, 20 m).
      The sizing formula itself fired exactly per Decision 5 — all 10 corrections matched their
      confirmed deviation to the sample, none within an order of magnitude of the sanity ceiling —
      but every single correction left the very next drift-check reading within ±4% of the
      pre-correction value (at scales from 1,200 to 13,800 samples), and the underlying reading
      climbed steadily across the whole session largely independent of when corrections fired.
      The fix is sized correctly but does not converge on real hardware — see the report's
      §3.2–3.3/§5 and the follow-on dev-task for the full analysis, ruled-out explanations, and a
      working hypothesis (processing/scheduling delay rather than genuine capture-clock drift).
      **Superseded by section 8's root-cause instrumentation below** — 6.6/7.6 cannot be checked
      off until that investigation lands and this same live setup is re-run against its outcome.

## 8. Root-cause instrumentation: correction is sized correctly but does not converge on real hardware (dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md)

Follow-up to 7.6's live re-confirmation finding above. Unlike sections 6 and 7, this is not yet a
known fix to implement — the dev-task's own conclusion is that the proximate cause is not
isolated, and re-tuning `CorrectionSanityCeilingSamples`/`DriftThresholdSamples`/
`RequiredConsecutiveReadings` again without isolating it first is explicitly discouraged (dev-task
Recommended next steps, item 3). This section tracks the investigation, not a pre-chosen
implementation.

- [x] 8.1 Instrument each relevant pipeline stage with timestamps — WASAPI `DataAvailable` firing
      time, `Channel<float[]>` enqueue/dequeue instants, and `CycleFramer`'s own processing
      instant relative to when it reads `_clock.UtcNow` — to isolate where the measured
      "deviation" actually originates: genuine capture-rate mismatch vs. `CycleFramer`'s own
      loop-scheduling delay vs. something else. This is the same instrumentation recommended and
      not yet done in `dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md`
      Recommended Next Step 1 (deferred there as a scope expansion beyond `CycleFramer.cs` —
      touching `WasapiAudioSource.cs` needs its own scope decision, a `proposal.md` amendment or
      follow-on change, same as noted at 6.3). Two independent live runs (that dev-task's session
      and this one) now motivate it.
      **Done:** scope widened via a `proposal.md` Impact amendment (Captain's explicit choice —
      see `design.md` Decision 6). Debug-level, periodically-aggregated (not per-event —
      `DataAvailable` fires ~50 Hz) diagnostic timing added at three stages:
      `WasapiAudioSource.cs` (`DataAvailable` inter-arrival cadence, resampler-drain-to-enqueue
      latency, flushed every 200 firings ≈ 4 s), `CaptureManager.cs` (chunk-receive cadence and
      outer-channel write latency, flushed every 200 chunks — the platform-agnostic point
      downstream of all three `IAudioSource` implementations, so this covers `arecord`/`sox` too
      for free), and `CycleFramer.cs` (real wall-clock inter-window elapsed time and
      chunk-dequeue-gap stats, logged once per cycle alongside the existing drift-check line).
      All new timestamps use `DateTime.UtcNow` directly, never `_clock.UtcNow` — the
      `RateClock`/`StepClock`/`BouncingClock` test doubles model drift purely as a function of
      `_clock.UtcNow`'s read count, so any additional read there would have silently corrupted
      their arithmetic. New test coverage:
      `CycleFramerTests.RunAsync_WindowCloses_LogsPipelineTimingDebug` and
      `CaptureManagerTests.StartAsync_AfterManyChunks_LogsPeriodicCadenceDebug`; all 18
      `OpenWSFZ.Ft8.Tests` `CycleFramerTests` and all 20 `OpenWSFZ.Audio.Tests` pass. Not yet
      exercised live — see 8.6.
- [x] 8.2 Reconcile against `qa/endurance/2026-07-24-ce13e30/report.md`'s decode-elapsed-time
      finding specifically: that run explicitly ruled out decode-side slowdown (elapsed times flat
      300–600 ms across its whole session), while `qa/endurance/2026-07-24-1cebf81/report.md`
      found elapsed times growing +19.6% (508 ms → 607 ms, first-100 vs last-100 cycles) alongside
      `hashTableRejectCount` growing ~17x. Re-check `ce13e30`'s raw log with the same first-N/last-N
      method used in the newer report before treating either "ruled out"/"contributing factor"
      conclusion as settled — the two runs' evidence currently disagrees on a checkable point, not
      just on interpretation.
      **Done:** re-checked both raw logs with the same method plus a full-session decile
      breakdown + linear regression. Neither original framing survives: `ce13e30`'s "flat, no
      growth trend" claim is wrong (real ~24% decrease, r=−0.56, one mid-session step-down, not
      noise); this run's "+19.6% growth" headline is real as an endpoint comparison but not backed
      by a whole-session trend (r=+0.06, essentially flat) — driven by a noisy final decile.
      `hashTableRejectCount` could not be reconciled at all — neither raw log contains it (ad hoc
      `/api/v1/status` sampling only), confirming 8.4's premise. Full numbers and both reports'
      errata: dev-task addendum, `dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`.
      Net effect: decode-elapsed-time growth should not be leaned on as supporting evidence for
      Evidence 5's working hypothesis in either direction without better data (8.4). Does not
      resolve non-convergence; narrows what 8.3 can safely assume.
- [ ] 8.3 Only after 8.1–8.2 land: decide on a fix shape. Do not adjust
      `CorrectionSanityCeilingSamples`, `DriftThresholdSamples`, or `RequiredConsecutiveReadings`
      before root cause is isolated — `qa/endurance/2026-07-24-1cebf81/report.md` §3.2 already
      shows Decision 5's sizing math itself is not where the problem lives.
      **Updated 2026-07-24 — root cause now has direct isolated-test confirmation, fix shape
      still not decided:** 8.7's two falsification tests (above) confirmed the discard-costs-
      real-time mechanism under a controlled, confound-free rate-limited source — a materially
      stronger evidence class than 8.6's live-only correlational data (which could not rule out
      the resync-log-call/concurrent-decode confounds 8.7 was specifically designed to eliminate
      by construction). This narrows 8.3 considerably: the leading candidate is no longer "genuine
      capture-rate mismatch vs. pipeline-scheduling delay vs. something else" (8.6 already
      de-prioritized the scheduling-delay-at-the-three-instrumented-stages half) but specifically
      "the discard branch's relabel/skip is not actually free in real time." **Still not
      decided:** what fix shape follows from that — e.g., whether to size the *discard* correction
      differently, redefine what deviation is measured against so a self-inflicted wait isn't
      re-counted as fresh drift, or something else; each is a design.md-level decision, not
      something to pick without the Captain/Architect's sign-off given HK-011's session-separation
      intent for exactly this kind of call. 8.6's live re-confirmation (using 8.1's instrumentation
      against a fix, once one exists) is still the acceptance test before 6.6/7.6/8.6 can be
      checked off.
- [x] 8.4 Add systematic logging for `hashTableRejectCount` and decode elapsed time at a regular
      cadence (both were only available via ad hoc `/api/v1/status` polling in the 2026-07-24 run)
      if 8.2 finds session-length CPU/memory load is a real contributing factor.
      **Done 2026-07-24, per Captain's explicit sign-off to treat this session as Developer.**
      Narrowed by 8.2's own finding before implementation: decode elapsed time already has
      systematic per-cycle logging (the existing spec-mandated "Cycle {Time}: {Count} decode(s)
      found, elapsed={Elapsed} ms" line in `Ft8Decoder.cs` — that's how 8.2's reconciliation
      pulled it from both raw logs in the first place), so only `hashTableRejectCount` had the gap
      8.2 confirmed ("neither raw log contains it... confirming 8.4's premise"). Added one new
      Information-level log line in `Ft8Decoder.DecodeAsync`
      (`src/OpenWSFZ.Ft8/Ft8Decoder.cs`, design.md Decision 7), immediately after the existing
      elapsed-time line, same cadence and level: `"Cycle {Time}: hashTableRejectCount={Count}
      (process-lifetime cumulative)."`. `proposal.md`'s Impact section amended (Decision 7,
      mirroring how Decision 6 handled the same kind of scope widening). New coverage:
      `HashTableRejectCountLoggingTests.cs` (`DecodeAsync_EveryCycle_LogsHashTableRejectCountAtInformation`,
      `DecodeAsync_ZeroRejectCount_LogsZeroExplicitly`) using the existing `IFt8NativeInterop`
      fake-injection seam (no native DLL load, independent of `HashTableRejectCountTests`'s
      real-shim run-order constraints) — both pass. `hashTableRejectCount` remains a
      process-lifetime cumulative counter (unchanged contract); logging it every cycle still lets
      a raw-log analysis derive cycle-over-cycle deltas or a whole-session trend, same as the
      elapsed-time reconciliation already does. Does not touch, gate, or condition on the
      drift-correction logic itself — pure observability.
- [x] 8.5 Re-run `python3 tools/pre_merge_check.py` (HK-006) against whatever this section
      produces before calling the change ready for merge again.
      **Done:** all gates PASS — G9a doc/VERSION, Release build, UDP-margin lint, G10 lint, full
      test suite (all projects, incl. 300/300 `OpenWSFZ.Ft8.Tests` — up one from section 7's run —
      and 20/20 `OpenWSFZ.Audio.Tests` — up one from 19), G3 traceability, WSL Debian compile+test,
      G8 openspec strict validation (57/57, incl. this change's Decision-6-revised design.md/
      proposal.md), self-contained publish, AOT publish. Result: READY.
      **Erratum (QA review, 2026-07-24):** this item originally read "17/17
      `OpenWSFZ.Audio.Tests`" — incorrect on both the total and the delta; independently
      re-run and confirmed as 20/20 (up from 19, one new test:
      `StartAsync_AfterManyChunks_LogsPeriodicCadenceDebug`), consistent with 8.1's own
      correct count two sections above. All other gate results in this item stand unchanged.
- [ ] 8.6 Live re-confirmation: re-run the same live setup (same device, same technique) used in
      6.6/7.6 against the outcome of 8.1–8.4, checked specifically for whether the post-correction
      reading actually drops near the noise floor rather than re-establishing at the same
      magnitude — the property `qa/endurance/2026-07-24-1cebf81/report.md` found failing, and the
      one any fix needs to demonstrate. Only after this passes should 6.6/7.6 be checked off and
      the HK-011 merge hold be reconsidered.
      **Run 2026-07-24 (short, ~32 min, by design — see below) — still open, remains
      unchecked:** `qa/endurance/2026-07-24-29041f7/report.md`. Non-convergence reproduces
      exactly as `1cebf81` found (8 corrections fired, none produced a next-reading drop toward
      the noise floor; net deviation growth ≈31.6 samples/min, closely matching `ce13e30`'s
      whole-session ≈34.1 samples/min despite the sessions differing >14x in length) — expected,
      since no fix has landed since `1cebf81`. The actual new result: 8.1's pipeline-timing
      instrumentation stayed completely flat throughout (real inter-window elapsed 14.970-15.287 s
      around nominal 15.000 s; chunk-dequeue-gap and WASAPI/`CaptureManager` cadence stats
      unchanged all session) across a ~40% rise in deviation-at-fire — a real negative result
      that de-prioritizes the "scheduling delay visible at these three stages" half of the
      dev-task's Evidence 5 hypothesis, narrowing what 8.3 has left to consider. Session length
      was an explicit, Captain-confirmed choice (short-first, extend only if evidence motivates
      it, per 7.6's own original plan) and a mid-run stop-or-continue check-in found the flat
      instrumentation signal gave no reason to extend. Scope limits stated in the report: 32
      minutes cannot rule out an hours-only-emerging correlation (8.4's `hashTableRejectCount`
      logging gap still open), nor confirm whether the last-4-corrections' ~3,380-3,470 plateau
      is real. **Superseded-pending:** a longer follow-up run, once 8.4 lands and/or 8.3 needs
      stronger confidence specifically on the pipeline-timing correlation — not committed to by
      default.

- [x] 8.7 Candidate mechanism identified from 8.6's own artefacts (no new live run) — a discard
      ("lengthen"/positive) correction requires waiting to receive the discarded samples at the
      real device delivery rate before the next window can close, so it spends real wall-clock
      time rather than reclaiming any; the next drift check then re-measures that self-inflicted
      wait as a fresh deviation of almost the same size. Empirically: all 8 corrections in
      `29041f7` are followed, one cycle later, by a real-inter-window-elapsed excess matching the
      correction's own size at 89-114% (avg 98.5%). See
      `dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`'s continued
      addendum for the full analysis, an errata correction to `29041f7`'s report (a mis-attributed
      outlier), and a proposed two-part deterministic test (discard-costs-real-time; replay-does-
      not, as an asymmetry/falsification check — the replay branch has never fired live in any
      endurance run, so this is otherwise untested).
      **Explicitly not a root-cause confirmation:** code-consistent and empirically corroborated,
      but not the result of an isolated/controlled test — confounds sharing the same timing window
      (the resync log call, a concurrent decode kickoff) have not been individually ruled out.
      **Implemented and run 2026-07-24, per Captain's explicit sign-off to treat this session as
      Developer for this item** (supersedes the "not implemented here" note below, which
      described the state before that sign-off): `RunAsync_DiscardCorrectionOnRateLimitedSource_CostsProportionalRealTime`
      and `RunAsync_ReplayCorrectionOnRateLimitedSource_DoesNotCostExtraRealTime` in
      `CycleFramerTests.cs`, following the dev-task's proposed spec essentially verbatim (a new
      `FeedSamplesAtRealRate` helper reintroducing genuine per-chunk `Task.Delay`, deliberately
      absent from every other feed helper in this file so those stay immune to real-timing
      flakiness). Both engineer a clean, chunk-aligned 45 000-sample correction (10x a
      4 500-sample chunk) via a large exaggerated 1.25 s/cycle `RateClock` offset, and assert a
      *relative ratio* against this run's own measured baseline chunk timing (never a hardcoded
      millisecond threshold — per `test-delay-debt.md`/Gate G10) so the test self-calibrates
      against whatever the actual Task.Delay/OS-timer granularity is on the machine running it.
      **Result: CONFIRMED, both tests, clean pass across 5 consecutive runs (no flake).** Test 1:
      the window spanning a discard correction took ~1.10-1.60x an ordinary window's real time
      (theoretical 1.25x); Test 2: the window spanning a replay correction took ~0.55-0.95x an
      ordinary window's real time (theoretical 0.75x) — the predicted asymmetry holds under a
      controlled, confound-free rate-limited source, with the specific confounds this addendum
      flagged as not-yet-ruled-out (the resync `LogInformation` call, a concurrent decode kickoff)
      absent entirely from this test. Per the dev-task's own "What a result would mean": this is
      strong support for treating the discard-costs-real-time mechanism as 8.3's root cause — the
      fix shape needs to address that the discard branch's premise (relabelling/skipping raw
      samples is "free") is false, not just re-tune constants again. **This unblocks 8.3's
      root-cause question but does not by itself decide a fix shape or re-open 8.3** — that
      remains a separate design decision.
      **Original note (state before the above sign-off, kept for the record):** not implemented
      here, per HK-011 — the proposed test lives in `tests/`, which is Developer-session territory
      same as `src/` for this change; QA's role stops at the specification.

- [x] 8.8 Re-run `python3 tools/pre_merge_check.py` (HK-006) against 8.4's and 8.7's combined
      changes before calling this pass done.
      **Done 2026-07-24:** all gates PASS — G9a doc/VERSION, Release build, UDP-margin lint, G10
      lint, full test suite (all projects, incl. 304/304 `OpenWSFZ.Ft8.Tests` — up 4 from 8.5's
      300/300: the 2 new 8.7 falsification tests + the 2 new 8.4
      `HashTableRejectCountLoggingTests`; `OpenWSFZ.Audio.Tests` unchanged at 20/20, no changes in
      that project this pass), G3 traceability, WSL Debian compile+test, G8 openspec strict
      validation (57/57, incl. this change's Decision-7-revised `design.md`/`proposal.md`), G9b
      self-contained publish, AOT publish. Result: READY (on the mechanical gates only — this is
      **not** a merge-readiness claim: `tasks.md` 6.6/7.6/8.6 remain unchecked, 8.3 still needs a
      fix-shape decision, and HK-011's Captain pre-push sign-off on this session's `src/` diff is
      still outstanding).
