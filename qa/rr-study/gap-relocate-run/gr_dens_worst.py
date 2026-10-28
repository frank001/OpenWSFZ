#!/usr/bin/env python3
"""GAP-RELOCATE DENS worst case (Architect ruling 7aaa7e33): U rows (the 164 unencodable misses) in q1 counted as N and as W, in q5 as neither,
q2-q4 as measured. Same standardisation, bootstrap and seed as gr_item2.py (the RNG is advanced identically so the as-measured result is
reproduced first as a check). Data on file only; no run. Output: counts and CIs."""
import json
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gr_item2 as I2

B, SEED = I2.B, I2.SEED
BANDS = I2.BANDS


def main():
    pop = json.load(open(C.S + "\\population.json"))
    rows, stamps = pop["rows"], pop["stamps"]
    recs = {}
    for fn in ("forced_pilot.jsonl", "forced_main.jsonl"):
        for line in open(C.S + "\\" + fn, encoding="utf-8"):
            r = json.loads(line)
            recs[(r["stamp"], r["idx"])] = r
    ref = C.load_ref(set(stamps))
    ncyc = len(stamps)
    cyc = {s: i for i, s in enumerate(stamps)}
    refc = np.array([len(ref[s]) for s in stamps], dtype=float)
    M = [r for r in rows if not r["matched"]]
    cls = {(r["stamp"], r["idx"]): I2.classify(r, recs.get((r["stamp"], r["idx"]))) for r in M}
    order = sorted(range(ncyc), key=lambda i: (refc[i], i))
    groups = [order[i * 80:(i + 1) * 80] for i in range(5)]
    gid = {}
    for qi, g in enumerate(groups):
        for i in g:
            gid[i] = qi
    # U per group
    u_per = [0] * 5
    for r in M:
        if cls[(r["stamp"], r["idx"])] == "XU":
            u_per[gid[cyc[r["stamp"]]]] += 1
    print("U rows per group q1..q5:", u_per, "total", sum(u_per))

    band_w = {b: sum(1 for r in rows if r["band"] == b) for b in BANDS}
    keep = BANDS            # no band was marked "not established" (report section 1)
    wsum = sum(band_w[b] for b in keep)
    wts = {b: band_w[b] / wsum for b in keep}
    zero = {(i, b): 0 for i in range(ncyc) for b in BANDS}

    def cells(worst):
        cR, cN, cW = dict(zero), dict(zero), dict(zero)
        for r in rows:
            cR[(cyc[r["stamp"]], r["band"])] += 1
        for r in M:
            i = cyc[r["stamp"]]
            k = cls[(r["stamp"], r["idx"])]
            rec = recs.get((r["stamp"], r["idx"]))
            if k == "N":
                cN[(i, r["band"])] += 1
            if k == "XU":
                if worst and gid[i] == 0:
                    cN[(i, r["band"])] += 1
                    cW[(i, r["band"])] += 1
                continue
            if rec is not None and k != "P" and I2.wrong_any(rec):
                cW[(i, r["band"])] += 1
        return cR, cN, cW

    def std_rate(cyc_list, cR, cX):
        R = {b: sum(cR[(i, b)] for i in cyc_list) for b in BANDS}
        X = {b: sum(cX[(i, b)] for i in cyc_list) for b in BANDS}
        for b in ("D", "C", "B"):
            if R[b] < 30:
                nb = BANDS[BANDS.index(b) - 1]
                R[nb] += R[b]; X[nb] += X[b]; R[b] = 0; X[b] = 0
        tot = wsm = 0.0
        for b in keep:
            if R[b] > 0:
                tot += wts[b] * X[b] / R[b]; wsm += wts[b]
        return tot / wsm if wsm else float("nan")

    out = {"U_per_group_q1_to_q5": u_per}
    for label, worst in (("as_measured", False), ("worst_case", True)):
        cR, cN, cW = cells(worst)
        rng = np.random.default_rng(SEED)
        rng.integers(0, ncyc, size=(B, ncyc))       # the class-CI draw gr_item2 makes first: keeps the stream identical
        res = {}
        for name, cX in (("N", cN), ("W", cW)):
            pt = [std_rate(g, cR, cX) for g in groups]
            ds = []
            for _ in range(B):
                q1 = rng.choice(groups[0], size=80, replace=True)
                q5 = rng.choice(groups[4], size=80, replace=True)
                ds.append(std_rate(list(q5), cR, cX) - std_rate(list(q1), cR, cX))
            res[name] = {"std_rate": pt, "d": pt[4] - pt[0], "CI": [float(np.nanpercentile(ds, 2.5)), float(np.nanpercentile(ds, 97.5))]}
        res["verdict"] = "DENS-YES" if res["N"]["CI"][0] > 0 and res["W"]["CI"][0] > 0 else "DENS-NO" if res["N"]["CI"][1] <= 0 else "OPEN"
        out[label] = res
    json.dump(out, open(C.S + "\\dens_worst.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
