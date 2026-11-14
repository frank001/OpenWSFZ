#!/usr/bin/env python3
"""Shipped-defaults check for the frozen thresholds (the Architect's 'default-values replay as an exact comparison').  COUNTS ONLY out (HK-037): message text is read inside the functions and never printed or written.
Usage:  python -I xc_defaults_cmp.py cmp <defaults arm dir> <reference arm dir> <N> [<surviving numeric files dir>]
        python -I xc_defaults_cmp.py selftest
The arm dirs hold run.csv, matchedbatch.csv, testb.csv and nc.tsv (the Replay81 outputs).  The first N FULL cycles of the DEFAULTS arm define the stamps.
EQUAL means, over those N cycles:  (a) the per-cycle multiset of (batch, text, freq, dt, snr) of every published row (all batches, batch 6 included) is identical (A3.3 identity);  (b) the per-batch counts (b1_n .. b6_n) are identical;
(c) matchedbatch lines and testb rows are identical (timing columns excluded);  (d) batch 6 is non-empty in at least one cycle (else the comparison proves nothing about the stage).
If a directory of SURVIVING numeric files of the original arm is given (matchedbatch.csv, testb.csv, run.csv: the text files were released at the HK-037 close), (b) and (c) are repeated against it, restricted to the same cycles."""
from __future__ import annotations

import collections
import csv
import os
import shutil
import sys
import tempfile

N_DEFAULT = 100
assert N_DEFAULT == 100


def read_run(path):
    rows = list(csv.DictReader(open(os.path.join(path, "run.csv"), encoding="utf-8")))
    return rows


def counts_of(rows, stamps):
    keys = [k for k in ("decodes", "b1_n", "b2_n", "b3_n", "b4_n", "b5_n", "b6_n") if rows and k in rows[0]]
    by = {r["stamp"]: tuple(r[k] for k in keys) for r in rows}
    return keys, {s: by.get(s) for s in stamps}


def matched_of(path, stamps):
    d = {}
    for r in csv.reader(open(os.path.join(path, "matchedbatch.csv"), encoding="utf-8")):
        if r and r[0] != "stamp":
            d[r[0]] = r[1] if len(r) > 1 else ""
    return {s: d.get(s) for s in stamps}


def testb_of(path, stamps):
    want = set(stamps)
    d = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(path, "testb.csv"), encoding="utf-8")):
        if r["stamp"] in want:
            d[r["stamp"]].append((r["kind"], r["band"], r["n"], r["corroborated"]))
    return {s: sorted(d.get(s, [])) for s in stamps}


