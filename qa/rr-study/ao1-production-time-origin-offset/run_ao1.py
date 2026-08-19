#!/usr/bin/env python3
"""AO1 -- the production time-origin offset. Part B (the offset) and Part C
(recall cost), run in the pre-registration's own Sec.11 execution order.

Spec: qa/rr-study/2026-08-19-1058-architect-to-qa-prereg-ao1-production-time-origin-offset.md
("the spec", all Sec. references below are to it unless stated otherwise).

WHAT THIS RUNS, Sec.11 order:
  1. ROW 0a  -- DLL SHA256 re-hashed from disk, asserted against the pin, before arming.
  2. Build the matched-pair population on PRIMARY (Sec.4), draw the seeded K-sample,
     load contexts from OUR OWN archived audio (owsfz/wav/<ts>.wav).
  3. ROW 0e  -- mandatory sign unit test, Stage 2's OWN construction reused VERBATIM
     (run_stage2.run_sign_test / _pooled_argmin) -- it already passed both signs
     there, and exercises the identical extraction code path the K sweep uses.
  4. ROW 0b  -- matched-pair dry count (rows AND clusters) on the full population.
  5. ROW 0c  -- reference dt grid-lock plausibility check.
  6. Compute R on the FULL matched population, cluster-bootstrapped, SIGNED.
  7. Sweep K on the seeded sample (>=600 rows), our own audio, M3's 49-point grid
     (REUSED verbatim via run_stage2.sweep_matrix/pooled_curve/argmin_curve).
  8. ROW 0d  -- median BER_V0 at K's argmin, two-sided plausibility.
  9. ROW 0f  -- 4 chronological ts-quartiles' own argmin vs pooled K.
 10. ROW 0g  -- reference SNR-field parseability (gates Part C only).
 11. Part B main rows 1-5, strict order, over (|R|, |K|, signs).
 12. Part C (Sec.7) -- ONLY if ROW 3 fired and ROW 0f cleared; 0g downgrades to
     descriptive/non-gating rather than blocking, per Sec.5's own table.
 13. Descriptive replication of R (and K, if affordable) on the THREE extension
     corpora AO1 actually uses (Sec.4 excludes both -8081 legs) -- per corpus,
     NEVER pooled, gates nothing (HK-021(k)).
 14. Report. STOP.

NFR-021: message TEXT is used in-process only (ExtractLLRs.true_codeword, inside
load_row_context) and is NEVER written to any row dict, JSON file, or log line
this module produces. Every emitted file is grepped individually for "message"
after the run.

No src/, no Developer session, no DLL rebuild, no capture run -- HK-011 not engaged.
"""
from __future__ import annotations

import argparse
import collections
import os
import statistics as st
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402,F401
from m3_common import STRATA, stratum_of as m3_stratum_of, TIME_ANCHOR_OFFSETS_S  # noqa: E402
from n1_stats import cluster_bootstrap_median_diff  # noqa: E402 -- Sec.4: reused verbatim
from run_stage1 import DEFAULT_DLL_PATH, DEFAULT_DLL_SHA256, EXPECTED_SHIM_VERSION, WavCache  # noqa: E402
from run_stage1r import deterministic_sample  # noqa: E402 -- same seeded, sort-stabilised sample
from run_stage2 import (  # noqa: E402 -- Sec.11 step 3: reused verbatim
    argmin_curve, pooled_curve, run_sign_test, sweep_matrix,
)

from ao1_common import (  # noqa: E402
    PRIMARY_CORPUS, build_matched_pairs, build_reference_population, corpus_paths,
)

# -- Sec.4: the three extension corpora AO1 actually replicates on -- both -8081
# legs are EXCLUDED (same cycles as their -8080 twin at median Jaccard ~1.000,
# and 0155-80m's -8081 additionally carries the G1 hardlink defect).
AO1_EXTENSION_CORPORA = [
    "20260808_live_run_0016-8080",
    "20260808_live_run_1154-8080-17m",
    "20260809_live_run_0155-8080-80m",
]

# -- Sec.4/Sec.11: this run's own seed, distinct from every prior arm's --------
AO1_SEED = 20260819
SAMPLE_ROWS = 600

# -- Sec.5 bars, derived not chosen (see spec for derivation) ------------------
ROW_0B_MIN_ROWS = 2000
ROW_0B_MIN_CLUSTERS = 500
ROW_0C_LO, ROW_0C_HI = -0.35, 0.35
ROW_0D_LO, ROW_0D_HI = 0.01, 0.15
ROW_0F_TOL_S = 0.05
ROW_0G_MAX_FRAC = 0.05
THETA = 0.10          # Sec.5: reporting resolution of the reference instrument
ROW_3_K_MINUS_R_TOL = 0.15

