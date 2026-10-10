# STRONG-MISS (a): result (QA to Architect)

- **From:** QA. **To:** Architect, cc Captain. **Read-out:** 2026-10-10 12:01Z (`date -u`). **Run:** 10:32:56Z to 11:53:48Z (4,844 s), one process, 433 cycles x 2 arms.
- **Protocol:** `2026-10-10-1130-qa-strong-miss-run-protocol.md`, committed (`8f9f3f7a`) before any decode; spec `2026-10-10-1015-architect-to-qa-spec-strong-miss-replay.md` with amendment 1. Data: `artefacts/rr_2026-10-10_strong_miss/` (copied to `qa/rr-study/results/2026-10-10-strong-miss/`).
- **Nature:** diagnostic and descriptive. One night (`20261009_1752`), one chain (direct USB CODEC), first nhard 24 + corrected-OSD row, subtraction ON. No gain is claimable and nothing is pooled. Aggregates only (HK-037); the result file was scanned for callsign-shaped tokens: none.

## Validity (read first)

| row | result |
|---|---|
| **SM-V1** | PASS. `libft8.dll` SHA-256 `a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610` equals the pin at the start (10:32:56Z) and at the end (11:53:48Z); harness readback identical at start and end: subtraction ON, threads 8, nhard 24, sign fix set 1 / read 1, kMinScorePass2 10, osdCorrThreshold 0.10, shim 20260061. Build checkout `421e3ce2`. No orphan process. |
| **SM-V2** (frozen 99 % / 1 %) | **PASS.** R-OWN reproduced **8,057 of 8,064 live OpenWSFZ rows (99.91 % [99.82, 99.96])** in the 433 cycles; **5 R-OWN rows (0.06 % [0.03, 0.15]) are not in the live output**. Per cycle (amendment 1): **423 of 433 cycles have an equal row count**, sum \|diff\| **12 of 8,064 rows = 0.149 %**, net -2. For comparison the 10-01 subtraction-ON replay against the 09-30 live night (older build, other night, counts only) had 409/430 equal cycles and 0.42 %. |
| **SM-V3** | C recovered in R-OWN: **1,671 of 1,671 (100 % [99.8, 100])**. |
| residual pass | ran 433 + 433 times; **0 deadline-abandoned, 0 contained exceptions** in either arm (867 log lines including the warm-up). |
| SM-V4 self-check | R-OWN and R-WSJ outputs differ in **262 of 433 cycles** (the two captures are different files; 0 would have been suspicious). |

Basis of the bar and the stated limits are in the protocol note: not the live early/final path, process-global hash table (arms interleaved per cycle, key collapses `<...>`), no repeat run.

## Classes (504 targets, exclusive, first match wins)

| class | targets | share (Wilson 95 %) |
|---|---:|---|
| SM-LIVE (R-OWN decodes it) | 0 | 0.0 % [0.0, 0.8] |
| SM-CAPTURE (R-OWN misses, R-WSJ decodes) | 33 | 6.5 % [4.7, 9.1] |
| **SM-DECODER (both miss)** | **471** | **93.5 % [90.9, 95.3]** |

By form (n; LIVE / CAPTURE / DECODER):

| form | n | SM-LIVE | SM-CAPTURE | SM-DECODER |
|---|---:|---|---|---|
| two-call | 318 | 0 | 20 (6.3 % [4.1, 9.5]) | 298 (93.7 % [90.5, 95.9]) |
| CQ | 72 | 0 | 6 (8.3 % [3.9, 17.0]) | 66 (91.7 % [83.0, 96.1]) |
| hashed | 66 | 0 | 3 (4.5 % [1.6, 12.5]) | 63 (95.5 % [87.5, 98.4]) |
| compound `/` | 48 | 0 | 4 (8.3 % [3.3, 19.6]) | 44 (91.7 % [80.4, 96.7]) |

SM-DECODER by WSJT-X SNR bin: (0,5] dB 340, (5,10] dB 101, >10 dB 30. By WSJT-X DT bin: <=0 s 86, (0,0.5] s 345, (0.5,1] s 26, >1 s 14.

## Reading

- **The replay reproduces the live run (SM-V2 and SM-V3 pass), so the classes are not descriptive-only.** There is no SM-LIVE: nothing the live run missed was decodable offline by the same build on the same audio. The live-only explanations (thread scheduling with subtraction ON, early/final split, dedup order, the input path at run time) are not supported by this night.
- **SM-CAPTURE is small:** 33 targets (6.5 %) decode on WSJT-X's copy of the audio and not on OpenWSFZ's. That is a real but minor capture-chain difference; it is 33 rows in 433 cycles and I did not look further (no per-target view, HK-037).
- **SM-DECODER is 93.5 %** with a spread across all forms and no form separating: this is a reproducible decoder gap on strong, uncrowded, standard-form signals. 72 % of them sit between 0 and 5 dB (WSJT-X's figure), so most are only just above the threshold used to call them strong.
- The step 2 gate (at least 50 in SM-DECODER) is met (471). Step 2 also needs the Captain's go in the QA window.
- Limits: one night, one chain; the first stage of the product is the two-stage call, not the daemon's early decode path; the live process's 15 h callsign-hash history is not reproduced (arms interleaved, key collapses `<...>`); no replay-to-replay repeat on this build.

## Facts for scoring the Architect's blind predictions (scored at the ruling)

SM1 (SM-V2 passes as frozen): yes. SM2 (SM-DECODER largest class): yes. SM3 (SM-CAPTURE < 15 % of T): yes (6.5 %). SM4 (SM-LIVE >= 25 %): no (0 %). SM6 (compound `/` has a higher SM-DECODER share than two-call): no (91.7 % against 93.7 %, intervals overlap widely).
