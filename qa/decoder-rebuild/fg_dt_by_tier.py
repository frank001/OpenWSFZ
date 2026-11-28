#!/usr/bin/env python3
"""FINE-GRID: the mean reported DT of the published, WSJT-X-matched decodes by publishing tier, baseline (xn) against arm T and arm F (Architect's question, 2026-11-28: is the +0.024 s DT shift of the 4 x 4 grid
the grid-timed tiers (+0.040 s expected) mixed with tier B (refined, about 0)?).

  python -I fg_dt_by_tier.py

Numbers only (HK-037): nc.tsv is read for stamp, matched flag, frequency and DT; the text column is never touched. A published decode is linked to the probe's CAND row of the same cycle with a PUBLISHED outcome
(1 tier A, 5 tier B, 8 CQ-AP) nearest in frequency within 2 Hz; decodes with no such row are counted as 'unlinked' (a duplicate-replaced row, a later-round or cross-cycle decode, a frequency conflict).
"""
import os
import statistics
from collections import defaultdict

R = r"D:\Projects\claude\_qa-scratch\lc-base\runs"
SL = {"S40": 170, "H40": 240, "H20": 240}
TIER = {1: "A", 5: "B", 8: "CQ"}
TOL_HZ = 2.0


def load_cands(d):
    out = defaultdict(list)                          # stamp -> [(freq, outcome, time_s, round)]
    with open(os.path.join(d, "probe.tsv"), encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 17 or c[1] != "2":
                continue
            o = int(c[9])
            if o in TIER:
                out[c[0]].append((float(c[3]), o, float(c[4]), int(c[2])))
    return out


def run(tag, sl, n):
    d = os.path.join(R, "%s_%s_L_n%d" % (tag, sl, n))
    cands = load_cands(d)
    by = defaultdict(list)
    seen = set()
    unlinked = 0
    with open(os.path.join(d, "nc.tsv"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 11 or c[2] != "1":
                continue
            k = (c[0], c[10])
            if k in seen:
                continue
            seen.add(k)
            try:
                f, dt = float(c[3]), float(c[4])
            except ValueError:
                continue
            best = None
            for (cf, o, t, rd) in cands.get(c[0], []):
                if abs(cf - f) <= TOL_HZ and (best is None or abs(cf - f) < best[0]):
                    best = (abs(cf - f), o, t, rd)
            if best is None:
                unlinked += 1
                by["unlinked"].append(dt)
            else:
                by[TIER[best[1]] + (".r0" if best[3] == 0 else ".res")].append(dt)
    return by


def main():
    for sl, n in SL.items():
        res = {t: run(t, sl, n) for t in ("xn", "fgT", "fgF")}
        keys = sorted({k for r in res.values() for k in r})
        print("== %s" % sl)
        for k in keys:
            row = []
            for t in ("xn", "fgT", "fgF"):
                v = res[t].get(k, [])
                row.append("%s n=%d mean=%.4f" % (t, len(v), statistics.mean(v)) if v else "%s n=0" % t)
            shift = ""
            if res["xn"].get(k) and res["fgF"].get(k):
                shift = "  shift F-xn %+.4f s" % (statistics.mean(res["fgF"][k]) - statistics.mean(res["xn"][k]))
            print("  %-9s %s%s" % (k, " | ".join(row), shift))


if __name__ == "__main__":
    main()
