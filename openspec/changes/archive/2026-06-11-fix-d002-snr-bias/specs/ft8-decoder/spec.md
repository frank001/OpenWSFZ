## ADDED Requirements

### Requirement: Reported SNR is within ±2.0 dB of true SNR

The FT8 decoder SHALL report SNR values whose mean bias, measured over the R&R study S1 scenario (10 SNR parts × 3 trials = 30 observations, SNR range −12 to +15 dB), does not exceed ±2.0 dB relative to the true synthesised SNR. This requirement applies to both reference appraisers (OpenWSFZ and WSJT-X). Bias is defined as `mean(reported_snr − true_snr)` across all 30 matched observations.

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
