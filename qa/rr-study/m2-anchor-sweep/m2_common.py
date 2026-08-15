#!/usr/bin/env python3
"""M2 -- shared infrastructure: anchor-sweep grid, real-population sampling helpers,
positive-control synthesis. Reuses M1's corpus/DLL pins and WAV/ALL.TXT loaders
unchanged (single source of truth for the pin and the basis discipline) rather than
re-declaring them.

Spec: qa/rr-study/2026-08-15-1301-architect-to-qa-m1-ruling-and-m2-anchor-sweep-spec.md
S4.0/S4.1: no src/ change, pure harness work driving the same diagnostic
ft8_refine_candidate export as M1/R1b, over a widened ANCHOR sweep (the anchor we
hand the refiner, not the refiner's own internal aperture).
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RR_STUDY = os.path.dirname(_HERE)
_M1_DIR = os.path.join(_RR_STUDY, "m1-sync-vs-extraction")
_R1_DIR = os.path.join(_RR_STUDY, "r1-sync-refiner")
for _p in (_M1_DIR, _R1_DIR, _RR_STUDY):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Re-exported unchanged from M1 -- same corpus, same window, same DLL pin, same
# basis discipline (spec S4.1: "same corpus ... same basis ... same DLL SHA256 pin").
from m1_common import (  # noqa: E402,F401
    REPO_ROOT, CORPUS_DIR, OWSFZ_ALL_TXT, WSJTX_ALL_TXT, OWSFZ_WAV_DIR,
    WINDOW, DLL_PATH, DLL_SHA256, SHIM_VERSION, BUFFER_SAMPLES, SAMPLE_RATE_HZ,
    BAND_LO_HZ, BAND_HI_HZ, has_unresolved_hash, load_all_txt, assert_field_mapping,
    read_wav_12k_15s, owsfz_wav_path, write_json,
)

RESULTS_DIR = os.path.join(_HERE, "results")

# M2's own seed -- distinct from M1's 20260815 (M1's manifest was drawn with that
# stream already; reusing it here would correlate the two draws for no reason).
M2_SEED = 20260816

# ── Spec S4.1: the anchor sweep grid ────────────────────────────────────────────
# "Sweeping the anchor we hand it is equivalent to widening the aperture."
FREQ_ANCHOR_OFFSETS_HZ = tuple(range(-10, 11))          # 21 values, 1 Hz steps
TIME_ANCHOR_OFFSETS_S = (-0.05, 0.0, 0.05)               # 3 values
N_SWEEP_CALLS = len(FREQ_ANCHOR_OFFSETS_HZ) * len(TIME_ANCHOR_OFFSETS_S)  # 63
assert N_SWEEP_CALLS == 63, N_SWEEP_CALLS

EDGE_FREQ_HZ = max(abs(v) for v in FREQ_ANCHOR_OFFSETS_HZ)   # 10
EDGE_TIME_S = max(abs(v) for v in TIME_ANCHOR_OFFSETS_S)      # 0.05

# Sweep order, ascending distance from (0, 0) -- i.e. the original anchor is tried
# first, then progressively wider offsets. This matters because the refiner's score
# genuinely PLATEAUS (float-identical) across a band of nearby anchors once their
# internal aperture reaches the same true peak (confirmed empirically during M2
# smoke-testing on the positive control: (790, 0.3) and (788, 0.25) against the same
# PCM returned bit-identical score=522849.25 with different delta_freq_hz/coarse_dt_samp,
# because both anchors' apertures reach the same absolute peak). A winner-selection
# loop that keeps the FIRST strictly-greatest score under nested (df, dt) iteration
# order would silently favour whichever offset is iterated first on a tie -- for a
# plain `range(-10, 11)` loop that is df=-10, a directional artefact with no physical
# meaning. Iterating nearest-to-zero-first makes ties resolve toward the anchor
# closest to zero offset, which is the physically meaningful tie-break (least
# hypothesised displacement from the reported/lattice position) and removes the
# artefact from ROW 0c (edge-winner fraction) and ROW 0d (NULL mean df_anchor).
def _sweep_distance(df: int, dt: float) -> float:
    return (df / EDGE_FREQ_HZ) ** 2 + (dt / EDGE_TIME_S) ** 2


SWEEP_GRID_ORDERED = tuple(sorted(
    ((df, dt) for df in FREQ_ANCHOR_OFFSETS_HZ for dt in TIME_ANCHOR_OFFSETS_S),
    key=lambda pair: _sweep_distance(*pair),
))
assert len(SWEEP_GRID_ORDERED) == N_SWEEP_CALLS
assert SWEEP_GRID_ORDERED[0] == (0, 0.0), SWEEP_GRID_ORDERED[0]

# ── Spec S6 strata, reused verbatim from M1 (same WSJT-X-SNR stratification) ────
STRATA = [(-24, -21), (-21, -18), (-18, -15), (-15, -12), (-12, -9), (-9, -6), (-6, float("inf"))]

# ── Spec 4.1: real-population subsample sizes ────────────────────────────────────
N_PER_ARM_PER_STRATUM = 300

# ── Spec 4.1: positive control ───────────────────────────────────────────────────
N_CONTROL = 400
CONTROL_SNR_DB_LEVELS = (-18.0, -12.0, -6.0, 0.0)   # 4 levels x 100 rows = 400
N_CONTROL_PER_LEVEL = N_CONTROL // len(CONTROL_SNR_DB_LEVELS)
assert N_CONTROL_PER_LEVEL * len(CONTROL_SNR_DB_LEVELS) == N_CONTROL

# Near-anchor jitter grid.
#
# QA CORRECTION (post-first-run, same day): the first M2 run used
# r1-sync-refiner/population.py's full validated grid here (offsets up to +-1.5 Hz /
# +-39 ms). That is the RIGHT grid for validating the refiner's OWN internal aperture
# in isolation (what R0/R1/R1b did), but it is the WRONG grid for THIS control, whose
# ROW 0a gate reads raw |coarse_dt_samp| (spec 4.2) -- a quantity defined relative to
# the SWEEP ANCHOR, not relative to the truth. Diagnostic run showed the 63-point
# sweep's own winner sits at (df=0, dt=0) in 399/400 control rows regardless of
# injected offset (the refiner's internal aperture reaches the peak from the base
# anchor every time, so the external sweep never needs to move) -- so coarse_dt_samp
# on that grid was reporting the INJECTED OFFSET itself (median ~20 ms / 4 samples
# across the 9-value time grid), not a harness or refiner defect. The subset with
# time_offset_s==0 (anchor already exactly correct) showed median |coarse_dt_samp| =
# 1 sample -- the harness and refiner both work; the control's own grid was simply
# not "near the anchor" the way ROW 0a's bar assumes. Corrected to small jitter well
# inside the bar even allowing for R0/R1/R1b's own ~1.1 ms/0.5 Hz measured residual.
CONTROL_FREQ_OFFSETS_HZ = (0.0, 0.3, -0.3, 0.6, -0.6)
CONTROL_TIME_OFFSETS_S = (0.0, 0.005, -0.005, 0.01, -0.01)

CONTROL_BASE_FREQ_BAND_HZ = (300.0, 2700.0)   # mirrors population.py's NOISE_FREQ_BAND_HZ
CONTROL_BASE_EXCLUSION_HZ = 50.0              # keep the injected slot clear of real signals
CONTROL_BASE_MAX_ATTEMPTS = 2000
CONTROL_BASE_DT_S = 0.3                        # fixed lattice DT (population.py's T_LATTICE_S)

REFERENCE_BANDWIDTH_HZ = 2500.0  # WSJT-X SNR reference bandwidth (matches synth/constants.py)

# Distinct-message grid locators (NFR-021 -- fictional Q1AW callsign, distinct msg
# per buffer), independent 4-char space, no collision risk with any other arm's
# trial-index-based scheme since this module owns indices 0..399 only.
_GRID_LETTERS = "ABCDEFGHIJKLMNOPQR"


def control_message_for_index(index: int) -> str:
    index = index % 32_400
    a = _GRID_LETTERS[(index // (18 * 100)) % 18]
    b = _GRID_LETTERS[(index // 100) % 18]
    dd = index % 100
    return f"CQ Q1AW {a}{b}{dd:02d}"


def stratum_of(snr_db: float) -> int:
    for i, (lo, hi) in enumerate(STRATA):
        if lo <= snr_db < hi:
            return i
    raise AssertionError("snr_db %r outside all strata" % snr_db)


def stratum_label(i: int) -> str:
    lo, hi = STRATA[i]
    return "[%g,%s)" % (lo, "inf" if hi == float("inf") else "%g" % hi)


def is_edge_winner(df_anchor: float, dt_anchor: float) -> bool:
    """ROW 0c: winner sits at the sweep's own outer edge."""
    return abs(df_anchor) >= EDGE_FREQ_HZ - 1e-9 or abs(dt_anchor) >= EDGE_TIME_S - 1e-9
