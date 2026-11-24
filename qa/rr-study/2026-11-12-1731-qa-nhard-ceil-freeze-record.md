# NHARD-CEIL freeze record (QA): build, DLL pin, inputs, arms, bars with their sources, analysis code and self-test, dry run. **No arm output exists.**

**Written:** 2026-11-12, `date -u` read 17:30:24Z at the last check. **To:** Architect, then the Captain. **Spec:** `arch/fp-alarm-nhard` §2 with Amendment 1 (`524c05ca`, A1.3 for TOOL-FAIL, A1.4, A1.5) and the step 1 ruling (`1b89cada`, "step 2 proceeds with U′ only"). One complete record: the analysis code, its self-test and the dry run are committed **before** it (`5704d92f`). Any change to a frozen item after an arm's output exists is a complete redo, not an amendment.

## 1. The question and the arms

How much does OSD contribute on today's decoder? **N24** (`--nhard 24`) against **N0** (`--nhard 0`, OSD off), the stack the station runs: Deep (`three1`), kmin 5, osdCorr 0.05, R-F4 ON, L1′ ON, fallback + multi-set ON, `Both`, **CQ-AP ON** (`--cq-ap 1`), **v2 ON** (`--cohrescand 1`), 8 threads. **The two command lines are identical except `--nhard`** (`qa/nhard-ceil/nhard_arms.sh`, arm function; its readback preflight requires at the start and at the end of each process `nhard=24 ` or `nhard=0 `, `cqap=True`, `cohrescand=True`, Deep, kmin 5, osdCorr 0.05, 8 threads, R-F4, L1′, fallback, multi-set, `Both`).

| item | value |
|---|---|
| night, cycles | `20261110_1817` (40 m, the Captain's CQ-AP session, WSJT-X alongside), the 500 cycles of `qa/cq-ap/live-session-cycle-list.txt` SHA-256 `842e67909378a0d1dbf387b27d2e080b4f1e8c1dec3e9bd9770e2e3bac76c8f9`; selection `_qa-scratch\cq-ap\sel_500.json` SHA-256 `c618a66e24bb0d129aa6f5df0ecdad978a53f4b0e9e991d308557378fef5de7f` (13 warm-up cycles, then the 500) |
| build | `bin_v2` built from `feat/coh-res-cand-v2` **`59eb5a8f`** (harness `17dcb1fc`, flags as in the v2 freeze); `libft8.dll` SHA-256 **`bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`** (the pin); `Ft8.FitProbe.dll` `9aab54a24dfd541e288083247bac1c6cbe5f4450eb8a202d861d765581d918ba` |
| tree identity | the spec's build is `main` `260190e8`. `git diff --stat 59eb5a8f 260190e8 -- src tests native` shows exactly **two files, the Linux `libft8.so` and the macOS `libft8.dylib`** (refreshed binaries from #281); source, tests and the Windows DLL are identical, so `bin_v2` is reused (V-NAT asserts the native diff is empty) |
| order and cost | N24 then N0, one after the other (`bash nhard_arms.sh both`, detached), about **85 min** of PC (the CQ-AP ON arm took 41.9 min on this night; v2 adds a few minutes); PC exclusive, station daemon stopped, WSJT-X closed or idle and recorded in each `status.txt`; **the Captain's go is needed** |

## 2. Rows and bars, and where each number comes from (HK-038)

Predicates are the code in `qa/nhard-ceil/nhard_analyse.py` (header docstring, `row_set`, `row_wire`, `compute_nat`, `verdict`).

| row | predicate | number and source |
|---|---|---|
| **V-NAT** (validity) | native diff empty; DLL = pin at the start and end of each arm | spec §2; the pin is the CQ-AP and v2 arms' DLL |
| **V-SET** (validity) | both readbacks equal except `nhard`; N24 reads 24, N0 reads 0; `cqap=True`, `cohrescand=True` | spec §2 |
| **V-WIRE** (validity) | N24 and N0 differ in the published rows of ≥ 1 cycle | spec §2 (plumbing floor); NHARD-REP A3: at 0 the OSD gate rejects every codeword |
| **C-NET** | NET_{N24−N0} with a 95 % CI: corroborated rows of N24 minus N0 (WSJT-X match), per 100 reference rows, paired cycle bootstrap B = 2000, seed 20261112 | as v2 / `crc_analyse.py` at `87c5486a`; TRAIN FIX24 − FIX0 on file: +0.082 [+0.044, +0.123] at 621 cycles |
| **C-U** | ΔU′_ta,{N24−N0} with a 95 % CI: N24's new-text rows (absent from N0's rows of the cycle) not corroborated, classified tested_absent, **all batches (1 to 5)**, per cycle with WSJT-X lines | **QA's choice of batches (the spec does not name them): OSD acts in every native pass, so its false accepts can appear in any batch**; TRAIN's ΔU (+0.005 [0, +0.010]) was over all not-confirmed rows |
| **SETTLED** | CI_hi(NET) **< 0.15 pp** AND CI_hi(ΔU′_ta) **≤ 0.021** | **0.15 pp: the Architect's choice of the smallest prize worth a below-24 grid (A1.5, his E166; about KEEP-5's +0.146 pp); not a resolution limit. The Captain may move it before data, never after.** QA's power table (a plan, normal approximation, half-width 0.044 from TRAIN's own contrast): P(SETTLED) 0.86 if OSD's contribution is unchanged (0.082 pp), 0.005 if doubled; P(GRID) 0.99 if tripled. **0.021: U_bar_G, ruled absolute (v2 A1.3).** |
| **GRID** | CI_lo(NET) ≥ 0.15 pp OR CI_lo(ΔU′_ta) > 0.021 | as above |
| **BETWEEN** | otherwise: goes to the Captain with the numbers | spec §2 |
| **VOID** | any validity row fails; nothing else is read | spec §2 |
| **Flag** | CI_hi(NET) < 0: OSD **costs** decodes on this stack; the Captain is told | spec §2 |
| **Wording (TOOL-FAIL)** | SETTLED is worded **"settled where U′ can see"**, with U-COV beside it; the FP-ALARM tool (frozen `0aca3945`) is **not used**, and C-F does not exist | step 1 ruling, A1.3 |

