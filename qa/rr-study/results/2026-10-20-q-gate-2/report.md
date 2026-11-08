# Q-GATE-2 result (QA, 2026-10-20, run 16:51Z to 17:00Z by `date -u`)

Spec: `qa/rr-study/2026-10-20-1530-architect-to-qa-spec-q-gate-2.md` with Amendment 1 (A1.1-A1.4) and Amendment 2 (A2.1-A2.5), branch `arch/coherent-limb2`. `U_max` = 0.05 (Captain, 2026-10-20). `BAR_G` = 1.0 pp.

## Verdict: G2-OK

**Necessary, not sufficient, for the step-3 build: UPC counts false outputs at real-signal positions only; it does not establish the step-3 false-decode rate.**

| row | value | bar | result |
|---|---|---|---|
| KG (gated, GA T1 = 17.552446 dB) | 3.031 pp, 95 % CI [2.722, 3.346] (754 kept RIGHT of 24,876 encodable rows) | CI_lo >= 1.0 pp | met |
| UPC (kept unexplained per sampled cycle) | 0.01396, CI [0.00644, 0.02256] (13 kept unexplained) | CI_hi <= 0.05 | met |

Blocks of 8 sampled cycles (117 blocks), B = 10,000, seed 20261020. UPC is over the 931 cycles that have encodable rows; over all 933 sampled cycles it is 0.01393 (two sampled cycles hold no encodable row).

## Validity (any FAIL would withhold the reading)

| row | result |
|---|---|
| S0 pin selector | `8b2f7c82` (shim 20260065), `libft8.dll` SHA-256 `cf5ee3de...15deab`, #225 V1 PASS (455/455), nhard 24, osd-sign-fix 1 read back |
| V-L | PASS, 97,480 matched, exact |
| V-P | PASS, even 466 / odd 467 (0.11 %) |
| V-T1 | PASS, 795/795 (old DLL `2fa6d993`, same `enc_flags` code) |
| V-G1 | PASS, 5,350/5,350 path-0 G-RIGHT rows reproduced (bar 99.9 %) |
| V-C1 | PASS, 172/172 identical on the old-path-0 rows of the first 300; BP path-0 agreement 300/300; 128 old-OSD rows counted, not compared (the OSD fix changes OSD by design) |
| V-K | PASS, GA kept 822 of 1,111 fallback outputs on P |
| V-T2 (Amendment 2 A2.2) | PASS: main n = 124, 0 matches (point 0 %); pooled with the pilot n = 324, 0 matches, Wilson upper 1.17 % (bar 2 %). Pilot control pooled over `i mod 5 == 3` (108) and `== 2` (92): n = 200, 0 matches |

## Population and counts (main sample `i mod 5 == 1`, 933 cycles, frozen SHA-256 LF `930d2480...`)

- Encodable WSJT-X rows 24,876 (excluded before extraction, by reason: hashed call token 2,042; other unencodable 150; type 0.1 DXpedition 90). Live hits 18,214; live misses 6,662. 13 rows were faults (a cell extraction failed or the line did not match its audio index) and are in no figure.
- G RIGHT 14,833 rows (97 by rule (ii)). **P** (live miss AND G not RIGHT) = 6,596 rows. C3 BP-only produced a CRC-valid output on 1,111 of them.
- Of the 822 kept outputs: 754 RIGHT (7 by rule (ii)), 55 M-NEAR, 13 unexplained (M-OWS or M-NONE), 0 M-FAR.

## Descriptive (no row)

- **Ungated fallback on P:** KG 3.879 pp [3.556, 4.203], UPC 0.0301 [0.0171, 0.0451] (965 RIGHT, 118 M-NEAR, 28 unexplained).
- **KG / UPC counts by WSJT-X SNR band, kept:** <= -16 dB: 266 RIGHT, 6 unexplained; -15..-6: 361 / 5; -5..+4: 112 / 2; >= +5: 15 / 0.
- **Bridge (Q-GATE's population: G-fail only, live hit ignored; never difference it against Q-GATE's TEST):** gated KG 3.980 pp [3.634, 4.315], UPC 0.0580 [0.0397, 0.0773]; ungated KG 5.230, UPC 0.1096.
- **Rule (ii)** moved 9 of the 37 ungated old-rule unexplained outputs out of M-NONE (24.3 %): the forward measurement of FIELD-ID's 795/917 pointer is far weaker on this night.
- **Concentration:** 452 distinct cycles carry kept RIGHT; the top 5 blocks hold 11.3 % of KG.
- **Live OWS-only rows per sampled cycle** (today's product, `87beed94`): 0.170, so UPC (0.014) can be read against it.

## Predictions (Architect's section 11; he scores them)

QG1 every validity row passes: yes. QG2b (G2-OK at `U_max` 0.05): yes. QG3 (point KG in [2.0, 4.5] pp): yes, 3.03. QG4 (rule (ii) moves >= 70 % of old-rule unexplained out of M-NONE): no, 24 %.

## What this does not show

- Positions are WSJT-X's (no product candidate search), no noise-only candidates, one night, one band (spec section 10). The step-3 false-decode rate is not measured here.
- The pilot's per-cycle point values are discarded and in no row.

## Run notes (HK-022: what was and was not covered)

- Command: `qg2.py run --rows frozen/rows_main.json --out main --workers 4 --fresh`; all 24,876 encodable rows, no filter. Cost 2,464 CPU-s (0.099 CPU-s per row), about 10 minutes wall.
- Pins: `libft8.dll` SHA-256 `cf5ee3dea09f55cbbd3a46bd387b3b7eb5510d862282bbf12bda27aa4c15deab` at start and end (`main_pins.jsonl`).
- 🛑 **Process slip, disclosed:** my chain script computed the pilot-pool gate with a path form the Windows Python could not read, so that gate silently produced an empty string and the script went on to the main run without it. I re-ran the pool check afterwards with correct paths: n = 200, 0 matches, PASS. The main run was therefore permitted under Amendment 2, and the result stands, but the order in the spec (gate first) was not mechanically enforced. The chain script should fail closed on an empty result.
- Code (QA, `qa/rr-study/coh-gain/`): `qg2.py`, `qg2_live.py`, `qg2_rows.py`, `qg2_vt1.py`, `qg2_vg.py`. Work files in `_qa-scratch\q-gate-2\` (outside git; no message text is persisted by any of them).
