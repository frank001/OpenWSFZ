# COH-RES-CAND v2 Stage 2: QA report (2026-11-12, `date -u` 15:36:12Z at the last check): verdict by the registered rows **ACCEPT**

Build `59eb5a8f4d9321b608b410f3d9226c1c927bb1db` (v0.71, `feat/coh-res-cand-v2` on `70bc72b1`), harness `17dcb1fc`, freeze record `7064738a` (code first `17dcb1fc`). Night `20261110_1817` (40 m), the 500 cycles of `qa/cq-ap/live-session-cycle-list.txt`, PC, `libft8.dll` `bbde6eb6…6528` (the pin) at the start and the end of every leg. **No `--filter`** (this is a replay study; the unit suite was run unfiltered at the review). Arm A = the CQ-AP OFF arm, reused (`cq-ap/arms/OFF`, folder hashes in the freeze). **Analysis run once:** `python -I qa/coh-res-cand-v2/crc2_analyse.py main` (blob `c6e48546d09e478e72d9540ae006ecf4a8f5b4d5`, unchanged since the freeze), 2026-11-12T15:35:25Z; the result is `crc2_result.json` beside this report. The Architect rules on it.

## Runs (QA's stamps)

| leg | start | end | wall | rc / preflight | `wsjtx.exe` |
|---|---|---|---|---|---|
| B-OFF (40 cycles, `--cohrescand 0`) | 14:53:24Z | 14:56:32Z | 3 min 8 s | 0 / ok, rows 40 | not running |
| arm B (500 cycles, `--cohrescand 1`) | 14:56:57Z | 15:35:10Z | 38 min 13 s | 0 / ok, rows 500 | not running |

Both legs: pin at start and end, all readback tokens at start and end (`cqap=False`, `cohrescand=False` for B-OFF and `True` for B), orphan check clean. The station daemon was stopped throughout. The PC was left alone.

## Rows

| row | predicate (frozen) | result | |
|---|---|---|---|
| **B-NAT** | `native/` diff empty; DLL = pin at every start and end | empty; pin held at every start and end | **PASS** |
| **B-OFF** | 40 of 40 cycles identical to arm A, every field | **40 of 40**, 0 cycles outside the 40 | **PASS** |
| **B-WIRE** | (i) `resrun != no-snapshot` in 100 % of residual-level cycles; (ii) `resNewGated > 0` or `resNewKept > 0` in ≥ 1 cycle | denominator **500 of 500** cycles (R3 440, R2 60); `resRun=ran` in **500**; the third run produced new-text rows in **155** cycles; the log's residual-level line count equals the denominator | **PASS** |
| **B-KEEP** | every arm-A row of batches 1 to 4 is in arm B | A rows 11,834; **0 missing**; 3 allowed hashed re-renderings (same freq and dt) | **PASS** |
| **B-DUP** | no text twice in a cycle | 0 instances | **PASS** |
| **N-GO / N-STOP** | CI_lo(NET) > 0 pp / CI_hi ≤ 0 pp | NET **+0.357 pp [0.250, 0.464]** (A 11,604 corroborated = 82.90 %, B 11,654 = 83.26 %, n_ref 13,997, 500 cycles with WSJT-X lines) | **N-GO fires**, N-STOP does not |
| **U-OK / U-FAIL** | CI_hi(ΔU′_ta) ≤ 0.021 / CI_lo > 0.021 | ΔU′_ta **0.006 [0.000, 0.014]** per cycle (3 tested_absent outputs in 500 cycles) | **U-OK fires**, U-FAIL does not |
| **B-AB** (Amendment 3) | B cycles with `abandoned > 0` or `resAbandoned > 0` ≤ A cycles with `abandoned > 0` | **0 ≤ 0** (`resAbandoned` total 0) | **PASS** |
| **B-LATE** | B L1′-abandoned cycles ≤ A's + 5 | **0 ≤ 0 + 5** | **PASS** |

