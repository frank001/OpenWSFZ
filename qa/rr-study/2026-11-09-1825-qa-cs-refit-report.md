# CS-REFIT: REPORT (QA, 2026-11-09T18:24Z `date -u`), CLOSE by the registered rows

Freeze record `f6328103` (code `94834f63` and `c25656b0`), written before any S or I output; spec `arch/cs-refit` `ff122c5a` (Amendments 1 and 2). Same 400 cycles of `20260925_2010`, no replay, no station. Results `_qa-scratch\cs-refit\refit_result.json` SHA-256 `0fcc1422825c230e95efc02540d6f474e832987e65737798039fcd2b13126eb1`; forced records `forced_S.jsonl` `50111f8e…`, `forced_I.jsonl` `44b2ada5…`, `forced_R3B.jsonl` `832785e4…` (12,124 rows each). Aggregates only (HK-037). **The first L-REPRO failed (R3 363 of 382) and was re-run once under Amendment 2: PASS, R2 400/400 and R3 382/382 bit-identical** (disclosed in the freeze record).

## Rows

| row | leg S (strongest first, refit on the running residual) | leg I (one refit on the residue) |
|---|---|---|
| L-REPRO | PASS (both legs share it) | |
| L-CTRL batch 1 (set hits still decodable, leg minus R3B) | 3.04 % vs 3.08 %: **-0.044 pp [-0.130, +0.029]** | 2.35 % vs 3.08 %: **-0.730 pp [-0.934, -0.548]** |
| L-CTRL batch 2 | 3.48 % vs 3.48 %: **0.000 pp [0.000, 0.000]** | 2.95 % vs 3.48 %: **-0.530 pp [-0.934, -0.161]** |
| L-CTRL verdict (CI_hi <= +2.0) | PASS | PASS |
| L-LOSS (rows not in the set, decodable on R3B, not on the leg) | **5 lost**, 21 gained | **168 lost**, 40 gained |
| NET_all (A1.3, rows not in the set, 3,956 rows; pp of n_ref) | **+0.132 pp [+0.050, +0.221]** | **-1.056 pp [-1.287, -0.821]** |
| L-FZ (report only) | fit-zero 208 of 8,219 = 2.53 % | 208 of 8,219 = 2.53 % (the product procedure rebuilt: 208, 2.53 %: the same count in all three) |

Set: 6,846 batch-1 and 1,322 batch-2 decodes (re-encodable, in the cycles the third pass ran for batch 2).

## The decision number, G_CS (the 700 CS rows decodable on the leg and not on O u R2 u R3)

| leg | rows | G_CS | CI_hi < 0.5? | BUILD-WORTH row (CI_lo(G_CS) >= 1.0 and CI_lo(NET_all) > 0) |
|---|---|---|---|---|
| **S** | 10 of 700 | **+0.082 pp [0.033, 0.145]** | yes | no |
| **I** | 16 of 700 | **+0.132 pp [0.067, 0.204]** | yes | no |

**Both legs valid (L-REPRO and their own L-CTRL pass) and both CI_hi < 0.5 pp: CLOSE.** The ceiling is 5.77 pp (700 rows); a better fit of the SAME set reaches at most 16 of them.

## Descriptive

- **By category (new rows decodable on the leg, not on O u R2 u R3, NR rows):** S: CS 10, CW 1, all others 0; I: CS 16, all others 0.
- **CS by neighbour gap (max Delta-SNR of a stronger decoded neighbour; quartile edges 9, 12, 16 dB from the 700 rows):** S new rows Q1 2 (219 rows), Q2 2 (152), Q3 2 (155), Q4 4 (174); I: Q1 4, Q2 2, Q3 4, Q4 6. No concentration at either end of the gap.
- **Wrong payloads at NR positions:** 29 NR rows on each leg (O*v1 had 27, O*v2 24; not comparable populations).
- **Time (A1.4, ratio only, same pool; my product-procedure rebuild is sequential, not the product's parallel fit):** S / product-procedure = 1.03, I / product-procedure = 1.00. The sequential leg's cost is in the analytic-signal recompute per signal (S's 8,219 recomputes), and my pool cannot say what it costs under the product's `Parallel.For`.

## Notes for the ruling

1. **Leg I does net harm:** 168 rows decodable on R3B are lost (NET_all -1.056 pp, CI_hi -0.82). Which rows (batch-3/4 hits and misses that decode on R3 only because the neighbour's residue is still there?) is not separated here. It is a result about the U side, not a gain.
2. **Leg S is harmless but empty:** NET_all +0.132 pp (21 gained, 5 lost) and G_CS 0.08 pp.
3. **Same fit-zero count in S, I and the product rebuild (208):** the -3 outcome looks tied to the signal's own placement, not to the buffer it is fitted on. Not examined further.
4. **What this does not say (spec §4):** a new signal model (per-symbol amplitude, multipath) is not tested; both legs use today's fitter. Forced legs at WSJT-X's position; one night.
5. Predictions (the Architect scores): CR-1 missed (L-REPRO failed once); CR-2 (G_CS(S) >= 0.5 pp) no; CR-3 no; CR-4 CLOSE yes; CR-5 BUILD-WORTH no.

Nothing running. `qa/same-chain` holds this report, the freeze record and the code, local.
