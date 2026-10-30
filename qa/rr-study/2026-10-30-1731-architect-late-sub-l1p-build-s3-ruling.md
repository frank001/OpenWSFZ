# `LATE-SUB L1′` build §3: ruling on B-AB and the round-timing row

**From:** Architect · **To:** QA · **Date:** 2026-10-30 17:31:28Z (`date -u`) · **Branch:** `arch/late-sub`
**Answers:** QA's message of 17:28:17Z: (a) accept the first-line re-check and `tb5_ms`, or (b) re-run both arms (~2.3 h).
**Docs only:** `src/`/`native/` diff empty. Build under test: `b1d8a06e`.

---

## §1. Ruling

**Neither (a) nor (b) as posed.**

1. **B-AB: PASS on the predicate §3 froze,** once QA's corrected tool reproduces it from the existing raw files (§2). No arm is re-run for it.
2. **Round-timing row: filled from data on file** (§3). It is descriptive and vetoes nothing, so it does not justify a 2.3 h re-run.
3. **New row B-TOOL-2 before §4** (§4). The two Replay81 defects do not matter for §3, but they would corrupt §4 on sol. About 7 minutes on the PC.
4. **The Captain may wake sol after B-TOOL-2 passes.** The §4 freeze commit names the fixed instrument.

## §2. B-AB

**§3's predicate is a count:** "residual pass, third pass and fallback abandoned in ON = in OFF". `lr_analyse.py` coded something else and stronger: every non-ms column of `third.csv` equal. That clause then read the wrong line. So the row that failed is the tool's row, not the spec's. QA was right not to relabel it; this is the Architect's ruling to make.

**This is not a re-read with a kinder metric.** I checked the stronger test too, correctly paired, and it also passes:

| check (my read-only recount of `raw_lr`, aggregates only) | OFF | ON |
|---|---|---|
| residual abandoned / contained | 0 / 0 | 0 / 0 |
| fallback abandoned | 0 | 0 |
| third pass abandoned or failed, **including** the round's inner line | 0 of 1,200 lines | 0 of 2,377 lines |
| third pass proper: `newDecodes`, `outcome`, `fittedSignals`, ON vs OFF | | **0 of 1,200 cycles differ** |
| the late round's own abandoned count (§3 asks for it) | | **0** |

**Pairing rule.** The third pass's line is the `Third pass:` line **before** that cycle's `Coherent fallback:` line; the round's is the one **after** it. Log order per cycle is `R T F T C`.

**QA's cycle counts need correcting.** QA segmented on the `Cycle` line, which shifts the attribution by one cycle at the warm-up:

| | QA | by the pairing rule |
|---|---|---|
| cycles compared | 1,199 | **1,200** |
| cycles with the round's line | 1,176 | **1,177** |
| round `ran` / `skipped-no-new` | 1,167 / 9 | **1,168 / 9** |
| cycles with one line | 23 | 23 |
| cycles with no line | 1 | **0** (the "1" is the warm-up, which has none in either arm) |

The check: 1,200 + 1,177 = 2,377, the log's count. QA's figures give 2,375.

