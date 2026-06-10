"""L5/L6 — channel SNR scaling and WAV round-trip tests."""
import os
import tempfile

import numpy as np
from scipy import signal as sp

from synth import channel, modulator, wavio
from synth.channel import (
    _LOG_FLOOR,
    _PASSBAND_LOWER_HZ,
    _PASSBAND_UPPER_FRACTION,
    _WELCH_NPERSEG,
)
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


# ── FIR filter quality tests (fix-synth-brickwall-noise-filter) ──────────────

def _pure_bandlimited_noise(cutoff_hz: float, fs: int = 48_000,
                             duration_s: float = 10.0, seed: int = 42) -> np.ndarray:
    """Return pure bandlimited noise (signal=zeros) for PSD inspection.

    10 s default gives ~233 Welch segments (nperseg=4096, 50% overlap) which
    reduces the peak passband deviation from ~1.8 dB (2 s) to well below 1 dB.
    """
    n = int(fs * duration_s)
    return channel.add_awgn(np.zeros(n), sigma=1.0, seed=seed,
                             noise_cutoff_hz=cutoff_hz, sample_rate_hz=fs)


def test_fir_no_gibbs_ridge():
    """Stopband at 1.2× cutoff must be ≥ 30 dB below passband mean.

    The former brick-wall FFT filter produced a Gibbs-phenomenon ridge near the
    cutoff; the Kaiser FIR filter has deep stopband attenuation there instead.
    We check at 1.2× cutoff because that is well into the stopband (the −6 dB
    transition point of firwin is exactly at cutoff, not 30 dB below it).
    """
    fs = 48_000
    cutoff = 4000.0
    stopband_check_hz = cutoff * 1.2  # 4800 Hz — stopband for 4 kHz Kaiser FIR
    noise = _pure_bandlimited_noise(cutoff, fs=fs)
    freqs, psd = sp.welch(noise, fs=float(fs), nperseg=_WELCH_NPERSEG)
    psd_db = 10.0 * np.log10(np.maximum(psd, _LOG_FLOOR))
    passband_mask = (freqs >= _PASSBAND_LOWER_HZ) & (freqs <= cutoff * _PASSBAND_UPPER_FRACTION)
    pb_mean_db = float(np.mean(psd_db[passband_mask]))
    sb_idx = int(np.argmin(np.abs(freqs - stopband_check_hz)))
    sb_psd_db = float(psd_db[sb_idx])
    attenuation_db = pb_mean_db - sb_psd_db
    assert attenuation_db >= 30.0, (
        f"Insufficient stopband attenuation at {freqs[sb_idx]:.0f} Hz: "
        f"only {attenuation_db:.1f} dB below passband mean (need ≥ 30 dB)"
    )


def test_fir_passband_flat_4khz():
    """verify_noise_psd returns True on FIR-filtered noise with a 4 kHz cutoff.

    Uses a 10-second noise vector to keep Welch variance below the ±1 dB tolerance.
    """
    fs = 48_000
    cutoff = 4000.0
    noise = _pure_bandlimited_noise(cutoff, fs=fs, seed=7)
    result = channel.verify_noise_psd(noise, cutoff, sample_rate_hz=fs,
                                      tolerance_db=1.0, assert_ok=True)
    assert result is True


def test_fir_passband_flat_3khz():
    """verify_noise_psd returns True on FIR-filtered noise with a 3 kHz cutoff.

    Uses a 10-second noise vector to keep Welch variance below the ±1 dB tolerance.
    """
    fs = 48_000
    cutoff = 3000.0
    noise = _pure_bandlimited_noise(cutoff, fs=fs, seed=13)
    result = channel.verify_noise_psd(noise, cutoff, sample_rate_hz=fs,
                                      tolerance_db=1.0, assert_ok=True)
    assert result is True


def test_output_length_preserved():
    """add_awgn with noise_cutoff_hz must return the exact same number of samples."""
    sig, fs = _signal()
    n = len(sig)
    result = channel.add_awgn(sig, sigma=0.1, seed=42,
                               noise_cutoff_hz=4000.0, sample_rate_hz=fs)
    assert len(result) == n, f"length changed: {n} -> {len(result)}"


def test_snr_preserved_with_cutoff():
    """In-band SNR must be within ±0.5 dB of target when noise_cutoff_hz=4000 is set.

    Calls add_noise (not add_awgn) — the high-level API now accepts noise_cutoff_hz
    so callers do not need to compute sigma manually (F-001 fix).
    """
    sig, fs = _signal()
    target_snr = 0.0
    noisy = channel.add_noise(sig, target_snr, seed=99,
                               sample_rate_hz=fs, noise_cutoff_hz=4000.0)
    measured = channel.measure_inband_snr_db(sig, noisy, sample_rate_hz=fs)
    assert abs(measured - target_snr) < 0.5, (
        f"SNR not preserved: target {target_snr:.1f} dB, measured {measured:.3f} dB"
    )


def test_verify_noise_psd_rejects_unfiltered_white_noise():
    """verify_noise_psd must return False for unfiltered white noise.

    White noise has flat PSD across the full Nyquist band (0–24 kHz at 48 kHz).
    At 1.2 × cutoff (4800 Hz) the PSD equals the passband mean, giving ~0 dB
    stopband attenuation — well below the required 30 dB threshold.  This is
    the correct negative case: white noise represents the state *before* any
    lowpass filter is applied, and verify_noise_psd must reliably detect it.

    Note on the spec scenario — the original spec called for testing against
    'brickwall (FFT bin-zeroing) filtered noise'.  That case is physically
    incorrect as a negative test: FFT bin-zeroing on random Gaussian noise
    produces flat passband PSD and zero stopband PSD (both criteria pass).
    The Gibbs-phenomenon ridge is a time-domain artefact visible for
    deterministic signals, not a steady-state PSD feature of random noise.
    Unfiltered white noise is therefore the correct and deterministic negative
    case for the stopband criterion.
    """
    fs = 48_000
    cutoff = 4000.0
    rng = np.random.default_rng(42)
    n = int(fs * 10.0)  # 10 s gives a stable Welch estimate
    white_noise = rng.standard_normal(n)
    result = channel.verify_noise_psd(white_noise, cutoff, sample_rate_hz=fs,
                                      assert_ok=False)
    assert result is False, (
        "verify_noise_psd should reject unfiltered white noise "
        "(stopband attenuation ≈ 0 dB at 1.2× cutoff; need ≥ 30 dB)"
    )
