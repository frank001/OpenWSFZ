#!/usr/bin/env python3
"""SUB-FEAS: spec sec.5's "report X and D by SNR band [0,5),[5,10),[10,inf) as a
description only" -- omitted from the original run (per-row fit records weren't
persisted). Re-fits split B ONLY (tau0 and W* both already fixed/known from the
accepted run -- not re-derived here) and buckets by SNR. Purely descriptive: does
not touch, and cannot touch, the Stage 1 gate (already ruled, not re-read).
"""
from __future__ import annotations

import json
import os
import time

import numpy as np

import common

common.log_stdout_utf8()
import corpus
import bigfit

TAU0_S = -0.1600   # ROW 0g, accepted result, sub_feas_result.json
W_STAR = 0.32      # W* selection, accepted result, sub_feas_result.json

SNR_BANDS = [(0.0, 5.0), (5.0, 10.0), (10.0, float("inf"))]


def band_of(snr):
    for lo, hi in SNR_BANDS:
        if lo <= snr < hi:
            return "[%g,%s)" % (lo, ("inf" if hi == float("inf") else "%g" % hi))
    return None


def main():
    log_path = os.path.join(common.RUN_DIR, "snr_band_addendum.log")
    log = common.make_logger(log_path)
    t0 = time.time()

    dll_path = os.path.join(common.RUN_DIR, "bin", "libft8_C3.dll")
    enc = corpus.Encoder(dll_path)
    pop = corpus.build_population(enc, log)

    rows_by_id = {r["row_id"]: r for r in pop["split_b"]}
    log("re-fitting split B only (%d rows), tau0=%.4f (accepted) -- descriptive addendum, not a re-gate"
        % (len(pop["split_b"]), TAU0_S))
    fits_b = bigfit.fit_population(pop["split_b"], TAU0_S, log, progress_every=200)

    by_band = {}
    for f in fits_b:
        r = rows_by_id.get(f["row_id"])
        if r is None:
            continue
        b = band_of(float(r["snr"]))
        if b is None:
            continue
        by_band.setdefault(b, {"X": [], "D": []})
        x = f["X_by_w"].get(W_STAR)
        d = f["D_by_w"].get(W_STAR)
        if x is not None and np.isfinite(x):
            by_band[b]["X"].append(x)
        if d is not None and np.isfinite(d):
            by_band[b]["D"].append(d)

    result = {"w_star": W_STAR, "tau0_s": TAU0_S, "n_fit": len(fits_b), "by_band": {}}
    for b in [band_of(lo) for lo, hi in SNR_BANDS]:
        vals = by_band.get(b, {"X": [], "D": []})
        entry = {
            "n": len(vals["X"]),
            "median_X_db": float(np.median(vals["X"])) if vals["X"] else None,
            "p25_X_db": float(np.percentile(vals["X"], 25)) if vals["X"] else None,
            "p75_X_db": float(np.percentile(vals["X"], 75)) if vals["X"] else None,
            "median_D_db": float(np.median(vals["D"])) if vals["D"] else None,
        }
        result["by_band"][b] = entry
        log("SNR band %s: %s" % (b, entry))

    out_path = os.path.join(common.RUN_DIR, "snr_band_addendum.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    log("wrote %s (elapsed=%.0fs)" % (out_path, time.time() - t0))


if __name__ == "__main__":
    main()
