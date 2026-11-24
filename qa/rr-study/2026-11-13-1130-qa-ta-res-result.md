# TA-RES result: REPAIRED by the registered rule. Scored on the buffer it came from, buried rows read present at 0.992 and every guard passes. But R also reads every not-corroborated late decode present (53 of 53), which no registered row tests.

**Written:** 2026-11-13, `date -u` read 11:29:20Z. **To:** Architect, then the Captain. **Spec:** `arch/accept-gate` `cae3015c` + A1 `ef0b6e51` + A2 (A-RESIDUE run as registered, §9). **Code:** `qa/same-chain` `a6ab9115` (frozen before the pilot); `tr_score.py` and `tr_analyse.py` gained one descriptive stage afterwards (blobs `5281960c`, `e8563eb1`; the verdict path is unchanged). **Run:** capture replay (record `d07670ff`), `tr_score.py own` once (1,740 acceptance rows), `tr_analyse.py`. T_R = 0.2759, committed before any own score. No filter applies; the encoder DLL pin is asserted at start. Working files in `_qa-scratch\ta-res\`, numbers only in this record.

## 1. The decision, mechanically (A1: VOID > CREDULOUS > UNGUARDED > REPAIRED > NOT-REPAIRED)

| row | predicate | value | result |
|---|---|---|---|
| V-REPRO | ≥ 98 % of cycles identical to arm B | 500 / 500 | pass |
| V-PROV | every T row has a resolved source | 0 unresolved | pass |
| V-N / V-N2 | n(T_bur) ≥ 100 / n(A-RESIDUE eligible) ≥ 60 | 237 / **182** | pass / pass |
| **A-KEEP** (A1.2) | CI_lo(PR_R(B1)), (B1m), **(T_iso)** ≥ 0.80 | 1.000 / 0.994 / **0.988** | pass |
| **A-GHOST** | CI_hi(PR_R(ghost) − PR_U(ghost)) ≤ 0.05, paired | ghost R 0.037 (8/219), U 0.055 (12/219); difference −0.018 [−0.051, **0.015**] | pass |
| **A-RESIDUE** | CI_hi(PR_R(residue ghost)) ≤ 0.05 | **0.011 (2 of 182), CI [0, 0.028]** | pass |
| **A-SEE** | CI_lo(PR_R(T_bur)) ≥ 0.80 | **PR_R(T_bur) 0.992 [0.979, 1.000]**, CI_lo 0.979 | pass |

**Outcome: REPAIRED.** The pilot's 1 of 24 residue ghosts was a high draw: on 182 eligible rows it is 2 (0.011).

## 2. Present rates (acceptance rows; cycle bootstrap B = 2000, seed 20261113; T_R 0.2759)

| group | rows | PR_R | 95 % CI | unmasked U′ (O, 0.276) | masked M (TA-MASK) |
|---|---:|---:|---|---:|---:|
| B1 (on O) | 986 | 1.000 | [1.000, 1.000] | 1.000 | 0.988 |
| B1m (on O) | 506 | 0.998 | [0.994, 1.000] | 0.998 | 0.976 |
| T | 506 | 0.994 | [0.987, 1.000] | 0.874 | 0.889 |
| **T_bur** | 237 | **0.992** | [0.979, 1.000] | **0.738** | 0.835 |
| T_iso | 269 | 0.996 | [0.988, 1.000] | 0.993 | 0.937 |

- **By source buffer, T_bur:** R3 179 rows 0.989, R2 20 rows 1.000, X3 38 rows 1.000, O 0 rows. T_iso: R3 227 0.996, R2 37, X3 4, O 1: **the control reads present on the residual buffers as it does on O.**
- **T_bur by ΔSNR quartile** (cuts 2, 6, 12 dB), PR_R / U′ / M: 0.95 / 0.95 / 0.90; 1.00 / 0.94 / 0.91; 1.00 / **0.71** / 0.94; 1.00 / **0.41** / **0.60**. **By |Δf| quartile** (14, 23, 37 Hz): 0.96 / 0.56 / 0.65; 1.00 / 0.62 / 0.80; 1.00 / 0.84 / 0.97; 1.00 / 0.92 / 0.90. The quartiles that U′ and masking could not read (strongest and nearest neighbours) are read at 1.00 and 0.96.
- **A-RESIDUE by source:** R3 2 of 128, R2 0 of 17, X3 0 of 37; within ΔSNR ≥ 20 dB: **0 of 14**. The share of T_bur rows whose strongest neighbour was subtracted before the source buffer: 0.768.
- **A-GHOST within ΔSNR ≥ 20 dB (14 rows):** R 0.071, U′ 0.071 (one row each way), the same stratum and size as TA-MASK.
- **V-O (descriptive): maximum difference 0.0** in tone share between the captured O buffer and the WAV-derived PCM over 200 B1 rows.
- **Our position (descriptive):** our dt is WSJT-X's + 0.6 s (0.6 to 0.7), our frequency within ±1 Hz; scored there (dt − 0.6) PR_R(T) = 0.998 against 0.994 at WSJT-X's position, both present in 0.994 of rows.

## 3. The limit no registered row tests (stated in full; I computed one unregistered descriptive for it)

- **R is not independent of the decode.** A late-batch decode was produced **from the buffer R scores it on**. For a real signal that is fine; for a false decode it means the message's tones are, by construction, the best the decoder found in that same audio. The registered guards test two other constructions (neighbour copies; the subtracted neighbour's own message), not false messages decoded from residue.
- **An unregistered descriptive, post hoc, not a verdict row:** the **53 not-corroborated decodes of batches 4 and 5** in testable classes (49 batch 4, 4 batch 5; hashed rows and untestable classes excluded) scored with R on their source buffer at our position (dt − 0.6): **PR_R = 53 of 53 (1.000), minimum S 0.345, median 0.690**; the unmasked U′ on O reads **37 of 53 (0.698)** present, i.e. 16 of 53 are tested absent on O. So **under R the tested-absent count in the late batches goes to zero on this night.**
- **What this does and does not mean.** Not-corroborated is not the same as false (WSJT-X misses real signals), so I do not claim these are false decodes. It means the instrument, as repaired, **cannot show a late-batch decode absent**: ΔU′ in a Stage 2 arm would read zero by construction for decodes found from the buffer that R scores. A reading of "REPAIRED" as "R is a better U′" would overstate it: R is a better reader of **real buried signals** (TA-CHECK's finding fixed), and a poorer judge of decodes it shares a buffer with.
- This is for the Stage 2 spec: whatever is judged in Stage 2 needs a presence test whose audio is **not** the decode's own buffer, or a control made of false decodes from that same buffer (none exists on file). I have no row for it and add none.

## 4. Predictions (Architect's, §7) for scoring at the ruling

SR-1 REPAIRED: **yes**. SR-2 A-RESIDUE passes: **yes** (0.011, CI_hi 0.028). SR-3 V-REPRO passes: **yes** (500 of 500).

## 5. Limits (§5)

- Not-corroborated rows are not in the registered test (see §3 for the one descriptive).
- One night, 40 m, arm B's stack (CQ-AP OFF, v2 ON); WSJT-X's positions.
- B1 and B1m are scored on O, as registered, so A-KEEP's first two conditions do not test the residual buffers; the third (T_iso) does.
- The A-RESIDUE pass is on 182 rows with 2 events: the interval's top (0.028) is well inside the bar but the row is a hard-case construction, not a false-decode census.

## 6. What is owed

**The Architect rules.** His §4 consequence for REPAIRED: a Stage 2 spec, one fresh pre-registered arm of the refused late round judged by U′ with R as the presence test, under the capture harness, on the Captain's go with its cost. §3 above bears on its design. Working files stay in `_qa-scratch\ta-res\` (natives text inside; deleted at job close), with `ta-check\` and `ta-mask\`.
