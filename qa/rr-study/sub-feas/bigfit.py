#!/usr/bin/env python3
"""SUB-FEAS: the one full-population fine-fit pass. Computed ONCE per row (grouped
by cycle so each WAV is loaded once), reused for ROW 0h (convergence), W* selection
(split A), and the Stage 1 gate (split B). Numeric only (HK-037).

Amendment 3 (arch/subtraction-feasibility b0dff3d2): parallelised across cycles by
multiprocessing -- every per-row computation here is a pure function of its own
inputs (no shared/global RNG state, no cross-row dependency), so distributing
whole CYCLES (never splitting a cycle's own rows across workers, since they share
one WAV load) across worker processes and reassembling via `Pool.map` (which
returns results in SUBMISSION order regardless of which worker finishes first)
gives a result byte-identical to a serial run -- verified below in
`_verify_parallel_matches_serial`.
"""
from __future__ import annotations

import collections
import multiprocessing
import time

import numpy as np
from scipy.signal import hilbert

import common
import corpus
import fitter
import lattice
import wavio

W_FAMILY = (12.64, 2.56, 1.28, 0.64, 0.32)

N_WORKERS = min(12, max(1, multiprocessing.cpu_count() - 1))


def fit_population(rows: list, tau0_s: float, log, progress_every: int = 500,
                    parallel: bool = True) -> list:
    """rows: any subset of pop['all_rows']. Returns a list of per-row result dicts
    (numeric only): row_id, split, at_edge_t, at_edge_f, at_edge_fdot,
    best_fdot_hz_per_s, X_l0, X_by_w (dict W->X), D_by_w (dict W->D)."""
    by_cycle = collections.defaultdict(list)
    for r in rows:
        by_cycle[r["cycle_ts"]].append(r)
    cycle_items = list(by_cycle.items())  # fixed submission order -> deterministic output order

    t0 = time.time()
    out = []
    n_done = 0

    if parallel and len(cycle_items) > 1 and N_WORKERS > 1:
        tasks = [(ts, rs, tau0_s) for ts, rs in cycle_items]
        with multiprocessing.Pool(processes=N_WORKERS) as pool:
            for cycle_result in pool.imap(_fit_cycle_group, tasks):
                out.extend(cycle_result)
                n_done += 1
                if n_done % max(1, progress_every // 20) == 0 or n_done == len(cycle_items):
                    log("  bigfit: [%d/%d cycles, %d/%d rows] elapsed=%.0fs"
                        % (n_done, len(cycle_items), len(out), len(rows), time.time() - t0))
    else:
        for ts, rs in cycle_items:
            out.extend(_fit_cycle_group((ts, rs, tau0_s)))
            n_done += len(rs)
            if n_done % progress_every == 0:
                log("  bigfit: [%d/%d] elapsed=%.0fs" % (n_done, len(rows), time.time() - t0))

    log("bigfit: done n_rows=%d n_fit=%d elapsed=%.0fs (workers=%d)"
        % (len(rows), len(out), time.time() - t0, N_WORKERS if parallel else 1))
    return out


def _fit_cycle_group(args):
    ts, rs, tau0_s = args
    pcm = wavio.load_cycle_pcm(corpus.cycle_wav_path(ts))
    x_a = hilbert(pcm)
    return [rec for r in rs for rec in [_fit_one(x_a, r, tau0_s)] if rec is not None]


def _fit_one(x_a: np.ndarray, r: dict, tau0_s: float):
    nominal_t = float(r["dt"]) + tau0_s
    # Amendment 2: L1/L2 use the drift-extended fit (widened +/-100ms box too).
    fit = fitter.fine_fit_with_drift(x_a, r["tones"], float(r["freq_hz"]), nominal_t_s=nominal_t)
    if fit is None:
        return None

    r_l1 = fitter.apply_freq_shift(fit["r_base"], fit["best_df_hz"])
    x_by_w, d_by_w = {}, {}
    for w in W_FAMILY:
        y = fitter.subtract(fit["seg"], r_l1, w_s=w)
        m = fitter.residual_metrics(fit["seg"], y, float(r["freq_hz"]))
        x_by_w[w] = m["X_db"]
        d_by_w[w] = m["D_db"]

    # L0: lattice-snapped position (no search) -- the control. Amendment 2: must
    # NOT use the drift-extended fit -- plain r_fit, single scalar, as specified.
    cell = lattice.snap_and_neighbours(float(r["freq_hz"]), nominal_t)[0]
    assert cell["is_centre"]
    seg0 = fitter.extract_segment(x_a, int(round(cell["time_offset_s"] * fitter.FS)))
    x_l0 = float("nan")
    if seg0 is not None:
        r0_unit = fitter.r_fit(r["tones"])
        r0_base = fitter.apply_freq_shift(r0_unit, cell["freq_hz"])
        y0 = fitter.subtract(seg0, r0_base, w_s=12.64)
        m0 = fitter.residual_metrics(seg0, y0, float(r["freq_hz"]))
        x_l0 = m0["X_db"]

    return {
        "row_id": r["row_id"],
        "split": r["split"],
        "at_edge_t": fit["at_edge_t"],
        "at_edge_f": fit["at_edge_f"],
        "at_edge_fdot": fit["at_edge_fdot"],
        "best_fdot_hz_per_s": fit["best_fdot_hz_per_s"],
        "X_l0": x_l0,
        "X_by_w": x_by_w,
        "D_by_w": d_by_w,
    }
