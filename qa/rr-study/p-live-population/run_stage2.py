#!/usr/bin/env python3
"""Stage 2 -- the combined pre-registration: the anchor-offset arm (Part A) AND,
gated on Part A's own output, N1's harm-replication question re-run on P-LIVE.

Spec: qa/rr-study/2026-08-18-1921-architect-to-qa-stage2-unblock-ruling-and-combined-
prereg.md ("this document"), superseding Sec.6 ONLY of the 16:16Z ruling
(2026-08-18-1616-architect-to-qa-p-live-stage1-ruling-anchor-provenance-defect.md).
Captain's ruling 2026-08-18: Stage 2 is UNBLOCKED via ROW A's second limb ("or the
Captain rules otherwise").

WHAT THIS RUNS, IN THE SPEC'S OWN Sec.6 ORDER:
  1. ROW 0a  -- DLL SHA256 re-hashed from disk, asserted against the header pin.
  2. Mandatory sign unit test (Sec.6, new -- NOT the same as N1's sign_unit_test.py,
     which only checks the pure-statistics d_ber/f_cross sign convention). This one
     exercises the REAL extraction code path the sweep itself uses: on a handful of
     real P-HIT rows, the anchor fed to the sweep is displaced by a KNOWN delta
     (content untouched) and the sweep's minimum must land at dt_offset ~= -delta
     relative to that displaced anchor -- "lands at its negation", the spec's own
     phrase, verified for two opposite-sign deltas.
  3. Part A -- build P-HIT on PRIMARY, sweep m3_common.TIME_ANCHOR_OFFSETS_S (49
     points, REUSED verbatim), derive OFFSET = argmin median BER_V0. Evaluate ROW 0c
     (offset plausibility) then ROW 0d (4 chronological ts-quartiles, offset must be
     one constant within one grid step).
  4. Dry-count P-LIVE on PRIMARY (population size only, no DLL calls) -> ROW 0b,
     evaluated BEFORE any Stage 2 measurement.
  5. Stage 2 -- GRID vs REFINED (N1's own pattern: ft8_extract_llrs_at then
     ft8_refine_candidate then re-extract) on P-LIVE at anchor_dt + OFFSET. Evaluate
     0e (refiner rail fraction) -> 0f (treatment can move) -> 0g (ber_grid
     plausibility), then ROW 1 (BENEFIT) -> ROW 3 (HARM) -> ROW 2 (NULL) -> ROW 4
     (residue), strict order, first match wins.
  6. Part A item 2 -- the SAME 49-point sweep on ONE extension corpus's P-HIT
     (20260808_live_run_0016-8080), DESCRIPTIVE ONLY, gates nothing (HK-021(k) --
     Stage 2 runs on PRIMARY regardless of what a second corpus says).

Sec.2's two findings, both load-bearing for this harness's design (read there, not
re-derived here):
  Finding 1 -- the refiner's search window is +/-70ms / +/-2.5Hz. ROW 0e exists
  because a railed refiner returns the window edge, not an estimate.
  Finding 2 -- N1's own ROW 2 gated on |d_ber| (HK-021 sibling (l)). Stage 2's gate
  is SIGNED: ROW 2 (NULL) requires CI_hi >= 0 as well as |d_ber|<=5pp, and a separate
  ROW 3 (HARM) exists so a real harmful effect cannot be reported as "no effect".

NFR-021: message TEXT is used in-process only (ExtractLLRs.true_codeword, inside
load_row_context / Part A's context loader) and is NEVER written to any row dict,
JSON file, or log line this module produces. Every emitted file is grepped
individually for "message" after the run, per the spec's own instruction, not
merely asserted.

No src/, no Developer session, no DLL rebuild, no capture run -- HK-011 not engaged.
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r1-sync-refiner"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from refiner_ctypes import Refiner  # noqa: E402
from m3_common import TIME_ANCHOR_OFFSETS_S  # noqa: E402 -- Sec.3 item 2: REUSE verbatim
from n1_stats import cluster_bootstrap_median_diff, d_ber_row, f_cross_row  # noqa: E402
from plive_population import (  # noqa: E402
    PRIMARY_CORPUS, build_p_hit_population, build_p_live_population, corpus_paths,
)
from run_stage1 import (  # noqa: E402
    DEFAULT_DLL_PATH, DEFAULT_DLL_SHA256, EXPECTED_SHIM_VERSION, WavCache, decile_table,
)
from run_stage1r import deterministic_sample  # noqa: E402 -- Sec.3: same seeded, sort-stabilised sample procedure

# -- Sec.5, second-corpus pick for Part A item 2 (QA's choice, per Sec.5 item 2) ----
SECOND_CORPUS = "20260808_live_run_0016-8080"

# -- Sec.3: derivation-procedure seed, stated explicitly in the spec ---------------
PART_A_SEED = 20260818
PART_A_SAMPLE_ROWS = 600   # see report Sec."compute budget" for the full-population math

# -- Sec.4 bars, derived not chosen (see spec Sec.4/4.4 for the derivation) --------
ROW_0B_MIN_ROWS = 500
ROW_0B_MIN_CLUSTERS = 200
ROW_0C_LO, ROW_0C_HI = 0.010, 0.150          # two-sided
ROW_0D_TOL_S = 0.05                          # one grid step
ROW_0E_RAIL_T_THRESHOLD = 0.0695             # 0.070s hard ceiling less half a fine step
ROW_0E_FRAC_RAIL_T_MAX = 0.50
FRAC_RAIL_F_THRESHOLD = 2.495                # descriptive only, no gate
ROW_0F_DT_FLOOR_S = 0.005                    # N1's own ROW 0d floor, reused
ROW_0F_DF_FLOOR_HZ = 0.25                    # N1's own ROW 0d floor, reused
ROW_0G_LO, ROW_0G_HI = 0.080, 0.400          # two-sided
ROW_1_D_BER_MIN = 0.15
ROW_1_CI_LO_MIN = 0.05
ROW_1_F_CROSS_MIN = 0.20
ROW_3_CI_HI_MAX = 0.0
ROW_3_D_BER_MAX = -0.02
ROW_2_CI_LO_MIN = -0.05
ROW_2_CI_HI_MAX = 0.15
ROW_2_D_BER_ABS_MAX = 0.05

SIGN_TEST_N_ROWS = 20
SIGN_TEST_DELTA_S = 0.30    # 6 grid steps, clean multiple of 0.05s


# =============================================================================
# HK-025 -- independent re-classification, per the spec's own Sec.4.3 instruction
# =============================================================================

def hk025_check() -> dict:
    """Every ROW 0 evaluated fresh under both branches (HK-025). Re-derived here,
    not copied from the spec's own Sec.4.3 table, per its explicit instruction to
    treat that table as a claim to check.

    0a: fires -> every extraction in the run is against an unidentified binary, no
        named instrument at all, refuse to arm. Clears -> proceed on a pinned
        binary. Different actions. VALIDITY, not diagnostic.
    0b: fires -> the P-LIVE target population itself cannot support a reliable
        measurement, escalate. Clears -> proceed to measure it. Different actions.
        VALIDITY, not diagnostic.
    0c: fires -> on rows we ourselves decoded (positive control), the best offset
        this sweep can find still does not read a plausible signal -- no usable
        global anchor correction exists AT ALL, stop. Clears -> a real, usable
        offset exists, proceed. This is a premise failure, not reduced precision
        on a still-valid measurement. VALIDITY, not diagnostic.
    0d: fires -> the offset drifts by cycle, so applying ONE global correction to
        every P-LIVE row is the wrong design (a per-cycle correction is a DIFFERENT
        arm), stop and escalate. Clears -> one offset is valid, proceed. Different
        downstream designs, not different confidence in the same design. VALIDITY,
        not diagnostic.
    0e: fires -> the refiner is pinned against its own search boundary on the
        majority of rows, so d_ber measures the window edge, not refinement -- a
        DIFFERENT quantity from what the gate names. Clears -> d_ber is about
        refinement. VALIDITY, not diagnostic.
    0f: fires -> GRID and REFINED are the same position in practice, no treatment
        contrast exists to measure. Clears -> a real contrast exists. VALIDITY,
        not diagnostic.
    0g: fires (either direction) -> either ber_grid is chance-level (d_ber is a
        difference of two noise readings, a STRUCTURAL fact about the population,
        not about refinement) or implausibly low (membership leak, a DIFFERENT
        population than intended). Both fired-subcases share the same downstream
        action (stop, escalate, do not read d_ber as a refinement result) against
        the same cleared-branch action (read d_ber as refinement). VALIDITY, not
        diagnostic, even though the two fired-subcases differ from EACH OTHER in
        cause -- HK-025 only requires fired-vs-cleared to differ, which it does.

    No refusal. Concurs with the spec's own Sec.4.3 table."""
    reasons = {
        "0a": "unidentified binary invalidates every downstream number",
        "0b": "dry-count underpowered -- the target population cannot support a "
              "reliable estimate, not merely reduced precision",
        "0c": "no usable global anchor correction exists on positive-control rows "
              "-- a premise failure, not imprecision in a valid measurement",
        "0d": "the offset is not one constant across the cycle timeline -- wrong "
              "DESIGN (needs a per-cycle correction, a different arm), not noise",
        "0e": "refiner railed on the majority -- d_ber measures the search-window "
              "edge, a different quantity from refinement",
        "0f": "no material motion -- no treatment contrast exists to measure",
        "0g": "chance-level (structural) or implausibly low (membership leak) -- "
              "either way the treatment question does not apply as framed",
    }
    classification = {k: {"class": "VALIDITY", "reason": v} for k, v in reasons.items()}
    return {"classification": classification, "refusal": False, "concurs_with_spec": True}


