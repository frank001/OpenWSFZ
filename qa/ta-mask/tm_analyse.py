#!/usr/bin/env python3
"""TA-MASK analysis (spec 104f197f + A1 0777c9b9 + A2 §10).  Reads frozen groups, tm.json (T_M), the pilot exclusion list and own.json; writes numbers only.   python tm_analyse.py   (run ONCE per frozen scoring)"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TC = os.path.join(HERE, "..", "ta-check")
for p in (HERE, TC):
    sys.path.insert(0, p)
import tm_lib as M          # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/ta-mask"
TCOUT = "D:/Projects/claude/_qa-scratch/ta-check"
T_UNMASKED = 0.276


def main():
    grp = json.load(open(TCOUT + "/frozen/tc_groups.json"))
    tm = json.load(open(OUT + "/frozen/tm.json"))
    own = json.load(open(OUT + "/own.json"))["rows"]
    pil = json.load(open(OUT + "/frozen/tm_pilot_rows.json"))
    pilset = {tuple(k) for k in pil["T_bur"]} | {tuple(k) for k in pil["B1m"]}
    t_m = tm["T_M"]
    stamps = grp["stamps"]
    cix = {s: i for i, s in enumerate(stamps)}
    idx = M.boot_idx(len(stamps))
    rows = [r for r in grp["rows"] if (r["stamp"], r["idx"]) not in pilset and f"{r['stamp']}:{r['idx']}" in own]
    for r in rows:
        r["o"] = own[f"{r['stamp']}:{r['idx']}"]
        S, n = r["o"]["own"]
        r["pm"] = M.present(S, n, t_m)
        r["pu"] = bool(r["o"]["own_unmasked"] >= T_UNMASKED)
        r["n_s"] = n
    sel = {"B1": lambda r: r["in_B1"], "B1m": lambda r: r["in_B1m"], "T": lambda r: r["in_T"], "T_bur": lambda r: r["in_Tbur"], "T_iso": lambda r: r["in_T"] and not r["bur"]}
    res = {}
    for name, f in sel.items():
        rs = [r for r in rows if f(r)]
        tl = M.tally([(r["stamp"], r["band"], r["pm"]) for r in rs], len(stamps), cix)
        p = M.rate(tl, idx)
        tu = M.tally([(r["stamp"], r["band"], r["pu"]) for r in rs], len(stamps), cix)
        res[name] = {"rows": len(rs), "PR_M": float(tl[1].sum() / tl[0].sum()), "CI_M": M.ci(p), "PR_unmasked_TA_CHECK_rule": float(tu[1].sum() / tu[0].sum()),
                     "unscorable": int(sum(1 for r in rs if r["n_s"] < M.MIN_SCORABLE)), "n_s_pctl_0_25_50_75_100": [float(x) for x in np.percentile([r["n_s"] for r in rs], [0, 25, 50, 75, 100])],
                     "masked_bins_per_symbol_mean": float(np.mean([r["o"]["stats"]["masked_bins_per_symbol"] for r in rs])),
                     "by_band_PR_M": {b: (lambda xs: (sum(xs) / len(xs)) if xs else None)([r["pm"] for r in rs if r["band"] == b]) for b in "ABCD"}}
    tb = [r for r in rows if r["in_Tbur"]]
    # ghosts (T_bur acceptance rows with a scorable ghost: strongest overlapping neighbour encodable)
    gr = [r for r in tb if "ghost1" in r["o"]]
    gm = [(r["stamp"], r["band"], M.present(r["o"]["ghost1"][0], r["o"]["ghost1"][1], t_m)) for r in gr]
    gu = [(r["stamp"], r["band"], r["o"]["ghost1_unmasked"] >= T_UNMASKED) for r in gr]
    diff = M.paired_diff(gm, gu, len(stamps), cix, idx)
    tlg, tlu = M.tally(gm, len(stamps), cix), M.tally(gu, len(stamps), cix)
    strat = [r for r in gr if r["nbr"][0] >= 20]
    g2 = [r for r in tb if "ghost2" in r["o"]]
    res["ghost"] = {"rows_scored": len(gr), "rows_neighbour_unencodable": sum(1 for r in tb if r["o"].get("ghost1_status") == "neighbour_unencodable"),
                    "PR_M_ghost": float(tlg[1].sum() / tlg[0].sum()), "PR_U_ghost": float(tlu[1].sum() / tlu[0].sum()), "diff_M_minus_U": {"point": float((tlg[1].sum() - tlu[1].sum()) / tlg[0].sum()), "CI": M.ci(diff)},
                    "dSNR_ge_20": {"rows": len(strat), "PR_M_ghost": (sum(M.present(r["o"]["ghost1"][0], r["o"]["ghost1"][1], t_m) for r in strat) / len(strat)) if strat else None,
                                   "PR_U_ghost": (sum(r["o"]["ghost1_unmasked"] >= T_UNMASKED for r in strat) / len(strat)) if strat else None},
                    "ghost1_unscorable_masked": int(sum(1 for r in gr if r["o"]["ghost1"][1] < M.MIN_SCORABLE)),
                    "second_ghost": {"rows": len(g2), "present": int(sum(M.present(r["o"]["ghost2"][0], r["o"]["ghost2"][1], t_m) for r in g2)), "unscorable": int(sum(1 for r in g2 if r["o"]["ghost2"][1] < M.MIN_SCORABLE))}}
    # descriptives: T_bur by dSNR / |df| quartile beside the unmasked rule; unencodable-neighbour split
    desc = {}
    for nm, k in (("nbr_dsnr", 0), ("nbr_abs_df", 1)):
        q = np.percentile([r["nbr"][k] for r in tb], [25, 50, 75])
        desc[nm + "_quartile"] = {"cuts": [float(x) for x in q], "q": {str(i): {"n": sum(1 for r in tb if int(np.searchsorted(q, r["nbr"][k], side="right")) == i),
                                                                                  "PR_M": (lambda xs: (sum(xs) / len(xs)) if xs else None)([r["pm"] for r in tb if int(np.searchsorted(q, r["nbr"][k], side="right")) == i]),
                                                                                  "PR_unmasked": (lambda xs: (sum(xs) / len(xs)) if xs else None)([r["pu"] for r in tb if int(np.searchsorted(q, r["nbr"][k], side="right")) == i])} for i in range(4)}}
    with_u = [r for r in tb if r["o"]["unencodable_neighbours"] > 0]
    wo_u = [r for r in tb if r["o"]["unencodable_neighbours"] == 0]
    desc["T_bur_unencodable_neighbour_split"] = {"with": {"n": len(with_u), "PR_M": (sum(r["pm"] for r in with_u) / len(with_u)) if with_u else None}, "without": {"n": len(wo_u), "PR_M": sum(r["pm"] for r in wo_u) / len(wo_u)}}
    rr = {"ci_B1": res["B1"]["CI_M"], "ci_B1m": res["B1m"]["CI_M"], "ci_Tbur": res["T_bur"]["CI_M"], "ci_ghost_diff": res["ghost"]["diff_M_minus_U"]["CI"], "n_Tbur": res["T_bur"]["rows"]}
    out = {"verdict": M.decide(rr), "rule_inputs": rr, "T_M": tm, "results": res, "descriptives": desc,
           "limits": ["not-corroborated rows are not in the test", "neighbours are WSJT-X's n_ref rows (Stage 2 masks with our own decodes)", "one night, 40 m", "unencodable neighbours stay unmasked"]}
    json.dump(out, open(OUT + "/tm_result.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
