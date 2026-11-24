# XC-BUILD: HK-039 review of the Developer's build `b5da578c`: RETURNED, tests owed for 11 surviving mutants

Reviewed-commit: b5da578cf403c7ca7c8d0f17236acf0a854d62d8
Verdict: RETURNED

**Written:** 2026-11-13, `date -u` read 16:03:06Z. **Branch of this record:** `qa/same-chain`. **Reviewed tree:** `D:\Projects\claude\_qa-scratch\xc-review\tree`, detached at `b5da578c`.

## 1. What was checked

| check | result |
|---|---|
| Full suite (`fullsuite.out`) | Web 447, Daemon 935, E2E 9, Ft8 774, **0 failed** |
| 40-cycle smoke, OFF vs TR (T_E = +infinity), TRAIN night `20261110_1817` | `matched`, `matchedbatch`, `outcomes`, `testb`, `abandon` and `nc.tsv` **byte-identical**; per-cycle decode counts identical; `b6_n` = 0 in both; only timing columns differ. `xc.csv` and `probe.csv` populated, `threshold=Infinity` |
| Mutation pass, 38 mutants over the new `src/` (store, stage, decoder hand-off) | **26 killed, 12 survived** (list: `qa/xc-build/xc-build-b5da578c-mutants.json`; runner `qa/xc-build/xc_mutate.py`). Filter: `--filter "FullyQualifiedName~CrossCycle"` (40 tests, baseline green). The filter is the tests' own; a mutant counts as killed only when that run reports `Failed!` |

Not yet done: the 200-pair numeric comparison, and the DLL pin's actual/pinned SHA pair (HK-022); both are owed before any arm.

## 2. Surviving mutants: tests owed

One (M26) is equivalent; **11 are genuine gaps**.

| id | mutation | what the test must pin |
|---|---|---|
| M21, M22, M23, M24 | batch 3, 5, 4, 2 published messages not recorded in the store (`xcBatch: 0`) | a message published in **each** of batches 1 to 5 becomes a prior (only batch 1 is pinned now) |
| M01 | slot = floor, not nearest 15 s | a cycle start with +-ms framing jitter lands on the same slot as the exact stamp |
| M28 | `(int)o.FreqHz`, not `Math.Round` | the published frequency is the rounded argmax (a value of x.6 Hz) |
| M29 | `batch6.Count >= 0` | no batch-6 callback when nothing is detected |
| M31 | publish reserve dropped from the start-stopping bound | templates stop starting at budget less reserve |
| M33 | probe also reports untested (abandoned) templates | the sink gets a record only for a tested template |
| M35 | shadow runs when the live run failed | no shadow run, no shadow counts, when the live stage failed |
| M37 | `BeginCycle` runs while OFF | R11: with the setting OFF the store holds no cycle entry at all (`CycleCount` 0, not only `TotalCount` 0) |
| M26 | shadow flag read without the prior flag | **equivalent**: the stage only runs when `xcOn` |

The four mutants I killed only after rewriting them in a compilable form (M05, M09, M10, M34) are killed.

## 3. Required changes

Add tests for M01, M21 to M24, M28, M29, M31, M33, M35, M37. No change to the shipped code is required by this review. Then I re-run the same 38 mutants (one command) and approve if only M26 survives.

## 4. Still owed by QA after approval

200-pair numeric comparison; DLL pin pair; `pre_merge_check.py` before any push; V-OFF, TR, OFF and ON arms in the Captain's PC windows.
