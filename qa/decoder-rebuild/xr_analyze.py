#!/usr/bin/env python3
"""XC-ROUND analysis (spec-xc-round.md section 4): the replay `xr_*` against the PAYLOAD-FIT runs `pf_*` (same audio, same flags, same 16 threads; the decoder differs only by the XC round).

  python -I xr_analyze.py      (reads lc-base\\runs\\{pf,xr}_<slice>_L_n<cycles>\\{arm.json, lean.csv, matched.csv, probe.tsv, sel.json, the decode dump} and WSJT-X's own decodes)

0  FREE CHECK: batches 1-3 byte-identical to the baseline in every cycle (decodes: cycle, batch, frequency, dt, SNR, message; and every probe row of rounds 0-3). If this fails the replay is void: stop and tell the Architect.
4.1 Table 1 numbers and deltas.  4.2 cost.  4.3 the XC cases (the K2 cases of the PAYLOAD-FIT run whose never-subtracted neighbour was a cross-cycle result): round-4 SUB row for N, T matched now; the new never-subtracted split.
4.4 knock-on: matched gained and lost, in and outside those cases.  Batch-4 decodes: how many, how many matched.
Counts and numbers only (HK-037): message text is read INSIDE `free_check_slice` and `batch4_slice` and never leaves them (only counts and flags do).
"""
import csv
import json
import os
import statistics
import sys
from collections import Counter

NEW_TAG = sys.argv[1] if len(sys.argv) > 1 else "xr"        # the run under test: xr = XC-ROUND with the prior-store feed, xn = as shipped (batch 4 not stored)
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r1r4_split as rs          # noqa: E402
import sub_probe_analyze as sp   # noqa: E402

SC = sp.SC
SLICES = ["S40", "H40", "H20"]
BASE, NEW = "pf", NEW_TAG
PIN_NEW = "fa0b96c1c8a220b3"                          # first 16 hex of the SHA256 of libft8.dll of 65bca805 (XC-ROUND, shim 20260082): the arm.json's bin_pin
BASE_RATE = {"S40": 87.79, "H40": 87.243, "H20": 85.241}   # asserted against the PAYLOAD-FIT arm.json below (inherited constants, rounded)


def run_dir(tag, name):
    return SC + r"\lc-base\runs\%s_%s_L_n%d" % (tag, name, sp.SL[name][0])


def norm(t):
    return " ".join(t.split())


