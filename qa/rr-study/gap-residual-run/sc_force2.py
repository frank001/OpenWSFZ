#!/usr/bin/env python3
"""SUB-COVER v2 (#273): GAP-RELOCATE's frozen forced legs (gr_forced.force_cycle, unchanged; delta_p 0.6 s, delta_c 0.7 s) on the O*v2 buffers. Same as sc_force.py, buffers from v2/.

    python sc_force2.py ostar2    every NR row and every hit, buffer OSTAR2                  -> v2/forced_OSTAR2.jsonl
    python sc_force2.py orc       the WSJT-X rows that route 2 used as the oracle (O-ORC)    -> v2/forced_ORC.jsonl
          For these rows ONLY, the target text for the forced legs is the candidate's text with '<' '>' stripped (the text route 2 verified as the same transmission by the consistency
          check; a bracketed text cannot be encoded, so the forced legs would call the row unencodable). Substituted in memory inside the worker; no text is written (HK-037).
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

SC = "D:/Projects/claude/_qa-scratch/sub-cover"
V2 = SC + "/v2"
GR = "D:/Projects/claude/_qa-scratch/gap-residual"
DELTA_P, DELTA_C = 0.6, 0.7
_K = [None]
_SUBST = set()


def _load(path):
    stamp = os.path.splitext(os.path.basename(path))[0]
    return np.fromfile(f"{V2}/buffers/{stamp}_{_K[0]}.f32", dtype=np.float32)


def _init(subst):
    F._init()
    F.wavio.load_cycle_pcm = _load
    if subst:
        F._W["ref"] = C.load_ref(set(C.selection_stamps()))
        for (stamp, idx) in subst:
            snr, dt, freq, text = F._W["ref"][stamp][idx]
            F._W["ref"][stamp][idx] = (snr, dt, freq, text.replace("<", "").replace(">", "").strip())


def _job(job):
    kind, stamp, rows, dp, dc = job
    _K[0] = kind
    return kind, F.force_cycle((stamp, rows, dp, dc))


def run_kind(kind, rows, out_path, subst=(), workers=8):
    by = collections.OrderedDict()
    for r in rows:
        if os.path.isfile(f"{V2}/buffers/{r['stamp']}_{kind}.f32"):
            by.setdefault(r["stamp"], []).append(r)
    jobs = [(kind, s, rl, DELTA_P, DELTA_C) for s, rl in by.items()]
    t0, n = time.time(), 0
    with open(out_path, "w", encoding="utf-8") as fh, mp.Pool(workers, initializer=_init, initargs=(tuple(subst),)) as pool:
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ostar2":
        hits = [r for r in rows if r["matched"]]
        tg = tags()
        nr = [r for r in rows if tg.get((r["stamp"], r["idx"]), {}).get("pop") == "NR"]
        assert len(hits) == 9931 and len(nr) == 1589, (len(hits), len(nr))
        n, secs = run_kind("OSTAR2", hits + nr, f"{V2}/forced_OSTAR2.jsonl")
    elif cmd == "orc":
        o2 = json.load(open(f"{V2}/ostar2.json"))["cycles"]
        want = [(c["stamp"], r["idx"]) for c in o2 for r in c["route2"]]
        by_key = {(r["stamp"], r["idx"]): r for r in rows}
        sel = [by_key[k] for k in want]
        n, secs = run_kind("OSTAR2", sel, f"{V2}/forced_ORC.jsonl", subst=want)
    else:
        sys.exit(__doc__)
    print(f"{n} (row, buffer) records in {secs:.0f}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
