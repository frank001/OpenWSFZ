# Result: OWS-REPLAY-CONSISTENCY step 5, the log step (sweep 1) (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-16 21:07Z (`date -u`). **Spec:** step-test ruling section 3 + amendment 1 (`arch/ows-replay-consistency` `4df9a2e3`): position-matched control (i) is the row that matters, beside the random-instant control (ii); "inside" = interval overlap at about 1 s resolution; (c) confirms only that the instrument is blind; pass durations added; counts only, no CI, no bar. The Captain gave the go in QA's window.
- **Scope line:** `sol` (FX-8350), build `338ef61c` shim 20260062, non-default ALSA chain (`samplerate_best`), replayed B2BASE sweep 1 (S6 SEQUENTIAL, OpenWSFZ pass), daemon log `~/rr-run/b2base-1/daemon.stdout.log` (UTC via `s6_tz.json`, 2 h). **Desk work on kept logs: no run, no decode.** Replayed audio, not the station's live operation; no decode-rate claim; nothing about the Windows station.
- **Tooling:** `qa/rr-study/s6/ows_decode_overlap.py` (commit in the log of `qa/refset`, 6 unit tests). Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/sweep1_decode_overlap_result.json`.

## Definitions as run

Windows of slot S, relative to S. The previous cycle (S-15) decodes in the first seconds: **pass 0 = [0, C]** with C the Cycle line's `elapsed=`; **residual pass = [C, C + R]** with R the pass line's `elapsedMs` (pass line attributed by its adjacent Cycle line, as `s6_analyse.read_pass_lines` does); **decode-active = [0, C + R]**. A step that begins at chunk c has the interval [c - 0.5, c + 0.5] s. Log stamps are whole seconds, so pass starts are anchored on the Cycle line's elapsed. All 180 windows had a previous Cycle line; **11 had no residual-pass line** (their R is missing; they count only where C is enough). Step windows: **21**; step-free windows: 159; the seeded step-free set: 21 (seed 20261016); each step window is paired with one seeded step-free window, which takes that step's c (all steps: c = 3 for 18, 2 for 2, 4 for 1).

## (a) Do the steps fall inside the previous cycle's decode?

Overlap of the step interval with the interval named (counts of steps; the controls are counts of windows):

| interval | the 21 steps | (i) position-matched, the seeded 21 step-free windows | (i) position-matched, ALL 159 step-free windows, at c = 3 (the modal position) | (ii) random instant, the seeded step-free windows |
|---|---|---|---|---|
| decode-active [0, C+R] | **21 of 21** | **14 of 21** (66.7 %) | **111 of 159** (69.8 %) | 3 of 21 (14.3 %) |
| residual pass [C, C+R] | **21 of 21** | 14 of 20 (70 %) | 111 of 148 (75.0 %) | 2 of 20 (10 %) |
| pass 0 [0, C] | 0 of 21 | 0 of 21 | 0 of 159 | 0 of 21 |

(All-step-free at c = 2: 133 of 159 active; at c = 4: 81 of 159.)

**Read plainly:** (i) is NOT about the same in the two groups: 21 of 21 steps lie inside the previous cycle's decode-active period against two thirds to 70 % at the same position in step-free windows. But the step-free windows are mostly inside it too, so coincidence with a decode is common (70 % of step-free windows have the decode still running at c = 3) and does not by itself predict a step: 18 step windows at c = 3 against 111 step-free windows with the decode active at c = 3. Where the previous decode had already ended before c = 3 (48 of 159 step-free windows at c = 3), there are no steps. The random-instant control (ii) is lower (14 %) only because it ignores the position. Pass 0 never overlaps the steps (all steps are at c >= 2 and pass 0 ends by about 1.5 s): uninformative.

**Pass durations (descriptive; seconds):**

| | step windows (n) | step-free windows (n) |
|---|---|---|
| pass 0, C: median / p90 / max | 1.256 / 1.487 / 1.497 (21) | 1.047 / 1.380 / 1.602 (159) |
| residual pass, R | 3.523 / 5.536 / 5.868 (21) | 2.765 / 3.871 / 7.954 (148) |
| decode-active, C + R | 4.962 / 6.792 / 7.194 (21) | 3.779 / 5.232 / 9.091 (148) |

The previous cycle's decode ran longer before the step windows (median 5.0 s against 3.8 s; the residual pass 3.5 s against 2.8 s) but the ranges overlap widely (step-free windows reach 9.1 s).

## (b) Framer lines in the same and the preceding cycle

"Cycle-grid realignment clamped" lines: **5 of 21** step windows have at least one in the same window or the preceding cycle, against **58 of 159** (36 %) step-free windows. No excess for the step windows. Medians 0 in both groups for both cycles. Lines matching the log-drop patterns (overflow, dropped, xrun, overrun, backlog, discard, underrun, DropOldest, stall) in the whole daemon log: **0**.

## (c) Any `arecord` stderr captured anywhere?

Searched for "overrun" or "arecord" in the kept sweep-1 logs (daemon, gatherer, monitor, launcher, the daemon-lib record): **0 mentions in each**. As frozen: this confirms only that the instrument is blind. `arecord`'s stderr is piped and never read, so the logs would read the same whether or not overruns happened.

## Reading and limits

- **Consistent with reading 1** (audio lost while the previous cycle decodes): every step lies where the previous cycle's decode was still running, and no step lies where it had already ended. It is not sufficient: most step-free windows have a decode running at the same position too, so overlap alone does not make a step. Whether the decode's duration (the residual pass was longer before step windows) or something that co-occurs with it matters is not separated.
- **Not the framer, on these counts:** clamp lines are no more frequent around step windows (5 of 21) than step-free ones (58 of 159).
- Resolution: steps are known to about 1 s, log stamps to 1 s; pass starts anchored on the Cycle line's elapsed. With 21 step windows nothing here carries a CI (as agreed).
- Sweep 1 only; the OpenWSFZ pass only; one host, one build, one chain. It does not say what in the capture path loses the audio (the pipe from `arecord`, the reader, the thread that decodes), and nothing about the Windows station.

## NFR-021

Aggregates only; this report and the JSON were scanned for callsign patterns: none. The logs and scratch stay in `~/rr-run/` and `~/qa-scratch/ows-consistency/` on `sol`.
