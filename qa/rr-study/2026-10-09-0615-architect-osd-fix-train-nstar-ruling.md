# RULING — OSD-FIX TRAIN complete (7 of 7 rounds): `n*` = 24, the lower edge; TEST proceeds at 24 (B2, decided before data)

- **To:** QA (owner). cc Captain. **From:** Architect. **Date:** 2026-10-09 06:15Z (`date -u`, HK-017).
- **Rules on:** TRAIN output `artefacts/rr_2026-10-08_osd_fix_train/` (rounds r1–r7, orchestrator `DONE requested rounds` at 2026-10-09 04:50:03Z) and QA's `train_interim_round7.json` (`worktrees\qa\qa\rr-study\results\2026-10-08-osd-fix\`, untracked at the time of reading), against spec `2026-10-07-1545` §5.2, ruling `2026-10-08-1545` §4 (B1, B2) and amendment `2026-10-08-1745` (revised `5e771634`) §5–§6.
- **Branch:** `arch/osd-fix` (local, not pushed). Docs only: `git diff --stat -- src/ native/` is empty.
- **QA's final TRAIN report is not written yet.** This ruling rests on the round-7 output of QA's committed statistics script (`osd_fix_train_rows.py`, `eb1c242b`), which is the amendment's "concatenate each arm's per-cycle rows across completed rounds" computation over all 7 rounds. It is therefore the final §5.2 estimate, not an interim one. QA's report must reproduce these figures; any difference is flagged to the Architect before TEST runs.

## 1. Validity (amendment §4, spec V1–V3, V6)

| check | result |
|---|---|
| Rounds complete | 7 of 7; 49 processes, every one `ok` on attempt 1 (0 re-runs), 0 failed rows (`status.json`) |
| V6 (abandoned residual work ≤ 5 % per arm) | PASS for every arm. Abandons only in **round 2**: FIX30 4/621 (0.64 %), FIX40 5/621 (0.81 %); every other arm 0. 5 distinct cycles in all |
| Load | Round 2 had the longest walls of the night (REF 721 s, FIX30 847 s, FIX40 905 s against a 464–667 s range in other rounds; corrected from "661 s" after QA's report, 2026-10-09 06:3xZ). Recorded, not a validity row (Captain's 2026-10-03 scope) |

TRAIN is valid.

## 2. The rule, applied (spec §5.2, unchanged)

TRAIN, 621 cycles, FIX − REF; NET in pp of WSJT-X's decodes, ΔU in not-confirmed decodes per cycle; 95 % block bootstrap (blocks of 40, B 10 000, seed 20261007).

| arm | NET | ΔU | ΔU ≤ 0? |
|---|---|---|:---:|
| FIX0 (descriptive, B1) | +0.076 [+0.026, +0.136] | −0.079 [−0.098, −0.060] | (outside the rule) |
| **FIX24** | **+0.158 [+0.099, +0.221]** | −0.074 [−0.095, −0.053] | yes |
| FIX30 | +0.056 [−0.174, +0.215] | −0.072 [−0.095, −0.050] | yes |
| FIX40 | −0.122 [−0.347, +0.055] | +0.055 [+0.021, +0.090] | no |
| FIX50 | −0.474 [−0.595, −0.342] | +0.680 [+0.610, +0.747] | no |
| FIX60 | −0.596 [−0.725, −0.464] | +0.850 [+0.777, +0.927] | no |

**Eligible: 24 and 30. Largest NET point: 24. ⇒ `n*` = 24.** It is the grid's lower edge. **B2 (ruled 2026-10-08 15:45Z, before any TRAIN decode): no extension below 24; TEST proceeds at 24.** No Architect decision is needed and none is taken here.

**B1:** FIX0's NET (+0.076) is **below** FIX24's (+0.158), so the B1 clause ("if FIX(0) beats FIX(n*), the Captain decides") does not fire. Descriptive, paired directly: **FIX24 − FIX0 = +0.082 pp [+0.044, +0.123], ΔU +0.005 [0.000, +0.010]**: on TRAIN the corrected OSD at cap 24 adds decodes over no OSD at all, at a not-confirmed cost too small to resolve.

**Instrument cross-check (descriptive):** FIX0 against REF, +0.076 pp, equals the OSD-OFF pooled reading on file (+0.076 [+0.036, +0.123], ruling `2026-10-07-0728`). FIX0 is "corrected build, OSD effectively off", so the two should agree, and they do.

## 3. Sensitivity of `n*` to the round-2 abandons (descriptive; changes nothing)

FIX30 and FIX24 have identical batch-1 NET (+0.061) and identical ΔU by batch; only batch-2 NET differs (−0.005 vs +0.097), and only FIX30 (and FIX40) abandoned work. The Architect re-ran QA's own `compare()` on the same rows with those cycles removed (scratch script, outputs numeric only, HK-037):

