#!/usr/bin/env python3
"""X2 -- 80m density floor and the crowding term.

Spec: qa/cycleframer-alignment-replay/2026-08-10-1538-architect-to-qa-spec-x2-80m-density-floor-and-the-crowding-term.md
      -- AMENDMENT 1 (2026-08-10 16:44Z) WINS wherever it disagrees with the spec body; this
      harness follows the amended version throughout (pinned SNR edges, L1-only primary metric,
      no candidate-budget consequence).
Governing pre-registration (NOT superseded, still binds ROW 0a-0e and the S4 prediction):
  qa/cycleframer-alignment-replay/2026-08-09-0149-qa-prereg-80m-dying-band-density-floor.md

Question: does OpenWSFZ's recovery deficit vs WSJT-X grow when a cycle is more crowded, holding
SNR fixed? "Crowding" here is a per-cycle REF-row COUNT (density) only -- never a spectral-
neighbourhood measure (S.1 is CLOSED, spec S4.3; do not go there).

Shares its basis with X1: same LEGS, same REF = A n B (+ the same two exclusions), same density
definition (per-cycle count of clean REF rows), and reuses t1_frequency_quantisation.load()
UNMODIFIED. Reuses X1's cycle-clustered bootstrap machinery (build_cycle_agg / aggregate_cells /
bootstrap_cell_replicates / percentile) UNMODIFIED, and X1's PUBLISHED pooled SNR strata edges
PINNED VERBATIM (Amendment 1 S A1.6.2) rather than recomputed -- identical by construction, but
pinning removes a drift path. Only the standardisation weighting is genuinely new here (spec S2:
equally-weighted across qualifying SNR strata, NOT X1's coverage-weighted b_std -- X2 contrasts two
density regimes of the SAME band, not two different bands, so composition-weighting would just
re-import the density effect being measured).

No src/ change. No capture. Pure re-analysis of ALL.TXT already on disk.
"""
import collections
import io
import json
import os
import random
import statistics
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_frequency_quantisation import load  # noqa: E402 -- reused unmodified
from x1_cross_band_decomposition import (  # noqa: E402 -- shared basis + bootstrap machinery
    LEGS, EXPECT_CLEAN_REF, has_unresolved_hash, aggregate_cells,
    bootstrap_cell_replicates, percentile, assign_stratum,
)

SEED = 20260810           # fixed seed, HK-021 -- reproducible bit-for-bit
N_BOOT = 1000
MIN_STRATUM_N = 30        # spec S2: strata with <30 rows on either side dropped
SHAPE_MIN_STRATUM_N = 10  # S4.2 is descriptive only -- disclosed, relaxed threshold
LEVEL = "L1"               # Amendment 1 S A1.6.3: "X2's primary metric uses L1"

# Amendment 1 S A1.6.2 -- X1's PUBLISHED pooled SNR strata edges, pinned verbatim (not recomputed).
SNR_EDGES_L1 = [-15, -10, -5, 2]

# spec S2 -- density regimes, fixed identically across every band (HK-021(g)), NOT derived from
# any one band's own quantiles.
FLOOR_MAX = 5
MID_MAX = 13
OVERLAP_MAX = 26


def regime_of(d):
    if d <= FLOOR_MAX:
        return "FLOOR"
    if d <= MID_MAX:
        return "MID"
    if d <= OVERLAP_MAX:
        return "OVERLAP"
    return None


# ── population / band construction (shared shape with X1, generalised for ROW 0g) ──────────

def clean_population(a, ref_keys):
    """Applies the two pre-registered exclusions off reference-A's fields -- identical
    convention to X1/T1. ref_keys is EITHER (A n B) for the primary basis, or A alone for the
    ROW 0g selection-control variant."""
    excl_hash = excl_band = 0
    kept = []
    for k in ref_keys:
        ts, msg = k
        if has_unresolved_hash(msg):
            excl_hash += 1
            continue
        snr, freq_hz = a[k]
        if not (200 <= freq_hz <= 3000):
            excl_band += 1
            continue
        kept.append(k)
    return kept, excl_hash, excl_band


