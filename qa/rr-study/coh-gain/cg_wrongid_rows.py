#!/usr/bin/env python
"""COH-GAIN Amendment 6 (WRONG-ID), as amended by note 1 (Architect `5e728ee9`, section 15.7): the pre-registered rows, computed AFTER the re-extraction, as code.

Inputs (numbers only, HK-037): wrongid_rows.csv (cg_wrongid.OUT_COLUMNS), the persisted rows.csv files of the fresh samples (for the joins), the frozen row lists (for each sample's cycle order).

Validity (any FAIL => no reading; the report names the row and stops):
  W1  re-extraction reproduces the persisted C3_ok / C3_crc / C3_path / C3_nbe (the G set: G_*) on EVERY selected row.
  W2  of the C3-set OSD (path 1) wrongs, M-NEAR + M-FAR <= 5 %.            (negative control: a sign-inverted OSD output is a chance codeword)
  W3  among the C3-set BP (path 0) wrongs that match a WSJT-X decode, M-NEAR >= 80 %.      (vacuously true when none match, and said so)
Reading, on the C3-set BP (path 0) wrongs, F = M-NEAR / N  (WSJT-X ONLY, note 1; M-OWS is descriptive), 95 % block bootstrap (blocks of 8 cycles WITHIN each sample over the sample's FULL
cycle order, cycles with no wrong row carry 0/0, then pooled; B 10 000, seed 20261006):
  W-REAL   CI_lo(F) >= 0.50     W-FALSE  CI_hi(F) < 0.50     W-MIXED otherwise.     HK-038: 0.50 is the decision value the question implies ("most of them").

  python qa/rr-study/coh-gain/cg_wrongid_rows.py
"""
from __future__ import annotations

import collections
import csv
import datetime
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_rows as R  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_wrongid as W  # noqa: E402

W2_MAX_MATCH_SHARE = 0.05
W3_MIN_NEAR_SHARE = 0.80
F_BAR = 0.50
ANALYSIS_NAME = "analysis_wrongid.json"      # never a rows*.json name


def load_out(path):
    out = []
    for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
        d = dict(r)
        for k in ("sample", "cycle_index", "widx", "w1_ok", "ok", "crc", "path", "nbe", "n_ws_unenc", "n_ows_unenc"):
            d[k] = int(d[k])
        for k in ("m_widx", "in_sample", "dist"):
            d[k] = int(d[k]) if d[k] not in ("", None) else None
        for k in ("m_df", "m_dt", "m_snr"):
            d[k] = float(d[k]) if d[k] not in ("", None) else None
        out.append(d)
    return out


def sel(rows, set_name, path=None):
    return [r for r in rows if r["set"] == set_name and (path is None or r["path"] == path)]


def row_w1(rows):
    bad = [r for r in rows if not r["w1_ok"]]
    return (bool(rows) and not bad), {"n": len(rows), "not_reproduced": len(bad), "examples": [(r["set"], r["sample"], r["cycle_index"], r["widx"]) for r in bad[:5]]}


def row_w2(rows):
    osd = sel(rows, "C3", 1)
    matched = sum(1 for r in osd if r["cls"] in ("M-NEAR", "M-FAR"))
    share = matched / len(osd) if osd else float("nan")
    return (bool(osd) and share <= W2_MAX_MATCH_SHARE), {"n_osd_wrongs": len(osd), "matched_near_or_far": matched, "share": share, "bar": W2_MAX_MATCH_SHARE}


def row_w3(rows):
    bp = sel(rows, "C3", 0)
    near = sum(1 for r in bp if r["cls"] == "M-NEAR")
    far = sum(1 for r in bp if r["cls"] == "M-FAR")
    n = near + far
    share = near / n if n else float("nan")
    return (n == 0 or share >= W3_MIN_NEAR_SHARE), {"bp_wrongs_matching_wsjtx": n, "M_NEAR": near, "M_FAR": far, "near_share": share, "bar": W3_MIN_NEAR_SHARE, "vacuous": n == 0}


def cycle_orders():
    """{sample: [cycle_index, ...]} the sample's FULL cycle order from its frozen row list."""
    return {res: sorted({r[0] for r in json.load(open(SEL.rows_path(res)))["rows"]}) for res in W.SAMPLES}


def f_bootstrap(rows, cycles=None, block=CG.BLOCK_CYCLES, numerator=("M-NEAR",)):
    """F = (rows of the C3-set BP wrongs whose class is in `numerator`) / N, with the pooled within-sample block bootstrap. Returns (F, lo, hi, n_blocks)."""
    cycles = cycles or cycle_orders()
    bp = sel(rows, "C3", 0)
    nums, dens = [], []
    for res, order in sorted(cycles.items()):
        n_c, d_c = collections.Counter(), collections.Counter()
        for r in bp:
            if r["sample"] == res:
                d_c[r["cycle_index"]] += 1
                n_c[r["cycle_index"]] += int(r["cls"] in numerator)
        num = np.array([n_c[c] for c in order], dtype=float)
        den = np.array([d_c[c] for c in order], dtype=float)
        edges = list(range(0, len(order), block))
        nums.append(np.array([num[i:i + block].sum() for i in edges]))
        dens.append(np.array([den[i:i + block].sum() for i in edges]))
    num, den = np.concatenate(nums), np.concatenate(dens)
    if den.sum() == 0:
        return float("nan"), float("nan"), float("nan"), len(num)
    f = float(num.sum() / den.sum())
    rng = np.random.default_rng(CG.SEED)
    idx = rng.integers(0, len(num), size=(CG.B_RESAMPLES, len(num)))
    d_s = den[idx].sum(axis=1)
    ratio = np.where(d_s > 0, num[idx].sum(axis=1) / np.where(d_s > 0, d_s, 1), np.nan)
    lo, hi = np.nanpercentile(ratio, [2.5, 97.5])
    return f, float(lo), float(hi), len(num)


