# SPEC `S1-SNR-REPLAY` — does the OSD fix move OpenWSFZ's S1 SNR reading, or does the recorded audio? (offline cross-replay, CPU only)

- **To:** QA (owner). cc Captain. **From:** Architect. **Date:** 2026-10-09 10:25Z (`date -u`, HK-017).
- **Asked for by:** the Captain, in the Architect's window (2026-10-09): *"spec the early-decode freq. mismatch and the S1 SNR replay for QA"* (board open question; the early-decode spec is `2026-10-09-1025-architect-to-qa-spec-early-dup.md` on `arch/122-latency`). 🔴 The Captain dropped the +1.45 dB follow-up on 2026-09-29; **he has now reopened it himself**, so the scan reports' "does not reopen it" guard does not apply to this spec.
- **Branch:** `arch/osd-fix` (local, not pushed). Docs only: `git diff --stat -- src/ native/` is empty.
- **Cost:** offline, recorded audio on disk, CPU only, no station; about 30 cycles per audio set, minutes per cell. Ordinary PC load is fine (no timing is compared).
- **Why before the merge:** if the fix changed the SNR the product reports, that would matter before it reaches `main`. The Architect expects it does not (§5), but nothing on file separates the build from the audio.

## 0. What is on file (HK-018)

| live run | build / DLL | OpenWSFZ S1 mean bias | WSJT-X | scan S1 `g_db` / `resid_db` (OpenWSFZ, median of 30) | daemon audio |
|---|---|---:|---:|---|---|
| 2026-09-29 OFF | `0d6b1937`, DLL `5a6a4dc0…` | +1.45 | — | (QA reads it, if the scan ran) | `artefacts/_rr_subfeas_off_daemon_output/cycle-audio/` |
| 2026-10-02 / 10-03 | `cddd7e34`, DLL `ee00d118…` | +0.92 / +0.85 | — | −1.86 / −9.75; −1.68 / −9.19 | `artefacts/_rr_baseline194_daemon_output/cycle-audio/` (both runs) |
| **2026-10-04** | `main` `766f9cc2`, DLL `2fa6d993…` | **+0.88** | +0.85 | −1.63 / −9.70 | `artefacts/_rr_main766f9cc2_daemon_output/cycle-audio/` |
| **2026-10-08** | fix `3276573b`, DLL `2029b080…82bb` | **+1.48** | +0.82 | −1.68 / −9.84 | `artefacts/_rr_fix3276573b_daemon_output/cycle-audio/` |

S1 = 30 rows in 30 cycles per run (`truth.csv`, scenario `S1`, `cycle_utc`). Bias values from `qa/rr-study/trend.csv` (`bias_snr_owsfz`), WSJT-X from the reports.

**Observation (descriptive):** the scan's chain gain and residual for OpenWSFZ's S1 slots are about the same in every run (`g_db` −1.63 to −1.86, `resid_db` −9.19 to −9.84), while the bias jumps by about 0.6 dB. Whatever moves the SNR reading is something the scan's level metrics do not see. WSJT-X decodes the same played audio and does not move.

## 1. Design: audio × DLL cross-replay

Replay the S1 cycles of each audio set through each DLL, with the harness QA uses for OSD-FIX (Replay81-family, mode `two1`, subtraction ON, threads as in TRAIN, fresh process per cell, DLL SHA pinned at start and end, switch and `nhard` read back).

| cell | audio | DLL | `nhard` / switch | role |
|---|---|---|---|---|
| **A04·M** | 10-04 | `2fa6d993…` (`766f9cc2`) | 40 / n.a. | validity (its own live run) |
| **A08·F** | 10-08 | `2029b080…82bb` | 40 / 1 | validity (its own live run) |
| **A04·F** | 10-04 | fix | 40 / 1 | cross |
| **A08·M** | 10-08 | `766f9cc2` | 40 / n.a. | cross |
| A0929·M, A0929·F | 09-29 OFF | both | 40 | descriptive (a second "high" run) |
| A1002·M, A1002·F | 10-02 (and 10-03 if separable) | both | 40 | descriptive (a second "low" run) |
| A08·F24 | 10-08 | fix | **24** / 1 | descriptive (the setting that will ship) |

