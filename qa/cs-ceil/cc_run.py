#!/usr/bin/env python3
"""CS-CEIL relocated run (spec arch/cs-model-ceiling 6d911263 + A1 fc82317a + A2 e3e5feca).  QA tooling; no src/ or native/ change; needs the PC (8 workers: about 1,100 fits and forced decodes).
    python cc_run.py [--limit N] [--out DIR]     -> <out>/relocated.jsonl   (default D:/Projects/claude/_qa-scratch/cs-ceil/run)
For every row of the four groups that HAS a slot in the frozen table (cc_groups.json, rule = summary.rule_that_runs):
  1. analytic(base) of the stored R3 (R2 in the 18 cycles without R3); the product fitter ft8_subfeas_fit_signal (data-aided from the WSJT-X text's tones; start (dt + DELTA_P, freq)) -> shat;
     rc -3 = fit-zero (no copy; counted by the readout);
  2. analytic(shat), frequency-shifted by delta = f_s + 5 - f_row, real part; B = base + copy;
  3. gr_forced.force_cycle UNCHANGED at (f_row + delta, same dt) on B: only the PCM loader and the row's frequency are substituted (the same single change as sc_refit_force.py).
HK-037: the text is read in memory by the worker and never written; the output holds stamps, indices, flags and numbers only.  Rows with no slot are written with slot=false (no fit, no copy)."""
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
import sc_build as B        # noqa: E402

GR = "D:/Projects/claude/_qa-scratch/gap-residual"
CAP = GR + "/cap/off"
OUT = "D:/Projects/claude/_qa-scratch/cs-ceil"
_S = {"ref0": None, "base": None}


def _init():
    B._init()
    F._init()
    _S["ref0"] = C.load_ref(set(C.selection_stamps()))


def _loader(path):
    return _S["base"]


def job(args):
    stamp, rows = args                       # rows: list of frozen-table rows of this cycle (with a slot)
    p3 = f"{CAP}/buffers/{stamp}_R3.f32"
    p = p3 if os.path.isfile(p3) else f"{CAP}/buffers/{stamp}_R2.f32"
    base = np.fromfile(p, dtype=np.float32)
    assert base.shape == (L.PCM,)
    re_b, im_b = B.analytic(base)
    out = []
    for r in rows:
        rec = {"stamp": stamp, "idx": r["idx"], "buf": "R3" if p == p3 else "R2", "delta_hz": r["delta_hz"], "f_s": r["f_s"], "fit_rc": None, "fit_zero": False, "unencodable": False, "decodable": False}
        snr, dt, freq, text = _S["ref0"][stamp][r["idx"]]
        assert freq == r["freq"] and abs(dt - r["dt"]) < 1e-9
        tones = B.encode(text)
        if tones is None:
            rec["unencodable"] = True
            out.append(rec)
            continue
        rc, shat = B.fit(re_b, im_b, tones, np.float32(dt + L.DELTA_P), np.float32(freq))
        rec["fit_rc"] = rc
        if rc == -3:
            rec["fit_zero"] = True
            out.append(rec)
            continue
        rec["amp_rms"] = float(np.sqrt(np.mean(shat.astype(np.float64) ** 2)))
        re_s, im_s = B.analytic(shat)
        copy = L.shift_copy(shat, re_s, im_s, r["delta_hz"])
        rel = (base + copy).astype(np.float32)
        _S["base"] = rel
        F.wavio.load_cycle_pcm = _loader
        lst = list(_S["ref0"][stamp])
        lst[r["idx"]] = (snr, dt, float(freq) + r["delta_hz"], text)
        F._W["ref"] = dict(_S["ref0"])
        F._W["ref"][stamp] = lst
        f = F.force_cycle((stamp, [{"idx": r["idx"]}], L.DELTA_P, L.DELTA_C))[0]
        rec.update({"fp_found": bool((f.get("fp") or {}).get("found")), "fc_v3_match": bool((f.get("fc") or {}).get("v3_match")), "decodable": L.either(f),
                    "fp_wrong": int((f.get("fp") or {}).get("wrong", 0)), "fc_v3_wrong": bool((f.get("fc") or {}).get("v3_wrong"))})
        out.append(rec)
    return out


def main():
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    od = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT + "/run"
    os.makedirs(od, exist_ok=True)
    G = json.load(open(OUT + "/frozen/cc_groups.json"))
    assert G["summary"]["rule_that_runs"] in ("two-sided", "upper")
    deltas = json.load(open(C.S + "\\deltas.json", encoding="utf-8"))
    assert abs(deltas["delta_p"] - L.DELTA_P) < 1e-9 and abs(deltas["delta_c"] - L.DELTA_C) < 1e-9
    by = collections.OrderedDict()
    for r in G["rows"]:
        if r["f_s"] is not None:
            by.setdefault(r["stamp"], []).append(r)
    jobs = list(by.items())
    if lim:
        jobs = jobs[:lim]
    t0, n = time.time(), 0
    with open(od + "/relocated.jsonl", "w", encoding="utf-8") as fh, mp.Pool(8, initializer=_init) as pool:
        for recs in pool.imap_unordered(job, jobs):
            for rec in recs:
                fh.write(json.dumps(rec) + "\n")
                n += 1
            fh.flush()
    print(f"{n} rows relocated in {time.time() - t0:.0f}s -> {od}/relocated.jsonl (rule {G['summary']['rule_that_runs']})")


if __name__ == "__main__":
    mp.freeze_support()
    main()
