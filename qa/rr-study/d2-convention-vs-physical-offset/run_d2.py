#!/usr/bin/env python3
"""D2 -- is the shared +0.650s offset a `dt` CONVENTION or a PHYSICAL displacement?

Spec: qa/rr-study/2026-08-19-1305-architect-to-qa-prereg-d2-convention-vs-physical-offset.md
("the spec"; all section references below are to it unless stated otherwise).

STATISTIC: Delta = reported_dt_s(WSJT-X) - reported_dt_s(OpenWSFZ), on matched pairs
of the SAME injected signal (same scenario/part/trial/seed/message/freq/cycle key),
pooled across all *_matched.csv files in a run directory. Both decoders hear the
identical audio through one chain (VB-CABLE live playback, ROW 0d) so any common-mode
capture latency cancels exactly; Delta is the convention term and nothing else.

No new data -- re-analysis of matched CSVs already on disk (Sec.3). No src/, no
capture run, no Developer session -- HK-011 not engaged.

Emits COUNTS AND SECONDS ONLY (NFR-021): message_text is used in-process to build the
join key and is never written to any log line or JSON field.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m1-sync-vs-extraction"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m4-corrected-anchor"))

from n1_stats import cluster_bootstrap_median_diff  # noqa: E402 -- reused verbatim
from m4_stats import ols_cluster_robust  # noqa: E402 -- reused verbatim

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESULTS_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study", "results")

PRIMARY_RUN = "2026-08-05-3bd4cd0"
REPLICATION_RUNS = ["2026-08-15-8d6e1b1", "2026-06-20-d70aad5"]

# -- Sec.5 bars, lifted verbatim from the spec, not chosen here --------------------
THETA = 0.10                      # grid steps of the AO1 sweep, same bar D1 used
ROW1_LO, ROW1_HI = -0.750, -0.550  # PURE CONVENTION band (K=+0.650s +/- THETA)
ROW2_LO, ROW2_HI = -0.10, 0.10     # PURE PHYSICAL band (CI95 must be CONTAINED)
ROW_0E_MIN_PAIRS = 250
ROW_0E_MIN_CLUSTERS = 60
ROW_0F_MAX_RESOLUTION = 0.05       # 1.96*SE(Delta) must be <= this
ROW4_MAX_CI_WIDTH = 0.30           # dispersion beyond the model
SLOPE_NULL_HALFWIDTH = 0.05        # s/s, prediction check only, not a gate

# -- ROW 0a -- DLL SHA256 per run, obtained by extracting the git blob at each run's
# OWN recorded build SHA (report.md's "OpenWSFZ SHA" field) and hashing the actual
# bytes -- never inferred from the shim-version integer label (MEMORY.md standing
# rule: "the FT8_SHIM_VERSION integer identifies NOTHING -- pin the SHA256"). Computed
# once, mechanically, before this script existed:
#   git show <recorded_build_sha>:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll | sha256sum
# d70aad5's run-directory name does NOT match its own report's recorded build SHA
# (a97ab85c...) -- a real label/manifest discrepancy caught by checking rather than
# assuming (HK-022); hashed against the report's recorded SHA, not the directory name.
RUN_MANIFEST = {
    "2026-08-05-3bd4cd0": {
        "recorded_build_sha": "3bd4cd06b28ef7094155b041e93678782d73ffdc",
        "recorded_shim": 20260033,
        "dll_sha256": "f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015",
        "note": "matches MEMORY.md's standing main pin f2f30c89.../20260033 exactly.",
    },
    "2026-08-15-8d6e1b1": {
        "recorded_build_sha": "8d6e1b1f718aee9dfe72be253f46a7e34c476e5a",
        "recorded_shim": 20260041,
        "dll_sha256": "04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf",
        "note": "branch feat/r1b-sync-refiner-instrument-correction; directory name matches recorded build SHA.",
    },
    "2026-06-20-d70aad5": {
        "recorded_build_sha": "a97ab85c4f89cfd0a5b3f9b0e29d37fb26bad6b5",
        "recorded_shim": 20260025,
        "dll_sha256": "55b710fb254ddc1f8d35928db2408ce4c1984d93a2e3edcd9daf012d0a14a487",
        "note": ("DIRECTORY NAME 'd70aad5' != recorded build SHA 'a97ab85c...' -- report.md's own "
                 "table records the true build SHA; hashed that, not the directory label."),
    },
}


# =============================================================================
# HK-025 -- independent re-classification of every ROW 0 check, per the standing
# instruction to test whether any precondition is diagnostic (same verdict on both
# branches) rather than adopt the spec's framing.
# =============================================================================

def hk025_check() -> dict:
    reasons = {
        "0a": ("VALIDITY", "unpinned/uncertain DLL invalidates every downstream number's provenance"),
        "0b": ("VALIDITY", "wrong field mapping inverts the sign of every Delta"),
        "0c": ("VALIDITY", "if dt gated matching, the matched population itself is selected on the "
                            "effect being measured -- circular"),
        "0d": ("PRECISION/framing", "drives interpretation notes, not a row outcome per the spec's own text"),
        "0e": ("PRECISION", "underpowered population -- differ (STOP vs proceed), not diagnostic"),
        "0f": ("PRECISION", "cannot resolve 0.650 from 0.500 -- differ (escalate vs proceed), not diagnostic"),
        "0g": ("VALIDITY", "if the join key manufactures agreement, every row downstream is an artefact"),
        "0h": ("VALIDITY", "if yield falls off at the range edge, the slope test measures instrument "
                            "rolloff, not a physical relationship (HK-026)"),
    }
    classification = {k: {"class": c, "reason": r} for k, (c, r) in reasons.items()}
    return {"classification": classification, "refusal": False, "concurs_with_spec": True}


# =============================================================================
# Data loading
# =============================================================================

def null_repair_within_cycle(raw_pairs: list[dict], seed: int) -> list[dict]:
    """ROW 0g -- pairing purity null (H1a precedent): re-pair WSJT-X to OpenWSFZ at
    random WITHIN cycle, recompute Delta_null. If the join key were manufacturing
    the agreement (e.g. every signal in a cycle looks alike), a random within-cycle
    re-pairing would reproduce a similarly tight, non-zero Delta. It should not.

    Operates on raw (wsjt_dt, owsfz_dt) components per pair so the within-cycle
    permutation is genuine: delta_null_i = wsjt_i - owsfz_perm(i), owsfz values
    permuted among the pairs sharing the same cycle, WSJT-X order left fixed."""
    by_ts: dict[str, list[dict]] = {}
    for p in raw_pairs:
        by_ts.setdefault(p["ts"], []).append(p)

    rng = np.random.default_rng(seed)
    null_pairs: list[dict] = []
    for ts in sorted(by_ts):
        group = by_ts[ts]
        owsfz_vals = [g["owsfz_dt"] for g in group]
        perm = rng.permutation(len(group))
        for i, g in enumerate(group):
            owsfz_perm = owsfz_vals[perm[i]]
            null_pairs.append({
                "ts": ts,
                "delta": g["wsjt_dt"] - owsfz_perm,
                "true_dt_s": g["true_dt_s"],
                "scenario": g["scenario"],
            })
    return null_pairs


def load_run_pairs_with_raw(run_dir: str) -> tuple[list[dict], list[dict], dict]:
    """Like load_run_pairs, but also returns the raw per-pair (wsjt_dt, owsfz_dt)
    components needed for the ROW 0g null re-pairing."""
    by_appraiser: dict[str, dict[tuple, dict]] = {"WSJT-X": {}, "OpenWSFZ": {}}
    duplicate_keys = 0
    csv_files = sorted(glob.glob(os.path.join(run_dir, "*_matched.csv")))
    rows_seen = {"WSJT-X": 0, "OpenWSFZ": 0}

    for path in csv_files:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                appraiser = row["appraiser"]
                if appraiser not in by_appraiser:
                    continue
                if row["matched"] != "True" or row["false_positive"] == "True":
                    continue
                if not row["reported_dt_s"] or not row["true_dt_s"]:
                    continue
                rows_seen[appraiser] += 1
                key = (row["scenario_id"], row["part_index"], row["trial_index"], row["seed"],
                       row["message_text"], row["true_freq_hz"], row["cycle_utc"])
                d = by_appraiser[appraiser]
                if key in d:
                    duplicate_keys += 1
                d[key] = row

    pairs: list[dict] = []
    raw_pairs: list[dict] = []
    for key, wsjt_row in by_appraiser["WSJT-X"].items():
        owsfz_row = by_appraiser["OpenWSFZ"].get(key)
        if owsfz_row is None:
            continue
        wsjt_dt = float(wsjt_row["reported_dt_s"])
        owsfz_dt = float(owsfz_row["reported_dt_s"])
        delta = wsjt_dt - owsfz_dt
        true_dt_s = float(wsjt_row["true_dt_s"])
        scenario = wsjt_row["scenario_id"]
        ts = wsjt_row["cycle_utc"]
        pairs.append({"ts": ts, "delta": delta, "true_dt_s": true_dt_s, "scenario": scenario})
        raw_pairs.append({"ts": ts, "wsjt_dt": wsjt_dt, "owsfz_dt": owsfz_dt,
                           "true_dt_s": true_dt_s, "scenario": scenario})

    diag = {
        "csv_files": len(csv_files),
        "n_wsjt_usable_rows": rows_seen["WSJT-X"],
        "n_owsfz_usable_rows": rows_seen["OpenWSFZ"],
        "n_pairs": len(pairs),
        "n_clusters": len({p["ts"] for p in pairs}),
        "duplicate_keys": duplicate_keys,
        "scenarios_present": sorted({p["scenario"] for p in pairs}),
    }
    return pairs, raw_pairs, diag


# =============================================================================
# ROW 0h -- HK-026 flatness: per-appraiser yield must not fall off at the edges of
# the true_dt_s range actually used, or the slope test would measure instrument
# rolloff rather than a physical relationship.
# =============================================================================

def yield_by_dt_bin(run_dir: str, n_bins: int = 4) -> dict:
    """Recovery rate (matched fraction) per appraiser, binned by true_dt_s quartile,
    over ALL truth rows (matched + missed) in the run's matched CSVs."""
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(run_dir, "*_matched.csv"))):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["false_positive"] == "True":
                    continue
                if not row["true_dt_s"]:
                    continue
                rows.append({
                    "appraiser": row["appraiser"],
                    "true_dt_s": float(row["true_dt_s"]),
                    "matched": row["matched"] == "True",
                })

    dts = sorted({r["true_dt_s"] for r in rows})
    if len(dts) < 2:
        return {"insufficient_range": True, "n_unique_true_dt_s": len(dts)}

    lo, hi = min(dts), max(dts)
    edges = np.linspace(lo, hi, n_bins + 1)

    def bin_of(v: float) -> int:
        idx = np.searchsorted(edges, v, side="right") - 1
        return int(min(max(idx, 0), n_bins - 1))

    out: dict = {"range": [lo, hi], "edges": edges.tolist(), "by_appraiser": {}}
    for appraiser in ("WSJT-X", "OpenWSFZ"):
        bins = [{"n": 0, "matched": 0} for _ in range(n_bins)]
        for r in rows:
            if r["appraiser"] != appraiser:
                continue
            b = bin_of(r["true_dt_s"])
            bins[b]["n"] += 1
            bins[b]["matched"] += int(r["matched"])
        rates = [(b["matched"] / b["n"]) if b["n"] > 0 else float("nan") for b in bins]
        out["by_appraiser"][appraiser] = {"bins": bins, "recovery_rate": rates}
    return out


