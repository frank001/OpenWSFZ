# LATE-SUB L1′: one late subtract-and-decode round, primary decoder only, verdict on a fresh night

**Date:** 2026-10-30T13:17:22Z (`date -u`) · **From:** QA · **Spec:** `8152d4ce` + Amendment 1 §8 `e3fd391e` + A1.6 (refset leg from cycle 1) · QA review `2ce7eabc` · freeze record `23a35eb4` · code `b7c17464` · **Captain's go:** "go with your recommendations" (2026-10-30)
**Bars (HK-038, unchanged):** BAR_G 0.5 pp, U_bar_G 0.021 per cycle on tested_absent, h 0.5 (the COH-GATE-G bars; spec §4 gives their origin). Bootstrap by cycle, B = 2000, seed 20261030.
**Status:** an offline lever study; nothing built, no setting changed. **OFF on the verdict night decides; ON and the refset leg are descriptive.**
Aggregates only. No callsign or message text. Working files are in `D:\Projects\claude\_qa-scratch\late-sub\` and are deleted at job close.

## Result in one paragraph

**L1′-GO on the verdict night (OFF).** One late subtract-and-decode round with the primary decoder only, fit list = published batch 3 + batch 4, adds **NET +0.742 pp [0.621, 0.859]** (CI_lo 0.621 ≥ 0.5) at **ΔU′(tested_absent) 0.0063 [0.0013, 0.0125]** (CI_hi 0.0125 ≤ 0.021) and **H-SHARE 0** (bar 0.5). 167 rows were added over 800 cycles of a night the study had never seen, 154 of them (92.2 %) corroborated; 5 are tested-absent, none hashed, none in an untestable class (so the HK-026 re-freeze did not fire). The rule is mechanical: `l1p_analyse.py` printed `L1p-GO`. The next step the spec names is a Developer build spec (HK-011) with a sol timing row; the acceptance night for that build is a third night, never this one.

## Validity rows (all PASS)

| row | verdict night OFF | verdict night ON | refset leg | pilot (40 cycles) |
|---|---|---|---|---|
| **V0** DLL = pin `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` | PASS | PASS | PASS | PASS |
| **V2** batches 1/2/3 and the B buffer reproduced | 0 not reproduced | 0 | 0 | 0 |
| **V3** batch 4 reproduced | 0 | 0 | 0 | 0 |
| **V5** abandoned/contained | 0 | 0 | 0 | 0 |
| **V6** freeze record committed before the first output | PASS | PASS | PASS | PASS |
| **V7** mode l1p reproduces the old pilot on refset cycles 1-40 | PASS (run before the freeze: 0 cycles differ; fit list = old minus Arm C rows in all 40; run.csv and nc_dump identical; 0 C or L2 rows) | | | |
| **V8** n_ref = 20,753 on the PC | PASS (20,753; 799 of 800 cycles with WSJT-X lines) | | | |

**V1 is descriptive** (the R-F4 2N arms ran on sol): this PC's product batch counts differ from sol's in **0 of 800 cycles** (OFF) and **0 of 800** (ON). Platform enters the comparison not at all on this evidence.
**Levels (verdict night):** R3 in 708 cycles, R2 in 92. L1′ ran in 758 cycles and was skipped in 42 (nothing new to subtract, ON: 769 and 31). Fit list: 2,588 entries, **245 (9.5 %)** refused by `IsReencodable`/`EncodeMessage` (the #273 gap again; ON 2,913 and 294).
**Frozen inputs:** selection `cf9908a5…` (R-F4's 800-cycle 2N), classes `0d83d685…` (the 200-cycle Original arm, 4 of 5 classes testable, instrument blob `66dd1e94…` asserted), selection hash and class hash asserted in code before any figure was computed.

## T1: verdict night OFF (800 cycles, n_ref 20,753)

| metric | value | bar | row |
|---|---|---|---|
| NET pp [95 % CI] | **0.742 [0.621, 0.859]** | CI_lo ≥ 0.5 | met |
| ΔU′ tested_absent per cycle [CI] | **0.0063 [0.0013, 0.0125]** | CI_hi ≤ 0.021 | met |
| H-SHARE | 0 of 167 | ≤ 0.5 | met |
| added outputs / corroborated | 167 / 154 (92.2 %) | | |
| tested-absent / tested-present / hashed / untestable-class (unconfirmed) | 5 / 8 / 0 / 0 | | HK-026 not triggered |
| **Verdict** | | | **L1′-GO** |

## T2: ON arm (descriptive; L1′ against the ON product)

NET **1.123 pp [0.980, 1.269]**; ΔU′ta 0.0075 [0.0025, 0.0138]; 251 added, 233 corroborated (92.8 %); 6 tested-absent; 0 hashed. Same rule would also read GO. Do not pool ON with OFF.

## T3: refset TEST 401-1,200, OFF (descriptive; one process from cycle 1, scored on 401-1,200; n_ref 23,158)

NET **1.140 pp [1.009, 1.278]**; ΔU′ta 0.005 [0.0013, 0.010]; 282 added, 264 corroborated (93.6 %); 4 tested-absent. LATE-SUB's L1 on the same cycles was +1.140 pp (282 rows): **the point estimates are the same.** The row sets are not identical over the 1,200 cycles (30 rows in L1 only, 28 in L1′ only, of about 430), so putting Arm C's rows in the fit list moved about 7 % of the L1 rows, and on TEST the net effect is nil. The fallback rows were not what made the late round pay.
**Verdict night against refset:** 0.742 / 1.140 = 0.65. R-F4 gave 0.70 of TEST on its second night; the same shrinkage again.

## T4: timing on the PC (ms; descriptive; sol's margin is a build-spec row)

| | median | p90 | max |
|---|---:|---:|---:|
| L1′ round (verdict night OFF) | 748 | 913 | 1,308 |
| product fallback end | 3,247 | 3,914 | 4,906 |
| **end of work with L1′** | 3,950 | 4,761 | 5,837 |

Budget 13,000 ms. On the PC the worst cycle ends at 5.8 s. Sol is slower than the PC, so its margin must be measured (build spec).

## Predictions (Architect's L1P-1 to L1P-5; scored by him at ruling; QA's reading)

| # | prediction | outcome |
|---|---|---|
| L1P-1 | pilot and full V-rows pass without an amendment | yes: all rows passed; the only code change after the freeze was the chain script's path syntax (not a checked file) |
| L1P-2 | L1′-GO (0.50) | **yes** |
| L1P-3 | NET point ≥ 0.8 pp on the verdict night (0.35) | **no**: 0.742 |
| L1P-4 | ΔU′ta point ≤ 0.010 (0.75) | yes: 0.0063 |
| L1P-5 | refset TEST L1′ NET ≥ 0.9 pp (0.55) | yes: 1.140 |

## Limitations (stated)

- **NET is conservative:** every extra call is bracketed by HashStateSave/Restore, so L1′'s outputs do not feed later cycles' hash state. A live implementation would feed it.
- **One verdict night.** The 0.5 pp lower bound is 0.12 pp from 0.621; the second-night shrinkage (0.65) is already inside this figure because the verdict night is itself the second night.
- **U′ instrument:** classes taken as frozen from a sol Original arm; the platform pointer is 0 differing cycles, and the instrument blob is asserted. The tested-absent count is small (5), so the CI_hi 0.0125 rests on few events; that is the bar's own definition, not a defect.
- **Hash table / publication** emulated as Amendment 1 D5; the pilot and all runs reproduced the product's batches 1-4 exactly (V2/V3).
- **9.5 % of the fit list is refused** by the re-encoding check on this night (5.8 % on the refset): the lever is working with part of its subtraction list missing (#273).
- The PC did not hibernate and was not asked to; the station is still stopped.

## What follows (spec §4, L1′-GO)

A Developer **build spec** (HK-011): the primary-decoder late round on R3/R2, fit list = batch 3 + batch 4, with a **sol timing row** and a **third acceptance night** (not 20261022_1949 and not the refset). Nothing in this report authorises a `src/` change.
