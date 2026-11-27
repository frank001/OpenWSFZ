#!/usr/bin/env python3
"""PAYLOAD-FIT analysis (spec-payload-fit.md section 4): the replay `pf_*` against the SUB-PROBE runs `probe_*` (same audio, same flags, same 16 threads; the decoder differs only by the removed text gate).

  python -I pf_analyze.py            (reads lc-base\\runs\\{probe,pf}_<slice>_L_n<cycles>\\{arm.json, matched.csv, probe.tsv, log.log, lean.csv, sel.json, matchedbatch.csv} and the WSJT-X ALL.TXT numbers)

Counts and numbers only (HK-037); the one text-reading function is r1r4_split.load_results (gate codes only).
4.1 Table 1 numbers and deltas.  4.2 cost.  4.3 the R1-linked K2 cases of the SUB-PROBE run: did N get a SUB row now, is T matched now.  4.4 knock-on: matched gained and lost, in and outside those cases.
"""
import csv
import json
import os
import re
import statistics
import sys
from collections import Counter

sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r1r4_split as rs          # noqa: E402
import sub_probe_analyze as sp   # noqa: E402

SC = sp.SC
SLICES = ["S40", "H40", "H20"]
CLASSIC = {"S40": {"matched": 5716, "ours": 5971, "wsjtx": 6773, "rate": 84.39, "ours_only": 3.77},       # the committed SUB-PROBE result, Table 1 (LC-BASE's classic arm)
           "H40": {"matched": 7662, "ours": 8233, "wsjtx": 8983, "rate": 85.29, "ours_only": 6.36},
           "H20": {"matched": 7438, "ours": 7999, "wsjtx": 9154, "rate": 81.25, "ours_only": 6.13}}
PIN_NEW = "2f522765d508085861bd0098b66c39d628ab7884"          # libft8.dll of b26a156c (PAYLOAD-FIT, shim 20260081), first 40 hex of the SHA256


def run_dir(tag, name):
    return SC + r"\lc-base\runs\%s_%s_L_n%d" % (tag, name, sp.SL[name][0])


def load_matched_idx(d):
    return sp.load_matched(d)