def build_cycle_agg_l1(band):
    """Local, single-level (L1) analogue of X1's build_cycle_agg -- X1's version iterates its
    own module-level LEVELS=("L1","L2","L3") tuple unconditionally, and X2 only ever assigns an
    "L1" stratum to each row (Amendment 1 S A1.6.3: X2's primary metric uses L1 only), so X1's
    function cannot be reused unmodified here without also computing L2/L3 strata X2 never uses.
    Produces the same {level: {ts: {stratum: [n, m8080, m8081]}}} shape aggregate_cells/
    bootstrap_cell_replicates (both reused UNMODIFIED from X1) expect."""
    per_cycle = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
    for r in band.rows:
        e = per_cycle[r["ts"]][r["strat"][LEVEL]]
        e[0] += 1
        e[1] += 1 if r["matched8080"] else 0
        e[2] += 1 if r["matched8081"] else 0
    return {LEVEL: {ts: dict(v) for ts, v in per_cycle.items()}}


def build_band(name, use_b=True):
    """Returns a types.SimpleNamespace shaped so X1's build_cycle_agg/aggregate_cells/
    bootstrap_cell_replicates can be reused unmodified (they only touch .rows/.cycles/
    .density_by_cycle/.cycle_agg)."""
    cfg = LEGS[name]
    lo, hi = cfg["window"]
    a = load(cfg["ref_a"], lo, hi)
    b = load(cfg["ref_b"], lo, hi)
    o8080 = load(cfg["owsfz8080"], lo, hi)
    o8081 = load(cfg["owsfz8081"], lo, hi)

    ref_keys = (set(a) & set(b)) if use_b else set(a)
    kept, excl_hash, excl_band = clean_population(a, ref_keys)

    density_by_cycle = collections.Counter(ts for ts, _ in kept)
    rows = []
    for k in kept:
        ts, msg = k
        snr, freq_hz = a[k]
        rows.append({
            "ts": ts, "snr": snr, "freq_hz": freq_hz,
            "density": density_by_cycle[ts],
            "matched8080": k in o8080,
            "matched8081": k in o8081,
            "strat": {LEVEL: assign_stratum(snr, SNR_EDGES_L1)},
        })

    band = types.SimpleNamespace()
    band.name = name
    band.n_a_raw = len(a)
    band.n_ref_raw = len(ref_keys)
    band.n_ref_clean = len(kept)
    band.excl_hash = excl_hash
    band.excl_band = excl_band
    band.rows = rows
    band.density_by_cycle = dict(density_by_cycle)
    band.cycles = sorted(density_by_cycle)
    band.cycle_agg = build_cycle_agg_l1(band)
    band.o8080_keys = set(o8080)
    band.o8081_keys = set(o8081)
    return band


# ── X2's own standardisation: equal-weighted across qualifying SNR strata (spec S2) ────────

def collapse_to_regime_cells(density_stratum_cells, regime_a, regime_b):
    """cells: (density, stratum) -> [n, matched] (SUT=8080, from aggregate_cells).
    Returns {stratum: {"a": [n, matched], "b": [n, matched]}} summed within each regime."""
    out = collections.defaultdict(lambda: {"a": [0, 0], "b": [0, 0]})
    for (d, s), (n, m) in density_stratum_cells.items():
        r = regime_of(d)
        if r == regime_a:
            out[s]["a"][0] += n
            out[s]["a"][1] += m
        elif r == regime_b:
            out[s]["b"][0] += n
            out[s]["b"][1] += m
    return out


def f_std_from_regime_cells(regime_cells, min_n=MIN_STRATUM_N):
    diffs = []
    for _s, sides in regime_cells.items():
        na, ma = sides["a"]
        nb, mb = sides["b"]
        if na < min_n or nb < min_n:
            continue
        diffs.append(100.0 * ma / na - 100.0 * mb / nb)
    if not diffs:
        return None, 0
    return statistics.mean(diffs), len(diffs)


def raw_recovery_for_regime(rows, regime_name, sut="matched8080"):
    n = m = 0
    for r in rows:
        if regime_of(r["density"]) == regime_name:
            n += 1
            m += 1 if r[sut] else 0
    return (100.0 * m / n if n else None), n, m


def point_cells(band, sut="8080"):
    return aggregate_cells({ts: 1 for ts in band.cycles}, band.density_by_cycle,
                            band.cycle_agg[LEVEL], sut)


