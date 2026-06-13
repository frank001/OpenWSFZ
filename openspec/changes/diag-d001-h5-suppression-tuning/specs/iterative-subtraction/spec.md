## MODIFIED Requirements

### Requirement: Soft SNR-scaled tile attenuation (H5 suppression constant tuning)

Rather than hard-zeroing suppressed tiles (which over-suppresses borderline decodes whose tile
bins may overlap with an adjacent co-channel signal), the suppression SHALL use a linear
attenuation factor derived from the decoded signal's SNR:

```
factor = 1.0 − clamp((snr_db − K_SOFT_SUPP_SNR_MIN_DB) / (K_SOFT_SUPP_SNR_MAX_DB − K_SOFT_SUPP_SNR_MIN_DB), 0.0, 1.0)
tile_value = noise_raw + factor * (tile_value − noise_raw)
```

where `K_SOFT_SUPP_SNR_MIN_DB = −15.0f` and `K_SOFT_SUPP_SNR_MAX_DB = +5.0f`.

The ramp window shifts 10 dB toward lower SNRs relative to H4 (which used −5.0f / +15.0f):

| SNR | Factor (H4 baseline) | Factor (H5) | Suppression (H5) |
|---|---|---|---|
| ≤ −15 dB | 1.0 | 1.0 | 0% (unchanged) |
| −5 dB | 1.0 | 0.5 | 50% |
| 0 dB | 0.75 | 0.25 | 75% |
| +5 dB | 0.5 | 0.0 | 100% |
| ≥ +15 dB | 0.0 | 0.0 | 100% (unchanged) |

- At SNR ≥ +5 dB: factor = 0.0 → tile is fully suppressed (assigned noise_raw).
- At SNR ≤ −15 dB: factor = 1.0 → tile is unchanged (no suppression).
- Between: factor varies linearly between 0.0 and 1.0.

Both constants SHALL be defined as named C preprocessor constants in `ft8_shim.c`; no magic
numbers for the SNR gate boundaries.

#### Scenario: Strong signal (SNR ≥ K_SOFT_SUPP_SNR_MAX_DB) is fully suppressed

- **WHEN** a signal decoded in pass 0 has SNR ≥ K_SOFT_SUPP_SNR_MAX_DB (+5 dB)
- **THEN** all suppressed tiles SHALL be assigned noise_raw (attenuation factor = 0.0)

#### Scenario: Weak signal (SNR ≤ K_SOFT_SUPP_SNR_MIN_DB) is not suppressed

- **WHEN** a signal decoded in pass 0 has SNR ≤ K_SOFT_SUPP_SNR_MIN_DB (−15 dB)
- **THEN** no tile energy is removed from the waterfall (attenuation factor = 1.0)

#### Scenario: 0 dB SNR signal receives 75% suppression

- **WHEN** a signal decoded in pass 0 has SNR = 0 dB
- **THEN** each suppressed tile SHALL be set to noise_raw + 0.25 × (tile − noise_raw)
  (attenuation factor ≈ 0.25; 75% of tile energy above noise floor removed)

#### Scenario: Mid-range SNR (−5 dB) produces 50% suppression

- **WHEN** a signal decoded in pass 0 has SNR = −5 dB
- **THEN** each suppressed tile SHALL be set to noise_raw + 0.5 × (tile − noise_raw)
  (attenuation factor ≈ 0.5)
