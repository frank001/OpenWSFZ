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


def instantaneous_phase(
    tones: list[int],
    base_freq_hz: float,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    *,
    drift_hz: float = 0.0,
) -> np.ndarray:
    """Return the unwrapped, unplaced instantaneous phase (radians) for `tones`.

    Factored out of :func:`modulate` (2026-09-15, E4-BENCH FADE family, Sec.2.3) so that
    FADE can build the complex analytic signal ``z(t) = exp(j*phase(t))`` "from the
    modulator's own phase" without duplicating this computation -- there is exactly one
    place this arithmetic exists. `modulate` itself is now a thin wrapper around this
    function plus :func:`_apply_click_envelope` and :func:`_place_in_slot`; the refactor
    changes no arithmetic and no operation order, so its output is unchanged (verified
    byte-identical against the pre-refactor function, ROW 0a(i)).

    Length is the transmission span only (``NUM_SYMBOLS`` symbols at `sample_rate_hz`),
    NOT yet placed into a slot. See :func:`modulate`'s docstring for `drift_hz`.
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
    if drift_hz != 0.0:
        t_tx = np.arange(len(smoothed), dtype=np.float64) / fs
        transmission_s = len(smoothed) / fs
        inst_freq = inst_freq + drift_hz * (t_tx / transmission_s - 0.5)
    return 2.0 * np.pi * np.cumsum(inst_freq) / fs


def _apply_click_envelope(signal: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    """Apply the 10 ms raised-cosine fade-in/out in place and return `signal`.

    Factored out of :func:`modulate` unchanged (see that function's original comment,
    preserved below) -- eliminates the audible click at slot boundaries.
    """
    # Apply a short raised-cosine fade-in and fade-out to eliminate the audible
    # click that would otherwise occur where the signal abruptly starts and stops
    # against silence.  Without this, the signal ends at an arbitrary phase
    # (e.g. amplitude = −0.74 followed immediately by 0.0 silence), producing a
    # 0.74-amplitude step — clearly audible as a click.  Real FT8 transmitters
    # use a similar RF ramp (typically 5–20 ms).  A 10 ms Hann ramp is
    # inaudible as a ramp but removes the click completely.  The fade is applied
    # to the signal BEFORE placement so that the slot boundaries stay at zero.
    fs = sample_rate_hz
    _FADE_S = 0.010  # 10 ms
    n_fade = int(round(_FADE_S * fs))
    n_fade = min(n_fade, len(signal) // 2)          # guard for very short signals
    fade = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_fade) / n_fade))
    signal[:n_fade]  *= fade
    signal[-n_fade:] *= fade[::-1]
    return signal


def _place_in_slot(
    signal: np.ndarray,
    dt_s: float,
    sample_rate_hz: int,
    slot_length_s: float,
    extended: bool,
):
    """Place a transmission-length `signal` into a slot at `dt_s`. See :func:`modulate`."""
    fs = sample_rate_hz

    # Place at the DT offset -- exactly, or refuse (C1). No clamping past this point.
    slot_samples = int(round(slot_length_s * fs))
    start = int(round(dt_s * fs))
    end = start + len(signal)

    if not extended:
        if start < 0 or end > slot_samples:
            max_dt_s = (slot_samples - len(signal)) / fs
            raise ValueError(
                f"dt_s={dt_s:.4f} places a {len(signal) / fs:.4f} s signal at samples "
                f"[{start}, {end}) which does not fit inside a single {slot_length_s:.2f} s "
                f"slot buffer [0, {slot_samples}). Single-slot dt_s must be in "
                f"[0.0000, {max_dt_s:.4f}]. Pass extended=True to render across slot "
                f"boundaries instead of raising (contracts C1/C2, Route B)."
            )
        slot = np.zeros(slot_samples, dtype=np.float64)
        slot[start: end] = signal
        return slot

    # extended=True (C2): grow the buffer to bound both the nominal slot and the
    # signal's actual placement, whichever is larger on each side. `buffer_start_samples`
    # is <= 0 whenever the signal starts before the nominal slot (negative dt_s) and is
    # exactly 0 whenever the placement already fits in a single slot -- see docstring.
    buffer_start_samples = min(0, start)
    buffer_end_samples = max(slot_samples, end)
    buffer = np.zeros(buffer_end_samples - buffer_start_samples, dtype=np.float64)
    local_start = start - buffer_start_samples
    buffer[local_start: local_start + len(signal)] = signal
    buffer_start_s = buffer_start_samples / fs
    return buffer, buffer_start_s


def modulate(
    tones: list[int],
    base_freq_hz: float,
    dt_s: float = 0.0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    slot_length_s: float = SLOT_LENGTH_S,
    amplitude: float = 1.0,
    *,
    extended: bool = False,
    drift_hz: float = 0.0,
):
    """Render `tones` as GFSK audio, placed at `dt_s` relative to a `slot_length_s` slot.

    `base_freq_hz` is the audio frequency of tone 0; tone k sits at base + k * 6.25 Hz.

    Route B / contracts C1-C2 (2026-08-19, following the 2026-08-19 discovery that the
    prior implementation silently clamped `dt_s` at BOTH ends -- see
    ``qa/rr-study/2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md``):
    placement is exact to one sample, or the call fails loudly. There is no longer any
    `dt_s` value this function will silently mis-place.

    Default (``extended=False``) -- SINGLE-SLOT CONTRACT, unchanged return shape/semantics
    for every existing caller. Returns a `slot_length_s`-long float64 array with the signal
    placed at sample ``round(dt_s * fs)``. If that placement does not fit entirely inside
    ``[0, slot_length_s)`` -- true for any `dt_s` outside
    ``[0, slot_length_s - transmission_s]`` (~[0.0, 2.36] s at the FT8 defaults: a 12.64 s
    transmission in a 15 s slot) -- raises `ValueError` instead of clamping. This is the
    replacement for the `24b6d9f` (2026-06-05) clamp that made S3 parts labelled 2.4 s and
    2.7 s both render at 2.3600 s under two different truth labels for two and a half months.

    ``extended=True`` -- MULTI-SLOT CONTRACT, opt-in, for S3b/negative-DT and any positive
    `dt_s` beyond the single-slot cap. Returns ``(buffer, buffer_start_s)``: `buffer_start_s`
    is the offset, in seconds, of `buffer` sample 0 relative to the nominal slot boundary,
    always <= 0.0. Whenever the requested placement already fits inside a single slot,
    `buffer_start_s` is exactly 0.0 and `buffer` is byte-identical to what `extended=False`
    would return -- this mode is a superset of the single-slot contract, not a divergent one.
    The caller (`run_scenario.py`, C3) must arm playback `buffer_start_s` seconds relative to
    the nominal slot boundary so that `buffer` sample 0 reaches the device at time
    ``boundary + buffer_start_s``.

    ``drift_hz`` -- E4-BENCH DRIFT family (2026-09-15 architect-to-qa spec, Sec.2.2), default
    0.0. Linear transmitter-frequency ramp across the transmission, centred so the mean
    frequency is unchanged: ``inst_freq(t) += drift_hz * (t / T_tx - 0.5)`` for
    ``t in [0, T_tx)``, where ``T_tx`` is the transmission length (``NUM_SYMBOLS *
    SYMBOL_PERIOD_S``, 12.64 s at the FT8 defaults) and ``t`` is time since the start of the
    (unplaced) transmission array -- NOT since the slot boundary, so `dt_s` does not shift the
    ramp's own timing. At the default ``drift_hz=0.0`` the added term is an array of exact
    ``0.0``s (IEEE 754: ``0.0 * finite = 0.0``, ``x + 0.0 = x``), so the default path stays
    bit-for-bit identical to a caller that never passes this parameter at all (ROW 0a(i)).
    Sign is the caller's choice (E4 alternates it by trial); this function does not alternate
    it itself.
    """
    phase = instantaneous_phase(tones, base_freq_hz, sample_rate_hz, drift_hz=drift_hz)
    signal = amplitude * np.sin(phase)
    signal = _apply_click_envelope(signal, sample_rate_hz)
    return _place_in_slot(signal, dt_s, sample_rate_hz, slot_length_s, extended)
