#!/usr/bin/env python3
"""CS-CEIL V-REPRO (spec 3 + A1.4): the forced legs IN PLACE on the stored buffers (R3; R2 in the 18 cycles without R3) for CS-NR (700), CTRL-HIT (300) and CTRL-WEAK (73), against
NR-TAX's per-row decodability.  Expected: CS-NR and CTRL-WEAK all NOT decodable, CTRL-HIT all decodable.  PASS iff CS-NR and CTRL-HIT agree in >= 98 % of rows AND every CTRL-WEAK row
is not decodable in place (A1.4: 'all').  Also reported: determinism against NR-TAX's own stored records for the same buffer.  gr_forced.force_cycle is called UNCHANGED; only the PCM
comes from the stored buffer (the same single change as sc_refit_force.py).  Writes numbers only.  No relocated output exists in this step."""
from __future__ import annotations

import collections
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "..", "rr-study")
for p in (HERE, os.path.join(RR, "gap-relocate-run"), os.path.join(RR, "gap-residual-run")):
    sys.path.insert(0, p)
import cc_lib as L          # noqa: E402
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402

GR = "D:/Projects/claude/_qa-scratch/gap-residual"
OUT = "D:/Projects/claude/_qa-scratch/cs-ceil"
_BUF = {}


def _load(path):
    stamp = os.path.splitext(os.path.basename(path))[0]
    p3 = f"{GR}/cap/off/buffers/{stamp}_R3.f32"
    p = p3 if os.path.isfile(p3) else f"{GR}/cap/off/buffers/{stamp}_R2.f32"
    return np.fromfile(p, dtype=np.float32)


def _init():
    F._init()
    F.wavio.load_cycle_pcm = _load


def _job(job):
    return F.force_cycle(job)


def main():
    G = json.load(open(OUT + "/frozen/cc_groups.json"))["rows"]
    by = collections.OrderedDict()
    for r in G:
        by.setdefault(r["stamp"], []).append({"idx": r["idx"]})
    flags = {(r["stamp"], r["idx"]): r for r in G}
    jobs = [(s, rl, L.DELTA_P, L.DELTA_C) for s, rl in by.items()]
    t0 = time.time()
    recs = {}
    with mp.Pool(8, initializer=_init) as pool:
        for out in pool.imap_unordered(_job, jobs):
            for rec in out:
                recs[(rec["stamp"], rec["idx"])] = rec
    old = {}
    for line in open(GR + "/forced_all.jsonl", encoding="utf-8"):
        r = json.loads(line)
        k = (r["stamp"], r["idx"])
        if k in flags and r["buf"] == flags[k]["buf"]:
            old[k] = r
    res = {"seconds": round(time.time() - t0), "rows_forced": len(recs)}
    for g, flag, expect in (("CS-NR", "in_CS_NR", False), ("CTRL-HIT", "in_CTRL_HIT", True), ("CTRL-WEAK", "in_CTRL_WEAK", False)):
        keys = [k for k, r in flags.items() if r[flag]]
        agree = sum(1 for k in keys if L.either(recs[k]) == expect)
        unenc = sum(1 for k in keys if recs[k].get("unencodable"))
        same_as_stored = sum(1 for k in keys if k in old and L.either(old[k]) == L.either(recs[k]))
        res[g] = {"rows": len(keys), "agree_with_expected": agree, "share": agree / len(keys), "unencodable": unenc, "same_as_NR_TAX_stored_record": same_as_stored,
                  "stored_records_found": sum(1 for k in keys if k in old)}
    ok = res["CS-NR"]["share"] >= L.V_REPRO and res["CTRL-HIT"]["share"] >= L.V_REPRO and res["CTRL-WEAK"]["agree_with_expected"] == res["CTRL-WEAK"]["rows"]
    res["V-REPRO"] = {"PASS": bool(ok), "bar": L.V_REPRO, "CTRL-WEAK_bar": "all rows not decodable in place (A1.4)"}
    json.dump(res, open(OUT + "/frozen/v_repro.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    mp.freeze_support()
    main()
