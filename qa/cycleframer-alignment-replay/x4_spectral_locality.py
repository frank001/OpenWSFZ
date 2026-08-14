#!/usr/bin/env python3
"""X4 -- S.1 REOPENED: within-cycle spectral locality, third and final attempt.

Spec: qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-x4-s1-reopened-within-cycle-spectral-locality.md
Pre-registered gate per HK-021; rows evaluated in strict order (see main()).

Question: given X2 already measured the crowding cost (F_std = +17.22 pp), is that cost
delivered by SPECIFIC NEAR NEIGHBOURS (LOCAL: pairwise co-channel contamination) or DIFFUSELY
by the whole cycle (DIFFUSE: aggregate noise-floor rise)?

Fixes both prior instrument failures (spec S1):
  - S.1 (2026-07-31) VOID: n_local proxied n_cycle (a between-cycle confound). Fix: a
    WITHIN-CYCLE estimator -- each cycle is its own stratum by construction, so density
    cannot be a confound (a cycle has exactly one density).
  - S.1r (2026-08-07) ROW 4: an ABSOLUTE 150 Hz cut left the "clear" stratum unpopulated
    (0/12 cells). Fix: GLOBAL QUANTILE cuts on separation (HK-021(b)+(g)), never absolute Hz.

Population: REF = raw A n B (ts, message) intersection, 20m weekend corpus, via
t1_frequency_quantisation.load() UNMODIFIED -- the SAME population P1/P2/P3/T1 use (must
reproduce 69222 exactly, ROW 0a). NOT X1's further hash+band-excluded "clean" population
(67243) -- the spec's own ROW 0a bar pins 69222, so this arm follows the raw-REF convention.
SNR is standardised on X1/X2's PINNED L1 edges [-15, -10, -5, 2] -- never re-derived
(HK-021(g)).

Band-edge exclusion (spec S3.3, S.1r's fix carried forward verbatim): decodes outside
[200, 3000) Hz are 100% missed by construction (ft8_shim.c's hardcoded search band) --
excluded from the OUTCOME tally but RETAINED as candidate neighbours for other decodes' sep
(they are real signals genuinely on the air).

No src/ change. No capture. No decoder replay. Pure re-analysis of ALL.TXT already on disk.
NFR-021: message text is read only to build (ts, message) match keys and is never printed or
written to any output file.
"""
from __future__ import annotations

import collections
import io
import json
import os
import random
import statistics
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_frequency_quantisation import load, WINDOW_20M, LEG_20M  # noqa: E402

SEED = 20260810
N_BOOT = 1000
N_SHUFFLE = 20
BAND_LO_HZ, BAND_HI_HZ = 200.0, 3000.0
L1_EDGES = [-15, -10, -5, 2]        # X1/X2's pinned SNR quintile edges -- never re-derived
REF_EXPECTED = 69222
MIN_DECODES_PER_STRATUM = 300       # spec S3, ROW 0e
MIN_CYCLES_PER_STRATUM = 150        # spec S3, ROW 0e
MIN_DISTINCT_SEP = 50               # spec S3, ROW 0d / HK-021(f)
NULL_BAR_PP = 2.0                   # spec S3, ROW 0b
POWER_BAR_PP = 2.0                  # spec S3, ROW 0f
GATE_ROW1_PP = 8.0
GATE_ROW2_PP = 3.0
GATE_ROW2_SE_PP = 1.5


def assign_stratum(v, edges):
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def quintile_edges(values):
    s = sorted(values)
    n = len(s)
    return [s[int(n * k / 5)] for k in range(1, 5)]


# ---- population ------------------------------------------------------------------------

def load_ref():
    lo, hi = WINDOW_20M
    a = load(LEG_20M["wsjtx_a"], lo, hi)
    b = load(LEG_20M["wsjtx_b"], lo, hi)
    o = load(LEG_20M["owsfz"], lo, hi)
    ref_raw = set(a) & set(b)
    return a, o, ref_raw


