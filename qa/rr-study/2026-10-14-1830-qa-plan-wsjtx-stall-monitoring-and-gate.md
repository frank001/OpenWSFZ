# QA PLAN: WSJT-X stall on `sol` (monitoring M1, liveness gate M2, coverage row M3)

- **From:** QA. **To:** Captain, cc Architect. **Date:** 2026-10-14 (`date -u` 16:2xZ at drafting). **Status:** DRAFT, nothing built. Architect consulted by message the same day (`arch-9f`): "Do M1+M2+M3 now as one small QA tooling change; M4 only if it doesn't recur." Their answers are folded in below. No `src/` or `native/` change (HK-011 not engaged).
- **Problem.** In repeat B2 of the corrected-chain WSJT-X repeats (sol, 2026-10-14, battery 10:37Z to 12:33Z) WSJT-X stopped taking in audio at 11:09:30Z (its per-cycle `save/` WAVs and `ALL.TXT` lines both stop) and stayed silent until repeat 3's script restarted it at about 12:33Z. About 1 h 24 min of the sweep has no WSJT-X data. The warm-up check ran once, at the start, and could not see it. The sweep was replaced (about 2 h of `sol` lost). Cause unknown.

## What is already known (HK-018: data on file)

| Fact | Source | Reading |
|---|---|---|
| Stop at 11:09:30Z, WAV for cycle 11:09:30 is the last | `save/261014_110930.wav`, `wsjt-all.txt` | WSJT-X stopped capturing, not only decoding |
| 11:09:30Z is **inside** scenario S4 (part 3, trial 1), 1 min 30 s after S4 began at 11:08:00Z | B2 `supervisor.log` lines 171-177, `truth.csv` | **Not a scenario boundary.** The "aplay restarts at a scenario boundary" idea does not fit the timing as stated |
| Same seed 139150452, same content, same trial played in repeats B1 (09:11:45Z) and B3 (13:07:15Z) without incident | the three `truth.csv` | The stall is not caused by the audio content of that cycle |
| Playback is one `aplay` process per played cycle (raw float32, `-r 48000 -c N`, device `plughw:0,0`) | `linux/shim/*.py` lines 53-76 | A per-cycle open/close of the loopback playback side; a race with the capture side remains possible (Architect's first suspect, unconfirmed) |
| No aplay error in `supervisor.log`; no segfault, OOM, killed-process or trap line in `/var/log/messages` 13:05-14:35 CEST; `dmesg` empty for 14 Oct; WSJT-X's log file 0 bytes; `ulimit -c` 0; `core_pattern` = `core`; no coredump dir | `sol` | Silent hang or silent death; no trace kept |
| The first watcher logged the PID of the `xvfb-run` wrapper (579774), not of `wsjtx` | `~/rr-run/wwatch.log` | It would not have shown a WSJT-X death. Fixed in M1 |
| `sol` has `perf`; no `strace`, `gdb`, `coredumpctl` | `which` | M1 reads `/proc` instead |

## Incident 1 retrospective (Architect's follow-up, HK-018; data on `sol`, all times UTC)

The 2026-10-11/12 incident (WSJT-X silent through all three corrected-chain repeats, `wsjt-all.txt` 0 lines) is the **first occurrence**; 2026-10-14 is the second.

| Q | Finding | Evidence |
|---|---|---|
| (a) Did the `save/` WAVs stop too? | **Yes, but not when the decodes did.** Decodes stop after hour 06 only because run 2 ended at 06:57Z (nothing was played). WAVs kept arriving every cycle (240 per hour) through 07 and 08 and into hour 09. **Last WAV `261011_093230.wav`** (09:32:30Z); none again until `261012_193930.wav`. Not one WAV during the three repeats (19:10Z 11 Oct to 00:56Z 12 Oct) | `save/` listing; `ALL.TXT` hourly counts (`261011_06` 364, then nothing until `261012_19`) |
| (b) What was happening at the last good slot? | **Nothing.** No battery, no `aplay`, no script: the battery had ended 2 h 35 min earlier, the next sweep started 9 h 37 min later. No file in `sol`'s home was modified between 09:20Z and 09:50Z. Not a scenario boundary, not an `aplay` restart, not a run start. WSJT-X therefore stopped **idle**, 2 h 35 min after the last audio was played | `status.json`/`repeats.log`; `find -newermt` over 09:20-09:50Z: empty |
| (c) Was the `wsjtx` process alive afterwards? | **Not established.** No `ps` history, no watcher then, WSJT-X's own log is 0 bytes. The WAVs resume at 12 Oct 19:39Z (my reading, not checked against a log: the leg E work of that evening, whose scripts run `stop-wsjtx.sh` first), so a restart there would say nothing about the process's state before it | `~/wsjtx27-rr.log` 0 bytes; the leg E queue script |
| (d) WSJT-X uptime at the stall | **Incident 1: about 4 h 39 min** (started 04:53:39Z, `start-wsjtx27.sh`/log mtime 06:53:39 CEST; last WAV 09:32:30Z). **Incident 2: about 33 min** (restarted by the repeat script at 10:36:00Z; last WAV 11:09:30Z). Repeats B1 and B3 ran 1 h 57 min each on a fresh WSJT-X without a stall; the replacement repeat 2's WSJT-X has run since 14:43Z without one | `start-wsjtx27.sh` timestamps; `repeatsB.log` |

**Reading (descriptive, two incidents).** The signature is **not** the same in the two: incident 1 stopped **idle, with no playback, 4 h 39 min after start**; incident 2 stopped **under playback, mid-S4, 33 min after start**, with a sweep before and after it clean. What they share: WSJT-X's audio input stops while the process may stay alive, the `save/` WAVs stop, nothing is logged by the kernel, syslog or WSJT-X, and nothing restarts it. Neither coincides with an `aplay` boundary, so **the `aplay`/loopback boundary idea is not supported by either incident**. Two events cannot tell "one cause with a random trigger" from "two causes". **Consequence: M4 becomes worthwhile** (Architect's condition: the incidents do not point to the aloop/`aplay` boundary).

