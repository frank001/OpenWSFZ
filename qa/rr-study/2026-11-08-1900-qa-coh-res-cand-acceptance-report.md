# COH-RES-CAND (#272) acceptance: QA report (2026-11-08T18:58:07Z `date -u`), verdict by the registered rows: **FAIL (U-FAIL)**; N-GO fires

Build `b0d01f4f1335cd5f98c2d43d9b67a4afea0dbd1e` (v0.69), freeze record `5770ed8b`, spec `14f4e28d`. Night `20260930_1930`, the first 400 of selection `2575e115…`, classes `8046a4be…` (reused), PC, `libft8.dll` `1ba8dc3d…` (pin) at the start and end of every arm. Instruments exactly as frozen (analysis `crc_analyse.py` at `87c5486a`; B = 2000, seed 20261108). Chains: stage 1 `2026-11-08T18:00:42Z` to `18:31:36Z` (`chain1.out`), stage 2 `18:32:19Z` to `18:57:17Z` (`chain2.out`); all read-back and row-count checks `ok=1`; orphan check clean; sol and the station not used.

## Rows

| row | predicate | result | |
|---|---|---|---|
| B-NAT | `git diff --stat fe1454c1 b0d01f4f -- native src/OpenWSFZ.Ft8/Native` empty; DLL = pin | empty; pin held at every start and end | **PASS** |
| B-OFF | 40 of 40 cycles identical to `main` `fe1454c1`, every published field | 40 of 40 | **PASS** |
| V1-3N | arm A = sol OFF arm, 400 of 400 (A1.3) | 399 of 400; the one cycle `260930_200230` is the cycle where sol's OFF arm abandoned the fallback (fb start 12,134 ms, recorded 2026-10-30); on the PC the fallback ran: 5 extra batch-4 rows in A, none missing; 0 differing rows in `untestable_class` | not 400/400; **A1.4: the night stays** (no differing row reaches `untestable_class`) |
| B-WIRE | (i) `resCand=residual-*` in >= 95 % of arm-B cycles whose fallback line shows `audio=both(residual2\|residual3)`; (ii) `resEligible` != `origEligible` in >= 1 | denominator 400 of 400 cycles; (i) 400 of 400 = 100 % (`residual-R3` 389, `residual-R2` 11); (ii) 400 of 400 cycles differ | **PASS** |
| B-DUP | no text twice in one cycle of arm B | 0 instances | **PASS** |
| N-GO / N-STOP | CI_lo(NET_B-A) > 0 pp / CI_hi <= 0 | NET **+0.504 pp [0.286, 0.717]** (A 10,118 corroborated = 82.31 %, B 10,180 = 82.82 %, n_ref 12,292, 400 cycles with WSJT-X lines) | **N-GO fires**, N-STOP does not |
| U-OK / U-FAIL | CI_hi(dU'_ta) <= 0.021 / CI_lo > 0.021 | dU'_ta **0.0475 [0.0274, 0.0700]** per cycle with WSJT-X lines (19 tested_absent over 400 cycles) | **U-FAIL fires**, U-OK does not |
| B-AB | fallback abandoned cycles, B <= A | A 0, B 0 (residual pass 0 and 0, third pass 0 and 0) | **PASS** (the line carries one `abandoned` figure for both runs, so the per-run split of A1.2 is not readable) |

**Verdict by the registered rule: FAIL** (U-FAIL fires; ACCEPT needs U-OK). The size of NET clears the Captain's 0 pp bar with room (CI_lo 0.286); the wrong-payload proxy exceeds the 0.021 bar with its lower limit (0.0274) above it, 2.3 times the point bar.

## Descriptive lines (no verdict)

- **dU' decomposition** (B's new-text, not-corroborated batch-4 outputs, per the frozen instrument): 149 new-text batch-4 outputs, 119 corroborated; of the 30 not corroborated: 19 tested_absent (0.0475), 9 tested_present (0.0225), 2 hashed or unencodable (0.005), 0 untestable_class.
- **B minus A, by text:** B-only 150 texts (149 batch-4, 1 batch-1; 120 corroborated); A-only **79 texts** (78 batch-4, 1 batch-1; **58 corroborated**). Net corroborated gain 120 - 58 = **+62**, which is the NET above. The lever therefore **replaces** part of the residual run's rows (the original list on the residual audio) rather than adding to them. Spec §0 says "every candidate offered today is still offered": that holds for the original run, which keeps its list, but not for the residual run, which now reads the residual buffer's list and no longer sees the original list's candidates on that audio.
- **By `resCand` (arm B's fallback lines):** `residual-R3` 389, `residual-R2` 11, `fallback-orig` 0.
- **Timing (both runs together, `fbWallMs`):** median 605 ms in A, 529.5 ms in B; max 1,094 ms (A) and 1,160 ms (B); latest fallback end 5,606 ms (A) and 5,561 ms (B) of the 13,000 ms budget. B is not slower.
- **Gained corroborated rows as a share of GAP-RESIDUAL's 153-row ceiling:** 62 / 153 = 0.405 (a different night, `20260925_2010`: indicative only).

## What QA does not conclude

- U-FAIL reads the registered metric; it says nothing here about WHY 19 tested_absent outputs appear (the instrument cannot say whether they are wrong payloads or true signals WSJT-X missed beyond its own test; `tested_present` 9 are signals the audio contains).
- No second night and no changed bar: any further arm, cycle or bar change needs the Captain's word (the size rule).
- A merged candidate list (the original list plus the residual buffer's) would keep the 58 corroborated texts B lost and might add the 120; it is outside §2 of the spec (no merged list), was **not tested**, and its dU' cost is unknown. Stated as an observation for the Architect, not a recommendation.

## Next (the Captain's order)

Architect's ruling on these rows; `pre_merge_check.py` on `b0d01f4f1335cd5f98c2d43d9b67a4afea0dbd1e` only if the build is to be merged (with the setting OFF, as shipped: B-OFF passes); the Captain's push go and merge sign-off (HK-010). QA's ledger: no new row for this arm. Aggregates only in this file (HK-037); working files stay in `_qa-scratch\coh-res-cand` and are deleted at job close; the arm folders (`raw`, with `crc_result.json`, SHA-256 `2b53b412366ce250…` prefix) are kept until the ruling.