**Verdict by the registered rule: ACCEPT** (no validity row failed; N-GO, U-OK, B-AB and B-LATE all pass; neither N-STOP nor U-FAIL fires). Bootstrap B = 2000, seed 20261112, paired over the same cycles, as frozen.

## Descriptive lines (no verdict)

- **The third run:** 179 new-text rows came out of it (`resNew`), the gate dropped **113 (63 %)** and kept **66** (`resNewGated` 113, `resNewKept` 66). `resRun=ran` in all 500 cycles; `resWallMs` median **259 ms**, max **594 ms**; the fallback's total wall time (`fb_wall_ms`) max 1,527 ms. 0 abandoned.
- **Timing:** latest-batch p95 **A 5,459 ms, B 5,221 ms** (B − A = −238 ms) against the 13,000 ms budget. B is not later than A here.
- **B-only rows by batch (text absent from A's rows of the cycle):** batch 4: 67, batch 5: 3, batch 1: 1 (that batch-1 row is the hashed re-rendering case B-KEEP allows). **A-only batch-5 rows: 0.**
- **The not-corroborated new rows (batches 4 and 5):** 70 new outputs, 51 corroborated, **19 not corroborated = 3 tested_absent + 1 tested_present + 4 hashed + 11 in an untestable class.**
- ⚠️ **Where the U side is thin (HK-026, stated, not a rule change).** Only the classes `report` and `report CQ` are testable on this night (frozen from arm A), so the registered ΔU′_ta, which counts `tested_absent` only, can judge **4 of those 19 rows** (3 absent, 1 present). The other 15 (4 hashed, 11 untestable class) are **not shown present and not shown absent**. Counting every not-shown-present row as a possible wrong decode gives (3 + 4 + 11) / 500 = **0.036 per cycle as a point value**, above the 0.021 bar; **I computed no interval for it and the registered row does not use it.** On #272's night the untestable count was 0 and the hashed count 2. Read the ACCEPT as "no wrong-payload signal where the instrument can see", not as "no wrong decodes".
- **NOT COMPUTABLE (withdrawn, Amendment 4):** the gated-out rows' C / TA split; `resNewGated` counts stand as above.

## What QA does not conclude

- It does not say v2 is free of wrong decodes (see the thin-U point), nor that the gate is *why* the U side is clean: the third run's wrong-payload rate without the gate was not measured, and 113 of 179 rows were dropped.
- One night, one arm. The gate was fitted on a 20 m night (R-F4 and L1′ OFF) and tested on 40 m (both ON); this result does not say it transfers to other bands or stations.
- **CQ-AP was OFF in both arms** (A already existed that way); the interaction with CQ-AP ON, which the station runs, is **unmeasured**. Any v2 ON on the station starts a new era.
- No timing figure here is a sol-class timing (PC only).
- The dry run and the smoke tests of the freeze are not results.

## Predictions (for the Architect's scoring; QA does not score them)

CV-4 (U-OK, restated 0.35) and CV-5 (ACCEPT, restated 0.25) both occurred.

## Next (spec §5 item 7)

ACCEPT leads to `pre_merge_check.py` on a clean checkout of the exact commit (`59eb5a8f`, HK-006) and then the Captain's sign-off to merge **with the setting OFF**. Turning it ON at the station is a separate decision of his and starts a new era. QA holds `cq-ap/arms/OFF`, `coh-res-cand\raw` and `scratch`, and `coh-res-cand-v2\` until v2 is ruled. Committed beside this report (numbers only, no message text, scanned for NFR-021): `qa/rr-study/results/2026-11-12-coh-res-cand-v2/` (`crc2_result.json`, `boff_result.json`, arm B's `coh.csv`, `run.csv`, `late.csv`, `abandon.csv`, `third.csv`, both `status.txt`). Scratch-only: arm B's `nc.tsv` (SHA-256 `7515ae451be38529ee472a87…`) and `log.log` (`cf78eca4a7283d0f1eb5dfeb…`).
