#!/usr/bin/env python
"""Merge-gate control (Captain, 2026-09-30; Architect spec 5g): flag-OFF managed `DecodeAsync`, origin/main vs the merge head.

Compares two numeric outcome files written by the Replay81 harness (`--mode off --outcomes <file>`, numeric-only, 6 fields per line:
stamp,kind,idx,freqHz,dt,snr), one per build, per run, over the 161 E1 cycles, and prints COUNTS only.
PASS iff 161 / 161 cycles are identical IN ORDER on (freqHz, dt, snr).

Usage:
  python flagoff_managed_compare.py <derived_selection.json> <main_dir> <head_dir>
where <main_dir> and <head_dir> each hold <run>.outcomes.txt for the three runs (20260922_2056, 20260923_1730, 20260925_2010).

HK-037 / NFR-021: the files are numeric; this script prints counts and stamps of mismatching cycles only.
"""
import collections
import json
import os
import sys

RUNS = ["20260922_2056", "20260923_1730", "20260925_2010"]


def read(path):
    d = collections.defaultdict(list)
    for line in open(path, encoding="utf-8"):
        p = line.rstrip("\n").split(",")
        if len(p) != 6:
            raise SystemExit("unexpected outcome line width %d in %s (numeric-only files have 6 fields)" % (len(p), path))
        d[p[0]].append((int(p[3]), float(p[4]), int(p[5])))
    return d


def main():
    sel = json.load(open(sys.argv[1], encoding="utf-8"))
    md, hd = sys.argv[2], sys.argv[3]
    total = ok = 0
    bad = []
    n_main = n_head = 0
    for run in RUNS:
        a = read(os.path.join(md, run + ".outcomes.txt"))
        b = read(os.path.join(hd, run + ".outcomes.txt"))
        for stamp in sel["runs"][run]["E1"]:
            total += 1
            n_main += len(a[stamp])
            n_head += len(b[stamp])
            if a[stamp] == b[stamp]:
                ok += 1
            else:
                bad.append(run + "|" + stamp)
    print(json.dumps({"cycles": total, "identical_in_order": ok, "decodes_main": n_main, "decodes_head": n_head,
                      "mismatching_cycles": bad[:40], "PASS": total == 161 and ok == 161}, indent=1))
    return 0 if (total == 161 and ok == 161) else 1


if __name__ == "__main__":
    sys.exit(main())
