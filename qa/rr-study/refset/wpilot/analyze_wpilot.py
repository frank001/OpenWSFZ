"""REFERENCE-SET W pilot analysis (QA). Protocol: PROTOCOL.md (frozen before the first decode). Aggregates only.

    python -s -E analyze_wpilot.py            # uses every block with all five W cells finished
"""
import json
import os
import random
import sys

SCRATCH = r"D:\Projects\claude\_qa-scratch\wpilot"
WS = [0, 4, 8, 16, 40]
TOL = 0.01                      # 1 percentage point (Architect's rule, 2c item 3)
BOOT, SEED = 10000, 1
LIVE_START_AGE_SENS_H = 6.0     # sensitivity subset: first scored cycle >= 6 h after the live run began

blocks = json.load(open(os.path.join(SCRATCH, "..", "refset-inventory", "wpilot_blocks.json")))["blocks"]


def load(bi, w):
    p = os.path.join(SCRATCH, "cells", f"cell_b{bi:02d}_w{w:02d}.json")
    return json.load(open(p)) if os.path.exists(p) else None


complete = [bi for bi in range(len(blocks)) if all(load(bi, w) for w in WS)]
cells = {bi: {w: load(bi, w) for w in WS} for bi in complete}


def ratio(num, den):
    return num / den if den else float("nan")


METRICS = {
    "A_all": lambda c: (c["ReproAll"], c["LiveRows"]),
    "A_nonhashed": lambda c: (c["ReproNonHashed"], c["LiveNonHashed"]),
    "A_hashed_exact": lambda c: (c["ReproHashedExact"], c["LiveHashed"]),
    "A_hashed_key": lambda c: (c["ReproHashedKey"], c["LiveHashed"]),
    "extra_all": lambda c: (c["ExtraAll"], c["LiveRows"]),
    "extra_nonhashed": lambda c: (c["ExtraNonHashed"], c["LiveRows"]),
    "extra_hashed": lambda c: (c["ExtraHashedKey"], c["LiveRows"]),
}


def pooled(bis, w, m):
    num = den = 0
    for bi in bis:
        n, d = METRICS[m](cells[bi][w]["counts"])
        num += n
        den += d
    return ratio(num, den)


def boot(bis, f):
    """Percentile 95 % interval of f(resampled block list); fixed seed."""
    rng = random.Random(SEED)
    vals = []
    for _ in range(BOOT):
        s = [rng.choice(bis) for _ in bis]
        v = f(s)
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]) if vals else (float("nan"), float("nan"))


def analyse(bis, label):
    out = {"label": label, "blocks": len(bis), "per_W": {}, "diff_vs_W40": {}}
    for w in WS:
        out["per_W"][str(w)] = {m: round(pooled(bis, w, m), 5) for m in METRICS}
        out["per_W"][str(w)]["live_hashed_rows"] = sum(cells[b][w]["counts"]["LiveHashed"] for b in bis)
        out["per_W"][str(w)]["live_rows"] = sum(cells[b][w]["counts"]["LiveRows"] for b in bis)
    for w in WS:
        if w == 40:
            continue
        d = {}
        for m in ("A_hashed_exact", "A_nonhashed", "A_all", "A_hashed_key"):
            point = pooled(bis, w, m) - pooled(bis, 40, m)
            lo, hi = boot(bis, lambda s, m=m, w=w: pooled(s, w, m) - pooled(s, 40, m))
            d[m] = {"diff": round(point, 5), "ci95": [round(lo, 5), round(hi, 5)]}
        out["diff_vs_W40"][str(w)] = d
    # the rule, as code
    passing = [w for w in WS if abs(pooled(bis, w, "A_hashed_exact") - pooled(bis, 40, "A_hashed_exact")) <= TOL]
    out["rule_W_star"] = min(passing) if passing else 40
    out["rule_none_within_1pp"] = not passing or passing == []
    out["W_within_1pp_of_W40"] = passing
    out["flag_nonhashed_depends_on_W"] = any(
        abs(pooled(bis, w, "A_nonhashed") - pooled(bis, 40, "A_nonhashed")) > TOL for w in WS)
    ws = out["rule_W_star"]
    if ws != 40:
        ci = out["diff_vs_W40"][str(ws)]["A_hashed_exact"]["ci95"]
        out["resolution_at_1pp"] = "resolved" if (ci[0] >= -TOL and ci[1] <= TOL) else "NOT resolved at 1 pp (CI reaches beyond +-1 pp)"
    else:
        out["resolution_at_1pp"] = "n/a (W*=40)"
    return out


def main():
    if not complete:
        print("no block has all five W cells yet")
        return 1
    ab = sum(cells[b][w]["residual_pass"]["abandoned"] for b in complete for w in WS)
    co = sum(cells[b][w]["residual_pass"]["contained"] for b in complete for w in WS)
    live_consistent = all(len({cells[b][w]["counts"]["LiveRows"] for w in WS}) == 1 for b in complete)
    res = {
        "protocol": "qa/rr-study/refset/wpilot/PROTOCOL.md",
        "blocks_complete": len(complete), "blocks_total": len(blocks),
        "P-V1_same_live_reference_in_all_W": live_consistent,
        "P-V2_abandoned_cells": [f"b{b:02d}_w{w:02d}" for b in complete for w in WS if cells[b][w]["residual_pass"]["abandoned"] > 0],
        "abandoned_total": ab, "contained_exceptions_total": co,
        "elapsed_s_per_cell_mean": round(sum(cells[b][w]["elapsed_s"] for b in complete for w in WS) / (len(complete) * len(WS)), 1),
    }
    res["primary"] = analyse(complete, "all complete blocks")
    sens = [b for b in complete if float(blocks[b]["age_h"]) >= LIVE_START_AGE_SENS_H]
    if len(sens) >= 3:
        res["sensitivity_age_ge_6h"] = analyse(sens, f"blocks with first scored cycle >= {LIVE_START_AGE_SENS_H} h after the live start")
    clean = [b for b in complete if all(cells[b][w]["residual_pass"]["abandoned"] == 0 for w in WS)]
    if len(clean) != len(complete) and len(clean) >= 3:
        res["sensitivity_no_abandonment"] = analyse(clean, "blocks with no abandonment in any cell")
    # RS-V2 reading (not gating)
    p40 = res["primary"]["per_W"]["40"]
    res["RS-V2_reading_at_W40_nonhashed"] = {"reproduced": p40["A_nonhashed"], "extra_nonhashed_of_live_rows": p40["extra_nonhashed"],
                                              "bar": "reproduced >= 0.99 and extra <= 0.01 (2f item 4)"}
    json.dump(res, open(os.path.join(SCRATCH, "wpilot_result.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
