"""G2A-REMEASURE-A Part A (PRIMARY, GATED) -- H = rate_unresolved(L1) -
rate_unresolved(L2), paired cycle-clustered bootstrap. Spec Sec.4.
"""
from __future__ import annotations

import random
from collections import defaultdict


def _by_cycle_hash(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["ts"]].append(r["has_hash"])
    return d


def _rate(by_cycle, cycles):
    num = 0
    den = 0
    for ts in cycles:
        hs = by_cycle.get(ts)
        if not hs:
            continue
        num += sum(hs)
        den += len(hs)
    return (num / den) if den else 0.0, num, den


def run_part_a(l1_rows, l2_rows, log, n_boot=2000, seed=20260825001) -> dict:
    l1_by_cycle = _by_cycle_hash(l1_rows)
    l2_by_cycle = _by_cycle_hash(l2_rows)
    cycles = sorted(set(l1_by_cycle) | set(l2_by_cycle))  # sort at construction

    rate_l1, num_l1, den_l1 = _rate(l1_by_cycle, cycles)
    rate_l2, num_l2, den_l2 = _rate(l2_by_cycle, cycles)
    h_point = rate_l1 - rate_l2

    log("Part A: rate_unresolved(L1) = %d/%d = %.4f%%" % (num_l1, den_l1, rate_l1 * 100))
    log("Part A: rate_unresolved(L2) = %d/%d = %.4f%%" % (num_l2, den_l2, rate_l2 * 100))
    log("Part A: H (point) = %.4f%%" % (h_point * 100))

    n = len(cycles)
    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        idxs = [rng.randrange(n) for _ in range(n)]
        sample = [cycles[i] for i in idxs]
        r1, _, _ = _rate(l1_by_cycle, sample)
        r2, _, _ = _rate(l2_by_cycle, sample)
        boots.append(r1 - r2)
    boots.sort()
    lo = boots[int(0.025 * n_boot)]
    hi = boots[int(0.975 * n_boot) - 1]

    log("Part A: H 95%% CI (cycle-clustered bootstrap, n_boot=%d, n_cycles=%d) = [%.4f%%, %.4f%%]"
        % (n_boot, n, lo * 100, hi * 100))

    bar = 0.02
    if lo > bar:
        row = "A1"
        reading = ("The fix works and the programme's evidence base is stale. Every D-001 "
                   "figure captured pre-merge understates our text quality, and the headline "
                   "gap must be restated on a post-fix basis before any further DSP arm is "
                   "funded.")
    elif hi < 0:
        row = "A3"
        reading = ("REGRESSION -- the fix made text rendering worse. Escalate immediately; "
                   "do not proceed to Part B.")
    else:
        row = "A2"
        reading = ("The fix did not materially change text rendering on this corpus. Bucket "
                   "B1 is then not primarily a sizing problem, and the T3 callsign-character "
                   "population inherits the question.")
    log("Part A: ROW %s -- %s" % (row, reading))

    return {
        "rate_l1": rate_l1, "rate_l2": rate_l2, "n_l1": den_l1, "n_l2": den_l2,
        "h_point": h_point, "h_ci": [lo, hi], "bar": bar, "n_boot": n_boot, "seed": seed,
        "row": row, "reading": reading,
    }
