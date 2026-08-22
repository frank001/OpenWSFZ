# ft8-decoder Specification

## Purpose
Specifies the behavioural requirements for the OpenWSFZ FT8 decoder component. The decoder accepts a 15-second 12 kHz mono PCM buffer and returns all decodable FT8 messages present in that window. From p12, decoding is delegated to the `kgoba/ft8_lib` native library via the `ft8lib-interop` layer; see that spec for P/Invoke and ABI requirements.

## Requirements

### Requirement: FT8 decode cycle completes within the 15-second budget

The FT8 decoder SHALL complete a full decode cycle — including all time-domain analysis, sync candidate detection, LDPC decode, iterative signal subtraction, and message unpacking — within **13 seconds** of wall-clock time on a single modern CPU core, leaving at least 2 seconds headroom before the next cycle window is delivered by the framer.

#### Scenario: Decode completes within budget on a multi-signal fixture

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a real off-air PCM buffer containing multiple simultaneous FT8 signals
- **THEN** the method SHALL return within 13 000 ms on a development machine and within 30 000 ms on a CI runner (allowing for runner variance)

#### Scenario: Decode does not stall the cycle pump on a live band

- **WHEN** a continuous stream of 15-second PCM windows is delivered by `CycleFramer` on a band with up to 30 simultaneous FT8 transmissions
- **THEN** the decode pump SHALL complete each window before the second subsequent window arrives (i.e., at most one window queued at any time during steady-state operation)

---

### Requirement: Decode diagnostic log reports elapsed time per cycle

The decode cycle log line SHALL include the wall-clock elapsed time in milliseconds so that performance regressions are visible to the operator without external instrumentation.

#### Scenario: Elapsed time appears in the cycle log line

- **WHEN** `Ft8Decoder.DecodeAsync` completes a decode cycle
- **THEN** the logged Information message SHALL include an `elapsed` field in milliseconds, e.g. `elapsed=2341 ms`, alongside the cycle summary counters

---

### Requirement: Real off-air signal recovery (G6 gate) — all three reference platforms

The FT8 decoder SHALL correctly decode real off-air FT8 transmissions captured from the 40 m band on **all three reference platforms** (Windows x64, Linux x64, macOS ARM64), per **NFR-001**. Given a 15-second PCM window from the committed WAV fixture corpus, the decoder SHALL recover the signals identified by WSJT-X for the same recording.

From p15, the answer-key subsets for the three committed fixture WAVs SHALL include all signals decoded by WSJT-X at SNR ≥ 0 dB (previously only ≥ +6 to ≥ +14 dB). The expanded answer keys reflect the medium-SNR signals now recoverable via the second decode pass.

The G6 gate CI check SHALL execute and pass on all three matrix legs (`windows-latest`, `ubuntu-latest`, `macos-latest`). A skip or absence on any leg is a gate failure. The use of `[WindowsOnlyFact]`, `[WindowsOnlyTheory]`, or any equivalent platform-conditional test skip attribute on G6 tests is a violation of this requirement.

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture (Windows)

- **WHEN** `Ft8Decoder.DecodeAsync` is called on Windows with a PCM buffer from the committed fixture corpus (`260528_235745`, `260529_000030`, or `260529_000200`)
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file (expanded to SNR ≥ 0 dB from p15)

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture (Linux)

- **WHEN** `Ft8Decoder.DecodeAsync` is called on Linux x64 with a PCM buffer from the committed fixture corpus
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file

#### Scenario: Decoder recovers the strongest signals from a busy-band fixture (macOS)

- **WHEN** `Ft8Decoder.DecodeAsync` is called on macOS ARM64 with a PCM buffer from the committed fixture corpus
- **THEN** the returned `DecodeResult` list SHALL contain every message listed in the fixture's `.expected.txt` answer-key file

#### Scenario: Decoder produces no decode for a silent buffer