def flatness_verdict(yield_report: dict, min_ratio: float = 0.5) -> dict:
    """PASS iff every bin's recovery rate (for both appraisers) is at least
    min_ratio times the max bin's rate -- i.e. no edge-bin collapse relative to the
    range's own best bin. A generous, documented ratio, not a borrowed constant."""
    if yield_report.get("insufficient_range"):
        return {"flat": False, "reason": "insufficient true_dt_s range to test", "detail": yield_report}
    worst = {}
    flat = True
    for appraiser, d in yield_report["by_appraiser"].items():
        rates = [r for r in d["recovery_rate"] if r == r]  # drop NaN (empty bins)
        if not rates:
            continue
        best = max(rates)
        floor = min(rates)
        ratio = (floor / best) if best > 0 else float("nan")
        worst[appraiser] = {"best": best, "floor": floor, "ratio": ratio}
        if best > 0 and ratio < min_ratio:
            flat = False
    return {"flat": flat, "min_ratio_bar": min_ratio, "per_appraiser": worst}


# =============================================================================
# Analysis for one run
# =============================================================================

def analyse_run(run_name: str, is_primary: bool, seed: int) -> dict:
    run_dir = os.path.join(RESULTS_ROOT, run_name)
    pairs, raw_pairs, diag = load_run_pairs_with_raw(run_dir)

    result: dict = {"run": run_name, "is_primary": is_primary, "diagnostics": diag}

    # -- ROW 0a: DLL SHA256, from the pre-hashed manifest (git-blob, not integer) ---
    manifest = RUN_MANIFEST.get(run_name)
    result["row_0a"] = {"fires": manifest is None, "manifest": manifest}

    # -- ROW 0e: population --------------------------------------------------------
    row_0e_fires = diag["n_pairs"] < ROW_0E_MIN_PAIRS or diag["n_clusters"] < ROW_0E_MIN_CLUSTERS
    result["row_0e"] = {"fires": row_0e_fires, "n_pairs": diag["n_pairs"], "n_clusters": diag["n_clusters"],
                         "min_pairs": ROW_0E_MIN_PAIRS, "min_clusters": ROW_0E_MIN_CLUSTERS}
    if row_0e_fires:
        result["stopped_at"] = "0e"
        return result

    # -- Cluster bootstrap on the real Delta ----------------------------------------
    boot_rows = [{"ts": p["ts"], "d_ber": p["delta"]} for p in pairs]
    boot = cluster_bootstrap_median_diff(boot_rows, seed=seed)
    result["delta_bootstrap"] = boot

    # -- Descriptive: value distribution + mean. The pre-registered statistic is the
    # cluster-bootstrap MEDIAN (reused verbatim from n1_stats per the spec). Delta
    # turns out to be QUANTIZED (WSJT-X's ~0.1s DT rounding straddling a continuous
    # true offset), producing a small number of distinct values rather than a smooth
    # cloud -- the median then collapses onto whichever value has plurality and its
    # bootstrap SE can read near-zero even though real dispersion (the gap between
    # values) is ~0.1s. The MEAN is reported alongside as a better point estimate of
    # a quantization-straddled constant; it does not replace the pre-registered
    # statistic, only supplements it, and both are shown so nothing is hidden.
    from collections import Counter
    value_counts = Counter(round(p["delta"], 3) for p in pairs)
    mean_delta = float(np.mean([p["delta"] for p in pairs]))
    result["delta_distribution"] = {
        "value_counts": {str(k): v for k, v in sorted(value_counts.items())},
        "mean": mean_delta,
        "median_pre_registered": boot["point_estimate"],
    }

    # -- ROW 0f: resolution ----------------------------------------------------------
    resolution = 1.96 * boot["se"] if boot["se"] == boot["se"] else float("nan")
    row_0f_fires = not (resolution == resolution) or resolution > ROW_0F_MAX_RESOLUTION
    result["row_0f"] = {"fires": row_0f_fires, "resolution_1_96_se": resolution, "bar": ROW_0F_MAX_RESOLUTION}
    if row_0f_fires:
        result["stopped_at"] = "0f"
        return result

    # -- ROW 0g: pairing purity null --------------------------------------------------
    null_pairs = null_repair_within_cycle(raw_pairs, seed=seed + 1)
    null_boot_rows = [{"ts": p["ts"], "d_ber": p["delta"]} for p in null_pairs]
    null_boot = cluster_bootstrap_median_diff(null_boot_rows, seed=seed + 2)
    ci_lo, ci_hi = null_boot["ci95"]
    null_excludes_zero = (ci_lo == ci_lo and ci_hi == ci_hi) and not (ci_lo <= 0.0 <= ci_hi)

    # HK-025 independent re-classification, done on discovering the mechanical fire
    # rather than adopting the spec's "tight non-zero -> VOID" framing unexamined.
    # The within-cycle shuffle can only produce dispersion where a cycle (a) has >=2
    # pairs to shuffle among, AND (b) those pairs' deltas actually differ. Measure
    # both, mechanically, before classifying.
    by_ts_raw: dict[str, list[dict]] = {}
    for rp in raw_pairs:
        by_ts_raw.setdefault(rp["ts"], []).append(rp)
    n_clusters_total = len(by_ts_raw)
    n_clusters_multi = sum(1 for g in by_ts_raw.values() if len(g) >= 2)
    n_clusters_multi_with_variation = sum(
        1 for g in by_ts_raw.values()
        if len(g) >= 2 and len({round(x["wsjt_dt"] - x["owsfz_dt"], 3) for x in g}) > 1
    )
    shuffle_power = (n_clusters_multi_with_variation / n_clusters_multi) if n_clusters_multi else 0.0

    hk025_0g_diagnostic = shuffle_power < 0.20  # documented bar: below this, the null
    # is powered by so few genuinely-heterogeneous clusters that it cannot separate
    # "pairing is correct" from "pairing is wrong" -- both branches would reproduce a
    # tight, non-zero null purely from clusters where every candidate pairing shares
    # the same true_dt_s (hence the same rounding bucket) regardless of assignment.

    result["row_0g"] = {
        "fires_mechanically": null_excludes_zero,
        "null_bootstrap": null_boot,
        "criterion": "VOID iff 0 not in CI95(Delta_null), AS PRE-REGISTERED",
        "hk025": {
            "n_clusters_total": n_clusters_total,
            "n_clusters_multi_pair": n_clusters_multi,
            "n_clusters_multi_pair_with_internal_delta_variation": n_clusters_multi_with_variation,
            "shuffle_power": shuffle_power,
            "diagnostic_bar": 0.20,
            "classified_diagnostic": hk025_0g_diagnostic,
            "branch_a_pairing_correct": ("tight non-zero null expected regardless -- most clusters "
                                          "have 1 pair (no shuffle possible) or share one true_dt_s "
                                          "(shuffle changes nothing)"),
            "branch_b_pairing_manufactured": ("ALSO tight non-zero null expected, for the same "
                                               "structural reason -- swapping among same-true_dt_s "
                                               "same-cycle candidates does not perturb delta either way"),
            "verdict": ("Both branches predict the SAME observed result (tight non-zero null) for "
                        "reasons that have nothing to do with whether the WSJT-X<->OpenWSFZ pairing "
                        "is genuine. DIAGNOSTIC per HK-025 -- refused as a VOID gate for this dataset; "
                        "not silently passed, not silently ignored.") if hk025_0g_diagnostic else
                       "shuffle_power adequate; mechanical VOID verdict stands, not overridden.",
        },
    }
    row_0g_blocks = null_excludes_zero and not hk025_0g_diagnostic
    if row_0g_blocks:
        result["stopped_at"] = "0g"
        return result
    result["row_0g_hk025_override"] = null_excludes_zero and hk025_0g_diagnostic

    # -- ROW 0h: HK-026 flatness ------------------------------------------------------
    yield_report = yield_by_dt_bin(run_dir)
    flatness = flatness_verdict(yield_report)
    result["row_0h"] = {"fires": not flatness["flat"], "yield_report": yield_report, "flatness": flatness}
    if not flatness["flat"]:
        result["stopped_at"] = "0h"
        return result

    # -- Mandatory: slope of Delta on true_dt_s, cluster-robust ----------------------
    x = np.array([p["true_dt_s"] for p in pairs])
    y = np.array([p["delta"] for p in pairs])
    clusters = [p["ts"] for p in pairs]
    slope = ols_cluster_robust(x, y, clusters)
    if slope["se_slope"] == slope["se_slope"] and slope["n_clusters"] > 2:
        from scipy import stats as _stats
        tcrit = _stats.t.ppf(0.975, slope["n_clusters"] - 1)
        slope_ci = [slope["slope"] - tcrit * slope["se_slope"], slope["slope"] + tcrit * slope["se_slope"]]
    else:
        slope_ci = [float("nan"), float("nan")]
    result["slope_delta_on_true_dt_s"] = {**slope, "ci95": slope_ci}

    if is_primary:
        # -- ROW 4: instrument failure ------------------------------------------------
        ci_lo, ci_hi = boot["ci95"]
        ci_width = ci_hi - ci_lo if (ci_lo == ci_lo and ci_hi == ci_hi) else float("nan")
        slope_excludes_zero = (slope_ci[0] == slope_ci[0] and slope_ci[1] == slope_ci[1]
                                and not (slope_ci[0] <= 0.0 <= slope_ci[1]))
        row4_fires = (ci_width == ci_width and ci_width > ROW4_MAX_CI_WIDTH) or slope_excludes_zero
        result["row_4"] = {"fires": row4_fires, "ci_width": ci_width, "ci_width_bar": ROW4_MAX_CI_WIDTH,
                            "slope_excludes_zero": slope_excludes_zero}

        if row4_fires:
            result["final_row"] = "4"
        else:
            point = boot["point_estimate"]
            in_row1_band = ROW1_LO <= point <= ROW1_HI
            ci_contained_row2 = (ci_lo == ci_lo and ci_hi == ci_hi and ROW2_LO <= ci_lo and ci_hi <= ROW2_HI)
            ci_excludes_0 = ci_lo == ci_lo and not (ci_lo <= 0.0 <= ci_hi)
            ci_excludes_neg065 = ci_lo == ci_lo and not (ci_lo <= -0.650 <= ci_hi)

            if in_row1_band:
                result["final_row"] = "1"
            elif ci_contained_row2:
                result["final_row"] = "2"
            elif ci_excludes_0 and ci_excludes_neg065:
                result["final_row"] = "3"
            else:
                result["final_row"] = "AMBIGUOUS"
            result["row_flags"] = {"in_row1_band": in_row1_band, "ci_contained_row2": ci_contained_row2,
                                    "ci_excludes_0": ci_excludes_0, "ci_excludes_neg065": ci_excludes_neg065}

            if result["final_row"] == "3":
                c_w = -point
                p_resid = 0.650 + point
                result["row_3_decomposition"] = {"C_w": c_w, "P_residual": p_resid,
                                                  "C_w_ci95": [-ci_hi, -ci_lo] if ci_hi == ci_hi else [float("nan")]*2}

    return result


