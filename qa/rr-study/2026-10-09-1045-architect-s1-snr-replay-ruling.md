# RULING — `S1-SNR-REPLAY`: the verdict row as coded is SR-BUILD; read, it is the old build's extra false decode, not an SNR change. **The fix does not move the SNR OpenWSFZ reports; no SNR objection to the merge.**

- **To:** QA (owner). cc Captain. **From:** Architect. **Date:** 2026-10-09 10:45Z (`date -u`, HK-017).
- **Rules on:** QA's `report_s1_snr_replay.md` (`4f866f65` on local `qa/osd-fix`; run 10:34–10:37Z on the Captain's "Start the replay"), the cell outputs in `qa/rr-study/results/2026-10-09-s1-snr-replay/`, against spec `2026-10-09-1025-architect-to-qa-spec-s1-snr-replay.md` + amendment 1 (`67408dec`).
- **Branch:** `arch/osd-fix` (local, not pushed). Docs only: `git diff --stat -- src/ native/` is empty.

## 1. Validity: all PASS

SV1 (12 cells rc 0, both harness and DLL pins held), **SV2** (A04·M reproduces the 10-04 live S1 rows, 30/30, same SNR on every row, +0.883), **SV3** (A08·F reproduces 10-08, +1.483), **SV4** (the A04·M repeat is identical). The replay is the live path for this quantity.

## 2. The verdict row as coded: SR-BUILD, on one row. It stays recorded as SR-BUILD

One row differs between builds: stamp `261008_194430` (S1 part 4, true +0.4 dB), M −18 dB, F +2 dB (live +2). A04: 0 rows differ.

The spec's consequence of SR-BUILD is "the Architect reads the differing rows and rules". 🛑 **It is not relabelled SR-AUDIO** (standing prohibition: never re-read a closed gate with a better metric). The text-aware pass below is post-data and descriptive.

## 3. The Architect's reading of the row (checked in the raw `outcomes.csv`, numeric fields only)

| cell | decodes at that stamp (batch, index, Hz, DT s, SNR dB) |
|---|---|
| A08·M (old build) | `b1,0,1500,0.1,+2` and **`b1,1,1500,2.3,−18`** |
| A08·F (fix) | `b1,0,1500,0.1,+2` |

The real decode is **+2 dB in both builds**. The old build also returns a second decode at the same 1500 Hz, at DT 2.3 s and −18 dB, which QA's text check shows is a **different text**: the profile of a chance-CRC accept by the sign-inverted OSD (weak, off-timing). The text-free join needed a tie rule the spec did not give (mine to have given); QA's "lowest SNR" picked the false decode. **The row differs because the old build emits an extra false decode, not because the fix changes any SNR.** It is a difference in the fix's favour.

**Ruled:** for every true decode in the cross-replay, the fix and `766f9cc2` report the **same SNR**. The fix is **cleared** on SNR reporting.

## 4. Descriptive (post-data; QA's text-aware pass, raw first decode call, text compared inside the function)

- Truth-text SNR differs between builds on **0 rows in all five audio sets** (150 cycles). Bias identical across builds per audio set: **09-29 +1.45, 10-02 +0.92, 10-03 +0.85, 10-04 +0.88, 10-08 +1.48**; A08·F24 +1.483 (the shipping cap does not move it either).
- **The shift lives in the recorded audio and is uniform:** against 10-04, the 10-08 audio reads +1 dB on 18 of 30 rows and equal on 12, never lower; 09-29 likewise (17 / 13 / 0). Two recordings read high, three low, regardless of build. The scan's level metrics (`g_db`, `resid_db`) do not track it. **What in the audio causes it is open** and upstream of the decoder (OpenWSFZ's capture path; WSJT-X's capture of the same playback does not move). Whether to chase it is the Captain's (he dropped it once on 2026-09-29).
- **Side finding (raw call, not the live path):** across the 150 S1 cycles the old build returns 11 wrong-text decodes, the fix 5. Consistent with TEST's −19 % not-confirmed. Not a row.

## 5. QA's disclosure, accepted

The first rows run was withheld by QA's own loader bug (`S1_matched.csv` carries every scenario's OpenWSFZ decodes under `scenario_id` S1); fixed with a test, cells not re-run (the bug was in the reader, not the replay). No action.

## 6. Predictions (ledger), scored on the verdict row as coded

| # | prediction | P | result |
|---|---|---:|---|
| SR1 | SV2 and SV3 pass | 0.80 | ✅ HIT |
| SR2 | verdict SR-AUDIO | 0.75 | ❌ MISS as coded (one-row SR-BUILD from a join tie); the substance (audio, not build) held |
| SR3 | verdict SR-BUILD | 0.10 | ✅ HIT as coded, for a reason the prediction did not mean |
| SR4 | 09-29 OFF audio reads ≥ +1.2 dB under both builds | 0.75 | ✅ HIT (+1.45) |

Lesson (mine): a text-free join needs a tie rule written before the data, and "0 rows differ" is only as sharp as the join beneath it.

## 7. Next

Nothing for QA on this spec. For the merge, the board's remaining open item is EARLY-DUP A1 (two S4 plays on `main`, station).
