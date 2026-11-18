#!/usr/bin/env python3
"""LR-FULL V-OFF comparison (counts only; message text is never printed, HK-037).
  python -I lr_voff_compare.py <base dir> <new OFF dir> [<new ON dir>]
V-OFF passes iff, between base and new-OFF: nc.tsv columns 1-12 identical line by line; outcomes.csv, matched.csv, matchedbatch.csv and testb.csv identical; the 'Coherent fallback:' and
'Late subtraction round:' log lines equal after dropping their timing fields; no 'Diagnostic X' line in the OFF log. Informational for new-ON: rows added by step, X1/X2 lines, abandoned candidates."""
import collections
import os
import re
import sys

TIMING = re.compile(r"(?i)^[a-z0-9]*(ms|elapsed|wall|publish)[a-z0-9]*=")


def lines(p):
    with open(p, encoding="utf-8", errors="replace", newline="") as fh:
        return [l.rstrip("\r") for l in fh.read().split("\n")]


def nc_cols(p, n):
    return [tuple(l.split("\t")[:n]) for l in lines(p) if l]


def logfam(p, prefix):
    out = []
    for l in lines(p):
        i = l.find(prefix)
        if i >= 0:
            toks = [t for t in l[i:].replace(",", " ").split() if not TIMING.match(t)]
            out.append(" ".join(toks))
    return out


def main():
    base, off = sys.argv[1], sys.argv[2]
    on = sys.argv[3] if len(sys.argv) > 3 else None
    res = []

    def same(a, b, what):
        res.append((what, a == b, len(a), len(b)))

    same(nc_cols(os.path.join(base, "nc.tsv"), 12), nc_cols(os.path.join(off, "nc.tsv"), 12), "nc.tsv columns 1-12 (rows)")
    for f in ("outcomes.csv", "matched.csv", "matchedbatch.csv", "testb.csv"):
        same([l for l in lines(os.path.join(base, f)) if l], [l for l in lines(os.path.join(off, f)) if l], f)
    for pre in ("Coherent fallback:", "Late subtraction round:"):
        same(logfam(os.path.join(base, "log.log"), pre), logfam(os.path.join(off, "log.log"), pre), "log '" + pre + "' lines, timing fields dropped")
    diagoff = sum(1 for l in lines(os.path.join(off, "log.log")) if "Diagnostic X" in l)
    res.append(("no Diagnostic X line in the OFF log", diagoff == 0, diagoff, 0))
    for what, ok, a, b in res:
        print(("PASS " if ok else "FAIL ") + what + " (%d vs %d)" % (a, b))
    print("V-OFF " + ("PASS" if all(r[1] for r in res) else "FAIL"))
    st = collections.Counter(l.split("\t")[12] for l in lines(os.path.join(off, "nc.tsv")) if l and len(l.split("\t")) > 12)
    print("OFF arm step column (0 none, 1 v2 at or below the gate, 3 late-round primary):", dict(sorted(st.items())))
    if on:
        no, non = nc_cols(os.path.join(off, "nc.tsv"), 12), nc_cols(os.path.join(on, "nc.tsv"), 13)
        koff, kon = collections.Counter((r[0], r[1]) for r in no), collections.Counter((r[0], r[1]) for r in non)
        diff = {k: kon[k] - koff[k] for k in sorted(set(kon) | set(koff)) if kon[k] != koff[k]}
        print("ON arm (informational, not an identity): rows", len(non), "vs OFF", len(no), "| by step:", dict(sorted(collections.Counter(r[12] for r in non).items())),
              "| per (cycle, batch) row differences ON minus OFF:", len(diff), "cells")
        for fam in ("Diagnostic X1", "Diagnostic X2"):
            L = [l for l in lines(os.path.join(on, "log.log")) if fam in l]
            ab = sum(int(m.group(1)) for l in L for m in [re.search(r"abandonedCandidates=(\d+)", l)] if m)
            print("  '%s' lines: %d" % (fam, len(L)) + (", abandoned candidates %d" % ab if fam.endswith("X2") else ""))


main()
