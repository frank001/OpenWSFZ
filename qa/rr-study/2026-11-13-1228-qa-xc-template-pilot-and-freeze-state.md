# XC-TEMPLATE: pilot read, null scored, T_E = 3.011 committed before any E1 or P acceptance score. One flag: V-POS looks borderline (pilot D(P on O) 24 of 30).

**Written:** 2026-11-13, `date -u` read 12:27:48Z. **To:** Architect. **Spec:** `arch/cross-cycle-prior` `2e133bc0` + Amendment 1 (§10: V-POS on O, the null gate, the in-gate window, T_E interval and split-half). **Code:** `qa/same-chain` `99e7ef85` (blobs `xt_lib` `a11179c2`, `xt_score` `a1b1913f`, `xt_analyse` `4c21dbef`, `xt_selftest` `a5d95021`; **22 of 22 mutations killed**). **No acceptance E1 or P score exists.** Working folder `_qa-scratch\xc-template\` holds numbers only.

## 1. What is frozen

| item | frozen as |
|---|---|
| detector | S_E = mean over 79 symbols of P[known tone] / mean over the 8 bins (`coherent_extract` downconvert + correlate); window = the prior's position ± 3.0 Hz in 0.5 Hz steps (13; inside the ±3.125 Hz gate) × ± 0.12 s in 0.01 s steps (25) = 325 positions, one downconvert and the other frequencies by shifting the decimated baseband (checked equal to a direct downconvert to 6e-4 of the maximum at 10 Hz); TA-CHECK's calibration 0.48 s. **Detected** ⇔ S_E\* ≥ T_E and the argmax within ±3.125 Hz / ±0.12 s of the row's own WSJT-X position; hashed or unencodable E1 rows count as not detected (and stay in the denominator) |
| buffers | primary: the fallback's first-run residual per cycle, `{stamp}_{level}.f32` with `level` = `capture_index.tsv` column 10 (R3 440 cycles, R2 60; arm B's capture); descriptive: O |
| groups | **E1** the 520 frozen rows (76 hashed, 2 more unencodable); **P** matched exact repeats scored on O for V-POS: **4,644 rows** (5,167 less 509 hashed and 14 unencodable: V-POS measures the detector, not hash handling); pilot rows excluded (30 E1, 30 P) |
| null | every matched message with an encodable text at the opposite-parity cycles ± 15 s, tests dropped where `ALL.TXT` holds that text in that cycle: **20,874 tests** (7 dropped; the pool is smaller than the 23,411 I quoted in (k) because **1,266 matched rows are hashed texts that `EncodeMessage` refuses**, and hashed messages are excluded from the null as they are from detection); 1,000 are the pilot's; **19,874 acceptance tests** |
| K, FA\* | **K = 49** (median of the distinct matched texts in the 3 preceding same-parity cycles; the count includes hashed texts, so FA\* is slightly conservative); **FA\* = 0.021 / 49 = 4.286 × 10⁻⁴** per test; V-NULL-N floor 3 / FA\* = 7,000 |
| **T_E** | **3.0113**: the smallest threshold with null exceedance ≤ FA\* on the 19,874 tests (8 exceedances, share 4.03 × 10⁻⁴). **V-NULL-N: PASS** (19,874 ≥ 7,000). `frozen\te.json` sha256 prefix `091a96728a33ccde` |
| T_E interval and split-half (A1.4) | cycle-bootstrap CI **[2.961, 3.413]**; even→odd: T 3.126, exceedance 1.9 × 10⁻⁴ on the odd half; odd→even: T 2.973, exceedance **8.6 × 10⁻⁴** on the even half (twice FA\*): with about 10 exceedances in the pool the threshold is a noisy tail estimate, as (k) said |
| null S_E\* quantiles (50 / 90 / 99 / 99.9 / max) | 1.23 / 1.43 / 2.13 / 2.80 / 3.66 |

## 2. The pilot (30 E1, 30 P, 1,000 null tests; 1,114 tests in 12.4 s on 8 workers: about 0.09 s per test per worker)

| group | rows scored | S_E\* percentiles 5 / 25 / 50 / 75 / 95 | argmax inside the truth window | tone-share baseline ≥ 0.276 |
|---|---:|---|---:|---:|
| E1 on the residual | 27 (3 hashed skipped) | 2.34 / 3.00 / 3.42 / 3.96 / 4.25 | 0.963 | 0.889 |
| E1 on O | 27 | 1.48 / 2.24 / 3.13 / 3.57 / 4.14 | 0.963 | 0.778 |
| **P on O** | 30 | 1.78 / 3.49 / 5.12 / 6.57 / 7.59 | 0.967 | 0.867 |
| P on the residual | 30 | 1.09 / 1.14 / 1.18 / 1.54 / 4.94 | 0.867 | 0.167 |
| null (1,000 tests) | 1,000 | median 1.24, 99th 2.22, 99.9th 2.64, max 3.00 | n/a | n/a |

- **K1's prediction holds:** P (rows we decoded) falls from median 5.12 on O to 1.18 on the residual: they are subtracted there, exactly why V-POS reads on O.
- **Against the pilot null's maximum (3.0) with the truth check:** E1 residual 20 of 27 (0.74), E1 on O 14 of 27 (0.52), P on O 24 of 30 (**0.80**), P residual 4 of 30 (0.13). The final T_E is 3.011.
- **At face value the pilot says BUILD-WORTH is reachable** (D(E1) ≈ 0.7 would give G ≈ 2.6 pp against the 0.4 bar; the bar is crossed at D(E1) ≈ 0.11). Hashed rows (14.6 %) can only lower it.

## 3. The flag: V-POS may fail on a hair

- **V-POS needs CI_lo(D(P on O)) ≥ 0.80.** The pilot's point is 24 of 30 = **0.80**, on 30 rows. If the true rate is 0.80 the interval's lower end on 4,614 acceptance rows is about 0.79, and V-POS fails.
- **What a miss would mean (HK-025):** the detector sums known-tone energy without coherent combining. P rows are signals **our LDPC decoder** reached, some at levels where forward error correction beats a non-coherent energy sum; D(P) < 1 is therefore partly a property of the method, not a fault. V-POS then **VOIDs** a stage whose E1 result may be clear (E1 median S\* 3.42 against T_E 3.01). It is not unreachable (the pilot sits at the bar), so I do not refuse it.
- **I do not ask to change the bar** (no data on file other than the pilot sets one, and changing it after the pilot is the TA-MASK lesson). I flag it so that a VOID, if it comes, is read as "the control sits at the instrument's bar" and not as "the detector is broken", and so that you can say now whether you want that reading or a different bar before the run.

## 4. State

Code frozen (`99e7ef85`), T_E committed with this record. **Next, unless you rule otherwise: `xt_score.py own` once, then `xt_analyse.py` once.** The own stage scores 490 E1 acceptance rows (hashed skipped, counted as not detected) on the residual and on O and 4,614 P rows on O and on the residual: about 10,000 tests, ≈ 2 minutes.
