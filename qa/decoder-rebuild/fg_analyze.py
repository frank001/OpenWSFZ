#!/usr/bin/env python3
"""FINE-GRID analysis (spec-fine-grid.md section 4): the two-arm replay (`fgT` = thin 1 at 2 x 2, `fgF` = thin 1 at 4 x 4) against the XC-ROUND confirmation runs `xn_*` (same audio, same flags, same 16 threads).

  python -I fg_analyze.py [slice,slice,...]       (reads lc-base\\runs\\{xn,fgT,fgF}_<slice>_L_n<cycles>\\{arm.json, lean.csv, matched.csv, matchedbatch.csv, probe.tsv, sel.json}; numbers only)

4.1 the candidate counts per round (what THIN did to the lists); 4.2 Table 1 with deltas (T and F against xn, F against T); 4.3 cost; 4.4 K0..K4 against the baseline (K3 + K4 is prediction FG-3's quantity) and the
added decodes by batch (1 = round 0, 2 = rounds 1 to 3, 3 = cross-cycle stage; the XC round's own decodes come from lean.csv's xr_decodes), with matched gained and lost.
The ours_only check is pf_oo_check.py (run it as `pf_oo_check.py xn fgT` and `pf_oo_check.py xn fgF`). The first check is fg_firstcheck.py (done before anything here is read).
"""
import csv
import json
import os
import statistics
import sys
from collections import Counter

SEL = sys.argv[1].split(",") if len(sys.argv) > 1 else ["S40", "H40", "H20"]
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sub_probe_analyze as sp   # noqa: E402

SC = sp.SC
PIN = "0ef023d55a381db9"                                # first 16 hex of the SHA256 of libft8.dll of e9c8f02d (FINE-GRID, shim 20260083): the arm.json's bin_pin
BASE_RATE = {"S40": 88.203, "H40": 87.899, "H20": 86.279}      # the XC-ROUND confirmation runs (asserted against their arm.json: inherited constants)
CLASSIC_RATE = {"S40": 84.39, "H40": 85.29, "H20": 81.25}
KIND_CAND = 2


def run_dir(tag, name):
    return SC + r"\lc-base\runs\%s_%s_L_n%d" % (tag, name, sp.SL[name][0])


