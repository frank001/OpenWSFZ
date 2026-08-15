#!/usr/bin/env python3
"""M2 -- pre-registered gate evaluator.

Spec 4.2, verbatim pseudocode reproduced below. Rows mutually exclusive, evaluated
in STRICT ORDER, first match wins (HK-021(k), re-checked in the spec's own HK-025
self-check, section 4.2).

Primary statistic: rho_rb(HIT vs NULL) on |coarse_dt_samp| AT THE WINNING ANCHOR,
oriented so positive = HIT more concentrated than NULL. Reuses M1's exact stratify +
inverse-variance-pool + cluster-bootstrap machinery (m1_evaluate.pooled_contrast) by
transforming each row's "score" field to -abs(coarse_dt_samp) before calling it: since
pooled_contrast's rank-biserial convention is rho=+1 iff every "a" (HIT) value EXCEEDS
every "b" (NULL) value, feeding it NEGATIVE |coarse_dt_samp| makes rho positive exactly
when HIT's absolute deviations are SMALLER (more concentrated) than NULL's -- the
orientation the spec calls for.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m2_common import (  # noqa: E402
    RESULTS_DIR, STRATA, is_edge_winner, stratum_of, stratum_label, write_json,
)
import m1_evaluate  # noqa: E402 -- reuse rank_biserial / cluster bootstrap / pooled_contrast

RESULTS_PATH = os.path.join(RESULTS_DIR, "m2_results.json")
REPORT_PATH = os.path.join(RESULTS_DIR, "m2_gate_report.json")

# ── Spec 4.2 thresholds ──────────────────────────────────────────────────────────
ROW0A_CONTROL_MEDIAN_MAX = 2          # |coarse_dt_samp| samples (2 -> 10 ms @ 200 Hz)
ROW0B_STRATUM_MIN_N = 200
ROW0B_N_STRATA_OK_MIN = 4
ROW0C_EDGE_FRAC_MAX = 0.20
ROW0D_NULL_MEAN_DF_ABS_MAX = 1.0      # Hz

ROW1_RHO_MIN = 0.30
ROW1_CI_LO_MIN = 0.10
ROW2_RHO_ABS_MAX = 0.10
ROW2_CI_HI_MAX = 0.30


def to_concentration_rows(rows):
    """Rows with 'score' replaced by -abs(coarse_dt_samp), for reuse with
    m1_evaluate.pooled_contrast (which is written in terms of a 'score' field)."""
    return [{"snr_db": r["snr_db"], "cycle_id": r["cycle_id"],
              "score": -abs(r["coarse_dt_samp"])} for r in rows]


def m2_row(control_median_abs, n_strata_ok, edge_frac_hit, null_mean_df_abs,
           rho_rb, ci_lo, ci_hi) -> str:
    if control_median_abs > ROW0A_CONTROL_MEDIAN_MAX:
        return "ROW 0a"
    if n_strata_ok < ROW0B_N_STRATA_OK_MIN:
        return "ROW 0b"
    if edge_frac_hit > ROW0C_EDGE_FRAC_MAX:
        return "ROW 0c"
    if abs(null_mean_df_abs) > ROW0D_NULL_MEAN_DF_ABS_MAX:
        return "ROW 0d"
    if np.isnan(rho_rb) or np.isnan(ci_lo) or np.isnan(ci_hi):
        return "ROW 0b"  # pooled statistic unavailable -- power failure, not a null
    if rho_rb >= ROW1_RHO_MIN and ci_lo > ROW1_CI_LO_MIN:
        return "ROW 1"
    if abs(rho_rb) <= ROW2_RHO_ABS_MAX and ci_hi < ROW2_CI_HI_MAX:
        return "ROW 2"
    return "ROW 3"


def main():
    with open(RESULTS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    results = data["results"]
    print("loaded %d results (dll sha256=%s shim=%s)"
          % (len(results), data["dll_sha256"], data["shim_version"]))

    hit = [r for r in results if r["kind"] == "real" and r["arm"] == "HIT"]
    null = [r for r in results if r["kind"] == "real" and r["arm"] == "NULL"]
    control = [r for r in results if r["kind"] == "control"]
    print("HIT=%d NULL=%d CONTROL=%d" % (len(hit), len(null), len(control)))

    # ── ROW 0a: positive control concentration ──────────────────────────────────
    control_abs = np.array([abs(r["coarse_dt_samp"]) for r in control])
    control_median_abs = float(np.median(control_abs)) if len(control_abs) else float("nan")
    control_median_ms = control_median_abs * 5.0  # 200 Hz coarse stage: 1 sample = 5 ms
    print("\ncontrol median |coarse_dt_samp| = %.3f samples (%.1f ms)  (bar <= %d samples / 10 ms)"
          % (control_median_abs, control_median_ms, ROW0A_CONTROL_MEDIAN_MAX))

    # ── ROW 0b: power on the real HIT/NULL population ───────────────────────────
    n_strata_ok = 0
    strata_power = []
    for si in range(len(STRATA)):
        n_hit_s = sum(1 for r in hit if stratum_of(r["snr_db"]) == si)
        n_null_s = sum(1 for r in null if stratum_of(r["snr_db"]) == si)
        ok = n_hit_s >= ROW0B_STRATUM_MIN_N and n_null_s >= ROW0B_STRATUM_MIN_N
        strata_power.append({"stratum": stratum_label(si), "n_hit": n_hit_s, "n_null": n_null_s, "power_ok": ok})
        if ok:
            n_strata_ok += 1
    print("\nstrata power (need n>=%d in both HIT and NULL):" % ROW0B_STRATUM_MIN_N)
    for e in strata_power:
        print("  %-14s n_hit=%5d n_null=%5d  %s" % (e["stratum"], e["n_hit"], e["n_null"],
                                                       "OK" if e["power_ok"] else "UNDERPOWERED"))
    print("n_strata_ok = %d (need >= %d)" % (n_strata_ok, ROW0B_N_STRATA_OK_MIN))

    # ── ROW 0c: sweep still binds (HIT rows winning at the sweep's own edge) ────
    n_hit_edge = sum(1 for r in hit if is_edge_winner(r["df_anchor"], r["dt_anchor"]))
    edge_frac_hit = n_hit_edge / len(hit) if hit else float("nan")
    print("\nHIT edge-winner fraction: %d/%d = %.4f (bar <= %.2f)"
          % (n_hit_edge, len(hit), edge_frac_hit, ROW0C_EDGE_FRAC_MAX))

    # ── ROW 0d: sweep's own directional artefact on NULL ────────────────────────
    null_mean_df = float(np.mean([r["df_anchor"] for r in null])) if null else float("nan")
    print("NULL mean df_anchor: %.4f Hz (bar |.| <= %.2f)" % (null_mean_df, ROW0D_NULL_MEAN_DF_ABS_MAX))

    # ── Primary contrast: HIT vs NULL on -|coarse_dt_samp| at the winning anchor ─
    hit_c = to_concentration_rows(hit)
    null_c = to_concentration_rows(null)
    contrast = m1_evaluate.pooled_contrast(hit_c, null_c, "HIT vs NULL (concentration)")
    print("\nHIT vs NULL concentration contrast, per stratum:")
    for e in contrast["per_stratum"]:
        rho_s = "n/a" if e["rho_rb"] is None else "%.4f" % e["rho_rb"]
        se_s = "n/a" if not e.get("se_bootstrap") or np.isnan(e.get("se_bootstrap", float("nan"))) else "%.4f" % e["se_bootstrap"]
        print("  %-14s n_hit=%5d n_null=%5d power_ok=%-5s rho_rb=%8s se=%8s"
              % (e["stratum"], e["n_a"], e["n_b"], e["power_ok"], rho_s, se_s))
    print("pooled (inverse-variance, %d usable strata): rho_rb=%.4f  SE=%.4f  95%% CI=[%.4f, %.4f]"
          % (contrast["n_strata_usable"], contrast["pooled_rho_rb"], contrast["pooled_se"],
             contrast["ci_lo"], contrast["ci_hi"]))

    # ── Gate ──────────────────────────────────────────────────────────────────
    row = m2_row(control_median_abs, n_strata_ok, edge_frac_hit, null_mean_df,
                 contrast["pooled_rho_rb"], contrast["ci_lo"], contrast["ci_hi"])
    print("\n>>> %s <<<" % row)

    report = {
        "spec": "2026-08-15-1301-architect-to-qa-m1-ruling-and-m2-anchor-sweep-spec.md",
        "dll_sha256": data["dll_sha256"], "shim_version": data["shim_version"],
        "n_hit": len(hit), "n_null": len(null), "n_control": len(control),
        "control_median_abs_coarse_dt_samp": control_median_abs,
        "control_median_ms": control_median_ms,
        "n_strata_ok": n_strata_ok, "strata_power": strata_power,
        "edge_frac_hit": edge_frac_hit, "n_hit_edge": n_hit_edge,
        "null_mean_df_anchor_hz": null_mean_df,
        "hit_vs_null_concentration": contrast,
        "row": row,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(REPORT_PATH, report)
    print("\nreport written: %s" % REPORT_PATH)


if __name__ == "__main__":
    main()
