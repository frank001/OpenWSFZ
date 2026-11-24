# COH-RES-CAND v2 freeze record (QA): build, DLL pin, inputs, arm A manifest, bars with their sources, analysis code and self-test, dry run. **No arm output exists.**

> **Correction 2026-11-12 (the Architect's E165; QA ledger Q59):** this record labelled several replay nights "20 m". The dial frequency in each night's WSJT-X log (second column, `ALL.TXT`) is **7.074 MHz (40 m) for every replay night on file** (`20260922_2056`, `20260925_2010`, `20260930_1930`, the `20261004` to `20261028` runs and `20261110_1817`); only the live station session of 2026-11-10 was on 20 m. The band-shift caveat in this record is therefore withdrawn; what remains is a night-to-night and configuration difference. Edited where it lives; the original wording is in the git history.

**Written:** 2026-11-12, `date -u` read 14:46:44Z at the last check. **To:** Architect, then the Captain. **Spec:** `arch/coh-res-cand-v2` §3 with Amendments 1 (A1.2, A1.3), 2 (A2.1), 3 (A3.1) (`53cf80a6`). **Build review:** `qa/rr-study/2026-11-12-1432-qa-code-review-coh-res-cand-v2-59eb5a8f-APPROVED.md` (`b5e65309`).
This is ONE complete record: the analysis code, its self-test, the instrument classes and the dry run are all committed **before** this record, in `17dcb1fc`. Nothing below changes after an arm's output exists. Any change to a frozen item after that point is a complete redo (the CQ-AP rule), not an amendment.

## 1. The build under test

| item | value |
|---|---|
| build | `feat/coh-res-cand-v2` **`59eb5a8f4d9321b608b410f3d9226c1c927bb1db`**, base `70bc72b1` (v0.71, shim 20260072, FR-104), clean detached checkout `_qa-scratch\coh-res-cand-v2\tree` (`git status` empty) |
| `native/` | `git diff --stat 70bc72b1 59eb5a8f -- native src/OpenWSFZ.Ft8/Native` **empty**; `libft8.dll` SHA-256 **`bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`** (the pin, equal to the CQ-AP arms' DLL) |
| the gate | `freq <= 1097` Hz on the published integer Hz (A2.1); constant `CohFallbackAudioSelector.ResidualRunMaxFreqHz`, formed in `PublishedFreqHz` (the review's table); **not re-fitted** |
| harness | Replay81 at QA commit **`17dcb1fc`** (`qa/rr-study/sub-feas/replay81/Program.cs` blob `d84d2f4bf4ddc41338b64c5a35e86f1a3f56d7ef`): the fallback-line regex accepts v2's tail and eight `res*` values are appended as the LAST columns of `coh.csv` (only on a `HAS_COHRESCAND` build; arm A's file layout is untouched). The older CQ-AP configuration still compiles (checked). Without this change the line would not have matched and arm B's `coh.csv` would have been blank. |
| build command | `dotnet build Replay81.csproj -c Release -p:RepoRoot=<tree> -p:HasSubfeas=true -p:HasMaxThreads=true -p:HasTwoStage=true -p:HasOsdSignFix=true -p:HasThirdPass=true -p:HasCohFb=true -p:HasCohFb4=true -p:HasLateRound=true -p:HasCohMs=true -p:HasCohAudio=true -p:HasInternals=true -p:HasUngated=true -p:HasCohResCand=true -p:HasCqAp=true -o _qa-scratch\coh-res-cand-v2\bin_v2` |
| `bin_v2` SHA-256 | `libft8.dll` `bbde6eb6…6528` (pin); `Ft8.FitProbe.dll` `9aab54a24dfd541e288083247bac1c6cbe5f4450eb8a202d861d765581d918ba`; `OpenWSFZ.Ft8.dll` `9031c3354bd578a6498b190784d3d073a98d7738470ecdf4a91157c80d2f78f0`; `OpenWSFZ.Abstractions.dll` `8785eee73bec7a13675b3de683e2f5eb9b7d3f6045d6bdd748538f506f6c9ae4`; `Ft8.FitProbe.exe` `b6516f29ccc53793c972fa3cd956104f8f19beb85a2a270c63e2c45246ff67c9` |

## 2. Inputs

- **Night:** `20261110_1817_cq-ap-live` (40 m, the Captain's CQ-AP session with WSJT-X alongside, FT991A profile `frans`), WAVs `owsfz\wav` (739), WSJT-X `ALL.TXT`.
- **Cycles:** the 500 of `qa/cq-ap/live-session-cycle-list.txt`, SHA-256 `842e67909378a0d1dbf387b27d2e080b4f1e8c1dec3e9bd9770e2e3bac76c8f9`, in that order, one process; selection `_qa-scratch\cq-ap\sel_500.json` SHA-256 `c618a66e24bb0d129aa6f5df0ecdad978a53f4b0e9e991d308557378fef5de7f` (13 warm-up cycles, then the 500).
- **B-OFF selection:** built at run time from `sel_500.json` (the first 40 of the 500, the SAME warm-up, so the process-global hash table sees arm A's sequence); its SHA-256 is written to `arms\chain_status.txt` when it is built.

## 3. Arm A: reused, with its full manifest

`_qa-scratch\cq-ap\arms\OFF` (build `7ca00264` = `70bc72b1`'s tree, `--cq-ap 0`, 2026-11-11 18:05:35Z to 18:45:35Z, 500 rows, rc 0, `wsjtx.exe` not running). Its repeat OFF2 differed in **0 of 500** cycles (CQ-AP arms report, `8c38585a`), so A is reproducible on this PC. It must be unchanged until v2 is ruled (the Architect's request); SHA-256 now:

`nc.tsv` `89ed189fc63933c75efd47faa46544347696ccb9f7702a0cb8aeb68a998209df` (12,036 rows) · `coh.csv` `01a1d9b0659e435883661a3b50ad25612a8e4252b39c7cf4bd6e2f9c2a0465f6` · `late.csv` `90ddd164d566e70622685388f27f10fd2009a6b2beb79f4d367331d82939225d` · `run.csv` `a51cbc52d61fdd6d426ac066485ec1a82166ee4b985a227a06cf5c6d9b4918a9` · `testb.csv` `f13531cd9a9d7885eeb2c62b83790ba7fa7666da8f634d0d77d0ee4d799b007f` · `abandon.csv` `833800f1560d91be7052b4f1f457538ab63080045ffda8bf6a064bfbc3459801` · `third.csv` `d551c605f5648b23c2018ea7730ffe8142cbd8be507001fc2d7ff4700c0b3fd6` · `outcomes.csv` `da596ab94e994f72438264412b4428ca800530eb5f42dae421dfd57538ae0f79` · `matched.csv` `767cc56dce541b286b99bf05a60e338a97b5dbff0121c55caae583561ed5d188` · `matchedbatch.csv` `9ab0e1a960a14a3aa0086ff8822e75d0f6190676cf7d97948aa95874924fc59b` · `log.log` `9b1acaa9ac44ea2fd444e9ef0f2d132ce53d2efc1434acb2e08f4a3d779b2c22` · `status.txt` `0875308cb57995fbcc10c6a588ad00b3a965065220c87b6416c5f81383961f9a` · `stdout.txt` `e3b0c442…b855` (empty).

## 4. The U′ instrument for this night

`cf_uprime.py off` on arm A's `nc.tsv` + `testb.csv` (T = 0.276 frozen, instrument blob `ecc4c5e7:cf_fbid.py` asserted), pinned DLL, WAVs through a junction. **Run twice, byte-identical:** `uprime_off_classes.json` SHA-256 **`84ec02bafa75740a142b16b96beeccb36723dfb156209c4e1da6fe020cd3d9b2`**, committed as `qa/coh-res-cand-v2/frozen/uprime_arm_a_classes.json` (git blob `1760b58f6e6e0398e25e1a50b610a70a45cb9934`); the full `uprime_off.json` SHA-256 `9dc1dcdb1716b47bf8a6ae29a33a25364586131b3299bb54bf63bd969013cc84` (scratch).
- Testable classes: `report` and `report CQ` (each 45 of 50 sampled present, rate 0.90); every other class is `untestable_class` and counts as NOT shown present only in the instrument's own U′ (the ΔU′_ta of the verdict counts `tested_absent` only, as #272).
- **Null check:** this night's null p99 = **0.2931**, |p99 − 0.276| = **0.0171 ≤ 0.03**, no exit-4 flag; the instrument is usable here (Amendment 1 A1.3).
- **U′0 on arm A (descriptive, A1.3):** total 0.558 per cycle (500 cycles with WSJT-X lines); tested_absent 0.136; hashed/unencodable 0.422; untestable class 0.000. **The U bar is 0.021 per cycle ABSOLUTE (ruled, A1.3); the Captain may change it only before arm B, and has not as of this record.**

## 5. Rows and bars, and where each number comes from (HK-038)

Predicates are the code in `qa/coh-res-cand-v2/crc2_analyse.py` (header docstring and functions `row_*`, `ci_rows`, `verdict`).

| row | predicate | number and source |
|---|---|---|
| **VALIDITY (any failure ⇒ VOID, one re-run on a fixed build)** | | |
| B-NAT | git diff of `native/` empty AND DLL SHA = pin at the start and end of every leg | spec §3; the pin is the CQ-AP arms' DLL |
| B-OFF | the build with the setting OFF, first 40 cycles, rows identical to arm A's, every field (kind, matched, freq, dt, snr, path, text, apKind), **40 of 40** | spec §3; OFF vs OFF2 differed in 0 of 500 on this night and PC |
| B-WIRE | (i) `resrun != no-snapshot` in **100 %** of residual-level cycles; (ii) `resnewgated > 0` or `resnewkept > 0` in ≥ 1 cycle | spec §3; the snapshot plumbing passed 400/400 in #272 (report, B-WIRE) |
| B-KEEP | every arm-A row of batches 1 to 4 is in arm B; hashed re-renderings at the same freq and dt are allowed and counted; batch 5 outside | spec §3, A1.2 |
| B-DUP | no text twice in a cycle of arm B | spec §3 |
| **PRECISION** | | |
| N-GO / N-STOP | CI_lo(NET_B−A) > 0 pp / CI_hi ≤ 0 pp | **0 pp: the Captain's bar for #272 (2026-11-08, "fine with me"), carried unchanged**; he may change it only before arm B |
| U-OK / U-FAIL | CI_hi(ΔU′_ta) ≤ 0.021 / CI_lo > 0.021 | **0.021: U_bar_G, ratified 2026-10-28 (COH-GATE-G) on the replay nights of that study (all 40 m); ruled absolute for this night (A1.3)**; the baseline is 2.05× higher on tested_absent here than on the two nights I read, a night-to-night difference and not a band effect (stated) |
| B-AB | arm-B cycles with `abandoned > 0` OR `resabandoned > 0` ≤ arm-A cycles with `abandoned > 0` | Amendment 3 (A3.1); data on file: 0 fallback abandons in #272's arms and in both CQ-AP arms |
| B-LATE | arm-B cycles with the L1′ round abandoned ≤ arm-A's + 5 | **+5: the Architect's choice (1 % of 500), stated as a choice, not derived**; data on file 0 of 940 and 0 in both CQ-AP arms |
| verdict | VOID iff a validity row fails; else ACCEPT iff N-GO, U-OK, B-AB, B-LATE; FAIL iff N-STOP or U-FAIL; else OPEN | A1.2 |

Scoring: the night's WSJT-X lines through `gg_lib.match` (±`CORROB_HZ`, exact text), the frozen U′ instrument, a cycle bootstrap **B = 2000, seed 20261112**, paired (the same cycle indices for both arms), as `crc_analyse.py` at `87c5486a`. ΔU′_ta = B's new-text (absent from A's rows of that cycle), not-corroborated outputs in **batches 4 and 5**, classified `tested_absent`, per cycle with WSJT-X lines.

**Descriptive lines (no verdict):** `resNew`, `resNewGated`, `resNewKept` totals; `resAbandoned` total and cycle count and the `resRun` counts (A3.1); `resWallMs` median and max; latest-batch p95 of A and B against 13 s; B-only rows by batch (4 vs 5); A-only batch-5 rows; the not-corroborated new-text split (tested_absent / tested_present / hashed). 🟡 **Not computable:** the spec's descriptive line "the gated-out rows' C / TA split" (§3): a gated-out row is dropped before publication, so no text of it exists in any output file. It would need an extra arm with the gate off (about 45 min, the Captain's word, and a size-rule amendment); QA does not propose it unless the Architect or the Captain asks.

## 6. Analysis code, self-test, dry run

| item | value |
|---|---|
| analysis | `qa/coh-res-cand-v2/crc2_analyse.py`, git blob **`c6e48546d09e478e72d9540ae006ecf4a8f5b4d5`** (`boff` and `main`; `main` refuses to run twice and refuses without a passing `boff_result.json`) |
| self-test | `qa/coh-res-cand-v2/crc2_selftest.py`, blob **`44618d4352c17f52c98e1dbebcc9bd4b976796a7`**: synthetic 40-cycle night (Q-prefix calls), every row, every verdict branch and the CI-bar boundaries, B-OFF field by field, the loader. **ALL PASSED; 15 mutations killed** (LATE_SLACK ±1, B-AB without `resAbandoned`, B-AB `<`, WIRE_SHARE 0.9, B-KEEP always passing, a validity failure reading OPEN, N-GO `>=`, U-OK `<`, B-DUP always passing, batch 5 inside B-KEEP, ΔU′ without batch 5, B-OFF without apKind, B-OFF without text, N_BOFF 39) |
| real-data smoke (plumbing only) | arm A as both arms: 500 cycles, 13,997 WSJT-X reference rows, the real matcher, bootstrap and instrument on 40 real rows. Not a result; B-WIRE fails there by design (arm A has no `res` columns) |
| arm driver | `qa/coh-res-cand-v2/crc2_arms.sh`, blob **`cc61e18c8168e29071a1e31bb09915da9a590139`**: arm B's command line is `cqap_arms.sh`'s arm A line **identical** except the build (`bin_v2`), the label, the output folder and `--cohrescand` (`--cq-ap 0` kept in both legs); preflight: DLL pin at start and end, readback tokens at start and end (`decodingDepth=Deep`, `nhard=24`, `osdSignFixRead=1`, `cohfb=True`, `cohms=True`, `cohaudio=Both`, `ungated=True`, `lateround=True`, `threadsResolved=8`, `kMinScorePass2=5`, `osdCorrThreshold=0.05`, `cqap=False`, `cohrescand=False\|True`), row count, orphan check |
| **dry run** (plumbing check) | `bash crc2_arms.sh dry`, 14:44:05Z to 14:44:22Z, 3 cycles OUTSIDE the selection of the old night `20260930_1930`, `--cohrescand 1`: rc 0, preflight ok (pin at start and end, all readback tokens), orphan check clean, **`wsjtx.exe` not running**. **Plumbing result only (not a gain, loss or timing):** the harness parsed v2's line tail, `coh.csv` carries `resrun, rescand, reselig, resnew, resnewgated, resnewkept, resabandoned, reswallms` with sane values, and the decoder logged `resRun=ran, resCand=residual-R3`. The live window was not read. Outputs in `_qa-scratch\coh-res-cand-v2\arms_dry` (scratch) |

## 7. The invocations (fixed)

```
bash qa/coh-res-cand-v2/crc2_arms.sh boff        # B-OFF: 40 cycles, --cohrescand 0, about 3.5 min; then:
python qa/coh-res-cand-v2/crc2_analyse.py boff   # reads B-OFF against arm A; writes boff_result.json; STOP here if not PASS (VOID, back to the Developer)
bash qa/coh-res-cand-v2/crc2_arms.sh armb        # arm B: 500 cycles, --cohrescand 1, about 42 to 46 min (refuses to start without a PASS boff_result.json); then, ONCE:
python qa/coh-res-cand-v2/crc2_analyse.py main
```
Each arm run detached (`nohup … & disown`), PC exclusive, station daemon stopped, WSJT-X closed or idle and recorded in `status.txt` (the Captain's word), one arm at a time. The Captain's go is needed for the PC time.

## 8. What this record does not contain

No arm output of any kind: `arms\` holds no `B_OFF` and no `B` folder, and no B-OFF or arm B file has been read. No number of this study's verdict has been computed (the descriptive U′0 above is arm A alone, as A1.3 required before arm B). The dry run and the smoke test are plumbing and are not citable as a gain, a loss, a timing or a false-decode rate.