## Incident list (for the results README, both together)

| # | Sweeps affected | What | Treatment |
|---|---|---|---|
| 1 | `2026-10-11-64246e4-LINUX-sol-SAMPLERATE-chain-REPEAT1`, `-REPEAT2`, `-REPEAT3` | WSJT-X not decoding for all three sweeps (WAVs stopped 11 Oct 09:32:45Z, restarted only 12 Oct 19:39Z); `wsjt-all.txt` 0 lines. The existing footnote in the consolidated report | OpenWSFZ-only repeatability readings; never used as paired data; labelled in the report |
| 2 | `2026-10-14-64246e4-LINUX-sol-SAMPLERATE-chain-WSJTX-REPEAT2` | WSJT-X silent from 11:09:30Z to about 12:33Z (S4 part 3 to the end); 127 `wsjt-all.txt` lines | **INVALID (stall 11:09:30Z)**; none of its data used, including the first 32 minutes; replaced by `…-WSJTX-REPEAT2-REPLACEMENT` |

## M1: monitoring that explains the next stall (QA tooling, runs beside every sol battery)

A detached sampler `~/rr-run/wsjtx_monitor.sh` (HK-023: `setsid nohup`, no cron), stopped by the launcher's teardown with an orphan check (HK-019). Every 15 s (one cycle):
- PIDs by `pgrep -x wsjtx` and `pgrep -x jt9` (**the real binaries, never the `xvfb-run` wrapper**), `State`, `VmRSS`, thread count from `/proc/<pid>/status`;
- mtime and count of the newest `save/*.wav`; size of `ALL.TXT`;
- the capture and playback sides of the loopback: `/proc/asound/card*/pcm*/sub*/status` and `hw_params` (state RUNNING, DRAINING, XRUN, SETUP, PREPARED), plus the PIDs holding `/dev/snd/*` open;
- the number of live `aplay` processes (more than 1, or one older than 20 s, is logged).