# =============================================================================
# Population / context loading
# =============================================================================

def load_row_context(ex: ExtractLLRs, wav_cache: WavCache, row: dict):
    """Returns ((ts, pcm, true_bits, freq_int, anchor_dt), None) or (None, reason).
    message text touches this function only via ex.true_codeword and is never
    retained past this call (NFR-021)."""
    try:
        pcm = wav_cache.get(row["ts"])
    except FileNotFoundError:
        return None, "no_wav"
    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return None, "no_true_codeword"
    freq_int = round(row["anchor_freq_hz"])  # no-op: WSJT-X freq is already int Hz
    anchor_dt = float(row["anchor_dt"])
    return (row["ts"], pcm, true_bits, freq_int, anchor_dt), None


def load_contexts_for_sample(ex: ExtractLLRs, wav_dir: str, sample: list[dict], log) -> tuple[list, dict]:
    wav_cache = WavCache(wav_dir)
    contexts = []
    drop_reasons: dict[str, int] = {}
    for row in sample:
        ctx, reason = load_row_context(ex, wav_cache, row)
        if ctx is None:
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
            continue
        contexts.append(ctx)
    log("  n_measured=%d/%d n_clusters_measured=%d drop_reasons=%s"
        % (len(contexts), len(sample), len({c[0] for c in contexts}), drop_reasons))
    return contexts, drop_reasons


