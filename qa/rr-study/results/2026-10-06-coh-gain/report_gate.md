# COH-GAIN Q-GATE (Amendment 7, spec section 16): the own-strength gate test

QA, 2026-10-07. Offline, one night (`20261004_1634`), one band (40 m), DLL SHA-256 `2fa6d993…f365` (shim 20260058), build `be3cc5ac`. No `--filter` suite: this is a harness run, not a test run.

## Verdict

**No form is GATE-OK. GA and GC are GATE-OPEN, GB is GATE-FAIL (no threshold feasible on TRAIN). No step-3 form is named.**

| Form | TRAIN threshold | TEST KG (95 % CI) | TEST UPC (95 % CI) | Row |
|---|---|---|---|---|
| GA keep F1b ≤ T1 | T1 = 17.552 dB | +4.07 pp [3.81, 4.33] | 0.178 [0.145, 0.213] | **GATE-OPEN** |
| GB keep F2 ≥ T2 | none feasible (U_max 0.15) | not run | not run | **GATE-FAIL** |
| GC both | T1 = 17.552 dB, T2 = 0.379 | identical to GA | identical to GA | **GATE-OPEN** |

KG clears the 1.0 pp bar with room (CI_lo 3.81). UPC does not clear 0.15: the point estimate is 0.178 and the interval [0.145, 0.213] straddles the bar, so the pre-registered row is OPEN, not OK. The TRAIN threshold sat exactly at the cap (0.149), so the TEST excess is the usual regression from a threshold picked at its limit. GC's F2 limb is inert (the pair selected equals GA's kept set), so the F2 consistency check adds nothing on top of strength.

## Validity

- Q1 (reproduction of persisted C3_ok, C3_crc, C3_path, C3_nbe, computed after the features): **4,949 / 4,949 rows reproduced, 0 not.** PASS.
- Q2 (feature predicates give both answers on synthetic signals) and Q3 (no-leakage signature): committed in `d748e721`; 6 tests, plus 9 new for the threshold/row module (`test_cg_gate_rows.py`, including GC grid = brute force).
- Order of operations enforced in code and visible in git: `6a8fe449` (row list SHA `ee4b243f…dd4ff` + harness) → features → `899448af` → thresholds committed (TRAIN only) → `--test` (refuses unless the thresholds file is tracked and clean).

## Figures

- TRAIN samples 5, 1, 2, 4 (1,240 cycles): GA keeps 1,395 RIGHT, 185 unexplained, 110 M-NEAR (UPC 0.149).
- TEST samples 6, 8, 9 (930 cycles, 27,495 rows): GA keeps 1,118 RIGHT, 166 unexplained, 71 M-NEAR. Unexplained per kept RIGHT = 0.148. M-NEAR is 5.2 % of kept outputs (not counted as unexplained).
- TRAIN KG (GA, T1 = 17.552 dB): +3.77 pp [3.55, 3.99] (1,395 kept RIGHT over 36,960 rows), UPC 0.149 [0.121, 0.179]; TEST KG +4.07 pp (so the gain did not regress; only UPC did).
- F1b ≤ 17.55 dB runs the fallback on the WEAKER own-strength rows and withholds it on the strongest (corrected 2026-10-07 on the Architect's review; the first draft said the opposite). The unexplained residue is concentrated on strong rows (Architect's join: 609 of 912 unexplained at WSJT-X SNR ≥ −5 dB), which is why a strength gate removes it.

## Limits (spec 16.7)

Noise-only candidate false decodes are unmeasured (needs the step-3 replay); UNEXPLAINED is an upper bound (M-OWS counted against the gate, M-NONE includes anything WSJT-X missed); one night, one band, offline; native cost unmeasured. KG here is kept RIGHT per all rows and is NOT reconciled with the pooled NET_C3 +1.37 pp (different numerator/denominator); do not difference them.

## What it means

The gate removes most unexplained output yet not enough at U_max 0.15 on held-out cycles, while delivering ~4 pp. The remaining question is for the Captain/Architect: the OPEN row is a precision problem (a CI straddling the cap), not a gain problem. A tighter U_max-compliant threshold would be a post-hoc choice and is NOT made here.

Files: `gate_rows.json`, `gate_thresholds.json`, `analysis_gate.json`; features `artefacts/rr_2026-10-07_coh_gain_gate/gate_features.csv` (numbers only; HK-037).
