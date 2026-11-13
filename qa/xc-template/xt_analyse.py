#!/usr/bin/env python3
"""XC-TEMPLATE analysis (spec 2e133bc0 + A1).  Reads frozen\\xt_tasks.json, frozen\\te.json (T_E), own.json; numbers only.   python xt_analyse.py   (run ONCE per frozen scoring)"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xt_lib as L          # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/xc-template"


def rate(xs):
    return (sum(xs) / len(xs)) if len(xs) else None


def detected(res, row, te, hashed_not_detected=False):
    if hashed_not_detected and row.get("hashed"):
        return False
    return bool(res["S"] >= te and res["truth"])


def main():
    T = json.load(open(OUT + "/frozen/xt_tasks.json"))
    te = json.load(open(OUT + "/frozen/te.json"))
    own = json.load(open(OUT + "/own.json"))
    pil = T["pilot"]
    stamps = T["stamps"]
    cix = {s: i for i, s in enumerate(stamps)}
    idx = L.boot_idx(len(stamps))
    t_e = te["T_E"]
    E1, P = T["E1"], T["P"]
    e1_pil = set(pil["E1"])
    # E1 acceptance rows: ALL (non-pilot) rows are in the denominator; hashed / unencodable rows count as not detected
    e1_all = [i for i in range(len(E1)) if i not in e1_pil]
    sc = {i: (own["E1_resid"][k], own["E1_O"][k]) for k, i in enumerate(own["E1_idx"])}
    det_r = {i: (detected(sc[i][0], E1[i], t_e) if i in sc else False) for i in e1_all}
    det_o = {i: (detected(sc[i][1], E1[i], t_e) if i in sc else False) for i in e1_all}

    def by_cycle(sel, det):
        n, d = np.zeros(len(stamps)), np.zeros(len(stamps))
        for i in sel:
            c = cix[E1[i]["stamp"]]
            n[c] += 1
            d[c] += det[i]
        return d, n

    d, n = by_cycle(e1_all, det_r)
    D_e1, ci_d = L.rate_ci(d, n, idx)
    g = L.g_pp(D_e1)
    g_ci = [L.g_pp(x) for x in ci_d]
    # V-POS: D(P) on O (acceptance rows), by cycle bootstrap
    pi = own["P_idx"]
    pdet_o = [bool(r["S"] >= t_e and r["truth"]) for r in own["P_O"]]
    pdet_r = [bool(r["S"] >= t_e and r["truth"]) for r in own["P_resid"]]
    pn, pd = np.zeros(len(stamps)), np.zeros(len(stamps))
    for k, i in enumerate(pi):
        c = cix[P[i]["stamp"]]
        pn[c] += 1
        pd[c] += pdet_o[k]
    D_p, ci_p = L.rate_ci(pd, pn, idx)
    rin = {"v_null_n_ok": bool(te["V_NULL_N"]["PASS"]), "v_pos_ci": ci_p, "g_ci": g_ci}
    verdict = L.decide(rin)
    res = {"verdict": verdict, "rule_inputs": rin, "T_E": t_e, "T_E_bootstrap_CI": te["T_E_bootstrap_CI"], "split_half": te["split_half"], "V_FA": {"exceedance_at_T_E": te["V_FA_exceedance_at_T_E"], "FA_star": te["FA_star"], "n_null": te["n_null"]},
           "D_E1_residual": {"rows": len(e1_all), "detected": int(sum(det_r.values())), "D": D_e1, "CI": ci_d, "G_pp": g, "G_CI_pp": g_ci}, "D_P_on_O": {"rows": len(pi), "D": D_p, "CI": ci_p}}
    # descriptives
    desc = {"D_E1_on_O": rate([det_o[i] for i in e1_all]), "D_E1_hashed_or_unencodable_rows": sum(1 for i in e1_all if E1[i]["hashed"] or E1[i]["tones"] is None), "D_P_on_residual": rate(pdet_r)}
    band = lambda s: "A" if s >= 0 else "B" if s >= -10 else "C" if s >= -15 else "D"
    for name, key in (("by_band", lambda r: band(r["snr"])), ("by_prior_age_s", lambda r: r["lag_s"]), ("by_kind", lambda r: r["kind"]), ("by_prior_batch", lambda r: "batch1" if r["prior_batch"] == 1 else "later"),
                      ("by_buried", lambda r: "buried" if r["buried"] else "isolated")):
        groups = {}
        for i in e1_all:
            groups.setdefault(key(E1[i]), []).append(det_r[i])
        desc["E1_" + name] = {str(k): {"n": len(v), "D": rate(v)} for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}
    pb = {}
    for k, i in enumerate(pi):
        pb.setdefault(P[i]["batch"], []).append(pdet_r[k])
    desc["P_on_residual_by_matched_batch"] = {str(b): {"n": len(v), "D": rate(v)} for b, v in sorted(pb.items())}
    desc["P_on_O_by_matched_batch"] = {str(b): {"n": len(v), "D": rate(v)} for b, v in sorted({b: [pdet_o[k] for k, i in enumerate(pi) if P[i]["batch"] == b] for b in set(P[i]["batch"] for i in pi)}.items())}
    desc["tone_share_baseline_E1_resid_ge_0.276"] = rate([r["base"] >= 0.276 for r in own["E1_resid"]])
    desc["tone_share_baseline_P_O_ge_0.276"] = rate([r["base"] >= 0.276 for r in own["P_O"]])
    desc["E1_S_pctl_5_25_50_75_95_resid"] = [float(x) for x in np.percentile([r["S"] for r in own["E1_resid"]], [5, 25, 50, 75, 95])]
    desc["E1_argmax_truth_ok_share_resid"] = rate([r["truth"] for r in own["E1_resid"]])
    desc["null_S_quantiles_50_90_99_99.9_max"] = te["null_S_quantiles_50_90_99_99.9_max"]
    json.dump({"result": res, "descriptives": desc}, open(OUT + "/xt_result.json", "w"), indent=1)
    print(json.dumps({"result": res, "descriptives": desc}, indent=1))


if __name__ == "__main__":
    main()
