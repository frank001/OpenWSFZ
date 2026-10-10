# STRONG-MISS follow-up B: bit-error profile of the P-WEAK targets (QA, 2026-10-10)

- **To:** Architect, cc Captain. **From:** QA. **Spec:** `2026-10-10-1400-architect-to-qa-spec-strong-miss-followups-a-b.md` section B (`arch/strong-miss` `0625c6fd`). **Protocol:** `2026-10-10-1540-qa-strong-miss-followup-b-protocol.md` (frozen before the run; harness and protocol `e36c6097`). **Go:** the Captain, in the QA window.
- **Run:** 14:08:08Z to 15:37:55Z, one process, detached, exit 0. DLL `a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610`, pin equal at start and end. In-process readback: nhard 24, sign fix on, subtraction ON, threads 8, shim 20260061. No competing process at the end.
- **Nature:** diagnostic, descriptive. One night (`20261009_1752`), one chain, new era. No gain claimable, nothing built, `ft8_coherent_llr_at` not run. Aggregates only (HK-037); callsign scan of the outputs: clean. Aggregates: `qa/rr-study/results/2026-10-10-strong-miss-bprofile/`.
- **Consistency with step 2:** the repeat reproduces it exactly: SM-DECODER 471, SM-P1 480/500, SM-P2 6/500, P-FILTER 73, P-CLEAN 2, P-WEAK 396.

## 1. Validity rows (first)

| row | bar | reading | verdict |
|---|---|---|---|
| **B-V1** CW P95 < NW P5 | | CW P95 = **14**, NW P5 = **67** | PASS |
| **B-V2** convention | saturated round trip 100 % of CW; CW median E < 87 | round trip: **0 failures** on every codeword of 458 CW controls (alternatives included); C# encoder port equals the DLL's codeword on every primary (0 mismatches); CW median E = **0** | PASS |
| **B-V3** NW median E >= 60 | | **74** | PASS |

All three hold, so the classes are scored.

## 2. Groups and exclusions

| group | population | scored | excluded |
|---|---|---|---|
| CW | 480 pilot controls that decoded | 458 | 22 (21 unpackable by the encoder, 1 unresolved `<...>`) |
| NW | 500 null points (codewords drawn with seed 20261012) | 500 | 0 |
| TW | 396 P-WEAK targets | **366** | 30 (29 unpackable, 1 unresolved `<...>`) |

The 30 TW exclusions are all 26 hashed targets and 4 CQ; **the hashed form is therefore not analysed at all in B** (the encoder cannot pack `<CALL>` text). Grid-RR73 alternative won: CW 37, NW 20, TW 17.

## 3. The reading of E (hard-bit errors of 174, best of the 25 points)

| group | n | min | P5 | P25 | median | P75 | P95 | max |
|---|---|---|---|---|---|---|---|---|
| CW | 458 | 0 | 0 | 0 | **0** | 2 | **14** | 24 |
| TW | 366 | 7 | 14 | 22 | **28** | 35 | 53 | 84 |
| NW | 500 | 54 | **67** | 71 | **74** | 77 | 82 | 87 |

Best-point offset: TW sits where CW does (centre 159 of 366, dt +1 step 134; CW 255 and 174), not spread over the window as NW is.

## 4. The classes (366 scored TW rows)

| class | k | % [95 % CI] |
|---|---|---|
| W-NOSIGNAL (E >= 67) | 9 | 2.5 [1.3, 4.6] |
| W-NEAR (E <= 14) | 23 | 6.3 [4.2, 9.3] |
| **W-DEGRADED** | **334** | **91.3 [87.9, 93.7]** |

