# First full S1-S8 battery on Linux (`sol`): result and one open FAIL row (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-11 04:50Z (`date -u`). **Go:** the Captain, in the QA window: "try to get the full S1-S8 running on sol. you are in control of both applications and their data".
- **A NEW SERIES, not comparable with the Windows sweeps** (different platform, CPU and audio chain; WSJT-X built by QA from source). Run folder on this PC: `qa/rr-study/results/2026-10-11-64246e4-LINUX-sol/` (run on `sol` as `2026-10-11-64246e4`; analysis commit `64246e40`; harness `qa/refset`, local, not pushed).

## What ran

| item | value |
|---|---|
| Battery | S1, S1b, S2, S3, S4, S5, S7, S8, S3c; played 02:31:11Z to 04:25:34Z (1 h 54 min), detached supervisor, every PRECHECK check passed |
| OpenWSFZ | `main` `76aa48cd`, v0.57, shim 20260060, `libft8.so` SHA-256 `e8132650310e0fbb427540351d7d01b1ca258741e87771ec9cc24e3840c64ed0`, `nhard` 24, subtraction ON, 8 threads (read back) |
| WSJT-X | **2.7.0, built from the verified source tarball on `sol`** (SHA-256 `3788f5df636af792514609ec2b4abe58477aa5f0ad32cb826424866fc21cec93`; conda-forge Qt 5.15, gfortran 13.4, hamlib 4.6.1); profile `rr`: NDepth 3, no AP, decode keys whitelisted from the station ini |
| Audio | synthesiser -> `aplay` -> onboard codec output -> codec `Stereo Mix` digital loopback -> ALSA `dsnoop` -> both programs read the same stream (`rr_in`); Master 40 % (-37.5 dB) |
| Clock | chrony, system 0.5 ms from NTP |
| Why not WSJT-X 3.x | its new `callok` rejects every callsign starting with Q; the synthetic truth set is Q-prefix only (jt9 3.0.2: `K1ABC`/`DL1ABC` decode, `Q1ABC` never, even at +20 dB) |

## Result (report.md, analyser verdict **FAIL** on exactly one row)

| row | Linux run | Windows sweeps (trend.csv, 2026-10-02..10-08) |
|---|---|---|
| S1 OpenWSFZ SNR bias | **-3.75 dB, FAIL (bar +-2)** | +0.85, +0.88, +1.48 dB |
| S1 WSJT-X SNR bias | +0.82 dB, PASS | not in the trend file |
| S1 %GR&R / ndc | 11.2 % MARGINAL / 3 | 0.14 to 0.41 % / 22 to 37 |
| S2 %GR&R, ndc | 0.0 %, 1,576 PASS | |
| S3 %GR&R, ndc | 1.0 %, 14 PASS | |
| Kappa vs truth (OWS / WSJT-X / between) | 0.909 / 0.955 / 0.954 PASS | OWS 0.909 in every Windows row |
| S5 false positives (OWS, WSJT-X) | 0/120, 0/120; Gate A-W 0/480 UB 0.62 % PASS; Check B 0/60 each PASS | |
| S4 recovery OWS / WSJT-X | 88.9 % / 94.4 % (specificity 100 % both) | |
| S1b (-24..-15 dB) decode rate OWS / WSJT-X | 8.3 % / 66.7 % | not read |
| S7 recovery | OWS 83.3 %, WSJT-X 94.4 % | not read |
| S8 | 91.7 % both | |

The S1 %GR&R is dominated by reproducibility (11.1 % of the variance), which is consistent with the 4.6 dB gap between the two appraisers' SNR readings: the same effect, not a separate finding.

## The FAIL row, diagnosed in three steps (all on S1, 30 trials, ~10 min each)

1. **Repeat at the same level:** OWS -3.92 dB, WSJT-X +0.85 dB. The reading is stable to about 0.2 dB.
2. **Playback level raised by 19.5 dB** (captured rms 0.0104 -> 0.187, no clipping): OWS **-3.85 dB**, WSJT-X +0.78. **Not a level effect.**
3. **Same audio, two decoders:** the 30 S1 cycles OpenWSFZ recorded on `sol` were decoded on this PC by the **Windows** decoder (`libft8.dll` `2029b080...`, shim 20260060) through the same managed path: reported SNR minus true SNR **-3.75 dB; the difference to the Linux daemon is 0.00 dB, maximum 0 dB, on all 30 cycles** (files in `diag-same-audio-two-decoders/`). **The decoder is platform-identical; the -3.75 dB is a property of the audio the chain delivers.**
4. The capture spectrum of S1's wideband noise is flat to 5 kHz and rolls off to -15 dB at 5-5.5 kHz and -36 dB at 5.8-6 kHz, so the chain does not alias noise down; **cause not found**. Candidates left (untested): the shape of the noise spectrum towards 6 kHz (OWS estimates its noise floor over the whole band; WSJT-X does not read it the same way), the codec's response, the ALSA `plug` rate converter (linear; the better `samplerate` plugin is not installed on `sol`).

## Process findings (for the standing procedure)

1. `run_study_detached` forwards `--wsjt-all-txt` only if that file exists when the battery STARTS. On a clean WSJT-X profile it does not, and `run_study.py` then looks for the Windows default path and stops after the last scenario (the playback was complete; recovered with `qa/rr-study/linux/post_run_linux.py`, same functions, same arguments). Fix: pre-create an empty `ALL.TXT`, or forward the path unconditionally.
2. `run_study.py` hard-codes `wsjt-version.txt` as "WSJT-X 2.7.0 (inferred from binary date 2025-02-04)" for EVERY run. For this run QA overwrote it with the real build string. Your endorsed PRECHECK row (record the WSJT-X version, refuse a Q-prefix battery at >= 3.0) will replace it.
3. A fresh headless WSJT-X profile decodes nothing at 1500 Hz unless `[WideGraph]` `PlotWidth`/`BinsPerPixel`/`StartFreq` are set (decode window derived from the waterfall width). Documented in `qa/rr-study/linux/README.md`.

## Limits

One run, one night of synthetic audio, a different audio chain than the Windows series; the Linux series needs its own baseline (repeat runs) before any trend is read. QA's own reading: the Linux layer works and is reproducible; the SNR-bias row is a chain issue to be understood (or accepted as that chain's offset) before this series is used as a gate.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