# -- Sec.7 Part C bars -----------------------------------------------------------
PART_C_MIN_SE_RESOLUTION_PP = 1.0   # C0: 1.96*SE >= this -> underpowered
PART_C_C1_MIN_PP = 2.0
PART_C_C2_MIN_PP = 0.2
PART_C_C4_MAX_PP = -0.2
PART_C_MIN_CELL = 10                # X1's own MIN_CELL, reused verbatim (Sec.7: "the
                                     # standardisation method already proven in X1/X2")
PART_C_N_BOOT = 2000

DT_STRATA_EDGES = [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


# =============================================================================
# HK-025 -- independent re-classification, per Sec.6's own instruction to treat
# the spec's table as a claim to check, not a conclusion to adopt.
# =============================================================================

def hk025_check() -> dict:
    """Re-derived fresh against Sec.6's table, not copied from it.

    0a: fires -> unidentified binary, every number describes an unknown build.
        Clears -> pinned build. VALIDITY, branches differ, not diagnostic.
    0b: fires -> CI cannot separate theta=0.10s. Clears -> powered. PRECISION,
        branches differ (STOP either way per Sec.5's own table, but the STOP is
        the SAME action Sec.5 assigns regardless of this row's own class --
        HK-025 asks whether fired vs cleared differ, and they do: escalate-as-
        underpowered vs proceed-to-measure).
    0c: fires -> reference's own grid lock is in question, R measures an unknown
        sum of two origins. Clears -> reference is the grid. VALIDITY, differ.
    0d: fires -> the sweep is not reading (K's argmin is noise, not a position).
        Clears -> K is a position. VALIDITY, differ.
    0e: fires -> sweep sign convention unverified, K's sign uninterpretable, and
        sign drives ROWS 3/4/5. Clears -> sign verified. VALIDITY, differ.
    0f: fires -> offset is not one constant; a POOLED K is a mixture, but a
        per-quartile K is still an estimate -- Part B still reports (per spec's
        own table), only Part C is withheld. Clears -> constant. PRECISION,
        differ (Part C withheld vs eligible).
    0g: fires -> Part C cannot control SNR, becomes descriptive/non-gating; Part
        B is UNAFFECTED either way. Clears -> Part C gated normally. PRECISION,
        scoped to Part C only, differ.

    No row evaluates to the same downstream action on both branches -> no
    HK-021(k) diagnostic row here, no HK-025 refusal. Concurs with Sec.6."""
    reasons = {
        "0a": ("VALIDITY", "unidentified binary invalidates every downstream number"),
        "0b": ("PRECISION", "underpowered to resolve theta -- escalate vs proceed to measure"),
        "0c": ("VALIDITY", "reference's own grid lock in question -- R would measure an "
               "unknown sum of two origins, not ours"),
        "0d": ("VALIDITY", "sweep argmin is noise, not a position"),
        "0e": ("VALIDITY", "sign convention unverified, and sign drives ROWS 3/4/5"),
        "0f": ("PRECISION", "offset not one constant -- Part C withheld, Part B still reports"),
        "0g": ("PRECISION", "Part C loses SNR control and becomes descriptive only; "
               "Part B unaffected"),
    }
    classification = {k: {"class": c, "reason": r} for k, (c, r) in reasons.items()}
    return {"classification": classification, "refusal": False, "concurs_with_spec": True}


# =============================================================================
# Context loading -- our OWN archived audio (owsfz/wav), anchored at the
# REFERENCE's reported (freq, dt) -- Sec.4's K definition.
# =============================================================================

def load_row_context(ex: ExtractLLRs, wav_cache: WavCache, pair: dict):
    """Returns ((ts, pcm, true_bits, freq_int, anchor_dt), None) or (None, reason).
    message text touches this function only via ex.true_codeword and is never
    retained past this call (NFR-021)."""
    try:
        pcm = wav_cache.get(pair["ts"])
    except FileNotFoundError:
        return None, "no_wav"
    true_bits = ex.true_codeword(pair["message"])
    if true_bits is None:
        return None, "no_true_codeword"
    freq_int = round(pair["ref_freq_hz"])  # reference's own reported freq is already int Hz
    anchor_dt = float(pair["ref_dt"])      # anchor = REFERENCE's (freq, dt), Sec.4
    return (pair["ts"], pcm, true_bits, freq_int, anchor_dt), None


def load_contexts_for_sample(ex: ExtractLLRs, owsfz_wav_dir: str, sample: list[dict], log) -> tuple[list, dict]:
    wav_cache = WavCache(owsfz_wav_dir)
    contexts = []
    drop_reasons: dict[str, int] = {}
    for pair in sample:
        ctx, reason = load_row_context(ex, wav_cache, pair)
        if ctx is None:
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
            continue
        contexts.append(ctx)
    log("  n_measured=%d/%d n_clusters_measured=%d drop_reasons=%s"
        % (len(contexts), len(sample), len({c[0] for c in contexts}), drop_reasons))
    return contexts, drop_reasons


# =============================================================================
# Part C -- SNR/dt standardisation, X1's b_std formula reproduced locally
# (Sec.7: "the standardisation method already proven in X1/X2").
# =============================================================================

def snr_stratum_of(snr_db: float) -> int:
    """Wraps m3_common.stratum_of with a clamp at the low end -- m3's STRATA
    bottom bin is [-24,-21); it would assert on anything below -24. Measured
    range on PRIMARY's reference population is exactly [-24, 29], so this clamp
    is a defensive no-op there, but extension corpora are not pre-checked."""
    if snr_db < STRATA[0][0]:
        return 0
    return m3_stratum_of(snr_db)


def dt_stratum_of(dt: float) -> int:
    edges = DT_STRATA_EDGES
    if dt < edges[0]:
        return 0
    for i in range(len(edges) - 1):
        if edges[i] <= dt < edges[i + 1]:
            return i
    return len(edges) - 2  # clamp to the last bin


def dt_stratum_label(i: int) -> str:
    return "[%.1f,%.1f)" % (DT_STRATA_EDGES[i], DT_STRATA_EDGES[i + 1])


def build_cycle_cells(ref_population: list[dict]) -> dict:
    """{ts: {(snr_idx, dt_idx): [n, matched]}}, rows with unparseable SNR excluded
    (ROW 0g's own concern -- those rows cannot be stratified by SNR at all)."""
    out: dict = {}
    for r in ref_population:
        if r["snr"] is None:
            continue
        key = (snr_stratum_of(r["snr"]), dt_stratum_of(r["dt"]))
        cell = out.setdefault(r["ts"], {}).setdefault(key, [0, 0])
        cell[0] += 1
        if r["recovered"]:
            cell[1] += 1
    return out


def aggregate_cells(cycle_cells: dict, ts_mult: dict) -> dict:
    out: dict = {}
    for ts, mult in ts_mult.items():
        cc = cycle_cells.get(ts)
        if not cc:
            continue
        for key, (n, m) in cc.items():
            cell = out.setdefault(key, [0, 0])
            cell[0] += n * mult
            cell[1] += m * mult
    return out


def cells_for_dt(cells: dict, d_idx: int) -> dict:
    return {s: v for (s, d), v in cells.items() if d == d_idx}


def std_diff(cells_a: dict, cells_b: dict, min_cell: int) -> "float | None":
    """Identical formula to x1_cross_band_decomposition.b_std -- coverage-
    weighted standardised recovery difference (a minus b, in pp), reproduced
    locally to avoid pulling that module's corpus-specific setup code."""
    common = [s for s in cells_a if s in cells_b
              and cells_a[s][0] >= min_cell and cells_b[s][0] >= min_cell]
    w = sum(cells_a[s][0] + cells_b[s][0] for s in common)
    if w == 0:
        return None
    return sum((cells_a[s][0] + cells_b[s][0]) *
               (100.0 * cells_a[s][1] / cells_a[s][0] - 100.0 * cells_b[s][1] / cells_b[s][0])
               for s in common) / w


def compute_L(cells: dict, modal_d: int, min_cell: int = PART_C_MIN_CELL):
    """Sec.7: 'within each SNR stratum, compare each dt stratum's recovery
    against the modal dt stratum's, weight by the dt stratum's share of the
    reference population, and sum.' SIGNED so that positive = cost (modal
    recovers BETTER than the non-modal stratum, per Sec.7's C1 'material recall
    cost' / C4 'the offset APPEARS to help' framing).

    Returns (L, coverage) or (None, None) if the modal cell itself is empty."""
    dt_indices = sorted({d for (_s, d) in cells})
    total_n = sum(v[0] for v in cells.values())
    if total_n == 0 or modal_d not in dt_indices:
        return None, None
    modal_cells = cells_for_dt(cells, modal_d)
    covered_n = sum(v[0] for (s, d), v in cells.items() if d == modal_d)
    l_sum = 0.0
    for d in dt_indices:
        if d == modal_d:
            continue
        cd = cells_for_dt(cells, d)
        diff = std_diff(modal_cells, cd, min_cell)  # modal - d: positive = d costs recall
        if diff is None:
            continue
        n_d = sum(v[0] for v in cd.values())
        l_sum += (n_d / total_n) * diff
        covered_n += n_d
    return l_sum, covered_n / total_n


def run_part_c(ref_population: list[dict], log) -> dict:
    log("\n" + "=" * 90)
    log("PART C -- recall cost at matched SNR (Sec.7)")
    log("=" * 90)

    n_snr_none = sum(1 for r in ref_population if r["snr"] is None)
    usable = [r for r in ref_population if r["snr"] is not None]
    log("  reference population: n=%d, SNR-unparseable dropped=%d, usable=%d"
        % (len(ref_population), n_snr_none, len(usable)))

    cycle_cells = build_cycle_cells(ref_population)
    ts_list = sorted(cycle_cells)
    n_clusters = len(ts_list)

    point_cells = aggregate_cells(cycle_cells, {ts: 1 for ts in ts_list})
    dt_totals = collections.defaultdict(int)
    for (s, d), (n, _m) in point_cells.items():
        dt_totals[d] += n
    if not dt_totals:
        log("  no usable cells at all -- cannot evaluate Part C.")
        return {"evaluated": False, "reason": "no_usable_cells"}
    modal_d = max(dt_totals, key=lambda d: dt_totals[d])
    log("  modal dt stratum: %s (n=%d, %.1f%% of usable rows)"
        % (dt_stratum_label(modal_d), dt_totals[modal_d], 100.0 * dt_totals[modal_d] / len(usable)))

    dt_breakdown = {dt_stratum_label(d): n for d, n in sorted(dt_totals.items())}
    log("  dt-stratum row counts: %s" % dt_breakdown)

    l_point, coverage = compute_L(point_cells, modal_d)
    if l_point is None:
        log("  modal cell itself empty at the point estimate -- cannot evaluate Part C.")
        return {"evaluated": False, "reason": "modal_cell_empty"}
    log("  L (point estimate) = %+.3fpp, coverage=%.1f%% of usable rows in a defined cell"
        % (l_point, coverage * 100))

    rng = np.random.default_rng(AO1_SEED)
    draws = []
    for _ in range(PART_C_N_BOOT):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        mult = collections.Counter(ts_list[i] for i in pick)
        cells_draw = aggregate_cells(cycle_cells, mult)
        l_draw, _cov = compute_L(cells_draw, modal_d)
        if l_draw is not None:
            draws.append(l_draw)
    arr = np.array(draws)
    se = float(arr.std(ddof=1)) if len(arr) > 1 else float("nan")
    ci95 = [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))] if len(arr) else [float("nan")] * 2
    resolution = 1.96 * se
    log("  bootstrap: n_draws=%d n_clusters=%d SE=%.3fpp CI95=[%+.3f,%+.3f]pp 1.96*SE=%.3fpp"
        % (len(arr), n_clusters, se, ci95[0], ci95[1], resolution))

    result = {
        "evaluated": True, "l_point": l_point, "coverage": coverage,
        "se": se, "ci95": ci95, "resolution_1_96se": resolution,
        "n_draws": len(arr), "n_clusters": n_clusters, "modal_dt_stratum": dt_stratum_label(modal_d),
        "dt_stratum_row_counts": dt_breakdown, "n_snr_unparseable": n_snr_none,
    }

    log("\nROW C0 first, strict: 1.96*SE=%.3fpp (bound <%.1fpp) -> %s"
        % (resolution, PART_C_MIN_SE_RESOLUTION_PP,
           "FIRES (UNDERPOWERED)" if resolution >= PART_C_MIN_SE_RESOLUTION_PP else "clear"))
    if resolution >= PART_C_MIN_SE_RESOLUTION_PP or np.isnan(se):
        result["row"] = "C0"
        log("ROW C0: UNDERPOWERED -- an instrument failure, not a null. No verdict.")
        return result

    ci_lo, ci_hi = ci95
    if l_point >= PART_C_C1_MIN_PP and ci_lo > 0:
        row = "C1"
        log("ROW C1: L=%+.2fpp (>=%.1fpp) AND CI_lo=%+.2fpp (>0). MATERIAL recall cost."
            % (l_point, PART_C_C1_MIN_PP, ci_lo))
    elif PART_C_C2_MIN_PP <= l_point < PART_C_C1_MIN_PP and ci_lo > 0:
        row = "C2"
        log("ROW C2: L=%+.2fpp in [%.1f,%.1f)pp AND CI_lo=%+.2fpp (>0). Real but small."
            % (l_point, PART_C_C2_MIN_PP, PART_C_C1_MIN_PP, ci_lo))
    elif l_point <= PART_C_C4_MAX_PP and ci_hi < 0:
        row = "C4"
        log("ROW C4: L=%+.2fpp (<=%.1fpp) AND CI_hi=%+.2fpp (<0). The offset APPEARS TO HELP -- "
            "reported as-is, not rationalised." % (l_point, PART_C_C4_MAX_PP, ci_hi))
    else:
        row = "C3"
        log("ROW C3: L=%+.2fpp, CI95=[%+.2f,%+.2f]pp -- L<0.2pp or CI contains 0. No measurable "
            "recall cost at matched SNR." % (l_point, ci_lo, ci_hi))
    result["row"] = row
    return result


