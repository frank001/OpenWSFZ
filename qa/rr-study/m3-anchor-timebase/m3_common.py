#!/usr/bin/env python3
"""M3 -- shared infrastructure: the time-only anchor sweep grid, real-population
sampling helpers. Reuses M1's corpus/DLL pins and WAV/ALL.TXT loaders unchanged
(single source of truth for the pin and the basis discipline), and reuses M2's
positive-control MANIFEST verbatim (not rebuilt -- spec S7.2: "the existing 400-row
control, unchanged").

Spec: qa/rr-study/2026-08-15-1545-architect-to-qa-m2-row0c-ruling-and-m3-anchor-timebase-spec.md
S7.2: no src/ change, pure harness work, same shape as M2 -- HK-011 not engaged.

Frequency anchor is FIXED at df=0 throughout M3 (spec S7.2: "the frequency question
is confounded until the time origin is right, and fixing it keeps the run cheap").
Only the time anchor is swept.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RR_STUDY = os.path.dirname(_HERE)
_M1_DIR = os.path.join(_RR_STUDY, "m1-sync-vs-extraction")
_M2_DIR = os.path.join(_RR_STUDY, "m2-anchor-sweep")
_R1_DIR = os.path.join(_RR_STUDY, "r1-sync-refiner")
for _p in (_M1_DIR, _M2_DIR, _R1_DIR, _RR_STUDY):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Re-exported unchanged from M1 -- same corpus, same window, same DLL pin, same
# basis discipline (spec S7.2: "same corpus ... same basis ... same DLL SHA256 pin").
from m1_common import (  # noqa: E402,F401
    REPO_ROOT, CORPUS_DIR, OWSFZ_ALL_TXT, WSJTX_ALL_TXT, OWSFZ_WAV_DIR,
    WINDOW, DLL_PATH, DLL_SHA256, SHIM_VERSION, BUFFER_SAMPLES, SAMPLE_RATE_HZ,
    BAND_LO_HZ, BAND_HI_HZ, has_unresolved_hash, load_all_txt, assert_field_mapping,
    read_wav_12k_15s, owsfz_wav_path, write_json,
)

RESULTS_DIR = os.path.join(_HERE, "results")

# Positive control is REUSED VERBATIM from M2 -- spec S7.2. Not rebuilt, not
# reseeded. Its self-consistency limitation (S5.2 of the ruling: it validates
# plumbing only, never the anchor convention) is restated in the M3 report, not
# re-derived here.
M2_CONTROL_MANIFEST_PATH = os.path.join(_M2_DIR, "results", "m2_control_manifest.json")

# M3's own seed -- distinct from M1's 20260815 and M2's 20260816.
M3_SEED = 20260817

# -- Spec S7.2: the time-only anchor sweep grid --------------------------------
# "dt_offset in {-1.20, -1.15, ..., +1.20} in 0.05 s steps = 49 points. Step is
# below the refiner's own +-60ms coarse aperture so the sweep cannot step over the
# peak. Frequency anchor fixed at df=0."
DT_STEP_S = 0.05
DT_EDGE_S = 1.20
_N_STEPS = round(2 * DT_EDGE_S / DT_STEP_S)
TIME_ANCHOR_OFFSETS_S = tuple(
    round(-DT_EDGE_S + i * DT_STEP_S, 10) for i in range(_N_STEPS + 1)
)
assert len(TIME_ANCHOR_OFFSETS_S) == 49, len(TIME_ANCHOR_OFFSETS_S)
assert TIME_ANCHOR_OFFSETS_S[0] == -1.20 and TIME_ANCHOR_OFFSETS_S[-1] == 1.20, TIME_ANCHOR_OFFSETS_S
assert any(abs(v) < 1e-9 for v in TIME_ANCHOR_OFFSETS_S), "0.0 must be on the grid"

# Sweep visitation order, ascending |dt_offset| -- nearest to the un-swept anchor
# first. This is ONLY used to decide which member of a genuine score-plateau is
# "nearest to zero displacement"; it is not the tie-break itself. See
# m3_run_harness.sweep_one_row's docstring and section 5.1 of the M3 spec: M2's
# sweep resolved ties by fixed ascending-df visitation order, which silently
# favoured the more-negative offset on every mirror-image tie (confirmed the
# source of NULL's mean df_anchor=-0.588Hz finding in M2). M3 does not repeat
# that construction: ties are detected explicitly by comparing scores across ALL
# 49 recorded calls, and a genuine mirror-image tie (dt=-k vs dt=+k, both at the
# row's maximum score, symmetric about zero) is recorded as TIED and excluded
# from every signed statistic, never silently resolved toward either sign.
SWEEP_ORDER = tuple(sorted(TIME_ANCHOR_OFFSETS_S, key=abs))
N_SWEEP_CALLS = len(SWEEP_ORDER)

EDGE_TIME_S = DT_EDGE_S

# -- Spec S6/M1 strata, reused verbatim ------------------------------------------
STRATA = [(-24, -21), (-21, -18), (-18, -15), (-15, -12), (-12, -9), (-9, -6), (-6, float("inf"))]

# -- Spec S7.2: real-population subsample size (100 HIT + 100 NULL per stratum) --
N_PER_ARM_PER_STRATUM = 100

# -- Internal aperture rail, for the S7.4 (recorded, non-gating) frequency
# residual readout -- matches M2's report convention (+-2.5 Hz internal aperture).
FREQ_RAIL_HZ = 2.5


def stratum_of(snr_db: float) -> int:
    for i, (lo, hi) in enumerate(STRATA):
        if lo <= snr_db < hi:
            return i
    raise AssertionError("snr_db %r outside all strata" % snr_db)


def stratum_label(i: int) -> str:
    lo, hi = STRATA[i]
    return "[%g,%s)" % (lo, "inf" if hi == float("inf") else "%g" % hi)


def is_edge_winner_time(dt_win) -> bool:
    """ROW 0c: winner sits at the sweep's own outer time edge. dt_win may be None
    (a tied/excluded row) -- a tied row is, by definition, not a resolved edge
    winner, so it does not count toward the edge fraction either way."""
    if dt_win is None:
        return False
    return abs(dt_win) >= EDGE_TIME_S - 1e-9
