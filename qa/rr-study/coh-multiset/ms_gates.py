#!/usr/bin/env python3
"""COH-MULTISET analysis: the gates (spec section 6 + Amendment 1) as pure functions, and the report numbers. Numbers only; no audio, no text.

  python qa/rr-study/coh-multiset/ms_gates.py analyse --rows <rows_sample.json> --run <dir with rows_part.csv> [--v5 <dir with rows_part.csv of the second process>] --out <result.json>

Definitions (all frozen before the first real-audio decode):
  N        every WSJT-X row of the sampled cycles, unencodable rows included (credited zero).
  X        consulted only where G and C3 both returned no CRC-valid payload (A1.1). X = the FIRST of C1 > J2 > J3 > N1 (fixed, A1.3) with a CRC-valid BP-only output; it is RIGHT iff
           that output matches the row's text, otherwise WRONG.
  NET_X    100 * (rows where X is RIGHT) / N, in pp; interval = cycle-block bootstrap (blocks of 8 consecutive sampled cycles, B 10 000, seed 20261024, numerator and denominator
           resampled together, percentile 2.5/97.5).
  f_X      X wrong / (X wrong + X right) over the consulted rows where X returned a payload; Wilson 95 % interval.
  f_C3     the SAME night's C3 wrong share on G-no-output rows: (c3_out and not c3_right) / (c3_out) over rows with g_out == 0 (A1.2).
  L1-GO    CI_lo(NET_X) >= BAR_L; L1-STOP CI_hi(NET_X) < BAR_L; else L1-OPEN.   BAR_L = 0.5 pp (the Captain, 2026-10-24 12:50:57Z, before any real-audio decode).
  W-FAIL   Wilson CI_lo(f_X) > f_C3 (same night). L1-GO together with W-FAIL goes to the Captain (A1.2).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ORDER = ("C1", "J2", "J3", "N1")
BAR_L = 0.5
SEED = 20261024
B_RESAMPLES = 10_000
BLOCK_CYCLES = 8
V4_MIN = 0.90
V5_ROWS = 300
TIMING = ("t_g", "t_c3", "t_sets")
assert (BAR_L, SEED, B_RESAMPLES, BLOCK_CYCLES, V4_MIN, V5_ROWS) == (0.5, 20261024, 10_000, 8, 0.90, 300)


# ------------------------------------------------------------------------------------------------------------------------ pure predicates
def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def l1_row(ci_lo: float, ci_hi: float, bar: float = BAR_L) -> str:
    if ci_lo >= bar:
        return "L1-GO"
    if ci_hi < bar:
        return "L1-STOP"
    return "L1-OPEN"


def w_fail(f_x_ci_lo: float, f_c3: float) -> bool:
    return f_x_ci_lo > f_c3


def x_outcome(rec: dict):
    """-> ('none'|'right'|'wrong', set name) for a CONSULTED row: the first set in the fixed order with a CRC-valid BP-only output."""
    for s in ORDER:
        if int(rec[f"{s}_bp_out"]):
            return ("right" if int(rec[f"{s}_bp_right"]) else "wrong"), s
    return "none", ""


def block_ci(num, den, block=BLOCK_CYCLES, B=B_RESAMPLES, seed=SEED):
    """Percentile CI (pp) of sum(num)/sum(den) with blocks of consecutive cycles as the resampling unit; numerator and denominator resampled together."""
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    edges = range(0, len(num), block)
    bn = np.array([num[i:i + block].sum() for i in edges])
    bd = np.array([den[i:i + block].sum() for i in edges])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(bn), size=(B, len(bn)))
    ratio = 100.0 * bn[idx].sum(axis=1) / bd[idx].sum(axis=1)
    lo, hi = np.percentile(ratio, [2.5, 97.5])
    return float(100.0 * bn.sum() / bd.sum()), float(lo), float(hi), len(bn)


# ------------------------------------------------------------------------------------------------------------------------ loading
def load_rows_csv(path):
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append(r)
    return out


def _i(r, k):
    return int(float(r[k] or 0))


# ------------------------------------------------------------------------------------------------------------------------ analysis
def analyse(rows_json, recs):
    spec = json.load(open(rows_json))
    all_rows = spec["rows"]
    n_all = len(all_rows)
    cycles = []
    for r in all_rows:
        if not cycles or cycles[-1] != r[0]:
            cycles.append(r[0])
    cyc_pos = {c: i for i, c in enumerate(cycles)}
    den = np.zeros(len(cycles))
    for r in all_rows:
        den[cyc_pos[r[0]]] += 1
    faults = sum(_i(r, "fault") for r in recs)
    num = np.zeros(len(cycles))
    num_gc = np.zeros(len(cycles))          # sanity: G-union-C3 over G
    n_cons = x_right = x_wrong = 0
    first = collections.Counter()
    first_wrong = collections.Counter()
    right_any = collections.Counter()
    blocked = any_right_rows = 0
    g_wrong_rows = 0
    c3_right_n = c3_wrong_n = 0
    overlap = collections.Counter()
    l2 = collections.Counter()
    strata_rows = []
    for r in recs:
        ci = cyc_pos[_i(r, "cycle_index")]
        if _i(r, "g_out") and not _i(r, "g_right"):
            g_wrong_rows += 1
        if not _i(r, "g_right") and _i(r, "c3_right"):
            num_gc[ci] += 1
        if not _i(r, "g_out") and _i(r, "c3_out"):
            c3_right_n += _i(r, "c3_right")
            c3_wrong_n += int(not _i(r, "c3_right"))
        if not _i(r, "consulted"):
            continue
        n_cons += 1
        kind, s = x_outcome(r)
        sets_right = [t for t in ORDER if _i(r, f"{t}_bp_right")]
        for t in sets_right:
            right_any[t] += 1
        if sets_right:
            any_right_rows += 1
            overlap[tuple(t in sets_right for t in ORDER)] += 1
        if kind != "none":
            if kind == "right":
                x_right += 1
                num[ci] += 1
                first[s] += 1
            else:
                x_wrong += 1
                first_wrong[s] += 1
                if sets_right:
                    blocked += 1            # an earlier wrong output hid a later right one
        l2["c3_osd_right"] += _i(r, "c3_osd_right")
        l2["c3_osd_wrong"] += int(_i(r, "c3_osd_out") and not _i(r, "c3_osd_right"))
        for t in ORDER:
            l2[f"{t}_osd_right"] += _i(r, f"{t}_osd_right")
            l2[f"{t}_osd_wrong"] += int(_i(r, f"{t}_osd_out") and not _i(r, f"{t}_osd_right"))
        any_osd_right = any(_i(r, f"{t}_osd_right") or _i(r, f"{t}_bp_right") for t in ORDER)
        l2["x_with_osd_any_right_rows"] += int(any_osd_right)
        first_out = next((t for t in ORDER if _i(r, f"{t}_bp_out") or _i(r, f"{t}_osd_out")), None)
        if first_out:
            ok = _i(r, f"{first_out}_bp_right") or _i(r, f"{first_out}_osd_right")
            l2["x_with_osd_right"] += int(bool(ok))
            l2["x_with_osd_wrong"] += int(not ok)
        strata_rows.append((_i(r, "snr"), _i(r, "load"), kind))
    net, lo, hi, nblocks = block_ci(num, den)
    n_out = x_right + x_wrong
    f_x = x_wrong / n_out if n_out else float("nan")
    f_lo, f_hi = wilson(x_wrong, n_out)
    c3_n = c3_right_n + c3_wrong_n
    f_c3 = c3_wrong_n / c3_n if c3_n else float("nan")
    g_net, g_lo, g_hi, _ = block_ci(num_gc, den)
    # live_hit control (V4)
    hit = [r for r in recs if _i(r, "live_hit")]
    v4 = sum(_i(r, "g_right") for r in hit) / len(hit) if hit else float("nan")
    # strata: cut points from ALL sampled rows (SNR terciles, load quintiles); NET_X per stratum is over that stratum's rows of N
    strata = {}
    for name, col, k in (("snr_tercile", 5, 3), ("load_quintile", 6, 5)):
        xs = sorted(r[col] for r in all_rows)
        cuts = [xs[(len(xs) * j) // k] for j in range(1, k)]
        band = lambda v: sum(1 for c in cuts if v >= c)
        n_b = collections.Counter(band(r[col]) for r in all_rows)
        right_b, wrong_b = collections.Counter(), collections.Counter()
        for (snr, load, kind) in strata_rows:
            b = band(snr if col == 5 else load)
            right_b[b] += int(kind == "right")
            wrong_b[b] += int(kind == "wrong")
        strata[name] = {"cuts": cuts, "bands": {str(b): {"rows": n_b[b], "x_right": right_b[b], "x_wrong": wrong_b[b],
                                                         "NET_X_pp": 100.0 * right_b[b] / n_b[b] if n_b[b] else None,
                                                         "f_X": wrong_b[b] / (right_b[b] + wrong_b[b]) if right_b[b] + wrong_b[b] else None} for b in sorted(n_b)}}
    timing = {t: round(statistics.median([float(r[t]) for r in recs if float(r[t] or 0) > 0]), 4) for t in TIMING if any(float(r[t] or 0) > 0 for r in recs)}
    return {
        "N_all_rows_incl_unencodable": n_all, "N_encodable_evaluated": len(recs), "faults": faults, "cycles": len(cycles), "blocks": nblocks,
        "G_wrong_rows_not_consulted": g_wrong_rows,
        "consulted_rows": n_cons,
        "NET_X_pp": net, "NET_X_ci95": [lo, hi], "BAR_L": BAR_L, "L1": l1_row(lo, hi),
        "X": {"right": x_right, "wrong": x_wrong, "f_X": f_x, "f_X_wilson95": [f_lo, f_hi]},
        "f_C3_same_night": {"value": f_c3, "c3_right": c3_right_n, "c3_wrong": c3_wrong_n, "population": "rows with g_out == 0 and a CRC-valid C3 output", "COH_GAIN_reference": 0.284},
        "W_FAIL": bool(w_fail(f_lo, f_c3)) if n_out and c3_n else None,
        "first_success_by_set": dict(first), "first_wrong_by_set": dict(first_wrong), "right_at_all_by_set": dict(right_any), "any_set_right_rows": any_right_rows,
        "earlier_wrong_blocks_later_right_rows": blocked,
        "overlap_right_C1_J2_J3_N1": {"".join("1" if b else "0" for b in k): v for k, v in sorted(overlap.items())},
        "L2_descriptive": dict(l2), "strata": strata, "median_cpu_s_per_row_by_arm": timing,
        "sanity_G_union_C3_over_G": {"NET_pp": g_net, "ci95": [g_lo, g_hi], "note": "sanity line only (COH-GAIN post-hoc +5.25); not a result"},
        "V4_G_success_on_live_hit_rows": {"value": v4, "n": len(hit), "min": V4_MIN, "pass": bool(v4 >= V4_MIN)},
    }


def v5_compare(main_recs, second_recs):
    """V5: a second fresh process over the first V5_ROWS rows: every per-row field identical (timing fields excluded)."""
    key = lambda r: (_i(r, "cycle_index"), _i(r, "widx"))
    a = {key(r): r for r in main_recs}
    keys = sorted(key(r) for r in second_recs)
    n = diff = 0
    for r in second_recs:
        m = a.get(key(r))
        n += 1
        if m is None or any(str(m[c]) != str(r[c]) for c in r if c not in TIMING):
            diff += 1
    return {"rows": n, "rows_with_any_difference": diff, "pass": bool(n >= 1 and diff == 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["analyse"])
    ap.add_argument("--rows", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--v5")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    recs = load_rows_csv(os.path.join(a.run, "rows_part.csv"))
    out = analyse(a.rows, recs)
    if a.v5:
        second = load_rows_csv(os.path.join(a.v5, "rows_part.csv"))
        out["V5"] = v5_compare(recs, second)
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
