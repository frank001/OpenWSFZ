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

AC3_SIGNIFICANCE = 0.01           # pre-registered significance level (both dimensions)
AC3_FREQ_RANGE_HZ = (-2.5, 2.5)   # joint coarse search frequency range (sync_refiner.c)
AC3_FREQ_STEP_HZ  = 0.5           # matches REFINE_FREQ_STEP_HZ -- freq output is DISCRETE

# D2 (r1b-sync-refiner-instrument-correction): reflection-symmetry sub-tests replace the
# R1 time-dimension chi-squared-against-convolution-null check (retired per the Captain's
# ruling -- that null's independence assumption between Stage A+B and Stage C is known
# false). The old AC3_TIME_RANGE_S / AC3_TIME_NBINS / AC3_COARSE_STEP_S / AC3_COARSE_HALF_N /
# AC3_FINE_STEP_S / AC3_FINE_HALF_N constants that fed that logic are DELETED, not merely
# unused -- design.md D2's reflection-symmetry test needs no grid model at all, only that
# each search grid is symmetric about zero (true by inspection of sync_refiner.c).
# Bonferroni-corrected so the family-wise false-positive rate across the three sub-tests
# (combined, coarse-only, fine-only) stays at the pre-registered AC3_SIGNIFICANCE = 0.01.
AC3_TIME_SUBTEST_ALPHA = AC3_SIGNIFICANCE / 3.0

SNR_STRATA_ASCENDING = (-20.0, -15.0, -10.0, -5.0, 0.0, 5.0)

# D4 (r1b-sync-refiner-instrument-correction): pooled SNR trend test, time dimension only
# (successor to AC-4's per-stratum any-adjacent-pair-increases-fails rule, retired per the
# Captain's ruling -- that rule had a ~99.9% chance of FAILing a flawless refiner at
# n=400/stratum, HK-021(k), void by construction).
AC4_SIGNIFICANCE = 0.01                    # matches AC-3's convention
AC4_MIN_STRATUM_N = 200                    # standing power floor (spec's pre-existing bar)

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


def reflection_symmetry_test(x: np.ndarray, alpha: float) -> dict:
    """D2 (r1b-sync-refiner-instrument-correction): reflection-symmetry test.

    x: the per-trial values for ONE dimension (combined dt, coarse-only, or fine-only).

    Compares the observed sample against its own negation via a two-sample
    Kolmogorov-Smirnov test. Needs no grid model and no independence assumption between
    search stages -- only that the search grid itself is symmetric about zero, which is
    true by inspection of sync_refiner.c for both stages (design.md D2). ROW 0: a
    degenerate (zero-variance) sub-population is reported as an instrument failure, never
    silently as a PASS.
    """
    if np.std(x) == 0:
        return {"pass": None, "instrument_failure": "degenerate: zero variance, cannot test"}
    stat, p = stats.ks_2samp(x, -x)
    return {"pass": bool(p >= alpha), "ks_statistic": float(stat), "p_value": float(p)}