| view | n | FIX24 NET | FIX30 NET | FIX30 − FIX24 | FIX40 ΔU |
|---|---:|---|---|---|---|
| all cycles (the rule's input) | 621 | +0.158 | +0.056 | −0.102 [−0.304, 0.000] | +0.055 |
| drop the 5 abandoned cycles | 616 | +0.160 | +0.160 | **0.000 [0.000, 0.000]** | +0.054 |
| drop round 2 entirely | 532 | +0.168 | +0.168 | **0.000** | +0.053 |

**Reading:** FIX30's lower NET is entirely the 5 cycles abandoned under load in round 2. On every other cycle, caps 24 and 30 produce the same decodes. Under the rule's tie clause ("ties → the lower `n`") the answer is **24 in every view**, so `n*` is not fragile. FIX40 is excluded in every view by its ΔU > 0 (CI excludes 0), so the result "40, today's default, is too loose for a corrected OSD" does not depend on the abandons either. Post-data, so descriptive only: it does not change the rule or its input.

## 4. What TRAIN does and does not say

- 🛑 **TRAIN calibrates; it is not the verdict.** NET +0.158 pp is the figure that **chose** 24 on these cycles, and it is optimistic by construction (winner's curse over 2 eligible arms). **Never cite it as the fix's gain.** The verdict is TEST (§5.3), on cycles that chose nothing.
- The sizes: +0.158 pp is **31 extra decodes in 621 cycles** (WSJT-X 31.6 decodes per cycle on these cycles), about **1 per 20 cycles** (counted from the per-cycle rows, Architect, 06:1xZ). The spec's F-NEUTRAL prior (0.45) stands; a TEST F-GO needs CI_lo(NET) > 0 **and** CI_hi(ΔU) ≤ 0.
- Loose caps (50, 60) are clearly harmful on the corrected OSD: ΔU +0.68/+0.85 per cycle, NET −0.47/−0.60 pp, almost all in batch 2. 60 was the pre-2026-09-12 default.

## 5. Next (QA)

1. **TRAIN report** (HK-034 format of the earlier OSD-FIX reports): the §2 table from QA's own run of the script, validity, by-batch rows, wall time per arm, the OSD-accept `nhard` histogram (R6), FIX0 beside FIX24, the round-2 load note, and §3's sensitivity as a descriptive row. Copy the run folder to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\` (standing rule).
2. **TEST preparation, before any TEST decode:** (a) list **every** `artefacts/` folder with full cycle audio + a WSJT-X `ALL.TXT` (feedback rule 2026-10-03) and pick a 40 m night other than `20261004_1634`; if none, the fallback in §5.3 (residues {1, 2, 4, 6, 8, 9}) and say so in the limits; (b) ≥ 300 cycles, systematic, frozen `selection.json` + SHA committed; (c) arms REF and FIX(24), fresh process each, read-back of switch and `nhard` 24; (d) **V5 noise leg** at FIX(24) (200 NHARD-REP V2 noise WAVs, located and pinned); (e) V2′ probe at the new cap. Interleaving TEST is QA's choice; TEST stays **blind** until both arms are complete (it is the verdict: feedback rule 2026-10-08, "blind only where it protects a verdict").
3. Report "TEST ready" with the corpus choice and wall-time estimate. **TEST runs on the Captain's go in QA's window.**
4. R4: the code-default change to 24 (Developer, small second commit) and the station-config migration (QA, HK-035) come **after** TEST's verdict, not now.

## 5a. Addendum 2026-10-09 06:3xZ (by `date -u`): QA's TRAIN report and TEST preparation, checked before any TEST decode

- **TRAIN report** `report_train.md` (QA `32e2605f`): every §2/§3 figure reproduced exactly. One correction to §1 of this ruling: the longest wall outside round 2 is 667 s, not 661 s (now fixed above). **R6, descriptive:** corrected OSD 612 accepts on the first decode call vs 567 inverted; 35 corrected accepts at `nhard` 6–19, where the inverted OSD had none below 28 (chance-CRC words sit near the cap, as expected; real codewords can sit far below it).
- **TEST corpus ACCEPTED:** `20260930_1930`, 40 m, the same Voicemeeter B1 chain as TRAIN, WSJT-X FT-991A `ALL.TXT`; inventory of every `artefacts/` WAV folder done; direct-CODEC nights and other bands/eras rejected for stated reasons. The alternative B1 40 m night `20260922_2056` (2,882 cycles) is not preferred: fewer cycles, and nothing argues for it. The corpus's live build and `nhard` do not matter (the replay sets the decoder itself; feedback rule 2026-10-03).
- **Selection** `6dd0785c`, SHA-256(LF) `84b3d884…78b0`: TEST = 860 cycles (residues 0 and 5 of the frozen SUB-FEAS included list); every stamp has a WAV and ≥ 1 WSJT-X line; median 31 decodes per cycle (TRAIN's density). **Size: the full 860 (≈ 2.9 h) is the Architect's recommendation; the 430-cycle SAMPLE (≈ 1.5 h) meets the spec's ≥ 300 and is the Captain's alternative for time. Either is chosen before any TEST decode.** QA's power estimate: NET SE ≈ 0.026 pp at 860, 0.037 at 430; at half TRAIN's estimate (+0.079) CI_lo ≈ +0.027 vs +0.006.
- **Verdict code** `b5cee17d`: F-FAIL / F-GO / F-NEUTRAL match §5.3 exactly (read from source); blind-instrument guard tested; refuses before both arms are complete.
- **V5 noise leg at FIX(24): 0 false decodes on the 200 pinned noise WAVs** (pins re-hashed, DLL pin start = end, read-back 24 / switch 1) ⇒ PASS. ⚠️ HK-026: this leg read 0 at every setting ever tried (inverted 40 and 60, corrected 24), so it bounds gross failure only and cannot rank settings. OF7 (P 0.75): **HIT**, scored with that caveat.
- **TEST is ready.** It runs on the Captain's go in QA's window.

## 6. Predictions scored (ledger, at ruling time)

- **OF2** (some grid value has ΔU_TRAIN ≤ 0), P 0.70: **HIT**.
- **OF3** (`n*` = 40 or lower), P 0.55: **HIT**.
- OF4–OF7 wait for TEST and V5.
