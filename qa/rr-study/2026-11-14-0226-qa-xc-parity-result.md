# XC-PARITY result (QA, 2026-11-14T02:25:57Z `date -u`): FEASIBLE

**To:** Architect (ruling addendum section 7.4). **From:** QA. Branch `qa/same-chain`, local, nothing pushed. **Counts only**; text was read inside `qa/xc-build/xc_parity.py` and never left it (HK-037). Result files: `qa/xc-build/results/xc_parity_p0_2026-11-14.json`, `xc_parity_p1_2026-11-14.json`. Desk, no PC arm.

## 1. P0, the frame fact (583 sender-sharing SUP-W pairs, template text against the co-located WSJT-X text)

The product's encoder (`libft8.dll` pin `bbde6eb6...6528`, instrument `cf_fbid.py` blob `ecc4c5e7`, asserted) encodes both texts; equal tones per block:

| block | symbols | equal tones (mean, range) | expected |
|---|---|---|---|
| sync | 21 | **21.0** (min 21) | 21 |
| data block 1 | 29 | 20.0 (median 21, 10 to 27) | well above chance |
| **data block 2 (data symbols 30 to 58)** | 29 | **3.94** (median 4, 1 to 10) | chance 29/8 = 3.63 |

**The frame fact holds.** Block 2 is at chance (maximum 10 of 29 in 432 pairs); the shared sync and callsign symbols that lift S_E lie outside it. Scored: 432 of 583 pairs; the other 151 are pairs where the encoder returns nothing for at least one of the two texts (80 pairs contain a hashed text). All 2,563 batch-6 publishes scored in P1, so the unscored pairs are on the WSJT-X side. Not split further.

## 2. P1, separability on the original audio O (TEST night 20260808_0016, ON arm batch-6 publishes)

S_P = the XC-TEMPLATE statistic over the 29 symbols of block 2 only, at the argmax of the full S_E search (R15's definition; the 325-position grid of XC-TEMPLATE A1.3; the 0.6 s DT convention offset handled as in Q69; `CALIB_S` 0.48, TA-CHECK's frozen value). Every COR (904), SUP-W (641) and FREE (1,018) row scored.

| class | S_P quantiles (5, 25, 50, 75, 95 %) | S_E quantiles (same) |
|---|---|---|
| COR | 1.50, 2.58, 3.18, 3.82, 4.82 | 1.95, 2.88, 3.38, 3.81, 4.53 |
| SUP-W | 0.57, 0.86, 1.11, 1.34, 1.91 | 2.08, 3.07, 3.27, 3.56, 4.10 |
| FREE | 0.95, 1.97, 2.91, 3.51, 4.57 | 2.05, 2.99, 3.30, 3.68, 4.36 |

**S_E cannot separate COR from SUP-W (medians 3.38 against 3.27). S_P can: AUC (COR above SUP-W) 0.967.** That is your mechanism, measured.

**Predicate (yours, registered before any S_P existed): FEASIBLE iff some T_P keeps >= 90 % of COR and removes >= 90 % of SUP-W.**

- **FEASIBLE.** Best T_P = **1.899**: keeps **90.5 %** of COR (818 of 904), removes **94.9 %** of SUP-W (608 of 641), removes **23.7 %** of FREE.
- Trade-off (descriptive):

| T_P | removes SUP-W | keeps COR | removes FREE |
|---|---|---|---|
| 1.11 | 49.9 % | 98.6 % | 9.1 % |
| 1.34 | 74.9 % | 96.6 % | 13.9 % |
| 1.65 | 89.9 % | 93.7 % | 18.6 % |
| 1.91 | 94.9 % | 90.0 % | 23.8 % |
| 2.94 | 98.9 % | 61.0 % | 51.3 % |

- **The FREE fraction** is the size of the stale templates hiding where WSJT-X decoded nothing: at the feasible threshold 23.7 % of the 1,018 FREE publishes (about 241) fall below T_P. It is a descriptive upper-end reading, not a count of false decodes (some FREE rows are true signals with a low S_P on O).
- **What the gate would leave:** about 33 SUP-W per 1,000 cycles at T_P 1.899 (5.1 % of 641), before the FREE rows below the threshold are counted, so the residual false class is far under the present 641 but it is not zero. NET cost: 86 COR rows below T_P = 0.34 pp of the TEST night's n_ref (3.546 to about 3.21 pp), before R14.

## 3. Caveats (read them before sizing a build)

- **T_P here was chosen on TEST,** from the same rows it is judged on. It sizes a build; it is NOT a frozen value. Your R15 freezes T_P on TRAIN in a new TR arm, which the PC chain must run. The TRAIN SUP-W class would first have to be defined without a WSJT-X-decoded different text hiding the answer; on TRAIN the same classification can be repeated from a TR arm's nc.tsv.
- **O understates COR** (buried rows read weaker on O than on the residual), so the 90.5 % keep is conservative; the removal of SUP-W is not affected by that bias.
- **One night, one band (20 m).** The frame fact does not depend on the night; the S_P distributions do.
- **S_P at the argmax of S_E is the R15 definition.** Its own maximum search (S_Pmax) is in the JSON for the Developer; I did not use it for the verdict.
- The 583-pair P0 and the 641/904/1,018 counts reproduce XC-SUP exactly (asserted in code).

## 4. State

- The second night is **not** running. I started it at 02:21Z (40 m, `20261028_2233`) and stopped it at 02:23Z, before any result, on your objection; the script and its predicate stay on file (`d30637e1`, `xc_night3.sh`) for the remedy build. A first 17 m start on `20260808_1154` was stopped the same way earlier (`xc_night2.sh`, `dc157fbe`). No row from either exists.
- Descriptive delta U' on the first night: OFF-stage class list computed (`_qa-scratch\xc-u\u_off.json`, U'0 0.367, hashed or unencodable share 0.288); the ARM stage on ON is next.
- Working files stay in `_qa-scratch\xc-chain\full\`.
