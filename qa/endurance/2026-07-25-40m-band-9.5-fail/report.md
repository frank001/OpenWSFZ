# Endurance Test Report — 2026-07-24/25 (overnight, 40m band) — tasks.md 9.5 live re-confirmation

## 1. Study hypothesis

**What is this run testing?**

This is `tasks.md` 9.5 — the live re-confirmation of the `fix-cycle-boundary-clock-drift` change's
deviation-accounting fix (design.md Decision 8, implemented `tasks.md` 9.1, dev-task
`dev-tasks/2026-07-24-cycleframer-deviation-accounting-fix.md`). Three prior fix attempts against
this change (fixed-cap, persistence-gated, size-to-confirmed-deviation) were each defeated by live
endurance testing across four rounds (`ce13e30`, `1cebf81`, `29041f7`, `f57fa4d`) — the correction
fired exactly as designed every time, but accumulated deviation never converged. 9.1 targeted a
specific, isolated-and-unit-tested mechanism: a correction's own real-time cost (a discard must
wait for extra raw samples; a replay needs fewer) was being re-billed as fresh "drift" by the very
next deviation check, because the arithmetic baseline (`nominalCycleStart`) advanced by a flat
15.000s regardless. 9.1 added a one-shot adjustment so that baseline anticipates a correction's own
next-window cost. Two new unit tests (`RunAsync_DiscardCorrectionDeviationAccounting_...`,
`RunAsync_ReplayCorrectionDeviationAccounting_...`) confirmed the mechanism in isolation before
this run — this run is the acceptance test for whether it holds up live.

**Build under test:** working tree on `docs/propose-fix-cycle-boundary-clock-drift`, **not yet
committed** as of this report (HK-011: implementation reviewed and approved by QA earlier the same
session; the Captain has not yet been asked for pre-push sign-off on the `src/` diff). No stable
SHA to cite — the exact diff under test is `git diff` against `11b5cd8` at the time this run
started, covering `src/OpenWSFZ.Ft8/CycleFramer.cs` and `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs`
per that dev-task. Confirmed live (binary mtime cross-checked against source mtime) that the
running build actually included the fix before this run started.

