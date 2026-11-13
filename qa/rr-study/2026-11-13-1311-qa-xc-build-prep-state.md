# XC-BUILD: QA's preparation is done while the Developer builds. Harness, analysis library and the three selections are ready; nothing is run.

**Written:** 2026-11-13, `date -u` read 13:10:17Z at the last commit. **To:** Architect, Captain. **Spec:** `arch/cross-cycle-prior` `14dc9bd3` + Amendment 1. **Dev task:** `dev-tasks/2026-11-13-xc-template-build.md` (`f31458a8`), the Captain's to hand over. No PC window has been used.

## 1. What is ready (QA-owned, under `qa/`, no `src/` change)

| item | state |
|---|---|
| **Replay81 harness** (`qa/rr-study/sub-feas/replay81`, commit `0eaa3868`) | batch 6 is a kind of its own everywhere (`ScoreTestB` `b6` rows, `run.csv` `b6_n,tb6_ms`, outcomes `b6`, matched-batch tag 6, nc-dump kind 6); `-p:HasXcPrior=true` build define with the arguments `--xc-prior 0\|1`, `--xc-shadow 0\|1`, `--xc-te <inf\|number>` (all required, read back at start and end), `--xc-out` (the stage's counts line kept raw, one row per cycle) and `--xc-probe-out` (the numbers-only sink, `_qa-scratch` only). The names follow the dev task; **the XC-specific code compiles only against the Developer's build and is reconciled then**. The default build is unchanged: it compiles against the v2 tree, the harness self-test gives **24 PASS, 0 FAIL** (4 new batch-6 checks), and **8 cycles of arm B reproduced identically** (matched files, every test-B row) |
| **Analysis library** (`qa/xc-build/xb_lib.py`, `xb_selftest.py`, `7612378e`) | K, FA\* = 0.021 / K, T_E from the TR sink (smallest threshold with shadow exceedance ≤ FA\*), V-TR-N, SHADOW by **exact Poisson** (passes iff ≤ 12 events in 500 cycles, ≤ 29 in 1,000, ≤ 8 in 400: asserted), NET with cycle bootstrap, LATE, V-WIRE, the decision order; **22 of 22 mutations killed**. The log-line parsers for V-STORE and LATE wait for the Developer's line format |
| **Selections** (`_qa-scratch\xc-build\`) | `sel_test_1000.json` (sha256 prefix `d12be5054244247b`): the TEST night's **1,000 contiguous cycles `260808_001600` to `260808_042545`**, warm-up `260808_001445` (the preceding archive cycle, 75 s earlier); `sel_test_500.json` (`1b330b7efe342057`) the first 500 of them; `sel_train_100.json` (`3d95b2d944cbd847`) the first 100 TRAIN cycles for V-OFF's text-level leg |
| **TEST reference** | WSJT-X `artefacts\20260808_live_run_0016-8080\wsjt-x\ALL.TXT`: **25,493 rows in the 1,000 cycles (25.5 per cycle; first 500: 33.2; the quieter second half lowers it)**, rows in 998 of 1,000 cycles |

## 2. What waits, and on whom

1. **The Captain** hands the dev task to the Developer, and decides the TEST length (1,000 cycles: SHADOW passes at its designed rate with probability 0.96; 500 cycles: 0.74; +90 min of PC across OFF and ON).
2. **The Developer** builds (≈ 1 day).
3. **QA** then: reconciles the harness with his names; the HK-039 review with a `Reviewed-commit` record **before any arm**; `pre_merge_check.py` before any push; V-OFF (45 min PC), TR (45–50 min), OFF and ON (1,000 cycles ≈ 90 min each): **the Captain's windows**.