Per cell: per S1 row (matched to truth by text and ±4 Hz, the harness's own rule, inside the function, HK-037): decoded yes/no and reported SNR (integer dB); mean bias = mean(reported − true) over decoded rows. Output numeric only.

## 2. Rows (mechanical; predicates as code, committed before the first replay)

**Validity (any FAIL ⇒ no verdict; QA reports the differences and the Architect rules):**

| row | predicate | basis (HK-038) |
|---|---|---|
| SV1 | DLL pin equal at start and end of every cell; read-back as intended | as OSD-FIX |
| SV2 | **A04·M reproduces the 10-04 live S1 OpenWSFZ rows** (from `S1_matched.csv`): same rows decoded, **same SNR on every row** | replay of captured cycle audio reproduced live counts exactly before (S3c separating replay, 2026-10-05: 32/32, 17/17, 16/16). If a replay of a run's own audio through its own DLL does not give its own live SNR, the replay is not the live path for this quantity and nothing below is readable |
| SV3 | **A08·F reproduces the 10-08 live S1 OpenWSFZ rows**, same predicate | as SV2 |

**Verdict rows (exclusive, first match wins):**

| row | predicate | meaning |
|---|---|---|
| **SR-BUILD** | in A04 **or** A08, ≥ 1 row decoded by both DLLs has a **different SNR** under the fix than under `766f9cc2` | the fix changes the SNR the product reports ⇒ Architect rules before the merge is recommended |
| **SR-AUDIO** | 0 such rows in both A04 and A08, **and** mean bias(A08) − mean bias(A04) ≥ **0.40 dB** under **both** DLLs | the build is cleared; the 0.6 dB lives in the recorded audio (upstream of the decoder) |
| **SR-NEITHER** | 0 such rows, and the A08 − A04 difference is < 0.40 dB under either DLL | contradicts SV2/SV3 unless the live readings came from rows the replay does not reproduce ⇒ Architect rules |

**Where 0.40 dB comes from (HK-038):** the live difference is +1.48 − 0.88 = +0.60 dB, today's two runs. 0.40 is two-thirds of it, so that rounding on 30 integer SNRs (one row changing by 1 dB moves the mean by 0.033 dB) cannot reach it by chance, while a reproduced effect clears it. The **"0 rows differ"** predicate needs no tolerance: for a row decoded by both DLLs on the same PCM, the SNR is computed after the decode from the same audio and candidate; the fix changes only which LLR sign the OSD receives. If any row differs, the Architect wants to see why, whatever the size.

**HK-025(k):** SR-AUDIO can be reached by a replay that ignores the DLL (both cells identical by construction). SV1 (pins differ between M and F cells) and the OSD-FIX A-SIGN′ record show the two DLLs differ; QA also reports the count of S1 rows whose **decode** (not SNR) differs between DLLs (expected 0 or close to it, since S1 is strong single signals; it is not a row).

## 3. Descriptive, after the verdict (no bars)

- The full audio × DLL bias table, including 09-29, 10-02/03 and A08·F24.
- Per audio set: the distribution of per-row (reported − true), not only the mean (is it a shift of every row, or a few rows by several dB?).
- Per audio set, from each run's own `captured-audio-scan` output where it exists: S1 `g_db`, `resid_db`, and any noise-floor or in-band level the scan already records (HK-027: use what the instrument records before adding a measurement). If SR-AUDIO, these show whether any recorded metric tracks the bias.
- WSJT-X's live S1 bias per run beside it (its audio is a different capture of the same playback).

## 4. What each outcome leads to

- **SR-AUDIO:** the fix is cleared for SNR reporting; the open question moves to the capture chain (OpenWSFZ's input path only, since WSJT-X does not move). Whether to chase it is the Captain's (he dropped it once on 2026-09-29). Not a merge blocker.
- **SR-BUILD:** the Architect reads the differing rows and rules before recommending the merge.
- **SR-NEITHER / any validity FAIL:** the Architect rules; nothing is cited.

## 5. Predictions (blind; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| SR1 | SV2 and SV3 pass | 0.80 | C |
| SR2 | verdict SR-AUDIO | 0.75 | H |
| SR3 | verdict SR-BUILD | 0.10 | H |
| SR4 | the 09-29 OFF audio reads high (≥ +1.2 dB) under both DLLs | 0.75 | H |

⚠️ SR2 is not 0.90 because the scan's level metrics do **not** move with the bias (§0), which weakens the plain "the audio was different" story; something in the audio that the scan does not measure, or a live-path effect the replay does not reproduce (SV2/SV3 would then fail), are both open.

## 5a. Amendment 1 (2026-10-09 10:2xZ by `date -u`, before any build or run): QA's review accepted

QA (`qa-ee`) accepted the spec; the Architect accepts all of its points.

1. **The cross is audio × BUILD, not audio × DLL.** The fix commit also changes managed code (the P/Invoke for the switch), so one harness cannot swap DLLs. The M cells run the **NHARD-REP harness** (DLL `2fa6d993…`; QA checked with `git diff` that `src/OpenWSFZ.Ft8` is unchanged between `766f9cc2` and `be3cc5ac`), the F cells run the **osd-fix harness** (DLL `2029b080…82bb`). **SV1 pins both harness binaries and both DLLs.** This is the merge question anyway (the whole build, not the DLL alone). §1's "DLL" column reads "build".
2. **SV4 (added): same-build repeat.** A04·M runs **twice**, in fresh processes; the decoded rows and SNRs must be identical. If not, the tolerance-free "0 rows differ" predicate is **withheld** (it could fire on replay nondeterminism, HK-026) and the Architect rules.
3. **SR-NEITHER is unreachable when SV2 and SV3 pass:** A04·M then reads +0.88 and A08·F +1.48 exactly, so with 0 differing rows the gap is +0.60 under both builds. The 0.40 clause is kept (it guards a partial-validity reading) but the verdict is effectively SR-BUILD vs SR-AUDIO. Noted, not changed.
4. **Join:** the harness's `outcomes.csv` has no text, so S1 rows join to the live `S1_matched.csv` by cycle stamp and frequency within 4 Hz (S1 is one signal per cycle at 1500 Hz). A wrong-text decode at the right frequency would count as decoded; QA reports any decode at another frequency separately. Accepted.
5. **Data on disk:** 30 of 30 S1 WAVs for 10-04, 10-08, 09-29 OFF, and 10-02 and 10-03 separately (stamps from `261002_231600` and `261003_011645`, no overlap). Cost about 11 cells, about 35 min CPU, no station.

## 6. Limits

S1 is 30 synthetic rows per run. Integer SNR. Replay, not live: SV2/SV3 are the guard. The 09-29 and 10-02/03 audio sets have no validity row (their own DLLs are not part of the design), so they are descriptive only.
