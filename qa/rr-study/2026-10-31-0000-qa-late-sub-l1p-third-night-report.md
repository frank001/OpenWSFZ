# LATE-SUB L1′ THIRD ACCEPTANCE NIGHT (sol, `20260930_1930`): REPORT (QA, 2026-10-30T23:33:40Z `date -u`, written after the first analysis run at 23:32:54Z)

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
**One** unconfirmed batch-5 output falls in `untestable_class` (`HK026_untestable_class_outputs_need_refreeze` true). By the freeze record (item 7) and the spec, the Original arm must be run on the other 600 cycles, the classes re-frozen from all 800, and the U rows computed only then (about +1.5 h on sol). **The U rows above (U-OK, dU′) were computed by the script in the same pass, on the first-200 classes, so they are provisional**; NET, N-GO and H-SHARE do not depend on the classes. The verdict is therefore not final: it holds only after the re-freeze. Nothing is started yet. **The Captain, 2026-10-30T23:35Z: nothing is to be started on sol unless he says so;** the Architect withdrew his instruction to start the Original arm (ledger E127). `tn_orig600.sh` (commit `edd521b8`) is prepared on the PC only. The first pass computing the U rows before the re-freeze is disclosed here and was accepted by the Architect.

## ON minus OFF corroborated (209) against batch-5 corroborated (205): the +4 decomposed
PC-only count from the pulled `nc_dump`s, no re-run, accepted by the Architect (205 + 2 + 2 = 209). Outside X: ON minus OFF = 207 = 205 batch-5 + 2. Inside X: 2 = 0 batch-5 + 2. Batches 1–4 corroborated change in exactly three cycles: `260930_200230` (in X) +2; `260930_193745` (outside X) +1; `260930_221430` (outside X) +1.
- **`260930_193745` and `260930_221430`:** in each, one batches 1–4 row exists only in OFF and one only in ON, both carrying a hashed `<…>` token. This is the shared hash-table mechanism of F3/B-EQ-1: batch-5 decodes of an earlier cycle enter the process-global hash table, so a later cycle resolves a `<…>` call differently; here ON's resolution matches the WSJT-X line.
- **`260930_200230`:** the cycle where the fallback abandoned in both arms (it started at 12,134 ms in OFF). ON has 2 more rows, OFF none that ON lacks, no hashed tokens. Abandonment is time-dependent, so the number of candidates worked before the 13 s limit differs between runs: run-to-run timing noise. The late round cannot affect batches 1–4 of its own cycle.
- **Consequence:** about **0.015 pp** of NET (4 rows of 27,064) is **not the late round's direct yield**: 2 from hash resolution (the round's indirect effect through the hash table, arguably part of it) and 2 from timing noise at the abandoned cycle. It cannot move a row. On the refset the two figures were equal (264 and 264); that run had no abandoned cycle.

