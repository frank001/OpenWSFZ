#!/usr/bin/env python3
"""ARCHITECT DIAGNOSTIC (not a gate, not a QA arm, no pre-registration).

Re-analysis of Stage 1RE's OWN delivered per-row dump
(`results/stage1re_rows.json`, 15,389 rows) plus N5's own per-row dump
(`../n5-outcome-conversion/results/n5_results.json`, 405 rows). Reads files
only -- no decoder call, no WAV, no native binary, nothing re-measured.

It answers two questions the 1613Z QA report escalated to the Architect:

  (A) N5 RECONCILIATION. Is N5's `0/403` in contradiction with Stage 1RE's
      `f_cross = 2.47%`? Apply Stage 1RE's OWN BER_V0-stratum-specific
      crossing rates to N5's OWN BER_V0 distribution and read off the
      expected crossing count `lambda`. (HK-021(j): an absence claim needs
      lambda >= 5.)

  (B) NULL CALIBRATION of `f_net`. `f_net` counts flux across a FIXED
      threshold B50 in a population whose density is grossly asymmetric
      about that threshold (14,934 crossable vs 455 breakable). Any
      perturbation of BER -- informative or not -- therefore produces a
      POSITIVE net down-flux by construction. The placebo keeps each row's
      OWN |BER_V3 - BER_V0| magnitude and randomises only the SIGN, i.e.
      "same size of change, no information about direction", and asks what
      `f_net` reads under it.

  Both placebo variants are APPROXIMATIONS: they perturb BER directly, not
  the LLR vector, so they are a DIAGNOSTIC that motivates a pre-registered
  arm -- they are NOT a measurement and they do NOT re-rule ROW 1.
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
S1RE = os.path.join(HERE, "results", "stage1re_rows.json")
N5 = os.path.join(HERE, "..", "n5-outcome-conversion", "results", "n5_results.json")

B50 = 0.113          # n5_stats.B50_THRESHOLD, unchanged
EDGES = [0.113, 0.13, 0.15, 0.18, 0.22, 0.28, 0.35, 0.45, 1.01]
N_DRAWS = 500
SEED = 11


def stratum(ber: float) -> "int | None":
    for i in range(len(EDGES) - 1):
        if EDGES[i] <= ber < EDGES[i + 1]:
            return i
    return None


def placebo(rows, seed: int, n_draws: int = N_DRAWS):
    """Own-magnitude sign-flip placebo. Returns (mean_cross, mean_break, sorted f_net list)."""
    rng = random.Random(seed)
    n_crossable = sum(1 for r in rows if r["ber_v0"] > B50)
    out, cc, bb = [], [], []
    for _ in range(n_draws):
        nc = nb = 0
        for r in rows:
            m = abs(r["ber_v3"] - r["ber_v0"])
            v3 = r["ber_v0"] + (m if rng.random() < 0.5 else -m)
            if r["ber_v0"] > B50 and v3 <= B50:
                nc += 1
            elif r["ber_v0"] <= B50 and v3 > B50:
                nb += 1
        cc.append(nc)
        bb.append(nb)
        out.append((nc - nb) / n_crossable)
    out.sort()
    return sum(cc) / n_draws, sum(bb) / n_draws, out


def main() -> int:
    rows = json.load(open(S1RE))
    n5 = json.load(open(N5))["rows"]

    n_cross = sum(1 for r in rows if r["crosses"])
    n_break = sum(1 for r in rows if r["breaks"])
    n_crossable = sum(1 for r in rows if r["ber_v0"] > B50)
    f_net = (n_cross - n_break) / n_crossable
    print("Stage 1RE as delivered: n_cross=%d n_break=%d n_crossable=%d f_net=%+.4f%%"
          % (n_cross, n_break, n_crossable, 100 * f_net))

    # -- (A) N5 reconciliation -------------------------------------------------
    tot = [0] * (len(EDGES) - 1)
    cr = [0] * (len(EDGES) - 1)
    for r in rows:
        i = stratum(r["ber_v0"])
        if i is None:
            continue
        tot[i] += 1
        cr[i] += 1 if r["crosses"] else 0
    rate = [cr[i] / tot[i] if tot[i] else 0.0 for i in range(len(tot))]

    print("\n(A) Stage 1RE crossing rate by BER_V0 stratum (crossable rows only):")
    for i in range(len(tot)):
        print("    [%.3f,%.3f): n=%5d  crossed=%3d  rate=%.4f%%"
              % (EDGES[i], EDGES[i + 1], tot[i], cr[i], 100 * rate[i]))

    lam = 0.0
    n5_crossable = 0
    hist = {}
    for r in n5:
        i = stratum(r["ber_v0"])
        if i is None:
            continue
        n5_crossable += 1
        lam += rate[i]
        hist[i] = hist.get(i, 0) + 1
    print("\n    N5 crossable n=%d, median BER_V0=%.4f" % (n5_crossable, st.median(r["ber_v0"] for r in n5)))
    print("    N5 stratum counts: %s"
          % {"[%.3f,%.3f)" % (EDGES[i], EDGES[i + 1]): hist[i] for i in sorted(hist)})
    print("    EXPECTED crossings in N5 under Stage 1RE's own rates: lambda=%.2f" % lam)
    print("    P(0 | Poisson lambda) = %.3f     N5 observed: %d"
          % (math.exp(-lam), sum(1 for r in n5 if r["crosses"])))
    print("    HK-021(j) bar for an absence claim is lambda >= 5 -> %s"
          % ("MET" if lam >= 5 else "NOT MET"))

    # -- (B) null calibration --------------------------------------------------
    mc, mb, dist = placebo(rows, SEED)
    print("\n(B) Own-magnitude sign-flip placebo, whole population, %d draws:" % N_DRAWS)
    print("    placebo n_cross mean %.1f (real %d) | n_break mean %.1f (real %d)"
          % (mc, n_cross, mb, n_break))
    print("    placebo f_net mean %+.4f%%  p2.5 %+.4f%%  p97.5 %+.4f%%"
          % (100 * sum(dist) / len(dist), 100 * dist[int(0.025 * len(dist))],
             100 * dist[int(0.975 * len(dist))]))
    print("    fraction of placebo draws >= the real f_net (%+.4f%%): %.3f"
          % (100 * f_net, sum(1 for x in dist if x >= f_net) / len(dist)))

    near = [r for r in rows if r["ber_v0"] <= 0.22]
    nc_r = sum(1 for r in near if r["crosses"])
    nb_r = sum(1 for r in near if r["breaks"])
    ncr_near = sum(1 for r in near if r["ber_v0"] > B50)
    mc2, mb2, dist2 = placebo(near, SEED + 1)
    print("\n    Restricted to the physically reachable band BER_V0 <= 0.22 "
          "(median |d_ber|=%.4f, so a 0.30 swing is not being assumed):" % st.median(
              abs(r["ber_v3"] - r["ber_v0"]) for r in near))
    print("    real:    n_cross=%d n_break=%d f_net=%+.4f%%" % (nc_r, nb_r, 100 * (nc_r - nb_r) / ncr_near))
    print("    placebo: n_cross mean %.1f n_break mean %.1f f_net mean %+.4f%% [%+.4f%%, %+.4f%%]"
          % (mc2, mb2, 100 * sum(dist2) / len(dist2),
             100 * dist2[int(0.025 * len(dist2))], 100 * dist2[int(0.975 * len(dist2))]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
