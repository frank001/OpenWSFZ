#!/usr/bin/env python3
"""FD-PROXY pilot, N-RAND half (spec 4.2, 5, 7): synthetic noise-mode rows from the product's unpacker + plausibility filter (harness `nrand/`), each placed at the
(cycle, frequency) of a Q row drawn at random (seed 20261118) in the PILOT cycles. Q rows contribute POSITIONS ONLY: no Q text and no instrument output is read.
P (confirmed b4+5) as in fd_pilot. Output: counts and rates (no text).

  python -I fd_pilot_nrand.py <nc.tsv> <ALL.TXT> <nrand_rand.txt> <nrand_ap.txt> <out.json>
"""
from __future__ import annotations

import collections
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fd_lib as L
import fd_pilot as FP

SEED = 20261118
B_BOOT = 2000
AP_ROWS_OF_Q, Q_ROWS = 18, 1308           # (k) record: AP-tagged unconfirmed rows / unconfirmed rows of batches 4+5
N_RAND, N_AP = 2959, 41                   # 3,000 after the filter, AP share round(3000 * 18 / 1308) = 41
assert (SEED, B_BOOT, N_RAND + N_AP, N_AP) == (20261118, 2000, 3000, round(3000 * AP_ROWS_OF_Q / Q_ROWS))


def main(nc_path, all_path, rand_path, ap_path, out_path):
    t0 = time.time()
    rows = FP.load_nc(nc_path)
    E = L.Evidence(L.load_E(all_path))
    stamps = sorted({r["st"] for r in rows})
    pil = set(stamps[:FP.PILOT_CYCLES])
    qpos = [(L.cycle_of(r["st"]), r["f"]) for r in rows if r["k"] in FP.BATCHES and not r["m"] and r["st"] in pil]     # POSITIONS only
    # Q's stratum structure for the s weights (counts of band x burial, whole night; no instrument output)
    qstr = collections.Counter()
    for r in rows:
        if r["k"] in FP.BATCHES and not r["m"] and L.parse(r["tx"]) is not None:
            qstr[(L.band(r["snr"]), "buried" if E.buried(L.cycle_of(r["st"]), r["f"], r["snr"]) else "isolated")] += 1
    tot = sum(qstr.values())
    W = {k: v / tot for k, v in qstr.items()}
    # P in the pilot cycles
    P = []
    for r in rows:
        if r["k"] in FP.BATCHES and r["m"] == 1 and r["st"] in pil and L.parse(r["tx"]) is not None:
            cyc = L.cycle_of(r["st"])
            j = E.judge(cyc, r["f"], r["tx"])
            st = (L.band(r["snr"]), "buried" if E.buried(cyc, r["f"], r["snr"], text=r["tx"], confirmed=True) else "isolated")
            P.append((cyc, st, j["plausible"]))

    def s_weighted(sample):
        by = collections.defaultdict(list)
        for (_c, st, pl) in sample:
            by[st].append(pl)
        num = den = 0.0
        for st, w in W.items():
            if by.get(st):
                num += w * sum(by[st]) / len(by[st]); den += w
        return num / den if den else float("nan")

    s = s_weighted(P)

    # synthetic rows at Q positions
    rng = random.Random(SEED)
    syn = []
    for path, tag in ((rand_path, "rand"), (ap_path, "ap")):
        for ln in open(path, encoding="utf-8"):
            t = ln.rstrip("\n")
            c, f = rng.choice(qpos)
            j = E.judge(c, float(f), t)
            syn.append((tag, c, j))
    judged = [(tag, c, j) for (tag, c, j) in syn if j is not None]
    res = {"pilot_cycles": len(pil), "Q_positions_pilot": len(qpos), "P_pilot_n": len(P), "s_weighted": round(s, 4),
           "synthetic_total": len(syn), "synthetic_unjudgeable": len(syn) - len(judged)}

    def comp(items):
        n = len(items)
        if not n:
            return None
        return dict(n=n, f=round(sum(j["plausible"] for _t, _c, j in items) / n, 4), C=round(sum(j["C"] for _t, _c, j in items) / n, 4),
                    R_fail=round(sum(not j["R"] for _t, _c, j in items) / n, 4), F_fail=round(sum(j["F"] == "FAIL" for _t, _c, j in items) / n, 4),
                    F_unseen=round(sum(j["F"] == "UNSEEN" for _t, _c, j in items) / n, 4), S_behind=round(sum(j["S"] for _t, _c, j in items) / n, 4))

    res["N_RAND_mixture"] = comp(judged)                              # f_RAND: AP mixed in at its share by construction
    res["N_RAND_nonAP"] = comp([x for x in judged if x[0] == "rand"])
    res["N_RAND_AP"] = comp([x for x in judged if x[0] == "ap"])
    f = sum(j["plausible"] for _t, _c, j in judged) / len(judged)
    # cycle bootstrap of P (s), binomial f; descriptive on the pilot
    cyc_ix = collections.defaultdict(list)
    for i, (c, _st, _pl) in enumerate(P):
        cyc_ix[c].append(i)
    cycs = sorted(cyc_ix)
    brng = random.Random(SEED)
    diffs = []
    for _ in range(B_BOOT):
        pick = [brng.choice(cycs) for _ in cycs]
        sample = [P[i] for c in pick for i in cyc_ix[c]]
        fb = sum(brng.random() < f for _ in range(len(judged))) / len(judged)
        diffs.append(s_weighted(sample) - fb)
    diffs.sort()
    res["s_minus_f_RAND"] = dict(point=round(s - f, 4), ci_lo=round(diffs[int(0.025 * B_BOOT)], 4), ci_hi=round(diffs[int(0.975 * B_BOOT) - 1], 4), bar_V_SEP=0.70)
    res["run_seconds"] = round(time.time() - t0, 1)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:6])
