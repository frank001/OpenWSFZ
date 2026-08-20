#!/usr/bin/env python3
"""N3 -- the frequency-accuracy requirement: how much carrier-frequency accuracy does
coherent multi-symbol LLR extraction require, and does the requirement tighten with
coherent order?

Spec: qa/rr-study/2026-08-16-1608-architect-to-qa-n2-ruling-and-n3-frequency-requirement-spec.md
Sec.4. Rules on N2's ROW 0b escalation (5% V1 bound not achievable; anchor rounding
inert for V0's lattice-snapped magnitude extractor but LIVE for V1/V2/V3's float-carrier
downconversion) -- see the spec's Sec.1 for the traced defect and Sec.2 for the larger
finding it produced anyway (the two D-001 limbs are a CONJUNCTION, not independent).

🛑 REQUIREMENT MEASUREMENT, not a treatment arm (spec Sec.4.1): NO ROW SHIPS ANYTHING.
On the matched-hit control population (population.py's build_matched_hit_control(),
N1's, reused unmodified -- known-good rows are correct here because a requirement is
about the METRIC'S RESPONSE, not about decodability), sweeps a COMMON df_hz over
[-4.0,+4.0] Hz step 0.25 (33 points, n3_stats.DF_SWEEP_HZ) through coherent_extract_ext.
extract_variants_ext(), producing FIVE median-BER curves: V1 (order 1), V2_cum/V2_pure
(order 2 cumulative and alone), V3_cum/V3_pure (order 3 cumulative and alone) -- the
pure/cumulative pair is what separates the N2 ruling's Sec.2.2 confound (growing
frequency sensitivity vs. V3's own cumulative inheritance of V1's and V2's already-
corrupted terms).

Primary statistic per curve: W_n, the total df-WIDTH where median BER stays below
B50=11.3%. Gate reads W_3^cum only; every curve's W_n and df*_n (argmin, secondary,
does not gate) is reported alongside (Sec.4.2/4.3).

🛑 No per-row frequency search anywhere -- the sweep applies ONE common df to every row
at once; that is what makes this a requirement statement, not a treatment (Sec.4.5).

Runs the mandatory sign unit test FIRST (Sec.4.4: n3_sign_unit_test.py, DSP-level, not
the generic stats sign test N1/N2 also run -- this one proves the SWEEP's own minimum
tracks a known injected frequency error with the correct sign) and refuses to proceed
if it fails. Then ROW 0a (instrument continuity against N1's/N2's own EXTERNAL V0/V1
reference points -- Sec.4.3's own note: no synthetic round-trip here, real audio only),
ROW 0b (order-1 curve must FLATTEN at both grid ends or W is not identifiable), ROW 0c
(n>=150), ROW 0d (order-1's own minimum median BER must clear B50 somewhere on the grid
or W is undefined), then the ROW 1/2/3/4 gate on W_3^cum, in strict pre-registered order.

NFR-021: message TEXT is used in-process only (recovering true bits via the native
ft8_encode_message) and is NEVER written to a result file or printed, and is never even
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
# N1_DIR MUST be inserted after r1-sync-refiner: that dir has its OWN, unrelated
# population.py (build_signal_population, not build_matched_hit_control) which would
# otherwise shadow N1's (see coherent_extract_ext_selftest.py's own comment on this
# exact trap, and run_n2.py's n2_stats.py, which escapes it only as a side effect).
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
import n3_sign_unit_test  # noqa: E402
from coherent_extract_ext import VARIANT_NAMES, extract_variants_ext  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from n3_stats import B50_THRESHOLD, DF_SWEEP_HZ, argmin_curve, edge_flat, width_below_threshold  # noqa: E402
from population import build_matched_hit_control  # noqa: E402
from run_n1 import WavCache, _anchor  # noqa: E402 -- reuse N1's loader/anchor verbatim

DEFAULT_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DEFAULT_DLL_SHA256 = "6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672"
EXPECTED_SHIM_VERSION = 20260042

ROW_0A_V0_TARGET = 0.0287     # N1 Sec.3.1's own independent reproduction
ROW_0A_V1_TARGET = 0.0575     # N2 ROW 0b's own reproduction, at df=0
ROW_0A_TOL = 0.01             # +/-1pp, both arms
ROW_0B_EDGE_SPAN_HZ = 1.0     # "the outermost 1.0 Hz"
ROW_0B_EDGE_TOL = 0.01        # "change by <1pp"
ROW_0C_MIN_ROWS = 150
ROW_1_W3_MIN_HZ = 2.0
ROW_2_W3_LO_HZ = 0.5
ROW_2_W3_HI_HZ = 2.0
ROW_3_W3_MAX_HZ = 0.5

DF_ZERO_INDEX = list(DF_SWEEP_HZ).index(0.0)


def measure_row(ex: ExtractLLRs, wav_cache: WavCache, row: dict) -> dict | None:
    """Returns {ts, v0_ber, curves: {variant: [ber_at_df0, ber_at_df1, ...]}} or a
    {"reason": ...} drop record. Message text touches this function only via
    ex.true_codeword(row["message"]) and true_bits never leaves this function's local
    scope (NFR-021)."""
    pcm = wav_cache.get(row["ts"])
    anchor_freq, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc0, llr_v0 = ex.extract_at(pcm, float(anchor_freq), anchor_dt)
    if rc0 != 0 or llr_v0 is None:
        return {"reason": "v0_extract_rc_%d" % rc0}
    v0_ber = hard_decision_ber(llr_v0, true_bits)

    pcm64 = np.asarray(pcm, dtype=np.float64)
    curves: dict[str, list[float]] = {name: [] for name in VARIANT_NAMES}
    for df in DF_SWEEP_HZ:
        variants = extract_variants_ext(pcm64, float(anchor_freq), anchor_dt, df_hz=df)
        for name in VARIANT_NAMES:
            curves[name].append(hard_decision_ber(list(variants[name]), true_bits))

    return {"ts": row["ts"], "v0_ber": v0_ber, "curves": curves}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--limit", type=int, default=None,
                     help="cap the control population to this many rows (smoke runs only)")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("N3 -- the frequency-accuracy requirement (REQUIREMENT MEASUREMENT, no row ships anything)")
    log("=" * 90)

    log("\n[MANDATORY] Running the sign unit test first (spec Sec.4.4)...")
    sign_rc = n3_sign_unit_test.main()
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
    log("Building the matched-hit control population (N1's, reused unmodified)")
    log("=" * 90)
    control = build_matched_hit_control()
    if args.limit is not None:
        control = control[: args.limit]
        log("--limit applied: n=%d (SMOKE RUN, not a valid gate evaluation)" % len(control))

    log("\n" + "=" * 90)
    log("Sweeping df in [%.2f, %.2f] Hz, step %.2f Hz, %d points, 5 curves/row"
        % (DF_SWEEP_HZ[0], DF_SWEEP_HZ[-1], DF_SWEEP_HZ[1] - DF_SWEEP_HZ[0], len(DF_SWEEP_HZ)))
    log("=" * 90)
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(control):
        result = measure_row(ex, wav_cache, row)
        if result is None or "reason" in result:
            reason = result["reason"] if result else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(result)
        if (i + 1) % 25 == 0:
            log("  ... %d/%d rows processed (%d measured, %.1fs elapsed)"
                % (i + 1, len(control), len(rows), time.time() - t0))
    log("\nMeasured %d/%d rows (%.1fs). Drop reasons: %s"
        % (len(rows), len(control), time.time() - t0, reasons))

    result_bundle: dict = {"n_control": len(control), "n_measured": len(rows),
                            "drop_reasons": reasons, "df_sweep_hz": list(DF_SWEEP_HZ)}

    log("\n" + "=" * 90)
    log("Aggregating: median BER per (variant, df) across %d measured rows" % len(rows))
    log("=" * 90)
    agg_curves: dict[str, list[float]] = {}
    for name in VARIANT_NAMES:
        agg_curves[name] = [float(st.median(r["curves"][name][i] for r in rows))
                             for i in range(len(DF_SWEEP_HZ))] if rows else \
            [float("nan")] * len(DF_SWEEP_HZ)
    v0_median = float(st.median(r["v0_ber"] for r in rows)) if rows else float("nan")
    result_bundle["v0_median_ber"] = v0_median
    result_bundle["curves"] = agg_curves
    for name in VARIANT_NAMES:
        log("  %-7s median BER at df=0: %.2f%%  (min over grid: %.2f%%  max: %.2f%%)"
            % (name, agg_curves[name][DF_ZERO_INDEX] * 100,
               min(agg_curves[name]) * 100, max(agg_curves[name]) * 100))
    log("  V0 (native, df=0 only) median BER: %.2f%%" % (v0_median * 100))

    log("\n" + "=" * 90)
    log("ROW 0a -- instrument continuity (external reference: N1's V0, N2's V1, real audio)")
    log("=" * 90)
    v1_at_df0 = agg_curves["V1"][DF_ZERO_INDEX] if rows else float("nan")
    v0_ok = (not np.isnan(v0_median)) and abs(v0_median - ROW_0A_V0_TARGET) <= ROW_0A_TOL
    v1_ok = (not np.isnan(v1_at_df0)) and abs(v1_at_df0 - ROW_0A_V1_TARGET) <= ROW_0A_TOL
    row0a_fires = not (v0_ok and v1_ok)
    log("V0 median=%.2f%% (target %.2f%%+/-%.0fpp) V1@df=0 median=%.2f%% (target %.2f%%+/-%.0fpp) -> %s"
        % (v0_median * 100, ROW_0A_V0_TARGET * 100, ROW_0A_TOL * 100,
           v1_at_df0 * 100, ROW_0A_V1_TARGET * 100, ROW_0A_TOL * 100,
           "FIRES" if row0a_fires else "clear"))
    result_bundle["row_0a"] = {"row": "0a", "fires": row0a_fires,
                                "v0_median": v0_median, "v1_at_df0": v1_at_df0,
                                "v0_target": ROW_0A_V0_TARGET, "v1_target": ROW_0A_V1_TARGET,
                                "tol": ROW_0A_TOL}
    if row0a_fires:
        log("\nROW 0a FIRES: this is not the same instrument N1/N2 ran. NO VERDICT, escalate.")
        result_bundle["final_row"] = "0a"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 2
    log("ROW 0a clear.\n")

    log("=" * 90)
    log("ROW 0b -- does the order-1 curve flatten at BOTH grid ends?")
    log("=" * 90)
    left_flat, right_flat, left_chg, right_chg = edge_flat(
        list(DF_SWEEP_HZ), agg_curves["V1"], span_hz=ROW_0B_EDGE_SPAN_HZ, tol_pp=ROW_0B_EDGE_TOL)
    row0b_fires = not (left_flat and right_flat)
    log("left change over outermost %.1fHz=%.2fpp (flat<%.0fpp: %s), right change=%.2fpp "
        "(flat<%.0fpp: %s) -> %s"
        % (ROW_0B_EDGE_SPAN_HZ, left_chg * 100, ROW_0B_EDGE_TOL * 100, left_flat,
           right_chg * 100, ROW_0B_EDGE_TOL * 100, right_flat,
           "FIRES" if row0b_fires else "clear"))
    result_bundle["row_0b"] = {"row": "0b", "fires": row0b_fires,
                                "left_flat": left_flat, "right_flat": right_flat,
                                "left_change": left_chg, "right_change": right_chg,
                                "span_hz": ROW_0B_EDGE_SPAN_HZ, "tol": ROW_0B_EDGE_TOL}
    if row0b_fires:
        log("\nROW 0b FIRES: the grid is too narrow -- W is not identifiable from a "
            "truncated curve. Escalate. Do NOT extend the grid and re-read (HK-026).")
        result_bundle["final_row"] = "0b"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 3
    log("ROW 0b clear.\n")

    log("=" * 90)
    log("ROW 0c -- underpowered check")
    log("=" * 90)
    row0c_fires = len(rows) < ROW_0C_MIN_ROWS
    log("n_measured=%d (bound >=%d) -> %s" % (len(rows), ROW_0C_MIN_ROWS,
                                               "FIRES" if row0c_fires else "clear"))
    result_bundle["row_0c"] = {"row": "0c", "fires": row0c_fires, "n_measured": len(rows),
                                "min_required": ROW_0C_MIN_ROWS}
    if row0c_fires:
        log("\nROW 0c FIRES: instrument failure, NOT a null.")
        result_bundle["final_row"] = "0c"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 4
    log("ROW 0c clear.\n")

    log("=" * 90)
    log("ROW 0d -- is W defined at all? (order-1's own best case must clear B50 SOMEWHERE)")
    log("=" * 90)
    min_v1 = min(agg_curves["V1"])
    row0d_fires = min_v1 > B50_THRESHOLD
    log("min(order-1 median BER over the grid)=%.2f%% (bound <=%.1f%%) -> %s"
        % (min_v1 * 100, B50_THRESHOLD * 100, "FIRES" if row0d_fires else "clear"))
    result_bundle["row_0d"] = {"row": "0d", "fires": row0d_fires, "min_v1_ber": min_v1,
                                "b50_threshold": B50_THRESHOLD}
    if row0d_fires:
        log("\nROW 0d FIRES: even a perfect frequency does not bring order 1 below B50 on "
            "known-good rows. W is undefined; the failure is not about frequency at all. "
            "Escalate -- bigger than any verdict row.")
        result_bundle["final_row"] = "0d"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 5
    log("ROW 0d clear.\n")

    log("=" * 90)
    log("Primary/secondary statistics -- W_n and df*_n for all five curves")
    log("=" * 90)
    w_n: dict[str, float] = {}
    dfstar_n: dict[str, float] = {}
    for name in VARIANT_NAMES:
        w_n[name] = width_below_threshold(list(DF_SWEEP_HZ), agg_curves[name], B50_THRESHOLD)
        dfstar_n[name] = argmin_curve(list(DF_SWEEP_HZ), agg_curves[name])
        log("  %-7s W=%.2f Hz  df*=%+.2f Hz  (min BER %.2f%% at df*)"
            % (name, w_n[name], dfstar_n[name],
               min(agg_curves[name]) * 100))
    result_bundle["W_n"] = w_n
    result_bundle["dfstar_n"] = dfstar_n

    displacements = [dfstar_n[n] for n in VARIANT_NAMES]
    systematic_bias = all(d > 0.25 for d in displacements) or all(d < -0.25 for d in displacements)
    log("\ndf* across all five curves: %s -> %s"
        % (["%+.2f" % d for d in displacements],
           "SYSTEMATIC DISPLACEMENT (all same sign, |d|>0.25Hz)" if systematic_bias
           else "no consistent displacement"))
    result_bundle["systematic_frequency_bias"] = systematic_bias

    log("\n" + "=" * 90)
    log("ROW 1/2/3/4 -- the gate, strict order, on W_3^cum = W['V3_cum']")
    log("=" * 90)
    w3 = w_n["V3_cum"]
    row1_fires = w3 >= ROW_1_W3_MIN_HZ
    row2_fires = (not row1_fires) and (ROW_2_W3_LO_HZ < w3 < ROW_2_W3_HI_HZ)
    row3_fires = (not row1_fires) and (not row2_fires) and (w3 <= ROW_3_W3_MAX_HZ)

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES: W_3^cum=%.2fHz (>=%.1fHz)." % (w3, ROW_1_W3_MIN_HZ))
        log("CONSEQUENCE: the requirement is MEETABLE. Coherent extraction is viable "
            "given a frequency estimator of stated accuracy; next round SIZES that "
            "estimator against this number. Does not authorise building it.")
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES: %.1fHz < W_3^cum=%.2fHz < %.1fHz."
            % (ROW_2_W3_LO_HZ, w3, ROW_2_W3_HI_HZ))
        log("CONSEQUENCE: viable but DEMANDING -- the requirement exceeds what the "
            "lattice+rounding anchor delivers by a stated factor. Next round measures "
            "the estimator's ACHIEVABLE accuracy. R2's existing figures are not the answer.")
    elif row3_fires:
        final_row = "3"
        log("ROW 3 FIRES: W_3^cum=%.2fHz (<=%.1fHz)." % (w3, ROW_3_W3_MAX_HZ))
        log("CONSEQUENCE: coherent multi-symbol extraction requires frequency accuracy "
            "at or beyond WSJT-X's own. Limb 2 is not a viable D-001 route at any anchor "
            "precision this architecture can plausibly reach. BOTH LIMBS are then closed "
            "on outcome evidence, and the 2026-08-11 diagnosis itself REOPENS.")
    else:
        final_row = "4"
        log("ROW 4 (residue -- should be unreachable by the exclusivity proof): "
            "W_3^cum=%.2fHz." % w3)
        log("CONSEQUENCE: escalate; the gate's own exclusivity proof did not hold.")

    result_bundle["final_row"] = final_row
    result_bundle["gate_w3_cum"] = w3
    _write_report(args.out_dir, result_bundle, log_lines)
    _write_rows(args.out_dir, rows)
    log("\nWrote results/n3_results.json, results/n3_gate_report.json, results/harness_run.log")
    return 0


def _write_rows(out_dir: str, rows: list[dict]) -> None:
    # rows already carry ONLY ts + numeric fields (measure_row never stores message text
    # or true_bits past its own local scope) -- NFR-021.
    P.write_json(os.path.join(out_dir, "n3_results.json"), {"rows": rows})


def _write_report(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "n3_gate_report.json"), bundle)
    with open(os.path.join(out_dir, "harness_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