def f_std_band(band, regime_a="FLOOR", regime_b="OVERLAP", rng=None, n_boot=N_BOOT,
                min_n=MIN_STRATUM_N, boot_cells=None):
    """Point estimate + cycle-clustered bootstrap SE/CI for F_std(band) = std_recovery(regime_a)
    - std_recovery(regime_b), equal-weighted over qualifying SNR strata (spec S2)."""
    cells = point_cells(band, "8080")
    regime_cells = collapse_to_regime_cells(cells, regime_a, regime_b)
    point, n_strata = f_std_from_regime_cells(regime_cells, min_n)

    raw_a, n_a, _ = raw_recovery_for_regime(band.rows, regime_a)
    raw_b, n_b, _ = raw_recovery_for_regime(band.rows, regime_b)
    f_raw = (raw_a - raw_b) if (raw_a is not None and raw_b is not None) else None

    if boot_cells is None:
        boot_cells = bootstrap_cell_replicates(band, LEVEL, "8080", rng, n_boot)
    boot_vals = []
    for bc in boot_cells:
        rc = collapse_to_regime_cells(bc, regime_a, regime_b)
        v, _ = f_std_from_regime_cells(rc, min_n)
        if v is not None:
            boot_vals.append(v)
    boot_vals.sort()
    se = statistics.pstdev(boot_vals) if len(boot_vals) > 1 else float("nan")
    ci_lo = percentile(boot_vals, 0.025) if boot_vals else float("nan")
    ci_hi = percentile(boot_vals, 0.975) if boot_vals else float("nan")

    return {
        "f_std": point, "n_strata": n_strata, "f_raw": f_raw,
        "n_a": n_a, "n_b": n_b, "raw_a": raw_a, "raw_b": raw_b,
        "se": se, "ci_lo": ci_lo, "ci_hi": ci_hi, "n_boot_valid": len(boot_vals),
    }, boot_cells


# ── S4.2 shape: SNR-standardised recovery against EXACT integer density ────────────────────

def shape_curve(band, boot_cells, min_n_stratum=SHAPE_MIN_STRATUM_N):
    point = point_cells(band, "8080")
    by_density = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for (d, s), (n, m) in point.items():
        by_density[d][s][0] += n
        by_density[d][s][1] += m

    out = {}
    for d, strata in by_density.items():
        n_total = sum(v[0] for v in strata.values())
        m_total = sum(v[1] for v in strata.values())
        raw = 100.0 * m_total / n_total if n_total else None
        qualifying = [100.0 * v[1] / v[0] for v in strata.values() if v[0] >= min_n_stratum]
        std = statistics.mean(qualifying) if qualifying else None
        out[d] = {"n": n_total, "raw_recovery": raw, "std_recovery": std,
                   "n_strata_used": len(qualifying), "boot": []}

    for bc in boot_cells:
        by_d = collections.defaultdict(lambda: [0, 0])
        for (d, _s), (n, m) in bc.items():
            by_d[d][0] += n
            by_d[d][1] += m
        for d, (n, m) in by_d.items():
            if d in out and n > 0:
                out[d]["boot"].append(100.0 * m / n)

    rows = []
    for d in sorted(out):
        e = out[d]
        bv = sorted(e["boot"])
        se = statistics.pstdev(bv) if len(bv) > 1 else None
        ci_lo = percentile(bv, 0.025) if bv else None
        ci_hi = percentile(bv, 0.975) if bv else None
        rows.append({"density": d, "n": e["n"], "raw_recovery": e["raw_recovery"],
                      "std_recovery": e["std_recovery"], "n_strata_used": e["n_strata_used"],
                      "se_raw": se, "ci_lo_raw": ci_lo, "ci_hi_raw": ci_hi})
    return rows


# ── main ─────────────────────────────────────────────────────────────────────────────────

