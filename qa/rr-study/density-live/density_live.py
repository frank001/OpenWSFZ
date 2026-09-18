#!/usr/bin/env python3
"""DENSITY-LIVE -- do our live misses concentrate in the near-neighbour
geometry the F-NBR-A bench proved causal?

Spec: qa/rr-study/2026-09-18-1339-architect-to-qa-spec-density-live-concentration.md
(branch arch/density, commit 517db622). Captain-cleared, ONE confirmatory
test; spectral-locality's exploratory question stays closed (spec Sec.0).

Imports live-gap-now's corpus/analyse/matcher VERBATIM (spec Sec.6 item 1).
Deliverable 1 hard gate: Sec.2.1's REF-only class table must reproduce
EXACTLY before any TEST (OpenWSFZ) decode is loaded. That gate lives in
main() as an explicit assert-and-stop, not a warning.

NFR-021: classify() reads snr/freq fields only. Message text is touched only
inside matcher.load_all()/recovery() (already-audited, verbatim-reused code)
and is never re-emitted here. All outputs of this script are counts, rates,
and CIs.

Usage: python qa/rr-study/density-live/density_live.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LIVE_GAP_NOW_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "live-gap-now")
sys.path.insert(0, LIVE_GAP_NOW_DIR)

import corpus  # noqa: E402  (verbatim reuse)
import matcher  # noqa: E402  (verbatim reuse)
import analyse  # noqa: E402  (verbatim reuse -- load_ref_c2, load_live_c2_openwsfz)

OUT_DIR = os.path.join(HERE, "results")
RESULT_JSON = os.path.join(OUT_DIR, "density_live_result.json")

N_BOOT = 2000
SEED = 20260918  # spec Sec.3, distinct from live-gap-now's own 20260912

BAR_PRIMARY = 0.170          # = 1.0 pp attributable cost (spec Sec.3)
BAR_0A = 0.05                # placebo-null tolerance (spec Sec.4.1)
MIN_CELL_N = 20              # spec Sec.3
MAX_DROP_FRAC = 0.05         # ROW 0b (spec Sec.4.1)
A1_TARGET = 61.09            # ROW 0c reproduction target, R_wild, 2dp (spec Sec.4.1)

# --- Sec.2.1's REF-only class table, reproduced by the Architect before this
# script existed. This is the fixed target Deliverable 1 checks against.
EXPECTED_TABLE = {
    "EXPOSED": 5363,
    "PL": 7476,
    "PF": 10781,
    "TRANSITION": 7429,
    "CLEAR": 28310,
    "GAP": 598,
    "PL_TRANS_STRONG": 282,
}
EXPECTED_TOTAL = 60239


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Sec.2: classify(), reproduced verbatim from the spec's own code block.
# ---------------------------------------------------------------------------
def classify(v_snr, v_f, neighbours):
    """neighbours: [(snr, f), ...] -- same cycle, v excluded. Returns one of
    EXPOSED / GAP / PL / PL_TRANS_STRONG / TRANSITION / PF / CLEAR."""
    near = [s - v_snr for s, f in neighbours if abs(f - v_f) <= 18]
    trans = [s - v_snr for s, f in neighbours if 18 < abs(f - v_f) <= 31]
    far = [s - v_snr for s, f in neighbours if 50 <= abs(f - v_f) <= 100]
    if near:
        m = max(near)
        if m >= 0:
            return "EXPOSED"
        if m >= -2:
            return "GAP"
        return "PL" if not trans or max(trans) < 0 else "PL_TRANS_STRONG"
    if trans:
        return "TRANSITION"
    if far and max(far) >= 0:
        return "PF"
    return "CLEAR"


def snr_band5(snr):
    if snr < -6:
        return "-10..-6"
    if snr < 0:
        return "-5..-1"
    if snr < 5:
        return "0..4"
    if snr < 10:
        return "5..9"
    return ">=10"


def build_by_cycle(ref_all: dict):
    by_cycle = {}
    for (ts, msg), (snr, f) in ref_all.items():
        by_cycle.setdefault(ts, []).append((snr, f, msg))
    return by_cycle


def classify_population(ref_all: dict, by_cycle: dict):
    """ref_all: {(ts,msg): (snr, freq_hz)} -- FULL C2 REF (91,046 rows, spec
    Sec.1). Population = ref_all rows with snr >= -10 (spec Sec.1, 60,239).
    Neighbour pool for every row is the FULL ref_all cycle membership (not
    restricted to the population), since Sec.2's GAP/PL/PF predicates make no
    population restriction on neighbours and a sub-(-10dB) neighbour can still
    drive a GAP/PL read at the population boundary.

    Returns classes: {key: class_name}."""
    classes = {}
    for (ts, msg), (snr, f) in ref_all.items():
        if snr < -10:
            continue  # not in population -- not classified
        neighbours = [(s, nf) for (s, nf, m) in by_cycle[ts] if not (s == snr and nf == f and m == msg)]
        classes[(ts, msg)] = classify(snr, f, neighbours)
    return classes


def build_class_table(ref_all: dict, classes: dict):
    counts = {c: 0 for c in EXPECTED_TABLE}
    bands = {c: {b: 0 for b in ("-10..-6", "-5..-1", "0..4", "5..9", ">=10")} for c in EXPECTED_TABLE}
    for k, c in classes.items():
        counts[c] = counts.get(c, 0) + 1
        snr = ref_all[k][0]
        if c in bands:
            bands[c][snr_band5(snr)] += 1
    return counts, bands


def deliverable1_gate(ref_all: dict, by_cycle: dict):
    """Sec.6 item 1: re-derive Sec.2.1's table from REF ONLY, before any TEST
    load. STOP (raise) if it does not match -- this is the mechanical gate,
    not a warning (HK-021(r): predicate as code)."""
    classes = classify_population(ref_all, by_cycle)
    counts, bands = build_class_table(ref_all, classes)
    total = sum(counts.values())

    log("=== Deliverable 1: REF-only class table (no TEST loaded yet) ===")
    for c in ("EXPOSED", "PL", "PF", "TRANSITION", "CLEAR", "GAP", "PL_TRANS_STRONG"):
        log("  %-16s n=%6d  (expected %6d)" % (c, counts[c], EXPECTED_TABLE[c]))
    log("  %-16s n=%6d  (expected %6d)" % ("TOTAL", total, EXPECTED_TOTAL))

    mismatches = []
    if total != EXPECTED_TOTAL:
        mismatches.append("total %d != expected %d" % (total, EXPECTED_TOTAL))
    for c, expected in EXPECTED_TABLE.items():
        if counts.get(c, 0) != expected:
            mismatches.append("%s: %d != expected %d" % (c, counts.get(c, 0), expected))

    if mismatches:
        for m in mismatches:
            log("  MISMATCH: " + m)
        raise SystemExit(
            "DELIVERABLE 1 STOP: classifier does not reproduce Sec.2.1's REF-only "
            "table (%d mismatch(es)). Per spec Sec.6 item 1, this arm halts here -- "
            "no TEST decode may be loaded until the classifier matches." % len(mismatches)
        )

    log("  MATCH -- classifier reproduces Sec.2.1 exactly. Proceeding to TEST load.")
    return classes, counts, bands


# ---------------------------------------------------------------------------
# Sec.3: the standardised statistic D(A,B), and its bootstrap.
# ---------------------------------------------------------------------------
def snr_cell(snr):
    """1dB cells -10..+9 (20 individual cells) + one >=+10 cell (spec Sec.3:
    21 cells total)."""
    if snr >= 10:
        return 10
    return max(snr, -10)


def cell_index(snr):
    # maps snr_cell()'s value (-10..10) to a dense 0..20 index
    return snr_cell(snr) + 10


N_CELLS = 21


def compute_D(class_a_rows, class_b_rows):
    """class_a_rows/class_b_rows: list of (cell_index, hit:bool). Returns
    (D, n_a_dropped, n_a_total, n_b_dropped, n_b_total) using direct
    standardisation to A's (retained-cell) SNR mix, spec Sec.3."""
    n_a = np.zeros(N_CELLS, dtype=np.int64)
    h_a = np.zeros(N_CELLS, dtype=np.int64)
    for cidx, hit in class_a_rows:
        n_a[cidx] += 1
        h_a[cidx] += hit
    n_b = np.zeros(N_CELLS, dtype=np.int64)
    h_b = np.zeros(N_CELLS, dtype=np.int64)
    for cidx, hit in class_b_rows:
        n_b[cidx] += 1
        h_b[cidx] += hit

    keep = (n_a >= MIN_CELL_N) & (n_b >= MIN_CELL_N)
    n_a_total = int(n_a.sum())
    n_a_dropped = int(n_a[~keep].sum())

    if not keep.any() or n_a[keep].sum() == 0:
        return float("nan"), n_a_dropped, n_a_total, int(n_b[~keep].sum()), int(n_b.sum())

    w = n_a[keep].astype(float)
    w = w / w.sum()
    miss_a = 1.0 - (h_a[keep] / np.maximum(n_a[keep], 1))
    miss_b = 1.0 - (h_b[keep] / np.maximum(n_b[keep], 1))
    D = float(np.sum(w * (miss_a - miss_b)))
    return D, n_a_dropped, n_a_total, int(n_b[~keep].sum()), int(n_b.sum())


