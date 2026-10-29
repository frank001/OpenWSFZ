#!/usr/bin/env python3
"""NR-TAX B4 option (b) (spec 4179a1e3 + Amendment 1 section 8 001bf76e): force EVERY hit and every non-U miss on the three stored buffers (O, R2, R3) with GAP-RELOCATE's legs,
so the `W` tag (F_wrong on any of O, R2, R3) is symmetrical across NR, hits and the reachable misses. Forced legs on stored buffers: not a replay, no station.
Only counts and flags are written (stamp + row index + numbers)."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import gr_item2 as I2       # noqa: E402
import gres_pilot as P      # noqa: E402

NEW = "D:/Projects/claude/_qa-scratch/gap-residual"


def main():
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    old = {}
    for fn in ("forced_pilot.jsonl", "forced_main.jsonl"):
        for line in open(C.S + "\\" + fn, encoding="utf-8"):
            r = json.loads(line)
            old[(r["stamp"], r["idx"])] = r
    rows = pop["rows"]
    hits = [r for r in rows if r["matched"]]
    miss = [r for r in rows if not r["matched"] and I2.classify(r, old.get((r["stamp"], r["idx"]))) != "XU"]
    assert len(hits) == 9931 and len(miss) == 2029, (len(hits), len(miss))
    sel = hits + miss
    n, secs = P.run_kind({"O": sel, "R2": sel, "R3": sel}, f"{NEW}/forced_all.jsonl")
    print(f"{n} (row, buffer) records in {secs:.0f}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
