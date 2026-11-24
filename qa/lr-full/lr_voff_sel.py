#!/usr/bin/env python3
"""Subset of the registered XC-LIVE selection: the first N FULL cycles of 20261114_2312 with the same warm-up cycle.  python -I lr_voff_sel.py <sel_full.json> <out.json> <N>"""
import json
import sys

src, dst, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
s = json.load(open(src))
r = s["runs"]["20261114_2312"]
assert len(r["FULL"]) == 2833
s["runs"]["20261114_2312"] = {"warmup": r["warmup"], "FULL": r["FULL"][:n]}
s["note"] = "LR-FULL V-OFF subset: the first %d FULL cycles of the XC-LIVE selection (same warm-up cycle)" % n
json.dump(s, open(dst, "w"))
print("selection subset written:", n, "cycles")
