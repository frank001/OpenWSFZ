# DRAFT product issue (NOT filed; revised 2026-10-12 per the Architect's review R1-R8; filing needs the Captain's go): on an AMD FX-8350 the residual (subtraction) pass takes longer than the 15 s cycle even with no deadline

**Status:** draft by QA, 2026-10-11; revised 2026-10-12 after the Architect's review (`2026-10-12-1930-architect-to-qa-review-old-cpu-issue-draft.md`). Replay evidence only. The live path is untested. To be filed only with the Captain's go. Run the NFR-021 scan on the final text before filing.

**Title:** Decoder: on an AMD FX-8350 the residual (subtraction) pass alone takes longer than a 15 s FT8 cycle even with no deadline, so the 13 s budget abandons it on busy cycles (replay evidence; live path untested)

## Summary

On one AMD FX-8350 (Linux, 8 cores, 8 threads), the residual pass of the product decoder (`Ft8Decoder.DecodeTwoStageAsync`, subtraction ON) has a median duration **above the 15 s cycle even with the deadline removed**, on two separate builds (table below). So this is a throughput problem, not a budget that is set a little too tight: no budget value fixes it on this CPU. With the 13 s budget unchanged, the pass was abandoned in **40 of 40** cycles of the first block tried. The station PC (16 cores, Windows) takes about 5 s per cycle on that block and abandons none.

## Evidence (replay only; each row is its own build and series, never pooled)

| | Build and native library | Cycles | Residual pass alone |
|---|---|---|---|
| Row 1: anchor night | `421e3ce2` (shim 20260061), `libft8.so` `8839a780…27b342f7`, budget lifted | 288 scored (9 blocks, 40 m, one night) | median 21.2 s, max 50.0 s |
| Row 2: first reference-set run | `main` `76aa48cd` (v0.57) + the replay-only override, `libft8.so` `dc517dc9ba88b78618535fcf9da4ad8bcf3db18cfd4a68e186459520bd618e6c`, budget lifted | 1,025 scored (33 blocks) | median 18.8 s, max 49.5 s |

Row 2's band mix (from the run log, 3 blocks per cell): 17 m, 20 m, 40 m and 80 m, in day, twilight and night cells (17 m has no night block): 11 cells, 33 blocks. It is a mixed set, not busy 40 m cycles only.

| | FX-8350, 8 cores, Linux | station PC, 16 cores, Windows |
|---|---|---|
| First block (row 1 build), budget 13 s unchanged | residual pass abandoned in **40 of 40** cycles, each cycle ending at 11.5 s | **0 of 40**, about 5.2 s per cycle, block 208 s wall, 1,147 s CPU |
| First block, budget lifted | median 23.8 s per cycle (17.9 to 34.6 s), block 970 s wall, 5,801 s CPU | not run |

Correctness on that CPU (anchor night, budget lifted): the Linux build reproduced **99.90 %** of the live (Windows) non-hashed rows (4,810 of 4,815; cycle-clustered CI 99.79 to 99.98) with **0.06 %** extra rows, and a second process on the same audio gave identical output in 288 of 288 cycles. In row 2, leg D agrees with leg A on 5,801 of 5,801 rows (0 extra). So the decoder is correct on that CPU; it is too slow.

Conditions: one process at a time, the machine otherwise idle, the frozen REFERENCE-SET corpus (real off-air 15 s cycles), gcc 14.3.1 -O2 native builds on the host. Settings read back: `nhard` 24, OSD sign fix on, subtraction ON, **8 threads, the only setting tried**.

## Cause (code read, `main` `76aa48cd`)

- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:108`: `SubtractionCycleBudget` = 13 s for pass 0 plus the residual pass.
- `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs`: **abandonment is all-or-nothing.** `DeadlineAbandon` (`:200-207`) returns `[]` at every checkpoint (`:241`, `:246`, `:285`, `:297`, `:299`, `:303`, `:337`). That includes `:337`, after the residual decode: a residual decode that has already finished, but late, is thrown away. No partial result survives, and the decoder falls back to pass 0 only.
- The trace is a `LogWarning` naming the phase (`:203`) plus the stats line with `deadlineAbandoned=True` (`:137-142`). Neither reaches the UI as far as the Architect and QA could find.
- Background, general CPU knowledge and not measured here: the FX-8350 (2012) has 8 integer cores sharing 4 floating-point units, so 8 threads may scale worse than "8 cores" suggests.

## What is NOT shown

- **The live path was not tested.** The early-decode plus final split and the capture chain were not involved. A live test on Linux also goes through #234, so it is optional.
- **Where the time goes.** The stats line records only the total `elapsedMs`: there is no split between the per-signal fits and the residual `DecodeAll`, so nobody can say which phase is slow.
- **Overrun and queueing (code read, unmeasured).** The fits are cancelled at `budget − reserve` and the residual decode is not started with less than the reserve left (`:303`), which matches the 11.5 s cycle end. One `DecodeAll` (`:328`) that starts with the reserve left and runs past it is not interruptible from what was read, so it can overrun and is then discarded at `:337`. Whether a late decode delays the next cycle was not measured.
- One CPU model, two builds, 8 threads only. No claim about other CPUs.
- The size of the subtraction gain lost on such a CPU is not measured here.

## Why it may matter

A user on this CPU would silently get pass-0-only decoding on busy cycles, with no indication in the UI. Whether that is a defect or an accepted hardware floor is for the Captain and the Developer. What is at stake, with its full label: the only like-for-like figure on file is the station-PC offline flag-OFF/ON replay, **NET +11.73 pp [11.41, 12.03]**, one 40 m night, replay against replay, Test B match rule. It was not measured on this CPU, and it must never be differenced against +8.89.

## Directions (for the Developer; directions, not requirements; QA does not touch `src/`)

1. Measure where the time goes: add a fit-phase and residual-decode split to the stats line (aggregates only).
2. Make the pass cheaper on slow machines, or let it degrade: for example fit the strongest K signals first, or keep a completed residual decode instead of discarding it at `:337`. A design choice for the Developer, with spec work if it changes output on the station PC.
3. Surface abandonment to the user (a counter or a warning).
4. Raising or adapting the 13 s budget is **not** a fix on this CPU: the median is over 15 s with no deadline.
5. A replay-only budget override exists (Developer branch `feat/subtraction-budget-replay-override`, unset = 13 s, byte-identical); both rows above were measured with it.