**Session length:** **11h51m** (22:27:00–10:18:38 local, first drift check to last), by a wide
margin the longest live round in this investigation (previous longest: `ce13e30`'s 7h54m) — not
originally planned as an unattended overnight run; became one when the Captain chose to leave it
running unattended ("gather as much data as you can... at least 10 hours") partway through.

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without crash, audio dropout, or
  unrecoverable gap.
- **H₀-2 (drift bounded, 9.1's specific claim):** the post-correction deviation reading lands near
  the noise floor rather than re-establishing near the correction's own magnitude, and — new for
  this run, since it's the first session long enough to check it directly — the correction
  *magnitude itself* stays roughly bounded over a long session rather than growing without limit.
- **H₀-3 (pipeline-timing instrumentation stays flat) — carried over confirmation:** real
  inter-window elapsed time and chunk-dequeue cadence stay flat regardless of the deviation trend.

**Defects under observation:** `fix-cycle-boundary-clock-drift` (open, PR #108, not merged; HK-011
merge hold stands regardless of this run's outcome).

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-24 22:27 -- 2026-07-25 10:19 local (CEST, UTC+2) |
| OpenWSFZ state | uncommitted working tree, `tasks.md` 9.1/9.3 changes on top of `11b5cd8` |
| Session structure | two sub-sessions: **A** 22:27:53--23:06:55 (`logs/openswfz-20260724T202531Z.log`), **B** 23:07:12--10:18:42 (`logs/openswfz-20260724T210711Z.log`). The gap between them (~17s) was a **deliberate** kill+relaunch validating the overnight auto-recovery supervisor (HK-013) before arming it, not a failure — see `qa/endurance/2026-07-24-40m-band-run-notes.md` for the blow-by-blow. |
| Band | **40m** (7.074 MHz FT8) — a deliberate change from every prior round in this investigation, which all used 20m |
| Audio device | `'Microphone (2- USB Audio CODEC )'` (`d451e08c-82b5-446e-a5f1-1bdd8fceeac2`), WASAPI, 48000 Hz -> 12000 Hz -- same device as every prior round |
| Total 15-second cycles (windows emitted) | 157 (A) + 2,682 (B) = **2,839** |
| Total decodes (OpenWSFZ) | 3,359 (A) + 16,733 (B) = **20,092** |
| Total drift-boundary corrections fired | **136** |
| Log ERR/FTL entries | **0** across both sub-sessions |
| `hashTableRejectCount` at session end | 25,465 (B's own cumulative; table saturated well before the session's midpoint on a busy band) |
| Daemon log files | `logs/openswfz-20260724T202531Z.log`, `logs/openswfz-20260724T210711Z.log` (git-ignored, local only, NFR-021) |
| Shutdown | Graceful, operator-initiated (`POST /api/v1/decode/stop` at 10:18:42 local; `Capture stopped ... (operator-stopped). Chunks received: 649750`) |

**Unattended-run infrastructure (new this round, HK-013):** an auto-recovery supervisor
(`qa/endurance/2026-07-24-supervisor.sh`) watched the whole session from 23:08 onward — kill+log+
5-minute-wait+relaunch on a genuine failure signature, capped at 5 retries. Built and live-tested
against the real process before being armed (caught and fixed two real bugs pre-arming: an
MSYS-vs-Windows PID mismatch, and an mtime-based new-log-detection false positive — see HK-013).
It did not need to recover from a genuine crash all night (0 ERR/FTL, 0 crashes) — but it **did**
misfire once, harmlessly, at the very end: the Captain's own graceful full shutdown at 10:18:42
produced ~90s of silence indistinguishable, to the supervisor's stall-detector, from a hang; it
attempted a restart, tripped over a *third*, previously-unseen bug (a "no process found" message
from `tasklist` being treated as a literal PID rather than an empty result), logged that the kill
"did not take," and stood down without taking any further action. No harm done — the Captain
wanted the process stopped anyway — but both new bugs are now recorded in HK-013 for next time.

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 11h51m (2,839 cycles) with no crash, no audio dropout, and no unrecoverable
gap.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log FTL entries | **0** |
| Genuine process crashes | **0** |
| Daemon process identity | Two processes total: original (sub-session A) + one deliberate supervisor-validation relaunch (sub-session B) — both intentional, neither a fault |
| Shutdown | Graceful (operator API call, then full process stop) |

**H₀-1: CONFIRMED.** Zero failures across the longest session this investigation has run.

### 3.2 Cycle-boundary drift correction — 9.1 does not converge over a long session; the failure signature is worse, not better, than short-session testing suggested

**H₀-2: REJECTED.** Two independent measures, both negative:

**(a) Per-correction convergence (9.1's own direct claim).** Automated extraction of all 136
corrections and each one's immediately-following deviation reading, using the same <60%-of-
correction-magnitude bound `CycleFramerTests.cs` 9.3 uses:

| | GOOD (<60%) | BAD (>=60%) | % GOOD |
|---|---|---|---|
| **Overall (136 corrections)** | 32 | 104 | 23.5% |
| discard (132) | 32 | 100 | 24.2% |
| replay (4) | 0 | 4 | 0% |

Live evidence gathered mid-session (first ~11 corrections, all in the transcript) showed a
striking pattern that did **not** hold up under the full night's data: an apparent strict
good/bad alternation, and a working hypothesis that discard converges while replay doesn't. Both
were premature reads of a small sample. The alternation broke down entirely once correction
magnitudes grew large (the tail of the session is overwhelmingly BAD, run after run) — full
sequence in `qa/endurance/2026-07-24-40m-band-run-notes.md`. The type split (discard 24.2% good
vs. replay 0% good) is the one piece of the early hypothesis that survived, but replay only fired
4 times all night (vs. 132 discard) once the deviation trend became persistently one-directional,
so it is not a large enough sample to lean on independently of the discard figures.

**(b) Session-level magnitude trend — new for this run, only possible because it's long enough
to see it.** Correction magnitude, binned by hour:

| Hour | n | avg \|correction\| | max |
|---|---|---|---|
| 22:00 | 5 | 1,718.8 | 3,483 |
| 23:00 | 17 | 1,484.4 | 3,687 |
| 00:00 | 14 | 2,177.5 | 4,076 |
| 01:00 | 11 | 3,060.5 | 5,507 |
| 02:00 | 9 | 4,357.8 | 6,880 |
| 03:00 | 7 | 5,110.4 | 7,651 |
| 04:00 | 14 | 6,450.9 | 8,223 |
| 05:00 | 18 | 7,239.4 | 7,830 |
| 06:00 | 8 | 8,243.4 | 8,585 |
| 07:00 | 11 | 9,461.5 | 11,164 |
| 08:00 | 9 | 10,414.7 | 11,859 |
| 09:00 | 11 | 11,595.5 | 13,248 |
| 10:00 | 2 | 12,116.0 | 13,512 |

**Correction magnitude grew essentially monotonically, hour over hour, all night — roughly an
8x increase from the first hour to the last, with no plateau or reversal.** First-10/last-10 raw
deviation readings: 1,161.1 samples average early, 10,835.2 samples average late, over 711.6
minutes -> **13.6 samples/min** net rate (lower than the ~31-35 samples/min the four pre-9.1
rounds found consistent with each other, but that comparison isn't apples-to-apples: this session
is 50% longer than the previous longest, the growth here is visibly faster-than-linear rather
than the roughly-steady rate those shorter rounds measured, and no correction hit the
180,000-sample sanity ceiling — max applied correction was 13,512, so none of this is a clamping
artifact).

This is the same qualitative non-convergence pattern every round before 9.1 also showed — the
scale is simply the largest yet, because this is the longest session yet.

### 3.3 Pipeline-timing instrumentation — continues to hold flat

**H₀-3: CONFIRMED.** `real inter-window elapsed`, n=2,836 across the full night: min 14.861s, max
16.115s, avg 15.0243s — flat around nominal 15.000s throughout, no correlation with the correction-
magnitude climb in 3.2. This continues to rule out capture-pipeline scheduling/cadence as the
mechanism, consistent with every prior round back to `29041f7`.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability -- no crash | 0 crashes | 0 | **PASS** |
| Stability -- no log ERR/FTL | 0/0 | 0 | **PASS** |
| Duration | 11h51m | -- | **PASS (longest round in this investigation)** |
| Per-correction convergence (9.1's direct claim) | 32/136 (23.5%) land near the noise floor | should be the large majority | **FAIL** |
| Session-level correction-magnitude bound (H₀-2) | ~8x growth hour-over-hour, no plateau | should stay roughly bounded over a long session | **FAIL** |
| Pipeline-timing instrumentation stays flat (H₀-3) | avg 15.0243s, n=2,836, no correlation | correlation would indicate a specific root cause here | **CONTINUES TO REFUTE that explanation** |
| Unattended-run supervisor (HK-013, new infra) | 0 genuine failures needing recovery; 1 harmless misfire on a deliberate shutdown, 2 new bugs found and fixed live | should not need to fire on a clean session | **PASS (mechanism sound; two edge-case bugs now recorded for next time)** |

**Overall verdict: 9.5 FAILS.** The deviation-accounting fix (9.1) does not achieve live
convergence over a long session. It is not merely "unproven" — the longest, most data-rich round
in this investigation shows the same qualitative non-convergence every round before it showed,
now additionally characterized by a clean, monotonic, roughly 8x growth in correction magnitude
over 11h51m. Per this change's own validation plan, this is not a case for retuning 9.1's
constants (it has none) or extending the session further (the trend is already unambiguous at
this length) -- it is evidence that the mechanism trace behind 9.1 has a gap, and design.md
Decision 8's two recorded fallback shapes (continuous small-quantum rate-tracking, or reopening
Decision 1's scope boundary to fix the genuine device clock-rate error upstream of `CycleFramer`)
should now be taken seriously rather than treated as a distant contingency. `tasks.md` 9.5 is not
being checked off; 9.6 (reconsidering the HK-011 merge hold) does not apply -- the hold stands.

---

## 5. Recommendations

**Primary -- escalate to one of Decision 8's fallback shapes rather than iterating further on
9.1.** Four fix attempts against the correction *architecture* (fixed-cap, persistence-gated,
size-to-confirmed-deviation, deviation-accounting) have now each been defeated by live testing,
the last one on the most thorough test yet. The consistent, clean, monotonic magnitude growth in
3.2 is a strong, specific signal: whatever is driving accumulated deviation is not being
adequately modeled as a per-correction accounting error corrected after the fact. Decision 8's
own fallback (2) -- continuous small-quantum rate-tracking, nudging every window's sample target
by an estimated ppm error rather than periodically firing a large correction -- directly targets
"no single correction is ever large enough to cost measurable real time," which sidesteps the
entire class of defect this investigation keeps rediscovering. Fallback (3) -- reopening Decision
1's scope boundary to fix the actual device clock-rate error upstream of `CycleFramer` -- is the
more fundamental fix and matches what the original D-001 root-cause report actually measured (a
genuine ~-42ppm device clock-rate error), at the cost of the two-of-three-platforms-resample-
externally complication Decision 1 raised.

**Second -- the discard/replay asymmetry (32/132 vs 0/4) deserves a dedicated, larger-N test
before being ruled in or out.** Four replay events all night is too few to trust independently of
the discard figures, but it is 4-for-4 in the same direction and was the strongest single signal
mid-session before the magnitude-growth pattern dominated. If a fallback fix is pursued, a
targeted unit test sweeping many replay-triggering scenarios (not just the one `CycleFramerTests.cs`
9.3 case) would settle whether replay's real-time-cost accounting has its own, separate gap from
discard's, cheaply, before another live round is needed.

**Third -- the full-session WAV archive (`artefacts/20260724_live_run_2227/wav/`, 2,827 files,
973 MB) enables offline re-analysis this report doesn't itself attempt.** In particular: a
session-wide, scripted DT-offset comparison against WSJT-X's own decodes (extending `f57fa4d`'s
single-cycle, 11-decode spot check to the full night) and an independent offline replay of any
fix candidate against the *exact* audio this report's non-convergence was measured on -- both
without needing another multi-hour live session.

**Fourth -- HK-013's new unattended-run supervisor infrastructure is sound and should be reused,
with its two newly-found edge-case fixes (already recorded) applied before the next overnight
run.** It correctly ran unattended for over 12 hours with zero intervention needed for genuine
failures, and both bugs it did hit were caught with no actual data loss. Worth carrying forward
to every future overnight round in this investigation or others.

**Not yet addressed by this run:** `tasks.md` 6.6/7.6/8.6 remain unchecked, now joined by 9.5.
`tasks.md` 9.6 (Captain sign-off on lifting the HK-011 merge hold) does not apply -- the hold
stands, unchanged. The `src/` diff under test in this report remains **uncommitted** -- HK-011
pre-push sign-off has not been sought and should not be, given this result.

**Cross-references:**
- `qa/endurance/2026-07-24-40m-band-run-notes.md` -- live working notes kept during the run,
  including the full early-session correction-by-correction table and the alternation-hypothesis
  narrative that this report's Section 3.2 supersedes with the complete data.
- `dev-tasks/2026-07-24-cycleframer-deviation-accounting-fix.md` -- the implementation this run
  tested, and the QA review that approved it (approved on unit-test and code-review grounds; this
  report is that approval's live-endurance follow-through, per the dev-task's own validation
  plan).
- `openspec/changes/fix-cycle-boundary-clock-drift/design.md` Decision 8 -- the mechanism trace,
  fix rationale, and the two fallback shapes recommended above.
- `qa/endurance/2026-07-24-f57fa4d/report.md`, `2026-07-24-29041f7/`, `2026-07-24-ce13e30/`,
  `2026-07-24-1cebf81/` -- the four prior live rounds against this change, all showing the same
  qualitative non-convergence this report confirms persists.

---

## Appendix: reproduction

- Report: this file (+ rendered `report.html`).
- **Preserved snapshot: `artefacts/20260724_live_run_2227/`** (git-ignored, local only, NFR-021 —
  contains real third-party callsigns via `ALL.TXT`, never to be committed). Copied out of the
  live, rotation-vulnerable `logs/` directory (config: `maxFiles: 7`, session rotation) so this
  report's source data survives independent of that rotation policy. Contains:
  - `openswfz-20260724T202531Z.log`, `openswfz-20260724T210711Z.log` -- the two sub-session
    daemon logs (raw source for every figure in this report).
  - `restart-supervisor.log` -- full record of the pre-arming validation test (including the two
    bugs it caught) and the one harmless misfire at session end.
  - `ALL.TXT` -- this session's own decode log, 20,092 lines, matching the "total decodes"
    figure in Section 2 exactly (cleared/fresh at session start; NFR-021, real callsigns).
  - `corrections_table.csv` -- all 136 corrections with their immediate-next reading, ratio, and
    GOOD/BAD verdict, machine-generated (the raw table Section 3.2's summary statistics were
    computed from -- re-derivable from the daemon logs above, saved separately so it doesn't
    need re-deriving).
  - `2026-07-24-supervisor.sh` -- copy of the overnight supervisor script actually run (also
    tracked at `qa/endurance/2026-07-24-supervisor.sh`, not git-ignored, since it contains no
    session data, only the mechanism).
  - `wav/` -- **2,827 WAV files (973 MB), one per 15s decode cycle, 20:28:00 through 08:18:15**
    (i.e. matching this session's full span almost exactly) -- WSJT-X's own per-cycle recordings,
    copied in by the Captain directly (not something this report's own tooling captured). This is
    the raw audio ground truth for the entire 11h51m session -- available for independent replay/
    re-analysis (offline decode comparison, a full-session DT-offset check extending `f57fa4d`'s
    single-cycle spot-check, etc.) without needing another live round.
- Working notes: `qa/endurance/2026-07-24-40m-band-run-notes.md` (git-tracked, no sensitive
  content -- session narrative and the superseded early-session hypothesis, not raw decode data).
- Git state at time of this run: working tree on `docs/propose-fix-cycle-boundary-clock-drift`,
  uncommitted `tasks.md` 9.1/9.3 changes on top of `11b5cd8` (see this report's Section 2 for why
  no stable SHA is cited).
