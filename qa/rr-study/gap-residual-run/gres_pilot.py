#!/usr/bin/env python3
"""GAP-RESIDUAL pilot (spec 74a38158 + Amendment 1 section 9, ea7496d1). The Captain's go: "run the pilot first" (2026-10-29).

  0d : P_ctrl,R per STRATUM on the 40 PILOT cycles, BEFORE any N row is forced:
         (i)  batch 2 / batch 3 K rows (tag b23)        -> forced PRIMARY leg on R2 u R3   (bar 0.90)
         (ii) residual-only fallback K rows (tag fb_res) -> forced COHERENT legs (V3 any gate u walk) on R2 u R3 (bar 0.90)
       Wilson 95 % CI beside each. STOP per stratum when below the bar. Also the union of all legs, for information.
  0e : byte compare of the captured O with the PCM gr_forced.py used (the WAV); if not identical, the forced legs on O give GAP-RELOCATE's class
       for >= 0.98 of the pilot's M rows.
The forced legs are GAP-RELOCATE's own code (gr_forced.force_cycle); ONLY the PCM argument changes (the loader is patched to read the captured buffer).
Only counts, flags and positions are written (stamp + row index + numbers); message text is read in memory by the legs and never persisted.
"""
from __future__ import annotations

import collections
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import gr_item2 as I2       # noqa: E402

CAP = "D:/Projects/claude/_qa-scratch/gap-residual/cap/off"
OUT = "D:/Projects/claude/_qa-scratch/gap-residual"
PILOT_CYCLES = 40
P_BAR = 0.90
O_AGREE_BAR = 0.98
DELTA_P, DELTA_C = 0.6, 0.7                      # frozen, GAP-RELOCATE deltas.json (asserted against the file below)
assert PILOT_CYCLES == 40 and P_BAR == 0.90 and O_AGREE_BAR == 0.98

_K = [None]


def _load_captured(path):
    stamp = os.path.splitext(os.path.basename(path))[0]
    return np.fromfile(f"{CAP}/buffers/{stamp}_{_K[0]}.f32", dtype=np.float32)


def _init():
    F._init()
    F.wavio.load_cycle_pcm = _load_captured          # the ONLY change to the legs: the PCM comes from the capture


def _job(job):
    kind, stamp, rows, dp, dc = job
    _K[0] = kind
    return kind, F.force_cycle((stamp, rows, dp, dc))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def run_kind(rows_by_kind, out_path, workers=8):
    jobs = []
    for kind, rows in rows_by_kind.items():
        by = collections.OrderedDict()
        for r in rows:
            if os.path.isfile(f"{CAP}/buffers/{r['stamp']}_{kind}.f32"):
                by.setdefault(r["stamp"], []).append(r)
        jobs += [(kind, s, rl, DELTA_P, DELTA_C) for s, rl in by.items()]
    t0 = time.time()
    nrow = 0
    with open(out_path, "w", encoding="utf-8") as fh, mp.Pool(workers, initializer=_init) as pool:
        for kind, recs in pool.imap_unordered(_job, jobs):
            for rec in recs:
                rec["buf"] = kind
                fh.write(json.dumps(rec) + "\n")
                nrow += 1
            fh.flush()
    return nrow, time.time() - t0


