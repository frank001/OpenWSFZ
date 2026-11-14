# XC-BUILD PC arms: result (QA, 2026-11-14T02:12:53Z `date -u`)

**To:** Architect (ruling owed; spec `arch/cross-cycle-prior` section 3 and amendments 1 to 5). **From:** QA. Branch `qa/same-chain`, local, nothing pushed.
**Counts only.** No message text is in this file (NFR-021, HK-037). Numbers come from `_qa-scratch\xc-chain\full\analysis.json`, produced by `qa/xc-build/xc_analyse.py` (frozen analysis library `xb_lib.py`, seed 20261113, B = 2000).

## 1. Verdict by the pre-registered table (first matching row wins)

**Row 4, ACCEPT (mechanical):** CI_lo(NET) 3.313 pp >= 0.4 pp, and LATE holds. Nothing before it fires: V-OFF PASS, V-STORE PASS, V-WIRE PASS, V-TR-N PASS, SHADOW PASS.
This is a QA mechanical reading. The ruling, and any default-ON, are the Architect's and the Captain's. Two items are still owed by the Architect before any default-ON (PSK Reporter template tag; `BatchesPerCycleFallbackOn = 4`).

## 2. Provenance (HK-020, HK-022)

- **Host:** the PC (the station's platform), Windows, 8 threads read back in every arm, one build for every arm (`f82b6432` harness copy `_qa-scratch\xc-chain\bin_new`), runtime as recorded in each arm's `log.log` readback.
- **Native library pin:** `libft8.dll` SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`, pinned `bbde6eb6...6528`; the chain checked it before every arm and again at the end ("END new-build libft8.dll pin OK", `chain_status.txt`).
- **Run:** `nohup bash qa/xc-build/xc_pc_chain.sh full` with `NOHIB=1`, started 2026-11-13T21:41:03Z (two earlier launches halted in the preflight on my script bugs, fixed in `abb0a4fe`); ended 2026-11-14T02:11:15Z, `halted=0`. Filter: none, every arm ran its full selection (the chain checks the row counts: V-OFF 500, PRE100 100, TR 500, OFF 1000, ON 1000).
- **Clock:** `clock=system` in every arm. Late round abandoned: **0 of 1000 cycles in ON, 0 of 1000 in OFF** (the K4 capacity rule is met on the PC).
- **TEST night:** `20260808_live_run_0016-8080`, first 1,000 cycles from `260808_001600`. **The recording has a hole:** WAVs `001500` to `001545` do not exist, so the warmup cycle is 75 s before the first FULL cycle. The 1,000 FULL cycles are contiguous. Effect: ON's first cycles carry fewer priors (conservative for NET).
- **T_E:** frozen from TR before OFF and ON, **3.076042** (`te.json` sha256 prefix `6e0fbc52b2e989dc`), K = 36 (tested, Amendment 5), FA* 0.000583, 23,219 shadow tests against 5,143 needed. T_E if K were the priors: 3.174 (not used).

## 3. Rows

| Row | Result | Value |
|---|---|---|
| V-OFF vs N24 (TRAIN 500) | **PASS** | `matchedbatch` 0 of 501 lines differ; `testb` 0 of 10,501 (2,000 new batch-6 rows excluded, all zero); per-cycle counts 0 of 500 differ |
| V-OFF text leg (first 100 cycles, new OFF vs pre-change build) | **PASS** | 2,945 rows, 0 differing |
| V-TR-N | **PASS** | 23,219 shadow tests >= 5,143 |
| V-STORE | **PASS** | live prior ages {2, 4, 6} cycles only (-30/-60/-90 s), shadow ages {1, 3, 5}; priorsLive never above what batches 1 to 5 published at those ages (0 cycles above; 4 exactly equal) |
| V-WIRE | **PASS** | ON differs from OFF in 822 cycles; batch 6 non-empty in 822 cycles |
| **NET** | **+3.546 pp [3.313, 3.768]** | n_ref 25,493; corroborated ON 21,239 against OFF 20,335 = **+904 rows**, all 904 matched by batch 6; ON > OFF in 537 cycles, ON < OFF in **0** |
| SHADOW | **PASS** | 25 events in 1,000 cycles = 0.025 per cycle, exact Poisson [0.0162, 0.0369], bar 0.042 (designed point 0.021) |
| LATE | **PASS** | 0 template publishes after the 13 s budget; batch-6 publish p95 7,201 ms (max 8,432); cycle p95 7,281 ms ON against 6,355 ms OFF; 0 cycles over 13 s in either arm |
| ABANDON (descriptive) | 0 | live 0 of 33,360 tested; shadow 0 of 42,482; the "host-bound" label does not apply |
| Stage | | outcome "ran" in 1,000 of 1,000 cycles; 33,360 live templates tested, **2,579 published** (detected), shadow 42,482 tested |

## 4. Why I do not take +3.55 pp at face value yet

- **It is 1.9 times the desk value** (G 1.911 pp) and above the Architect's BX-3 line (NET >= 1.0 pp, p 0.50). A result this far above its prediction wants a check before a ruling leans on it (HK-018, HK-026).
- **Checks already made, all consistent:** the whole gain is batch-6 matches (904 = 904); no cycle is worse with ON; the shadow null agrees with the calibration (25 of 42,482 = 0.00059 per test against FA* 0.00058); the false live detections expected at FA* are about 19.5 of 2,579.
- **What is NOT established:** 2,579 published against 904 corroborated by WSJT-X. The other ~1,675 are either real signals WSJT-X did not print or false. The shadow null says at most about 20 are false; I have not looked at them individually. U' (descriptive row) is **not computed**; angle A's statement 1 stands: U' on O is blind under burial (0.742 against 0.993), cite that beside any U row.
- **One night, one band (20 m), one frozen T_E from a 40 m-era TRAIN night.** The pre-registered rule is one night; a second night is the obvious replication, not a requirement of the spec.

## 5. Open items and leads (QA proposals, not rulings)

1. **Replicate on a second night** with the frozen T_E (about 3 h of PC per OFF + ON pair at 1,000 cycles). It asks whether +3.5 pp is the night or the product.
2. **ΔU' (descriptive)** on these arms, with angle A's caveat beside it.
3. **Where the 904 come from:** matched rows by SNR band, batch-6 prior age (2/4/6) and the first cycles after the recording hole.
4. **Owed by the Architect before default-ON:** PSK Reporter template tag; `BatchesPerCycleFallbackOn = 4`.
5. The committed Linux `libft8.so` on `main` still needs GLIBC_2.43 (the rebuild is skipped when no native file changes); not related to the arms.

## 5b. Lead 2, where the 904 come from (`qa/xc-build/xc_where.py`, counts only, `where.json`)

| SNR band | n_ref | matched OFF | matched ON | batch-6 gain | gain in pp of all n_ref | share of the OFF-unreached recovered |
|---|---|---|---|---|---|---|
| A (>= 0 dB) | 3,902 | 3,673 | 3,693 | 20 | 0.08 | 8.7 % |
| B (-1 to -10) | 9,895 | 8,594 | 8,865 | 271 | 1.06 | 20.8 % |
| C (-11 to -15) | 6,895 | 5,246 | 5,571 | 325 | 1.27 | 19.7 % |
| D (< -15) | 4,801 | 2,822 | 3,110 | 288 | 1.13 | 14.6 % |

- 893 of 904 (98.8 %) are in bands B, C and D, the weak signals; band A has almost nothing left to recover. That is the direction a cross-cycle prior should pull, and it does not look like an artefact of the strong rows.
- By 100-cycle block (0 to 9): 147, 161, 153, 111, 96, 68, 36, 14, 37, 81. The first block (right after the recording hole) is not anomalous; the shape follows the night's activity. No cycle after the hole is special.
- The prior-age split (2/4/6) is not done; the sink holds the ages of the tests, not of the published matches.

## 6. Housekeeping

- Message-text working files (`nc.tsv`, `matched.csv`) remain under `_qa-scratch\xc-chain\full\*` until the lead analysis is done; they are deleted at job close (HK-037).
- No push, no merge, sol not used, no radio.
- Tools: `qa/xc-build/xc_analyse.py` (this analysis), `xc_pc_chain.sh` (`abb0a4fe`). Counts-only result file copied to `qa/xc-build/results/xc_analysis_2026-11-14.json`.
