#!/usr/bin/env python3
"""GAP-RELOCATE item 2 analysis: ROW 0c/0d, classes P/FP/FC/G/FCw/N, D1-D7, routing rows, DENS (spec 690e8cb5 + Amendments 1-2).

Classes (A1.5a, first match wins, as code): P -> FP -> FC (V3 payload, gated=1) -> G (V3 payload, gated=0) -> FCw (walk payload) -> N.
Bootstrap: resample the 400 cycles with replacement (the unit of independence), B = 2000, seed 20261028, percentile 95 % CI.
Output: counts / rates / CIs only. Message text is read in memory ONLY to key per-station clustering (counts out).
"""
from __future__ import annotations

import collections
import json
import math
import sys

import numpy as np

import gr_common as C

SEED = 20261028
B = 2000
BAR_L_PP = 0.5            # section 5: BAR_L, ratified by the Captain 2026-10-24 12:50:57Z (COH-MULTISET)
P_CTRL_BAR = 0.90
BAND_NOT_ESTABLISHED_P = 0.80   # A1.3 proposal; frozen only after the pilot's per-band figures are on file
BAND_NOT_ESTABLISHED_MIN_N = 50
T1 = 17.552446
CLASSES = ["P", "FP", "FC", "G", "FCw", "N"]
BANDS = ["A", "B", "C", "D"]
assert B == 2000 and SEED == 20261028 and BAR_L_PP == 0.5


def classify(row, rec):
    if rec is None:
        return "X?"            # not forced (should not occur)
    if rec.get("unencodable"):
        return "XU"            # excluded: cannot be compared (0d)
    if row["p_flag"]:
        return "P"
    if rec["fp"]["found"]:
        return "FP"
    if rec["fc"]["v3_match"] and rec["fc"]["gated"] == 1:
        return "FC"
    if rec["fc"]["v3_match"]:
        return "G"
    if rec["walk"]["match"]:
        return "FCw"
    return "N"


def wrong_any(rec):
    return (rec["fp"]["wrong"] > 0 and not rec["fp"]["found"]) or rec["fc"]["v3_wrong"] or rec["walk"]["wrong"]


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def station_key(text):
    t = text.split()
    if not t:
        return ""
    if t[0] == "CQ":
        return t[2] if len(t) > 3 and t[1].isalpha() and len(t[1]) <= 4 else (t[1] if len(t) > 1 else "")
    return t[1] if len(t) > 1 else t[0]


