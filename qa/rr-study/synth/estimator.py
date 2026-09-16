"""E4-STAGE2 Sec.1 -- per-symbol channel-gain estimator.

Correlates known-message audio against its own (undistorted, undrifted)
reference GFSK carrier, one complex gain per symbol (``NUM_SYMBOLS`` = 79,
sampled at ``1 / SYMBOL_PERIOD_S`` = 6.25 Hz). Two statistics are derived from
that gain sequence for ROW 0a and the live census: ``rho1`` (fading) and the
total drift ``delta_f_hz`` across the transmission.

Reused unchanged between the bench-render calibration (ROW 0a, truth known by
construction) and the live C2 census (Sec.2-3) -- one estimator, two inputs,
per Stage-2 spec Sec.0.3.
"""
from __future__ import annotations

import numpy as np

from .constants import DEFAULT_SAMPLE_RATE_HZ, NUM_SYMBOLS, SYMBOL_PERIOD_S
from .modulator import instantaneous_phase


def extract_channel_gains(
    audio: np.ndarray,
    tones: "list[int]",
    base_freq_hz: float,
    dt_s: float = 0.0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """Return ``g[0..NUM_SYMBOLS-1]``, the complex channel gain per symbol.

    ``audio`` must contain the transmission window starting at ``dt_s``
    seconds (a single-slot render, or an extracted slot/cycle buffer for a
    live row). ``tones`` / ``base_freq_hz`` / ``dt_s`` are the row's KNOWN
    values -- truth for bench renders, REF's own decode for the live census.

    Method: build the reference analytic carrier ``z_ref(t) = exp(j*phase(t))``
    from the known tones with NO drift and NO fade -- the clean phase the
    channel is imposed on -- then correlate per symbol:

        g[i] = 2 * mean( audio[window_i] * conj(z_ref[window_i]) )

    which recovers the channel's local complex gain at the carrier frequency.
    The real transmitted signal is ``Re{g(t) z(t)} = (g*z + conj(g)*conj(z))/2``;
    mixing against ``conj(z_ref)`` and averaging over one symbol leaves the
    ``g`` term near-DC within the window and pushes the conjugate term to
    ~2x the carrier frequency (hundreds to thousands of Hz at FT8 audio
    frequencies), which averages to ~0 over a 0.16 s window. The factor of 2
    undoes the 1/2 in that identity.
    """
    if len(tones) != NUM_SYMBOLS:
        raise ValueError(f"expected {NUM_SYMBOLS} tones, got {len(tones)}")

    fs = sample_rate_hz
    phase_ref = instantaneous_phase(list(tones), base_freq_hz, fs)
    z_ref = np.exp(1j * phase_ref)
    n_tx = len(z_ref)

    start = int(round(dt_s * fs))
    seg = np.asarray(audio, dtype=np.float64)[start:start + n_tx]
    if len(seg) < n_tx:
        raise ValueError(
            f"audio too short for extraction: need {n_tx} samples from offset "
            f"{start}, got {len(seg)}"
        )

    mixed = seg * np.conj(z_ref)
    sps = int(round(SYMBOL_PERIOD_S * fs))
    g = np.empty(NUM_SYMBOLS, dtype=complex)
    for i in range(NUM_SYMBOLS):
        s, e = i * sps, i * sps + sps
        g[i] = 2.0 * np.mean(mixed[s:e])
    return g


def rho1(g: np.ndarray) -> float:
    """Magnitude of the normalised lag-1 autocorrelation of ``g`` (fading statistic).

    ``rho1 = |sum_i g[i] * conj(g[i-1])| / sum_i |g[i]|^2`` -- the denominator
    uses the full sequence's power (not a separate variance term), the
    standard normalised-autocovariance convention for a sequence whose mean
    is not separately removed (a fading channel gain has no meaningful "DC
    level" to subtract; removing one would bias rho1 low for slow fades on
    a short 79-sample window).
    """
    if len(g) < 2:
        raise ValueError("need at least 2 samples for a lag-1 statistic")
    num = np.sum(g[1:] * np.conj(g[:-1]))
    den = np.sum(np.abs(g) ** 2)
    if den <= 0.0:
        raise ValueError("zero-power channel-gain sequence")
    return float(np.abs(num) / den)


def drift_hz(g: np.ndarray, sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ) -> float:
    """Total drift Delta-f (Hz) across the transmission, the bench's own DRIFT unit.

    NOT a linear fit of arg(g) itself -- a centred linear frequency ramp of
    total ``D`` Hz produces a QUADRATIC phase trajectory (phase is frequency's
    integral), and fitting a straight line to a quadratic over a symmetric
    window recovers the WRONG answer: the ramp's quadratic term's own
    best-fit-line slope exactly cancels the ramp's already-linear term
    (verified empirically before shipping this version -- a naive phase-slope
    fit read ~0 Hz at every injected dose, including 16 Hz).

    Correct method: recover per-step INSTANTANEOUS frequency first (the thing
    that is actually linear in time by construction), via adjacent-symbol
    phase differences ``angle(g[i+1] * conj(g[i])) / (2*pi*SYMBOL_PERIOD_S)``,
    then fit a weighted line (weights = step magnitude) to those frequency
    samples against time and read the total excursion as ``slope *
    transmission_s`` -- matching ``modulator.modulate``'s convention
    (instantaneous frequency deviation linear in t, centred, total excursion
    = ``drift_hz``).

    KNOWN LIMITATION, analytic, not a bug (E4-STAGE2 Sec.1.2's Nyquist argument
    applies here too): ``g`` is sampled once per symbol, 6.25 Hz, Nyquist
    3.125 Hz. A true centred linear ramp of total ``D`` Hz sweeps instantaneous
    offset +/-D/2; once ``D/2`` exceeds ~3.125 Hz (``D`` gtr approx 6.25 Hz) the
    per-step phase difference can exceed +/-pi and alias. See the calibration
    report's own drift-ladder addendum for where this actually bites.

    🔴 SUPERSEDED for anything gating on drift (2026-09-16, amendment B1, spec
    Sec.8): this function reads back ~3.3 Hz for a true 8 Hz dose and ~2.9 Hz
    for a true 16 Hz dose -- aliased LOW, the unsafe direction for Sec.3.2's
    E4/E5, which gate on exactly that threshold. Kept only as the historical
    record of the defect ROW 0a(v) was written to catch; use
    :func:`split_window_drift_hz` for any new measurement.
    """
    n = len(g)
    if n < 3:
        raise ValueError("need at least 3 samples for a drift estimate")
    step = g[1:] * np.conj(g[:-1])                       # n-1 adjacent-symbol products
    freq_est_hz = np.angle(step) / (2.0 * np.pi * SYMBOL_PERIOD_S)
    w = np.abs(step)
    if np.sum(w) <= 0.0:
        raise ValueError("zero-power channel-gain sequence")
    t_mid = (np.arange(n - 1) + 1) * SYMBOL_PERIOD_S      # symbol-boundary times
    A = np.vstack([t_mid, np.ones_like(t_mid)]).T
    ATA = A.T @ (w[:, None] * A)
    ATb = A.T @ (w * freq_est_hz)
    slope, _intercept = np.linalg.solve(ATA, ATb)
    transmission_s = n * SYMBOL_PERIOD_S
    return float(slope * transmission_s)


# ── Replacement drift estimator (amendment B1, Stage-2 spec Sec.8.4) ─────────
#
# Split-window frequency difference. No phase unwrapping anywhere -- there is
# therefore no Nyquist ceiling to fold across. The ambiguity limit becomes the
# search range (chosen below, +/-25 Hz), and a row that pins at the edge is
# flagged out-of-range rather than silently folded -- the change of failure
# mode (loud vs silent) is the point of the redesign, more than the range.

NUM_SYMBOLS_SW = NUM_SYMBOLS  # local alias, for readability below
WINDOW_A = (0, 26)     # symbols 1-26 (1-indexed) -- Sec.8.4 step 1
WINDOW_B = (53, 79)    # symbols 54-79 (1-indexed)
_CENTROID_A = (WINDOW_A[0] + WINDOW_A[1] - 1) / 2.0   # 12.5
_CENTROID_B = (WINDOW_B[0] + WINDOW_B[1] - 1) / 2.0   # 65.5
CENTROID_GAP_SYMBOLS = _CENTROID_B - _CENTROID_A       # 53.0
DRIFT_SCALE = NUM_SYMBOLS_SW / CENTROID_GAP_SYMBOLS    # 79/53 = 1.4906 (Sec.8.4 step 3)

SEARCH_RANGE_HZ = 25.0
_COARSE_STEP_HZ = 0.5
_FINE_HALF_WINDOW_HZ = 0.5
_FINE_STEP_HZ = 0.05           # Sec.8.4 step 2: "final step <= 0.05 Hz"
EDGE_FLAG_MARGIN_HZ = 0.5       # Sec.8.4 step 4: "within 0.5 Hz of a search edge"


def _window_freq_offset(
    mixed: np.ndarray,
    t: np.ndarray,
) -> float:
    """argmax_f |sum mixed * exp(-j*2*pi*f*t)| over a coarse-then-fine grid.

    ``mixed`` is already ``seg * conj(z_ref)`` for the base (delta_f=0)
    reference, restricted to one sub-window's samples -- so this is a search
    over the RESIDUAL offset only, not the whole carrier. Looped rather than
    an outer-product matrix (samples-per-window x grid-size would be tens of
    millions of complex entries per call): each grid point is one vectorised
    dot product, cheap, and this keeps memory flat.
    """
    def score(freqs: np.ndarray) -> np.ndarray:
        return np.array([
            abs(np.sum(mixed * np.exp(-1j * 2.0 * np.pi * f * t))) for f in freqs
        ])

    coarse = np.arange(-SEARCH_RANGE_HZ, SEARCH_RANGE_HZ + 1e-9, _COARSE_STEP_HZ)
    c_best = float(coarse[np.argmax(score(coarse))])

    lo = max(-SEARCH_RANGE_HZ, c_best - _FINE_HALF_WINDOW_HZ)
    hi = min(SEARCH_RANGE_HZ, c_best + _FINE_HALF_WINDOW_HZ)
    fine = np.arange(lo, hi + 1e-9, _FINE_STEP_HZ)
    return float(fine[np.argmax(score(fine))])


def split_window_drift_hz(
    audio: np.ndarray,
    tones: "list[int]",
    base_freq_hz: float,
    dt_s: float = 0.0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> "tuple[float, bool]":
    """Total drift Delta-f (Hz) via the split-window method (B1, Sec.8.4).

    Returns ``(delta_f_hz, out_of_range)``. ``out_of_range`` is True iff
    either sub-window's fitted offset lands within :data:`EDGE_FLAG_MARGIN_HZ`
    of the +/-:data:`SEARCH_RANGE_HZ` search edge -- per Sec.8.4 step 4, such a
    row must be counted separately, never silently included in a median.

    Method: for each of sub-window A (symbols 1-26) and B (symbols 54-79),
    find the frequency offset (relative to ``base_freq_hz``) that maximises
    coherent correlation against that window's own KNOWN tones, restricted to
    that window's own samples. The two windows' centroids are
    :data:`CENTROID_GAP_SYMBOLS` (53) of 79 symbols apart, so
    ``delta_f_total = (f_B - f_A) * NUM_SYMBOLS / CENTROID_GAP_SYMBOLS``.
    """
    if len(tones) != NUM_SYMBOLS:
        raise ValueError(f"expected {NUM_SYMBOLS} tones, got {len(tones)}")

    fs = sample_rate_hz
    phase_ref = instantaneous_phase(list(tones), base_freq_hz, fs)
    z_ref = np.exp(1j * phase_ref)
    n_tx = len(z_ref)

    start = int(round(dt_s * fs))
    seg = np.asarray(audio, dtype=np.float64)[start:start + n_tx]
    if len(seg) < n_tx:
        raise ValueError(
            f"audio too short for extraction: need {n_tx} samples from offset "
            f"{start}, got {len(seg)}"
        )
    mixed_full = seg * np.conj(z_ref)
    sps = int(round(SYMBOL_PERIOD_S * fs))

    def window_estimate(win: "tuple[int, int]") -> "tuple[float, bool]":
        s, e = win[0] * sps, win[1] * sps
        t_w = np.arange(s, e, dtype=np.float64) / fs
        f_hat = _window_freq_offset(mixed_full[s:e], t_w)
        oor = abs(f_hat) >= (SEARCH_RANGE_HZ - EDGE_FLAG_MARGIN_HZ)
        return f_hat, oor

    f_a, oor_a = window_estimate(WINDOW_A)
    f_b, oor_b = window_estimate(WINDOW_B)
    delta_f_total = (f_b - f_a) * DRIFT_SCALE
    return delta_f_total, (oor_a or oor_b)