def build_records(a, o, ref_raw):
    """One record per REF decode: n_cycle (density, includes band-edge decodes), sep (Hz to
    nearest OTHER REF decode in the same cycle, computed against ALL decodes in the cycle
    including band-edge ones, per spec S3.3), missed, snr, band_edge flag. Single-decode
    cycles are excluded (sep undefined).

    Iterates ref_raw in SORTED (deterministic) order, not raw set-iteration order: `ref_raw`
    is a set of (ts, message) string tuples, and Python's per-process string hash
    randomisation makes set-iteration order differ run to run. That order silently leaks
    into every downstream per-cycle list (by_cycle[ts]), which is what ROW 0b's frequency-
    permutation shuffle later consumes positionally -- an unsorted build makes the whole
    pipeline non-deterministic under a fixed seed despite looking seeded. Sorting here is
    the single fix that makes every consumer downstream deterministic for free.
    """
    by_cycle = collections.defaultdict(list)
    for k in sorted(ref_raw):
        ts, msg = k
        snr, freq_hz = a[k]
        by_cycle[ts].append({"ts": ts, "snr": snr, "freq_hz": freq_hz, "missed": k not in o})

    records = []
    n_excluded_single = 0
    for ts, decs in by_cycle.items():
        n_cycle = len(decs)
        if n_cycle < 2:
            n_excluded_single += len(decs)
            continue
        freqs = [d["freq_hz"] for d in decs]
        for i, d in enumerate(decs):
            others = [freqs[j] for j in range(n_cycle) if j != i]
            sep = min(abs(d["freq_hz"] - f) for f in others)
            band_edge = not (BAND_LO_HZ <= d["freq_hz"] < BAND_HI_HZ)
            records.append({
                "ts": ts, "snr": d["snr"], "freq_hz": d["freq_hz"], "missed": d["missed"],
                "n_cycle": n_cycle, "sep": sep, "band_edge": band_edge,
            })
    return records, n_excluded_single


def outcome_population(records):
    """Non-band-edge records only -- the population the E_sep estimator reads (spec S3.3)."""
    return [r for r in records if not r["band_edge"]]


def tag_strata(records, sep_edges):
    for r in records:
        r["snr_stratum"] = assign_stratum(r["snr"], L1_EDGES)
        r["sep_q"] = assign_stratum(r["sep"], sep_edges)   # 0=Q1 (closest) .. 4=Q5 (farthest)


# ---- the within-cycle estimator --------------------------------------------------------

