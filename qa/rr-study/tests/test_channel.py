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


def test_add_awgn_is_seed_reproducible_and_scales_to_sigma():
    sig, _ = _signal()
    a = channel.add_awgn(sig, sigma=0.1, seed=3)
    b = channel.add_awgn(sig, sigma=0.1, seed=3)
    assert np.array_equal(a, b)                       # same seed -> identical
    # On a zero buffer the result *is* the noise; its std-dev should match sigma.
    noise = channel.add_awgn(np.zeros(50_000), sigma=0.5, seed=1)
    assert abs(np.std(noise) - 0.5) < 0.02


def test_mix_single_signal_realises_target_snr():
    """One station via the mixer realises its target SNR vs the shared floor."""
    sig, fs = _signal()
    for target in (-10.0, 0.0, 3.0):
        mixed = channel.mix_to_shared_floor([sig], [target], seed=11, sample_rate_hz=fs)
        scaled_clean = (10.0 ** (target / 20.0)) * sig
        measured = channel.measure_inband_snr_db(scaled_clean, mixed, sample_rate_hz=fs)
        assert abs(measured - target) < 0.5, f"target {target} -> {measured}"


def test_mix_capture_pair_differs_in_level_only():
    """0 dB vs -10 dB stations share an identical floor; only strength differs.

    The old per-signal-noise convention rendered both at equal amplitude, so
    there was no capture ratio. Here the weak station is 10 dB down in level.
    """
    sig, fs = _signal()
    strong = channel.mix_to_shared_floor([sig], [0.0], seed=5, sample_rate_hz=fs)
    weak = channel.mix_to_shared_floor([sig], [-10.0], seed=5, sample_rate_hz=fs)
    # Same seed + floor referenced to the same unit signal => identical noise.
    noise_strong = strong - (10.0 ** (0.0 / 20.0)) * sig
    noise_weak = weak - (10.0 ** (-10.0 / 20.0)) * sig
    assert np.allclose(noise_strong, noise_weak, atol=1e-9)
    # And the strong station's clean contribution is ~3.16x (10 dB) the weak one.
    assert abs(np.std(strong - noise_strong) / np.std(weak - noise_weak)
               - 10.0 ** (10.0 / 20.0)) < 0.05


def test_mix_floor_independent_of_stack_size():
    """Adding more co-channel stations must not inflate the noise floor."""
    sig, fs = _signal()
    sigma0 = channel.noise_sigma_for_snr(sig, 0.0, sample_rate_hz=fs)
    one = channel.mix_to_shared_floor([sig], [0.0], seed=9, sample_rate_hz=fs)
    three = channel.mix_to_shared_floor([sig, sig, sig], [0.0, 0.0, 0.0],
                                        seed=9, sample_rate_hz=fs)
    noise_one = one - sig                 # 1-stack: floor only
    noise_three = three - 3.0 * sig       # 3-stack: floor only (clean sums to 3*sig)
    assert abs(np.std(noise_one) - sigma0) < sigma0 * 0.05
    assert abs(np.std(noise_three) - sigma0) < sigma0 * 0.05  # NOT sqrt(3)*sigma0


def test_mix_rejects_length_mismatch_and_empty():
    sig, _ = _signal()
    import pytest
    with pytest.raises(ValueError):
        channel.mix_to_shared_floor([sig], [0.0, 1.0], seed=0)
    with pytest.raises(ValueError):
        channel.mix_to_shared_floor([], [], seed=0)


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
