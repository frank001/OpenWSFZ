#!/usr/bin/env python3
"""COH-MULTISET-BUILD descriptive follow-ups owed after the ruling (Architect 2026-10-25 09:50Z; spec 6.7, A3.3). Numbers only; no message text is read.

  python mb_desc.py <raw dir with ref/ ms/> <sol|pc> <out json> [--u-ref uprime_ref.json.byband.csv --u-ms uprime_ms.json.byband.csv]

(a) NET and dU' by Test-B band. The bands are Replay81's pre-registered SNR bands OF THE OPENWSFZ DECODE (A snr >= 0, B >= -10, C >= -15, D below).
    NET_band = sum over cycles of (corroborated_ms - corroborated_ref in the band) / sum of W (WSJT-X decodes per cycle), same block bootstrap as the verdict
    (blocks of 40, B 10,000, seed 20261025), over the cycles with WSJT-X decodes; the four bands sum to the NET of the verdict.
    dU'_band = mean over those cycles of (U' numerator MS - REF in the band) from the U' stage by-band files (sol only: the PC run has no U' stage).
(b) the cost lines from coh.csv for the machine named (the same definitions as the verdict analysis: fallback wall, batch-4 publish, margin to the 13 s budget).
Descriptive: there is no bar on any of it.
"""
import collections
import csv
import json
import sys

import numpy as np

import mb_analysis as A


def band_c(path):
    c = collections.defaultdict(float)
    for r in A.rows(path):
        if r["kind"] in ("b1", "b2", "b3", "b4") and r["band"] in "ABCD":
            c[(r["stamp"], r["band"])] += int(r["corroborated"])
    return c


def ubyband(path):
    u = collections.defaultdict(float)
    for r in A.rows(path):
        u[(r["stamp"], r["band"])] += int(r["tested_absent"]) + int(r["hashed_or_unencodable"]) + int(r["untestable_class"])
    return u


def cost(raw, arm):
    coh = {r["stamp"]: r for r in A.rows(f"{raw}/{arm}/coh.csv")}
    wall = [float(r["fb_wall_ms"]) for r in coh.values() if r.get("fb_wall_ms") not in ("", None)]
    t4 = [float(r["batch4_publish_ms"]) for r in coh.values() if r.get("batch4_published") == "1" and r.get("batch4_publish_ms") not in ("", None)]
    return {"cycles_with_fallback_run": len(wall), "fb_wall_ms": {"median": A.pct(wall, 50), "p95": A.pct(wall, 95), "max": max(wall)},
            "batch4_published_cycles": len(t4), "batch4_publish_ms": {"median": A.pct(t4, 50), "p95": A.pct(t4, 95), "max": max(t4)},
            "margin_to_budget_ms_min": A.CYCLE_BUDGET_MS - max(t4)}


def main():
    raw, machine, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ref_tb, ms_tb = A.load_testb(f"{raw}/ref/testb.csv"), A.load_testb(f"{raw}/ms/testb.csv")
    stamps = sorted(ref_tb[0])
    cyc = [s for s in stamps if ref_tb[0][s][0] > 0]
    W = {s: float(ref_tb[0][s][0]) for s in cyc}
    cr, cm = band_c(f"{raw}/ref/testb.csv"), band_c(f"{raw}/ms/testb.csv")
    res = {"machine": machine, "cycles_with_ws": len(cyc), "bands": {}, "cost": {a: cost(raw, a) for a in ("ref", "ms")}}
    tot = 0.0
    for b in "ABCD":
        d = {s: cm[(s, b)] - cr[(s, b)] for s in cyc}
        n = A.boot_ratio(d, W, cyc)
        tot += sum(d.values())
        res["bands"][b] = {"delta_corroborated": sum(d.values()), "NET_pp": {"point": 100 * n[0], "lo": 100 * n[1], "hi": 100 * n[2]}}
    res["sum_delta_corroborated_bands"] = tot
    res["delta_M_from_ws_rows"] = sum(ms_tb[0][s][1] - ref_tb[0][s][1] for s in cyc)
    if "--u-ref" in sys.argv:
        ur, um = ubyband(sys.argv[sys.argv.index("--u-ref") + 1]), ubyband(sys.argv[sys.argv.index("--u-ms") + 1])
        ones = {s: 1.0 for s in cyc}
        for b in "ABCD":
            d = {s: um.get((s, b), 0.0) - ur.get((s, b), 0.0) for s in cyc}
            n = A.boot_ratio(d, ones, cyc)
            res["bands"][b]["dU_prime"] = {"sum": sum(d.values()), "per_cycle": n[0], "lo": n[1], "hi": n[2], "U_bar_reference_only": A.U_BAR}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
