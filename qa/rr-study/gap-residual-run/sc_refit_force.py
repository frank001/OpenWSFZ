#!/usr/bin/env python3
"""CS-REFIT: GAP-RELOCATE's frozen forced legs (gr_forced.force_cycle, unchanged; delta_p 0.6 s, delta_c 0.7 s) on the S, I and R3B buffers for EVERY row of n_ref (12,124) (spec 1; A1.2: the R3
baseline by the same code as the legs). Same as sc_force.py / sc_force2.py; buffers from _qa-scratch/cs-refit/buffers.

    python sc_refit_force.py S | I | R3B        -> cs-refit/forced_<kind>.jsonl
Counts, flags and positions only are written (stamp + row index + numbers)."""
from __future__ import annotations

import collections
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402

CS = "D:/Projects/claude/_qa-scratch/cs-refit"
DELTA_P, DELTA_C = 0.6, 0.7
_K = [None]


def _load(path):
    stamp = os.path.splitext(os.path.basename(path))[0]
    return np.fromfile(f"{CS}/buffers/{stamp}_{_K[0]}.f32", dtype=np.float32)


def _init():
    F._init()
    F.wavio.load_cycle_pcm = _load


def _job(job):
    kind, stamp, rows, dp, dc = job
    _K[0] = kind
    return kind, F.force_cycle((stamp, rows, dp, dc))


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    if kind not in ("S", "I", "R3B"):
        sys.exit(__doc__)
    deltas = json.load(open(C.S + "\\deltas.json", encoding="utf-8"))
    assert abs(deltas["delta_p"] - DELTA_P) < 1e-9 and abs(deltas["delta_c"] - DELTA_C) < 1e-9, deltas
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    rows = pop["rows"]
    assert len(rows) == 12124
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r["stamp"], []).append(r)
    assert all(os.path.isfile(f"{CS}/buffers/{s}_{kind}.f32") for s in by), "a buffer is missing"
    jobs = [(kind, s, rl, DELTA_P, DELTA_C) for s, rl in by.items()]
    t0, n = time.time(), 0
    with open(f"{CS}/forced_{kind}.jsonl", "w", encoding="utf-8") as fh, mp.Pool(8, initializer=_init) as pool:
        for k, recs in pool.imap_unordered(_job, jobs):
            for rec in recs:
                rec["buf"] = k
                fh.write(json.dumps(rec) + "\n")
                n += 1
            fh.flush()
    assert n == 12124, n
    print(f"{kind}: {n} records in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
