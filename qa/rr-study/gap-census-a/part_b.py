"""GAP-CENSUS-A Part B (GATED) -- the text-recovery census, null-corrected.
Spec Sec.5. The null is mandatory and is disclosed in the spec's own Sec.0.3
as "the whole lesson" of this arm -- a raw co-location count is not a result.
"""
from __future__ import annotations

import math
import statistics

from common import cluster_bootstrap_ci
from partition import (circular_shift_lookup, cycle_permutation_lookup,
                        run_null_trials)

N_NULL_TRIALS = 200         # spec Sec.5.2: ">=200 offsets, not the five I used"
NULL1_BASE_SEED = 20260823001   # circular-shift null seed grid, sorted-at-construction (range())
NULL2_BASE_SEED = 20260823002   # cycle-permutation null, a DIFFERENT construction (spec Sec.5.2)
ROW0E_BAR_PP = 0.25          # half-width bar, in pp of D-001


def _mean_sd_halfwidth(samples: list[int]) -> tuple[float, float, float]:
    n = len(samples)
    mean = statistics.mean(samples)
    sd = statistics.pstdev(samples) if n > 1 else 0.0
    se_of_mean = sd / math.sqrt(n) if n > 0 else float("nan")
    half_width = 1.959963984540054 * se_of_mean
    return mean, sd, half_width


def _observed_per_cycle_counts(bucket_of: dict[tuple, str]) -> tuple[dict[str, float], dict[str, float]]:
    b1_by_cycle: dict[str, float] = {}
    b2_by_cycle: dict[str, float] = {}
    for (ts, _msg), bucket in bucket_of.items():
        if bucket == "B1":
            b1_by_cycle[ts] = b1_by_cycle.get(ts, 0.0) + 1.0
        elif bucket == "B2":
            b2_by_cycle[ts] = b2_by_cycle.get(ts, 0.0) + 1.0
    return b1_by_cycle, b2_by_cycle


