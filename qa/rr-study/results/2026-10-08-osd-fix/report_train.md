# OSD-FIX TRAIN, interleaved, 7 rounds: `n*` = 24 (the lower edge); calibration, not the verdict

- **From:** QA. **To:** Architect, cc Captain. **Date:** 2026-10-09 06:3xZ by `date -u`. TRAIN ran 2026-10-08 17:51:11Z to 19:03:19Z (round 1) and 22:06:33Z to 2026-10-09 04:50:03Z (rounds 2 to 7), Captain's go in QA's window.
- **Spec:** `qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md` §5.2 (`arch/osd-fix`), ruling `2026-10-08-1545` (B1, B2), amendment `2026-10-08-1745` (revised `5e771634`), **ruling `2026-10-09-0615` (`63617c71`)**, which rests on QA's round-7 output of the committed statistics script.
- **Build:** `feat/osd-sign-fix` `3276573b`, shim 20260060, `libft8.dll` SHA-256 `2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb` (pinned at the start and end of all 49 processes). Replay81 `c2ff1981…e5843`. Replay81 `two1`, subtraction ON, threads 8, Test B match rule, `kMinScorePass2` 10, corr 0.10.
- **Commands (scripts, no `--filter` applies):** `python qa/rr-study/osd-fix/osd_fix_train.py --rounds 1-1`, then `--rounds 2-7` (detached, resumable); statistics `python qa/rr-study/osd-fix/osd_fix_train_rows.py` (committed `eb1c242b`, run after each round); this report's final numbers `python qa/rr-study/osd-fix/osd_fix_train_report.py rows` and `… diag` (committed `d991e703` before it ran). Files: `train_final.json`, `train_r6_hist.json`, `train_interim_round1…7.json`.
- **Pins:** `selection.json` SHA-256(LF) `27bb840f…db11e`; chunk manifest `3420070f…b029` (7 chunks, 6 × 89 + 87 = **621** cycles; the spec's "622" was an approximation, as the earlier reports said); probe vectors `probe_vectors.json` `bc914e99…27b8` (REF) and `probe_vectors_fix.json` `e92b91c1…2e7c` (FIX arms).
- 🛑 **TRAIN calibrates; it is not the verdict.** NET +0.158 pp is the figure that **chose** 24 on these cycles (winner's curse over two eligible arms). Never cite it as the fix's gain. The verdict is TEST.

## Validity

| row | result |
|---|---|
| Rounds / processes | 7 of 7; 49 processes, **every one `ok` on attempt 1** (0 re-runs, 0 failed rows) |
| V1 DLL and harness pin | equal at start and end of every process |
| V2 read-back, chunk SHA | `nhard` and `osdSignFixSet/Read` read back as intended in every process; every chunk SHA = its manifest SHA |
| V2' probe | met at each arm's own cap in every process (REF with the old vectors at 40; FIX arms with the corrected vectors at 40/30/24/50/60/0) |
| V3 | 0 contained exceptions, 0 non-zero exits, every process complete |
| V6 abandoned residual work ≤ 5 % per arm | **PASS** for every arm: FIX30 **4**/621 (0.64 %), FIX40 **5**/621 (0.81 %), the other five arms 0. 5 distinct cycles, all in round 2 (`261004_193915`, `261004_194145`, `261004_194415`, `261004_195145` in both FIX30 and FIX40; `261004_200145` in FIX40 only) |
| Load | round 2 had the longest walls in every arm (708, 708, 847, 905, 733, 726 and 721 s for FIX0, FIX24, FIX30, FIX40, FIX50, FIX60 and REF) against 464 to 667 s in the other rounds. **One small difference from the ruling §1, which says 464 to 661 s: the maximum outside round 2 is 667 s in my table.** Recorded, not a row (the Captain's 2026-10-03 scope). |

## Rows: FIX − REF on 621 cycles (NET in pp of WSJT-X's 19,616 decodes on these cycles; 95 % block bootstrap, blocks of 40, B 10,000, seed 20261007)

QA's own run of the committed script. **Every figure below equals the Architect's ruling §2 and §3 to the printed digit; there is no difference to flag.**

| arm | NET | ΔU (not-confirmed per cycle) | NET batch 1 | NET batch 2 | ΔU batch 1 / batch 2 | ΔU ≤ 0? |
|---|---|---|---|---|---|:---:|
| FIX0 (descriptive, B1) | +0.076 [+0.026, +0.136] | −0.079 [−0.098, −0.060] | +0.000 [0.000, 0.000] | +0.076 [+0.026, +0.136] | −0.063 / −0.016 | outside the rule |
| **FIX24** | **+0.158 [+0.099, +0.221]** | −0.074 [−0.095, −0.053] | +0.061 [+0.031, +0.093] | +0.097 [+0.050, +0.151] | −0.060 / −0.014 | yes |
| FIX30 | +0.056 [−0.174, +0.215] | −0.072 [−0.095, −0.050] | +0.061 [+0.031, +0.093] | −0.005 [−0.222, +0.140] | −0.058 / −0.014 | yes |
| FIX40 | −0.122 [−0.347, +0.055] | +0.055 [+0.021, +0.090] | +0.056 [+0.026, +0.089] | −0.178 [−0.387, −0.025] | +0.050 / +0.005 | no |
| FIX50 | −0.474 [−0.595, −0.342] | +0.680 [+0.610, +0.747] | +0.041 [−0.005, +0.083] | −0.515 [−0.606, −0.417] | +0.512 / +0.167 | no |
| FIX60 | −0.596 [−0.725, −0.464] | +0.850 [+0.777, +0.927] | +0.036 [−0.005, +0.075] | −0.632 [−0.738, −0.520] | +0.630 / +0.221 | no |

**Rule (spec §5.2, unchanged):** eligible = 24 and 30; the larger NET is **24** ⇒ **`n*` = 24**, the grid's lower edge. B2 (decided 2026-10-08 before any decode): no extension below 24. **B1 does not fire:** FIX0's NET (+0.076) is below FIX24's (+0.158).

**FIX24 − FIX0, paired directly (descriptive):** NET **+0.082 pp [+0.044, +0.123]**, ΔU **+0.005 [0.000, +0.010]**: on TRAIN the corrected OSD at cap 24 adds decodes over no OSD at all, at a not-confirmed cost too small to resolve. FIX0 against REF (+0.076) equals the OSD-OFF pooled reading on file (+0.076 [+0.036, +0.123]), as the Architect noted.

**Sensitivity of `n*` to the round-2 abandons (descriptive, post-data, changes nothing):** QA's `compare()` on the same rows with cycles removed.

| view | n | FIX24 NET | FIX30 NET | FIX30 − FIX24 | FIX40 ΔU |
|---|---:|---|---|---|---|
| all cycles (the rule's input) | 621 | +0.158 [+0.099, +0.221] | +0.056 [−0.174, +0.215] | −0.102 [−0.304, 0.000] | +0.055 [+0.021, +0.090] |
| drop the 5 abandoned cycles | 616 | +0.160 [+0.102, +0.221] | +0.160 [+0.102, +0.221] | **0.000 [0.000, 0.000]** | +0.054 [+0.026, +0.080] |
| drop round 2 entirely | 532 | +0.168 [+0.108, +0.231] | +0.168 [+0.108, +0.231] | **0.000 [0.000, 0.000]** | +0.053 [+0.022, +0.083] |

FIX30's lower NET is entirely those 5 cycles. On every other cycle caps 24 and 30 give the same decodes, so the tie clause picks **24 in every view**. FIX40 is excluded in every view by ΔU > 0.

## Trajectory (interim statistics after each round, each labelled "interim, k of 7, not citable" at the time)

| after round | cycles | would-be `n*` | FIX24 NET | FIX0 NET |
|---:|---:|---|---:|---:|
| 1 | 89 | none (< 4 rounds) | +0.090 | 0.000 |
| 2 | 178 | none | +0.102 | +0.044 |
| 3 | 267 | none | +0.119 | +0.043 |
| 4 | 356 | 24 | +0.110 | +0.051 |
| 5 | 445 | 24 | +0.142 | +0.067 |
| 6 | 534 | 24 | +0.156 | +0.069 |
| 7 | 621 | 24 | +0.158 | +0.076 |

The `n*` named at round 4 did not move; nobody stopped early and nothing about the grid, the rule or the arms was changed after looking.

## Wall time (pooled per arm across the 7 rounds, one process each per round; the rotation exists so these are comparable)

| arm | median s per process (89 cycles) | min to max | per cycle |
|---|---:|---|---:|
| REF | 542 | 474 to 721 | ≈ 6.1 s |
| FIX0 | 533 | 465 to 708 | ≈ 6.0 s |
| FIX24 | 537 | 467 to 708 | ≈ 6.0 s |
| FIX30 | 539 | 464 to 847 | ≈ 6.1 s |
| FIX40 | 540 | 473 to 905 | ≈ 6.1 s |
| FIX50 | 584 | 511 to 733 | ≈ 6.6 s |
| FIX60 | 596 | 516 to 726 | ≈ 6.7 s |

Whole rounds: 4,329 / 5,348 / 3,474 / 3,666 / 4,448 / 3,871 / 3,403 s (the per-cycle figures are medians divided by 89, not measured per cycle). The corrected OSD at cap 24 costs no measurable decode time against REF; the loose caps cost about 8 to 10 %.

## R6: `nhard` of the OSD gate's accepts (descriptive)

From a separate ctypes pass of `ft8_decode_all` on **all 621 TRAIN cycles** (PEEK-100's PK5 method, its limit stands: **first decode call only, passes 0 and 1, not the residual-subtraction decode**; the native diagnostics are thread-local so Replay81 cannot read them), at the production parameters (cap 40), switch 0 against switch 1. 0 truncated calls.

| | switch 0 (inverted LLRs: today) | switch 1 (corrected LLRs) |
|---|---:|---:|
| OSD gate accepts, total (per cycle) | 567 (0.91) | 612 (0.99) |
| `nhard` 5 to 9 / 10 to 14 / 15 to 19 / 20 to 24 | 0 / 0 / 0 / 0 | **4 / 23 / 8 / 0 (35 accepts ≤ 24, 5.7 %)** |
| `nhard` 25 to 29 / 30 to 34 | 1 / 38 | 2 / 26 |
| `nhard` 35 to 39 / 40 (the cap) | 362 / 166 | 368 / 181 |
| accepts with `nhard` ≥ 25 | 567 | 577 |
| minimum `nhard` | 28 | 6 |
| corr/norm of accepts, median | 0.361 | 0.367 |
| nhard-cap rejects, pass 0 / pass 1 | 1,609 / 2,769 | 1,580 / 2,734 |
| corr rejects | 0 / 0 | 0 / 0 |

**Reading (descriptive).** Under the inverted sign **no** accept has `nhard` below 28 and 528 of 567 sit at 35 to 40: the shape of accepts at the cap's edge, i.e. chance. Under the corrected sign **35 accepts appear at `nhard` 6 to 19**, which the inverted sign never produced, while the mass at 25 to 40 stays about the same (577 against 567). A cap of 24 keeps the first group and drops the second, which is what `n*` = 24 does; 35 accepts in 621 cycles sits beside the 31 extra decodes the Architect counted (the two are not the same quantity: accepts are first-pass only and unclassified here). The confirmed / not-confirmed split of accepts is NOT available here (spec §5.3's histogram is a TEST row and has the same limit).

## Limits

TRAIN is one night (`20261004_1634`), residues {0, 5}, replay, one band; `n*` is chosen here and judged on TEST. The R6 pass covers the first decode call only. The sensitivity rows are post-data and descriptive. FIX0's and FIX24's batch-1 NET differ (0.000 against +0.061) because FIX0 turns the OSD off, so the batch-1 gain belongs to the OSD accepts at `nhard` ≤ 24.

## Next (QA)

TEST is prepared (`2026-10-09-osd-fix-test`): selection frozen, runner and verdict script committed, V5 run. **TEST needs the Captain's go in QA's window.** The run folder is copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-08-osd-fix-train`.
