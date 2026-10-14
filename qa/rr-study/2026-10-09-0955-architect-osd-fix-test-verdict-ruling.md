# RULING — OSD-FIX TEST: **F-GO** (corrected OSD at `nhard` 24 vs today's build, held-out night)

- **To:** QA (owner). cc Captain. **From:** Architect. **Date:** 2026-10-09 09:55Z (`date -u`, HK-017).
- **Rules on:** QA's `report_test.md` (`d3e2acbc` on local `qa/osd-fix`) and the raw TEST output `artefacts/rr_2026-10-09_osd_fix_test/` (r1–r4, `status.json`), against spec `2026-10-07-1545` §5.3, the `n*` ruling `2026-10-09-0615` and its addendum (`ff1ab2c8`).
- **Branch:** `arch/osd-fix` (local, not pushed). Docs only: `git diff --stat -- src/ native/` is empty.

## 1. Validity (§5.3, V1–V6): all PASS

| row | result |
|---|---|
| V1 DLL pin | equal at start and end of all 8 processes (QA) |
| V2 read-back | switch and `nhard` read back as intended in every process; selection SHA `84b3d884…78b0` (QA) |
| V3 | 8 of 8 processes `ok` on attempt 1, 0 failed rows (`status.json`, read by the Architect) |
| V4 | A-SIGN′ and A-OFF PASS (ruled 2026-10-08) |
| V5 noise leg | 0/200 at FIX(24) ⇒ PASS. ⚠️ HK-026: 0 at every setting tried; bounds gross failure only |
| V6 abandons | REF 3/860, FIX24 2/860 (≤ 5 %) |
| Blind-instrument guard | not blind: confirmed decodes differ in 39 cycles |

## 2. Verdict, recomputed independently

The Architect re-read the per-cycle Test B rows of both arms from the raw `testb.csv` files (QA's loader, own summation and own bootstrap with a **different seed**; numeric outputs only, HK-037):

| quantity | QA (`b5cee17d`, seed 20261007) | Architect (seed 12345) |
|---|---|---|
| cycles | 860 | 860, same stamps in both arms, WSJT-X `W` identical per cycle |
| WSJT-X decodes | 25,995 | 25,995 |
| confirmed-decode difference | +54 (55 gained in 38 cycles, 1 lost) | +54 (55 / 1; 39 cycles differ) |
| **NET** | **+0.208 pp [+0.117, +0.326]** | +0.208 [+0.118, +0.324] |
| **ΔU** (not-confirmed per cycle) | **−0.073 [−0.090, −0.058]** (REF 0.386 → FIX24 0.313) | −0.073 [−0.090, −0.058] |

Verdict rows, first match wins: F-FAIL needs CI_lo(ΔU) > 0: **no** (−0.090). F-GO needs CI_lo(NET) > 0 **and** CI_hi(ΔU) ≤ 0: **yes** (+0.117 > 0; −0.058 ≤ 0). ⇒ **F-GO.**

## 3. What it means, in proportion

- **The fix is correct and slightly better on both counts.** On a night that chose nothing, the corrected OSD at 24 finds **54 more decodes that WSJT-X also made, in 860 cycles (≈ 1 per 16 cycles, +0.21 % of WSJT-X's decodes)**, and gives **19 % fewer decodes that WSJT-X did not make** (0.386 → 0.313 per cycle; not-confirmed is an upper bound on false decodes, since hashed `<...>` texts cannot match).
- **It is a correctness fix with a small dividend, not a decode-rate lever.** Do not present +0.21 pp as a programme gain on the scale of SUB-FEAS (+8.89 / +11.73 pp).
- **TEST exceeds TRAIN (+0.208 vs +0.158):** no shrinkage on held-out data, which argues the effect is not a selection artefact. Different nights, so the two are **never differenced or pooled**.
- **Batch rows:** NET batch 1 +0.077 [+0.040, +0.121], batch 2 +0.131 [+0.056, +0.240]. **The Captain's mechanism is seen on TEST** (mandatory rows): batch-1 not-confirmed per cycle 0.287 → 0.231 **and** batch-2 confirmed 3.495 → 3.535. Fewer false first-pass decodes, more residual decodes. PEEK-100 did not see it at `nhard` 40; at 40 the corrected gate still admits loose words (TRAIN: ΔU +0.055 at 40), so the two readings are consistent.
- **By SNR band:** NET positive in all four bands (A/B/C/D +0.042 / +0.096 / +0.046 / +0.023), ΔU ≤ 0 in all four; the band-D FP-watch flag fires nowhere.
- **Cost:** wall per 215-cycle process REF 1,530 s, FIX24 1,493 s (one night, descriptive): no cost visible.

## 4. Limits (spec §6)

One band (40 m), one TRAIN night and one TEST night, both via the same B1 chain; replay, not live; Test B's not-confirmed count is an upper bound on false decodes; V5 cannot discriminate settings. The OSD accepts' confirmed/not-confirmed split by `nhard` is not available (thread-local diagnostics).

## 5. Predictions scored (ledger)

| # | prediction | P | result |
|---|---|---:|---|
| OF4 | TEST: F-NEUTRAL | 0.45 | ❌ MISS |
| OF5 | TEST: F-GO | 0.35 | ✅ HIT |
| OF6 | TEST: F-FAIL | 0.20 | ✅ (did not occur, as the low P implied) |

Calibration note: this time the Architect leaned **against** the tidy mechanism (held F-GO below F-NEUTRAL because every corrected-OSD figure on file was near zero) and the tidy mechanism was right. The figures "on file" were all at `nhard` 40, the cap TRAIN now shows is too loose. Lesson: a near-zero reading taken at the wrong operating point is not evidence about the right one.

## 6. Next: decisions are the Captain's

1. **Merge of `feat/osd-sign-fix`** (`3276573b`, shim 20260060): the spec's merge row is met on the measurement side (F-GO; unit and characterisation tests were green at QA's U1/U3/U5 and A-SIGN′/A-OFF). It still needs **the Captain's diff review (HK-011) and sign-off (HK-010)**.
2. **R4, after his decision, as one change with the merge or straight after:** the Developer's small second commit sets the code default `nhard` to **24**; QA writes the station-config migration (HK-035: the station config stores `nhard` 40 explicitly since 2026-09-12, so a new default alone does not reach the station; check whether a stored value overrides the default, as in the v0.54 flag-ON migration).
3. 🛑 **From the deploy moment on, `nhard` 24 + corrected OSD is a new era:** never pool live or endurance data across it with the `nhard` 40 era (same rule as 60/40). The board records the deploy timestamp.
4. **Open questions on the board, not blockers by this ruling but worth settling before the merge:** the early-decode frequency mismatch (an S4 classifier run on `main` would show whether it predates the fix, ≈ 5 min station) and the S1 SNR-bias replay (offline, minutes).
5. QA: the first R&R and endurance run after the deploy are the live check; QA's choice of which comes first.
