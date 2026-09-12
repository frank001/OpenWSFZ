#!/usr/bin/env python3
"""LIVE-GAP-NOW paired frequency-clustered bootstrap (spec 3.1).

Extends p23_common.cluster_bootstrap's own method (HK-018: same resampling
scheme, same seed discipline) to keep PER-DRAW arrays for each named metric,
so a paired Delta (NOW's R minus L08's R, same resampled cluster set per draw)
can be computed directly -- "do not difference two independent CIs" (spec).
"""
from __future__ import annotations

import numpy as np

N_BOOT = 2000
SEED = 20260912


def paired_cluster_bootstrap(ref_freq: dict, member_sets: dict, n_draws=N_BOOT, seed=SEED):
    """ref_freq: {key -> freq_hz} for every REF key.
    member_sets: {name -> set(keys)} -- each metric's own "hit" set (e.g. a
    leg's exact_matched | gained, from matcher.recovery()'s own 'hit_set').

    Resamples distinct frequencies ONCE per draw (paired across all named
    metrics) and recomputes each metric's R (%) on that same cluster set.
    Returns {"per_draw": {name: np.ndarray[n_draws]}, "n_distinct_freq": int}.
    """
    byf = {}
    for k, f in ref_freq.items():
        byf.setdefault(f, []).append(k)
    freqs = list(byf)
    rng = np.random.default_rng(seed)
    per_draw = {name: np.empty(n_draws) for name in member_sets}
    for d in range(n_draws):
        pick = rng.choice(len(freqs), size=len(freqs), replace=True)
        keys = []
        for i in pick:
            keys.extend(byf[freqs[i]])
        denom = len(keys)
        for name, s in member_sets.items():
            if denom == 0:
                per_draw[name][d] = float("nan")
            else:
                per_draw[name][d] = 100.0 * sum(1 for k in keys if k in s) / denom
    return {"per_draw": per_draw, "n_distinct_freq": len(freqs), "n_draws": n_draws, "seed": seed}


def delta_summary(per_draw: dict, name_a: str, name_b: str) -> dict:
    """Delta = per_draw[name_a] - per_draw[name_b], PAIRED per draw (same
    resampled cluster set). Returns mean, se, ci95 of the per-draw Delta."""
    a = per_draw[name_a]
    b = per_draw[name_b]
    delta = a - b
    return {
        "mean": float(np.nanmean(delta)),
        "se": float(np.nanstd(delta, ddof=1)),
        "ci95": [float(np.nanpercentile(delta, 2.5)), float(np.nanpercentile(delta, 97.5))],
        "n_draws": len(delta),
    }
