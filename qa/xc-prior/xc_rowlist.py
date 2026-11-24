#!/usr/bin/env python3
"""XC-PRIOR: the frozen E1 / E2 / E-OPP ROW LISTS for Stage 1 (numbers only: stamp, WSJT-X row index, the nearest prior's cycle lag and its stamp and row index, the prior's matched batch).
Uses the frozen xc_lib (blob 586218d9) unchanged and the frozen counter's inputs; ASSERTS its counts equal the frozen run's (E1 520, E2 171, E-OPP 1) before writing.
    python xc_rowlist.py   -> _qa-scratch\\xc-prior\\xc_rowlist.json      HK-037: text read in memory only; no text is written."""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "ta-check")):
    sys.path.insert(0, p)
import xc_lib as L          # noqa: E402
import xc_count as C        # noqa: E402
import tc_groups as G       # noqa: E402


def find_prior(text, f, i, lags, mcyc, stamps, mb_idx):
    """the prior row xc_lib.prior_hit found for kind E1: nearest lag first, first matching row in that cycle's matched order."""
    for k in lags:
        j = i - k
        if j < 0:
            continue
        for (ptext, pf, pb), pidx in zip(mcyc[j], mb_idx[j]):
            if ptext == text and abs(pf - f) <= L.WINDOW_HZ:
                return k, stamps[j], pidx, pb
    return None


def main():
    stamps = [l.strip()[:-4] for l in open(C.LIST) if l.strip()]
    ref = G.load_ref_night(set(stamps))
    mb = {}
    for r in csv.reader(open(C.N24)):
        if r and r[0] != "stamp":
            mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    mcyc, mb_idx = [], []
    for s in stamps:
        rows = ref.get(s, [])
        ks = sorted(mb.get(s, {}))
        mcyc.append([(rows[j][3], rows[j][2], mb[s][j]) for j in ks])
        mb_idx.append(ks)
    out = {"E1": [], "E2": [], "E_OPP": []}
    for i, s in enumerate(stamps):
        for j, (snr, dt, f, text) in enumerate(ref.get(s, [])):
            if j in mb.get(s, {}):
                continue
            k1, lag, pb = L.prior_hit((text, f), i, L.SAME_LAGS, mcyc)
            ko, _, _ = L.prior_hit((text, f), i, L.OPP_LAGS, mcyc)
            if ko == "E1":
                lagk, ps, pi, pbb = find_prior(text, f, i, L.OPP_LAGS, mcyc, stamps, mb_idx)
                out["E_OPP"].append({"stamp": s, "idx": j, "snr": snr, "lag_s": lagk * L.CYCLE_S, "prior_stamp": ps, "prior_idx": pi, "prior_batch": pbb})
            if k1 == "E1":
                lagk, ps, pi, pbb = find_prior(text, f, i, L.SAME_LAGS, mcyc, stamps, mb_idx)
                assert lagk == lag and pbb == pb
                out["E1"].append({"stamp": s, "idx": j, "snr": snr, "freq": f, "lag_s": lagk * L.CYCLE_S, "prior_stamp": ps, "prior_idx": pi, "prior_batch": pbb})
            elif k1 == "E2":
                out["E2"].append({"stamp": s, "idx": j, "snr": snr, "freq": f, "lag_s": lag * L.CYCLE_S, "prior_batch": pb})
    frozen = json.load(open(C.OUT + "/xc_result.json"))
    assert (len(out["E1"]), len(out["E2"]), len(out["E_OPP"])) == (frozen["E1"]["rows"], frozen["E2_descriptive"]["rows"], frozen["E_OPP"]["rows"]) == (520, 171, 1), (len(out["E1"]), len(out["E2"]), len(out["E_OPP"]))
    json.dump(out, open(C.OUT + "/xc_rowlist.json", "w"))
    print({k: len(v) for k, v in out.items()}, "written; counts equal the frozen run's")


if __name__ == "__main__":
    main()
