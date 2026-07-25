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
- [x] 8.3 Only after 8.1–8.2 land: decide on a fix shape. Do not adjust
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
      **Decided 2026-07-24 evening, by the Captain:** fix the deviation-accounting math (design.md
      Decision 8) — keep the existing threshold/persistence-gate/size-to-confirmed-deviation
      architecture, but stop measuring the window immediately after a correction against a flat
      15.000 s expectation when its genuine real-time cost is `15.000 s ± correction/SampleRate`
      by construction. Chosen over (a) continuous small-quantum rate-tracking instead of periodic
      corrections, and (b) reopening Decision 1 to fix at the resampler/capture layer — both
      remain available as fallbacks if this proves insufficient, per design.md Decision 8. See
      section 9 below for the implementation/verification tasks this decision unblocks.
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
      **Run 2026-07-24 evening (short, ~39 min, by design) — still open, remains unchecked:**
      `qa/endurance/2026-07-24-f57fa4d/report.md`, the first live run with 8.4's
      `hashTableRejectCount` logging and 8.7's confirmed mechanism in the build under test (8.7
      itself confirmed via isolated unit tests, not re-tested live here). Non-convergence
      reproduces again: 3 corrections fired (mixed next-reading direction, 2 decreases/1
      increase — not the clean `1cebf81` failure pattern, but not convergence either), and the
      session-wide oscillation band still climbed ~2.2x (1,122.3 -> 2,469.0 samples avg,
      first-10 vs last-10 readings) at ≈35.3 samples/min — the third session in a row
      (`ce13e30` ≈34.1/min, `29041f7` ≈31.6/min) to show a consistent rate despite differing
      length/band/correction-cadence, itself the strongest cross-run evidence yet of one stable
      underlying mechanism. 8.4's logging confirmed working correctly under real sustained load
      (0 -> 2,394 `hashTableRejectCount` over the session, harmless). **New finding, not
      previously gathered by any run against this change:** a manual DT comparison against
      WSJT-X (one cycle, 11 matched decodes) found OpenWSFZ's DT running a flat ~+0.5 to +0.6s
      higher than WSJT-X's throughout — larger and flatter than the ~0.1-0.2s `deviation` the
      drift-check instrumentation itself reported at that point, suggesting (hypothesis, not
      yet confirmed) a possibly separate, time-invariant measurement-reference offset distinct
      from the session-scale drift this change targets. Flagged as the report's top follow-up
      recommendation — not yet checked against any prior baseline characterization, and based
      on a single cycle, not a session-wide comparison.

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

## 9. Deviation-accounting fix: correct for a correction's own real-time cost (design.md Decision 8, tasks.md 8.3's decided fix shape)

