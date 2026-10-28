#!/usr/bin/env python3
"""GAP-RELOCATE pilot diagnostic (DESCRIPTIVE ONLY; no M row is touched; nothing here changes the frozen deltas).
Why did the pilot's P_ctrl fall below 0.90? Shows the production-minus-REF dt distribution and how the pilot K rows' forced success
moves with delta. Pilot K rows only (cycles 1-40)."""
import collections
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gr_forced as F


def main():
    pop = F.load_pop()
    pk = [r for r in pop["rows"] if r["K"] and r["pilot"]]
    d = [r["ows_dt"] - r["dt"] for r in pk if r["kind"] in (1, 2, 3)]
    print("pairs", len(d), "median", round(statistics.median(d), 3), "mean", round(statistics.mean(d), 4), "stdev", round(statistics.pstdev(d), 4))
    print("hist 0.05 bins", sorted(collections.Counter(round(x * 20) / 20 for x in d).items()))
    print("ows_dt second decimal values", sorted({round(r["ows_dt"] * 100) % 10 for r in pk}))
    print("ref_dt second decimal values", sorted({round(r["dt"] * 100) % 10 for r in pk}))
    key = {(r["stamp"], r["idx"]): r for r in pop["rows"]}
    for dp in (0.60, 0.65, 0.70):
        out = C.S + f"\\diag_pilot_{int(round(dp * 100))}.jsonl"
        if os.path.exists(out):
            os.remove(out)
        F.run_forced(pk, dp, dp, out)
        recs = [json.loads(x) for x in open(out)]
        for tag, sel in (("original-path", lambda t: t != "fb_res"), ("b123", lambda t: t == "b123"), ("fb_orig", lambda t: t == "fb_orig")):
            o = [x for x in recs if not x["unencodable"] and sel(key[(x["stamp"], x["idx"])]["tag"])]
            u = sum(1 for x in o if x["fp"]["found"] or x["fc"]["v3_match"] or x["walk"]["match"])
            p = sum(1 for x in o if x["fp"]["found"])
            c = sum(1 for x in o if x["fc"]["v3_match"] or x["walk"]["match"])
            print("delta", dp, tag, "n", len(o), "union", round(u / len(o), 3), "FP", round(p / len(o), 3), "FC(any gate)+walk", round(c / len(o), 3))


if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()
    main()
