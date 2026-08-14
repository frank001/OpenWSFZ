#!/usr/bin/env python3
"""r1-sync-refiner-instrument-validation -- six acceptance-criteria evaluator (task 4.2-4.7).

Reads the results file(s) written by run_harness.py and computes AC-1 through AC-6
per spec.md's Requirements. Every bar is the pre-registered, mechanical threshold from
spec.md -- this script does not choose or tune any bar.

Usage:
    python evaluate_acs.py --results run1.json --results2 run2.json --results3 run3.json \
                            --timing run1.json.timing.json --out report.json
"""
from __future__ import annotations

import argparse
import filecmp
import json
import math
import sys

import numpy as np
from scipy import stats

# ── Pre-registered bars (spec.md Requirements; D4 for AC-1/AC-2's derivation) ───────
AC1_RMS_FREQ_HZ_MAX = 0.30
AC1_RMS_TIME_S_MAX  = 0.0077
AC2_MEAN_FREQ_HZ_MAX = 0.10
AC2_MEAN_TIME_S_MAX  = 0.002
AC1_AC2_MIN_SNR_DB   = -10.0

AC3_SIGNIFICANCE = 0.01           # pre-registered chi-squared alpha
AC3_FREQ_RANGE_HZ = (-2.5, 2.5)   # joint coarse search frequency range (sync_refiner.c)
AC3_TIME_RANGE_S  = (-0.07, 0.07) # stage-A + stage-C combined time search range
AC3_FREQ_STEP_HZ  = 0.5           # matches REFINE_FREQ_STEP_HZ -- freq output is DISCRETE
AC3_TIME_NBINS    = 14            # time output is also discrete (0.5 ms grid) but much finer;
                                   # binned into 14 x 10 ms bins for a valid chi-squared test
                                   # (>=5 expected count per bin at n=1200 trials)

# sync_refiner.c's two time-search grids (must match REFINE_COARSE_TIME_HALF_SAMPLES etc.):
AC3_COARSE_STEP_S = 1.0 / 200.0    # 5 ms, d in [-12, 12]
AC3_COARSE_HALF_N = 12
AC3_FINE_STEP_S   = 1.0 / 2000.0   # 0.5 ms, d in [-20, 20]
AC3_FINE_HALF_N   = 20

SNR_STRATA_ASCENDING = (-20.0, -15.0, -10.0, -5.0, 0.0, 5.0)

AC6_ESCALATION_HOURS = 8.0
AC6_CANDIDATES_PER_CYCLE_RANGE = (100, 340)  # 340 = K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2 (worst case)
AC6_CORPUS_CYCLES = 2529  # design.md Trade-off note: "36-44 min for 2,529 cycles" reference corpus


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rms(errors: np.ndarray) -> float:
    return float(np.sqrt(np.mean(errors ** 2)))


def evaluate_ac1_ac2(signal_results: list[dict]) -> dict:
    rows = [r for r in signal_results if r["snr_db"] >= AC1_AC2_MIN_SNR_DB]
    freq_err = np.array([r["measured_delta_freq_hz"] - r["true_freq_offset_hz"] for r in rows])
    time_err = np.array([r["measured_delta_time_s"] - r["true_time_offset_s"] for r in rows])

    rms_freq = _rms(freq_err)
    rms_time = _rms(time_err)
    mean_freq = float(np.mean(freq_err))
    mean_time = float(np.mean(time_err))

    ac1_pass = rms_freq <= AC1_RMS_FREQ_HZ_MAX and rms_time <= AC1_RMS_TIME_S_MAX
    ac2_pass = abs(mean_freq) <= AC2_MEAN_FREQ_HZ_MAX and abs(mean_time) <= AC2_MEAN_TIME_S_MAX

    # Sign-error signature check (design.md Risk / spec.md AC-2 scenario): mean large
    # relative to RMS in a consistent direction is the named highest-probability defect.
    sign_error_suspected = False
    if rms_freq > 0 and abs(mean_freq) / rms_freq > 0.7:
        sign_error_suspected = True
    if rms_time > 0 and abs(mean_time) / rms_time > 0.7:
        sign_error_suspected = True

    return {
        "n_trials": len(rows),
        "ac1": {
            "pass": ac1_pass,
            "rms_freq_hz": rms_freq, "bar_freq_hz": AC1_RMS_FREQ_HZ_MAX,
            "rms_time_s": rms_time, "bar_time_s": AC1_RMS_TIME_S_MAX,
        },
        "ac2": {
            "pass": ac2_pass,
            "mean_freq_error_hz": mean_freq, "bar_freq_hz": AC2_MEAN_FREQ_HZ_MAX,
            "mean_time_error_s": mean_time, "bar_time_s": AC2_MEAN_TIME_S_MAX,
            "sign_error_suspected": sign_error_suspected,
        },
    }


