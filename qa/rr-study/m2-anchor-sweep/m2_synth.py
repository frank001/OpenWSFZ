#!/usr/bin/env python3
"""M2 -- render a positive-control trial's PCM: a clean synthesised FT8 tone, scaled
to a target nominal SNR against the REAL background's own measured noise sigma, added
to that real captured 15 s buffer.

Nominal SNR, not WSJT-X-calibrated: the scaling formula is the algebraic inverse of
synth/channel.py's own noise_sigma_for_snr (same 2500 Hz reference-bandwidth
convention, same white-noise assumption), but the "noise" here is the real
background's own broadband sample std-dev, not a calibrated flat floor. This is a
control for HARNESS correctness (does the sweep+refiner pipeline lock onto a signal
we know the exact position of, embedded in real capture noise), not a claim about the
real corpus's WSJT-X-scale SNR -- the M2 report must not cite these SNR labels as if
they were WSJT-X-comparable.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m2_common import BUFFER_SAMPLES, REFERENCE_BANDWIDTH_HZ, SAMPLE_RATE_HZ  # noqa: E402

_RR_STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RR_STUDY not in sys.path:
    sys.path.insert(0, _RR_STUDY)


def render_control_pcm(row: dict, background_pcm: np.ndarray) -> np.ndarray:
    """row: one m2_control_manifest.json row. background_pcm: real WAV samples
    (float32, raw int16 units, BUFFER_SAMPLES long) for row['cycle_id'].

    Returns float32 PCM: background + scaled clean tone, same units/length.
    """
    from synth import encoder, modulator  # noqa: PLC0415

    assert background_pcm.shape == (BUFFER_SAMPLES,), background_pcm.shape

    tones = encoder.message_to_tones(row["message"])
    clean = modulator.modulate(
        tones,
        base_freq_hz=row["true_freq_hz"],
        dt_s=row["true_dt_s"],
        sample_rate_hz=SAMPLE_RATE_HZ,
        slot_length_s=BUFFER_SAMPLES / SAMPLE_RATE_HZ,
        amplitude=1.0,
    )
    assert clean.shape == (BUFFER_SAMPLES,), clean.shape

    # Real background noise sigma, measured directly off this cycle's own captured
    # samples (raw int16 units, same scale m1_common.read_wav_12k_15s returns).
    sigma_real = float(np.std(background_pcm.astype(np.float64)))

    snr_db = row["target_snr_db"]
    snr_lin = 10.0 ** (snr_db / 10.0)
    p_noise_inband = sigma_real ** 2 * 2.0 * REFERENCE_BANDWIDTH_HZ / SAMPLE_RATE_HZ
    p_target = snr_lin * p_noise_inband

    p_clean_unit = float(np.mean(clean ** 2))
    if p_clean_unit <= 0.0:
        raise ValueError("clean tone has zero power -- cannot scale to target SNR")
    amp_scale = float(np.sqrt(p_target / p_clean_unit))

    # Deterministic given row['render_seed'] only insofar as message/offsets are
    # already fixed in the manifest; no additional randomness is introduced here
    # (the "noise" is the real WAV, not a synthesised realisation).
    out = background_pcm.astype(np.float64) + amp_scale * clean
    return out.astype(np.float32)
