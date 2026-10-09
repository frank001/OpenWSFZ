# OSD-FIX TEST: F-GO. FIX(24) against today's behaviour on 860 cycles of a night that chose nothing

- **From:** QA. **To:** Architect, cc Captain. **Date:** 2026-10-09, run 06:39:53Z to 09:48:56Z by `date -u`; verdict computed 09:49Z. **Go:** the Captain, in QA's window ("start TEST at 860 cycles").
- **Spec:** `qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md` §5.3; ruling `2026-10-09-0615` (`n*` = 24, B2). **Rows as code, committed before any TEST decode:** `osd_fix_test_rows.py` `b5cee17d`; runner `osd_fix_test.py` `44c86232`; selection `6dd0785c`.
- **Build:** `feat/osd-sign-fix` `3276573b`, shim 20260060, `libft8.dll` SHA-256 `2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb`, pinned at the start and end of every process. Replay81 `two1`, subtraction ON, threads 8, Test B match rule, corr 0.10. **REF** = switch 0, `nhard` 40 (today); **FIX24** = switch 1, `nhard` 24.
- **Corpus:** night `20260930_1930`, 40 m, Voicemeeter Out B1 chain, **not** the TRAIN night (`20261004_1634`): no TEST cycle played any part in choosing `n*`. 860 cycles = residues 0 and 5 of the SUB-FEAS included list (4,298 cycles), `selection.json` SHA-256(LF) `84b3d884…78b0`; chunk manifest `e3835bd7…b704` (4 × 215). WSJT-X's own `ALL.TXT` of the night is the reference (Test B).
- **Commands (scripts; no `--filter` applies):** `python qa/rr-study/osd-fix/osd_fix_test.py v5` (06:27Z), `… run TEST` (pid 37956, detached), then `python qa/rr-study/osd-fix/osd_fix_test_rows.py TEST` once all 8 processes were done. The runner never opened a result file, and nobody read one before the verdict script ran. Numbers: `test_result_test.json`.

## Validity (any FAIL ⇒ no verdict)

