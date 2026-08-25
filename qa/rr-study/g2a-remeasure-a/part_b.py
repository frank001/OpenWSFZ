"""G2A-REMEASURE-A Part B (GATED) -- does the fix close bucket B1? Spec
Sec.5, AMENDED by 2026-08-25-1550 Sec.3.1/3.2: nulls P (primary) and Q
(mandatory second) replace the original circular-shift/permutation pair;
null R (circular shift) is retained ONLY as a diagnostic, laid beside arm
#1's published figures, and may not enter any gate/CI/headline number.

ROW B3 (amended): Gate B evaluated independently under null P and under
null Q. Per-null classification of DeltaB1's 95% CI:
  - excludes zero, positive -> candidate 'B1'
  - includes zero           -> candidate 'B2'
  - excludes zero, negative -> candidate 'B_NEG' (not in the spec's table --
    L2's bucket B1 is LARGER than L1's; reported plainly if it occurs, never
    silently folded into B1 or B2)
If both nulls' candidates agree, that is the arm's row. If they disagree
(including EITHER candidate being B_NEG), the row is B3, UNRESOLVED --
report both readings, propose nothing (amendment Sec.3.2, no averaging, no
friendlier-null picking).
"""
from __future__ import annotations

import math
import statistics

import common_g2a as G
import nulls_pq as NPQ
from partition import circular_shift_lookup, classify_partition, ours_lookup_from_population

Z95 = 1.959963984540054
N_NULL_TRIALS = 200
NULL_P_BASE_SEED = 20260825101
NULL_Q_BASE_SEED = 20260825102
NULL_R_BASE_SEED = 20260825103  # diagnostic only


def _mean_sd(samples):
    n = len(samples)
    mean = statistics.mean(samples)
    sd = statistics.pstdev(samples) if n > 1 else 0.0
    return mean, sd


def _per_cycle_b1_b2(bucket_of):
    b1 = {}
    b2 = {}
    for (ts, _msg), b in bucket_of.items():
        if b == "B1":
            b1[ts] = b1.get(ts, 0.0) + 1.0
        elif b == "B2":
            b2[ts] = b2.get(ts, 0.0) + 1.0
    return b1, b2


def _excess_ci(obs_by_cycle, obs_count, null_mean, null_sd):
    _, lo_obs, hi_obs = G.gc.cluster_bootstrap_ci(obs_by_cycle)
    se_obs = (hi_obs - lo_obs) / (2 * Z95)
    excess = obs_count - null_mean
    se_total = math.sqrt(se_obs ** 2 + null_sd ** 2)
    ci = (excess - Z95 * se_total, excess + Z95 * se_total)
    return excess, se_total, ci


