"""L4 — Tones -> continuous-phase GFSK audio, placed in a 15 s slot.

FT8 uses Gaussian Frequency Shift Keying: the tone-index sequence is upsampled,
smoothed by a Gaussian pulse (BT product), integrated to a continuous phase, and
mixed up to the base audio frequency. Continuous phase avoids spectral splatter
between symbols.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

from .constants import (
    DEFAULT_SAMPLE_RATE_HZ,
    GFSK_BT,
    NUM_SYMBOLS,
    SLOT_LENGTH_S,
    SYMBOL_PERIOD_S,
    TONE_SPACING_HZ,
)


def _gaussian_pulse(samples_per_symbol: int, bt: float) -> np.ndarray:
    """Length-3-symbol Gaussian smoothing pulse, normalised to unit area per symbol."""
    span = 3  # symbols
    n = span * samples_per_symbol
    t = (np.arange(n) - n / 2 + 0.5) / samples_per_symbol  # in symbol periods
    sigma = np.sqrt(np.log(2)) / (2 * np.pi * bt)
    pulse = np.exp(-(t ** 2) / (2 * sigma ** 2))
    pulse /= pulse.sum()
    return pulse


def modulate(
    tones: list[int],
    base_freq_hz: float,
    dt_s: float = 0.0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    slot_length_s: float = SLOT_LENGTH_S,
    amplitude: float = 1.0,
) -> np.ndarray:
    """Render `tones` as GFSK audio into a `slot_length_s` buffer, offset by `dt_s`.

    `base_freq_hz` is the audio frequency of tone 0; tone k sits at
    base + k * 6.25 Hz. Returns a float64 array of length slot_length_s * fs.
    """
    if len(tones) != NUM_SYMBOLS:
        raise ValueError(f"expected {NUM_SYMBOLS} tones, got {len(tones)}")

    fs = sample_rate_hz
    sps = int(round(SYMBOL_PERIOD_S * fs))  # samples per symbol

    # Per-sample tone index (piecewise constant), then Gaussian-smoothed.
    tone_arr = np.repeat(np.asarray(tones, dtype=np.float64), sps)
    pulse = _gaussian_pulse(sps, GFSK_BT)
    smoothed = fftconvolve(tone_arr, pulse, mode="same")

    # Instantaneous frequency (Hz) then integrated phase.
    inst_freq = base_freq_hz + smoothed * TONE_SPACING_HZ
    phase = 2.0 * np.pi * np.cumsum(inst_freq) / fs
    signal = amplitude * np.sin(phase)

    # Place into the full slot at the DT offset.
    slot = np.zeros(int(round(slot_length_s * fs)), dtype=np.float64)
    start = int(round(dt_s * fs))
    start = max(0, min(start, len(slot) - len(signal)))
    slot[start: start + len(signal)] = signal
    return slot
