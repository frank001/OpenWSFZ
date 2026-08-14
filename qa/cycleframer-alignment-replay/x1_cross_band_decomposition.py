#!/usr/bin/env python3
"""X1 -- cross-band recovery decomposition (20m / 17m / 80m).

Spec: qa/cycleframer-alignment-replay/2026-08-10-1538-architect-to-qa-spec-x1-cross-band-recovery-decomposition.md
Pre-registered gate per HK-021; rows mutually exclusive, strict order, boundary values fall
to the inconclusive row (see row_verdict() below, copied verbatim from the spec's own S4
pseudocode).

Question: is "band" a real term in OpenWSFZ's recovery deficit, once density and SNR
composition are matched exactly, or is it entirely composition?

Reuses t1_frequency_quantisation.load() UNMODIFIED (spec S3) so the population is provably
the one the rest of the programme uses. No src/ change. No capture. Pure re-analysis of
ALL.TXT already on disk -- the 80m leg's wsjt-x/ALL.TXT was repaired under this same spec's
X0 (see artefacts/20260809_live_run_0155-8081-80m/contents.md, "X0 repair" section) before
this harness was written; it was a hardlink duplicate of the -8080 leg's FT991A file, not an
independent second reference instance.

Definitions (spec S3), mechanical, no judgement:
  - Population REF = A n B on (ts, message), then two exclusions applied symmetrically and
    identically on every band: drop messages containing "<...>", and drop rows whose
    REFERENCE frequency (always ref-A's, per t1 convention) falls outside 200-3000 Hz.
  - Density: per cycle, count of REF rows in that cycle. Cycle-level property, NOT binned
    (HK-021(f): it is discrete).
  - SNR: always the reference's (ref-A's) reported SNR, never ours (DEFECT-snr-reported-gain-
    error.md -- our own SNR carries a band-dependent gain error).
  - Strata fixed GLOBALLY (HK-021(g)): SNR quantile edges computed ONCE from the pooled
    three-band REF SNR distribution, never re-derived per band or per sub-stratum.
  - The ladder: L1 = exact density x SNR quintile, L2 = exact density x SNR decile,
    L3 = exact density x SNR 20-tile. All three always reported.

Uncertainty (HK-021(i), non-negotiable): the unit of observation is a decode; the unit of
independence is a CYCLE (density is a cycle property; decodes within a cycle share a
propagation instant). Cycle-clustered bootstrap, 1000 draws, fixed seed, resampling whole
cycles WITHIN each band independently and recomputing cells/B_std on every draw. A binomial
SE is forbidden here.
"""
import collections
import io
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_frequency_quantisation import load  # noqa: E402  -- reused unmodified, per spec S3

SEED = 20260810          # fixed seed, HK-021 -- every run must reproduce bit-for-bit
N_BOOT = 1000
MIN_CELL = 10
LEVELS = ("L1", "L2", "L3")
LEVEL_K = {"L1": 5, "L2": 10, "L3": 20}   # quintile / decile / 20-tile

LEGS = {
    "20m": {
        "window": ("260808_004000", "260808_111500"),
        "owsfz8080": "artefacts/20260808_live_run_0016-8080/owsfz/ALL.TXT",
        "owsfz8081": "artefacts/20260808_live_run_0016-8081/owsfz/ALL.TXT",
        "ref_a": "artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT",
        "ref_b": "artefacts/20260808_live_run_0016-8081/wsjt-x/ALL.TXT",
    },
    "17m": {
        "window": ("260808_120000", "260808_193900"),
        "owsfz8080": "artefacts/20260808_live_run_1154-8080-17m/owsfz/ALL.TXT",
        "owsfz8081": "artefacts/20260808_live_run_1154-8081-17m/owsfz/ALL.TXT",
        "ref_a": "artefacts/20260808_live_run_1154-8080-17m/wsjt-x/ALL.TXT",
        "ref_b": "artefacts/20260808_live_run_1154-8081-17m/wsjt-x/ALL.TXT",
    },
    "80m": {
        "window": ("260809_015445", "260809_072815"),
        "window_alt_end": "260809_101100",   # ROW 0e mechanical check -- must yield same REF
        "owsfz8080": "artefacts/20260809_live_run_0155-8080-80m/owsfz/ALL.TXT",
        "owsfz8081": "artefacts/20260809_live_run_0155-8081-80m/owsfz/ALL.TXT",
        "ref_a": "artefacts/20260809_live_run_0155-8080-80m/wsjt-x/ALL.TXT",
        "ref_b": "artefacts/20260809_live_run_0155-8081-80m/wsjt-x/ALL.TXT",
    },
}