def compute_E_sep(records, weight_of=None,
                   min_decodes=MIN_DECODES_PER_STRATUM, min_cycles=MIN_CYCLES_PER_STRATUM,
                   apply_power_gate=True, fixed_qualifying=None):
    """spec S2: 'for each cycle c and each SNR stratum s, compute the miss-rate difference
    between Q1 and Q5 using only decodes in that cycle and stratum; pool those within-cycle
    contrasts across all cycles, weighted by minority-side support.'

    Operationalisation (disclosed, the spec's pseudocode does not spell out the pooling
    weights): for each (cycle, SNR-stratum) cell carrying >=1 record in BOTH Q1 and Q5
    (the mandatory support condition), weight = min(n_Q1, n_Q5) in that cell (minority-side
    support); E_sep = sum(weight * (missrate_Q1 - missrate_Q5)) / sum(weight), pooled first
    within each SNR stratum, then across the strata that qualify at the 300-decode /
    150-cycle bar (spec ROW 0e). apply_power_gate=False + fixed_qualifying is used by the
    bootstrap engines, which hold the SET of qualifying strata fixed at the point estimate
    (standard practice -- re-deriving which strata qualify inside every bootstrap draw would
    conflate qualification noise with the estimator's own sampling noise).

    weight_of(record) -> float lets the frequency-clustered bootstrap reweight individual
    records by their frequency-cluster's draw multiplicity without recomputing sep/n_cycle.
    """
    per_stratum = {s: {"n_q1": 0.0, "m_q1": 0.0, "n_q5": 0.0, "m_q5": 0.0,
                        "cycles": set(), "weight_sum": 0.0, "weighted_diff_sum": 0.0}
                   for s in range(5)}
    cells = collections.defaultdict(lambda: {"q1": [], "q5": []})
    for r in records:
        if r["sep_q"] not in (0, 4):
            continue
        w = weight_of(r) if weight_of else 1.0
        if w == 0:
            continue
        key = (r["ts"], r["snr_stratum"])
        side = "q1" if r["sep_q"] == 0 else "q5"
        cells[key][side].append((w, r["missed"], r["n_cycle"]))

    n_cycle_gap_w = 0.0
    n_cycle_gap_wsum = 0.0
    n_contributing_cells = 0

    for (ts, snr_s), sides in cells.items():
        q1, q5 = sides["q1"], sides["q5"]
        if not q1 or not q5:
            continue
        n1 = sum(w for w, _, _ in q1)
        m1 = sum(w for w, missed, _ in q1 if missed)
        n5 = sum(w for w, _, _ in q5)
        m5 = sum(w for w, missed, _ in q5 if missed)
        if n1 <= 0 or n5 <= 0:
            continue
        cell_w = min(n1, n5)
        diff = (m1 / n1) - (m5 / n5)
        st = per_stratum[snr_s]
        st["n_q1"] += n1
        st["m_q1"] += m1
        st["n_q5"] += n5
        st["m_q5"] += m5
        st["cycles"].add(ts)
        st["weight_sum"] += cell_w
        st["weighted_diff_sum"] += cell_w * diff
        n_contributing_cells += 1

        # ROW 0c construction check: n_cycle is a per-cycle constant, so it is IDENTICAL for
        # every Q1 and every Q5 record in this cell (same ts) regardless of weighting -- the
        # gap must be exactly 0.00. Computed explicitly per HK-021 ("draft it by writing the
        # code that evaluates it"), not merely asserted.
        mean_nc_q1 = statistics.mean(nc for _, _, nc in q1)
        mean_nc_q5 = statistics.mean(nc for _, _, nc in q5)
        n_cycle_gap_w += cell_w * (mean_nc_q1 - mean_nc_q5)
        n_cycle_gap_wsum += cell_w

    detail = {}
    qualifying = []
    for s in range(5):
        st = per_stratum[s]
        if fixed_qualifying is not None:
            qualifies = s in fixed_qualifying
        elif apply_power_gate:
            qualifies = (st["n_q1"] >= min_decodes and st["n_q5"] >= min_decodes
                         and len(st["cycles"]) >= min_cycles)
        else:
            qualifies = st["weight_sum"] > 0
        detail[s] = {
            "n_q1": st["n_q1"], "n_q5": st["n_q5"], "n_cycles": len(st["cycles"]),
            "weight": st["weight_sum"], "qualifies": qualifies,
        }
        if qualifies:
            qualifying.append(s)

    total_w = sum(per_stratum[s]["weight_sum"] for s in qualifying)
    total_wd = sum(per_stratum[s]["weighted_diff_sum"] for s in qualifying)
    e_sep = 100.0 * total_wd / total_w if total_w > 0 else float("nan")
    n_cycle_gap = n_cycle_gap_w / n_cycle_gap_wsum if n_cycle_gap_wsum > 0 else float("nan")

    return {
        "E_sep": e_sep, "qualifying_strata": qualifying, "detail": detail,
        "total_weight": total_w, "n_contributing_cells": n_contributing_cells,
        "n_cycle_gap": n_cycle_gap,
    }


# ---- ROW 0b: the mandatory null (within-cycle frequency permutation) --------------------

