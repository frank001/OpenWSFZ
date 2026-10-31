# `LATE-SUB L1′` build: acceptance ruling. ACCEPT-3N: +0.77 pp on the tight machine, with the budget's price included

**From:** Architect · **To:** the Captain, QA · **Date:** 2026-10-31 10:34:30Z (`date -u`) · **Branch:** `arch/late-sub`
**On:** QA's final rows (message of about 10:30Z); report `4a54145f`; freeze record `3275f843`, addendum 1 `20e111b4`, addendum 2 `7546ec8b`; analysis code `d50a98fe`; build spec §4 and §8 (Amendment 2). Build under test: Developer `b1d8a06e` (`dev/late-sub-round`, v0.68). This ruling is docs only; `git diff --stat origin/main -- src/ native/` is empty.

---

## §1. Verdict

**ACCEPT-3N, final.** Night `20260930_1930`, sol, 800 cycles, n_ref 27,064.

| reading | cycles | NET pp | bar: CI_lo ≥ 0.5 | ΔU′_ta per cycle | bar: CI_hi ≤ 0.021 | H-SHARE (bar ≤ 0.5) | verdict |
|---|---:|---|:---:|---|:---:|:---:|---|
| **R-ALL** | 800 | **+0.772 [0.655, 0.889]** | ✅ | 0.0050 [0.00125, 0.0100] | ✅ | 0 of 220 ✅ | ACCEPT-3N |
| **R-CLEAN** | 796 | **+0.771 [0.649, 0.893]** | ✅ | 0.0050 [0.00126, 0.0101] | ✅ | 0 of 220 ✅ | ACCEPT-3N |

V-3N-X PASS (X = 4, bar 8). V-3N-REF PASS (WSJT-X lines in 800 of 800 cycles). The two readings agree, so that is the verdict (Amendment 2).

**What I checked myself (HK-018, HK-022).** I ran `tn_analyse.py` as committed at `d50a98fe`, with its output redirected to my scratchpad and QA's result file untouched.
- The result is **identical to QA's final JSON**.
- The class-file SHA matches addendum 2 (`8046a4be…`), and the script asserts it.
- Addendum 2 was committed at 10:25:59Z and the final result is stamped 10:26:44Z, so the order holds.
- **The byte-identical result is expected, not suspicious.** The rows read only the testable set and the DT offset from the class file, and neither changed from 200 cycles to 800 (same four classes, offset −0.200 s, T 0.276).

## §2. HK-026: `other CQ` is settled as untestable

**Ruling:** the condition has been carried out and is closed. The one output stays `untestable_class`, it is disclosed, and it does not hold the verdict.

**The flag stays true in the file, and it should not be read as an open item.** `HK026_untestable_class_outputs_need_refreeze` tests whether an output is in that class. It does not test whether the re-freeze has been done, so no re-freeze can clear it for a class the instrument cannot see. §4 asks for three things, and all three happened: the other 600 cycles, a re-freeze from all 800, and only then the final U rows. The frozen code and result file stay as they are, and this ruling is what reads them.

**More cycles would not make the class testable.** `other CQ` is 13 of 50 present (26 %), Wilson [0.159, 0.396], and the testable bar is 0.80. Its upper limit is about half the bar, on a sample already at the 50-row cap, drawn from 262 confirmed rows.

**Both branches give the same verdict** (HK-025; my run, from the same code):

| the one output counted as | R-ALL ΔU′_ta | R-ALL CI_hi | R-CLEAN CI_hi | U-OK | verdict |
|---|---:|---:|---:|:---:|---|
| not absent (as registered) | 0.00500 | 0.0100 | 0.0101 | ✅ | ACCEPT-3N |
| tested-absent | 0.00625 | 0.0125 | 0.0126 | ✅ | ACCEPT-3N |

**A correction to QA's message.** It says "at most about 0.0063 added to the 0.005". The 0.0063 is the **total**; the addition is 0.00125. The conclusion is unchanged, and the true figure is smaller than the wording implied.

**What remains blind.** The U′ instrument says nothing about `other CQ`. That class is 262 of 19,797 confirmed Original-arm rows (1.3 %), and 1 of this round's 220 outputs (0.5 %). The class is rare, and this round's outputs are not concentrated in it. HK-026 is not answered by that comparison, because no instrument has measured the class. It stays a named blind spot.

**A gap in my spec (ledger E128).** §4 did not say what happens if an output is still untestable after the re-freeze. **From now on the HK-026 condition carries this branch:** after the full re-freeze, report the remaining outputs under both counts. The same verdict under both is that verdict; a different verdict is OPEN. I wrote that after seeing this data, so it is disclosed as such; here both counts agree, so it decides nothing.

## §3. Timing on sol (vetoes nothing; NET already pays for it)

| quantity | value |
|---|---|
| late round abandoned, cycles with fit > 0 | **228 of 784 (29.1 %)**: T-WARN fires |
| `elapsedMs`, fit > 0: median / p90 / max | 1,578 / 2,086 / 2,676 ms |
| `endMs` max | 12,946 ms (54 ms inside 13,000) |
| fallback end max, OFF / ON | 12,892 / 12,917 ms |

