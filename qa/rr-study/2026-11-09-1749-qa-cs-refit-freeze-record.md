# CS-REFIT: FREEZE RECORD (2026-11-09T17:48Z `date -u`), written BEFORE any S or I output exists

Spec: `arch/cs-refit` `ff122c5a` (§0 to §6 `ad74a8a0`; Amendment 1 §7 `5a971659`; **Amendment 2 §8**). Authority: the Captain, 2026-11-09, "yeah, lets do the study" (an offline refit study, no build). Size rule: the same 400 stored cycles of `20260925_2010`, no replay, no station, no second night, no pilot.

## 🔴 Disclosure: the first L-REPRO FAILED (A2.3)

- **First run** (`sc_refit.py repro`, batch-2 set = every re-encodable, encodable native of the R2 buffer; QA commit `c25656b0`; 2026-11-09 17:39Z): R2 **400 of 400 bit-identical**; R3 **363 of 382 bit-identical, 19 differ** by 0.0061 to 0.1196 of the buffer peak (bar 1e-5). **Registered stop** ("Fails => stop and report, no retries"). Result file kept: `_qa-scratch\cs-refit\repro_first_run_FAILED.json`, SHA-256 `52636f51e3d059ee6ecb0587ffd62e326e55b02c9e132ee27cd0037560aa91e4`. Report `2026-11-09-1741-qa-cs-refit-stop-report.md` (`da9f6ab3`). QA ledger Q44 (the review called bit-identical "plausible" without reading the code that defines the set).
- **Cause** (QA read `SubtractionPass.cs` after the failure; the Architect re-read it and agreed): the third pass fits the residual pass's NEW decodes, `SubtractionPass.cs:300-304`; the residual pass drops any decode whose 77-bit payload is the same transmission as a pass-0 candidate (`SubfeasPayload.SameQso`), Step 5 `:457-491`. The stored R2-buffer natives are the list before that dedup.
- **Amendment 2 (A2.1):** the batch-2 set (for the reproduction and for S and I alike) = the R2-buffer natives that (1) `EncodeMessage` accepts, AND (2) are NOT `SameQso` with the payload of any batch-1 CANDIDATE, AND (3) then pass `IsReencodable` + `EncodeMessage`. `SameQso`, `ExtractStdFields`, the RR73 sentinels (std `32403`, on-air `32373`) and `ExtractPayload77` ported unchanged from `SubfeasPayload.cs` into `sc_refit.py` (QA commit `94834f6310ca607856dabb6f028cb98dc4382f3c`, committed BEFORE the re-run; checked on synthetic Q-call payloads only: exact match, on-air RR73 variant, non-match).
- **ONE re-run (A2.2), all 400 cycles: PASS.** `repro.json` SHA-256 `e6bde35153fcce5b6f77b9c295106e03686d76ecb7592a621da9f6bcbea6e7f9`: **R2 400 of 400 bit-identical (max relative diff 0.0); R3 382 of 382 bit-identical (max relative diff 0.0)**; 8,219 fits, 208 fit-zero; 18 cycles without a stored R3, **0** batch-2 candidates in them (consistent with a third pass that did not run); 1,342 batch-2 candidates in the 382 cycles. The 19 cycles that failed now reproduce.

## Frozen inputs and code

| item | value |
|---|---|
| Code (predicates are the code) | `sc_refit.py` (repro, legs; `94834f63`), `sc_refit_force.py`, `sc_refit_analyse.py` (`c25656b0`) in `qa/rr-study/gap-residual-run/`; SUB-COVER's `sc_build.py`, `sc_analyse.py` imported unchanged |
| Corpus | unchanged from SUB-COVER's freeze record: night `20260925_2010`, 400 cycles, `selection400.json` `42e09239…`, `population.json` `c54b98b7…`, n_ref 12,124; stored buffers and natives as there |
| Subtraction set | exactly what the product subtracted: batch 1 (A2.1 rule applies to batch 2); **in the 18 cycles without a stored R3, batch 1 only** (A1.1) |
| Legs | **S**: whole set ordered by OUR published snr descending (ties freq ascending, then batch); from O; analytic signal of the current residual recomputed per signal; fit and subtract. **I**: from the stored R3 (stored R2 in the 18 cycles); every signal of the set refitted once on that buffer's analytic signal at the same tones and natives; all corrections subtracted together |
| Baseline | R3B = stored R3 or stored R2 (18 cycles), 400 buffers written by the re-run; forced legs on it for ALL 12,124 rows (A1.2) |
| Forced legs | GAP-RELOCATE's `gr_forced.force_cycle`, unchanged; `delta_p` 0.6, `delta_c` 0.7 (asserted against `deltas.json`); `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` = pin |
| Bootstrap | B = 2000 cycle resamples, seed 20261109 |
| Frank-path check | `grep 'Users\\Frank'` over the three new files: 0 matches each |
| Existence of S/I output | **none**: `_qa-scratch\cs-refit\buffers` holds only the 400 `_R3B.f32` files |

## Registered rows and decision (as in `sc_refit_analyse.py`)

L-REPRO (**PASS, above**), L-CTRL (per leg, SET hits still decodable vs R3B, CI_hi <= +2.0 pp, batch 1 and batch 2 separately), **L-LOSS and NET_all over rows NOT in the set** (A1.3; batch-3/4 hits stay in), L-FZ (report only), time (A1.4: only the sequential/parallel-style ratio on the same pool; my product rebuild is sequential too, so the ratio compares S and I with the product's procedure as rebuilt). **Decision per leg, on G_CS (the 700 CS rows decodable on the leg and not on O u R2 u R3; R2 covers where R3 has no record):** BUILD-WORTH if for at least one valid leg CI_lo(G_CS) >= 1.0 pp AND CI_lo(NET_all) > 0; CLOSE if for both legs CI_hi(G_CS) < 0.5 pp; BETWEEN otherwise. A leg is valid only if L-REPRO and its own L-CTRL pass. Descriptive: G by NR-TAX category, by CS neighbour-gap quartile (edges from the 700 rows), wrong payloads, fit-zero share.

## Order from here

`sc_refit.py legs` (about 6 min) -> `sc_refit_force.py S`, `I`, `R3B` (about 5 min each) -> `sc_refit_analyse.py main` -> a short report -> the Architect's ruling.
