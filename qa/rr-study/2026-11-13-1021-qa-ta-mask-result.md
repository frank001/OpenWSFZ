# TA-MASK result: NOT-REPAIRED by the registered rule, by a near miss. Masking lifts buried rows from 0.738 to 0.835 present, but CI_lo is 0.786 against the 0.80 bar. A-KEEP and A-GHOST pass.

**Written:** 2026-11-13, `date -u` read 10:20:43Z. **To:** Architect, then the Captain. **Spec:** `arch/accept-gate` `104f197f` + A1 `0777c9b9` + A2 (§10). **Code:** `qa/same-chain` (blobs in the freeze record `9ff18132`), unchanged. **Run:** `tm_run.py own` once (1,740 acceptance rows), `tm_analyse.py` once. No filter applies; the encoder DLL SHA-256 pin is asserted at start. T_M = 0.480 committed before any acceptance S_M. Numbers only; working files in `_qa-scratch\ta-mask\` (pilot rows excluded everywhere).

## 1. The decision, mechanically

| row | predicate | value | result |
|---|---|---|---|
| V-N | n(T_bur) ≥ 100 | 237 | holds |
| **A-KEEP** | CI_lo(PR_M(B1)) ≥ 0.80 and CI_lo(PR_M(B1m)) ≥ 0.80 | 0.981 and 0.963 | **passes** |
| **A-GHOST** (A2.1) | CI_hi(PR_M(ghost) − PR_U(ghost)) ≤ 0.05, paired | CI_hi = **−0.010** (difference −0.041 [−0.074, −0.010]) | **passes** |
| **A-SEE** | CI_lo(PR_M(T_bur)) ≥ 0.80 | PR_M(T_bur) = **0.835 [0.786, 0.883]**; CI_lo **0.786** | **FAILS by 0.014** |

**Outcome: NOT-REPAIRED** (rule 4). The near miss is stated: the point estimate clears the bar by 0.035, the lower end misses it by 0.014 on 237 rows.

## 2. Present rates (acceptance rows only; cycle bootstrap B = 2000, seed 20261113; T_M 0.480)

| group | rows | PR_M | 95 % CI | unmasked U′ rule (0.276), same rows | unscorable (n_s < 20) | masked bins / symbol |
|---|---:|---:|---|---:|---:|---:|
| B1 | 986 | 0.988 | [0.981, 0.994] | 1.000 | 3 | 0.75 |
| B1m | 506 | 0.976 | [0.963, 0.989] | 0.998 | 0 | 0.63 |
| **T_bur** | 237 | **0.835** | [0.786, 0.883] | **0.738** | 5 | 2.34 |
| T_iso | 269 | 0.937 | [0.906, 0.963] | 0.993 | 4 | 0.91 |
| T (all) | 506 | 0.889 | [0.861, 0.916] | 0.874 | 9 | 1.58 |

- **The repair works on the buried rows:** +0.097 (0.738 → 0.835). By ΔSNR quartile (cuts 2, 6, 12 dB), PR_M vs unmasked: 0.90 vs 0.95, 0.91 vs 0.94, **0.94 vs 0.71**, **0.60 vs 0.41**. By |Δf| quartile (cuts 14, 23, 37 Hz): **0.65 vs 0.56**, **0.80 vs 0.62**, 0.97 vs 0.84, 0.90 vs 0.92.
- **What it costs:** the higher T_M (0.480 against 0.276) lowers the rate for rows that did not need repair: T_iso 0.993 → 0.937, B1m 0.998 → 0.976, B1 1.000 → 0.988. A-KEEP still passes with room.
- **Where it still fails:** the quartiles with the strongest or nearest neighbour (ΔSNR > 12 dB: 0.60; |Δf| < 14 Hz: 0.65). The bar is missed by those rows, not by the middle of T_bur. By band, T_bur: A 0.75 (n small), B 0.83, C 0.90, D 0.81.
- **T_bur rows with an unencodable neighbour** (left unmasked; 30 rows): 0.90; without (207 rows): 0.83.

## 3. The ghosts (T_bur acceptance rows with a scorable ghost: 219; 18 rows' strongest neighbour is unencodable)

| ghost | present | note |
|---|---:|---|
| masked (A-GHOST's quantity) | **0.014** (3 of 219) | 11 unscorable under the mask |
| unmasked U′ | **0.055** (12 of 219) | same rows |
| within ΔSNR ≥ 20 dB (14 rows) | masked 0.071, unmasked 0.071 | one row each way: the mask does not remove leakage from a neighbour that strong (the pilot's mechanism) |
| second ghost (neighbour's sequence at its own position, the row's mask) | **0 present, 219 / 219 unscorable** | as predicted |

The pilot's 3 of 30 was a high draw: on 219 rows the unmasked instrument reads **5.5 %** of neighbour-copy ghosts present (a rate on this one construction, not a citable false-decode rate, per the Architect's A2.3), and masking cuts it to 1.4 %.

## 4. Predictions (Architect, §8, A1.5, A2) for scoring at the ruling

SA-1 REPAIRED: **no** (NOT-REPAIRED). SA-2 A-KEEP passes: **yes**. SA-3 A-GHOST passes (restated to A2.1): **yes**. SA-4 withdrawn.

## 5. Limits (§6, K3)

- Not-corroborated rows are not in the test (the direction that lowers PR still more).
- Neighbours are WSJT-X's rows; a product arm masks with its own decodes (a Stage 2 question).
- One night, 40 m; position is WSJT-X's.
- The A-SEE miss rests on 237 rows; a fresh draw of the same size would move CI_lo by about ±0.02, so I do not call the 0.014 miss noise: the rule is registered and it fires.

## 6. What is owed

**The Architect rules.** His §5 consequence for NOT-REPAIRED: to the Captain, (a) route R (a capture replay on today's stack, which does not exist for 20261110: cost stated then) or (b) stop angle A's instrument work and record U′ as blind under burial, with the TA-CHECK size beside every future late-pass U row. Working files stay until the ruling.
