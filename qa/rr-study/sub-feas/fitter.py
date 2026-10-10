#!/usr/bin/env python3
"""SUB-FEAS core: template synthesis, fine positional fit, envelope estimation,
residual/suppression metrics (spec sec.4/5).

Method: Franke, Somerville & Taylor, "The FT4 and FT8 Communication Protocols",
QEX, July/Aug 2020 -- METHOD ONLY (per the spec's licence note); every line below
is a from-scratch numpy implementation, reusing this repo's OWN existing, already-
reviewed GFSK synthesiser (qa/rr-study/synth/modulator.py, MIT-licensed ft8_lib
vendor mirrors it per that module's own history) rather than transcribing anything
from the QEX paper or WSJT-X.

All functions here are purely numeric (tones/PCM arrays in, floats/arrays out) --
no message text ever enters this module (HK-037).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

import common
import synth.modulator as MOD
from synth.constants import NUM_SYMBOLS

FS = common.SAMPLE_RATE_HZ           # 12000 Hz -- matches the real corpus WAVs
N_TX = NUM_SYMBOLS * 1920            # 79 * 1920 = 151,680 samples (12.64 s @ 12 kHz)
assert N_TX == 151680, N_TX          # inherited-constant assertion (HK rule)
SAMPLES_PER_MS = FS // 1000
assert SAMPLES_PER_MS == 12, SAMPLES_PER_MS

TRANSMISSION_S = N_TX / FS           # 12.64 s, exact


def r_fit(tones: list) -> np.ndarray:
    """Unit-amplitude complex reference carrier for `tones` at baseband (freq 0 --
    the frequency offset is applied separately as a phase ramp during the search,
    not baked in here, so one template serves every frequency candidate)."""
    phase = MOD.instantaneous_phase(tones, 0.0, FS)
    return np.exp(1j * phase).astype(np.complex128)


def r_fit_drift(tones: list, fdot_hz_per_s: float) -> np.ndarray:
    """Amendment 2: unit-amplitude baseband template with an added linear drift
    rate `fdot_hz_per_s` (Hz/s), instantaneous frequency offset
    `fdot * (t - T_tx/2)` -- reuses modulator.instantaneous_phase's OWN existing
    `drift_hz` parameter (centred linear ramp, total excursion = drift_hz over
    the transmission) rather than re-deriving the integration: `drift_hz =
    fdot_hz_per_s * TRANSMISSION_S` gives instantaneous offset
    `drift_hz * (t/T_tx - 0.5) = fdot * (t - T_tx/2)`, algebraically identical to
    Amendment 2's own `fdot * (t - t_mid)` formula. At `fdot=0` this is byte-for-
    byte `r_fit(tones)` (modulator.py's own documented zero-drift identity)."""
    drift_hz = fdot_hz_per_s * TRANSMISSION_S
    phase = MOD.instantaneous_phase(tones, 0.0, FS, drift_hz=drift_hz)
    return np.exp(1j * phase).astype(np.complex128)


def extract_segment(x_a: np.ndarray, start_sample: int) -> "np.ndarray | None":
    """x_a: analytic signal of a full 15 s cycle buffer (BUFFER_SAMPLES). Returns
    the N_TX-length segment starting at start_sample, or None if that would run
    outside the buffer."""
    if start_sample < 0 or start_sample + N_TX > len(x_a):
        return None
    return x_a[start_sample:start_sample + N_TX]


# ── Fine fit: integer-sample Δt grid (1 ms = SAMPLES_PER_MS samples, exact -- no
# interpolation needed) x FFT-based Δf search (spec sec.4 step 2). ────────────

def _freq_search(mixed: np.ndarray, n_fft: int, f_range_hz: float):
    """argmax_f |FFT(mixed, n_fft)| restricted to |f| <= f_range_hz. Returns
    (best_f_hz, best_val, at_edge: bool)."""
    spec = np.fft.fft(mixed, n_fft)
    freqs = np.fft.fftfreq(n_fft, d=1.0 / FS)
    idx = np.where(np.abs(freqs) <= f_range_hz)[0]
    mag = np.abs(spec[idx])
    k = int(np.argmax(mag))
    best_f = float(freqs[idx][k])
    best_val = float(mag[k])
    step = FS / n_fft
    at_edge = (f_range_hz - abs(best_f)) < (1.5 * step)
    return best_f, best_val, at_edge


def apply_freq_shift(r_unit: np.ndarray, df_hz: float) -> np.ndarray:
    t = np.arange(len(r_unit), dtype=np.float64) / FS
    return r_unit * np.exp(1j * 2.0 * np.pi * df_hz * t)


def fine_fit(x_a: np.ndarray, tones: list, freq_hz: float, nominal_t_s: float,
             dt_range_ms: float = 60.0, dt_step_ms: float = 1.0,
             df_range_hz: float = 2.0, n_fft: int = 262144):
    """Spec sec.4 steps 1-2. `freq_hz` is the nominal (decoded) frequency; the
    Δf search below is a RESIDUAL correction around it (± df_range_hz), not a
    search for the base frequency itself -- the template is shifted to `freq_hz`
    FIRST (`r_base`), and `_freq_search` only has to find the small leftover
    offset. Returns a dict: best_dt_s, best_df_hz (residual, add to `freq_hz` for
    the absolute fitted frequency), best_val, at_edge_t, at_edge_f, r_base (the
    freq_hz-shifted unit template, baseband-local-time, for envelope reuse), seg
    (the best-position segment), or None if every candidate ran off the buffer
    edge."""
    r_unit = r_fit(tones)
    r_base = apply_freq_shift(r_unit, freq_hz)   # local-time axis, same for every Δt
    n_steps = int(round(dt_range_ms / dt_step_ms))
    step_samples = int(round(dt_step_ms * SAMPLES_PER_MS))
    base_start = int(round(nominal_t_s * FS))

    best = None  # (val, dt_ms, df_hz, at_edge_f, seg)
    for k in range(-n_steps, n_steps + 1):
        dt_ms = k * dt_step_ms
        start = base_start + k * step_samples
        seg = extract_segment(x_a, start)
        if seg is None:
            continue
        mixed = seg * np.conj(r_base)
        f_hat, val, edge_f = _freq_search(mixed, n_fft, df_range_hz)
        if best is None or val > best[0]:
            best = (val, dt_ms, f_hat, edge_f, seg)

    if best is None:
        return None
    val, dt_ms, df_hz, edge_f, seg = best
    at_edge_t = abs(dt_ms) >= (dt_range_ms - dt_step_ms / 2.0)
    return {
        "best_dt_s": dt_ms / 1000.0,
        "best_df_hz": df_hz,
        "best_val": val,
        "at_edge_t": bool(at_edge_t),
        "at_edge_f": bool(edge_f),
        "r_base": r_base,
        "seg": seg,
        "start_sample": base_start + int(round(dt_ms / 1000.0 * FS)),
    }


FDOT_RANGE_HZ_PER_S = 0.10
FDOT_STEP_HZ_PER_S = 0.005


def fine_fit_with_drift(x_a: np.ndarray, tones: list, freq_hz: float, nominal_t_s: float,
                         dt_range_ms: float = 100.0, dt_step_ms: float = 1.0,
                         df_range_hz: float = 2.0, n_fft: int = 262144,
                         fdot_range: float = FDOT_RANGE_HZ_PER_S,
                         fdot_step: float = FDOT_STEP_HZ_PER_S):
    """Amendment 2 (arch/subtraction-feasibility cdba5cf4): adds a linear drift-
    rate term to the fine fit, coarse-to-fine, disclosed equivalent of the spec's
    own search order --
      1. fit (Δt, Δf) at ḟ=0 (plain `fine_fit`, now with the widened ±100ms box).
      2. search ḟ over [-0.10, +0.10] Hz/s (0.005 steps), Δt HELD at step 1's
         value, Δf RE-FITTED at each ḟ (same `_freq_search`); keep the best-
         scoring (ḟ, Δf) pair.
      3. refine Δt once more (same ±100ms grid), (ḟ, Δf) HELD at step 2's values,
         scoring each Δt candidate directly (no further Δf search).
    Returns the same dict shape as `fine_fit`, plus `best_fdot_hz_per_s` and
    `at_edge_fdot`; `r_base` is the freq_hz-shifted, DRIFT-INCLUDED unit template
    (still not yet Δf-shifted -- callers apply `best_df_hz` via `apply_freq_shift`
    exactly as with plain `fine_fit`, so bigfit.py's L1/L2 construction is
    unchanged). L0 (the June control) must NOT call this function -- it stays on
    plain `r_fit`/lattice-snap, per Amendment 2."""
    step0 = fine_fit(x_a, tones, freq_hz, nominal_t_s, dt_range_ms, dt_step_ms, df_range_hz, n_fft)
    if step0 is None:
        return None
    seg = step0["seg"]

    n_fdot_steps = int(round(fdot_range / fdot_step))
    best = None  # (val, fdot, df_hz, edge_f)
    for kf in range(-n_fdot_steps, n_fdot_steps + 1):
        fdot = kf * fdot_step
        r_unit_fdot = r_fit_drift(tones, fdot)
        r_base_fdot = apply_freq_shift(r_unit_fdot, freq_hz)
        mixed = seg * np.conj(r_base_fdot)
        f_hat, val, edge_f = _freq_search(mixed, n_fft, df_range_hz)
        if best is None or val > best[0]:
            best = (val, fdot, f_hat, edge_f)
    _val, fdot_star, df_star, edge_f = best
    at_edge_fdot = abs(fdot_star) >= (fdot_range - fdot_step / 2.0)

    r_unit_final = r_fit_drift(tones, fdot_star)
    r_base_final = apply_freq_shift(r_unit_final, freq_hz)
    r_template_final = apply_freq_shift(r_base_final, df_star)

    n_steps = int(round(dt_range_ms / dt_step_ms))
    step_samples = int(round(dt_step_ms * SAMPLES_PER_MS))
    base_start = int(round(nominal_t_s * FS))
    best_t = None  # (score, dt_ms, seg)
    for k in range(-n_steps, n_steps + 1):
        dt_ms = k * dt_step_ms
        start = base_start + k * step_samples
        seg_k = extract_segment(x_a, start)
        if seg_k is None:
            continue
        score = float(np.abs(np.sum(seg_k * np.conj(r_template_final))))
        if best_t is None or score > best_t[0]:
            best_t = (score, dt_ms, seg_k)
    if best_t is None:
        return None
    score, dt_ms_final, seg_final = best_t
    at_edge_t = abs(dt_ms_final) >= (dt_range_ms - dt_step_ms / 2.0)

    return {
        "best_dt_s": dt_ms_final / 1000.0,
        "best_df_hz": df_star,
        "best_fdot_hz_per_s": fdot_star,
        "best_val": score,
        "at_edge_t": bool(at_edge_t),
        "at_edge_f": bool(edge_f),
        "at_edge_fdot": bool(at_edge_fdot),
        "r_base": r_base_final,
        "seg": seg_final,
        "start_sample": base_start + int(round(dt_ms_final / 1000.0 * FS)),
    }


# ── Envelope estimation (spec sec.4 step 3) ───────────────────────────────────

def lp_envelope(x_seg: np.ndarray, r_seg: np.ndarray, w_s: float) -> np.ndarray:
    """c(t): Hann-weighted moving-average complex-gain envelope. W >= the full
    transmission span is treated as "one complex scalar for the whole 12.64 s"
    (June's model) -- broadcast, not a windowed convolution (avoids edge-window
    algebra that would otherwise not reduce to a true global average; see the
    accompanying report for the derivation)."""
    n = len(x_seg)
    num = x_seg * np.conj(r_seg)
    den = np.abs(r_seg) ** 2
    w_samples = int(round(w_s * FS))
    if w_samples >= n:
        c0 = np.sum(num) / np.sum(den)
        return np.full(n, c0, dtype=complex)
    win = np.hanning(w_samples)
    num_c = fftconvolve(num, win, mode="same")
    den_c = fftconvolve(den, win, mode="same")
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(den_c > 1e-12, num_c / np.where(den_c == 0, 1.0, den_c), 0.0)
    return c


def subtract(x_seg: np.ndarray, r_seg: np.ndarray, w_s: float) -> np.ndarray:
    """s_hat = Re{c(t) r(t)}; returns residual y = Re{x_seg} - s_hat (both real)."""
    c = lp_envelope(x_seg, r_seg, w_s)
    s_hat = np.real(c * r_seg)
    return np.real(x_seg) - s_hat


# ── Metrics (spec sec.5) ───────────────────────────────────────────────────────

BAND_LOW_OFFSET_HZ = -6.25
BAND_HIGH_OFFSET_HZ = 50.0
NOISE_BAND_LO_HZ = 200.0
NOISE_BAND_HI_HZ = 2800.0
BIN_HZ = 6.25
NOISE_PERCENTILE = 20.0


def _band_energy(y_real: np.ndarray, lo_hz: float, hi_hz: float) -> float:
    win = np.hanning(len(y_real))
    yw = y_real * win
    spec = np.fft.rfft(yw)
    power = spec.real ** 2 + spec.imag ** 2
    freqs = np.fft.rfftfreq(len(y_real), d=1.0 / FS)
    mask = (freqs >= lo_hz) & (freqs < hi_hz)
    return float(power[mask].sum())


def noise_floor(y_real: np.ndarray, band_width_hz: float) -> float:
    """N_hat: 20th percentile of per-6.25 Hz-bin energy across [200, 2800) Hz,
    scaled to band_width_hz (spec sec.5)."""
    win = np.hanning(len(y_real))
    yw = y_real * win
    spec = np.fft.rfft(yw)
    power = spec.real ** 2 + spec.imag ** 2
    freqs = np.fft.rfftfreq(len(y_real), d=1.0 / FS)
    edges = np.arange(NOISE_BAND_LO_HZ, NOISE_BAND_HI_HZ, BIN_HZ)
    bin_energies = []
    for lo in edges:
        hi = lo + BIN_HZ
        mask = (freqs >= lo) & (freqs < hi)
        if mask.any():
            bin_energies.append(power[mask].sum())
    if not bin_energies:
        return float("nan")
    per_bin = float(np.percentile(bin_energies, NOISE_PERCENTILE))
    n_bins_in_band = band_width_hz / BIN_HZ
    return per_bin * n_bins_in_band


def residual_metrics(x_seg: np.ndarray, y_residual: np.ndarray, freq_hz: float) -> dict:
    """Returns X (dB, residual-above-noise), D (dB, suppression), and N_hat."""
    lo = freq_hz + BAND_LOW_OFFSET_HZ
    hi = freq_hz + BAND_HIGH_OFFSET_HZ
    band_width = hi - lo
    e_residual = _band_energy(y_residual, lo, hi)
    e_original = _band_energy(np.real(x_seg), lo, hi)
    n_hat = noise_floor(y_residual, band_width)
    x_db = 10.0 * np.log10(e_residual / n_hat) if (n_hat and n_hat > 0 and e_residual > 0) else float("nan")
    d_db = 10.0 * np.log10(e_original / e_residual) if (e_residual > 0 and e_original > 0) else float("nan")
    return {"X_db": float(x_db), "D_db": float(d_db), "N_hat": float(n_hat),
            "E_residual": float(e_residual), "E_original": float(e_original)}
