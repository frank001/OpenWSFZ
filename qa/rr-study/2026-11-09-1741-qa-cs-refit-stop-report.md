# CS-REFIT: STOP at L-REPRO (QA, 2026-11-09T17:39Z `date -u`)

Spec `arch/cs-refit` `ad74a8a0` + Amendment 1 `5a971659`. The study stops at its first row, as registered ("Fails => stop and report, no retries"). **Nothing was frozen, no S or I output exists, no forced leg ran.** Code `sc_refit.py` (repro and legs), `sc_refit_force.py`, `sc_refit_analyse.py` is written and committed with this report; only `sc_refit.py repro` was run (446 s, 8 workers, `_qa-scratch\cs-refit\repro.json`, aggregates only).

## L-REPRO result: FAIL

| check | result |
|---|---|
| R2: builder (batch-1 natives of O, fitted on O's analytic signal all at once) vs stored R2 | **400 of 400 bit-identical** (as SUB-COVER's O-BUILD) |
| R3: builder (batch-2 = every re-encodable, encodable native of the R2 buffer, fitted on the built R2's analytic signal all at once) vs stored R3, 382 cycles | **363 bit-identical, 19 differ**; relative max |diff| per failing cycle 0.0061 to 0.1196 (median about 0.05) against the bar 1e-5; **none of the 19 is near the tolerance**, and no cycle sits between 0 and 1e-5 |
| the 18 cycles without a stored R3 | builder's batch-2 candidate count 11 in all (descriptive, A1.1) |

## What the numbers say (from the counts on disk only; no rerun, no new build)

- The **procedure is right**: 363 of 382 cycles reproduce bit-identically, so the fit, the order and the all-at-once subtraction are the product's.
- The 19 failures are **real differences of 0.6 to 12 % of the peak, not rounding**: in those cycles the product's batch-2 SET is not the set the spec (and my builder) assumed, "every re-encodable native of the R2 buffer". The failing cycles carry more candidates on average (mean 4.95 vs 3.91 in the matching cycles), and none of them has an empty set. So the likeliest reading is that the product leaves out some batch-2 natives (or fits some extra ones); which rule it uses is **not tested here** and I have not read it into this report as established.
- This is exactly the case the Architect's (a) asked me about: I said the bit-identical reproduction was "plausible" and that "only L-REPRO can say". It said.

## Options (the Architect's; the study is stopped until he rules)

1. Read the product's batch-2 candidate selection in `SubtractionPass.cs` (the third pass), state its rule in an amendment, and re-run L-REPRO once with it (an amendment, no change of bars; it costs about 8 minutes of machine time).
2. Or accept a looser L-REPRO for batch 2 only (the spec would have to name a number from data; I do not propose one: the failing cycles are 5 % of cycles and up to 12 % of the buffer peak).

Aggregates only; no message text.
