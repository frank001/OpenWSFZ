# STRONG-MISS follow-up B (P-WEAK bit-error profile): run protocol (QA, frozen before the run)

- **To:** Architect, cc Captain. **From:** QA. **Spec:** `2026-10-10-1400-architect-to-qa-spec-strong-miss-followups-a-b.md` section B (`arch/strong-miss` `0625c6fd`). **Go:** the Captain, in the QA window ("go", after the explanation of what B gives).
- **Nature:** diagnostic and descriptive. One night (`20261009_1752`), one chain, first nhard 24 + corrected-OSD row. No gain claimable, nothing built. Aggregates only (HK-037). `ft8_coherent_llr_at` is NOT run.

## Frozen by the spec (not re-opened)

Groups TW (the P-WEAK targets), CW (the pilot controls that decoded), NW (the 500 step-2 null points, each scored against the codeword of a control drawn with seed 20261012). `E` = hard-bit errors (sign of the pass-0 LLR, positive = bit 1) against the 174-bit codeword, at the best of the step-2 25 points. Grid-RR73 rule as in step 2. Unresolved `<...>` excluded and counted. B-V1: CW P95 < NW P5. B-V2: saturated LLRs from the encoder codeword give 0 parity errors and `crc_ok` on 100 % of CW, and CW median E < 87. B-V3: NW median E >= 60. Classes W-NOSIGNAL (E >= NW P5) / W-NEAR (E <= CW P95) / W-DEGRADED, first match wins. Measures: burst share (largest count in 15 consecutive data symbols / E, for E >= 10), edge share (first and last 10 data symbols), confident-wrong share (errors above the median |LLR| of the correct bits of the row), offset of the best point. If a validity row fails, no W-class is scored.

## Choices QA makes here, frozen before the run

| item | choice | reason |
|---|---|---|
| Process | the step-2 run is repeated in one process (replay, pilot, classification), and B is scored inside it; the P-WEAK set is the step-2 classification recomputed | nothing per message on disk (amendment 1); the replay is already validated against live output (SM-V2 99.91 %). Consistency check reported: the P-WEAK count must equal step 2's 396, the CW count 480, the pilot rows must repeat |
| Codewords | primary: the DLL encoder's tones, Gray-inverted. Grid-RR73 alternative: the primary payload with g15 = 32373, passed through a C# port of ft8_lib's CRC-14 and `encode174` (generator table generated from `constants.c` of build `421e3ce2`, `LdpcGenerator.cs`) | the DLL encoder cannot produce the grid form. The port is checked against the DLL on every primary codeword (a mismatch counts into B-V2 and fails it) |
| B-V2(i) | the saturated round trip (+-8 LLRs, `ft8_ldpc_decode_llrs` BP-only, 0 parity errors, `crc_ok`) is checked on EVERY codeword of every CW control, alternatives included | stronger than the spec's "primary or alternative" |
| Best point | fewest errors over the 25 points and, for RR73 texts, over the two encodings; ties keep the first in step 2's order (nearest the centre) | spec; deterministic |
| NW codewords | seed 20261012 draws, in the order of the null points, from the pilot-sample controls whose text packs | spec says "a control drawn with seed 20261012"; QA's reading: from the 500 sample |
| Percentiles | nearest rank on the sorted values, index `(int)(p * (n - 1))` | one rule for all groups |
| Splits | form (step 2's groups), WSJT-X SNR bin ((0,5], (5,10], >10 dB), refined sync inside or outside the controls' P5 to P95 (or refine failed), WSJT-X DT bin (dt < 0, 0 to 0.2, 0.2 to 0.4, >= 0.4 s) | spec lists the axes; the DT edges are QA's, frozen here |
| Hashed texts | `<CALL>` with a call inside is encoded as printed | stated limit: the over-the-air bits for a hashed call may differ from the encoder's, which would inflate E for those rows. The form split shows it |
| Smoke (disclosed) | before freezing, the machinery was run on 20 controls from OUTSIDE the pilot sample and 20 empty points on another seed, with a fixed rough offset: C# port equals the DLL codeword on 2,030 packable control and target texts (0 mismatches; 145 unpackable, 14 of them unresolved hash; 164 end in RR73); saturated round trip 60 of 60; smoke E: controls median 0 (max 39, n 19), nulls median 75 (67 to 82, n 20). NOT the run; no target was scored | |

## Limits stated now

First-stage audio only (the residual pass is not modelled). `E` is measured before BP and without OSD. The replay is the two-stage call, not the daemon's early/final path. One night, one chain. P-WEAK is a class from step 2 in which SM-P2 fired (1.2 %); B does not use P-CLEAN.

## Run

`python qa/rr-study/sub-feas/strong_miss_run.py --bprofile` (detached). Output `artefacts/rr_2026-10-10_strong_miss_bprofile/`. Estimate: replay about 80 to 85 minutes, then the pilot and the classification (about 7 minutes in step 2) plus the profile passes (about 5 minutes more).