def main():
    cmd = sys.argv[1]
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    d = json.load(open(C.S + "\\deltas.json"))
    assert abs(d["delta_p"] - DELTA_P) < 1e-9 and abs(d["delta_c"] - DELTA_C) < 1e-9, d
    stamps = pop["stamps"]
    pilot = set(stamps[:PILOT_CYCLES])
    # the capture must hold every pilot cycle
    idx = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(f"{CAP}/capture_index.tsv", encoding="utf-8")}
    missing = [s for s in pilot if s not in idx]
    assert not missing, f"capture index lacks {len(missing)} pilot cycles"
    rows = pop["rows"]
    key = {(r["stamp"], r["idx"]): r for r in rows}

    if cmd == "0d":
        ctrl = [r for r in rows if r["K"] and r["stamp"] in pilot and r["tag"] in ("b23", "fb_res")]
        cnt = collections.Counter(r["tag"] for r in ctrl)
        print("pilot K control rows by tag:", dict(cnt))
        n, secs = run_kind({"R2": ctrl, "R3": ctrl}, f"{OUT}/forced_pilot_0d.jsonl")
        print(f"forced {n} (row, buffer) records in {secs:.0f}s")
        recs = [json.loads(x) for x in open(f"{OUT}/forced_pilot_0d.jsonl", encoding="utf-8")]
        per = collections.defaultdict(lambda: {"fp": False, "v3": False, "walk": False, "unenc": False})
        for r in recs:
            k = (r["stamp"], r["idx"])
            if r.get("unencodable"):
                per[k]["unenc"] = True
                continue
            per[k]["fp"] |= bool(r["fp"]["found"])
            per[k]["v3"] |= bool(r["fc"]["v3_match"] and r["fc"]["gated"] is not None)
            per[k]["walk"] |= bool(r["walk"]["match"])
        res = {}
        for tag, leg_name, legs in (("b23", "primary", ("fp",)), ("fb_res", "coherent (V3 any gate u walk)", ("v3", "walk"))):
            ks = [k for k in per if key[k]["tag"] == tag and not per[k]["unenc"]]
            hit = sum(1 for k in ks if any(per[k][l] for l in legs))
            uni = sum(1 for k in ks if per[k]["fp"] or per[k]["v3"] or per[k]["walk"])
            lo, hi = wilson(hit, len(ks))
            ulo, uhi = wilson(uni, len(ks))
            res[tag] = {"validates": leg_name, "n": len(ks), "recovered": hit, "P": hit / len(ks) if ks else None, "wilson95": [lo, hi],
                        "STOP": (hit / len(ks) < P_BAR) if ks else True,
                        "union_all_legs": {"recovered": uni, "P": uni / len(ks) if ks else None, "wilson95": [ulo, uhi]},
                        "excluded_unencodable": sum(1 for k in per if key[k]["tag"] == tag and per[k]["unenc"])}
        json.dump(res, open(f"{OUT}/pilot_0d.json", "w"), indent=1)
        print(json.dumps(res, indent=1))
        return
    if cmd == "0e":
        # byte compare O with the WAV PCM gr_forced.py used
        import wavio
        ident = 0
        ratios = []
        for s in sorted(pilot):
            o = np.fromfile(f"{CAP}/buffers/{s}_O.f32", dtype=np.float32)
            w = np.ascontiguousarray(wavio.load_cycle_pcm(os.path.join(C.WAVDIR, s + ".wav")), dtype=np.float32)
            if o.shape == w.shape and o.tobytes() == w.tobytes():
                ident += 1
            else:
                m = np.abs(w) > 1e-6
                ratios.append(float(np.median(o[m] / w[m])) if m.any() else float("nan"))
        res = {"pilot_cycles": len(pilot), "O_identical_to_wav_pcm": ident}
        if ident < len(pilot):
            res["scale_ratio_O_over_wav"] = {"n": len(ratios), "min": min(ratios), "max": max(ratios)}
            mrows = [r for r in rows if r["stamp"] in pilot and not r["matched"]]
            old = {}
            for line in open(C.S + "\\forced_main.jsonl", encoding="utf-8"):
                r = json.loads(line)
                old[(r["stamp"], r["idx"])] = r
            n, secs = run_kind({"O": mrows}, f"{OUT}/forced_pilot_0e.jsonl")
            new = {}
            for line in open(f"{OUT}/forced_pilot_0e.jsonl", encoding="utf-8"):
                r = json.loads(line)
                new[(r["stamp"], r["idx"])] = r
            same = tot = 0
            for r in mrows:
                k = (r["stamp"], r["idx"])
                a, b = I2.classify(r, old.get(k)), I2.classify(r, new.get(k))
                tot += 1
                same += (a == b)
            res.update({"M_rows": tot, "same_class": same, "agreement": same / tot, "bar": O_AGREE_BAR, "PASS": same / tot >= O_AGREE_BAR,
                        "forced_records": n, "seconds": secs, "seconds_per_record": secs / n if n else None})
        else:
            res["0e"] = "IMPLIED (O byte-identical to the WAV PCM in every pilot cycle)"
        json.dump(res, open(f"{OUT}/pilot_0e.json", "w"), indent=1)
        print(json.dumps(res, indent=1))
        return
    raise SystemExit("usage: gres_pilot.py 0d|0e")


if __name__ == "__main__":
    mp.freeze_support()
    main()
