#!/usr/bin/env python3
"""X5 -- which dependence structure governs E_sep? (X4's unresolved robustness flag)

Spec: qa/cycleframer-alignment-replay/2026-08-11-1723-architect-to-qa-spec-x5-clustering-dependence-structure.md
Pre-registered gate per HK-021; rows evaluated in strict order (see main()).
Authorisation: Captain ruled 2026-08-11 -- do NOT retire spectral locality; run the fourth
(and per the spec, LAST) registration. Re-arms X4's retirement rule with the gap closed (spec S4.1).

Question X4 left open: E_sep's point estimate (+46.039 pp) is large and passed every ROW 0
condition, but its cycle-clustered and frequency-clustered bootstrap SEs disagreed by 2.102x
against a 2.0x bar -- X4's own precondition stopped the arm before the gate was ever evaluated.
X5 does not re-read X4's numbers under a new metric; it computes a genuinely new quantity
(a two-way/multiway Cameron-Gelbach-Miller cluster-robust SE, crossing the cycle and frequency
dimensions) and evaluates X4's gate -- verbatim, not one threshold moved -- under it.

Reuse, not rewrite (HK-004, spec S2.4): every population-construction, point-estimate and
single-way-bootstrap function is IMPORTED from x4_spectral_locality.py, not copied. This file
adds only the intersection-clustered bootstrap, the CGM combination + degeneracy handling, the
connected-component diagnostic, and the coarsened frequency-block diagnostic -- all genuinely
new to X5.

No src/ change. No capture. No decoder replay. Pure re-analysis of ALL.TXT already on disk.
NFR-021: no callsign or message text appears in this file's output; only counts, rates,
frequencies and cycle timestamps (all inherited from x4_spectral_locality.py's population).
"""
from __future__ import annotations

import collections
import io
import json
import math
import os
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x4_spectral_locality as x4  # noqa: E402 -- reuse, not rewrite (spec S2.4/HK-004)

SEED = x4.SEED               # 20260810 -- X4's seed, unchanged (spec S2.3)
N_BOOT = x4.N_BOOT            # 1000 draws per bootstrap (spec S2.3)
REF_EXPECTED = x4.REF_EXPECTED  # 69222

E_SEP_EXPECTED_3DP = 46.039     # spec S0.1 -- X4's published point estimate, ROW 0a bar
POWER_BAR_PP = 2.0              # spec S3, ROW 0f -- SE_2way bar (X4's ROW 0f bar, unchanged)
MIN_MEAN_DECODES_PER_INTERSECTION = 1.05  # spec S3.2, ROW 0d
CC_CLOSE_BAR = 0.95             # spec S3.3, ROW 0g -- closes the connected-component route
BLOCK_HZ = 50.0                 # spec S5.1 -- coarsened frequency-block diagnostic width

# spec S0.1 -- X4's published values that X5's ROW 0c must reproduce EXACTLY on import, to
# prove the imported population is X4's and has not drifted.
X4_PUBLISHED = {
    "row0b_null_mean_3dp": -0.248,
    "row0c_n_cycle_gap_2dp": 0.00,
    "row0d_n_distinct_sep": 540,
    "row0e_n_qualifying_strata": 5,
    "row0g_n_band_edge": 868,
}


# ---- new to X5: intersection-clustered bootstrap (spec S2.1) ---------------------------

def intersection_clustered_bootstrap(outcome, fixed_qualifying, n_boot=N_BOOT, seed=SEED + 2):
    """Clusters on the distinct (cycle, freq_hz) pair -- the CGM intersection term. Same
    reweight-by-draw-multiplicity mechanism as X4's cycle_clustered_bootstrap /
    freq_clustered_bootstrap, over `x4.compute_E_sep`'s existing weight_of hook (spec S2.1/S2.4)."""
    by_pair = collections.defaultdict(list)
    for r in outcome:
        by_pair[(r["ts"], r["freq_hz"])].append(r)
    pairs = sorted(by_pair)   # deterministic order -- X4 S1.1's lesson, applied on construction
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        draw = collections.Counter(rng.choices(pairs, k=len(pairs)))

        def w(r, draw=draw):
            return float(draw.get((r["ts"], r["freq_hz"]), 0))

        res = x4.compute_E_sep(outcome, weight_of=w, fixed_qualifying=fixed_qualifying)
        vals.append(res["E_sep"])
    return vals, by_pair


