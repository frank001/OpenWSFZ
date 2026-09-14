#!/usr/bin/env python3
"""PASSBAND-140 paired bootstrap, two cluster schemes (spec 3.1).

N_BOOT = 2000, seed 20260914 (spec's own pin, not LIVE-GAP-NOW's 20260912).
Both legs recomputed on the SAME draw (paired), Delta taken per draw, never
the difference of two independently-computed CIs.

Generalises live-gap-now's paired_cluster_bootstrap (spec 0.5: reused, not
rebuilt) to take an explicit key->cluster mapping, so the same routine
serves both required schemes:
  - frequency clusters: cluster = REF row's freq_hz (as LIVE-GAP-NOW)
  - cycle clusters: cluster = REF row's ts (revision 6's own unit,
    HK-021(i): decodes in one cycle share one noise realisation and one
    candidate ordering)

CI_lo = min(lo_freq, lo_cyc), CI_hi = max(hi_freq, hi_cyc) -- the WIDER
interval governs (spec 3.1). SE is reported for both schemes.
"""
from __future__ import annotations

import numpy as np

N_BOOT = 2000
SEED = 20260914


def paired_cluster_bootstrap(ref_to_cluster: dict, member_sets: dict,
                              n_draws=N_BOOT, seed=SEED):
    """ref_to_cluster: {key -> cluster_id} for every REF key (key is (ts,msg)).
    member_sets: {name -> set(keys)} -- each metric's own hit set
    (matcher.recovery()'s 'hit_set': exact_matched | gained).

    Resamples distinct cluster_ids ONCE per draw (paired across all named
    metrics) and recomputes each metric's R (%) on that same cluster set.
    Returns {"per_draw": {name: ndarray[n_draws]}, "n_distinct_clusters": int}.
    """
    by_cluster = {}
    for k, c in ref_to_cluster.items():
        by_cluster.setdefault(c, []).append(k)
    clusters = list(by_cluster)
    rng = np.random.default_rng(seed)
    per_draw = {name: np.empty(n_draws) for name in member_sets}
    for d in range(n_draws):
        pick = rng.choice(len(clusters), size=len(clusters), replace=True)
        keys = []
        for i in pick:
            keys.extend(by_cluster[clusters[i]])
        denom = len(keys)
        for name, s in member_sets.items():
            if denom == 0:
                per_draw[name][d] = float("nan")
            else:
                per_draw[name][d] = 100.0 * sum(1 for k in keys if k in s) / denom
    return {"per_draw": per_draw, "n_distinct_clusters": len(clusters),
            "n_draws": n_draws, "seed": seed}


def delta_summary(per_draw: dict, name_a: str, name_b: str) -> dict:
    """Delta = per_draw[name_a] - per_draw[name_b], PAIRED per draw."""
    a, b = per_draw[name_a], per_draw[name_b]
    delta = a - b
    return {
        "mean": float(np.nanmean(delta)),
        "se": float(np.nanstd(delta, ddof=1)),
        "ci95": [float(np.nanpercentile(delta, 2.5)), float(np.nanpercentile(delta, 97.5))],
        "n_draws": len(delta),
    }


def wider_ci(ci_freq: list, ci_cyc: list) -> list:
    """CI_lo = min(lo_freq, lo_cyc), CI_hi = max(hi_freq, hi_cyc) (spec 3.1)."""
    return [min(ci_freq[0], ci_cyc[0]), max(ci_freq[1], ci_cyc[1])]
