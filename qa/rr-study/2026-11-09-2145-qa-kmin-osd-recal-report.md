# KMIN-OSD-RECAL: REPORT (QA, 2026-11-09T21:45Z `date -u`), KEEP-5 by the registered rows

Freeze record `823f62a3` (code `58b6f321`, harness `7122404e`), written before any arm output. Spec `arch/kmin-osd-recal` (Amendments 1 and 2). Night `20260930_1930`, the first 400 cycles of L1′'s selection (`sel_400.json` `7691e33b…`), classes `8046a4be…`, PC, build `ef2fc84b` (`libft8.dll` = pin `1ba8dc3d…`, start and end of both arms). **Arm A** (`kMinScorePass2` 10, `osdCorrThreshold` 0.10) ran 20:41:01Z to 21:09:27Z (28 min); **arm B** (5, 0.05) 21:09:28Z to 21:44:19Z (35 min). Both: Deep, nhard 24, OSD fix, multi-set, `Both`, **R-F4 ON and L1′ ON**, 8 threads, `rc 0`, 400 rows, 400 "Late subtraction round" lines, orphan check clean. Results `_qa-scratch\kmin-osd-recal\kr_result.json` SHA-256 `080f63153f4086dfa7707e9aa0f87412d8806f7416703b96153e0a315d3dd78a`; `run.csv` A `e2953795…`, B `bcdf82a7…`; nc dumps (scratch only, text) `55640ea4…`, `4869016e…`. Aggregates only (HK-037). I read nothing from either arm before the analysis had run on both.

## Rows

| row | result |
|---|---|
| V-NAT | PASS (tree at `ef2fc84b`, native diff empty, DLL = pin) |
| V-SET | PASS (both arms, start and end readbacks: exact table values, `ungated=True`, `lateround=True`, nhard 24, Deep, `Both`, 8 threads) |
| V-WIRE | PASS: (i) V-SET; (ii) residual-buffer check on file (second pass B 200 vs A 59 to 98, 10/10); **OSD wire: PASS but thin** (B 1 accepted vs A 0 in one cycle), not isolated from `kMinScorePass2` |
| **N-BETTER** | **fires: NET_B−A +0.146 pp [0.057, 0.236]**, CI_lo > 0; N-WORSE does not fire. **Interval width 0.178 pp** (A1.5) |
| **U-OK** | **fires: dU′_ta 0.005 per cycle [0.000, 0.0125]**, CI_hi <= 0.021; U-FAIL does not fire |
| HK-026 flag | **False**: B's new-text uncorroborated outputs in `untestable_class`: **0**; hashed or unencodable: **0** (A-only: 0 and 0) |
| **Verdict** | **KEEP-5** (V-rows pass, N-BETTER and U-OK fire, flag False). The OSD wire is "PASS but thin, not isolated", so the verdict reads **as the pair** (the Architect's ruling of the freeze) |

## What it is in counts

- WSJT-X decodes in the 400 cycles: 12,292. Corroborated: **A 10,561 (85.92 %), B 10,579 (86.06 %)**: **+18** rows.
- B's rows whose text is absent from A's in the cycle: **24** (22 corroborated, **2 tested_absent**, 0 untestable, 0 hashed); by batch: 4: 11, 2: 9, 5: 3, 3: 1. A's rows absent from B: **5** (4 corroborated, 0 tested_absent); by batch: 4: 4, 5: 1. So +22 − 4 = +18, and the net uncorroborated addition of B is 2 rows over 400 cycles. No duplicate text in B.
- The gain is small: 18 rows in 12,292 (0.146 pp), CI lower edge 0.057 pp. It says "5 / 0.05 is not worse and slightly better on this night", not more.

## Descriptive (no verdict)

- **Abandons (fallback, residual pass, third pass, late round): 0 of 400 cycles in both arms.** Late round ran in all 400 cycles in both.
- **Latest batch arrival (ms), median / p95 / max: A 3,826 / 5,233 / 6,446; B 4,627 / 5,916 / 7,236** (the 13 s cycle). The lower floor costs about +0.8 s at the median and about +0.8 s at the maximum; no cycle is near the budget.
- **Rows decoded by the OSD path** (the `path` code 1 in the nc dump; the shim's `out_path`: 0 BP converged, 1 OSD succeeded): **A 1,873, B 1,890 (+17)**; path 0: 7,310 in both; path code 2 (not documented in what I read, probably the coherent fallback): A 1,612, B 1,614. **My analysis line "rows_with_osd_path" printed 0 and 0 because it searched the column for the text "osd"; the column holds numeric codes (QA ledger Q46). It is a descriptive line, not a row, and the table above uses the codes.**

## Limits

- **One night, 40 m, 400 cycles, PC.** The interval is about ±0.09 pp around +0.146.
- **The pair moves together:** this is "his pair against the default pair", not which knob does what.
- **`kMinScorePass2` acts on the residual side, not on the first decode** (the first pass is cap-bound at 200 on busy cycles, so the floor changes nothing there; on residual buffers it binds). The +18 therefore comes from the residual pass and the later rounds, where R-F4 and L1′ also act, so the number is "the pair with R-F4 and L1′ ON".
- **The OSD wire is thin** (one accepted candidate in the pre-freeze check). The +17 OSD-path rows in B are consistent with the looser gate but are not a controlled isolation.

## For the ruling

Predictions (the Architect scores): KO-1 missed (the first V-WIRE failed); KO-2 NET point > 0: **yes**; KO-3 U-FAIL fires: **no**; KO-4 KEEP-5: **yes**; KO-5 REVERT-10: **no**. A KEEP-5 means the station's 5 / 0.05 stays as it is; making it the code default is a small `src/` change for the Captain to decide. Nothing in the station configuration needs an edit.
