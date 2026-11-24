# LR-FULL, nights 1 and 2: RESULT (QA, 2026-11-20 09:23Z `date -u`). Counts only; no message text, no callsign (NFR-021, HK-037).

**Registered outcome (A1.3c, decision rows as code, first match wins, night 2 added): X1 = OPEN, X2 = OPEN.** One scoring run on the frozen scorer (`lr_decide.py`, `lr_score.py` and the FD-PROXY tree bit-identical to `fe62ebea`; run head `caed79c6`), 09:18:50Z to 09:23:01Z, nothing re-scored, no bar, window or row changed after it. **The path ends in OPEN because V-AGREE-NI cannot be powered at this lever's scale (E218, ruled before night 2).** The per-night NET and H-COST rows are the readings; the pooled instrument row is UNDERPOWERED.

## 1. What was run (HK-022)
- **Command:** `python -I lr_score.py final night1_spec_final.json night2_spec_final.json <out>` from `qa/lr-full/`; the scorer refused to start unless the scorer files were committed and clean. Output `qa/lr-full/night1_night2_final_counts.json`.
- **Night 2 arms:** `CAP=1300 SEL_SHA=894f86ff6d5af650 bash qa/lr-full/lr_arms.sh 20261119_2204 test`: OFF (`--lr-x1 0 --lr-x2 0`) 04:43:54Z to 06:59:02Z (2 h 15 m), ON (`--lr-x1 1 --lr-x2 1`) 06:59:02Z to 09:18:25Z (2 h 19 m); **1,299 contiguous cycles after the 144-cycle pilot, warm-up = the last pilot cycle**, identical in both arms; read-backs OK; **libft8.dll actual = pinned `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`**. Night 2: live 6 h recording `20261119_2204` (40 m, 7.074 MHz, USB codec, PSK off; spectrum scan clean; Section 4: 85.2 % matched, 33.0 WSJT-X rows per cycle). Night 1 as in its report (2,000 cycles, `20261118_1954`).
- Recomputed WSJT-X matching equals the harness flag: 0 mismatches, both arms, both nights. n_ref (WSJT-X rows of the TEST cycles): night 1 42,464, night 2 43,076.

## 2. Rows, per night (NET and H-COST are never pooled)
| row | night 1 | night 2 |
|---|---|---|
| V-RUN | pass (0 abandons both arms; OFF re-run identical) | **pass** (0 abandons both arms; OFF re-run identical) |
| V-H | pass: V-SEP 0.9483 [0.9407, 0.9549], V-GHOST 0.8663 [0.8544, 0.8778], V-BURIAL -0.0023 [-0.0166, 0.0124] | **pass**: V-SEP 0.9578 [0.9515, 0.9639], V-GHOST 0.8688 [0.8570, 0.8801], V-BURIAL -0.0025 [-0.0152, 0.0101] |
| NET(X1) | +0.4733 pp [0.4088, 0.5391] (201 rows) GOOD | **+0.5339 pp [0.4665, 0.6006]** (230 of 43,076) GOOD |
| NET(X2) | +0.9467 pp [0.8527, 1.0493] (402) GOOD | **+1.2420 pp [1.1269, 1.3610]** (535) GOOD |
| X2 split (descriptive) | F1b-passed +0.8407 (357), admitted-only +0.1060 (45) | F1b-passed +1.0795 [0.9695, 1.1851] (465), admitted-only +0.1625 [0.1241, 0.2022] (70) |
| H-COST(X1) | PASS: H-HI 0.00393, CI_hi 0.00597 | **PASS**: H-LO 0.00882, H-HI 0.01301, **CI_hi 0.01949** (budget 0.021: thin) |
| H-COST(X2) | PASS: H-HI 0.00605, CI_hi 0.01009 | **OPEN**: H-LO 0.00809 [0.00215, 0.01530], H-HI 0.01644, **CI_hi 0.02424 > 0.021**; CI_lo(H-LO) 0.0022 is not above 0.021, so not FAIL. Parts: F1b-passed OPEN (CI_hi 0.02313), admitted-only PASS (CI_hi 0.00303). |
| NET(ON) total | +1.5331 [1.4137, 1.6574], above NET(X1)+NET(X2) = 1.42, not flagged | **+1.8827 [1.7417, 2.0182]**, above the sum 1.7759, not flagged (47 other rows newly corroborated indirectly, 1 lost) |
| X2 abandoned candidates | 0 | **0 of 1,299 cycles** (OFF 0) |

