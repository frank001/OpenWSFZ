# Endurance Test Report — 2026-07-24 (sizing-fix live re-confirmation)

## 1. Study hypothesis

**What is this run testing?**

This run is the live-hardware re-confirmation step for `fix-cycle-boundary-clock-drift`
(`openspec/changes/fix-cycle-boundary-clock-drift/`, `tasks.md` item **7.6**), following the
correction-sizing fix (`design.md` Decision 5, landed `1cebf81`,
`dev-tasks/2026-07-24-cycleframer-correction-sizing-fix.md`). The prior live endurance run
(`qa/endurance/2026-07-24-ce13e30/`) found the persistence gate (Decision 4) working correctly
but the fixed 48-sample correction cap absorbing as little as 0.3% of confirmed deviation per
firing, leaving a residual drift rate matching the original unfixed D-001 defect. Decision 5
replaced that cap with full absorption of the confirmed deviation, bounded only by a much larger
`CorrectionSanityCeilingSamples` (180,000 samples, one full cycle) intended as a pathological-input
backstop only. A new unit test (`RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`)
confirmed the revised sizing keeps residual bounded near the noise floor in simulation. This run's
purpose, per the dev-task's own Validation plan step 3, was to confirm real-hardware behaviour
matches that simulation before checking off `tasks.md` 6.6/7.6 and reconsidering the HK-011
merge hold.

**Build under test:** `src/OpenWSFZ.Ft8/CycleFramer.cs` at git HEAD `1cebf81` (persistence-gated
correction, `RequiredConsecutiveReadings = 3`, full-absorption sizing,
`CorrectionSanityCeilingSamples = 180,000`). Two docs-only, zero-`src/` changes were made in the
working tree during this session (`proposal.md` content-drift fix, a status update to
`dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`) — neither touches
`src/`, so they do not affect the build under test.

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without crash, audio dropout, or
  unrecoverable gap.
- **H₀-2 (sizing correctness):** Once the persistence gate fires, the applied correction matches
  the full confirmed deviation (not a smaller fixed quantum), and never saturates the much larger
  sanity ceiling under ordinary operation — i.e., Decision 5 is implemented and behaving as
  designed.
- **H₀-3 (bounded residual — the property the simulation predicted):** After each correction
  fires, the measured deviation on the next check drops back near zero (a small multiple of
  `DriftThresholdSamples`, 24) and stays there barring fresh drift accumulating from that point —
  i.e., the fix actually achieves the change's Goal of bounding cycle-boundary drift over a
  long-running session, not just of sizing each individual correction "correctly" in isolation.

**Defects under observation:** `fix-cycle-boundary-clock-drift` (open, `tasks.md` 6.6/7.6 both
still unchecked pending this run). Cross-referenced: `qa/endurance/2026-07-24-ce13e30/report.md`
(the sizing defect this fix targets) and `dev-tasks/2026-07-24-cycleframer-correction-sizing-fix.md`
(the fix this run re-tests).

**What constitutes a meaningful result?**

- Stability: zero crashes, zero unrecoverable gaps, clean shutdown.
- Sizing: every fired correction's magnitude matches its logged confirmed deviation to the
  sample, with zero corrections hitting the sanity ceiling.
