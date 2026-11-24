# FD-PROXY result (angle H, Stage 1), QA, 2026-11-18 09:02Z (`date -u`). Counts only: no message text, no callsign (NFR-021, HK-037).

**Registered outcome (spec §6, decision rule in code, first match wins): VALID.** One scoring run, nothing re-scored, no bar, window or row changed after it.
Spec `arch/false-decode-instrument` f01d6acd, Amendments 1 (3a389fff) and 2 (69dfaa16). Night `20261114_2312` (XC ON, 40 m, `66b3ddf1`), one night.

## 1. What was run (HK-022: the line, the pins, the filter)
- **Command:** `python -I fd_score.py final D:/Projects/claude/_qa-scratch/fd-proxy/score_final.json` from `qa/fd-proxy/`, started 08:59:01Z, 169.9 s. Frozen at `qa/same-chain` **4639e742** (the scorer refuses to start unless `fd_lib.py`, `fd_pilot.py`, `fd_uprime.py`, `fd_score.py` are committed and clean; the run recorded that head). Output `qa/fd-proxy/score_final_counts.json` (sha256 84cbecf1…).
- **Inputs (all `ls`-checked):** replay `_qa-scratch\xc-live-free\ON\nc.tsv` (79,401 rows, 2,833 cycles), `wsjt-x\ALL.TXT` of the gathered night (E = 85,783 Rx FT8 rows), archived WAVs `owsfz\wav` for the U′ side. **Acceptance cycles = 2,550** (the first 283 are the pilot, excluded from every count below).
- **Pins:** `libft8.dll` asserted equal to the pin before the run: actual = pinned = `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`. N-RAND harness built from a scratch checkout of `66b3ddf1` (the unpacker `CohFallbackUnpack` and `Ft8Decoder.IsPlausibleMessage` at `Ft8Decoder.cs:1823`, grammar store null = the replay decoder's). Synthetic sets asserted by sha256 (`nrand_sets.sha256.txt`). U′ instrument `cf_fbid.py` blob ecc4c5e7 asserted by `cf_uprime.load_instrument`, T 0.276, start offset −0.18 s (calibrated on the first 80 confirmed pilot-cycle controls, asserted unchanged).
- **Filter / suites:** no test suite or `--filter` is involved; the selftests were `fd_lib.py selftest` (57 PASS) and the pilot-mode and smoke-mode dry runs on control cycles only.

## 2. Rows
| row | reading | bar | result |
|---|---|---|---|
| **V-N** | rows 79,401, cycles 2,833, batch 6 3,851, E 85,783 | Amendment 1 C1 | **pass** |
| **V-SEP** | s − f_RAND = 0.9552, CI [0.9502, 0.9605] (s 0.9552 weighted to Q's strata; f_RAND 0.000 on 1,398 judgeable noise rows, rule-of-three hi 0.0021) | CI_lo ≥ 0.70 | **pass** |
| **V-GHOST** | s − f_MISS = 0.8775, CI [0.8668, 0.8880] (f_MISS 0.0777; N-FIELD-MISS governs, Amendment 2) | CI_lo ≥ 0.50 | **pass** |
| **V-BURIAL** | s_isolated 0.9572 − s_buried 0.9531 = +0.0041, CI [−0.0059, 0.0139] (P: 3,655 isolated, 6,084 buried) | CI_hi ≤ 0.10 | **pass** |
| **V-AGREE** (batches 2–5, isolated unconfirmed judgeable) | n 533 (≥ 200); φ_H 0.0062, φ_U 0.0361, difference −0.0299, CI [−0.0605, +0.0070] | CI inside ±0.10 | **INSIDE** |
| Outcome | VALID | | |

## 3. φ, the false share of the governed Q (unconfirmed batches 4+5; n_Q 1,150, judgeable 891, unjudgeable 259 = 22.5 %)
- p (plausible share of judgeable Q) 0.9450 against s 0.9552.
- **φ_lo 0.0107 [0.0, 0.0277]; φ_hi 0.0116 [0.0, 0.0303]** (f_lo 0.0000 = min(f_RAND, f_NFIELD visible 0.0259); f_hi 0.0777 = max(f_RAND, f_MISS)).
- **Share of ALL Q, with the unjudgeable rows entered at 0 and 1 (§4.3): 0.0083 to 0.2342.** False decodes per cycle: **0.0037 [0.0, 0.0097] to 0.1056 [0.1016, 0.1121]**. About 0.1016 of the upper end is the 259 unjudgeable rows entered as false; the judgeable part contributes at most 0.0040.
- Unjudgeable share: Q 22.5 % (batch 4: 258 of 1,041; batch 5: 1 of 109), N-RAND 53.4 % (reported side by side, descriptive; the unjudgeable side is NOT estimated, per the Architect's ruling).
- **Stated beside every H reading, NOT corrected for (Amendment 2): X-field ghosts (report or grid corrupted) within 10 Hz of an undecoded sender read plausible in 85.5 % of N-FIELD-MISS draws.**

## 4. Descriptives (each batch on its own; s from that batch's confirmed rows, strata of that batch's Q)
| batch | Q judgeable | Q unjudgeable | P | s | p | φ_lo | φ_hi | false share of all Q, lower to upper | false per cycle, lower to upper |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 363 | 609 | 44,500 | 0.978 | 0.920 | 0.059 | 0.065 | 0.022 to 0.651 | 0.0085 to 0.248 |
| 2 | 253 | 2 | 8,343 | 0.964 | 0.957 | 0.008 | 0.008 | 0.008 to 0.016 | 0.0008 to 0.0016 |
| 3 | 56 | 0 | 750 | 0.964 | 0.946 | 0.018 | 0.020 | 0.018 to 0.020 | 0.0004 |
| 4 | 783 | 258 | 8,583 | 0.954 | 0.941 | 0.014 | 0.015 | 0.010 to 0.259 | 0.0042 to 0.1057 |
| 5 | 108 | 1 | 1,156 | 0.965 | 0.972 | 0.000 | 0.000 | 0.000 to 0.009 | 0.0000 to 0.0004 |
| 6 | 1,721 | 0 | 1,770 | 0.989 | 0.990 | 0.000 | 0.000 | 0.000 | 0.000 |

- **Batch 6 (XC): only C and S are informative** (R and F pass by construction): Q C 0.0006, S 0.0023, R fail 0.0006 (1 row), F-fail 0.0064. The split by XC-LIVE class (COR / SUP-W / FREE, with FREE's NONE half) is **not produced** in this run: `sup.json` holds counts, not per-row classes, and building them would be a new step. Not done; stated.
- **Governed Q by kind:** CQ n 193, s 0.995, p 0.990, φ 0.005–0.006; STD n 698, s 0.946, p 0.933, φ 0.014–0.016.
- **Components alone** (governed): Q n 891: C 0.000, R-fail 0.0168, F-fail 0.0337, F-unseen 0.258, S-behind 0.0045. P n 9,739: C 0.000, R-fail 0.0105, F-fail 0.0293, F-unseen 0.107, S-behind 0.0024. Q is not different from P by stratum (plausible share, Q vs P: ≤ −18 isolated 0.941 / 0.954; ≤ −18 buried 0.946 / 0.949; −17..−10 isolated 0.963 / 0.963; −17..−10 buried 0.926 / 0.960; ≥ −9: n 21 and 19).
- **Synthetic sets** (f, and within 10 Hz): N-FIELD visible B 0.000, A 0.001, X 0.077 (within 10 Hz 0.006), equal-share 0.0259; **N-FIELD-MISS B 0.000, A 0.001, X 0.232 (within 10 Hz 0.855), 0.0777**; with E-drawn calls (descriptive): visible 0.109, MISS 0.186 (B 0.225: a swapped real call is mostly plausible).
- **U′ against H on BURIAL-class unconfirmed rows of batches 4+5** (n 429; s and f from the isolated controls; descriptive only, no verdict re-read): **p_H 0.939, p_U 0.522; φ_H 0.019, φ_U 0.447.** U′'s burial blindness moves its estimate by about 0.43 on the very rows where H reads almost nothing false.
- **§9 add-on (Q failing R whose sender is in no E row at all, per batch):** batch 1: 0 of 2; batch 2: 0 of 1; batch 3: 0 of 0; **batch 4: 4 of 15 (27 %)**; batch 5: 0 of 0; batch 6: 0 of 1; governed 4+5: 4 of 15. So of the 891 judgeable governed rows only 15 fail R, 4 of them from a sender WSJT-X never decoded all night.

## 5. Caveats QA states (HK-026), not in the outcome row
1. **φ is near zero, and so is the agreement test's discrimination.** V-AGREE passed with φ_H 0.006 and φ_U 0.036; the spec sized it for φ ≈ 0.3. Both instruments say "almost nothing false" on isolated rows, which is agreement, but it is agreement at the bottom of the range: the test never saw a population where the two could separate a large false share.
2. **The dominant uncertainty is the 259 unjudgeable rows (22.5 % of Q; batch 1 is 63 %, batch 4 25 %).** H says nothing about them. The bracket's upper end is that ignorance, not a measurement.
3. **The blind spot is real and measured (85.5 %).** φ_hi uses f_MISS 0.078, an equal-share mean over the three fields, so it does not move for the X-field ghost at its sender's frequency.
4. **Confirmed rows may overstate s** (§9): a station WSJT-X can decode is easier for H. That biases φ upward (conservative). V-BURIAL bounds the burial part only.
5. Q's plausible share sits within 0.013 of P's in every governed stratum with n ≥ 100 except −17..−10 buried (Q 0.926, P 0.960, gap 0.034): H does not separate Q from P, which is the reading of a population that is mostly real (or false in the blind spot).
6. One night, 40 m, the shipped stack. Nothing here is citable until the Architect rules.

## 6. Deviations and QA errors in this stage (all disclosed to the Architect)
- **Q81:** my `:1460` line was from this worktree's older tree (shipped: `:1823`). Corrected.
- **Q82:** the first `smoke` dry run judged real pilot-cycle Q rows (batch 6: 184 of 184 plausible) while described as Q-free; fixed, the output kept as `score_smoke_v1_CONTAMINATED…` and never cited; no code or bar changed on that sight.
- Amendment 1 C1–C4 and Amendment 2 (N-FIELD-MISS governs) were adopted by the Architect before the freeze; the +3.2 dB burial variant was pilot-descriptive only (51.6 % → 41.2 % buried share).

## 7. Predictions as read by QA (the Architect scores them)
FD-1 V-SEP passes: **hit**. FD-2 V-GHOST passes: **hit** (on f_MISS). FD-3 V-BURIAL passes: **hit** (diff +0.004). FD-4 outcome VALID: **hit**.
