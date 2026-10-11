# DRAFT product issue (NOT filed; the Architect reviews first): the residual (subtraction) pass takes longer than the 15 s cycle on an FX-8350-class CPU

**Status:** draft by QA, 2026-10-11. Replay evidence only. The live path is untested. To be filed only after the Architect's review and the Captain's go.

**Title:** Decoder: on an FX-8350-class CPU the residual (subtraction) pass takes a median of 21 s per cycle on busy 40 m cycles, so the 13 s cycle budget cancels it in every cycle (replay evidence only; live path untested)

## Summary

Replaying real 40 m cycles through the product decoder (`Ft8Decoder.DecodeTwoStageAsync`, subtraction ON, 8 threads) on an AMD FX-8350 (Linux, 8 cores) cancelled the residual pass in **40 of 40** cycles of the first block tried. With the per-cycle budget lifted for the replay, the same decoder over **288 cycles (9 blocks, 40 m, one night)** took a **median of 21.2 s and a maximum of 50.0 s for the residual pass alone**, longer than the 15 s FT8 cycle itself. The station PC (16 cores, Windows) takes about 5 s per cycle on the first block and abandons none.

## Evidence (replay only)

| | FX-8350, 8 cores, Linux `libft8.so` | station PC, 16 cores, Windows `libft8.dll` |
|---|---|---|
| First block, budget 13 s (unchanged) | residual pass cancelled in **40 of 40** cycles, each cycle ending at 11.5 s | **0 of 40**, about 5.2 s per cycle, block 208 s wall, 1,147 s CPU |
| First block, budget lifted (`unlimited`) | median 23.8 s per cycle (17.9 to 34.6 s), block 970 s wall, 5,801 s CPU | not run (not needed) |
| 9 anchor blocks, 288 scored cycles, budget lifted | residual pass alone: median 21.2 s, maximum 50.0 s; per block per leg: median 945 s (734 to 1,300 s) | not run |

With the budget lifted, the Linux build on that CPU reproduced **99.90 %** of the live (Windows) non-hashed rows (4,810 of 4,815; cycle-clustered CI 99.79 to 99.98) with **0.06 %** extra rows, and a second process on the same audio gave identical output in 288 of 288 cycles. So the decoder is correct on that CPU; it is only too slow for the cycle budget.

Conditions: one process at a time, the machine otherwise idle, the frozen REFERENCE-SET corpus (real off-air 15 s cycles, 40 m), decoder at the anchor commit `421e3ce2` (shim 20260061), native library built on the host from that commit's source (`build_linux.sh`, gcc 14.3.1, -O2; SHA-256 `8839a780f1a0dd3e7960955088af1d1f5ad1ea1b991a781ccb4e9e4f27b342f7`). Settings read back: `nhard` 24, OSD sign fix on, `kMinScorePass2` 10, `osdCorrThreshold` 0.10, subtraction ON, 8 threads.

## Cause (in the code)

`src/OpenWSFZ.Ft8/Ft8Decoder.cs:108`: `SubtractionCycleBudget` = 13 s for pass 0 plus the residual pass; the residual pass is cancelled shortly before that (`SubtractionPass.cs`, `DeadlineAbandon`) and the decoder falls back to pass-0-only, with the one log line `deadlineAbandoned=True` as the only trace.

## What is NOT shown

- **The live path was not tested.** The daemon's early-decode plus final split and its capture chain were not involved. On Linux a live test also goes through the capture defect in #234, so it is optional.
- One CPU, one band, one night, one build. No claim about other CPUs or bands.
- The size of the subtraction gain a user on such a CPU would lose is not measured here.

## Why it may matter

A user on a CPU of this class would silently get pass-0-only decoding on busy cycles, with no indication in the UI. Whether that is a defect or an accepted hardware floor is for the Captain and the Developer. A related question: if one cycle's decode takes longer than the 15 s cycle, does the next cycle's decode queue behind it?

## Directions (for the Developer; QA does not touch `src/`)

1. Decide whether 13 s is a hard product requirement (the runtime gate) or should adapt to the machine.
2. Surface an abandonment to the user (a counter or warning) if it is not already.
3. A replay-only budget override already exists on the Developer's branch `feat/subtraction-budget-replay-override` (unset = 13 s, byte-identical), which is how the 288-cycle figures above were measured.
