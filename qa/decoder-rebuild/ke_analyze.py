#!/usr/bin/env python3
"""KNOWN-ERASURE analysis (spec-known-erasure.md section 4): the replay `ke_*` against the XC-ROUND confirmation runs `xn_*` (same audio, same flags, same 16 threads; the decoder differs only by the erasure).

  python -I ke_analyze.py      (reads lc-base\\runs\\{xn,ke}_<slice>_L_n<cycles>\\{arm.json, lean.csv, matched.csv, probe.tsv, log.log, sel.json} and WSJT-X's own decodes; numbers only, no message text)

0  FREE CHECK (the Architect's, stated against his section 2): the round-0 CAND rows' numeric columns (position, score, a_code, a_unsat, b_code, b_unsat) are identical to the baseline in every cycle.
   Published batches may differ (later cycles learn from new decodes); they are NOT part of the check. If it fails, stop and tell the Architect.
4.1 Table 1 numbers and deltas.  4.2 cost and the erased-bin share.  4.3 K2 by dSNR band and how many baseline K2 T are now matched.  4.4 knock-on and losses.  (The ours_only check is pf_oo_check.py xn ke.)
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
import sub_probe_analyze as sp   # noqa: E402

SC = sp.SC
SLICES = ["S40", "H40", "H20"]
BASE, NEW = "xn", "ke"
PIN_NEW = "12444634b1882c36"                          # first 16 hex of the SHA256 of libft8.dll of 104bc426 (KNOWN-ERASURE, shim 20260083): the arm.json's bin_pin
BASE_RATE = {"S40": 88.203, "H40": 87.899, "H20": 86.279}      # the XC-ROUND confirmation runs, asserted against their arm.json (inherited constants)
CLASSIC_RATE = {"S40": 84.39, "H40": 85.29, "H20": 81.25}
R_KIND, R_ROUND, R_F, R_T, R_SCORE, R_KEPT, R_OUT = sp.R_KIND, sp.R_ROUND, sp.R_F, sp.R_T, sp.R_SCORE, sp.R_KEPT, sp.R_OUT


def run_dir(tag, name):
    return SC + r"\lc-base\runs\%s_%s_L_n%d" % (tag, name, sp.SL[name][0])


def round0_cand_numeric(d):
    """stamp -> sorted list of the round-0 CAND rows' numeric columns (position, score, a_code, a_unsat, b_code, b_unsat), as text from probe.tsv."""
    per = {}
    with open(d + r"\probe.tsv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 17 or c[1] != "2" or c[2] != "0":
                continue
            per.setdefault(c[0], []).append((c[3], c[4], c[7], c[11], c[12], c[13], c[14]))
    return {s: sorted(v) for s, v in per.items()}


def k2_universe(name, tag, wl, stamps):
    """(stamp, wsjtx index of T) -> dSNR band of every K2 case (a crowded WSJT-X decode lean missed, its nearest neighbour decoded, a failed candidate at T and no decoded one): CS-MAP / SUB-PROBE's definitions."""
    d = run_dir(tag, name)
    M, prb = sp.load_matched(d), sp.load_probe(d + r"\probe.tsv")[0]
    off = statistics.median(sp.calibrate(wl, M, prb))
    out = {}
    classified = 0
    for st in stamps:
        w, rows, ml = wl[st], prb.get(st, []), M.get(st, set())
        cand_low = [r for r in rows if r[R_KIND] in (sp.KIND_CAND, sp.KIND_LOW)]
        for j, (snr, f, dt) in enumerate(w):
            others = [(abs(w[i][1] - f), i) for i in range(len(w)) if i != j]
            if not others or sum(1 for dd, _ in others if dd <= sp.CROWD_HZ) < 1 or j in ml:
                continue
            _, ni = min(others)
            if ni not in ml:
                continue
            classified += 1
            nsnr, nf, ndt = w[ni]
            tt = dt + off
            near = [r for r in cand_low if abs(r[R_F] - f) <= sp.TOL_HZ and abs(r[R_T] - tt) <= sp.TOL_S and abs(r[R_F] - f) <= abs(r[R_F] - nf)]
            if any(r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.PUBLISHED for r in near) or any(r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.DROPPED for r in near):
                continue
            if any(r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.FAILED for r in near):
                out[(st, j)] = sp.dsnr_bin(nsnr - snr)
    return out, classified


def erased_share(d):
    """Tier-A candidates of rounds 1 to 3 and of the XC round, and those with at least one erased bin, from the lean log lines (absent fields = 0) and lean.csv's xr_* columns."""
    r13 = Counter()
    with open(d + r"\log.log", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "lean:" not in line or "r1[" not in line:
                continue
            for r in (1, 2, 3):
                b = re.search(r"r%d\[([^\]]*)\]" % r, line)
                if b:
                    kv = dict(re.findall(r"(\w+)=([\d.]+)", b.group(1)))
                    r13["cands"] += int(float(kv.get("aCands", 0))); r13["erased"] += int(float(kv.get("aErased", 0)))
                    r13["cands_r%d" % r] += int(float(kv.get("aCands", 0))); r13["erased_r%d" % r] += int(float(kv.get("aErased", 0)))
    xc = Counter()
    for row in csv.DictReader(open(d + r"\lean.csv", newline="")):
        if "xr_acands" in row:
            xc["cands"] += int(row["xr_acands"]); xc["erased"] += int(row["xr_aerased"])
    tot_c, tot_e = r13["cands"] + xc["cands"], r13["erased"] + xc["erased"]
    pct = lambda e, c: round(100.0 * e / c, 1) if c else None
    return {"rounds1to3": {"tierA_candidates": r13["cands"], "with_erased_bin": r13["erased"], "share_pct": pct(r13["erased"], r13["cands"]),
                           "by_round": {str(r): {"tierA_candidates": r13["cands_r%d" % r], "with_erased_bin": r13["erased_r%d" % r], "share_pct": pct(r13["erased_r%d" % r], r13["cands_r%d" % r])} for r in (1, 2, 3)}},
            "xc_round": {"tierA_candidates": xc["cands"], "with_erased_bin": xc["erased"], "share_pct": pct(xc["erased"], xc["cands"])},
            "all_residual_rounds": {"tierA_candidates": tot_c, "with_erased_bin": tot_e, "share_pct": pct(tot_e, tot_c)}}


def run_slice(name):
    n, folder = sp.SL[name]
    od, nd = run_dir(BASE, name), run_dir(NEW, name)
    oa, na = json.load(open(od + r"\arm.json")), json.load(open(nd + r"\arm.json"))
    assert na["bin_pin"] == PIN_NEW, na["bin_pin"]
    assert abs(oa["rate_pct"] - BASE_RATE[name]) < 0.01, (oa["rate_pct"], BASE_RATE[name])
    assert na["wsjtx_decodes"] == oa["wsjtx_decodes"]
    so, sn = json.load(open(od + r"\sel.json")), json.load(open(nd + r"\sel.json"))
    assert so == sn, "the two runs must replay the same cycles"
    stamps = list(sn["runs"][sn["run"]]["FULL"])
    # 0 the free check
    co, cn = round0_cand_numeric(od), round0_cand_numeric(nd)
    differing = [s for s in stamps if co.get(s, []) != cn.get(s, [])]
    free = {"cycles": len(stamps), "cycles_with_round0_cand_rows_before": len(co), "cycles_with_round0_cand_rows_after": len(cn), "round0_cand_rows_before": sum(len(v) for v in co.values()),
            "round0_cand_rows_after": sum(len(v) for v in cn.values()), "cycles_differing": len(differing)}
    # 4.1
    t1 = {"before_xn_run": {k: oa[k] for k in ("matched", "ours", "rate_pct", "ours_only_pct")}, "after_ke": {k: na[k] for k in ("matched", "ours", "rate_pct", "ours_only_pct")},
          "delta": {"rate_pp": round(na["rate_pct"] - oa["rate_pct"], 3), "ours_only_pp": round(na["ours_only_pct"] - oa["ours_only_pct"], 3), "matched": na["matched"] - oa["matched"], "ours": na["ours"] - oa["ours"]},
          "lean_minus_classic_pp": round(na["rate_pct"] - CLASSIC_RATE[name], 2)}
    # 4.2 cost
    ln = list(csv.DictReader(open(nd + r"\lean.csv", newline="")))
    att = [r for r in ln if int(r.get("xr_detections", 0)) > 0]
    assert sum(int(r["xr_fits"]) for r in att) > 0 and sum(float(r["xr_wall_ms"]) for r in att) > 0, "the XC round did no work in this replay: the harness wrapper did not forward DecodeLeanXcRound (a signature mismatch lands on the interface's empty default): the replay is VOID"
    cost = {"cpu_s_per_cycle": [oa["cpu_s_per_cycle"], na["cpu_s_per_cycle"]], "cpu_change_pct": round(100.0 * (na["cpu_s_per_cycle"] / oa["cpu_s_per_cycle"] - 1.0), 1),
            "last_p95_ms": [oa["last_p95_ms"], na["last_p95_ms"]], "abandoned_cycles": [oa["abandoned_cycles"], na["abandoned_cycles"]], "native_error_cycles": [oa["lean_error_cycles"], na["lean_error_cycles"]],
            "lean_parse_failed": na.get("lean_parse_failed"), "xc_rounds_run": len(att), "xr_batch4_decodes": sum(int(r["xr_decodes"]) for r in att),
            "xr_cpu_s_per_cycle_added": round(sum(float(r["xr_cpu_ms"]) for r in att) / 1000.0 / len(ln), 3), "erased_share": erased_share(nd)}
    # 4.3 / 4.4 K2 by dSNR band and the baseline K2 T now matched
    wl = sp.load_wsjtx(os.path.join(sp.ART, folder, "wsjt-x", "ALL.TXT"), stamps)
    k2_old, cl_old = k2_universe(name, BASE, wl, stamps)
    k2_new, cl_new = k2_universe(name, NEW, wl, stamps)
    Mo, Mn = sp.load_matched(od), sp.load_matched(nd)
    bands = [b[0] for b in sp.DSNR]
    band_tab = {b: {"k2_before": sum(1 for v in k2_old.values() if v == b), "k2_after": sum(1 for v in k2_new.values() if v == b),
                    "baseline_K2_T_now_matched": sum(1 for (st, j), v in k2_old.items() if v == b and j in Mn.get(st, set()))} for b in bands}
    k2 = {"classified_before": cl_old, "classified_after": cl_new, "k2_before": len(k2_old), "k2_after": len(k2_new), "baseline_K2_T_now_matched": sum(1 for (st, j) in k2_old if j in Mn.get(st, set())), "by_dsnr_band": band_tab}
    gained = lost = gained_in = 0
    for st in stamps:
        g, l = Mn.get(st, set()) - Mo.get(st, set()), Mo.get(st, set()) - Mn.get(st, set())
        gained += len(g); lost += len(l)
        gained_in += sum(1 for j in g if (st, j) in k2_old)
    assert gained - lost == na["matched"] - oa["matched"]
    knock = {"matched_gained_gross": gained, "matched_lost_gross": lost, "net": gained - lost, "gained_in_the_baseline_K2_cases": gained_in, "gained_outside_the_baseline_K2_cases": gained - gained_in}
    return {"free_check": free, "table1": t1, "cost": cost, "k2": k2, "knock_on": knock}


def main():
    out = {s: run_slice(s) for s in SLICES}
    with open(os.path.join(SC, "lc-base", "ke_analyze.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
