# FINAL TEXT of the old-CPU product issue (NOT filed yet; the Captain's go to file was relayed by the Architect on 2026-10-14, AFTER the B2 merge and QA's sol timing; QA asks the Captain to confirm in this window before `gh issue create`)

**Revision history:** draft 2026-10-11; revised 2026-10-12 per the Architect's review R1-R8 (`fe019c7a`); this text 2026-10-14 adds the merged-build row (the B2 pruned frequency search) as the Architect asked: sol figures stated as `main` WITHOUT B2, the merged-build median beside them with build, shim 20260062 and block `822498b61291`, links to #122 and #234, NFR-021 scan of this final text (clean, below).

**Title:** Decoder: on an AMD FX-8350 the residual (subtraction) pass alone takes about 18 s on `main` (longer than a 15 s FT8 cycle, so the 13 s budget abandons it); the B2 pruned frequency search brings it to about 3 s (replay evidence, B2 not yet on `main`)

## Summary

On one AMD FX-8350 (Linux, 8 cores, 8 threads), the residual pass of the product decoder (`Ft8Decoder.DecodeTwoStageAsync`, subtraction ON) on **`main` (v0.57, shim 20260060, without B2)** has a median duration **above the 15 s cycle even with the deadline removed**, on two separate builds (rows 1 and 2 below). So this is a throughput problem, not a budget set a little too tight: no budget value fixes it on this CPU. With the 13 s budget unchanged, the pass was abandoned in **40 of 40** cycles of the first block tried. The station PC (16 cores, Windows) takes about 5 s per cycle on that block and abandons none.

**The speed-up that addresses it already exists.** Stage B item B2 (a pruned frequency search inside the native sub-feasibility fit, shim 20260059) was accepted on 2026-10-04 and never merged; see the B2 status comment on #122 (2026-10-14). On 2026-10-14 it was merged with `main` **locally** (branch `feat/sub-feas-stage-b`, commit `338ef61c`, shim 20260062, not pushed, not on `main`). On the same CPU, block and cycles, the residual-pass median fell from **17.8 to 18.0 s (`main`, without B2) to 3.15 to 3.22 s (merged build)**, a factor of about 5.6, with identical decodes on those cycles. **The merged median sits comfortably inside 15 s.** This issue is filed as the record of the old-CPU behaviour on `main` and of its fix.

## Evidence (replay only; each row is its own build and series, never pooled)