def evaluate_ac3(noise_results: list[dict]) -> dict:
    """AC-3 (noise-only null): frequency dimension UNCHANGED from
    r1-sync-refiner-instrument-validation (chi-squared goodness-of-fit against a DISCRETE
    uniform null); time dimension REPLACED by D2's three reflection-symmetry sub-tests
    (r1b-sync-refiner-instrument-correction, per the Captain's ruling on R1's AC-3 FAIL).

    HK-021(k) correction, recorded here (a test-construction fix, not a refiner
    fix -- discovered while diagnosing an initial KS-test-based AC-3 FAIL):
    ft8_refine_candidate's frequency output is drawn from an EXPLICIT DISCRETE
    grid (11 values, +/-2.5 Hz in 0.5 Hz steps -- design.md's own coarse search
    grid, sync_refiner.c's joint 2-D search). A Kolmogorov-Smirnov test against a
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

    r1's ORIGINAL time-dimension test (chi-squared against the convolution of the two
    search grids' PMFs) rejected a null whose independence assumption (Stage A+B and
    Stage C search independently) is known false, concentrated in exactly the two
    single-path extreme bins where that false assumption does the most damage (the
    Captain's ruling). D2's reflection-symmetry test makes NO independence assumption at
    all -- it only needs each search grid's own symmetry about zero, verified directly
    against sync_refiner.c's constants (design.md D2), and is run three times: on the
    combined `Δt`, on the Stage A+B coarse selection alone (now separately identifiable
    via D1's `coarse_dt_samp`), and on the Stage C fine selection alone
    (`fine_dt_samp`) -- so a FAIL, if any, names which stage(s) it implicates.
    """
    freq = np.array([r["measured_delta_freq_hz"] for r in noise_results])
    dt        = np.array([r["measured_delta_time_s"] for r in noise_results])
    coarse_dt = np.array([r["coarse_dt_samp"] for r in noise_results], dtype=float)
    fine_dt   = np.array([r["fine_dt_samp"] for r in noise_results], dtype=float)
    n = len(noise_results)

    # ── Frequency: exact discrete categories (11 grid points) -- UNCHANGED from R1 ──
    freq_categories = np.round(np.arange(
        AC3_FREQ_RANGE_HZ[0], AC3_FREQ_RANGE_HZ[1] + 1e-6, AC3_FREQ_STEP_HZ), 6)
    freq_counts = np.array([np.sum(np.isclose(freq, c, atol=1e-3)) for c in freq_categories])
    n_unclassified_freq = n - int(freq_counts.sum())
    freq_expected = n / len(freq_categories)
    chi2_freq, p_freq = stats.chisquare(freq_counts, f_exp=[freq_expected] * len(freq_categories))
    freq_pass = bool(p_freq >= AC3_SIGNIFICANCE)

    # ── Time: D2's three reflection-symmetry sub-tests, Bonferroni-corrected ────────
    time_combined = reflection_symmetry_test(dt, AC3_TIME_SUBTEST_ALPHA)
    time_coarse   = reflection_symmetry_test(coarse_dt, AC3_TIME_SUBTEST_ALPHA)
    time_fine     = reflection_symmetry_test(fine_dt, AC3_TIME_SUBTEST_ALPHA)

    time_subtests = {"combined": time_combined, "coarse_stage": time_coarse, "fine_stage": time_fine}
    # ROW 0: any instrument_failure (degenerate sub-population) means the overall time
    # sub-check is NOT reported PASS, regardless of the other two sub-tests' verdicts.
    time_failed_stages = [name for name, r in time_subtests.items() if r["pass"] is not True]
    time_pass = len(time_failed_stages) == 0

    ac3_pass = freq_pass and time_pass

    return {
        "n_trials": n,
        "pass": ac3_pass,
        "test": "frequency: chi-squared goodness-of-fit (discrete uniform null, unchanged from R1); "
                "time: D2 reflection-symmetry (sample vs. own negation, KS test, 3 sub-tests)",
        "significance_level": AC3_SIGNIFICANCE,
        "freq_chi2_statistic": float(chi2_freq), "freq_pvalue": float(p_freq),
        "freq_categories": freq_categories.tolist(), "freq_counts": freq_counts.tolist(),
        "freq_n_unclassified": n_unclassified_freq, "freq_pass": freq_pass,
        "time_subtest_alpha": AC3_TIME_SUBTEST_ALPHA,
        "time_subtests": time_subtests,
        "time_failed_stages": time_failed_stages,
        "time_pass": time_pass,
    }


