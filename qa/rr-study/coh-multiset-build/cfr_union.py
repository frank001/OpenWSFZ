#!/usr/bin/env python3
"""COH-FB-RESIDUAL probe, Architect asks 2 and 3 (2026-10-27): REF-only / RES-only / both batch-4 decodes, and the UNION. COUNTS ONLY (HK-037).

  python cfr_union.py <raw dir with ref/ res/> <scratch dir with ref/nc_dump.tsv res/nc_dump.tsv> <out json> <label>

The message text of the nc_dump (scratch only: --nc-dump) is read INSIDE load() to build per-cycle sets of distinct payloads; only counts leave it.
nc_dump columns: stamp,kind(batch 1-4),matched(0/1: corroborated by WSJT-X),freq,dt,snr,same_any,min_df,wcount,path,text.
Bands of the OpenWSFZ decode SNR (Replay81): A snr >= 0, B >= -10, C >= -15, D below.
Checks asserted: (i) per arm, sum over cycles of (matched decodes, all batches) equals testb's corroborated total (the NET numerator), (ii) RES-only minus REF-only confirmed = sum dM.
NET of the union: M_union = M_ref + confirmed(RES-only), per cycle (REF-only decodes are already in M_ref); same bootstrap as cfr_desc.py.
"""
import collections
import csv
import json
import sys

import mb_analysis as A


def band(snr):
    return "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"


def load(path):
    """-> (b4: {stamp: {text: (matched, snr)}}, anyb: {stamp: set(text)}, matched_total: {stamp: int})"""
    b4 = collections.defaultdict(dict)
    anyb = collections.defaultdict(set)
    mt = collections.Counter()
    with open(path, newline="", encoding="utf-8") as f:
        for ln in f:
            p = ln.rstrip("\n").split("\t")
            if len(p) < 11:
                continue
            s, k, m, snr, text = p[0], int(p[1]), int(p[2]), int(float(p[5])), p[10]
            anyb[s].add(text)
            mt[s] += m
            if k == 4:
                b4[s][text] = (m, snr)
    return b4, anyb, mt


def tally(items):
    t = {"n": 0, "confirmed": 0, "not_confirmed": 0, "by_band": {b: {"n": 0, "confirmed": 0, "not_confirmed": 0} for b in "ABCD"}}
    for m, snr in items:
        t["n"] += 1
        t["confirmed" if m else "not_confirmed"] += 1
        bb = t["by_band"][band(snr)]
        bb["n"] += 1
        bb["confirmed" if m else "not_confirmed"] += 1
    return t


def main(raw, scr, out, label):
    R = {a: A.load_arm(raw, a) for a in ("ref", "res")}
    stamps = sorted(R["ref"]["run"])
    ws = R["ref"]["tb"][0]
    cyc = [s for s in stamps if ws.get(s, (0, 0))[0] > 0]
    W = {s: ws[s][0] for s in cyc}
    L = {a: load(f"{scr}/{a}/nc_dump.tsv") for a in ("ref", "res")}
    M = {a: {s: R[a]["tb"][0][s][1] for s in cyc} for a in ("ref", "res")}
    for a in L:                                            # check (i)
        got = sum(L[a][2][s] for s in cyc)
        assert got == sum(M[a].values()), (a, got, sum(M[a].values()))
    only_ref, only_res, both_ref, both_res = [], [], [], []
    res_only_in_ref_anybatch = 0
    ref_only_in_res_anybatch = 0
    per = {}
    for s in stamps:
        r4, s4 = L["ref"][0].get(s, {}), L["res"][0].get(s, {})
        for t, v in r4.items():
            if t in s4:
                both_ref.append(v)
            else:
                only_ref.append(v)
                if t in L["res"][1].get(s, set()):
                    ref_only_in_res_anybatch += 1
        for t, v in s4.items():
            if t in r4:
                both_res.append(v)
            else:
                only_res.append(v)
                if t in L["ref"][1].get(s, set()):
                    res_only_in_ref_anybatch += 1
        per[s] = (sum(m for m, _ in (v for t, v in s4.items() if t not in r4)),)   # confirmed RES-only
    res = {"label": label, "cycles": len(stamps),
           "REF_only": tally(only_ref), "RES_only": tally(only_res), "both_REF_view": tally(both_ref), "both_RES_view": tally(both_res),
           "REF_only_texts_present_in_RES_in_some_batch": ref_only_in_res_anybatch, "RES_only_texts_present_in_REF_in_some_batch": res_only_in_ref_anybatch}
    dM = {s: M["res"][s] - M["ref"][s] for s in cyc}
    res["reconciliation_ii"] = {"sum_dM": sum(dM.values()), "RES_only_conf_minus_REF_only_conf": res["RES_only"]["confirmed"] - res["REF_only"]["confirmed"]}
    # union: distinct batch-4 payloads in REF or RES
    uni = [v for s in stamps for v in {**L["ref"][0].get(s, {}), **L["res"][0].get(s, {})}.values()]
    res["UNION_batch4_distinct"] = tally(uni)
    dMu = {s: per[s][0] for s in cyc}                       # confirmed RES-only per cycle on top of REF
    net_u = A.boot_ratio(dMu, W, cyc)
    net_r = A.boot_ratio(dM, W, cyc)
    res["NET_vs_REF_pp"] = {"RES": {"point": 100 * net_r[0], "lo": 100 * net_r[1], "hi": 100 * net_r[2], "sum_dM": sum(dM.values())},
                            "UNION": {"point": 100 * net_u[0], "lo": 100 * net_u[1], "hi": 100 * net_u[2], "sum_dM": sum(dMu.values())}}
    res["corroborated_pct_of_W"] = {"REF": 100 * sum(M["ref"].values()) / sum(W.values()), "RES": 100 * sum(M["res"].values()) / sum(W.values()),
                                    "UNION": 100 * (sum(M["ref"].values()) + sum(dMu.values())) / sum(W.values())}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, separators=(",", ":"), default=float))


if __name__ == "__main__":
    main(*sys.argv[1:5])
