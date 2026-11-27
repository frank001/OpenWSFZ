# FINE-GRID: thin the candidate list (THIN) and a finer search grid (FINE)

**Date:** 2026-11-27 · **Author:** QA · **Spec:** `docs/decoder-rebuild/spec-fine-grid.md` (Architect, `arch/decoder-rebuild` `4f147930`, with his amendment: THIN suppresses by already KEPT candidates), authorised by the Captain on 2026-11-27 · **Status:** a measurement, no bars; he sets the shipped defaults. Aggregates only (NFR-021): no message text, no callsign.

**Build and runs (HK-022).** Developer `feat/fine-grid` `e9c8f02d` (shim 20260083; HK-039 APPROVED, `qa/rr-study/2026-11-27-qa-code-review-fine-grid-e9c8f02d-APPROVED.md`), merged with `feat/interface-no-defaults` `7031bb38` into `qa/sprint-known-erasure`; harness `Replay81` built from that tree with the flags of the XC-ROUND build plus `HasFineGrid` (`--lean-thin`, `--lean-time-osr`, `--lean-freq-osr`; the wrapper sets them on every lean request, the cycle's and the XC round's). `libft8.dll` SHA256 **actual = pinned = `0ef023d55a381db9da5ccd209d4b720f1b902ed1e1e55b9c8ea6cfd114d1d77b`** (arm.json `bin_pin` `0ef023d55a381db9`, asserted in the runner and the analysis). Runner: `lc_base_run.py <slice> L <n> --tag fgT|fgF --bin ...\bin_fg --pin <sha> --probe --grid 1:2:2|1:4:4`, i.e. lean, `--lean-threads 16`, `--effort normal`, `--lean-probe 1`, XC on (the XC-ROUND arm's flags); **arm T** `--lean-thin 1 --lean-time-osr 2 --lean-freq-osr 2`, **arm F** `--lean-thin 1 --lean-time-osr 4 --lean-freq-osr 4`. S40 170, H40 240, H20 240 cycles; baseline = the XC-ROUND confirmation runs on disk (`xn_*`, same audio and flags, rate asserted against their `arm.json`: 88.203 / 87.899 / 86.279 %). The cycle lists of the three runs are identical (asserted). No `--filter`, no suite filter: these are replays. Runs 21:10Z to 21:53Z, one after the other, nothing else running.

## Summary

1. **The first check passed for both arms on every slice, before any rate was read** (the script prints it separately from the numbers): **arm T: 0 shadowed candidates** in round 0, the residual rounds and the XC round (by the spec's predicate, ties by lower frequency then earlier time), sub-positions 0 to 1 only; **arm F: 0 shadowed, sub-positions 0 to 3 in both axes, and published candidates on odd sub-positions** (round-4 rows present in all three). One lapse, disclosed: the 10-cycle *quick* runs I made before the full runs for timing printed their rates next to the first check; they are not used.
2. **The defaults change nothing** (the Developer's test (a) is self-referential; QA's note-1 check): the new build with thin 0 and osr 2/2 on the first 10 cycles of S40 equals `xn_S40`: **all 21,485 probe rows, `matched.csv`, `matchedbatch.csv` and all 342 published results identical, 0 cycles differing** (`fg_defaults_check.py`).
3. **THIN alone (arm T) is mixed: rate +1.00 / +0.06 / -0.44 pp** (S40, H40, H20); round 0 now holds 112 / 103 / 98 distinct places on average instead of 140 (the thinned list is shorter than the cap), the residual rounds and the XC round still fill their 200. K3 + K4 fall on all three slices (77 to 29, 88 to 61, 88 to 57) and K1 (found and dropped as duplicate or gate) falls from 28 / 53 / 46 to 4 / 7 / 15, but K2 does not fall (337 to 342, 450 to 493, 527 to 545).
4. **THIN plus FINE (arm F) is positive on all three slices: rate +2.08 / +1.39 / +0.60 pp** (88.20 to 90.29, 87.90 to 89.29, 86.28 to 86.88 %), and **+1.08 / +1.34 / +1.04 pp over arm T**; lean over classic grows from +3.81 / +2.61 / +5.03 to **+5.89 / +4.00 / +5.63 pp**. Matched **+141 / +125 / +55**. `ours_only` rises **+0.46 / +0.42 / +0.12 pp** (arm T: -0.12 / 0.00 / -0.55).
5. **The cost is small.** CPU per cycle (whole process, noisy by a few percent): arm T +1.2 / -11.0 / -11.6 % against `xn`, arm F +9.7 / -2.5 / -1.0 %; arm F over arm T +8.3 / +9.6 / +11.9 %. `last_p95` 2,167 / 2,012 / 2,199 ms (T) and 2,569 / 2,414 / 2,540 ms (F) against 2,397 / 2,472 / 2,536; 0 abandoned cycles, 0 native errors, 0 lean parse failures in every run.
6. **QA's reading (the Captain decides):** the grid is where the gain is. THIN by itself trades duplicates for distinct places and the result depends on the slice (it hurts the crowded H20 by 0.44 pp); with the 4 x 4 grid the same thinning gives a gain on every slice, concentrated in rounds 1 to 3 (the decodes gained over the baseline are 140 of 185 in S40 in batch 2), at about +10 % CPU. **Whether to ship THIN + FINE as the lean default is his call; the numbers support it for the three slices, and nothing here supports THIN alone.** The knock-on (matched lost 44 / 101 / 148 in arm F) is large in H20 and is the thing to read next if he wants it.

## Table 1: rate and ours_only (matched of WSJT-X decodes; 6,773 / 8,983 / 9,154)

| Slice | Run | matched | ours | rate % | ours_only % | ours / WSJT-X % |
|---|---|---:|---:|---:|---:|---:|
| S40 | `xn` baseline | 5,974 | 6,297 | 88.203 | 4.769 | 92.972 |
| S40 | arm T | 6,042 | 6,357 | 89.207 | 4.651 | 93.858 |
| S40 | arm F | 6,115 | 6,469 | 90.285 | 5.227 | 95.512 |
| H40 | `xn` baseline | 7,896 | 8,605 | 87.899 | 7.893 | 95.792 |
| H40 | arm T | 7,901 | 8,610 | 87.955 | 7.893 | 95.848 |
| H40 | arm F | 8,021 | 8,768 | 89.291 | 8.316 | 97.607 |
| H20 | `xn` baseline | 7,898 | 8,641 | 86.279 | 8.117 | 94.396 |
| H20 | arm T | 7,858 | 8,551 | 85.842 | 7.570 | 93.413 |
| H20 | arm F | 7,953 | 8,707 | 86.880 | 8.237 | 95.117 |

Deltas in pp (rate / ours_only / ours ÷ WSJT-X): **T vs `xn`:** S40 +1.004 / -0.118 / +0.886; H40 +0.056 / 0.000 / +0.056; H20 -0.437 / -0.547 / -0.983. **F vs `xn`:** S40 +2.082 / +0.458 / +2.540; H40 +1.392 / +0.423 / +1.815; H20 +0.601 / +0.120 / +0.721. **F vs T:** S40 +1.078 / +0.576 / +1.654; H40 +1.336 / +0.423 / +1.759; H20 +1.038 / +0.667 / +1.704. Matched, T vs `xn`: +68 / +5 / -40; F vs `xn`: +141 / +125 / +55.

## Candidate lists (CAND rows per round, mean over the replay)

| Slice | Run | round 0 | rounds 1 to 3 | XC round |
|---|---|---:|---:|---:|
| S40 | `xn` / T / F | 140.0 / **112.1** / 140.0 | 200 / 200 / 200 | 200 / 200 / 200 |
| H40 | `xn` / T / F | 140.0 / **102.6** / 139.9 | 200 / 200 / 200 | 200 / 200 / 200 |
| H20 | `xn` / T / F | 140.0 / **98.2** / 139.5 | 200 / 200 / 200 | 200 / 200 / 200 |

At 2 x 2 THIN leaves round 0 with about 100 to 112 distinct places (fewer than the cap of 140: the list above the floor ran out); at 4 x 4 the finer grid gives enough distinct positions to fill the cap again, and the residual rounds fill their 200 in every case.

## Cost

| Slice | CPU-s per cycle `xn` / T / F | `last_p95` ms `xn` / T / F | abandoned / native errors / parse failed |
|---|---|---|---|
| S40 | 16.47 / 16.67 / 18.06 | 2,397 / 2,167 / 2,569 | 0 / 0 / 0 in all runs |
| H40 | 17.31 / 15.40 / 16.87 | 2,472 / 2,012 / 2,414 | 0 / 0 / 0 |
| H20 | 17.05 / 15.08 / 16.88 | 2,536 / 2,199 / 2,540 | 0 / 0 / 0 |

Whole-process CPU is noisy (a few percent between runs of the same build); the arms ran one after the other, `xn` on earlier days. XC-round batch-4 decodes: `xn` 51 / 140 / 187, T 58 / 153 / 191, F 55 / 119 / 183.

## Where the gain comes from (SUB-PROBE classes of the crowded WSJT-X decodes lean missed whose nearest neighbour it decoded)

| Slice | Run | K0 | K1 | K2 | K3 | K4 | K3 + K4 |
|---|---|---:|---:|---:|---:|---:|---:|
| S40 | `xn` | 91 | 28 | 337 | 54 | 23 | **77** |
| S40 | T | 86 | 4 | 342 | 21 | 8 | **29** |
| S40 | F | 78 | 4 | 317 | 11 | 11 | **22** |
| H40 | `xn` | 86 | 53 | 450 | 58 | 30 | **88** |
| H40 | T | 88 | 7 | 493 | 46 | 15 | **61** |
| H40 | F | 108 | 9 | 458 | 16 | 13 | **29** |
| H20 | `xn` | 64 | 46 | 527 | 52 | 36 | **88** |
| H20 | T | 67 | 15 | 545 | 36 | 21 | **57** |
| H20 | F | 59 | 15 | 533 | 22 | 18 | **40** |

K3 and K4 (not found or not kept) fall by 55 to 71 % in arm F (77 to 22, 88 to 29, 88 to 40), as the spec's §0.4 predicted for a search-side change; **K2 (found, tried, not decoded) is unchanged** (337 to 317, 450 to 458, 527 to 533): the finer grid does not help the tiers, as predicted. K1 falls sharply with THIN (the duplicate copies are gone).

**Matched gained and lost** (gross; by the batch of the new decode: 1 round 0, 2 rounds 1 to 3, 3 cross-cycle, 4 XC round):

| Slice | T vs `xn` gained / lost / net | batches 1 / 2 / 3 / 4 | F vs `xn` gained / lost / net | batches 1 / 2 / 3 / 4 |
|---|---|---|---|---|
| S40 | 120 / 52 / +68 | 8 / 97 / 14 / 1 | 185 / 44 / +141 | 22 / 140 / 21 / 2 |
| H40 | 118 / 113 / +5 | 11 / 91 / 16 / 0 | 226 / 101 / +125 | 40 / 157 / 26 / 3 |
| H20 | 102 / 142 / -40 | 15 / 70 / 15 / 2 | 203 / 148 / +55 | 47 / 132 / 20 / 4 |

Arm F over arm T: net +73 / +120 / +95. The gains are mostly in batch 2 (rounds 1 to 3): finding a signal in the thinned residual rounds. The losses are large on H20 (142 and 148 matched decodes the baseline had and these arms do not): the ones to read next if the Captain wants to ship.

## The ours_only check (`pf_oo_check.py xn fgT|fgF`, unchanged)

Added decodes that WSJT-X did not confirm (`added_oo`), the share repeated in the next four cycles at about the same frequency (the Architect's definition), against the baseline's own ours_only (`base_oo`) and the matched extras:

| Slice | Arm | added_oo n | repeat % | matched extras n / repeat % | baseline ours_only n / repeat % | added_oo median SNR |
|---|---|---:|---:|---|---|---:|
| S40 | T | 21 | 38.1 | 120 / 42.6 | 323 / 43.2 | -19.0 |
| S40 | F | 54 | 39.6 | 185 / 40.7 | 323 / 44.1 | -19.0 |
| H40 | T | 56 | 44.6 | 118 / 47.9 | 709 / 48.3 | -19.0 |
| H40 | F | 132 | 45.7 | 226 / 51.6 | 709 / 47.4 | -19.0 |
| H20 | T | 36 | 41.7 | 102 / 52.5 | 743 / 51.2 | -18.5 |
| H20 | F | 96 | 50.0 | 203 / 49.8 | 743 / 51.6 | -18.0 |

The added unconfirmed decodes repeat at 38 to 50 %, close to the baseline's own unconfirmed 43 to 52 %, and sit at the same weak SNR (-18 to -19 dB): they look like the same kind of signal as the ones already there, no more likely to be spurious.

## The Architect's predictions (for his ledger; QA only states the numbers)

FG-1 arm T rate rises by 0.20 pp or more on at least two slices: **+1.00 / +0.06 / -0.44, one slice**. FG-2 arm F over arm T by 0.20 pp or more on at least two: **+1.08 / +1.34 / +1.04, all three**. FG-3 arm T K3 + K4 fall on all three: **yes** (77 to 29, 88 to 61, 88 to 57). FG-4 arm T ours_only rises by at most 0.30 pp on every slice: **yes** (-0.12 / 0.00 / -0.55). FG-5 arm F CPU is at least 1.5 times arm T's on every slice: **no** (1.08 / 1.10 / 1.12 times). FG-6 the first check passes for both arms: **yes**.

## What was not done, and the files

Not done: no per-band (SNR / dSNR) breakdown of the gains, no read of the H20 losses, no run on the live station, no second replay (one run, two arms, as specified). Scripts (all in `qa/decoder-rebuild/`): `fg_recount.py` (§0), `fg_defaults_check.py`, `fg_firstcheck.py`, `fg_analyze.py`; the harness options are in `qa/rr-study/sub-feas/replay81` (`HasFineGrid`); `lc_base_run.py --grid`. Numbers: `fg_analyze.json`, `oo_check_xn_fgT.json`, `oo_check_xn_fgF.json` in this folder. Run folders `_qa-scratch\lc-base\runs\{fgT,fgF}_*` and the harness `_qa-scratch\lc-base\bin_fg` are kept.