# =============================================================================
# Sec.6 mandatory sign unit test -- exercises the REAL sweep code path
# =============================================================================

def _pooled_argmin(ex: ExtractLLRs, contexts: list, anchor_delta: float):
    """Sweeps TIME_ANCHOR_OFFSETS_S starting from (anchor_dt + anchor_delta) for
    every context, pools median BER per offset across contexts, returns the
    argmin offset (or None if nothing extracted)."""
    by_off: dict[float, list[float]] = {off: [] for off in TIME_ANCHOR_OFFSETS_S}
    for ts, pcm, true_bits, freq_int, anchor_dt in contexts:
        base = anchor_dt + anchor_delta
        for dt_offset in TIME_ANCHOR_OFFSETS_S:
            rc, llr = ex.extract_at(pcm, float(freq_int), base + dt_offset)
            if rc != 0 or llr is None:
                continue
            by_off[dt_offset].append(hard_decision_ber(llr, true_bits))
    medians = [(off, st.median(bers)) for off, bers in by_off.items() if bers]
    if not medians:
        return None
    return min(medians, key=lambda p: p[1])[0]


def run_sign_test(ex: ExtractLLRs, contexts: list, log) -> bool:
    log("\n" + "=" * 90)
    log("MANDATORY SIGN UNIT TEST (Sec.6) -- exercises the real sweep code path")
    log("=" * 90)
    log("Construction: content untouched; the anchor FED TO THE SWEEP is displaced by a")
    log("known delta (wrong_anchor = anchor_dt + delta). A too-late anchor needs an")
    log("earlier-searching correction, so the sweep's minimum should land at")
    log("dt_offset ~= -delta relative to that displaced anchor -- 'lands at its")
    log("negation', the spec's own phrase (Sec.6). Two opposite-sign deltas exercised.")

    rows = contexts[:SIGN_TEST_N_ROWS]
    log("  using n=%d real P-HIT contexts (WAV + true codeword already loaded)" % len(rows))

    o0 = _pooled_argmin(ex, rows, 0.0)
    o_pos = _pooled_argmin(ex, rows, +SIGN_TEST_DELTA_S)
    o_neg = _pooled_argmin(ex, rows, -SIGN_TEST_DELTA_S)
    log("  baseline argmin O0=%s" % ("%+.2fs" % o0 if o0 is not None else "NONE"))
    log("  delta=%+.2fs -> O_pos=%s (expect O0-delta=%s)"
        % (SIGN_TEST_DELTA_S, "%+.2fs" % o_pos if o_pos is not None else "NONE",
           "%+.2fs" % (o0 - SIGN_TEST_DELTA_S) if o0 is not None else "n/a"))
    log("  delta=%+.2fs -> O_neg=%s (expect O0-delta=%s)"
        % (-SIGN_TEST_DELTA_S, "%+.2fs" % o_neg if o_neg is not None else "NONE",
           "%+.2fs" % (o0 + SIGN_TEST_DELTA_S) if o0 is not None else "n/a"))

    if o0 is None or o_pos is None or o_neg is None:
        log("SIGN UNIT TEST FAILED: at least one sweep found no extractable offset.")
        return False

    expect_pos = o0 - SIGN_TEST_DELTA_S
    expect_neg = o0 + SIGN_TEST_DELTA_S
    ok_pos = abs(o_pos - expect_pos) <= ROW_0D_TOL_S + 1e-9
    ok_neg = abs(o_neg - expect_neg) <= ROW_0D_TOL_S + 1e-9
    shift_pos = o_pos - o0
    shift_neg = o_neg - o0
    ok_opposite_sign = (shift_pos < 0 < shift_neg) or (shift_neg < 0 < shift_pos)
    log("  |O_pos - expect|=%.3fs (<=%.2fs) -> %s" % (abs(o_pos - expect_pos), ROW_0D_TOL_S,
                                                        "PASS" if ok_pos else "FAIL"))
    log("  |O_neg - expect|=%.3fs (<=%.2fs) -> %s" % (abs(o_neg - expect_neg), ROW_0D_TOL_S,
                                                        "PASS" if ok_neg else "FAIL"))
    log("  shift_pos=%+.2fs shift_neg=%+.2fs opposite signs -> %s"
        % (shift_pos, shift_neg, "PASS" if ok_opposite_sign else "FAIL"))

    passed = ok_pos and ok_neg and ok_opposite_sign
    log("\nRESULT: %s" % ("PASS -- Part A / Stage 2 may be armed." if passed
                           else "FAIL -- REFUSING to arm Part A / Stage 2."))
    return passed


