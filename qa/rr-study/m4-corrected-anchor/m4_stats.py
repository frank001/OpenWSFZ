#!/usr/bin/env python3
"""M4 -- statistics helpers: rho_conc (lifted from m1_evaluate.pooled_contrast,
metric swapped per spec S5.3 -- imported unchanged, not rewritten) and a
cluster-robust OLS slope for ROW 0d's condition (2).
"""
from __future__ import annotations

import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
_M1_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "m1-sync-vs-extraction")
if _M1_DIR not in sys.path:
    sys.path.insert(0, _M1_DIR)

# Lifted unchanged, per spec S5.3: "m1_evaluate.pooled_contrast, metric swapped --
# lift it, do not rewrite it". rank_biserial's own convention (Wendt 1972):
# rho_rb(a, b) = +1 iff every element of a strictly exceeds every element of b.
from m1_evaluate import pooled_contrast, rank_biserial  # noqa: E402,F401


def to_conc_rows(rows, metric_key="coarse_dt_samp"):
    """Maps refiner-call rows (each carrying 'snr_db', 'cycle_id', metric_key) to
    the {'snr_db','cycle_id','score'} shape pooled_contrast expects, with
    score = -|metric|.

    This is the entire sign convention for rho_conc: pooled_contrast(A, B) calls
    rank_biserial(scores_A, scores_B), which is +1 iff every A-score exceeds every
    B-score. With score = -|coarse_dt_samp|, "A-score exceeds B-score" means
    "A's |coarse_dt_samp| is SMALLER than B's" -- i.e. A is more concentrated.
    So rho_conc(HIT, NULL) == +1 iff every HIT row is strictly more concentrated
    (smaller |coarse_dt_samp|) than every NULL row -- exactly spec S5.3's
    mandatory unit-test assertion, with no sign flip anywhere in this function.
    """
    return [{"snr_db": r["snr_db"], "cycle_id": r["cycle_id"], "score": -abs(r[metric_key])}
            for r in rows]


def rho_conc(rows_a, rows_b, label: str, metric_key="coarse_dt_samp") -> dict:
    """rows_a, rows_b: lists of raw M4 result rows (HIT, NULL, or MISS). Returns
    the pooled_contrast dict (per_stratum, pooled_rho_rb, pooled_se, ci_lo, ci_hi)
    with pooled_rho_rb being rho_conc under the sign convention above."""
    return pooled_contrast(to_conc_rows(rows_a, metric_key), to_conc_rows(rows_b, metric_key), label)


def ols_cluster_robust(x, y, cluster_ids):
    """Simple OLS y = a + b*x with a cluster-robust (CR1, Stata-style small-sample
    corrected) sandwich SE on b, clustered over cluster_ids (HK-021(i): rows in
    one cycle share noise/propagation, so per-row SEs understate uncertainty).

    Returns dict(slope, intercept, se_slope, t_stat, p_value, n, n_clusters).
    NaN se/p if fewer than 2 distinct clusters (degenerate -- cannot estimate a
    cluster SE) or fewer than 3 observations.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = len(x)
    if n < 3:
        return {"slope": float("nan"), "intercept": float("nan"), "se_slope": float("nan"),
                "t_stat": float("nan"), "p_value": float("nan"), "n": n, "n_clusters": 0}

    X = np.column_stack([np.ones(n), x])
    XtX = X.T @ X
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ (X.T @ y)
    intercept, slope = float(beta[0]), float(beta[1])
    resid = y - X @ beta

    clusters = {}
    for i, c in enumerate(cluster_ids):
        clusters.setdefault(c, []).append(i)
    n_clusters = len(clusters)

    if n_clusters < 2:
        return {"slope": slope, "intercept": intercept, "se_slope": float("nan"),
                "t_stat": float("nan"), "p_value": float("nan"), "n": n, "n_clusters": n_clusters}

    K = X.shape[1]
    meat = np.zeros((K, K))
    for idx in clusters.values():
        Xg = X[idx]
        ug = resid[idx]
        score_g = Xg.T @ ug
        meat += np.outer(score_g, score_g)

    correction = (n_clusters / (n_clusters - 1)) * ((n - 1) / max(n - K, 1))
    V = correction * (XtX_inv @ meat @ XtX_inv)
    se_slope = float(np.sqrt(V[1, 1])) if V[1, 1] > 0 else float("nan")

    if se_slope > 0 and not np.isnan(se_slope):
        t_stat = slope / se_slope
        df = n_clusters - 1
        p_value = float(2.0 * stats.t.sf(abs(t_stat), df))
    else:
        t_stat = float("nan")
        p_value = float("nan")

    return {"slope": slope, "intercept": intercept, "se_slope": se_slope,
            "t_stat": float(t_stat), "p_value": p_value, "n": n, "n_clusters": n_clusters}
