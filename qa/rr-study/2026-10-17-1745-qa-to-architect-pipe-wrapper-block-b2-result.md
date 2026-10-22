# Result: pipe-wrapper check block on the B2 build (amendment 2) - PASS on every row (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-17 17:45Z (`date -u`). **Spec:** reliable-capture spec amendment 2 (pending the Captain's go; given in QA's window: "sigh, rerun it") on top of amendment 1 and A1.1. The same block as `f2-check`, with one change: the build is B2.
- **Scope line:** `sol` (FX-8350), **build `f2beb559`** (`338ef61c` + the instrument; the series' B2 decoder), published daemon in `~/OpenWSFZ-capture-loss`, `libft8.so` `873287b1…ab03ac6a`, `config.json` `661de047…`, the **real rig** (`~/.asoundrc` unchanged, hash equal start/end), the test-only wrapper on the daemon's PATH setting the stdout pipe to 1 MiB, OpenWSFZ only, the 60 refset WAVs of trial 0 (`--k-trials 1`). Replayed audio, not the station's live operation; no decode-rate claim; nothing about the Windows station.
- **Run:** `f2-b2`, 17:06:44Z to 17:32:08Z. The earlier run on `main` is kept as `f2-check-main` (ruled FAIL, `7ab08881`). Tooling: `qa/rr-study/linux/f2-run.sh`, `f2-controls.sh`, `pipewrap-arecord.py`, `status_poller.py`, `qa/rr-study/s6/f2_rows.py`. Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/f2-b2/`.

## Verdict in three lines

- **PASS on V1a, V1b, V2, CT1, CT2, C1, C2 and C3.** RC-15 scores a **HIT**.
- **C1 = 0 overruns; C2 = 0 of 60; C3 = 0 of 60** (no window excluded: no overrun inside the plays). `wanted` of the own window: median 10, p5 -228, p95 19 samples.
- **Channel drops over the block: 2 chunks** (0.34 s of audio), against 95 on `main`. One of the two falls in a play window (the last, play 59); it produced no off-grid or clamped window.

## Validity and controls

| item | result |
|---|---|
| V0 | no holder on `/dev/snd/pcmC0D0c`; no WSJT-X, jt9, aplay, arecord, daemon |
| V1a | `/proc/sys/fs/pipe-max-size` = 1,048,576 |
| V1b | daemon log (P3): `arecord stderr [1]: pipe size 1048576`; `/proc/<arecord>/fd/1` = `pipe:[103477660]` |
| V2 | `arecord -D rr_in -f FLOAT_LE -r 12000 -c 1 -t raw -` (exe `/usr/bin/aplay`, the same binary), one `arecord` child of the daemon, no python in the chain; same args at the end |
| **CT1** (STOP the DAEMON 3.0 s) | **PASS**: counter 0 -> 0; net applied over the 3 windows after `-CONT` -76 samples (bar +-600); third window `wanted` 212 (bar <= 600); windows (wanted/applied): [-116/-116] [-172/-172] [212/212] |
| **CT2** (STOP `arecord` 1.0 s) | **PASS**: counter 0 -> 1 within 5 s |
| Gap, watchdog, pins | 10 cycles; 0 watchdog restarts; build, `libft8.so`, `config.json`, `.asoundrc` equal at start and end; 0 residual passes abandoned |
| S6 (pass O) | V1, V3, V5 PASS; 60 of 60 plays, 0 slips |

## Rows

| row | result | bar |
|---|---|---|
| **C1** overruns in the 60 windows | **0** (the counter's 1 is CT2's, 17:09:19Z) | <= 1 PASS |
| **C2** \|`wanted`\| > 600, excl. the 10 windows after any overrun | **0 of 60** (nothing to exclude) | <= 2 PASS |
| **C3** windows at the clamp | **0 of 60** | 0 PASS |
| C4 `wanted` of the own window | median 10; p5 -228; p95 19 samples | descriptive |
| **C5** channel drops per play window (1 Hz status poll, 1,507 polls) | 1 drop in one window (play 59, distance 19 from its batch's first slot, 17:31:04Z); the second drop (counter after 2) falls outside the play windows | descriptive |
| C5 distance of each C2/C3 window from its batch's first slot | none: no C2/C3 window exists | descriptive |

**The batch-render confound (your C5):** no window failed, so there is no distance to read. The three batch starts (plays 0, 20, 40) carry no off-grid window and no drop here. On `main` the episodes began within two windows of those starts; on B2 the same schedule, the same harness and the same batch renders produce none. So the batch render alone does not cause the stall on this build; it appears only with `main`'s decoder.

**Residual passes in this block:** 61 passes, median 3.0 s, p90 4.4 s, max 5.9 s, 0 abandoned (the `main` block: median 1.1 s, p90 8.2 s, max 22.6 s, 4 abandoned). Pass 0: median 0.59 s, max 1.50 s.

## What this does and does not establish

- **Does:** on the series' build the pipe wrapper is enough on this rig: no `arecord` overrun, no clamped window, no off-grid window in 60 plays; CT1 shows that a 3 s stall of the daemon is absorbed by the pipe without a backlog bias; CT2 shows that the instrument is live. RC-15 (pass on C1, C2, C3 together) is a HIT.
- **Does not:** show that the pipe alone is sufficient on a slower or busier machine, on `main`'s decoder (the failed block), or on plain `hw`; show what the 2 dropped chunks were (a reader stall near the end of the block: the last window and the teardown); say how the three product items (pipe 1 MiB, `--period-time`, channel 16 -> 256) behave together. This block tested only the pipe, through a wrapper.
- **One block, 60 plays.** The earlier blocks of this series were also one block per point.

## Housekeeping

- The wrapper was on the daemon's PATH only; the daemon is stopped; `~/.asoundrc` and `config.json` unchanged. Run folder copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-17-f2-b2\`.
- Not deleted: `~/qa-scratch/capture-loss/` and the F1' private ALSA files, until your ruling and the product change are settled.
- Not posted: the #236 comment you asked for (it waits for the Captain's word); nothing is pushed; nothing handed to the Developer yet.
