# LATE-SUB L1′ THIRD NIGHT: FREEZE ADDENDUM 1 (QA, 2026-10-30T19:37:30Z `date -u`; commit written before any ON output exists)

**Amends:** freeze record `3275f843` (row V-3N-AB), by build spec §8 Amendment 2 (`arch/late-sub`, Captain: "Amend, keep real budget"; ledger E125, E126).
**New analysis code:** `tn_analyse.py` commit **`2526b5a4`** (`qa/refset`, local).

## Statement
**No ON analysis had run when this addendum was written.** The ON arm had not started on sol (`off` at 445 of 800 cycles, `on` and `orig` not begun); no NET, U′ or verdict code had run on any output of this night; `tn_analyse.py` had been run only on `raw_lr` (refset, F-KA known answers) and `raw_t2` (timing). The only readings of the night so far are the OFF arm's abandon and timing counts (cycle `260930_200230`: fallback start 12,134 ms, wall 729 ms, 227 candidates abandoned), reported to the Architect on 2026-10-30.

## What changed in the code (and nothing else)
- **V-3N-AB is replaced** by X and V-3N-X: X = selected cycles in which the residual pass, the third pass (the cycle's FIRST `Third pass:` line, abandoned or failed) or the fallback abandoned, in the OFF or the ON arm; the late round's own abandonment does not enter X. V-3N-X: |X| ≤ 8; if it fails the script prints `NO-VERDICT` (no automatic re-run). The Original arm's abandon counts are reported (including whether it abandoned at `260930_200230`) and do not enter X.
- **R-ALL** (all 800) and **R-CLEAN** (800 minus X), each with the registered rows (N-GO, N-STOP, U-OK, U-FAIL, H-SHARE) and the verdict rule; bootstrap over the kept cycles, B 2000, seed 20261030. Same verdict in both: that verdict. Different: OPEN-3N. HK-026 reads the all-800 outputs.
- **T-WARN and BL-4 are scored on cycles with fit > 0** (E126); the R2-eligible rate is printed beside.
- Unchanged: the bars 0.5 / 0.021 / 0.5, V-3N-REF on all 800, the selection `2575e115…`, the `libft8.so` pin `488bfa0b…`, Replay81 `cfdf724c`, the arms and the running chain.

## Known-answer checks (run before this commit, none on the night)
| check | result |
|---|---|
| `raw_lr` refset 401–1,200, `TN_CFG=ka`: X empty, R-ALL = R-CLEAN | **PASS**: X 0; both 800 cycles; NET 1.140 [1.009, 1.278]; both ACCEPT-3N (descriptive: a refset leg) |
| same with one stamp injected into X (`TN_INJECT_X=260925_221700`) | **PASS**: R-CLEAN 799 cycles (NET 1.1415 [1.0066, 1.2863]); R-ALL unchanged (800, 1.140) |
| `raw_t2` timing, `TN_CFG=t2` | **PASS**: 60 rows; 59 ran + 1 no-new (fit 0); fit > 0 rows 59 (the started-cycle denominator); abandoned share 0.0; T-WARN not fired, BL-4 met; `elapsedMs` 586 / 694 / 817; new 19 = published 19; `endMs` max 4,431; no-new with fit > 0: 0 |

Both readings with NET, CI, rows, and the list of X by stamp, pass and arm go in the report.
