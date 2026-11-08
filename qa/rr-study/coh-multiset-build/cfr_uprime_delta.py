#!/usr/bin/env python3
"""COH-FB-RESIDUAL probe: paired dU' (RES - REF) per cycle with the tool's block bootstrap, plus the U' split and by-band sums. Counts only; no bar applied.

  python cfr_uprime_delta.py <u dir with uprime_ref.json.* and uprime_res.json.*> <testb.csv of REF> <out json>
"""
import collections
import json
import sys

import mb_analysis as A


def main(u, testb, out):
    ur = {a: A.load_uprime(f"{u}/uprime_{a}.json.percycle.csv") for a in ("ref", "res")}
    ws = A.load_testb(testb)[0]
    cyc = sorted(s for s in ws if ws[s][0] > 0)
    ones = {s: 1.0 for s in cyc}
    d = A.boot_ratio({s: float(ur["res"].get(s, 0) - ur["ref"].get(s, 0)) for s in cyc}, ones, cyc)
    res = {"cycles": len(cyc), "U_prime_per_cycle": {a: sum(ur[a].get(s, 0) for s in cyc) / len(cyc) for a in ur},
           "dU_prime": {"point": d[0], "lo": d[1], "hi": d[2]}}
    band = {}
    for a in ("ref", "res"):
        t = collections.defaultdict(lambda: collections.Counter())
        for r in A.rows(f"{u}/uprime_{a}.json.byband.csv"):
            for k in ("not_confirmed", "tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present"):
                t[r["band"]][k] += int(r[k])
        band[a] = {b: dict(t[b]) for b in sorted(t)}
    res["byband_totals"] = band
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, separators=(",", ":"), default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
