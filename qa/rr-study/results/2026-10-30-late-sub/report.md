# LATE-SUB: does a late subtraction round (Arm L) or the fallback on the plain buffer (Arm C) pay for itself?

**Date:** 2026-10-30T06:52:34Z (`date -u`) · **From:** QA · **Spec:** `arch/gap-residual` LATE-SUB `5c33391f` + Amendment 1 `e2f7c5b2` · QA review `809e4f7e` · **Captain's go:** "go" (2026-10-29)
**Bars (re-used, not re-derived):** the Captain's "agreed" on re-using the COH-GATE-G bars, relayed by the Architect on 2026-10-29: **BAR_G 0.5 pp, U_bar_G 0.021 (tested_absent only), h 0.5**. Asserted in the code (`ls_analyse.py:33`).
**Status:** an offline lever study. Nothing was built, no setting changed. **The OFF arm decides; the ON arm is descriptive.**
Aggregates only. No callsign or message text in this report. Working files are in `D:\Projects\claude\_qa-scratch\late-sub\` and are deleted at job close.

## Result in one paragraph

**Both levers find rows, and both fail the cost bar.** On the TEST cycles 401-1,200 with the verdict configuration (OFF), **Arm L (C + a late subtraction round + a second fallback) adds NET +2.863 pp [2.637, 3.086]** and **Arm C alone adds NET +0.838 pp [0.722, 0.953]**; both clear BAR_G (CI_lo ≥ 0.5 pp). But the U′ instrument says both cost too much: **dU′(tested_absent) 0.0663 [0.050, 0.084] for L and 0.035 [0.024, 0.049] for C, against U_bar_G 0.021**. Mechanical verdict rows: **L-COST, C-COST** (not L-GO, not L-STOP). H-SHARE is nowhere near binding (hashed share of added outputs 1.5 % for L, 2.9 % for C, bar 0.5). The yield is real; the price in the instrument is the reason it is not a GO.

## Validity rows (all PASS, both arms, 1,200 cycles)

| row | OFF | ON |
|---|---|---|
| **V0** libft8.dll SHA-256 = pin `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` | PASS | PASS |
| **V1** product output byte-identical to the on-disk R-F4 arm, per cycle (OFF vs `raw_main\main`, ON vs `raw\on`) | 1,200 / 1,200, 0 differing | PASS |
| **V2** offline reproduction of batches 1/2/3 and the R3 buffer | 0 not reproduced | PASS |
| **V3** batch 4 reproduction | 0 not reproduced | PASS |
| **V4** snapshots present; diag-switch check | 0 missing; 5 switch checks, 0 differ | PASS |
| **V5** nothing abandoned or contained | 0 / 0 / 0; 1,200 fallback lines | PASS |

**Selection:** `selection1200.json`, SHA-256 prefix **`328c85d4`** (checked by the chain before it started). The spec's `81372df5` is a git **commit** (the COH-MULTISET-BUILD selection freeze), not a file hash; its `selection.json` holds the 2,882 whole-night stamps of `20260925_2010` (SHA-256(LF) `53d9ba4e…`). Checked 2026-10-30: the 1,200 FULL stamps of `selection1200.json` equal the first 1,200 stamps of that list element for element, and the warm-up is its first stamp (`260925_201200`). Same list, different identifiers. (An earlier draft of this report said the identifier was untraceable; corrected.)
**Levels:** R3 in 1,124 cycles, R2 in 76 (no third pass). L ran in 1,173 cycles, skipped (nothing new to subtract) in 27.
**Fit list:** 5,020 entries, of which **279 (5.6 %)** were refused by `IsReencodable`/`EncodeMessage` and so not subtracted (same refusal as the product; relates to #273).

## T1: verdict table, OFF, TEST cycles 401-1,200 (n_ref 23,158; bootstrap by cycle, B = 2000, seed 20261030)

| arm | NET pp [95 % CI] | added outputs / corroborated | dU′ tested_absent [CI] | dU′ present / hu | hashed share | row |
|---|---|---:|---|---|---:|---|
| C | 0.838 [0.722, 0.953] | 238 / 194 | 0.035 [0.024, 0.049] | 0.019 / 0.001 | 2.9 % | **C-COST** |
| C + L1 | 1.978 [1.803, 2.151] | 520 / 458 | 0.040 [0.028, 0.055] | 0.036 / 0.001 | 1.3 % | (not a row) |
| **L (C + L1 + L2)** | **2.863 [2.637, 3.086]** | 780 / 663 | **0.066 [0.050, 0.084]** | 0.075 / 0.004 | 1.5 % | **L-COST** |

**Decomposition** (rows published per step): C 238, L1 282, L2 260. Marginal NET: L minus C **+2.025 pp [1.845, 2.219]**; the first late round (L1) alone +1.140 [1.007, 1.283]; the second fallback (L2) alone +0.885 [0.767, 1.011]. Both add real rows; L2 (the fallback on the R4 buffer) is not a rounding error.
One row class is untestable by the instrument (dU′ untestable 0.00125 for L, 0 for C); it is reported, not counted.

## T2: ON arm (R-F4 ungated), descriptive

| arm | NET pp [CI] | dU′ tested_absent [CI] | row (descriptive) |
|---|---|---|---|
| C | 0.885 [0.767, 1.002] | 0.035 [0.024, 0.049] | C-COST |
| C + L1 | 2.457 [2.258, 2.653] | 0.044 [0.031, 0.059] | |
| L | 3.666 [3.414, 3.910] | 0.074 [0.056, 0.093] | L-COST |

ON adds yield to L (+0.80 pp over OFF) and the same cost; it changes no row. Do not pool ON with OFF.

## T3: TRAIN mechanism check (cycles 1-400, descriptive; the NR-TAX tags)

| NR-TAX group | rows | C | C+L1 | L (OFF) | L (ON) |
|---|---:|---:|---:|---:|---:|
| CU-d (stronger neighbour we decoded late) | 333 | 0 | 76 | 118 | 125 |
| CU-u (stronger neighbour never decoded) | 228 | 0 | 0 | 2 | 64 |
| never offered to the fallback (RC/RG/RW) | 153 | 111 | 113 | 115 | 120 |

Reading (association, not proof): the late round does recover rows sitting beside a **late-decoded** stronger neighbour (CU-d: 35 % in OFF), exactly where NR-TAX said to look. CU-u is not reached by subtraction in OFF (2 of 228); only ON, which widens what the fallback may publish, reaches it (64). The never-offered rows come back **mostly from Arm C alone** (111 of 153), which is the cheap lever.

## T4: timing (ms; product residual pass and third pass for context)

| step | median | p90 | max |
|---|---:|---:|---:|
| Arm C fallback | 207 | 323 | 628 |
| Arm L round (subtract + decode + fallback) | 782 | 995 | 1,589 |
| of which subtract + decode | 679 | 829 | 1,395 |
| of which fallback on R4 | 105 | 180 | 386 |
| product residual pass (context) | 1,365 | 2,026 | 2,421 |
| product third pass (context) | 707 | 857 | 1,163 |
| **end of work in the cycle, product fallback** | 3,172 | 3,938 | 4,613 |
| end of work with Arm C | 3,369 | 4,204 | 5,197 |
| **end of work with Arm L** | 4,145 | 5,115 | 6,534 |

Budget 13,000 ms: Arm L's worst cycle ends at 6.5 s on this PC, about half. Timing is not what stops it. (ON: L median 4.3 s, max 6.8 s.)

## Limitations (stated, not hidden)

- **NET is conservative.** Every extra call is bracketed by HashStateSave/Restore, so arm outputs do not feed later cycles' hash state. A live implementation would feed it; the true NET could differ either way, by a little (hashed share is 1.5 %).
- **Fit natives** were built as `Ft8Decoder.cs:1114` builds them (unrounded `OutDtS`, rounded frequency), not from published rounded dt.
- **dU′ is the U′ instrument** with classes frozen from the Original arm (`D:\Projects\claude\_qa-scratch\coh-gate-g\u\uprime_orig_classes.json`); it inherits that instrument's blind spots. I did not re-derive its scale here; the bars are the ones the Captain agreed to.
- **TEST is one night** (`20260925_2010`, cycles 401-1,200). Cycles 1-400 were not used for the verdict.
- The continuous-arm TEST corroborated count is 18,833 of 23,158 (the spec's 18,844 came from a process started at cycle 401; difference noted, not a defect).
- One instrument note: the watcher's `shutdown.exe /h` printed its usage text under Git Bash instead of hibernating (the `/h` argument was path-converted). **The PC did not hibernate.** Nothing was lost.

## Reading for the decision (QA's view, not a ruling)

1. Yield is not in doubt (L +2.9 pp, C +0.8 pp, both bootstrapped well clear of 0.5 pp). The bar that blocks is U′.
2. The two levers fail the **same** row for the **same** reason, so a "C only" ship does not escape it (0.035 vs 0.021).
3. If the U′ bar is the right gate, neither lever ships as specified. If the Captain thinks the bar is too severe for lever-sized gains, that is a bar question for him, not something this run can settle.
