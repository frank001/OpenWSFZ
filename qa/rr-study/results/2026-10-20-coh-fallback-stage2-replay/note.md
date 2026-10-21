# COH-FALLBACK step 3, Stage 2 decision replay: QA results (numbers only)

- **Run:** 2026-10-20 19:23:26Z to 21:30:08Z (`date -u` stamps in `chain2.log`). Build `feat/coh-fallback-stage1` `1405ada4`, shim 20260068, `libft8.dll` SHA-256 `581331da9383bc2d690e0b4146d8737b7f35738917839534d9f88ce72e85f5d1` (pinned 19:35Z, re-hashed 2026-10-21, equal; no per-arm end pin was logged, a deviation the Architect accepted in spec section 13).
- **Selection:** night `20261009_1752`, 1-in-3, 1,211 cycles (1,210 with a WSJT-X reference; `ws` = 0 cycle `261009_175215` excluded from every Test-B row, both arms). Arms: OFF (flag read back False), ON (True), ON-repeat on every 3rd cycle (404, True). No filter was applied; nothing was selected out.
- **Script:** `qa/rr-study/coh-fallback/cf_stage2_analysis.py` (numbers only; no message text is read). Full output: `stage2.json` beside this note.

## Validity
V-U0 PASS (1,211 cycles, 21,576 decodes, 0 differing; `U_max` 0.078 stands). V2 flags read back. V3 0 contained exceptions, 0 access violations. V4/A3 batch 1 identical N/N. V5 0/1,211 abandoned (Wilson upper 0.32 %). V6 0 differing of 404 (Wilson upper 0.94 %). V1 as above.

## Verdict rows
| row | value | result |
|---|---|---|
| NET (D-GO) | +6.56 pp [5.95, 7.22] (2,057 / 31,355; matched share 67.7 % to 74.3 %) | D-GO |
| DeltaU | +0.1017 per cycle [0.0821, 0.1242] vs `U_max` 0.078 | U-FAIL |
| A3' (a) content | batch 2 and batch 3 minus path 2 identical N/N | PASS |
| A3' (b) batch-2 delay, both arms published (n 1,005) | p50 86 ms, p95 496 ms, max 756 (bar 50 ms); noise floor ON-repeat minus ON n 326, p95 119 ms | FAIL |
| A3' (c) batch-3 delay, both arms published (n 154) | p50 145 ms, p95 756 ms, max 902 (bar 250 ms); noise floor n 345, p95 139 ms | FAIL |

OFF has no batch 3 in 1,057 of 1,211 cycles; 868 cycles have batch 3 only in ON. QA's first figures (batch 3 p50 2.3 s, p95 3.77 s) counted a missing batch (-1) as a delay: wrong population, corrected here per spec section 13 (Architect's E10). The reply-guard count (2.36 s) is not reported: the replay records no live decode-start offset (A2.2).

## Per band (batch-3 ON minus OFF, 1,210 cycles; fallback path-2 rows 2,180)
| band | NET | decodes | not confirmed | rate [Wilson] | batch-1 OFF rate [Wilson] | FP-watch |
|---|---:|---:|---:|---|---|---|
| A | 0.00 pp | 0 | 0 | | 1.4 % [1.1, 1.9] | |
| B | +0.07 pp | 22 | 0 | 0 % [0, 14.9] | 1.4 % [1.2, 1.7] | no |
| C | +1.24 pp | 395 | 7 | 1.8 % [0.9, 3.6] | 1.2 % [0.9, 1.6] | no |
| D | +5.25 pp | 1,763 | 118 | 6.7 % [5.6, 8.0] | 2.1 % [1.6, 2.7] | FIRES |

Overall the fallback's not-confirmed rate is 5.6 % [4.7, 6.7] against 1.4 % [1.3, 1.6] for batch 1: the FP-watch flag fires. Fallback per cycle: 1.80 published, 33 at the window edge (1.5 %), wall time median 1.40 s and p95 2.30 s, 0 abandoned. Test-B corroboration in batches 1 and 2 moves by +-2 with decodes unchanged (one-to-one matching reassignment, 2 of 31,355).

## Limits
Not-confirmed is an upper bound on false decodes (hashed `<...>` texts cannot match). One night, direct USB-CODEC chain, replay not live. NET by SNR band is derived from Test-B counts, not from the matched WSJT-X rows. The Architect's per-band counts differ from these by one because they include the `ws` = 0 cycle; the flags agree. Verdicts are the Architect's (spec section 13).