# ROW 0b -- these are T1/T2's own numbers; a mismatch means the loader or window drifted.
EXPECT_CLEAN_REF = {"20m": 67243, "17m": 38047}

PAIRS_ALL = [("80m", "20m"), ("17m", "20m"), ("80m", "17m")]
PRIMARY_PAIR = ("80m", "20m")


# ── population / exclusions ─────────────────────────────────────────────────────────────

def has_unresolved_hash(msg):
    return "<...>" in msg


def quantile_edges(values, k):
    """k-tile cut points (k-1 boundaries), nearest-rank -- generalises t1's quintile_edges."""
    s = sorted(values)
    n = len(s)
    return [s[int(n * i / k)] for i in range(1, k)]


def assign_stratum(v, edges):
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def load_band_raw(name):
    cfg = LEGS[name]
    lo, hi = cfg["window"]
    a = load(cfg["ref_a"], lo, hi)
    b = load(cfg["ref_b"], lo, hi)
    o8080 = load(cfg["owsfz8080"], lo, hi)
    o8081 = load(cfg["owsfz8081"], lo, hi)
    return a, b, o8080, o8081


def clean_population(a, b):
    """A n B, then the two pre-registered exclusions, applied off reference-A's fields
    (matches t1_frequency_quantisation's own convention: reference frequency/SNR always
    from the SAME-FOLDER WSJT-X instance as the OpenWSFZ side being scored)."""
    ref_raw = set(a) & set(b)
    excl_hash = excl_band = 0
    kept = []
    for k in ref_raw:
        ts, msg = k
        if has_unresolved_hash(msg):
            excl_hash += 1
            continue
        snr, freq_hz = a[k]
        if not (200 <= freq_hz <= 3000):
            excl_band += 1
            continue
        kept.append(k)
    return ref_raw, kept, excl_hash, excl_band


# ── per-band row / cycle aggregation ────────────────────────────────────────────────────

class Band:
    __slots__ = ("name", "n_a_raw", "n_ref_raw", "kept", "n_ref_clean", "excl_hash",
                 "excl_band", "rows", "cycles", "density_by_cycle",
                 "cycle_agg", "point_cells", "boot_cells")

    def __init__(self, name):
        self.name = name


def build_band(name):
    band = Band(name)
    a, b, o8080, o8081 = load_band_raw(name)
    ref_raw, kept, excl_hash, excl_band = clean_population(a, b)
    band.n_a_raw = len(a)
    band.n_ref_raw = len(ref_raw)
    band.kept = kept
    band.n_ref_clean = len(kept)
    band.excl_hash = excl_hash
    band.excl_band = excl_band

    # density = per-cycle count of REF (kept) rows -- a cycle property.
    density_by_cycle = collections.Counter(ts for ts, _ in kept)

    rows = []
    for k in kept:
        ts, msg = k
        snr, freq_hz = a[k]
        rows.append({
            "ts": ts,
            "snr": snr,
            "freq_hz": freq_hz,
            "density": density_by_cycle[ts],
            "matched8080": k in o8080,
            "matched8081": k in o8081,
        })
    band.rows = rows
    band.density_by_cycle = dict(density_by_cycle)
    band.cycles = sorted(density_by_cycle)
    return band