**V-AGREE-NI (pooled over both nights, the instrument row only): n = 70 isolated G rows (19 + 51; bar 200): UNDERPOWERED.** phi_U - phi_H = +0.1386, CI [+0.0357, +0.2322] (night 1 +0.1692 on 19 rows, night 2 +0.1272 on 51). **Decision: X1 OPEN, X2 OPEN.** X1 qualifies on both nights' NET (CI_lo 0.41 and 0.47, both >= 0.25) and both nights' H-COST (PASS, PASS); only the pooled agreement row blocks it. X2's night-2 H-COST is OPEN on its own.

## 3. The floors, pilot beside realised (as ruled)
| step | night 2 pilot floor (144 cycles) | night 2 realised TEST floor (1,299 cycles) | night 1 pilot | night 1 realised |
|---|---:|---:|---:|---:|
| X1 unjudgeable buried G rows per cycle | 0.0278 (4 rows) | **0.0038 (5 rows)** | 0.0035 | 0.0020 (4) |
| X2 | 0.0208 (3 rows) | **0.0077 (10 rows)** | 0.0000 | 0.0015 (3) |
The pilot overestimated night 2's floors 7x (X1) and 2.7x (X2), as the Architect ruled (a size guess from 3-4 rows); both realised floors are far under 0.021. G (ON-only unmatched rows) night 2: X1 90 rows (82 judgeable, 8 unjudgeable; 20 isolated, 70 buried), X2 156 rows (146 judgeable, 10 unjudgeable; 34 isolated, 122 buried); isolated part by U' (phi 0.362 on 20 rows for X1, 0.067 on 34 for X2), buried part by H (X1 phi 0.065-0.072 on 65 judgeable buried rows, X2 0.074-0.081 on 112).

## 4. Caveats QA states (HK-026), not in any outcome row
1. **V-AGREE-NI points the same way on both nights: phi_U is higher than phi_H on the isolated G rows (+0.169 on 19 rows, +0.127 on 51; pooled +0.139, CI [0.036, 0.232]).** UNDERPOWERED at 70 rows, so no pass and no fail; had it been powered at this estimate the CI straddles the 0.10 bar (INCONCLUSIVE), not a FAIL. It is the direction in which H would understate where both instruments can see.
2. **X1's night-2 H-COST PASS is thin** (CI_hi 0.0195 of 0.021): a few more buried unjudgeable or plausible-miss rows would have made it OPEN. X2's OPEN comes from its buried part (about 7 to 8 % false on H over 112 rows) plus 10 unjudgeable buried rows.
3. **H's blind spot (a corrupted report or grid within 10 Hz of an undecoded sender reads plausible in about 85 % of draws) is uncorrected, as ruled;** H was validated on one night at a low false share. The unjudgeable rows are carried at 0 / 1, never inferred.
4. **Two nights, 40 m, the shipped stack; night 1 noisy (21 rows per cycle in its TEST block), night 2 busy (33).** NET is per night and never pooled; no gain figure is a shipped gain (diagnostic build, replay of recorded audio).
5. NET counts only rows WSJT-X also decoded.

## 5. Predictions as read by QA (the Architect scores them)
LR-1 X2 is not NO-GAIN: hit (night 1). LR-2 X1 is NO-GAIN: miss. LR-3 H-COST(X2) PASS: hit on night 1, **OPEN on night 2**. **LR-4 V-AGREE-NI passes pooled after night 2: MISS (UNDERPOWERED, n 70).** **LR-5 at least one step reaches GO after night 2: MISS (both OPEN).**

## 6. State
Nothing is pushed, no build spec is written. The PC is NOT hibernated: the Captain withdrew that order on 2026-11-20 ("do not hibernate the system"). Scratch is kept in `_qa-scratch\lr-full\` and `fd-proxy\`; both nights stay reserved for LR-FULL.
