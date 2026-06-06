"""L5/L6 — channel SNR scaling and WAV round-trip tests."""
import os
import tempfile

import numpy as np

from synth import channel, modulator, wavio
from synth.constants import NUM_SYMBOLS


def _signal(fs=48000):
    tones = [0] * NUM_SYMBOLS
    for start in (0, 36, 72):
        tones[start:start + 7] = [3, 1, 4, 0, 6, 5, 2]
    return modulator.modulate(tones, base_freq_hz=1500.0, sample_rate_hz=fs), fs


def test_measured_inband_snr_matches_target():
    sig, fs = _signal()
    for target in (-24.0, -12.0, 0.0, 3.0):
        noisy = channel.add_noise(sig, target, seed=42, sample_rate_hz=fs)
        measured = channel.measure_inband_snr_db(sig, noisy, sample_rate_hz=fs)
        assert abs(measured - target) < 0.5, f"target {target} -> measured {measured}"


def test_noise_is_seed_reproducible():
    sig, fs = _signal()
    a = channel.add_noise(sig, -10.0, seed=7, sample_rate_hz=fs)
    b = channel.add_noise(sig, -10.0, seed=7, sample_rate_hz=fs)
    c = channel.add_noise(sig, -10.0, seed=8, sample_rate_hz=fs)
    assert np.array_equal(a, b)          # same seed -> identical realisation
    assert not np.array_equal(a, c)      # different seed -> different noise


def test_wav_roundtrip_preserves_shape_and_rate():
    sig, fs = _signal()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.wav")
        wavio.write_wav(path, sig, sample_rate_hz=fs)
        back, rate = wavio.read_wav(path)
    assert rate == fs
    assert len(back) == len(sig)
    # Peak-normalised waveform should correlate strongly with the original.
    corr = np.corrcoef(back, sig)[0, 1]
    assert corr > 0.99
