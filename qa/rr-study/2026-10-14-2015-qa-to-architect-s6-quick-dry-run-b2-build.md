# The S6 quick-tier dry run on the B2 build: the live path held; WSJT-X stalled inside S6 for the last 24 plays and the paused gate could not see it (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-14 (`date -u` 19:50Z at writing). **Go:** the Captain's direction relayed by the Architect (2026-10-14): "run the S6 quick-tier dry run on sol on the B2 build, M1-M3 on, then STOP AND REPORT". Nothing after it has been started.
- **Dry run, not a baseline, informational. Live-path reading, not a decode-rate claim.** Nothing filed, nothing pushed. Run folder (aggregates only; the recording-derived log slices with real callsigns stay on `sol` in `~/qa-scratch/s6-2026-10-14-68a2111/`, outside git): `qa/rr-study/results/2026-10-14-S6-QUICK-DRYRUN-B2build/` (`report.md`, `s6/`: `s6_result.json`, `s6_validity.json`, `collapse_check.json`, `s6_playlog.jsonl`; `supervisor/`: `monitor.jsonl`, `stall_events.jsonl`, the stall snapshot, the launcher log). NFR-021: scanned, no callsign-shaped tokens.

## Pins

| item | value |
|---|---|
| Build | `338ef61c` (B2 `aab18b75` merged with `main` `76aa48cd`), shim 20260062, daemon published from it; `libft8.so` `873287b114a8674f800d4816fd5362c51175fc050e535d190516e01dab03ac6a` loaded (S6-V5 PASS: equal at start and end); WSJT-X 2.7.0 exe `2f968b2f…` pinned |
| Tooling | `qa/refset` `68a21118` (M1 monitor, M2 gate, M3 coverage; analyser on %StudyVar) |
| Settings | AMD FX-8350, `subtractionMaxThreads` 8 on 8 logical CPUs, subtraction deadline ON (the station value), WSJT-X decoding on the same CPUs, corrected ALSA chain; `nhard`/`osdNhardMax` 24 |
| Run | launcher start 19:18:52Z; WSJT-X up 19:19:59Z; warm-up S6-V3 PASS on attempt 1 (slot 19:21:45); first play slot 19:22:45; 72 plays, 4 batches, last play slot 19:41:15; 0 slips; battery DONE 19:42:31Z |
| Gate | M2 **paused from S6 on** (as built; it is the only scenario here, so the gate ran for 0 s of play) |

## Did the live path hold? (against the 10-13 collapse; daemon log, `collapse_check.json`)

| measure | 10-13, `main` without B2 | 10-14, B2 build |
|---|---|---|
| residual passes in the play window / abandoned | 27 / **4** (budget 11.7 s; abandoned at 10.0 to 11.3 s) | **68 / 0** (elapsed median 3.0 s, p90 3.8 s, max 5.6 s; fitted signals median 11, max 22) |
| late cycles (log line more than 3 s after the slot end) | **32 of 81** | **0 of 78** (lag median 1.0 s, max 2 s) |
| cycle-grid realignment clamp warnings | **71** (56 positive up to +7.161 s, 15 negative to −4.831 s; 4 episodes) | **18**, all positive, `wanted` 0.26 to 1.741 s (the largest at +1.741 s), `applied` always 3,000 samples; 0 negative; 0 episodes |
| drop / overflow / xrun / underrun / stall lines in the daemon log | 0 | 0 |
| blind slots (WSJT-X has rows, OpenWSFZ none) | **43 of 70** | **2 of 47** slots in which WSJT-X had rows (`19:26:45`, `19:29:00`); the other 23 slots (after 19:35:00) cannot be judged: WSJT-X had no rows, OpenWSFZ had rows in 23 of 23 |
| OpenWSFZ decodes per WAV (plays heard by both) | 3.10 | **11.64** (per trial 11.58, 11.71, 11.63) |
| OpenWSFZ own consistency across the three trials of a WAV | 0.0 % | 79.7 % |
| per-play abandonment attribution (`s6_result`) | 4 of 72 plays | **UNKNOWN**: 59 of 68 pass lines map to a play slot, so the analyser withholds it (`not_trusted_because`); the whole-log count above (0 abandoned) does not depend on the mapping |