def cost(d, stamps):
    """fits, fitNone, rounds run (the s3: rounds= field), per cycle, from the lean log lines."""
    fits = fitnone = rounds = skipped = n = 0
    with open(os.path.join(d, "log.log"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "lean:" not in line or "r1[" not in line:
                continue
            n += 1
            m = re.search(r"s3: rounds=(\d+)", line)
            rounds += int(m.group(1)) if m else 0
            for r in (1, 2, 3):
                b = re.search(r"r%d\[([^\]]*)\]" % r, line)
                if b:
                    kv = dict(re.findall(r"(\w+)=([\d.]+)", b.group(1)))
                    fits += int(float(kv["fits"])); fitnone += int(float(kv["fitNone"])); skipped += int(float(kv["skipped"]))
    assert n == len(stamps), (n, len(stamps))
    return {"fits_per_cycle": round(fits / n, 2), "fitNone_per_cycle": round(fitnone / n, 2), "skipped_per_cycle": round(skipped / n, 2), "rounds_per_cycle": round(rounds / n, 3)}


def run_slice(name):
    n, folder = sp.SL[name]
    old_d, new_d = run_dir("probe", name), run_dir("pf", name)
    old_a, new_a = json.load(open(old_d + r"\arm.json")), json.load(open(new_d + r"\arm.json"))
    assert new_a["bin_pin"] == PIN_NEW[:16], new_a["bin_pin"]
    assert old_a["wsjtx_decodes"] == new_a["wsjtx_decodes"] == CLASSIC[name]["wsjtx"]
    sel_old = json.load(open(old_d + r"\sel.json")); sel_new = json.load(open(new_d + r"\sel.json"))
    assert sel_old == sel_new, "the two runs must replay the same cycles"
    stamps = list(sel_new["runs"][sel_new["run"]]["FULL"])
    Mo, Mn = sp.load_matched(old_d), sp.load_matched(new_d)

    # 4.1 Table 1
    t1 = {"wsjtx": new_a["wsjtx_decodes"],
          "classic": CLASSIC[name],
          "before_SUBPROBE_run": {k: old_a[k] for k in ("matched", "ours", "rate_pct", "ours_only_pct")},
          "after_PAYLOADFIT": {k: new_a[k] for k in ("matched", "ours", "rate_pct", "ours_only_pct")}}
    t1["delta_pp"] = {"rate": round(new_a["rate_pct"] - old_a["rate_pct"], 3), "ours_only": round(new_a["ours_only_pct"] - old_a["ours_only_pct"], 3),
                      "matched": new_a["matched"] - old_a["matched"], "ours": new_a["ours"] - old_a["ours"]}
    t1["after_minus_classic_pp"] = {"rate": round(new_a["rate_pct"] - CLASSIC[name]["rate"], 2), "ours_only": round(new_a["ours_only_pct"] - CLASSIC[name]["ours_only"], 2)}

    # 4.2 cost
    c = {"cpu_s_per_cycle": [old_a["cpu_s_per_cycle"], new_a["cpu_s_per_cycle"]], "cpu_change_pct": round(100.0 * (new_a["cpu_s_per_cycle"] / old_a["cpu_s_per_cycle"] - 1.0), 1),
         "last_p95_ms": [old_a["last_p95_ms"], new_a["last_p95_ms"]], "abandoned_cycles": [old_a["abandoned_cycles"], new_a["abandoned_cycles"]],
         "native_error_cycles": [old_a["lean_error_cycles"], new_a["lean_error_cycles"]], "old": cost(old_d, stamps), "new": cost(new_d, stamps)}

    # 4.3 / 4.4: the R1-linked K2 cases of the SUB-PROBE run (QA's script, the same universe as the 112 / 18 / 134)
    rs.run_slice(name, "probe")
    cases = rs.R1_CASES[("probe", name)]
    wl = sp.load_wsjtx(os.path.join(sp.ART, folder, "wsjt-x", "ALL.TXT"), stamps)
    prb_new, _ = sp.load_probe(os.path.join(new_d, "probe.tsv"))
    off_new = statistics.median(sp.calibrate(wl, Mn, prb_new))
    r1 = Counter()
    case_keys = set()
    for (st, j, ni) in cases:
        case_keys.add((st, j))
        _, nf, ndt = wl[st][ni]
        subs = [r for r in prb_new.get(st, []) if r[sp.R_KIND] == sp.KIND_SUB]
        has_sub = rs.sub_at(subs, nf, ndt + off_new) is not None
        t_matched = j in Mn.get(st, set())
        r1["n_cases"] += 1
        r1["N_has_SUB_row_now"] += has_sub
        r1["T_matched_now"] += t_matched
        r1["T_matched_now_and_N_SUB"] += (t_matched and has_sub)
        r1["T_matched_now_but_N_no_SUB"] += (t_matched and not has_sub)
    gained = lost = gained_in_cases = 0
    gained_crowded = gained_not_crowded = 0
    for st in stamps:
        g = Mn.get(st, set()) - Mo.get(st, set())
        l = Mo.get(st, set()) - Mn.get(st, set())
        gained += len(g); lost += len(l)
        for j in g:
            if (st, j) in case_keys:
                gained_in_cases += 1
            w = wl[st]
            crowded = any(i != j and abs(w[i][1] - w[j][1]) <= sp.CROWD_HZ for i in range(len(w)))
            gained_crowded += crowded; gained_not_crowded += (not crowded)
    knock = {"matched_gained_gross": gained, "matched_lost_gross": lost, "net": gained - lost, "gained_in_the_R1_cases": gained_in_cases, "gained_outside_the_R1_cases": gained - gained_in_cases,
             "gained_outside_that_were_crowded": gained_crowded - gained_in_cases, "gained_outside_that_were_not_crowded": gained_not_crowded}
    assert gained - lost == new_a["matched"] - old_a["matched"], (gained, lost)
    return {"table1": t1, "cost": c, "r1_cases": dict(r1), "knock_on": knock}


def main():
    out = {s: run_slice(s) for s in SLICES}
    with open(os.path.join(SC, "lc-base", "pf_analyze.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
