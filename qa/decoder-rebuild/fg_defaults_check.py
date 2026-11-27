#!/usr/bin/env python3
"""FINE-GRID defaults check (QA review note 1): a run of the new build with thin 0 and osr 0 (= 2 x 2) against the first N cycles of the xn_S40 baseline (the shipped build's XC-ROUND confirmation run).

  python -I fg_defaults_check.py <new run dir name> <baseline dir name> <n cycles>

Compares, per cycle of the first N: the probe rows (every numeric column the baseline has; the new build's two extra columns are ignored), matched.csv, matchedbatch.csv, and the set of published results
(nc.tsv, read by code only: only hashes are compared, nothing is printed but counts; HK-037). Prints counts and equal / not equal only.
"""
import csv
import hashlib
import json
import os
import sys

RUNS = r"D:\Projects\claude\_qa-scratch\lc-base\runs"
new, base, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
sel = json.load(open(os.path.join(RUNS, new, "sel.json")))
stamps = list(sel["runs"][sel["run"]]["FULL"])[:n]
assert len(stamps) == n
S = set(stamps)


def probe_rows(d):
    out = {s: [] for s in stamps}
    with open(os.path.join(RUNS, d, "probe.tsv"), encoding="utf-8") as fh:
        hdr = next(fh).rstrip("\n").split("\t")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if c[0] in S:
                out[c[0]].append(tuple(c[:17]))                     # the baseline's 17 columns
    return out, hdr


def csv_rows(d, name):
    out = {}
    with open(os.path.join(RUNS, d, name), newline="") as fh:
        for row in csv.DictReader(fh):
            if row["stamp"] in S:
                out[row["stamp"]] = tuple(row.items())
    return out


def published(d):
    out = {s: [] for s in stamps}
    with open(os.path.join(RUNS, d, "nc.tsv"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) >= 11 and c[0] in S:
                out[c[0]].append(hashlib.sha256(line.encode("utf-8", "replace")).hexdigest())
    return {k: sorted(v) for k, v in out.items()}


pn, hn = probe_rows(new)
pb, hb = probe_rows(base)
print("probe columns: new %d, baseline %d; new extras: %s" % (len(hn), len(hb), hn[len(hb):]))
rows_new = sum(len(v) for v in pn.values())
rows_base = sum(len(v) for v in pb.values())
diff_cycles = [s for s in stamps if pn[s] != pb[s]]
print("probe rows over %d cycles: new %d, baseline %d; cycles with any difference: %d" % (n, rows_new, rows_base, len(diff_cycles)))
r0n = sum(1 for s in stamps for r in pn[s] if r[1] == "2" and r[2] == "0")
print("round-0 CAND rows: %d (140 per cycle expected = %d)" % (r0n, 140 * n))
for name in ("matched.csv", "matchedbatch.csv"):
    a, b = csv_rows(new, name), csv_rows(base, name)
    print("%s: cycles %d / %d; cycles differing: %d" % (name, len(a), len(b), sum(1 for s in stamps if a.get(s) != b.get(s))))
a, b = published(new), published(base)
print("published (nc.tsv, hashes): new %d, baseline %d; cycles differing: %d" % (sum(map(len, a.values())), sum(map(len, b.values())), sum(1 for s in stamps if a[s] != b[s])))
ok = not diff_cycles and all(a[s] == b[s] for s in stamps)
print("RESULT:", "IDENTICAL" if ok else "DIFFERENT")