# =============================================================================
# Part B -- R (full population) and K (swept sample), on one corpus
# =============================================================================

def run_r(pairs: list[dict], log, label: str) -> dict:
    rows = [{"ts": p["ts"], "d_ber": p["d_dt"]} for p in pairs]
    res = cluster_bootstrap_median_diff(rows, seed=AO1_SEED)
    log("  R [%s]: point=%+.3fs mean=%+.3fs se=%.4fs CI95=[%+.3f,%+.3f]s p=%.4f "
        "(n_rows=%d n_clusters=%d n_draws=%d)"
        % (label, res["point_estimate"], res["mean"], res["se"], res["ci95"][0], res["ci95"][1],
           res["p_two_sided"], res["n_rows"], res["n_clusters"], res["n_draws"]))
    return res


def run_k_sweep(ex: ExtractLLRs, pairs: list[dict], owsfz_wav_dir: str, log, label: str,
                 sample_rows: int = SAMPLE_ROWS) -> dict:
    sample = deterministic_sample(pairs, min(sample_rows, len(pairs)), AO1_SEED)
    contexts, drop_reasons = load_contexts_for_sample(ex, owsfz_wav_dir, sample, log)
    out: dict = {
        "sample_n_rows": len(sample), "sample_n_clusters": len({p["ts"] for p in sample}),
        "n_measured": len(contexts), "n_clusters_measured": len({c[0] for c in contexts}),
        "drop_reasons": drop_reasons,
    }
    if not contexts:
        log("  K [%s]: no contexts loaded, cannot sweep." % label)
        out["k"] = None
        return out
    matrix = sweep_matrix(ex, contexts, log, label=label)
    all_idx = list(range(len(contexts)))
    pooled = pooled_curve(matrix, all_idx)
    best = argmin_curve(pooled)
    out["sweep_table"] = pooled
    out["k"] = best["dt_offset"] if best else None
    out["k_median_ber"] = best["median_ber"] if best else None
    out["_matrix"] = matrix  # internal use (quartile check), stripped before writing
    log("  K [%s]: argmin=%s median_BER_V0=%s"
        % (label, "%+.3fs" % out["k"] if out["k"] is not None else "NONE",
           "%.2f%%" % (out["k_median_ber"] * 100) if out.get("k_median_ber") is not None else "n/a"))
    return out