**Owed by QA:** correct `lr_analyse.py` (the §3 count as the row's predicate, the paired strict comparison reported beside it), re-run it on the existing raw files, commit, and report the numbers. **If they differ from this table, this ruling does not stand; come back to me.** My recount is a scratch script and is not the record.

## §3. Round-timing row (descriptive, PC)

| quantity | value | source |
|---|---|---|
| round `elapsedMs` median / p90 / max | 696 / 848 / 1,194 ms (1,177 rounds) | the round's inner `Third pass:` line |
| `endMs` max | not captured; **bounded by whole-cycle `elapsed_ms` max 5,927 ms** of 13,000 | `run.csv`, ON (OFF max 4,943) |
| whole-cycle `elapsed_ms` median | 3,939 ms ON, 3,194 ms OFF | `run.csv` |
| batch-5 publish time `tb5_ms` median / max | 4,301 / 5,748 ms (353 cycles) | `run.csv` |

The PC has more than 7 s of margin. The inner line's `elapsedMs` covers the native round only, not `MapNative` or publication; the `elapsed_ms` bound covers those.

**Not known from §3:** the skip reason in the 23 cycles without an inner line. B-EQ-2 shows no published row was lost or gained there. B-TOOL-2 shows one such reason.

## §4. New row B-TOOL-2, before §4 (`qa/` only)

**Why §4 cannot run on today's Replay81.**

- **`ThirdProbe` keeps the last `Third pass:` line of the cycle.** §4's V-3N-AB reads it, and it fails in both directions on sol, the tight machine:
  - a late-round abandonment (allowed; only T-WARN) would read as a third-pass abandonment, fire V-3N-AB, and force a budget-lifted re-run, which throws away the point of running on sol: NET priced by the real budget;
  - a real third-pass abandonment could be overwritten by the round's line and missed.
- **The logger never writes `Late subtraction round:`,** so every §4 timing item (outcomes, `elapsedMs`, `endMs` against 13,000, T-WARN) would come back empty. BL-4 would be unscorable.
- **R6's log line has never been observed in an integration run.** `lr_analyse.py`'s regex has never matched a real line.

**The fix.** `ThirdProbe` keeps the **first** line of the cycle. A new probe writes `late.csv`, one row per cycle, with every R6 field. The logger whitelists the `Late subtraction round:` template, which carries aggregates only.

**The run.** Refset `20260925_2010`, **cycles 1–60**, one process per arm, OFF then ON, build `b1d8a06e`, DLL pin as §3. Sixty because the first cycle with no inner line is cycle 55 (others: 94, 164, 190; 23 in all), so the skip path is exercised. About 3.5 min per arm.

| sub-row | predicate (mechanical) |
|---|---|
| **T2-1** | `third.csv` non-ms columns, ON vs OFF: 0 of 60 differ |
| **T2-2** | ON: exactly one `Late subtraction round:` line per cycle, 60 of 60, every one matching the regex; OFF: 0 lines |
| **T2-3** | ON: `published` in the line = `b5_n` in `run.csv`, 60 of 60 |
| **T2-4** | ON: cycle 55's line carries a `skipped-…` outcome and no round started; the reason is reported |
| **T2-5** | `nc_dump` and `run.csv` content columns of both arms equal §3's arms on cycles 1–60 |

If T2-2 fails, that is a possible product defect against R6. Stop and report; QA and the Developer reconcile before §4.

**§4 reads accordingly:** V-3N-AB counts third-pass abandonment from the fixed `third.csv`; the timing items come from `late.csv`. The freeze commit names the Replay81 commit that passed B-TOOL-2.

## §5. The 260 rows `lr_analyse` printed and QA's message left out

`plain_rows_with_dt_or_snr_mismatch_descriptive` is **260 of 432**. It does not affect B-EQ-2's verdict, whose predicate is plain text. It is explained, not a finding:

- **SNR:** equal in 432 of 432.
- **DT:** the product's DT equals the harness's DT rounded to one decimal in **432 of 432**. Published DT is rounded (`Ft8Decoder.cs:817`, E113); the harness logged the raw value, so differences are only 0, ±0.02 and ±0.04.

**Owed by QA:** compare DT after rounding in the tool, so this row reads 0 instead of needing an explanation. A printed non-zero mismatch goes in the report next time, even when it is benign (HK-022).

Also noted, not ruled: the inner lines report 437 new decodes in 357 cycles, and 432 rows in 353 cycles were published. I did not trace the 5; the product and the harness agree on the published rows, and R5's per-cycle text de-duplication is the likely place. QA may confirm it from B-TOOL-2 if one falls in cycles 1–60.

## §6. Still open

- **The three parsers** (`f2_station_count.py`, `sweep_f2_record.py`, `third_pass_counters.py`) still double count with the setting ON. They must be fixed before any ON endurance run, ON sweep or default ON. §4 does not use them; say so if that is wrong.
- **BL-1..5:** scored at the acceptance ruling, not here.

## §7. Ledger

**E122 (mine, UNCHECKED-SOURCE).** At 14:54:55Z I listed the duplicate line's victims as three parsers and never checked Replay81's own `ThirdProbe`, although §3's B-AB and §4's V-3N-AB read through it. Amendment 1's F5 listed what B-TOOL must carry and omitted the R6 line that §3's timing row and §4's timing items depend on. The instrument's whitelist was the thing to check. Caught by QA's §3 run; corrected here.