def free_check_slice(name):
    """The free check and the batch-4 numbers. READS TEXT; RETURNS COUNTS ONLY."""
    n = sp.SL[name][0]
    od, nd = run_dir(BASE, name), run_dir(NEW, name)

    def load(d):
        rows = {}
        with open(d + r"\nc.tsv", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) < 11:
                    continue
                k = (c[0], norm(c[10]))
                if k not in rows:
                    rows[k] = (int(c[1]), c[3], c[4], c[5], c[2])           # batch, freq, dt, snr, matched
        return rows

    old, new = load(od), load(nd)
    b123_old = {k: v[:4] for k, v in old.items() if v[0] in (1, 2, 3)}
    b123_new = {k: v[:4] for k, v in new.items() if v[0] in (1, 2, 3)}
    only_old = sum(1 for k in b123_old if k not in b123_new)
    only_new = sum(1 for k in b123_new if k not in b123_old)
    changed = sum(1 for k in b123_old if k in b123_new and b123_old[k] != b123_new[k])
    matched_flag_changed = sum(1 for k in b123_old if k in new and old[k][4] != new[k][4])
    cycles_differing = len({k[0] for k in b123_old if k not in b123_new} | {k[0] for k in b123_new if k not in b123_old} | {k[0] for k in b123_old if k in b123_new and b123_old[k] != b123_new[k]})
    b4 = {k: v for k, v in new.items() if v[0] == 4}
    # probe rows of rounds 0 to 3, per cycle, compared line by line (numbers only)
    def probe_lines(d):
        per = {}
        with open(d + r"\probe.tsv", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) < 3:
                    per.setdefault(c[0], []).append("OVERFLOW")
                    continue
                if c[2] == "4":
                    continue
                per.setdefault(c[0], []).append(line.rstrip("\n"))
        return per
    po, pn = probe_lines(od), probe_lines(nd)
    probe_cycles_differing = sum(1 for s in set(po) | set(pn) if sorted(po.get(s, [])) != sorted(pn.get(s, [])))
    r4_rows = Counter()
    with open(nd + r"\probe.tsv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > 2 and c[2] == "4":
                r4_rows[{"1": "SUB", "2": "CAND", "3": "LOW"}.get(c[1], c[1])] += 1
    return {"decodes_b123_before": len(b123_old), "decodes_b123_after": len(b123_new), "b123_only_in_before": only_old, "b123_only_in_after": only_new, "b123_changed_fields": changed,
            "b123_matched_flag_changed": matched_flag_changed, "decode_cycles_differing": cycles_differing, "probe_rows_round0to3_cycles_differing": probe_cycles_differing,
            "batch4_decodes": len(b4), "batch4_matched": sum(1 for v in b4.values() if v[4] == "1"), "round4_probe_rows": dict(r4_rows)}


def lean_cols(d):
    rows = list(csv.DictReader(open(d + r"\lean.csv", newline="")))
    return rows


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
    fc = free_check_slice(name)
    t1 = {"before_PAYLOADFIT_run": {k: oa[k] for k in ("matched", "ours", "rate_pct", "ours_only_pct")}, "after_XCROUND": {k: na[k] for k in ("matched", "ours", "rate_pct", "ours_only_pct")},
          "delta": {"rate_pp": round(na["rate_pct"] - oa["rate_pct"], 3), "ours_only_pp": round(na["ours_only_pct"] - oa["ours_only_pct"], 3), "matched": na["matched"] - oa["matched"], "ours": na["ours"] - oa["ours"]}}
    ln, lo = lean_cols(nd), lean_cols(od)
    attempted = [r for r in ln if "xr_detections" in r and int(r["xr_detections"]) > 0]
    cost = {"cpu_s_per_cycle": [oa["cpu_s_per_cycle"], na["cpu_s_per_cycle"]], "cpu_change_pct": round(100.0 * (na["cpu_s_per_cycle"] / oa["cpu_s_per_cycle"] - 1.0), 1),
            "last_p95_ms": [oa["last_p95_ms"], na["last_p95_ms"]], "abandoned_cycles": [oa["abandoned_cycles"], na["abandoned_cycles"]], "native_error_cycles": [oa["lean_error_cycles"], na["lean_error_cycles"]],
            "lean_parse_failed": na.get("lean_parse_failed"), "cycles": len(ln),
            "xc_rounds_run": len(attempted), "xc_rounds_per_cycle": round(len(attempted) / len(ln), 3),
            "xr_fits_per_cycle": round(sum(int(r["xr_fits"]) for r in attempted) / len(ln), 3), "xr_fitnone_per_cycle": round(sum(int(r["xr_fitnone"]) for r in attempted) / len(ln), 3),
            "xr_batch4_decodes": sum(int(r["xr_decodes"]) for r in attempted), "xr_batch4_decodes_per_cycle": round(sum(int(r["xr_decodes"]) for r in attempted) / len(ln), 3),
            "xr_round_errors": sum(1 for r in attempted if int(r["xr_error"]) != 0), "xr_round_abandoned": sum(int(r["xr_abandoned"]) for r in attempted),
            "xr_wall_ms_per_round_median": round(statistics.median(float(r["xr_wall_ms"]) for r in attempted), 1) if attempted else None,
            "xr_cpu_ms_per_round_median": round(statistics.median(float(r["xr_cpu_ms"]) for r in attempted), 1) if attempted else None,
            "xr_cpu_s_per_cycle_added": round(sum(float(r["xr_cpu_ms"]) for r in attempted) / 1000.0 / len(ln), 3)}
    # 4.3 the XC cases of the PAYLOAD-FIT run
    rs.run_slice(name, BASE)
    cases = rs.XC_CASES[(BASE, name)]
    wl = sp.load_wsjtx(os.path.join(sp.ART, folder, "wsjt-x", "ALL.TXT"), stamps)
    Mo, Mn = sp.load_matched(od), sp.load_matched(nd)
    prb_new, _ = sp.load_probe(nd + r"\probe.tsv")
    off_new = statistics.median(sp.calibrate(wl, Mn, prb_new))
    xc = Counter()
    keys = set()
    for (st, j, ni) in cases:
        keys.add((st, j))
        _, nf, ndt = wl[st][ni]
        subs = [r for r in prb_new.get(st, []) if r[sp.R_KIND] == sp.KIND_SUB]
        s = rs.sub_at(subs, nf, ndt + off_new)
        has_r4 = s is not None and s[sp.R_ROUND] == 4
        t_m = j in Mn.get(st, set())
        xc["cases"] += 1; xc["N_has_round4_SUB_row"] += has_r4; xc["N_has_SUB_row_of_another_round"] += (s is not None and not has_r4)
        xc["T_matched_now"] += t_m; xc["T_matched_now_and_N_round4_SUB"] += (t_m and has_r4); xc["T_matched_now_N_not_round4_SUB"] += (t_m and not has_r4)
    split = rs.run_slice(name, NEW)
    # 4.4 knock-on
    gained = lost = gained_in = gained_crowded = 0
    for st in stamps:
        g, l = Mn.get(st, set()) - Mo.get(st, set()), Mo.get(st, set()) - Mn.get(st, set())
        gained += len(g); lost += len(l)
        w = wl[st]
        for j in g:
            gained_in += (st, j) in keys
            gained_crowded += any(i != j and abs(w[i][1] - w[j][1]) <= sp.CROWD_HZ for i in range(len(w))) and (st, j) not in keys
    assert gained - lost == na["matched"] - oa["matched"]
    knock = {"matched_gained_gross": gained, "matched_lost_gross": lost, "net": gained - lost, "gained_in_the_XC_cases": gained_in, "gained_outside_the_XC_cases": gained - gained_in, "gained_outside_that_were_crowded": gained_crowded}
    return {"free_check": fc, "table1": t1, "cost": cost, "xc_cases": dict(xc), "new_split_k2": {"cases": sum(split["k2_neighbour_class"].values()), "never_subtracted": split["k2_unsubtracted"], "classes": split["k2_neighbour_class"]}, "knock_on": knock}


def main():
    out = {s: run_slice(s) for s in SLICES}
    with open(os.path.join(SC, "lc-base", "xr_analyze.json" if NEW == "xr" else "%s_analyze.json" % NEW), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