def multiset_of(path, stamps):
    """stamp -> Counter of (batch, freq, dt, snr, text) over every published row; the text stays in this function's frame."""
    want = set(stamps)
    d = {s: collections.Counter() for s in stamps}
    for line in open(os.path.join(path, "nc.tsv"), encoding="utf-8", errors="replace"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 11 or f[0] not in want:
            continue
        d[f[0]][(f[1], f[3], f[4], f[5], f[10].strip())] += 1
    return d


def compare(a_dir, b_dir, n, surviving=None):
    ra = read_run(a_dir)
    stamps = [r["stamp"] for r in ra][:n]
    assert len(stamps) == n, (len(stamps), n)
    res = {"cycles": n}
    ma, mb = multiset_of(a_dir, stamps), multiset_of(b_dir, stamps)
    res["multiset_cycles_differing"] = sum(1 for s in stamps if ma[s] != mb[s])
    res["published_rows_a"] = sum(sum(c.values()) for c in ma.values())
    res["published_rows_b"] = sum(sum(c.values()) for c in mb.values())
    res["batch6_rows_a"] = sum(v for c in ma.values() for (k, *_), v in c.items() if k == "6")
    res["batch6_rows_b"] = sum(v for c in mb.values() for (k, *_), v in c.items() if k == "6")
    ka, ca = counts_of(ra, stamps)
    kb, cb = counts_of(read_run(b_dir), stamps)
    res["per_batch_counts_cycles_differing"] = sum(1 for s in stamps if ca[s] != cb[s])
    res["matchedbatch_cycles_differing"] = sum(1 for s in stamps if matched_of(a_dir, stamps)[s] != matched_of(b_dir, stamps)[s])
    ta, tb = testb_of(a_dir, stamps), testb_of(b_dir, stamps)
    res["testb_cycles_differing"] = sum(1 for s in stamps if ta[s] != tb[s])
    res["batch6_nonempty_cycles_a"] = sum(1 for s in stamps if any(k == "6" for (k, *_) in ma[s]))
    ok = (res["multiset_cycles_differing"] == 0 and res["per_batch_counts_cycles_differing"] == 0 and res["matchedbatch_cycles_differing"] == 0
          and res["testb_cycles_differing"] == 0 and res["batch6_nonempty_cycles_a"] >= 1 and res["batch6_rows_a"] == res["batch6_rows_b"])
    if surviving:
        sc = counts_of(read_run(surviving), stamps)[1]
        res["vs_surviving_per_batch_counts_cycles_differing"] = sum(1 for s in stamps if ca[s] != sc[s])
        sm = matched_of(surviving, stamps)
        res["vs_surviving_matchedbatch_cycles_differing"] = sum(1 for s in stamps if matched_of(a_dir, stamps)[s] != sm[s])
        st = testb_of(surviving, stamps)
        res["vs_surviving_testb_cycles_differing"] = sum(1 for s in stamps if ta[s] != st[s])
        ok = ok and res["vs_surviving_per_batch_counts_cycles_differing"] == 0 and res["vs_surviving_matchedbatch_cycles_differing"] == 0 and res["vs_surviving_testb_cycles_differing"] == 0
    res["EQUAL"] = bool(ok)
    return res


def _write(d, stamps, rows, b6=True, tweak=None):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "run.csv"), "w", encoding="utf-8") as f:
        f.write("run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,b1_n,b2_n,b3_n,b4_n,b5_n,b6_n\n")
        for i, s in enumerate(stamps):
            f.write(f"r,FULL,{s},{i},DEEP,1000.0,{len(rows)},,{len(rows)},0,0,0,0,{1 if b6 else 0}\n")
    with open(os.path.join(d, "matchedbatch.csv"), "w", encoding="utf-8") as f:
        f.write("stamp,wsjtx_idx_batch\n")
        for s in stamps:
            f.write(f"{s},1:1;2:6\n")
    with open(os.path.join(d, "testb.csv"), "w", encoding="utf-8") as f:
        f.write("run,stamp,kind,band,n,corroborated\n")
        for s in stamps:
            f.write(f"r,{s},b1,A,{len(rows)},1\nr,{s},b6,A,{1 if b6 else 0},{1 if b6 else 0}\n")
    with open(os.path.join(d, "nc.tsv"), "w", encoding="utf-8") as f:
        for s in stamps:
            for k, (freq, dt, snr, text) in enumerate(rows):
                f.write("\t".join([s, "1", "1", str(freq), dt, str(snr), "1", "0", "5", "0", text, "0"]) + "\n")
            if b6:
                f.write("\t".join([s, "6", "1", "1500", "0.80", "-18", "0", "-1", "5", "3", tweak or "Q1AAA Q2BBB -10", "0"]) + "\n")


def selftest():
    tmp = tempfile.mkdtemp(prefix="xc_defaults_cmp_")
    try:
        stamps = [f"261114_10{i:02d}00" for i in range(12)]
        rows = [(1000, "0.90", -5, "CQ Q1AAA AA00"), (1200, "1.00", -12, "Q1AAA Q2BBB -10")]
        a, b, c, e, g = (os.path.join(tmp, x) for x in "abceg")
        _write(a, stamps, rows); _write(b, stamps, rows); _write(c, stamps, rows)
        assert compare(a, b, 10, c)["EQUAL"], compare(a, b, 10, c)                       # identical: EQUAL
        _write(e, stamps, rows, tweak="Q9ZZZ Q8YYY R-01")                                 # one batch-6 text differs in every cycle
        r = compare(a, e, 10)
        assert not r["EQUAL"] and r["multiset_cycles_differing"] == 10, r
        _write(g, stamps, rows, b6=False)                                                 # no batch 6 at all: nothing proved
        r = compare(g, g, 10)
        assert not r["EQUAL"] and r["batch6_nonempty_cycles_a"] == 0, r
        # a single dt differing in one cycle in one row is caught
        shutil.copytree(a, os.path.join(tmp, "h"))
        p = os.path.join(tmp, "h", "nc.tsv")
        lines = open(p, encoding="utf-8").read().split("\n")
        parts = lines[0].split("\t"); parts[4] = "0.91"; lines[0] = "\t".join(parts)
        open(p, "w", encoding="utf-8").write("\n".join(lines))
        r = compare(a, os.path.join(tmp, "h"), 10)
        assert not r["EQUAL"] and r["multiset_cycles_differing"] == 1, r
        # the surviving numeric files differ in one cycle's batch counts: caught
        shutil.copytree(a, os.path.join(tmp, "s"))
        rp = os.path.join(tmp, "s", "run.csv")
        t = open(rp, encoding="utf-8").read().replace(",2,0,0,0,0,1\n", ",2,0,0,0,0,0\n", 1)
        open(rp, "w", encoding="utf-8").write(t)
        r = compare(a, b, 10, os.path.join(tmp, "s"))
        assert not r["EQUAL"] and r["vs_surviving_per_batch_counts_cycles_differing"] >= 1, r
        print("xc_defaults_cmp self-test ALL PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        sys.exit(selftest())
    import json
    out = compare(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else None)
    print(json.dumps(out, indent=1))
    sys.exit(0 if out["EQUAL"] else 3)
