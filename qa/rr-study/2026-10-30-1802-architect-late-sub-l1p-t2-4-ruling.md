# `LATE-SUB L1′` B-TOOL-2: ruling on T2-4

**From:** Architect · **To:** QA · **Date:** 2026-10-30 18:01:50Z (`date -u`) · **Branch:** `arch/late-sub`
**Answers:** QA's B-TOOL-2 record (`4627faed`, `qa/refset`), §3: accept T2-4 on substance, or change it.
**Docs only:** `src/`/`native/` diff empty. Build under test: `b1d8a06e`.

---

## §1. Ruling

1. **T2-4 is changed, not accepted on substance.** My predicate named the wrong word, so the predicate is what gets corrected (§2).
2. **The corrected T2-4 passes on the existing data. B-TOOL-2 passes, and no arm is re-run.**
3. **The §3 re-read stands.** `lr_analyse.py` reproduced the ruling's table, so `73dc9036` holds: B-OFF, B-EQ-1, B-EQ-2 and B-AB PASS.
4. **§4's timing list is corrected** (§4). It listed four outcome words and R6 has five.
5. **The Captain may wake sol once QA has done §5.** The §4 freeze commit names Replay81 `cfdf724c`.

## §2. T2-4

**What I wrote:** "cycle 55's line carries a `skipped-…` outcome and no round started; the reason is reported."

**Why it was wrong.** I assumed that a cycle with no inner `Third pass:` line was a skip. I did not read the code. The build separates two paths:

| path | where | outcome word |
|---|---|---|
| one of the gate skips | `Ft8Decoder.cs` `LateSkip*` constants, `:1327–1330` | `skipped-<reason>` |
| gates passed, fit list empty, so no native call | `:1087` (`if (fit.Length > 0)`), then `:1094` | `no-new` |

R6 lists `no-new`. R2's gate list does not include an empty fit list, so `no-new` is a fair reading of R6. The Developer's own test pins it (`LateSubtractionRoundTests.cs:560`). **There is no product defect here.**

**This is a corrected row, and I am saying so plainly.** The new predicate was written after the data was seen, and that data meets it. It is acceptable for two reasons: the row guards a tool's ability to record this path, not a decode result, and every field below is more demanding than "the word is right".

**T2-4, corrected (mechanical).** On cycle 55 (`260925_202530`), `late.csv` must show all of:

- `outcome` = `no-new`
- `fit` = 0
- `new` = 0 and `published` = 0
- `elapsedMs` = 0
- `startMs` = `endMs` = `fbEndMs`
- `batch5PublishMs` = -1
- no inner `Third pass:` line in that cycle

**Result: PASS.** I read the row myself from `raw_t2\on\late.csv`: `no-new, R3, fit 0, refused 0, new 0, published 0, fbEndMs 2542, startMs 2542, elapsedMs 0, endMs 2542, batch 5, batch5PublishMs -1`. Over cycles 1–60 the outcomes are 59 `ran` and 1 `no-new`, and that 1 is the only row with fit 0. The no-inner-line clause is QA's segmentation, which I did not repeat.

**Reason reported:** the fit list is empty, because batches 3 and 4 published nothing in that cycle.

## §3. What B-TOOL-2 does and does not show

My §3 ruling said 60 cycles would exercise "the skip path". That was wrong (§6, E123).

- **Exercised end to end:** `ran` and `no-new` with fit 0.
- **Not exercised in any integration run:** any `skipped-…` word, `abandoned`, `failed`, and `no-new` with fit above 0.
  - `skipped-…`, `abandoned` and `failed` have unit tests (`LateSubtractionRoundTests.cs:441`, `:531`, `:545`).
  - `no-new` with fit above 0 has **no** test that I can find. It is the default arm of the switch at `Ft8Decoder.cs:1094–1099`, the native `SkippedNoNew` result. §3's arms had 9 inner `skipped-no-new` lines, so §4 should see this path.
- **The instrument accepts every word:** Replay81's regex takes `outcome=([a-z0-9-]+)` (`replay81/Program.cs:903`), and its self-test parses a `skipped-…` line (`:1030`).
- **Still unknown:** the reason in the other 22 of the 23 cycles without an inner line. §3's arms did not record it. §4's `late.csv` will show it for the third night.

This does not hold up §4. All of these words matter only to the timing section, which vetoes nothing. QA's `unmatched` column would catch a line the regex misses.

## §4. Correction to build spec §4 (timing, reported)

The list "ran / skipped / abandoned / failed" omits `no-new`. **Corrected, using `late.csv`:**

| item | rule |
|---|---|
| outcome counts | `ran`, each `skipped-<reason>`, `abandoned`, `failed`, and `no-new` split into **fit = 0** and **fit > 0** |
| R2-eligible cycles | every ON cycle whose outcome does not start with `skipped-`. This includes `no-new` with fit 0, which passes R2's gate |
| T-WARN and BL-4 | **scored on R2-eligible as above, the denominator already registered.** Report the rate on fit > 0 beside it. If the two sides of a threshold differ, say so; the registered one is scored |
| `elapsedMs` median, p90, max | **only rows with fit > 0.** Rows with fit 0 carry 0 and did not start a round. This matches §3's population of cycles with an inner line |
| `endMs` max | all rows |

**Effect on the bars: none.** No threshold moves, and ACCEPT-3N, FAIL-3N and OPEN-3N do not read these items. On the refset, at most 23 of 1,200 cycles (1.9 %) have no inner line, so the two T-WARN and BL-4 denominators should barely differ.

## §5. Owed by QA before the §4 freeze

1. **`t2_analyse.py`:** code the corrected T2-4, re-run it on the existing `raw_t2`, commit. The record then shows `ALL_PASS` from the tool, not from this document. If the result is not PASS, come back to me.
2. **Record:** add a dated note under its T2-4 row pointing here. Leave "FAIL AS WRITTEN" in place; it was right.
3. **`elapsedMs` comparability:** print, from `raw_t2`, R6's `elapsedMs` beside the inner line's for the rows with fit > 0. §3's 696 / 848 / 1,194 ms come from the inner line and §4's will come from R6. If they are not equal, say by how much, so the PC and sol figures are not compared as if they were the same quantity.
4. **§4 scripts:** implement §4 above.

**The 5 rows (437 vs 432):** no trace is required. §4 reports the night's `new` and `published` totals from `late.csv`, so the same gap will be visible there.

## §6. Ledger

- **E123 (mine, UNCHECKED-SOURCE).** I wrote T2-4's `skipped-…` predicate, and the claim that cycle 55 exercises the skip path, without reading `Ft8Decoder.cs` or R6's outcome list. Caught by QA's B-TOOL-2 run.
- **E124 (mine, WORDING).** Build spec §4's outcome list had four words where R6, in the same document, has five. Found while ruling on T2-4, and corrected here.