- **WHEN** `Ft8Decoder.DecodeAsync` is called with 180 000 samples of silence (all zeros)
- **THEN** the method SHALL return an empty list without throwing

---

### Requirement: Reported SNR is within ±2.0 dB of true SNR

The FT8 decoder SHALL report SNR values whose mean bias, measured over the R&R study S1 scenario (10 SNR parts × 3 trials = 30 observations, SNR range −12 to +15 dB), does not exceed ±2.0 dB relative to the true synthesised SNR. This requirement applies to both reference appraisers (OpenWSFZ and WSJT-X). Bias is defined as `mean(reported_snr − true_snr)` across all 30 matched observations.

From the `fix-d004-local-noise-floor` change, the SNR formula uses a **per-signal local noise floor** (`compute_local_noise_floor_db` — histogram median of 32-bin sideband windows on each side of the decoded signal's 8-tone span) rather than the prior global waterfall median. The S1 R&R run is a required post-implementation validation gate for this change. If the bias shifts outside ±2.0 dB after the fix, the −26.5 dB bandwidth constant SHALL be recalibrated before merging.

#### Scenario: S1 R&R bias is within threshold for OpenWSFZ

- **WHEN** the R&R study S1 scenario is run with the committed synthesiser and harness against an OpenWSFZ build under test
- **THEN** the mean SNR bias for OpenWSFZ SHALL be within ±2.0 dB of zero across all 30 matched observations

#### Scenario: S1 R&R bias is within threshold for WSJT-X

- **WHEN** the R&R study S1 scenario is run with the committed synthesiser and harness against WSJT-X 2.7.0
- **THEN** the mean SNR bias for WSJT-X SHALL be within ±2.0 dB of zero across all 30 matched observations

#### Scenario: SNR is monotonically non-decreasing across the S1 SNR ladder

- **WHEN** the R&R study S1 scenario is run and per-part mean reported SNR is computed for each of the 10 SNR parts (P0–P9, true SNR −12 to +15 dB)
- **THEN** the per-part mean reported SNR SHALL increase monotonically from P0 to P9 (no part SHALL have a lower mean reported SNR than the preceding part)

#### Scenario: PCM normalisation does not alter decode results on G6 fixtures

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a PCM buffer from the committed synthetic fixture corpus after PCM normalisation is applied
- **THEN** the returned decode results SHALL be identical to those produced without normalisation (same messages, same frequency and DT values within rounding)

---

### Requirement: Reported SNR is invariant to audio-chain frequency response across the passband

The FT8 decoder SHALL report SNR values that are independent of the decoded signal's audio frequency within the 200–3000 Hz FT8 passband. Specifically, the mean per-decode SNR delta (OpenWSFZ − WSJT-X) SHALL not vary by more than ±4.0 dB between the low-frequency region (200–1000 Hz) and the high-frequency region (2000–3000 Hz) in any live or corpus matched-pair study.

This requirement formalises the fix for D-003 and D-004: the prior global noise floor caused up to −22 dB SNR under-report at 2800–3000 Hz relative to 800–1000 Hz due to audio-chain rolloff. The per-signal local noise floor (`K_LOCAL_NOISE_WINDOW = 32` bins, histogram median of adjacent sideband bins) eliminates this frequency-dependent bias by anchoring noise estimation to the signal's own spectral neighbourhood.

#### Scenario: SNR bias is consistent at low frequency vs high frequency (S1 post-fix validation)

- **WHEN** the S1 R&R scenario is run with synthesised signals placed at a low-frequency tone offset (≤ 1000 Hz) and at a high-frequency tone offset (≥ 2000 Hz)
- **THEN** the mean SNR bias for each frequency region SHALL each be within ±2.0 dB, and the difference between the two region biases SHALL not exceed 4.0 dB

#### Scenario: No SNR values below −30 dB when WSJT-X reports normal SNR for the same message

- **WHEN** OpenWSFZ and WSJT-X decode the same FT8 message in the same cycle window and WSJT-X reports an SNR within its normal range (≥ −24 dB)
- **THEN** OpenWSFZ SHALL NOT report an SNR below −30 dB for that message (D-003 class failure)

---

### Requirement: Reported SNR is correct for candidates whose sync position precedes the decode window

The FT8 decoder SHALL compute a decoded candidate's `signal_db` term (the numerator of
the SNR formula, `snr = signal_db - local_noise_db - 26.5`) by averaging only the
waterfall samples that correspond to the candidate's own 79-symbol re-encoding at the
correct symbol position, for every candidate regardless of whether its sync position
(`time_offset`) is non-negative or negative (i.e. the signal's true start precedes the
nominal 15-second decode window). Specifically, for absolute waterfall block `b`, the
symbol index used to select the expected tone SHALL be `b - time_offset` computed from
the candidate's true, **unclamped** `time_offset` — never from a value that has been
clamped to a non-negative floor before the subtraction. Blocks whose derived symbol
index would fall outside `[0, FT8_NN)` SHALL be excluded from both the sum and the count
(never re-anchored to a different, wrong symbol), matching `ft8_lib`'s own out-of-range
convention (`patched/ft8/decode.c:160,226`: `if (block_abs < 0) continue;`).

