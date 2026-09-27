#!/usr/bin/env python3
"""GAP-LOCATE Amendment 2: paired bootstrap for Delta = P_own - P_ref.

Spec sec.2: "95% bootstrap CI, resampling by distinct REF frequency, N=2000, seed=20260921
(as spec sec.2)." Same frequency-clustered-resample pattern as p23_common.cluster_bootstrap
(HK-021(i)), extended to compute Delta directly per draw (not just each metric's own
marginal CI) so the two metrics' correlation within a draw is preserved -- p23_common's own
"PAIRED across metrics" design intent, made explicit for a difference statistic.
"""
from __future__ import annotations

import numpy as np


def paired_delta_ci(ref_freq: dict, found_ref: set, found_own: set, n_draws: int = 2000,
                     seed: int = 20260921) -> dict:
    """ref_freq: {key -> REF freq_hz} for every key in the population.
    found_ref / found_own: sets of keys found under each convention.
    Returns {P_ref, P_own, delta_mean, delta_se, delta_ci95, n_draws, n_distinct_freq}."""
    byf = {}
    for k, f in ref_freq.items():
        byf.setdefault(f, []).append(k)
    freqs = list(byf)
    rng = np.random.default_rng(seed)
    deltas = []
    p_refs = []
    p_owns = []
    for _ in range(n_draws):
        pick = rng.choice(len(freqs), size=len(freqs), replace=True)
        keys = []
        for i in pick:
            keys.extend(byf[freqs[i]])
        denom = len(keys)
        if denom == 0:
            continue
        p_ref = sum(1 for k in keys if k in found_ref) / denom
        p_own = sum(1 for k in keys if k in found_own) / denom
        p_refs.append(p_ref)
        p_owns.append(p_own)
        deltas.append(p_own - p_ref)
    d = np.array(deltas)
    n_all = len(ref_freq)
    return {
        "P_ref_point": sum(1 for k in ref_freq if k in found_ref) / n_all,
        "P_own_point": sum(1 for k in ref_freq if k in found_own) / n_all,
        "delta_mean": float(d.mean()),
        "delta_se": float(d.std(ddof=1)),
        "delta_ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
        "P_ref_ci95": [float(np.percentile(p_refs, 2.5)), float(np.percentile(p_refs, 97.5))],
        "P_own_ci95": [float(np.percentile(p_owns, 2.5)), float(np.percentile(p_owns, 97.5))],
        "n_draws": len(d), "n_distinct_freq": len(freqs), "seed": seed,
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    adj = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5)
    return ((centre - adj) / denom, (centre + adj) / denom)