def build_rows(classes: dict, ref_all: dict, hit_set: set):
    """{class_name: [(cell_index, hit_bool), ...]} and {class_name: [(freq, cell_index, hit_bool)]}
    for bootstrap resampling."""
    per_class = {}
    for k, c in classes.items():
        snr, f = ref_all[k]
        hit = k in hit_set
        per_class.setdefault(c, []).append((f, cell_index(snr), hit))
    return per_class


def point_estimate(per_class, name_a, name_b):
    rows_a = [(ci, h) for (_, ci, h) in per_class.get(name_a, [])]
    rows_b = [(ci, h) for (_, ci, h) in per_class.get(name_b, [])]
    return compute_D(rows_a, rows_b)


def bootstrap_D(per_class, contrasts, n_draws=N_BOOT, seed=SEED):
    """contrasts: list of (name_a, name_b). Resamples distinct REF integer
    frequencies with replacement over the UNION of rows in all classes named
    in `contrasts` (spec Sec.3: 'resample distinct REF integer frequencies...
    Paired: one resample per draw serves every contrast'). Returns
    {(name_a,name_b): np.ndarray[n_draws]}."""
    needed_classes = sorted({c for pair in contrasts for c in pair})
    # freq -> list of (class, cell_index, hit) for all rows in needed classes
    byf = {}
    for c in needed_classes:
        for (f, ci, h) in per_class.get(c, []):
            byf.setdefault(f, []).append((c, ci, h))
    freqs = list(byf)
    rng = np.random.default_rng(seed)
    n_freq = len(freqs)

    out = {pair: np.empty(n_draws) for pair in contrasts}
    for d in range(n_draws):
        pick = rng.choice(n_freq, size=n_freq, replace=True)
        by_class = {c: [] for c in needed_classes}
        for i in pick:
            for (c, ci, h) in byf[freqs[i]]:
                by_class[c].append((ci, h))
        for (name_a, name_b) in contrasts:
            D, *_ = compute_D(by_class.get(name_a, []), by_class.get(name_b, []))
            out[(name_a, name_b)][d] = D
    return out, n_freq


