# PAYLOAD-FIT: the lean decoder fits every result from its payload

**Date:** 2026-11-27 · **Author:** QA · **Spec:** `docs/decoder-rebuild/spec-payload-fit.md` (Architect, `arch/decoder-rebuild` `b28f6c6e`), authorised by the Captain on 2026-11-27 ("go. write it") · **Status:** a measurement, no bars; he decides whether it stays. Aggregates only (NFR-021): the one function that reads message text (`r1r4_split.load_results`) returns gate codes; no text is stored or printed.

## Summary

1. **The rate rises on all three slices: +3.09 pp (S40, 84.70 to 87.79 %), +0.97 pp (H40, 86.27 to 87.24 %), +2.36 pp (H20, 82.88 to 85.24 %).** Lean is now ahead of classic by +3.40, +1.95 and +3.99 pp (it was +0.31, +0.98, +1.63). The false side (`ours_only`) rises by +0.41, +0.18 and +0.55 pp. (Table 1.)
2. **The direct effect is as the split said, and large:** of the K2 cases whose neighbour N was an R1 result (112, 18, 134), **N now has a SUB row in 109, 18 and 133**, and **T is now matched in 90, 17 and 95 (80 %, 94 %, 71 %)**: that is 1.33, 0.19 and 1.04 pp of the gain, against the Architect's upper bounds of 1.65, 0.20 and 1.46.
3. **The knock-on is larger than the direct effect on S40 and H20:** **122, 74 and 132 matched decodes were gained outside those cases** (of which 112, 69 and 124 are crowded signals), against **3, 4 and 11 lost** (matched before, not now). Subtracting a result the old gate refused uncovers more than the signal beside it.
4. **Cost: CPU +18.9 %, +8.1 % and +16.4 % per cycle** (14.48 to 17.22, 16.10 to 17.41, 14.17 to 16.50 CPU-s); `last_p95` +179, +158 and +184 ms (2,268 / 2,315 / 2,260 ms); fits per cycle 27.0 to 30.7, 28.8 to 30.0, 25.9 to 29.2. No abandoned cycle, no native error.
5. **R1 is gone as a cause** (the gate is deleted): of the results the gate used to refuse (the hash-text and short-text ones), **84 %, 86 % and 87 % are now subtracted** (402 of 478, 89 of 103, 541 of 625); the rest are skipped by the step-2e rule or have no valid fit.
6. **The new never-subtracted K2 neighbours: 53, 87 and 132** (were 157, 105, 266), now dominated by the cross-cycle results (XC 27, 52, 89), which this change did not touch. (Table 4.)
7. **One thing to weigh:** the decodes added are confirmed by WSJT-X less often than the average ones: of the extra `ours`, 88 % (S40: 209 of 237), 84 % (87 of 103) and 81 % (216 of 266) are matched; the baseline `ours_only` share is 4 to 7 %. Whether the extra ones that WSJT-X did not decode are real (signals WSJT-X missed) or false is not measured here.

## 1. What was run

