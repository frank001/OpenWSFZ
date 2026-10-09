#!/usr/bin/env python
"""COH-GAIN Amendment 8 (FIELD-ID), spec 17 + 17.1: classes, validity rows and the reading, as code. Input: field_rows.csv (numbers and flags only). Output: analysis_field.json.

Classes (first match wins): E-ENC (t_alt_eq = 1) -> E-ADJ (adj != none) -> E-QSO (c1_eq AND c2_eq) -> E-G2 (g2 = 1) -> E-HASH (n_unenc_near >= 1) -> E-RESIDUAL.
E = (E-ADJ + E-QSO) / 917   (17.2; E-ENC stays a class but is 0 by construction; E-G2 is NOT in the numerator: its 321 was known before the run, 17.1 B]. CI: blocks of 8 cycles within each sample, pooled, B = 10,000, seed 20261006.
Validity: X1 every X and OSD row reproduces (C3 and G), X2 at most 5 % of the 215 OSD rows in E-ENC / E-ADJ / E-QSO (0 expected), X3 the identity packing round-trips on every encodable row.
Reading (exclusive, first match, only when X1-X3 pass): E-EXPLAINED iff CI_lo(E) >= 0.50; E-RESIDUAL iff CI_hi(E) < 0.50 (no claim about false decodes); else E-MIXED.
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
import cg_field as FD  # noqa: E402
import cg_select as SEL  # noqa: E402

N_X = 917
N_OSD = 215
HALF = 0.50                 # the "most of them" decision value, as WRONG-ID (17, HK-038: not carried)
X2_TOLERANCE = 0.05         # the W2 comparator tolerance (17, HK-038: not carried)
CLASS_ORDER = ("E-ENC", "E-ADJ", "E-QSO", "E-G2", "E-HASH", "E-RESIDUAL")
NUMERATOR = ("E-ADJ", "E-QSO")             # 17.2: E-ENC cannot fire with this instrument (t_alt_eq = 0 by construction), so it is out of E
ANALYSIS_NAME = "analysis_field.json"
assert N_X == 917 and N_OSD == 215 and "E-G2" not in NUMERATOR


def classify(r):
    """r: a field_rows.csv record (typed). First match wins."""
    if r["t_alt_eq"] == 1:
        return "E-ENC"
    if r["adj"] != "none":
        return "E-ADJ"
    if r["c1_eq"] == 1 and r["c2_eq"] == 1:
        return "E-QSO"
    if r["g2"] == 1:
        return "E-G2"
    if r["n_unenc_near"] != "" and r["n_unenc_near"] >= 1:
        return "E-HASH"
    return "E-RESIDUAL"


def load(path=None):
    out = []
    for r in csv.DictReader(open(path or FD.OUT_CSV, newline="", encoding="utf-8")):
        d = dict(r)
        for k in ("sample", "cycle_index", "widx", "w1_ok", "w1g_ok", "c1_eq", "c2_eq", "rpt_eq", "t_alt_eq", "g2"):
            d[k] = int(d[k])
        for k in ("i3x", "n3x", "i3t", "n3t", "n_unenc_near", "x3_ok"):
            d[k] = int(d[k]) if d[k] != "" else ""
        d["adj"] = d["adj"] if d["adj"] == "none" else int(d["adj"])
        out.append(d)
    return out


def reading(ci_lo, ci_hi, half=HALF):
    if ci_lo >= half:
        return "E-EXPLAINED"
    if ci_hi < half:
        return "E-RESIDUAL"
    return "E-MIXED"


def block_bootstrap_e(rows_x, cycles, block=CG.BLOCK_CYCLES):
    """E = numerator-class share of the X rows; blocks of `block` cycles within each sample, pooled."""
    num, den = [], []
    for res, order in sorted(cycles.items()):
        per = {c: [0, 0] for c in order}
        for r in rows_x:
            if r["sample"] == res:
                a = per.setdefault(r["cycle_index"], [0, 0])
                a[1] += 1
                a[0] += classify(r) in NUMERATOR
        for i in range(0, len(order), block):
            ch = order[i:i + block]
            num.append(sum(per[c][0] for c in ch))
            den.append(sum(per[c][1] for c in ch))
    num, den = np.array(num, dtype=float), np.array(den, dtype=float)
    rng = np.random.default_rng(CG.SEED)
    idx = rng.integers(0, len(num), size=(CG.B_RESAMPLES, len(num)))
    d = den[idx].sum(axis=1)
    est = num[idx].sum(axis=1) / np.where(d > 0, d, np.nan)
    return float(num.sum() / den.sum()), [float(v) for v in np.nanpercentile(est, [2.5, 97.5])], len(num)


def analyse(rows, cycles=None, check_n=True):
    x = [r for r in rows if r["kind"] == "X"]
    osd = [r for r in rows if r["kind"] == "OSD"]
    if check_n:
        assert len(x) == N_X and len(osd) == N_OSD, (len(x), len(osd))
    cycles = cycles or {res: sorted({r[0] for r in json.load(open(SEL.rows_path(res)))["rows"]}) for res in sorted({r["sample"] for r in rows})}
    cls_x = {c: sum(1 for r in x if classify(r) == c) for c in CLASS_ORDER}
    cls_o = {c: sum(1 for r in osd if classify(r) == c) for c in CLASS_ORDER}
    x1 = all(r["w1_ok"] and r["w1g_ok"] for r in rows)
    x2_n = sum(cls_o[c] for c in NUMERATOR)
    x2 = (x2_n / max(1, len(osd))) <= X2_TOLERANCE
    x3 = all(r["x3_ok"] == 1 for r in rows if r["x3_ok"] != "")
    e, ci, nb = block_bootstrap_e(x, cycles)
    valid = bool(x1 and x2 and x3)
    out = {"validity": {"X1": {"pass": bool(x1), "not_reproduced": sum(1 for r in rows if not (r["w1_ok"] and r["w1g_ok"]))},
                        "X2": {"pass": bool(x2), "osd_in_numerator_classes": x2_n, "osd_rows": len(osd), "osd_class_counts": cls_o},
                        "X3": {"pass": bool(x3), "failures": sum(1 for r in rows if r["x3_ok"] == 0)}},
           "valid": valid, "x_class_counts": cls_x, "n_x": len(x),
           "E": e, "E_ci95": ci, "n_blocks": nb, "reading": reading(ci[0], ci[1]) if valid else "NO READING",
           "descriptive": {
               "layout_x": {k: sum(1 for r in x if r["layout"] == k) for k in sorted({r["layout"] for r in x})},
               "type_pairs_x": {f"{r['i3x']}/{r['n3x']} vs {r['i3t']}/{r['n3t']}": 0 for r in x[:0]},
               "adj_counts_x": {str(k): sum(1 for r in x if r["adj"] == k) for k in (-2, -1, 1, 2, "none")},
               "c1_eq_x": sum(r["c1_eq"] for r in x), "c2_eq_x": sum(r["c2_eq"] for r in x), "rpt_eq_x": sum(r["rpt_eq"] for r in x),
               "g2_x": sum(r["g2"] for r in x), "g2_osd": sum(r["g2"] for r in osd), "t_alt_eq_x": sum(r["t_alt_eq"] for r in x)}}
    pairs = {}
    for r in x:
        k = f"X i3={r['i3x']} vs T i3={r['i3t']}"
        pairs[k] = pairs.get(k, 0) + 1
    res_pairs = {}
    for r in x:
        if classify(r) == "E-RESIDUAL":
            k = f"X i3={r['i3x']} vs T i3={r['i3t']}"
            res_pairs[k] = res_pairs.get(k, 0) + 1
    out["descriptive"]["type_pairs_x"] = dict(sorted(pairs.items()))
    out["descriptive"]["type_pairs_residual"] = dict(sorted(res_pairs.items()))
    out["descriptive"]["e_enc_is_zero_by_construction"] = True
    return out
