## MODIFIED Requirements

### Requirement: SNR value reflects signal power in the active tone bin only

The SNR value attached to each `DecodeResult` SHALL be computed using only the waterfall
bin corresponding to the transmitted FT8 tone at each symbol time, as determined by
`ft8_encode(msg.payload, tones)` applied to the successfully decoded message payload.

The signal power estimator SHALL NOT use the maximum over all 8 FT8 tone bins per symbol.
Instead, for symbol index `s` (0–78), it SHALL read `row[tones[s]]`, where `row` is the
waterfall row at the candidate's time sub-block and frequency origin, and `tones[s]` is
the tone index (0–7) for that symbol.

The SNR formula remains:
```
snr = signal_db - noise_floor_db - 26.0
```
where `signal_db` is the mean of the 79 per-symbol tone-bin readings,
`noise_floor_db` is the waterfall-wide median, and `26.0 dB` is the WSJT-X 2500 Hz
bandwidth normalisation constant (`10·log₁₀(2500 / 6.25)`).

#### Scenario: SNR is within 2 dB of injected SNR at moderate signal strength

- **WHEN** `Ft8Decoder.DecodeAsync` is called with a synthesised FT8 signal at a known
  injected SNR between −12 dB and +3 dB (per the R&R study S1 scenario)
- **THEN** the `Snr` field of the matched `DecodeResult` SHALL differ from the injected
  SNR by no more than **±2 dB**

#### Scenario: SNR bias is not systematically positive

- **WHEN** the R&R study S1 scenario is executed and the OpenWSFZ S1 bias is computed
  from the matched CSV
- **THEN** the mean bias (reported − injected) SHALL lie in the range **[−2.0, +0.5] dB**,
  consistent with WSJT-X's observed bias of −1.65 dB and eliminating the previous +1.08 dB
  positive offset

#### Scenario: SNR repeatability improves over the previous implementation

- **WHEN** the R&R study S1 scenario is executed and the bias-vs-reference R² is computed
  for OpenWSFZ
- **THEN** R² SHALL be ≥ 0.50, compared to the pre-fix value of 0.267, indicating that the
  bias is now more consistent across trials at the same injected SNR level

#### Scenario: Decode correctness is unaffected by the SNR estimation change

- **WHEN** `Ft8Decoder.DecodeAsync` is called with any PCM buffer from the committed
  fixture corpus
- **THEN** the set of decoded `Message` strings SHALL be identical to those produced by
  the previous implementation (SNR estimation does not affect decode success or message text)
