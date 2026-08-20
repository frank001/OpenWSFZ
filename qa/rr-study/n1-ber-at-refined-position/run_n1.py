#!/usr/bin/env python3
"""N1 -- does using the refiner's position fix the reading? BER as the primary metric.

Spec: qa/rr-study/2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-spec.md
Design of the export this harness drives: openspec/changes/n1-extract-llrs-at-position/

For each candidate-present-and-failed row (population.py), extracts hard-decision LLRs
TWICE on the identical audio buffer and the identical candidate:
  GRID     -- at the candidate's own grid position (its recorded freq_hz/dt, rounded to
              the nearest int Hz -- see _anchor() for why the rounding matters).
  REFINED  -- at GRID + ft8_refine_candidate's own (delta_f, delta_t), i.e. the position
              a real integration would extract at if it trusted the refiner.
Both use ft8_extract_llrs_at (n1-extract-llrs-at-position, shim 20260042) -- the exact
extraction code production uses, run at a caller-supplied position, unmodified.

Runs the mandatory sign unit test FIRST and refuses to proceed if it fails (spec Sec.4:
"Do not arm until it passes"). Then evaluates the gate in the spec's own strict order
(Sec.5), stopping at the first row that fires, exactly as pre-registered.

NFR-021: message TEXT is used in-process only (to recover the true codeword via
ft8_encode_message) and is NEVER written to a result file or printed. Per-row output
carries ts + numeric fields only.
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r1-sync-refiner"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))

import p23_common as P  # noqa: E402
import sign_unit_test  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, FTX_LDPC_N, hard_decision_ber  # noqa: E402
from n1_stats import B50_THRESHOLD, cluster_bootstrap_median_diff, d_ber_row, f_cross_row  # noqa: E402
from population import build_matched_hit_control, build_paired_population  # noqa: E402
from refiner_ctypes import Refiner  # noqa: E402

DEFAULT_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DEFAULT_DLL_SHA256 = "6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672"
EXPECTED_SHIM_VERSION = 20260042

ROW_0B_CONTROL_MEDIAN_MAX = 0.05     # 5% -- ROW 0b
ROW_0C_MIN_PAIRED_ROWS = 200          # ROW 0c
ROW_0D_DT_FLOOR_S = 0.005             # 5 ms -- ROW 0d
ROW_0D_DF_FLOOR_HZ = 0.25             # 0.25 Hz -- ROW 0d
ROW_1_D_BER_MIN = 0.15                # 15 pp -- ROW 1
ROW_1_CI_LO_MIN = 0.05                # 5 pp -- ROW 1
ROW_1_F_CROSS_MIN = 0.20              # ROW 1
ROW_2_D_BER_ABS_MAX = 0.05            # 5 pp -- ROW 2
ROW_2_CI_HI_MAX = 0.15                # 15 pp -- ROW 2


class WavCache:
    def __init__(self):
        self._cache: dict[str, "object"] = {}

    def get(self, ts: str):
        if ts not in self._cache:
            wav_path = os.path.join(_wav_dir(), ts + ".wav")
            pcm = P.read_wav(wav_path)
            pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)
            self._cache[ts] = pcm
        return self._cache[ts]


def _wav_dir() -> str:
    from population import WAV68_DIR
    return WAV68_DIR


def _anchor(grid_freq_hz: float, grid_dt: float) -> tuple[int, float]:
    """The GRID anchor BOTH extraction arms are built from.

    freq_hz is rounded to the nearest int Hz because ft8_refine_candidate's own
    coarse_freq_hz argument is a C int (matching FT8Result.freq_hz's own int type and
    r1/r1b's refiner_ctypes.Refiner.refine() convention) -- the refiner's reported
    (delta_f, delta_t) is defined RELATIVE TO whatever coarse position it was handed.

    GRID extraction MUST use this same rounded anchor, not the CSV's unrounded float
    freq_hz, so that REFINED = GRID + (delta_f, delta_t) exactly -- the two arms would
    otherwise differ by up to 0.5 Hz of rounding noise having nothing to do with the
    refiner, which is precisely the shape of confound this whole thread has been
    fighting (spec Sec.1's M1/M2 time-base confound, restated here for frequency
    rounding instead of a time base). The 3.125 Hz native lattice step (K_FREQ_OSR=2,
    symbol_period=0.16s) means this rounding is well inside half a lattice bin, so GRID
    still lands on the identical (freq_offset, freq_sub) the CSV's own float would have
    snapped to -- this is a comparability fix, not a resolution loss.
    dt is NOT rounded: ft8_refine_candidate's coarse_time_offset_s argument is a float,
    and the CSV's recorded dt already carries that precision.
    """
    return round(grid_freq_hz), grid_dt


def measure_row(ex: ExtractLLRs, refiner: Refiner, wav_cache: WavCache, row: dict) -> dict | None:
    """Returns a result dict (message text NEVER included) or None if the row could not
    be measured (a reason string is embedded for the counters in run())."""
    pcm = wav_cache.get(row["ts"])
    anchor_freq, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc_grid, llr_grid = ex.extract_at(pcm, float(anchor_freq), anchor_dt)
    if rc_grid != 0 or llr_grid is None:
        return {"reason": "grid_extract_rc_%d" % rc_grid}

    delta_f, delta_t, refine_score, coarse_dt_samp, fine_dt_samp, rc_refine = \
        refiner.refine(pcm, anchor_freq, anchor_dt)
    if rc_refine != 0:
        return {"reason": "refine_rc_%d" % rc_refine}

    refined_freq = anchor_freq + delta_f
    refined_dt = anchor_dt + delta_t
    rc_ref, llr_ref = ex.extract_at(pcm, refined_freq, refined_dt)
    if rc_ref != 0 or llr_ref is None:
        return {"reason": "refined_extract_rc_%d" % rc_ref}

    ber_grid = hard_decision_ber(llr_grid, true_bits)
    ber_refined = hard_decision_ber(llr_ref, true_bits)

    return {
        "ts": row["ts"],
        "population": row["population"],
        "ber_grid": ber_grid,
        "ber_refined": ber_refined,
        "d_ber": d_ber_row(ber_grid, ber_refined),
        "crosses": f_cross_row(ber_grid, ber_refined),
        "delta_f_hz": delta_f,
        "delta_t_s": delta_t,
        "refine_score": refine_score,
        "anchor_freq_hz": anchor_freq,
        "anchor_dt": anchor_dt,
    }


def run_control_check(ex: ExtractLLRs, wav_cache: WavCache, control_rows: list[dict]) -> dict:
    """ROW 0b: on the matched-hit control population, GRID-arm median BER must be <=5%
    and every extraction rc must be 0. Only the GRID arm is exercised -- ROW 0b is about
    whether the export is wired correctly, not about the refiner."""
    bers = []
    n_rc_nonzero = 0
    n_no_true_codeword = 0
    for row in control_rows:
        pcm = wav_cache.get(row["ts"])
        anchor_freq, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])
        true_bits = ex.true_codeword(row["message"])
        if true_bits is None:
            n_no_true_codeword += 1
            continue
        rc, llr = ex.extract_at(pcm, float(anchor_freq), anchor_dt)
        if rc != 0 or llr is None:
            n_rc_nonzero += 1
            continue
        bers.append(hard_decision_ber(llr, true_bits))

    median = float(st.median(bers)) if bers else float("nan")
    fires = (not bers) or median > ROW_0B_CONTROL_MEDIAN_MAX or n_rc_nonzero > 0
    return {
        "row": "0b", "fires": fires,
        "n_control": len(control_rows), "n_measured": len(bers),
        "n_rc_nonzero": n_rc_nonzero, "n_no_true_codeword": n_no_true_codeword,
        "median_ber": median, "threshold": ROW_0B_CONTROL_MEDIAN_MAX,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--limit", type=int, default=None,
                     help="cap the main population to this many rows (smoke runs only)")
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("N1 -- BER at the refiner's vs. the grid position")
    log("=" * 90)

    log("\n[MANDATORY] Running the sign unit test first (spec Sec.4)...")
    sign_rc = sign_unit_test.main()
    if sign_rc != 0:
        log("SIGN UNIT TEST FAILED -- refusing to arm the real harness.")
        return 1
    log("Sign unit test PASSED. Arming.\n")

    log("Loading DLL: %s" % args.dll_path)
    ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                      expected_shim_version=EXPECTED_SHIM_VERSION)
    refiner = Refiner(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                       expected_shim_version=EXPECTED_SHIM_VERSION)
    log("DLL SHA256 asserted (%s...), shim version %d confirmed on BOTH bindings.\n"
        % (args.dll_sha256[:16], ex.version))

    wav_cache = WavCache()

    log("=" * 90)
    log("ROW 0b -- control-population wiring check")
    log("=" * 90)
    control_rows = build_matched_hit_control()
    row0b = run_control_check(ex, wav_cache, control_rows)
    log("ROW 0b: n_control=%d n_measured=%d n_rc_nonzero=%d median_ber=%.2f%% (bound <=%.0f%%) "
        "-> %s" % (row0b["n_control"], row0b["n_measured"], row0b["n_rc_nonzero"],
                   row0b["median_ber"] * 100.0, row0b["threshold"] * 100.0,
                   "FIRES" if row0b["fires"] else "clear"))
    if row0b["fires"]:
        log("\nROW 0b FIRES: the new export does not reproduce the extraction the decoder "
            "actually performs. Harness invalid, NO VERDICT. QA fixes and re-runs.")
        _write_report(args.out_dir, {"final_row": "0b", "row_0b": row0b}, log_lines)
        return 2
    log("ROW 0b clear.\n")

    log("=" * 90)
    log("Building the candidate-present-and-failed population (THE 135 + THE 567)")
    log("=" * 90)
    population = build_paired_population()
    if args.limit is not None:
        population = population[: args.limit]
        log("--limit applied: n=%d (SMOKE RUN, not a valid gate evaluation)" % len(population))

    log("\n" + "=" * 90)
    log("Measuring GRID vs. REFINED for each row")
    log("=" * 90)
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        result = measure_row(ex, refiner, wav_cache, row)
        if result is None or "reason" in result:
            reasons[result["reason"] if result else "none"] = \
                reasons.get(result["reason"] if result else "none", 0) + 1
            continue
        rows.append(result)
        if (i + 1) % 100 == 0:
            log("  ... %d/%d rows processed (%d measured, %.1fs elapsed)"
                % (i + 1, len(population), len(rows), time.time() - t0))
    log("\nMeasured %d/%d rows (%.1fs). Drop reasons: %s"
        % (len(rows), len(population), time.time() - t0, reasons))

    result_bundle: dict = {"n_population": len(population), "n_measured": len(rows),
                            "drop_reasons": reasons, "row_0b": row0b}

    log("\n" + "=" * 90)
    log("ROW 0c -- underpowered check")
    log("=" * 90)
    row0c_fires = len(rows) < ROW_0C_MIN_PAIRED_ROWS
    log("n_paired=%d (bound >=%d) -> %s" % (len(rows), ROW_0C_MIN_PAIRED_ROWS,
                                             "FIRES" if row0c_fires else "clear"))
    result_bundle["row_0c"] = {"row": "0c", "fires": row0c_fires, "n_paired": len(rows),
                                "min_required": ROW_0C_MIN_PAIRED_ROWS}
    if row0c_fires:
        log("\nROW 0c FIRES: instrument failure, NOT a null. The candidate-present-and-failed "
            "population could not be assembled at >=200 pairs from the available corpora.")
        result_bundle["final_row"] = "0c"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 3

    log("\n" + "=" * 90)
    log("ROW 0d -- did the refiner move anything?")
    log("=" * 90)
    median_abs_dt = float(st.median(abs(r["delta_t_s"]) for r in rows))
    median_abs_df = float(st.median(abs(r["delta_f_hz"]) for r in rows))
    row0d_fires = median_abs_dt < ROW_0D_DT_FLOOR_S and median_abs_df < ROW_0D_DF_FLOOR_HZ
    log("median|delta_t|=%.4fs (floor %.4fs), median|delta_f|=%.4fHz (floor %.2fHz) -> %s"
        % (median_abs_dt, ROW_0D_DT_FLOOR_S, median_abs_df, ROW_0D_DF_FLOOR_HZ,
           "FIRES" if row0d_fires else "clear"))
    result_bundle["row_0d"] = {"row": "0d", "fires": row0d_fires,
                                "median_abs_delta_t_s": median_abs_dt,
                                "median_abs_delta_f_hz": median_abs_df,
                                "dt_floor_s": ROW_0D_DT_FLOOR_S, "df_floor_hz": ROW_0D_DF_FLOOR_HZ}
    if row0d_fires:
        log("\nROW 0d FIRES: the treatment arm is not a treatment (GRID and REFINED are "
            "effectively the same position). NO VERDICT, escalate.")
        result_bundle["final_row"] = "0d"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 4

    log("\n" + "=" * 90)
    log("Primary/secondary statistics")
    log("=" * 90)
    bootstrap = cluster_bootstrap_median_diff(rows, n_draws=args.n_draws)
    f_cross = float(sum(1 for r in rows if r["crosses"]) / len(rows))
    log("d_ber (paired median BER_grid - BER_refined): point_estimate=%+.2fpp mean=%+.2fpp "
        "se=%.2fpp CI95=[%+.2f, %+.2f]pp p=%.4f (n_rows=%d n_clusters=%d n_draws=%d)"
        % (bootstrap["point_estimate"] * 100, bootstrap["mean"] * 100, bootstrap["se"] * 100,
           bootstrap["ci95"][0] * 100, bootstrap["ci95"][1] * 100, bootstrap["p_two_sided"],
           bootstrap["n_rows"], bootstrap["n_clusters"], bootstrap["n_draws"]))
    log("f_cross (fraction crossing ABOVE->BELOW B50=%.1f%%): %.1f%%"
        % (B50_THRESHOLD * 100, f_cross * 100))
    result_bundle["d_ber"] = bootstrap
    result_bundle["f_cross"] = f_cross

    log("\nPer-population breakdown:")
    per_pop: dict[str, dict] = {}
    for label in sorted(set(r["population"] for r in rows)):
        sub = [r for r in rows if r["population"] == label]
        sub_bootstrap = cluster_bootstrap_median_diff(sub, n_draws=args.n_draws, seed=bootstrap["seed"])
        sub_fcross = float(sum(1 for r in sub if r["crosses"]) / len(sub)) if sub else float("nan")
        per_pop[label] = {"n": len(sub), "d_ber": sub_bootstrap, "f_cross": sub_fcross}
        log("  [%s] n=%d d_ber point_estimate=%+.2fpp CI95=[%+.2f,%+.2f]pp f_cross=%.1f%%"
            % (label, len(sub), sub_bootstrap["point_estimate"] * 100,
               sub_bootstrap["ci95"][0] * 100, sub_bootstrap["ci95"][1] * 100, sub_fcross * 100))
    result_bundle["per_population"] = per_pop

    log("\n" + "=" * 90)
    log("ROW 1/2/3 -- the gate, strict order")
    log("=" * 90)
    d_ber_pt = bootstrap["point_estimate"]
    ci_lo, ci_hi = bootstrap["ci95"]
    row1_fires = (d_ber_pt >= ROW_1_D_BER_MIN and ci_lo > ROW_1_CI_LO_MIN
                  and f_cross >= ROW_1_F_CROSS_MIN)
    row2_fires = (not row1_fires) and (abs(d_ber_pt) <= ROW_2_D_BER_ABS_MAX
                                        and ci_hi < ROW_2_CI_HI_MAX)

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES: d_ber=%+.2fpp (>=%.0fpp) AND CI_lo=%+.2fpp (>%.0fpp) AND "
            "f_cross=%.1f%% (>=%.0f%%)." % (d_ber_pt * 100, ROW_1_D_BER_MIN * 100,
                                             ci_lo * 100, ROW_1_CI_LO_MIN * 100,
                                             f_cross * 100, ROW_1_F_CROSS_MIN * 100))
        log("CONSEQUENCE: position is the root cause of the misread. R2 is justified and "
            "SIZED in decode units (f_cross = %.1f%% is its expected recall contribution)."
            % (f_cross * 100))
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES: |d_ber|=%.2fpp (<=%.0fpp) AND CI_hi=%+.2fpp (<%.0fpp)."
            % (abs(d_ber_pt) * 100, ROW_2_D_BER_ABS_MAX * 100, ci_hi * 100, ROW_2_CI_HI_MAX * 100))
        log("CONSEQUENCE: limb 1 is DEAD as a D-001 treatment. Extracting at a better "
            "position does not fix the reading -- the failure is in how the bits are "
            "formed (the non-coherent, magnitude-only, single-symbol metric), not where "
            "they are read. R2 as framed is dead; the next work is limb 2 (coherent "
            "multi-symbol LLRs).")
    else:
        final_row = "3"
        log("ROW 3 (partial/neither ROW 1 nor ROW 2 fired): d_ber=%+.2fpp CI95=[%+.2f,%+.2f]pp "
            "f_cross=%.1f%%." % (d_ber_pt * 100, ci_lo * 100, ci_hi * 100, f_cross * 100))
        log("CONSEQUENCE: escalate with the paired distribution and per-population table. "
            "Do not average to a verdict.")

    result_bundle["final_row"] = final_row
    _write_report(args.out_dir, result_bundle, log_lines)
    _write_rows(args.out_dir, rows)
    log("\nWrote results/n1_results.json, results/n1_gate_report.json, results/harness_run.log")
    return 0


def _strip_message_fields(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "message"} for r in rows]


def _write_rows(out_dir: str, rows: list[dict]) -> None:
    P.write_json(os.path.join(out_dir, "n1_results.json"), {"rows": _strip_message_fields(rows)})


def _write_report(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "n1_gate_report.json"), bundle)
    with open(os.path.join(out_dir, "harness_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