def quartile_check(matrix: dict, pooled_k: float, log) -> dict:
    n = len(matrix["ts"])
    quartile_idx = [list(a) for a in np.array_split(np.arange(n), 4)]
    quartiles = []
    max_delta = 0.0
    for qi, idx in enumerate(quartile_idx):
        if len(idx) == 0:
            quartiles.append({"quartile": qi, "n_rows": 0, "offset": None, "delta_vs_pooled": None})
            continue
        q_ts = sorted({matrix["ts"][i] for i in idx})
        q_curve = pooled_curve(matrix, idx)
        q_best = argmin_curve(q_curve)
        q_offset = q_best["dt_offset"] if q_best else None
        delta = abs(q_offset - pooled_k) if q_offset is not None else None
        if delta is not None:
            max_delta = max(max_delta, delta)
        quartiles.append({"quartile": qi, "n_rows": len(idx), "n_clusters": len(q_ts),
                           "ts_range": [q_ts[0], q_ts[-1]] if q_ts else None,
                           "offset": q_offset, "delta_vs_pooled": delta})
        log("    quartile %d: n_rows=%d ts=[%s..%s] argmin=%s delta_vs_pooled=%s"
            % (qi, len(idx), q_ts[0] if q_ts else "?", q_ts[-1] if q_ts else "?",
               "%+.2fs" % q_offset if q_offset is not None else "NONE",
               "%.3fs" % delta if delta is not None else "n/a"))
    fires = any(q["delta_vs_pooled"] is not None and q["delta_vs_pooled"] > ROW_0F_TOL_S for q in quartiles)
    return {"fires": fires, "quartiles": quartiles, "max_delta_vs_pooled": max_delta,
            "tolerance_s": ROW_0F_TOL_S}


