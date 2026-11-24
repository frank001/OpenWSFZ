# SUB-COVER v2 (#273): REPORT (QA, 2026-11-09T17:08Z `date -u`), BETWEEN on delta-273p

Freeze record `8daa36fe` (code `4e7e7297`), written before any O*v2 output. Spec `arch/sub-coverage` `50149101`. Same 400 cycles of `20260925_2010`, no replay, no station. Machine time: build 533 s, forced legs about 5 min. Results: `_qa-scratch\sub-cover\v2\sc2_result.json`. Aggregates only (HK-037).

## Rows

| row | result | verdict |
|---|---|---|
| O-REPRO, O-BUILD | unchanged from v1's freeze | PASS |
| O-V1 | route 2 OFF + pre-filter ON: 400 of 400 cycles bit-identical to O*v1 | PASS |
| O-CTRL | batch 1 vs R2: +0.083 pp, CI_hi +0.152; batch 2 vs R3: +0.896 pp, CI_hi +1.434 (bar +2.0) | PASS |
| O-ORC (A1.1: fails only if CI_lo > 5.44 %) | route 2 subtracted **211** decodes (>= 50, gated); 11 of 211 still decode = **5.21 % [2.45, 8.30]**, CI_lo 2.45 | PASS (see note 1) |
| O-ENC (report only) | not subtracted after both routes 205 + fit-zero 263 = 468 of 10,133 = 4.62 %; figures read ">=" | reported |

## Routes (10,133 decodes)

own (route 1, no pre-filter) 9,717 (v1: 9,596, so dropping the pre-filter placed **+121**); **oracle (route 2) 211**; inconsistent 195; no_candidate 10; ambiguous 0. Of the 416 decodes route 1 rejects without the pre-filter (537 - 121), route 2 placed 211 = **50.7 %**. By batch subtracted: 1: 7,129; 2: 1,359; 3: 128; 4: 1,312.

## The decision number

**delta-273p = +0.297 pp [0.199, 0.407]**, 36 of the 112 #273-proper rows (decodable on O*v2, not on O*v1 u R2 u R3); the true ceiling is 77 rows = 0.635 pp (A1.4), so 36 is 47 % of it. CI_lo 0.199 < 0.40 and CI_hi 0.407 >= 0.25: **BETWEEN**, to the Captain.

Beside it (not the decision): **G*v2 +1.980 pp [1.735, 2.260]** (v1 +1.542); **G273v2 +0.932 pp [0.764, 1.124]** (v1 +0.544). Of the +0.437 pp G* rise, +0.297 is the #273-proper stratum, about +0.09 CS (58 vs 47 rows) and +0.05 the L1' stratum (127 vs 121). Strata (NR rows / decodable on O*v2): CS 700 / 58; #273-proper 112 / 36; L1'-territory 221 / 127; CU-u 228 / 1; CW 103 / 16; E 9 / 0; IS 54 / 1; IW 73 / 0; NC 89 / 1. Rows with a wrong-payload output on O*v2: 24 in all, **4 in the #273-proper stratum** (v1: 7).

## Notes for the ruling

1. **O-ORC's point is above the on-file baseline.** 5.21 % against 3.44 % (R3, batch 2); the old rule (CI_hi <= 5.44) would have failed on CI_hi 8.30. Under A1.1 it passes, as intended, but 11 of 211 decodes still decoding means some route-2 subtractions are incomplete. I cannot say from the aggregates whether that is a wrong hash (the consistency check cannot see the hashed call) or ordinary incomplete subtraction; it does not move delta-273p's sign, since an incompletely subtracted neighbour can only make delta-273p smaller.
2. **delta-273p is a bound, not a build forecast.** It counts NR rows that decode when the neighbour is removed with the transmitted payload. A #273 build needs the decoder's own 77 bits (the `native/` change the spec names) and would, at the COH-RES-CAND capture ratio 0.405 (indicative only), land near 0.12 pp, below what one 400-cycle arm resolves (spec §3, "stated honestly").
3. **Attribution is not separated.** All G* rows new against v1 (+53: 240 vs 187) split as #273-proper +36, CS +11, L1'-territory +6. Route 1 without the pre-filter (+121 placed) and route 2 (211 placed) both feed them; this run does not say which route produced which row.
4. Predictions (the Architect scores): V2-1 both rows passed first run (yes); V2-2 route 2 placed >= 50 % (yes, 50.7 %); V2-3 CLOSE (no); V2-4 BUILD-WORTH (no).

Nothing running. `qa/same-chain` has this report, the freeze record and the builder/analysis commits, local and unpushed.
