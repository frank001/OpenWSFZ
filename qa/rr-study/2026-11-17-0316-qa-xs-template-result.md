# XS-TEMPLATE result (QA, 2026-11-17T03:15:57Z `date -u`): VOID (V-POS fails). Back to the Architect.

**To:** Architect (spec `arch/exchange-step-prior` `982ffb45` + Amendment 1 `06198a8d`). **From:** QA. Branch `qa/same-chain`, local, nothing pushed. **Counts only** (NFR-021, HK-037): text was read inside `qa/xs-prior/xs_score.py` and `xs_template_step0.py` and never left them; working files (tone lists, scores, buffers, the capture) are kept in `D:\Projects\claude\_qa-scratch\xs-template\`. Night: live endurance `20261114_2312` (XC ON, 40 m, `66b3ddf1`), one night.

## 0. Verdict

**VOID, decision row 2: V-POS fails.** D(P_low on O at T_E,low) = **0.7495, CI [0.7335, 0.7643]**, bar 0.80 (`MIN_PRESENT_RATE`, `cf_uprime.py:39`). Per the spec's order, V-POS comes before CLOSE, so **G is not a reading**: it is printed in section 4 as a description only. **QA does not re-read the gate with another metric**; section 5 sets out what the numbers say and what you may want to rule on.

## 1. Step 0 and (k) (all before the freeze)

| item | result |
|---|---|
| S rows | 1,149 (XS-PRIOR's, asserted equal: S1 872, S2 277) |
| **F-KNOWN** (S1, matched decode of the replier in the 40 cycles before t; a matched CQ of the replier counts, your acceptance) | **746 of 872 = 85.6 %** at 10 min (5 min 80.3 %, 20 min 88.2 %): XT2-4 hit |
| window (Amendment 1) | **frozen** at +-3.125 Hz x +-0.20 s; not testable 273 rows (23.8 % of S): 126 S1 without a known replier, 147 outside the window; **T0 = 876 rows = 1.021 pp [0.952, 1.094]**: CLOSE-EARLY did not fire (XT2-1 hit) |
| K per cycle (median) | K_low 19, K_all 1,018; FA*_low 1.105e-3, FA*_all 2.063e-5 |
| P rows | 7,435 on-script replies; testable (F-KNOWN, inside the window) 6,544 (P_low 3,287); 6,484 in the acceptance count (P_low 3,258) after the 60 pilot rows |
| buffers | the capture replay (`qa/xs-prior/xs_capture.sh`, shipped stack, XC ON, `--cap-dir`; 2-cycle dry run first; read-back ok at start and end; rc 0; orphan check clean): 2,833 cycles, residual level R3 in 2,630 and R2 in 203; the original buffer O in all |
| **dt mapping for OUR dt** (your A1.2) | the detector places the start at round((dt_c + e + 0.48) x 2000) with dt_c in WSJT-X's convention; our dt is WSJT-X's plus 0.600 s; so dt_c = dt_ours - 0.600 (start = dt_ours - 0.120 s). **Pilot check: 56 of 56 P detections have the argmax inside the +-3.125 Hz / +-0.12 s truth gate (bar 95 %): PASS**; median error 0.0 Hz and +0.01 s |
| code and freeze | scorer `qa/xs-prior/xs_score.py` (selftest ALL PASS incl. must-not-detect cases, vectorised score equal to `xt_lib.s_e`), frozen `b6ac443d`; the freeze record `cca0493b` (T_E per variant and the pilot report) was committed before any acceptance S or P score |
| pilot | 30 S + 60 P + 1,011 null template tests, excluded from the acceptance counts; 203 tasks in 5.1 s on 8 workers |

## 2. The null (acceptance; residual buffer, the opposite-parity cycles, seed 20261116)

| variant | n(null template tests) | floor 3 / FA* | V-NULL-N | **T_E** | T_E interval (cycle bootstrap) | exceedance at T_E | split-half exceedance (other half) |
|---|---|---|---|---|---|---|---|
| V-LOW | 27,143 | 2,714 | **PASS** | **2.93706** | [2.76871, 3.05758] | 1.105e-3 | 1.29e-3 and 8.1e-4 |
| V-ALL | 1,454,295 | 145,429 | **PASS** | **3.68394** | [3.41597, 3.74389] | 2.063e-5 | 0.0 and 2.3e-4 |

The null was sized at 10 x the floor (decided after the pilot, before the freeze, with no S score read). **V-ALL's split-half is asymmetric** (the tail at 2e-5 holds only about 15 exceedances per half): a noisy tail, stated as a limit; the spec has no row on it.

## 3. V-POS (the row that fires)

On O (the original buffer; the P rows were subtracted from the residual, E187), at T_E,low, P_low acceptance rows (3,258): **detected 2,442 = 75.0 %, CI [73.4, 76.4]; bar 0.80: FAIL.** (V-ALL's P rows, 6,484 at T_E,all: 72.2 % [71.2, 73.3], descriptive; the spec's row is V-LOW's.)

**Where the 25 % goes (descriptive; V-LOW, 3,258 rows):** the true template is the best one but its S is below T_E: 386 (11.8 %); a sibling template is best and below T_E: 238 (7.3 %); **a sibling wins above T_E (a wrong-message publish): 188 (5.8 %)**; the true template wins above T_E but the argmax lies outside the truth gate: 4 (0.1 %). (V-ALL: 1,281 below T_E, 453 sibling below T_E, 69 sibling above T_E = **W 1.06 %**.)

**Detection falls with SNR (WSJT-X SNR, lower bin edge, V-LOW, bins with >= 30 rows):** -24 dB: 11/56 (20 %); -21: 44/97 (45 %); -18: 71/169 (42 %); -15: 144/267 (54 %); -12: 209/334 (63 %); -9: 280/406 (69 %); -6: 304/387 (79 %); -3: 301/372 (81 %); 0: 329/372 (88 %); +3: 242/265 (91 %); +6: 189/199 (95 %); +9: 148/151 (98 %). **So the detector is not blind: it sees nearly every reply from 0 dB up, and loses the weak ones.** SNR quantiles (10/25/50/75/90 %): the P rows -16/-11/-4/+2/+8 dB; **the S rows -23/-19/-14/-8/-4 dB**, i.e. S lives about 10 dB below the matched replies V-POS is measured on.

## 4. Descriptive only (not a reading: V-POS comes first)

| | V-LOW | V-ALL |
|---|---|---|
| S acceptance testable | 846 | 846 |
| S detected on the residual | 207 (24.5 % [21.6, 27.2]) | 255 (30.1 % [27.2, 33.1]) |
| S detected on O (descriptive) | 111 | 112 |
| **G (pp of n_ref; x T0 for the 30 pilot rows)** | **0.250 [0.217, 0.283]** | **0.308 [0.271, 0.345]** |
| W on O (a sibling wins above T_E, P rows) | 5.77 % [4.96, 6.57] | 1.06 % [0.81, 1.32] |
| V-SIB (W/(1-W) x detected S per cycle at CI_hi of W; bar 0.021) | 0.0053: passes | 0.0012: passes |

By class (V-LOW, detected / testable): S1 123/291, S2 84/187. (V-ALL, S1 K-high 130/299, S1 K-low 50/291, S2 K-high 30/69, S2 K-low 45/187.)

## 5. What the numbers say, and what is yours to rule on

- The pre-registered row is unambiguous: **V-POS 0.7495, CI_hi 0.7643 < 0.80: VOID.** No row after it is consulted.
- The cause is not a broken detector (the dt mapping passes, the matched replies from 0 dB up are 88 to 98 % detected, the null and the thresholds are valid and V-NULL-N passes). It is **sensitivity at the SNRs where S lives**: at -15 dB the same detector at the same threshold sees about half of matched replies; the S rows are 10 dB lower still on the median and unreached.
- Descriptively, G is 0.25 pp (V-LOW) and 0.31 pp (V-ALL) with CI_hi 0.28 and 0.345 pp, both under the 0.4 pp bar. The spec orders V-POS before CLOSE "because a blind detector would understate G"; the SNR table shows the detector is not blind, it is **limited**, and P's SNR range is higher than S's, so V-POS as built cannot certify the detector at S's SNRs. That is the question for you: whether 0.80 on a P population 10 dB stronger than S is the right validity bar for this detector, or whether the angle is closed on the descriptive G. QA does not take that decision and did not change any row or bar after the scoring.
- **The wrong-message side is benign:** W is 5.8 % (V-LOW) and 1.1 % (V-ALL), V-SIB would pass by a factor of 4 and 17: the E194 / SUP-W failure mode is not the limiter here.
- One scoring run was made on frozen code; nothing was re-scored.

## 6. Predictions (the Architect scores; QA's reading)

| id | prediction | reading |
|---|---|---|
| XT2-1 | CLOSE-EARLY does not fire | **hit** (T0 1.021 pp) |
| XT2-2 | outcome BUILD-WORTH | **miss** (VOID) |
| XT2-3 | V-SIB passes for V-LOW | **hit** as a row (0.0053 <= 0.021), though the decision never reached it |
| XT2-4 | F-KNOWN >= 50 % of S1 | **hit** (85.6 %) |

## 7. Limits

One live night, 40 m. P (matched replies) is the only population with a known truth for V-POS and is 10 dB stronger than S. The residual primary buffer is the shipped stack's; O is descriptive. Timing (the late stage's 13 s budget) and a stage running after XC are not measured. V-ALL's T_E tail is noisy (split-half). Replies whose replier we never decoded (126 S1 rows) and rows outside the window (147) count as not detected. Nothing was pushed.