def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    result = {}
    print("=" * 88)
    print("X2 -- 80m density floor and the crowding term")
    print("=" * 88)

    # ---- ROW 0f -- verify (not redo) X1's reference repair on the 80m wsjt-x/ALL.TXT pair ----
    ino_a = os.stat(LEGS["80m"]["ref_a"]).st_ino
    ino_b = os.stat(LEGS["80m"]["ref_b"]).st_ino
    row0f = ino_a != ino_b
    print("\nROW 0f (X0/X1 repair, verified not redone) -- 80m wsjt-x/ALL.TXT inodes: A=%d B=%d -> %s"
          % (ino_a, ino_b, "distinct (repaired, OK)" if row0f else "SAME -- VOID, repair regressed"))

    # ---- ROW 0e -- window-end integrity (mechanical, same method as X1) ----
    lo, hi = LEGS["80m"]["window"]
    hi_alt = LEGS["80m"]["window_alt_end"]
    a_primary = load(LEGS["80m"]["ref_a"], lo, hi)
    b_primary = load(LEGS["80m"]["ref_b"], lo, hi)
    ref_primary_raw = len(set(a_primary) & set(b_primary))
    a_alt = load(LEGS["80m"]["ref_a"], lo, hi_alt)
    b_alt = load(LEGS["80m"]["ref_b"], lo, hi_alt)
    ref_alt_raw = len(set(a_alt) & set(b_alt))
    row0e = ref_primary_raw == ref_alt_raw
    print("ROW 0e -- 80m REF (raw A n B): window end 072815 = %d, window end 101100 = %d -> %s"
          % (ref_primary_raw, ref_alt_raw, "IDENTICAL" if row0e else "DIFFERS -- VOID"))

    print("\nBuilding bands (load + clean population, primary basis A n B)...")
    bands = {name: build_band(name, use_b=True) for name in LEGS}
    for name, band in bands.items():
        expect = EXPECT_CLEAN_REF.get(name)
        drift_flag = "" if expect is None else (" [T1 EXPECT %d -> %s]" % (
            expect, "MATCH" if expect == band.n_ref_clean else "MISMATCH -- basis drift!"))
        print("  %-4s  |A|=%6d  |REF| raw=%6d  clean=%6d  (excl hash=%d, out-of-band=%d)  cycles=%d%s"
              % (name, band.n_a_raw, band.n_ref_raw, band.n_ref_clean,
                 band.excl_hash, band.excl_band, len(band.cycles), drift_flag))

    # ---- ROW 0a -- population floor (>= 150 cycles), 80m ----
    row0a = len(bands["80m"].cycles) >= 150
    print("\nROW 0a -- 80m REF cycles = %d (bar >= 150) -> %s"
          % (len(bands["80m"].cycles), "PASS" if row0a else "VOID"))

    # ---- ROW 0b -- new floor reached (min density < 3, or bottom decile < 9.7) ----
    densities_80m = sorted(bands["80m"].density_by_cycle.values())
    min_density = densities_80m[0]
    bottom_decile = densities_80m[max(0, int(len(densities_80m) * 0.10) - 1)]
    n_floor_cycles = sum(1 for d in densities_80m if d <= FLOOR_MAX)
    row0b = (min_density < 3) or (bottom_decile < 9.7)
    print("ROW 0b -- 80m min density=%d, bottom decile=%.1f, FLOOR(<=%d) cycles=%d -> %s"
          % (min_density, bottom_decile, FLOOR_MAX, n_floor_cycles, "PASS" if row0b else "VOID"))

    # ---- ROW 0c -- self-consistency (OpenWSFZ 8080 vs 8081, Jaccard), pre-decline portion ----
    # "pre-decline" operationalised mechanically as cycles NOT in the FLOOR regime (density > 5) --
    # HK-021(a): structure decides what gets seen, chosen before looking at the Jaccard value.
    predecline_cycles = {ts for ts, d in bands["80m"].density_by_cycle.items() if d > FLOOR_MAX}
    o8080_pd = {k for k in bands["80m"].o8080_keys if k[0] in predecline_cycles}
    o8081_pd = {k for k in bands["80m"].o8081_keys if k[0] in predecline_cycles}
    inter = len(o8080_pd & o8081_pd)
    union = len(o8080_pd | o8081_pd)
    jaccard = inter / union if union else 0.0
    row0c = jaccard >= 0.90
    print("ROW 0c -- 80m self-consistency (OpenWSFZ 8080 vs 8081 Jaccard, pre-decline cycles=%d): "
          "%d / %d = %.4f -> %s" % (len(predecline_cycles), inter, union, jaccard,
                                     "PASS" if row0c else "VOID"))

    # ---- ROW 0d -- band label, mechanical, EVERY Rx FT8 line's dial-freq field ----
    def dial_freqs(path, lo, hi):
        vals = set()
        n_lines = 0
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = line.split()
                if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                    continue
                ts = f[0]
                if not (lo <= ts <= hi):
                    continue
                vals.add(f[1])
                n_lines += 1
        return vals, n_lines

    row0d = True
    row0d_detail = {}
    for side, path in (("ref_a", LEGS["80m"]["ref_a"]), ("ref_b", LEGS["80m"]["ref_b"]),
                        ("owsfz8080", LEGS["80m"]["owsfz8080"]), ("owsfz8081", LEGS["80m"]["owsfz8081"])):
        vals, n_lines = dial_freqs(path, lo, hi)
        ok = vals == {"3.573"}
        row0d = row0d and ok
        row0d_detail[side] = {"distinct_dial_freqs": sorted(vals), "n_lines": n_lines, "ok": ok}
        print("ROW 0d -- %-10s distinct dial-freq values over %d lines: %s -> %s"
              % (side, n_lines, sorted(vals), "OK" if ok else "FAIL"))
    print(">>> ROW 0d: %s <<<" % ("PASS" if row0d else "VOID"))

    result["row0"] = {
        "row0a_pass": row0a, "row0a_cycles": len(bands["80m"].cycles),
        "row0b_pass": row0b, "row0b_min_density": min_density, "row0b_bottom_decile": bottom_decile,
        "row0b_floor_cycles": n_floor_cycles,
        "row0c_pass": row0c, "row0c_jaccard": jaccard, "row0c_inter": inter, "row0c_union": union,
        "row0d_pass": row0d, "row0d_detail": row0d_detail,
        "row0e_pass": row0e, "row0e_072815": ref_primary_raw, "row0e_101100": ref_alt_raw,
        "row0f_pass": row0f,
    }

    void = not (row0a and row0b and row0c and row0d and row0e and row0f)
    print("\n>>> ROW 0 (a/b/c/d/e/f combined): %s <<<" % ("ALL PASS" if not void else "VOID -- STOPPING"))
    if void:
        with io.open("qa/cycleframer-alignment-replay/x2_result.json", "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        return 1

    # ---- ROW 0g -- selection control: A-only reference vs A n B ----
    print("\n" + "=" * 88)
    print("ROW 0g -- selection control (A-only reference vs A n B)")
    print("=" * 88)
    band_80m_aonly = build_band("80m", use_b=False)
    fstd_anb, _ = f_std_band(bands["80m"], "FLOOR", "OVERLAP", rng=None, n_boot=0)
    # point-estimate only for A-only (per spec: "recompute F_std with an A-only reference" --
    # a point comparison, not a second full bootstrap)
    cells_aonly = point_cells(band_80m_aonly, "8080")
    regime_cells_aonly = collapse_to_regime_cells(cells_aonly, "FLOOR", "OVERLAP")
    fstd_aonly_point, n_strata_aonly = f_std_from_regime_cells(regime_cells_aonly)
    row0g_diff = abs(fstd_anb["f_std"] - fstd_aonly_point) if (fstd_anb["f_std"] is not None and fstd_aonly_point is not None) else None
    row0g_material = row0g_diff is not None and row0g_diff > 3.0
    print("F_std(A n B)   = %+.3f pp (n_strata=%d)" % (fstd_anb["f_std"], fstd_anb["n_strata"]))
    print("F_std(A-only)  = %+.3f pp (n_strata=%d)  [n_ref_raw=%d vs A n B's %d]"
          % (fstd_aonly_point, n_strata_aonly, band_80m_aonly.n_ref_raw, bands["80m"].n_ref_raw))
    print("|difference|   = %.3f pp -> %s (bar 3.0 pp)"
          % (row0g_diff, "CONFOUNDED BY SELECTION" if row0g_material else "selection channel immaterial"))
    result["row0g"] = {
        "f_std_a_and_b": fstd_anb["f_std"], "f_std_a_only": fstd_aonly_point,
        "diff": row0g_diff, "material": row0g_material,
        "n_ref_raw_a_and_b": bands["80m"].n_ref_raw, "n_ref_raw_a_only": band_80m_aonly.n_ref_raw,
    }

    # ---- primary metric: F_std(80m), FLOOR vs OVERLAP, L1, cycle-clustered bootstrap ----
    print("\n" + "=" * 88)
    print("PRIMARY METRIC -- F_std(80m) = std_recovery(FLOOR) - std_recovery(OVERLAP), L1, N_BOOT=%d" % N_BOOT)
    print("=" * 88)
    rng = random.Random(SEED)
    fstd_80m, boot_cells_80m = f_std_band(bands["80m"], "FLOOR", "OVERLAP", rng=rng, n_boot=N_BOOT)
    print("F_std  = %+.3f pp  (n_strata=%d/5 qualifying, min n=%d each side)"
          % (fstd_80m["f_std"], fstd_80m["n_strata"], MIN_STRATUM_N))
    print("F_raw  = %+.3f pp  (FLOOR raw=%.2f%% n=%d, OVERLAP raw=%.2f%% n=%d)"
          % (fstd_80m["f_raw"], fstd_80m["raw_a"], fstd_80m["n_a"], fstd_80m["raw_b"], fstd_80m["n_b"]))
    print("SE(F_std) = %.3f pp   95%% CI = [%+.3f, %+.3f] pp   (n_boot_valid=%d)"
          % (fstd_80m["se"], fstd_80m["ci_lo"], fstd_80m["ci_hi"], fstd_80m["n_boot_valid"]))
    result["primary"] = fstd_80m

    # per-stratum breakdown, cross-checking the Architect's S0.1 disclosure of near-100%
    # recovery at the floor in the top SNR strata
    cells_80m_point = point_cells(bands["80m"], "8080")
    regime_cells_80m = collapse_to_regime_cells(cells_80m_point, "FLOOR", "OVERLAP")
    print("\nPer-SNR-stratum recovery, FLOOR vs OVERLAP (L1, edges=%s):" % SNR_EDGES_L1)
    per_stratum = {}
    for s in sorted(regime_cells_80m):
        na, ma = regime_cells_80m[s]["a"]
        nb, mb = regime_cells_80m[s]["b"]
        ra = 100.0 * ma / na if na else None
        rb = 100.0 * mb / nb if nb else None
        per_stratum[s] = {"floor_n": na, "floor_recovery": ra, "overlap_n": nb, "overlap_recovery": rb}
        print("  stratum %d  FLOOR n=%4d recovery=%s%%   OVERLAP n=%4d recovery=%s%%"
              % (s, na, "%.1f" % ra if ra is not None else "None",
                 nb, "%.1f" % rb if rb is not None else "None"))
    result["per_stratum"] = per_stratum

    # SNR-distribution check (descriptive, matches Architect's S0.1 disclosure)
    def snr_pctiles(rows, regime_name):
        vals = sorted(r["snr"] for r in rows if regime_of(r["density"]) == regime_name)
        if not vals:
            return None
        return {"p10": percentile(vals, 0.10), "median": percentile(vals, 0.50),
                "p90": percentile(vals, 0.90), "n": len(vals)}

    snr_floor = snr_pctiles(bands["80m"].rows, "FLOOR")
    snr_mid = snr_pctiles(bands["80m"].rows, "MID")
    snr_overlap = snr_pctiles(bands["80m"].rows, "OVERLAP")
    print("\nSNR distribution check (descriptive):")
    print("  FLOOR    p10/med/p90 = %s" % snr_floor)
    print("  MID      p10/med/p90 = %s" % snr_mid)
    print("  OVERLAP  p10/med/p90 = %s" % snr_overlap)
    result["snr_distributions"] = {"FLOOR": snr_floor, "MID": snr_mid, "OVERLAP": snr_overlap}

    # ---- gate (spec S3, verbatim; unchanged by Amendment 1 per A1.8) ----
    print("\n" + "=" * 88)
    print("GATE -- 80m primary")
    print("=" * 88)
    f = fstd_80m["f_std"]
    se = fstd_80m["se"]
    lo_ci, hi_ci = fstd_80m["ci_lo"], fstd_80m["ci_hi"]
    if se > 2.0:
        gate_row = "ROW 0h"  # UNDERPOWERED, instrument failure
    elif abs(f) >= 5.0 and not (lo_ci <= 0 <= hi_ci):
        gate_row = "ROW 1"
    elif abs(f) <= 1.5:
        gate_row = "ROW 2"
    else:
        gate_row = "ROW 3"
    print("F_std = %+.3f pp, SE = %.3f pp, 95%% CI = [%+.3f, %+.3f] pp" % (f, se, lo_ci, hi_ci))
    print(">>> %s <<<" % gate_row)
    result["gate"] = {"row": gate_row, "f_std": f, "se": se, "ci_lo": lo_ci, "ci_hi": hi_ci}

    # ---- S4.1 replication: 20m and 17m, same regimes/strata/estimator, power check first ----
    print("\n" + "=" * 88)
    print("S4.1 -- replication on 20m / 17m")
    print("=" * 88)
    replication = {}
    band_seed_offset = {"20m": 1, "17m": 2}  # fixed, deterministic -- NOT Python's salted hash()
    for name in ("20m", "17m"):
        band = bands[name]
        rng_r = random.Random(SEED + band_seed_offset[name])
        floor_n = sum(1 for r in band.rows if regime_of(r["density"]) == "FLOOR")
        res_floor, bc = f_std_band(band, "FLOOR", "OVERLAP", rng=rng_r, n_boot=N_BOOT)
        underpowered = (floor_n < 300) or (res_floor["se"] is not None and not (res_floor["se"] != res_floor["se"]) and res_floor["se"] > 3.0)
        entry = {"floor_n": floor_n, "floor_overlap": res_floor, "underpowered": underpowered}
        print("\n%s: FLOOR n=%d  F_std(FLOOR-OVERLAP)=%s pp  SE=%s  -> %s"
              % (name, floor_n,
                 "%+.3f" % res_floor["f_std"] if res_floor["f_std"] is not None else "None",
                 "%.3f" % res_floor["se"] if res_floor["se"] == res_floor["se"] else "nan",
                 "UNDERPOWERED (floor n<300 or SE>3.0)" if underpowered else "powered"))
        if underpowered:
            res_mid, _ = f_std_band(band, "MID", "OVERLAP", rng=rng_r, n_boot=N_BOOT)
            entry["mid_overlap"] = res_mid
            print("  substituting MID vs OVERLAP: F_std=%s pp  SE=%s  95%% CI=[%s, %s]"
                  % ("%+.3f" % res_mid["f_std"] if res_mid["f_std"] is not None else "None",
                     "%.3f" % res_mid["se"] if res_mid["se"] == res_mid["se"] else "nan",
                     "%+.3f" % res_mid["ci_lo"] if res_mid["ci_lo"] == res_mid["ci_lo"] else "nan",
                     "%+.3f" % res_mid["ci_hi"] if res_mid["ci_hi"] == res_mid["ci_hi"] else "nan"))
        replication[name] = entry
    result["replication"] = replication

    # Context only, not gated: 80m's OWN MID-vs-OVERLAP, for apples-to-apples comparison against
    # the substituted metric used on 20m/17m above (their FLOOR regime is unreachable).
    res_80m_mid, _ = f_std_band(bands["80m"], "MID", "OVERLAP", rng=random.Random(SEED + 3), n_boot=N_BOOT)
    print("\n80m (context only, same MID-vs-OVERLAP proxy used above for 20m/17m): "
          "F_std=%+.3f pp  SE=%.3f  95%% CI=[%+.3f, %+.3f]"
          % (res_80m_mid["f_std"], res_80m_mid["se"], res_80m_mid["ci_lo"], res_80m_mid["ci_hi"]))
    result["mid_overlap_80m_context"] = res_80m_mid

    # ---- S4.2 shape: SNR-standardised recovery vs exact integer density (descriptive) ----
    print("\n" + "=" * 88)
    print("S4.2 -- shape (descriptive only, no row turns on this, no slope fit)")
    print("=" * 88)
    shape_rows = shape_curve(bands["80m"], boot_cells_80m)
    for row in shape_rows:
        print("  density=%3d  n=%4d  raw=%s%%  std=%s%% (strata used=%d)  95%%CI(raw)=[%s,%s]"
              % (row["density"], row["n"],
                 "%.1f" % row["raw_recovery"] if row["raw_recovery"] is not None else "None",
                 "%.1f" % row["std_recovery"] if row["std_recovery"] is not None else "None",
                 row["n_strata_used"],
                 "%.1f" % row["ci_lo_raw"] if row["ci_lo_raw"] is not None else "None",
                 "%.1f" % row["ci_hi_raw"] if row["ci_hi_raw"] is not None else "None"))
    result["shape"] = shape_rows

    with io.open("qa/cycleframer-alignment-replay/x2_result.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("\nWrote qa/cycleframer-alignment-replay/x2_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