def _leg_analysis(pop, ours_rows, label, pool, strata, log):
    """Real (observed) partition for one leg, plus null P/Q/R trial runs."""
    ours_lookup = ours_lookup_from_population(pop)
    bucket_of = classify_partition(pop, ours_lookup)
    b1_by_cycle, b2_by_cycle = _per_cycle_b1_b2(bucket_of)
    obs_b1 = sum(b1_by_cycle.values())
    obs_b2 = sum(b2_by_cycle.values())
    log("Part B [%s]: observed B1=%d B2=%d" % (label, obs_b1, obs_b2))

    # null P
    p_trials = NPQ.run_null_trials_pq(pop, NPQ.iid_resample_lookup, N_NULL_TRIALS,
                                       NULL_P_BASE_SEED, precompute_shared=pool)
    p_b1 = [t["B1"] for t in p_trials]
    p_b2 = [t["B2"] for t in p_trials]
    p_b1_mean, p_b1_sd = _mean_sd(p_b1)
    p_b2_mean, p_b2_sd = _mean_sd(p_b2)

    # null Q
    q_trials = NPQ.run_null_trials_pq(pop, NPQ.density_matched_derangement_lookup, N_NULL_TRIALS,
                                       NULL_Q_BASE_SEED, precompute_shared=strata)
    q_b1 = [t["B1"] for t in q_trials]
    q_b2 = [t["B2"] for t in q_trials]
    q_b1_mean, q_b1_sd = _mean_sd(q_b1)
    q_b2_mean, q_b2_sd = _mean_sd(q_b2)

    # null R -- DIAGNOSTIC ONLY, laid beside arm #1's published figures
    r_trials = []
    for i in range(N_NULL_TRIALS):
        lookup = circular_shift_lookup(pop, NULL_R_BASE_SEED + i)
        bo = classify_partition(pop, lookup)
        r_trials.append({"B1": sum(1 for v in bo.values() if v == "B1"),
                          "B2": sum(1 for v in bo.values() if v == "B2")})
    r_b1_mean, r_b1_sd = _mean_sd([t["B1"] for t in r_trials])
    r_b2_mean, r_b2_sd = _mean_sd([t["B2"] for t in r_trials])

    log("Part B [%s]: null P  B1 mean=%.1f sd=%.1f | B2 mean=%.1f sd=%.1f"
        % (label, p_b1_mean, p_b1_sd, p_b2_mean, p_b2_sd))
    log("Part B [%s]: null Q  B1 mean=%.1f sd=%.1f | B2 mean=%.1f sd=%.1f"
        % (label, q_b1_mean, q_b1_sd, q_b2_mean, q_b2_sd))
    log("Part B [%s]: null R (DIAGNOSTIC, biased low ~1.85x, see 2026-08-25-1550 Sec.2) "
        "B1 mean=%.1f sd=%.1f | B2 mean=%.1f sd=%.1f"
        % (label, r_b1_mean, r_b1_sd, r_b2_mean, r_b2_sd))

    p_excess_b1, p_se_b1, p_ci_b1 = _excess_ci(b1_by_cycle, obs_b1, p_b1_mean, p_b1_sd)
    q_excess_b1, q_se_b1, q_ci_b1 = _excess_ci(b1_by_cycle, obs_b1, q_b1_mean, q_b1_sd)
    r_excess_b1, r_se_b1, r_ci_b1 = _excess_ci(b1_by_cycle, obs_b1, r_b1_mean, r_b1_sd)
    p_excess_b2, p_se_b2, p_ci_b2 = _excess_ci(b2_by_cycle, obs_b2, p_b2_mean, p_b2_sd)
    q_excess_b2, q_se_b2, q_ci_b2 = _excess_ci(b2_by_cycle, obs_b2, q_b2_mean, q_b2_sd)

    return {
        "observed": {"B1": obs_b1, "B2": obs_b2},
        "b1_by_cycle": b1_by_cycle, "b2_by_cycle": b2_by_cycle,
        "null_p": {"B1": {"mean": p_b1_mean, "sd": p_b1_sd}, "B2": {"mean": p_b2_mean, "sd": p_b2_sd}},
        "null_q": {"B1": {"mean": q_b1_mean, "sd": q_b1_sd}, "B2": {"mean": q_b2_mean, "sd": q_b2_sd}},
        "null_r_diagnostic": {"B1": {"mean": r_b1_mean, "sd": r_b1_sd}, "B2": {"mean": r_b2_mean, "sd": r_b2_sd}},
        "excess_b1": {"P": {"value": p_excess_b1, "se": p_se_b1, "ci": p_ci_b1},
                      "Q": {"value": q_excess_b1, "se": q_se_b1, "ci": q_ci_b1},
                      "R_diagnostic": {"value": r_excess_b1, "se": r_se_b1, "ci": r_ci_b1}},
        "excess_b2": {"P": {"value": p_excess_b2, "se": p_se_b2, "ci": p_ci_b2},
                      "Q": {"value": q_excess_b2, "se": q_se_b2, "ci": q_ci_b2}},
    }


def _classify_delta(ci):
    lo, hi = ci
    if lo > 0:
        return "excludes_zero_positive"
    if hi < 0:
        return "excludes_zero_negative"
    return "includes_zero"