| row | result |
|---|---|
| V1 DLL pin | equal at the start and end of all 8 processes |
| V2 read-back, SHA | `nhard` 40 / switch 0 in REF and `nhard` 24 / switch 1 in FIX24 read back in every process; every chunk SHA = its manifest SHA; selection SHA = its pin |
| V2' probe | met at each arm's own cap in every process |
| V3 | 8 of 8 processes `ok` on attempt 1 (0 re-runs), 0 contained exceptions, 0 non-zero exits, every process complete |
| V4 | A-SIGN' and A-OFF PASS (QA's reports, accepted by the Architect 2026-10-08) |
| **V5 noise leg at FIX(24)** | **PASS: 0 false decodes on the 200 noise WAVs** (re-hashed against NHARD-REP's pins; run 06:27Z). Limit: this leg has read 0 at every setting tried (inverted OSD at 40 and 60, corrected at 24), so it cannot discriminate (HK-026); the bar was the population's own REF reading (0/200). |
| V6 abandoned residual work ≤ 5 % | PASS: REF 3/860 (0.35 %), FIX24 2/860 (0.23 %) |
| Blind instrument (HK-025(k)) | **not blind**: the FIX24 arm's confirmed decodes differ from REF's in 39 cycles (38 with a gain, 1 with a loss) |

## Verdict: **F-GO** (`CI_lo(NET)` > 0 and `CI_hi(ΔU)` ≤ 0; F-FAIL's `CI_lo(ΔU)` > 0 does not fire)

95 % non-overlapping block bootstrap, blocks of 40 (22 blocks), B 10,000, seed 20261007; FIX24 − REF; NET in pp of WSJT-X's 25,995 decodes on these cycles, ΔU in not-confirmed decodes per cycle.

| row | value |
|---|---|
| **NET** | **+0.208 pp [+0.117, +0.326]** = 54 more confirmed decodes in 860 cycles (REF 18,791; FIX24 18,845): 55 gained in 38 cycles, 1 lost in 1 cycle |
| **ΔU** | **−0.073 [−0.090, −0.058]** not-confirmed per cycle (REF 0.386, FIX24 0.313: 63 fewer in 860 cycles) |
| NET batch 1 / batch 2 | +0.077 [+0.040, +0.121] / +0.131 [+0.056, +0.240] |
| ΔU batch 1 / batch 2 | −0.056 [−0.071, −0.042] / −0.017 [−0.025, −0.010] |

For scale: TRAIN's FIX24 NET (the figure that chose it, optimistic by construction) was +0.158 [+0.099, +0.221] and its ΔU −0.074 [−0.095, −0.053]. TEST's point estimates are +0.208 and −0.073; the intervals overlap. A different night, so this is not a replication of the same cycles.

## Descriptive rows (mandatory; no bar)

**The Captain's mechanism (first-pass false decodes cost residual decodes), both halves together:** batch-1 not-confirmed per cycle **falls** 0.287 → 0.231 (−0.056) **and** batch-2 confirmed per cycle **rises** 3.495 → 3.535 (+0.040). PEEK-100 (100 cycles, `nhard` 40) did not see this; TEST at the calibrated cap does. Descriptive, no bar, one night.

**By SNR band** (NET pp [95 % CI] / ΔU / not-confirmed per cycle REF → FIX):

| band | NET | ΔU | not-confirmed per cycle | FP-watch flag |
|---|---|---|---|---|
| A | +0.042 [+0.011, +0.083] | +0.000 [0.000, 0.000] | 0.062 → 0.062 | no |
| B | +0.096 [+0.038, +0.170] | −0.006 [−0.012, 0.000] | 0.102 → 0.097 | no |
| C | +0.046 [+0.019, +0.074] | −0.017 [−0.026, −0.009] | 0.077 → 0.059 | no |
| D | +0.023 [0.000, +0.051] | −0.050 [−0.063, −0.039] | 0.145 → 0.095 | no |

Every band's NET is non-negative; the not-confirmed reduction sits in the weakest band (D) and in C. The FP-watch rule (CI_lo of FIX's not-confirmed rate above CI_hi of REF's) fires in no band. The spec's U-OK safeguard (REF's not-confirmed per cycle inside [0.30, 0.65]): **0.386, inside**.

**Wall time** per 215-cycle process, median of 4: REF 1,530 s, FIX24 1,493 s; whole rounds 2,842 / 3,242 / 3,202 / 2,057 s. No cost of the fix at cap 24 is visible. (Timing is not compared against another build; WSJT-X was open during the run, the same load for both arms, and the arms alternated order each round.)

**Not available (stated limits):** the OSD-accept `nhard` histogram of confirmed against not-confirmed accepts under FIX (the native diagnostics are thread-local, Replay81 decodes on pool threads; TRAIN's R6 pass gives the accept histogram without the confirmed split).

## Limits

One band, one night's audio, replay not live (Test B's not-confirmed count is an upper bound on false decodes; hashed `<...>` texts cannot match). `n*` was chosen on a different night (`20261004_1634`), so TEST is not contaminated by the choice. The 1,846 GO "wrongs" from the COH-GAIN work remain unclassified. The effect is small in absolute terms: 54 extra confirmed decodes in 860 cycles (about 1 per 16 cycles, 0.2 % of WSJT-X's decodes). TEST's `CI_lo` (+0.117) is positive; nothing here says how it behaves live or on another band.

## What this does and does not authorise (spec §4)

Verdict row F-GO satisfies the spec's condition for the merge row (with unit and characterisation tests green and **the Captain's sign-off, HK-010**). Nothing has been merged or pushed. R4 stands: the code default `osdNhardMax` = 24 (Developer, small second commit) and the station-config migration (QA, HK-035, the config overlay) come **after** this verdict, on the Captain's decision. Predictions OF4 to OF7 are the Architect's to score.

## Reproduction

`python qa/rr-study/osd-fix/osd_fix_test_rows.py TEST` re-reads the 8 processes' `testb.csv` under `artefacts/rr_2026-10-09_osd_fix_test/` (copied with this report to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-09-osd-fix-test`).
