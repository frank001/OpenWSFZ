#!/usr/bin/env python3
"""SUB-FEAS: W* selection (spec sec.4) and the Stage 1 gate (sec.7). Numeric only.
"""
from __future__ import annotations

import collections

import numpy as np

import common
from bigfit import W_FAMILY

N_BOOT = 2000
BOOT_SEED = common.SEED


def select_w_star(fits_a: list, log) -> dict:
    """W* = argmin median X over split A, per W family member."""
    medians = {}
    for w in W_FAMILY:
        xs = [f["X_by_w"][w] for f in fits_a if np.isfinite(f["X_by_w"][w])]
        medians[w] = float(np.median(xs)) if xs else float("nan")
    w_star = min(medians, key=lambda w: medians[w] if np.isfinite(medians[w]) else float("inf"))
    log("W* selection (split A, n=%d): medians=%s -> W*=%.2f"
        % (len(fits_a), {("%.2f" % k): round(v, 3) for k, v in medians.items()}, w_star))
    return {"medians_by_w": {str(k): v for k, v in medians.items()}, "w_star": w_star}


def _cycle_clustered_bootstrap_median(values_by_cycle: dict, n_boot: int, seed: int):
    """values_by_cycle: cycle_ts -> list of per-row values. Resample CYCLES with
    replacement (not rows), pool all rows of the resampled cycles, take the
    median, repeat n_boot times. Returns (median_point, ci_lo, ci_hi)."""
    cycles = list(values_by_cycle.keys())
    rng = np.random.default_rng(seed)
    all_vals = [v for vs in values_by_cycle.values() for v in vs]
    point = float(np.median(all_vals)) if all_vals else float("nan")
    if not cycles:
        return point, float("nan"), float("nan")
    boot_medians = np.empty(n_boot)
    n_c = len(cycles)
    idx_arr = np.arange(n_c)
    for b in range(n_boot):
        draw = rng.choice(idx_arr, size=n_c, replace=True)
        vals = []
        for di in draw:
            vals.extend(values_by_cycle[cycles[di]])
        boot_medians[b] = np.median(vals) if vals else float("nan")
    lo = float(np.nanpercentile(boot_medians, 2.5))
    hi = float(np.nanpercentile(boot_medians, 97.5))
    return point, lo, hi


def _by_cycle(fits: list, rows_by_id: dict, value_fn):
    out = collections.defaultdict(list)
    for f in fits:
        r = rows_by_id[f["row_id"]]
        v = value_fn(f)
        if v is not None and np.isfinite(v):
            out[r["cycle_ts"]].append(v)
    return out


def stage1_gate(fits_b: list, rows_by_id: dict, w_star: float, log) -> dict:
    """Spec sec.7. Statistic: median X over P_B at L2 (fitted position, W*), 95%
    CI via a cycle-clustered bootstrap (2000 draws, seed 20260927)."""
    x_l2_by_cycle = _by_cycle(fits_b, rows_by_id, lambda f: f["X_by_w"][w_star])
    x_l2_point, x_l2_lo, x_l2_hi = _cycle_clustered_bootstrap_median(x_l2_by_cycle, N_BOOT, BOOT_SEED)

    d_l2_vals = [f["D_by_w"][w_star] for f in fits_b if np.isfinite(f["D_by_w"][w_star])]
    median_d = float(np.median(d_l2_vals)) if d_l2_vals else float("nan")

    if x_l2_hi <= 3.0 and median_d >= 10.0:
        row = "PASS"
    elif x_l2_hi <= 6.0:
        row = "PARTIAL"
    else:
        row = "FAIL"

    # Controls: paired median delta X for L0-L2 and L1-L2 (L1 = X_by_w[12.64]).
    def paired_delta_by_cycle(a_key_fn, b_key_fn):
        out = collections.defaultdict(list)
        for f in fits_b:
            a, b = a_key_fn(f), b_key_fn(f)
            if a is not None and b is not None and np.isfinite(a) and np.isfinite(b):
                r = rows_by_id[f["row_id"]]
                out[r["cycle_ts"]].append(a - b)
        return out

    l0_minus_l2 = paired_delta_by_cycle(lambda f: f["X_l0"], lambda f: f["X_by_w"][w_star])
    l1_minus_l2 = paired_delta_by_cycle(lambda f: f["X_by_w"][12.64], lambda f: f["X_by_w"][w_star])
    d_l0l2 = _cycle_clustered_bootstrap_median(l0_minus_l2, N_BOOT, BOOT_SEED + 1)
    d_l1l2 = _cycle_clustered_bootstrap_median(l1_minus_l2, N_BOOT, BOOT_SEED + 2)

    # C-FLAG: L0's own median X, bootstrap CI.
    x_l0_by_cycle = _by_cycle(fits_b, rows_by_id, lambda f: f["X_l0"])
    x_l0_point, x_l0_lo, x_l0_hi = _cycle_clustered_bootstrap_median(x_l0_by_cycle, N_BOOT, BOOT_SEED + 3)
    c_flag = bool(x_l0_hi <= 3.0)

    log("Stage1: n_B_fit=%d W*=%.2f median_X_L2=%.3f CI=[%.3f,%.3f] median_D_L2=%.3f -> %s"
        % (len(fits_b), w_star, x_l2_point, x_l2_lo, x_l2_hi, median_d, row))
    log("Stage1 controls: L0-L2 median=%.3f CI=[%.3f,%.3f]; L1-L2 median=%.3f CI=[%.3f,%.3f]; "
        "C-FLAG(L0 own median X ci_hi<=3.0)=%s (L0 median=%.3f CI=[%.3f,%.3f])"
        % (d_l0l2[0], d_l0l2[1], d_l0l2[2], d_l1l2[0], d_l1l2[1], d_l1l2[2],
           c_flag, x_l0_point, x_l0_lo, x_l0_hi))

    return {
        "n_B_fit": len(fits_b),
        "w_star": w_star,
        "median_X_L2": x_l2_point, "ci_lo_X_L2": x_l2_lo, "ci_hi_X_L2": x_l2_hi,
        "median_D_L2": median_d,
        "gate_row": row,
        "control_L0_minus_L2": {"median": d_l0l2[0], "ci_lo": d_l0l2[1], "ci_hi": d_l0l2[2]},
        "control_L1_minus_L2": {"median": d_l1l2[0], "ci_lo": d_l1l2[1], "ci_hi": d_l1l2[2]},
        "c_flag_L0_alone_passes": c_flag,
        "L0_median_X": x_l0_point, "L0_ci_lo": x_l0_lo, "L0_ci_hi": x_l0_hi,
    }