def run_part_b(l1_ours_rows, l2_ours_rows, theirs_rows, log) -> dict:
    pop_l1 = G.gc.Population(l1_ours_rows, theirs_rows)
    pop_l2 = G.gc.Population(l2_ours_rows, theirs_rows)

    our_hash_rate_l1 = sum(1 for r in l1_ours_rows if r["has_hash"]) / len(l1_ours_rows)
    our_hash_rate_l2 = sum(1 for r in l2_ours_rows if r["has_hash"]) / len(l2_ours_rows)
    ref_hash_rate = sum(1 for r in theirs_rows if r["has_hash"]) / len(theirs_rows)
    log("Part B: unresolved-hash rate -- L1(pre)=%.2f%% L2(post)=%.2f%% reference=%.2f%%"
        % (our_hash_rate_l1 * 100, our_hash_rate_l2 * 100, ref_hash_rate * 100))
    log("Part B: 08-08 leg comparison figure on record: ours 5.5%% vs reference 1.7%%")

    # shared null-P pool / null-Q strata computed PER LEG (each leg's own
    # corpus-wide ours pool/strata -- pool/strata must reflect that leg's own
    # decode population, not the other leg's)
    pool_l1 = NPQ.build_ours_pool(pop_l1)
    strata_l1 = NPQ._density_strata(pop_l1)
    pool_l2 = NPQ.build_ours_pool(pop_l2)
    strata_l2 = NPQ._density_strata(pop_l2)

    log("Part B: analysing L1 (pre-G2a) leg...")
    l1_res = _leg_analysis(pop_l1, l1_ours_rows, "L1(pre)", pool_l1, strata_l1, log)
    log("Part B: analysing L2 (post-G2a) leg...")
    l2_res = _leg_analysis(pop_l2, l2_ours_rows, "L2(post)", pool_l2, strata_l2, log)

    # DeltaB1 per null = excess_B1(L1) - excess_B1(L2), legs independent
    results_per_null = {}
    for null_name in ("P", "Q"):
        e1 = l1_res["excess_b1"][null_name]
        e2 = l2_res["excess_b1"][null_name]
        delta = e1["value"] - e2["value"]
        se = math.sqrt(e1["se"] ** 2 + e2["se"] ** 2)
        ci = (delta - Z95 * se, delta + Z95 * se)
        candidate = _classify_delta(ci)
        results_per_null[null_name] = {"delta_b1": delta, "se": se, "ci": ci, "candidate": candidate}
        log("Part B: null %s -- DeltaB1 (excess_B1(L1) - excess_B1(L2)) = %.1f, "
            "95%% CI [%.1f, %.1f] -> candidate=%s"
            % (null_name, delta, ci[0], ci[1], candidate))

    # diagnostic null R, reported not gated
    eR1 = l1_res["excess_b1"]["R_diagnostic"]
    eR2 = l2_res["excess_b1"]["R_diagnostic"]
    delta_r = eR1["value"] - eR2["value"]
    se_r = math.sqrt(eR1["se"] ** 2 + eR2["se"] ** 2)
    ci_r = (delta_r - Z95 * se_r, delta_r + Z95 * se_r)
    log("Part B: null R (DIAGNOSTIC ONLY, not gated) -- DeltaB1 = %.1f, 95%% CI [%.1f, %.1f]"
        % (delta_r, ci_r[0], ci_r[1]))

    cand_p = results_per_null["P"]["candidate"]
    cand_q = results_per_null["Q"]["candidate"]
    if cand_p == cand_q == "excludes_zero_positive":
        row = "B1"
        reading = "The gap itself is smaller than the record says, by a measured amount. Restate before funding further DSP work."
    elif cand_p == cand_q == "includes_zero":
        row = "B2"
        reading = "Text improved but the gap did not -- our <...> decodes were not the ones the reference was resolving. A genuinely informative negative."
    else:
        row = "B3"
        reading = ("UNRESOLVED -- Gate B evaluated under null P and null Q gives different "
                   "candidate rows (P=%s, Q=%s). Per the amendment's Sec.3.2 rule: no "
                   "averaging, no picking the friendlier null. Report both readings, "
                   "propose nothing." % (cand_p, cand_q))
    log("Part B: ROW %s -- %s" % (row, reading))

    # amendment Sec.3.3 -- bucket B2 re-derived on L1, descriptive, not gated
    log("Part B (Sec.3.3, descriptive, NOT gated): bucket B2 excess on L1 under "
        "null P = %.1f (CI %.1f..%.1f), under null Q = %.1f (CI %.1f..%.1f)"
        % (l1_res["excess_b2"]["P"]["value"], l1_res["excess_b2"]["P"]["ci"][0], l1_res["excess_b2"]["P"]["ci"][1],
           l1_res["excess_b2"]["Q"]["value"], l1_res["excess_b2"]["Q"]["ci"][0], l1_res["excess_b2"]["Q"]["ci"][1]))

    return {
        "hash_rate": {"l1_pre": our_hash_rate_l1, "l2_post": our_hash_rate_l2, "reference": ref_hash_rate,
                      "0808_leg_ours": 0.055, "0808_leg_reference": 0.017},
        "l1_leg": l1_res, "l2_leg": l2_res,
        "delta_b1_per_null": results_per_null,
        "delta_b1_null_r_diagnostic": {"value": delta_r, "se": se_r, "ci": ci_r},
        "b2_on_l1_sec3_3": {"P": l1_res["excess_b2"]["P"], "Q": l1_res["excess_b2"]["Q"]},
        "row": row, "reading": reading,
    }