- **The time guard worked:** no round ran past the budget, and an abandoned round published nothing.
- **Reading T-WARN:** on sol, 29 % of rounds were thrown away and the NET still cleared the bar. That is the worst case this night was chosen to price.
- **On the PC** the round was abandoned in **0 of 1,177** rounds on the refset, with the whole cycle finishing by 5.9 s. That is a different night, so I am not predicting a PC figure for this one.

**Original arm (reported; not in X):** over all 800 cycles, fallback abandoned 0, residual pass 0, third pass abandoned or failed 1 (in the 600-cycle part). QA's report gave the first 200 only.

## §4. Three nights

| night | machine | role | NET pp | ΔU′_ta |
|---|---|---|---|---:|
| `20260925_2010` (refset TEST) | PC | descriptive | +1.140 [1.009, 1.278] | not a verdict row |
| `20261022_1949` | PC | L1′ verdict (harness) | +0.742 [0.621, 0.859] | 0.0063 |
| `20260930_1930` | sol | **acceptance (the build)** | **+0.772 [0.655, 0.889]** | 0.0050 |

The two fresh nights agree. The refset again overstates the lever by about a third.

**In plain terms:** of the 220 decodes the round added, 205 (93.2 %) were also decoded by WSJT-X. Four were tested and found absent from the audio, which is about one every 50 minutes of decoding (800 cycles ≈ 3.3 h). Ten were tested present, and one could not be tested.

**About 0.015 pp of the NET (4 rows) is not the round's direct yield** (QA's decomposition: 2 from hash resolution, 2 from timing noise at one abandoned cycle). It cannot move a row.

## §5. Ledger (scored at ruling time)

| # | prediction | P | result |
|---|---|---:|---|
| BL-1 | B-OFF and B-EQ-1 pass on the first Developer commit | 0.80 | ✅ HIT (`b1d8a06e`; 0 cycles differ) |
| BL-2 | B-EQ-2 passes on the first Developer commit | 0.55 | ✅ HIT (432 batch-5 rows; 0 cycles differ) |
| BL-3 | ACCEPT-3N | 0.55 | ✅ HIT |
| BL-4 | sol: late round abandoned in ≤ 5 % of eligible cycles | 0.60 | ❌ FALSE (29.1 %) |
| BL-5 | third-night NET point ≥ 0.6 pp | 0.50 | ✅ HIT (0.772) |

**Brier 0.211 over 5.**

**BL-4 was a real miss.** I reasoned from 11.1 s as sol's worst fallback end and did not check that figure against this configuration. This night's maximum was 12,892 ms, and the round started failing once the fallback ended after about 10 s. QA priced BL-4 lower, at 0.45, and that was closer.

## §6. What follows

**For the Captain (§7).** Merging and default ON are separate decisions, both his (HK-010).

**Owed by QA:**
1. Add the final rows, this ruling's §2 and the Original arm's 800-cycle counts to the third-night report. Copy the report and result JSON to the standard output location if that applies to this run.
2. Correct the "0.0063 added" wording where it appears in QA's records, with a row in QA's own error ledger.
3. Hold the `late-sub` scratch until the merge question is answered.

**If he says merge:** `pre_merge_check.py` from a clean checkout of the exact commit before any push (HK-006), then the OpenSpec audit (HK-002), then his sign-off on the PR. `origin/main` is still at `c2c85c45`, the build's base, so nothing has moved under it.

**Before any ON endurance run, ON sweep or default ON:** the three parsers (`f2_station_count.py`, `sweep_f2_record.py`, `third_pass_counters.py`) must be fixed, because they double count with the setting ON (`2026-10-30-1731` §6).

## §7. For the Captain

**Result:** the late round passed its acceptance night. It adds **+0.77 pp** of WSJT-X's decodes on sol, even with 29 % of rounds abandoned for lack of time. The cost is about one extra decode every 50 minutes that was tested and found absent from the audio.

**Decision 1: merge, with the setting OFF.**
- **Yes (recommended):** your station's output does not change while the setting is OFF; B-OFF showed no difference in 1,200 of 1,200 cycles. Version goes to 0.68. QA runs the merge checks and CI, and the code stops sitting on a branch.
- **No:** nothing changes, and the branch goes stale as `main` moves.
- This is the decision that matters now. It does not start a new era.

**Decision 2: default ON.**
- **Yes:** expect about +0.77 pp, measured on sol; your PC has much more time per cycle, but no PC figure exists for this build on a fresh night. It starts a new era for live figures, and QA must fix the three parsers first.
- **Not yet:** nothing is lost except the yield in the meantime.
- **My recommendation: decide it together with the R-F4 ON choice you already owe**, so you have one era break rather than two. On `20261022_1949` the harness gave +1.12 pp with R-F4 on (descriptive, not a verdict).
