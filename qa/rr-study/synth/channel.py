"""L5 — Additive white Gaussian noise scaled to a target SNR (2500 Hz reference).

WSJT-X reports SNR in a 2500 Hz reference bandwidth (STUDY-SPEC §5). For a real
signal sampled at fs, white noise of sample variance sigma^2 has one-sided power
spectral density sigma^2 / (fs/2) per Hz, so its power within a bandwidth B is

    P_noise(B) = sigma^2 * B / (fs/2) = sigma^2 * 2B / fs.

Given a target SNR (dB) and signal power P_sig = mean(signal^2), the noise sample
variance that realises that SNR in the reference band is

    sigma^2 = P_sig / (snr_linear * 2B / fs).

Each trial draws an independent seeded noise realisation (STUDY-SPEC §2.1).
"""
from __future__ import annotations

import numpy as np

from .constants import DEFAULT_SAMPLE_RATE_HZ, REFERENCE_BANDWIDTH_HZ


def noise_sigma_for_snr(
    signal: np.ndarray,
    snr_db: float,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    bandwidth_hz: float = REFERENCE_BANDWIDTH_HZ,
) -> float:
    """Return the noise sample std-dev that yields `snr_db` in the reference band."""
    p_sig = float(np.mean(signal ** 2))
    if p_sig <= 0.0:
        raise ValueError("signal has zero power; cannot set SNR")
    snr_lin = 10.0 ** (snr_db / 10.0)
    sigma2 = p_sig / (snr_lin * 2.0 * bandwidth_hz / sample_rate_hz)
    return float(np.sqrt(sigma2))


def add_noise(
    signal: np.ndarray,
    snr_db: float,
    seed: int,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    bandwidth_hz: float = REFERENCE_BANDWIDTH_HZ,
) -> np.ndarray:
    """Return signal + seeded AWGN at the requested in-band SNR."""
    sigma = noise_sigma_for_snr(signal, snr_db, sample_rate_hz, bandwidth_hz)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(signal)) * sigma
    return signal + noise


def measure_inband_snr_db(
    signal: np.ndarray,
    noisy: np.ndarray,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    bandwidth_hz: float = REFERENCE_BANDWIDTH_HZ,
) -> float:
    """Estimate the realised in-band SNR (dB) of `noisy = signal + noise`.

    Used by tests to confirm the scaling: full-band noise power is converted to the
    reference bandwidth analytically.
    """
    noise = noisy - signal
    p_sig = float(np.mean(signal ** 2))
    p_noise_fullband = float(np.mean(noise ** 2))
    p_noise_inband = p_noise_fullband * (2.0 * bandwidth_hz / sample_rate_hz)
    return 10.0 * np.log10(p_sig / p_noise_inband)