def evaluate_ac3(noise_results: list[dict]) -> dict:
    """AC-3 (noise-only null): chi-squared goodness-of-fit against a DISCRETE
    uniform null, not a Kolmogorov-Smirnov test against a continuous uniform.

    HK-021(k) correction, recorded here (a test-construction fix, not a refiner
    fix -- discovered while diagnosing an initial KS-test-based AC-3 FAIL):
    ft8_refine_candidate's frequency output is drawn from an EXPLICIT DISCRETE
    grid (11 values, +/-2.5 Hz in 0.5 Hz steps -- design.md's own coarse search
    grid, sync_refiner.c's joint 2-D search) and the time output is likewise
    discrete (0.5 ms fine-search grid). A Kolmogorov-Smirnov test against a
    CONTINUOUS uniform null is the wrong instrument for a discrete, bounded
    output: at n=1200 trials it has enough power to reject ANY discretised
    distribution purely from the discreteness itself (the empirical step-CDF
    can never match a continuous diagonal), regardless of how fair the
    underlying discrete distribution actually is -- this is a mismatch between
    the metric and what the gate names (HK-021(k): "is the failure still an
    estimate of what the gate names, or a property of the instrument?"),
    exactly the class of defect HK-025 authorises correcting. Chi-squared
    goodness-of-fit against the correct discrete/binned uniform null is the
    mechanically appropriate test for this output's actual support.
    """
    freq = np.array([r["measured_delta_freq_hz"] for r in noise_results])
    dt   = np.array([r["measured_delta_time_s"] for r in noise_results])
    n = len(noise_results)

    # ── Frequency: exact discrete categories (11 grid points) ───────────────
    freq_categories = np.round(np.arange(
        AC3_FREQ_RANGE_HZ[0], AC3_FREQ_RANGE_HZ[1] + 1e-6, AC3_FREQ_STEP_HZ), 6)
    freq_counts = np.array([np.sum(np.isclose(freq, c, atol=1e-3)) for c in freq_categories])
    n_unclassified_freq = n - int(freq_counts.sum())
    freq_expected = n / len(freq_categories)
    chi2_freq, p_freq = stats.chisquare(freq_counts, f_exp=[freq_expected] * len(freq_categories))

    # ── Time: binned into AC3_TIME_NBINS equal-width bins, against the CORRECT
    #    (non-flat) null -- see the HK-021(k) note below. ─────────────────────
    # Range padded by 1 ms beyond the nominal search range to absorb float32
    # boundary rounding (e.g. 0.070000000298 > 0.07 exactly) without silently
    # dropping trials from the histogram.
    time_range_padded = (AC3_TIME_RANGE_S[0] - 0.001, AC3_TIME_RANGE_S[1] + 0.001)
    time_counts, bin_edges = np.histogram(dt, bins=AC3_TIME_NBINS, range=time_range_padded)

    # HK-021(k) correction #2: dt_total = dt_coarse + dt_fine is the SUM of two
    # independent (under a "no real signal" null) discrete-uniform search
    # outputs -- a 25-point grid (+/-12 samples @ 200 Hz) and a 41-point grid
    # (+/-20 samples @ 2000 Hz). The sum of two uniform variables is NOT itself
    # uniform (basic convolution result: it is trapezoidal, tapering at the
    # combined extremes, since reaching +/-0.07 s requires BOTH components to
    # simultaneously sit at their own extreme). A flat/uniform null over
    # [-0.07, 0.07] is therefore the WRONG null for this output even for a
    # refiner with zero noise sensitivity, and rejects it purely from that
    # structural mismatch (exactly analogous to the freq-dimension KS-vs-
    # discrete mismatch above). The correct null is computed here directly by
    # convolving the two search grids' PMFs (mechanical, per HK-021: computed,
    # not asserted in prose) and binning it identically to the observed data.
    coarse_vals = np.arange(-AC3_COARSE_HALF_N, AC3_COARSE_HALF_N + 1) * AC3_COARSE_STEP_S
    fine_vals   = np.arange(-AC3_FINE_HALF_N, AC3_FINE_HALF_N + 1) * AC3_FINE_STEP_S
    null_samples = (coarse_vals[:, None] + fine_vals[None, :]).ravel()  # all 25*41 sums, each equally likely
    null_counts, _ = np.histogram(null_samples, bins=AC3_TIME_NBINS, range=time_range_padded)
    time_expected = n * null_counts / null_counts.sum()
    # chi-squared requires every expected count > 0; the convolution null is
    # smooth enough in practice that this holds for AC3_TIME_NBINS=14, but
    # guard explicitly rather than let scipy raise an opaque error.
    if np.any(time_expected <= 0):
        raise RuntimeError("AC-3 time null has a zero-expectation bin -- reduce AC3_TIME_NBINS")
    chi2_time, p_time = stats.chisquare(time_counts, f_exp=time_expected)

    freq_pass = bool(p_freq >= AC3_SIGNIFICANCE)
    time_pass = bool(p_time >= AC3_SIGNIFICANCE)
    ac3_pass = freq_pass and time_pass

    return {
        "n_trials": n,
        "pass": ac3_pass,
        "test": "chi-squared goodness-of-fit (discrete/binned uniform null)",
        "significance_level": AC3_SIGNIFICANCE,
        "freq_chi2_statistic": float(chi2_freq), "freq_pvalue": float(p_freq),
        "freq_categories": freq_categories.tolist(), "freq_counts": freq_counts.tolist(),
        "freq_n_unclassified": n_unclassified_freq, "freq_pass": freq_pass,
        "time_chi2_statistic": float(chi2_time), "time_pvalue": float(p_time),
        "time_nbins": AC3_TIME_NBINS, "time_counts": time_counts.tolist(),
        "time_expected_counts": time_expected.tolist(),
        "time_null_model": "convolution of coarse (25pt) and fine (41pt) search grids, not flat-uniform",
        "time_range_s": AC3_TIME_RANGE_S, "time_pass": time_pass,
    }