**Descriptive lines (no verdict):** **U-COV** (the share of N24's new not-corroborated rows that U′ can judge, with hashed and untestable counts; on the v2 night it was 4 of 19); NET and ΔU′_ta by batch; N0-only rows; latest-batch p95 per arm against 13 s; abandoned counts (fallback, third-run `resAbandoned`, L1′ round); and **N24 minus v2's Stage 2 arm B** (only `--cq-ap` differs: the first CQ-AP effect on the v2 stack), no verdict.

## 3. U′ classes: frozen from arm A, not from N24 (a deviation from the spec's wording, stated before any output)

The spec says "the U′ classes frozen from N24". Classes derive from the reference arm's confirmed decodes, so they cannot exist before N24 has run, and the freeze is to precede any arm output. **I reuse the classes frozen from arm A of this very night** (`qa/coh-res-cand-v2/frozen/uprime_arm_a_classes.json`, git blob `1760b58f6e6e0398e25e1a50b610a70a45cb9934`, SHA-256 `84ec02bafa75740a142b16b96beeccb36723dfb156209c4e1da6fe020cd3d9b2`, testable classes `report` and `report CQ`; null p99 0.2931 against T = 0.276, no flag), computed on the same audio before any N24 or N0 output. After the run I will also compute the classes from N24 (`cf_uprime.py off`) and report whether they equal arm A's, **descriptive only; the verdict uses the frozen ones.**

## 4. Analysis code, self-test, dry run

| item | value |
|---|---|
| analysis | `qa/nhard-ceil/nhard_analyse.py`, git blob **`c02f04f9bad26997ee4128deca9cb8bc91f7c39e`** (`main`, runs once; imports `crc2_analyse.py` at blob `c6e48546d09e478e72d9540ae006ecf4a8f5b4d5` for the loaders, matcher, bootstrap and instrument wrapper) |
| self-test | `qa/nhard-ceil/nhard_selftest.py`, blob **`ffa921c8a77eb25a26efd78f01101d71e784fc88`**: a synthetic 40-cycle night (Q-prefix calls), every verdict branch and both bars on both sides (SETTLED, GRID, BETWEEN, VOID, the OSD-costs flag), V-SET and V-WIRE case by case, U-COV counts, all-batch counting, the descriptive N24-minus-arm-B line. **ALL PASSED; 15 mutations killed** (each bar moved either way, the four strictness choices, a validity failure reading BETWEEN, no flag, a flag on `<= 0`, V-WIRE not a validity row, batches 4 and 5 only, V-SET ignoring cqap or comparing unstripped lines) |
| real-data smoke (plumbing only) | the existing CQ-AP ON arm against its OFF2 repeat stood in for N24 against N0: 500 cycles through the real loaders, matcher, bootstrap and instrument. Not a result and not citable |
| arm driver | `qa/nhard-ceil/nhard_arms.sh`, blob **`46492b292526b3535e18bb1983799612581401cb`** |
| **dry run** (A1.4) | `bash nhard_arms.sh dry`, 17:28:45Z to 17:29:27Z: 3 cycles OUTSIDE the selection of the old night `20260930_1930`, `--nhard 0` then `--nhard 24`, both `--cq-ap 1 --cohrescand 1`: rc 0 and preflight ok for both (pin at start and end, every readback token incl. `nhard=0` / `nhard=24`, `cqap=True`, `cohrescand=True`), orphan check clean, **`wsjtx.exe` not running**. The analysis's V-SET accepts the two readbacks. **Plumbing only (not a gain, loss or timing):** the live window was not read; V-WIRE reads 0 differing cycles on these 3 cycles, which is expected at that size and says nothing. Outputs in `_qa-scratch\nhard-ceil\arms_dry` (scratch) |

## 5. The invocations (fixed)

```
bash qa/nhard-ceil/nhard_arms.sh both            # N24 then N0, about 85 min, detached; then, ONCE:
python qa/nhard-ceil/nhard_analyse.py main       # writes _qa-scratch\nhard-ceil\nhard_result.json; refuses to run twice
```

## 6. What this record does not contain

No arm output of any kind: `_qa-scratch\nhard-ceil\arms` holds no `N24` and no `N0` folder, and nothing of either has been read. No number of this study's verdict has been computed. The dry run and the smoke test are plumbing. The alarm tool takes no part.