def ci95(draws):
    clean = draws[~np.isnan(draws)]
    if len(clean) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(clean, 2.5)), float(np.percentile(clean, 97.5))


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- Phase 1: REF ONLY. No TEST load above this line. ----
    log("Loading REF (C2, WSJT-X FT991A, A-only) ...")
    ref_all = analyse.load_ref_c2()
    log("REF(C2) = %d rows" % len(ref_all))
    by_cycle = build_by_cycle(ref_all)

    classes, ref_counts, ref_bands = deliverable1_gate(ref_all, by_cycle)
    # ---- Deliverable 1 gate passed. TEST may now be loaded. ----

    log("\nLoading TEST (C2, OpenWSFZ, live ALL.TXT) ...")
    test = analyse.load_live_c2_openwsfz()
    log("TEST(C2) = %d rows" % len(test))

    result = {"spec_commit": "517db622", "seed": SEED, "n_boot": N_BOOT}
    result["ref_only_class_table"] = {"counts": ref_counts, "total": sum(ref_counts.values())}

    # ---- ROW 0c: pooled R_wild over ALL 91,046 REF rows reproduces A1 ----
    rec_all = matcher.recovery(test, ref_all)
    row0c_pass = round(rec_all["R_wild"], 2) == A1_TARGET
    log("\nROW 0c: pooled R_wild=%.4f%% (target %.2f%%, n_ref=%d) -> %s" %
        (rec_all["R_wild"], A1_TARGET, rec_all["n_ref"], "PASS" if row0c_pass else "STOP"))
    result["row0c"] = {"R_wild": rec_all["R_wild"], "target": A1_TARGET,
                        "n_ref": rec_all["n_ref"], "pass": row0c_pass}
    hit_set = rec_all["hit_set"]

    per_class = build_rows(classes, ref_all, hit_set)
    class_names = sorted(per_class)
    log("\nPopulation classes (rows used in the statistic): " +
        ", ".join("%s=%d" % (c, len(per_class[c])) for c in class_names))

    # ---- ROW 0a: placebo null D(PL, PF) ----
    D_0a, drop_a_0a, n_a_0a, drop_b_0a, n_b_0a = point_estimate(per_class, "PL", "PF")
    boot_0a, nfreq_0a = bootstrap_D(per_class, [("PL", "PF")])
    lo_0a, hi_0a = ci95(boot_0a[("PL", "PF")])
    row0a_pass = (lo_0a >= -BAR_0A) and (hi_0a <= BAR_0A)
    log("\nROW 0a: D(PL,PF)=%.4f CI95=[%.4f,%.4f] (bar +/-%.2f) -> %s" %
        (D_0a, lo_0a, hi_0a, BAR_0A, "PASS" if row0a_pass else "STOP"))
    result["row0a"] = {"D": D_0a, "ci95": [lo_0a, hi_0a], "bar": BAR_0A, "pass": row0a_pass,
                        "n_freq_resampled": nfreq_0a,
                        "PL_dropped": drop_a_0a, "PL_total": n_a_0a,
                        "PF_dropped": drop_b_0a, "PF_total": n_b_0a}

    # ---- ROW 0b: standardisation coverage (EXPOSED-vs-PL drop, and PL-vs-PF drop from 0a) ----
    D_primary, drop_exp, n_exp, drop_pl, n_pl = point_estimate(per_class, "EXPOSED", "PL")
    frac_exp_dropped = (drop_exp / n_exp) if n_exp else float("nan")
    frac_pl0a_dropped = (drop_a_0a / n_a_0a) if n_a_0a else float("nan")
    row0b_pass = (frac_exp_dropped <= MAX_DROP_FRAC) and (frac_pl0a_dropped <= MAX_DROP_FRAC)
    log("\nROW 0b: EXPOSED dropped %d/%d (%.2f%%); PL(0a) dropped %d/%d (%.2f%%) (bar <=%.0f%%) -> %s" %
        (drop_exp, n_exp, 100 * frac_exp_dropped, drop_a_0a, n_a_0a, 100 * frac_pl0a_dropped,
         100 * MAX_DROP_FRAC, "PASS" if row0b_pass else "STOP"))
    result["row0b"] = {"EXPOSED_dropped": drop_exp, "EXPOSED_total": n_exp,
                        "EXPOSED_drop_frac": frac_exp_dropped,
                        "PL_0a_dropped": drop_a_0a, "PL_0a_total": n_a_0a,
                        "PL_0a_drop_frac": frac_pl0a_dropped,
                        "max_drop_frac": MAX_DROP_FRAC, "pass": row0b_pass}

    row0_fires = not (row0a_pass and row0b_pass and row0c_pass)
    result["row0_fires"] = row0_fires

    # ---- Primary: D(EXPOSED, PL) ----
    boot_primary, nfreq_primary = bootstrap_D(per_class, [("EXPOSED", "PL")])
    lo_p, hi_p = ci95(boot_primary[("EXPOSED", "PL")])
    n_exposed = len(per_class.get("EXPOSED", []))
    # spec Sec.3: C = D * n_EXPOSED / 91,046, IN PP -- the worked example
    # (D=0.170 <=> C=1.0pp) only holds after x100 (D and the ratio are both
    # fractions in [0,1]; pp is a percentage). n=91,046 is ALL REF, not the
    # population subset.
    C_cost = D_primary * n_exposed / 91046.0 * 100.0

    if row0_fires:
        verdict = "ROW 0 STOP"
    elif lo_p >= BAR_PRIMARY:
        verdict = "ROW 1 CONCENTRATES"
    elif hi_p < BAR_PRIMARY:
        verdict = "ROW 2 DEFLATES"
    else:
        verdict = "ROW 3 UNRESOLVED"

    log("\nPRIMARY: D(EXPOSED,PL)=%.4f CI95=[%.4f,%.4f] (bar %.3f) C=%.3fpp n_freq=%d" %
        (D_primary, lo_p, hi_p, BAR_PRIMARY, C_cost, nfreq_primary))
    log(">>> VERDICT: %s <<<" % verdict)
    result["primary"] = {"D": D_primary, "ci95": [lo_p, hi_p], "bar": BAR_PRIMARY,
                          "C_pp": C_cost, "n_exposed": n_exposed, "n_freq_resampled": nfreq_primary,
                          "verdict": verdict}

    # ---- Sec.4.3: reporting-only items ----
    log("\n=== Sec.4.3 reporting-only items ===")
    reporting = {}

    # 1. Raw recovery per class, pooled and per 5dB band, with n.
    per_class_recovery = {}
    for c in class_names:
        rows = per_class[c]
        n = len(rows)
        hits = sum(1 for (_, _, h) in rows if h)
        per_class_recovery[c] = {"n": n, "hits": hits, "recovery_pct": (100.0 * hits / n) if n else float("nan")}
    reporting["1_raw_recovery_per_class"] = per_class_recovery
    for c in class_names:
        r = per_class_recovery[c]
        log("  %-18s n=%6d recovery=%6.2f%%" % (c, r["n"], r["recovery_pct"]))

    # 1b. per-class per-5dB-band recovery, with n (recomputed with true snr, not cell index)
    per_class_band = {}
    for c in class_names:
        band_n = {b: 0 for b in ("-10..-6", "-5..-1", "0..4", "5..9", ">=10")}
        band_hit = {b: 0 for b in ("-10..-6", "-5..-1", "0..4", "5..9", ">=10")}
        for k, cls in classes.items():
            if cls != c:
                continue
            snr = ref_all[k][0]
            b = snr_band5(snr)
            band_n[b] += 1
            if k in hit_set:
                band_hit[b] += 1
        per_class_band[c] = {b: {"n": band_n[b],
                                  "recovery_pct": (100.0 * band_hit[b] / band_n[b]) if band_n[b] else float("nan")}
                              for b in band_n}
    reporting["1b_raw_recovery_per_class_per_5dB_band"] = per_class_band

    # 2. D(EXPOSED,PL) per 5dB band -- reporting only, never gated (HK-021(y))
    d_by_band = {}
    for b in ("-10..-6", "-5..-1", "0..4", "5..9", ">=10"):
        rows_a = [(cell_index(ref_all[k][0]), k in hit_set) for k, c in classes.items()
                  if c == "EXPOSED" and snr_band5(ref_all[k][0]) == b]
        rows_b = [(cell_index(ref_all[k][0]), k in hit_set) for k, c in classes.items()
                  if c == "PL" and snr_band5(ref_all[k][0]) == b]
        D_b, da, na, db, nb = compute_D(rows_a, rows_b)
        d_by_band[b] = {"D": D_b, "n_EXPOSED": na, "n_PL": nb}
    reporting["2_D_exposed_pl_per_5dB_band"] = d_by_band
    log("  D(EXPOSED,PL) per band: " + ", ".join("%s=%.3f" % (b, d_by_band[b]["D"]) for b in d_by_band))

    # 3. D(TRANSITION, PF) -- graded-zone check, reporting only
    D_trans, drop_t, n_t, drop_pf3, n_pf3 = point_estimate(per_class, "TRANSITION", "PF")
    boot_trans, nfreq_trans = bootstrap_D(per_class, [("TRANSITION", "PF")])
    lo_t, hi_t = ci95(boot_trans[("TRANSITION", "PF")])
    reporting["3_D_transition_pf"] = {"D": D_trans, "ci95": [lo_t, hi_t],
                                       "TRANSITION_total": n_t, "PF_total": n_pf3}
    log("  D(TRANSITION,PF)=%.4f CI95=[%.4f,%.4f]" % (D_trans, lo_t, hi_t))

    # 4. D(EXPOSED, PF) -- for completeness
    D_ep, drop_e4, n_e4, drop_pf4, n_pf4 = point_estimate(per_class, "EXPOSED", "PF")
    boot_ep, nfreq_ep = bootstrap_D(per_class, [("EXPOSED", "PF")])
    lo_ep, hi_ep = ci95(boot_ep[("EXPOSED", "PF")])
    reporting["4_D_exposed_pf"] = {"D": D_ep, "ci95": [lo_ep, hi_ep],
                                    "EXPOSED_total": n_e4, "PF_total": n_pf4}
    log("  D(EXPOSED,PF)=%.4f CI95=[%.4f,%.4f]" % (D_ep, lo_ep, hi_ep))

    # 5. EXPOSED recovery split by rel==0 vs rel>=1
    rel0_n = rel0_hit = relpos_n = relpos_hit = 0
    for k, cls in classes.items():
        if cls != "EXPOSED":
            continue
        ts, msg = k
        snr, f = ref_all[k]
        neighbours = [(s, nf) for (s, nf, m) in by_cycle[ts] if not (s == snr and nf == f and m == msg)]
        # recompute the max rel among <=18Hz neighbours to split at 0 vs >=1
        near = [s - snr for s, nf in neighbours if abs(nf - f) <= 18]
        m = max(near) if near else None
        is_hit = k in hit_set
        if m == 0:
            rel0_n += 1
            rel0_hit += is_hit
        elif m is not None and m >= 1:
            relpos_n += 1
            relpos_hit += is_hit
    reporting["5_exposed_recovery_by_rel"] = {
        "rel_eq_0": {"n": rel0_n, "recovery_pct": (100.0 * rel0_hit / rel0_n) if rel0_n else float("nan")},
        "rel_ge_1": {"n": relpos_n, "recovery_pct": (100.0 * relpos_hit / relpos_n) if relpos_n else float("nan")},
    }
    log("  EXPOSED rel==0: n=%d recovery=%.2f%% | rel>=1: n=%d recovery=%.2f%%" %
        (rel0_n, reporting["5_exposed_recovery_by_rel"]["rel_eq_0"]["recovery_pct"],
         relpos_n, reporting["5_exposed_recovery_by_rel"]["rel_ge_1"]["recovery_pct"]))

    # 6. Counts: GAP, PL_TRANS_STRONG, dropped cells (already in row0a/row0b), ambiguous wildcard matches
    reporting["6_counts"] = {
        "GAP": ref_counts.get("GAP", 0),
        "PL_TRANS_STRONG": ref_counts.get("PL_TRANS_STRONG", 0),
        "n_ambiguous_wildcard": rec_all["n_ambiguous"],
        "ambiguous_frac": rec_all["ambiguous_frac"],
    }
    log("  GAP=%d PL_TRANS_STRONG=%d ambiguous_wildcard=%d (%.2f%%)" %
        (reporting["6_counts"]["GAP"], reporting["6_counts"]["PL_TRANS_STRONG"],
         rec_all["n_ambiguous"], 100 * rec_all["ambiguous_frac"]))

    result["reporting"] = reporting

    with open(RESULT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log("\nWrote %s" % os.path.abspath(RESULT_JSON))
    return 0


if __name__ == "__main__":
    sys.exit(main())
