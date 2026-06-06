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


def test_instantaneous_frequency_non_zero_tone():
    # A constant tone-4 sequence should sit at base_freq + 4 * 6.25 = 1525.0 Hz.
    # Costas positions are also set to tone=4 — valid for unit-testing the modulator
    # in isolation (we are not testing the encode pipeline here).
    fs = 48000
    base = 1500.0
    tone = 4
    expected_freq = base + tone * TONE_SPACING_HZ  # 1525.0 Hz
    out = modulator.modulate([tone] * NUM_SYMBOLS, base_freq_hz=base, sample_rate_hz=fs)
    sig = out[out != 0.0]
    # Estimate dominant frequency via zero-crossings over the active region.
    mid = sig[len(sig) // 4: 3 * len(sig) // 4]
    crossings = np.sum((mid[:-1] < 0) & (mid[1:] >= 0))
    est_freq = crossings / (len(mid) / fs)
    assert abs(est_freq - expected_freq) < TONE_SPACING_HZ  # within one tone bin


def test_negative_dt_is_clamped_to_zero():
    """Negative dt_s must render identically to dt_s=0 (harness_note contract for S3b).

    NOTE: when D-001 (true negative-DT playback) is implemented, this test must be
    removed or updated, because the clamping behaviour will intentionally change.
    At that point D-001 and D-003 are resolved together.
    """
    tones = [0] * NUM_SYMBOLS
    for start in (0, 36, 72):
        tones[start:start + 7] = [3, 1, 4, 0, 6, 5, 2]

    at_zero = modulator.modulate(tones, base_freq_hz=1500.0, dt_s=0.0)
    at_neg  = modulator.modulate(tones, base_freq_hz=1500.0, dt_s=-1.5)

    assert np.array_equal(at_zero, at_neg), (
        "Negative dt_s must be clamped to 0 — S3b harness_note relies on this contract."
    )