| | Build and native library | Cycles | Residual pass alone |
|---|---|---|---|
| Row 1: anchor night | `421e3ce2` (shim 20260061), `libft8.so` `8839a780…27b342f7`, budget lifted. B2 not in it | 288 scored (9 blocks, 40 m, one night) | median 21.2 s, max 50.0 s |
| Row 2: first reference-set run | `main` `76aa48cd` (v0.57, shim 20260060) + the replay-only override, `libft8.so` `dc517dc9ba88b78618535fcf9da4ad8bcf3db18cfd4a68e186459520bd618e6c`, budget lifted. **B2 not in it** | 1,025 scored (33 blocks) | median 18.8 s, max 49.5 s |
| Row 3a: control for row 4, block `822498b61291`, first 8 scored cycles (index range 8:8, no warm-up, 8 threads) | the same `main` `76aa48cd` + override, `libft8.so` `dc517dc9…` (byte-identical to row 2's build), two runs | 8 scored, 2 runs | medians **18.0 s and 17.8 s**, max 19.4 s; the first run's own values for the same 8 cycles: median 17.7 s |
| **Row 4: merged build, same block, same 8 cycles, same settings** | `338ef61c` (B2 `aab18b75` merged with `main` `76aa48cd`, **shim 20260062**) + the same override, `libft8.so` `59258c68bfdafe6fbd2abeb4f56d9e208702bd59ccafdca6786761045631a350` built on the host (gcc 14.3.1), three runs | 8 scored, 3 runs | medians **3.22, 3.15 and 3.18 s**, max 3.53 s; block wall 35 s against 153 to 155 s, CPU 124 s against 823 s; fitted signals per cycle identical (12 10 12 11 9 10 12 11); 0 of 8 abandoned in every run |

Runs alternated control, merged, control, merged on the one host with otherwise idle conditions (a constant background load of about one core from a root task was present in every run). Row 2's band mix (from the run log, 3 blocks per cell): 17 m, 20 m, 40 m and 80 m, in day, twilight and night cells (17 m has no night block): 11 cells, 33 blocks. It is a mixed set, not busy 40 m cycles only. Rows 3a and 4 are 8 cycles of one block (the block at the median wall time of row 2), not a distribution.

| | FX-8350, 8 cores, Linux | station PC, 16 cores, Windows |
|---|---|---|
| First block (row 1 build, B2 not in it), budget 13 s unchanged | residual pass abandoned in **40 of 40** cycles, each cycle ending at 11.5 s | **0 of 40**, about 5.2 s per cycle, block 208 s wall, 1,147 s CPU |
| First block, budget lifted | median 23.8 s per cycle (17.9 to 34.6 s), block 970 s wall, 5,801 s CPU | not run |

**Correctness.** On `main` (anchor night, budget lifted): the Linux build reproduced **99.90 %** of the live (Windows) non-hashed rows (4,810 of 4,815; cycle-clustered CI 99.79 to 99.98) with **0.06 %** extra rows, and a second process on the same audio gave identical output in 288 of 288 cycles. In row 2, leg D agrees with leg A on 5,801 of 5,801 rows (0 extra). **On the merged build, on the 8 cycles of row 4, the decodes equal the control's: 98 rows (93 non-hashed), reproduced 100 % both ways, 0 extra rows, in all three runs.** That sample is small and does not replace B2's own acceptance (2026-10-04: 3,628 of 3,629 signals bit-identical, 795 = 795 residual decodes). The decoder is correct on that CPU; on `main` it is too slow.

Conditions: one process at a time, the frozen REFERENCE-SET corpus (real off-air 15 s cycles), gcc 14.3.1 -O2 native builds on the host. Settings read back: `nhard` 24, OSD sign fix on, subtraction ON, **8 threads, the only setting tried**, replay-only budget override set to unlimited.

## Cause (code read, `main` `76aa48cd`) and what B2 changes

- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:108`: `SubtractionCycleBudget` = 13 s for pass 0 plus the residual pass.
- `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs`: **abandonment is all-or-nothing.** `DeadlineAbandon` (`:200-207`) returns `[]` at every checkpoint (`:241`, `:246`, `:285`, `:297`, `:299`, `:303`, `:337`). That includes `:337`, after the residual decode: a residual decode that has already finished, but late, is thrown away. No partial result survives, and the decoder falls back to pass 0 only.
- The trace is a `LogWarning` naming the phase (`:203`) plus the stats line with `deadlineAbandoned=True` (`:137-142`). Neither reaches the UI as far as the Architect and QA could find.
- B2 changes only `freq_search` in `native/ft8_lib_vendor/subfeas/subfeas_fit.c` (no new export, no ABI change). The residual pass fell from about 17.9 s to about 3.2 s with the same signals fitted, so **at least about 80 % of the residual-pass time on this CPU was in that search**; the split itself is still not instrumented.
- Background, general CPU knowledge and not measured here: the FX-8350 (2012) has 8 integer cores sharing 4 floating-point units, so 8 threads may scale worse than "8 cores" suggests.

## What is NOT shown

- **The live path was not tested**, on `main` or on the merged build. The early-decode plus final split and the capture chain were not involved, and the merged build was not run under the 13 s budget (the 40-of-40 abandonment count above is from `main`). A live test on Linux also goes through #234, so it is optional.
- **B2 is not on `main`.** It is merged with `main` locally only; push, PR and the merge to `main` need the Captain's sign-off.
- **Rows 3a and 4 are 8 cycles of one block**, replay, budget unlimited, 8 threads only, one CPU model. No claim about other CPUs or about the 33-block mix on the merged build.
- **Where the rest of the time goes** after B2 (per-signal fits against the residual `DecodeAll`) is not measured: the stats line records only the total `elapsedMs`.
- **Overrun and queueing (code read, unmeasured).** The fits are cancelled at `budget − reserve` and the residual decode is not started with less than the reserve left (`:303`), which matches the 11.5 s cycle end. One `DecodeAll` (`:328`) that starts with the reserve left and runs past it is not interruptible from what was read, so it can overrun and is then discarded at `:337`. Whether a late decode delays the next cycle was not measured.
- The size of the subtraction gain lost on such a CPU is not measured here.

## Why it matters

On `main` (v0.57), a user on this CPU silently gets pass-0-only decoding on busy cycles, with no indication in the UI. The only like-for-like figure on file for what that costs is the station-PC offline flag-OFF/ON replay, **NET +11.73 pp [11.41, 12.03]**, one 40 m night, replay against replay, Test B match rule. It was not measured on this CPU, and it must never be differenced against +8.89. Whether the old-CPU behaviour is a defect or an accepted hardware floor is for the Captain and the Developer; B2 removes most of the problem on this CPU if it is merged.

## Directions (for the Developer; directions, not requirements; QA does not touch `src/`)

1. Merge B2 (the Captain's sign-off); then run the 40-of-40 abandonment check again on the merged build under the 13 s budget, and a short live check if wanted.
2. Measure where the remaining time goes: add a fit-phase and residual-decode split to the stats line (aggregates only).
3. Surface abandonment to the user (a counter or a warning).
4. Optional, a design choice with spec work if output changes on the station PC: keep a completed residual decode instead of discarding it at `:337`, or fit the strongest K signals first on slow machines.
5. Raising or adapting the 13 s budget is **not** a fix for `main` on this CPU: the median is over 15 s with no deadline.
6. A replay-only budget override exists (Developer branch `feat/subtraction-budget-replay-override`, unset = 13 s, byte-identical); all rows above were measured with it.

## References

#122 (B2 status comment, 2026-10-14; decode latency); #234 (Linux capture resampling, relevant to any live test on this host); QA records of the timing: `qa/rr-study/results/2026-10-14-b2-merge-sol-timing/` and the first reference-set run (`2026-10-12-refset-first-run-76aa48cd-LINUX-sol`).
