#!/usr/bin/env python3
"""Diagnostic: verify_noise_psd at 3 kHz and 4 kHz cutoffs.

Generates a 10-second filtered noise buffer at each cutoff frequency,
runs verify_noise_psd for the pass/fail verdict, and also prints the
raw passband deviation and stopband attenuation figures.

Run from the repo root:
    python qa/rr-study/tests/siggen/diagnose_noise_psd.py
"""
from __future__ import annotations

import io
import os
import sys

# Force UTF-8 on Windows consoles that default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Allow imports from qa/rr-study/ regardless of working directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
from scipy import signal as _signal

from synth.channel import (
    _lowpass_fir,
    _LOG_FLOOR,
    _WELCH_NPERSEG,
    _PASSBAND_LOWER_HZ,
    _PASSBAND_UPPER_FRACTION,
    _STOPBAND_CHECK_FACTOR,
    verify_noise_psd,
)
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

FS = DEFAULT_SAMPLE_RATE_HZ
DURATION_S = 10.0  # 10 s → stable Welch estimate; matches test_channel.py
N = int(FS * DURATION_S)


def _run_check(cutoff_hz: float, seed: int) -> None:
    """Generate bandlimited noise, verify it, and print diagnostic figures."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(N)
    filtered = _lowpass_fir(white, cutoff_hz, FS)

    # Reproduce RC-4 renormalisation (np.std-based RMS restore).
    filtered = filtered / np.std(filtered)

    # ── pass/fail verdict ────────────────────────────────────────────────────
    ok = verify_noise_psd(
        filtered, cutoff_hz, sample_rate_hz=FS, tolerance_db=1.0, assert_ok=False
    )

    # ── raw figures (same Welch calculation as verify_noise_psd) ────────────
    freqs, psd = _signal.welch(filtered, fs=float(FS), nperseg=_WELCH_NPERSEG)
    psd_db = 10.0 * np.log10(np.maximum(psd, _LOG_FLOOR))

    passband_mask = (freqs >= _PASSBAND_LOWER_HZ) & (freqs <= cutoff_hz * _PASSBAND_UPPER_FRACTION)
    pb_psd_db = psd_db[passband_mask]
    pb_mean_db = float(np.mean(pb_psd_db))
    pb_deviation_db = float(np.max(np.abs(pb_psd_db - pb_mean_db)))

    stopband_hz = cutoff_hz * _STOPBAND_CHECK_FACTOR
    stopband_idx = int(np.argmin(np.abs(freqs - stopband_hz)))
    stopband_psd_db = float(psd_db[stopband_idx])
    stopband_attenuation_db = pb_mean_db - stopband_psd_db

    pb_low_hz = _PASSBAND_LOWER_HZ
    pb_high_hz = cutoff_hz * _PASSBAND_UPPER_FRACTION

    verdict = "PASS" if ok else "FAIL"
    print(f"\n--- cutoff {cutoff_hz:.0f} Hz  (seed {seed}) ---")
    print(f"  Verdict                          : {verdict}")
    print(f"  Passband ({pb_low_hz:.0f}–{pb_high_hz:.0f} Hz) mean  : {pb_mean_db:.2f} dB")
    print(f"  Passband peak deviation          : {pb_deviation_db:.3f} dB  (tolerance ≤ 1.0 dB)")
    print(f"  Stopband @ {stopband_hz:.0f} Hz             : {stopband_attenuation_db:.1f} dB attenuation  (required ≥ 30 dB)")
    print(f"  Post-filter peak amplitude       : {float(np.max(np.abs(filtered))):.3f}  (renorm sigma=1.0)")


if __name__ == "__main__":
    print("verify_noise_psd diagnostic -- 10 s Kaiser FIR noise, renorm sigma=1.0")
    _run_check(cutoff_hz=4000.0, seed=7)
    _run_check(cutoff_hz=3000.0, seed=13)
    print()