On a **stall** (no new WAV for more than 45 s = 3 cycles, Architect's rule) it writes a one-shot snapshot folder `stall-<UTC>/`: for every `wsjtx` thread `/proc/<pid>/task/*/{stat,wchan,stack}` (if readable) and `fd` list, the same for `jt9` and `Xvfb`, the ALSA status files, `ps -eLf`, the last 200 lines of `/var/log/messages` if readable, and `dmesg` tail. The **wchan of the audio thread** separates "blocked in `snd_pcm_read` (ALSA or loopback)" from "a Qt or jt9 wedge". It never kills or restarts anything: it observes.

**Core dumps (Architect's note):** `ulimit -c unlimited` in the launcher is QA's to set (done in the launch script). `core_pattern` needs root on `sol`: **request to the Captain** (a one-line root change to a directory such as `/home/claude/cores/core.%e.%p.%t`). Without it the next hard crash still leaves no core.

## M2: liveness gate inside the battery (QA harness `run_study.py`, stop and flag only)

Before each scenario starts, and every 5 minutes inside the long ones (S5, S7), the harness checks the M1 stall rule on the real `wsjtx` PID (alive, and a WAV newer than 45 s). If it fails: **stop the battery and flag it** (`status.json` phase `STALLED`, the scenario named, the snapshot path). **No silent recovery** (Architect). An automatic WSJT-X restart plus a rerun of the one affected scenario is allowed only if the Captain asks for it, is logged as a **replacement scenario** in the run folder, and is capped at **1 per sweep**. A battery with `--skip-warmup` keeps the mechanical warm-up it already has.

## M3: analyser coverage row (mechanical, HK-021)

For each scenario and each appraiser, `expected_cycles` (from `truth.csv`) against `cycles_with_data` (cycles for which that appraiser's `ALL.TXT` copy has a line or, for WSJT-X, a `save/` WAV at that slot). **Predicate as code:** `FAIL` when `cycles_with_data < expected_cycles - 1` for any scenario (Architect's threshold). Source of the threshold: the Architect's ruling of 2026-10-14; the "- 1" allows for the one cycle that straddles a scenario start. It is a **validity row**: a FAIL makes the sweep INVALID and the report says so before any figure; it is triggered by missing data, never by a result. The analyser's `ndc = 1 FAIL` row stays as it is and is relabelled "one appraiser only" when M3 fires.

## Series rule (Architect, no further ruling needed)

The corrected-chain series is **N complete sweeps**. A sweep whose M3 coverage fails is **invalid and replaced**. The stalled sweep stays in its folder, labelled **INVALID (stall 11:09:30Z)**; **none of its data is used, including the valid first 32 minutes**. The results README says so. It is never pooled.

## M4 (cause test): NOW WORTHWHILE (two incidents, neither at an `aplay` boundary)

The Architect withdrew the "one stall in 8 h" estimate. Proposed, after M1 is in place and sol is idle: **two arms, run back to back unattended, M1 on, no battery**: (A) WSJT-X alone with the loopback idle, 6 h (incident 1 stopped at 4 h 39 min idle); (B) WSJT-X plus a per-cycle `aplay` of a synthetic cycle exactly as the battery plays it, 3 h (incident 2 stopped at 33 min under playback). A stall in either arm gives the snapshot; no stall in 9 h leaves the cause open and says so. The 10-minute `aplay`-parameter test stays available but is **not** where the data point. **Not run without the Captain's go**; sol is the station for the baseline re-run too, so this competes for its time.

**Sequencing (Architect): M2 is mandatory before the baseline re-run.** A start-up-only check demonstrably let this through once.

## Order and cost

1. M1 sampler and launcher hook, plus `ulimit -c` (small shell script; test on `sol` while idle, 10 minutes).
2. M3 analyser row with synthetic cases: a run with no gap, a gap of exactly `expected - 1`, a gap of `expected - 2`, an appraiser with no data at all, and the real faulty B2 folder (must FAIL; B1, B3 must PASS).
3. M2 gate in `run_study.py` with a unit test on the stall predicate (a fake clock and fake WAV directory).
4. `RUNBOOK.md` and `linux/README.md` updated; the three Linux repeats' README gets the INVALID label.

The tooling edits are in `qa/rr-study/`, branch `qa/refset`. Not pushed (HK-033). The replacement repeat 2 currently running on `sol` is **not touched**.

## What this does not do

It does not find the cause by itself and does not make a stall impossible: it makes the next one **visible, bounded to one scenario, and explained**. Whether the cause is the loopback, Qt's audio input or a jt9 wedge stays open until M1 catches one.
