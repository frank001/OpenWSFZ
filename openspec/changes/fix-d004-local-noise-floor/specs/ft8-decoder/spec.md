## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Reported SNR is invariant to audio-chain frequency response across the passband

The FT8 decoder SHALL report SNR values that are independent of the decoded signal's audio frequency within the 200–3000 Hz FT8 passband. Specifically, the mean per-decode SNR delta (OpenWSFZ − WSJT-X) SHALL not vary by more than ±4.0 dB between the low-frequency region (200–1000 Hz) and the high-frequency region (2000–3000 Hz) in any live or corpus matched-pair study.

This requirement formalises the fix for D-003 and D-004: the prior global noise floor caused up to −22 dB SNR under-report at 2800–3000 Hz relative to 800–1000 Hz due to audio-chain rolloff. The per-signal local noise floor (`K_LOCAL_NOISE_WINDOW = 32` bins, histogram median of adjacent sideband bins) eliminates this frequency-dependent bias by anchoring noise estimation to the signal's own spectral neighbourhood.

#### Scenario: SNR bias is consistent at low frequency vs high frequency (S1 post-fix validation)

- **WHEN** the S1 R&R scenario is run with synthesised signals placed at a low-frequency tone offset (≤ 1000 Hz) and at a high-frequency tone offset (≥ 2000 Hz)
- **THEN** the mean SNR bias for each frequency region SHALL each be within ±2.0 dB, and the difference between the two region biases SHALL not exceed 4.0 dB

#### Scenario: No SNR values below −30 dB when WSJT-X reports normal SNR for the same message

- **WHEN** OpenWSFZ and WSJT-X decode the same FT8 message in the same cycle window and WSJT-X reports an SNR within its normal range (≥ −24 dB)
- **THEN** OpenWSFZ SHALL NOT report an SNR below −30 dB for that message (D-003 class failure)
