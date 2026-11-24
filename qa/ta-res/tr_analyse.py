#!/usr/bin/env python3
"""TA-RES analysis (spec cae3015c + A1 ef0b6e51).  Reads prep.json, frozen\\tr_rows.json, frozen\\tr.json (T_R), own.json and TA-MASK's own.json (the unmasked PR_U on the same rows); numbers only.
    python tr_analyse.py      (run ONCE per frozen scoring)"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "ta-mask")):
    sys.path.insert(0, p)
import tr_lib as L          # noqa: E402
import tm_lib as M          # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/ta-res"
TCOUT = "D:/Projects/claude/_qa-scratch/ta-check"
TMOUT = "D:/Projects/claude/_qa-scratch/ta-mask"


def rate(xs):
    return (sum(xs) / len(xs)) if xs else None


def main():
    grp = json.load(open(TCOUT + "/frozen/tc_groups.json"))
    G = {(r["stamp"], r["idx"]): r for r in grp["rows"]}
    stamps = grp["stamps"]
    cix = {s: i for i, s in enumerate(stamps)}
    idx = M.boot_idx(len(stamps), seed=L.SEED)
    prep = json.load(open(OUT + "/prep.json"))
    rows = {(r["stamp"], r["idx"]): r for r in json.load(open(OUT + "/frozen/tr_rows.json"))["rows"]}
    t_r = json.load(open(OUT + "/frozen/tr.json"))["T_R"]
    ownf = json.load(open(OUT + "/own.json"))
    own = ownf["rows"]
    tmo = json.load(open(TMOUT + "/own.json"))["rows"]
    tm_t = json.load(open(TMOUT + "/frozen/tm.json"))["T_M"]
    R = []
    for kk, o in own.items():
        k = (kk.split(":")[0], int(kk.split(":")[1]))
        g = G[k]
        u = tmo.get(kk)
        R.append({"k": k, "stamp": k[0], "band": g["band"], "g": g, "src": o["source"], "o": o, "pr": o["own"] >= t_r, "pu": (u["own_unmasked"] >= L.T_UNMASKED) if u else None,
                  "pm": (M.present(u["own"][0], u["own"][1], tm_t) if u else None), "u": u, "rec": rows[k]})
    sel = {"B1": lambda r: r["g"]["in_B1"], "B1m": lambda r: r["g"]["in_B1m"], "T": lambda r: r["g"]["in_T"], "T_bur": lambda r: r["g"]["in_Tbur"], "T_iso": lambda r: r["g"]["in_T"] and not r["g"]["bur"]}
    res = {}
    for name, f in sel.items():
        rs = [r for r in R if f(r)]
        tl = M.tally([(r["stamp"], r["band"], r["pr"]) for r in rs], len(stamps), cix)
        res[name] = {"rows": len(rs), "PR_R": float(tl[1].sum() / tl[0].sum()), "CI": M.ci(M.rate(tl, idx)), "PR_U": rate([r["pu"] for r in rs if r["pu"] is not None]), "PR_M": rate([r["pm"] for r in rs if r["pm"] is not None]),
                     "by_source_PR_R": {s: {"n": sum(1 for r in rs if r["src"] == s), "PR_R": rate([r["pr"] for r in rs if r["src"] == s])} for s in ("O", "R2", "R3", "X3")},
                     "by_band_PR_R": {b: rate([r["pr"] for r in rs if r["band"] == b]) for b in "ABCD"}}
    # A-GHOST: neighbour copies, R on the row's source buffer vs the unmasked instrument on O (TA-MASK's own.json ghost1_unmasked), paired by row
    gr = [r for r in R if r["g"]["in_Tbur"] and "ghost1" in r["o"] and r["u"] is not None and "ghost1_unmasked" in r["u"]]
    gm = [(r["stamp"], r["band"], r["o"]["ghost1"] >= t_r) for r in gr]
    gu = [(r["stamp"], r["band"], r["u"]["ghost1_unmasked"] >= L.T_UNMASKED) for r in gr]
    diff = M.paired_diff(gm, gu, len(stamps), cix, idx)
    strat = [r for r in gr if r["g"]["nbr"][0] >= 20]
    res["ghost"] = {"rows": len(gr), "PR_R_ghost": rate([x[2] for x in gm]), "PR_U_ghost": rate([x[2] for x in gu]), "diff": {"point": rate([a[2] - b[2] for a, b in zip(gm, gu)]), "CI": M.ci(diff)},
                    "dSNR_ge_20": {"rows": len(strat), "PR_R_ghost": rate([r["o"]["ghost1"] >= t_r for r in strat]), "PR_U_ghost": rate([r["u"]["ghost1_unmasked"] >= L.T_UNMASKED for r in strat])}}
    # A-RESIDUE
    rr = [r for r in R if r["g"]["in_Tbur"] and "residue" in r["o"]]
    tl = M.tally([(r["stamp"], r["band"], r["o"]["residue"] >= t_r) for r in rr], len(stamps), cix) if rr else None
    st20 = [r for r in rr if r["g"]["nbr"][0] >= 20]
    res["residue"] = {"rows_eligible": len(rr), "PR_R_residue": rate([r["o"]["residue"] >= t_r for r in rr]), "CI": (M.ci(M.rate(tl, idx)) if tl else None),
                      "dSNR_ge_20": {"rows": len(st20), "PR_R_residue": rate([r["o"]["residue"] >= t_r for r in st20])},
                      "by_source": {s: {"n": sum(1 for r in rr if r["src"] == s), "PR": rate([r["o"]["residue"] >= t_r for r in rr if r["src"] == s])} for s in ("R2", "R3", "X3")}}
    tb = [r for r in R if r["g"]["in_Tbur"]]
    desc = {"T_bur_neighbour_subtracted_before_source": rate([bool(r["rec"].get("nbr_subtracted_before")) for r in tb]), "T_bur_source_mix": {s: sum(1 for r in tb if r["src"] == s) for s in ("O", "R2", "R3", "X3")}}
    for nm, k_ in (("nbr_dsnr", 0), ("nbr_abs_df", 1)):
        q = np.percentile([r["g"]["nbr"][k_] for r in tb], [25, 50, 75])
        lab = lambda r, q=q, k_=k_: int(np.searchsorted(q, r["g"]["nbr"][k_], side="right"))
        desc[nm + "_quartile"] = {"cuts": [float(x) for x in q], "q": {str(i): {"n": sum(1 for r in tb if lab(r) == i), "PR_R": rate([r["pr"] for r in tb if lab(r) == i]), "PR_U": rate([r["pu"] for r in tb if lab(r) == i]),
                                                                                  "PR_M": rate([r["pm"] for r in tb if lab(r) == i])} for i in range(4)}}
    oursf = json.load(open(OUT + "/ours.json"))["rows"] if os.path.isfile(OUT + "/ours.json") else {}
    ours = [r for r in R if f"{r['k'][0]}:{r['k'][1]}" in oursf]
    desc["our_position_descriptive"] = {"rows": len(ours), "PR_R_at_WSJTX_position": rate([r["pr"] for r in ours]), "PR_R_at_our_position": rate([oursf[f"{r['k'][0]}:{r['k'][1]}"] >= t_r for r in ours]),
                                        "both_present_share": rate([r["pr"] and oursf[f"{r['k'][0]}:{r['k'][1]}"] >= t_r for r in ours]), "our_dt_minus_wsjtx_dt_converted_by_0.6_s": True,
                                        "our_f_minus_wsjtx_f_Hz_pctl_5_50_95": [float(x) for x in np.percentile([r["rec"]["our_f"] - r["g"]["freq"] for r in ours], [5, 50, 95])] if ours else None}
    rin = {"v_repro_ok": prep["V_REPRO"]["PASS"], "n_Tbur": res["T_bur"]["rows"], "ci_B1": res["B1"]["CI"], "ci_B1m": res["B1m"]["CI"], "ci_Tiso": res["T_iso"]["CI"], "ci_Tbur": res["T_bur"]["CI"],
           "ci_ghost_diff": res["ghost"]["diff"]["CI"], "n_resid": res["residue"]["rows_eligible"], "ci_resid": res["residue"]["CI"]}
    out = {"verdict": L.decide(rin), "rule_inputs": rin, "T_R": t_r, "prep": {k: prep[k] for k in ("V_REPRO", "V_PROV", "multi_source_counts_all_batch4_rows", "excluded", "included_rows")},
           "V_O": ownf["V_O"], "results": res, "descriptives": desc}
    json.dump(out, open(OUT + "/tr_result.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
