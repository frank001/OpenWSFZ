# LATE-SUB L1′: FREEZE RECORD (committed BEFORE any L1′ output on the verdict night; V6)

**From:** QA · **Frozen:** 2026-10-30T07:16:20Z (`date -u` at writing) · **Spec:** `8152d4ce` + Amendment 1 §8 `e3fd391e` (`arch/late-sub`) · **QA review:** `2ce7eabc`
**State:** pilot and run NOT started. The only L1′ outputs that exist are the V7 regression (refset cycles 1-40, already-read data, name `reg40`). **The run needs the Captain's go.**

## Frozen items (the V6 checker parses the `key=value` lines)

1. **Verdict night:** `20261022_1949_endurance_run-gathered`, selection = R-F4's frozen 2N selection (stride 3, offset 1, first 800 slots; 0 outage drops; first `261022_194915`, last `261023_054830`, warm-up `261022_194900`).
   - selection_sha256=cf9908a5dcc66ef8966693b2d29ae5bd04fc357d3e1af5058b0e35d7eea6726e
   - file: `D:\Projects\claude\_qa-scratch\coh-gate-r-f4\selection_2n.json`
2. **U′ classes:** R-F4's frozen 2N classes, from the 200-cycle Original arm (the first 200 selected cycles), instrument blob `66dd1e94403ba2b26d4f0482a8320ef66bc4f049` (asserted equal to the loaded instrument), 4 testable classes of 5, `T_frozen` 0.276.
   - classes_sha256=0d83d685db2aee961211b022d5b563c0b5b24a83e51f16c126d0f6cff870ab25
   - file: `D:\Projects\claude\_qa-scratch\coh-gate-r-f4\u2\orig_classes.json`
3. **DLL (PC, Windows):**
   - dll_sha256=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
   - build: Replay81 against `main` `c2c85c45` (worktree `_qa-scratch\gap-residual\main-tree`), output `_qa-scratch\late-sub\bin_l1p`; `Ft8.FitProbe.dll` SHA-256 `7f41b06fc3a9d6a6b68018cb8e8c96894f5785a3ea3f350d8afff8db4804099b`.
4. **Code commit (the harness mode, arm script, checks, analysis):**
   - code_commit=b7c17464fea3bdc31f12b41d17a455ca83b8ff03
   - files: `l1p_arm.sh`, `l1p_check.py`, `l1p_analyse.py` (`qa/rr-study/gap-residual-run/`), `LateSub.cs`, `Program.cs` (`qa/rr-study/sub-feas/replay81/`). V6 requires them unchanged since this commit.
5. **Arm:** Amendment 1 of LATE-SUB, L1′ per spec §1: fit list = published batch 3 ∪ batch 4 (unrounded `OutDtS`); `RunThirdPassAsync(B, fit, alsoKnown = batch 1 ∪ batch 2)`; its primary decodes are the L1′ rows; no Arm C, no fallback on B or R4; HashStateSave/Restore around every extra call; publication emulation as D5. Mode `--late-sub-mode l1p`.
6. **Baseline for NET and ΔU′:** this same run's own product output (`nc_dump.tsv` of the run, batches 1-4). V1 vs sol is descriptive only.
7. **Rows (exclusive, in this order; predicate is code in `l1p_analyse.py`):** L1′-GO: `CI_lo(NET)` ≥ 0.5 pp and `CI_hi(ΔU′_ta)` ≤ 0.021 and H-SHARE ≤ 0.5. L1′-COST: `CI_lo(NET)` ≥ 0.5 but the U or H condition fails. L1′-STOP: `CI_hi(NET)` < 0.5. L1′-OPEN: otherwise. Bars: 0.5 pp, 0.021 tested_absent per cycle, h 0.5 (the COH-GATE-G bars; HK-038 origin in spec §4). Bootstrap by cycle, B = 2000, seed 20261030.
8. **HK-026 (mechanical, Amendment 1 E3):** if any unconfirmed L1′ output on the OFF arm falls in `untestable_class`, `l1p_analyse.py` **withholds the verdict** and prints `HK026_REFREEZE_REQUIRED`. Then the Original arm is run on the remaining 600 cycles (about 1 h, outside the 4.5 h estimate), the classes are re-frozen from all 800 cycles in a new record, and the verdict is computed once. The report states the cycle count behind the classes.
9. **Descriptive legs:** refset `20260925_2010`, OFF only, `selection1200.json` (`328c85d4`), run **from cycle 1 to cycle 1,200** so that the product baseline is the one LATE-SUB used (a process that starts at cycle 401 has another hash-table history; the continuous-arm corroborated count differs: 18,833 against 18,844). The block read is cycles 401-1,200. This costs about 2.4 h, not 1.4 h (the spec's 800-cycle estimate assumed a start at 401): QA recommends it and will ask the Captain; an 800-cycle start at 401 is the cheaper alternative and is then reported as a different baseline. ON on the verdict night: descriptive.

## Validity rows already evidenced (before any verdict-night output)

| row | result |
|---|---|
| **V7** (mode l1p on refset cycles 1-40 against the old LATE-SUB pilot) | **PASS**: 0 cycles differ in level, calls, V2 b1/b2/b3/R3-bytes, V3 b4, snapB; `fit_n_new` = `fit_n_old` − `pubC_old` in all 40 cycles; run.csv batch counts and nc_dump identical; 0 Arm C and 0 L2 rows written |
| **V8** (n_ref of the verdict selection on this PC) | **PASS**: n_ref 20,753; cycles with WSJT-X lines 799 of 800; selection hash matches item 1 |
| V0 | the DLL in `bin_l1p` equals item 3 |

## Order from here
This record committed → Captain's go → pilot (first 40 cycles of the verdict selection; V0/V2/V3/V5/V6/V7/V8 only; no outcome read) → verdict night OFF → ON → refset leg (OFF) → analysis → report → Architect's ruling. Message text stays under `D:\Projects\claude\_qa-scratch\late-sub\` and is deleted at job close (HK-037).
