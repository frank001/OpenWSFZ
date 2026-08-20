"""L4 — modulator tests (structure, duration, instantaneous frequency, placement)."""
import numpy as np
import pytest
from scipy.signal import fftconvolve

from synth import modulator
from synth.constants import (
    COSTAS_ARRAY,
    NUM_SYMBOLS,
    SLOT_LENGTH_S,
    SYMBOL_PERIOD_S,
    TONE_SPACING_HZ,
)


def _measured_dt_s(candidate: np.ndarray, buffer_start_s: float,
                    reference: np.ndarray, fs: int) -> float:
    """Cross-correlate `candidate` (an extended-mode buffer starting `buffer_start_s`
    relative to the nominal slot boundary) against `reference` (a non-extended, dt_s=0.0
    render of the SAME tones) and return the empirically measured dt_s.

    This is the black-box placement proof (contracts C1/C2, gate G1) at unit-test scale —
    the same method as g1_s3_positive_grid_placement_check.py — deliberately NOT a
    re-derivation of modulate()'s own placement arithmetic, so it catches a placement bug
    modulate() might have regardless of whether that bug also corrupts the formula a
    white-box test would recompute.
    """
    corr = fftconvolve(candidate, reference[::-1], mode="full")
    lag_samples = int(np.argmax(corr)) - (len(reference) - 1)
    return buffer_start_s + lag_samples / fs


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


def test_negative_dt_shifts_signal_earlier():
    """Negative dt_s must render GENUINELY EARLY audio — the direct inversion of the
    retired clamp-to-zero contract this test replaces (name kept, deliberately renamed
    rather than deleted, so a diff shows a CONTRACT CHANGE rather than a lost test — see
    contracts C1/C2, qa/rr-study/2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md
    §3). Was `test_negative_dt_is_clamped_to_zero`, asserted array_equal(at_zero, at_neg).
    """
    tones = [0] * NUM_SYMBOLS
    for start in (0, 36, 72):
        tones[start:start + 7] = [3, 1, 4, 0, 6, 5, 2]

    fs = 48000
    buffer, buffer_start_s = modulator.modulate(
        tones, base_freq_hz=1500.0, dt_s=-1.5, sample_rate_hz=fs, extended=True,
    )
    assert buffer_start_s == -1.5, "buffer must start 1.5 s before the nominal slot boundary"

    # "Genuinely early" (C2): energy exists in the samples BEFORE the nominal slot
    # boundary — the tail of the preceding slot. The retired clamp had ZERO energy there,
    # ever, for any negative dt_s.
    boundary_local_index = int(round(-buffer_start_s * fs))  # local index of absolute t=0
    pre_boundary_energy = np.mean(buffer[:boundary_local_index] ** 2)
    assert pre_boundary_energy > 0.0

    # Black-box placement proof: the SIGNAL content itself, not merely "some energy",
    # sits at dt_s = -1.5 s, to one sample.
    at_zero = modulator.modulate(tones, base_freq_hz=1500.0, dt_s=0.0, sample_rate_hz=fs)
    measured_dt_s = _measured_dt_s(buffer, buffer_start_s, at_zero, fs)
    assert abs(measured_dt_s - (-1.5)) <= 1.0 / fs


def test_positive_dt_beyond_single_slot_raises_or_places_exactly():
    """S3 part 9's SS0 defect case (label dt_s=2.7 s): a 12.64 s transmission in a 15 s
    slot cannot start at 2.7 s and finish inside that same slot (max is ~2.36 s). C1: the
    non-extended (default) call must RAISE — the retired contract silently saturated this
    to 2.3600 s, identical to part 8's 2.4 s label. extended=True must place it exactly.
    """
    tones = _tones()
    fs = 48000
    base = 1500.0

    with pytest.raises(ValueError):
        modulator.modulate(tones, base_freq_hz=base, dt_s=2.7, sample_rate_hz=fs)

    buffer, buffer_start_s = modulator.modulate(
        tones, base_freq_hz=base, dt_s=2.7, sample_rate_hz=fs, extended=True,
    )
    assert buffer_start_s == 0.0  # positive dt_s never needs an earlier-than-0 buffer

    at_zero = modulator.modulate(tones, base_freq_hz=base, dt_s=0.0, sample_rate_hz=fs)
    measured_dt_s = _measured_dt_s(buffer, buffer_start_s, at_zero, fs)
    assert abs(measured_dt_s - 2.7) <= 1.0 / fs


def test_extended_matches_single_slot_when_placement_already_fits():
    """extended=True is a superset of the single-slot contract, not a divergent one: for
    any dt_s that already fits in one slot, it must return buffer_start_s=0.0 and content
    byte-identical to the non-extended call (docstring claim, checked directly)."""
    tones = _tones()
    fs = 48000
    single = modulator.modulate(tones, base_freq_hz=1500.0, dt_s=0.9, sample_rate_hz=fs)
    buffer, buffer_start_s = modulator.modulate(
        tones, base_freq_hz=1500.0, dt_s=0.9, sample_rate_hz=fs, extended=True,
    )
    assert buffer_start_s == 0.0
    assert np.array_equal(single, buffer)