def cand_counts(d):
    """CAND rows per round group: mean rows per (cycle, round) for round 0, rounds 1-3 and the XC round (4)."""
    cnt, rnd = Counter(), Counter()
    per = Counter()
    with open(d + r"\probe.tsv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 17 or int(c[1]) != KIND_CAND:
                continue
            per[(c[0], int(c[2]))] += 1
    for (st, r), n in per.items():
        g = "round0" if r == 0 else ("xc_round4" if r == 4 else "rounds1to3")
        cnt[g] += n
        rnd[g] += 1
    return {g: {"rounds": rnd[g], "rows": cnt[g], "mean_per_round": round(cnt[g] / rnd[g], 1) if rnd[g] else None} for g in ("round0", "rounds1to3", "xc_round4")}


def arm_numbers(d):
    a = json.load(open(d + r"\arm.json"))
    return {k: a[k] for k in ("matched", "ours", "wsjtx_decodes", "rate_pct", "ours_only_pct", "cpu_s_per_cycle", "last_p95_ms", "abandoned_cycles", "lean_error_cycles", "lean_parse_failed", "bin_pin", "flags")}


def xr_decodes(d):
    return sum(int(r.get("xr_decodes", 0) or 0) for r in csv.DictReader(open(d + r"\lean.csv", newline="")))


def kclasses(name, tag):
    sp.TAG = tag
    res = sp.run_slice(name)
    c = res["counts"]
    return {"classified": res["classified"], "crowded_missed": res["crowded_missed_by_L"], "counts": c, "K3_plus_K4": c.get("K3", 0) + c.get("K4", 0)}


def run_slice(name):
    n, folder = sp.SL[name]
    dirs = {t: run_dir(t, name) for t in ("xn", "fgT", "fgF")}
    nums = {t: arm_numbers(d) for t, d in dirs.items()}
    assert abs(nums["xn"]["rate_pct"] - BASE_RATE[name]) < 0.01, nums["xn"]["rate_pct"]
    for t in ("fgT", "fgF"):
        assert nums[t]["bin_pin"] == PIN, nums[t]["bin_pin"]
        assert nums[t]["wsjtx_decodes"] == nums["xn"]["wsjtx_decodes"]
    assert "--lean-thin 1" in nums["fgT"]["flags"] and "--lean-time-osr 2 --lean-freq-osr 2" in nums["fgT"]["flags"], nums["fgT"]["flags"]
    assert "--lean-thin 1" in nums["fgF"]["flags"] and "--lean-time-osr 4 --lean-freq-osr 4" in nums["fgF"]["flags"], nums["fgF"]["flags"]
    sels = [json.load(open(d + r"\sel.json")) for d in dirs.values()]
    assert sels[0] == sels[1] == sels[2], "the runs must replay the same cycles"
    stamps = list(sels[0]["runs"][sels[0]["run"]]["FULL"])
    out = {"cycles": len(stamps), "wsjtx_decodes": nums["xn"]["wsjtx_decodes"]}
    out["candidates_per_round"] = {t: cand_counts(d) for t, d in dirs.items()}
    pct = lambda k, t: round(100.0 * nums[t][k] / nums[t]["wsjtx_decodes"], 3)
    t1 = {t: {"matched": nums[t]["matched"], "ours": nums[t]["ours"], "rate_pct": nums[t]["rate_pct"], "ours_only_pct": nums[t]["ours_only_pct"], "ours_over_wsjtx_pct": pct("ours", t)} for t in dirs}
    for t, base in (("fgT", "xn"), ("fgF", "xn"), ("fgF", "fgT")):
        t1["delta_%s_vs_%s" % (t, base)] = {"rate_pp": round(nums[t]["rate_pct"] - nums[base]["rate_pct"], 3), "ours_only_pp": round(nums[t]["ours_only_pct"] - nums[base]["ours_only_pct"], 3),
                                            "ours_over_wsjtx_pp": round(pct("ours", t) - pct("ours", base), 3), "matched": nums[t]["matched"] - nums[base]["matched"], "ours": nums[t]["ours"] - nums[base]["ours"]}
    t1["lean_minus_classic_pp"] = {t: round(nums[t]["rate_pct"] - CLASSIC_RATE[name], 2) for t in dirs}
    out["table1"] = t1
    out["cost"] = {t: {"cpu_s_per_cycle": nums[t]["cpu_s_per_cycle"], "cpu_vs_xn_pct": round(100.0 * (nums[t]["cpu_s_per_cycle"] / nums["xn"]["cpu_s_per_cycle"] - 1.0), 1), "last_p95_ms": nums[t]["last_p95_ms"],
                       "abandoned_cycles": nums[t]["abandoned_cycles"], "native_error_cycles": nums[t]["lean_error_cycles"], "lean_parse_failed": nums[t]["lean_parse_failed"], "xr_batch4_decodes": xr_decodes(d)}
                   for t, d in dirs.items()}
    wl = sp.load_wsjtx(os.path.join(sp.ART, folder, "wsjt-x", "ALL.TXT"), stamps)
    out["k_classes"] = {t: kclasses(name, t) for t in dirs}
    Mx = {t: sp.load_matched(d) for t, d in dirs.items()}
    MB = {t: sp.load_batch(d) for t, d in dirs.items()}
    knock = {}
    for t, base in (("fgT", "xn"), ("fgF", "xn"), ("fgF", "fgT")):
        gained = lost = 0
        by_batch = Counter()
        for st in stamps:
            g, l = Mx[t].get(st, set()) - Mx[base].get(st, set()), Mx[base].get(st, set()) - Mx[t].get(st, set())
            gained += len(g)
            lost += len(l)
            for j in g:
                by_batch[MB[t].get((st, j), 0)] += 1
        assert gained - lost == nums[t]["matched"] - nums[base]["matched"]
        knock["%s_vs_%s" % (t, base)] = {"matched_gained_gross": gained, "matched_lost_gross": lost, "net": gained - lost, "gained_by_batch_1_round0_2_rounds1to3_3_crossCycle": dict(sorted(by_batch.items()))}
    out["knock_on"] = knock
    return out


def main():
    out = {s: run_slice(s) for s in SEL}
    with open(os.path.join(SC, "lc-base", "fg_analyze.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