## Timing on sol (reported; vetoes nothing)
- Late round outcomes over the 800 cycles: `ran` 552, `abandoned` 228, `no-new` with fit = 0: 16, `no-new` with fit > 0: 4 (`260930_193615`, `261001_003145`, `261001_032715`, `261001_034900`; no test pins that label). No `skipped-…`.
- **T-WARN (registered denominator, fit > 0: 784 cycles): abandoned share 29.1 % (228/784), fires. BL-4 (≤ 5 %): not met.** R2-eligible rate beside it: 28.5 % (228/800). Both sides of the threshold agree.
- `elapsedMs` on fit > 0 rows: median 1,578, p90 2,086, max 2,676 ms (the abandoned rounds' median is 618 ms). `endMs` max over all rows 12,946 ms, a margin of 54 ms to 13,000.
- Fallback end (OFF and ON logs): max 12,892 / 12,917 ms. Fallback end of the cycles whose round ran: median 9,274 ms; of those abandoned: median 10,894 ms. By the whole second of fallback end, fit > 0 rows: 9 s: 220 ran, 1 abandoned; 10 s: 118 ran, 130 abandoned; 11 s: 82 abandoned, 0 ran; 12 s: 15 abandoned. So the round is abandoned once the fallback ends after about 10 s, which is the price NET already includes.
- The R6-versus-inner `elapsedMs` agreement (within 1 ms) was checked on refset cycles 1–60 only.

## ADDENDUM 2026-10-31T10:36:53Z (`date -u`): FINAL ROWS after the re-freeze, the Architect's ruling, and the Original arm's 800-cycle counts
**Supersedes the provisional wording above where it says the U rows are provisional.** The final U rows equal the provisional ones: `third_night_result.json` from the 800-cycle classes is byte-identical (`cmp`) to the one from the first-200 classes.
- **What ran:** Original arm on cycles 201–800 (sol, 2026-10-30T23:57:56Z to 2026-10-31T01:28:15Z, rc 0, 600 rows, pins OK, no halt); records pulled, nc_dump SHA sol = PC. Classes frozen from all 800 (control on the first 200 reproduced `b3dbdaf3…`); classes SHA `8046a4be4b806fcd08b90d376ece7c1203f86446a0476cc98167f8f4a2fc38c1`; freeze addendum 2 `7546ec8b` and code `d50a98fe` committed BEFORE the re-run. Command: `TN_CLASSES=…/u3_800/orig800_classes.json python tn_analyse.py 8046a4be…c38c1`; no `--filter` (a script, not a test suite); `libft8.so` pin `488bfa0b…`, selection `2575e115…`.
- **Final rows (identical to the provisional ones):** V-3N-X PASS (X = 4), V-3N-REF PASS. R-ALL (800 cycles) NET +0.772 pp [0.655, 0.889], dU′ tested-absent 0.005 [0.00125, 0.01]; R-CLEAN (796) NET +0.771 [0.649, 0.893], dU′ tested-absent 0.00503. Both ACCEPT-3N. The classes: same four testable (`RR73/73/RRR` 45/50, `grid` 46/50, `grid CQ` 50/50, `report` 47/50); untestable `other CQ` 13/50 (26 %) and `other` n = 6 (new).
- **Where the one untestable output lands:** class `other CQ` (label only; found with a throwaway probe copy of `tn_analyse.py`, no text printed, the result file untouched). **Both counts** (the Architect's ruling §2, the HK-026 branch he added after this data, E128): counted as not absent (as registered) dU′_ta 0.00500, CI_hi 0.0100; counted as tested-absent dU′_ta 0.00625 (baseline 0.005 plus **an increment of 0.00125**), CI_hi 0.0125, against the 0.021 bar. Same verdict (ACCEPT-3N) both ways. **Correction:** my message of about 10:30Z said "at most about 0.0063 added to the 0.005"; 0.0063 is the total, the addition is 0.00125 (ledger row Q33).
- **The Architect's ruling (`eb422516`, `arch/late-sub`, local, `qa/rr-study/2026-10-31-1034-architect-late-sub-l1p-acceptance-ruling.md`):** ACCEPT-3N, final. §2: `other CQ` settled as untestable (13/50, Wilson hi 0.396 against 0.80); the HK-026 flag stays true in the file by design (it tests class membership, not whether the re-freeze happened); the frozen code and result file stay as they are. A named blind spot: `other CQ` is 262 of 19,797 confirmed Original-arm rows (1.3 %) and 1 of the 220 outputs. He re-ran `tn_analyse.py` at `d50a98fe` into his scratchpad: identical to my JSON.
- **The Original arm's abandon counts over all 800 cycles (reported; not in X):**

| part | cycles | fallback abandoned | residual pass abandoned | third pass abandoned or failed |
|---|---:|---:|---:|---:|
| first 200 (`raw/orig`) | 200 | 0 | 0 | 0 |
| 600 (`raw/orig600`, recounted by QA from `coh.csv`, `abandon.csv`, `third.csv` with the script's own predicates) | 600 | 0 | 0 | 1 (`261001_031600`, outcome `abandoned`) |
| **all 800** | 800 | **0** | **0** | **1** |

  This confirms the Architect's read. `261001_031600` is also in X (OFF and ON abandoned there in the third pass and the fallback); the Original arm never abandoned at `260930_200230`. The "Original arm" counts in the X section above cover the first 200 cycles only.
- **Scratch held** (`late-sub`, `coh-gate-r-f4`, `serena-backup-qa`) until the Captain answers on merge. Result files copied to `qa/rr-study/results/2026-10-31-late-sub-l1p-third-night/`.
