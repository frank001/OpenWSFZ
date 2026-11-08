#!/usr/bin/env python3
"""SUB-COVER (#273): GAP-RELOCATE's frozen forced legs (gr_forced.force_cycle, unchanged; delta_p 0.6 s, delta_c 0.7 s) run on the oracle buffers. ONLY the PCM argument changes, exactly as
GAP-RESIDUAL changed it to R2/R3 (gres_pilot.py): the loader reads the buffer written by sc_build.py. Counts, flags and positions only are written (stamp + row index + numbers).

    python sc_force.py r2r      forced legs on the dt-rounded R2 (O-ROUND) for the 7,239 batch-1 hits
    python sc_force.py ostar    forced legs on O* for every NR row and every hit
"""
from __future__ import annotations

import collections
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402

SC = "D:/Projects/claude/_qa-scratch/sub-cover"
GR = "D:/Projects/claude/_qa-scratch/gap-residual"
DELTA_P, DELTA_C = 0.6, 0.7                    # frozen, GAP-RELOCATE deltas.json; asserted against the file in main()
_K = [None]


def _load(path):
    stamp = os.path.splitext(os.path.basename(path))[0]
    return np.fromfile(f"{SC}/cap/buffers/{stamp}_{_K[0]}.f32", dtype=np.float32)


def _init():
    F._init()
    F.wavio.load_cycle_pcm = _load


def _job(job):
    kind, stamp, rows, dp, dc = job
    _K[0] = kind
    return kind, F.force_cycle((stamp, rows, dp, dc))


def run_kind(kind, rows, out_path, workers=8):
    by = collections.OrderedDict()
    for r in rows:
        if os.path.isfile(f"{SC}/cap/buffers/{r['stamp']}_{kind}.f32"):
            by.setdefault(r["stamp"], []).append(r)
    jobs = [(kind, s, rl, DELTA_P, DELTA_C) for s, rl in by.items()]
    t0, n = time.time(), 0
    with open(out_path, "w", encoding="utf-8") as fh, mp.Pool(workers, initializer=_init) as pool:
        for k, recs in pool.imap_unordered(_job, jobs):
            for rec in recs:
                rec["buf"] = k
                fh.write(json.dumps(rec) + "\n")
                n += 1
            fh.flush()
    return n, time.time() - t0


def tags():
    d = {}
    for line in open(GR + "/nrtax_row_tags.jsonl", encoding="utf-8"):
        r = json.loads(line)
        d[(r["stamp"], r["idx"])] = r
    return d


def main():
    deltas = json.load(open(C.S + "\\deltas.json", encoding="utf-8"))
    assert abs(deltas["delta_p"] - DELTA_P) < 1e-9 and abs(deltas["delta_c"] - DELTA_C) < 1e-9, deltas
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    rows = pop["rows"]
    hits = [r for r in rows if r["matched"]]
    cmd = sys.argv[1]
    if cmd == "r2r":
        sel = [r for r in hits if r["kind"] == 1]
        assert len(sel) == 7239, len(sel)
        n, secs = run_kind("R2R", sel, f"{SC}/forced_R2R.jsonl")
    elif cmd == "ostar":
        tg = tags()
        nr = [r for r in rows if tg.get((r["stamp"], r["idx"]), {}).get("pop") == "NR"]
        assert len(hits) == 9931 and len(nr) == 1589, (len(hits), len(nr))
        n, secs = run_kind("OSTAR", hits + nr, f"{SC}/forced_OSTAR.jsonl")
    else:
        sys.exit(__doc__)
    print(f"{n} (row, buffer) records in {secs:.0f}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
