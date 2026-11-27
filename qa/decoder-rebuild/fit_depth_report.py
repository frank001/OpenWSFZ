#!/usr/bin/env python3
"""FIT-DEPTH report (spec-fit-depth.md section 4-6): tables, checks C1-C4 and the section 6 predicates, from the per-signal records fit_depth.py wrote.

  python -I fit_depth_report.py <tag> [--probe-tag xn]

Aggregates only (HK-037). Reads _qa-scratch\\fit-depth\\<tag>\\recs_<slice>.jsonl and meta.json, and (check C1) the xn run's probe.tsv SUB rows, matched.csv and the WSJT-X lines' numbers.
"""
import collections
import csv
import json
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fit_depth as F  # noqa: E402

SC = F.SC
WINDOWS = F.WINDOWS
VARIANTS = ["%s_%.2f" % (s, w) for s, _ in F.SHAPES for w in WINDOWS]
REF = "gfsk_0.32"
TOL_HZ, TOL_S = 3.2, 0.2                                  # spec 3.5: +-3 Hz and +-0.2 s


def q(v):
    v = sorted(x for x in v if x is not None and x == x)
    if not v:
        return None
    f = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]
    return {"n": len(v), "q1": round(f(0.25), 2), "med": round(statistics.median(v), 2), "q3": round(f(0.75), 2)}


def load(tag):
    d = SC + r"\fit-depth\%s" % tag
    meta = json.load(open(d + r"\meta.json"))
    recs = {}
    for sl in meta["slices"].split(","):
        recs[sl] = [json.loads(l) for l in open(d + r"\recs_%s.jsonl" % sl, encoding="utf-8")]
    return meta, recs


