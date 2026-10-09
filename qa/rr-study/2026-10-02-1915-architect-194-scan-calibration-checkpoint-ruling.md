# RULING — #194 captured-audio scan, calibration checkpoint (Amendments A1–A6)

- **To:** Engineer (owner of #194 part A) — cc QA, Captain  **From:** Architect  **Date:** 2026-10-02 ~19:15Z (HK-017)
- **Branch:** `arch/194-rr-improvements` (fresh off `origin/main`). Docs only: `git diff --stat -- src/ native/` empty.
- **On:** `eng/194-scan` `37de2e4a`, `qa/rr-study/captured-audio-scan/INTERIM-REPORT-2026-10-02.md`; spec `qa/rr-study/2026-10-02-1720-architect-to-qa-spec-194-captured-audio-scan.md` (on `main` since `e5feb132`).
- **Order respected:** the Engineer stopped where §5 says to stop. Nothing is frozen and no 09-29 WAV has been opened. Every amendment below is decided on the calibration run alone, before the validation runs are read. **That is the pre-registration working.**

## 1. Verdict

**Accepted with amendments. The Engineer may freeze, then run PC1, then read the 09-29 pair**, in exactly the order of §5 below. No new run is needed.

The spec was wrong in two places, and both are mine: R0c's yardstick, and the assumption that one population per side would do. The Engineer found both from data, and his remedies are the right shape. One condition is added to each (§2, §3), so that what was a judgement call becomes a rule.

## 2. Rulings on A1–A4 and A6

| # | Ruling |
|---|---|
| **A1** R0c per slot, on discriminating slots | **ACCEPTED as an amendment of §3.** A slot is *discriminating* iff its reference's peak correlation with each neighbour's reference is < 0.5. On those, R0c passes iff the slot's own `rho_peak` exceeds **both of its own** neighbours' by ≥ 0.2, and the 2 % stop line applies to discriminating slots only. Non-discriminating slots get the new status **`REF-UNVERIFIABLE`**: they are scanned, their mapping rests on the file-name ↔ `cycle_utc` identity alone, and the report counts them separately and never calls them verified. **Condition:** `REF-UNVERIFIABLE` > 50 % of a run's slots ⇒ stop and report. (09-23: 175/407 = 43 %.) The literal R0c result (FAIL, 2.9 % / 10.3 %) stays in the report as the result of the rule as written. |
| **A2** end-touching zero runs | **ACCEPTED.** A zero run touching either end of the file is `head_zero_ms` / `tail_zero_ms`, excluded from `zero_run_ms` and from the support. **Rule for the tail, fixed now:** WSJT-X flags if \|`tail_zero_ms` − 600.0\| > 5 ms; OpenWSFZ flags if `tail_zero_ms` > 5 ms. `head_zero_ms` flags on either side if > 5 ms. The 600 ms is WSJT-X's own file structure (14.4 s written), not a dropout. **A2 is a blind spot, stated:** a dropout in WSJT-X's last 600 ms cannot be seen. |
| **A3** `lag_ambiguous` | **ACCEPTED** (second distinct peak ≥ 0.9 × best ⇒ `tau_ms`, `dtau_ms`, `drift_ppm` = NaN). **Stated as a blind spot (HK-026):** on those slots (68 on 09-23, mostly S5 p2/p3), timing faults are invisible. The report gives the count per group and never reads "no timing flag" there as "timing normal". |
| **A4** metric definitions as in `scan_core.py`'s header | **ACCEPTED** as the definitions of record. The code is the predicate, and its SHA goes in `thresholds.json`. |
| **A6** `clip_n` "exceeds 1" | **AMENDED:** the floor is meant as "any clipping". Flag at `clip_n` ≥ 1. 09-23 has 0 clipped samples on both sides, so this changes no calibration flag. |

## 3. A5: per-group thresholds, ACCEPTED, with the groups fixed by scene type (not by their medians)

Grouping by looking at which medians resemble each other would be choosing populations after seeing the data. The groups are therefore fixed by **what the scenario plays**, which is known before any audio is read:

| Group | Scenarios | n (09-23) |
|---|---|---:|
| `single` | S1, S1b, S2, S3 (one signal) | 102 |
| `multi` | S4, S7, S8 (several signals) | 125 |
| `noise` | S5 p0, p1 (noise only) | 120 |
| `tone2` | S5 p2 | 30 |
| `tone3` | S5 p3 | 30 |

Per side and group: the §5 rule unchanged (median + 6 × 1.4826 × MAD, the same floors). A group with n < 20 in a future run uses its 09-23 thresholds and is never recalibrated on its own.

**The 1 % test, made mechanical, so that there is no second ruling round:** the calibration run contains real shared events (§4), and those must not be counted as evidence of a mixed population. Per side, group and metric, count the flagged slots **excluding those classified BOTH on the same metric family**. If that count exceeds **2 %** of the group, the metric becomes **`DESCRIPTIVE` in that group**: it is reported, never used to flag, and listed as such in `thresholds.json`. No `DESCRIPTIVE` metric needs PC1. The report's headline says how many (group, metric) cells went `DESCRIPTIVE`, because each one is a hole in what the scan can see.

**Expected consequences, not a bar** (so that nobody is surprised): WSJT-X `click_max` in `multi` and `tone3`, and `tile_excess_db` in `tone2`/`tone3`, will probably go `DESCRIPTIVE`. Their residual is structured by the apps' own decimation filters on tones (median `resid_db` −10 to −29 dB, CA2 MISS), so they measure content, not chain.

## 4. The findings already in hand (09-23, calibration run, descriptive)

1. **Shared ≈ 10 ms mid-slot lag steps, 12 slots (≈ 3 %), identical on both recordings to 0.1 sample** (108–144 samples at 12 kHz). By §1 this is the **shared playback path**. Note the Engineer's FILE:LINE fact: the harness plays up to 20 slots as **one continuous `sd.play`** (`run_scenario.py:1196`), so these are slips **inside** a continuous stream (render → PortAudio → Voicemeeter), not slot-boundary effects. **What it could touch:** 10 ms is 1/16 of an FT8 symbol, too small to cost a decode at R&R SNRs, but it is a DT error of the same size. QA checks whether any of the 12 slots is an S3 slot and whether its DT reading is an outlier in `S3_matched.csv`. That is a descriptive cross-check, not a reopened S3 result.
2. **11:08:45Z, S5 p0 `t010`: a 49–56 dB `step_db_max`, followed by 14 slots (t011–t024, to ≈ 11:12Z) with `rho` lower on both apps** (0.82 / 0.69 against 0.93 / 0.88 around them). This is the kind of event the Captain predicted for #194 (a Windows or operator change mid-run). **Run §7, the event-log cross-reference, for 09-23 FIRST, before the 09-29 pair, while that log may still be retained (nine days).** If the log no longer reaches 2026-09-23, say so. Do not read the absence of events as "nothing happened". **Captain: if you remember touching Windows sound settings, Voicemeeter, or the PC around 11:08Z on 2026-09-23, that answers it outright.**
3. **Section 11 cause CONFIRMED** (`tools/gather_live_run_artefacts.py:288–298` runs `git rev-parse HEAD` in the QA worktree). The fix is still the spec's: take the build from the run's own record (`arm_config.json`). The Engineer may do it in the same branch. It is QA tooling, but the gatherer serves live runs too, so its tests (`tools/tests/test_gather_live_run_artefacts.py`) must stay green.
4. 🛑 **§9 guard stands:** S1's `g_db` −1.63 (owsfz) / −0.67 (wsjt-x) are chain gains and say **nothing** about the dropped +1.45 dB SNR-bias follow-up. Not to be cited.

## 5. Order from here (each step committed before the next)

1. Apply A1–A6 as ruled. Recompute the calibration per §3. Commit `thresholds.json` (per side × group: median, MAD, floor, `T`, `DESCRIPTIVE` list) and the SHA-256 of `thresholds.json` and of `scan_core.py`. **That is the freeze.**
2. Run §7 on 09-23 (finding 2 first).
3. Run PC1 on copies of 09-23 slots, **per group, at 0.5×/1×/2× of that group's frozen `T`**, for every non-`DESCRIPTIVE` metric. The drawn slots are the 10 per side per group that are not flagged (seed 20261002). **PC1 FAIL ⇒ stop; nothing is read on 09-29.**
4. Only then read the 09-29 pair: V1–V3, classification, report.
5. Report to the Architect. The scan is wired into the post-run step only after the Architect has ruled on that report (unchanged).

## 6. Predictions scored now (the rest wait for the validation report)

| # | Prediction | P | Outcome |
|---|---|---:|---|
| CA1 | R0c passes on all three runs with < 0.5 % `REF-MISMATCH` | 0.70 | 🔴 **MISS** on 09-23: the rule as written fails (2.9 % / 10.3 %). The failure is in my yardstick, not in the mapping (0 mismatches under A1). Scored on the rule I wrote, not on the amended one. |
| CA2 | WSJT-X median `resid_db` ∈ [−45, −25] dB | 0.45 | 🔴 **MISS**: −12.45 dB. I assumed a near-digital path; the apps' own decimation filters dominate. |
| CA3 | ≥ 1 slot FLAGGED and BOTH across the three runs | 0.35 | ✅ **HIT** already on 09-23 (12 shared lag steps). I priced a real finding at 0.35. That is the opposite of my usual bias, and it still missed in the cautious direction. |
| CA4 | PC1 passes first time | 0.65 | open |
| CA5 | §11's cause is the worktree-`HEAD` read | 0.70 | ✅ **HIT** (FILE:LINE confirmed) |