# ---- new to X5: coarsened 50 Hz frequency-block bootstrap (spec S5.1, non-gating) -------

def block_clustered_bootstrap(outcome, fixed_qualifying, n_boot=N_BOOT, seed=SEED + 3,
                               block_hz=BLOCK_HZ):
    """Deliberately the direction that could kill the arm (spec S5.1): clusters on 50 Hz
    frequency blocks (FT8's occupied-bandwidth scale, close to X4's own median sep of 40 Hz).
    Reported alongside, never gating -- the 50 Hz width is an invented parameter, not one the
    data supplied (HK-021(d))."""
    by_block = collections.defaultdict(list)
    for r in outcome:
        by_block[math.floor(r["freq_hz"] / block_hz)].append(r)
    blocks = sorted(by_block)
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        draw = collections.Counter(rng.choices(blocks, k=len(blocks)))

        def w(r, draw=draw, block_hz=block_hz):
            return float(draw.get(math.floor(r["freq_hz"] / block_hz), 0))

        res = x4.compute_E_sep(outcome, weight_of=w, fixed_qualifying=fixed_qualifying)
        vals.append(res["E_sep"])
    return vals, by_block


# ---- new to X5: CGM two-way combination + pre-registered degeneracy handling (spec S2.1/2.2) --

def resolve_se_2way(v_cycle, v_freq, v_intersection, se_cycle, se_freq):
    """spec S2.2, verbatim: V_2way = V_cycle + V_freq - V_intersection; two conservative
    fallbacks, neither may reduce SE below the marginals."""
    v_2way = v_cycle + v_freq - v_intersection
    if v_2way <= 0:
        return max(se_cycle, se_freq), v_2way, "CGM_DEGENERATE_NONPOSITIVE"
    se = math.sqrt(v_2way)
    if se < max(se_cycle, se_freq):
        return max(se_cycle, se_freq), v_2way, "CGM_DOMINATED"
    return se, v_2way, "CGM_OK"


# ---- new to X5: connected-component degeneracy diagnostic (spec S3.3) ------------------

class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def connected_component_share(outcome):
    """Bipartite cycle<->frequency graph over the outcome population: a decode is an edge
    between its cycle node and its frequency node. Computes the largest component's share of
    decodes (spec S3.3) -- killed by computation, not by argument."""
    uf = _UnionFind()
    for r in outcome:
        uf.union(("c", r["ts"]), ("f", r["freq_hz"]))
    comp_decodes = collections.Counter()
    for r in outcome:
        comp_decodes[uf.find(("c", r["ts"]))] += 1
    total = len(outcome)
    largest = max(comp_decodes.values()) if comp_decodes else 0
    n_cycles = len({r["ts"] for r in outcome})
    n_freqs = len({r["freq_hz"] for r in outcome})
    return {
        "n_components": len(comp_decodes),
        "largest_component_decodes": largest,
        "total_decodes": total,
        "share": (largest / total) if total else float("nan"),
        "n_cycles": n_cycles,
        "n_distinct_freqs": n_freqs,
    }