# =============================================================================
# Part A -- P-HIT sweep, OFFSET derivation, ROW 0c / ROW 0d
# =============================================================================

def sweep_matrix(ex: ExtractLLRs, contexts: list, log, label: str) -> dict:
    """Extracts every context at every offset in TIME_ANCHOR_OFFSETS_S. Returns
    {"ts": [...], "bers": [[per-offset BER or None]], "offsets": [...]}."""
    t0 = time.time()
    ts_list = [c[0] for c in contexts]
    bers: list[list] = []
    n_fail = 0
    for ts, pcm, true_bits, freq_int, anchor_dt in contexts:
        row_bers = []
        for dt_offset in TIME_ANCHOR_OFFSETS_S:
            rc, llr = ex.extract_at(pcm, float(freq_int), anchor_dt + dt_offset)
            if rc != 0 or llr is None:
                row_bers.append(None)
                n_fail += 1
                continue
            row_bers.append(hard_decision_ber(llr, true_bits))
        bers.append(row_bers)
    elapsed = time.time() - t0
    log("  [%s] swept %d rows x %d offsets in %.1fs (%d extraction failures)"
        % (label, len(contexts), len(TIME_ANCHOR_OFFSETS_S), elapsed, n_fail))
    return {"ts": ts_list, "bers": bers, "offsets": list(TIME_ANCHOR_OFFSETS_S), "elapsed_s": elapsed}


def pooled_curve(matrix: dict, row_indices) -> list[dict]:
    curve = []
    for j, off in enumerate(matrix["offsets"]):
        vals = [matrix["bers"][i][j] for i in row_indices if matrix["bers"][i][j] is not None]
        curve.append({"dt_offset": off, "median_ber": float(st.median(vals)) if vals else None,
                      "n_ok": len(vals)})
    return curve


def argmin_curve(curve: list[dict]):
    valid = [c for c in curve if c["median_ber"] is not None]
    if not valid:
        return None
    return min(valid, key=lambda c: c["median_ber"])


def run_part_a(ex: ExtractLLRs, corpus_name: str, log, descriptive_only: bool = False) -> dict:
    log("\n" + "=" * 90)
    log("PART A -- P-HIT sweep on %s%s" % (corpus_name, " (DESCRIPTIVE ONLY, Sec.5 item 2)"
                                            if descriptive_only else ""))
    log("=" * 90)
    full_population = build_p_hit_population(corpus_name)
    full_n_clusters = len({r["ts"] for r in full_population})
    log("  full P-HIT population: n_rows=%d n_clusters=%d" % (len(full_population), full_n_clusters))

    sample = deterministic_sample(full_population, min(PART_A_SAMPLE_ROWS, len(full_population)), PART_A_SEED)
    sample_n_clusters = len({r["ts"] for r in sample})
    log("  sampled (seed=%d): n_rows=%d n_clusters=%d" % (PART_A_SEED, len(sample), sample_n_clusters))

    paths = corpus_paths(corpus_name)
    log("  loading row contexts (true codeword + WAV)...")
    contexts, drop_reasons = load_contexts_for_sample(ex, paths["wsjtx_wav_dir"], sample, log)

    result = {
        "corpus": corpus_name,
        "full_population_n_rows": len(full_population),
        "full_population_n_clusters": full_n_clusters,
        "sample_n_rows": len(sample),
        "sample_n_clusters": sample_n_clusters,
        "n_measured": len(contexts),
        "n_clusters_measured": len({c[0] for c in contexts}),
        "drop_reasons": drop_reasons,
    }

    sign_test_passed = None
    if not descriptive_only:
        sign_test_passed = run_sign_test(ex, contexts, log)
        result["sign_unit_test_passed"] = sign_test_passed
        if not sign_test_passed:
            return result

    matrix = sweep_matrix(ex, contexts, log, label=corpus_name)
    all_idx = list(range(len(contexts)))
    pooled = pooled_curve(matrix, all_idx)
    best = argmin_curve(pooled)
    result["sweep_table"] = pooled
    result["offset"] = best["dt_offset"] if best else None
    result["offset_median_ber"] = best["median_ber"] if best else None
    log("  swept optimum (pooled median BER_V0): %s"
        % ("dt_offset=%+.2fs median_BER=%.2f%%" % (best["dt_offset"], best["median_ber"] * 100)
           if best else "NONE (no offset had any successful extraction)"))

    if descriptive_only:
        # Trough characterisation, descriptive only, no gate (Sec.5.1/5.2).
        if best is not None:
            near = [c for c in pooled if c["median_ber"] is not None
                    and c["median_ber"] <= best["median_ber"] + 0.05]
            offs = [c["dt_offset"] for c in near]
            result["trough_within_5pp"] = {"n_points": len(near),
                                            "offset_range": [min(offs), max(offs)] if offs else None}
            log("  trough (median BER within 5pp of the minimum): %d grid points, offset range %s"
                % (len(near), result["trough_within_5pp"]["offset_range"]))
        return result

    # ROW 0c: median BER at OFFSET on the positive control, two-sided [1%,15%].
    offset = result["offset"]
    offset_ber = result["offset_median_ber"]
    row0c_fires = offset_ber is None or not (ROW_0C_LO <= offset_ber <= ROW_0C_HI)
    log("\nROW 0c: median_BER_V0(OFFSET=%s)=%s outside [%.0f%%,%.0f%%] two-sided -> %s"
        % ("%+.2fs" % offset if offset is not None else "n/a",
           "%.2f%%" % (offset_ber * 100) if offset_ber is not None else "n/a",
           ROW_0C_LO * 100, ROW_0C_HI * 100, "FIRES" if row0c_fires else "clear"))
    result["row_0c"] = {"fires": row0c_fires, "offset": offset, "offset_median_ber": offset_ber,
                         "band": [ROW_0C_LO, ROW_0C_HI]}
    if row0c_fires:
        log("ROW 0c FIRES: no usable global anchor correction exists. VALIDITY, STOP.")
        return result

    # ROW 0d: 4 chronological ts-quartiles (sample is construction-sorted by ts
    # already -- plive_population.build_p_hit_population's own docstring), each
    # swept independently from the SAME precomputed matrix (no extra extraction).
    n = len(contexts)
    quartile_idx = [list(a) for a in np.array_split(np.arange(n), 4)]
    quartile_results = []
    max_delta = 0.0
    for qi, idx in enumerate(quartile_idx):
        if len(idx) == 0:
            quartile_results.append({"quartile": qi, "n_rows": 0, "n_clusters": 0,
                                      "offset": None, "delta_vs_pooled": None})
            continue
        q_ts = sorted({matrix["ts"][i] for i in idx})
        q_curve = pooled_curve(matrix, idx)
        q_best = argmin_curve(q_curve)
        q_offset = q_best["dt_offset"] if q_best else None
        delta = abs(q_offset - offset) if q_offset is not None else None
        if delta is not None:
            max_delta = max(max_delta, delta)
        quartile_results.append({
            "quartile": qi, "n_rows": len(idx), "n_clusters": len(q_ts),
            "ts_range": [q_ts[0], q_ts[-1]] if q_ts else None,
            "offset": q_offset, "offset_median_ber": q_best["median_ber"] if q_best else None,
            "delta_vs_pooled": delta,
        })
        log("  quartile %d: n_rows=%d n_clusters=%d ts=[%s..%s] argmin=%s delta_vs_pooled=%s"
            % (qi, len(idx), len(q_ts), q_ts[0] if q_ts else "?", q_ts[-1] if q_ts else "?",
               "%+.2fs" % q_offset if q_offset is not None else "NONE",
               "%.2fs" % delta if delta is not None else "n/a"))

    row0d_fires = any((qr["delta_vs_pooled"] is not None and qr["delta_vs_pooled"] > ROW_0D_TOL_S)
                       for qr in quartile_results)
    log("\nROW 0d: max |quartile_offset - pooled_offset| = %.3fs (bound <=%.2fs) -> %s"
        % (max_delta, ROW_0D_TOL_S, "FIRES" if row0d_fires else "clear"))
    result["row_0d"] = {"fires": row0d_fires, "quartiles": quartile_results,
                         "max_delta_vs_pooled": max_delta, "tolerance_s": ROW_0D_TOL_S}
    if row0d_fires:
        log("ROW 0d FIRES: the offset is not one constant across the cycle timeline. "
            "VALIDITY, STOP, escalate.")
    return result


