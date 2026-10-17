# Result: F1' - a 4 s capture buffer (dsnoop slave + `--buffer-time`) on `sol` (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-17 14:45Z (`date -u`). **Spec:** F1 (`ef0c5a32`'s parent) plus amendment 1 (`d5d95454`): the dsnoop slave at 4 s AND the `--buffer-time=4000000` wrapper. The Captain gave the go for F1' in QA's window ("go for F1'"); D-b' was not authorised and was **not run**.
- **Scope line:** `sol` (FX-8350), build `f2beb559` (`338ef61c` + the instrument), published daemon in `~/OpenWSFZ-capture-loss`, `libft8.so` `873287b1…ab03ac6a` at start and end, shim 20260062, `config.json` unchanged, same chain (plug, `samplerate_best`, route, dsnoop) with only the slave buffer and `ipc_key` changed in a **private** ALSA config for the daemon. OpenWSFZ only (WSJT-X off), S6 trial 0: the 60 WAVs of today's plays 0-59, same order and gains (checked: identical). Replayed audio, not the station's live operation; no decode-rate claim; nothing about the Windows station.
- **Run:** `f1p-a`, 13:58:17Z to 14:28:51Z (plays 14:10Z to 14:28Z). Tooling: `qa/rr-study/linux/f1-run.sh`, `f1-controls.sh`, `qa/rr-study/s6/f1_rows.py`, `s6_play.py --k-trials 1`. Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/f1p/`. No `--filter` applies.

## Verdict in three lines

- **Valid.** V0, V1a (**G = 4.0 s**), V1b, CT1 and CT2 all PASS on the first attempt; pins equal at start and end.
- **F-1 = 0 overruns in the 60 play windows -> EFFECTIVE** (bar <= 1; baseline 10 at G = 0.2 s). Counter delta over the block 0; channel drops 0; watchdog restarts 0.
- **RC-13: HIT** (0.75 on the ledger). The loss at the rig's 0.2 s dsnoop ring is the cause of the overruns and steps seen earlier; a 4 s buffer removes it. One block, 60 plays.

## Validity and controls

| item | result |
|---|---|
| V0 | `fuser` on `/dev/snd/pcmC0D0c`: no holder; WSJT-X, jt9, aplay, arecord, daemon not running before the daemon started |
| **V1a** | `arecord -v --buffer-time=4000000 -D rr_in -f FLOAT_LE -r 12000 -c 1 -t raw -d 2` under the daemon's environment: client plug PCM `buffer_size` 48,000 frames at 12 kHz = **G = 4.0 s** (bars: < 1.0 VOID, < 2.7 RC VOID: neither applies). Layers (all in `v1a.txt`): plug -> rate conversion (libsamplerate, 48000) -> route -> **Direct Snoop PCM, buffer_size 192,000 / period 6,400 at 48 kHz** |
| Diff, test asoundrc vs the rig's `~/.asoundrc` | `ipc_key 51234 -> 51235` and `buffer_size 9600 -> 192000`, nothing else. The rig's `~/.asoundrc` was not touched |
| **V1b** | the daemon's `arecord` child args: `/usr/bin/arecord --buffer-time=4000000 -D rr_in -f FLOAT_LE -r 12000 -c 1 -t raw -` at start and at end; the daemon's environment shows `ALSA_CONFIG_PATH` (private) and `ALSA_PLUGIN_DIR`; the wrapper dir first on its PATH |
| **CT1** (stop `arecord` 1.5 s) | **PASS**: overrun counter 0 -> 0; next-window `wanted` **574** samples (bar < 2400). Today at 0.2 s a 2.0 s stop gave 24,002 |
| **CT2** (stop `arecord` G + 1.0 = 5.0 s) | **PASS**: counter 0 -> 1 within 5 s of `-CONT`; next-window `wanted` 62,233 samples (5.19 s: the whole stop is lost once the buffer is exceeded). The instrument is alive under the wrapper (HK-026), so the zero below means something |
| Quiet gap | 30 s after CT1 and 150 s (10 cycles) after CT2 before the first play; settle: two windows with \|wanted\| <= 600 each time |
| Watchdog | no restart in either control; 0 "Capture ended unexpectedly" lines |
| S6 validity (pass O) | V1, V3, V5 PASS; 60 of 60 plays, 0 slips; residual passes abandoned: 0 (every pass line `deadlineAbandoned=False`) |

## Rows (the unit is the OpenWSFZ window of each of the 60 plays)

Baseline = trial 0 of the 2026-10-17 block, same WAVs, same order, **taken at G = 0.2 s** (recomputed with `cl_rows.py`'s code, own-window framer line: 10 / 27 / 21, as you confirmed).

| row | F1' (G = 4.0 s) | baseline trial 0 (G = 0.2 s) |
|---|---|---|
| **F-1** overruns in the 60 windows | **0** (counter delta over the block 0: cross-check holds) | 10 (trials 1, 2: 6, 6) |
| F-2 windows with \|wanted\| > 600 samples | 17 | 27 |
| F-3 windows at the clamp (applied +-3,000) | **0** | 21 |
| F-4 remaining overruns | none | - |
| F-5 decode lines for the 60 plays (count only) | 896 | 721 |

**F-1 class: EFFECTIVE** (<= 1; the bar from the lowest baseline trial, mean 6, P(<= 1) = 0.017).

**F-2 read plainly (not pre-registered; the spec said to say if it does not fall to near 0):** it does not. Split by size:
- \|wanted\| above 1,100 samples (a loss): **0** of 60 here against **24** of 27 in the baseline.
- \|wanted\| 600-1,100 samples: **17** here (all of magnitude 1,013-1,037 samples, 4 positive and 13 negative) against 3 in the baseline.
Those 17 are not losses. A \|wanted\| of ~1,020 samples (~85 ms) is the size of the framer's chunk-boundary quantisation (chunks are 2,048 samples), so the 600-sample bar of F-2 sits inside the quantisation band; with the 4 s buffer the arecord period is larger (1,600 frames at 12 kHz against 240) and the quantisation is more visible. I read F-2's remaining 17 as "off-grid by about one chunk's quantisation, no loss", and F-3 = 0 and \|wanted\| above 1,100 = 0 as "no windows displaced by a loss". The off-grid tail after a loss is gone; I make no claim that the grid is exact.

**F-5 (descriptive; WITHHELD as a finding pending the Architect's ruling, corrected 2026-10-17):** the first version of `f1_rows.json` carried 0 for both blocks because `f1_rows.py` was run without the ALL.TXT paths it needs; those fields are now null. The numbers in this note were counted separately: ALL.TXT lines whose first token equals one of the 60 play slot stamps (plays 0-59). Baseline 721, from the 2026-10-17 block's captured-audio `owsfz/ALL.TXT`; F1' 896, from `sol`'s `~/rr-run/owsfz-ALL.TXT`. Two different files, counted by one rule; counts only; one block each; never a rate. Provenance is in `f1_rows.json` (`F5_provenance`).

## What this does and does not establish

- **Does:** on `sol`'s chain the overruns, the steps and the multi-window off-grid tail come from the 0.2 s dsnoop ring being outrun; with a 4 s buffer there is no overrun, no channel drop and no clamped window in 60 plays. The treatment was demonstrated (CT1) and the instrument was proven alive (CT2) in the same daemon instance.
- **Does not:**
  - Say that the product needs a larger `--buffer-time`. The lever that did the work is the **dsnoop slave ring of this rig**, plus `--buffer-time` on top of it (the spec's A2). The two were applied together; their separate effects were not measured. A user without dsnoop (plain `hw`/`plughw`) starts at a larger default; this block does not say whether such a user loses audio. That is D-b' (same private config, no wrapper, G about 0.5 s), which needs the Captain's go.
  - Tell L1 from L2 (no sampler was run; D-a/D-b' not authorised).
  - Say anything for a faster CPU or another day. One block of 60 plays; the baseline is trial 0 of an earlier block.
- **Next, for you and the Captain:** F2 (the framer re-anchors after a detected loss) stays a product question regardless: CT2 shows that a stall longer than the buffer still costs the whole stall and then a long tail.

## Housekeeping

- The wrapper dir (`~/qa-scratch/capture-loss/f1/bin`) was on the **daemon's** PATH only and went away with that daemon; the daemon is stopped and no process was left. `~/.asoundrc` and `~/rr-run/config.json` are unchanged (hashes in `pins_start.txt`).
- Run folder copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-17-f1p-a\`. `~/qa-scratch/capture-loss/` stays until the F1/F2 job closes.
- The OpenWSFZ ALL.TXT lines were counted on `sol` by slot stamp; no message text left `sol` or entered this note (HK-037).