def assign_all_strata(bands, pooled_snr_edges):
    """Attach strat={"L1":.., "L2":.., "L3":..} to every row, from the GLOBAL pooled edges
    (HK-021(g) -- fixed once, never re-derived per band)."""
    for band in bands.values():
        for r in band.rows:
            r["strat"] = {lvl: assign_stratum(r["snr"], pooled_snr_edges[lvl]) for lvl in LEVELS}


def build_cycle_agg(band):
    """{level: {cycle_ts: {stratum: [n, matched8080, matched8081]}}}"""
    per_level = {lvl: collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
                 for lvl in LEVELS}
    for r in band.rows:
        for lvl in LEVELS:
            e = per_level[lvl][r["ts"]][r["strat"][lvl]]
            e[0] += 1
            e[1] += 1 if r["matched8080"] else 0
            e[2] += 1 if r["matched8081"] else 0
    # freeze to plain dicts (defaultdicts are fine but plain dicts are less surprising downstream)
    return {lvl: {ts: dict(strata) for ts, strata in cyc.items()} for lvl, cyc in per_level.items()}


def aggregate_cells(cycle_mult, density_by_cycle, level_agg, sut):
    """cycle_mult: {ts: multiplicity} -- 1 for every cycle at the point estimate, bootstrap
    resample counts otherwise. Returns {(density, stratum): [n, matched]}."""
    idx = 1 if sut == "8080" else 2
    out = collections.defaultdict(lambda: [0, 0])
    for ts, mult in cycle_mult.items():
        strat_counts = level_agg.get(ts)
        if not strat_counts:
            continue
        density = density_by_cycle[ts]
        for stratum, vals in strat_counts.items():
            cell = out[(density, stratum)]
            cell[0] += vals[0] * mult
            cell[1] += vals[idx] * mult
    return dict(out)


# ── primary metric (spec S3, verbatim) ──────────────────────────────────────────────────

def b_std(cells_a, cells_b, min_cell=MIN_CELL):
    """Coverage-weighted standardised recovery difference, band A minus band B."""
    common = [c for c in cells_a
              if c in cells_b and cells_a[c][0] >= min_cell and cells_b[c][0] >= min_cell]
    w = sum(cells_a[c][0] + cells_b[c][0] for c in common)
    if w == 0:
        return None
    return sum((cells_a[c][0] + cells_b[c][0]) *
               (100.0 * cells_a[c][1] / cells_a[c][0] - 100.0 * cells_b[c][1] / cells_b[c][0])
               for c in common) / w


def coverage(cells_a, cells_b, n_ref_a, n_ref_b, min_cell=MIN_CELL):
    """Share of the SMALLER band's REF that lies inside common support."""
    common = [c for c in cells_a
              if c in cells_b and cells_a[c][0] >= min_cell and cells_b[c][0] >= min_cell]
    smaller_cells, smaller_n = (cells_a, n_ref_a) if n_ref_a <= n_ref_b else (cells_b, n_ref_b)
    if smaller_n == 0:
        return None
    return sum(smaller_cells[c][0] for c in common) / smaller_n


# ── cycle-clustered bootstrap ───────────────────────────────────────────────────────────

def bootstrap_cell_replicates(band, level, sut, rng, n_boot=N_BOOT):
    """1000 cell-dict replicates, resampling whole cycles WITH replacement, independently
    per band (HK-021(i)). Returns a list of {(density, stratum): [n, matched]} dicts."""
    cycles = band.cycles
    level_agg = band.cycle_agg[level]
    out = []
    for _ in range(n_boot):
        draw = collections.Counter(rng.choices(cycles, k=len(cycles)))
        out.append(aggregate_cells(draw, band.density_by_cycle, level_agg, sut))
    return out


def percentile(sorted_vals, p):
    n = len(sorted_vals)
    idx = max(0, min(n - 1, int(round(p * (n - 1)))))
    return sorted_vals[idx]