def reading_row(ci_lo, ci_hi, bar=F_BAR):
    """Exclusive, first match wins."""
    if ci_lo >= bar:
        return "W-REAL"
    if ci_hi < bar:
        return "W-FALSE"
    return "W-MIXED"


def _quant(xs):
    return [float(x) for x in np.quantile(xs, [0.1, 0.5, 0.9])] if xs else None


def class_counts(rs):
    c = collections.Counter(r["cls"] for r in rs)
    return {k: c.get(k, 0) for k in W.CLASSES} | {"NO-PAYLOAD": c.get("NO-PAYLOAD", 0), "n": len(rs)}


def analyse(out_csv=None, results_dir=None, rows_by_sample=None, cycles=None):
    out_csv = out_csv or W.OUT_CSV
    rows = load_out(out_csv)
    if rows_by_sample is None:
        rows_by_sample = {res: {(int(x["cycle_index"]), int(x["widx"])): x for x in R.load_rows(os.path.join(W.ART, d, "rows.csv")) if not x["fault"]} for res, d in W.SAMPLES.items()}
    v = {"W1": row_w1(rows), "W2": row_w2(rows), "W3": row_w3(rows)}
    valid = all(ok for ok, _ in v.values())
    failing = [k for k, (ok, _) in v.items() if not ok]
    bp, osd, gset = sel(rows, "C3", 0), sel(rows, "C3", 1), sel(rows, "G")
    f, lo, hi, nb = f_bootstrap(rows, cycles)
    f_ows = f_bootstrap(rows, cycles, numerator=("M-NEAR", "M-OWS"))
    f_far = f_bootstrap(rows, cycles, numerator=("M-NEAR", "M-FAR"))
    correct = sum(1 for d in rows_by_sample.values() for x in d.values() if int(x["C3_ok"]) and not int(x["G_ok"]))
    n_none_bp = sum(1 for r in bp if r["cls"] == "M-NONE")
    near = [r for r in bp if r["cls"] == "M-NEAR"]
    near_insample = [r for r in near if r["in_sample"] == 1]
    g_already = sum(1 for r in near_insample if int(rows_by_sample[r["sample"]].get((r["cycle_index"], r["m_widx"]), {}).get("G_ok", 0)))
    none_by_band = collections.Counter()
    for r in bp:
        if r["cls"] == "M-NONE":
            snr = int(rows_by_sample[r["sample"]][(r["cycle_index"], r["widx"])]["ws_snr"])
            none_by_band[next(n for n, lo_, hi_ in R.SNR_BANDS if lo_ <= snr <= hi_)] += 1
    result = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "F_bar": F_BAR,
              "validity": {k: {"pass": ok, **d} for k, (ok, d) in v.items()}, "failing_rows": failing,
              "selection": {"C3_bp": len(bp), "C3_osd": len(osd), "G_set": len(gset), "G_bp": sum(1 for r in gset if r["path"] == 0), "G_osd": sum(1 for r in gset if r["path"] == 1)}}
    if valid:
        result["F_wsjtx_only"] = {"F": f, "ci95": [lo, hi], "n": len(bp), "n_blocks": nb, "M_NEAR": len(near)}
        result["reading"] = reading_row(lo, hi)
    else:
        result["reading"] = "NO READING"
        result["reading_withheld_because"] = failing
    result["descriptive"] = {
        "C3_bp_classes": class_counts(bp), "C3_osd_classes": class_counts(osd), "G_set_classes_by_path": {str(p): class_counts([r for r in gset if r["path"] == p]) for p in (0, 1)},
        "G_set_near_share": (sum(1 for r in gset if r["cls"] == "M-NEAR") / len(gset)) if gset else None,
        "F_with_M_OWS": {"F": f_ows[0], "ci95": [f_ows[1], f_ows[2]]}, "F_M_NEAR_plus_M_FAR": {"F": f_far[0], "ci95": [f_far[1], f_far[2]]},
        "M_NONE_bp": n_none_bp, "correct_recoveries_fresh": correct, "M_NONE_per_correct_recovery_after_osd_off": (n_none_bp / correct) if correct else None,
        "dist_quantiles_10_50_90_by_class_bp": {c: _quant([r["dist"] for r in bp if r["cls"] == c and r["dist"] is not None]) for c in W.CLASSES},
        "M_NEAR_in_sample": {"n": len(near_insample), "of_M_NEAR": len(near), "matched_row_G_already_decodes": g_already, "not_already": len(near_insample) - g_already},
        "M_NONE_bp_by_ws_snr_band": dict(none_by_band),
        "unencodable_decodes_in_cycle_blind_spot": {"mean_ws_unenc_per_row": float(np.mean([r["n_ws_unenc"] for r in bp])) if bp else None,
                                                    "mean_ows_unenc_per_row": float(np.mean([r["n_ows_unenc"] for r in bp])) if bp else None,
                                                    "note": "M-NONE is an UPPER bound: a wrong payload equal to an unencodable (hashed-call) decode cannot be matched"}}
    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(result, open(os.path.join(results_dir, ANALYSIS_NAME), "w"), indent=1, sort_keys=True, default=str)
    return result


if __name__ == "__main__":
    res = analyse(results_dir=SEL.OUT_DIR)
    print(json.dumps({k: res[k] for k in ("reading", "failing_rows", "F_wsjtx_only", "selection") if k in res}, indent=1, default=str))