- [x] 9.1 `src/OpenWSFZ.Ft8/CycleFramer.cs`: at the moment a correction fires (inside the
      `driftStreakCount >= RequiredConsecutiveReadings` branch), record
      `pendingNominalAdjustSeconds = correction / (double)SampleRate` — a one-shot value
      representing the genuine extra-or-reduced real time the *next* window will take to fill
      because of this correction (positive for a discard/lengthen, negative for a replay/shorten).
      Apply it to `nominalCycleStart`'s *next* advance only — change the unconditional
      `nominalCycleStart = nominalCycleStart.AddSeconds(CycleDurationSecs)` (currently at the top
      of the per-window block, alongside `cycleStart`'s own advance) to
      `nominalCycleStart = nominalCycleStart.AddSeconds(CycleDurationSecs + pendingNominalAdjustSeconds)`,
      then reset `pendingNominalAdjustSeconds` to 0 immediately after that one use so it does not
      persist beyond the single window it applies to. `cycleStart` itself (the reported,
      decoder-facing timestamp) is unaffected — this only changes the internal reference
      `nominalCycleStart` is compared against. See design.md Decision 8 for the full mechanism
      trace and rationale. **`src/` change — Developer-session territory per HK-011; QA's role
      stops at this specification unless the Captain explicitly grants a session-treat-as-Developer
      exception, as was done for 8.4/8.7.**
- [x] 9.2 Confirm this does not change behaviour for the no-correction-fires path (the vast
      majority of windows): `pendingNominalAdjustSeconds` must default to/settle at exactly 0 when
      no correction has just fired, so `nominalCycleStart`'s advance is the unchanged flat
      `CycleDurationSecs` in that case — existing tests asserting "no correction fires absent
      drift" and "cycleStart advances by exactly 15 seconds" must continue to pass unmodified.
      Confirmed: `RunAsync_ClockInLockStep_NoCorrectionFires` and
      `RunAsync_RecurringNonMonotonicDeviation_NeverFiresCorrection` pass unmodified. One
      *correction-fires* test, `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`
      (many repeated corrections over a long session), needed its tolerance updated — its own
      docstring now explains why: 9.1 legitimately shifts subsequent-correction timing/sizing in a
      multi-correction session (out of scope for this task's "no-correction-fires" guarantee), and
      the residual it measures settles into a new, still-bounded, still-non-growing steady-state
      plateau (~80 samples higher than before), not unbounded growth. Not a regression.
- [x] 9.3 Unit test (extends 8.7's `FeedSamplesAtRealRate` rate-limited-source harness in
      `CycleFramerTests.cs`): after a correction fires under a genuinely rate-limited source (both
      discard and replay directions, mirroring 8.7's two tests), assert that the **deviation
      reading** on the window immediately following the corrected one lands near the noise floor —
      not near the correction's own magnitude. This operationalizes, as a fast isolated test, the
      exact property every live endurance run so far has checked for and found failing
      (`1cebf81`'s report: "does the post-correction reading actually drop near the noise floor,
      or re-establish at the same magnitude"). This is the acceptance criterion for whether 9.1
      actually fixes non-convergence, independent of any live run.
      Implemented as `RunAsync_DiscardCorrectionDeviationAccounting_NextReadingNearNoiseFloor` /
      `RunAsync_ReplayCorrectionDeviationAccounting_NextReadingNearNoiseFloor`. A first attempt
      tied the test `IClock` to actually-measured real elapsed time (scaled ~35x to compress 15 s
      into a sub-second test window) — correct in principle but fatally flaky, since any OS-
      scheduler hiccup got amplified 35x into thousands of spurious samples (observed directly: a
      247 000-sample reading where ~45 000 was expected). Replaced with a deterministic
      `SampleCountClock` (true UTC derived from the exact count of raw samples delivered by the
      still-genuinely-rate-limited feed, divided by an assumed true device sample rate) — physically
      equivalent, immune to scheduler jitter, 5/5 clean repeated local runs. Both tests confirm the
      fixed case (post-correction reading ~25-42% of the correction's own magnitude) is clearly
      separated from the unfixed case (analytically ~125-142%, hand-derived, not re-tested against
      old code) — the bound is not "near-zero" because 9.1 only ever claimed to cancel the
      correction's own real-time cost, not the window's ordinary ongoing per-cycle device-rate
      contribution (see 9.2's note above and the test's own inline comments).
- [x] 9.4 Re-run `python3 tools/pre_merge_check.py` (HK-006) against 9.1-9.3's combined changes.
      Result: READY — every gate passed (G9a, Release build+full test suite incl. WSL Debian, G3
      traceability, G8 openspec validate --strict --all, self-contained publish, AOT publish).
- [ ] 9.5 Live re-confirmation: same live setup as 6.6/7.6/8.6 (same device, same technique),
      checked specifically for whether the post-correction deviation reading now actually drops
      near the noise floor across a real session, not just in the isolated unit test (9.3). This
      is the actual gate before the HK-011 merge hold can be reconsidered — 6.6/7.6/8.6 remain
      historical markers of the three prior (failed) fix attempts and are not retroactively
      satisfied by this section; 9.5 is this fix's own live acceptance test.
      **FAILED, 2026-07-24/25 overnight, 40m band, 11h51m — the longest and most data-rich round
      in this investigation.** `qa/endurance/2026-07-25-40m-band-9.5-fail/report.md`. Only 32/136
      (23.5%) of corrections landed near the noise floor on their immediate next reading; the
      session-level signal is worse than that number alone suggests — correction magnitude grew
      essentially monotonically, hour over hour, roughly 8x from the first hour to the last, with
      no plateau. Zero crashes, zero ERR/FTL, pipeline-timing instrumentation stayed flat
      throughout (H₀-3 continues to hold) — this is squarely the same non-convergence defect
      every round before 9.1 also showed, not a stability or instrumentation problem. Do not
      retry 9.5 against 9.1 unmodified; see 9.6.
- [ ] 9.6 Once 9.5 passes: reconsider the HK-011 merge hold with the Captain. If 9.5 does not
      converge either, escalate to fallback fix shapes 2 or 3 recorded in design.md Decision 8
      (continuous rate-tracking, or reopening Decision 1's scope boundary) rather than re-tuning
      9.1's constants in isolation.
      **Does not apply — 9.5 failed, not passed.** Per this item's own instruction, escalate to
      one of Decision 8's fallback shapes rather than re-tuning 9.1 (which has no tunable
      constants to begin with). The HK-011 merge hold stands, unchanged. Not the Captain's call
      to make yet — there is nothing converging to sign off on.
      **SUPERSEDED by §10 (design.md Decision 9, Architect 2026-07-25):** the escalation to
      fallback shapes 2/3 is withdrawn. 9.5's failure was traced to a defect *in* 9.1's
      implementation (`nominalCycleStart = cycleStart` discarding the divergence 9.1 itself
      creates), not to Decision 8's mechanism trace being wrong. 9.1 is retained; §10 fixes it.

## 10. Reset-conflation fix: `nominalCycleStart` must be shifted, not re-anchored to `cycleStart` (design.md Decision 9)

Context: the 9.5 overnight round's own artefacts show each post-correction deviation reading
reproducing the **previous** correction (r=0.9931, slope 0.977, sign match 135/135), and an energy
balance in which 66.8 s of the session's 68.9 s excess real time is the corrections' own discard
cost. See design.md Decision 9 for the full derivation, the five findings, and the risks.

- [x] 10.1 `src/OpenWSFZ.Ft8/CycleFramer.cs`: in the `driftStreakCount >= RequiredConsecutiveReadings`
      branch, replace `nominalCycleStart = cycleStart;` with
      `nominalCycleStart = nominalCycleStart.AddSeconds(correction / (double)SampleRate);`.
      Shift by `correction`, **not** by `deviationSeconds` — in the ordinary unclamped case they are
      equal and the current deviation is zeroed exactly, but if `CorrectionSanityCeilingSamples`
      ever binds, shifting by `correction` correctly carries the residual forward as a slew
      (Decision 5's intended behaviour) whereas shifting by `deviationSeconds` would silently
      swallow it. `cycleStart` keeps its own separate `+correction/SampleRate` advance — the whole
      point is that the two quantities are not interchangeable. **`src/` change — Developer-session
      territory per HK-011, with the Captain's pre-push sign-off.**
- [x] 10.2 Same file: correct the now-false invariant in the `nominalCycleStart` declaration comment
      ("Reset to match cycleStart whenever a correction fires") and in the class-level `<summary>`
      Decision 8 paragraph. State the actual invariant: `nominalCycleStart` is a pure arithmetic
      measurement reference that legitimately diverges from `cycleStart` by the accumulated history
      of one-shot adjustments, and must never be re-anchored to it. This comment asserting the
      pre-Decision-8 invariant is part of the defect, not incidental to it.
- [x] 10.3 Change the 9.3 acceptance metric (`CycleFramerTests.cs`) to regress the post-correction
      reading against **both** its own and the preceding correction's magnitude. Without this the
      test suite cannot distinguish a full fix from another half-fix — this is exactly why 9.1's
      partial success read as "changed nothing" in 9.5, and it is a prerequisite for trusting any
      future live round.
      **Done as:** both existing tests fire exactly one correction each, so there is no *preceding*
      correction within either test to regress against for a session's first correction (10.1's fix
      and the pre-10.1 bug are numerically identical on a lone first correction — confirmed by
      hand-derivation, see the new comments added to both tests). Both tests still pass unchanged
      post-10.1; their comments now say so explicitly and point at 10.4's new test for the actual
      both-magnitudes falsification check.
- [ ] 10.4 New unit test: fire **two or more consecutive corrections** under the deterministic
      `SampleCountClock` + `FeedSamplesAtRealRate` harness and assert the second correction's
      post-reading does not reproduce the first's magnitude. Every existing 9.3 test fires exactly
      one correction, which is precisely why this escaped a full `pre_merge_check.py` pass.
      Additionally: restore
      `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections` to its
      pre-9.1 tolerance. Per Decision 9 Finding 5, that test *did* detect this regression (residual
      "~80 samples higher") and its tolerance was widened and the shift rationalised as a benign new
      plateau; if 10.1 is correct the original tolerance must pass again. Treat failure to restore it
      as evidence the fix is incomplete, not as a reason to re-widen.
      **Status: half-done, blocked — see dev-tasks/2026-07-25-cycleframer-nominal-reset-conflation-fix.md
      addendum.** The new multi-correction test
      (`RunAsync_TwoConsecutiveDiscardCorrections_SecondPostReadingDoesNotReproduceFirstCorrection`,
      `SampleCountClock`-based) is written and passes against the 10.1 fix; hand-confirmed as a
      genuine falsification test by temporarily reverting 10.1 and observing it fail exactly as
      predicted (second post-reading ≈ first correction's magnitude, ratio 1.33x vs the 0.6x bound).
      **The tolerance-restore sub-item does NOT pass and is not a matter of picking a new number:**
      reverting `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections` to
      220 fails at windowCount=24 exactly as before (residual reaches 660), and extending the same
      run to windowCount=60 shows residual climbing *linearly without bound* (reaches 1740, no
      plateau) — this is not "needs a wider constant," it cannot pass at any fixed tolerance if run
      long enough. Root cause: this test's `RateClock` is a fixed per-read-count formula with zero
      correlation between a correction firing and the clock's own reading — i.e. it models a
      correction as having exactly zero real-time cost. Decision 8/9's mechanism assumes the
      opposite (a discard genuinely costs real time, per Decision 8's own live-evidence basis) and,
      per Decision 9's own math (Finding 2: "the derivation requires `2·c_now/SampleRate`"),
      *correctly and intentionally* leaves a permanent `correction/SampleRate` gap baked into
      `nominalCycleStart` after every correction under that assumption. Under `RateClock`, since the
      clock reading never reflects any of that assumed real cost, this permanent gap has nothing to
      reconcile against and compounds every correction, unbounded. The pre-10.1 buggy `= cycleStart`
      reset was, empirically, acting as a periodic release valve for exactly this synthetic
      mismatch (hand-confirmed: buggy code plateaus cleanly at 300 samples through windowCount=60,
      matching the original 9.1 rationale) — which is a coincidence of the bug, not a property worth
      preserving, per Decision 9's own Finding 2 argument that the reset was wrong. This is a real
      discrepancy between design.md Decision 9's explicit prediction ("the original tolerance must
      pass again") and observed behaviour, not an implementation slip in 10.1 (10.1 is the verbatim
      prescribed one-liner, and the three `SampleCountClock`-based real-cost tests — the two 9.3
      tests plus the new 10.4 test — all pass, confirming the fix is correct for the real-device
      model). Escalated to the Captain rather than resolved unilaterally: re-widening the tolerance
      is explicitly excluded by this task's own instructions and wouldn't work anyway (unbounded),
      and changing this test's clock model to something cost-consistent (mirroring why 9.3's own
      tests moved off `RateClock`/`StepClock`/`BouncingClock` to `SampleCountClock`) is a design-
      level call, not a Developer-session one. `src/` fix (10.1/10.2) and the new falsification test
      are left in place and verified; the tolerance-restore sub-item is unchecked pending direction.
      **QA review (2026-07-25) confirmed this failure and its diagnosis independently (re-derived
      the math, re-ran the suite) and, per the Captain's explicit direction, routed it to the
      Architect as a Decision 9 addendum question rather than resolving it here** — see
      `qa/cycleframer-code-review/2026-07-25-decision9-review-and-rateclock-escalation.md` for the
      three options surfaced (rebuild on `SampleCountClock`, retire in favour of 10.4's new test, or
      an Architect-preferred alternative). 10.1-10.3 and the new multi-correction test are approved;
      do not proceed to 10.7 until this is resolved.
- [ ] 10.5 Re-derive and record the drift constants against the ~101 ppm figure measured from
      correction-free cycles (95% CI [46, 156] ppm) rather than D-001's 42.41 ppm. Document whether
      `DriftThresholdSamples = 24` and `RequiredConsecutiveReadings = 3` still hold at ~18
      samples/cycle instead of the 7.6 they were derived from. Expected outcome is "unchanged, fires
      ~2.4x more often, not a defect" — but the discrepancy must not stay undocumented, and the
      wide CI is itself worth narrowing from the WAV archive if cheap.
- [ ] 10.6 Offline, no live time: session-wide DT-offset comparison against WSJT-X using the
      preserved archive (`artefacts/20260724_live_run_2227/wav/`, 2,827 files) to close Decision 9
      Finding 4 / the report's Section 7. Falsifiable prediction: the OpenWSFZ-vs-WSJT-X DT offset
      **tracks the cumulative signed correction sum over the session** rather than sitting flat at
      +0.5–0.6 s. If it tracks, Section 7 is not a separate defect and needs no further
      investigation; if it sits flat, there is a genuine second, time-invariant offset to chase
      separately.
      **Amended 2026-07-25 (Architect) — two corrections and a dependency, see §11:**
      (a) ~~**The prediction as written is not testable on the preserved archive.**~~
      **RETRACTED same day — I was wrong, and wrong in the way this whole thread keeps warning
      about.** The original amendment observed that `artefacts/20260724_live_run_2227/` has no
      WSJT-X `ALL.TXT` (true) and generalised that to "the preserved archive" without looking at
      the other runs (false). The Captain pointed at
      **`artefacts/20260723_live_run_2223/`**, which holds a complete matched set. Verified
      2026-07-25:

      | file | content |
      |---|---|
      | `wsjtx/ALL.TXT` | 50,501 lines, `260723_222345` → `260724_061730` |
      | `openwsfz/ALL.TXT` | 31,517 lines, `260723_222330` → `260724_061730` |
      | `openwsfz/openswfz-20260723T222314Z.log` | **20 `Cycle boundary resync` + 1,897 `Cycle boundary drift check` lines** |
      | `wsjtx/wav/` | 1,884 files, mono/12 kHz/16-bit/exactly 180,000 frames, 99.5% contiguous (1,873×15 s, 8×30 s, 2×45 s) |

      **This makes 10.6 fully executable, and it is the only run that does.** The daemon log yields
      the cumulative signed correction sum per cycle; the two `ALL.TXT`s yield the per-cycle DT
      offset; the prediction ("offset tracks the correction sum" vs "sits flat") is testable as
      written. The WAVs are format-identical to the 0724 archive, so `rewindow.py` consumes them
      unmodified.
      **This is not the §3-invalidated comparison.** §3 voided *OpenWSFZ vs OpenWSFZ* (a
      self-comparison); this is two genuinely different decoders. Two real confounds remain and
      must be handled explicitly, not assumed away:
      - **Different captures, not different windows on one capture.** SPEC §6's "do not attempt
        sample-level registration between OpenWSFZ's and WSJT-X's captures" still binds. Match on
        **per-cycle message sets**, never on samples.
      - **OpenWSFZ's cycle labels slide off the UTC grid** by the cumulative correction (study §2
        item 1), so naive timestamp-keyed matching breaks by construction — which is precisely what
        this item is measuring. Use the daemon log's correction sum to align, and say so.
      - The raw 50,501-vs-31,517 line ratio is **not** a recall figure (§3's trap). Filter Tx lines
        and non-FT8 modes, and use the paired within-cycle metric of SPEC §5.3.
      **Note the run differs from 0724_2227**: build `ce13e308` + the persistence-gated diff, 7h54m,
      40 m — a *different* session and build from the 9.5 round. Same device and band. Any figure
      derived here describes that session; per §2.5 item 10 the tolerance interval tracks `DT_med`
      1:1, so **0723's own DT baseline must be measured, not inherited from 0724's +0.80.**
      (b) **The measurement it needs is already funded elsewhere.** §11's Phase 1b produces the
      arm-A DT baseline across all 2,827 cycles; that is the same distribution 10.6 needs for its
      OpenWSFZ side, at zero extra decode cost. Sequence 10.6 *after* 11.5, not in parallel.
      (c) The +0.5–0.6 s figure this item chases came from a **single cycle, 11 matched decodes**
      (8.6's evening run). Segment 0's measured DT median is +0.80 with p10–p90 +0.60…+1.10
      (study §2.5 item 6) — i.e. the claimed "offset" is inside the ordinary per-cycle spread of
      real signals' DT. **It may not be an offset at all.** Establish the session-wide baseline
      first (11.5) before treating this as a defect to chase.
- [ ] 10.7 Re-run `python3 tools/pre_merge_check.py` (HK-006) against 10.1–10.4's combined changes.
- [ ] 10.8 Live re-confirmation, replacing 9.5 as this change's live acceptance gate. Reuse the
      HK-013 supervisor (`qa/endurance/2026-07-24-supervisor.sh`) with its two recorded edge-case
      fixes applied. Acceptance criteria, all three required:
      (a) post-correction readings land near the noise floor against **both** own and previous
      correction magnitude (10.3's metric);
      (b) correction magnitude reaches a plateau rather than growing hour over hour;
      (c) the pipeline-timing figure for correction-free windows sits at nominal 15.000 s — tested
      **against nominal, not merely for absence of a trend**, per Decision 9's inversion of H₀-3.
      A session need not match 9.5's 11h51m: with the loop fixed, corrections should be ~2 orders of
      magnitude smaller, so a plateau should be visible within 2–3 hours. Run longer only if the
      short round passes.
      **(d) added 2026-07-25 (Architect) — the outcome criterion this gate has never had.**
      Criteria (a)–(c) all read the framer's own internal deviation log; none measures what
      misalignment actually *costs*, which is the gap the alignment-replay study (§11) exists to
      close. Add: **per-cycle alignment error, derived as `δ_live(k) = DT_ref(k) − DT_live(k)`
      (study §6 — mind the sign, it was inverted once already), must stay inside the measured
      tolerance interval for ≥95% of cycles.**
      - **Provisional interval: `δ ∈ [−1.6, +2.0] s` for ≥92% median recall**, hard cliff centres at
        −2.32 / +2.40, derived at `DT_med` = +0.80 (study §2.5 item 10, deliverable #5). **Not
        final** — pending 11.5. Do not hard-code it into a gate before 11.7 lands.
      - **The interval is not a constant of the decoder.** It is `[DT_med − 3.12, DT_med + 1.60]`
        and moves 1:1 with the signal population's DT, so it must be quoted together with the
        `DT_med` it was derived from and re-derived for a different band or session.
      - Quote conformance against a **stated percentile, not the median** — the recall distribution
        has a left tail the median hides (study §5.3).
      **Sequencing:** (d) needs 11.7's final bound, so 10.8 should not be scheduled ahead of §11.
      (a)–(c) are independent of §11 and can proceed on the existing schedule; a run that satisfies
      (a)–(c) but has not yet been scored against (d) is a **partial** pass, not a green gate.
- [ ] 10.9 Once 10.8 passes: reconsider the HK-011 merge hold with the Captain. If 10.8 fails, *then*
      escalate to Decision 8's fallback shapes — but note that Decision 9's diagnosis is
      quantitative and closed, so a failure here would indicate a *further* distinct mechanism and
      should be root-caused from the run's own artefacts first, in the manner Decision 9 was, before
      any architecture change is chosen.

## 11. Alignment-replay study: what does misalignment actually cost in decodes? (`qa/cycleframer-alignment-replay/SPEC.md`)

Five live rounds have measured the *correction loop's* behaviour in detail. **None has ever measured
what misalignment costs in recall** — which is what 10.8's acceptance bound and the D-001 scope
decision both turn on. This section tracks that study.

**Scope: QA tooling only, zero `src/`, no live radio time** — HK-000 applies, not HK-011. Runs
entirely offline against the preserved WAV archive. Does not modify `CycleFramer` and does not
depend on whether 10.1–10.4 land; it measures the audio, not the framer. It can therefore proceed
**in parallel with** §10's live work, and should, since 10.8(d) and 10.6 both now depend on it.

- [x] 11.1 Phase 0 — re-windowing self-test + the four mandatory controls (SPEC §5.1, §7). 129
      decodes. **PASSED and ratified**, SPEC §2.5/§14. Findings:
      `qa/cycleframer-alignment-replay/2026-07-25-phase0-findings.md`.
- [x] 11.2 Phase 0b — §7.4(b) cross-input determinism + the §7.3 provenance guard. **§7.3 guard
      passed. §7.4(b) FAILED and was resolved by narrowing the metric**, not by the remedy the SPEC
      prescribed (fresh managed `Ft8Decoder` per window does not clear `ft8_shim.c:627`'s native
      process-global `g_session_hash_table`). Hash-bracket canonicalization
      (`normalize_hash_tokens()`) takes the forward-vs-reverse mismatch 14/25 → 0/25 and moves no
      already-ratified §2.5 figure by >0.002. Findings: `2026-07-25-phase0b-findings.md`; ruling:
      SPEC §7.4(b), §15.2. **Two guards outstanding — see 11.6.**
- [x] 11.3 Phase 1a — asymmetry probe, 25 cycles × 7 δ, 175 decodes. **PASSED**, and did its job:
      **falsified SPEC §2.5 item 9's predicted −1.7 negative cliff** (recall still 0.833 at
      δ=−2.125; real cliff at −2.3…−2.4). The retracted grid would have put 13 dense points in the
      wrong place while stopping short of the cliff bottom. Findings:
      `2026-07-25-phase1a-findings.md`.
- [x] 11.4 Architect review of 11.2/11.3 (SPEC §15) — **a fifth pre-existing SPEC defect, and the
      second serious one after §6.3's inverted sign.** The decoder's time search is
      `DT_obs ∈ [−1.60, +3.12]`, read from `native/ft8_lib_build/patched/ft8/decode.c:279`, not the
      symmetric ±2.5 s the SPEC asserted three times. Applied to arm A's own DT distribution with
      **zero fitted parameters** it reproduces all 12 measured recall points at RMS 0.085 (the
      assumed ±2.5 s bound scores 0.472). Recorded as SPEC §2.5 item 10; item 9 retracted.
      Consequences already folded into 10.6 and 10.8(d) above.
      **Standing note for any future session:** `decode.c:279` is now load-bearing for every figure
      in SPEC §2.5 item 10, §5.2 and deliverable #5. **Any re-vendoring or re-patching of ft8_lib
      must re-check that line.**
- [ ] 11.5 **Phase 1b — confirm-and-cut** (Captain's decision, 2026-07-25). 400 cycles stratified
      across the session × 11 non-anchor offsets (SPEC §5.2 second amendment), plus the arm-A DT
      baseline extended to all 2,827 cycles. ≈7,200 decodes, down from ≈13,200 for the full
      27-point grid. Weighted toward the **positive cliff**, which has exactly two measurements ever
      (+2.0, +3.0) and whose predicted centre (+2.40) has never been probed — the model's strongest
      untested prediction.
      **Gated on SPEC §5.2's three-part falsification criterion, evaluated against the
      *session-wide* DT median, not segment 0's.** State the verdict before looking.
      **If any part fails, fall back to the full 27-point grid before quoting deliverables #2/#5** —
      a cut budget is only legitimate while the model justifying it is still standing.
      The DT baseline is the single highest-value measurement in the phase: if the model holds, the
      curve is *derived* from that distribution rather than traced, and 10.6 gets its OpenWSFZ side
      for free.
- [ ] 11.6 Guards carried forward from 11.2's narrowed metric, both mandatory in 11.5:
      (a) **Collision assertion** (SPEC §7.4(b-i)) — `normalize_hash_tokens()` can merge two
      *genuinely distinct* messages and thereby *inflate* recall. Measured on Phase 0's reference:
      7.18% of rows carry a bracket token, **0 within-cycle merges across 25 cycles**. Safe there;
      will not stay zero at 400 cycles. `score_recall.py` must **count merges per run and fail
      loudly if nonzero.** Assert it, don't assume it.
      (b) **Reject-count recording** (SPEC §7.4(b-ii)) — `hashTableRejectCount` is the hazard §7.4
      actually names, and a hash-driven *reject* is a genuinely missing decode that normalization
      neither fixes nor reveals. Record it per arm and compare across arms; a systematic difference
      is a confound signature. 8.4 already added the per-cycle log line this needs.
- [ ] 11.7 Deliverables (SPEC §10), in particular **#5: the maximum acceptable alignment error**,
      which is what 10.8(d) consumes. Must be stated as an **asymmetric interval `δ_min … δ_max`,
      never `±X`** — with *more* headroom on the negative side, the opposite of the retracted item
      9's claim — against a **stated percentile**, and **together with the `DT_med` it was derived
      from**. Provisional pending 11.5: `δ ∈ [−1.6, +2.0]` at `DT_med` = +0.80.
- [ ] 11.8 `qa/cycleframer-alignment-replay/report.md` per NFR-024/HK-001 section conventions (QA
      authors Sections 1/5 and the Section 2 framing; render HTML via `render_report.py`).
      NFR-021: derived artefacts contain real third-party callsigns — keep them git-ignored and
      local, exactly as `artefacts/` is.
- [x] 11.9 ~~**Open request to the Captain**~~ — **ANSWERED 2026-07-25, and better than the request
      asked for.** The 2026-07-24 WSJT-X `ALL.TXT` is **unrecoverable** (Captain: if it is not in
      the artefact folder it is lost) — but `artefacts/20260723_live_run_2223/` holds a complete
      matched set that the 0724 run never had: WSJT-X `ALL.TXT` (50,501 lines), OpenWSFZ `ALL.TXT`
      (31,517 lines), the daemon log with 20 resync + 1,897 drift-check lines, and 1,884 WAVs
      verified format-identical to the 0724 archive. See 10.6(a) for the full table and caveats.
- [ ] 11.10 **D-001 absolute-gap sizing on the 0723 archive** — newly unblocked by 11.9, and the
      thing SPEC §11 explicitly said this study *could not settle*. With both decoders' `ALL.TXT`
      over the same session, the harness can size **how much of D-001's recall gap is alignment and
      how much is everything else** — the decomposition §1 has wanted from the start and which no
      run has ever had the data for.
      **Do not fold this into the recall(δ) curve.** Keep the curve on 0724's audio: Phases 0/0b/1a
      are three phases deep on segment 0 there, and rebasing would discard a ratified baseline to
      buy a comparison that is better run as its own arm. 0723 is a *different session and build*
      (`ce13e308` + persistence-gated diff, 7h54m, 40 m).
      Sequence **after 11.5**, which supplies the scoring machinery and the DT-baseline method;
      0723 needs **its own** `DT_med`, not 0724's +0.80 (§2.5 item 10 — the interval tracks the
      population 1:1).
      Carries the same three confounds as 10.6(a): different captures (no sample registration —
      §6), OpenWSFZ's sliding cycle labels, and the raw line-count ratio not being a recall figure.
      NFR-021: 0723's `ALL.TXT` files contain real third-party callsigns — derived artefacts stay
      git-ignored and local, as `artefacts/` already is.