# ── main analysis ───────────────────────────────────────────────────────────────────────

def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    result = {}

    print("=" * 88)
    print("X1 -- cross-band recovery decomposition (20m / 17m / 80m)")
    print("=" * 88)

    # ---- ROW 0a part 1: 80m wsjt-x/ALL.TXT inode check ----
    ino_a = os.stat(LEGS["80m"]["ref_a"]).st_ino
    ino_b = os.stat(LEGS["80m"]["ref_b"]).st_ino
    same_inode = ino_a == ino_b
    print("\nROW 0a (basis) -- 80m wsjt-x/ALL.TXT inodes: A=%d B=%d  %s"
          % (ino_a, ino_b, "SAME (X0 NOT repaired!)" if same_inode else "distinct (repaired)"))

    # ---- ROW 0e: 80m window-end integrity, BEFORE building the band (uses the primary window) ----
    a80_alt = load(LEGS["80m"]["ref_a"], LEGS["80m"]["window"][0], LEGS["80m"]["window_alt_end"])
    b80_alt = load(LEGS["80m"]["ref_b"], LEGS["80m"]["window"][0], LEGS["80m"]["window_alt_end"])
    ref_alt = set(a80_alt) & set(b80_alt)

    print("\nBuilding bands (load + clean population)...")
    bands = {name: build_band(name) for name in LEGS}

    # The raw (uncleaned) A n B intersection at the primary window end is already computed
    # as bands["80m"].n_ref_raw -- reuse it rather than recomputing.
    ref_primary_raw = bands["80m"].n_ref_raw
    row0e_identical = (ref_primary_raw == len(ref_alt))
    print("ROW 0e -- 80m REF (raw A n B): window end 072815 = %d, window end 101100 = %d -> %s"
          % (ref_primary_raw, len(ref_alt), "IDENTICAL" if row0e_identical else "DIFFERS -- VOID"))

    print("\nPopulation summary:")
    row0a_ratio_ok = True
    for name, band in bands.items():
        ratio = band.n_ref_raw / band.n_a_raw if band.n_a_raw else 0.0
        ok = ratio >= 0.95
        row0a_ratio_ok = row0a_ratio_ok and ok
        print("  %-4s  |A|=%6d  |A^B| raw=%6d (ratio=%.4f %s)  clean=%6d  "
              "(excl hash=%d, out-of-band=%d)  cycles=%d"
              % (name, band.n_a_raw, band.n_ref_raw, ratio, "OK" if ok else "FAIL",
                 band.n_ref_clean, band.excl_hash, band.excl_band, len(band.cycles)))

    row0a = (not same_inode) and row0a_ratio_ok
    print("\n>>> ROW 0a: %s <<<" % ("PASS" if row0a else "VOID"))

    row0b_checks = {}
    for name, expect in EXPECT_CLEAN_REF.items():
        actual = bands[name].n_ref_clean
        row0b_checks[name] = (actual == expect)
        print("ROW 0b -- %s clean REF: expected %d, actual %d -> %s"
              % (name, expect, actual, "MATCH" if row0b_checks[name] else "MISMATCH -- VOID"))
    row0b = all(row0b_checks.values())
    print(">>> ROW 0b: %s <<<" % ("PASS" if row0b else "VOID"))

    print(">>> ROW 0e: %s <<<" % ("PASS" if row0e_identical else "VOID"))

    void = not (row0a and row0b and row0e_identical)
    result["row0"] = {
        "row0a_pass": row0a, "row0a_same_inode": same_inode, "row0a_ratio_ok": row0a_ratio_ok,
        "row0b_pass": row0b, "row0b_checks": row0b_checks,
        "row0e_pass": row0e_identical,
        "row0e_ref_072815": ref_primary_raw, "row0e_ref_101100": len(ref_alt),
    }

    if void:
        print("\n" + "!" * 88)
        print("X1 is VOID under ROW 0a/0b/0e -- no row may be cited. Stopping.")
        print("!" * 88)
        with io.open("qa/cycleframer-alignment-replay/x1_result.json", "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        return 1

    # ---- pooled global SNR strata edges (HK-021(g)) ----
    pooled_snr = []
    for band in bands.values():
        pooled_snr.extend(r["snr"] for r in band.rows)
    pooled_snr_edges = {lvl: quantile_edges(pooled_snr, LEVEL_K[lvl]) for lvl in LEVELS}
    print("\nPooled SNR strata edges (n=%d, fixed globally):" % len(pooled_snr))
    for lvl in LEVELS:
        print("  %s (%d-tile): %s" % (lvl, LEVEL_K[lvl], pooled_snr_edges[lvl]))

    assign_all_strata(bands, pooled_snr_edges)
    for band in bands.values():
        band.cycle_agg = build_cycle_agg(band)
        band.point_cells = {
            lvl: {
                "8080": aggregate_cells({ts: 1 for ts in band.cycles}, band.density_by_cycle,
                                         band.cycle_agg[lvl], "8080"),
                "8081": aggregate_cells({ts: 1 for ts in band.cycles}, band.density_by_cycle,
                                         band.cycle_agg[lvl], "8081"),
            } for lvl in LEVELS
        }

    # ---- cycle-clustered bootstrap replicates, per band per level, SUT=8080 ----
    print("\nRunning cycle-clustered bootstrap (%d draws, seed=%d)..." % (N_BOOT, SEED))
    rng = random.Random(SEED)
    for name, band in bands.items():
        band.boot_cells = {}
        for lvl in LEVELS:
            band.boot_cells[lvl] = bootstrap_cell_replicates(band, lvl, "8080", rng)
        print("  %s done" % name)

    # ---- ladder table: every pair, every level ----
    print("\n" + "=" * 88)
    print("LADDER -- B_std (band_A - band_B), coverage, cycle-clustered 95% CI")
    print("=" * 88)
    ladder = {}
    for pa, pb in PAIRS_ALL:
        ladder[f"{pa}-{pb}"] = {}
        print("\n%s minus %s:" % (pa, pb))
        for lvl in LEVELS:
            ca = bands[pa].point_cells[lvl]["8080"]
            cb = bands[pb].point_cells[lvl]["8080"]
            point = b_std(ca, cb)
            cov = coverage(ca, cb, bands[pa].n_ref_clean, bands[pb].n_ref_clean)
            boot_vals = sorted(
                v for v in (b_std(bca, bcb) for bca, bcb in
                            zip(bands[pa].boot_cells[lvl], bands[pb].boot_cells[lvl]))
                if v is not None
            )
            se = statistics.pstdev(boot_vals) if len(boot_vals) > 1 else float("nan")
            ci_lo = percentile(boot_vals, 0.025) if boot_vals else float("nan")
            ci_hi = percentile(boot_vals, 0.975) if boot_vals else float("nan")
            ladder[f"{pa}-{pb}"][lvl] = {
                "b_std": point, "coverage": cov, "se": se, "ci_lo": ci_lo, "ci_hi": ci_hi,
                "n_boot_valid": len(boot_vals),
            }
            print("  %s  B_std=%+7.2f pp  coverage=%5.1f%%  SE=%.3f pp  95%% CI=[%+.2f, %+.2f] pp  (n_boot=%d)"
                  % (lvl, point, 100 * cov if cov is not None else float("nan"), se, ci_lo, ci_hi,
                     len(boot_vals)))
    result["ladder"] = ladder

    # ---- ROW 0c (identifiability) / ROW 0d (power), per pair being read ----
    print("\n" + "=" * 88)
    print("ROW 0c/0d -- identifiability and power, per pair")
    print("=" * 88)
    pair_status = {}
    for pa, pb in PAIRS_ALL:
        key = f"{pa}-{pb}"
        covs = {lvl: ladder[key][lvl]["coverage"] for lvl in LEVELS}
        identifiable = all(c is not None and c >= 0.60 for c in covs.values())
        se_l1 = ladder[key]["L1"]["se"]
        powered = se_l1 <= 1.5
        pair_status[key] = {"identifiable": identifiable, "powered": powered, "coverage": covs, "se_l1": se_l1}
        print("  %-10s  coverage L1/L2/L3 = %s  -> %s   SE(L1)=%.3f pp -> %s"
              % (key, {lvl: "%.1f%%" % (100 * c) for lvl, c in covs.items()},
                 "IDENTIFIABLE" if identifiable else "NOT IDENTIFIABLE (instrument failure)",
                 se_l1, "POWERED" if powered else "UNDERPOWERED (instrument failure)"))
    result["row0cd"] = pair_status

    # ---- ROW 1/2/3 gate on the primary pair, verbatim from spec S4 ----
    print("\n" + "=" * 88)
    print("PRIMARY GATE -- 80m vs 20m")
    print("=" * 88)
    pa, pb = PRIMARY_PAIR
    key = f"{pa}-{pb}"
    if not (pair_status[key]["identifiable"] and pair_status[key]["powered"]):
        gate_row = "ROW 0c/0d -- INSTRUMENT FAILURE, not a null. No row may be cited."
        print(gate_row)
        result["gate"] = {"row": gate_row}
    else:
        b1 = abs(ladder[key]["L1"]["b_std"])
        b3 = abs(ladder[key]["L3"]["b_std"])
        ci_lo, ci_hi = ladder[key]["L1"]["ci_lo"], ladder[key]["L1"]["ci_hi"]

        if b1 >= 3.0 and b3 >= 0.5 * b1 and not (ci_lo <= 0 <= ci_hi):
            gate_row = "ROW 1"
        elif b1 <= 1.0 or b3 <= 0.3 * b1:
            gate_row = "ROW 2"
        else:
            gate_row = "ROW 3"
        print("b1 (|B_std| L1) = %.3f pp" % b1)
        print("b3 (|B_std| L3) = %.3f pp  (%.1f%% of b1)" % (b3, 100 * b3 / b1 if b1 else float("nan")))
        print("L1 95%% CI = [%+.3f, %+.3f] pp  (excludes 0: %s)" % (ci_lo, ci_hi, not (ci_lo <= 0 <= ci_hi)))
        print("\n>>> %s <<<" % gate_row)
        result["gate"] = {"row": gate_row, "b1": b1, "b3": b3, "ci_lo": ci_lo, "ci_hi": ci_hi}

    # ---- replicate check: 8081 as SUT, primary pair, L1 ----
    print("\n" + "=" * 88)
    print("REPLICATE CHECK -- OpenWSFZ 8081 as SUT, primary pair, L1 (reported, not gated)")
    print("=" * 88)
    ca80 = bands[pa].point_cells["L1"]["8081"]
    cb80 = bands[pb].point_cells["L1"]["8081"]
    b_std_8081 = b_std(ca80, cb80)
    b_std_8080 = ladder[key]["L1"]["b_std"]
    replicate_diff = abs(b_std_8080 - b_std_8081) if (b_std_8080 is not None and b_std_8081 is not None) else None
    print("B_std(8080, L1) = %+.3f pp" % b_std_8080)
    print("B_std(8081, L1) = %+.3f pp" % b_std_8081)
    print("|difference|    = %.3f pp  -> %s" %
          (replicate_diff, "STABLE" if (replicate_diff is not None and replicate_diff <= 1.0) else "FLAG: unstable"))
    result["replicate"] = {"b_std_8080": b_std_8080, "b_std_8081": b_std_8081, "diff": replicate_diff}

    with io.open("qa/cycleframer-alignment-replay/x1_result.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("\nWrote qa/cycleframer-alignment-replay/x1_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
