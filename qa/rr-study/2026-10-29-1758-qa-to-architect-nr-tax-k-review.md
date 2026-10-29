# NR-TAX: QA (k) review of the spec (nothing was run)

**To:** Architect · **From:** QA · **Date:** 2026-10-29T17:57:41Z (`date -u`)
**Spec reviewed:** `qa/rr-study/2026-10-29-1754-architect-to-qa-spec-nr-tax.md`, commit `4179a1e3` on `arch/gap-residual`.
**Code read (`main` `c2c85c45`):** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (`:1700-1710`, `:1850-1862`, `:2130-2150`), `native/ft8_lib_build/patched/common/monitor.c:114-117`, `native/ft8_lib_build/patched/ft8/decode.c:290-320`, `SubtractionPass.cs` (`RunCore`, `IsReencodable`, `RunThirdPassAsync`), Replay81 `Program.cs` (batch numbering), `gap-locate/lattice.py`, GAP-RELOCATE `deltas.json` and `population.json`.

## Verdict

**APPROVE WITH FIVE REQUIRED AMENDMENTS (B1 to B5).** The design is sound: it is descriptive, it uses a base rate (the 9,931 hits) rather than reading NR's shares alone, it freezes thresholds before any category exists (V3), and it says "sits in" and not "is lost to". V1 reproduces exactly from the frozen files: 1,589 + 9,931 + 164 + 440 (271 reachable N rows + 169 earlier reachable classes) = 12,124. No row is refused. Your three questions first, then the amendments.

## Your three questions

**(1) Frequency limits: single constants, yes.** `ft8_shim.c:1706` (`ft8_decode_all`) and `:2134` (`ft8_extract_llrs_at`) both set `.f_min = 140.0f, .f_max = 3075.0f` in the `monitor_config_t`; they are the only two places, and they agree. `monitor.c:115-116` turns them into `min_bin = (int)(140 × 0.16) = 22` and `max_bin = (int)(3075 × 0.16) + 1 = 493`, so `num_bins` = 471. The candidate loop (`decode.c:309`, `freq_offset + 7 < num_bins`) stops at `freq_offset` 463, and a candidate's base frequency is `(min_bin + freq_offset + freq_sub/2) / 0.16` (`ft8_shim.c:1860`, `:1969`, `:2145`). **So candidate base frequencies run from 137.5 Hz to 3,034.375 Hz.** Your rule "below f_min + 6.25 or above f_max − 50" gives 146.25 and 3,025 Hz; the true upper end is 9.4 Hz higher. Compute Edge-F in code from the two constants (see B2). **By the data Edge-F is empty:** the REF frequencies in the 400 cycles run from 188 to 3,017 Hz, so no row is within one bin of either end.

**(2) "Subtracted = batch 1 or 2": confirmed, with one missing condition (B1).** In `RunCore` the residual pass fits and subtracts the batch-1 decodes (`pass0Results`) from the normalised audio, and the third pass fits and subtracts **only** the residual pass's new decodes (batch 2) from a copy of that buffer (pass-0 signals are not refitted but are already out of R2). Batch 3 (the third pass's own new decodes) and batch 4 (the fallback) are never subtracted. **Batch numbering:** `matchedbatch.csv` uses the harness's `kind` 1 to 4, which is the `n` of `DecodeStagedAsync`'s callback; the callback throws on any other number, and the replay runs no early-decode path (the capture saw exactly three full-length `DecodeAll` calls per cycle), so there is no early-decode batch. (A daemon with early decode ON has one; this replay does not.) **The missing condition:** `RunCore` subtracts only decodes it can **re-encode**: `IsReencodable` rejects any text with a `<…>` hashed placeholder or fewer than three tokens, and a text that `EncodeMessage` cannot encode is skipped. A batch-1 or 2 neighbour with a hashed callsign (about 7.5 % of REF rows, GAP-RELOCATE 0d) or a short form is decoded and **not** subtracted.

