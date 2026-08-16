#!/usr/bin/env python3
"""M4 -- shared infrastructure: fixed corrected-anchor, one call per row, no sweep.

Reuses M1's corpus/DLL pins and WAV/ALL.TXT loaders unchanged (single source of
truth for the pin and the basis discipline). Reuses M1's own manifest (the ENTIRE
51,186-row population, no subsampling) and M2's positive-control manifest verbatim
(not rebuilt, not reseeded) -- spec S5.1/S5.2.

Spec: qa/rr-study/2026-08-15-1658-architect-to-qa-m4-corrected-anchor-spec.md

No src/ change, no capture run, no Developer session, no ABI bump (spec S10) --
pure harness work driving the same already-pinned diagnostic ft8_refine_candidate
export as M1/M2/M3/R1b.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RR_STUDY = os.path.dirname(_HERE)
_M1_DIR = os.path.join(_RR_STUDY, "m1-sync-vs-extraction")
_M2_DIR = os.path.join(_RR_STUDY, "m2-anchor-sweep")
_M3_DIR = os.path.join(_RR_STUDY, "m3-anchor-timebase")
_R1_DIR = os.path.join(_RR_STUDY, "r1-sync-refiner")
for _p in (_M1_DIR, _M2_DIR, _M3_DIR, _R1_DIR, _RR_STUDY):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Re-exported unchanged from M1 -- same corpus, same window, same DLL pin, same
# basis discipline (assert the SHA256, never infer it from a label -- spec S5).
from m1_common import (  # noqa: E402,F401
    REPO_ROOT, CORPUS_DIR, OWSFZ_ALL_TXT, WSJTX_ALL_TXT, OWSFZ_WAV_DIR,
    WINDOW, DLL_PATH, DLL_SHA256, SHIM_VERSION, BUFFER_SAMPLES, SAMPLE_RATE_HZ,
    BAND_LO_HZ, BAND_HI_HZ, has_unresolved_hash, load_all_txt, assert_field_mapping,
    read_wav_12k_15s, owsfz_wav_path, write_json,
)

RESULTS_DIR = os.path.join(_HERE, "results")

M1_MANIFEST_PATH = os.path.join(_M1_DIR, "results", "m1_manifest.json")
M2_CONTROL_MANIFEST_PATH = os.path.join(_M2_DIR, "results", "m2_control_manifest.json")
M3_RESULTS_PATH = os.path.join(_M3_DIR, "results", "m3_results.json")

# -- Spec S1/S5.2: THE CORRECTION -- WSJT-X DT + 0.45s, buffer-relative. M3's
# MEASURED value (the direct correlator measurement), NOT the Architect's missed
# +0.60...+0.70s prediction. Applied to real (HIT/MISS/NULL) rows only.
ANCHOR_CORRECTION_S = 0.45

# -- Spec S6: strata, reused verbatim from M1/M2/M3 (same WSJT-X-SNR stratification)
STRATA = [(-24, -21), (-21, -18), (-18, -15), (-15, -12), (-12, -9), (-9, -6), (-6, float("inf"))]
STRATUM_MIN_N = 200          # spec S5.1/S6 ROW 0b
N_STRATA_OK_MIN = 4          # spec S6 ROW 0b

# -- Spec S2: the refiner's own instrument geometry (native/ft8_lib_vendor/refine/
# sync_refiner.c), read from source, not inferred --
COARSE_RAIL_SAMP = 12         # REFINE_COARSE_TIME_HALF_SAMPLES @ 200 Hz -> d in [-12,+12]
COARSE_STEP_S = 0.005         # 5 ms/sample @ 200 Hz
COARSE_UNIFORM_MEDIAN = 6.0   # 25-point uniform-argmax median |d| (spec S2 table)
COARSE_UNIFORM_MEAN = 6.24
COARSE_UNIFORM_RAIL_FRAC = 2.0 / 25.0   # 8.0%

FINE_RAIL_SAMP = 20            # REFINE_FINE_TIME_HALF_MS @ 2000 Hz -> f in [-20,+20]
FINE_UNIFORM_MEDIAN = 10.0     # 41-point uniform-argmax median |f| (spec S2 table)

# -- Spec S6 ROW 0c: coarse-stage internal-aperture rail bar --
ROW0C_RAIL_FRAC_MAX = 0.25

# -- Spec S6 ROW 0d: bars derived from aperture geometry alone (2 steps = 10 ms,
# 1/6 of the coarse half-aperture), NOT calibrated against any observed value --
ROW0D_NULL_MEDIAN_ABS_MAX_STEPS = 2
ROW0D_SLOPE_ABS_MAX_STEPS_PER_S = 2.0
ROW0D_SLOPE_P_MAX = 0.01

# -- Spec S6 ROW 1/2 --
ROW1_RHO_MIN = 0.30
ROW1_CI_LO_MIN = 0.10
ROW2_RHO_ABS_MAX = 0.10
ROW2_CI_HI_MAX = 0.30

N_BOOTSTRAP = 500
BOOTSTRAP_SEED = 20260817   # M4's own seed for the cluster bootstrap RNG stream


def stratum_of(snr_db: float) -> int:
    for i, (lo, hi) in enumerate(STRATA):
        if lo <= snr_db < hi:
            return i
    raise AssertionError("snr_db %r outside all strata" % snr_db)


def stratum_label(i: int) -> str:
    lo, hi = STRATA[i]
    return "[%g,%s)" % (lo, "inf" if hi == float("inf") else "%g" % hi)


def is_coarse_railed(coarse_dt_samp) -> bool:
    """ROW 0c: the coarse stage's OWN internal-aperture rail, |coarse_dt_samp| == 12
    (not a sweep edge -- M4 has no sweep). Spec S6 ROW 0c."""
    return abs(coarse_dt_samp) >= COARSE_RAIL_SAMP