def evaluate_ac4(signal_results: list[dict]) -> dict:
    per_stratum = {}
    for snr in SNR_STRATA_ASCENDING:
        rows = [r for r in signal_results if r["snr_db"] == snr]
        freq_err = np.array([r["measured_delta_freq_hz"] - r["true_freq_offset_hz"] for r in rows])
        time_err = np.array([r["measured_delta_time_s"] - r["true_time_offset_s"] for r in rows])
        per_stratum[snr] = {"n": len(rows), "rms_freq_hz": _rms(freq_err), "rms_time_s": _rms(time_err)}

    broken_pairs = []
    prev_snr = None
    for snr in SNR_STRATA_ASCENDING:
        if prev_snr is not None:
            prev, cur = per_stratum[prev_snr], per_stratum[snr]
            # allow tiny float noise (1e-9) so exact ties never spuriously fail
            if cur["rms_freq_hz"] > prev["rms_freq_hz"] + 1e-9:
                broken_pairs.append((prev_snr, snr, "freq", prev["rms_freq_hz"], cur["rms_freq_hz"]))
            if cur["rms_time_s"] > prev["rms_time_s"] + 1e-9:
                broken_pairs.append((prev_snr, snr, "time", prev["rms_time_s"], cur["rms_time_s"]))
        prev_snr = snr

    return {
        "pass": len(broken_pairs) == 0,
        "per_stratum": {str(k): v for k, v in per_stratum.items()},
        "broken_pairs": broken_pairs,
    }


def evaluate_ac5(path1: str, path2: str, path3: str) -> dict:
    diffs = []
    for a, b in ((path1, path2), (path1, path3), (path2, path3)):
        same = filecmp.cmp(a, b, shallow=False)
        entry = {"a": a, "b": b, "byte_identical": same}
        if not same:
            entry.update(_first_diff_offset(a, b))
        diffs.append(entry)
    return {"pass": all(d["byte_identical"] for d in diffs), "pairwise": diffs}


def _first_diff_offset(a: str, b: str) -> dict:
    with open(a, "rb") as fa, open(b, "rb") as fb:
        ba, bb = fa.read(), fb.read()
    n = min(len(ba), len(bb))
    for i in range(n):
        if ba[i] != bb[i]:
            return {"first_diff_byte_offset": i}
    return {"first_diff_byte_offset": n, "note": "one file is a prefix of the other (length differs)"}