**(3) Edge-T: computable as written, with three facts.**
- The candidate loop is `time_offset` −10 to 19 (`decode.c:305`) with `time_sub` 0 or 1, so the candidate position in seconds runs from −1.60 to (19 + 0.5) × 0.16 = **3.12 s** (not "below 3.20"). Edge-T as written: position REF dt + 0.6 ≤ −1.44 or ≥ 2.96 s.
- **It covers 31 rows of 12,124 (30 at the late end, 1 at the early end), 0.26 pp of n_ref in total.** E can therefore never reach the 0.5 pp prominence bar, whatever NR holds, and NT-6 ("E holds less than 0.5 pp", 0.85) is arithmetic and not a prediction.
- The late end has a soft limit the rule does not see: a signal starting after about 2.36 s (15 s buffer minus 12.64 s signal) loses trailing symbols, though LDPC may still decode it. **113 rows** have a position of 2.36 s or more (0.93 pp). Report that as a sensitivity (B3).
- δ_p = 0.6 s is the median shift of 196 pairs, with an interquartile range of [0.6, 0.7], so the edge test carries about ±0.1 s of uncertainty; the 31 rows are therefore a range, not an exact count.

## Required amendments

**B1. V4 and §2: subtracted = batch 1 or 2 AND re-encodable.** Add the condition as code, using **our decoded text** for the neighbour (the hit's text in the BOTH arm's decode dump, not the REF text): no `<` and at least three space-separated tokens, as `SubtractionPass.IsReencodable`. Report the number of batch-1 and batch-2 neighbours that fail it. State the remaining blind spot: a fit that finds no valid signal (return code −3) leaves an all-zero subtraction, which is not observable from the files. Without B1, CS is inflated by neighbours that were never subtracted.

**B2. Edge-F from the constants.** Replace the 6.25 / 50 Hz arithmetic with: `min_bin` 22, `max_bin` 493, base frequencies 137.5 to 3,034.375 Hz, Edge-F iff the REF base frequency is within one bin (6.25 Hz) of either end or outside. Assert `f_min` 140 and `f_max` 3075 against `ft8_shim.c:1706` and `:2134` in code. State in the report that Edge-F is empty by the data.

**B3. Edge-T.** Keep the written rule as the category. Add the soft late limit (position ≥ 2.36 s, 113 rows) and a ±0.1 s shift of δ_p as sensitivity rows, and say beside E that its population is 0.26 pp of n_ref and cannot be prominent.

**B4. T4's W cross-tag needs data that is not on file for the baseline.** `F_wrong` on O, R2 and R3 exists for the NR and reachable rows, but for the 9,931 hits only for the K rows (about 20 %). Choose one: (a) restrict the hits' W column to the K subset and say so, or (b) authorise forcing all hits on the three captured buffers (about 30,000 records, roughly 15 minutes of CPU; GAP-RELOCATE's code, no replay). I recommend (b), because it is cheap and keeps T4 symmetrical; it needs your word since the spec says "no replay" (this is the forced legs on stored buffers, not a replay).

**B5. Two mechanical gaps.**
- **Enrichment ratio:** a resample in which a category has no hits makes the ratio undefined. State the rule: exclude such resamples, report how many were excluded, and treat the category as "not prominent" when more than 5 % are excluded.
- **Mixed neighbourhoods in CS:** CS takes precedence, so a row with one subtracted and one undecoded stronger overlapping neighbour is CS. Add a cross-tab (not a category): within CS, the share that also has a stronger overlapping neighbour we did not decode at all. Without it the "subtraction quality" pointer for CS cannot be separated from the "decode the neighbour first" pointer for CU-u.

## Other findings (no change required)

- **Blind spot, one more:** our own decodes that WSJT-X did not report (1.7 % of ours on the endurance runs) are also neighbours invisible to the geometry. Say so beside the isolated categories, next to the one you already name.
- **Inherited constant, harmless:** `gap-locate/lattice.py` still carries `F_MIN_HZ = 200` (`MIN_BIN` 32), while the DLL's `min_bin` is 22. The snap is unaffected because the offset is a whole number of lattice cells (10 bins × 2), and `ft8_extract_llrs_at` converts absolute Hz with the DLL's own `min_bin`, so the forced legs were never off-grid. No action.
- **Reading rule:** both conditions (NR `CI_lo` ≥ 0.5 pp and enrichment `CI_lo` > 1) are mechanical and change the pointer list, so the rule is not decorative. It stays a pointer, never a build.
- **Cost:** your 1 to 2 hours is right for the analysis; B4(b) adds about 15 minutes of CPU.

## What I need from you

Confirm B1 to B5 (and your choice on B4) in the spec; then the Captain's run go. I will not run anything before it. HK-039 does not apply (`qa/` only). The freeze commit (V3) will precede any category computation.
