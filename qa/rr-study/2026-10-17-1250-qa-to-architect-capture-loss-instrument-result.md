# Result: capture-loss instrument, controls C1/C2 and one instrumented S6 block (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-17 12:50Z (`date -u`). **Spec:** `2026-10-17-0927-architect-to-qa-spec-capture-loss-instrument.md` plus amendment 1 (`7c31c1dd`). The Captain gave the go for `sol` in QA's window ("go for sol").
- **Scope line:** `sol` (FX-8350), build `f2beb559` = `338ef61c` + the Developer's commit `1c19c2d3` (cherry-picked), `libft8.so` `873287b1…ab03ac6a` at start and end, shim 20260062, non-default ALSA chain (`samplerate_best`), refset standard tier (60 WAVs x 3 trials), **S6 SEQUENTIAL**, one block, log level Information. Replayed audio on `sol`, not the station's live operation; no decode-rate claim; nothing about the Windows station.
- **Run:** supervisor `cl-s6`, 10:38:44Z to 12:27:07Z; run folder `2026-10-17-837a029`; pass W 10:39:58Z, pass O 11:36:31Z (controls 11:29:55Z to 11:36:31Z on the same daemon instance, pid 909257, then the plays). Scenario retries 0, orphans 0.
- **Tooling:** `qa/rr-study/s6/cl_rows.py` (this note's rows), `qa/rr-study/linux/capture-loss-controls.sh`, `s6-phase-cl.sh`, `battery-cl.sh`. Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/capture_loss_rows.json`, `capture_loss_controls.txt`. No `--filter` applies (no test suite in this run).

## Verdict in four lines

- **V: valid.** Both controls PASS on the first attempt; S6-V1, V2, V3, V4, V5, V7 PASS; no watchdog restart; step rate 22 / 180 is inside the 2-40 band.
- **RC-11: HIT.** O1 = 21 / 22 = **95.5 %** (>= 80 %), O2 = 0 of 158 step-free windows, O1 - O2 = **+95.5 pp, 95 % CI [+84.2, +100.0]** (lower bound above 0).
- **K1 holds 21 of 22 steps (95.5 %)**: the working cause is **loss on the `arecord` side (L1/L2)**. The pre-stated reading "O1 high, O2 low" applies. K2 = 0, K3 = 1, K4 = 0.
- **The channel (L3) lost nothing:** `CaptureChannelDroppedChunks` = 0 at hand-over, no drop Warning in the block.

## V: validity

| item | result |
|---|---|
| Pins (start / end) | build `f2beb559…`; `libft8.so` `873287b1…ab03ac6a` both ends (S6-V5 PASS, pid 909257); WSJT-X `2f968b2f…`; tooling `837a0298` |
| S6 validity | V1, V2 (incl. onset +0.1 s, 174 plays read), V3, V4 (180 plays), V5, V7 PASS; abandonment 0 of 180 |
| C1 (SIGSTOP `arecord` 2.0 s) | **PASS**, attempt 1: counter 0 -> 1 within 5 s of `-CONT`; next window `wanted` **24002** samples (bar >= 12000). No restart |
| C2 (SIGSTOP daemon 3.0 s) | **PASS**, attempt 1: counter 1 -> 2; next window `wanted` 20892. No restart |
| Verbatim `arecord` text | `overrun!!! (at least 0.315 ms long)` (C1) and `overrun!!! (at least 0.404 ms long)` (C2). All 24 lines have this form |
| Watchdog | `watchdogRestartCount` unchanged in both controls; 0 "Capture ended unexpectedly" lines in the log |
| Counters at hand-over | overruns 2, reported ms 1, channel drops 0; log total at the end: 24 overruns (2 control + **22 in the block**) |

**Two things the controls taught that the spec did not expect (both recorded before the block):**
1. `arecord`'s "at least N ms" is **not the lost duration**: 0.3 ms for a 2 s stall, 0.4 ms for a 3 s stall. `CaptureOverrunReportedMs` therefore carries no size information. O6's reported-length column is empty by nature. The size of a loss is read from the step and from `wanted`.
2. After a loss the framer **converges at 3000 samples per window** (the clamp), so a 2 s loss needs about 9 windows (C1: 24002, 21031, 18166 ... 70, 8).

## O1 - O7 (anchor +-2 s; J = 0.01541 s from this run's WSJT-X captures at p99.9; B2BASE sweep-1 J = 0.01704 s beside it)

A step between chunk k and k+1 starts at chunk k+1 and its interval is [cycle start + k+1, +k+2) UTC (the step test's own definition). Overrun time = the UTC millisecond time in the Warning text. WAV-clustered bootstrap, 2,000 resamples of the 60 WAVs, **seed 20261017**, 2,000 of 2,000 resamples usable. One step is 4.5 pp here; the CI is accordingly wide at the bottom.

| row | result |
|---|---|
| **O1** | **21 of 22** step windows have an overrun within +-2 s = **95.5 %** (CI [84.2, 100.0]) |
| **O2** | **0** (the position-matched test on all 158 step-free windows: not one overrun within +-2 s at those chunk positions) |
| O1 - O2 | **+95.5 pp, CI [+84.2, +100.0]** |
| sensitivity (never scoring) | +-1 s: O1 20/22 = 90.9 %, O1-O2 CI [+78.3, +100.0]. +-4 s: 22/22 = 100 %, O2 = 0. J = 0.01704 (sweep 1) at +-2 s: identical (22 steps, 21 hits) |
| **O3** | **1** of the 22 block overruns lies outside +-2 s of every step: #9, 5.1 s into its window (reported 0.17 ms). It produced no step above J |
| **O4** | channel drops **0**; no Warning line. L3 did not lose audio in this block |
| **O5** | the window after a step has `wanted` >= +0.2 s in **22 of 22** (100 %); quartiles of those `wanted`: min 2455, 4451, median 6716, 17769, max 31889 samples. Control, step-free windows: 31.6 % have `wanted` >= 2400 raw, but **0 of 25** once the windows within 10 cycles after a step are excluded (the raw figure is the convergence tail of earlier losses, not a second mechanism; step-free quartiles: -235, 10, 21, 5169, 28786) |
| **O6** | step sizes: median 0.423 s, max 2.649 s; within 0.05 s of 0.25 s: 5 of 22 (22.7 %); within 0.05 s of any multiple of 0.25 s: 59 %. **Sizes are not clustered at the clamp** (sweep 1: half within 0.05 s of 0.25 s). 9 steps are 1.43-1.54 s. The step size equals the framer's next-window `wanted` in samples to within 10 % for 18 of 22 steps (ratio 0.95-1.08; the other four 0.58-0.73 or 1.11): two independent instruments (audio cross-correlation, the sample clock) agree on how much was lost |
| **O7** | step rate **22 / 180** (band 2-40: comparable; sweep 1: 21 / 180). OpenWSFZ own consistency (live pass O) **63.4 %**; the replay of the archive windows reproduces it exactly (A = L = 0.6339, 0 of 175 passes abandoned, pin held). Sweep 1: 71.5 %; B2BASE band 63.3-74.8 %: **at the bottom edge of the band**, below sweep 1. WSJT-X own consistency 93.9 %. Positive agreement W vs O 60.7 % |

### K1 - K4 (one class per step, first match)

| class | steps | share |
|---|---|---|
| K1 (overrun within +-2 s) | **21** | **95.5 %** |
| K2 (channel drop within +-2 s) | 0 | 0 % |
| K3 (`wanted` >= +0.2 s, no overrun) | 1 | 4.5 % |
| K4 (unseen) | **0** | 0 % |

**Working cause (>50 %): K1.** K4 is 0, so the instruments do see the loss. The one K3 step is 2.65 s with the nearest overrun 3.1 s after the chunk start (outside +-2 s, inside +-4 s): it is a timing-resolution case, not a fourth place.

Overrun time minus the step's start chunk: -0.15 to +3.12 s, median ~ +0.5 s (the line is printed at recovery, as the amendment expected).

## What else the block shows (descriptive, not pre-registered; counts)

- **Correction 2026-10-17 (F1 baseline recompute):** the "80 of 180" below was counted on the framer line of the window AFTER each play (cycle start + 15 s). On each play's OWN window line it is **79 of 180 (44 %)**, 65 at the clamp both ways, and per trial 27 / 20 / 32 off-grid, 21 / 17 / 27 at the clamp, 10 / 6 / 6 overruns. The Architect's reconstruction (79) is the own-window count; the loss size (O5/K3) correctly uses the next window.
- **The step count understates the damage.** In 80 of 180 windows (44 %) the framer's `wanted` is outside +-600 samples (50 ms) and 65 windows are at the clamp (applied +-3000). After each loss the grid stays displaced for up to ~9 windows, while the realignment is applied *between* windows, so those windows contain no step above J but are offset from the slot. That is consistent with the earlier finding that OpenWSFZ's capture start wanders (0.52 s vs 0.025 s for WSJT-X). The fix spec should judge against "overruns" and "off-grid windows", not steps alone.
- 22 overruns in 50 minutes and 22 steps: nearly one-to-one. Reported lengths in the block are 0.02-0.19 ms (sum 3 ms); they say nothing about the loss.
- Control overruns (#1, #2) are outside the block (11:30 and 11:33) and not counted in O3.

## What this does and does not establish

- **Does:** where the audio is lost on `sol` in this block: `arecord` reports an overrun at (or within seconds after) 21 of 22 steps and at no step-free position; the channel and the capture watchdog are not involved. RC-11: **HIT** (O1 >= 80 % and the lower bound of O1 - O2 above 0; valid under O7 and A4).
- **Does not:** tell L1 from L2 (the spec did not ask); say why `arecord` is late (CPU headroom, buffer, priority are the candidates; this block cannot choose); say anything for Windows or for a faster CPU; say the step rate on another day. One block, 22 steps, 60 WAVs.
- **Instrument overhead (O7):** step rate 22 vs 21 in sweep 1; consistency 63.4 % vs 71.5 % is inside the old band but lower. One block; no test. QA does not read it as the instrument changing behaviour; it is flagged so that you can.
- **Open item for you:** this note gives no fix. The pre-stated reading names the fix spec's options (CPU headroom, a larger `--buffer-time`, reader priority, #234), each to be judged by `CaptureOverrunCount` on a short run.

## Housekeeping

- Local only, not pushed (HK-033): `qa/capture-loss-instrument` (OpenSpec change `08636dad`), the Developer's `feat/capture-loss-instrument` (`1c19c2d3`), the study tree `qa/capture-loss-study` (`f2beb559`).
- `~/qa-scratch/ows-consistency/` on `sol` stays until you rule; I will delete it then (HK-037). `~/qa-scratch/capture-loss/` (dry run, analysis work files) is deleted at job close.
- Run folder copied to `qa/rr-study/results/` (files only, aggregates, NFR-021 scan clean) as the last step.
