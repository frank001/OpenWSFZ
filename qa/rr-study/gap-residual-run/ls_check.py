#!/usr/bin/env python3
"""LATE-SUB validity rows V0-V5 (spec 5c33391f + Amendment 1 e2f7c5b2) for one arm's output. Counts and flags only.
usage: ls_check.py <arm name> <reference arm dir under coh-gate-r-f4: main|off|on>   (V1 per cycle against the on-disk R-F4 arm: OFF -> main (continuous B-OFF), ON -> on)"""
import collections
import csv
import hashlib
import json
import re
import sys

S = "D:/Projects/claude/_qa-scratch/late-sub"
R4 = "D:/Projects/claude/_qa-scratch/coh-gate-r-f4"
PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
name, ref = sys.argv[1], sys.argv[2]
ref_scr = {"main": f"{R4}/scratch_main/main", "off": f"{R4}/scratch/off", "on": f"{R4}/scratch/on"}[ref]
ref_raw = {"main": f"{R4}/raw_main/main", "off": f"{R4}/raw/off", "on": f"{R4}/raw/on"}[ref]


def lines_by_stamp(p):
    d = collections.defaultdict(list)
    for l in open(p, encoding="utf-8", errors="replace"):
        d[l.split("\t", 1)[0]].append(l)
    return d


out = {"arm": name, "reference": ref}
cyc = list(csv.DictReader(open(f"{S}/ls/{name}/ls_cycle.tsv", encoding="utf-8"), delimiter="\t"))
stamps = [r["stamp"] for r in cyc]
out["cycles"] = len(cyc)
out["V0"] = {"dll_sha_matches_pin": hashlib.sha256(open(f"{S}/bin/libft8.dll", "rb").read()).hexdigest() == PIN}
a, b = lines_by_stamp(f"{S}/scratch/{name}/nc_dump.tsv"), lines_by_stamp(ref_scr + "/nc_dump.tsv")
bad = [s for s in stamps if a.get(s) != b.get(s)]
# also the per-cycle batch counts of run.csv against the reference arm
ra = {r["stamp"]: r for r in csv.DictReader(open(f"{S}/raw/{name}/run.csv"))}
rb = {r["stamp"]: r for r in csv.DictReader(open(ref_raw + "/run.csv"))}
cols = ["decodes", "b1_n", "b2_n", "b3_n", "b4_n"]
bad_run = [s for s in stamps if [ra[s][c] for c in cols] != [rb[s][c] for c in cols]]
out["V1"] = {"cycles_compared": len(stamps), "nc_dump_cycles_differing": len(bad), "run_csv_count_cycles_differing": len(bad_run), "PASS": not bad and not bad_run,
             "first_differing": bad[:3]}
f = lambda k: sum(1 for r in cyc if r[k] == "0")
out["V2"] = {"b1_not_reproduced": f("v2_b1"), "b2_not_reproduced": f("v2_b2"), "b3_not_reproduced": f("v2_b3"), "R3_bytes_not_equal": f("v2_r3_bytes")}
out["V2"]["PASS"] = all(v == 0 for k, v in out["V2"].items())
out["V3"] = {"b4_not_reproduced": f("v3_b4"), "PASS": f("v3_b4") == 0}
nonO = [r for r in cyc if r["level"] != "O"]
snapB_bad = sum(1 for r in nonO if r["snapB"] != "1")
snapR4_bad = sum(1 for r in nonO if r["l_outcome"] == "ran" and r["snapR4"] != "1")
diag = [r["diag_check"] for r in cyc if r["diag_check"] != "-"]
out["V4"] = {"level_counts": dict(collections.Counter(r["level"] for r in cyc)), "snapB_missing_or_unparsed": snapB_bad, "snapR4_missing_where_decoded": snapR4_bad,
             "diag_switch_checks": len(diag), "diag_switch_snapshot_differs": sum(1 for d in diag if d != "1"),
             "l_outcomes": dict(collections.Counter(r["l_outcome"] for r in cyc)),
             "PASS": snapB_bad == 0 and snapR4_bad == 0 and all(d == "1" for d in diag) and len(diag) >= min(5, len(cyc))}
ab = list(csv.DictReader(open(f"{S}/raw/{name}/abandon.csv"), fieldnames=["stamp", "ran", "abandoned", "contained"]))
ab = [r for r in ab if r["stamp"][:1].isdigit()]
th = collections.Counter(r["outcome"] for r in csv.DictReader(open(f"{S}/raw/{name}/third.csv")))
log = open(f"{S}/raw/{name}/log.log", encoding="utf-8", errors="replace").read()
out["V5"] = {"residual_abandoned": sum(int(r["abandoned"]) for r in ab), "residual_contained": sum(int(r["contained"]) for r in ab),
             "third_abandoned_or_failed": th.get("abandoned", 0) + th.get("failed", 0), "fallback_lines": len(re.findall("Coherent fallback:", log)),
             "fallback_lines_abandoned_gt0": len(re.findall(r"abandoned=[1-9]", log))}
out["V5"]["PASS"] = out["V5"]["residual_abandoned"] == 0 and out["V5"]["residual_contained"] == 0 and out["V5"]["third_abandoned_or_failed"] == 0 and out["V5"]["fallback_lines_abandoned_gt0"] == 0
out["ALL_PASS"] = bool(out["V0"]["dll_sha_matches_pin"] and out["V1"]["PASS"] and out["V2"]["PASS"] and out["V3"]["PASS"] and out["V4"]["PASS"] and out["V5"]["PASS"])
json.dump(out, open(f"{S}/check_{name}.json", "w"), indent=1)
print(json.dumps(out, indent=1))