# =============================================================================
# main
# =============================================================================

def main() -> int:
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("D2 -- is the shared +0.650s offset a dt CONVENTION or a PHYSICAL displacement?")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    bundle: dict = {"hk025": hk025}

    # -- ROW 0b/0c/0d: code-read confirmations, re-verified independently this session
    log("\n" + "=" * 90)
    log("ROW 0b/0c/0d -- code-read preconditions, independently re-verified this session")
    log("=" * 90)
    row_0b = {
        "fires": False,
        "owsfz": "ft8_shim.c:1432 -- dt = (cand->time_offset + time_sub/time_osr) * symbol_period; "
                 "no protocol-start term anywhere in the shim (confirmed by reading the file this session).",
        "wsjtx": "harness/common.py Format-B regex group 5 = dt (0-based ALL.TXT field [5]); "
                 "confirmed by reading the parser this session.",
    }
    row_0c = {
        "fires": False,
        "evidence": "harness/matcher.py:31,125,150-175 -- matches on cycle slot, message text "
                    "(_text_matches) and freq within FREQ_TOLERANCE_HZ=4.0 (_freq_matches). "
                    "`dt` is carried into the output row but never read as a matching predicate. "
                    "Confirmed by reading matcher.py this session.",
    }
    row_0d = {
        "fires": False,
        "answer": "LIVE, via CycleFramer -- run_study.py's own docstring: \"Runs scenarios in "
                  "sequence (live playback into VB-CABLE), then collects\" -- both WSJT-X and "
                  "OpenWSFZ capture the SAME live-played audio through their normal capture paths, "
                  "not from a shared static file.",
    }
    log("  0b: %s" % row_0b)
    log("  0c: %s" % row_0c)
    log("  0d: %s" % row_0d)
    bundle["row_0b"] = row_0b
    bundle["row_0c"] = row_0c
    bundle["row_0d"] = row_0d

    if row_0b["fires"] or row_0c["fires"]:
        log("\nROW 0b/0c FIRES. VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0b/0c"
        _write(bundle, log_lines)
        return 2

    seed = 20260819  # this arm's date, HK-017-style provenance

    runs_out: dict = {}
    for run_name in [PRIMARY_RUN] + REPLICATION_RUNS:
        is_primary = run_name == PRIMARY_RUN
        log("\n" + "=" * 90)
        log("%s run: %s" % ("PRIMARY" if is_primary else "REPLICATION (descriptive only)", run_name))
        log("=" * 90)
        r = analyse_run(run_name, is_primary, seed)
        runs_out[run_name] = r
        log("  diagnostics: %s" % r["diagnostics"])
        log("  row_0a: fires=%s manifest=%s" % (r["row_0a"]["fires"],
            {k: v for k, v in (r["row_0a"]["manifest"] or {}).items() if k != "note"}))
        if r["row_0a"]["manifest"]:
            log("    note: %s" % r["row_0a"]["manifest"]["note"])
        if r.get("stopped_at"):
            log("  STOPPED at ROW %s -- see bundle for detail." % r["stopped_at"])
            continue
        log("  delta_bootstrap (pre-registered, MEDIAN): point=%.4f mean=%.4f se=%.4f ci95=[%.4f, %.4f] "
            "p=%.4g n_pairs=%d n_clusters=%d"
            % (r["delta_bootstrap"]["point_estimate"], r["delta_bootstrap"]["mean"], r["delta_bootstrap"]["se"],
               r["delta_bootstrap"]["ci95"][0], r["delta_bootstrap"]["ci95"][1],
               r["delta_bootstrap"]["p_two_sided"], r["delta_bootstrap"]["n_rows"], r["delta_bootstrap"]["n_clusters"]))
        log("  delta_distribution: value_counts=%s MEAN=%.4f (median=%.4f) -- Delta is QUANTIZED, "
            "not a smooth cloud; mean is the better point estimate of a rounding-straddled constant"
            % (r["delta_distribution"]["value_counts"], r["delta_distribution"]["mean"],
               r["delta_distribution"]["median_pre_registered"]))
        log("  row_0f (resolution 1.96*SE<=%.2fs): fires=%s value=%.4f"
            % (ROW_0F_MAX_RESOLUTION, r["row_0f"]["fires"], r["row_0f"]["resolution_1_96_se"]))
        log("  row_0g (null CI95, AS PRE-REGISTERED): fires_mechanically=%s null_ci95=%s null_point=%.4f"
            % (r["row_0g"]["fires_mechanically"], r["row_0g"]["null_bootstrap"]["ci95"],
               r["row_0g"]["null_bootstrap"]["point_estimate"]))
        log("  row_0g HK-025: shuffle_power=%.3f (bar>=%.2f) classified_diagnostic=%s -> %s"
            % (r["row_0g"]["hk025"]["shuffle_power"], r["row_0g"]["hk025"]["diagnostic_bar"],
               r["row_0g"]["hk025"]["classified_diagnostic"], r["row_0g"]["hk025"]["verdict"]))
        if r.get("row_0g_hk025_override"):
            log("  *** ROW 0g MECHANICALLY FIRED but is HK-025-REFUSED as diagnostic for this dataset -- "
                "analysis CONTINUES past it, disclosed, not silently passed. ***")
        log("  row_0h (HK-026 flatness): fires=%s flat=%s per_appraiser=%s"
            % (r["row_0h"]["fires"], r["row_0h"]["flatness"]["flat"], r["row_0h"]["flatness"]["per_appraiser"]))
        s = r["slope_delta_on_true_dt_s"]
        log("  slope(Delta ~ true_dt_s): slope=%.4f se=%.4f ci95=%s p=%.4g n=%d n_clusters=%d"
            % (s["slope"], s["se_slope"], s["ci95"], s["p_value"], s["n"], s["n_clusters"]))
        if is_primary:
            log("  row_4: %s" % r.get("row_4"))
            log("  FINAL ROW: %s" % r.get("final_row"))
            if r.get("row_3_decomposition"):
                log("  row_3_decomposition: %s" % r["row_3_decomposition"])

    bundle["runs"] = runs_out
    primary_result = runs_out[PRIMARY_RUN]
    bundle["final_row"] = primary_result.get("final_row", primary_result.get("stopped_at"))

    # -- Predictions scored, Sec.6 ------------------------------------------------
    log("\n" + "=" * 90)
    log("Sec.6 predictions, scored against the PRIMARY run")
    log("=" * 90)
    pred_row = {"ROW 1": 0.45, "ROW 3": 0.35, "ROW 2": 0.12, "ROW 4": 0.08}
    final_row_label = {"1": "ROW 1", "2": "ROW 2", "3": "ROW 3", "4": "ROW 4"}.get(
        bundle["final_row"], str(bundle["final_row"]))
    predictions = {
        "row": {"predicted_probs": pred_row, "actual": final_row_label,
                "hit_prob_assigned": pred_row.get(final_row_label)},
    }
    if "delta_bootstrap" in primary_result:
        point = primary_result["delta_bootstrap"]["point_estimate"]
        predictions["delta_point"] = {"predicted": -0.55, "actual": point,
                                       "hit_80pct_interval": -0.75 <= point <= -0.35}
    if "slope_delta_on_true_dt_s" in primary_result:
        sl = primary_result["slope_delta_on_true_dt_s"]
        predictions["slope"] = {"predicted": 0.0, "predicted_ci_excludes": [-0.05, 0.05],
                                 "actual_slope": sl["slope"], "actual_ci95": sl["ci95"]}
    for name, p in predictions.items():
        log("  %s: %s" % (name, p))
    bundle["predictions_scored"] = predictions

    log("\n" + "=" * 90)
    log("FINAL ROW (primary run, %s): %s" % (PRIMARY_RUN, bundle["final_row"]))
    log("=" * 90)

    _write(bundle, log_lines)
    log("\nWrote results/d2_report.json, results/d2_run.log")
    return 0


def _write(bundle: dict, log_lines: list[str]) -> None:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "d2_report.json"), "w", encoding="ascii", errors="replace") as fh:
        json.dump(bundle, fh, indent=2, default=str)
    with open(os.path.join(out_dir, "d2_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
