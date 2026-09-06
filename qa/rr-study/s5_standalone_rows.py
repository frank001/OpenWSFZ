"""
S5-STANDALONE -- mechanical computation of ROW 0e, ROW 1, ROW 2, ROW 3.
ROW 0a/0b/0c/0d already established by direct measurement (see QA report).

Reuses the S5-BASELINE cp_interval() pattern (exact Clopper-Pearson via scipy.stats.beta).
Does not re-derive anything in spec Sec 1 (HK-018).
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

RUN_DIR = Path(__file__).resolve().parent / "results" / "2026-09-05-10bbaad-s5-standalone-n300"
JULY_K, JULY_N = 8, 300
NEW_K, NEW_N = 6, 300  # OpenWSFZ, from matcher.py / analyse.py (post warm-up-line correction)
JULY_GAP_FRACTION = 0.127

ROW2_SEED = 20260905
ROW2_MC_DRAWS = 2_000_000

# The 12 S5-BASELINE ROW 0c admissible runs (name, AWGN N, AWGN k, gap fraction from spec Sec 2.3)
ADMISSIBLE_12 = [
    ("2026-07-04-a3738fc-f002-s5-n300", 300, 8, 0.127),
    ("d011-fp-recheck-2026-07-04", 120, 7, 0.118),
    ("2026-07-07-df4cc89", 60, 0, 0.134),
    ("2026-08-05-3bd4cd0", 60, 0, 0.034),
    ("2026-08-15-8d6e1b1", 60, 1, 0.008),
    ("2026-08-21-7d36038", 60, 1, 0.496),
    ("2026-08-22-f5dec23", 60, 4, 0.529),
    ("2026-08-27-22b749c", 60, 0, 0.271),
    ("2026-08-29-872ba65", 60, 1, 0.0),
    ("2026-08-30-2e60949", 60, 2, 0.0),
    ("2026-09-02-3b52608", 60, 4, 0.034),
    ("2026-09-03-35378b9", 60, 2, 0.034),
]


def cp_interval(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson interval (HK-021(o): no bootstrap SE)."""
    if n == 0:
        return (float("nan"), float("nan"))
    alpha = 1.0 - conf
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def row0e_gap_fraction(truth_path: Path) -> dict:
    with open(truth_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows = [r for r in rows if r["scenario_id"] == "S5"]
    rows.sort(key=lambda r: (int(r["part_index"]), int(r["trial_index"])))
    cycles = [datetime.strptime(r["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) for r in rows]
    n_pairs = len(cycles) - 1
    gaps = 0
    for a, b in zip(cycles, cycles[1:]):
        delta = (b - a).total_seconds()
        if delta > 15.0:  # more than one 15s slot apart
            gaps += 1
    frac = gaps / n_pairs if n_pairs else float("nan")
    return {"n_trials": len(cycles), "n_pairs": n_pairs, "n_gaps": gaps, "gap_fraction": frac}


def row1(k: int, n: int, july_k: int, july_n: int) -> dict:
    ci = cp_interval(k, n)
    rate = k / n
    july_rate = july_k / july_n
    # Fisher exact one-sided (upper tail: is today's rate higher than July's), via
    # a 2x2 contingency table [[k, n-k], [july_k, july_n-july_k]], alternative='greater'
    table = [[k, n - k], [july_k, july_n - july_k]]
    _, p_one_sided = stats.fisher_exact(table, alternative="greater")
    ratio = rate / july_rate if july_rate else float("inf")
    fires = k >= 18
    july_ci = cp_interval(july_k, july_n)
    straddle = {
        "today_ci": ci,
        "threshold": 18 / 300,
        "today_ci_straddles_threshold": ci[0] <= (18 / 300) <= ci[1],
        "july_ci": july_ci,
        "july_ci_straddles_threshold": july_ci[0] <= (18 / 300) <= july_ci[1],
    }
    return {
        "k": k, "n": n, "rate": rate, "cp95": ci,
        "july_k": july_k, "july_n": july_n, "july_rate": july_rate, "july_ci95": july_ci,
        "fisher_one_sided_p": p_one_sided,
        "ratio_vs_july": ratio,
        "fires": fires,
        "straddle": straddle,
    }


def row2(pool_12: list, new_run: tuple) -> dict:
    pool = pool_12 + [new_run]
    names = [p[0] for p in pool]
    ns = np.array([p[1] for p in pool], dtype=np.int64)
    ks = np.array([p[2] for p in pool], dtype=np.int64)
    gaps = np.array([p[3] for p in pool], dtype=np.float64)
    total_events = int(ks.sum())

    def observed_stat(ks_arr, gaps_arr):
        return float(np.dot(ks_arr, gaps_arr))

    def two_sided_mc_p(ns_arr, gaps_arr, total, obs_stat, seed):
        probs = ns_arr / ns_arr.sum()
        rng = np.random.default_rng(seed)
        draws = rng.multinomial(total, probs, size=ROW2_MC_DRAWS)
        stats_sim = draws @ gaps_arr
        p_ge = float(np.mean(stats_sim >= obs_stat))
        p_le = float(np.mean(stats_sim <= obs_stat))
        p = 2.0 * min(p_ge, p_le)
        return min(p, 1.0), p_ge, p_le

    obs = observed_stat(ks, gaps)
    p_full, p_ge, p_le = two_sided_mc_p(ns, gaps, total_events, obs, ROW2_SEED)

    loo = []
    for i, name in enumerate(names):
        ks_i = np.delete(ks, i)
        ns_i = np.delete(ns, i)
        gaps_i = np.delete(gaps, i)
        total_i = int(ks_i.sum())
        if total_i == 0 or len(ks_i) == 0:
            loo.append((name, None))
            continue
        obs_i = observed_stat(ks_i, gaps_i)
        p_i, _, _ = two_sided_mc_p(ns_i, gaps_i, total_i, obs_i, ROW2_SEED + i + 1)
        loo.append((name, p_i))

    any_loo_above_010 = any(p is not None and p > 0.10 for _, p in loo)
    fires = (p_full < 0.05) and (not any_loo_above_010)

    return dict(
        population=names, n_awgn=ns.tolist(), k_awgn=ks.tolist(), gap_fraction=gaps.tolist(),
        total_events=total_events, observed_stat=obs, p_full=p_full, p_ge=p_ge, p_le=p_le,
        leave_one_out=loo, fires=fires, seed=ROW2_SEED, mc_draws=ROW2_MC_DRAWS,
        two_sided_method="p = 2*min(P(T_sim>=obs), P(T_sim<=obs)), capped at 1",
    )


def row3(new_k: int, new_n: int, fixed_build_k: int, fixed_build_n: int) -> dict:
    return {
        "today_k": new_k, "today_n": new_n, "today_ci95": cp_interval(new_k, new_n),
        "fixed_build_run": "2026-09-03-35378b9",
        "fixed_build_k": fixed_build_k, "fixed_build_n": fixed_build_n,
        "fixed_build_ci95": cp_interval(fixed_build_k, fixed_build_n),
        "note": "descriptive only -- no p-value, no ratio, no adjudication (spec Sec 4 ROW 3)",
    }


def main():
    truth_path = RUN_DIR / "truth.csv"
    r0e = row0e_gap_fraction(truth_path)
    r0e["july_gap_fraction"] = JULY_GAP_FRACTION
    r0e["exceeds_40pct_bound"] = r0e["gap_fraction"] > 0.40

    r1 = row1(NEW_K, NEW_N, JULY_K, JULY_N)

    new_run_tuple = ("2026-09-05-10bbaad-s5-standalone-n300", NEW_N, NEW_K, r0e["gap_fraction"])
    r2 = row2(ADMISSIBLE_12, new_run_tuple)

    r3 = row3(NEW_K, NEW_N, fixed_build_k=2, fixed_build_n=60)

    result = {"row0e": r0e, "row1": r1, "row2": r2, "row3": r3}
    out_path = Path(__file__).resolve().parent / "s5_standalone_rows_result.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="ascii")

    print("=== ROW 0e ===")
    print(json.dumps(r0e, indent=2))
    print("\n=== ROW 1 ===")
    print(json.dumps({k: v for k, v in r1.items() if k != "straddle"}, indent=2))
    print(json.dumps(r1["straddle"], indent=2))
    print("\n=== ROW 2 ===")
    print(json.dumps({k: v for k, v in r2.items() if k not in ("leave_one_out",)}, indent=2))
    print("Leave-one-out p values:")
    for name, p in r2["leave_one_out"]:
        print(f"  {name:38s} p={p}")
    print("\n=== ROW 3 ===")
    print(json.dumps(r3, indent=2))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
