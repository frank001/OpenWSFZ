#!/usr/bin/env python3
"""N1 -- statistics helpers: the paired primary statistic (d_ber), the secondary
crossing fraction (f_cross), and a cluster bootstrap over `ts` for d_ber's CI/p.

Spec: qa/rr-study/2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-spec.md
Sec.4 ("Primary statistic d_ber ... paired median of BER_grid - BER_refined, positive
meaning refinement helps ... cluster bootstrap over ts -- HK-021(i)") and Sec.5's ROW
1/2/3 thresholds, which read this module's output directly.

Both statistics are SIGNED (HK-021 sibling (l), ruled off M4's third occurrence of the
same defect): d_ber keeps its sign (positive = refined is better), f_cross counts only
the ABOVE-bar -> BELOW-bar direction, never |crossing| in either direction pooled.
"""
from __future__ import annotations

import numpy as np

B50_THRESHOLD = 0.113  # W1 Sec.5/Sec.8 correction threshold, this branch's own
                        # reproduction landed at 11.65%, within the pre-registered 1pp
                        # tolerance (qa/rr-study/2026-08-16-1121-...). Retracted k_50 =
                        # 7.47% (C.5a) is a DIFFERENT quantity and must never be used here.

SEED = 20260816  # this session's date, HK-017-style provenance; fixed for reproducibility


def d_ber_row(ber_grid: float, ber_refined: float) -> float:
    """Positive = refinement helped (lower BER at the refined position)."""
    return ber_grid - ber_refined


def f_cross_row(ber_grid: float, ber_refined: float) -> bool:
    """True iff this row crosses from ABOVE the correction threshold (grid) to AT-OR-
    BELOW it (refined) -- the direction that converts to a recall gain. The reverse
    direction (refined pushes a correctable row above the bar) is not counted here: it
    is a real and reportable outcome but a DIFFERENT quantity from f_cross, and pooling
    both directions into one number would hide a harmful refiner behind a helpful one --
    exactly the kind of unsigned statistic HK-021(l) forbids."""
    return ber_grid > B50_THRESHOLD and ber_refined <= B50_THRESHOLD


def cluster_bootstrap_median_diff(rows: list[dict], n_draws: int = 2000, seed: int = SEED) -> dict:
    """Cluster bootstrap of the paired median d_ber, resampling distinct `ts` values
    (HK-021(i): rows sharing a cycle share propagation/noise, so per-row treatment as
    independent observations understates uncertainty).

    rows: each a dict with at least {"ts": str, "d_ber": float} (pp, i.e. 0-1 scale here;
    caller converts to percentage points for reporting).

    Returns {point_estimate (median over ALL rows, not resampled), mean, se, ci95:
    [lo, hi], p_two_sided, n_draws, n_rows, n_clusters}.

    p_two_sided: percentile-bootstrap two-sided p-value against the null d_ber == 0,
    p = 2 * min(P(draw <= 0), P(draw >= 0)), clipped to 1.0. This is the same convention
    used for a percentile-bootstrap sign test elsewhere in this thread's statistics
    (M4's cluster-robust slope reports an analogous two-sided p from its own sampling
    distribution) -- here the sampling distribution is the bootstrap itself, not a
    t-distribution, because the statistic (a median) has no closed-form SE.
    """
    by_ts: dict[str, list[float]] = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r["d_ber"])
    ts_list = sorted(by_ts)  # HK-021(i) sibling of the hash-randomisation bug: sort before
                             # any seeded draw indexes into this list (BOARD.md standing note)
    n_clusters = len(ts_list)

    point_estimate = float(np.median([r["d_ber"] for r in rows])) if rows else float("nan")

    if n_clusters < 2 or not rows:
        return {"point_estimate": point_estimate, "mean": float("nan"), "se": float("nan"),
                "ci95": [float("nan"), float("nan")], "p_two_sided": float("nan"),
                "n_draws": 0, "n_rows": len(rows), "n_clusters": n_clusters, "seed": seed}

    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_draws):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        vals: list[float] = []
        for i in pick:
            vals.extend(by_ts[ts_list[i]])
        if vals:
            draws.append(float(np.median(vals)))
    arr = np.array(draws)

    p_le0 = float(np.mean(arr <= 0.0))
    p_ge0 = float(np.mean(arr >= 0.0))
    p_two_sided = float(min(1.0, 2.0 * min(p_le0, p_ge0)))

    return {
        "point_estimate": point_estimate,
        "mean": float(arr.mean()),
        "se": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
        "ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
        "p_two_sided": p_two_sided,
        "n_draws": len(arr),
        "n_rows": len(rows),
        "n_clusters": n_clusters,
        "seed": seed,
    }
