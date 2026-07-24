# Endurance Test Report — 2026-07-24

## 1. Study hypothesis

**What is this run testing?**

This run is the live-hardware validation step for `fix-cycle-boundary-clock-drift`
(`openspec/changes/fix-cycle-boundary-clock-drift/`, open PR #108, branch
`docs/propose-fix-cycle-boundary-clock-drift`) — specifically `tasks.md` item **6.6**, the last
unchecked item and the Captain's HK-011 precondition for lifting the merge hold. That change was
proposed to fix a real, previously-documented defect: three consecutive endurance runs
(`qa/endurance/2026-06-22-f11f438` → `2026-07-06-7340e45` → `2026-07-07-bb0a1c4`) tracked
OpenWSFZ's own decode-cycle DT drifting progressively more negative and more widely spread
relative to WSJT-X (stdev 0.513 → 0.597 → 0.698 s across those three reports), and QA's D-001
live-path investigation (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/`) attributed
~89% of that drift to a genuine ~-42 ppm capture-device clock-rate error compounding through
`CycleFramer`'s never-resynced arithmetic cycle boundary.

A first live pre-merge validation attempt (dev-task
`2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md`) found the originally
proposed correction firing on every single 15 s cycle from cycle 1 — not genuine device drift,
but a recurring ~500–2400-sample pipeline-scheduling latency swamping the threshold check. That
was fixed by gating the correction on **persistence** (`design.md` Decision 4):
`RequiredConsecutiveReadings = 3` consecutive same-sign, non-decreasing readings required before
a correction fires, with `MaxCorrectionSamples` raised 32 → 48. This run is the re-test of that
revised mechanism against the same live setup, to answer the question `tasks.md` 6.6 poses
directly: *does the correction now stay quiet during ordinary operation and only engage for
genuine, sustained, multi-cycle drift?*

**Build under test:** `src/OpenWSFZ.Ft8/CycleFramer.cs` at git HEAD `ce13e308` **plus the
`fix-cycle-boundary-clock-drift` implementation diff, still uncommitted in the working tree**
(persistence-gated correction, `RequiredConsecutiveReadings = 3`, `MaxCorrectionSamples = 48`,
`DriftThresholdSamples = 24`). Not yet reviewed for push per HK-011 — this run is part of the
evidence gathering for that sign-off, not a post-merge regression check.

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without crash, audio dropout, or
  unrecoverable gap.
- **H₀-2 (drift bounded):** The persistence-gated correction keeps the cycle-boundary's
  accumulated deviation from `_clock.UtcNow` small and roughly stable over the session — i.e.,
  firing corrections at a rate and magnitude sufficient to satisfy `design.md`'s stated Goal
  ("bound how far a decode-cycle window's actual sample content can drift from the true UTC
  15-second grid over an arbitrarily long-running session").

**Defects under observation:** `fix-cycle-boundary-clock-drift` (open, PR #108, not merged).
Cross-referenced: `dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md`
(the persistence-gate fix this run re-tests) and
`dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md` (a related, previously
Captain-accepted-as-deferred gap in the same correction mechanism, for one-off clock steps
specifically — see §3.2 for why this run's finding intersects it).

**What constitutes a meaningful result?**

- Stability: zero crashes, zero unrecoverable gaps, clean shutdown.
- Drift correction: H₀-2 confirmed if accumulated deviation stays within a small multiple of
  `DriftThresholdSamples` (24) throughout the session, with corrections firing rarely and
  the residual not showing a sustained, session-long growth trend. H₀-2 refuted if the
  residual instead grows materially and continuously despite corrections firing.

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-23/24 UTC (local 2026-07-24 00:23:34 → 08:17:54 CEST) |
| OpenWSFZ SHA | `ce13e308` (HEAD) **+ uncommitted `fix-cycle-boundary-clock-drift` diff** (`CycleFramer.cs`, `CycleFramerTests.cs`, openspec artefacts) — not merged, not reviewed for push |
| ft8_lib shim | 20260033 (unchanged from the 07-07 endurance baseline) |
| Session start (UTC) | 2026-07-23 22:23:34.069 (capture start) |
| Session end (UTC) | 2026-07-24 06:17:54.878 (graceful operator-initiated stop) |
| Duration | 7 hours 54 minutes 21 seconds |
| Total 15-second cycles (windows emitted) | 1,897 |
| Total decodes (OpenWSFZ) | 31,517 (mean 16.6/cycle) |
| Band | 40 m (7.074 MHz FT8) |
| Audio device | USB Audio CODEC (`d451e08c`), WASAPI, 48000 Hz → 12000 Hz — same device as the Phase 3 ~-42 ppm measurement and the three prior endurance reports |
| WSJT-X | Running in parallel, saving WAV files, per this run's setup instructions — WSJT-X-vs-OpenWSFZ `delta_dt`/recall comparison intentionally **not** performed this run (per the originating dev-task's own ordering: that comparison is gated on this drift-correction re-test going cleanly, which it did not — see §3.2) |
| Daemon log file | `logs/openswfz-20260723T222314Z.log` (26,025 lines; git-ignored, local only) |
| Shutdown | Graceful (operator-initiated `POST /api/v1/decode/stop`; `RecordingStopped (graceful)`, `Capture stopped ... (operator-stopped). Chunks received: 459765`) |
| Cycle-boundary drift checks logged | 1,897 (one per window, Debug level, per `tasks.md` 6.3) |
| Cycle-boundary resyncs fired | 20 (Information level) |

**Acceptance thresholds (this run):**

- Stability: 0 crashes, 0 unrecoverable gaps, 0 log ERR/WRN/FTL entries.
- Drift correction: accumulated deviation should remain small (order of `DriftThresholdSamples`,
  24, to perhaps a few hundred samples) and non-trending over a multi-hour session, consistent
  with the change's stated Goal of bounding — not merely slowing — cycle-boundary drift.

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 7h54m21s (1,897 decoded cycles) with no crash, audio dropout, or decode
gap, on the build under test.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log WRN entries | **0** |
| Log FTL entries | **0** |
| Heartbeat count | 5,716 |
| Daemon process identity | Single PID throughout (no restart) |
| Shutdown | Graceful (operator API call) |

**H₀-1: CONFIRMED** — zero failures, clean session, no stability concern with the build under
test.

### 3.2 Cycle-boundary drift correction — BLOCKING FINDING: correction does not bound cumulative drift

**H₀-2: REJECTED.** The persistence gate (Decision 4) is working exactly as designed at
rejecting the *false-positive* case it was built for — no correction fired on recurring
pipeline-latency noise. But this full-length run surfaces a second, more serious problem the
short validation window couldn't show: **once the gate correctly confirms genuine, sustained
drift, the fixed 48-sample-per-event cap is nowhere near large enough to keep pace with it, so
the cumulative deviation grows through the whole session anyway — the mechanism fires
correctly, but does not bound anything.**

**All 20 resyncs, in order:**

| # | Time (local) | Accumulated deviation at fire | Correction applied |
|---|---|---|---|
| 1 | 00:32:30.154 | 1,848.4 samples (154.03 ms) | 48 (cap) |
| 2 | 00:33:15.149 | 1,736.0 samples (144.67 ms) | 48 (cap) |
| 3 | 00:38:30.148 | 1,673.8 samples (139.48 ms) | 48 (cap) |
| 4 | 00:39:45.182 | 2,044.4 samples (170.37 ms) | 48 (cap) |
| 5 | 00:48:30.211 | 2,341.6 samples (195.14 ms) | 48 (cap) |
| 6 | 01:11:45.277 | 3,084.3 samples (257.03 ms) | 48 (cap) |
| 7 | 01:21:30.306 | 3,384.0 samples (282.00 ms) | 48 (cap) |
| 8 | 01:28:30.339 | 3,729.2 samples (310.76 ms) | 48 (cap) |
| 9 | 01:43:30.369 | 4,044.3 samples (337.02 ms) | 48 (cap) |
| 10 | 03:12:00.625 | 7,065.5 samples (588.79 ms) | 48 (cap) |
| 11 | 03:22:15.663 | 7,469.6 samples (622.47 ms) | 48 (cap) |
| 12 | 03:32:00.684 | 7,681.2 samples (640.10 ms) | 48 (cap) |
| 13 | 03:38:30.731 | 8,189.5 samples (682.46 ms) | 48 (cap) |
| 14 | 03:45:15.752 | 8,394.9 samples (699.57 ms) | 48 (cap) |
| 15 | 03:51:30.779 | 8,678.6 samples (723.22 ms) | 48 (cap) |
| 16 | 03:57:45.786 | 8,711.0 samples (725.92 ms) | 48 (cap) |
| 17 | 04:19:00.843 | 9,351.4 samples (779.28 ms) | 48 (cap) |
| 18 | 04:34:45.906 | 10,060.6 samples (838.38 ms) | 48 (cap) |
| 19 | 06:18:46.196 | 13,484.9 samples (1,123.74 ms) | 48 (cap) |
| 20 | 08:10:16.529 | 17,438.0 samples (1,453.17 ms) | 48 (cap) |

**Every single correction saturated the cap** — the deviation at fire time was always vastly
larger than the 48 samples actually removed. And the deviation at which corrections fire is
itself climbing steadily through the session — not bouncing around a stable floor:

| Time (local) | Deviation reading |
|---|---|
| 00:23:45 | 964 samples |
| 01:01:15 | 2,686 samples |
| 01:39:00 | 3,821 samples |
| 02:16:30 | 4,934 samples |
| 02:54:00 | 6,086 samples |
| 03:31:30 | 7,432 samples |
| 04:09:00 | 8,677 samples |
| 04:46:30 | 10,345 samples |
| 05:24:00 | 11,387 samples |
| 06:01:30 | 12,808 samples |
| 06:39:00 | 13,734 samples |
| 07:16:30 | 15,494 samples |
| 07:54:00 | 16,378 samples |
| 08:17:46 (last reading before operator stop) | 17,119 samples (1,426.55 ms) |

**The arithmetic:** over the full 7h54m21s session, the checked deviation grew from 964 to
17,119 samples — a net increase of 16,155 samples, despite 20 corrections firing along the way.
Total sample-count actually removed by all 20 corrections combined: 20 × 48 = 960 samples — **a
correction pushback of about 6% of the net growth actually observed.** The residual is not being
bounded; it is climbing at a materially unbounded rate for the whole session.

**Net residual drift rate this run: ≈0.171 s/hour** (16,155 samples ÷ 12,000 Hz ÷ 7.899 h). This
is not merely "still present despite the fix" — it is, within rounding, the same magnitude as
the original, independently-measured, *unfixed* defect this whole change exists to eliminate:
QA's D-001 investigation (`proposal.md`, `qa/rr-study/results/2026-07-23-d001-live-path-root-cause/`)
measured OpenWSFZ's live decoded DT drifting at **-0.171 s/hour** relative to WSJT-X, before any
of this fix existed. This run's own internal CycleFramer check — a different measurement,
against `_clock.UtcNow` rather than decoded-message DT vs. WSJT-X, so not a like-for-like
replication of that figure — nonetheless lands on the same order of magnitude, which is a
striking, if circumstantial, sign that the corrected build may be delivering close to none of
the intended benefit over a session this length.

**Ruled out as an alternative explanation:** decode-side slowdown (thread-pool contention
building up over the session, which would show up as growing `elapsed=` decode times and could
independently explain a growing gap between "window ready" and "clock read"). Checked directly —
decode elapsed times stayed flat (300–600 ms) across the entire session with no growth trend, and
no ERR/WRN/FTL log entries or other anomalies appear anywhere in the log. The growth is
consistent with genuine, confirmed, accumulating cycle-boundary drift — exactly the case the
persistence gate is supposed to catch and the correction is supposed to then bound — not a
pipeline-latency or decode-performance artefact.

**Why this happens:** `MaxCorrectionSamples = 48` was sized (design.md Decision 4) as "a
modestly larger cap [than the original 32] to resolve [a threshold crossing] in fewer follow-on
slew events," reasoned from the *persistence gate's delayed-reaction effect* on a single crossing
— not from the accumulated magnitude a real, hours-long, continuously-accumulating drift will
have reached by the time three consecutive non-decreasing readings satisfy the gate. Once the
gate has already confirmed (through persistence) that a reading reflects genuine sustained
drift rather than noise, capping the correction to a small fixed quantum no longer serves the
purpose it was designed for (protecting against a single anomalous/implausible reading,
`design.md`'s Risks section) — it simply throttles the fix's own remedy far below the rate it
needs to keep up with what has already been confirmed as real.

**Relationship to the already-known slow-convergence gap:** this is the same root tension flagged
in `dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md` (a flat cap taking
~19–39 days to absorb a one-off multi-minute clock step) — except that dev-task's scenario was a
rare, hypothetical one-off event the Captain explicitly accepted deferring. **This run shows the
same ceiling applies to the change's primary, everyday target case — ordinary continuous device
clock-rate drift over a multi-hour session — not just an unlikely edge case.** That is a
materially different risk profile than what was deferred on 2026-07-23, and reopens the
question the Captain settled for the one-off-step scenario.

### 3.3 Decode volume (context only, not analysed further this run)

31,517 total decodes across 1,897 cycles (mean 16.6/cycle) — consistent with a normally
functioning decode pipeline throughout; no anomaly observed here. A full WSJT-X-vs-OpenWSFZ
recall/`delta_dt` comparison was intentionally not run this session (§2) and remains blocked on
resolving §3.2 first, per the originating dev-task's own recommended ordering.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no crash | 0 crashes | 0 | **PASS** |
| Stability — no log ERR/WRN/FTL | 0/0/0 | 0 | **PASS** |
| Duration | 7h54m21s | — | **PASS** |
| Persistence gate rejects pipeline-noise false positives | Confirmed — 0 corrections in first ~9 min despite readings exceeding threshold every cycle | no correction on noise | **PASS** |
| Correction bounds cumulative cycle-boundary drift | Deviation grew 964 → 17,119 samples (net +16,155) over the session; corrections removed only 960 samples total (~6% of growth); net rate ≈0.171 s/hr, order-of-magnitude matching the original unfixed D-001 figure | should stay small/non-trending | **FAIL — BLOCKING** |

**Overall verdict: FAIL (blocking).** Stability is clean and the persistence gate correctly
solves the false-positive problem it was built for (§3.2's first paragraph), but this run
demonstrates the correction mechanism, as currently sized, does not achieve the change's own
primary stated goal of bounding cycle-boundary drift over a long-running session. Recommend
**tasks.md 6.6 remains unchecked** and the HK-011 merge hold **stays in place** pending a design
revision.

---

## 5. Recommendations

**Primary recommendation — return to design, not just re-tune a constant.** The core issue is
structural: `MaxCorrectionSamples` conflates two different jobs that need different answers —
(a) bounding a *single, unconfirmed* reading against an implausible one-off event (where a small
cap is exactly right, per `design.md`'s Risks section), and (b) sizing the correction once
`RequiredConsecutiveReadings` has already confirmed the reading reflects genuine, sustained
drift (where a small fixed cap actively defeats the change's Goal #1). Suggest considering,
for the Developer session's design discussion:

1. Once the persistence gate fires, correct by (at least) the full confirmed accumulated
   deviation rather than a small fixed quantum — the gate has already done the work of ruling out
   noise, so there is no remaining reason to under-correct.
2. Keep a separate, smaller safety cap only for the *first* candidate reading in a streak (i.e.,
   before persistence is established) if an implausibly large single reading needs bounding —
   this preserves `design.md`'s original one-off-step mitigation without throttling confirmed,
   persistent drift.
3. Re-open `dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md` for the
   Captain's awareness: this run shows the same flat-cap ceiling affects the change's primary
   continuous-drift case, not only the one-off-step scenario that was explicitly accepted as
   deferred. The two gaps likely share one fix.

**Not blocking, but worth folding into the same follow-up:** the WSJT-X-vs-OpenWSFZ `delta_dt`
comparison (this run's originally intended purpose, per the live-evidence dev-task's Recommended
Next Step 4) should stay deferred until a revised correction is re-validated with another run
like this one — running it against a build that demonstrably doesn't bound drift would not
cleanly test the ~42 ppm hypothesis, for the same reason the very first live-evidence dev-task
gave for pausing it originally.

**Historical thread worth closing the loop on:** the three-run DT-spread trend flagged in
`qa/endurance/2026-07-07-bb0a1c4` §3.4/§5 ("recommend a dedicated look at OpenWSFZ's
cycle-framing/DT-computation path before it is dismissed again") is exactly what this change was
commissioned to address. This run's finding suggests that dedicated look is still not
complete — worth citing this report alongside that trend when the Developer session revisits
the design.

**Next endurance run:** should be a re-run of this same setup (same device, same technique)
against whatever revised correction sizing comes out of the recommendation above, checked
specifically for whether the accumulated-deviation-at-fire-time series stays flat/bounded across
a multi-hour session rather than climbing as it did here.