# =============================================================================
# Stage 2 -- GRID vs REFINED on P-LIVE at the corrected anchor
# =============================================================================

def measure_stage2_row(ex: ExtractLLRs, refiner: Refiner, wav_cache: WavCache,
                        row: dict, offset: float) -> dict:
    try:
        pcm = wav_cache.get(row["ts"])
    except FileNotFoundError:
        return {"reason": "no_wav"}

    freq_int = round(row["anchor_freq_hz"])
    corrected_dt = float(row["anchor_dt"]) + offset

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc0, llr_grid = ex.extract_at(pcm, float(freq_int), corrected_dt)
    if rc0 != 0 or llr_grid is None:
        return {"reason": "grid_extract_rc_%d" % rc0}

    delta_f, delta_t, refine_score, coarse_dt_samp, fine_dt_samp, rc_refine = \
        refiner.refine(pcm, freq_int, corrected_dt)
    if rc_refine != 0:
        return {"reason": "refine_rc_%d" % rc_refine}

    refined_freq = freq_int + delta_f
    refined_dt = corrected_dt + delta_t
    rc_ref, llr_refined = ex.extract_at(pcm, refined_freq, refined_dt)
    if rc_ref != 0 or llr_refined is None:
        return {"reason": "refined_extract_rc_%d" % rc_ref}

    ber_grid = hard_decision_ber(llr_grid, true_bits)
    ber_refined = hard_decision_ber(llr_refined, true_bits)

    return {
        "ts": row["ts"],
        "corpus": row["corpus"],
        "ber_grid": ber_grid,
        "ber_refined": ber_refined,
        "d_ber": d_ber_row(ber_grid, ber_refined),
        "crosses": f_cross_row(ber_grid, ber_refined),
        "delta_f_hz": delta_f,
        "delta_t_s": delta_t,
        "corrected_dt": corrected_dt,
        "anchor_freq_hz": freq_int,
    }


