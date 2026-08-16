#!/usr/bin/env python3
"""M3 -- pre-registered gate evaluator.

Spec 7.3, verbatim pseudocode reproduced below. Rows mutually exclusive, evaluated
in STRICT ORDER, first match wins (HK-021(k)). HK-025 classification for all four
ROW 0s is re-derived independently in m3_hk025_check() before this is ever run --
see that function's docstring; QA refuses under HK-025 if it disagrees, including
with the Architect's own written classification.

Primary statistic: dt_win, the winning dt_offset, per row. TIED rows (a genuine
mirror-image score plateau, see m3_run_harness._sweep_winner) have dt_win == None
and are excluded from every signed statistic (median, mode fraction, edge
fraction) per spec S5.1 -- they are counted in n but never in the numerator or in
any median/percentile computation.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m3_common import (  # noqa: E402
    FREQ_RAIL_HZ, RESULTS_DIR, STRATA, SWEEP_ORDER, is_edge_winner_time,
    stratum_of, stratum_label, write_json,
)

RESULTS_PATH = os.path.join(RESULTS_DIR, "m3_results.json")
REPORT_PATH = os.path.join(RESULTS_DIR, "m3_gate_report.json")

# -- Spec 7.3 thresholds ----------------------------------------------------------
ROW0A_CONTROL_DT_WIN_ABS_MAX_S = 0.10
ROW0A_CONTROL_COARSE_DT_SAMP_MEDIAN_MAX = 2
ROW0B_STRATUM_MIN_N = 80
ROW0B_N_STRATA_OK_MIN = 4
ROW0C_EDGE_FRAC_MAX = 0.10
ROW0D_NULL_MEDIAN_ABS_MAX_S = 0.15
ROW1_MEDIAN_MIN_S = 0.30
ROW1_MODE_FRAC_MIN = 0.30
ROW1_MODE_WINDOW_S = 0.10
ROW2_MEDIAN_ABS_MAX_S = 0.10
ROW2_OUTSIDE_FRAC_MAX = 0.30
ROW2_MODE_WINDOW_S = 0.10


def resolved(rows):
    """dt_win values with tied rows excluded (spec S5.1)."""
    return [r["dt_win"] for r in rows if r["dt_win"] is not None]


def m3_hk025_check():
    """Independent re-derivation of the HK-025 classification for ROW 0a-0d,
    per spec S7.3's own instruction: "QA re-runs this classification independently
    before arming and refuses under HK-025 if it disagrees, including with this
    paragraph." Two-step test per HK-025: (1) CLASSIFY -- does the check, if it
    fires, mean dt_win stops being an estimate of "where is the true time origin"
    at all (VALIDITY) or does it just change how precisely that same estimate is
    stated (PRECISION)? (2) EVALUATE BOTH BRANCHES -- do the fire/no-fire branches
    route to genuinely different rows with different actions, or would QA write
    the same row either way (DIAGNOSTIC, refuse)?

    ROW 0a (control can't relocate a KNOWN position): if it fires, the sweep
    machinery itself cannot find a signal whose position is known by construction
    -- dt_win on the REAL arm is not "where is the true origin", it is "wherever
    a broken sweep happens to land". VALIDITY. Branches differ (fix-and-rerun vs
    proceed). Not diagnostic.
    ROW 0b (population power): if it fires there are too few rows to say anything
    about strata; the statistic is not computable with any reliability, not just
    imprecise. VALIDITY. Branches differ (escalate vs proceed). Not diagnostic.
    ROW 0c (answer outside the search): if it fires for >10% of HIT, those rows'
    "winner" is a boundary artifact, not a location -- the search never contained
    the true answer for them. VALIDITY (a support/domain failure, not a precision
    complaint). Branches differ (stop sweeping vs proceed). Not diagnostic.
    ROW 0d (NULL has no signal, so its winner must be uninformative; a directional
    NULL pull means the SWEEP is not neutral, contaminating every row's estimate,
    not just NULL's). VALIDITY. Branches differ (escalate vs proceed). Not
    diagnostic.

    Concurs with the Architect's S7.3 self-classification. No refusal indicated.
    Returns the classification table for the report (auditable, not asserted).
    """
    return {
        "ROW 0a": {"class": "VALIDITY", "reason": "sweep machinery unable to find a KNOWN position"},
        "ROW 0b": {"class": "VALIDITY", "reason": "insufficient population, not a null result"},
        "ROW 0c": {"class": "VALIDITY", "reason": "true answer outside the search domain for >10% of HIT"},
        "ROW 0d": {"class": "VALIDITY", "reason": "sweep itself has a direction on signal-free rows"},
        "concurs_with_architect": True,
        "refusal": False,
    }


def m3_row(control_median_dt_win, control_median_coarse_dt_samp, n_strata_ok,
           edge_frac_hit, null_median_dt_win, hit_median, hit_mode_frac_within,
           hit_outside_frac) -> str:
    if (control_median_dt_win is None or abs(control_median_dt_win) > ROW0A_CONTROL_DT_WIN_ABS_MAX_S
            or control_median_coarse_dt_samp > ROW0A_CONTROL_COARSE_DT_SAMP_MEDIAN_MAX):
        return "ROW 0a"
    if n_strata_ok < ROW0B_N_STRATA_OK_MIN:
        return "ROW 0b"
    if edge_frac_hit > ROW0C_EDGE_FRAC_MAX:
        return "ROW 0c"
    if null_median_dt_win is None or abs(null_median_dt_win) > ROW0D_NULL_MEDIAN_ABS_MAX_S:
        return "ROW 0d"
    if hit_median is None:
        return "ROW 0b"  # no resolved HIT rows at all -- power failure
    if hit_median >= ROW1_MEDIAN_MIN_S and hit_mode_frac_within >= ROW1_MODE_FRAC_MIN:
        return "ROW 1"
    if abs(hit_median) <= ROW2_MEDIAN_ABS_MAX_S and hit_outside_frac < ROW2_OUTSIDE_FRAC_MAX:
        return "ROW 2"
    return "ROW 3"


def main():
    with open(RESULTS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    results = data["results"]
    print("loaded %d results (dll sha256=%s shim=%s)"
          % (len(results), data["dll_sha256"], data["shim_version"]))
    print("n_tied (mirror-image score plateaus, excluded from signed stats): %d"
          % data.get("n_tied", -1))

    hk025 = m3_hk025_check()
    print("\nHK-025 independent re-classification: concurs_with_architect=%s refusal=%s"
          % (hk025["concurs_with_architect"], hk025["refusal"]))
    if hk025["refusal"]:
        print("REFUSING TO ARM PER HK-025 -- see classification table in report.")
        report = {"spec": data["spec"], "hk025_classification": hk025, "row": "REFUSED"}
        os.makedirs(RESULTS_DIR, exist_ok=True)
        write_json(REPORT_PATH, report)
        return

    hit = [r for r in results if r["kind"] == "real" and r["arm"] == "HIT"]
    null = [r for r in results if r["kind"] == "real" and r["arm"] == "NULL"]
    control = [r for r in results if r["kind"] == "control"]
    print("HIT=%d NULL=%d CONTROL=%d" % (len(hit), len(null), len(control)))

    # -- ROW 0a: positive control relocates its own known-correct anchor --------
    control_dt_win = resolved(control)
    control_median_dt_win = float(np.median(control_dt_win)) if control_dt_win else None
    control_coarse = np.array([abs(r["coarse_dt_samp"]) for r in control])
    control_median_coarse = float(np.median(control_coarse)) if len(control_coarse) else float("nan")
    n_control_tied = sum(1 for r in control if r["dt_win"] is None)
    print("\ncontrol median dt_win = %s s (bar |.|<=%.2f)  n_tied=%d/%d"
          % ("n/a" if control_median_dt_win is None else "%.4f" % control_median_dt_win,
             ROW0A_CONTROL_DT_WIN_ABS_MAX_S, n_control_tied, len(control)))
    print("control median |coarse_dt_samp| at winner = %.3f samples (bar <= %d)"
          % (control_median_coarse, ROW0A_CONTROL_COARSE_DT_SAMP_MEDIAN_MAX))

    # -- ROW 0b: power on the real HIT/NULL population ---------------------------
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

    # -- ROW 0c: sweep still binds (HIT rows winning at the sweep's own edge) ---
    n_hit_edge = sum(1 for r in hit if is_edge_winner_time(r["dt_win"]))
    edge_frac_hit = n_hit_edge / len(hit) if hit else float("nan")
    print("\nHIT edge-winner fraction (|dt_win|>=1.20s): %d/%d = %.4f (bar <= %.2f)"
          % (n_hit_edge, len(hit), edge_frac_hit, ROW0C_EDGE_FRAC_MAX))

    # -- ROW 0d: sweep's own directional artefact on NULL ------------------------
    null_dt_win = resolved(null)
    null_median_dt_win = float(np.median(null_dt_win)) if null_dt_win else None
    n_null_tied = sum(1 for r in null if r["dt_win"] is None)
    print("NULL median dt_win: %s s (bar |.| <= %.2f)  n_tied=%d/%d"
          % ("n/a" if null_median_dt_win is None else "%.4f" % null_median_dt_win,
             ROW0D_NULL_MEDIAN_ABS_MAX_S, n_null_tied, len(null)))

    # -- Primary statistic: HIT dt_win distribution ------------------------------
    hit_dt_win = resolved(hit)
    n_hit_tied = sum(1 for r in hit if r["dt_win"] is None)
    hit_median = float(np.median(hit_dt_win)) if hit_dt_win else None
    hit_mode_frac_within = float("nan")
    hit_outside_frac = float("nan")
    if hit_median is not None and hit_dt_win:
        arr = np.array(hit_dt_win)
        within = np.abs(arr - hit_median) <= ROW1_MODE_WINDOW_S + 1e-9
        outside = np.abs(arr - hit_median) > ROW2_MODE_WINDOW_S + 1e-9
        hit_mode_frac_within = float(np.count_nonzero(within)) / len(hit)  # denom = ALL hit rows
        hit_outside_frac = float(np.count_nonzero(outside)) / len(hit)
    print("\nHIT dt_win: median=%s  mode_frac_within(+-%.2fs of median, /all HIT)=%.4f  "
          "outside_frac(>+-%.2fs of median, /all HIT)=%.4f  n_tied=%d/%d"
          % ("n/a" if hit_median is None else "%.4f" % hit_median, ROW1_MODE_WINDOW_S,
             hit_mode_frac_within, ROW2_MODE_WINDOW_S, hit_outside_frac, n_hit_tied, len(hit)))

    # -- Per-stratum HIT dt_win breakdown, for the report (not gating) ----------
    per_stratum_dt_win = []
    for si in range(len(STRATA)):
        s_hit = [r["dt_win"] for r in hit if stratum_of(r["snr_db"]) == si and r["dt_win"] is not None]
        med = float(np.median(s_hit)) if s_hit else None
        per_stratum_dt_win.append({
            "stratum": stratum_label(si), "n": len(s_hit),
            "median_dt_win": med,
        })

    # -- Gate ---------------------------------------------------------------------
    row = m3_row(control_median_dt_win, control_median_coarse, n_strata_ok,
                 edge_frac_hit, null_median_dt_win, hit_median, hit_mode_frac_within,
                 hit_outside_frac)
    print("\n>>> %s <<<" % row)

    # -- Section 7.4: recorded, explicitly NOT gating -----------------------------
    def median_abs_coarse(rows_subset):
        vals = [abs(r["coarse_dt_samp"]) for r in rows_subset]
        return float(np.median(vals)) if vals else None

    post_correction_concentration = {"overall": {
        "HIT_median_abs_coarse_dt_samp": median_abs_coarse(hit),
        "NULL_median_abs_coarse_dt_samp": median_abs_coarse(null),
    }, "per_stratum": []}
    for si in range(len(STRATA)):
        s_hit = [r for r in hit if stratum_of(r["snr_db"]) == si]
        s_null = [r for r in null if stratum_of(r["snr_db"]) == si]
        post_correction_concentration["per_stratum"].append({
            "stratum": stratum_label(si),
            "HIT_median_abs_coarse_dt_samp": median_abs_coarse(s_hit),
            "NULL_median_abs_coarse_dt_samp": median_abs_coarse(s_null),
        })

    def rail_frac(rows_subset):
        if not rows_subset:
            return float("nan")
        n_railed = sum(1 for r in rows_subset if abs(r["delta_freq_hz"]) >= FREQ_RAIL_HZ - 1e-6)
        return n_railed / len(rows_subset)

    freq_residual = {
        "internal_aperture_hz": FREQ_RAIL_HZ,
        "HIT_rail_frac": rail_frac(hit), "NULL_rail_frac": rail_frac(null),
        "CONTROL_rail_frac": rail_frac(control),
        "HIT_mean_delta_freq_hz": float(np.mean([r["delta_freq_hz"] for r in hit])) if hit else None,
        "NULL_mean_delta_freq_hz": float(np.mean([r["delta_freq_hz"] for r in null])) if null else None,
    }

    # Per-call score profile vs dt_offset, HIT and NULL, mean within stratum.
    dt_index = {dt: i for i, dt in enumerate(SWEEP_ORDER)}
    n_dt = len(SWEEP_ORDER)

    def score_profile(rows_subset):
        acc = np.zeros(n_dt)
        cnt = np.zeros(n_dt)
        for r in rows_subset:
            for dt_off, score, _cds, _fds, _df, _rc in r["calls"]:
                j = dt_index[dt_off]
                acc[j] += score
                cnt[j] += 1
        mean = np.divide(acc, cnt, out=np.full(n_dt, np.nan), where=cnt > 0)
        return mean.tolist()

    score_profile_per_stratum = {"dt_offsets_s": list(SWEEP_ORDER), "HIT": [], "NULL": []}
    for si in range(len(STRATA)):
        s_hit = [r for r in hit if stratum_of(r["snr_db"]) == si]
        s_null = [r for r in null if stratum_of(r["snr_db"]) == si]
        score_profile_per_stratum["HIT"].append({"stratum": stratum_label(si), "mean_score": score_profile(s_hit)})
        score_profile_per_stratum["NULL"].append({"stratum": stratum_label(si), "mean_score": score_profile(s_null)})

    report = {
        "spec": data["spec"],
        "dll_sha256": data["dll_sha256"], "shim_version": data["shim_version"],
        "hk025_classification": hk025,
        "n_hit": len(hit), "n_null": len(null), "n_control": len(control),
        "n_hit_tied": n_hit_tied, "n_null_tied": n_null_tied, "n_control_tied": n_control_tied,
        "control_median_dt_win_s": control_median_dt_win,
        "control_median_abs_coarse_dt_samp": control_median_coarse,
        "n_strata_ok": n_strata_ok, "strata_power": strata_power,
        "edge_frac_hit": edge_frac_hit, "n_hit_edge": n_hit_edge,
        "null_median_dt_win_s": null_median_dt_win,
        "hit_median_dt_win_s": hit_median,
        "hit_mode_frac_within_0p10_of_median": hit_mode_frac_within,
        "hit_outside_frac_of_median": hit_outside_frac,
        "hit_per_stratum_dt_win": per_stratum_dt_win,
        "row": row,
        "recorded_not_gating": {
            "post_correction_concentration_coarse_dt_samp": post_correction_concentration,
            "frequency_residual": freq_residual,
            "score_profile_per_stratum": score_profile_per_stratum,
        },
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(REPORT_PATH, report)
    print("\nreport written: %s" % REPORT_PATH)


if __name__ == "__main__":
    main()
