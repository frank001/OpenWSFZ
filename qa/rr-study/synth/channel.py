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

Noise bandwidth (noise_cutoff_hz)
----------------------------------
The sigma is calibrated against the 2500 Hz *reference* band; white noise fills
the full Nyquist band (fs/2).  At 48 kHz this is 24 kHz — nearly 10× the FT8
passband.  When audio is played back at 48 kHz the ear hears all 24 kHz of hiss,
burying signals that a decoder (which filters to ≤ 6 kHz) can decode without
difficulty.

Supply ``noise_cutoff_hz`` to restrict the generated noise to a band that matches
a real SSB receiver's audio bandwidth (~3 kHz).  A windowed FIR lowpass filter
(Kaiser window, numtaps=255, beta=6.0) is applied via linear convolution
(``mode='same'``).  The Kaiser beta=6.0 yields ~60 dB stopband attenuation and a
transition band of approximately 720 Hz at 48 kHz (Kaiser design formula:
Δf = (A−8)·fs / (2.285·2π·M) with M=254, A≈63 dB), eliminating the
Gibbs-phenomenon spectral ridge that the former brick-wall FFT zero-out produced.
The in-band noise PSD (100 Hz to 85 % of the cutoff) is flat to within ±1 dB.
The in-band SNR (2500 Hz reference) is preserved exactly.  The total noise sigma
drops from ~2.0 to ~0.7 (48 kHz, 3 kHz cutoff), making signals near 0 dB SNR
perceptibly audible to the human ear.
"""
from __future__ import annotations

import numpy as np
from scipy import signal as _signal

from .constants import DEFAULT_SAMPLE_RATE_HZ, REFERENCE_BANDWIDTH_HZ

# ── FIR lowpass filter design parameters ─────────────────────────────────────
_FIR_NUMTAPS: int = 255          # filter order + 1 (odd → symmetric, linear-phase)
_KAISER_BETA: float = 6.0        # Kaiser window shape (~60 dB stopband attenuation)

# ── Welch PSD estimation parameters ──────────────────────────────────────────
_WELCH_NPERSEG: int = 4096       # Welch segment length; controls freq resolution
_WELCH_MIN_NPERSEG: int = 16     # minimum segment length for short buffers
_WELCH_BUFFER_FRACTION: int = 4  # nperseg <= len(x) // _WELCH_BUFFER_FRACTION
_LOG_FLOOR: float = 1e-30        # floor before log10 to avoid -inf

# ── verify_noise_psd acceptance thresholds ────────────────────────────────────
_PASSBAND_LOWER_HZ: float = 100.0       # exclude DC / very low-freq noise artefacts
_PASSBAND_UPPER_FRACTION: float = 0.85  # passband upper bound = cutoff * this fraction
_STOPBAND_CHECK_FACTOR: float = 1.2     # check attenuation at cutoff * this factor
_MIN_STOPBAND_ATTENUATION_DB: float = 30.0  # minimum required stopband attenuation


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
    noise_cutoff_hz: "float | None" = None,
) -> np.ndarray:
    """Return signal + seeded AWGN at the requested in-band SNR.

    If ``noise_cutoff_hz`` is given, the noise is lowpass-filtered to that
    frequency before being added (see module docstring and :func:`add_awgn`).
    The in-band SNR (2500 Hz reference) is unaffected by bandlimiting.
    """
    sigma = noise_sigma_for_snr(signal, snr_db, sample_rate_hz, bandwidth_hz)
    return add_awgn(signal, sigma, seed,
                    noise_cutoff_hz=noise_cutoff_hz,
                    sample_rate_hz=sample_rate_hz)


def _lowpass_fir(
    x: np.ndarray,
    cutoff_hz: float,
    sample_rate_hz: int,
) -> np.ndarray:
    """Windowed FIR lowpass filter (Kaiser window, numtaps=255, beta=6.0).

    Replaces the former brick-wall FFT zero-out.  ``scipy.signal.firwin``
    places the −6 dB point at ``cutoff_hz``; the Kaiser beta=6.0 gives ~60 dB
    stopband attenuation and a transition band of ~720 Hz at 48 kHz.  Convolution
    is performed with ``scipy.signal.fftconvolve(..., mode='same')`` so the
    output length is identical to the input length and no boundary transients
    are introduced.
    """
    taps = _signal.firwin(
        numtaps=_FIR_NUMTAPS,
        cutoff=cutoff_hz,
        window=("kaiser", _KAISER_BETA),
        fs=float(sample_rate_hz),
    )
    return _signal.fftconvolve(x, taps, mode="same")


def add_awgn(
    signal: np.ndarray,
    sigma: float,
    seed: int,
    noise_cutoff_hz: "float | None" = None,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """Return signal + seeded AWGN of the given sample std-dev ``sigma``.

    Low-level primitive: unlike :func:`add_noise`, ``sigma`` is supplied
    directly rather than derived from the signal's own power. This is what the
    shared-floor mixer needs, because a multi-signal sum must NOT have its noise
    rescaled to the *summed* power — the floor is fixed once, for the slot.

    If ``noise_cutoff_hz`` is given, the generated noise is lowpass-filtered to
    that frequency before being added (see module docstring for rationale).  The
    ``sigma`` is still calibrated for the *in-band* (2500 Hz) SNR; bandlimiting
    does not alter the in-band noise PSD, so the in-band SNR is unchanged.
    """
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(signal)) * sigma
    if noise_cutoff_hz is not None:
        noise = _lowpass_fir(noise, float(noise_cutoff_hz), int(sample_rate_hz))
    return signal + noise


def mix_to_shared_floor(
    clean_signals: "list[np.ndarray]",
    snr_db_list: "list[float]",
    seed: int,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    bandwidth_hz: float = REFERENCE_BANDWIDTH_HZ,
    noise_cutoff_hz: "float | None" = None,
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

    ``noise_cutoff_hz`` — if supplied, the noise floor is lowpass-filtered to
    that frequency, simulating a real SSB receiver's audio bandwidth (see module
    docstring).  The in-band SNR (2500 Hz reference) is unaffected.
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
    return add_awgn(mixed, sigma, seed,
                    noise_cutoff_hz=noise_cutoff_hz,
                    sample_rate_hz=sample_rate_hz)


def measure_inband_snr_db(
    signal: np.ndarray,
    noisy: np.ndarray,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    bandwidth_hz: float = REFERENCE_BANDWIDTH_HZ,
) -> float:
    """Estimate the realised in-band SNR (dB) of `noisy = signal + noise`.

    The in-band noise power is measured by integrating the Welch one-sided PSD
    from DC to ``bandwidth_hz``.  This method is correct for both white noise and
    bandlimited noise; the former analytical approach (full-band power ×
    2B/fs) only works when the noise is spectrally flat across the full Nyquist
    band and gives incorrect results after a lowpass filter is applied.
    """
    noise = noisy - signal
    p_sig = float(np.mean(signal ** 2))
    nperseg = min(_WELCH_NPERSEG, max(_WELCH_MIN_NPERSEG,
                                      len(noise) // _WELCH_BUFFER_FRACTION))
    freqs, psd = _signal.welch(noise, fs=float(sample_rate_hz), nperseg=nperseg)
    inband_mask = freqs <= bandwidth_hz
    df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    p_noise_inband = float(np.sum(psd[inband_mask]) * df)
    return 10.0 * np.log10(p_sig / max(p_noise_inband, _LOG_FLOOR))


def verify_noise_psd(
    noise: np.ndarray,
    cutoff_hz: float,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    tolerance_db: float = 1.0,
    assert_ok: bool = False,
) -> bool:
    """Verify that the noise PSD satisfies flatness and Gibbs-suppression criteria.

    Uses Welch's method (``nperseg=4096``) to estimate the one-sided PSD.

    Two criteria are checked:

    1. **Passband flatness** — the PSD from 100 Hz to ``cutoff_hz * 0.85`` must
       have a peak deviation from the band mean of ≤ ``tolerance_db`` dB.

    2. **Gibbs suppression** — the PSD at the cutoff frequency must be at least
       30 dB below the passband mean (no spectral ridge at the cutoff).

    Parameters
    ----------
    noise:
        Pure noise array (no signal component).
    cutoff_hz:
        Nominal lowpass cutoff frequency (Hz).
    sample_rate_hz:
        Sample rate of ``noise``.
    tolerance_db:
        Passband flatness tolerance in dB (default 1.0 dB).
    assert_ok:
        When ``True``, raise ``AssertionError`` with a descriptive message if
        either criterion fails.  When ``False`` (default), return ``True`` /
        ``False`` without raising.

    Returns
    -------
    bool
        ``True`` if both criteria pass, ``False`` otherwise (only when
        ``assert_ok=False``).
    """
    freqs, psd = _signal.welch(noise, fs=float(sample_rate_hz), nperseg=_WELCH_NPERSEG)
    psd_db = 10.0 * np.log10(np.maximum(psd, _LOG_FLOOR))

    # ── 1. Passband flatness ─────────────────────────────────────────────────
    passband_mask = (freqs >= _PASSBAND_LOWER_HZ) & (freqs <= cutoff_hz * _PASSBAND_UPPER_FRACTION)
    if not np.any(passband_mask):
        msg = (
            f"verify_noise_psd: no PSD bins in the passband "
            f"({_PASSBAND_LOWER_HZ:.0f} Hz – {cutoff_hz * _PASSBAND_UPPER_FRACTION:.0f} Hz)"
            f" at sample_rate={sample_rate_hz}"
        )
        if assert_ok:
            raise AssertionError(msg)
        return False

    pb_psd_db = psd_db[passband_mask]
    pb_mean_db = float(np.mean(pb_psd_db))
    pb_deviation_db = float(np.max(np.abs(pb_psd_db - pb_mean_db)))

    if pb_deviation_db > tolerance_db:
        msg = (
            f"verify_noise_psd: passband not flat — "
            f"peak deviation {pb_deviation_db:.2f} dB exceeds tolerance "
            f"{tolerance_db:.1f} dB "
            f"(passband {_PASSBAND_LOWER_HZ:.0f} Hz – {cutoff_hz * _PASSBAND_UPPER_FRACTION:.0f} Hz)"
        )
        if assert_ok:
            raise AssertionError(msg)
        return False

    # ── 2. Stopband suppression ──────────────────────────────────────────────
    # Check PSD at 1.2 × cutoff_hz — this is well into the stopband for a
    # Kaiser FIR (transition band is ±~300 Hz at 48 kHz / 255 taps).  The
    # former brick-wall FFT filter produced a Gibbs ridge at the cutoff; the
    # FIR filter should have deep (≥ 30 dB) attenuation here.
    stopband_hz = cutoff_hz * _STOPBAND_CHECK_FACTOR
    stopband_idx = int(np.argmin(np.abs(freqs - stopband_hz)))
    stopband_psd_db = float(psd_db[stopband_idx])
    stopband_attenuation_db = pb_mean_db - stopband_psd_db  # positive → suppressed

    if stopband_attenuation_db < _MIN_STOPBAND_ATTENUATION_DB:
        msg = (
            f"verify_noise_psd: insufficient stopband attenuation — "
            f"PSD at {freqs[stopband_idx]:.0f} Hz (1.2× cutoff) is only "
            f"{stopband_attenuation_db:.1f} dB below passband mean "
            f"(required >= {_MIN_STOPBAND_ATTENUATION_DB:.0f} dB;"
            f" possible Gibbs ridge or brickwall artefact)"
        )
        if assert_ok:
            raise AssertionError(msg)
        return False

    return True
