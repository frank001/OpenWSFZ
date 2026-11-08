#!/usr/bin/env python3
"""GAP-RESIDUAL ROW 0 (spec 74a38158 + Amendment 1, ea7496d1): 0a identity, 0b replay = GAP-RELOCATE, 0c capture identity (i) and (ii), 0f no abandonment.
(0c(iii) is the separate-process recheck: Ft8.FitProbe.exe --cap-recheck.)  Counts and flags only; message text is compared in memory and never written.

Expected DecodeAll count per cycle, from RunCore (SubtractionPass.cs, origin/main c2c85c45), as QA states it for 0c(i):
  call 0 (O)  : always (the first full DecodeAll of the cycle).
  call 1 (R2) : iff the residual pass fitted >= 1 signal and was not abandoned/failed BEFORE its decode (RunCore returns [] before any DecodeAll when no candidate is re-encodable).
  call 2 (R3) : iff the third pass fitted >= 1 signal (its new signals) and was not abandoned/failed before its decode.
Third-pass outcome (third.csv): ran -> R3 exists and is taken; skipped-no-new -> no third DecodeAll (FittedSignals 0); abandoned / failed -> a third DecodeAll MAY have happened
(abandoned after the decode); such a buffer is NOT taken as R3 (R3 only where the outcome is ran). Each outcome is listed separately below.
Selector (CohFallbackAudioSelector.Select, Both): O when no usable residual buffer (residual pass abandoned, contained exception, no buffer, FittedSignals 0); else R3 when the third
pass outcome is ran with a buffer; else R2.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import os
import sys

NEW = "D:/Projects/claude/_qa-scratch/gap-residual"
OLD = "D:/Projects/claude/_qa-scratch/gap-relocate"
ARM = sys.argv[1] if len(sys.argv) > 1 else "off"
PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
B4_PUBLISHED, CORROBORATED, REF_N = 1350, 9931, 12124          # GAP-RELOCATE 0b
assert (B4_PUBLISHED, CORROBORATED, REF_N) == (1350, 9931, 12124)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rows(p):
    return list(csv.DictReader(open(p, encoding="utf-8")))


def main():
    out = {"arm": ARM}
    r_new, r_old = f"{NEW}/raw/{ARM}", f"{OLD}/raw/both"
    # 0a
    dll_ok = sha(f"{NEW}/bin/libft8.dll") == PIN
    out["0a"] = {"dll_sha_matches_pin": dll_ok, "pin": PIN}
    # 0b: per-row hit/miss, batch counts, nc dump
    mb_new, mb_old = open(f"{r_new}/matchedbatch.csv", "rb").read(), open(f"{r_old}/matchedbatch.csv", "rb").read()
    out["0b"] = {"matchedbatch_identical": mb_new == mb_old}
    nn, no = open(f"{NEW}/scratch/{ARM}/nc_dump.tsv", "rb").read(), open(f"{OLD}/scratch/both/nc_dump.tsv", "rb").read()
    out["0b"]["nc_dump_identical"] = nn == no
    out["0b"]["nc_dump_lines"] = [nn.count(b"\n"), no.count(b"\n")]
    rn, ro = rows(f"{r_new}/run.csv"), rows(f"{r_old}/run.csv")
    cols = ["stamp", "decodes", "exception", "b1_n", "b2_n", "b3_n", "b4_n"]
    out["0b"]["run_csv_count_columns_identical"] = [[r[c] for c in cols] for r in rn] == [[r[c] for c in cols] for r in ro]
    out["0b"]["batch4_published"] = sum(int(r["b4_n"]) for r in rn)
    out["0b"]["batch4_published_expected"] = B4_PUBLISHED
    # corroborated = distinct REF rows hit in the matchedbatch file
    hit = sum(len([x for x in r["wsjtx_idx_batch"].split(";") if x]) for r in rows(f"{r_new}/matchedbatch.csv"))
    out["0b"]["corroborated"] = hit
    out["0b"]["corroborated_expected"] = CORROBORATED
    out["0b"]["PASS"] = bool(out["0b"]["matchedbatch_identical"] and out["0b"]["run_csv_count_columns_identical"] and out["0b"]["batch4_published"] == B4_PUBLISHED and hit == CORROBORATED)
    # 0f: abandonment (this arm), from the harness's own files
    ab = rows(f"{r_new}/abandon.csv")
    out["0f"] = {"residual_abandoned": sum(int(r["abandoned"]) for r in ab), "residual_contained": sum(int(r["contained"]) for r in ab)}
    th = {r["stamp"]: r for r in rows(f"{r_new}/third.csv")}
    out["0f"]["third_outcomes"] = dict(collections.Counter(r["outcome"] for r in th.values()))
    coh = open(f"{r_new}/log.log", encoding="utf-8", errors="replace").read()
    import re
    out["0f"]["fallback_lines"] = len(re.findall("Coherent fallback:", coh))
    out["0f"]["fallback_lines_with_abandoned_gt0"] = len(re.findall(r"abandoned=[1-9]", coh))
    out["0f"]["PASS"] = bool(out["0f"]["residual_abandoned"] == 0 and out["0f"]["residual_contained"] == 0 and out["0f"]["third_outcomes"].get("abandoned", 0) == 0
                             and out["0f"]["third_outcomes"].get("failed", 0) == 0 and out["0f"]["fallback_lines_with_abandoned_gt0"] == 0)
    # 0c(i), (ii)
    ab = {r["stamp"]: r for r in ab}
    idx = [l.rstrip("\n").split("\t") for l in open(f"{NEW}/cap/{ARM}/capture_index.tsv", encoding="utf-8")]
    c1 = {"cycles": len(idx), "O_in_every_cycle": 0, "mismatch_count_rule": 0, "calls_by_third_outcome": collections.defaultdict(collections.Counter)}
    c2 = {"level_counts_observed": collections.Counter(), "level_matches_selector": 0, "second_run_cycles": 0, "second_run_reads_O": 0, "no_residual_usable_cycles": 0}
    for t in idx:
        stamp, ncalls = t[0], int(t[1])
        lens = t[2].split("|")
        if ncalls >= 1 and lens[0] == "180000":
            c1["O_in_every_cycle"] += 1
        a, o = ab[stamp], th.get(stamp, {"outcome": "no-line"})["outcome"]
        c1["calls_by_third_outcome"][o][ncalls] += 1
        resid_ran = a["ran"] == "1"
        usable = resid_ran and a["abandoned"] == "0" and a["contained"] == "0"
        if o == "ran":
            exp = {3}
        elif o == "skipped-no-new":
            exp = {2} if usable else {1}
        elif o == "no-line":
            exp = {1, 2}              # no third-pass line: residual pass did not reach it (not Deep / abandoned / nothing fitted)
        else:
            exp = {2, 3}              # abandoned / failed: a third DecodeAll may or may not have happened
        if ncalls not in exp:
            c1["mismatch_count_rule"] += 1
        level_obs, second = t[9], t[10]
        c2["level_counts_observed"][level_obs] += 1
        exp_level = "R3" if (o == "ran" and usable) else ("R2" if usable else "O")
        if level_obs == exp_level:
            c2["level_matches_selector"] += 1
        if not usable:
            c2["no_residual_usable_cycles"] += 1
        if t[7] == "2":
            c2["second_run_cycles"] += 1
            c2["second_run_reads_O"] += (second == "O")
    c1["calls_by_third_outcome"] = {k: dict(v) for k, v in c1["calls_by_third_outcome"].items()}
    c2["level_counts_observed"] = dict(c2["level_counts_observed"])
    c1["PASS"] = bool(c1["O_in_every_cycle"] == len(idx) and c1["mismatch_count_rule"] == 0)
    c2["PASS"] = bool(c2["level_matches_selector"] == len(idx) and c2["second_run_reads_O"] == c2["second_run_cycles"])
    out["0c_i"], out["0c_ii"] = c1, c2
    json.dump(out, open(f"{NEW}/row0_{ARM}.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