- **Build:** `feat/payload-fit` `b26a156c` (`main` `326538fb` + the change; the doc commit `3ea762ee` after it changes no binary), HK-039 record `qa/rr-study/2026-11-27-qa-code-review-payload-fit-b26a156c-APPROVED.md`. Harness `Ft8.FitProbe` built from a clean checkout of that commit with `HasLean`, `HasProbe` and the usual feature flags. **`libft8.dll` SHA-256 `2f522765d508085861bd0098b66c39d628ab7884584f91d7bcaf8763bcd654b9` = the Developer's reported hash = the runner's pin** (the runner asserts it; the harness's copy hashes to it), shim 20260081. No `--filter` (a replay, not a test run).
- **Arm and slices:** exactly the SUB-PROBE arm: lean, 16 threads, effort normal, `--lean-probe 1`, LC-BASE's L flags (`qa/decoder-rebuild/lc_base_run.py ... --tag pf --probe`): **S40** (170 cycles), **H40** and **H20** (240 each), one after another on the otherwise idle PC (20 minutes, 11:17 to 11:38 UTC). **Baseline: the SUB-PROBE runs already on disk** (`probe_*`, decoder `fc3d5b5c`, shim 20260080), the same cycles (asserted: the two `sel.json` files are equal). No baseline re-run.

## 2. Table 1: rate and false side

| Slice | Arm | WSJT-X decodes | matched | ours | rate % | ours_only % |
|---|---|---:|---:|---:|---:|---:|
| S40 | classic | 6773 | 5716 | 5971 | 84.39 | 3.77 |
|  | lean before (SUB-PROBE run) | 6773 | 5737 | 6009 | 84.70 | 4.02 |
|  | **lean with PAYLOAD-FIT** | 6773 | 5946 | 6246 | **87.79** | 4.43 |
|  | **PAYLOAD-FIT effect** |  | +209 | +237 | **+3.09 pp** | +0.41 pp |
|  | **lean now minus classic** |  |  |  | **+3.40 pp** | +0.66 pp |
| H40 | classic | 8983 | 7662 | 8233 | 85.29 | 6.36 |
|  | lean before | 8983 | 7750 | 8362 | 86.27 | 6.81 |
|  | **lean with PAYLOAD-FIT** | 8983 | 7837 | 8465 | **87.24** | 6.99 |
|  | **PAYLOAD-FIT effect** |  | +87 | +103 | **+0.97 pp** | +0.18 pp |
|  | **lean now minus classic** |  |  |  | **+1.95 pp** | +0.63 pp |
| H20 | classic | 9154 | 7438 | 7999 | 81.25 | 6.13 |
|  | lean before | 9154 | 7587 | 8188 | 82.88 | 6.57 |
|  | **lean with PAYLOAD-FIT** | 9154 | 7803 | 8454 | **85.24** | 7.11 |
|  | **PAYLOAD-FIT effect** |  | +216 | +266 | **+2.36 pp** | +0.55 pp |
|  | **lean now minus classic** |  |  |  | **+3.99 pp** | +0.98 pp |

## 3. Cost

| Slice | CPU-s per cycle (before, after, change) | `last_p95` ms (before, after) | fits per cycle | `fitNone` per cycle | fits skipped by step 2e per cycle | rounds run per cycle | abandoned | native errors |
|---|---|---|---|---|---|---|---:|---:|
| S40 | 14.48, 17.22, **+18.9 %** | 2,089, 2,268 | 27.0, 30.7 | 0.15, 0.22 | 4.12, 4.45 | 2.65, 2.78 | 0, 0 | 0, 0 |
| H40 | 16.10, 17.41, **+8.1 %** | 2,157, 2,315 | 28.8, 30.0 | 0.57, 0.58 | 3.10, 3.19 | 2.62, 2.65 | 0, 0 | 0, 0 |
| H20 | 14.17, 16.50, **+16.4 %** | 2,076, 2,260 | 25.9, 29.2 | 0.51, 0.58 | 2.58, 2.86 | 2.60, 2.70 | 0, 0 | 0, 0 |

The extra fits are more than the 2.7 / 0.4 / 2.5 per cycle the R1 count predicted (3.7, 1.2, 3.3): subtracting more in round 1 leaves more results for rounds 2 and 3 to fit, and the rounds run per cycle rise slightly (+0.13, +0.04, +0.10). The fit finds no valid fit about as often as before.

## 4. The R1 cases and the new split

**4.1 The K2 cases whose neighbour was an R1 result in the SUB-PROBE run** (the same universe as QA's R1-R4 split):

| Slice | cases | N has a SUB row now | T matched now | direct gain, pp (bound) |
|---|---:|---:|---:|---|
| S40 | 112 | 109 | 90 (80 %) | 1.33 (1.65) |
| H40 | 18 | 18 | 17 (94 %) | 0.19 (0.20) |
| H20 | 134 | 133 | 95 (71 %) | 1.04 (1.46) |

In no case was T matched without N having a SUB row now (0, 0, 0): the recovery is the subtraction's.

**4.2 The new never-subtracted K2 neighbours** (the universe is new: the K2 cases fell from 436 / 495 / 686 to 350 / 478 / 577):

| Slice | K2 cases | never subtracted | XC (cross-cycle) | R2 fit skipped | R3 no valid fit | R4 last round | R1 text gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| S40 | 350 | 53 (was 157) | 27 | 14 | 8 | 4 | 0 (the gate is gone) |
| H40 | 478 | 87 (was 105) | 52 | 8 | 25 | 1 | 0 |
| H20 | 577 | 132 (was 266) | 89 | 12 | 30 | 0 | 0 |

(H40: one more neighbour counts as unsubtracted by the inherited position rule although its own position has a SUB row; H20: one has no result row; as in the R1-R4 note. The XC share of the remaining is now 51 %, 60 % and 67 %.) Where the results the gate used to refuse ended up (all published results): subtracted 402 of 478 (S40), 89 of 103 (H40), 541 of 625 (H20); the remainder are step-2e skips (62, 13, 66), no valid fit (12, 0, 16) and last-round results (2, 0, 2).

## 5. Knock-on (DR-3's lesson)

| Slice | matched gained | in the R1 cases | **outside them** | of those, crowded | matched lost | net |
|---|---:|---:|---:|---:|---:|---:|
| S40 | 212 | 90 | **122** | 112 | **3** | +209 |
| H40 | 91 | 17 | **74** | 69 | **4** | +87 |
| H20 | 227 | 95 | **132** | 124 | **11** | +216 |

Gains outside the R1 cases are mostly crowded signals (92 %, 93 % and 94 %) beside a result that is now subtracted in an earlier round, i.e. the same mechanism one step removed; the losses (3, 4, 11 of the 5,737 / 7,750 / 7,587 matched before) are small and were not traced.

## 6. The Architect's predictions, read mechanically (the ledger is his)

| # | Prediction | Result |
|---|---|---|
| PF-1 | S40 rate +0.30 pp or more | +3.09: **hit** |
| PF-2 | H20 rate +0.30 pp or more | +2.36: **hit** |
| PF-3 | H40 moves less than 0.20 pp either way | +0.97: **miss** |
| PF-4 | `ours_only` rises by no more than 0.20 pp on every slice | +0.41, +0.18, +0.55: **miss** (S40 and H20) |
| PF-5 | CPU rises by no more than 10 % on every slice | +18.9, +8.1, +16.4: **miss** (S40 and H20) |

The upper bound for direct recoveries (1.65 / 0.20 / 1.46 pp) was not exceeded by the direct effect (1.33 / 0.19 / 1.04); the totals exceed it because of the knock-on.

## 7. What this does and does not say

- It says the change works as intended and the gain is large; the 109 / 18 / 133 new SUB rows show the mechanism, and the total gain is mostly knock-on.
- It does **not** say whether the extra `ours_only` decodes are real: WSJT-X's list is the reference, and WSJT-X misses some real signals. The `ours_only` rise (+0.18 to +0.55 pp) is the price in the Architect's terms; the Captain decides.
- The cost is real: about a sixth more CPU on two slices. Nothing was abandoned and the 95th percentile of the last decode stays near 2.3 s (the budget is 13 s).
- XC is now the largest remaining cause of a never-subtracted neighbour (51 to 67 %); that is the parked item.
- **Not measured (the Architect's optional observation):** DR-3's text dedup can drop a different payload that renders the same `<...>` text; the DUP rows on `<` texts were not counted.

**Reproduce:** `python -I qa/decoder-rebuild/pf_analyze.py` (reads `_qa-scratch\lc-base\runs\{probe,pf}_*`; writes `pf_analyze.json`), `python -I qa/decoder-rebuild/r1r4_split.py pf` (the new split, `r1r4_split_pf.json`). Both outputs are beside this note.
