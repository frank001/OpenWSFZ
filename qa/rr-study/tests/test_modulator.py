"""L4 — modulator tests (structure, duration, instantaneous frequency)."""
import numpy as np

from synth import modulator
from synth.constants import (
    COSTAS_ARRAY,
    NUM_SYMBOLS,
    SLOT_LENGTH_S,
    SYMBOL_PERIOD_S,
    TONE_SPACING_HZ,
)


def _tones():
    # 79 tones: valid Costas at the sync slots, zeros elsewhere.
    seq = [0] * NUM_SYMBOLS
    for start in (0, 36, 72):
        seq[start:start + 7] = list(COSTAS_ARRAY)
    return seq


def test_output_length_matches_slot():
    fs = 48000
    out = modulator.modulate(_tones(), base_freq_hz=1500.0, dt_s=0.0, sample_rate_hz=fs)
    assert len(out) == int(round(SLOT_LENGTH_S * fs))


def test_signal_is_finite_and_bounded():
    out = modulator.modulate(_tones(), base_freq_hz=1500.0)
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0 + 1e-9


def test_dt_offset_shifts_energy():
    early = modulator.modulate(_tones(), 1500.0, dt_s=0.0)
    late = modulator.modulate(_tones(), 1500.0, dt_s=2.0)
    fs = 48000
    # First 0.5 s should be near-silent when DT=2.0 but not when DT=0.0.
    head = int(0.5 * fs)
    assert np.mean(late[:head] ** 2) < np.mean(early[:head] ** 2)


def test_instantaneous_frequency_near_base_for_tone_zero():
    # A constant tone-0 sequence should sit at base_freq.
    fs = 48000
    base = 1500.0
    out = modulator.modulate([0] * NUM_SYMBOLS, base_freq_hz=base, sample_rate_hz=fs)
    sig = out[out != 0.0]
    # Estimate dominant frequency via zero-crossings over the active region.
    mid = sig[len(sig) // 4: 3 * len(sig) // 4]
    crossings = np.sum((mid[:-1] < 0) & (mid[1:] >= 0))
    est_freq = crossings / (len(mid) / fs)
    assert abs(est_freq - base) < TONE_SPACING_HZ  # within one tone bin
