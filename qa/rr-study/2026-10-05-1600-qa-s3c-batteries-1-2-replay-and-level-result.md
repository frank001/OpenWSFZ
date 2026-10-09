# S3c batteries 1-2 replay and in-band level: result (Architect ruling 2026-10-05 section 4b, S3Y1-3)

**From:** QA. **To:** Architect, cc Captain. **Date:** 2026-10-05, Captain's go in QA's window ("go"). `src/`/`native/` untouched.
Committed BEFORE any run: harness unchanged (`db2da962`), replay driver and level predicate v1 (`4211342e`), predicate v2 (`64ed720c`), all on
`qa/main-with-sampler`, local. Outputs `artefacts/20261005_s3c_replay/` (gitignored; planted synthetic texts and numbers only).

## 1. Replay of batteries 1 and 2 (same harness, fresh process per arm, flag ON, nhard 40, both batches)

Audio `_rr_baseline194_daemon_output/cycle-audio` (261003_010600-010845 and 261003_030645-030930). DLL pins checked at start and end of
every process (`ee00d118…990e4c` for `cddd7e34`, `2fa6d993…f365` for `766f9cc2`). Scored by `s3c_score` against each battery's own playback log.

| Battery | Live count at E -2.00 | `cddd7e34` replay | `766f9cc2` early ON replay | other parts (both arms) |
|---|---:|---:|---:|---|
| 1 (2026-10-02) | 17 | **17** | **17** | E-1.75 32, L+2.75 32, L+3.00 0 |
| 2 (2026-10-03) | 16 | **16** | **16** | E-1.75 32, L+2.75 32, L+3.00 0 |
| 3 (2026-10-04), from the earlier replay | 32 | 32 | 32 | E-1.75 32, L+2.75 32, L+3.00 0 |

Reading table (ruling 4b), applied as code: both arms agree within 2 on each battery and both are <= 24 on each battery, so **AUDIO**.
**S3Y1 HIT** (arms identical on both batteries). **S3Y2 HIT** (Audio on both). The replay reproduces the live count exactly in all three
batteries and on both builds, so the decoder is deterministic on these recordings and the "live path" class (state after S1-S8, live timing)
is not what separates battery 3 from batteries 1 and 2.

## 2. In-band level (read-only, no decode)

| Battery | all 64 early signals: median dB [IQR] | 32 S3c-E50 signals: median dB [IQR] | signal / noise window, dBFS (medians) |
|---|---|---|---|
| 1 | +8.63 [+8.28, +8.86] | +8.68 [+8.33, +9.00] | -30.41 / -39.11 |
| 2 | +8.61 [+8.30, +8.87] | +8.69 [+8.34, +9.00] | -30.42 / -39.09 |
| 3 | +8.61 [+8.25, +8.87] | +8.66 [+8.32, +8.97] | -30.41 / -39.07 |

Gap, battery 3 minus the pooled median of batteries 1 and 2: **-0.02 dB** (all 64), -0.03 dB (E50). **S3Y3 MISS** (predicted >= +0.5 dB).
Level, in this band and measured this way, is the same to within 0.05 dB: it is NOT what separates the batteries.

### DEVIATION from the ruling's wording, stated and for you to rule on
The ruling asks for the power "in the idle cycle that follows at the same frequency". The design's early block is (idle, planted) x 4, so the idle
cycle precedes each planted cycle, and, more importantly, **the "idle" cycles carry no noise**: about 78 % of their samples are exact zeros (RMS 0.07
against 0.16 in planted cycles) in all three batteries, because the playback is silent there and only its last ~3.3 s holds the early-armed audio.
Predicate v1 (the adjacent idle cycle) FAILED on its first run with a division by zero; that run produced no number. Predicate v2 (committed before any
level number was seen) uses the same planted cycle's own post-transmission tail (after the 12.64 s transmission plus 0.2 s, at least 2 s) as the noise
reference at the same frequency. The instrument was checked first (noise alone reads -0.03 dB mean, max |x| 0.56; a known tone reads its theoretical
level within 1 dB and rises monotonically over a span of 12.7 dB). The level it reports is signal-plus-noise over noise in a 50 Hz band, not a calibrated SNR.

## 3. Exploratory, NOT pre-registered (post hoc; no reading drawn)
Cross-correlating the same cycle across batteries (identical source audio) gives the capture lag: it wanders by about +-20 ms from cycle to cycle
(for example -154 to +261 samples at 12 kHz, 1 sample = 0.083 ms) with mixed signs, between batteries 1 and 2 as much as between either and 3.
So there is no systematic timing shift of battery 3, and a random one of that size is present in the pair that scores alike. It does not
explain the movement, and I do not claim it excludes a timing effect at a finer level than this.

## 4. What this leaves
Established: the movement is in the recording, not in either build, not in the live daemon's state, not in the early path, and not in the in-band
level. Not established: which property of the recording moved 15 of 32 signals across the E -2.00 threshold. Open candidates, none tested: the noise
realisation the chain delivered (capture-chain noise or dither differences at the threshold), a sub-band or spectral-shape difference outside +-25 Hz,
finer timing or drift within a cycle, or the clipping of the cut onset. The guard (`r_ref`, `k*`) is untouched and ruling section 5 stands.
