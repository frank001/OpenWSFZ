# Live-run finding: `fix-cycle-boundary-clock-drift`'s correction is sized correctly but does not converge — real hardware needs root-cause instrumentation, not another sizing tweak

**Status:** BLOCKING. Surfaced during the sizing-fix live re-confirmation run (`tasks.md` item
7.6), the step that was specifically meant to confirm Decision 5's full-absorption sizing behaves
on real hardware the way `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`
predicted in simulation. It does not. Full data and analysis:
`qa/endurance/2026-07-24-1cebf81/report.md` (§3.2–3.3); raw artefacts (daemon log, WSJT-X
`ALL.TXT`, all 1,501 session WAV files) preserved at `artefacts/20260724_live_run_0821/` so this
investigation doesn't need to reproduce the run from scratch. Recommend holding
`fix-cycle-boundary-clock-drift` out of merge — `tasks.md` 6.6 and 7.6 both remain unchecked —
until at least Recommended next steps 1–2 below are addressed.

## Context

- Change under review: `openspec/changes/fix-cycle-boundary-clock-drift/`. Decision 5 (sizing
  fix, `dev-tasks/2026-07-24-cycleframer-correction-sizing-fix.md`, landed `1cebf81`) replaced
  the old fixed-cap correction with full absorption of the confirmed deviation, bounded only by a
  much larger `CorrectionSanityCeilingSamples` (180,000, one full cycle) meant as a
  pathological-input backstop. Unit-level regression testing
  (`RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`) confirmed
  residual stays bounded near the noise floor in simulation, using deterministic `RateClock`/
  `StepClock` doubles.
- This run's purpose, per that dev-task's own Validation plan step 3: confirm real-hardware
  behaviour matches the simulation before checking off `tasks.md` 6.6/7.6.
- Live run setup: daemon already running (`dotnet run`-launched, PID 5564) when QA began
  monitoring; same physical capture device Phase 3 measured (`'Microphone (2- USB Audio CODEC )'`,
  `d451e08c-82b5-446e-a5f1-1bdd8fceeac2`, WASAPI), 20 m (14.074 MHz FT8) — note the prior
  `ce13e30` baseline used 40 m; band is not expected to matter for a capture-timing mechanism, but
  is recorded since exact reproduction wasn't attempted. WSJT-X running in parallel throughout.
- Full daemon log: `artefacts/20260724_live_run_0821/openswfz-20260724T082055Z.log`. Session:
  08:20:55Z start → 14:37:04Z graceful, operator-initiated capture stop (6h16m8s, 1,502 cycles,
  19,077 decodes). Zero crashes, zero ERR/FTL, one pre-existing benign WebSocket-timeout WRN
  unrelated to `CycleFramer`.

## Evidence

### 1. Every correction is sized exactly right — and every correction leaves the deviation almost exactly where it was

10 corrections fired over the session. Every single one matched its logged confirmed deviation to
the sample (no capping, none within an order of magnitude of the sanity ceiling — max 7.67% of
it). That part of Decision 5 works as designed. But the drift-check reading *immediately
following* each correction (one cycle, ~15 s real time, later) landed within **±4% of the
pre-correction value, all ten times, at every scale from 1,200 to 13,800 samples**:

| # | Deviation at fire | Very next reading | Change |
|---|---|---|---|
| 1 | 1,264.5 | 1,286.1 | +1.71% |
| 2 | 2,849.1 | 2,807.3 | −1.47% |
| 3 | 3,454.9 | 3,565.6 | +3.20% |
| 4 | 4,173.9 | 4,196.8 | +0.55% |
| 5 | 5,151.6 | 5,289.7 | +2.68% |
| 6 | 11,842.0 | 11,777.3 | −0.55% |
| 7 | 13,268.6 | 13,256.8 | −0.09% |
| 8 | 13,403.0 | 13,141.8 | −1.95% |
| 9 | 13,037.0 | 13,035.0 | −0.02% |
| 10 | 13,801.5 | 13,252.9 | −3.97% |

