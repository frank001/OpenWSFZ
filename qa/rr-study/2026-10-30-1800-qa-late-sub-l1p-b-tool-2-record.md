# LATE-SUB L1′ B-TOOL-2: record (QA, 2026-10-30T17:59:47Z `date -u`)

**To:** Architect · **Answers:** ruling `73dc9036` §4 (and §2, §5 owed items) · **Build under test:** Developer `b1d8a06e`, DLL SHA-256 `1ba8dc3d…` (pin OK at start and end) · **Instrument:** Replay81 commit `cfdf724c` (`qa/refset`, local).

## 1. Owed items from the ruling, done

- `lr_analyse.py` (commit `341e7373`): the row's predicate is now the §3 count (abandoned counts ON = OFF: residual pass, third pass proper, fallback), the strict paired comparison is reported beside it, lines are paired by log order `R T F T C`, DT is compared after rounding. Re-run on the existing `raw_lr`: **B-OFF, B-EQ-1, B-EQ-2, B-AB all PASS; ALL_PASS true.**
- **Numbers against your table:** cycles compared 1,200 (after dropping the warm-up cycle, 1 per arm); third pass lines OFF 1,200, ON 2,377; rounds 1,177 (1,168 ran, 9 skipped-no-new); 23 cycles with one line; 0 with none; abandoned or failed 0 in every pass in both arms including the round's inner line; strict third-pass-proper comparison 0 of 1,200 differ. **All equal to your table.**
- **DT after rounding:** 0 of 432 mismatch (SNR equal 432/432). The raw-DT count 260 is printed beside it.
- **Timing from data on file:** inner round `elapsedMs` median 696, p90 848, max 1,194 ms (1,177 rounds); whole-cycle `elapsed_ms` ON median 3,939, max 5,927; OFF median 3,195, max 4,943; `tb5_ms` 4,301 / 5,748 (353 cycles). Equal to your §3.
- Ledger Q30 and Q31 written in the same edit (error ledger now 31 rows).

## 2. B-TOOL-2 run

Cycles 1–60 of the frozen selection (`selection60.json`, its first 60 stamps), OFF then ON, one process per arm, 17:52:37Z–17:59:19Z. Chain log `_qa-scratch\late-sub\chain_t2.out`; analysis `t2_analyse.py` → `t2_result.json`. Replay81 changes: `ThirdProbe` keeps the first line; `LateProbe` and `late.csv` (every R6 field, a per-cycle line count and an unmatched count); the logger writes the R6 line. Self-test `--selftest-batch3 true` (HasInternals build): **20 of 20 PASS** (my commit message for `cfdf724c` says 19; 20 is the count).

| Row | Result |
|---|---|
| **T2-1** `third.csv` non-ms ON vs OFF | **PASS**: 0 of 60 differ |
| **T2-2** exactly one R6 line per ON cycle, all matching; OFF none | **PASS**: 60 of 60; unmatched 0; an independent regex pass over `log.log` also 60 of 60; OFF 0 lines |
| **T2-3** `published` = `b5_n` | **PASS**: 60 of 60 |
| **T2-4** cycle 55 carries a `skipped-…` outcome, no round started | **FAIL AS WRITTEN** (see §3) |
| **T2-5** `nc_dump` and `run.csv` content columns = §3's arms on 1–60 | **PASS**: `run.csv` 0 differ; `nc_dump` OFF 0 of 60 differ (1,624 rows both), ON 0 of 60 differ (1,643 rows both) |

**Note, 2026-10-30 (after the Architect's ruling `2026-10-30-1802-architect-late-sub-l1p-t2-4-ruling.md` on `arch/late-sub`):** T2-4 was changed by the Architect (his predicate named the wrong word, ledger E123) and the corrected row **PASSES** from `t2_analyse.py` on the existing `raw_t2`: cycle 55 shows `no-new`, fit 0, new 0, published 0, `elapsedMs` 0, `startMs` = `endMs` = `fbEndMs`, `batch5PublishMs` -1, no inner `Third pass:` line (checked in `raw_t2`'s own ON log and in the §3 ON arm); fit 0 occurs in exactly 1 of 60 rows. The corrected predicate was written after the data was seen. **The "FAIL AS WRITTEN" above stays; it was the original predicate's result.** `ALL_PASS` true from the tool.

**R6 against the inner line, rows with fit > 0 (ruling §5.3), cycles 1–60:** 59 rows; every one has exactly one inner line. R6 `elapsedMs` median / p90 / max 586 / 694 / 817 ms; inner 586 / 693 / 817 ms; R6 minus inner 0 / 0 / +1 ms (min / median / max), equal on 31 of 59 rows. So the PC's 696 / 848 / 1,194 ms (inner line) and §4's R6 figures are the same quantity to within 1 ms.

T2-2 passing means R6's line exists and has the specified shape: **no product defect against R6.**

## 3. T2-4, and why I did not relabel it

Cycle 55 (stamp `260925_202530`): R6 line `outcome=no-new, buffer=R3, fit=0, refused=0, new=0, published=0, fbEndMs=2542, startMs=2542, elapsedMs=0, endMs=2542, batch=5, batch5PublishMs=-1`. No round started (no native pass: `elapsedMs` 0, start = end = fbEndMs, no inner `Third pass:` line), but the outcome word is **`no-new`, not `skipped-…`**.

- **Reason:** the round's fit list is empty (`fit=0`). In `Ft8Decoder.cs` the round calls `RunThirdPassAsync` only when `fit.Length > 0`; otherwise `late` is null and the outcome is `LateOutcomeNoNew`. `skipped-…` is reserved for the four gate skips (`normal-depth`, `fallback-not-run`, `nothing-decoded`, `no-residual`).
- **This agrees with R6 as written** (build spec line 51 lists `no-new` among the outcomes). The ruling's T2-4 predicate expected the wrong word for this path; the substance it asked for (the skip path is exercised, and the line says why) holds.
- **QA's own segmentation cross-check:** cycles with no inner `Third pass:` line in the §3 ON arm are 55, 94, 164, 190 (first four), so cycle 55 is the first, as you said. ON outcomes over 1–60: 59 `ran`, 1 `no-new`.
- **Asked:** accept T2-4 on its substance (outcome `no-new`, fit 0, no round started), or tell me to change it. No instrument change is needed either way.

## 4. Ruling §6 (the 5 rows), cycles 1–60

Inner `new` total 19, `published` total 19, no cycle differs. **None of the 5 rows (437 vs 432 over 1,200 cycles) falls in cycles 1–60**, so the question stays untraced; I will not trace it unless asked.

## 5. §4 and the parsers

§4 on sol is planned on the fixed Replay81 (`third.csv` first-line, `late.csv`). The §4 scripts are not written yet; none of the existing late-sub chain scripts references `f2_station_count.py`, `sweep_f2_record.py` or `third_pass_counters.py` (grep), and the §4 scripts will not.

## 6. State

Nothing pushed. sol not touched. The §4 freeze commit should name Replay81 commit `cfdf724c` once you accept T2-4.
