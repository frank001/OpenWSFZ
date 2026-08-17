#!/usr/bin/env python3
"""N4 -- statistics: the central-lobe half-width H_n and its cluster-bootstrap CI.

Spec: qa/rr-study/2026-08-17-1553-architect-to-qa-n3-ruling-and-n4-lobe-width-spec.md
Sec.4's primary statistic: "H_n, the central-lobe half-width. Let M_n(df) be the median
hard-decision BER over rows at common offset df for order n. Let df* = argmin. Walking
outward from df* in each direction, let xL and xR be the first crossings of B50=11.3%
(linear interpolation between adjacent grid points). W_n^lobe = xR - xL, H_n = W_n^lobe/2."

This deliberately replaces N3's W_n (a GLOBAL total-below-threshold measure) -- the
Architect's own N3 ruling (Sec.0/1.1) traced why a global measure was the wrong
statistic for a row that guarded EDGE FLATNESS: flatness is neither necessary nor
sufficient for exhaustion of the below-B50 set, and the two properties can point in
opposite directions. H_n is scoped to the CONTIGUOUS lobe containing the minimum, which
is exactly the region ROW 0e (aliasing) exists to check is the WHOLE below-B50 story.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "n3-frequency-requirement"))
from n1_stats import B50_THRESHOLD  # noqa: E402,F401
from n3_stats import argmin_curve, width_below_threshold  # noqa: E402,F401 -- reused unchanged;
                                                            # width_below_threshold is kept
                                                            # available for non-gating context
                                                            # only (spec Sec.1: NOT the
                                                            # requirement), never for H_n.

import numpy as _np  # noqa: E402

# Spec Sec.4.2: two-resolution grid, one instrument.
#   core:  -2.5 .. +2.5 Hz, step 0.125 Hz -> 41 points (resolves the crossing)
#   outer: +-(2.5 .. 10.0] Hz, step 0.5 Hz -> 30 points (tests exhaustion past the
#          6.25 Hz tone-spacing null and its 9.375 Hz worst-case midpoint)
_CORE = _np.arange(-2.5, 2.5 + 1e-9, 0.125)
_OUTER_POS = _np.arange(3.0, 10.0 + 1e-9, 0.5)
_OUTER_NEG = -_OUTER_POS[::-1]
_ALL = _np.concatenate([_OUTER_NEG, _CORE, _OUTER_POS])

DF_SWEEP_HZ = tuple(round(float(x), 3) for x in _ALL)
assert len(DF_SWEEP_HZ) == 71, len(DF_SWEEP_HZ)
assert DF_SWEEP_HZ[0] == -10.0 and DF_SWEEP_HZ[-1] == 10.0
assert DF_SWEEP_HZ == tuple(sorted(DF_SWEEP_HZ)), "grid must be strictly ascending"
assert 0.0 in DF_SWEEP_HZ, "grid must contain an exact df=0 point (ROW 0a reads it)"
assert len(set(DF_SWEEP_HZ)) == 71, "no duplicate grid points"

DF_CORE_STEP_HZ = 0.125   # sign unit test tolerance -- injected offsets live in the core

# ROW thresholds (spec Sec.5) -- derived, not chosen (spec Sec.5, final paragraph).
ROW_1_CI_LO_MIN_HZ = 1.5625    # lattice half-cell, K_FREQ_OSR=2, 3.125 Hz step
ROW_3_CI_HI_MAX_HZ = 0.5       # WSJT-X ALL.TXT integer-Hz reporting quantisation

SEED = 20260817  # this session's date (HK-017-style provenance), reused for both the
                  # Slice-B cluster draw (n4_population.py) and the bootstrap below.


def contiguous_lobe(ys: "list[float]", threshold: float) -> "tuple[int, int] | None":
    """Indices (lo, hi), inclusive, of the run of consecutive grid points with
    ys[i] < threshold that contains the (first) global minimum of ys. None if the
    global minimum itself is not below threshold (no lobe -- ROW 0c's job)."""
    imin = min(range(len(ys)), key=lambda i: ys[i])
    if not (ys[imin] < threshold):
        return None
    lo = imin
    while lo - 1 >= 0 and ys[lo - 1] < threshold:
        lo -= 1
    hi = imin
    while hi + 1 < len(ys) and ys[hi + 1] < threshold:
        hi += 1
    return lo, hi


def any_below_threshold_outside_lobe(ys: "list[float]", threshold: float) -> bool:
    """ROW 0e: is there a below-threshold grid point that is NOT part of the contiguous
    lobe containing the global minimum? (An aliased second below-B50 region.)"""
    lobe = contiguous_lobe(ys, threshold)
    if lobe is None:
        return False  # "no lobe at all" is ROW 0c's finding, not this one's
    lo, hi = lobe
    return any(y < threshold and not (lo <= i <= hi) for i, y in enumerate(ys))


def lobe_half_width(xs: "list[float]", ys: "list[float]", threshold: float) -> dict:
    """H_n per spec Sec.4: df_star (argmin, reporting only -- the centroid tie-break of
    n3_stats.argmin_curve), xL/xR (linear-interpolated crossings bracketing the
    CONTIGUOUS lobe containing the global minimum), lobe_width = xR-xL, half_width =
    lobe_width/2. If the grid touches threshold exactly at an edge sample (lo==0 or
    hi==len-1) the crossing is reported AT that edge (xL=xs[0] / xR=xs[-1]) -- ROW 0d is
    what flags this case as "not contained", not this function.

    Returns half_width=None (and xL/xR=None) if no lobe exists (global min >= threshold,
    i.e. contiguous_lobe returns None)."""
    assert len(xs) == len(ys) and len(xs) >= 2
    df_star = argmin_curve(xs, ys)
    lobe = contiguous_lobe(ys, threshold)
    if lobe is None:
        return {"df_star": df_star, "xL": None, "xR": None,
                "lobe_width": None, "half_width": None}
    lo, hi = lobe
    if lo == 0:
        xL = xs[0]
    else:
        x0, x1, y0, y1 = xs[lo - 1], xs[lo], ys[lo - 1], ys[lo]
        frac = (threshold - y0) / (y1 - y0)
        xL = x0 + frac * (x1 - x0)
    if hi == len(xs) - 1:
        xR = xs[-1]
    else:
        x0, x1, y0, y1 = xs[hi], xs[hi + 1], ys[hi], ys[hi + 1]
        frac = (threshold - y0) / (y1 - y0)
        xR = x0 + frac * (x1 - x0)
    lobe_width = xR - xL
    return {"df_star": df_star, "xL": xL, "xR": xR,
            "lobe_width": lobe_width, "half_width": lobe_width / 2.0}


def median_curve(rows: "list[dict]", variant: str, n_df: int) -> "list[float]":
    """Median BER per df across `rows`, each a dict with rows[i]['curves'][variant] a
    length-n_df list. Pure aggregation helper shared by the point estimate and every
    bootstrap resample -- never re-extracts, only re-medians (spec Sec.4.3.2)."""
    if not rows:
        return [float("nan")] * n_df
    return [float(_np.median([r["curves"][variant][j] for r in rows])) for j in range(n_df)]


def cluster_bootstrap_lobe(rows: "list[dict]", variant_names: "tuple[str, ...]",
                            xs: "list[float]", threshold: float,
                            n_draws: int = 2000, seed: int = SEED) -> dict:
    """Cluster bootstrap over distinct `ts`, resampling WHOLE clusters with replacement
    (HK-021(i)). Per draw, re-medians the ALREADY-EXTRACTED (rows x offsets) BER matrix
    for every variant using the SAME cluster pick (so cross-variant differences like
    D = H_1 - H_3^cum are computed on paired draws, not independent ones) and reads off
    each variant's lobe_half_width. Never re-extracts (spec Sec.4.3.2).

    Returns {variant: {point_estimate, mean, se, ci95, n_draws, n_no_lobe_draws}} plus
    a top-level {"n_rows", "n_clusters", "seed", "diff_H1_minus_H3cum": {...}} entry --
    the paired difference's own point estimate/CI/p, spec Sec.5.1's D statistic, 🛑
    NOTHING in Sec.5.1 gates (enforced by the caller, not this function)."""
    n_df = len(xs)
    by_ts: "dict[str, list[dict]]" = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r)
    ts_list = sorted(by_ts)  # sort before ANY seeded draw indexes into this list
    n_clusters = len(ts_list)
    n_rows = len(rows)

    point: "dict[str, dict]" = {}
    for v in variant_names:
        curve = median_curve(rows, v, n_df)
        point[v] = lobe_half_width(xs, curve, threshold)

    out: "dict[str, dict]" = {v: {"point_estimate": point[v]["half_width"],
                                   "point_detail": point[v]} for v in variant_names}
    diff_point = None
    if point["V1"]["half_width"] is not None and point["V3_cum"]["half_width"] is not None:
        diff_point = point["V1"]["half_width"] - point["V3_cum"]["half_width"]

    if n_clusters < 2 or not rows:
        for v in variant_names:
            out[v].update({"mean": float("nan"), "se": float("nan"),
                            "ci95": [float("nan"), float("nan")],
                            "n_draws": 0, "n_no_lobe_draws": 0})
        return {"variants": out, "n_rows": n_rows, "n_clusters": n_clusters, "seed": seed,
                "diff_H1_minus_H3cum": {"point_estimate": diff_point, "mean": float("nan"),
                                         "se": float("nan"), "ci95": [float("nan"), float("nan")],
                                         "p_two_sided": float("nan"), "n_draws": 0}}

    # Vectorised resampling: precompute (n_rows x n_df) matrices once per variant and
    # each cluster's row-index list, then per draw gather row indices with numpy fancy
    # indexing and call np.median(axis=0) ONCE per variant instead of rebuilding python
    # lists element-by-element (5 variants x 71 df x ~700 rows x 2000 draws of pure-
    # python indexing would otherwise be ~500M interpreter-level operations). Numerically
    # identical to the naive per-element re-median -- np.median over the same multiset of
    # values either way; only the construction path changed.
    row_index_by_ts: "dict[str, list[int]]" = {}
    for idx, r in enumerate(rows):
        row_index_by_ts.setdefault(r["ts"], []).append(idx)
    cluster_row_indices = [_np.array(row_index_by_ts[t], dtype=_np.int64) for t in ts_list]
    matrices = {v: _np.array([r["curves"][v] for r in rows], dtype=_np.float64)
                for v in variant_names}  # each (n_rows, n_df)

    rng = _np.random.default_rng(seed)
    draws: "dict[str, list[float]]" = {v: [] for v in variant_names}
    diff_draws: "list[float]" = []
    no_lobe: "dict[str, int]" = {v: 0 for v in variant_names}
    for _ in range(n_draws):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        row_idx = _np.concatenate([cluster_row_indices[i] for i in pick])
        hw: "dict[str, float | None]" = {}
        for v in variant_names:
            curve = list(_np.median(matrices[v][row_idx], axis=0))
            res = lobe_half_width(xs, curve, threshold)
            hw[v] = res["half_width"]
            if hw[v] is None:
                no_lobe[v] += 1
            else:
                draws[v].append(hw[v])
        if hw.get("V1") is not None and hw.get("V3_cum") is not None:
            diff_draws.append(hw["V1"] - hw["V3_cum"])

    for v in variant_names:
        arr = _np.array(draws[v])
        if len(arr) == 0:
            out[v].update({"mean": float("nan"), "se": float("nan"),
                            "ci95": [float("nan"), float("nan")],
                            "n_draws": 0, "n_no_lobe_draws": no_lobe[v]})
        else:
            out[v].update({
                "mean": float(arr.mean()),
                "se": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
                "ci95": [float(_np.percentile(arr, 2.5)), float(_np.percentile(arr, 97.5))],
                "n_draws": len(arr), "n_no_lobe_draws": no_lobe[v],
            })

    darr = _np.array(diff_draws)
    if len(darr) == 0:
        diff = {"point_estimate": diff_point, "mean": float("nan"), "se": float("nan"),
                "ci95": [float("nan"), float("nan")], "p_two_sided": float("nan"), "n_draws": 0}
    else:
        p_le0 = float(_np.mean(darr <= 0.0))
        p_ge0 = float(_np.mean(darr >= 0.0))
        diff = {
            "point_estimate": diff_point,
            "mean": float(darr.mean()),
            "se": float(darr.std(ddof=1)) if len(darr) > 1 else float("nan"),
            "ci95": [float(_np.percentile(darr, 2.5)), float(_np.percentile(darr, 97.5))],
            "p_two_sided": float(min(1.0, 2.0 * min(p_le0, p_ge0))),
            "n_draws": len(darr),
        }

    return {"variants": out, "n_rows": n_rows, "n_clusters": n_clusters, "seed": seed,
            "diff_H1_minus_H3cum": diff}
