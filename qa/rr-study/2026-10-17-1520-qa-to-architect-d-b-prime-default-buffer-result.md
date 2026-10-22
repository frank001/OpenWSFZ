# Result: D-b' - the plughw-like default buffer (G 0.53 s) with the /proc sampler, on `sol` (QA to Architect)

- **To:** Architect. **From:** QA. **Date:** 2026-10-17 15:20Z (`date -u`). **Spec:** F1 amendment 1, A7 (D-b') and section D. The Captain gave the go in QA's window ("go for D-b'").
- **Scope line:** same as F1' (`f1p-a`): `sol`, build `f2beb559`, `libft8.so` `873287b1…ab03ac6a` at start and end, `config.json` hash `661de047…` (pinned, equal to F1''s), the private ALSA config (dsnoop slave 4 s) for the daemon only, OpenWSFZ only, the 60 WAVs of today's trial 0 in order and gains (checked identical). **Difference from F1': no `--buffer-time` wrapper**, so the client buffer is arecord's default for this chain. Replayed audio, not the station's live operation; no decode-rate claim; nothing about the Windows station.
- **Run:** `f1p-b`, 14:41:14Z to 15:15:07Z (plays 14:56Z to 15:15Z). Tooling: `qa/rr-study/linux/f1-run.sh` (`WRAP=0`), `f1-controls.sh` (`ONLY_CT2`), `f1_sampler.py`, `s6/f1_dclassify.py` (5 tests), `s6/f1_rows.py`. Evidence (aggregates only): `qa/rr-study/ows-replay-consistency/f1p-b/`.

## Validity

| item | result |
|---|---|
| V0 | no holder on `/dev/snd/pcmC0D0c`; WSJT-X, jt9, aplay, arecord, daemon not running |
| V1a | **G = 0.533 s** (client buffer 6,400 frames at 12 kHz; period 1,600 frames = 133 ms; dsnoop slave 192,000 at 48 kHz). Dump in `v1a.txt` |
| V1b | the daemon's `arecord` child args at start and at end: `arecord -D rr_in -f FLOAT_LE -r 12000 -c 1 -t raw -` (no `--buffer-time`); wrapper not on the daemon's PATH |
| Control CT2 (stop `arecord` G + 1.0 = 1.533 s) | **PASS**: counter 0 -> 1; next-window `wanted` 20,218. CT1 was not run (it would lose audio by design at this buffer) |
| Quiet gap, pins, watchdog | 10 cycles after CT2; pins equal at start and end; 0 watchdog restarts; 0 channel drops; 60 of 60 plays, 0 slips |
| Sampler | 20,247 samples, every one with a state, no gap over 0.3 s; checked beforehand on `sol` on two known shapes (arecord writing into an unread pipe: 47 of 55 samples `S`+`pipe_write`; arecord pinned and starved of CPU: 54 of 56 `R`, run-queue delay 5.0 s in 5.5 s) |

## Rows (unit: the OpenWSFZ window of each of the 60 plays; the F-1 classes were pre-registered for the F1' arm, so for this arm every row is descriptive)

| row | D-b' (G 0.53 s, no wrapper) | F1' (G 4.0 s) | baseline trial 0 (G 0.2 s) |
|---|---|---|---|
| **F-1** overruns in the 60 windows | **3** (counter delta over the block 3: cross-check holds) | 0 | 10 |
| F-2 \|wanted\| > 600 samples | 45 | 17 | 27 |
| of which above 1,100 (a loss) | 29 | 0 | 24 |
| of which 600-1,100 | 16 (11 of 714-738, 5 of 1,012-1,039) | 17 (all 1,013-1,037) | 3 |
| F-3 windows at the clamp | 12 | 0 | 21 |
| F-5 decode lines for the 60 plays (count only) | 828 | 896 | 721 |

**F-4, the three remaining overruns:** play 45 (3.95 s into its window; next-window `wanted` 16,564 = 1.38 s), play 50 (4.86 s; 23,999 = 2.00 s), play 59 (5.88 s; 7,416 = 0.62 s). The losses are 1.2 to 3.8 times G.

## D: L1 or L2 (the Architect's rule: the 3 s before each overrun; L2 if >= 50 % of samples are blocked writing to a pipe; L1 if >= 50 % runnable with run delay >= 50 % of the window; else unclassified)

| overrun | class | samples | blocked on pipe | runnable | run delay / window |
|---|---|---|---|---|---|
| play 45 | unclassified | 30 | 40 % | 7 % | 3 % |
| play 50 | **L2** | 30 | 60 % | 10 % | 4 % |
| play 59 | unclassified | 30 | 20 % | 20 % | 7 % |

**Read plainly (descriptive, three overruns):**
- By the rule: 1 L2, 2 unclassified, **0 L1**. All three are far from the L1 cut-off: `arecord` was runnable in 7-20 % of the samples and its run-queue delay was 3-7 % of the window, never near 50 %. That is **no evidence that `arecord` was starved of the CPU**.
- In all three `arecord` spent 20-60 % of the 3 s blocked in `pipe_write`; the rest of the time it sat in its normal ALSA wait (`do_sys_poll`), the larger share in two of the three. That is the shape of the daemon's reader not draining the pipe for part of the 3 s before the Warning. The two unclassified cases fall short of the 50 % cut-off (40 %, 20 %); the cut-off is a judgment with no prior data, and with three overruns no share is estimated. The overrun line is printed at recovery, so the stall began up to 1.4-2.0 s before it (the F-4 losses); the 3 s window therefore contains stalled and unstalled seconds, which lowers every share.
- The block spent 15 minutes with the sampler running; there is no control without it, so its overhead on F-1 is not separated (it reads three small `/proc` files at 10 Hz).

## Correction after the Architect's ruling (b56691ec, 2026-10-17)

F-2 is NOT accepted as a loss measure, here or in F1'. In this block's daemon log before any loss (14:45-15:10Z) `wanted` repeats +1871 / -1888 / +123 every three cycles (about +-156 ms), applied in full: the framer chases delivery-period jitter of the 1,600-frame client period. My split of F-2 at 1,100 samples into "loss-sized" (29) and "quantisation" (16) therefore has no basis: the 29 include jitter. The loss rows are F-1, F-3 and the loss-anchored tails (F-4), not F-2. The same holds for F1' (its 17 windows at about 1,020 samples are not a mechanism I established).

## What this does and does not establish

- **Does:** at the default-like buffer (G 0.53 s) the loss persists but is smaller than at 0.2 s: 3 overruns and 12 clamped windows in 60 plays against 10 and 21. At 4 s there are none. So on this rig the loss falls with the buffer (0.2 s: 10; 0.53 s: 3; 4 s: 0), one block per point. A plain-`plughw` user with a 0.5 s default is therefore not shown to be safe on this load: the same 60 plays lose audio there too, less often.
- **Does:** point the remaining losses at the **daemon's reader side (L2 shape), not at `arecord`'s CPU access (no L1)**: pipe-blocked time in all three, run delay small in all three. Three overruns only, one classified by the rule.
- **Does not:** separate the effect of the dsnoop slave from the client buffer; give a rate; say what the daemon was doing while it did not read. The three stalls (0.6-2.0 s) coincide with the previous cycle's residual pass in the earlier block (K1/O-rows); this block did not re-test that coincidence.
- **For the Captain's options:** if the question is whether users on plain devices lose audio, this block says yes at this load, rarely at G 0.53 s. That raises F2 (the framer re-anchors after a detected loss) and the question of what stalls the daemon's reader for 0.6-2 s; both are product questions, not rig ones.

## Housekeeping

- No wrapper was used. `~/.asoundrc` and `~/rr-run/config.json` are unchanged (hashes in `pins_start.txt`); the private config was on the daemon only; the daemon is stopped, no process left (sampler stopped by its stop file).
- Run folder in `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-17-f1p-b\`. `~/qa-scratch/capture-loss/` stays until the F1/F2 job closes.
- F-5 here is a count of the same kind as F1' (daemon ALL.TXT lines for the 60 slot stamps; provenance in `f1_rows.json`); one block each, never a rate.
