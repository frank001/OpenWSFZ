# NR-TAX: where do GAP-RESIDUAL's 1,589 unreached rows sit?

**Date:** 2026-10-29T18:16:58Z (`date -u`) · **From:** QA · **Spec:** `arch/gap-residual` `4179a1e3` + Amendment 1 section 8 `001bf76e` · **Captain's go:** "go" (2026-10-29)
**Status:** descriptive. **Associations, not causes**: every sentence says "sits in", never "is lost to". No bar decides a default; nothing was built.
**Data:** all on file (the BOTH/OFF arm's decode dump and match files, GAP-RELOCATE's population, GAP-RESIDUAL's class rows). The only computation added was B4(b): GAP-RELOCATE's forced legs on the stored O, R2 and R3 buffers for every hit and every non-U miss (35,493 records, 848 s; **not a replay**, no station).
**Freeze (V3):** the category code and thresholds are `nrtax_defs.py` in commit `cebd2acf`, committed **before** any category was computed; the analysis asserts the file is unchanged since (blob `cf02e22a…`).
Aggregates only. No callsign or message text in this report. Per-message working files are in `D:\Projects\claude\_qa-scratch\gap-residual\` and are deleted at job close.

## Result in one paragraph

**Most of NR sits in a co-channel neighbourhood: 1,364 of 1,589 rows (85.8 %).** The three categories that are **prominent** by the spec's mechanical rule are **CS** (a stronger overlapping neighbour that we subtracted: 700 rows, 5.77 pp), **CU-d** (a stronger overlapping neighbour that we decoded but did not subtract: 333 rows, 2.75 pp) and **CU-u** (a stronger overlapping neighbour that we did not decode at all: 228 rows, 1.88 pp). CU-d and CU-u are the sharply enriched ones: 14 to 16 times as common among NR as among the rows we decode, and **about 7 in 10 REF rows in those two categories end up NR**. The isolated categories are not prominent (IS 0.45 pp, IW 0.60 pp) and are *under*-represented among NR. Edge rows are a rounding error (9 rows).

## Validity rows

| row | result |
|---|---|
| **V1** populations | PASS, exact: NR 1,589; hits 9,931; U 164; reachable misses 440 (271 reachable N + 169 earlier classes); n_ref 12,124 |
| **V2** fields | PASS: 0 REF rows missing SNR, freq or dt; 0 hits without a batch or our decoded text |
| **V3** freeze | PASS: `nrtax_defs.py` is byte-identical to the blob committed in `cebd2acf`, an ancestor of the analysis commit |
| **V4** subtraction rule | confirmed against `RunCore` (QA review `df57ce41`) and implemented as: batch 1 or 2 **and** `IsReencodable` on our decoded text. **375 of the 8,578 batch-1/2 decodes (4.4 %) fail it** and are therefore not subtracted. Blind spot: a fit returning −3 leaves an all-zero subtraction, invisible in the files |

**Reading stated in the freeze:** spec section 3 words CU-d as "decoded in batch 3 or 4", but Amendment 1 says B1 moves rows from CS into CU-d or CU-u, which only works if CU-d means "a stronger overlapping neighbour that we **decoded** (any batch) but did not subtract". I implemented that. Sub-count of the 333 NR CU-d rows: **221** have a batch-3/4 neighbour, **112** have only batch-1/2 neighbours that fail `IsReencodable`.

## T1: the main table (category exclusive, first match wins; 95 % bootstrap of the 400 cycles, B = 2000, seed 20261029; no multiplicity adjustment)

| category | NR rows (share) | hit rows (share) | reachable misses | NR pp of n_ref [95 % CI] | enrichment NR share / hit share [95 % CI] | loss rate NR / (NR + hits) | prominent |
|---|---:|---:|---:|---|---|---:|:---:|
| E (edge) | 9 (0.6 %) | 20 (0.2 %) | 2 | 0.074 [0.033, 0.125] | 2.81 [1.10, 5.80] | 31.0 % | no |
| **CS** | **700 (44.1 %)** | 2,471 (24.9 %) | 245 | **5.774 [5.327, 6.224]** | **1.77 [1.64, 1.90]** | 22.1 % | **yes** |
| **CU-d** | **333 (21.0 %)** | 130 (1.3 %) | 11 | **2.747 [2.403, 3.099]** | **16.0 [13.1, 19.9]** | 71.9 % | **yes** |
| **CU-u** | **228 (14.3 %)** | 104 (1.0 %) | 20 | **1.881 [1.588, 2.173]** | **13.7 [10.9, 17.3]** | 68.7 % | **yes** |
| CW (weaker only) | 103 (6.5 %) | 2,908 (29.3 %) | 94 | 0.850 [0.698, 1.006] | 0.22 [0.18, 0.26] | 3.4 % | no |
| NC (near channel) | 89 (5.6 %) | 867 (8.7 %) | 25 | 0.734 [0.594, 0.876] | 0.64 [0.51, 0.77] | 9.3 % | no |
| IS (isolated strong) | 54 (3.4 %) | 2,524 (25.4 %) | 24 | 0.445 [0.332, 0.561] | 0.13 [0.10, 0.17] | 2.1 % | no |
| IW (isolated weak) | 73 (4.6 %) | 907 (9.1 %) | 19 | 0.602 [0.473, 0.748] | 0.50 [0.39, 0.63] | 7.4 % | no |
| total | 1,589 | 9,931 | 440 | 13.106 | | | |

Prominent = NR `CI_lo` ≥ 0.5 pp **and** enrichment `CI_lo` > 1 **and** at most 5 % of resamples excluded. **No resample was excluded in any category (0 of 2,000).** IW misses the bar twice over (CI_lo 0.473 pp, enrichment 0.50); IS and CW and NC are enriched *below* 1 (they are rarer among NR than among hits).
- **Loss rate** here is the NR share of (NR + hits) in the category, not the product's overall loss rate (reachable misses and U are outside it).
- Co-channel together (CS + CU-d + CU-u + CW): **1,364 of 1,589 NR rows (85.8 %)**; the three prominent ones alone: 1,261 rows, **10.40 pp**.

## What each prominent category points at (spec section 3; a pointer, never a build)

| category | what the data adds | family it points at (status) |
|---|---|---|
| **CS** | the stronger neighbour is much stronger for NR rows than for hits (T5: median ΔSNR **12 dB** against 8 dB, quartiles 9 to 17 against 4 to 12) and a little closer in frequency (median 25 Hz against 30). **169 of the 700 NR CS rows (24 %) also have an undecoded stronger overlapping neighbour**, against 1.6 % for hits | subtraction quality: residue of a fitted signal (subtract-and-resynthesise: build prohibition lifted 2026-09-28, scoped) |
| **CU-d** | 333 rows; 221 have a batch-3/4 neighbour, 112 have a batch-1/2 neighbour that was decoded but is not re-encodable. Loss rate 62 to 81 % at every load quintile | **subtracting batch 3/4 decodes too** (a new question; no closed family), and subtracting the decodes `IsReencodable` rejects (4.4 % of batch-1/2 decodes) |
| **CU-u** | 228 rows. Supplementary (not in the spec, added after the freeze, no category depends on it): **106 of the 228 have an undecoded stronger neighbour that is itself a reachable miss** (RC, RG, RW or an earlier reachable class); 122 have only NR or U neighbours; 124 have an NR neighbour | decode the neighbour first (COH-RES-CAND helps where the neighbour is reachable); oracle subtraction is the direct test |

## T2 and T3 (counts and loss rates; point estimates only)

- **By band (loss rate A, B, C, D):** CS 5 %, 11 %, 22 %, **36 %**; CU-d 50 %, 66 %, 70 %, **80 %**; CU-u 59 %, 68 %, 62 %, **76 %**. IW exists only in bands C and D (by definition). NR's weight sits in band D (736 of 1,589) and the co-channel loss rates rise with weakness.
- **By load quintile (edges 23 / 28 / 33 / 37):** CS NR rows 59, 86, 97, 152, **306**, with loss rates 23, 19, 17, 22, 25 %; CU-d 33, 51, 66, 72, 111 (loss 62 to 81 %); CU-u 20, 31, 47, 60, 70 (loss 74, 74, 69, 70, 64 %). So the rise of NR with load (GAP-RESIDUAL D4-R) follows the *number* of CS and CU rows in busy cycles, while the within-category loss rates stay roughly flat. **Descriptive; not a DENSITY result.**

## T4: cross-tags

- **W** (F_wrong on any of O, R2, R3; forced for all but the 370 hits that cannot be encoded for comparison): CS NR 7.1 % against hits 7.6 %; CU-d NR 3.9 % against 0.8 %; CU-u 2.2 % against 6.1 %; CW 1.0 % against 7.0 %. W does not concentrate in one category for NR.
- **D8** (the 15 NR rows the R-F4 ON arm publishes): CS 7, CW 3, IS 3, CU-u 2. They sit in four categories; none is a pattern.

## T5: strongest overlapping neighbour (quartiles Q1 / median / Q3; NR against hits)

| category | |Δf| Hz, NR | |Δf| Hz, hits | ΔSNR dB, NR | ΔSNR dB, hits |
|---|---|---|---|---|
| CS | 11 / 25 / 39 | 16 / 30 / 41 | 9 / 12 / 17 | 4 / 8 / 12 |
| CU-d | 6 / 17 / 30 | 23 / 36 / 44 | 4 / 7 / 11 | 1 / 2 / 5 |
| CU-u | 9 / 21 / 35 | 20 / 33 / 44 | 2 / 5 / 10 | 1 / 2 / 5 |
| CW | 6 / 18 / 36 | 12 / 25 / 39 | −6 / −3 / −1 | −12 / −8 / −4 |

In every co-channel category the NR rows have the stronger and closer neighbour.

## Sensitivity (only categories whose NR pp moves by more than 0.5 pp of n_ref)

- Overlap 40 Hz: CS −1.07 pp, NC +0.73 pp. Overlap 60 Hz: CS +0.91 pp. Near-channel ΔSNR at 6 or 15 dB: no category moves. Edge-T late limit at 2.36 s (114 rows), δ_p ±0.1 s: no category moves.
- B1 switched off (subtracted ignoring `IsReencodable`): CS +0.95 pp, CU-d −0.95 pp. That is the whole effect of the re-encodability rule, and it is the size of the CU-d "not re-encodable" sub-count above.
- **Which categories are prominent does not change** under any of these variants.

## E, the edge category

Edge-T covers **31 of the 12,124 REF rows (0.26 pp of n_ref) in total**: E can never be prominent. Edge-F is **empty** by the data (REF 188 to 3,017 Hz; candidate base frequencies run 137.5 to 3,034.375 Hz from `f_min` 140 and `f_max` 3075 at `ft8_shim.c:1706` and `:2134`, asserted in code). E holds 9 NR rows.

## Blind spots and cautions

- **A neighbour WSJT-X did not decode is invisible here**, and so is **one of our own decodes that WSJT-X did not report** (OWS-only rows). Such a row can land in "isolated" while it is not; the isolated categories are therefore lower bounds on how many NR rows have a co-channel neighbour.
- NR rows often neighbour other unreached rows: of the 228 CU-u rows, 124 have an NR neighbour, so part of CU-u is a cluster of unreached rows, not a lone strong undecoded signal.
- The geometry uses WSJT-X's SNR for both rows; a −3 subtraction fit is not observable; category assignment of a hit uses the neighbours' decode status, which correlates with the cycle's difficulty. Associations only. The causal test is the oracle-subtraction instrument, not run here.
- The 15 D8 rows and the 15-row gap between the forced legs and the product (GAP-RESIDUAL D8) are unchanged context: NR is an upper bound on "undecodable".

## Architect predictions (facts only; scoring is the Architect's)

NT-1 (co-channel at least half of NR): **yes, 85.8 %**. NT-2 (CU-u prominent): **yes**. NT-3 (CS prominent): **yes**. NT-4 (IW prominent): **no** (0.602 pp, CI_lo 0.473; enrichment 0.50). NT-5 (IS prominent): **no**. NT-6: void (Amendment 1).

## Reproduction

`qa/rr-study/gap-residual-run/`: `nrtax_defs.py` (the frozen definitions, commit `cebd2acf`), `nrtax_force.py` (B4(b)), `nrtax_analyse.py`; inputs from GAP-RESIDUAL (`class_rows.jsonl` written by `gres_main.py analyse`). Seed 20261029, B = 2000. No test suite is involved (HK-022): the pins are the DLL SHA-256 `1ba8dc3d…` of the underlying arms and the frozen-blob check above.
