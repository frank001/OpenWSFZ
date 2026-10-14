# S1-SNR-REPLAY: as coded the verdict row is SR-BUILD, on one row that is a join artefact; read text-aware, the build moves no SNR and the 0.6 dB lives in the audio

- **From:** QA. **To:** Architect, cc Captain. **Date:** 2026-10-09, run 10:34Z to 10:37Z by `date -u` (CPU only, no station); the diagnosis shortly after. **Go:** the Captain, in QA's window ("Start the replay").
- **Spec:** `qa/rr-study/2026-10-09-1025-architect-to-qa-spec-s1-snr-replay.md` with amendment 1 (`arch/osd-fix`). Script `qa/rr-study/s1-snr-replay/s1_snr_replay.py` (committed before any replay, `d8263907`); numbers `s1_snr_replay_result.json`, `s1_text_aware.json`.
- **Builds (two pinned harnesses; the cross is audio x BUILD):** **M** = NHARD-REP harness, DLL SHA-256 `2fa6d993…f365`, Replay81 `4a9cf533…79a8` (766f9cc2's decoder: `src/OpenWSFZ.Ft8` is unchanged between 766f9cc2 and be3cc5ac); **F** = osd-fix harness, DLL `2029b080…82bb`, Replay81 `c2ff1981…5843` (the fix, `3276573b`). Mode `two1`, subtraction ON, threads 8, `nhard` 40 (24 in the last cell), fresh process per cell, the cycle before the first S1 cycle as warm-up. 12 cells, each 30 S1 cycles (selection SHA-256 per audio set in `selection_manifest.json`).
- **Join (accepted in amendment 1):** by cycle stamp and frequency within 4 Hz, text-free. **Tie rule (mine, not in the spec): among decodes within 4 Hz the one nearest the true frequency, then the lowest SNR.** That tie rule is the cause of the row below.

## Disclosures (read first)

1. **The first `rows` run was WITHHELD by my own bug:** `S1_matched.csv` also holds OpenWSFZ decodes from the cycles of every other scenario under `scenario_id` S1, and my live-row loader did not restrict itself to the 30 S1 stamps, so SV2/SV3 listed S7/S8 stamps as "differing". Fixed (restricted to the S1 stamps), a test added, committed; the replay cells were not re-run (they do not depend on it).
2. **The verdict row below is the pre-registered rule applied as coded.** The text-aware reading after it is **post-data** and a separate pass (raw `ft8_decode_all`, first decode call only, not the live path). The Architect rules which stands.

## Validity

| row | result |
|---|---|
| SV1 | PASS: all 12 cells rc 0, DLL and harness pins equal at start and end and equal to their build's pin, `nhard` read back (40; 24 in A08.F24) |
| SV2 | **PASS:** A04.M reproduces the 10-04 live S1 OpenWSFZ rows: 30 of 30 decoded, the same integer SNR on every row (mean bias +0.883, live +0.88) |
| SV3 | **PASS:** A08.F reproduces the 10-08 live S1 rows: 30 of 30, same SNR on every row (+1.483, live +1.48) |
| SV4 | **PASS:** A04.M run twice in fresh processes: identical decoded rows and SNRs |

## Verdict as coded: **SR-BUILD** (one row)

A04: 0 rows differ between M and F. **A08: 1 row differs, stamp `261008_194430` (S1 part 4 trial 2, true SNR +0.4 dB): M reports −18 dB, F reports +2 dB** (the live 10-08 value was +2). Mean bias: A08.M +0.817, A08.F +1.483.

## What that row is (post-data, text-aware)

For the cycle `261008_194430` each build's native decode returns (frequency, SNR, whether the text equals the truth text):

| build | decodes of the cycle |
|---|---|
| M (766f9cc2) | 1500.0 Hz, **+2 dB, truth text**; **1500.0 Hz, −18 dB, a different text** |
| F (fix) | 1500.0 Hz, +2 dB, truth text (only) |

**The decode with the truth text has the same SNR (+2) under both builds. M returns a second, wrong-text decode at the very same frequency; my tie rule (lowest SNR) picked it.** So the row differs because the old build outputs an extra false decode at the signal's own frequency and the fix does not, not because the fix changed an SNR. Run over all 150 S1 cycles (5 audio sets × 30) through both DLLs with the text compared inside the function:

| audio set | truth-text decodes M / F | **rows whose truth-text SNR differs M vs F** | bias M = F | wrong-text decodes M / F (cycles) |
|---|---|---:|---:|---|
| A0929 (09-29 OFF) | 30 / 30 | **0** | +1.450 | 3 / 1 |
| A1002 (10-02) | 30 / 30 | **0** | +0.917 | 2 / 1 |
| A1003 (10-03) | 30 / 30 | **0** | +0.850 | 4 / 0 |
| A04 (10-04, live +0.88) | 30 / 30 | **0** | +0.883 | 1 / 1 |
| A08 (10-08, live +1.48) | 30 / 30 | **0** | +1.483 | 1 / 2 |

(The raw first-call bias equals the replay harness's in every audio set, so this pass reproduces the harness.) **Read text-aware: 0 rows differ in all five audio sets; the bias is the same under both builds in each set; A08 − A04 = +0.600 dB under both builds, which is above the 0.40 bar ⇒ the pre-registered SR-AUDIO row would fire.** A08.F24 (the setting that will ship) reads +1.483, identical to F at 40.

## Descriptive

- **The shift is uniform, not a few rows:** on the same 30-row ladder, the 10-08 audio reads **+1 dB on 18 rows and equal on 12, never lower**, against 10-04 (sum +18 dB over 30 rows = +0.60 dB, each row quantised to an integer). The 09-29 audio does the same (17 higher, 13 equal, 0 lower, +17). 10-02 and 10-03 are within ±1 of 10-04 (3 higher / 2 lower, sum +1; 2 higher / 3 lower, sum −1).
- **Two high nights, three low:** bias 09-29 +1.45, 10-02 +0.92, 10-03 +0.85, 10-04 +0.88, 10-08 +1.48. SR4 (09-29 OFF reads ≥ +1.2 under both DLLs): +1.45 under both.
- Reported − true per row (min / median / max, F cells): A0929 +0.9 / +1.45 / +2.0; A04 −0.1 / +0.9 / +1.5; A08 +0.9 / +1.5 / +2.0.
- **A side finding (raw first call, not the live path):** the old build returns wrong-text decodes in S1 cycles more often than the fix (11 against 5 over the 150 cycles), one of them at the true signal's own frequency. The raw call is before the product's plausibility filter and text-dedup, so this is not a live false-decode rate.
- WSJT-X's live S1 bias per run is in each run's own report; its audio is a different capture of the same playback.

## Limits

30 synthetic rows per set, integer SNR, replay not live (SV2/SV3 are the guard and pass). The text-aware table is a raw C-ABI first-call pass, not `two1`. The 09-29 and 10-02/03 sets have no validity row of their own. Whatever shifts OpenWSFZ's reported SNR by about 0.6 dB on two of the five nights lives in the recorded audio, upstream of the decoder; the scan's `g_db` / `resid_db` did not see it, and this replay does not say what it is.

## For the Architect

Rule between (a) the verdict as coded, SR-BUILD, with the finding that its one row is a removed false decode and (b) the text-aware reading, SR-AUDIO. My view: the SNR of every true decode is identical across builds, so nothing here argues against the merge on SNR grounds; the join's tie rule should have preferred the truth-text decode, which a text-free join cannot do. No threshold, row or arm was changed after seeing the data; the one code change was the live-row filter (disclosure 1).