def run_part_b(pop, bucket_of: dict[tuple, str], log) -> dict:
    # ---- observed ----
    b1_by_cycle, b2_by_cycle = _observed_per_cycle_counts(bucket_of)
    obs_b1 = sum(b1_by_cycle.values())
    obs_b2 = sum(b2_by_cycle.values())
    log("Part B: observed co-locations B1(hash)=%d B2(other)=%d" % (obs_b1, obs_b2))

    # ---- hash-rate comparison (spec Sec.5.3, mandatory disclosure) ----
    our_hash_rate = sum(1 for r in pop.ours_rows if r["has_hash"]) / pop.n_ours
    ref_hash_rate = sum(1 for r in pop.theirs_rows if r["has_hash"]) / pop.n_theirs
    log("Part B: unresolved-hash rate -- ours=%.2f%% reference=%.2f%% (near parity if close; "
        "the 2026-08-08 leg that motivated G2(a) showed 5.5%% vs 1.7%%)"
        % (our_hash_rate * 100, ref_hash_rate * 100))

    # ---- null 1: circular frequency shift, independent per cycle ----
    log("Part B: running null 1 (circular frequency shift), %d trials..." % N_NULL_TRIALS)
    null1_trials = run_null_trials(pop, circular_shift_lookup, N_NULL_TRIALS, NULL1_BASE_SEED)
    null1_b1 = [t["B1"] for t in null1_trials]
    null1_b2 = [t["B2"] for t in null1_trials]
    n1_b1_mean, n1_b1_sd, n1_b1_hw = _mean_sd_halfwidth(null1_b1)
    n1_b2_mean, n1_b2_sd, n1_b2_hw = _mean_sd_halfwidth(null1_b2)
    log("Part B: null 1 (circular shift) B1: mean=%.1f sd=%.1f half-width=%.2f (%.3fpp)"
        % (n1_b1_mean, n1_b1_sd, n1_b1_hw, pop.pp_of_d001(n1_b1_hw)))
    log("Part B: null 1 (circular shift) B2: mean=%.1f sd=%.1f half-width=%.2f (%.3fpp)"
        % (n1_b2_mean, n1_b2_sd, n1_b2_hw, pop.pp_of_d001(n1_b2_hw)))

    # ---- null 2: cycle-label permutation (a different construction) ----
    log("Part B: running null 2 (cycle-label permutation), %d trials..." % N_NULL_TRIALS)
    null2_trials = run_null_trials(pop, cycle_permutation_lookup, N_NULL_TRIALS, NULL2_BASE_SEED)
    null2_b1 = [t["B1"] for t in null2_trials]
    null2_b2 = [t["B2"] for t in null2_trials]
    n2_b1_mean, n2_b1_sd, n2_b1_hw = _mean_sd_halfwidth(null2_b1)
    n2_b2_mean, n2_b2_sd, n2_b2_hw = _mean_sd_halfwidth(null2_b2)
    log("Part B: null 2 (cycle permutation) B1: mean=%.1f sd=%.1f half-width=%.2f (%.3fpp)"
        % (n2_b1_mean, n2_b1_sd, n2_b1_hw, pop.pp_of_d001(n2_b1_hw)))
    log("Part B: null 2 (cycle permutation) B2: mean=%.1f sd=%.1f half-width=%.2f (%.3fpp)"
        % (n2_b2_mean, n2_b2_sd, n2_b2_hw, pop.pp_of_d001(n2_b2_hw)))

    # ---- ROW 0e: null adequacy, worst-case half-width across both nulls/buckets ----
    worst_hw_pp = max(pop.pp_of_d001(hw) for hw in (n1_b1_hw, n1_b2_hw, n2_b1_hw, n2_b2_hw))
    row0e_ok = worst_hw_pp <= ROW0E_BAR_PP
    log("Part B: ROW 0e -- worst-case null half-width = %.3fpp, bar <= %.2fpp -> %s"
        % (worst_hw_pp, ROW0E_BAR_PP, "PASS" if row0e_ok else "FAIL (Bucket B -> UNRESOLVED)"))

    # ---- the two nulls must agree within the ROW 0e bar, or B is unresolved ----
    b1_disagree_pp = pop.pp_of_d001(abs(n1_b1_mean - n2_b1_mean))
    b2_disagree_pp = pop.pp_of_d001(abs(n1_b2_mean - n2_b2_mean))
    nulls_agree = (b1_disagree_pp <= ROW0E_BAR_PP) and (b2_disagree_pp <= ROW0E_BAR_PP)
    log("Part B: null1 vs null2 disagreement -- B1=%.3fpp B2=%.3fpp, bar=%.2fpp -> %s"
        % (b1_disagree_pp, b2_disagree_pp, ROW0E_BAR_PP,
           "AGREE" if nulls_agree else "DISAGREE (Bucket B -> UNRESOLVED)"))

    # ---- excess + combined CI (primary null = null 1, circular shift) ----
    _, obs_b1_lo, obs_b1_hi = cluster_bootstrap_ci(b1_by_cycle)
    _, obs_b2_lo, obs_b2_hi = cluster_bootstrap_ci(b2_by_cycle)
    se_obs_b1 = (obs_b1_hi - obs_b1_lo) / (2 * 1.959963984540054)
    se_obs_b2 = (obs_b2_hi - obs_b2_lo) / (2 * 1.959963984540054)
    se_null1_b1 = n1_b1_sd  # per-trial spread of the null's OWN estimator, not its mean's SE
    se_null1_b2 = n1_b2_sd

    excess_b1 = obs_b1 - n1_b1_mean
    excess_b2 = obs_b2 - n1_b2_mean
    se_total_b1 = math.sqrt(se_obs_b1 ** 2 + se_null1_b1 ** 2)
    se_total_b2 = math.sqrt(se_obs_b2 ** 2 + se_null1_b2 ** 2)
    ci_b1 = (excess_b1 - 1.959963984540054 * se_total_b1, excess_b1 + 1.959963984540054 * se_total_b1)
    ci_b2 = (excess_b2 - 1.959963984540054 * se_total_b2, excess_b2 + 1.959963984540054 * se_total_b2)

    pp_b1 = pop.pp_of_d001(excess_b1)
    pp_b2 = pop.pp_of_d001(excess_b2)
    pp_b1_ci = (pop.pp_of_d001(ci_b1[0]), pop.pp_of_d001(ci_b1[1]))
    pp_b2_ci = (pop.pp_of_d001(ci_b2[0]), pop.pp_of_d001(ci_b2[1]))

    log("Part B: excess B1 = %.1f (95%% CI %.1f..%.1f), %.2fpp (CI %.2f..%.2fpp)"
        % (excess_b1, ci_b1[0], ci_b1[1], pp_b1, pp_b1_ci[0], pp_b1_ci[1]))
    log("Part B: excess B2 = %.1f (95%% CI %.1f..%.1f), %.2fpp (CI %.2f..%.2fpp)"
        % (excess_b2, ci_b2[0], ci_b2[1], pp_b2, pp_b2_ci[0], pp_b2_ci[1]))

    # ---- gate, spec Sec.5.3 ----
    b1_excludes_zero = ci_b1[0] > 0
    b2_excludes_zero = ci_b2[0] > 0

    if not row0e_ok or not nulls_agree:
        row = "B3"
        reading = ("Text recovery is not established (ROW 0e failed or the two nulls "
                   "disagree beyond the bar). Report the counts and the null; propose nothing.")
    elif b1_excludes_zero and excess_b1 > excess_b2:
        row = "B1"
        reading = ("Text recovery is dominated by hash resolution. G2(a) (256->4096, merged "
                   "9500e03) targets it directly and has never been re-measured -- a "
                   "post-G2(a) re-measure is recommended as the cheapest item on the board.")
    elif b2_excludes_zero and excess_b2 > excess_b1:
        row = "B2"
        reading = ("Text recovery is NOT primarily hash -- the T3 callsign-character "
                   "population needs its own diagnosis before any fix is proposed.")
    elif not b1_excludes_zero and not b2_excludes_zero:
        row = "B3"
        reading = "S_B CI includes zero for both buckets. Report the counts and the null; propose nothing."
    else:
        row = "B3"
        reading = ("Mixed signal (one bucket's CI excludes zero but does not dominate cleanly). "
                   "Report the counts and the null; propose nothing beyond what is directly "
                   "supported.")

    log("Part B: ROW %s -- %s" % (row, reading))

    return {
        "observed": {"B1": obs_b1, "B2": obs_b2},
        "hash_rate": {"ours": our_hash_rate, "reference": ref_hash_rate},
        "null1_circular_shift": {
            "n_trials": N_NULL_TRIALS,
            "B1": {"mean": n1_b1_mean, "sd": n1_b1_sd, "half_width": n1_b1_hw,
                   "half_width_pp": pop.pp_of_d001(n1_b1_hw)},
            "B2": {"mean": n1_b2_mean, "sd": n1_b2_sd, "half_width": n1_b2_hw,
                   "half_width_pp": pop.pp_of_d001(n1_b2_hw)},
        },
        "null2_cycle_permutation": {
            "n_trials": N_NULL_TRIALS,
            "B1": {"mean": n2_b1_mean, "sd": n2_b1_sd, "half_width": n2_b1_hw,
                   "half_width_pp": pop.pp_of_d001(n2_b1_hw)},
            "B2": {"mean": n2_b2_mean, "sd": n2_b2_sd, "half_width": n2_b2_hw,
                   "half_width_pp": pop.pp_of_d001(n2_b2_hw)},
        },
        "row0e": {"pass": row0e_ok, "worst_half_width_pp": worst_hw_pp, "bar_pp": ROW0E_BAR_PP},
        "nulls_agree": nulls_agree,
        "nulls_disagreement_pp": {"B1": b1_disagree_pp, "B2": b2_disagree_pp},
        "excess": {
            "B1": {"count": excess_b1, "ci": ci_b1, "pp": pp_b1, "pp_ci": pp_b1_ci},
            "B2": {"count": excess_b2, "ci": ci_b2, "pp": pp_b2, "pp_ci": pp_b2_ci},
        },
        "row": row,
        "reading": reading,
    }
