# Endurance Test Report — 2026-07-24 (short session)

## 1. Study hypothesis

**What is this run testing?**

This is the live-hardware run for `openspec/changes/fix-cycle-boundary-clock-drift/`
`tasks.md` item **8.6**, the step that gathers real-hardware data for item **8.3**'s
fix-shape decision. Unlike the two prior endurance runs against this change
(`qa/endurance/2026-07-24-ce13e30/report.md`, `qa/endurance/2026-07-24-1cebf81/report.md`), this
run does **not** test a new correction mechanism — the correction logic itself is unchanged
since `1cebf81`. It tests whether `tasks.md` 8.1's newly added Debug-level pipeline-timing
instrumentation (`design.md` Decision 6;
`dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`'s Recommended
Next Step 1) reveals *where* the still-growing "deviation" originates: genuine capture-rate
mismatch, `CycleFramer`'s own loop-scheduling delay, or something the instrumented stages don't
see at all.

**Build under test:** `29041f7` (root-cause pipeline-timing instrumentation:
`WasapiAudioSource.cs`, `CaptureManager.cs`, `CycleFramer.cs`) plus `82469ca` (docs-only
test-count correction, no `src/` change) on top, branch
`docs/propose-fix-cycle-boundary-clock-drift`, open PR #108. Reviewed pre-push per HK-011
before this run (see this session's earlier code review) — approved, with the merge hold
explicitly unaffected (8.3/8.4/8.6 remained open going into this run).

**Session length, and why it's short by this change's own precedent:** ~32 minutes, against
`ce13e30`'s 7h54m and `1cebf81`'s 6h16m. This was an explicit, discussed choice, not a shortcut:
per `tasks.md` 7.6's own original plan (a short session first, extend only if the data motivates
it — the multi-hour length of the prior two runs was a *consequence* of what they found, not the
starting intent), and confirmed directly with the Captain at the start of this run. A mid-session
check-in (see §3.2) found the new instrumentation already giving a clean, consistent signal with
no indication more time would change it, so the session was stopped rather than extended by
default. This is stated plainly as a scope limit, not hidden: 32 minutes cannot rule out an
effect that only emerges after hours (see §5).

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without crash, audio dropout, or
  unrecoverable gap.
- **H₀-2 (drift bounded) — carried over, not re-tested by new logic:** the correction keeps
  accumulated deviation small and non-trending. Already rejected twice (`ce13e30`, `1cebf81`);
  not expected to pass here either, since nothing about the correction itself changed. Included
  for continuity, not as this run's point.
- **H₀-3 (pipeline-timing correlation) — this run's actual question:** the growing accumulated
  deviation correlates with growing real inter-window elapsed time (would support genuine
  capture-rate mismatch) and/or growing chunk-dequeue-gap statistics (would support upstream
  capture-pipeline scheduling delay/backpressure). If neither correlates, that rules out both
  explanations *at the three instrumented stages*, narrowing — not yet answering — 8.3's
  root-cause question.

**Defects under observation:** `fix-cycle-boundary-clock-drift` (open, PR #108, not merged;
merge hold per HK-011 stands regardless of this run's outcome — 8.3/8.4 are still open even if
H₀-3 is refuted).

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-24 (local CEST, UTC+2) |
| OpenWSFZ SHA | `29041f7` + `82469ca` (docs-only) on `docs/propose-fix-cycle-boundary-clock-drift` |
| ft8_lib shim | 20260033 (unchanged) |
| Session start | 2026-07-24 18:07:05.369 local (16:07:05.369 UTC) |
| Session end | 2026-07-24 18:39:09.804 local (16:39:09.804 UTC) |
| Duration | 32 minutes 4.4 seconds |
| Total 15-second cycles (windows emitted) | 127 |
| Total decodes (OpenWSFZ) | 2,466 (mean 19.4/cycle) |
| Band | 20 m (14.074 MHz FT8) |
| Audio device | USB Audio CODEC (`d451e08c-82b5-446e-a5f1-1bdd8fceeac2`), WASAPI, 48000 Hz → 12000 Hz — same device family as `ce13e30`/`1cebf81` |
| WSJT-X | Running in parallel throughout; ALL.TXT cleared before this run; capturing session WAV files |
| Daemon log file | `logs/openswfz-20260724T160705Z.log` (git-ignored, local only, NFR-021) |
| Shutdown | Graceful (operator-initiated `POST /api/v1/decode/stop` at 18:39:06; `RecordingStopped (graceful)`; `Capture stopped ... (operator-stopped). Chunks received: 30778`) |
| Cycle-boundary drift checks logged | 127 (one per window, Debug level) |
| Cycle-boundary resyncs fired | 8 (Information level) |
| Hash table reject count (session end) | 1,783 (F-005 metric; not comparable across runs of different length without a rate calculation — not attempted this run, see §5/tasks.md 8.4) |