def f_cross_cluster_bootstrap(rows: list[dict], n_draws: int = 2000, seed: int = PART_A_SEED) -> dict:
    """Cluster bootstrap over `ts` for f_cross's ALL-ROWS-denominator fraction
    (matching run_n1.py's own f_cross convention: sum(crosses)/len(rows), NOT the
    'crossable-only' denominator n5_stats.f_cross uses for a different purpose).
    Spec Sec.4 mandatory deliverable: 'f_cross ... with its cluster CI and its
    rule-of-three bound if n_cross = 0'."""
    by_ts: dict[str, list[bool]] = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r["crosses"])
    ts_list = sorted(by_ts)
    n_clusters = len(ts_list)
    n_cross = sum(1 for r in rows if r["crosses"])
    point = (n_cross / len(rows)) if rows else float("nan")
    rule_of_three = (3.0 / n_clusters) if (n_cross == 0 and n_clusters > 0) else None

    if n_clusters < 2 or not rows:
        return {"point": point, "ci95": [float("nan"), float("nan")], "se": float("nan"),
                "n_draws": 0, "n_clusters": n_clusters, "n_cross": n_cross,
                "rule_of_three_bound": rule_of_three, "seed": seed}

    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_draws):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        vals: list[bool] = []
        for i in pick:
            vals.extend(by_ts[ts_list[i]])
        if vals:
            draws.append(sum(vals) / len(vals))
    arr = np.array(draws)
    return {
        "point": point,
        "ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
        "se": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
        "n_draws": len(arr), "n_clusters": n_clusters, "n_cross": n_cross,
        "rule_of_three_bound": rule_of_three, "seed": seed,
    }


