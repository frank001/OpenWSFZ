# LR-FULL night 1 (`20261118_1954`): RESULT (QA, 2026-11-19 14:40Z `date -u`). Counts only; no message text, no callsign (NFR-021, HK-037).

**Registered outcome (A1.3c, decision rows as code, first match wins): X1 = GO-2N, X2 = GO-2N.** One scoring run at freeze `fe62ebea` (`FREEZE_night1.md`), 14:37:00Z to 14:39:06Z, nothing re-scored, no bar, window or row changed after it. **One night can at best give GO-2N (ruled); it is not a GO.** Night 2 is not recorded and needs the Captain's word.

## 1. What was run (HK-022)
- **Command:** `python -I lr_score.py final night1_spec_final.json <out>` from `qa/lr-full/` (spec sha256 `6c2dbfffacef972a`); the scorer refused to start unless `lr_decide.py`, `lr_score.py`, `lr_selftest.py` and the FD-PROXY files were committed and clean (head `fe62ebea`). Output `qa/lr-full/night1_final_counts.json`.
- **Arms:** `SEL_SHA=6638f6acb8f72cb0 bash qa/lr-full/lr_arms.sh 20261118_1954 test`, OFF (`--lr-x1 0 --lr-x2 0`) 08:52:09Z to 11:41:06Z (2 h 49 m), ON (`--lr-x1 1 --lr-x2 1`) 11:41:06Z to 14:36:11Z (2 h 55 m); **2,000 contiguous cycles after the pilot, warm-up = the last pilot cycle**, identical in both arms; read-backs OK; **libft8.dll actual = pinned `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`**; harness `bin_lrfull` over a clean checkout of `80bbd74b`. WSJT-X (the Captain's) stayed open, equal for both arms.
- **Night:** live recording `20261118_1954_endurance_run` (40 m, 7.074 MHz, USB codec, PSK off), reserved for LR-FULL; WSJT-X rows per cycle: pilot 28.6, TEST block 21.2 (a noisier stretch).
- **Recomputed WSJT-X matching equals the harness flag: 0 mismatches in both arms.** n_ref (WSJT-X rows of the 2,000 TEST cycles) = 42,464.

## 2. Rows
| row | result |
|---|---|
| **V-RUN** | **pass**: pins ok; OFF abandons 0 cycles; ON abandons beyond OFF's 0 of 2,000 (bar 1 %); ON >= OFF on batches 1-4 in every cycle; 20-cycle OFF re-run byte-identical (pilot OFF vs `rerun20_OFF`). WSJT-X open beside the arms did not matter by V-RUN's own predicates. |
| **V-H** | **pass**: s 0.9483 (P 6,199, Q 498); V-SEP s - f_RAND 0.9483 [0.9407, 0.9549] vs 0.70; V-GHOST s - f_MISS 0.8663 [0.8544, 0.8778] vs 0.50; V-BURIAL -0.0023 [-0.0166, 0.0124] vs 0.10 (P 2,997 isolated, 3,202 buried). f_RAND 0.0000, f_NFIELD visible 0.0297, f_MISS 0.0819. |
| **NET(X1)** (per night) | **+0.4733 pp [0.4088, 0.5391]**: 201 WSJT-X rows newly corroborated by X1 rows (not matched in OFF) of n_ref 42,464. CI_lo >= 0.25: GOOD. |
| **NET(X2)** (per night) | **+0.9467 pp [0.8527, 1.0493]**: 402 rows. GOOD. Split (descriptive): **F1b-passed +0.8407 pp [0.7525, 0.9351] (357 rows), admitted-only +0.1060 pp [0.0765, 0.1369] (45 rows).** |
| **H-COST(X1)** | **PASS**: H-LO 0.00193, H-HI 0.00393 per cycle; CI_hi(H-HI) **0.00597** <= 0.021. |
| **H-COST(X2)** | **PASS**: H-LO 0.00427, H-HI 0.00605; CI_hi(H-HI) **0.01009** <= 0.021. (F1b-passed part H-HI 0.00565, CI_hi 0.00967; admitted-only part 0.0005.) |
| **V-AGREE-NI** (pooled, the instrument row only) | **UNDERPOWERED: 19 isolated G rows (bar 200)**; phi_U - phi_H = +0.1692, CI [-0.0526, +0.3868]. |
| **Decision** | X1: row 6 **GO-2N** (night 1 qualifies, V-AGREE-NI UNDERPOWERED); X2: row 6 **GO-2N**. |

## 3. G, floors and the hybrid (counts)
G (ON-only rows with that step's tag, no WSJT-X match, not published in OFF): **X1 47 rows (41 judgeable, 6 unjudgeable; 8 isolated, 39 buried; 4 unjudgeable buried); X2 78 rows (74 judgeable, 4 unjudgeable; 14 isolated, 64 buried; 3 unjudgeable buried)** (X2 F1b-passed 73, admitted-only 5). H-HI floors: X1 4 / 2,000 = 0.0020, X2 3 / 2,000 = 0.0015 per cycle, far under 0.021. Isolated part: U' on all isolated G rows (phi_U 0.482 for X1 on 8 rows, 0.187 for X2 on 14 rows); buried part: H (X2 phi_lo 0.097, phi_hi 0.107 on 61 judgeable buried rows; X1 phi 0.0 on 35). f_H and f_U at isolated G positions 0.0000 and 0.0014 (n 1,400); f_RAND at buried G positions 0.0000 (n 1,400).
- **NET(ON) total +1.5331 pp [1.4137, 1.6574]** against NET(X1) + NET(X2) = 1.4200: ON is ABOVE the sum, not flagged (49 further WSJT-X rows newly corroborated by untagged or late-primary rows, the indirect effect of X1's rows on batch 5 and the later stages; 1 WSJT-X row matched in OFF and lost in ON).
- **X2 abandoned candidates: 0 in 2,000 cycles (OFF 0).** LATE (descriptive): last batch end p50 / p99 / max ON 5,345 / 7,128 / 7,766 ms, OFF 5,357 / 7,148 / 7,682 ms; batch-5 publish ON 6,016 / 7,627 / 8,236, OFF 5,811 / 7,489 / 7,682 ms; X2's own run 197 / 330 / 470 ms.
- **The hybrid supersedes the standing DeltaU'_ta (Amendment 3 D6): the standing route is not produced.**

## 4. Caveats QA states (HK-026), not in any outcome row
1. **V-AGREE-NI is UNDERPOWERED (19 rows) and its point estimate is on the wrong side for H**: phi_U is 0.17 higher than phi_H on the isolated G rows (CI [-0.05, +0.39]). On 19 rows that is not a failure and not evidence, but it is the direction in which H would UNDERSTATE the false share where both instruments can see. Night 2 pooled is the only way to read it; the pooled row needs about 200 rows and this night supplied 19 (the pilot's scaling of about 98 per night was too high: the TEST block was noisier, and X1's G is tiny).
2. **H-COST PASS rests on very few G rows** (X1 47, X2 78 over 2,000 cycles) and, for the isolated part, on a handful of U'-judged rows (8 and 14). CI_hi of H-HI is 0.006 (X1) and 0.010 (X2) per cycle against 0.021: about one extra false decode per 100 to 170 cycles at the upper end, on this night's G. H's blind spot (a corrupted report or grid within 10 Hz of an undecoded sender reads plausible in about 85 % of draws) is not corrected, as ruled; H was validated on one night at a low false share.
3. **The buried part of X2 reads about 10 % false on H** (phi 0.097 to 0.107 on 61 judgeable buried rows), which is where U' is blind; it is small in absolute terms because G is small.
4. **One night, 40 m, the shipped stack, a noisy stretch** (21.2 rows per cycle in the TEST block). The A5 gate did not fire (X1 0.094, X2 0.116 pp projected half-widths; realised 0.065 and 0.098).
5. NET counts rows WSJT-X also decoded; rows only OpenWSFZ decodes read as false in the cost and are not counted as gain (conservative on both sides).

## 5. Predictions as read by QA (the Architect scores them)
LR-1 X2 is not NO-GAIN: **hit** (CI_hi 1.05). LR-2 X1 is NO-GAIN: **miss** (NET +0.47, CI_lo 0.41). LR-3 H-COST(X2) PASS: **hit**. LR-4 V-AGREE-NI passes pooled after night 2 and LR-5 a step reaches GO after night 2: **not scoreable until night 2.**

## 6. What follows (for the Architect and the Captain)
Night 2 (a second fresh 40 m recording, then the same pilot-free procedure on the frozen scorer, TEST arms about 6 h) would be needed for a GO; it needs the Captain's explicit go. Nothing is pushed, no build spec is written, and nothing is citable as a decode-rate gain until the Architect rules.