If the correction were genuinely absorbing device-clock drift, the next reading should reflect
only one fresh cycle's worth of drift/noise — tens of samples, not a value comparable to what was
just "corrected." (Full per-event gaps and % of ceiling: report §3.2.)

### 2. The underlying reading climbs steadily across the whole session, largely independent of when corrections fire

Sampled every ~37 minutes, deliberately offset from correction events:

```
08:21:30Z   989.9 samples
08:59:00Z  2,152.8 samples
09:36:30Z  3,425.2 samples
10:14:01Z  5,091.7 samples
10:51:31Z  6,321.1 samples
11:29:02Z  7,352.4 samples
12:06:32Z  8,904.9 samples
12:44:02Z  9,805.5 samples
13:21:32Z 11,655.6 samples
13:59:03Z 12,182.8 samples
14:36:37Z 13,483.2 samples
```

A steady, roughly monotonic climb across 6+ hours, essentially unaffected by the 10 corrections
that fired along the way.

### 3. Ruled out

- **Device/capture instability.** Checked directly, including specifically across the run's
  largest gap (3h10m before correction #6): zero false `captureActive`/`audioActive`/
  `dataFlowing` heartbeat readings after the first minute of daemon startup. (A first-pass broad
  `grep -i false` returned 968 hits that looked alarming; on inspection those were almost
  entirely `[DBG]` "filtered implausible message (false-positive guard)" decoder lines, unrelated
  to capture health — re-checked scoped specifically to heartbeat lines and found clean. Noting
  this so the next person doesn't re-walk the same false lead.)
- **`IClock` implementation artefact.** `SystemClock.cs` (`src/OpenWSFZ.Ft8/SystemClock.cs`) is a
  bare `DateTime.UtcNow` passthrough — no caching, no smoothing, nothing that could produce a
  "sticky" reading on its own.
- **Genuine device clock-rate error at this magnitude.** The first correction alone (105 ms
  accumulated in well under 5 minutes of runtime) implies a clock-rate error on the order of
  thousands of ppm if attributed to the capture device — roughly two orders of magnitude above the
  ~42 ppm independently measured for this exact device
  (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/phase3_clockrate_results_usbcodec.json`).
  A crystal's clock-rate error is also a fixed physical property; it does not grow over the course
  of a single session the way the trend in Evidence 2 does.

### 4. The bookkeeping itself is not the bug

The persistence-streak counter correctly resets after every firing (3/3 → 1/3 on the very next
reading, confirming `driftStreakCount = 0` executes as coded) — Decision 4's persistence gate is
not in question here. What's not resetting is the *deviation value itself*, which is a different
claim than "the correction logic has an off-by-one or a stale-variable bug." Worth a second pair
of eyes on `nominalCycleStart`'s reset (`CycleFramer.cs`, the `driftStreakCount >=
RequiredConsecutiveReadings` block) before ruling this out entirely, but the pattern — the *exact
magnitude* reappearing rather than growing or vanishing — reads more like "correcting the wrong
thing" than "failing to correct at all."

### 5. Working hypothesis (not confirmed) — and a direct contradiction with the prior endurance run's own finding

What the drift check measures may not be genuine capture-device clock-rate drift in this regime,
but a processing/scheduling delay: `CycleFramer`'s own loop (or something upstream feeding it)
falling behind true wall-clock, plausibly correlated with growing CPU/memory load from the native
decoder's accumulating internal state over a long session. Circumstantial support this run:
decode `elapsed=` time grew from a first-100-cycle average of 508 ms to a last-100-cycle average
of 607 ms (+19.6%), and `hashTableRejectCount` grew roughly 17x (≈1,374 → 23,527) over the
session (sampled informally via `/api/v1/status` polling — not systematically logged, a gap worth
closing regardless of how this investigation resolves).

**This directly contradicts `ce13e30`'s own finding.** That run explicitly checked for and ruled
out decode-side slowdown as an explanation for its growth pattern — elapsed times stayed flat
300–600 ms across its entire 7h54m session there, and it attributed its growth to genuine
accumulating drift instead. This run's decode-elapsed-time data points the opposite way. That
tension is itself a lead: either the two sessions are dominated by genuinely different phenomena
(possible — different band, different point in whatever's driving `hashTableRejectCount` growth,
different session length), or one of the two "ruled out" conclusions needs revisiting. Don't
assume this run's hypothesis is simply "the same bug ce13e30 had, restated" — the evidence base
for the two runs disagrees on a specific, checkable point.

If the scheduling-delay hypothesis is correct: a correction cannot fix a scheduling delay — it
can only change which raw samples map to a window. Re-anchoring `nominalCycleStart` to a reading
that reflects processing delay rather than sample-rate mismatch just re-baselines against a
moving target that reappears on the next check, exactly as observed. It would also mean every one
of these 10 corrections discarded real captured audio (all 10 were positive/discard corrections;
82,246 samples ≈ 6.9 seconds total across the session) in response to something the mechanism
cannot actually correct.

## Why this matters

- The change's core Goal — bound cycle-boundary drift from true UTC over a long-running session —
  is not being achieved on real hardware, even though every individual correction is sized exactly
  per its own design. This is a different, and arguably more fundamental, failure mode than
  `ce13e30`'s under-sizing: that run showed the *formula* was wrong; this run shows the formula is
  now right but may be applied to the wrong *quantity*.
- Neither the existing synthetic unit tests nor a short live run could have caught this — the
  `RateClock`/`StepClock` doubles model a clean constant-rate or one-off-step clock, not a
  scheduling-delay signal that only reveals its shape over several hours of real, loaded operation.
- Real audio is being discarded (not silence) on each firing, in response to something that
  doesn't appear to be genuine capture-clock drift. Decode volume looked normal this run (19,077
  decodes, no anomaly noted), but that hasn't been checked rigorously against a
  no-correction-firing control — worth doing before assuming this is harmless.

## Confirmed vs. still open

**Confirmed:**
- Decision 5's sizing formula is implemented and firing exactly per spec — `correction =
  round(confirmed deviation)`, clamped only by the (never-hit) sanity ceiling.
- The persistence-gate streak-reset bookkeeping (Decision 4) is not the bug.
- Capture/device stability was clean for the entire session (checked specifically around the
  anomalous 3h10m gap, not just in aggregate).
- The post-correction non-convergence pattern reproduces at every scale observed (1,200–13,800
  samples), all 10/10 events, not an occasional outlier.

**Not yet isolated:**
- Where in the pipeline the measured "deviation" actually originates — genuine capture-rate
  mismatch vs. `CycleFramer`'s own loop-scheduling delay vs. something else entirely.
- Why this run's decode-elapsed-time/`hashTableRejectCount` growth contradicts `ce13e30`'s flat
  elapsed-time finding — same mechanism, same device family, apparently different behaviour.
- Whether the underlying cause is bounded (plateaus, as this run's last few readings loosely
  suggest — 13,037 → 13,403 → 13,037 → 13,801) or continues growing indefinitely over a longer
  session; 6h16m may not be long enough to tell.

## Recommended next steps

1. Instrument each relevant pipeline stage with timestamps (WASAPI `DataAvailable` firing time,
   `Channel<float[]>` enqueue/dequeue instants, `CycleFramer`'s own processing instant relative to
   when it reads `_clock.UtcNow`) — the same approach recommended and not yet done in
   `dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md` Recommended
   Next Step 1, now with a second, independent live dataset (this run) motivating it.
2. Once isolated, reconcile against `ce13e30`'s decode-elapsed-time data specifically — pull that
   run's raw log back out and re-check the elapsed-time claim with the same method used here
   (first-N vs last-N average), since the two runs' conclusions currently point opposite ways.
3. Decide on a fix shape only after 1–2 land. Do not re-tune `CorrectionSanityCeilingSamples`,
   `DriftThresholdSamples`, or `RequiredConsecutiveReadings` blindly against this data — §3.2 of
   the report already shows the sizing math itself isn't where the problem lives.
4. Re-run this same live setup (same device, same technique) against whatever comes out of 1–3,
   checked specifically for whether the post-correction reading actually drops near the noise
   floor rather than re-establishing at the same magnitude — that is the property this run shows
   failing, and the property any fix needs to demonstrate before `tasks.md` 6.6/7.6 can be checked
   off.
5. Consider extending the systematic-sampling gap noted in Evidence 5: `hashTableRejectCount` and
   decode elapsed time were only available via ad hoc `/api/v1/status` polling this run — logging
   them at a regular cadence would remove the need for that going forward.

## Disposition of the pending PR / merge

Found via live testing before merge, per the HK-011 pre-push gate. Recommend **holding**
`fix-cycle-boundary-clock-drift` out of merge until at least steps 1–2 above are addressed —
Decision 5, as implemented and unit-tested, does not achieve the change's stated Goal once run
against a real capture pipeline over a multi-hour session, even though the sizing formula itself
checks out exactly against its own specification.

## Cross-reference

- `qa/endurance/2026-07-24-1cebf81/report.md` — the full run this dev-task summarises (§3.2–3.3
  for the tables above, §5 for the report's own recommendations, which this dev-task narrows into
  concrete next steps).
- `qa/endurance/2026-07-24-ce13e30/report.md` — the prior endurance run that found the *sizing*
  defect Decision 5 fixed, and whose decode-elapsed-time "ruled out" conclusion this run's
  evidence directly contradicts (Evidence 5) — needs reconciling, not just noting.
- `dev-tasks/2026-07-24-cycleframer-correction-sizing-fix.md` — Decision 5, the fix this run
  re-tested.
- `dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md` — the earlier,
  smaller-magnitude live-evidence finding that produced Decision 4's persistence gate. Its
  Recommended Next Step 1 (stage-by-stage pipeline instrumentation) was deferred at the time as
  out of scope; this run is a second, independent data point motivating that it likely can't stay
  deferred through another cycle of this saga.
- `dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md` — the third item in
  this lineage (one-off clock-step slow convergence), status already updated to reflect Decision
  5's effect on its own scenario; unrelated to this finding's root cause but part of the same
  overall mechanism.

## Addendum (2026-07-24): instrumentation landed (8.1), decode-elapsed-time reconciliation done (8.2)

**8.1 — root-cause instrumentation.** Landed per `design.md` Decision 6 (scope amendment — see
`proposal.md`'s Impact section): Debug-level, periodically-aggregated diagnostic timing at three
pipeline stages (`WasapiAudioSource.cs` `DataAvailable` cadence + resampler-drain-to-enqueue
latency; `CaptureManager.cs` chunk-receive cadence + outer-channel write latency, platform-
agnostic so it covers `arecord`/`sox` too; `CycleFramer.cs` real wall-clock inter-window elapsed
time + chunk-dequeue-gap stats). All new timestamps use `DateTime.UtcNow` directly, never
`_clock.UtcNow`, so the existing `RateClock`/`StepClock`/`BouncingClock` test doubles (which model
drift purely as a function of `_clock.UtcNow`'s read count) are unaffected. New test coverage
(`CycleFramerTests.RunAsync_WindowCloses_LogsPipelineTimingDebug`,
`CaptureManagerTests.StartAsync_AfterManyChunks_LogsPeriodicCadenceDebug`) passes; full suites
green. **Not yet exercised live** — this instrumentation has not run against real hardware yet;
that is 8.6, still open.

**8.2 — reconcile against `ce13e30`'s decode-elapsed-time claim.** Re-checked both runs' raw logs
(`logs/openswfz-20260723T222314Z.log` for `ce13e30`, `logs/openswfz-20260724T082055Z.log` for this
run) with the same method, plus a full-session decile breakdown and linear regression the original
first-100/last-100 comparisons didn't do:

| | `ce13e30` | `1cebf81` (this run) |
|---|---|---|
| n cycles with `elapsed=` | 1,897 | 1,502 |
| first-100 avg | 561.2 ms | 507.6 ms |
| last-100 avg | 425.9 ms | 607.0 ms |
| endpoint delta | −24.1% | +19.6% |
| whole-session linear slope | −67.4 ms / 1,000 cycles | +11.0 ms / 1,000 cycles |
| correlation (r) | −0.56 (real, moderate) | +0.06 (~none) |

**Finding: neither "ruled out" / "contributing factor" framing survives intact.**
`ce13e30`'s "elapsed times stayed flat... with no growth trend" is not accurate — there is a real,
moderately-correlated ~24% *decrease*, concentrated in one mid-session step-down (decile 6→7:
545.8 ms → 431.7 ms), not noise. This run's own "+19.6%" headline is real as a raw endpoint
comparison but is not backed by a whole-session trend (r = 0.06, essentially flat) — it is driven
by a noisy final decile (576.4 ms, stdev 99.9) immediately following the *lowest* decile of the
entire session (433.8 ms, decile 9). Net: **decode-elapsed time does not show a clean, monotonic
growth pattern in either run** — the "growing CPU/memory load from accumulating decoder state"
half of Evidence 5's working hypothesis has weaker support than either report claimed, in both
directions. This doesn't resolve the core non-convergence question, but it means 8.3's eventual
fix-shape decision should not lean on "decode elapsed time is provably growing" as supporting
evidence without better data (see 8.4). Errata added to both source reports
(`qa/endurance/2026-07-24-ce13e30/report.md`, `qa/endurance/2026-07-24-1cebf81/report.md`) rather
than silently rewriting their original claims.

`hashTableRejectCount` could not be reconciled the same way — neither raw log contains it (it was
only sampled ad hoc via `/api/v1/status` polling in the 1cebf81 run, never logged), confirming 8.4's
premise that systematic logging is needed before that half of the hypothesis can be checked at all.

**Still open:** 8.3 (decide fix shape — blocked on live data from the new instrumentation, not
just this reconciliation), 8.4 (systematic `hashTableRejectCount`/elapsed-time logging — now more
clearly warranted, since ad hoc endpoint sampling has twice produced a misleading headline), 8.5
(`pre_merge_check.py` gate), 8.6 (live re-confirmation with the new instrumentation — needs real
capture hardware and session time, not something this session can execute). The merge hold stands.

## Appendix: reproduction

- Report: `qa/endurance/2026-07-24-1cebf81/report.md` (+ rendered `report.html`).
- Artefacts: `artefacts/20260724_live_run_0821/` — `openswfz-20260724T082055Z.log` (full daemon
  log), `ALL.TXT` (WSJT-X cumulative decode log), `wav/` (all 1,501 session WAV files, ~522 MB).
  Git-ignored (NFR-021/GDPR), local only — not reproducible from the repo alone; use these files
  directly rather than re-running live.
- Git state at time of this run: `HEAD = 1cebf81` + two uncommitted, zero-`src/` docs changes
  (`proposal.md` content-drift fix, a status update to
  `dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`) — neither affects the
  build under test.
- Evidence tables reproduced via direct `grep`/`awk` extraction of `Cycle boundary resync` and
  `Cycle boundary drift check` lines from `artefacts/20260724_live_run_0821/openswfz-20260724T082055Z.log`;
  exact commands are in this dev-task's originating conversation and mirrored in the report's
  Appendix A.
