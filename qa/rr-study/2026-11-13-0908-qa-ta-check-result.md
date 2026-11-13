# TA-CHECK result: BLIND-BURIED by the registered rule. Rows buried under a stronger neighbour read present only 74 % of the time; isolated rows of the same strength read 99 %.

**Written:** 2026-11-13, `date -u` read 09:07:52Z. **To:** Architect, then the Captain. **Spec:** `arch/accept-gate` `4336a281`. **Code:** `qa/same-chain` `980ce3a7` (blobs in the freeze record `4e82574a`), unchanged. **Run:** `tc_score.py ctrl` (before the freeze), `tc_score.py tgt` once, `tc_analyse.py main` once. No filter applies. Working files: `_qa-scratch\ta-check\` (scores keyed by stamp:index, no text).

## 1. The decision, mechanically (A1.2, first match wins)

| # | row | condition | value | fires |
|---|---|---|---|---|
| 1 | VOID | CI_lo(PR(B1)) < 0.80 | CI_lo = 1.000 | no |
| 2 | BLIND | CI_hi(PR(T)) < 0.80 and CI_lo(PR(B1m) − PR(T)) > 0 | CI_hi(PR(T)) = 0.894 | **no** |
| 3 | **BLIND-BURIED** | V-N holds for T_bur, CI_hi(PR(T_bur)) < 0.80 and CI_lo(PR_std(T_iso) − PR(T_bur)) > 0 | n(T_bur) 267 ≥ 100; CI_hi(PR(T_bur)) = **0.792**; CI_lo(diff) = **0.205** | **YES** |

**Outcome: BLIND-BURIED.** V-N: n(T) 536, n(T_bur) 267, n(T5) 53. V-NULL: p99 0.2759 vs 0.276.
**Near-miss stated:** CI_hi(PR(T_bur)) is 0.792, 0.008 under the 0.80 bar; the contrast clears zero by a wide margin (0.205).

## 2. Present rates (cycle bootstrap B = 2000, seed 20261112, 500 cycles)

| group | rows | PR | 95 % CI | by band A / B / C / D |
|---|---:|---:|---|---|
| B1 (convention check) | 1,000 | 1.000 | [1.000, 1.000] | 1.00 / 1.00 / 1.00 / 1.00 |
| B1m (SNR-matched control) | 536 | 0.998 | [0.994, 1.000] | 1.00 / 0.994 / 1.00 / 1.00 |
| **T** (batches 4 + 5) | 536 | **0.868** | [0.838, 0.894] | 0.90 / 0.86 / 0.89 / 0.85 |
| T4 | 483 | 0.865 | [0.835, 0.894] | 0.91 / 0.85 / 0.90 / 0.84 |
| T5 | 53 | 0.887 | [0.792, 0.963] | 0.83 / 0.95 / 0.79 / 0.92 |
| **T_bur** (stronger neighbour within 50 Hz) | 267 | **0.742** | [0.691, 0.792] | 0.80 / 0.76 / 0.78 / 0.69 |
| **T_iso** | 269 | **0.993** | [0.981, 1.000] | 0.94 / 1.00 / 1.00 / 1.00 |

- **PR(B1m) − PR(T) = +0.131 [0.104, 0.161]** (a batch effect exists, but T as a whole stays above the bar: row 2 needs CI_hi(PR(T)) < 0.80).
- **Standardised contrast** (all four bands qualified, 0 T_bur rows left out, 0 NaN replicates; weights = T_bur's band mix A 0.056, B 0.337, C 0.240, D 0.367): PR_std(T_iso) = 0.997 [0.992, 1.000]; PR(T_bur) in those bands 0.741 [0.691, 0.792]; **difference +0.255, CI [0.205, 0.307]**.
- **Reading:** the weak-row explanation does not hold here. Isolated rows of T read present at 99 % in every band, down to band D, so the instrument's blindness in T is **burial, not SNR**. The burial effect is the same in every band (0.69–0.80 for T_bur).

## 3. Descriptives

- **PR by first-publishing batch** (B1 = the 1,000 draw): 1: 1.000; 2: 0.697 (300 rows); 3: 0.704 (27); 4: 0.865 (483); 5: 0.887 (53). Batch 2 is almost all buried (289 of 300) and is not in T.
- **T_bur by the neighbour's ΔSNR quartile** (cuts 2, 6, 12 dB): 0.96, 0.95, 0.71, **0.42** (n 48 / 75 / 72 / 72). **By |Δf| quartile** (cuts 14, 23, 36.5 Hz): **0.56**, 0.61, 0.86, 0.93 (n 61 / 70 / 69 / 67). The nearer and the stronger the neighbour, the lower the rate.
- **Tone-share deciles** (10th to 90th percentile), T_bur: 0.17, 0.23, 0.33, 0.41, 0.48, 0.57, 0.62, 0.67, 0.74; B1: 0.78, 0.83, 0.88, 0.90, 0.93, 0.97, 0.98, 1.00, 1.00; B1m: 0.74, 0.79, 0.83, 0.88, 0.90, 0.93, 0.97, 0.98, 1.00. The threshold is 0.276: about 3 of 10 T_bur rows fall below it.
- **Arithmetic check (v2 new-text rows, `crc2_result.json`):** tested rows 4.0 (0.008 per cycle × 500), observed tested-absent 3.0, expected if every tested row were real (1 − PR(T)) × 4 = 0.53. Four rows; descriptive only, not a count to read.

## 4. Limits (K3, A1.3)

- **Not-corroborated rows are not in the test.** Every row here was decoded by WSJT-X. A real signal that WSJT-X missed is probably weaker or more buried, so its present rate is probably lower than PR(T) (the direction that makes the instrument blinder still, not safer).
- **n(T5) = 53**: its interval is [0.79, 0.96]; TC-4 (PR(T5) < PR(T4) at the point) is a MISS (0.887 vs 0.865).
- **WSJT-X's dt** may lower every PR slightly: B1 and B1m read 1.000 / 0.998, so the convention does not break the instrument on non-buried rows.
- **The testable-class filter** drops 1,211 of 2,048 confirmed batch-4 rows (59 %) and 137 of 190 batch-5 rows; T is the report-shaped rows only.
- **Not a statement about how many refused decodes were real** (Stage 1).

## 5. Predictions (Architect's, A1.4 and §7) — for scoring at the ruling

TC-1 V-CTRL passes first run: **yes**. TC-2 BLIND (row 2): **no** (CI_hi 0.894). TC-3 BLIND or BLIND-BURIED: **yes** (BLIND-BURIED). TC-4 PR(T5) < PR(T4) at the point: **no** (0.887 vs 0.865). TC-5 PR(T_bur) ≤ PR(T_iso) − 0.10: **yes** (0.742 vs 0.993, a gap of 0.25). TC-6 CI_lo(PR(B1m)) ≥ 0.80: **yes** (0.994).

## 6. What is owed

**The Architect rules** (his §4 consequence for BLIND-BURIED: Stage 1 as an instrument repair, presence scored on the buffer the decode came from, then, on the Captain's go, one fresh pre-registered arm of the refused late round under the repaired instrument; no earlier verdict is re-read). Working files stay in `_qa-scratch\ta-check\` until the ruling (HK-037; no message text in them).