**Reading (live path only):** with the B2 build the collapse of 10-13 did not recur on this CPU: no abandoned residual pass, no late cycle, the realignment warnings shrank from 71 to 18 and none is negative. The clamps are not zero (positive, up to +1.74 s, each recovering over a few cycles), so the capture path still lags occasionally, but without ever reaching a late cycle. The residual pass median (3.0 s) matches the replay timing of the same morning (3.15 to 3.22 s on block `822498b61291`). **What this does not show:** one run of 72 plays, one CPU, replay-through-loopback of recorded audio, the station's own load absent; the 10-13 run and this one differ in the build only by B2 (and the harness pins), but they are two runs, not a controlled pair.

## The stall inside S6 (found by M1; the gate was paused)

- **M1 logged a stall episode from 19:36:06Z** ("no new save WAV for 51 s") **to the end of the run at 19:42:29Z: 26 consecutive samples not ok, 6.4 minutes.** The process stayed alive (`wsjtx` pid 601651, state S, RSS 206,612 kB constant, 9 threads, `jt9` alive); the WAV count froze at 5,555; no `wsjtx` restart. WSJT-X's last rows are in slot 19:35:00 (its `wsjt-all` has 0 lines after it); the **24 plays from slot 19:35:15 to the last play slot 19:41:15 (24 of 72, a third) were not heard by WSJT-X** (the 26 is the number of 15 s monitor samples in the stall, not plays).
- **Consequence for the S6 figures:** WSJT-X trial 3 has 0.0 decodes per WAV (trial means 17.625, 17.5, 0.0), WSJT-X own consistency 0.0 % (it cannot be 3-of-3), positive agreement 49.7 % and every WSJT-X-involved S6 figure of this run are **contaminated and not citable**. `s6_validity.json` says VALID (V1 to V5 PASS): **S6 has no coverage row**, so a third of its plays unheard by one appraiser passed every validity row. The OpenWSFZ side (live-path table above) is unaffected: its own log and archive are complete (`coverage_slots_owsfz.txt` 85 slots to the end; `coverage_slots_wsjtx.txt` 58, ending at the stall).
- **Snapshot** (`supervisor/stall-2026-10-14T193606Z/`): all nine `wsjtx` threads idle in `do_sys_poll` (the main thread, the Qt event queue, the `QThread` that owns the capture PCM, 601660), `futex_wait` and `hrtimer_nanosleep` on the others; `Xvfb` and `jt9` alive; capture PCM `card0/pcm0c` state RUNNING, 48 kHz, 960-frame periods. **What it does not settle:** I read the same PCM on a healthy WSJT-X started afterwards: `appl_ptr: 0` and `avail == hw_ptr` also in a healthy run (those proc fields do not track the application's reads here), so the ALSA status file is **not** evidence either way. It does show that the process is not busy-looping or blocked in a lock (a frozen `SIGSTOP` process reads `do_signal_stop`, State T, in the injection test).
- **Where this sits with the other two stalls:** 14 Oct 11:09Z (33 min after the WSJT-X start, under playback), **14 Oct 19:35Z (15 min after start, under playback, this run)**, 11 Oct 09:32Z (4 h 39 min after start, idle, no playback). Suspend/resume ruled out for all (cron gap check). WSJT-X sessions on `sol` on 14 Oct that played audio for 5 min or more: B1 (1 h 57 min, no stall), B2 first attempt (stall at 33 min), B2 replacement (no stall), B3 (no stall), S1 smoke (10 min, no stall), retry test attempt 2 (5 min, no stall), this S6 run (stall at 15 min): **2 stalls in 7 sessions**; a rate cannot be read from 7, but it is not rare, and it matters for the baseline's cost (below).

## S6-V2 (offsets) for re-setting the 0.25 s design tolerance

| reading | 10-13 (66 plays read) | 10-14 (44 plays read of 72; 28 had too few matched rows; 24 plays fall after the stall, so most of the 28 are the stall's) |
|---|---|---|
| player call time against the slot boundary (row as designed) | 0.000 s for all 72 plays, 0 outside ±0.25 s | 0.000 s for all 72, 0 outside ±0.25 s |
| per-play median DT shift, replay minus live, of the same WSJT-X rows (the onset row) | min 0.1, p10 0.1, **median 0.1**, p90 0.1, max 0.2 s | min 0.1, p10 0.1, **median 0.1**, p90 0.15, **max 0.2 s** |
| all matched rows | median 0.1, p90 0.2 s (1,165 rows) | median 0.1, p90 0.2 s (780 rows) |
| onset row against its bar [0.0, 0.2] | PASS | PASS, at the upper edge (max exactly 0.2) |

**Proposal (HK-038: where the number comes from).** (1) The ±0.25 s row on the player's call time is vacuous by construction (always 0.000): keep it as a record, but **do not** count it as the V2 tolerance. (2) The informative row is the onset shift. The DT is read to 0.1 s, so the shift can only take values 0.0, 0.1, 0.2, 0.3...; in two runs (110 plays read) it is 0.1 or 0.2 s, the median 0.1 s, p90 0.1 to 0.15 s. A band of **[0.0, 0.3] s** (the observed maximum plus one reading step) would not be at the edge of the data as [0.0, 0.2] is, which is where the bar sits now: a play at 0.2 s passes today only by equality. This is a pilot figure from two runs on one host, not a derived bar; say if you want the plays read counted (28 of 72 were not read in this run) as part of the row.

## Keep-up (S6 amendment 3)

**Not logged by this run.** The S6 battery step does not record WSJT-X's decode times (the `Decoding` status intervals come from the UDP stream of the leg E driver, which S6 does not run), so the keep-up row cannot be filled from an S6 run as built. What exists on the OpenWSFZ side: residual-pass elapsed median 3.0 s (above) and a whole-cycle decode median of 0.99 s (max 1.53 s) from the daemon log. For WSJT-X's keep-up the 70 min and the 33-block leg E runs (WSJT-X alone on the CPU) stand as the figures.

## Settling the three things before the baseline (QA's view, for your decision)

1. **The gate stays on through S6 (as you accepted), and S6 needs its own coverage row.** The proof is in this run: with the gate paused the stall ran unseen for 6.4 minutes and S6 reported VALID. Two changes: (a) delete the pause in `run_study.py` (one block; S6 does not restart WSJT-X, `s6_play.py` read; my earlier "S6 restarts WSJT-X" was my unverified assumption and is withdrawn); (b) **an S6 coverage row in M3**: expected play slots from `s6_playlog.jsonl` against WSJT-X's saved WAV slots, FAIL if fewer than expected − 1, and the same for OpenWSFZ's archive. One policy question for you and the Captain: a stall inside S6, under the series rule "a sweep with an appraiser silent for part of the battery is INVALID", would make the whole sweep INVALID and costs a rerun of ~2 h 50 min; the S6 spec's own rule is "S6 failure voids the S6 block only, S1-S8 stand". Which applies in the baseline?
2. **Tier.** `TIERS` quick 24 WAVs (72 plays, the 24-min check just run), **standard 60 (180 plays, 15 per band, ≈ 47 min)**, extended 180. At quick, `anova_parts` is 0 (no balanced part) and per-band cells are too small ("not given at the quick tier"); I read the per-band and ANOVA output at standard from the spec, not from data. My recommendation: **standard**, since five sweeps of a 24-WAV list give little to compare and the baseline already costs hours; the choice is yours and the Captain's.
3. **S6-V2:** the proposal above.

**Cost, honestly:** with S6 standard the sweep is ≈ 2 h 50 min; 5 sweeps ≈ 14 h; and with 2 stalls in 7 WSJT-X sessions the expected number of attempts per sweep is not 1. The cap of 3 retries per sweep caps one sweep at ≈ 11 h; the worst case you quoted (≈ 57 h) is real if stalls cluster. The cause is still unknown; three events now, two of them under playback within 33 and 15 minutes of the WSJT-X start.

## Two improvements to M1 I would make, no build until you say (the snapshot could not separate "the device stopped delivering" from "WSJT-X stopped reading")

(a) sample the capture PCM's `hw_ptr` every 15 s (a healthy stream advances 720,000 frames per sample; if it advances during a stall, the sound hardware delivers and WSJT-X is not reading); (b) sample each `wsjtx` thread's CPU ticks (`task/*/stat`) so a snapshot shows which thread, if any, was last alive and the audio thread's progress. Both are a few lines in `wsjtx_monitor.py`, with tests.

## What I did not do

Nothing after the dry run: no baseline, no driver, no push. The series driver and the report tool for the baseline are built or being built per the Captain's reporting request (the full-ANOVA report for the baseline: `linux/build_baseline_anova_report.py`, `monitoring_summary.py`; tested on stand-in data; the old report regenerates byte-identical).
