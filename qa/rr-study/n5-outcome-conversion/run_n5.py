#!/usr/bin/env python3
"""N5 -- does order-3 coherent extraction CONVERT on the FAILED population, at the
shipping lattice anchor, with no frequency estimator and no refinement?

Spec: qa/rr-study/2026-08-17-1648-architect-to-qa-n4-ruling-and-n5-spec.md Sec.6, AS
AMENDED by Sec.6.1 (Amendment 1 wins wherever the two disagree -- this harness
implements the AMENDED gate throughout, not the pre-amendment body).

Route N5-outcome (Captain's ruling 2026-08-17 16:52Z): N4 found the shipping lattice's
own frequency accuracy MARGINALLY sufficient for order-3 coherent extraction (H_3^cum
equals the 1.5625 Hz lattice half-cell to within 0.41%, CI straddles). That unblocks
testing limb 2 (coherent order-3 LLRs) directly on real audio, at the anchor the
lattice already delivers, with no estimator built first. N5 measures OUTCOME
(does a failed candidate turn into a decode?), not requirement.

Population: THE 135 + THE 567 (candidate-present-and-failed), N1's EXACT population
-- reused verbatim via n1-ber-at-refined-position/population.py.build_paired_population().

Arms, at the production candidate's own lattice anchor, NO search of any kind:
  V0      -- ft8_extract_llrs_at, unmodified native C (the shipping read), via
             run_n1._anchor()'s ROUNDED anchor (unchanged from N1/N2/N3/N4's V0).
  V3_cum  -- coherent_extract_ext's order-3 cumulative variant, UNROUNDED anchor
             (N4's mandatory fix), df_hz=0.0 -- no offset, no sweep, no search
             (spec scope: "No per-row frequency search... Rectangular window only").

Primary statistic: f_cross (crossable-denominator fraction, n1_stats.f_cross_row
reused VERBATIM per Amendment A1.2) alongside the MANDATORY f_break/f_net pair
(n5_stats.py, new this spec) -- see that module's docstring for the denominator
convention. d_ber is attribution-only (spec: "d_ber is NOT [primary] ... the failed
population sits at ~44% median BER -- 4x the correction threshold -- so aggregate BER
movement of a few pp converts nothing").

Gate, strict order (spec Sec.6 table, AS AMENDED by Sec.6.1):
  0a  THE 135 stratum ALONE (n~126), V0 median BER != 43.97%+/-2pp -> VALIDITY
      (Amendment A1.1: the pooled 405-row population has no published reference; only
      THE 135 does. THE 567's own median is reported but gates nothing.)
  0b  <200 paired rows OR <30 ts clusters (combined population) -> PRECISION, escalate
  0c  median V0-vs-V3_cum hard-decision disagreement <5 of 174 bits -> VALIDITY
      (the M4 lesson, reused from N2's own ROW 0d: same reading, contrast cannot move)
  0d  sign unit test fails -> VALIDITY, re-run, do NOT inherit N3/N4's pass

  ROW 1  CI_lo(f_cross) > 0.05 AND CI_lo(f_net) > 0        -> limb 2 CONVERTS materially
  ROW 2  CI_hi(f_cross) < 0.05                             -> upper-bounded below 5%,
                                                                BOTH LIMBS close, 2026-
                                                                08-11 diagnosis REOPENS
  ROW 3  residue (CI straddles 0.05)                       -> report interval, no side

ORDERING NOTE (disclosed, not a silent deviation): the spec's table lists 0d (the
sign unit test) fourth, after 0a/0b/0c. 0a/0b/0c all require the real measured
population; 0d does not (it is pure DSP/statistics, synthetic input only) and every
prior harness in this series (N1/N2/N3/N4) runs its own equivalent mandatory
pre-arm test FIRST, before spending time on real extraction, refusing to arm if it
fails. This harness follows that established precedent -- 0d is evaluated (and, if it
fires, reported as the final row) BEFORE 0a/0b/0c are even computable, since no row
data exists yet at that point. This changes nothing about which row fires: if 0d
fires, 0a/0b/0c could not have been evaluated regardless of table position (they need
data that is never gathered), so running 0d first has no effect on final_row selection
in the case that matters.

Runs the mandatory sign tests FIRST: n5_stats_sign_test.py (new f_break/f_net logic,
this spec) AND n4_sign_unit_test.py (V3_cum's own DSP correctness, RE-RUN per spec
ROW 0d, not inherited from N3/N4's prior pass). Refuses to arm unless BOTH return 0.

Scope (spec, verbatim): no src/, no Developer session, no DLL rebuild, no capture run
(HK-011 NOT engaged). No per-row frequency search, no time refinement, no aperture
sweep. Rectangular window only. DLL pinned by SHA256, asserted not inferred.

NFR-021: message TEXT is used in-process only (recovering true bits via
ft8_encode_message) and is NEVER written to a result file or printed; measure_row's
returned dict never carries a "message" key.
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
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n4-central-lobe-halfwidth"))
# n1-ber-at-refined-position MUST be inserted after r1-sync-refiner -- same trap n3/n4's
# own run_n*.py document: that dir has its OWN unrelated bare-named population.py.
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
import n4_sign_unit_test  # noqa: E402
import n5_stats_sign_test  # noqa: E402
from coherent_extract_ext import extract_variants_ext  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from n5_stats import (  # noqa: E402
    B50_THRESHOLD, cluster_bootstrap_f_cross_break_net, d_ber_row, f_break_row, f_cross_row,
)
from population import build_paired_population  # noqa: E402
from run_n1 import WavCache, _anchor  # noqa: E402 -- reuse N1's loader/anchor verbatim

DEFAULT_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DEFAULT_DLL_SHA256 = "6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672"
EXPECTED_SHIM_VERSION = 20260042

ROW_0A_TARGET = 0.4397          # THE 135 stratum ONLY, N1 results line 15 (n~=126)
ROW_0A_TOL = 0.02               # +/- 2pp
ROW_0B_MIN_ROWS = 200
ROW_0B_MIN_CLUSTERS = 30
ROW_0C_MIN_DISAGREE_BITS = 5    # out of 174, the M4/N2 ROW 0d lesson
ROW_1_CI_LO_F_CROSS_MIN = 0.05
ROW_2_CI_HI_F_CROSS_MAX = 0.05
ROW_SEC_REACHABLE_MAX = 0.20    # secondary, non-gating: BER_V0 < 20% (N1's published
                                 # p10=17.2% for THE 135, pre-registered before this run)
MIN_BREAKABLE_FOR_DESCRIPTIVE = 30  # HK-021(j): <30 rows in f_break's own denominator
                                     # -> report descriptive-only, never let f_net turn on it


def hd_disagreement(llr_a, llr_b) -> int:
    """Identical to N2's run_n2.hd_disagreement (the M4 lesson, reused not re-derived)."""
    hd_a = [1 if x > 0.0 else 0 for x in llr_a]
    hd_b = [1 if x > 0.0 else 0 for x in llr_b]
    return sum(1 for x, y in zip(hd_a, hd_b) if x != y)


