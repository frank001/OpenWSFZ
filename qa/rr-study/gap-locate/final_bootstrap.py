#!/usr/bin/env python3
"""GAP-LOCATE spec sec.2 CIs: s, R_F, R_norm.

"CIs: 95% bootstrap, resampling by distinct REF frequency (as H10), N=2000, seed=20260921.
For R_norm, resample M and K jointly." Same frequency-clustered-resample pattern as
p23_common.cluster_bootstrap / bootstrap_delta.py (HK-021(i)).
"""
from __future__ import annotations

import numpy as np

SEED = 20260921
N_DRAWS = 2000


def _resample_rate(keys: list, freq_of: dict, member_set: set, rng) -> float:
    byf = {}
    for k in keys:
        byf.setdefault(freq_of[k], []).append(k)
    freqs = list(byf)
    pick = rng.choice(len(freqs), size=len(freqs), replace=True)
    picked_keys = []
    for i in pick:
        picked_keys.extend(byf[freqs[i]])
    denom = len(picked_keys)
    if denom == 0:
        return float("nan")
    return sum(1 for k in picked_keys if k in member_set) / denom


def rate_ci(keys: list, freq_of: dict, member_set: set, n_draws=N_DRAWS, seed=SEED) -> dict:
    rng = np.random.default_rng(seed)
    vals = [_resample_rate(keys, freq_of, member_set, rng) for _ in range(n_draws)]
    v = np.array(vals)
    point = sum(1 for k in keys if k in member_set) / len(keys)
    return {"point": point, "mean": float(v.mean()), "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
            "n_draws": n_draws, "n_distinct_freq": len(set(freq_of[k] for k in keys))}


def r_norm_ci(m_keys: list, m_freq_of: dict, m_found: set,
              k_keys: list, k_freq_of: dict, k_found: set,
              n_draws=N_DRAWS, seed=SEED) -> dict:
    rng = np.random.default_rng(seed)
    ratios = []
    r_fs = []
    p_ctrls = []
    for _ in range(n_draws):
        rf = _resample_rate(m_keys, m_freq_of, m_found, rng)
        pc = _resample_rate(k_keys, k_freq_of, k_found, rng)
        r_fs.append(rf)
        p_ctrls.append(pc)
        ratios.append(rf / pc if pc else float("nan"))
    r = np.array(ratios)
    r = r[~np.isnan(r)]
    r_f_point = sum(1 for k in m_keys if k in m_found) / len(m_keys)
    p_ctrl_point = sum(1 for k in k_keys if k in k_found) / len(k_keys)
    return {
        "R_F_point": r_f_point, "P_ctrl_point": p_ctrl_point,
        "R_norm_point": r_f_point / p_ctrl_point,
        "R_norm_mean": float(r.mean()), "R_norm_ci95": [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))],
        "n_draws": len(r), "seed": seed,
    }