def main():
    pop = json.load(open(C.S + "\\population.json"))
    rows = pop["rows"]
    recs = {}
    for fn in ("forced_pilot.jsonl", "forced_main.jsonl"):
        try:
            for line in open(C.S + "\\" + fn, encoding="utf-8"):
                r = json.loads(line)
                recs[(r["stamp"], r["idx"])] = r
        except FileNotFoundError:
            pass
    stamps = pop["stamps"]
    n_ref = pop["n_ref"]
    ref = C.load_ref(set(stamps))
    out = {"n_ref": n_ref, "n_miss": pop["n_miss"], "n_hits": pop["n_hits"], "K_n": pop["K_n"], "K_orig_path": pop["K_orig_path"],
           "K_extended_by": pop["K_extended_by"]}
    cyc_idx = {s: i for i, s in enumerate(stamps)}

    # ---- ROW 0c: P_ctrl on original-path K rows of the cycles after the pilot ---------------------------------------------
    def kstats(sel):
        n = u = p = c = cs = 0
        for r in sel:
            rec = recs.get((r["stamp"], r["idx"]))
            if rec is None or rec.get("unencodable"):
                continue
            n += 1
            fp = rec["fp"]["found"]
            fc = rec["fc"]["v3_match"] or rec["walk"]["match"]
            p += fp
            c += fc
            cs += (rec["fc"]["v3_match"] and rec["fc"]["gated"] == 1)
            u += (fp or fc)
        return {"n": n, "P_ctrl_union": u / n if n else None, "P_ctrl_p": p / n if n else None, "P_ctrl_c_any_gate": c / n if n else None,
                "P_ctrl_c_v3_gated_only": cs / n if n else None}
    K = [r for r in rows if r["K"]]
    Kmain_orig = [r for r in K if not r["pilot"] and r["tag"] != "fb_res"]
    Kpilot_orig = [r for r in K if r["pilot"] and r["tag"] != "fb_res"]
    Kres = [r for r in K if r["tag"] == "fb_res"]
    out["row0c"] = {"main_original_path": kstats(Kmain_orig), "pilot_original_path": kstats(Kpilot_orig), "P_ctrl_res_all_K": kstats(Kres),
                    "by_band_main_original_path": {b: kstats([r for r in Kmain_orig if r["band"] == b]) for b in BANDS},
                    "bar": P_CTRL_BAR}
    out["row0c"]["PASS"] = (out["row0c"]["main_original_path"]["P_ctrl_union"] or 0) >= P_CTRL_BAR
    not_est = [b for b in BANDS if out["row0c"]["by_band_main_original_path"][b]["n"] >= BAND_NOT_ESTABLISHED_MIN_N
               and out["row0c"]["by_band_main_original_path"][b]["P_ctrl_union"] < BAND_NOT_ESTABLISHED_P]
    out["bands_not_established_A1_3"] = not_est

    # ---- M classes ---------------------------------------------------------------------------------------------------------
    M = [r for r in rows if not r["matched"]]
    cls = {}
    for r in M:
        cls[(r["stamp"], r["idx"])] = classify(r, recs.get((r["stamp"], r["idx"])))
    cnt = collections.Counter(cls.values())
    out["M_total"] = len(M)
    out["D1_counts"] = dict(cnt)
    out["D1_pp_of_n_ref"] = {k: pct(v, n_ref) for k, v in cnt.items()}
    out["row0d"] = {"M_excluded_unencodable": cnt.get("XU", 0), "M_not_forced": cnt.get("X?", 0),
                    "share_of_M": pct(cnt.get("XU", 0) + cnt.get("X?", 0), len(M)), "PASS": (cnt.get("XU", 0) + cnt.get("X?", 0)) <= 0.01 * len(M)}
    # D2 / D3 / D4 / D5 / D7
    fpc = collections.Counter(recs[(r["stamp"], r["idx"])]["fp"]["cell"] for r in M if cls[(r["stamp"], r["idx"])] == "FP")
    out["D2_FP_cell"] = dict(fpc)
    out["D3_by_band"] = {c: {b: sum(1 for r in M if cls[(r["stamp"], r["idx"])] == c and r["band"] == b) for b in BANDS} for c in CLASSES}
    # D4 load quintile: quintiles of REF rows per cycle over the 400 cycles
    loads = np.array([len(ref[s]) for s in stamps])
    qedges = np.percentile(loads, [20, 40, 60, 80])
    def quint(n): return int(np.searchsorted(qedges, n, side="right")) + 1
    out["D4_by_load_quintile"] = {c: {q: sum(1 for r in M if cls[(r["stamp"], r["idx"])] == c and quint(r["n_cycle_ref"]) == q) for q in range(1, 6)} for c in CLASSES}
    out["D4_quintile_edges"] = [float(x) for x in qedges]
    fw = collections.Counter()
    for r in M:
        rec = recs.get((r["stamp"], r["idx"]))
        if rec is None or rec.get("unencodable") or cls[(r["stamp"], r["idx"])] == "P":
            continue
        k = cls[(r["stamp"], r["idx"])]
        if rec["fp"]["wrong"] > 0 and not rec["fp"]["found"]:
            fw[(k, "FP_wrong")] += 1
        if rec["fc"]["v3_wrong"]:
            fw[(k, "V3_wrong")] += 1
        if rec["walk"]["wrong"]:
            fw[(k, "walk_wrong")] += 1
    out["D5_F_wrong"] = {f"{k[0]}|{k[1]}": v for k, v in fw.items()}
    g = [recs[(r["stamp"], r["idx"])]["fc"] for r in M if cls[(r["stamp"], r["idx"])] == "G"]
    f1b = [x["f1b_db"] for x in g if x["f1b_db"] is not None]
    out["D7_G"] = {"n": len(g), "n_no_usable_reference": sum(1 for x in g if x.get("f1b_inf")),
                   "within_1dB_above_T1": sum(1 for v in f1b if T1 < v <= T1 + 1.0),
                   "median_f1b": float(np.median(f1b)) if f1b else None}

    # ---- bootstrap by cycle ------------------------------------------------------------------------------------------------
    rng = np.random.default_rng(SEED)
    ncyc = len(stamps)
    per = {c: np.zeros(ncyc) for c in CLASSES + ["XU"]}
    refc = np.array([len(ref[s]) for s in stamps], dtype=float)
    for r in M:
        k = cls[(r["stamp"], r["idx"])]
        if k in per:
            per[k][cyc_idx[r["stamp"]]] += 1
    idx = rng.integers(0, ncyc, size=(B, ncyc))
    den = refc[idx].sum(axis=1)
    ci = {}
    for c in CLASSES:
        v = 100.0 * per[c][idx].sum(axis=1) / den
        ci[c] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    others = {c: 100.0 * per[c].sum() / refc.sum() for c in CLASSES}
    out["CI_pp"] = ci
    out["point_pp"] = others
    # per-station clustering next to each class
    stn = {}
    for c in CLASSES:
        keys = collections.Counter(station_key(ref[r["stamp"]][r["idx"]][3]) for r in M if cls[(r["stamp"], r["idx"])] == c)
        tot = sum(keys.values())
        stn[c] = {"rows": tot, "distinct_senders": len(keys), "top_sender_share": (max(keys.values()) / tot) if tot else None,
                  "top5_share": (sum(v for _, v in keys.most_common(5)) / tot) if tot else None}
    out["per_station_clustering"] = stn
    # routing rows
    other_sum = lambda ex: sum(others[c] for c in CLASSES if c != ex)
    route = {"R-P": ci["P"][0] >= BAR_L_PP, "R-FP": ci["FP"][0] >= BAR_L_PP, "R-FC": ci["FC"][0] >= BAR_L_PP, "R-G": ci["G"][0] >= BAR_L_PP,
             "R-FCw": ci["FCw"][0] >= BAR_L_PP,
             "R-N": ci["N"][0] >= sum(others[c] for c in ("P", "FP", "FC", "FCw", "G"))}
    route["R-0"] = not any(route.values())
    out["routing"] = route

    # ---- DENS (spec section 10): q1..q5 = 80-cycle groups sorted by n_ref (ties by cycle index) --------------------------------
    order = sorted(range(ncyc), key=lambda i: (refc[i], i))
    groups = [order[i * 80:(i + 1) * 80] for i in range(5)]
    band_w = {b: sum(1 for r in rows if r["band"] == b) for b in BANDS}
    cellN = {(i, b): 0 for i in range(ncyc) for b in BANDS}
    cellW = dict(cellN)
    cellR = dict(cellN)
    for r in rows:
        i = cyc_idx[r["stamp"]]
        cellR[(i, r["band"])] += 1
    for r in M:
        i = cyc_idx[r["stamp"]]
        k = cls[(r["stamp"], r["idx"])]
        if k == "N":
            cellN[(i, r["band"])] += 1
        rec = recs.get((r["stamp"], r["idx"]))
        if rec is not None and not rec.get("unencodable") and k != "P" and wrong_any(rec):
            cellW[(i, r["band"])] += 1
    keep = [b for b in BANDS if b not in not_est]
    wsum = sum(band_w[b] for b in keep)
    wts = {b: band_w[b] / wsum for b in keep}

    def std_rate(cyc_list, cell):
        # pooled counts per band over the group's cycles; a band cell with n_ref < 30 is pooled toward A (D->C->B->A)
        R = {b: sum(cellR[(i, b)] for i in cyc_list) for b in BANDS}
        X = {b: sum(cell[(i, b)] for i in cyc_list) for b in BANDS}
        for b in ("D", "C", "B"):
            if R[b] < 30:
                nb = BANDS[BANDS.index(b) - 1]
                R[nb] += R[b]; X[nb] += X[b]; R[b] = 0; X[b] = 0
        tot = 0.0; wsm = 0.0
        for b in keep:
            if R[b] > 0:
                tot += wts[b] * X[b] / R[b]; wsm += wts[b]
        return tot / wsm if wsm else float("nan")
    dens = {}
    for name, cell in (("N", cellN), ("W", cellW)):
        pt = [std_rate(g_, cell) for g_ in groups]
        d_obs = pt[4] - pt[0]
        ds = []
        for _ in range(B):
            q1 = rng.choice(groups[0], size=80, replace=True)
            q5 = rng.choice(groups[4], size=80, replace=True)
            ds.append(std_rate(list(q5), cell) - std_rate(list(q1), cell))
        dens[name] = {"std_rate_q1_to_q5": pt, "d_q5_minus_q1": d_obs, "CI": [float(np.nanpercentile(ds, 2.5)), float(np.nanpercentile(ds, 97.5))]}
    yes = dens["N"]["CI"][0] > 0 and dens["W"]["CI"][0] > 0
    no = dens["N"]["CI"][1] <= 0
    dens["verdict"] = "DENS-YES" if yes else "DENS-NO" if no else "OPEN"
    # P_ctrl,res q1 vs q5 (K rows tagged fb_res, by their cycle's group)
    gid = {}
    for qi, g_ in enumerate(groups):
        for i in g_:
            gid[stamps[i]] = qi + 1
    def pres(q):
        sel = [r for r in Kres if gid[r["stamp"]] == q]
        k = kstats(sel)
        return {"n": k["n"], "P_ctrl_union": k["P_ctrl_union"]}
    dens["P_ctrl_res_q1"] = pres(1)
    dens["P_ctrl_res_q5"] = pres(5)
    dens["bands_dropped"] = not_est
    out["DENS"] = dens
    json.dump(out, open(C.S + "\\item2.json", "w"), indent=1, sort_keys=True, default=str)
    print(json.dumps(out, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    sys.exit(main())
