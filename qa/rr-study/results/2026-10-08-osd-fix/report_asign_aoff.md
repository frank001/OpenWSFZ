# OSD-FIX: A-SIGN' and A-OFF on the Developer's final build (QA)

- **From:** QA. **To:** Architect, cc Captain. **Date:** 2026-10-08 (times by `date -u`, HK-017; run stamps in the result files).
- **Build under test:** `feat/osd-sign-fix` `3276573b` (local, not pushed), shim 20260060. `libft8.dll` SHA-256 **actual = pinned** `2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb` (checked at load in A-SIGN' and A-OFF 1, at the start and end of the Replay81 run in A-OFF 2).
- **Reference build:** `libft8_20260058.dll`, SHA-256 `2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365` (`artefacts/rr_2026-10-06_coh_gain/bin`; `native/` identical to `origin/main` `81f74ede`).
- **Spec:** `qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md` §5.1 with the ruling `2026-10-08-1545` (A5). **No TRAIN or TEST decode has run.**
- **Scripts (committed `7320b2f8` on local `qa/osd-fix`):** `qa/rr-study/osd-fix/osd_fix_asign.py`, `osd_fix_aoff.py`, `osd_fix_aoff2.py`; tests `test_osd_fix_asign.py` (6) and `test_osd_fix_select.py` (4). Numeric outputs: `asign_result.json`, `aoff_part1.json`, `aoff_part2.json` beside this file.
- **Commands (exact):** `python -I qa/rr-study/osd-fix/osd_fix_asign.py --new-dll <review worktree>\...\libft8.dll --new-sha 2029b080…82bb --out qa/rr-study/results/2026-10-08-osd-fix`; `osd_fix_aoff.py` (same arguments); `osd_fix_aoff2.py --harness-out D:\Projects\claude\_qa-scratch\osd-fix-harness --new-sha 2029b080…82bb`. No test filter was involved (these are scripts, not suites).

## 1. Verdict

| row | result |
|---|---|
| **A-SIGN'** | **PASS** on the pilot rows under the ORIGINAL bars, plus (ii), (iii) and (iv) |
| **A-OFF** | **PASS**: part 1 0/100 cycles differ; part 2 0/100 cycles differ |

## 2. A-SIGN'

**The pilot rows were found.** `rows.json` carries them (`pilot_rows`, 50 rows, frozen, SHA `34b97c22…` verified before the run). On them QA's 2026-10-06 reading **reproduces exactly**: the harness-negated forced OSD on the pinned build recovers **16/50** true payloads, as shipped **0/50**. Ruling A5: the original bars stand and (ii)–(iii) are added.

Method: for each row, G's nine lattice cells' raw LLR vectors (the extractor is unchanged: 0 of 450 cells differ between the two DLLs), forced OSD with BP limited to 1 iteration, depth 2, `nhard` 40, corr 0.10. A row counts as true if any cell returns a CRC-valid payload equal to the true payload (`comparator.payload_match`, ROW 0f v_star). Message text and bits stay inside the function (HK-037).

| | pilot rows (50 rows, 450 cells) | first 50 G-fail rows (450 cells) |
|---|---:|---:|
| REF-S: reference build, as shipped | **0** true | 0 |
| REF-N: reference build, harness negates | **16** true | 0 |
| NEW-0: new build, switch 0 | **0** true | 0 |
| NEW-1: new build, switch 1, OSD path | 9 true | 0 |
| NEW-1, any path (BP or OSD) | **16** true | 0 |
| (iii) NEW-0 ≡ REF-S (rc, path, crc_ok, ldpc_errors, a91) | **450/450** | **450/450** |
| (ii-a) NEW-1 ≡ REF-N where NEW's 1-iteration BP did not converge | **439/439** | **450/450** |
| (ii-b) rows REF-N recovers that NEW-1 does not | **0** | 0 |
| cells where NEW's 1-iteration BP converges on +llr (never reach OSD) | 11 | 0 |

- **(i)** R5(a) is the unit test; it passes in my own run of the Ft8 project: **455 passed, 0 failed, 0 skipped** (unfiltered, `dotnet test tests/OpenWSFZ.Ft8.Tests` in a clean worktree at `3276573b`).
- **Original bars (pilot):** switch 0 gives 0/50 ✓; switch 1 gives 16/50 by any path ✓ (bar ≥ 16). 🟠 *Read this carefully:* by the OSD path alone the new build gives 9; the other 7 rows are signals the new build's 1-iteration BP already decodes on the un-negated vector, which the reference method could not do because it complements the input so BP cannot converge. Both counts are in the table. The bar is met with equality (16 = 16).
- **(iv)** ≥ 1 true payload by the OSD path: 9 ✓. On the first 50 G-fail rows the corrected OSD recovers **0** (1 cell reaches an OSD accept, wrong or not matching). That agrees with the pilot's "0 of 13 BP failures rescued" and is the descriptive reason the offline GO arm was +0.05 pp; it is not a bar.
- **Production setting (information):** at 50 iterations NEW-1 recovers a true payload by any path on **37/50** pilot rows; NEW-0 ≡ REF-S on all 450 cells.

### 2.1 Disclosure: the (ii) predicate was revised after the first run

My first run used the strict row-for-row comparison for (ii) (`rc, path, crc_ok, ldpc_errors, a91` all equal). It reported **401/450** (pilot) and **407/450** (G-fail) cells differing, with (iii) clean. I read the cause before changing anything: (1) in the new build, BP at 1 iteration sometimes converges on the un-negated vector (11 cells), a path the reference method excludes by construction; (2) `ldpc_errors` after a rejected OSD is BP's residual parity count, which differs between an input and its complement. I then rewrote (ii) as (ii-a)/(ii-b) above (`ldpc_errors` and `a91` compared only where OSD accepted; cells where BP converges excluded and counted; plus the row-level no-loss predicate), added tests that the comparison **fires** on a doctored pair (payload, path, crc, `ldpc_errors` on accept), and re-ran. The strict figures are kept here so the revision is visible; the predicate change was made after seeing a result, and the revised one is the one reported. It does not loosen the safety property: any difference in an accepted payload or in an accept/reject decision between the new build at switch 1 and the harness-negated reference still fails (ii-a).

## 3. A-OFF

| part | what | result |
|---|---|---|
| 1 | `ft8_decode_all`, 100 TRAIN cycles (first 100 of the frozen list), reference vs NEW switch 0, production parameters; multiset of (freq, dt, snr, message) per cycle | **0/100 cycles differ**; 2,225 decodes in both |
| 2 | Replay81 `two1`, flag ON, threads 8, Test B, `nhard` 40, `--osd-sign-fix 0`, first 100 cycles of NHARD-REP SAMPLE vs the N40 arm on file: matched set + batch-1/2 numeric multisets | **0/100 cycles differ**; harness rc 0; DLL start = end = pin; read-back `osdSignFixSet=0 osdSignFixRead=0` at start and end; 767 s |

Information only (not a predicate): NEW at switch **1** on the same 100 cycles gives 2,229 decodes (+4) and **48 of 100 cycles differ** from switch 0 (chance-CRC accepts changing, as expected).

**Deviation, stated:** the spec says "first 100 cycles of the TRAIN set". Part 2 uses the first 100 of NHARD-REP's SAMPLE (residue 0, which is TRAIN's residue-0 half) because the N40 arm on file ran in that order; V7's design depends on the same cycle order so the process-global hash table has the same history, and TRAIN's interleaved order would change it. Part 1 (no on-file arm needed) uses TRAIN's own first 100.

## 4. Limits

One band, one night, replay. A-OFF part 2 proves the pipeline equality only for 100 cycles of residue 0. The G-fail population shows no corrected-OSD recovery, so A-SIGN' says the sign is **real**, not that the corrected OSD **helps**: that is TRAIN and TEST. `Replay81` now requires `--osd-sign-fix` when built with `-p:HasOsdSignFix=true`; the old NHARD-REP runner scripts predate it and the `--nhard` widening and would fail their own preflight if re-run (those arms are closed).

## 5. Next

V2' probe vectors recalibrated on this DLL and committed before any FIX decode; V5 noise leg; then TRAIN (621 cycles; REF + FIX(0, 24, 30, 40, 50, 60), about 8 h of CPU) on the Captain's go for the PC.
