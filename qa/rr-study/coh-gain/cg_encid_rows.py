#!/usr/bin/env python
"""COH-GAIN Amendment 9 (ENC-ID), spec 18 + 18.1: validity rows and the reading, as code. Input: encid_rows.csv (numbers and flags only), encid_reach.csv. Output: analysis_encid.json.

P = sum(enc_match) / 795 over the X rows; CI: blocks of 8 cycles within each sample, pooled, B = 10,000, seed 20261006 (as before). P without placeholder rows is shown as well (18.1 item 1).
Validity: Y1 every row reproduces; Y2 enc_match = 0 on all 19 OSD i3 = 4 rows; Y3 the synthetic round trip (tests/test_cg_encid.py, committed before Y1; recorded here only as the instruction to run it);
Y4 the shuffled-truth control: y4_match <= 2 % of the 795.
Reading (exclusive, first match, only if Y1, Y2 and Y4 pass): ENC-CONFIRMED iff CI_lo(P) >= 0.80; ENC-REJECTED iff CI_hi(P) < 0.50; else ENC-PARTIAL.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_encid as EN  # noqa: E402
import cg_select as SEL  # noqa: E402

ANALYSIS_NAME = "analysis_encid.json"


def load(path=None):
    out = []
    for r in csv.DictReader(open(path or EN.OUT_CSV, newline="", encoding="utf-8")):
        d = dict(r)
        for k in ("sample", "cycle_index", "widx", "w1_ok", "enc_match", "call_eq", "hash_eq", "icq", "nrpt", "t_has_placeholder", "m1", "m2"):
            d[k] = int(d[k])
        d["y4_match"] = int(d["y4_match"]) if d["y4_match"] != "" else ""
        out.append(d)
    return out


def reading(ci_lo, ci_hi):
    if ci_lo >= EN.P_CONFIRMED:
        return "ENC-CONFIRMED"
    if ci_hi < EN.P_REJECTED:
        return "ENC-REJECTED"
    return "ENC-PARTIAL"


def block_bootstrap(rows_x, cycles, value, block=CG.BLOCK_CYCLES):
    num, den = [], []
    for res, order in sorted(cycles.items()):
        per = {c: [0, 0] for c in order}
        for r in rows_x:
            if r["sample"] == res:
                a = per.setdefault(r["cycle_index"], [0, 0])
                a[1] += 1
                a[0] += value(r)
        for i in range(0, len(order), block):
            ch = order[i:i + block]
            num.append(sum(per[c][0] for c in ch))
            den.append(sum(per[c][1] for c in ch))
    num, den = np.array(num, dtype=float), np.array(den, dtype=float)
    rng = np.random.default_rng(CG.SEED)
    idx = rng.integers(0, len(num), size=(CG.B_RESAMPLES, len(num)))
    d = den[idx].sum(axis=1)
    est = num[idx].sum(axis=1) / np.where(d > 0, d, np.nan)
    return float(num.sum() / den.sum()), [float(v) for v in np.nanpercentile(est, [2.5, 97.5])]


def analyse(rows, cycles=None, check_n=True):
    x = [r for r in rows if r["kind"] == "X"]
    osd = [r for r in rows if r["kind"] == "OSD"]
    if check_n:
        assert len(x) == EN.N_X and len(osd) == EN.N_OSD, (len(x), len(osd))
    cycles = cycles or {res: sorted({r[0] for r in json.load(open(SEL.rows_path(res)))["rows"]}) for res in sorted({r["sample"] for r in rows})}
    y1 = all(r["w1_ok"] for r in rows)
    y2_n = sum(r["enc_match"] for r in osd)
    y4_n = sum(1 for r in x if r["y4_match"] == 1)
    y4 = (y4_n / max(1, len(x))) <= EN.Y4_TOLERANCE
    valid = bool(y1 and y2_n == 0 and y4)
    p, ci = block_bootstrap(x, cycles, lambda r: r["enc_match"])
    ph = [r for r in x if r["t_has_placeholder"] == 1]
    nph = [r for r in x if r["t_has_placeholder"] == 0]
    p_nph = (sum(r["enc_match"] for r in nph) / len(nph)) if nph else None
    return {"validity": {"Y1": {"pass": bool(y1), "not_reproduced": sum(1 for r in rows if not r["w1_ok"])},
                         "Y2": {"pass": y2_n == 0, "osd_rows": len(osd), "osd_enc_match": y2_n},
                         "Y3": {"note": "synthetic round trip is tests/test_cg_encid.py, committed before Y1; run it with this analysis"},
                         "Y4": {"pass": bool(y4), "shuffled_enc_match": y4_n, "of": len(x), "share": y4_n / max(1, len(x)), "tolerance": EN.Y4_TOLERANCE}},
            "valid": valid, "n_x": len(x), "P": p, "P_ci95": ci, "reading": reading(ci[0], ci[1]) if valid else "NO READING",
            "enc_match": sum(r["enc_match"] for r in x), "call_eq": sum(r["call_eq"] for r in x), "hash_eq_given_call_eq": sum(1 for r in x if r["call_eq"] and r["hash_eq"]),
            "icq_rows": sum(r["icq"] for r in x), "placeholder_rows": len(ph), "placeholder_enc_match": sum(r["enc_match"] for r in ph), "P_without_placeholder_rows": p_nph,
            "mutants": {"m1_keep_RR73": {"enc_match": sum(r["m1"] for r in x), "rows_moved": sum(1 for r in x if r["m1"] != r["enc_match"])},
                        "m2_drop_slash_P": {"enc_match": sum(r["m2"] for r in x), "rows_moved": sum(1 for r in x if r["m2"] != r["enc_match"])}}}


def analyse_reach(path=None):
    rows = list(csv.DictReader(open(path or EN.REACH_CSV, newline="", encoding="utf-8")))
    table = {}
    for r in rows:
        key = f"{r['set']} {'right' if r['ok'] == '1' else 'wrong'}: X i3={r['i3x'] or 'none'} vs T i3={r['i3t']}"
        table[key] = table.get(key, 0) + 1
    t4 = {s: {"rows": 0, "t_i3_1_x_i3_4": 0, "x_i3_4": 0} for s in ("C3", "G")}
    for r in rows:
        a = t4[r["set"]]
        a["rows"] += 1
        a["x_i3_4"] += r["i3x"] == "4"
        a["t_i3_1_x_i3_4"] += r["i3x"] == "4" and r["i3t"] == "1"
    return {"pairs": dict(sorted(table.items())), "summary": t4, "w1_not_reproduced": sum(1 for r in rows if r["w1_ok"] != "1"), "rows": len(rows)}
