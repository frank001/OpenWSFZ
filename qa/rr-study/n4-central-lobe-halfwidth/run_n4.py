#!/usr/bin/env python3
"""N4 -- the central-lobe frequency-accuracy requirement: how much carrier-frequency
accuracy does coherent multi-symbol LLR extraction require, scoped to the CENTRAL lobe
(not the global below-B50 measure N3's W_n wrongly generalised to), and does the
requirement tighten with coherent order?

Spec: qa/rr-study/2026-08-17-1553-architect-to-qa-n3-ruling-and-n4-lobe-width-spec.md
Rules on N3 (ROW 0b fired correctly on a correctly-implemented row guarding a wrongly-
defined statistic -- W_n was GLOBAL, ROW 0b guarded EDGE FLATNESS, which is neither
necessary nor sufficient for exhaustion of the below-B50 set). N3's own committed data
is NOT void and is NOT re-read here (HK-026 -- a fired gate is never re-read; N4 is a
NEW pre-registration on data N3 never touched, per spec Sec.0).

🛑 REQUIREMENT MEASUREMENT, not a treatment arm: NO ROW SHIPS ANYTHING.

Primary statistic -- H_n, the central-lobe half-width (n4_stats.lobe_half_width):
M_n(df) = median hard-decision BER at common offset df, order n. df* = argmin. Walking
outward from df* in each direction, xL/xR = first B50=11.3% crossings (linear
interpolation). H_n = (xR - xL) / 2. Both ends physically pinned by the metric itself.
Gate reads H_3^cum with a 2,000-resample CLUSTER bootstrap 95% CI over `ts` -- never a
bare point estimate (spec Sec.4.3).

Population -- HELD OUT (spec Sec.4.1, n4_population.build_slices()): Slice A is N3's
own exact 171-row population (limit=200, first-200 file order) and its ONLY job is
ROW 0a; its curves never enter the gate. Slice B is drawn from pool rows BEYOND the
first 200 that N3 never touched -- whole `ts` clusters only, seeded, sorted at
construction, target >=600 rows / >=40 clusters, the 1 ts overlapping A's own range
excluded. This is what makes the pre-registration real: the Architect had already
computed post-hoc half-widths from N3's 171 rows before writing this spec, and any
threshold written against that population would be contaminated.

Grid -- two resolutions (spec Sec.4.2, n4_stats.DF_SWEEP_HZ): core +-2.5 Hz @ 0.125 Hz
(41 pts, resolves the crossing) + outer +-(2.5,10.0] Hz @ 0.5 Hz (30 pts, tests
exhaustion past the 6.25 Hz tone-spacing null and its 9.375 Hz worst-case midpoint) =
71 points total. The outer region exists ONLY to make ROW 0e decidable.

Two mandatory harness changes vs N3 (spec Sec.4.3, both here):
  1. The coherent variants (V1/V2_cum/V2_pure/V3_cum/V3_pure) receive the UNROUNDED
     grid_freq_hz float, not run_n1._anchor()'s rounded-to-int-Hz version -- N3's own
     rounding defect (spec Sec.2.2) is inert for V0 (which snaps to the lattice
     regardless) but was LIVE for the coherent variants, which downconvert at the
     literal float carrier. _anchor() itself is NOT edited (N1's own rows still read
     it). V0's own extraction keeps _anchor()'s rounded freq, unchanged from N1/N2/N3.
  2. The full (rows x offsets) BER matrix is stored per row (measure_row's own
     "curves" dict); the cluster bootstrap (n4_stats.cluster_bootstrap_lobe) re-medians
     that matrix per resample draw and never re-extracts.

Runs the mandatory sign unit test FIRST (n4_sign_unit_test.py, reused verbatim from N3
including the 48-realisation/-18dB correction) and refuses to arm if it fails. Then, in
strict pre-registered order, first fire stops: ROW 0a (Slice A instrument identity)
ROW 0b (Slice B underpowered -- PRECISION per spec Sec.6, not VALIDITY, but survives
HK-025 because its two branches land on different downstream rows) ROW 0c (no lobe
exists at all) ROW 0d (lobe not contained within +-10.0 Hz) ROW 0e (an aliased
below-B50 region exists outside the central lobe -- escalate WITH the distribution, a
fire here is a major finding, not a failure), then the ROW 1/2/3/4 gate on
CI(H_3^cum) against 1.5625 Hz (lattice half-cell) and 0.5 Hz (WSJT-X ALL.TXT integer-Hz
quantisation -- NOT the barred R0/R1/R1b refiner figure, spec Sec.3 item 4).

NFR-021: message TEXT is used in-process only (recovering true bits via the native
ft8_encode_message) and is NEVER written to a result file or printed, and is never
carried in this harness's own in-memory row dicts past the point true_bits is derived.
Per-row output carries ts + numeric fields only.
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r1-sync-refiner"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n2-coherent-llr-extractor"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n3-frequency-requirement"))
# N1_DIR (n1-ber-at-refined-position) MUST be inserted after r1-sync-refiner, same trap
# n3's own run_n3.py documents: that dir has its OWN unrelated population.py.
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
import n4_sign_unit_test  # noqa: E402
from coherent_extract_ext import VARIANT_NAMES, extract_variants_ext  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from n4_population import (  # noqa: E402
    SLICE_B_CAP_ROWS, SLICE_B_MIN_CLUSTERS, SLICE_B_MIN_ROWS, build_slices,
)
from n4_stats import (  # noqa: E402
    B50_THRESHOLD, DF_SWEEP_HZ, ROW_1_CI_LO_MIN_HZ, ROW_3_CI_HI_MAX_HZ,
    any_below_threshold_outside_lobe, cluster_bootstrap_lobe,
    lobe_half_width, median_curve,
)
from run_n1 import WavCache, _anchor  # noqa: E402 -- reuse N1's loader/anchor verbatim

DEFAULT_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DEFAULT_DLL_SHA256 = "6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672"
EXPECTED_SHIM_VERSION = 20260042

ROW_0A_V0_TARGET = 0.0287     # N1 Sec.3.1's own independent reproduction
ROW_0A_V1_TARGET = 0.0575     # N2 ROW 0b's own reproduction, at df=0
ROW_0A_TOL = 0.01             # +/-1pp, both arms
ROW_0B_MIN_ROWS = 400
ROW_0B_MIN_CLUSTERS = 30
ROW_OUTER_EDGE_HZ = 10.0      # ROW 0d's containment check

DF_LIST = list(DF_SWEEP_HZ)
DF_ZERO_INDEX = DF_LIST.index(0.0)
N_DF = len(DF_LIST)


def measure_row(ex: ExtractLLRs, wav_cache: WavCache, row: dict) -> "dict | None":
    """Returns {ts, v0_ber, curves: {variant: [ber_at_df0, ...71 pts...]}} or a
    {"reason": ...} drop record. Message text touches this function only via
    ex.true_codeword(row["message"]) and true_bits never leaves this function's local
    scope (NFR-021)."""
    pcm = wav_cache.get(row["ts"])
    anchor_freq_int, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])
    raw_freq_hz = float(row["grid_freq_hz"])   # UNROUNDED -- mandatory harness change 1
                                                 # (spec Sec.4.3.1): only the coherent
                                                 # variants read this; V0 keeps the
                                                 # rounded _anchor() frequency below.

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc0, llr_v0 = ex.extract_at(pcm, float(anchor_freq_int), anchor_dt)
    if rc0 != 0 or llr_v0 is None:
        return {"reason": "v0_extract_rc_%d" % rc0}
    v0_ber = hard_decision_ber(llr_v0, true_bits)

    pcm64 = np.asarray(pcm, dtype=np.float64)
    curves: "dict[str, list[float]]" = {name: [] for name in VARIANT_NAMES}
    for df in DF_LIST:
        variants = extract_variants_ext(pcm64, raw_freq_hz, anchor_dt, df_hz=df)
        for name in VARIANT_NAMES:
            curves[name].append(hard_decision_ber(list(variants[name]), true_bits))

    return {"ts": row["ts"], "v0_ber": v0_ber, "curves": curves}


def _measure_slice(ex: ExtractLLRs, wav_cache: WavCache, slice_rows: list, log) -> "tuple[list, dict]":
    t0 = time.time()
    rows: "list[dict]" = []
    reasons: "dict[str, int]" = {}
    for i, row in enumerate(slice_rows):
        result = measure_row(ex, wav_cache, row)
        if result is None or "reason" in result:
            reason = result["reason"] if result else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(result)
        if (i + 1) % 100 == 0:
            log("    ... %d/%d rows processed (%d measured, %.1fs elapsed)"
                % (i + 1, len(slice_rows), len(rows), time.time() - t0))
    log("  Measured %d/%d rows (%.1fs). Drop reasons: %s"
        % (len(rows), len(slice_rows), time.time() - t0, reasons))
    return rows, reasons


def _agg_curves(rows: list) -> "dict[str, list[float]]":
    return {name: median_curve(rows, name, N_DF) for name in VARIANT_NAMES}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--limit-a", type=int, default=None, help="smoke: cap Slice A")
    ap.add_argument("--limit-b", type=int, default=None, help="smoke: cap Slice B")
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: "list[str]" = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("N4 -- the central-lobe frequency-accuracy requirement (REQUIREMENT MEASUREMENT)")
    log("=" * 90)

    log("\n[MANDATORY] Running the sign unit test first (spec Sec.4.4)...")
    sign_rc = n4_sign_unit_test.main()
    if sign_rc != 0:
        log("SIGN UNIT TEST FAILED -- refusing to arm the real harness.")
        return 1
    log("Sign unit test PASSED. Arming.\n")

    log("Loading DLL: %s" % args.dll_path)
    ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                      expected_shim_version=EXPECTED_SHIM_VERSION)
    log("DLL SHA256 asserted (%s...), shim version %d confirmed.\n"
        % (args.dll_sha256[:16], ex.version))

    wav_cache = WavCache()

    log("=" * 90)
    log("Building Slice A (identity, N3's exact population) / Slice B (held out, the gate)")
    log("=" * 90)
    slice_a, slice_b, pop_meta = build_slices()
    log("Slice A: n=%d (target: N3's own 171)" % len(slice_a))
    log("Slice B: n=%d rows, %d clusters (target >=%d rows / >=%d clusters, cap %d)"
        % (len(slice_b), pop_meta["slice_b_clusters_used"],
           SLICE_B_MIN_ROWS, SLICE_B_MIN_CLUSTERS, SLICE_B_CAP_ROWS))
    log("Population provenance: %s" % pop_meta)
    if args.limit_a is not None:
        slice_a = slice_a[: args.limit_a]
        log("--limit-a applied: n=%d (SMOKE RUN)" % len(slice_a))
    if args.limit_b is not None:
        slice_b = slice_b[: args.limit_b]
        log("--limit-b applied: n=%d (SMOKE RUN)" % len(slice_b))

    log("\n" + "=" * 90)
    log("Sweeping df over %d points (%.3f..%.3f Hz, two resolutions), 5 curves/row" % (
        N_DF, DF_LIST[0], DF_LIST[-1]))
    log("=" * 90)
    log("-- Slice A --")
    rows_a, reasons_a = _measure_slice(ex, wav_cache, slice_a, log)
    log("-- Slice B --")
    rows_b, reasons_b = _measure_slice(ex, wav_cache, slice_b, log)

    result_bundle: dict = {
        "df_sweep_hz": DF_LIST, "b50_threshold": B50_THRESHOLD,
        "n_slice_a": len(slice_a), "n_measured_a": len(rows_a), "drop_reasons_a": reasons_a,
        "n_slice_b": len(slice_b), "n_measured_b": len(rows_b), "drop_reasons_b": reasons_b,
        "population_provenance": pop_meta,
    }

    agg_a = _agg_curves(rows_a)
    agg_b = _agg_curves(rows_b)
    v0_median_a = float(st.median(r["v0_ber"] for r in rows_a)) if rows_a else float("nan")
    result_bundle["v0_median_ber_slice_a"] = v0_median_a
    result_bundle["curves_slice_a"] = agg_a
    result_bundle["curves_slice_b"] = agg_b

    log("\n" + "=" * 90)
    log("ROW 0a -- Slice A instrument continuity (external reference: N1's V0, N2's V1)")
    log("=" * 90)
    v1_at_df0_a = agg_a["V1"][DF_ZERO_INDEX] if rows_a else float("nan")
    v0_ok = (not np.isnan(v0_median_a)) and abs(v0_median_a - ROW_0A_V0_TARGET) <= ROW_0A_TOL
    v1_ok = (not np.isnan(v1_at_df0_a)) and abs(v1_at_df0_a - ROW_0A_V1_TARGET) <= ROW_0A_TOL
    row0a_fires = not (v0_ok and v1_ok)
    log("V0 median=%.2f%% (target %.2f%%+/-%.0fpp) V1@df=0 median=%.2f%% (target %.2f%%+/-%.0fpp) -> %s"
        % (v0_median_a * 100, ROW_0A_V0_TARGET * 100, ROW_0A_TOL * 100,
           v1_at_df0_a * 100, ROW_0A_V1_TARGET * 100, ROW_0A_TOL * 100,
           "FIRES" if row0a_fires else "clear"))
    result_bundle["row_0a"] = {"row": "0a", "fires": row0a_fires,
                                "v0_median": v0_median_a, "v1_at_df0": v1_at_df0_a,
                                "v0_target": ROW_0A_V0_TARGET, "v1_target": ROW_0A_V1_TARGET,
                                "tol": ROW_0A_TOL}
    if row0a_fires:
        log("\nROW 0a FIRES: Slice A is not the same instrument N1/N2/N3 ran. NO VERDICT.")
        result_bundle["final_row"] = "0a"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows_a, rows_b)
        return 2
    log("ROW 0a clear.\n")

    log("=" * 90)
    log("ROW 0b -- is Slice B powered? (PRECISION per spec Sec.6, not VALIDITY)")
    log("=" * 90)
    n_clusters_b = len({r["ts"] for r in rows_b})
    row0b_fires = len(rows_b) < ROW_0B_MIN_ROWS or n_clusters_b < ROW_0B_MIN_CLUSTERS
    log("n_measured_b=%d (bound >=%d), n_clusters_b=%d (bound >=%d) -> %s"
        % (len(rows_b), ROW_0B_MIN_ROWS, n_clusters_b, ROW_0B_MIN_CLUSTERS,
           "FIRES" if row0b_fires else "clear"))
    result_bundle["row_0b"] = {"row": "0b", "fires": row0b_fires, "n_measured_b": len(rows_b),
                                "n_clusters_b": n_clusters_b, "min_rows": ROW_0B_MIN_ROWS,
                                "min_clusters": ROW_0B_MIN_CLUSTERS}
    if row0b_fires:
        log("\nROW 0b FIRES: Slice B is underpowered. An underpowered stratum is an "
            "instrument failure, not a null. Escalate.")
        result_bundle["final_row"] = "0b"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows_a, rows_b)
        return 3
    log("ROW 0b clear.\n")

    log("=" * 90)
    log("ROW 0c/0d/0e -- order-1 lobe existence, containment, aliasing (on Slice B)")
    log("=" * 90)
    v1_curve_b = agg_b["V1"]
    v1_lobe = lobe_half_width(DF_LIST, v1_curve_b, B50_THRESHOLD)
    min_v1 = min(v1_curve_b)
    row0c_fires = v1_lobe["half_width"] is None
    log("min(order-1 median BER over grid)=%.2f%% (bound <=%.1f%%), lobe found=%s -> 0c %s"
        % (min_v1 * 100, B50_THRESHOLD * 100, not row0c_fires,
           "FIRES" if row0c_fires else "clear"))
    result_bundle["row_0c"] = {"row": "0c", "fires": row0c_fires, "min_v1_ber": min_v1,
                                "b50_threshold": B50_THRESHOLD}
    if row0c_fires:
        log("\nROW 0c FIRES: even a perfect frequency does not bring order 1 below B50 "
            "on known-good rows. H is undefined; the failure is not about frequency at "
            "all. Escalate -- bigger than any verdict row.")
        result_bundle["final_row"] = "0c"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows_a, rows_b)
        return 4
    log("ROW 0c clear.\n")

    row0d_fires = (v1_curve_b[0] < B50_THRESHOLD) or (v1_curve_b[-1] < B50_THRESHOLD)
    log("order-1 median BER at +-%.1fHz: left=%.2f%% right=%.2f%% (must both be >=%.1f%%) -> 0d %s"
        % (ROW_OUTER_EDGE_HZ, v1_curve_b[0] * 100, v1_curve_b[-1] * 100, B50_THRESHOLD * 100,
           "FIRES" if row0d_fires else "clear"))
    result_bundle["row_0d"] = {"row": "0d", "fires": row0d_fires,
                                "left_edge_ber": v1_curve_b[0], "right_edge_ber": v1_curve_b[-1]}
    if row0d_fires:
        log("\nROW 0d FIRES: the lobe is not contained within +-%.1f Hz -- H would be a "
            "lower bound only. Escalate." % ROW_OUTER_EDGE_HZ)
        result_bundle["final_row"] = "0d"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows_a, rows_b)
        return 5
    log("ROW 0d clear.\n")

    row0e_fires = any_below_threshold_outside_lobe(v1_curve_b, B50_THRESHOLD)
    log("any below-B50 grid point outside the contiguous central lobe? -> 0e %s"
        % ("FIRES" if row0e_fires else "clear"))
    result_bundle["row_0e"] = {"row": "0e", "fires": row0e_fires}
    if row0e_fires:
        outside_pts = [(x, y) for x, y in zip(DF_LIST, v1_curve_b)
                       if y < B50_THRESHOLD]
        log("\nROW 0e FIRES: an ALIASED below-B50 region exists outside the central "
            "lobe -- H^lobe is not the whole requirement. This is a MAJOR FINDING, not "
            "a failure. Full order-1 curve (df_hz, median_BER) follows for diagnosis:")
        for x, y in zip(DF_LIST, v1_curve_b):
            log("    df=%+.3f  BER=%.4f" % (x, y))
        result_bundle["row_0e_full_curve"] = {"df": DF_LIST, "v1_median_ber": v1_curve_b}
        result_bundle["final_row"] = "0e"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows_a, rows_b)
        return 6
    log("ROW 0e clear.\n")

    log("=" * 90)
    log("Primary/secondary statistics -- H_n (point estimate) for all five curves, both slices")
    log("=" * 90)
    h_point_a: "dict[str, dict]" = {}
    h_point_b: "dict[str, dict]" = {}
    for name in VARIANT_NAMES:
        h_point_a[name] = lobe_half_width(DF_LIST, agg_a[name], B50_THRESHOLD)
        h_point_b[name] = lobe_half_width(DF_LIST, agg_b[name], B50_THRESHOLD)
        log("  %-7s  Slice A H=%s Hz df*=%s  |  Slice B H=%s Hz df*=%s"
            % (name,
               "%.3f" % h_point_a[name]["half_width"] if h_point_a[name]["half_width"] is not None else "n/a",
               "%+.3f" % h_point_a[name]["df_star"],
               "%.3f" % h_point_b[name]["half_width"] if h_point_b[name]["half_width"] is not None else "n/a",
               "%+.3f" % h_point_b[name]["df_star"]))
    result_bundle["h_point_slice_a"] = h_point_a
    result_bundle["h_point_slice_b"] = h_point_b
    log("(Slice A is NON-GATING context only -- spec Sec.4.1: 'I already know A's "
        "values; that is exactly why it cannot gate.')")

    log("\n" + "=" * 90)
    log("Cluster bootstrap on Slice B -- %d resamples over ts, H_n CI for all 5 curves + D" % args.n_draws)
    log("=" * 90)
    boot = cluster_bootstrap_lobe(rows_b, VARIANT_NAMES, DF_LIST, B50_THRESHOLD,
                                   n_draws=args.n_draws)
    for name in VARIANT_NAMES:
        v = boot["variants"][name]
        log("  %-7s  point=%.3fHz  ci95=[%.3f, %.3f]Hz  (n_draws=%d, no_lobe_draws=%d)"
            % (name, v["point_estimate"] if v["point_estimate"] is not None else float("nan"),
               v["ci95"][0], v["ci95"][1], v["n_draws"], v["n_no_lobe_draws"]))
    d = boot["diff_H1_minus_H3cum"]
    log("  D = H_1 - H_3^cum: point=%.3fHz ci95=[%.3f, %.3f]Hz p=%.4f (n_draws=%d)"
        % (d["point_estimate"] if d["point_estimate"] is not None else float("nan"),
           d["ci95"][0], d["ci95"][1], d["p_two_sided"], d["n_draws"]))
    result_bundle["bootstrap"] = boot

    log("\n" + "=" * 90)
    log("ROW 1/2/3/4 -- the gate, strict order, on CI(H_3^cum)")
    log("=" * 90)
    h3 = boot["variants"]["V3_cum"]
    ci_lo, ci_hi = h3["ci95"]
    row1_fires = ci_lo >= ROW_1_CI_LO_MIN_HZ
    row3_fires = (not row1_fires) and (ci_hi < ROW_3_CI_HI_MAX_HZ)
    row2_fires = (not row1_fires) and (not row3_fires) and \
        (ci_hi < ROW_1_CI_LO_MIN_HZ) and (ci_lo >= ROW_3_CI_HI_MAX_HZ)

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES: CI_lo(H_3^cum)=%.3fHz (>=%.4fHz)." % (ci_lo, ROW_1_CI_LO_MIN_HZ))
        log("CONSEQUENCE: requirement already met by the existing lattice -- K_FREQ_OSR=2 "
            "on the 3.125 Hz lattice delivers +-1.5625Hz worst case with no estimator at "
            "all. Coherent order-3 needs NO frequency enabler; the N2 conjunction finding "
            "weakens materially. Next round sizes the C integration. Does NOT authorise "
            "building it.")
    elif row3_fires:
        final_row = "3"
        log("ROW 3 FIRES: CI_hi(H_3^cum)=%.3fHz (<%.1fHz)." % (ci_hi, ROW_3_CI_HI_MAX_HZ))
        log("CONSEQUENCE: requirement is tighter than WSJT-X's own +-0.5Hz integer-Hz "
            "reporting quantisation -- our only external frequency reference cannot even "
            "observe an estimator meeting it. Limb 2 is not a viable D-001 route on "
            "current instruments; BOTH LIMBS close on outcome evidence and the "
            "2026-08-11 diagnosis REOPENS.")
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES: CI(H_3^cum)=[%.3f, %.3f]Hz, fully between the two cuts."
            % (ci_lo, ci_hi))
        log("CONSEQUENCE: estimator required; H_3^cum IS the requirement, and it is "
            "verifiable with instruments already in the corpus. Next round measures "
            "achievable accuracy. R2's barred figures are not the answer.")
    else:
        final_row = "4"
        log("ROW 4 (residue -- CI straddles a cut): CI(H_3^cum)=[%.3f, %.3f]Hz." % (ci_lo, ci_hi))
        log("CONSEQUENCE: report the interval and escalate. Do NOT pick a side.")

    result_bundle["final_row"] = final_row
    result_bundle["gate_ci_h3cum"] = [ci_lo, ci_hi]
    result_bundle["gate_point_h3cum"] = h3["point_estimate"]

    log("\n" + "=" * 90)
    log("Sec.5.1 secondary -- does the requirement tighten with order? NOTHING HERE GATES.")
    log("=" * 90)
    if d["point_estimate"] is None:
        d_verdict = "UNDEFINED (V1 or V3_cum has no central lobe on Slice B)"
    elif d["point_estimate"] > 0:
        d_verdict = "tightens with order (D>0)"
    else:
        d_verdict = "does NOT tighten with order (D<=0)"
    log("D = H_1 - H_3^cum = %.3fHz, ci95=[%.3f, %.3f]Hz, p=%.4f -- %s"
        % (d["point_estimate"] if d["point_estimate"] is not None else float("nan"),
           d["ci95"][0], d["ci95"][1], d["p_two_sided"], d_verdict))
    log("Pure-vs-cumulative agreement (Sec.2.2's confound separator):")
    for pair in (("V2_pure", "V2_cum"), ("V3_pure", "V3_cum")):
        pv, cv = pair
        pe_p = boot["variants"][pv]["point_estimate"]
        pe_c = boot["variants"][cv]["point_estimate"]
        log("  %-8s H=%s Hz  vs  %-8s H=%s Hz"
            % (pv, "%.3f" % pe_p if pe_p is not None else "n/a",
               cv, "%.3f" % pe_c if pe_c is not None else "n/a"))

    _write_report(args.out_dir, result_bundle, log_lines)
    _write_rows(args.out_dir, rows_a, rows_b)
    log("\nWrote results/n4_results.json, results/n4_gate_report.json, results/harness_run.log")
    return 0


def _write_rows(out_dir: str, rows_a: list, rows_b: list) -> None:
    # rows already carry ONLY ts + numeric fields (measure_row never stores message text
    # or true_bits past its own local scope) -- NFR-021.
    P.write_json(os.path.join(out_dir, "n4_results.json"),
                 {"rows_slice_a": rows_a, "rows_slice_b": rows_b})


def _write_report(out_dir: str, bundle: dict, log_lines: list) -> None:
    P.write_json(os.path.join(out_dir, "n4_gate_report.json"), bundle)
    with open(os.path.join(out_dir, "harness_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
