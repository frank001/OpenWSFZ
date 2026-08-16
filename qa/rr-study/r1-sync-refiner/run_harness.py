#!/usr/bin/env python3
"""r1-sync-refiner-instrument-validation -- validation harness (task 4.1).

Drives the diagnostic ft8_refine_candidate export against the population built by
population.py (signal-bearing grid, task 3.x) and the AC-3 noise-only population,
recording TRUTH vs MEASURED (delta_f, delta_t) plus the sync score and per-call
wall-clock cost for every trial, serialised to a results JSON file BEFORE any
aggregation -- so AC-5's byte-diff (three independent runs) has something meaningful
to compare, and AC-1/AC-2/AC-4/AC-6 are computed from this raw data by evaluate_acs.py.

Usage:
    python run_harness.py --dll-path PATH --dll-sha256 SHA --out results.json
                           [--population signal|noise|both] [--limit N]

Each invocation is a fully independent process; run three times with --out pointing at
three different files for AC-5's mechanical byte-diff (never assert determinism from a
single run).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import population as P  # noqa: E402
import refiner_ctypes as R  # noqa: E402


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def run_signal_population(refiner: R.Refiner, trials: list[dict]) -> tuple[list[dict], list[float]]:
    """Returns (deterministic results, per-trial wall-clock seconds).

    Kept as two SEPARATE return values deliberately: wall-clock timing is inherently
    non-deterministic (scheduler jitter, thermal throttling, etc.) and must never be
    mixed into the file AC-5 byte-diffs — see main()'s two-file split below.
    """
    out, timings = [], []
    for t in trials:
        pcm = P.render_signal_pcm(t)
        t0 = time.perf_counter()
        delta_f, delta_t, score, coarse_dt_samp, fine_dt_samp, rc = refiner.refine(
            pcm, t["coarse_freq_hz"], t["coarse_time_offset_s"])
        timings.append(time.perf_counter() - t0)

        out.append({
            "trial_index": t["trial_index"],
            "cell": t["cell"],
            "snr_db": t["snr_db"],
            "offset_class": t["offset_class"],
            "true_freq_offset_hz": t["freq_offset_hz"],
            "true_time_offset_s": t["time_offset_s"],
            "measured_delta_freq_hz": delta_f,
            "measured_delta_time_s": delta_t,
            "sync_score": score,
            # r1b D1: additive fields -- existing fields above unchanged.
            "coarse_dt_samp": coarse_dt_samp,
            "fine_dt_samp": fine_dt_samp,
            "rc": rc,
        })
    return out, timings


def run_noise_population(refiner: R.Refiner, trials: list[dict]) -> tuple[list[dict], list[float]]:
    out, timings = [], []
    for t in trials:
        pcm = P.render_noise_pcm(t)
        t0 = time.perf_counter()
        delta_f, delta_t, score, coarse_dt_samp, fine_dt_samp, rc = refiner.refine(
            pcm, t["coarse_freq_hz"], t["coarse_time_offset_s"])
        timings.append(time.perf_counter() - t0)

        out.append({
            "trial_index": t["trial_index"],
            "coarse_freq_hz": t["coarse_freq_hz"],
            "coarse_time_offset_s": t["coarse_time_offset_s"],
            "measured_delta_freq_hz": delta_f,
            "measured_delta_time_s": delta_t,
            "sync_score": score,
            # r1b D1: additive fields -- existing fields above unchanged.
            "coarse_dt_samp": coarse_dt_samp,
            "fine_dt_samp": fine_dt_samp,
            "rc": rc,
        })
    return out, timings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", required=True)
    ap.add_argument("--dll-sha256", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--population", choices=["signal", "noise", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None,
                     help="cap trials per population (debugging only; full runs omit this)")
    ap.add_argument("--seed", type=int, default=P.SEED)
    args = ap.parse_args()

    refiner = R.Refiner(args.dll_path, verify=True, expected_sha256=args.dll_sha256)

    signal_trials = P.build_signal_population(args.seed) if args.population in ("signal", "both") else []
    noise_trials  = P.build_noise_population(args.seed) if args.population in ("noise", "both") else []

    if args.limit is not None:
        signal_trials = signal_trials[:args.limit]
        noise_trials  = noise_trials[:args.limit]

    t_start = time.time()
    signal_results, signal_timings = run_signal_population(refiner, signal_trials) if signal_trials else ([], [])
    noise_results, noise_timings   = run_noise_population(refiner, noise_trials) if noise_trials else ([], [])
    t_total = time.time() - t_start

    # ── Deterministic results file (AC-1/2/3/4/5 all read this; AC-5 byte-diffs it
    #    directly) — contains ONLY refiner outputs + the truth/manifest fields that
    #    produced them. No wall-clock timing appears here BY CONSTRUCTION, so a
    #    byte-diff failure can only mean the refiner's own output differed. ────────
    out = {
        "dll_path": os.path.abspath(args.dll_path),
        "dll_sha256": R.dll_sha256(args.dll_path),
        "shim_version": refiner.version,
        "seed": args.seed,
        "n_signal_trials": len(signal_results),
        "n_noise_trials": len(noise_results),
        "per_cell_n": P.per_cell_counts(signal_trials) if signal_trials else {},
        "signal_results": signal_results,
        "noise_results": noise_results,
    }
    write_json(args.out, out)

    # ── Separate timing sidecar (AC-6 only; deliberately excluded from the file
    #    above so wall-clock jitter can never cause a spurious AC-5 FAIL). ────────
    timing_path = args.out + ".timing.json"
    write_json(timing_path, {
        "total_wall_clock_s": t_total,
        "n_signal_trials": len(signal_results),
        "n_noise_trials": len(noise_results),
        "signal_wall_clock_s": signal_timings,
        "noise_wall_clock_s": noise_timings,
    })

    print("WROTE %s (%d signal + %d noise trials, %.1f s total, dll_sha256=%s..., shim=%d)"
          % (args.out, len(signal_results), len(noise_results), t_total,
             out["dll_sha256"][:16], refiner.version))
    print("WROTE %s (timing sidecar, excluded from AC-5 diff)" % timing_path)


if __name__ == "__main__":
    main()
