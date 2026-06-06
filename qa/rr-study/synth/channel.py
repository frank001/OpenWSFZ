"""L5 — Additive white Gaussian noise scaled to a target SNR (2500 Hz reference).

WSJT-X reports SNR in a 2500 Hz reference bandwidth (STUDY-SPEC §5). For a real
signal sampled at fs, white noise of sample variance sigma^2 has one-sided power
spectral density sigma^2 / (fs/2) per Hz, so its power within a bandwidth B is

    P_noise(B) = sigma^2 * B / (fs/2) = sigma^2 * 2B / fs.

Given a target SNR (dB) and signal power P_sig = mean(signal^2), the noise sample
variance that realises that SNR in the reference band is

    sigma^2 = P_sig / (snr_linear * 2B / fs).

Each trial draws an independent seeded noise realisation (STUDY-SPEC §2.1).

For multi-signal slots (S4 density, S7 compounding) use :func:`mix_to_shared_floor`,
which models a single receiver: stations are scaled by their relative SNR and summed
over ONE shared noise floor, rather than each carrying its own (which would stack N
floors and erase capture-ratio differences).
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
    return add_awgn(signal, sigma, seed)


def add_awgn(signal: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    """Return signal + seeded AWGN of the given sample std-dev ``sigma``.

    Low-level primitive: unlike :func:`add_noise`, ``sigma`` is supplied
    directly rather than derived from the signal's own power. This is what the
    shared-floor mixer needs, because a multi-signal sum must NOT have its noise
    rescaled to the *summed* power — the floor is fixed once, for the slot.
    """
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(signal)) * sigma
    return signal + noise


def mix_to_shared_floor(
    clean_signals: "list[np.ndarray]",
    snr_db_list: "list[float]",
    seed: int,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    bandwidth_hz: float = REFERENCE_BANDWIDTH_HZ,
) -> np.ndarray:
    """Mix several stations into one slot over a single shared band-noise floor.

    Models a single receiver: every station's SNR is its strength *relative to
    one common noise floor*, and there is exactly one noise realisation for the
    slot — not one per station.

    Each ``clean_signals[i]`` is a unit-amplitude (noise-free) render. Station
    ``i`` is scaled by ``10**(snr_db_i / 20)`` so that a 0 dB station sits at
    unit amplitude, a +3 dB station is stronger and a -10 dB station is weaker
    (this is what produces a real *capture* ratio). The scaled stations are
    summed, then a single seeded AWGN floor is added, sized so that a 0 dB
    station realises 0 dB in-band SNR against it.

    Consequences vs the old per-signal-noise convention:
      * An N-stack no longer carries N noise floors (the floor is independent
        of stack size).
      * ``snr_db`` now changes a station's *strength*, so capture pairs
        (e.g. 0 / -10 dB) actually differ in level.
    """
    if not clean_signals:
        raise ValueError("mix_to_shared_floor requires at least one signal")
    if len(clean_signals) != len(snr_db_list):
        raise ValueError(
            f"signal/snr length mismatch: {len(clean_signals)} vs {len(snr_db_list)}"
        )

    mixed: "np.ndarray | None" = None
    for sig, snr_db in zip(clean_signals, snr_db_list):
        amp = 10.0 ** (snr_db / 20.0)
        contrib = amp * sig
        mixed = contrib if mixed is None else mixed + contrib

    # One shared floor: sigma such that a unit-amplitude (0 dB) station realises
    # 0 dB in-band SNR. Referenced to a single unit station, so it does not grow
    # with the number of stations in the stack.
    sigma = noise_sigma_for_snr(clean_signals[0], 0.0, sample_rate_hz, bandwidth_hz)
    return add_awgn(mixed, sigma, seed)


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