**Confirmed before monitoring began:** the running binary actually included 8.1's
instrumentation (not a stale pre-instrumentation build) — `WASAPI capture cadence`,
`Capture pipeline cadence`, and `Cycle boundary pipeline timing` Debug lines were all present
in the live log from the first cycle onward.

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 32m4s (127 decoded cycles) with no crash or decode gap.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log FTL entries | **0** |
| Heartbeat count | 384 |
| Heartbeat `=false` readings | 3 total — 2 at 18:07:13/18:07:18 (before `CycleFramer started` at 18:07:19.210; benign startup transient, same pattern already documented in `ce13e30`'s report) and 1 at 18:39:08 (`captureActive=false`, `audioActive=true`, `dataFlowing=true` — logged 2 seconds after the operator-initiated stop at 18:39:06, i.e. the expected shutdown transition, not a fault) |
| Daemon process identity | Single PID (38336) throughout, no restart |
| Shutdown | Graceful (operator API call) |

**H₀-1: CONFIRMED** — zero failures; the only non-`true` heartbeat readings are fully accounted
for by startup and operator-initiated shutdown, not a mid-session fault.

### 3.2 Cycle-boundary drift correction and pipeline-timing instrumentation — non-convergence reproduces immediately; new instrumentation gives a clean negative result

**H₀-2: REJECTED again, as expected.** The same non-convergent pattern `1cebf81` found
reproduced within the first 5 minutes of this run: 8 corrections fired (18:12:00, 18:13:30,
18:15:30, 18:25:15, 18:31:46, 18:32:46, 18:33:46, 18:38:47), each sized exactly to its confirmed
deviation, and none produced a next-reading drop toward the noise floor. First drift-check
reading (18:07:30): 2,385.8 samples. Last (18:39:02): 3,382.1 samples — net growth +996.3
samples over 31.53 minutes ≈ **31.6 samples/min**, remarkably close to `ce13e30`'s whole-session
net rate of ≈34.1 samples/min (+16,155 samples over 474.35 minutes) despite the two sessions
differing in length by more than 14x and in band (20 m here, 40 m there). That consistency is
itself worth noting: it suggests the same underlying mechanism at a comparable rate, not a
different or session-length-dependent phenomenon.

**H₀-3: REFUTED — the pipeline-timing instrumentation shows no correlation with the growing
deviation, at any of the three instrumented stages, across this session:**

| Instrumented signal | Observed range | Trend |
|---|---|---|
| Real inter-window elapsed (`CycleFramer`) | min 14.970 s, max 15.287 s, avg 15.017 s (n=126) | Flat — the one high outlier (15.287 s) coincides with the operator-stop transition at 18:39:02, not a mid-session event |
| Chunk-dequeue-gap avg/max (`CycleFramer`, per window) | avg consistently ~61.9-62.3 ms, max consistently ~63-64 ms | Flat throughout |
| WASAPI `DataAvailable` inter-arrival avg/max | avg ~61.9-62.3 ms, max 62.3-64.1 ms across the session | Flat throughout |
| `CaptureManager` outer-channel write latency avg/max | avg 0.00 ms, max 0.39-0.49 ms | Flat, negligible throughout |

None of these four signals show any growth, drift, or correlation with the ~40% rise in
deviation-at-fire over the session (2,409.6 → 3,453.5 across the 8 corrections). If genuine
capture-rate mismatch were responsible, real inter-window elapsed should itself have drifted
from 15.000 s; it did not. If capture-pipeline backpressure/scheduling delay were responsible,
chunk-dequeue gaps or channel-write latency should have grown; neither did. **This is a real,
useful negative result for 8.3** — it argues against the "scheduling delay visible at the
WASAPI/`CaptureManager`/`CycleFramer`-dequeue stages" half of Evidence 5's working hypothesis,
at least within this session's 32 minutes and its ~40% deviation swing.

> **Erratum (2026-07-24, post-hoc correlation analysis of this run's own artefacts — no new live
> run):** the table above misattributes the session's 15.287 s outlier to "the operator-stop
> transition at 18:39:02" — it did not occur there. The 15.287 s reading actually occurred at
> **18:34:02.058**, immediately following correction #7 (fired 18:33:46.771); the reading logged
> at 18:39:02 was a separate value, 15.282 s, following correction #8 (fired 18:38:47.058) by
> exactly one cycle — four seconds *before* the graceful stop command was even issued (18:39:06),
> not a shutdown artefact either. Correcting the record and looking systematically rather than at
> the two extremes: **every one of this session's 8 corrections is immediately followed by a
> real-inter-window-elapsed spike whose excess over 15.000 s matches the correction's own size, at
> 89-114% (avg 98.5%, n=8)**. This does not overturn H₀-3's verdict on the three *cadence* signals
> (WASAPI inter-arrival, chunk-dequeue gaps, channel-write latency genuinely stay flat), but
> `real inter-window elapsed` itself was mischaracterised — it is not flat, it spikes in lockstep
> with each correction's own magnitude, a per-event signal the slow-trend framing above wasn't
> built to detect. A candidate mechanism (the discard/"lengthen" branch cannot reclaim real time,
> only spend more of it) and a proposed confirming test are recorded in
> `dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`'s addendum. **Not
> yet confirmed as root cause** — this is a code-consistent correlation from existing data, not
> the result of an isolated, controlled test.

**What this does not tell us (scope limit, stated plainly, not discovered after the fact):**
32 minutes is short. It cannot rule out:
- A correlation that only emerges over hours (e.g. the "growing CPU/memory load from the native
  decoder's accumulating internal state" half of Evidence 5 — `hashTableRejectCount` growth —
  which `tasks.md` 8.4 has not yet instrumented for systematic logging; this run's single
  end-of-session value, 1,783, cannot be compared to `ce13e30`'s reported growth without a
  matching per-cycle series).
- Whether the deviation-at-fire values plateauing in a ~3,380-3,470 band for the last 4
  corrections (3,444.5 / 3,466.1 / 3,380.5 / 3,453.5) is a genuine plateau or coincidence — too
  short a window to tell, loosely echoing but not confirming the plateau `1cebf81` suggested
  near its own much longer session's end.
- Any pipeline stage upstream or downstream of the three instrumented here (e.g. the moment
  between "window buffer fully filled" and the code line reading `_clock.UtcNow` executing,
  which 8.1 does not separately instrument).

### 3.3 Decode volume (context only, not analysed further this run)

2,466 total decodes across 127 cycles (mean 19.4/cycle) — consistent with normal decode-pipeline
operation; no anomaly observed. No WSJT-X cross-comparison attempted this run (not this run's
purpose, and the change remains under a merge hold regardless).

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no crash | 0 crashes | 0 | **PASS** |
| Stability — no log ERR/FTL | 0/0 | 0 | **PASS** |
| Duration | 32m4s | — | **PASS (short session, by design)** |
| Correction bounds cumulative drift (H₀-2) | Deviation grew 2,385.8 → 3,382.1 samples (+996.3, ≈31.6 samples/min) despite 8 corrections firing | should stay small/non-trending | **FAIL (expected — no fix landed since `1cebf81`)** |
| Pipeline-timing instrumentation correlates with the growing deviation (H₀-3) | Real inter-window elapsed, chunk-dequeue gaps, WASAPI cadence, and channel-write latency all stayed flat across a ~40% deviation swing | correlation would support a specific root cause | **REFUTED — informative negative result** |

**Overall verdict: as expected on H₀-2 (still non-convergent, unchanged code), genuinely useful
on H₀-3 (rules out two of the three candidate explanations at the instrumented stages).**
`tasks.md` 6.6/7.6/8.6 all remain unchecked; the HK-011 merge hold stands. This run does not
decide 8.3 — it narrows the evidence 8.3 will be decided from.

---

## 5. Recommendations

**Primary — hand H₀-3's negative result to 8.3, do not treat it as inconclusive.** A flat
signal across a real ~40% swing in the thing we're trying to explain is evidence, not absence of
evidence. The next fix-shape discussion should treat "capture-cadence/scheduling-delay, as
visible at WASAPI/`CaptureManager`/`CycleFramer`'s own dequeue point" as a *de-prioritized*
explanation rather than the leading one, pending anything that contradicts this over a longer
run.

**Second — close the `hashTableRejectCount`/decode-elapsed-time systematic-logging gap
(`tasks.md` 8.4) before the next longer live run**, rather than after. This run's single
end-of-session `hashTableRejectCount` value (1,783) was not useful for anything beyond
confirming the counter exists — the same ad hoc-sampling problem `tasks.md` 8.2's reconciliation
already flagged twice. A per-cycle or per-N-minute logged series would make a future longer run
immediately comparable to `ce13e30`'s and this run's data without a follow-on reconciliation
effort.

**Third — a longer follow-up run is still warranted, but from a stated need, not by default.**
Specifically: (a) confirm whether the ~3,380-3,470 plateau in this run's last 4 corrections is
real or coincidental, which needs more corrections than a 32-minute window can produce; (b) with
8.4's logging in place, check whether `hashTableRejectCount`/decode-elapsed growth actually
correlates with the deviation over a multi-hour session, now on a real per-cycle basis instead of
first-N/last-N endpoint sampling (the method `tasks.md` 8.2 already found unreliable twice).

**Not yet addressed by this run:** `tasks.md` 8.3 (fix shape) remains blocked — this run
narrows candidate explanations but does not isolate root cause on its own. Recommend the
Developer session review this report plus `ce13e30`/`1cebf81`'s alongside it before proposing a
fix shape, given H₀-3's result changes which explanations are still live.

**Cross-references:** `dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`
(the finding this run gathers data for); `qa/endurance/2026-07-24-ce13e30/report.md` and
`qa/endurance/2026-07-24-1cebf81/report.md` (the two prior runs against this change);
`qa/endurance/2026-07-24-29041f7/run-notes.md` (this run's raw working notes, timestamped as
gathered).

---

## Appendix: reproduction

- Report: this file (+ rendered `report.html`).
- Artefacts: `artefacts/20260724_live_run_1607/` — `ALL.TXT` (WSJT-X's cumulative decode log,
  cleared before this run started), `owsfx ALL.TXT` (OpenWSFZ's own ALL.TXT, same format,
  also cleared beforehand), `openswfz-20260724T160705Z.log` (full daemon log, 32m4s, 323 KB),
  `wav/` (all 126 session WAV files, ~47 MB, `260724_160730.wav` through `260724_163845.wav`).
  Git-ignored (NFR-021/GDPR), local only — not reproducible from the repo alone; use these files
  directly rather than re-running live.
- Git state at time of this run: `HEAD = 5bcad5c` at time of artefact collection (this report +
  `tasks.md` 8.6 update, committed after the run completed) on top of `29041f7` (instrumentation
  under test) + `82469ca` (docs-only test-count fix, no `src/` change).
- Evidence figures reproduced via direct `grep`/`awk` extraction of `Cycle boundary drift check`,
  `Cycle boundary resync`, and `Cycle boundary pipeline timing` lines from
  `artefacts/20260724_live_run_1607/openswfz-20260724T160705Z.log`; the live monitoring script
  used during the run itself is preserved at `qa/endurance/2026-07-24-29041f7/monitor.sh`.
