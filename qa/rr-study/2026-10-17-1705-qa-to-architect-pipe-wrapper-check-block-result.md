# Result: pipe-wrapper check block - the pipe is no longer the loss, the daemon's channel is (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-17 17:05Z (`date -u`). **Spec:** reliable-capture spec `fd135b29` + amendment 1 (`66132efe`) + A1.1 (`1f12d120`). The Captain gave the go in QA's window ("go").
- **Scope line:** `sol` (FX-8350), **build = `main` `96dc5837`** (published self-contained, `libft8.so` `e8132650…c64ed0`, the main decoder, not B2BASE's), the **real rig** (`~/.asoundrc` unchanged, hash `8fab8270…`, no private config), a test-only wrapper first on the daemon's PATH that sets the stdout pipe to 1 MiB and then `execv`s `arecord`; OpenWSFZ only; the 60 refset WAVs of trial 0 (`--k-trials 1`). Replayed audio, not the station's live operation; no decode-rate claim; nothing about the Windows station.
- **Run:** `f2-check`, 16:24:18Z to 16:49:36Z. An earlier attempt (`f2-check-aborted`) produced no plays (a stale scratch copy of `s6_play.py` rejected `--config`) and a false CT1 FAIL (my controls script waited for 3 windows instead of 4); its data are not used. Tooling: `qa/rr-study/linux/f2-run.sh`, `f2-controls.sh`, `pipewrap-arecord.py`, `qa/rr-study/s6/f2_rows.py`. Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/f2-check/`.

## Verdict in three lines

- **Instrument and treatment valid; the block FAILS C2 and C3.** V1a, V1b, V2, CT1 and CT2 PASS; C1 PASS (0 overruns); **C2 = 58 of 60, C3 = 58 of 60** (bars <= 2 and 0), with 95 chunks dropped by the daemon's own capture channel.
- **The loss moved, it did not go away.** With a 1 MiB pipe `arecord` is never blocked (0 overruns in the plays), but the daemon's reader stalls for many seconds, so `CaptureManager`'s bounded channel (16 chunks, 2.7 s, DropOldest) overflows: **`CaptureChannelDroppedChunks` 0 -> 95 over the plays** (95 x 170.7 ms = 16.2 s of audio).
- **Per the spec: the series does not resume; the Architect rules.** The parked items (R, F2) come back into question.

## Validity and controls

| item | result |
|---|---|
| V0 | no holder on `/dev/snd/pcmC0D0c`; no WSJT-X, jt9, aplay, arecord, daemon |
| V1a | `/proc/sys/fs/pipe-max-size` = 1,048,576 |
| V1b | daemon log (P3): `arecord stderr [1]: pipe size 1048576`; `/proc/<arecord>/fd/1` = `pipe:[103388951]` |
| V2 | `arecord -D rr_in -f FLOAT_LE -r 12000 -c 1 -t raw -` (exe `/usr/bin/aplay`, the same binary as `arecord`), children of the daemon: one `arecord`; no python in the chain; same args at the end |
| **CT1** (STOP the DAEMON 3.0 s) | **PASS**: counter 0 -> 0; net applied over the 3 windows after `-CONT` -84 samples (bar +-600); third window `wanted` -185 (bar <= 600); windows (wanted/applied): [203/203] [-102/-102] [-185/-185]. No backlog bias; the pipe holds a 3 s stall |
| **CT2** (STOP `arecord` 1.0 s) | **PASS**: counter 0 -> 1 within 5 s |
| Gap, watchdog, pins | 10 cycles; 0 watchdog restarts; build, `libft8.so`, `config.json` and `.asoundrc` hashes equal at start and end |
| S6 (pass O) | V1, V3, V5 PASS; 60 of 60 plays, 0 slips |

## Rows

| row | result | bar |
|---|---|---|
| **C1** overruns in the 60 windows | **0** (the counter went 1 -> 2 across the plays, but the second overrun is at 16:49:09Z, after the last play window (16:48:30-16:48:45Z): outside the 60 windows; the first, 16:26:49Z, is CT2's) | <= 1 PASS |
| **C2** windows with \|`wanted`\| > 600, excl. the 10 after any overrun | **58 of 60** (no window excluded: no overrun in the plays) | <= 2 FAIL |
| **C3** windows at the clamp (applied +-3,000), same exclusion | **58 of 60** | 0 FAIL |
| C4 `wanted` of the own window | median 34,719; p5 7,301; p95 63,196 samples | descriptive |
| Channel drops over the plays | **95** (counter 0 before the plays, 95 after); first Warning at 16:33:41Z | - |

(Counters: before the plays `1 0 0` (overruns, drops, restarts); after `2 95 0`.)

**The sequence (own-window `wanted`/applied, the 58):** three episodes, each a jump of about 5 s followed by the clamp catching up at 3,000 samples per window: plays 2-21 (67,685 -> 7,437), plays 22-39 (55,689 -> 4,724) and plays 40-59 (66,341 -> 9,046); one window per play, each applied 3,000. The episodes start at plays 2, 22 and 40, i.e. within two windows of each 20-play batch's first slot (plays 0, 20, 40); the first channel-drop Warning is at 16:33:41Z, in play 1's window. The full sequence is in `f2_rows.json` (`C2_C3_windows`).

## Reading (descriptive; the cause is not established by this block)

- **Where the audio goes:** the framer sees the stream 5-6 s behind the wall clock at each episode and clamps; the channel counter says the daemon discarded 16.2 s of chunks. Both are the same event seen twice. `arecord` itself lost nothing (0 overruns).
- **What stalls the reader:** this build is `main`, whose decoder differs from B2BASE's. The residual passes in this block's log: 37 passes, median 1.07 s, p90 **8.2 s**, max **22.6 s**, **4 abandoned at the deadline**, against B2BASE's median 3.1 s, max 6.5 s with none abandoned (F1' block). #236 reports ~18 s residual passes for `main` on this CPU. A 20 s reader stall exceeds the channel's 2.7 s by a wide margin, and the 1 MiB pipe (21.8 s) holds it, so the bounded channel is now the binding buffer. The audio the pipe saved is dropped one layer later.
- **What this does not say:** which of the two (main's slower decoder; the channel size) the series should change, whether plain `hw` rigs behave the same, or whether the three episodes near the batch starts are caused by the harness (the next batch is rendered by numpy while the previous plays, a CPU burst at each batch start that earlier blocks, on the lighter B2 decoder, survived) or by the schedule's first slots; this block cannot separate that.
- **The pipe wrapper did its job** (0 overruns, CT1 PASS): the loss site moved from L1/L2 to L3 exactly as the F1' / D-b' reading (the reader does not drain) predicted for a longer stall.

## Housekeeping

- The wrapper was on the daemon's PATH only; the daemon is stopped; `~/.asoundrc` and `config.json` unchanged. Run folder copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-17-f2-check\`.
- `~/qa-scratch/capture-loss/` and the F1' private ALSA files are **not** deleted: the Architect's order was "after the check block's ruling", and a FAIL reopens the job.
- Nothing is pushed; no src change has been handed to the Developer (the spec made that conditional on a PASS).
