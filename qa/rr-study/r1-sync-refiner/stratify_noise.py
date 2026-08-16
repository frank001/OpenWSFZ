#!/usr/bin/env python3
"""r1b-sync-refiner-instrument-correction -- D3: stratify the noise-only population by
its own recorded coarse search position (task 1.1).

Reads a results file's `noise_results` (the same n=1,200 AC-3 population every
r1-sync-refiner-instrument-validation run already wrote) and computes, purely from
fields already on disk -- no new capture run:

  - the raw correlation between `coarse_time_offset_s` and the recovered `Δt`
    (`measured_delta_time_s`)
  - the correlation between `coarse_time_offset_s`'s FRACTIONAL POSITION within its own
    5 ms coarse search cell (the Stage A+B grid step, AC3_COARSE_STEP_S in evaluate_acs.py)
    and `Δt`
  - the correlation between `coarse_freq_hz` and `Δt`
  - a decile table of mean `Δt`, grouped by that fractional cell-position decile
  - a sign test and a two-sample KS test (sample vs. its own negation -- the same
    statistic D2's reflection_symmetry_test formalises) on the combined `Δt`, as an
    informal cross-check that this script's own reproduction matches proposal.md's
    Impact section numbers

This is purely a REPORT (design.md's own "Noise population is stratified..." requirement:
"SHALL NOT itself gate any acceptance criterion's PASS/FAIL disposition") -- it exists to
tell a position-dependent cause (edge/boundary artefact) apart from a pervasive one, not
to pass or fail the refiner. Reported statistics are informational, not gating.

Usage:
    python stratify_noise.py --results run_a.json [--out stratify_report.json]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from scipy import stats

# Stage A+B coarse search grid step (sync_refiner.c REFINE_DECIM_COARSE -> 200 Hz rate;
# must match AC3_COARSE_STEP_S in evaluate_acs.py).
COARSE_CELL_S = 1.0 / 200.0  # 5 ms

N_DECILES = 10


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def stratify(noise_results: list[dict]) -> dict:
    n = len(noise_results)
    coarse_time_s = np.array([r["coarse_time_offset_s"] for r in noise_results])
    coarse_freq_hz = np.array([r["coarse_freq_hz"] for r in noise_results], dtype=float)
    dt = np.array([r["measured_delta_time_s"] for r in noise_results])

    # Fractional position of coarse_time_offset_s within its own 5 ms coarse cell,
    # in [0, 1) -- e.g. 0.3123 s / 0.005 s = 62.46 -> fractional part 0.46.
    cell_position = np.mod(coarse_time_s / COARSE_CELL_S, 1.0)

    r_cell_position = _pearson_r(cell_position, dt)
    r_raw_offset = _pearson_r(coarse_time_s, dt)
    r_freq = _pearson_r(coarse_freq_hz, dt)

    # Decile table of mean Δt by cell-position decile. Quantile-based (equal COUNT per
    # bin, i.e. data-driven edges from cell_position's own empirical distribution) --
    # NOT fixed-width bins on [0, 1). The two differ here: cell_position's realised
    # sample (n=1200, drawn from a uniform coarse-position band) is not perfectly flat,
    # so fixed-width [0,1) bins put unequal counts per bin and shift decile 0's mean
    # enough to flip its sign relative to the quantile-based table (verified against
    # proposal.md's Impact section numbers, which are quantile-based: task 1.2).
    decile_edges = np.quantile(cell_position, np.linspace(0.0, 1.0, N_DECILES + 1))
    decile_idx = np.clip(np.digitize(cell_position, decile_edges[1:-1], right=False), 0, N_DECILES - 1)
    decile_table = []
    for d in range(N_DECILES):
        mask = decile_idx == d
        count = int(np.sum(mask))
        mean_dt_ms = float(np.mean(dt[mask]) * 1000.0) if count > 0 else None
        decile_table.append({
            "decile": d,
            "cell_position_range": [float(decile_edges[d]), float(decile_edges[d + 1])],
            "n": count,
            "mean_dt_ms": mean_dt_ms,
        })

    # Informal reflection-symmetry cross-check (D2's own statistic, run here only as a
    # reproduction check against proposal.md's Impact section -- NOT the pre-registered
    # gated test; that lives in evaluate_acs.py's reflection_symmetry_test at task 3.1).
    nonzero = dt[dt != 0.0]
    n_pos = int(np.sum(nonzero > 0))
    n_neg = int(np.sum(nonzero < 0))
    sign_test = stats.binomtest(min(n_pos, n_neg), n_pos + n_neg, 0.5, alternative="two-sided")
    ks_stat, ks_p = stats.ks_2samp(dt, -dt)

    return {
        "n_trials": n,
        "mean_dt_ms": float(np.mean(dt) * 1000.0),
        "median_dt_ms": float(np.median(dt) * 1000.0),
        "correlations": {
            "cell_position_vs_dt": r_cell_position,
            "raw_coarse_time_offset_vs_dt": r_raw_offset,
            "coarse_freq_hz_vs_dt": r_freq,
        },
        "decile_table_mean_dt_by_cell_position": decile_table,
        "informal_symmetry_crosscheck": {
            "note": "reproduction check only -- the gated test is evaluate_acs.py's "
                    "reflection_symmetry_test (task 3.1), not this script",
            "sign_test": {
                "n_positive": n_pos, "n_negative": n_neg,
                "p_value": float(sign_test.pvalue),
            },
            "ks_vs_own_negation": {
                "ks_statistic": float(ks_stat), "p_value": float(ks_p),
            },
        },
        "gates_any_acceptance_criterion": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="results JSON file written by run_harness.py")
    ap.add_argument("--out", default=None, help="optional path to write the report JSON")
    args = ap.parse_args()

    data = _load(args.results)
    noise_results = data["noise_results"]
    report = stratify(noise_results)
    report["source_results_file"] = args.results

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)

    print("=== D3: noise population stratification (report only, not gated) ===")
    print(f"n_trials={report['n_trials']}  mean(dt)={report['mean_dt_ms']:.3f} ms  "
          f"median(dt)={report['median_dt_ms']:.3f} ms")
    c = report["correlations"]
    print(f"r(cell_position, dt)={c['cell_position_vs_dt']:.4f}  "
          f"r(raw_offset, dt)={c['raw_coarse_time_offset_vs_dt']:.4f}  "
          f"r(coarse_freq_hz, dt)={c['coarse_freq_hz_vs_dt']:.4f}")
    print("Decile table (mean dt, ms, by fractional cell position):")
    for row in report["decile_table_mean_dt_by_cell_position"]:
        lo, hi = row["cell_position_range"]
        mean_str = f"{row['mean_dt_ms']:.3f}" if row["mean_dt_ms"] is not None else "n/a"
        print(f"  [{lo:.1f}, {hi:.1f}) n={row['n']:4d}  mean(dt)={mean_str} ms")
    sc = report["informal_symmetry_crosscheck"]
    print(f"Informal sign test: {sc['sign_test']['n_positive']} pos vs "
          f"{sc['sign_test']['n_negative']} neg, p={sc['sign_test']['p_value']:.4g}")
    print(f"Informal KS(x, -x): stat={sc['ks_vs_own_negation']['ks_statistic']:.4f}, "
          f"p={sc['ks_vs_own_negation']['p_value']:.4g}")
    if args.out:
        print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
