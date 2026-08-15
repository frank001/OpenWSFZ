#!/usr/bin/env python3
"""M1 -- pre-registered gate evaluator.

Spec S6. Mechanical, both branches evaluated (HK-021(k)), rows mutually
exclusive in strict order (verbatim pseudocode reproduced below).

Metric: within each WSJT-X-SNR stratum, the rank-biserial correlation rho_rb
between arm (HIT=high, MISS=low) and refiner `score`. Pooled across strata by
inverse-variance weighting, where each stratum's SE is itself estimated by a
cluster bootstrap over cycle_id (rows in one cycle share noise/propagation,
HK-021(i)) -- so the bootstrap is what PRODUCES the per-stratum variance that
inverse-variance pooling consumes; this is one coherent procedure, not two
competing ones. The overall CI is the pooled normal-approximation interval
built from that same pooled SE.

rho_null_vs_hit (ROW 0c instrument check) uses the identical stratify +
inverse-variance-pool machinery, just contrasting HIT against NULL instead of
HIT against MISS; NULL rows' SNR stratum is the one inherited from the
hit/miss pool row their DT was drawn from at population-build time (see
m1_build_population.py's docstring for why that is the correct label).

Rank-biserial correlation, Wendt 1972 convention: rho_rb = 2*U/(n1*n2) - 1,
where U is the Mann-Whitney U statistic with the FIRST sample (HIT) as the
reference. rho_rb = +1 iff every HIT score exceeds every MISS/NULL score.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from m1_common import write_json  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "m1_results.json")
REPORT_PATH = os.path.join(RESULTS_DIR, "m1_gate_report.json")

# Spec S6 strata (WSJT-X [4] SNR, dB).
STRATA = [(-24, -21), (-21, -18), (-18, -15), (-15, -12), (-12, -9), (-9, -6), (-6, float("inf"))]
STRATUM_MIN_N = 200          # spec S6 ROW 0a: ">= 200 rows in BOTH arms"
N_STRATA_OK_MIN = 4          # spec S6 ROW 0a

SAT_FRAC_MAX = 0.20          # spec S6 ROW 0b
RHO_NULL_MIN = 0.30          # spec S6 ROW 0c

ROW1_RHO_MIN = 0.30
ROW1_CI_LO_MIN = 0.10
ROW2_RHO_ABS_MAX = 0.10
ROW2_CI_HI_MAX = 0.30

N_BOOTSTRAP = 500
BOOTSTRAP_SEED = 20260815  # M1's own seed, matches population build (SEED in m1_common)


def stratum_of(snr_db: float) -> int:
    for i, (lo, hi) in enumerate(STRATA):
        if lo <= snr_db < hi:
            return i
    raise AssertionError("snr_db %r outside all strata" % snr_db)  # STRATA covers (-inf? no) -24..inf


def stratum_label(i: int) -> str:
    lo, hi = STRATA[i]
    return "[%g,%s)" % (lo, "inf" if hi == float("inf") else "%g" % hi)


def rank_biserial(a_scores: np.ndarray, b_scores: np.ndarray) -> float:
    """rho_rb for a (HIT, "high") vs b (MISS/NULL, "low"). NaN if either side empty."""
    if len(a_scores) == 0 or len(b_scores) == 0:
        return float("nan")
    if len(a_scores) == 1 and len(b_scores) == 1:
        # mannwhitneyu needs n>=1 each side but a single-vs-single comparison is fine.
        pass
    U, _ = stats.mannwhitneyu(a_scores, b_scores, alternative="two-sided", method="asymptotic")
    return 2.0 * U / (len(a_scores) * len(b_scores)) - 1.0


def cluster_bootstrap_se_per_stratum(cycle_ids_a, scores_a, cycle_ids_b, scores_b,
                                      n_draws=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    """HK-021(i): resample CYCLES with replacement (not rows), recompute rho_rb per draw.
    Returns (se, bootstrap_values). NaN se if fewer than 2 distinct cycles appear across
    both arms (degenerate -- cannot estimate a cluster SE)."""
    # Index rows by cycle for O(1) gather during resampling.
    by_cycle_a: dict[str, list[int]] = {}
    for i, c in enumerate(cycle_ids_a):
        by_cycle_a.setdefault(c, []).append(i)
    by_cycle_b: dict[str, list[int]] = {}
    for i, c in enumerate(cycle_ids_b):
        by_cycle_b.setdefault(c, []).append(i)

    all_cycles = sorted(set(by_cycle_a) | set(by_cycle_b))
    if len(all_cycles) < 2:
        return float("nan"), []

    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_draws):
        pick_idx = rng.integers(0, len(all_cycles), size=len(all_cycles))
        a_idx, b_idx = [], []
        for pi in pick_idx:
            c = all_cycles[pi]
            a_idx.extend(by_cycle_a.get(c, []))
            b_idx.extend(by_cycle_b.get(c, []))
        if not a_idx or not b_idx:
            continue
        rho = rank_biserial(scores_a[a_idx], scores_b[b_idx])
        if not np.isnan(rho):
            vals.append(rho)
    if len(vals) < 10:
        return float("nan"), vals
    return float(np.std(vals, ddof=1)), vals


def pooled_contrast(rows_a, rows_b, label: str) -> dict:
    """rows_a/rows_b: lists of dicts each with 'snr_db', 'score', 'cycle_id'.
    Returns per-stratum + inverse-variance-pooled rho_rb with a normal-approx CI."""
    per_stratum = []
    for si in range(len(STRATA)):
        a_s = [r for r in rows_a if stratum_of(r["snr_db"]) == si]
        b_s = [r for r in rows_b if stratum_of(r["snr_db"]) == si]
        n_a, n_b = len(a_s), len(b_s)
        entry = {"stratum": stratum_label(si), "n_a": n_a, "n_b": n_b}
        ok_power = n_a >= STRATUM_MIN_N and n_b >= STRATUM_MIN_N
        entry["power_ok"] = ok_power
        if n_a == 0 or n_b == 0:
            entry["rho_rb"] = None
            per_stratum.append(entry)
            continue
        scores_a = np.array([r["score"] for r in a_s])
        scores_b = np.array([r["score"] for r in b_s])
        cyc_a = [r["cycle_id"] for r in a_s]
        cyc_b = [r["cycle_id"] for r in b_s]
        rho = rank_biserial(scores_a, scores_b)
        se, _ = cluster_bootstrap_se_per_stratum(cyc_a, scores_a, cyc_b, scores_b)
        entry["rho_rb"] = rho
        entry["se_bootstrap"] = se
        per_stratum.append(entry)

    # Inverse-variance pooling over strata that (a) have both a point estimate and (b) a
    # usable (finite, >0) bootstrap SE. Strata failing the n>=200/200 power floor are
    # EXCLUDED from the pooled estimate too (ROW 0a already governs whether the whole
    # contrast is even reportable; a low-power stratum should not silently drag the
    # pooled point estimate around here).
    usable = [e for e in per_stratum if e.get("power_ok") and e.get("rho_rb") is not None
              and e.get("se_bootstrap") not in (None,) and not np.isnan(e.get("se_bootstrap", float("nan")))
              and e["se_bootstrap"] > 0]
    if usable:
        weights = np.array([1.0 / (e["se_bootstrap"] ** 2) for e in usable])
        rhos = np.array([e["rho_rb"] for e in usable])
        pooled_rho = float(np.sum(weights * rhos) / np.sum(weights))
        pooled_se = float(np.sqrt(1.0 / np.sum(weights)))
        ci_lo = pooled_rho - 1.96 * pooled_se
        ci_hi = pooled_rho + 1.96 * pooled_se
    else:
        pooled_rho = pooled_se = ci_lo = ci_hi = float("nan")

    return {
        "label": label,
        "per_stratum": per_stratum,
        "n_strata_usable": len(usable),
        "pooled_rho_rb": pooled_rho, "pooled_se": pooled_se,
        "ci_lo": ci_lo, "ci_hi": ci_hi,
    }


def is_saturated_row(r) -> bool:
    return bool(r["saturated"])


def m1_row(n_strata_ok, sat_frac_hit, sat_frac_miss, rho_null_vs_hit, rho_rb, ci_lo, ci_hi) -> str:
    """Verbatim from spec S6, with an explicit NaN guard: a NaN pooled statistic means
    the pooling itself could not be computed (e.g. no stratum had a usable bootstrap SE)
    -- that is an instrument failure in its own right, not a value that should be allowed
    to silently fail every numeric comparison and fall through to ROW 3."""
    if n_strata_ok < N_STRATA_OK_MIN:
        return "ROW 0a"
    if sat_frac_hit > SAT_FRAC_MAX or sat_frac_miss > SAT_FRAC_MAX:
        return "ROW 0b"
    if np.isnan(rho_null_vs_hit) or rho_null_vs_hit < RHO_NULL_MIN:
        return "ROW 0c"
    if np.isnan(rho_rb) or np.isnan(ci_lo) or np.isnan(ci_hi):
        return "ROW 0a"  # pooled HIT-vs-MISS statistic itself unavailable -- power failure
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

    hit = [r for r in results if r["arm"] == "HIT"]
    miss = [r for r in results if r["arm"] == "MISS"]
    null = [r for r in results if r["arm"] == "NULL"]
    print("HIT=%d MISS=%d NULL=%d" % (len(hit), len(miss), len(null)))

    # ── ROW 0a: strata with >=200 in BOTH HIT and MISS ──────────────────────────
    n_strata_ok = 0
    strata_power = []
    for si in range(len(STRATA)):
        n_hit_s = sum(1 for r in hit if stratum_of(r["snr_db"]) == si)
        n_miss_s = sum(1 for r in miss if stratum_of(r["snr_db"]) == si)
        ok = n_hit_s >= STRATUM_MIN_N and n_miss_s >= STRATUM_MIN_N
        strata_power.append({"stratum": stratum_label(si), "n_hit": n_hit_s, "n_miss": n_miss_s, "power_ok": ok})
        if ok:
            n_strata_ok += 1
    print("\nstrata power (need n>=%d in both HIT and MISS):" % STRATUM_MIN_N)
    for e in strata_power:
        print("  %-14s n_hit=%5d n_miss=%5d  %s" % (e["stratum"], e["n_hit"], e["n_miss"],
                                                       "OK" if e["power_ok"] else "UNDERPOWERED"))
    print("n_strata_ok = %d (need >= %d)" % (n_strata_ok, N_STRATA_OK_MIN))

    # ── ROW 0b: saturation fractions, whole-population per arm ──────────────────
    sat_frac_hit = sum(1 for r in hit if is_saturated_row(r)) / len(hit) if hit else float("nan")
    sat_frac_miss = sum(1 for r in miss if is_saturated_row(r)) / len(miss) if miss else float("nan")
    sat_frac_null = sum(1 for r in null if is_saturated_row(r)) / len(null) if null else float("nan")
    print("\nsaturation fraction: HIT=%.4f MISS=%.4f NULL=%.4f (bar > %.2f)"
          % (sat_frac_hit, sat_frac_miss, sat_frac_null, SAT_FRAC_MAX))

    # ── Main contrast: HIT vs MISS ───────────────────────────────────────────────
    hit_vs_miss = pooled_contrast(hit, miss, "HIT vs MISS")
    print("\nHIT vs MISS, per stratum:")
    for e in hit_vs_miss["per_stratum"]:
        rho_s = "n/a" if e["rho_rb"] is None else "%.4f" % e["rho_rb"]
        se_s = "n/a" if not e.get("se_bootstrap") or np.isnan(e.get("se_bootstrap", float("nan"))) else "%.4f" % e["se_bootstrap"]
        print("  %-14s n_hit=%5d n_miss=%5d power_ok=%-5s rho_rb=%8s se=%8s"
              % (e["stratum"], e["n_a"], e["n_b"], e["power_ok"], rho_s, se_s))
    print("pooled (inverse-variance, %d usable strata): rho_rb=%.4f  SE=%.4f  95%% CI=[%.4f, %.4f]"
          % (hit_vs_miss["n_strata_usable"], hit_vs_miss["pooled_rho_rb"], hit_vs_miss["pooled_se"],
             hit_vs_miss["ci_lo"], hit_vs_miss["ci_hi"]))

    # ── ROW 0c instrument check: HIT vs NULL ────────────────────────────────────
    hit_vs_null = pooled_contrast(hit, null, "HIT vs NULL")
    print("\nHIT vs NULL (instrument check), per stratum:")
    for e in hit_vs_null["per_stratum"]:
        rho_s = "n/a" if e["rho_rb"] is None else "%.4f" % e["rho_rb"]
        print("  %-14s n_hit=%5d n_null=%5d power_ok=%-5s rho_rb=%8s"
              % (e["stratum"], e["n_a"], e["n_b"], e["power_ok"], rho_s))
    print("pooled HIT vs NULL: rho_rb=%.4f (bar >= %.2f)" % (hit_vs_null["pooled_rho_rb"], RHO_NULL_MIN))

    # ── Gate ─────────────────────────────────────────────────────────────────────
    row = m1_row(n_strata_ok, sat_frac_hit, sat_frac_miss, hit_vs_null["pooled_rho_rb"],
                 hit_vs_miss["pooled_rho_rb"], hit_vs_miss["ci_lo"], hit_vs_miss["ci_hi"])
    print("\n>>> %s <<<" % row)

    report = {
        "spec": data["spec"], "dll_sha256": data["dll_sha256"], "shim_version": data["shim_version"],
        "n_hit": len(hit), "n_miss": len(miss), "n_null": len(null),
        "n_strata_ok": n_strata_ok, "strata_power": strata_power,
        "sat_frac_hit": sat_frac_hit, "sat_frac_miss": sat_frac_miss, "sat_frac_null": sat_frac_null,
        "hit_vs_miss": hit_vs_miss, "hit_vs_null": hit_vs_null,
        "row": row,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(REPORT_PATH, report)
    print("\nreport written: %s" % REPORT_PATH)


if __name__ == "__main__":
    main()