Splits (W-DEGRADED / W-NEAR / W-NOSIGNAL):
- Form: two-call 275 / 20 / 3 (n 298); CQ 45 / 3 / 5 (53); compound `/` 14 / 0 / 1 (15).
- WSJT-X SNR: (0,5] dB 238 / 12 / 9 (259); (5,10] 74 / 7 / 0 (81); above 10 dB 22 / 4 / 0 (26). W-NEAR rises with SNR (4.6 %, 8.6 %, 15.4 %); all 9 W-NOSIGNAL are in the (0,5] bin.
- Refined sync: inside the controls' P5 to P95 296 / 20 / 8 (324); outside 38 / 3 / 1 (42).
- WSJT-X DT: below 0 s 56 / 3 / 4 (63); 0 to 0.2 78 / 5 / 2 (85); 0.2 to 0.4 150 / 10 / 2 (162); 0.4 and above 50 / 5 / 1 (56).

## 5. Damage profile (E >= 10 only; medians, [P25, P75])

| measure | CW (n 38) | TW all (n 362) | **W-DEGRADED (n 334)** | NW (n 500) |
|---|---|---|---|---|
| burst share (15 data symbols) | 0.81 [0.61, 1.00] | 0.64 [0.50, 0.79] | **0.64 [0.50, 0.77]** | 0.32 [0.31, 0.34] |
| edge share (first and last 10 symbols) | 0.40 [0.14, 0.67] | 0.42 [0.33, 0.56] | **0.42 [0.32, 0.55]** | 0.34 [0.32, 0.37] |
| confident-wrong share | 0.00 [0.00, 0.10] | 0.15 [0.05, 0.32] | **0.14 [0.05, 0.28]** | 0.48 [0.43, 0.53] |

The CW column is small (only 38 of 458 controls have E >= 10), so its quartiles are coarse (its P75 is the ceiling 1.0).

## 6. What it says, and what it does not

1. **The signal is there.** 97.5 % of the scored P-WEAK rows read well below the noise floor (E <= 66 against NW's P5 of 67), and the best point falls where the controls' does. This is not a position or extraction failure for these rows (only 9 W-NOSIGNAL).
2. **It is not a threshold sliver either.** The median row has 28 wrong bits of 174 (16 %), against 0 for the controls, and 91 % are more than 14 away from anything a decodable control shows. W-NEAR (the "bits are good, BP or scaling failed" reading) is 6.3 %, below the spec's 10 % line for a desk read of scaling and BP.
3. **The errors are not uniform and not confident.** Burst share is about twice the empty-point value (0.64 against 0.32): the errors are bunched in time. The edge share is only slightly above the uniform expectation (0.42 against 0.34; 20 of 58 symbols is 0.34). The confident-wrong share is low (0.14 against 0.48 for random bits): the wrong bits are mostly faint ones, not strong wrong-tone energy, so it does not look like a strong interferer.
4. **How to read it against the spec's B.6:** "bursty or edge-heavy" points at time-span or fading handling; "uniform, low-confidence" points at bit formation. The data shows bunched and low-confidence, with only a mild edge excess. It supports neither reading cleanly. QA does not choose between them: that is a ruling for the Architect and a Captain's choice. Note that CW rows with errors are also bunched (0.81), so bunching alone is not specific to the failures.
5. **Limits.** Hard bits before BP; first-stage audio only (no residual pass); the replay is the two-stage call, not the daemon's early/final path; hashed forms not analysed (26 targets); the codeword is the encoder's for the printed text, so a hashed or contest-flavoured over-the-air form might differ; one night, one chain; the CW column for the damage measures is small. The best-of-25 selection lowers E in every group alike. Nothing here is a gain or a build instruction.

## 7. Predictions scored (QA's reading, for your ledger)

WB1 all three validity rows pass: HIT. WB2 W-NOSIGNAL < 20 % of scored TW: HIT (2.5 %). WB3 W-DEGRADED the largest class: HIT (91.3 %). WB4 W-DEGRADED median burst share above CW's P75: **MISS** (0.64 against CW's P75 of 1.00; the CW P75 sits at the ceiling on only 38 rows, so the row is weakly informative; the median is about twice the empty-point value).

## 8. For the Architect

1. What the bunched, faint, mildly edge-heavy profile asks for next: QA has no recommendation beyond the observation in 6.4.
2. Whether the 26 excluded hashed P-WEAK targets matter (a different codeword source would be needed; QA does not propose one).
3. Nothing is pending from QA.