def measure_row(ex: ExtractLLRs, wav_cache: WavCache, row: dict) -> "dict | None":
    """Returns a result dict (message text NEVER included) or a {"reason": ...} drop
    record."""
    pcm = wav_cache.get(row["ts"])
    anchor_freq_int, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])
    raw_freq_hz = float(row["grid_freq_hz"])  # UNROUNDED -- N4's mandatory fix for the
                                                # coherent variant only; V0 keeps the
                                                # rounded _anchor() frequency below.

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc0, llr_v0 = ex.extract_at(pcm, float(anchor_freq_int), anchor_dt)
    if rc0 != 0 or llr_v0 is None:
        return {"reason": "v0_extract_rc_%d" % rc0}

    pcm64 = np.asarray(pcm, dtype=np.float64)
    variants = extract_variants_ext(pcm64, raw_freq_hz, anchor_dt, df_hz=0.0)
    llr_v3 = list(variants["V3_cum"])

    ber_v0 = hard_decision_ber(llr_v0, true_bits)
    ber_v3 = hard_decision_ber(llr_v3, true_bits)

    return {
        "ts": row["ts"],
        "population": row["population"],
        "ber_v0": ber_v0,
        "ber_v3": ber_v3,
        "d_ber": d_ber_row(ber_v0, ber_v3),
        "crosses": f_cross_row(ber_v0, ber_v3),
        "breaks": f_break_row(ber_v0, ber_v3),
        "hd_disagree_v0_v3": hd_disagreement(llr_v0, llr_v3),
        "anchor_freq_hz": anchor_freq_int,
        "anchor_dt": anchor_dt,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--limit", type=int, default=None,
                     help="cap the population to this many rows (smoke runs only)")
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("N5 -- does order-3 coherent extraction CONVERT on the FAILED population?")
    log("=" * 90)

    log("\n[MANDATORY] Running BOTH sign unit tests first (spec ROW 0d, re-run not inherited)...")
    log("-- (a) n5_stats_sign_test.py (new f_break/f_net logic) --")
    rc_a = n5_stats_sign_test.main()
    log("-- (b) n4_sign_unit_test.py (V3_cum DSP correctness, re-run fresh) --")
    rc_b = n4_sign_unit_test.main()
    if rc_a != 0 or rc_b != 0:
        log("\nROW 0d FIRES (evaluated first, per this file's ORDERING NOTE): sign "
            "unit test(s) failed (a=%d b=%d). Refusing to arm the real harness. NO VERDICT."
            % (rc_a, rc_b))
        row_0d = {"row": "0d", "fires": True, "rc_f_break_net_sign_test": rc_a,
                   "rc_n4_dsp_sign_test": rc_b}
        _write_report(args.out_dir, {"final_row": "0d", "row_0d": row_0d}, log_lines)
        return 1
    log("Both sign unit tests PASSED. Arming.\n")

    log("Loading DLL: %s" % args.dll_path)
    ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                      expected_shim_version=EXPECTED_SHIM_VERSION)
    log("DLL SHA256 asserted (%s...), shim version %d confirmed.\n"
        % (args.dll_sha256[:16], ex.version))

    wav_cache = WavCache()

    log("=" * 90)
    log("Building the candidate-present-and-failed population (THE 135 + THE 567, N1's exact pop)")
    log("=" * 90)
    population = build_paired_population()
    if args.limit is not None:
        population = population[: args.limit]
        log("--limit applied: n=%d (SMOKE RUN, not a valid gate evaluation)" % len(population))

    log("\n" + "=" * 90)
    log("Measuring V0 vs V3_cum for each row")
    log("=" * 90)
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        result = measure_row(ex, wav_cache, row)
        if result is None or "reason" in result:
            reason = result["reason"] if result else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(result)
        if (i + 1) % 100 == 0:
            log("  ... %d/%d rows processed (%d measured, %.1fs elapsed)"
                % (i + 1, len(population), len(rows), time.time() - t0))
    log("\nMeasured %d/%d rows (%.1fs). Drop reasons: %s"
        % (len(rows), len(population), time.time() - t0, reasons))

    result_bundle: dict = {"n_population": len(population), "n_measured": len(rows),
                            "drop_reasons": reasons, "b50_threshold": B50_THRESHOLD}

    log("\n" + "=" * 90)
    log("ROW 0a -- THE 135 stratum ALONE, V0 median BER vs N1's own 43.97%%+/-2pp (Amendment A1.1)")
    log("=" * 90)
    rows_135 = [r for r in rows if r["population"] == "135"]
    rows_567 = [r for r in rows if r["population"] == "567"]
    median_v0_135 = float(st.median(r["ber_v0"] for r in rows_135)) if rows_135 else float("nan")
    median_v0_567 = float(st.median(r["ber_v0"] for r in rows_567)) if rows_567 else float("nan")
    row0a_fires = (not rows_135) or abs(median_v0_135 - ROW_0A_TARGET) > ROW_0A_TOL
    log("THE 135 (n=%d): V0 median BER=%.2f%% (target %.2f%%+/-%.0fpp) -> %s"
        % (len(rows_135), median_v0_135 * 100, ROW_0A_TARGET * 100, ROW_0A_TOL * 100,
           "FIRES" if row0a_fires else "clear"))
    log("THE 567 (n=%d): V0 median BER=%.2f%% (NO published reference -- reported, GATES NOTHING)"
        % (len(rows_567), median_v0_567 * 100 if rows_567 else float("nan")))
    result_bundle["row_0a"] = {"row": "0a", "fires": row0a_fires, "n_135": len(rows_135),
                                "median_v0_ber_135": median_v0_135, "target": ROW_0A_TARGET,
                                "tol": ROW_0A_TOL, "n_567": len(rows_567),
                                "median_v0_ber_567_non_gating": median_v0_567}
    if row0a_fires:
        log("\nROW 0a FIRES: not N1's population/instrument. NO VERDICT.")
        result_bundle["final_row"] = "0a"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 2
    log("ROW 0a clear.\n")

    log("=" * 90)
    log("ROW 0b -- underpowered? (<200 paired rows OR <30 ts clusters, combined population)")
    log("=" * 90)
    n_clusters_total = len({r["ts"] for r in rows})
    row0b_fires = len(rows) < ROW_0B_MIN_ROWS or n_clusters_total < ROW_0B_MIN_CLUSTERS
    log("n_paired=%d (bound >=%d), n_clusters=%d (bound >=%d) -> %s"
        % (len(rows), ROW_0B_MIN_ROWS, n_clusters_total, ROW_0B_MIN_CLUSTERS,
           "FIRES" if row0b_fires else "clear"))
    result_bundle["row_0b"] = {"row": "0b", "fires": row0b_fires, "n_paired": len(rows),
                                "n_clusters": n_clusters_total, "min_rows": ROW_0B_MIN_ROWS,
                                "min_clusters": ROW_0B_MIN_CLUSTERS}
    if row0b_fires:
        log("\nROW 0b FIRES: instrument failure, NOT a null. PRECISION, escalate.")
        result_bundle["final_row"] = "0b"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 3
    log("ROW 0b clear.\n")

    log("=" * 90)
    log("ROW 0c -- can the contrast move at all? (median V0-vs-V3_cum hard-decision disagreement)")
    log("=" * 90)
    median_disagree = float(st.median(r["hd_disagree_v0_v3"] for r in rows))
    row0c_fires = median_disagree < ROW_0C_MIN_DISAGREE_BITS
    log("median hard-decision disagreement V0 vs V3_cum = %.1f bits/174 (floor %d) -> %s"
        % (median_disagree, ROW_0C_MIN_DISAGREE_BITS, "FIRES" if row0c_fires else "clear"))
    result_bundle["row_0c"] = {"row": "0c", "fires": row0c_fires,
                                "median_disagree_bits": median_disagree,
                                "floor_bits": ROW_0C_MIN_DISAGREE_BITS}
    if row0c_fires:
        log("\nROW 0c FIRES: V0 and V3_cum are the same reading; no contrast is "
            "possible. VALIDITY, escalate.")
        result_bundle["final_row"] = "0c"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 4
    log("ROW 0c clear.\n")

    log("=" * 90)
    log("Primary/secondary statistics")
    log("=" * 90)
    boot = cluster_bootstrap_f_cross_break_net(rows, n_draws=args.n_draws)
    pt = boot["point"]
    log("f_cross (own denom, n_crossable=%d/%d clusters=%d): point=%.2f%% CI95=[%.2f, %.2f]%%"
        % (pt["n_crossable"], pt["n_total"], pt["n_clusters_crossable"],
           boot["point"]["f_cross"] * 100 if not np.isnan(boot["point"]["f_cross"]) else float("nan"),
           boot["f_cross"]["ci95"][0] * 100, boot["f_cross"]["ci95"][1] * 100))
    if pt["n_breakable"] < MIN_BREAKABLE_FOR_DESCRIPTIVE:
        log("f_break (own denom, n_breakable=%d/%d clusters=%d): point=%.2f%% -- "
            "DESCRIPTIVE ONLY, denominator <%d rows (HK-021(j))"
            % (pt["n_breakable"], pt["n_total"], pt["n_clusters_breakable"],
               pt["f_break"] * 100 if not np.isnan(pt["f_break"]) else float("nan"),
               MIN_BREAKABLE_FOR_DESCRIPTIVE))
    else:
        log("f_break (own denom, n_breakable=%d/%d clusters=%d): point=%.2f%% CI95=[%.2f, %.2f]%%"
            % (pt["n_breakable"], pt["n_total"], pt["n_clusters_breakable"],
               pt["f_break"] * 100, boot["f_break"]["ci95"][0] * 100, boot["f_break"]["ci95"][1] * 100))
    log("f_net = f_cross - f_break, both re-based on the WHOLE population (n=%d): "
        "point=%+.2f%% CI95=[%+.2f, %+.2f]%%"
        % (pt["n_total"], pt["f_net"] * 100, boot["f_net"]["ci95"][0] * 100,
           boot["f_net"]["ci95"][1] * 100))
    result_bundle["bootstrap"] = boot

    d_ber_rows = [{"ts": r["ts"], "d_ber": r["d_ber"]} for r in rows]
    from n1_stats import cluster_bootstrap_median_diff  # noqa: PLC0415
    d_ber_stats = cluster_bootstrap_median_diff(d_ber_rows, n_draws=args.n_draws)
    log("\nd_ber (ATTRIBUTION ONLY, not primary -- failed population sits at ~44%% median "
        "BER, 4x the correction threshold): point=%+.2fpp CI95=[%+.2f, %+.2f]pp"
        % (d_ber_stats["point_estimate"] * 100, d_ber_stats["ci95"][0] * 100,
           d_ber_stats["ci95"][1] * 100))
    result_bundle["d_ber_attribution_only"] = d_ber_stats

    log("\nSecondary, NON-GATING: f_cross restricted to the reachable stratum "
        "BER_V0 < %.0f%% (pre-registered from N1's published p10=17.2%%)" % (ROW_SEC_REACHABLE_MAX * 100))
    reachable_rows = [r for r in rows if r["ber_v0"] < ROW_SEC_REACHABLE_MAX]
    if reachable_rows:
        boot_reachable = cluster_bootstrap_f_cross_break_net(reachable_rows, n_draws=args.n_draws)
        log("  n_reachable=%d, clusters=%d: f_cross point=%.2f%% CI95=[%.2f, %.2f]%%"
            % (len(reachable_rows), len({r["ts"] for r in reachable_rows}),
               boot_reachable["point"]["f_cross"] * 100 if not np.isnan(boot_reachable["point"]["f_cross"]) else float("nan"),
               boot_reachable["f_cross"]["ci95"][0] * 100, boot_reachable["f_cross"]["ci95"][1] * 100))
        result_bundle["secondary_reachable_stratum"] = {
            "n_reachable": len(reachable_rows),
            "n_clusters_reachable": len({r["ts"] for r in reachable_rows}),
            "bootstrap": boot_reachable,
        }
    else:
        log("  n_reachable=0 -- no rows below the 20%% stratum bar.")
        result_bundle["secondary_reachable_stratum"] = {"n_reachable": 0}

    log("\nPer-population breakdown (non-gating context):")
    per_pop: dict[str, dict] = {}
    for label, sub in (("135", rows_135), ("567", rows_567)):
        if not sub:
            continue
        sub_boot = cluster_bootstrap_f_cross_break_net(sub, n_draws=args.n_draws, seed=boot["seed"])
        per_pop[label] = {"n": len(sub), "bootstrap": sub_boot}
        log("  [%s] n=%d f_cross=%.2f%% f_break=%.2f%% f_net=%+.2f%%"
            % (label, len(sub),
               sub_boot["point"]["f_cross"] * 100 if not np.isnan(sub_boot["point"]["f_cross"]) else float("nan"),
               sub_boot["point"]["f_break"] * 100 if not np.isnan(sub_boot["point"]["f_break"]) else float("nan"),
               sub_boot["point"]["f_net"] * 100))
    result_bundle["per_population"] = per_pop

    log("\n" + "=" * 90)
    log("ROW 1/2/3 -- the gate, strict order, AS AMENDED (A1.2)")
    log("=" * 90)
    ci_lo_cross, ci_hi_cross = boot["f_cross"]["ci95"]
    ci_lo_net, _ci_hi_net = boot["f_net"]["ci95"]
    row1_fires = ci_lo_cross > ROW_1_CI_LO_F_CROSS_MIN and ci_lo_net > 0.0
    row2_fires = (not row1_fires) and ci_hi_cross < ROW_2_CI_HI_F_CROSS_MAX

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES: CI_lo(f_cross)=%.2f%% (>%.0f%%) AND CI_lo(f_net)=%+.2f%% (>0%%)."
            % (ci_lo_cross * 100, ROW_1_CI_LO_F_CROSS_MIN * 100, ci_lo_net * 100))
        log("CONSEQUENCE: limb 2 CONVERTS materially -- C integration becomes scopeable "
            "and a proper sizing is ORDERED. Does NOT authorise building it.")
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES: CI_hi(f_cross)=%.2f%% (<%.0f%%)."
            % (ci_hi_cross * 100, ROW_2_CI_HI_F_CROSS_MAX * 100))
        log("CONSEQUENCE: limb 2's prize is upper-bounded below %.0f%% of the crossable "
            "population -- against a ~23pp D-001 prize this is not the treatment. BOTH "
            "LIMBS close on outcome evidence and the 2026-08-11 diagnosis REOPENS."
            % (ROW_2_CI_HI_F_CROSS_MAX * 100))
    else:
        final_row = "3"
        log("ROW 3 (residue -- CI straddles %.0f%%): CI(f_cross)=[%.2f, %.2f]%%, "
            "CI(f_net)=[%+.2f, %+.2f]%%." % (ROW_1_CI_LO_F_CROSS_MIN * 100, ci_lo_cross * 100,
                                              ci_hi_cross * 100, boot["f_net"]["ci95"][0] * 100,
                                              boot["f_net"]["ci95"][1] * 100))
        log("CONSEQUENCE: report the interval, do NOT pick a side.")

    result_bundle["final_row"] = final_row
    result_bundle["gate_ci_f_cross"] = [ci_lo_cross, ci_hi_cross]
    result_bundle["gate_ci_f_net"] = boot["f_net"]["ci95"]

    _write_report(args.out_dir, result_bundle, log_lines)
    _write_rows(args.out_dir, rows)
    log("\nWrote results/n5_results.json, results/n5_gate_report.json, results/harness_run.log")
    return 0


def _write_rows(out_dir: str, rows: list[dict]) -> None:
    # rows already carry ONLY ts + numeric fields (measure_row never stores message text
    # past its own local scope) -- NFR-021.
    P.write_json(os.path.join(out_dir, "n5_results.json"), {"rows": rows})


def _write_report(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "n5_gate_report.json"), bundle)
    with open(os.path.join(out_dir, "harness_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
