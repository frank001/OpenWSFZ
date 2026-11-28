#!/usr/bin/env python3
"""Held-out replay of the FG ON night: analysis (numbers only, HK-037).

  python -I fg_night_analyze.py

Reads lc-base\\runs\\{nx,nf}_{NB,NQ}_L_n400\\{arm.json, matched.csv, sel.json} (nx = the shipped build before FINE-GRID, nf = today's default: thin 1 + 4 x 4) and, for the LIVE cross-check, the night's own
ALL.TXT of the daemon and of WSJT-X (message text is read INSIDE `live_matched` only; it returns counts).
Prints per block: Table 1 (matched, ours, rate, ours_only, ours / WSJT-X; deltas), the paired per-cycle difference of matched decodes (mean, standard error, cycles), the cost, the gain by WSJT-X rows per cycle
(crowding bins), and the live daemon's matched share of the same cycles next to the replay of the default.
"""
import csv
import json
import math
import os
import statistics
from collections import Counter, defaultdict

SC = r"D:\Projects\claude\_qa-scratch"
RUNS = SC + r"\lc-base\runs"
G = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts\20261128_0038_endurance_run-gathered"
PIN_NF = "0ef023d55a381db9"
PIN_NX = "fa0b96c1c8a220b3"
BLOCKS = ["NB", "NQ"]
N = 400
BINS = [(0, 15), (16, 25), (26, 35), (36, 10 ** 6)]


def d(tag, blk):
    return os.path.join(RUNS, "%s_%s_L_n%d" % (tag, blk, N))


def matched_counts(path):
    out = {}
    with open(os.path.join(path, "matched.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            v = row["wsjtx_idx"]
            out[row["stamp"]] = len(v.split(";")) if v else 0
    return out


def wsjtx_rows(stamps):
    cnt = Counter()
    S = set(stamps)
    with open(os.path.join(G, "wsjt-x", "ALL.TXT"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = [x for x in line.split(" ") if x]
            if len(f) >= 8 and f[2] == "Rx" and f[3] == "FT8" and f[0] in S:
                cnt[f[0]] += 1
    return cnt


def live_matched(stamps):
    """The live daemon's decodes matched to WSJT-X's in the same cycle by normalised message text (the ANOVA's rule), counts only."""
    S = set(stamps)

    def load(path):
        out = set()
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = [x for x in line.split(" ") if x]
                if len(f) >= 8 and f[2] == "Rx" and f[3] == "FT8" and f[0] in S:
                    out.add((f[0], " ".join(f[7:]).strip()))
        return out
    ours = load(os.path.join(G, "owsfz", "ALL.TXT"))
    ref = load(os.path.join(G, "wsjt-x", "ALL.TXT"))
    return {"ours": len(ours), "wsjtx": len(ref), "matched": len(ours & ref)}


def main():
    out = {}
    for blk in BLOCKS:
        ax, af = json.load(open(d("nx", blk) + r"\arm.json")), json.load(open(d("nf", blk) + r"\arm.json"))
        assert af["bin_pin"] == PIN_NF and ax["bin_pin"] == PIN_NX, (af["bin_pin"], ax["bin_pin"])
        assert ax["wsjtx_decodes"] == af["wsjtx_decodes"] and ax["first_cycle"] == af["first_cycle"] and ax["last_cycle"] == af["last_cycle"]
        assert "--lean-thin 1" in af["flags"] and "--lean-time-osr 4 --lean-freq-osr 4" in af["flags"] and "--lean-thin" not in ax["flags"], (ax["flags"], af["flags"])
        sel = json.load(open(d("nf", blk) + r"\sel.json"))
        stamps = list(sel["runs"][sel["run"]]["FULL"])
        W = wsjtx_rows(stamps)
        mx, mf = matched_counts(d("nx", blk)), matched_counts(d("nf", blk))
        diffs = [mf.get(s, 0) - mx.get(s, 0) for s in stamps]
        wj = ax["wsjtx_decodes"]
        t1 = {}
        for nm, a in (("xn", ax), ("default", af)):
            t1[nm] = {"matched": a["matched"], "ours": a["ours"], "rate_pct": a["rate_pct"], "ours_only_pct": a["ours_only_pct"], "ours_over_wsjtx_pct": round(100.0 * a["ours"] / wj, 3)}
        t1["delta"] = {"rate_pp": round(af["rate_pct"] - ax["rate_pct"], 3), "ours_only_pp": round(af["ours_only_pct"] - ax["ours_only_pct"], 3), "matched": af["matched"] - ax["matched"],
                       "ours": af["ours"] - ax["ours"]}
        sd = statistics.stdev(diffs)
        paired = {"cycles": len(diffs), "mean_matched_per_cycle": round(statistics.mean(diffs), 3), "se": round(sd / math.sqrt(len(diffs)), 3),
                  "mean_over_se": round(statistics.mean(diffs) / (sd / math.sqrt(len(diffs))), 2), "cycles_better": sum(1 for x in diffs if x > 0), "cycles_worse": sum(1 for x in diffs if x < 0)}
        bins = {}
        for lo, hi in BINS:
            sel_s = [s for s in stamps if lo <= W.get(s, 0) <= hi]
            if not sel_s:
                continue
            wr = sum(W.get(s, 0) for s in sel_s)
            mxs, mfs = sum(mx.get(s, 0) for s in sel_s), sum(mf.get(s, 0) for s in sel_s)
            bins["%d-%s" % (lo, hi if hi < 10 ** 6 else "+")] = {"cycles": len(sel_s), "wsjtx_rows": wr, "xn_rate_pct": round(100.0 * mxs / wr, 2), "default_rate_pct": round(100.0 * mfs / wr, 2),
                                                                 "gain_pp": round(100.0 * (mfs - mxs) / wr, 2), "matched_gained": mfs - mxs}
        cost = {"cpu_s_per_cycle": [ax["cpu_s_per_cycle"], af["cpu_s_per_cycle"]], "last_p95_ms": [ax["last_p95_ms"], af["last_p95_ms"]], "abandoned": [ax["abandoned_cycles"], af["abandoned_cycles"]],
                "native_error_cycles": [ax["lean_error_cycles"], af["lean_error_cycles"]]}
        lv = live_matched(stamps)
        live = {"live_daemon_matched": lv["matched"], "live_daemon_rate_pct": round(100.0 * lv["matched"] / lv["wsjtx"], 3), "live_daemon_ours": lv["ours"], "live_wsjtx_dedup": lv["wsjtx"],
                "replay_default_rate_pct": af["rate_pct"], "replay_xn_rate_pct": ax["rate_pct"]}
        out[blk] = {"first_cycle": ax["first_cycle"], "last_cycle": ax["last_cycle"], "wsjtx_per_cycle": round(wj / len(stamps), 1), "wsjtx_decodes": wj, "table1": t1, "paired": paired, "by_crowding": bins,
                    "cost": cost, "live_crosscheck": live}
    with open(os.path.join(SC, "lc-base", "fg_night_analyze.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