def evaluate_ac6(timing_paths: list[str]) -> dict:
    all_times = []
    for p in timing_paths:
        d = _load(p)
        all_times.extend(d.get("signal_wall_clock_s", []))
        all_times.extend(d.get("noise_wall_clock_s", []))
    arr = np.array(all_times) if all_times else np.array([0.0])
    mean_s = float(np.mean(arr))

    projections = {}
    for cands in AC6_CANDIDATES_PER_CYCLE_RANGE:
        proj_s = mean_s * cands * AC6_CORPUS_CYCLES
        projections[f"{cands}_candidates_per_cycle"] = {
            "projected_full_corpus_hours": proj_s / 3600.0,
            "escalate": (proj_s / 3600.0) > AC6_ESCALATION_HOURS,
        }

    return {
        "n_calls_measured": len(all_times),
        "mean_per_candidate_wall_clock_s": mean_s,
        "corpus_cycles_reference": AC6_CORPUS_CYCLES,
        "candidates_per_cycle_range": AC6_CANDIDATES_PER_CYCLE_RANGE,
        "projections": projections,
        "gated": False,  # AC-6 SHALL NOT gate PASS/FAIL (spec Requirement)
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="primary results file (AC-1/2/3/4)")
    ap.add_argument("--results2", help="second independent run (AC-5)")
    ap.add_argument("--results3", help="third independent run (AC-5)")
    ap.add_argument("--timing", nargs="*", default=[], help="timing sidecar file(s) (AC-6)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = _load(args.results)
    ac1_ac2 = evaluate_ac1_ac2(data["signal_results"])
    ac3 = evaluate_ac3(data["noise_results"])
    ac4 = evaluate_ac4(data["signal_results"])

    ac5 = None
    if args.results2 and args.results3:
        ac5 = evaluate_ac5(args.results, args.results2, args.results3)

    ac6 = evaluate_ac6(args.timing) if args.timing else None

    report = {
        "source_results_file": args.results,
        "per_cell_n": data.get("per_cell_n", {}),
        "underpowered_cells": [c for c, n in data.get("per_cell_n", {}).items() if n < 200],
        "ac1": ac1_ac2["ac1"],
        "ac2": ac1_ac2["ac2"],
        "ac3": ac3,
        "ac4": ac4,
        "ac5": ac5,
        "ac6": ac6,
    }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    # ── Human-readable summary ───────────────────────────────────────────────
    def verdict(b):
        return "PASS" if b else "FAIL"

    print("=== r1-sync-refiner-instrument-validation: acceptance criteria ===")
    print(f"AC-1 (RMS accuracy):        {verdict(ac1_ac2['ac1']['pass'])}  "
          f"RMS(df)={ac1_ac2['ac1']['rms_freq_hz']:.4f} Hz (<= {AC1_RMS_FREQ_HZ_MAX}), "
          f"RMS(dt)={ac1_ac2['ac1']['rms_time_s']*1000:.3f} ms (<= {AC1_RMS_TIME_S_MAX*1000})")
    print(f"AC-2 (systematic bias):     {verdict(ac1_ac2['ac2']['pass'])}  "
          f"mean(df err)={ac1_ac2['ac2']['mean_freq_error_hz']:.4f} Hz (<= {AC2_MEAN_FREQ_HZ_MAX}), "
          f"mean(dt err)={ac1_ac2['ac2']['mean_time_error_s']*1000:.3f} ms (<= {AC2_MEAN_TIME_S_MAX*1000})"
          f"{'  [SIGN-ERROR SUSPECTED]' if ac1_ac2['ac2']['sign_error_suspected'] else ''}")
    print(f"AC-3 (noise-only null):     {verdict(ac3['pass'])}  "
          f"[chi2] freq p={ac3['freq_pvalue']:.4f}, time p={ac3['time_pvalue']:.4f} (alpha={AC3_SIGNIFICANCE})")
    print(f"AC-4 (SNR monotonicity):    {verdict(ac4['pass'])}  broken_pairs={ac4['broken_pairs']}")
    if ac5 is not None:
        print(f"AC-5 (determinism):        {verdict(ac5['pass'])}")
    else:
        print("AC-5 (determinism):        NOT EVALUATED (need --results2 and --results3)")
    if ac6 is not None:
        print(f"AC-6 (cost, not gated):    mean={ac6['mean_per_candidate_wall_clock_s']*1000:.2f} ms/candidate; "
              f"{ac6['projections']}")
    else:
        print("AC-6 (cost):               NOT EVALUATED (need --timing)")
    print(f"Underpowered cells:         {report['underpowered_cells']}")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