# =============================================================================
# main
# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--sample-rows", type=int, default=SAMPLE_ROWS)
    ap.add_argument("--skip-extension-k", action="store_true",
                     help="descriptive-only extension K sweeps are expensive; skip if pressed for time")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("AO1 -- the production time-origin offset")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    bundle: dict = {"hk025": hk025}
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        bundle["final_row"] = "REFUSED"
        _write(args.out_dir, bundle, log_lines)
        return 1

    # -- ROW 0a -------------------------------------------------------------
    log("\nLoading DLL: %s" % args.dll_path)
    try:
        ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                          expected_shim_version=EXPECTED_SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0a"
        bundle["row_0a"] = {"fires": True, "error": str(e)}
        _write(args.out_dir, bundle, log_lines)
        return 2
    log("ROW 0a clear: DLL SHA256 asserted (%s...), shim version %d confirmed."
        % (args.dll_sha256[:16], ex.version))
    bundle["row_0a"] = {"fires": False}

    # -- Build matched pairs on PRIMARY --------------------------------------
    log("\n" + "=" * 90)
    log("Building matched-pair population on PRIMARY (%s)" % PRIMARY_CORPUS)
    log("=" * 90)
    pairs, diag = build_matched_pairs(PRIMARY_CORPUS)
    log("  %s" % diag)
    bundle["primary_matched_pair_diagnostics"] = diag

    paths = corpus_paths(PRIMARY_CORPUS)

    # -- ROW 0e: sign unit test (Stage 2's construction, verbatim) ----------
    log("\nDrawing seeded K-sample (n<=%d, seed=%d) and loading contexts from OUR OWN "
        "archived audio (%s)..." % (args.sample_rows, AO1_SEED, paths["owsfz_wav_dir"]))
    sample = deterministic_sample(pairs, min(args.sample_rows, len(pairs)), AO1_SEED)
    contexts, drop_reasons = load_contexts_for_sample(ex, paths["owsfz_wav_dir"], sample, log)
    bundle["primary_sample"] = {"n_rows": len(sample), "n_clusters": len({p["ts"] for p in sample}),
                                 "n_measured": len(contexts),
                                 "n_clusters_measured": len({c[0] for c in contexts}),
                                 "drop_reasons": drop_reasons}

    sign_ok = run_sign_test(ex, contexts, log)
    bundle["row_0e"] = {"fires": not sign_ok}
    if not sign_ok:
        log("\nROW 0e FIRES: sign unit test failed. VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0e"
        _write(args.out_dir, bundle, log_lines)
        return 3

    # -- ROW 0b: matched-pair dry count, full population ---------------------
    log("\n" + "=" * 90)
    log("ROW 0b -- matched-pair dry count, full PRIMARY population")
    log("=" * 90)
    n_rows, n_clusters = diag["n_matched"], diag["n_matched_clusters"]
    row0b_fires = n_rows < ROW_0B_MIN_ROWS or n_clusters < ROW_0B_MIN_CLUSTERS
    log("n_rows=%d (>=%d) n_clusters=%d (>=%d) -> %s"
        % (n_rows, ROW_0B_MIN_ROWS, n_clusters, ROW_0B_MIN_CLUSTERS, "FIRES" if row0b_fires else "clear"))
    bundle["row_0b"] = {"fires": row0b_fires, "n_rows": n_rows, "n_clusters": n_clusters}
    if row0b_fires:
        log("\nROW 0b FIRES: underpowered. VALIDITY/PRECISION, STOP.")
        bundle["final_row"] = "0b"
        _write(args.out_dir, bundle, log_lines)
        return 4

    # -- ROW 0c: reference dt grid-lock plausibility --------------------------
    log("\n" + "=" * 90)
    log("ROW 0c -- reference dt grid-lock plausibility")
    log("=" * 90)
    dt_ref_rows = [{"ts": p["ts"], "d_ber": p["ref_dt"]} for p in pairs]
    dt_ref_res = cluster_bootstrap_median_diff(dt_ref_rows, seed=AO1_SEED)
    cluster_median_dt_ref = dt_ref_res["point_estimate"]
    row0c_fires = not (ROW_0C_LO <= cluster_median_dt_ref <= ROW_0C_HI)
    log("cluster-median dt_ref=%+.3fs, outside [%+.2f,%+.2f]s two-sided -> %s"
        % (cluster_median_dt_ref, ROW_0C_LO, ROW_0C_HI, "FIRES" if row0c_fires else "clear"))
    bundle["row_0c"] = {"fires": row0c_fires, "cluster_median_dt_ref": cluster_median_dt_ref,
                         "band": [ROW_0C_LO, ROW_0C_HI], "full_stats": dt_ref_res}
    if row0c_fires:
        log("\nROW 0c FIRES: reference's own grid lock is in question. VALIDITY, STOP.")
        bundle["final_row"] = "0c"
        _write(args.out_dir, bundle, log_lines)
        return 5

    # -- R, full population ----------------------------------------------------
    log("\n" + "=" * 90)
    log("R -- full PRIMARY matched population, cluster-bootstrapped, SIGNED")
    log("=" * 90)
    r_primary = run_r(pairs, log, "PRIMARY")
    bundle["r_primary"] = r_primary
    R = r_primary["point_estimate"]

    # -- K, swept sample ---------------------------------------------------------
    log("\n" + "=" * 90)
    log("K -- sweeping our own archived audio, anchored at the reference's (freq, dt), "
        "M3's 49-point grid")
    log("=" * 90)
    k_result = run_k_sweep(ex, pairs, paths["owsfz_wav_dir"], log, "PRIMARY",
                            sample_rows=args.sample_rows)
    matrix = k_result.pop("_matrix", None)
    bundle["k_primary"] = k_result
    K = k_result.get("k")
    K_ber = k_result.get("k_median_ber")

    # -- ROW 0d: median BER_V0 at K's argmin ---------------------------------
    log("\n" + "=" * 90)
    log("ROW 0d -- median BER_V0 at K's argmin")
    log("=" * 90)
    row0d_fires = K_ber is None or not (ROW_0D_LO <= K_ber <= ROW_0D_HI)
    log("median_BER_V0(K=%s)=%s outside [%.0f%%,%.0f%%] two-sided -> %s"
        % ("%+.3fs" % K if K is not None else "n/a",
           "%.2f%%" % (K_ber * 100) if K_ber is not None else "n/a",
           ROW_0D_LO * 100, ROW_0D_HI * 100, "FIRES" if row0d_fires else "clear"))
    bundle["row_0d"] = {"fires": row0d_fires, "k": K, "k_median_ber": K_ber, "band": [ROW_0D_LO, ROW_0D_HI]}
    if row0d_fires:
        log("\nROW 0d FIRES: the sweep is not reading. VALIDITY, STOP.")
        bundle["final_row"] = "0d"
        _write(args.out_dir, bundle, log_lines)
        return 6

    # -- ROW 0f: quartile drift ------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 0f -- 4 chronological ts-quartiles' own argmin vs pooled K")
    log("=" * 90)
    qcheck = quartile_check(matrix, K, log)
    log("max|quartile_argmin - pooled_K|=%.3fs (bound <=%.2fs) -> %s"
        % (qcheck["max_delta_vs_pooled"], ROW_0F_TOL_S, "FIRES" if qcheck["fires"] else "clear"))
    bundle["row_0f"] = qcheck
    if qcheck["fires"]:
        log("ROW 0f FIRES: offset is not one constant across the cycle timeline. Reported as "
            "drift; Part B still reports; Part C WITHHELD regardless of the main-row outcome.")

    # -- ROW 0g: reference SNR parseability (Part C only) ----------------------
    log("\n" + "=" * 90)
    log("ROW 0g -- reference SNR-field parseability (gates Part C only)")
    log("=" * 90)
    frac_bad = diag["frac_ref_snr_unparseable"]
    row0g_fires = frac_bad > ROW_0G_MAX_FRAC
    log("frac_ref_snr_unparseable=%.2f%% (bound <=%.0f%%) -> %s"
        % (frac_bad * 100, ROW_0G_MAX_FRAC * 100, "FIRES" if row0g_fires else "clear"))
    bundle["row_0g"] = {"fires": row0g_fires, "frac_ref_snr_unparseable": frac_bad,
                         "bound": ROW_0G_MAX_FRAC}
    if row0g_fires:
        log("ROW 0g FIRES: Part C (if it runs) is descriptive only, gates nothing. Part B unaffected.")

    # -- Part B main rows, strict order ----------------------------------------
    log("\n" + "=" * 90)
    log("PART B -- main rows 1-5, strict order, theta=%.2fs" % THETA)
    log("=" * 90)
    abs_r, abs_k = abs(R), abs(K) if K is not None else None
    log("R=%+.3fs |R|=%.3fs   K=%s |K|=%s   theta=%.2fs"
        % (R, abs_r, "%+.3fs" % K if K is not None else "n/a",
           "%.3fs" % abs_k if abs_k is not None else "n/a", THETA))

    if K is None:
        final_row = "no_verdict_k_unavailable"
        log("\nK could not be computed (no valid sweep optimum) -- NO VERDICT possible. Escalate.")
    elif abs_r < THETA and abs_k < THETA:
        final_row = "1"
        log("\nROW 1: |R|<theta AND |K|<theta. NO PRODUCTION OFFSET. The anchor-offset "
            "question CLOSES. Route A is NOT re-routed.")
    elif abs_r >= THETA and abs_k < THETA:
        final_row = "2"
        log("\nROW 2: |R|>=theta AND |K|<theta. LABELLING DEFECT ONLY -- product defect, "
            "no recall consequence. Part C does not run. D-001 UNAFFECTED.")
    elif (abs_r >= THETA and abs_k >= THETA
          and ((R >= 0) == (K >= 0)) and abs(K - R) <= ROW_3_K_MINUS_R_TOL):
        final_row = "3"
        log("\nROW 3 FIRES: |R|>=theta AND |K|>=theta AND sign(K)=sign(R) AND |K-R|<=%.2fs. "
            "PRODUCTION FRAMING DEFECT -- archive faithful to the live buffer. Route A is "
            "promoted from open to confirmed-in-part. Part C runs (if 0f clear)."
            % ROW_3_K_MINUS_R_TOL)
    elif abs_r < THETA and abs_k >= THETA:
        final_row = "5"
        log("\nROW 5: |R|<theta AND |K|>=theta. INCOHERENT, REVERSE. NO VERDICT. Escalate.")
    else:
        final_row = "4"
        log("\nROW 4: |R|>=theta AND |K|>=theta AND (sign disagreement OR |K-R|>%.2fs). "
            "INCOHERENT. NO VERDICT. Escalate." % ROW_3_K_MINUS_R_TOL)

    bundle["final_row"] = final_row
    bundle["R"] = R
    bundle["K"] = K

    # -- Part C ------------------------------------------------------------------
    part_c_result = None
    if final_row == "3" and not qcheck["fires"]:
        ref_population = build_reference_population(PRIMARY_CORPUS)
        part_c_result = run_part_c(ref_population, log)
        if row0g_fires and part_c_result.get("evaluated"):
            log("(Part C's row above is DESCRIPTIVE ONLY per ROW 0g -- SNR control is degraded "
                "on >5% of the reference population; it does not license the C1/C2 consequences "
                "formally.)")
        bundle["part_c"] = part_c_result
        bundle["part_c_descriptive_only"] = row0g_fires
    else:
        reason = ("ROW 3 did not fire" if final_row != "3" else "ROW 0f fired (offset not constant)")
        log("\nPart C SKIPPED: %s." % reason)
        bundle["part_c"] = {"evaluated": False, "reason": reason}

    # -- Descriptive replication on the extension corpora, never pooled ---------
    log("\n" + "=" * 90)
    log("Descriptive replication -- R (and K if affordable) on the extension corpora, "
        "PER CORPUS, NEVER POOLED, HK-021(k): gates nothing")
    log("=" * 90)
    extension_results = {}
    for corpus in AO1_EXTENSION_CORPORA:
        try:
            log("\n-- %s --" % corpus)
            ext_paths = corpus_paths(corpus)
            ext_pairs, ext_diag = build_matched_pairs(corpus)
            log("  %s" % ext_diag)
            ext_r = run_r(ext_pairs, log, corpus)
            entry = {"diagnostics": ext_diag, "r": ext_r}
            if not args.skip_extension_k and ext_diag["n_matched"] >= 50:
                ext_k = run_k_sweep(ex, ext_pairs, ext_paths["owsfz_wav_dir"], log, corpus,
                                     sample_rows=args.sample_rows)
                ext_k.pop("_matrix", None)
                entry["k"] = ext_k
            extension_results[corpus] = entry
        except Exception as e:  # noqa: BLE001 -- descriptive item, must not crash the whole report
            log("  %s raised %s: %s -- reported as failed, does not affect any gate."
                % (corpus, type(e).__name__, e))
            extension_results[corpus] = {"error": "%s: %s" % (type(e).__name__, e)}
    bundle["extension_replication"] = extension_results

    log("\n" + "=" * 90)
    log("FINAL ROW: %s" % bundle.get("final_row"))
    if part_c_result is not None:
        log("PART C ROW: %s" % part_c_result.get("row", "n/a"))
    log("=" * 90)

    _write(args.out_dir, bundle, log_lines)
    log("\nWrote results/ao1_report.json, results/ao1_run.log")
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "ao1_report.json"), bundle)
    with open(os.path.join(out_dir, "ao1_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