def c1(slice_name, recs, probe_tag):
    """Python suppression (W 0.32 s, GFSK, whole-footprint power before/after) minus the native SUB row's, per matched signal; median."""
    n, folder = F.SLICES[slice_name]
    d = F.LCRUNS + r"\%s_%s_L_n%d" % (probe_tag, slice_name, n)
    stamps = sorted({r["stamp"] for r in recs})
    # native SUB rows: stamp -> [(f, t, supp)]
    sub = collections.defaultdict(list)
    with open(d + r"\probe.tsv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 7 or c[0] not in stamps or int(c[1]) != F.KIND_SUB:
                continue
            if float(c[6]) != -999.0:
                sub[c[0]].append((float(c[3]), float(c[4]), float(c[6]), int(c[2])))
    # time convention: probe time = DT + OFFSET; OFFSET = median over the Python fits' (start/FS - dt) is NOT the probe's; calibrate on SUB rows near a WSJT-X decode by frequency (unique within 3.2 Hz) as SUB-PROBE does with CANDs
    diffs = []
    for r in recs:
        if r["status"] != "ok":
            continue
        near = [s for s in sub[r["stamp"]] if abs(s[0] - r["f"]) <= TOL_HZ]
        if len(near) == 1:
            diffs.append(near[0][1] - r["dt"])
    if not diffs:
        return None
    off = statistics.median(diffs)
    delta, clean, used = [], [], 0
    for r in recs:
        if r["status"] != "ok" or "supp_py_db" not in r:
            continue
        near = [s for s in sub[r["stamp"]] if abs(s[0] - r["f"]) <= TOL_HZ and abs(s[1] - (r["dt"] + off)) <= TOL_S]
        if len(near) != 1:
            continue
        used += 1
        delta.append(r["supp_py_db"] - near[0][2])
        # C1 prime: no other native SUB row within +-50 Hz in the same round
        if not any(o is not near[0] and o[3] == near[0][3] and abs(o[0] - near[0][0]) <= 50.0 for o in sub[r["stamp"]]):
            clean.append(r["supp_py_db"] - near[0][2])
    return {"n_matched": used, "offset_s": round(off, 3), "median_diff_db": round(statistics.median(delta), 2) if delta else None, "q": q(delta),
            "clean_n": len(clean), "clean_median_diff_db": round(statistics.median(clean), 2) if clean else None, "clean_q": q(clean),
            "py_median": round(statistics.median([r["supp_py_db"] for r in recs if r["status"] == "ok" and "supp_py_db" in r]), 2)}


def main():
    tag = sys.argv[1]
    ptag = sys.argv[sys.argv.index("--probe-tag") + 1] if "--probe-tag" in sys.argv else "xn"
    meta, recs = load(tag)
    out = {"tag": tag, "meta": meta, "seed": F.SEED}
    ok = {sl: [r for r in rs if r["status"] == "ok"] for sl, rs in recs.items()}
    # C4: completeness
    c4 = {}
    for sl, rs in recs.items():
        c4[sl] = {}
        for b in ("S0", "S1", "S2", "SC"):
            x = [r for r in rs if r["band"] == b]
            c4[sl][b] = {"fitted": sum(1 for r in x if r["status"] == "ok"), "fit_failed": sum(1 for r in x if r["status"] != "ok"),
                         "no_ctl_spot": sum(1 for r in x if r.get("no_ctl_spot")), "no_inj_spot": sum(1 for r in x if r.get("no_inj_spot")),
                         "by_crowd": {c: {"n": sum(1 for r in x if (r["crowded"] == (c == "crowded"))), "no_ctl_spot": sum(1 for r in x if (r["crowded"] == (c == "crowded")) and r.get("no_ctl_spot")),
                                          "no_inj_spot": sum(1 for r in x if (r["crowded"] == (c == "crowded")) and r.get("no_inj_spot"))} for c in ("isolated", "crowded")},
                         "no_inj_share": round(sum(1 for r in x if r.get("no_inj_spot")) / max(1, sum(1 for r in x if r["status"] == "ok")), 3) if b != "SC" else None,
                         "not_encodable": meta["not_encodable"].get(sl, {}).get(b, {}),
                         "same_signals_every_variant": all(len(r["var"]) == len(VARIANTS) for r in x if r["status"] == "ok")}
    out["C4"] = c4
    # Table 1: D by slice x band x crowd x variant; paired change
    t1 = {}
    for sl, rs in ok.items():
        for b in ("S0", "S1", "S2", "SC"):
            for crowd in ("isolated", "crowded", "all"):
                x = [r for r in rs if r["band"] == b and (crowd == "all" or (r["crowded"] == (crowd == "crowded"))) and REF in r["var"]]
                row = {}
                for v in VARIANTS:
                    row[v] = {}
                    for m in ("F", "F_side", "D"):
                        xs = [r for r in x if m in r["var"][v] and m in r["var"][REF]]
                        row[v][m] = q([r["var"][v][m] for r in xs])
                        row[v]["d" + m] = q([r["var"][v][m] - r["var"][REF][m] for r in xs])
                t1["%s/%s/%s" % (sl, b, crowd)] = row
    out["table1"] = t1
    # S0-S2 pooled
    pooled = {}
    for sl, rs in ok.items():
        x = [r for r in rs if r["band"] in ("S0", "S1", "S2") and "F" in r["var"][REF]]
        pooled[sl] = {v: {"F": q([r["var"][v]["F"] for r in x]), "dF": q([r["var"][v]["F"] - r["var"][REF]["F"] for r in x]),
                          "D": q([r["var"][v]["D"] for r in x]), "dD": q([r["var"][v]["D"] - r["var"][REF]["D"] for r in x])} for v in VARIANTS}
    out["table1_S0S2_pooled"] = pooled
    # Table 2: cost of a shorter window, GFSK, S0-S2 pooled
    t2 = {}
    for sl, rs in ok.items():
        x = [r for r in rs if r["band"] in ("S0", "S1", "S2") and r["var"][REF].get("LT_after") is not None]
        t2[sl] = {"n_injected": len(x), "LT_before": q([r["LT_before"] for r in x])}
        for w in WINDOWS:
            k = "gfsk_%.2f" % w
            loss = [r["var"][k]["T_loss_db"] for r in x]
            t2[sl][k] = {"L_ctl": q([r["var"][k]["L_ctl"] for r in rs if r["band"] in ("S0", "S1", "S2") and "L_ctl" in r["var"][k]]),
                         "LT_after": q([r["var"][k]["LT_after"] for r in x]),
                         "dLT_paired": q([r["var"][k]["LT_after"] - r["var"][REF]["LT_after"] for r in x]),
                         "T_loss": q(loss), "T_loss_share_gt_1db": round(sum(1 for v in loss if v > 1.0) / max(1, len(loss)), 3)}
    out["table2"] = t2
    # Table 3: pulse shape
    t3 = {}
    best_w = {}
    for sl, rs in ok.items():
        x = [r for r in rs if r["band"] in ("S0", "S1", "S2") and "F" in r["var"][REF]]
        med = {w: statistics.median([r["var"]["gfsk_%.2f" % w]["F"] for r in x]) for w in WINDOWS} if x else {}
        bw = min(med, key=med.get) if med else None
        best_w[sl] = bw
        t3[sl] = {"best_window_gfsk": bw}
        for w in sorted({0.32, bw}) if bw else [0.32]:
            dd = [r["var"]["gfsk_%.2f" % w]["F"] - r["var"]["cpfsk_%.2f" % w]["F"] for r in x]
            t3[sl]["W%.2f" % w] = {"F_gfsk_minus_cpfsk": q(dd), "share_cpfsk_better_gt_1db": round(sum(1 for v in dd if v > 1.0) / max(1, len(dd)), 3)}
        for b in ("S0", "S1", "S2"):
            xb = [r for r in x if r["band"] == b]
            dd = [r["var"]["gfsk_0.32"]["F"] - r["var"]["cpfsk_0.32"]["F"] for r in xb]
            t3[sl]["share_by_band_%s" % b] = round(sum(1 for v in dd if v > 1.0) / max(1, len(dd)), 3)
    out["table3"] = t3
    # Table 4: where in time
    t4 = {}
    for sl, rs in ok.items():
        x = [r for r in rs if r["band"] in ("S0", "S1", "S2")]
        t4[sl] = {}
        for k in {REF, "gfsk_%.2f" % best_w[sl] if best_w[sl] else REF}:
            t4[sl][k] = [q([r["var"][k]["thirds"][i] for r in x]) for i in range(3)]
    out["table4"] = t4
    # Checks
    out["C1"] = {sl: c1(sl, rs, ptag) for sl, rs in recs.items()}
    out["C1_pass"] = {sl: (v is not None and v["clean_median_diff_db"] is not None and abs(v["clean_median_diff_db"]) <= 2.0) for sl, v in out["C1"].items()}   # C1 prime: the clean signals
    c2, c3 = {}, {}
    for sl, rs in ok.items():
        sc = [r["var"][REF]["F"] for r in rs if r["band"] == "SC" and "F" in r["var"][REF]]
        s02 = [r["var"][REF]["F"] for r in rs if r["band"] in ("S0", "S1", "S2") and "F" in r["var"][REF]]
        c2[sl] = {"median_F_SC": round(statistics.median(sc), 2) if sc else None, "pass": bool(sc) and abs(statistics.median(sc)) <= 1.5}
        c3[sl] = {"median_F_S0S2": round(statistics.median(s02), 2) if s02 else None, "pass": bool(s02) and statistics.median(s02) >= 2.0,
                  "by_band": {b: q([r["var"][REF]["F"] for r in rs if r["band"] == b and "F" in r["var"][REF]]) for b in ("S0", "S1", "S2")}}
    out["C2"], out["C3"] = c2, c3
    # section 6 predicates, per window, all slices
    s6 = {}
    for w in (0.64, 0.16, 0.08):
        k = "gfsk_%.2f" % w
        per = {}
        for sl in ok:
            P = pooled[sl][k]["dF"]
            T = t2[sl][k]
            per[sl] = {"dF_med": P["med"] if P else None, "dLT_med": T["dLT_paired"]["med"] if T["dLT_paired"] else None,
                       "T_loss_med": T["T_loss"]["med"] if T["T_loss"] else None, "T_loss_q3": T["T_loss"]["q3"] if T["T_loss"] else None}
        s6[k] = {"per_slice": per}
        if w < 0.32:
            s6[k]["F_falls_ge_2"] = all(v["dF_med"] is not None and v["dF_med"] <= -2.0 for v in per.values())
            s6[k]["LT_falls_ge_1"] = all(v["dLT_med"] is not None and v["dLT_med"] <= -1.0 for v in per.values())
            s6[k]["retention_ok"] = all(v["T_loss_med"] is not None and v["T_loss_med"] <= 0.5 and v["T_loss_q3"] <= 1.0 for v in per.values())
            s6[k]["build_rule_met"] = s6[k]["F_falls_ge_2"] and s6[k]["LT_falls_ge_1"] and s6[k]["retention_ok"]
    out["section6"] = s6
    out["pulse_rule_met"] = all(t3[sl].get("W0.32", {}).get("share_cpfsk_better_gt_1db", 0) >= 0.10 for sl in ok)
    json.dump(out, open(SC + r"\fit-depth\%s\report.json" % tag, "w"), indent=1, default=float)
    print(json.dumps({k: out[k] for k in ("C1", "C1_pass", "C2", "C3", "C4")}, indent=1, default=float))
    if "--s6" in sys.argv:                      # the section 6 rows are printed ONLY on request, after the checks have been read (the pilot lapse)
        print(json.dumps({"section6": s6, "pulse_rule_met": out["pulse_rule_met"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
