# LATE-SUB L1′ THIRD ACCEPTANCE NIGHT (sol, `20260930_1930`): REPORT (QA, 2026-10-30T23:3xZ `date -u`, written after the first analysis)

**To:** Architect · **Build:** Developer `b1d8a06e` (v0.68) · **Freeze:** `3275f843` + addendum `20e111b4` · **Spec:** build spec §4, Amendment 1, Amendment 2 (§8) · **Analysis code:** `tn_analyse.py` `2526b5a4` (docstring line 10 corrected in `2c967b08`, comment only, no logic change; noted here as asked) · Nothing pushed.

## Pins and what ran (HK-022)
- `libft8.so` built on sol from `b1d8a06e`: SHA-256 `488bfa0b90a570ad0bc9f285d871147f62f4a71165fcf6dc39bd31eb584f58d0` at start and end of every arm (the expected value). Replay81 `cfdf724c`. Selection `2575e115…` (800 cycles, 0 dropped). `tn_arms.sh` (SHA-256 of the file run `82487c3d…`), no `--filter` of any kind: all three arms ran every selected cycle.
- Chain: off 18:29:12Z–20:37:03Z (800 rows, 0 R6 lines), on 20:37:04Z–23:03:31Z (800 rows, 800 R6 lines), orig 23:03Z–23:30:48Z (200 rows, 0 R6 lines); every readback and pin check ok; orphan check clean. Records pulled to `_qa-scratch\late-sub\sol3n` (nc_dump hashes equal sol vs PC for all three arms).
- Classes: frozen from the Original arm's first 200 cycles with `cf_uprime.py off` (`u3/orig_classes.json`, SHA-256 `b3dbdaf35a998f91528112742a5aa2819e8dfaece86bc0c19a47c466cd61f874`; testable classes `RR73/73/RRR`, `grid`, `grid CQ`, `report`; T 0.276).

## X and V-3N-X
- **X = 4 cycles, V-3N-X PASS (|X| ≤ 8).** `260930_200230` (fallback; OFF and ON), `261001_031300` (fallback OFF and ON; third pass ON), `261001_031600` (fallback and third pass, OFF and ON), `261001_050100` (fallback; OFF and ON). The same four cycles in both arms.
- OFF: fallback abandoned in 4 cycles (635 candidates), third pass abandoned/failed in 1, residual pass 0. ON: fallback 4 cycles (483 candidates), third pass 2, residual 0.
- **Original arm: no abandonment at all (fallback 0, residual 0, third pass 0), and none at `260930_200230`.** Its counts do not enter X.

## The two readings (bars 0.5 / 0.021 / 0.5, B = 2000, seed 20261030)
| | cycles | n_ref | NET | 95 % CI | dU′(tested_absent) | CI | rows | verdict |
|---|---|---|---|---|---|---|---|---|
| **R-ALL** | 800 | 27,064 | **+0.772 pp** | [0.655, 0.889] | 0.0050 | [0.0013, 0.0100] | N-GO yes, N-STOP no, U-OK yes, U-FAIL no, H-SHARE not fired | ACCEPT-3N |
| **R-CLEAN** | 796 | 26,853 | **+0.771 pp** | [0.649, 0.893] | 0.0050 | [0.0013, 0.0101] | same | ACCEPT-3N |

OFF corroborated 21,709 (80.21 % of n_ref), ON 21,918 (80.99 %); the replay's own match flags equal the scored counts in both arms. Batch-5 outputs 220 (new = published = 220, so the 437-versus-432 gap seen on the refset does not appear here), 205 corroborated, hashed share 0, cycles with a published batch-5 row 167. V-3N-REF PASS (WSJT-X lines in 800 of 800 cycles).

## HK-026: the classes need re-freezing before the U rows count
**One** unconfirmed batch-5 output falls in `untestable_class` (`HK026_untestable_class_outputs_need_refreeze` true). By the freeze record (item 7) and the spec, the Original arm must be run on the other 600 cycles, the classes re-frozen from all 800, and the U rows computed only then (about +1.5 h on sol). **The U rows above (U-OK, dU′) were computed by the script in the same pass, on the first-200 classes, so they are provisional**; NET, N-GO and H-SHARE do not depend on the classes. The verdict is therefore not final: it holds only after the re-freeze. Nothing is started yet.

## Timing on sol (reported; vetoes nothing)
- Late round outcomes over the 800 cycles: `ran` 552, `abandoned` 228, `no-new` with fit = 0: 16, `no-new` with fit > 0: 4 (`260930_193615`, `261001_003145`, `261001_032715`, `261001_034900`; no test pins that label). No `skipped-…`.
- **T-WARN (registered denominator, fit > 0: 784 cycles): abandoned share 29.1 % (228/784), fires. BL-4 (≤ 5 %): not met.** R2-eligible rate beside it: 28.5 % (228/800). Both sides of the threshold agree.
- `elapsedMs` on fit > 0 rows: median 1,578, p90 2,086, max 2,676 ms (the abandoned rounds' median is 618 ms). `endMs` max over all rows 12,946 ms, a margin of 54 ms to 13,000.
- Fallback end (OFF and ON logs): max 12,892 / 12,917 ms. Fallback end of the cycles whose round ran: median 9,274 ms; of those abandoned: median 10,894 ms. By the whole second of fallback end, fit > 0 rows: 9 s: 220 ran, 1 abandoned; 10 s: 118 ran, 130 abandoned; 11 s: 82 abandoned, 0 ran; 12 s: 15 abandoned. So the round is abandoned once the fallback ends after about 10 s, which is the price NET already includes.
- The R6-versus-inner `elapsedMs` agreement (within 1 ms) was checked on refset cycles 1–60 only.
