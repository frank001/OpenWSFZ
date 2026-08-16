#!/usr/bin/env python3
"""M4 -- pre-registered gate evaluator.

Spec 2026-08-15-1658-architect-to-qa-m4-corrected-anchor-spec.md S6, verbatim
pseudocode reproduced below. Rows mutually exclusive, evaluated in STRICT
ORDER, first match wins (HK-021(k)).

HK-025 classification is re-derived independently in m4_hk025_check() before
this is ever run, and QA refuses under HK-025 if it disagrees -- including
with the Architect's own §7 table.

Primary statistic: rho_conc, the rank-biserial correlation between arm and
|coarse_dt_samp|, signed so positive = HIT more concentrated. Lifted from
m1_evaluate.pooled_contrast (metric swapped, not rewritten -- see m4_stats.py).
The mandatory sign unit test (test_m4_rho_conc_sign.py) must pass before this
is ever run against real data -- QA ran it and recorded the result in §11 of
the results report before arming m4_run_harness.py.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m4_common import (  # noqa: E402
    COARSE_RAIL_SAMP, COARSE_UNIFORM_MEAN, COARSE_UNIFORM_MEDIAN,
    COARSE_UNIFORM_RAIL_FRAC, M3_RESULTS_PATH, N_STRATA_OK_MIN, RESULTS_DIR,
    ROW0C_RAIL_FRAC_MAX, ROW0D_NULL_MEDIAN_ABS_MAX_STEPS,
    ROW0D_SLOPE_ABS_MAX_STEPS_PER_S, ROW0D_SLOPE_P_MAX, ROW1_CI_LO_MIN,
    ROW1_RHO_MIN, ROW2_CI_HI_MAX, ROW2_RHO_ABS_MAX, STRATA, STRATUM_MIN_N,
    is_coarse_railed, stratum_label, stratum_of, write_json,
)
from m4_stats import ols_cluster_robust, rho_conc  # noqa: E402

RESULTS_PATH = os.path.join(RESULTS_DIR, "m4_results.json")
REPORT_PATH = os.path.join(RESULTS_DIR, "m4_gate_report.json")

ROW0A_CONTROL_COARSE_MEDIAN_MAX = 3  # spec S6 ROW 0a (uniform floor 6.0, M3 measured 1.0)


def m4_hk025_check():
    """Independent re-derivation of the HK-025 classification for ROW 0a-0d,
    per spec S7's own instruction: QA re-derives this independently and may
    refuse without the Architect's agreement, including against the spec's own
    §7 table.

    Two-step test per HK-025: (1) CLASSIFY -- if the row fires, is rho_conc
    still an estimate of what the gate names ("does the refiner concentrate
    real signals more tightly than a signal-free position, at the corrected
    anchor")? (2) EVALUATE BOTH BRANCHES -- do fire/no-fire route to genuinely
    different actions, or would QA write the same row either way (DIAGNOSTIC)?

    ROW 0a (harness invalid): if it fires, the harness cannot even relocate a
    KNOWN position or every call errored -- rho_conc on the real arms is not
    an estimate of anything, the plumbing itself is unverified. VALIDITY.
    Branches differ (fix+rerun, no verdict vs proceed). Not diagnostic.
    ROW 0b (underpowered): if it fires, too few strata carry reliable data for
    the pooled statistic to mean anything -- an instrument failure, not a
    measured null. VALIDITY. Branches differ (no verdict vs proceed). Not
    diagnostic.
    ROW 0c (metric censored by the aperture): if it fires, |coarse_dt_samp| is
    pinned at the rail for a large fraction of one arm -- it stops estimating
    concentration and starts estimating "how often the true position fell
    outside a fixed-anchor call's reach". VALIDITY. Branches differ (escalate,
    no verdict vs proceed). Not diagnostic.
    ROW 0d (NULL has its own direction): if it fires, the reference arm is not
    a neutral "signal-free" baseline -- rho_conc becomes a comparison against a
    biased reference, not against "nothing there". VALIDITY. Branches differ
    (escalate, no verdict vs proceed to ROW1/2/3). Not diagnostic.

    Concurs with the spec's own §7 self-classification (all four VALIDITY,
    none diagnostic). No refusal.
    """
    return {
        "ROW 0a": {"class": "VALIDITY", "reason": "harness cannot relocate a known position / a call errored"},
        "ROW 0b": {"class": "VALIDITY", "reason": "insufficient population, not a measured null"},
        "ROW 0c": {"class": "VALIDITY", "reason": "coarse_dt_samp censored at the aperture rail"},
        "ROW 0d": {"class": "VALIDITY", "reason": "reference (NULL) arm has its own directional artefact"},
        "concurs_with_spec": True,
        "refusal": False,
    }


def m4_row(control_median_coarse, n_rc_nonzero, control_dt_offset_ok,
           n_strata_ok, hit_rail_frac, null_rail_frac,
           null_median_signed_coarse, null_slope_p, null_slope_abs,
           pooled_rho, ci_lo, ci_hi) -> str:
    if (np.isnan(control_median_coarse) or control_median_coarse > ROW0A_CONTROL_COARSE_MEDIAN_MAX
            or n_rc_nonzero != 0 or not control_dt_offset_ok):
        return "ROW 0a"
    if n_strata_ok < N_STRATA_OK_MIN:
        return "ROW 0b"
    if hit_rail_frac > ROW0C_RAIL_FRAC_MAX or null_rail_frac > ROW0C_RAIL_FRAC_MAX:
        return "ROW 0c"
    cond1 = null_median_signed_coarse is not None and abs(null_median_signed_coarse) > ROW0D_NULL_MEDIAN_ABS_MAX_STEPS
    cond2 = (not np.isnan(null_slope_p) and null_slope_p < ROW0D_SLOPE_P_MAX
             and not np.isnan(null_slope_abs) and null_slope_abs > ROW0D_SLOPE_ABS_MAX_STEPS_PER_S)
    if cond1 or cond2:
        return "ROW 0d"
    if np.isnan(pooled_rho) or np.isnan(ci_lo) or np.isnan(ci_hi):
        return "ROW 3"  # pooled statistic unavailable but ROW 0s all passed -- partial, escalate
    if pooled_rho >= ROW1_RHO_MIN and ci_lo > ROW1_CI_LO_MIN:
        return "ROW 1"
    if abs(pooled_rho) <= ROW2_RHO_ABS_MAX and ci_hi < ROW2_CI_HI_MAX:
        return "ROW 2"
    return "ROW 3"


def _median_or_none(vals):
    return float(np.median(vals)) if len(vals) else None


def replication_leg():
    """Spec S5.5: M3 recorded all 49 calls per row, so the dt_offset=+0.45
    column of m3_results.json IS M4's exact call on a 1,400-row subsample --
    a free, independent wiring check the positive control structurally
    cannot see. Non-gating."""
    with open(M3_RESULTS_PATH, encoding="utf-8") as fh:
        m3 = json.load(fh)

    TARGET_DT = 0.45
    hit_rows, null_rows = [], []
    n_missing = 0
    for r in m3["results"]:
        if r["kind"] != "real" or r["arm"] not in ("HIT", "NULL"):
            continue
        match = None
        for dt_off, score, coarse_dt_samp, fine_dt_samp, delta_f, rc in r["calls"]:
            if abs(dt_off - TARGET_DT) < 1e-9:
                match = {"snr_db": r["snr_db"], "cycle_id": r["cycle_id"],
                         "coarse_dt_samp": coarse_dt_samp, "score": score, "rc": rc}
                break
        if match is None:
            n_missing += 1
            continue
        (hit_rows if r["arm"] == "HIT" else null_rows).append(match)

    result = rho_conc(hit_rows, null_rows, "M4 replication (M3 dt_offset=+0.45 column)")
    return {
        "n_hit": len(hit_rows), "n_null": len(null_rows), "n_missing_dt45_call": n_missing,
        "pooled_rho_conc": result["pooled_rho_rb"], "pooled_se": result["pooled_se"],
        "ci_lo": result["ci_lo"], "ci_hi": result["ci_hi"],
        "per_stratum": result["per_stratum"],
    }


def main():
    with open(RESULTS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    results = data["results"]
    print("loaded %d results (dll sha256=%s shim=%s)" % (len(results), data["dll_sha256"], data["shim_version"]))

    hk025 = m4_hk025_check()
    print("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
          % (hk025["concurs_with_spec"], hk025["refusal"]))
    if hk025["refusal"]:
        print("REFUSING TO EVALUATE PER HK-025 -- see classification table in report.")
        report = {"spec": data["spec"], "hk025_classification": hk025, "row": "REFUSED"}
        os.makedirs(RESULTS_DIR, exist_ok=True)
        write_json(REPORT_PATH, report)
        return

    hit = [r for r in results if r["kind"] == "real" and r["arm"] == "HIT"]
    miss = [r for r in results if r["kind"] == "real" and r["arm"] == "MISS"]
    null = [r for r in results if r["kind"] == "real" and r["arm"] == "NULL"]
    control = [r for r in results if r["kind"] == "control"]
    print("HIT=%d MISS=%d NULL=%d CONTROL=%d" % (len(hit), len(miss), len(null), len(control)))

    n_rc_nonzero = data["n_rc_nonzero"]
    control_dt_offset_ok = all(r["dt_offset_applied"] == 0.0 for r in control)

    # -- ROW 0a: harness invalid -------------------------------------------------
    control_coarse = [abs(r["coarse_dt_samp"]) for r in control]
    control_median_coarse = _median_or_none(control_coarse)
    print("\ncontrol median |coarse_dt_samp| = %s (bar <= %d; uniform floor %.1f)"
          % ("n/a" if control_median_coarse is None else "%.3f" % control_median_coarse,
             ROW0A_CONTROL_COARSE_MEDIAN_MAX, COARSE_UNIFORM_MEDIAN))
    print("n_rc_nonzero (whole run) = %d ; control dt_offset all 0.0 = %s" % (n_rc_nonzero, control_dt_offset_ok))

    # -- ROW 0b: strata power on HIT/NULL -----------------------------------------
    n_strata_ok = 0
    strata_power = []
    for si in range(len(STRATA)):
        n_hit_s = sum(1 for r in hit if stratum_of(r["snr_db"]) == si)
        n_null_s = sum(1 for r in null if stratum_of(r["snr_db"]) == si)
        ok = n_hit_s >= STRATUM_MIN_N and n_null_s >= STRATUM_MIN_N
        strata_power.append({"stratum": stratum_label(si), "n_hit": n_hit_s, "n_null": n_null_s, "power_ok": ok})
        if ok:
            n_strata_ok += 1
    print("\nstrata power (need n>=%d in both HIT and NULL):" % STRATUM_MIN_N)
    for e in strata_power:
        print("  %-14s n_hit=%5d n_null=%5d  %s" % (e["stratum"], e["n_hit"], e["n_null"],
                                                       "OK" if e["power_ok"] else "UNDERPOWERED"))
    print("n_strata_ok = %d (need >= %d)" % (n_strata_ok, N_STRATA_OK_MIN))

    # -- ROW 0c: coarse-stage internal-aperture rail ------------------------------
    hit_rail_n = sum(1 for r in hit if is_coarse_railed(r["coarse_dt_samp"]))
    null_rail_n = sum(1 for r in null if is_coarse_railed(r["coarse_dt_samp"]))
    hit_rail_frac = hit_rail_n / len(hit) if hit else float("nan")
    null_rail_frac = null_rail_n / len(null) if null else float("nan")
    print("\nHIT railed (|coarse_dt_samp|=%d): %d/%d = %.4f (bar <= %.2f; uniform floor %.4f)"
          % (COARSE_RAIL_SAMP, hit_rail_n, len(hit), hit_rail_frac, ROW0C_RAIL_FRAC_MAX, COARSE_UNIFORM_RAIL_FRAC))
    print("NULL railed (|coarse_dt_samp|=%d): %d/%d = %.4f (bar <= %.2f; uniform floor %.4f)"
          % (COARSE_RAIL_SAMP, null_rail_n, len(null), null_rail_frac, ROW0C_RAIL_FRAC_MAX, COARSE_UNIFORM_RAIL_FRAC))

    # -- ROW 0d: NULL's own directional artefact ----------------------------------
    null_signed_coarse = [r["coarse_dt_samp"] for r in null]
    null_median_signed_coarse = _median_or_none(null_signed_coarse)
    null_base_dt = [r["anchor_dt_s"] for r in null]
    null_cycle_ids = [r["cycle_id"] for r in null]
    ols = ols_cluster_robust(null_base_dt, null_signed_coarse, null_cycle_ids)
    null_slope_abs = abs(ols["slope"]) if not np.isnan(ols["slope"]) else float("nan")
    print("\nNULL median signed coarse_dt_samp = %s (bar |.| <= %d steps = %.0f ms)"
          % ("n/a" if null_median_signed_coarse is None else "%.3f" % null_median_signed_coarse,
             ROW0D_NULL_MEDIAN_ABS_MAX_STEPS, ROW0D_NULL_MEDIAN_ABS_MAX_STEPS * 5.0))
    print("NULL OLS slope(coarse_dt_samp ~ anchor_dt_s), cluster-robust: slope=%.4f steps/s  se=%.4f  "
          "p=%.6f  n_clusters=%d  (bar: p<%.2f AND |slope|>%.1f)"
          % (ols["slope"], ols["se_slope"], ols["p_value"], ols["n_clusters"],
             ROW0D_SLOPE_P_MAX, ROW0D_SLOPE_ABS_MAX_STEPS_PER_S))

    # -- Primary: rho_conc, HIT vs NULL -------------------------------------------
    primary = rho_conc(hit, null, "M4 primary HIT vs NULL")
    print("\nrho_conc (HIT vs NULL), per stratum:")
    for e in primary["per_stratum"]:
        rho_s = "n/a" if e["rho_rb"] is None else "%.4f" % e["rho_rb"]
        se_s = "n/a" if not e.get("se_bootstrap") or np.isnan(e.get("se_bootstrap", float("nan"))) else "%.4f" % e["se_bootstrap"]
        print("  %-14s n_hit=%5d n_null=%5d power_ok=%-5s rho_conc=%8s se=%8s"
              % (e["stratum"], e["n_a"], e["n_b"], e["power_ok"], rho_s, se_s))
    print("pooled (inverse-variance, %d usable strata): rho_conc=%.4f  SE=%.4f  95%% CI=[%.4f, %.4f]"
          % (primary["n_strata_usable"], primary["pooled_rho_rb"], primary["pooled_se"],
             primary["ci_lo"], primary["ci_hi"]))

    # -- Gate -----------------------------------------------------------------------
    row = m4_row(control_median_coarse if control_median_coarse is not None else float("nan"),
                 n_rc_nonzero, control_dt_offset_ok, n_strata_ok, hit_rail_frac, null_rail_frac,
                 null_median_signed_coarse, ols["p_value"], null_slope_abs,
                 primary["pooled_rho_rb"], primary["ci_lo"], primary["ci_hi"])
    print("\n>>> %s <<<" % row)

    # -- Secondary S1/S2 -- computed always, readable only on ROW 1 (spec S5.4) --
    s1 = None
    if hit and miss:
        # S1: sync-vs-extraction, lifted unchanged from m1_evaluate.pooled_contrast
        # (the "score" field already present on every M4 result row).
        from m1_evaluate import pooled_contrast  # noqa: PLC0415
        s1 = pooled_contrast(hit, miss, "S1 HIT vs MISS on score")
    s2 = rho_conc(hit, miss, "S2 HIT vs MISS positional") if hit and miss else None
    secondary_readable = row == "ROW 1"
    print("\nsecondary S1/S2 computed=%s readable=%s (per spec S5.4: withheld unless ROW 1)"
          % (s1 is not None and s2 is not None, secondary_readable))
    if s1 is not None:
        print("  S1 pooled rho_rb (HIT vs MISS, score) = %.4f  CI=[%.4f, %.4f]  %s"
              % (s1["pooled_rho_rb"], s1["ci_lo"], s1["ci_hi"],
                 "READABLE" if secondary_readable else "WITHHELD -- not a finding at this gate row"))
    if s2 is not None:
        print("  S2 pooled rho_conc (HIT vs MISS, position) = %.4f  CI=[%.4f, %.4f]  %s"
              % (s2["pooled_rho_rb"], s2["ci_lo"], s2["ci_hi"],
                 "READABLE" if secondary_readable else "WITHHELD -- not a finding at this gate row"))

    # -- Replication leg (spec S5.5) -- free, non-gating, second HK-022 guard ----
    repl = replication_leg()
    repl_row = m4_row(control_median_coarse if control_median_coarse is not None else float("nan"),
                       n_rc_nonzero, control_dt_offset_ok, n_strata_ok, hit_rail_frac, null_rail_frac,
                       null_median_signed_coarse, ols["p_value"], null_slope_abs,
                       repl["pooled_rho_conc"], repl["ci_lo"], repl["ci_hi"])
    print("\nreplication leg (M3's dt_offset=+0.45 column, n_hit=%d n_null=%d, n_missing_call=%d):"
          % (repl["n_hit"], repl["n_null"], repl["n_missing_dt45_call"]))
    print("  rho_conc=%.4f  CI=[%.4f, %.4f]  row-if-gated-alone=%s  %s"
          % (repl["pooled_rho_conc"], repl["ci_lo"], repl["ci_hi"], repl_row,
             "AGREES with primary" if repl_row == row else "*** DISAGREES with primary -- ESCALATE, do not choose ***"))

    report = {
        "spec": data["spec"], "dll_sha256": data["dll_sha256"], "shim_version": data["shim_version"],
        "hk025_classification": hk025,
        "n_hit": len(hit), "n_miss": len(miss), "n_null": len(null), "n_control": len(control),
        "n_rc_nonzero": n_rc_nonzero, "control_dt_offset_ok": control_dt_offset_ok,
        "control_median_abs_coarse_dt_samp": control_median_coarse,
        "n_strata_ok": n_strata_ok, "strata_power": strata_power,
        "hit_rail_frac": hit_rail_frac, "null_rail_frac": null_rail_frac,
        "hit_rail_n": hit_rail_n, "null_rail_n": null_rail_n,
        "null_median_signed_coarse_dt_samp": null_median_signed_coarse,
        "null_ols_slope_vs_base_dt_s": ols,
        "primary_rho_conc": primary,
        "row": row,
        "secondary": {
            "readable": secondary_readable,
            "S1_hit_vs_miss_score": s1,
            "S2_hit_vs_miss_position": s2,
        },
        "replication_leg": {**repl, "row_if_gated_alone": repl_row, "agrees_with_primary": repl_row == row},
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(REPORT_PATH, report)
    print("\nreport written: %s" % REPORT_PATH)


if __name__ == "__main__":
    main()
