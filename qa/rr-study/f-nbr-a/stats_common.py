"""Exact (Clopper-Pearson) two-sided binomial CI, alpha=0.05 by default.
Same construction as harness/analyse.py's _cp_upper_95 (one-sided) -- extended
to two-sided here since Gate A/rows C1-C3 need both bounds (HK-021(o))."""
from __future__ import annotations

from scipy.stats import beta as _beta_dist


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo = 0.0 if k == 0 else float(_beta_dist.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta_dist.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi
