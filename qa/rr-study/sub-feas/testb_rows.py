#!/usr/bin/env python
"""SUB-FEAS Test B: aggregate the per-cycle COUNT files into the corroboration report. Counts and stamps only (HK-037).

Input: artefacts/sub_feas_testb/testb_<run>.csv with rows run,stamp,kind,band,n,corroborated (kind b1 = pass-0 control, b2 = residual
decodes, ws = WSJT-X decodes in the cycle). Output: rows.json with, per run and pooled, per SNR band and overall:
n, corroborated, rate, and a cluster-bootstrap 95 % interval (blocks = maximal runs of stamps exactly 15 s apart within a run;
busy cycles cluster, so the effective N is the block count, not the cycle count; 4000 resamples, fixed seed 20260930).

Pre-registered reading (fixed before any result): the b1 rate is the CONTROL (how often WSJT-X also decodes what pass-0 decodes).
The b2 rate is the question. "Not corroborated" = 1 - rate is an UPPER BOUND on false positives (WSJT-X can miss a real weak signal,
and text equality counts a differently rendered hashed callsign as a miss). No decode-rate claim; not the base change's 8.2.
"""
import collections
import csv
import datetime
import json
import os
import random
import sys

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "artefacts")
OUT = os.path.join(os.path.abspath(ART), "sub_feas_testb")
RUNS = ["20260922_2056", "20260923_1730", "20260925_2010"]
BANDS = ["A", "B", "C", "D"]
SEED = 20260930
BOOT = 4000


def t(stamp):
    return datetime.datetime.strptime(stamp, "%y%m%d_%H%M%S")


def blocks_of(stamps):
    bl, cur, prev = [], [], None
    for s in sorted(stamps):
        if prev is not None and (t(s) - t(prev)).total_seconds() != 15:
            bl.append(cur)
            cur = []
        cur.append(s)
        prev = s
    if cur:
        bl.append(cur)
    return bl


def main():
    per = {}            # (run, stamp) -> {(kind, band): (n, c)}
    for run in RUNS:
        p = os.path.join(OUT, f"testb_{run}.csv")
        for r in csv.DictReader(open(p, newline="")):
            per.setdefault((run, r["stamp"]), {})[(r["kind"], r["band"])] = (int(r["n"]), int(r["corroborated"]))
    res = {"cycles": len(per), "seed": SEED, "bootstrap": BOOT}

    def agg(keys, kind, band):
        n = c = 0
        for k in keys:
            v = per[k].get((kind, band))
            if v:
                n += v[0]
                c += v[1]
        return n, c

    def rate_ci(runs, kind, band):
        keys_by_block = []
        for run in runs:
            stamps = [s for (r, s) in per if r == run]
            for b in blocks_of(stamps):
                keys_by_block.append([(run, s) for s in b])
        tot_n = tot_c = 0
        bn = []
        for b in keys_by_block:
            n, c = agg(b, kind, band)
            bn.append((n, c))
            tot_n += n
            tot_c += c
        rng = random.Random(SEED)
        rates = []
        for _ in range(BOOT):
            n = c = 0
            for _i in range(len(bn)):
                x = bn[rng.randrange(len(bn))]
                n += x[0]
                c += x[1]
            if n:
                rates.append(c / n)
        rates.sort()
        lo = rates[int(0.025 * len(rates))] if rates else None
        hi = rates[int(0.975 * len(rates)) - 1] if rates else None
        return {"n": tot_n, "corroborated": tot_c, "rate": (tot_c / tot_n) if tot_n else None,
                "not_corroborated_share": (1 - tot_c / tot_n) if tot_n else None, "ci95_blocks": [lo, hi], "blocks": len(bn)}

    for label, runs in [(r, [r]) for r in RUNS] + [("ALL", RUNS)]:
        res[label] = {}
        for kind in ("b1", "b2"):
            res[label][kind] = {"ALL": None, **{b: None for b in BANDS}}
            # ALL = sum over bands
            n = c = 0
            for run in runs:
                ks = [k for k in per if k[0] == run]
                for b in BANDS:
                    a, cc = agg(ks, kind, b)
                    n += a
                    c += cc
            res[label][kind]["ALL"] = {"n": n, "corroborated": c, "rate": (c / n) if n else None,
                                       "not_corroborated_share": (1 - c / n) if n else None}
            for b in BANDS:
                res[label][kind][b] = rate_ci(runs, kind, b)
        wsn = sum(per[k].get(("ws", "ALL"), (0, 0))[0] for k in per if k[0] in runs)
        res[label]["wsjtx_decodes_in_these_cycles"] = wsn
    json.dump(res, open(os.path.join(OUT, "rows.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