def main():
    result = {"spec": "2026-08-11-1723-architect-to-qa-spec-x5-clustering-dependence-structure.md"}
    print("=" * 88)
    print("X5 -- which dependence structure governs E_sep? (fourth registration, LAST)")
    print("=" * 88)

    # ---- rebuild X4's exact population, via X4's own functions, unmodified -------------
    a, o, ref_raw = x4.load_ref()
    records, n_excl_single = x4.build_records(a, o, ref_raw)
    outcome = x4.outcome_population(records)
    sep_vals = [r["sep"] for r in outcome]
    sep_edges = x4.quintile_edges(sep_vals)
    x4.tag_strata(outcome, sep_edges)
    point = x4.compute_E_sep(outcome)
    fixed_qualifying = point["qualifying_strata"]

    print("\nREF (raw A n B, 20m weekend corpus): %d (X4 expects %d)" % (len(ref_raw), REF_EXPECTED))
    print("Outcome (analysed) population: %d" % len(outcome))
    print("E_sep point estimate: %.6f pp (X4 published +%.3f pp)" % (point["E_sep"], E_SEP_EXPECTED_3DP))

    # ---- ROW 0a: E_sep reproduces X4's point estimate, REF reproduces X4's count -------
    row0a_ref = (len(ref_raw) == REF_EXPECTED)
    row0a_esep = (round(point["E_sep"], 3) == E_SEP_EXPECTED_3DP)
    row0a = row0a_ref and row0a_esep
    print("\n>>> ROW 0a: %s (REF %d==%d: %s; E_sep %.3f==%.3f: %s) <<<"
          % ("PASS" if row0a else "VOID", len(ref_raw), REF_EXPECTED, row0a_ref,
             round(point["E_sep"], 3), E_SEP_EXPECTED_3DP, row0a_esep))
    result["row0a"] = {"ref": len(ref_raw), "ref_expected": REF_EXPECTED, "ref_pass": row0a_ref,
                        "e_sep": point["E_sep"], "e_sep_3dp": round(point["E_sep"], 3),
                        "e_sep_expected_3dp": E_SEP_EXPECTED_3DP, "e_sep_pass": row0a_esep,
                        "pass": row0a}
    if not row0a:
        result["final_row"] = "ROW 0a"
        write_and_exit(result, 1)
        return 1

    # ---- ROW 0c: X4's own ROW 0b/0c/0d/0e/0g re-assert unchanged on import -------------
    # (X5's ROW 0b -- determinism -- is verified externally across two full process runs,
    # diffed mechanically; it is not a within-run computation. See the accompanying report.)
    by_cycle_all = collections.defaultdict(list)
    for k in sorted(ref_raw):
        ts, msg = k
        snr, freq_hz = a[k]
        by_cycle_all[ts].append({"ts": ts, "snr": snr, "freq_hz": freq_hz, "missed": k not in o})
    by_cycle_multi = {ts: decs for ts, decs in by_cycle_all.items() if len(decs) >= 2}

    n_band_edge = sum(1 for r in records if r["band_edge"])
    n_distinct_sep = len(set(sep_vals))
    n_qualifying = len(fixed_qualifying)
    print("\nRunning ROW 0c reassertion: X4's ROW 0b mandatory null (%d shuffles)..." % x4.N_SHUFFLE)
    null = x4.run_null(by_cycle_multi)

    checks = {
        "row0b_null_mean_3dp": {"value": round(null["mean"], 3),
                                 "expected": X4_PUBLISHED["row0b_null_mean_3dp"]},
        "row0c_n_cycle_gap_2dp": {"value": abs(round(point["n_cycle_gap"], 2)),
                                   "expected": X4_PUBLISHED["row0c_n_cycle_gap_2dp"]},
        "row0d_n_distinct_sep": {"value": n_distinct_sep,
                                  "expected": X4_PUBLISHED["row0d_n_distinct_sep"]},
        "row0e_n_qualifying_strata": {"value": n_qualifying,
                                       "expected": X4_PUBLISHED["row0e_n_qualifying_strata"]},
        "row0g_n_band_edge": {"value": n_band_edge,
                               "expected": X4_PUBLISHED["row0g_n_band_edge"]},
    }
    for name, c in checks.items():
        c["pass"] = (c["value"] == c["expected"])
    row0c = all(c["pass"] for c in checks.values())
    print("\nROW 0c reassertion (X4's published values, spec S0.1):")
    for name, c in checks.items():
        print("  %-28s measured=%-10s expected=%-10s -> %s"
              % (name, c["value"], c["expected"], "PASS" if c["pass"] else "MISMATCH"))
    print(">>> ROW 0c: %s <<<" % ("PASS" if row0c else "VOID -- imported population is not X4's"))
    result["row0c"] = {"checks": checks, "pass": row0c}
    if not row0c:
        result["final_row"] = "ROW 0c"
        write_and_exit(result, 1)
        return 1

    # ---- ROW 0d: intersection clusters counted, mean decodes/cluster (spec S3.2) -------
    # Computed first, before the bootstraps (spec S3.2) -- cheap, and decides whether the
    # rest of the arm means anything.
    by_pair_counts = collections.defaultdict(int)
    for r in outcome:
        by_pair_counts[(r["ts"], r["freq_hz"])] += 1
    n_intersection = len(by_pair_counts)
    counts = list(by_pair_counts.values())
    mean_decodes_per_pair = len(outcome) / n_intersection if n_intersection else float("nan")
    n_singleton = sum(1 for c in counts if c == 1)
    row0d = mean_decodes_per_pair >= MIN_MEAN_DECODES_PER_INTERSECTION
    print("\nROW 0d -- intersection (cycle, freq_hz) clusters: %d, mean decodes/cluster=%.4f "
          "(min=%d max=%d singleton_clusters=%d/%d) (bar >= %.2f) -> %s"
          % (n_intersection, mean_decodes_per_pair, min(counts), max(counts), n_singleton,
             n_intersection, MIN_MEAN_DECODES_PER_INTERSECTION,
             "PASS" if row0d else "STOP FOR RE-REGISTRATION"))
    result["row0d"] = {"n_intersection_clusters": n_intersection,
                        "mean_decodes_per_cluster": mean_decodes_per_pair,
                        "min_decodes_per_cluster": min(counts), "max_decodes_per_cluster": max(counts),
                        "n_singleton_clusters": n_singleton, "bar": MIN_MEAN_DECODES_PER_INTERSECTION,
                        "pass": row0d}
    if not row0d:
        result["final_row"] = "ROW 0d -- STOP FOR RE-REGISTRATION"
        write_and_exit(result, 1)
        return 1

    # ---- the three bootstraps (spec S2.1/S2.3) ------------------------------------------
    print("\nRunning cycle-clustered bootstrap (%d draws, seed=%d)..." % (N_BOOT, SEED))
    cyc_vals = x4.cycle_clustered_bootstrap(outcome, fixed_qualifying, n_boot=N_BOOT, seed=SEED)
    se_cyc, ci_cyc = x4.se_ci(cyc_vals)
    print("  SE=%.4f pp  95%% CI=[%+.3f, %+.3f] pp" % (se_cyc, ci_cyc[0], ci_cyc[1]))

    print("Running frequency-clustered bootstrap (%d draws, seed=%d)..." % (N_BOOT, SEED + 1))
    freq_vals = x4.freq_clustered_bootstrap(outcome, fixed_qualifying, n_boot=N_BOOT, seed=SEED)
    se_freq, ci_freq = x4.se_ci(freq_vals)
    print("  SE=%.4f pp  95%% CI=[%+.3f, %+.3f] pp" % (se_freq, ci_freq[0], ci_freq[1]))

    print("Running intersection-clustered bootstrap (%d draws, seed=%d)..." % (N_BOOT, SEED + 2))
    inter_vals, by_pair = intersection_clustered_bootstrap(outcome, fixed_qualifying,
                                                             n_boot=N_BOOT, seed=SEED + 2)
    se_inter, ci_inter = x4.se_ci(inter_vals)
    print("  SE=%.4f pp  95%% CI=[%+.3f, %+.3f] pp" % (se_inter, ci_inter[0], ci_inter[1]))

    v_cycle, v_freq, v_intersection = se_cyc ** 2, se_freq ** 2, se_inter ** 2
    se_2way, v_2way, branch = resolve_se_2way(v_cycle, v_freq, v_intersection, se_cyc, se_freq)
    print("\nCGM two-way combination: V_cycle=%.5f V_freq=%.5f V_intersection=%.5f "
          "-> V_2way=%.5f -> SE_2way=%.4f pp  (branch=%s)"
          % (v_cycle, v_freq, v_intersection, v_2way, se_2way, branch))
    result["bootstrap"] = {
        "cycle_clustered": {"se": se_cyc, "ci95": list(ci_cyc), "n_boot": len(cyc_vals)},
        "freq_clustered": {"se": se_freq, "ci95": list(ci_freq), "n_boot": len(freq_vals)},
        "intersection_clustered": {"se": se_inter, "ci95": list(ci_inter), "n_boot": len(inter_vals)},
        "v_cycle": v_cycle, "v_freq": v_freq, "v_intersection": v_intersection,
        "v_2way": v_2way, "se_2way": se_2way,
    }

    # ---- ROW 0e: se_2way_branch recorded (spec S3, S2.2) --------------------------------
    row0e = branch in ("CGM_OK", "CGM_DOMINATED", "CGM_DEGENERATE_NONPOSITIVE")
    print("\nROW 0e -- se_2way_branch recorded: %s -> %s" % (branch, "PASS" if row0e else "VOID"))
    result["row0e"] = {"se_2way_branch": branch, "pass": row0e}
    if not row0e:
        result["final_row"] = "ROW 0e"
        write_and_exit(result, 1)
        return 1

    # ---- ROW 0f: power -- SE_2way <= 2.0 pp (spec S3, TERMINAL per S3.4) ---------------
    row0f = se_2way <= POWER_BAR_PP
    print("\n>>> ROW 0f -- power: SE_2way=%.4f pp (bar <= %.1f) -> %s <<<"
          % (se_2way, POWER_BAR_PP, "PASS" if row0f else "UNDERPOWERED -- TERMINAL, no row read"))
    result["row0f"] = {"se_2way": se_2way, "bar": POWER_BAR_PP, "pass": row0f}
    if not row0f:
        result["final_row"] = "ROW 0f -- UNDERPOWERED, TERMINAL (spec S3.4); retirement fires (S4.1)"
        write_and_exit(result, 1)
        return 1

    # ---- ROW 0g: connected-component degeneracy, non-gating unless < 95% (spec S3.3) ---
    cc = connected_component_share(outcome)
    row0g_closed = cc["share"] >= CC_CLOSE_BAR
    print("\nROW 0g -- connected-component diagnostic: %d components, largest holds %d/%d "
          "decodes (%.2f%%) over %d cycles / %d distinct freqs -> %s"
          % (cc["n_components"], cc["largest_component_decodes"], cc["total_decodes"],
             100.0 * cc["share"], cc["n_cycles"], cc["n_distinct_freqs"],
             "CLOSED (route formally closed)" if row0g_closed
             else "SURPRISE -- STOP AND ESCALATE (spec S3.3)"))
    result["row0g"] = {**cc, "bar": CC_CLOSE_BAR, "route_closed": row0g_closed}
    if not row0g_closed:
        result["final_row"] = "ROW 0g -- ESCALATE (connected-component share below 95%, spec S3.3)"
        write_and_exit(result, 1)
        return 1

    # ---- diagnostics, never gating (spec S5) --------------------------------------------
    print("\nRunning coarsened 50 Hz frequency-block bootstrap diagnostic (%d draws, seed=%d)..."
          % (N_BOOT, SEED + 3))
    block_vals, by_block = block_clustered_bootstrap(outcome, fixed_qualifying,
                                                       n_boot=N_BOOT, seed=SEED + 3)
    se_block, ci_block = x4.se_ci(block_vals)
    print("  SE_block=%.4f pp  95%% CI=[%+.3f, %+.3f] pp  (%d blocks)"
          % (se_block, ci_block[0], ci_block[1], len(by_block)))
    result["diagnostics"] = {
        "se_block": se_block, "ci95_block": list(ci_block), "n_blocks": len(by_block),
        "block_hz": BLOCK_HZ,
        "n_intersection_clusters": n_intersection,
        "mean_decodes_per_intersection_cluster": mean_decodes_per_pair,
    }

    # ---- gate -- X4's, VERBATIM, se_E := SE_2way (spec S4) ------------------------------
    lo = point["E_sep"] - 1.96 * se_2way
    hi = point["E_sep"] + 1.96 * se_2way
    gate_row = x4.x4_gate(point["E_sep"], se_2way, (lo, hi))
    print("\n" + "=" * 88)
    print(">>> GATE: %s <<<  (E_sep=%.3f pp, SE_2way=%.4f, 95%% CI=[%+.3f, %+.3f])"
          % (gate_row, point["E_sep"], se_2way, lo, hi))
    print("=" * 88)
    result["final_row"] = gate_row
    result["E_sep"] = point["E_sep"]
    result["se_2way"] = se_2way
    result["ci95_2way"] = [lo, hi]
    result["se_2way_branch"] = branch
    write_and_exit(result, 0)
    return 0


def write_and_exit(result, code):
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "x5_result.json")
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    print("\nWrote %s" % out_path)


if __name__ == "__main__":
    raise SystemExit(main())