- Bounded residual: the drift-check reading immediately following each correction should be
  small (tens of samples, consistent with one fresh cycle's worth of noise/drift), not comparable
  in magnitude to the deviation that was just corrected.

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-24 UTC (local 10:20:55 → 16:37:04 CEST) |
| OpenWSFZ SHA | `1cebf81` (HEAD) + two uncommitted, zero-`src/` docs changes (see above) |
| ft8_lib shim | 20260033 |
| Session start (UTC) | 2026-07-24 08:20:55.638 (daemon start; this session was already running when QA began monitoring) |
| Monitoring window (UTC) | 08:26:03 → 14:30:09 (two consecutive `Monitor` watches, no gap between them) — daemon itself ran further, to graceful stop below |
| Session end (UTC) | 2026-07-24 14:37:04.058 (graceful, operator-initiated `POST` capture-stop; log continued running with capture idle afterwards) |
| Duration (daemon log, start to graceful capture stop) | 6h16m8s |
| Total 15-second cycles (windows emitted) | 1,502 |
| Total decodes (OpenWSFZ) | 19,077 (mean 12.7/cycle) |
| Band | 20 m (14.074 MHz FT8) — **note:** the prior `ce13e30` baseline used 40 m (7.074 MHz). Band is not expected to matter for this mechanism (`CycleFramer`'s drift correction operates purely on capture timing, not decoded signal content), but is recorded for the record since exact reproduction was not attempted. |
| Audio device | USB Audio CODEC (`d451e08c-82b5-446e-a5f1-1bdd8fceeac2`), WASAPI — same physical device as `ce13e30` and the Phase 3 ~-42 ppm measurement |
| WSJT-X | Running in parallel throughout, saving 15 s WAV files and appending to `ALL.TXT` — full `delta_dt`/recall comparison against OpenWSFZ was **not** performed this run (out of scope for this validation step; see §5) |
| Daemon log file | `openswfz-20260724T082055Z.log` (20,835+ lines) — copied into `artefacts/20260724_live_run_0821/` (see §2.1) |
| Shutdown | Graceful (`RecordingStopped (graceful)`; `Capture stopped ... (operator-stopped). Chunks received: 363,867`) |
| Cycle-boundary resyncs fired | 10 (Information level) |
| Cycle-boundary drift checks logged | 1,502 (one per window, Debug level) |

### 2.1 Artefacts

All raw artefacts for this run are gathered under `artefacts/20260724_live_run_0821/` at the
repo root (git-ignored per the repo's existing `artefacts/` rule — NFR-021/GDPR, real
third-party callsigns — local only, never committed). Originally placed under this report's own
directory (`qa/endurance/2026-07-24-1cebf81/artefacts/`); relocated to the repo-root
`artefacts/` convention already used by prior live runs (e.g. `20260723_live_run_2223`,
`20260706_live_run`) — the nested location tripped `tools/pre_merge_check.py`:

| File / folder | Contents |
|---|---|
| `artefacts/20260724_live_run_0821/openswfz-20260724T082055Z.log` | Full OpenWSFZ daemon log for the session under test |
| `artefacts/20260724_live_run_0821/ALL.TXT` | WSJT-X's cumulative decode log (all-time; today's session is the `260724_*` prefixed lines, 39,336 of them) |
| `artefacts/20260724_live_run_0821/wav/` | All 1,501 WSJT-X-saved 15 s WAV files for this session (`260724_082145.wav` … `260724_143645.wav`), ~522 MB total |

**Acceptance thresholds (this run):**

- Stability: 0 crashes, 0 unrecoverable gaps, 0 log ERR/FTL entries.
- Sizing: every correction's magnitude matches `round(confirmed deviation)` exactly; 0 ceiling
  saturations.
- Bounded residual: post-correction reading should fall to within roughly one order of magnitude
  below the pre-correction value at minimum, ideally near the noise floor (tens of samples).

---

## 3. Results

### 3.1 Stability — H₀-1 CONFIRMED

OpenWSFZ ran cleanly for 6h16m8s (1,502 decoded cycles) with no crash and a clean, graceful,
operator-initiated shutdown.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log WRN entries | **1** — a WebSocket send-timeout/dropped-connection at 10:22:13 local, unrelated to `CycleFramer`, before the monitored window's first event |
| Log FTL entries | **0** |
| Heartbeat `captureActive`/`audioActive`/`dataFlowing` false readings | 6, all in the first minute of daemon startup (warm-up); **zero** false readings for the remaining 6+ hours, including through the largest gap between corrections (checked specifically, see §3.2) |
| Daemon process identity | Single PID throughout (no restart) |
| Shutdown | Graceful (`Capture stopped ... (operator-stopped)`) |

**H₀-1: CONFIRMED** — zero failures, clean session, no stability concern with the build under
test.

### 3.2 Correction sizing — H₀-2 CONFIRMED

All 10 corrections fired matched their logged confirmed deviation exactly (rounded), and none
came close to the 180,000-sample sanity ceiling:

| # | Time (UTC) | Gap from prior | Confirmed deviation | Correction applied | % of ceiling |
|---|---|---|---|---|---|
| 1 | 08:26:30.106 | — | 1,264.5 samples (105.37 ms) | 1,264 | 0.70% |
| 2 | 09:12:00.343 | 45m30s | 2,849.1 samples (237.43 ms) | 2,849 | 1.58% |
| 3 | 09:36:00.631 | 24m0s | 3,454.9 samples (287.91 ms) | 3,455 | 1.92% |
| 4 | 09:48:45.979 | 12m45s | 4,173.9 samples (347.83 ms) | 4,174 | 2.32% |
| 5 | 10:20:31.408 | 31m45s | 5,151.6 samples (429.30 ms) | 5,152 | 2.86% |
| 6 | 13:30:32.395 | 3h10m1s | 11,842.0 samples (986.83 ms) | 11,842 | 6.58% |
| 7 | 14:11:48.501 | 41m16s | 13,268.6 samples (1,105.71 ms) | 13,269 | 7.37% |
| 8 | 14:13:34.618 | 1m46s | 13,403.0 samples (1,116.91 ms) | 13,403 | 7.45% |
| 9 | 14:18:50.704 | 5m16s | 13,037.0 samples (1,086.42 ms) | 13,037 | 7.24% |
| 10 | 14:29:51.854 | 11m1s | 13,801.5 samples (1,150.12 ms) | 13,801 | 7.67% |

Total samples absorbed across all 10 corrections: **82,246** (all positive/discard corrections —
zero replay-direction corrections this run). Every correction is, to the sample, the rounded
confirmed deviation logged at fire time — **no capping, no under-correction, exactly what
Decision 5 specifies.**

**H₀-2: CONFIRMED** — the sizing fix is implemented and firing exactly as designed against
whatever deviation value the persistence gate confirms.

### 3.3 Bounded residual — H₀-3 REJECTED (BLOCKING FINDING)

This is where the run diverges sharply from what the simulated unit test predicted. If a
correction genuinely absorbed the confirmed deviation, the very next drift-check reading (one
cycle, ~15 s of real time, later) should show only a small residual — fresh drift/noise
accumulated in that single cycle, not a value comparable to what was just corrected.

**Every one of the 10 corrections shows the opposite:**

| # | Deviation at fire | Very next reading (~15 s later) | Change |
|---|---|---|---|
| 1 | 1,264.5 | 1,286.1 | **+1.71%** |
| 2 | 2,849.1 | 2,807.3 | −1.47% |
| 3 | 3,454.9 | 3,565.6 | **+3.20%** |
| 4 | 4,173.9 | 4,196.8 | **+0.55%** |
| 5 | 5,151.6 | 5,289.7 | **+2.68%** |
| 6 | 11,842.0 | 11,777.3 | −0.55% |
| 7 | 13,268.6 | 13,256.8 | −0.09% |
| 8 | 13,403.0 | 13,141.8 | −1.95% |
| 9 | 13,037.0 | 13,035.0 | −0.02% |
| 10 | 13,801.5 | 13,252.9 | −3.97% |

At every scale from 1,200 to 13,800 samples, the post-correction reading lands within ±4% of the
pre-correction value. The persistence-streak counter does correctly reset each time (3/3 → 1/3,
confirming `driftStreakCount = 0` fires as coded — this part of Decision 4 is not in question),
but the deviation quantity itself is not converging toward zero; it re-establishes at essentially
the same magnitude one cycle later, every single time.

**Session-wide trend, independent of correction timing** (sampled every ~37 minutes across the
whole session, deliberately offset from correction events):

| Time (UTC) | Deviation reading |
|---|---|
| 08:21:30 | 989.9 samples |
| 08:59:00 | 2,152.8 samples |
| 09:36:30 | 3,425.2 samples |
| 10:14:01 | 5,091.7 samples |
| 10:51:31 | 6,321.1 samples |
| 11:29:02 | 7,352.4 samples |
| 12:06:32 | 8,904.9 samples |
| 12:44:02 | 9,805.5 samples |
| 13:21:32 | 11,655.6 samples |
| 13:59:03 | 12,182.8 samples |
| 14:36:37 | 13,483.2 samples |

A steady, roughly monotonic climb across the entire 6h+ session, largely independent of the 10
corrections that fired along the way.

**Ruled out:**

- **Device/capture instability.** Checked directly for the run's largest gap (3h10m before
  correction #6) and the session as a whole: zero false `captureActive`/`audioActive`/
  `dataFlowing` heartbeat readings after the first minute of startup (§3.1). An initial broad
  `grep -i false` search returned 968 hits that looked alarming but turned out to be almost
  entirely `[DBG]` "filtered implausible message (false-positive guard)" decoder lines —
  unrelated to capture health — not heartbeat flapping; re-checked scoped specifically to
  heartbeat lines and found clean.
- **`IClock` implementation artefact.** `SystemClock.cs` is a bare `DateTime.UtcNow` passthrough
  with no caching or smoothing that could produce a "sticky" reading.
- **Genuine device clock-rate error at this magnitude.** The first correction alone (105 ms
  deviation accumulated in well under 5 minutes of runtime) implies a clock-rate error on the
  order of thousands of ppm if attributed to the capture device — roughly two orders of magnitude
  above the ~42 ppm independently measured for this exact device
  (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/phase3_clockrate_results_usbcodec.json`).
  A hardware clock-rate error is also a fixed property of a crystal oscillator; it does not grow
  over the course of a single session the way the sampled trend above does.

**Working hypothesis (not confirmed, flagged for Developer-session investigation):** what
`CycleFramer`'s drift check is measuring may not be genuine capture-device clock-rate drift at
all in this regime, but a processing/scheduling delay — `CycleFramer`'s own loop (or something
upstream feeding it) falling behind true wall-clock, plausibly correlated with growing CPU/memory
load from the native decoder's accumulating internal state over a long session. Circumstantial
support: decode `elapsed=` time grew from a first-100-cycle average of 508 ms to a last-100-cycle
average of 607 ms (+19.6%), and `hashTableRejectCount` grew roughly 17x (≈1,374 → 23,527) over
the session (sampled informally via `/api/v1/status`, not systematically logged — noted as a
limitation). **This is the opposite of what the prior `ce13e30` run found** — that run explicitly
ruled out decode-side slowdown as an explanation (elapsed times stayed flat 300–600 ms there) and
attributed its growth to genuine accumulating drift. This run's data points the other way,
which is itself worth the Developer session's attention: the two runs may be seeing different
underlying phenomena, not necessarily the same one.

> **Erratum (2026-07-24, tasks.md 8.2 reconciliation):** a rigorous re-check of both raw logs
> (`logs/openswfz-20260723T222314Z.log` for `ce13e30`, `logs/openswfz-20260724T082055Z.log` for
> this run) using a full-session decile breakdown and linear regression, not just the two-point
> first-100/last-100 comparison above, complicates this section's framing. This run's own
> "+19.6%" headline turns out to be heavily endpoint-sensitive: the whole-session linear trend is
> essentially flat (slope ≈ +11 ms/1,000 cycles, r = +0.06 — no meaningful correlation), and the
> high last-100 average was driven by a noisy final decile (576.4 ms, stdev 99.9) sitting right
> after the *lowest* decile of the whole session (433.8 ms) — not a sustained climb. Separately,
> `ce13e30`'s "flat" claim also does not hold under the same method — it shows a real, if partial,
> ~24% *decrease* (r = −0.56) concentrated in one mid-session step-down, not decode-side growth
> either. Net: **neither run supports a clean, monotonic "decode load grows over the session"
> story** — this working hypothesis's circumstantial support is weaker than presented above, and
> the growing-CPU/memory-load mechanism should not be assumed without better evidence (e.g. actual
> `hashTableRejectCount`/elapsed-time logging at regular cadence, tasks.md 8.4, rather than ad hoc
> endpoint sampling). This does not resolve H₀-3 either way; it narrows what future investigation
> should treat as established. Full numbers: dev-task addendum,
> `dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`.

If this hypothesis is correct, it means: a correction cannot fix a scheduling delay — it can only
change which raw samples map to a window — so re-anchoring `nominalCycleStart` to a reading that
reflects processing delay rather than sample-rate mismatch just re-baselines against a moving
target that reappears on the next check, exactly as observed. It would also mean each of these 10
corrections discarded real captured audio (all 10 were positive/discard corrections; 82,246
samples ≈ 6.9 seconds of real audio removed across the session) in response to something the
mechanism cannot actually correct.

**H₀-3: REJECTED.** The fix, as sized by Decision 5, does not achieve bounded residual drift on
this real-hardware session — a materially different failure mode than `ce13e30`'s under-sizing,
and one the synthetic `RateClock`/`StepClock` unit tests could not have caught (they model a
clean constant-rate or one-off-step clock, not a scheduling-delay-driven signal).

### 3.4 Decode volume (context only, not analysed further this run)

19,077 total decodes across 1,502 cycles (mean 12.7/cycle) — no anomaly observed here in
isolation. WSJT-X ran in parallel throughout (artefacts gathered, §2.1) but the full
WSJT-X-vs-OpenWSFZ `delta_dt`/recall comparison was intentionally not performed this run, for the
same reason `ce13e30` gave: that comparison is only meaningful once the drift-correction
mechanism is confirmed sound, which §3.3 shows it is not yet.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no crash | 0 crashes, graceful stop | 0 | **PASS** |
| Stability — no log ERR/FTL | 0/0 | 0 | **PASS** |
| Duration | 6h16m8s | — | **PASS** |
| Correction sizing matches confirmed deviation (Decision 5) | 10/10 corrections match logged deviation exactly; 0 ceiling saturations (max 7.67% of ceiling) | correction = round(deviation), no capping | **PASS** |
| Correction bounds residual deviation session-over-session | 10/10 corrections left the next reading within ±4% of the pre-correction value; session-wide reading climbed ~990 → ~13,500 samples largely independent of corrections firing | post-correction reading should drop near the noise floor | **FAIL — BLOCKING** |

**Overall verdict: FAIL (blocking).** Stability is clean and the sizing formula itself is
implemented exactly per Decision 5 — this is not a repeat of `ce13e30`'s under-sizing defect.
But this run demonstrates that, on real hardware over a multi-hour session, firing a
correctly-sized correction does not bring the measured deviation back down — it re-establishes at
essentially the same magnitude on the very next check, every time. Recommend **`tasks.md` 6.6 and
7.6 both remain unchecked** and the HK-011 merge hold **stays in place**.

---

## 5. Recommendations

**Primary recommendation — this needs root-cause instrumentation, not another sizing tweak.**
§3.2 confirms the sizing formula itself is correct; the problem is upstream of it. Before any
further change to `CycleFramer`'s correction logic, the Developer session should establish what
is actually being measured as "deviation" under sustained live load:

1. Instrument (or reason precisely from existing telemetry about) where the gap between
   `_clock.UtcNow` and the arithmetic nominal sequence actually originates — genuine capture-rate
   mismatch (chunks arriving from the audio layer at the wrong long-run rate) versus
   `CycleFramer`'s own loop iteration being scheduled late relative to when data was actually
   captured (CPU/thread-pool contention, GC pressure, channel backpressure).
2. If it is scheduling delay rather than sample-rate mismatch, reconsider whether "discard/replay
   raw samples" is the right remedy at all for that class of deviation — it may need a different
   mechanism entirely, or the drift check may need to measure something closer to genuine capture
   throughput rather than wall-clock-at-loop-iteration.
3. Reconcile this run's decode-elapsed-time growth (+19.6%) and `hashTableRejectCount` growth
   (~17x) against `ce13e30`'s explicit finding of flat elapsed times — worth checking whether that
   difference reflects two genuinely different sessions/loads, or something that changed between
   the two builds under test.
4. Add systematic sampling of `hashTableRejectCount`/decode elapsed time over a session (this run
   relied on ad hoc `/api/v1/status` polling) if session-length CPU/memory load turns out to be a
   real factor — currently a gap in what gets logged.

**Not blocking, but worth folding into the same follow-up:** the WSJT-X-vs-OpenWSFZ `delta_dt`
comparison remains deferred until a revised mechanism is re-validated with another run like this
one, for the same reason given in `ce13e30` and the live-evidence dev-task before it.

**Artefacts preserved for that follow-up:** the full daemon log, WSJT-X `ALL.TXT`, and all 1,501
WAV files for this session are gathered under `artefacts/20260724_live_run_0821/` (§2.1)
specifically so the Developer session doesn't need to reproduce this run from scratch to start
root-cause work.

**Next endurance run:** should be a re-run of this same setup once a revised mechanism (or
diagnostic instrumentation) comes out of the recommendation above, checked specifically for
whether the post-correction reading actually drops near the noise floor rather than
re-establishing at the same magnitude, which is the property this run shows failing.

---

## Appendix A — Reproduction

- Build under test: git `1cebf81`.
- Daemon already running (PID 5564) when QA began monitoring; capture device USB Audio CODEC
  (`d451e08c-82b5-446e-a5f1-1bdd8fceeac2`), 20 m (14.074 MHz FT8), WSJT-X running in parallel.
- Monitoring method: two consecutive background log-tail watches
  (`tail -n0 -F <log> | grep -E "Cycle boundary resync|\[ERR\]|\[WRN\]|\[FTL\]"`), 08:26:03 →
  14:30:09 UTC, no gap between them.
- Post-hoc analysis: direct `grep`/`awk` extraction of `Cycle boundary resync` and
  `Cycle boundary drift check` lines from the full daemon log, cross-checked against
  `/api/v1/status` polls and heartbeat log lines for stability confirmation.
- Full commands used for the §3.2/§3.3 tables are reproducible directly against
  `artefacts/20260724_live_run_0821/openswfz-20260724T082055Z.log`.
