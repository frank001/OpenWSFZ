#!/usr/bin/env python3
"""XC-PRIOR counter (spec 28627a82 + A1).  python xc_count.py   -> _qa-scratch\\xc-prior\\xc_result.json  (numbers only; run ONCE per frozen code).
Inputs: WSJT-X's ALL.TXT of 20261110_1817 (read here, text never written), the 500-cycle list, NHARD-CEIL arm N24's matchedbatch.csv (CQ-AP ON, v2 ON, nhard 24)."""
from __future__ import annotations

import collections
import csv
import datetime
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "ta-check")):
    sys.path.insert(0, p)
import xc_lib as L          # noqa: E402
import tc_groups as G       # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/xc-prior"
N24 = "D:/Projects/claude/_qa-scratch/nhard-ceil/arms/N24/matchedbatch.csv"
LIST = os.path.join(HERE, "..", "cq-ap", "live-session-cycle-list.txt")


def band_of(snr):
    return "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"


def main():
    os.makedirs(OUT, exist_ok=True)
    stamps = [l.strip()[:-4] for l in open(LIST) if l.strip()]
    assert len(stamps) == 500
    ts = [datetime.datetime.strptime(s, "%y%m%d_%H%M%S") for s in stamps]
    gaps = [(stamps[i], (ts[i + 1] - ts[i]).total_seconds()) for i in range(len(ts) - 1) if (ts[i + 1] - ts[i]).total_seconds() != L.CYCLE_S]
    ref = G.load_ref_night(set(stamps))
    assert G.U.load_instrument()[0].WS_CONF_DF == L.WINDOW_HZ
    shape = G.U.load_instrument()[0].shape_class
    mb = {}
    for r in csv.reader(open(N24)):
        if r and r[0] != "stamp":
            mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    nref = sum(len(v) for v in ref.values())
    matched = sum(len(v) for v in mb.values())
    assert (nref, matched, nref - matched) == (L.N_REF, L.N24_MATCHED, L.N_UNREACHED), (nref, matched)
    mcyc = []                                          # per cycle: [(text, freq, batch)] of the matched rows
    for s in stamps:
        rows = ref.get(s, [])
        mcyc.append([(rows[j][3], rows[j][2], b) for j, b in sorted(mb.get(s, {}).items())])
    n = len(stamps)
    nref_c = np.array([len(ref.get(s, [])) for s in stamps], dtype=float)
    e1_c, e2_c, eo_c = np.zeros(n), np.zeros(n), np.zeros(n)
    unreached = []
    e1_rows, e2_rows = [], []
    lag_e1, kind_e1, band_e1, batch_e1 = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    hashed = collections.Counter()
    snr_all, snr_e1 = [], []
    for i, s in enumerate(stamps):
        for j, (snr, dt, f, text) in enumerate(ref.get(s, [])):
            if j in mb.get(s, {}):
                continue
            snr_all.append(snr)
            k1, lag, pb = L.prior_hit((text, f), i, L.SAME_LAGS, mcyc)
            ko, _, _ = L.prior_hit((text, f), i, L.OPP_LAGS, mcyc)
            if ko == "E1":
                eo_c[i] += 1
            if k1 == "E1":
                e1_c[i] += 1
                snr_e1.append(snr)
                lag_e1[lag * L.CYCLE_S] += 1
                kind_e1[shape(text)] += 1
                band_e1[band_of(snr)] += 1
                batch_e1["batch1" if pb == 1 else "later"] += 1
                hashed["E1_hashed"] += "<" in text
            elif k1 == "E2":
                e2_c[i] += 1
                hashed["E2_hashed"] += "<" in text
                band_e1["E2:" + band_of(snr)] += 1
    # how common repetition is among the MATCHED rows (same rule, the row's own text vs earlier matched rows)
    rep_matched = 0
    for i, s in enumerate(stamps):
        rows = ref.get(s, [])
        for j in mb.get(s, {}):
            k, _, _ = L.prior_hit((rows[j][3], rows[j][2]), i, L.SAME_LAGS, mcyc)
            rep_matched += (k == "E1")
    idx = L.boot_idx(n)
    pp_e1, ci_e1 = L.pp_ci(e1_c, nref_c, idx)
    pp_e2, ci_e2 = L.pp_ci(e2_c, nref_c, idx)
    pp_eo, ci_eo = L.pp_ci(eo_c, nref_c, idx)
    e1, e2, eo = int(e1_c.sum()), int(e2_c.sum()), int(eo_c.sum())
    par = L.v_par(eo, e1)
    verdict = L.decide(ci_e1, par)
    q = lambda v: [float(x) for x in np.percentile(v, [25, 50, 75])] if v else None
    out = {"verdict": verdict, "V_CONT": {"gaps": gaps, "PASS": True}, "V_N": {"n_ref": nref, "matched": matched, "unreached": nref - matched, "PASS": True},
           "V_PAR": {"E_OPP": eo, "E1": e1, "bar_E_OPP_le_0.25_x_E1": bool(par), "gates": "PURSUE and BETWEEN only (A1)"},
           "E1": {"rows": e1, "pp_of_n_ref": pp_e1, "CI_pp": ci_e1, "share_of_unreached": e1 / (nref - matched)}, "E2_descriptive": {"rows": e2, "pp": pp_e2, "CI_pp": ci_e2},
           "E_OPP": {"rows": eo, "pp": pp_eo, "CI_pp": ci_eo},
           "descriptives": {"E1_by_band_and_E2_by_band": dict(band_e1), "E1_by_nearest_prior_s": dict(sorted(lag_e1.items())), "E1_by_message_kind": dict(kind_e1), "E1_prior_matched_batch1_vs_later": dict(batch_e1),
                            "SNR_unreached_all_q25_50_75": q(snr_all), "SNR_E1_q25_50_75": q(snr_e1), "unreached_all_by_band": dict(collections.Counter(band_of(x) for x in snr_all)),
                            "hashed": dict(hashed), "matched_rows_that_are_exact_repeats": {"rows": rep_matched, "share_of_matched": rep_matched / matched}}}
    json.dump(out, open(OUT + "/xc_result.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