This requirement exists because a defect present through `FT8_SHIM_VERSION 20260045`
computed the symbol index from the **clamped** `time_offset` (floored to zero before the
block-to-symbol subtraction) while still iterating a full 79-block range, causing every
sample for a `time_offset < 0` candidate to be read from the wrong tone bin — a silent,
total corruption (not a partial-data effect) that under-reported SNR by roughly 15–20 dB.
Confirmed mechanically: `qa/rr-study/2026-08-22-1454-qa-to-architect-b-dt-c3-results.md`
(arm B-dt-C3) measured a 17.4 dB step in reported SNR co-located exactly with the block
at which `time_offset` turns negative, against a "signal partly outside the window"
alternative explanation that could account for at most 0.083 dB at that point.

#### Scenario: SNR does not collapse for a signal arriving before the nominal slot boundary

- **WHEN** the B-dt-C3 offline sweep (`qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py`) is run against a build under test, sweeping `true_dt` from `+0.08 s` to `−1.20 s` on the decoder's own 0.08 s sub-block lattice
- **THEN** the maximum per-step drop in mean reported SNR across adjacent parts (`Δ(p)`, as defined by the harness) SHALL be less than **8.0 dB** at every step, and mean reported SNR SHALL NOT differ by more than a few dB between the most-negative and least-negative parts of the sweep that both produce at least 3 matched decodes out of 5 trials

#### Scenario: A candidate with a negative sync position derives its symbol index from the true offset, not a clamped one

- **WHEN** `ft8_decode_all` computes `signal_db` for a candidate whose `time_offset < 0`
- **THEN** the symbol index used for waterfall block `b` SHALL be `b - time_offset` using the true (unclamped) `time_offset` value, so that the averaged samples correspond to the candidate's actual re-encoded tones, not tones offset by `|time_offset|` positions

#### Scenario: The averaged sample count is thinned, not corrupted, for early-arriving signals

- **WHEN** a candidate's `time_offset < 0` places some of its 79 symbols before the start of the retained waterfall
- **THEN** the count of samples contributing to `signal_db` (`cnt`) SHALL be less than 79 by exactly the number of blocks that fall outside the retained waterfall, and none of the remaining samples SHALL be drawn from the wrong tone bin as a result

#### Scenario: Existing real-decode replays are unaffected (regression)

- **WHEN** any of the eight committed AC-N1 replay corpora (`qa/rr-study/r2-coherent-llr-instrument/results/replay_*.json`, every recorded decode having `time_offset >= 0`) is replayed against a build under test
- **THEN** the decode results (message set, frequency, DT, and SNR for every decode) SHALL be bit-identical to the committed pre-fix replay, since this requirement only changes behaviour on the `time_offset < 0` branch