def run_stage2(ex: ExtractLLRs, refiner: Refiner, offset: float, log, n_draws: int) -> dict:
    log("\n" + "=" * 90)
    log("STAGE 2 -- GRID vs REFINED on P-LIVE (PRIMARY) at anchor_dt %+.2fs" % offset)
    log("=" * 90)
    paths = corpus_paths(PRIMARY_CORPUS)

    population = build_p_live_population(PRIMARY_CORPUS)
    n_population = len(population)
    n_pop_clusters = len({r["ts"] for r in population})
    log("  P-LIVE population (dry count): n_rows=%d n_clusters=%d" % (n_population, n_pop_clusters))

    row0b_fires = n_population < ROW_0B_MIN_ROWS or n_pop_clusters < ROW_0B_MIN_CLUSTERS
    log("ROW 0b: n_rows=%d (>=%d) n_clusters=%d (>=%d) -> %s"
        % (n_population, ROW_0B_MIN_ROWS, n_pop_clusters, ROW_0B_MIN_CLUSTERS,
           "FIRES" if row0b_fires else "clear"))
    result: dict = {
        "population_n_rows": n_population, "population_n_clusters": n_pop_clusters,
        "row_0b": {"fires": row0b_fires, "n_rows": n_population, "n_clusters": n_pop_clusters},
    }
    if row0b_fires:
        log("ROW 0b FIRES: P-LIVE on PRIMARY is underpowered. VALIDITY, STOP, escalate.")
        return result

    wav_cache = WavCache(paths["wsjtx_wav_dir"])
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        r = measure_stage2_row(ex, refiner, wav_cache, row, offset)
        if r is None or "reason" in r:
            reason = r["reason"] if r else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(r)
        if (i + 1) % 3000 == 0:
            log("  ... %d/%d processed (%d measured, %.1fs elapsed)"
                % (i + 1, n_population, len(rows), time.time() - t0))
    elapsed = time.time() - t0
    n_measured = len(rows)
    n_clusters_measured = len({r["ts"] for r in rows})
    log("  measured %d/%d rows (%.1fs). n_clusters_measured=%d. drop_reasons=%s"
        % (n_measured, n_population, elapsed, n_clusters_measured, reasons))
    result["n_measured"] = n_measured
    result["n_clusters_measured"] = n_clusters_measured
    result["drop_reasons"] = reasons
    result["measure_elapsed_s"] = elapsed

    if n_measured == 0:
        log("No rows measured -- cannot evaluate 0e/0f/0g. STOP.")
        result["final_row"] = "no_rows_measured"
        return result

    ber_grid_vals = [r["ber_grid"] for r in rows]
    median_ber_grid = float(st.median(ber_grid_vals))
    abs_dt = [abs(r["delta_t_s"]) for r in rows]
    abs_df = [abs(r["delta_f_hz"]) for r in rows]
    median_abs_dt = float(st.median(abs_dt))
    median_abs_df = float(st.median(abs_df))
    frac_rail_t = float(sum(1 for v in abs_dt if v >= ROW_0E_RAIL_T_THRESHOLD) / n_measured)
    frac_rail_f = float(sum(1 for v in abs_df if v >= FRAC_RAIL_F_THRESHOLD) / n_measured)

    result["median_ber_grid"] = median_ber_grid
    result["median_abs_delta_t_s"] = median_abs_dt
    result["median_abs_delta_f_hz"] = median_abs_df
    result["frac_rail_t"] = frac_rail_t
    result["frac_rail_f_descriptive"] = frac_rail_f
    result["ber_grid_deciles"] = decile_table(ber_grid_vals)

    log("\nmedian BER_grid=%.2f%%  median|delta_t|=%.4fs  median|delta_f|=%.3fHz"
        % (median_ber_grid * 100, median_abs_dt, median_abs_df))
    log("frac_rail_t (|delta_t|>=%.4fs)=%.1f%%  frac_rail_f (|delta_f|>=%.3fHz, descriptive)=%.1f%%"
        % (ROW_0E_RAIL_T_THRESHOLD, frac_rail_t * 100, FRAC_RAIL_F_THRESHOLD, frac_rail_f * 100))

    # ROW 0e
    row0e_fires = frac_rail_t >= ROW_0E_FRAC_RAIL_T_MAX
    log("\nROW 0e: frac_rail_t=%.1f%% (bound <%.0f%%) -> %s"
        % (frac_rail_t * 100, ROW_0E_FRAC_RAIL_T_MAX * 100, "FIRES" if row0e_fires else "clear"))
    result["row_0e"] = {"fires": row0e_fires, "frac_rail_t": frac_rail_t, "bound": ROW_0E_FRAC_RAIL_T_MAX}
    if row0e_fires:
        log("ROW 0e FIRES: refiner railed on the majority. VALIDITY, STOP, escalate.")
        return result

    # ROW 0f
    row0f_fires = median_abs_dt <= ROW_0F_DT_FLOOR_S or median_abs_df <= ROW_0F_DF_FLOOR_HZ
    log("ROW 0f: median|dt|=%.4fs (floor %.4fs) OR median|df|=%.3fHz (floor %.2fHz) -> %s"
        % (median_abs_dt, ROW_0F_DT_FLOOR_S, median_abs_df, ROW_0F_DF_FLOOR_HZ,
           "FIRES" if row0f_fires else "clear"))
    result["row_0f"] = {"fires": row0f_fires, "median_abs_dt": median_abs_dt,
                         "median_abs_df": median_abs_df, "dt_floor": ROW_0F_DT_FLOOR_S,
                         "df_floor": ROW_0F_DF_FLOOR_HZ}
    if row0f_fires:
        log("ROW 0f FIRES: no material treatment motion. VALIDITY, STOP.")
        return result

    # ROW 0g
    row0g_fires = not (ROW_0G_LO <= median_ber_grid <= ROW_0G_HI)
    log("ROW 0g: median_ber_grid=%.2f%% outside [%.0f%%,%.0f%%] two-sided -> %s"
        % (median_ber_grid * 100, ROW_0G_LO * 100, ROW_0G_HI * 100,
           "FIRES" if row0g_fires else "clear"))
    result["row_0g"] = {"fires": row0g_fires, "median_ber_grid": median_ber_grid,
                         "band": [ROW_0G_LO, ROW_0G_HI]}
    if row0g_fires:
        log("ROW 0g FIRES: %s. VALIDITY, STOP, escalate."
            % ("chance-level (structural)" if median_ber_grid > ROW_0G_HI
               else "implausibly low (suspect membership leak)"))
        return result

    # -- Primary statistics --------------------------------------------------
    log("\n" + "=" * 90)
    log("Primary statistics")
    log("=" * 90)
    bootstrap = cluster_bootstrap_median_diff(rows, n_draws=n_draws)
    f_cross_boot = f_cross_cluster_bootstrap(rows, n_draws=n_draws)
    log("d_ber (paired median BER_grid - BER_refined): point=%+.2fpp mean=%+.2fpp se=%.3fpp "
        "CI95=[%+.2f,%+.2f]pp p=%.4f (n_rows=%d n_clusters=%d n_draws=%d)"
        % (bootstrap["point_estimate"] * 100, bootstrap["mean"] * 100, bootstrap["se"] * 100,
           bootstrap["ci95"][0] * 100, bootstrap["ci95"][1] * 100, bootstrap["p_two_sided"],
           bootstrap["n_rows"], bootstrap["n_clusters"], bootstrap["n_draws"]))
    log("f_cross (ALL-rows denominator, N1 convention): point=%.2f%% CI95=[%.2f,%.2f]%% "
        "n_cross=%d n_clusters=%d rule_of_three_bound=%s"
        % (f_cross_boot["point"] * 100, f_cross_boot["ci95"][0] * 100, f_cross_boot["ci95"][1] * 100,
           f_cross_boot["n_cross"], f_cross_boot["n_clusters"],
           "%.4f%%" % (f_cross_boot["rule_of_three_bound"] * 100) if f_cross_boot["rule_of_three_bound"]
           is not None else "n/a"))
    result["d_ber"] = bootstrap
    result["f_cross"] = f_cross_boot

    # -- Gate: ROW 1 -> ROW 3 -> ROW 2 -> ROW 4, strict order -----------------
    log("\n" + "=" * 90)
    log("ROW 1 / 3 / 2 / 4 -- the gate, strict order")
    log("=" * 90)
    d_ber_pt = bootstrap["point_estimate"]
    ci_lo, ci_hi = bootstrap["ci95"]
    f_cross_pt = f_cross_boot["point"]

    row1_fires = (d_ber_pt >= ROW_1_D_BER_MIN and ci_lo > ROW_1_CI_LO_MIN
                  and f_cross_pt >= ROW_1_F_CROSS_MIN)
    row3_fires = (not row1_fires) and (ci_hi < ROW_3_CI_HI_MAX and d_ber_pt <= ROW_3_D_BER_MAX)
    row2_fires = (not row1_fires and not row3_fires) and (
        ci_hi >= 0.0 and ci_lo > ROW_2_CI_LO_MIN and ci_hi < ROW_2_CI_HI_MAX
        and abs(d_ber_pt) <= ROW_2_D_BER_ABS_MAX)

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES (BENEFIT): d_ber=%+.2fpp (>=%.0fpp) AND CI_lo=%+.2fpp (>%.0fpp) AND "
            "f_cross=%.1f%% (>=%.0f%%)."
            % (d_ber_pt * 100, ROW_1_D_BER_MIN * 100, ci_lo * 100, ROW_1_CI_LO_MIN * 100,
               f_cross_pt * 100, ROW_1_F_CROSS_MIN * 100))
        log("CONSEQUENCE: refinement helps materially on the miss population. Does NOT "
            "rehabilitate R2 (spec Sec.7) -- escalate to the Captain.")
    elif row3_fires:
        final_row = "3"
        log("ROW 3 FIRES (HARM): CI_hi=%+.2fpp (<%.0fpp) AND d_ber=%+.2fpp (<=%.0fpp)."
            % (ci_hi * 100, ROW_3_CI_HI_MAX * 100, d_ber_pt * 100, ROW_3_D_BER_MAX * 100))
        log("CONSEQUENCE: N1's -4.02pp harm REPLICATES at scale. Limb 1 is not merely dead "
            "but actively costly; strengthens N1's ROW 2, does not soften it.")
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES (NULL): CI_hi=%+.2fpp (>=0) AND CI_lo=%+.2fpp (>%.0fpp) AND "
            "CI_hi<%.0fpp AND |d_ber|=%.2fpp (<=%.0fpp)."
            % (ci_hi * 100, ci_lo * 100, ROW_2_CI_LO_MIN * 100, ROW_2_CI_HI_MAX * 100,
               abs(d_ber_pt) * 100, ROW_2_D_BER_ABS_MAX * 100))
        log("CONSEQUENCE: no material effect either way. N1's ROW 2 replicates at scale.")
    else:
        final_row = "4"
        log("ROW 4 (residue): d_ber=%+.2fpp CI95=[%+.2f,%+.2f]pp f_cross=%.1f%%."
            % (d_ber_pt * 100, ci_lo * 100, ci_hi * 100, f_cross_pt * 100))
        log("CONSEQUENCE: report the interval, do not pick a side, escalate.")

    result["final_row"] = final_row
    return result