def null_shuffle_records(all_records_by_cycle, rng):
    """Permutes freq_hz WITHIN each cycle (spec S1.1/S1.3): the cycle's frequency multiset
    is preserved exactly (so n_cycle and the pooled sep distribution are structurally
    unaffected), only the pairing between a decode's (snr, missed) identity and its
    frequency -- and hence its sep and band-edge status -- is destroyed."""
    out = []
    for ts in sorted(all_records_by_cycle):   # deterministic order (HK-017/S7): dict order
        decs = all_records_by_cycle[ts]        # depends on set-iteration hash randomisation
        n = len(decs)
        perm = list(range(n))
        rng.shuffle(perm)
        new_freqs = [decs[i]["freq_hz"] for i in perm]
        for j, orig in enumerate(decs):
            nf = new_freqs[j]
            others = [new_freqs[k] for k in range(n) if k != j]
            sep = min(abs(nf - f) for f in others)
            out.append({
                "ts": ts, "snr": orig["snr"], "missed": orig["missed"],
                "n_cycle": n, "sep": sep, "band_edge": not (BAND_LO_HZ <= nf < BAND_HI_HZ),
            })
    return out


def run_null(all_records_by_cycle, n_shuffle=N_SHUFFLE, seed=SEED):
    rng = random.Random(seed)
    vals = []
    for i in range(n_shuffle):
        shuffled = null_shuffle_records(all_records_by_cycle, rng)
        outcome = outcome_population(shuffled)
        sep_edges = quintile_edges([r["sep"] for r in outcome])
        tag_strata(outcome, sep_edges)
        res = compute_E_sep(outcome)
        vals.append(res["E_sep"])
    mean_e = statistics.mean(v for v in vals if v == v)  # nan-safe mean
    return {"values": vals, "mean": mean_e, "n_shuffle": n_shuffle}


# ---- bootstrap: cycle-clustered (primary) and frequency-clustered (robustness) ----------

def cycle_clustered_bootstrap(outcome, fixed_qualifying, n_boot=N_BOOT, seed=SEED):
    by_cycle = collections.defaultdict(list)
    for r in outcome:
        by_cycle[r["ts"]].append(r)
    cycles = sorted(by_cycle)   # deterministic order -- see null_shuffle_records's note
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        draw = collections.Counter(rng.choices(cycles, k=len(cycles)))

        def w(r, draw=draw):
            return float(draw.get(r["ts"], 0))

        res = compute_E_sep(outcome, weight_of=w, fixed_qualifying=fixed_qualifying)
        vals.append(res["E_sep"])
    return vals


def freq_clustered_bootstrap(outcome, fixed_qualifying, n_boot=N_BOOT, seed=SEED):
    """Frequency-clustered robustness check (spec S2, T2a convention -- a station's
    frequency is near-fixed, so records at the same exact freq_hz, even across different
    cycles, are not independent). Groups outcome records by exact freq_hz, resamples those
    clusters with replacement, and reweights each record by its own frequency's draw
    multiplicity -- sep/n_cycle/quintile membership stay fixed at their point-estimate
    values (same reasoning as fixing sep-quintile edges: the bootstrap targets sampling
    noise in which stations appear, not re-derivation noise)."""
    by_freq = collections.defaultdict(list)
    for r in outcome:
        by_freq[r["freq_hz"]].append(r)
    freqs = sorted(by_freq)   # deterministic order -- see null_shuffle_records's note
    rng = random.Random(seed + 1)
    vals = []
    for _ in range(n_boot):
        draw = collections.Counter(rng.choices(freqs, k=len(freqs)))
        mult_by_freq = draw

        def w(r, mult_by_freq=mult_by_freq):
            return float(mult_by_freq.get(r["freq_hz"], 0))

        res = compute_E_sep(outcome, weight_of=w, fixed_qualifying=fixed_qualifying)
        vals.append(res["E_sep"])
    return vals