def snr_trend_test(snr_db: np.ndarray, abs_time_error_s: np.ndarray, alpha: float) -> dict:
    """D4 (r1b-sync-refiner-instrument-correction): one-sided Spearman rank-correlation
    trend test, pooled across all in-power SNR strata (one row per TRIAL, not one row per
    stratum -- design.md D4's own correction to R1's AC-4, which collapsed 400 observations
    per stratum to a single RMS number first and had essentially no tolerance for the
    sampling noise that collapse introduces).
    """
    rho, p = stats.spearmanr(snr_db, abs_time_error_s)
    # one-sided: SNR increasing should correlate with error decreasing => rho < 0
    p_one_sided = p / 2 if rho < 0 else 1.0 - p / 2
    return {"pass": bool(rho < 0 and p_one_sided < alpha), "rho": float(rho), "p_value": float(p_one_sided)}


def evaluate_ac4(signal_results: list[dict]) -> dict:
    """AC-4: frequency dimension retired PERMANENTLY (R-1 of the Captain's ruling --
    RMS(Δf) is a flat function of the 0.5 Hz search-grid quantisation, not of SNR, hence
    unidentifiable as a monotonicity target; no successor frequency gate is registered
    under any name). RMS(Δf) per stratum is still computed and reported for INFORMATION
    ONLY -- it contributes to no pass/fail field below. Time dimension: D4's pooled
    Spearman trend test replaces R1's per-stratum any-adjacent-pair-increases-fails rule
    (deleted below, not merely stopped-calling, per task 4.3).
    """
    per_stratum = {}
    for snr in SNR_STRATA_ASCENDING:
        rows = [r for r in signal_results if r["snr_db"] == snr]
        freq_err = np.array([r["measured_delta_freq_hz"] - r["true_freq_offset_hz"] for r in rows])
        time_err = np.array([r["measured_delta_time_s"] - r["true_time_offset_s"] for r in rows])
        per_stratum[snr] = {"n": len(rows), "rms_freq_hz": _rms(freq_err), "rms_time_s": _rms(time_err)}

    underpowered_strata = [snr for snr, s in per_stratum.items() if s["n"] < AC4_MIN_STRATUM_N]

    pooled_snr, pooled_abs_time_err = [], []
    for snr in SNR_STRATA_ASCENDING:
        if snr in underpowered_strata:
            continue
        rows = [r for r in signal_results if r["snr_db"] == snr]
        for r in rows:
            pooled_snr.append(r["snr_db"])
            pooled_abs_time_err.append(abs(r["measured_delta_time_s"] - r["true_time_offset_s"]))

    trend = snr_trend_test(np.array(pooled_snr), np.array(pooled_abs_time_err), AC4_SIGNIFICANCE)

    return {
        "pass": trend["pass"],
        "test": "pooled one-sided Spearman rank-correlation trend test (time dimension only)",
        "significance_level": AC4_SIGNIFICANCE,
        "n_pooled_trials": len(pooled_snr),
        "spearman_rho": trend["rho"],
        "p_value_one_sided": trend["p_value"],
        "per_stratum": {str(k): v for k, v in per_stratum.items()},
        "per_stratum_note": "rms_freq_hz is INFORMATIONAL ONLY -- frequency monotonicity is "
                             "retired permanently (R-1); does not contribute to 'pass' above",
        "underpowered_strata": [str(s) for s in underpowered_strata],
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
          f"[chi2] freq p={ac3['freq_pvalue']:.4f} (alpha={AC3_SIGNIFICANCE}); "
          f"[D2 reflection-symmetry, alpha={AC3_TIME_SUBTEST_ALPHA:.5f}] time: "
          + ", ".join(
              f"{name}={'FAIL' if r['pass'] is not True else 'PASS'}"
              f"({'instrument_failure' if r['pass'] is None else 'p=%.4g' % r['p_value']})"
              for name, r in ac3["time_subtests"].items()
          ))
    print(f"AC-4 (SNR trend, time only): {verdict(ac4['pass'])}  "
          f"rho={ac4['spearman_rho']:.4f}, p={ac4['p_value_one_sided']:.4g} (alpha={AC4_SIGNIFICANCE}), "
          f"n={ac4['n_pooled_trials']}, underpowered={ac4['underpowered_strata']}")
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