# =============================================================================
# main
# =============================================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("STAGE 2 -- combined pre-registration (anchor-offset arm + P-LIVE harm replication)")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        _write(args.out_dir, {"hk025": hk025, "final_row": "REFUSED"}, log_lines)
        return 1

    bundle: dict = {"hk025": hk025}

    # -- ROW 0a -----------------------------------------------------------------
    log("\nLoading DLL: %s" % args.dll_path)
    try:
        ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                          expected_shim_version=EXPECTED_SHIM_VERSION)
        refiner = Refiner(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                           expected_shim_version=EXPECTED_SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0a"
        bundle["row_0a"] = {"fires": True, "error": str(e)}
        _write(args.out_dir, bundle, log_lines)
        return 2
    log("ROW 0a clear: DLL SHA256 asserted (%s...), shim version %d confirmed on BOTH bindings."
        % (args.dll_sha256[:16], ex.version))
    bundle["row_0a"] = {"fires": False}

    # -- Part A on PRIMARY --------------------------------------------------
    part_a = run_part_a(ex, PRIMARY_CORPUS, log, descriptive_only=False)
    bundle["part_a_primary"] = part_a

    proceed_to_stage2 = (
        part_a.get("sign_unit_test_passed") is True
        and not part_a.get("row_0c", {}).get("fires", True)
        and not part_a.get("row_0d", {}).get("fires", True)
    )

    if not proceed_to_stage2:
        bundle["final_row"] = "part_a_blocked"
        log("\nPart A did not clear -- Stage 2 measurement SKIPPED. Proceeding to the "
            "descriptive second-corpus sweep only, per Sec.6 item 5 (nothing gates on it).")
    else:
        offset = part_a["offset"]
        stage2 = run_stage2(ex, refiner, offset, log, n_draws=args.n_draws)
        bundle["stage2"] = stage2
        bundle["final_row"] = stage2.get("final_row", "stage2_blocked")

    # -- Part A item 2: second-corpus sweep, descriptive, always attempted --
    try:
        part_a2 = run_part_a(ex, SECOND_CORPUS, log, descriptive_only=True)
        bundle["part_a_second_corpus"] = part_a2
    except Exception as e:  # noqa: BLE001 -- descriptive item, must not crash the whole report
        log("\nPart A item 2 (second corpus) raised %s: %s -- reported as failed, "
            "does not affect any gate." % (type(e).__name__, e))
        bundle["part_a_second_corpus_error"] = "%s: %s" % (type(e).__name__, e)

    log("\n" + "=" * 90)
    log("FINAL ROW: %s" % bundle.get("final_row"))
    log("=" * 90)

    _write(args.out_dir, bundle, log_lines)
    log("\nWrote results/stage2_report.json, results/stage2_run.log")
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "stage2_report.json"), bundle)
    with open(os.path.join(out_dir, "stage2_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
