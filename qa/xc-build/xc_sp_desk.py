#!/usr/bin/env python3
"""200-pair numeric reference for the remedy build's S_P: the desk detector (xt_lib grid, coherent_extract) on the pairs of the first numeric comparison (_qa-scratch/xc-review/xcmp/pairs.tsv: residual buffer path, centre frequency, centre dt in WSJT-X's convention, 79 tones).
Writes S_E*, the argmax and S_P (frame symbols 43..71 at the S_E* argmax) per pair; numbers only.   python -I xc_sp_desk.py <pairs.tsv> <out json>"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "xc-template"))
sys.path.insert(0, os.path.join(HERE, "..", "rr-study", "n2-coherent-llr-extractor"))
import xc_remedy_fixtures as RF   # noqa: E402  (search_sp: S_E*, argmax, S_P at the argmax, the xt_lib grid)


def work(line):
    p = line.rstrip("\n").split("\t")
    pcm = np.fromfile(p[0], dtype=np.float32)
    tones = [int(x) for x in p[3].split(",")]
    S, arg, sp = RF.search_sp(pcm, tones, float(p[1]), float(p[2]))
    return {"S_E": S, "S_P": sp, "af": arg[0], "adt": arg[1]}


def main(pairs, out):
    lines = open(pairs).read().splitlines()
    assert len(lines) == 200, len(lines)
    with mp.Pool(8) as pool:
        res = pool.map(work, lines, chunksize=4)
    json.dump(res, open(out, "w"))
    print("desk done", len(res), "S_E range", min(r["S_E"] for r in res), max(r["S_E"] for r in res), "S_P range", min(r["S_P"] for r in res), max(r["S_P"] for r in res))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
