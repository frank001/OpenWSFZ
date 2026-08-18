#!/usr/bin/env python3
"""N5 -- statistics: f_cross (reused VERBATIM from n1_stats, spec Sec.6.1 A1.2), the new
f_break, and the paired cluster bootstrap that reports f_cross/f_break/f_net together
without ever pooling f_cross and f_break into one number.

Spec: qa/rr-study/2026-08-17-1648-architect-to-qa-n4-ruling-and-n5-spec.md Sec.6, as
AMENDED by Sec.6.1 (Amendment 1 wins wherever the two disagree).

Amendment A1.2's denominators (verbatim, stated because they are not automatic):
  f_cross's denominator = rows with BER_V0 > B50  ("only those CAN cross down")
  f_break's denominator = rows with BER_V0 <= B50 ("only those CAN break")
  f_net = f_cross - f_break, but EXPRESSED AS A FRACTION OF THE WHOLE MEASURED
          POPULATION for both terms (n_cross/N_total - n_break/N_total) -- the two
          per-subset fractions above are NOT directly subtractable (different
          denominators), so f_net re-bases both counts onto the same total before
          netting. f_cross/f_break themselves keep their own natural denominators
          when reported standalone.

HK-021(l): both statistics stay SIGNED. f_break is not "the harmful direction of
f_cross" collapsed into one instrument -- it is its own named quantity with its own CI,
reported and bootstrapped separately, per A1.2's "NEVER pooled" instruction. The paired
bootstrap below resamples clusters ONCE per draw and recomputes all three quantities
from that SAME draw (A1.2: "same draws"), which is what makes f_net meaningful as a
per-draw net rather than a difference of two independently-resampled CIs.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "n1-ber-at-refined-position"))
import numpy as np

from n1_stats import B50_THRESHOLD, SEED, d_ber_row, f_cross_row  # noqa: E402,F401


def f_break_row(ber_v0: float, ber_v3: float) -> bool:
    """True iff this row BREAKS: BER_V0 <= B50 (already correctable at V0) and BER_V3 >
    B50 (V3 pushes it above the bar). The reverse direction of f_cross_row.

    Not a theoretical concern for this treatment: N2 measured V3 making matched-hit-
    control BER monotonically WORSE than V0 with coherent order (2.87% -> 8.05%).
    A treatment already shown to degrade good rows can push correctable rows above B50
    while gross f_cross looks fine -- Amendment A1.2 exists because of this."""
    return ber_v0 <= B50_THRESHOLD and ber_v3 > B50_THRESHOLD


def _compute_point(rows: list[dict]) -> dict:
    """rows: each {"ts", "ber_v0", "crosses" (bool), "breaks" (bool)}.
    Returns f_cross/f_break (own-denominator fractions, NaN if that denominator is
    empty), f_net (whole-population-denominator net), and every count."""
    n_total = len(rows)
    crossable = [r for r in rows if r["ber_v0"] > B50_THRESHOLD]
    breakable = [r for r in rows if r["ber_v0"] <= B50_THRESHOLD]
    n_cross = sum(1 for r in crossable if r["crosses"])
    n_break = sum(1 for r in breakable if r["breaks"])
    f_cross = (n_cross / len(crossable)) if crossable else float("nan")
    f_break = (n_break / len(breakable)) if breakable else float("nan")
    f_net = ((n_cross / n_total) - (n_break / n_total)) if n_total else float("nan")
    return {
        "f_cross": f_cross, "f_break": f_break, "f_net": f_net,
        "n_cross": n_cross, "n_crossable": len(crossable),
        "n_break": n_break, "n_breakable": len(breakable),
        "n_total": n_total,
    }


def cluster_bootstrap_f_cross_break_net(rows: list[dict], n_draws: int = 2000,
                                         seed: int = SEED) -> dict:
    """Cluster bootstrap over `ts` (HK-021(i)), one resample per draw, f_cross/f_break/
    f_net all recomputed from that SAME resampled row set (A1.2's "same draws").

    Point estimates are computed on the FULL, unresampled row set (never on a draw).
    A draw contributing no observations to a given denominator (e.g. zero crossable
    rows in that resample) is excluded from THAT statistic's own draw distribution only
    -- f_net's per-draw n_total is never zero while any rows exist, so its draw count
    tracks n_draws exactly; f_cross/f_break's draw counts are reported separately and
    may be lower.

    Returns {point: {...all counts + point fractions...}, f_cross: {ci95, se, n_draws},
    f_break: {...}, f_net: {...}, n_clusters, seed}."""
    by_ts: dict[str, list[dict]] = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r)
    ts_list = sorted(by_ts)  # sort before any seeded draw indexes into this list
    n_clusters = len(ts_list)

    point = _compute_point(rows)
    point["n_clusters_crossable"] = len({r["ts"] for r in rows if r["ber_v0"] > B50_THRESHOLD})
    point["n_clusters_breakable"] = len({r["ts"] for r in rows if r["ber_v0"] <= B50_THRESHOLD})

    nan_summary = {"ci95": [float("nan"), float("nan")], "se": float("nan"), "n_draws": 0}
    if n_clusters < 2 or not rows:
        return {"point": point, "f_cross": nan_summary, "f_break": nan_summary,
                "f_net": nan_summary, "n_clusters": n_clusters, "seed": seed}

    rng = np.random.default_rng(seed)
    draws_cross: list[float] = []
    draws_break: list[float] = []
    draws_net: list[float] = []
    for _ in range(n_draws):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        sub_rows: list[dict] = []
        for i in pick:
            sub_rows.extend(by_ts[ts_list[i]])
        d = _compute_point(sub_rows)
        if not np.isnan(d["f_cross"]):
            draws_cross.append(d["f_cross"])
        if not np.isnan(d["f_break"]):
            draws_break.append(d["f_break"])
        if not np.isnan(d["f_net"]):
            draws_net.append(d["f_net"])

    def _summarise(draws: list[float]) -> dict:
        if not draws:
            return dict(nan_summary)
        arr = np.array(draws)
        return {"ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
                "se": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
                "n_draws": len(arr)}

    return {
        "point": point,
        "f_cross": _summarise(draws_cross),
        "f_break": _summarise(draws_break),
        "f_net": _summarise(draws_net),
        "n_clusters": n_clusters,
        "seed": seed,
    }