def se_ci(vals):
    v = sorted(x for x in vals if x == x)
    if len(v) < 2:
        return float("nan"), (float("nan"), float("nan"))
    se = statistics.pstdev(v)
    lo = v[max(0, min(len(v) - 1, int(round(0.025 * (len(v) - 1)))))]
    hi = v[max(0, min(len(v) - 1, int(round(0.975 * (len(v) - 1)))))]
    return se, (lo, hi)


# ---- gate --------------------------------------------------------------------------------

def x4_gate(e_sep, se_cycle, ci_cycle):
    lo, hi = ci_cycle
    if e_sep >= GATE_ROW1_PP and lo > 0:
        return "ROW 1"
    if abs(e_sep) < GATE_ROW2_PP and se_cycle <= GATE_ROW2_SE_PP:
        return "ROW 2"
    if e_sep <= -GATE_ROW1_PP and hi < 0:
        return "ROW 3"
    return "ROW 4"


def main():
    result = {"spec": "2026-08-10-1808-architect-to-qa-spec-x4-s1-reopened-within-cycle-spectral-locality.md"}
    print("=" * 88)
    print("X4 -- within-cycle spectral locality (S.1 reopened, attempt 3, LAST)")
    print("=" * 88)

    a, o, ref_raw = load_ref()
    print("\nREF (raw A n B, 20m weekend corpus): %d" % len(ref_raw))
    row0a = (len(ref_raw) == REF_EXPECTED)
    print(">>> ROW 0a: %s (expected %d) <<<" % ("PASS" if row0a else "VOID", REF_EXPECTED))
    result["row0a"] = {"ref": len(ref_raw), "expected": REF_EXPECTED, "pass": row0a}
    if not row0a:
        result["final_row"] = "ROW 0a"
        write_and_exit(result, 1)
        return 1

    records, n_excl_single = build_records(a, o, ref_raw)
    by_cycle_all = collections.defaultdict(list)
    for k in sorted(ref_raw):   # deterministic order -- see build_records's docstring
        ts, msg = k
        snr, freq_hz = a[k]
        by_cycle_all[ts].append({"ts": ts, "snr": snr, "freq_hz": freq_hz, "missed": k not in o})
    # restrict the null's cycle groups to the same >=2-decode cycles used everywhere else
    by_cycle_multi = {ts: decs for ts, decs in by_cycle_all.items() if len(decs) >= 2}

    outcome = outcome_population(records)
    n_band_edge = sum(1 for r in records if r["band_edge"])
    print("\nUsable decode-records (n_cycle>=2, sep defined): %d" % len(records))
    print("Excluded (single-decode cycles): %d" % n_excl_single)
    print("Band-edge (outside [%d,%d) Hz, excluded from OUTCOME tally, kept as neighbours): %d"
          % (BAND_LO_HZ, BAND_HI_HZ, n_band_edge))
    print("Outcome (analysed) population: %d" % len(outcome))

    # ROW 0g cross-check: recompute the band-edge count via an independent direct tally.
    n_band_edge_direct = sum(1 for k in ref_raw if not (BAND_LO_HZ <= a[k][1] < BAND_HI_HZ))
    # direct tally is over ALL ref_raw (incl. single-decode cycles); records-based count
    # excludes single-decode cycles already, so compare against the matching subset.
    n_band_edge_direct_multi = sum(
        1 for ts, decs in by_cycle_multi.items() for d in decs
        if not (BAND_LO_HZ <= d["freq_hz"] < BAND_HI_HZ)
    )
    row0g = (n_band_edge == n_band_edge_direct_multi)
    print("\nROW 0g band-edge cross-check: from records=%d, independent direct tally=%d -> %s"
          % (n_band_edge, n_band_edge_direct_multi, "PASS" if row0g else "VOID"))
    result["row0g"] = {"n_band_edge": n_band_edge, "n_band_edge_direct": n_band_edge_direct_multi,
                        "n_band_edge_all_cycles": n_band_edge_direct, "pass": row0g}

    # ROW 0d: distinct sep values
    sep_vals = [r["sep"] for r in outcome]
    n_distinct_sep = len(set(sep_vals))
    row0d = n_distinct_sep >= MIN_DISTINCT_SEP
    print("\nROW 0d -- distinct sep values in outcome population: %d (bar >= %d) -> %s"
          % (n_distinct_sep, MIN_DISTINCT_SEP, "PASS" if row0d else "STOP for re-registration"))
    result["row0d"] = {"n_distinct_sep": n_distinct_sep, "bar": MIN_DISTINCT_SEP, "pass": row0d}
    if not row0g or not row0d:
        result["final_row"] = "ROW 0g" if not row0g else "ROW 0d"
        write_and_exit(result, 1)
        return 1

    sep_edges = quintile_edges(sep_vals)
    print("Global sep quintile edges (Hz): %s" % sep_edges)
    tag_strata(outcome, sep_edges)
    result["sep_edges"] = sep_edges
    result["sep_summary"] = {
        "n": len(sep_vals), "min": min(sep_vals), "max": max(sep_vals),
        "p10": sorted(sep_vals)[int(0.10 * (len(sep_vals) - 1))],
        "p50": sorted(sep_vals)[int(0.50 * (len(sep_vals) - 1))],
        "p90": sorted(sep_vals)[int(0.90 * (len(sep_vals) - 1))],
    }

    # point estimate, with the ROW 0e power gate applied
    point = compute_E_sep(outcome)
    print("\nPer-SNR-stratum (L1) support:")
    for s in range(5):
        d = point["detail"][s]
        print("  stratum %d: n_Q1=%.0f n_Q5=%.0f cycles=%d weight=%.1f -> %s"
              % (s, d["n_q1"], d["n_q5"], d["n_cycles"], d["weight"],
                 "QUALIFIES" if d["qualifies"] else "UNDERPOWERED"))
    row0e = len(point["qualifying_strata"]) >= 1
    print("\nROW 0e -- qualifying strata: %d/5 -> %s"
          % (len(point["qualifying_strata"]), "PASS (>=1 qualifies)" if row0e else "VOID -- no stratum powered"))
    result["row0e"] = {"qualifying_strata": point["qualifying_strata"], "detail": point["detail"],
                        "pass": row0e}
    print("\nROW 0c -- mean n_cycle gap (Q1 side vs Q5 side), pooled over contributing cells: %.6f"
          % point["n_cycle_gap"])
    row0c = abs(round(point["n_cycle_gap"], 2)) == 0.00
    print(">>> ROW 0c: %s (bar == 0.00 exactly) <<<" % ("PASS" if row0c else "VOID"))
    result["row0c"] = {"n_cycle_gap": point["n_cycle_gap"], "pass": row0c}
    if not row0c or not row0e:
        result["final_row"] = "ROW 0c" if not row0c else "ROW 0e"
        write_and_exit(result, 1)
        return 1

    print("\nPoint estimate E_sep = %.3f pp  (n_contributing_cells=%d, total_weight=%.1f)"
          % (point["E_sep"], point["n_contributing_cells"], point["total_weight"]))
    result["E_sep_point"] = point["E_sep"]
    result["n_contributing_cells"] = point["n_contributing_cells"]

    # ROW 0b: mandatory null, run on the SAME point-estimate qualifying-stratum machinery
    # (each shuffle re-derives its own sep edges/strata, per the null's own pipeline)
    print("\nRunning ROW 0b mandatory null (%d within-cycle frequency-permutation shuffles)..."
          % N_SHUFFLE)
    null = run_null(by_cycle_multi)
    print("  shuffle E_sep values: %s" % ["%.3f" % v for v in null["values"]])
    print("  mean = %.3f pp (bar |mean| <= %.1f pp)" % (null["mean"], NULL_BAR_PP))
    row0b = abs(null["mean"]) <= NULL_BAR_PP
    print(">>> ROW 0b: %s <<<" % ("PASS" if row0b else "VOID -- contaminated estimator"))
    result["row0b"] = {"null_values": null["values"], "null_mean": null["mean"],
                        "bar": NULL_BAR_PP, "pass": row0b}
    if not row0b:
        result["final_row"] = "ROW 0b"
        write_and_exit(result, 1)
        return 1

    # bootstraps
    print("\nRunning cycle-clustered bootstrap (primary, %d draws, seed=%d)..." % (N_BOOT, SEED))
    cyc_vals = cycle_clustered_bootstrap(outcome, point["qualifying_strata"])
    se_cyc, ci_cyc = se_ci(cyc_vals)
    print("  SE=%.3f pp  95%% CI=[%+.3f, %+.3f] pp" % (se_cyc, ci_cyc[0], ci_cyc[1]))

    print("Running frequency-clustered bootstrap (robustness, %d draws, seed=%d)..."
          % (N_BOOT, SEED + 1))
    freq_vals = freq_clustered_bootstrap(outcome, point["qualifying_strata"])
    se_freq, ci_freq = se_ci(freq_vals)
    print("  SE=%.3f pp  95%% CI=[%+.3f, %+.3f] pp" % (se_freq, ci_freq[0], ci_freq[1]))

    disagree_sign = (ci_cyc[0] > 0 and ci_freq[1] < 0) or (ci_cyc[1] < 0 and ci_freq[0] > 0)
    ratio = (max(se_cyc, se_freq) / min(se_cyc, se_freq)) if min(se_cyc, se_freq) > 0 else float("inf")
    disagree = disagree_sign or ratio > 2.0
    print("\nRobustness check: SE ratio = %.2f (bar <= 2.0), sign disagreement = %s -> %s"
          % (ratio, disagree_sign, "FLAG -- do not read the row" if disagree else "OK, consistent"))
    result["bootstrap"] = {
        "cycle_clustered": {"se": se_cyc, "ci95": list(ci_cyc), "n_boot": len(cyc_vals)},
        "freq_clustered": {"se": se_freq, "ci95": list(ci_freq), "n_boot": len(freq_vals)},
        "se_ratio": ratio, "sign_disagree": disagree_sign, "flagged": disagree,
    }

    row0f = se_cyc <= POWER_BAR_PP
    print("\nROW 0f -- SE(E_sep), cycle-clustered: %.3f pp (bar <= %.1f) -> %s"
          % (se_cyc, POWER_BAR_PP, "PASS" if row0f else "VOID -- underpowered"))
    result["row0f"] = {"se_cycle": se_cyc, "bar": POWER_BAR_PP, "pass": row0f}
    if not row0f:
        result["final_row"] = "ROW 0f"
        write_and_exit(result, 1)
        return 1

    if disagree:
        result["final_row"] = "FLAGGED -- clustering disagreement, row not read"
        write_and_exit(result, 0)
        return 0

    gate_row = x4_gate(point["E_sep"], se_cyc, ci_cyc)
    print("\n" + "=" * 88)
    print(">>> GATE: %s <<<  (E_sep=%.3f pp, SE=%.3f, 95%% CI=[%+.3f, %+.3f])"
          % (gate_row, point["E_sep"], se_cyc, ci_cyc[0], ci_cyc[1]))
    print("=" * 88)
    result["final_row"] = gate_row
    result["E_sep"] = point["E_sep"]
    result["se_cycle"] = se_cyc
    result["ci95_cycle"] = list(ci_cyc)
    write_and_exit(result, 0)
    return 0


def write_and_exit(result, code):
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x4_result.json")
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    print("\nWrote %s" % out_path)


if __name__ == "__main__":
    raise SystemExit(main())
