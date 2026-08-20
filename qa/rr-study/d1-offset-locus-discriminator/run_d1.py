#!/usr/bin/env python3
"""D1 -- which file carries the offset: shared capture/save path, or ours alone.

Spec: qa/rr-study/2026-08-19-1226-architect-to-qa-spec-d1-offset-locus-discriminator-and-fix-shape.md
("the spec", all Sec. references below are to it unless stated otherwise).

ONE MEASUREMENT: re-run AO1's K sweep VERBATIM (run_ao1.run_k_sweep, reused by
import, not re-implemented) with the WAV directory repointed from owsfz/wav/ to
wsjt-x/wav/. Same anchor (the reference's own freq/dt), same true codeword, same
49-point grid, same seeded sample (run_ao1.AO1_SEED, unchanged), same corpus
(PRIMARY, 20260803_live_run_1713). Call the result K_ref; AO1's already-published
K = +0.650s (read MECHANICALLY from results/ao1_report.json, never hand-typed --
MEMORY.md: "NEVER HARDCODE 0.65/0.70s") is K_ours.

WHAT THIS RUNS, Sec.2 order:
  1. ROW 0a -- DLL SHA256 re-hashed from disk, asserted against the pin.
  2. Build matched pairs on PRIMARY (ao1_common.build_matched_pairs, unchanged),
     draw the SAME seeded sample AO1 drew (run_ao1.AO1_SEED, same sample_rows).
  3. Load contexts from wsjt-x/wav/ (D1's own leg), anchored at the reference's
     own (freq, dt) -- run_ao1.load_contexts_for_sample, reused verbatim.
  4. ROW 0b -- power: n_measured/n_clusters_measured on THIS load.
  5. ROW 0c -- mandatory sign unit test (run_stage2.run_sign_test, reused
     verbatim), on these wsjt-x-wav contexts.
  6. Sweep K_ref: run_stage2.sweep_matrix/pooled_curve/argmin_curve, reused
     verbatim via run_ao1.run_k_sweep's own code path.
  7. ROW 0d -- median BER_V0 at K_ref's argmin, two-sided plausibility.
  8. Recompute AO1's OWN context set (owsfz/wav/, same sample) -- cheap (no
     re-sweep: only WAV load + true_codeword lookup) -- for ROW 0e's overlap
     test, and as a sanity cross-check against AO1's own stored counts
     (n_measured=551, n_clusters_measured=519, drop_reasons={'no_true_codeword':
     49}), which additionally corroborates "same seeded sample" mechanically
     rather than by assertion.
  9. ROW 0e -- cycle-set overlap (filename-matched) between the wsjt-x-wav
     contexts and the recomputed owsfz-wav contexts.
 10. Main rows 1-4 (Sec.2.2), strict order, theta=0.10s, INTEGER GRID-STEP UNITS
     throughout (Sec.2.4 -- grid=0.05s, theta=2 steps; round(x/0.05) before every
     comparison, never raw floats).
 11. Report. STOP. No Sec.3 (the OpenSpec change) in this run, per the spec's own
     Sec.4 order of work item 2.

NFR-021: message TEXT never touches this module directly -- every context-loading
and sweep call is a verbatim re-use of run_ao1.py's own functions, which already
carry that discipline (ex.true_codeword, in-process only, never retained).

No src/, no Developer session, no DLL rebuild, no capture run -- HK-011 not
engaged by D1 itself (spec Sec.6).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "ao1-production-time-origin-offset"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH, DEFAULT_DLL_SHA256, EXPECTED_SHIM_VERSION  # noqa: E402
from run_stage1r import deterministic_sample  # noqa: E402 -- same seeded, sort-stabilised sample
from run_stage2 import argmin_curve, pooled_curve, run_sign_test, sweep_matrix  # noqa: E402,F401 -- reused verbatim

import ao1_common as AO1C  # noqa: E402
import run_ao1 as AO1  # noqa: E402 -- reused verbatim, per the spec's own instruction (Sec.2)

AO1_REPORT_PATH = os.path.join(REPO_ROOT, "qa", "rr-study", "ao1-production-time-origin-offset",
                                "results", "ao1_report.json")

# -- Sec.2.2 bars, all lifted verbatim from the spec, not chosen here ------------
THETA = 0.10                    # reference instrument's own reporting resolution (Sec.5 of AO1)
GRID_STEP = 0.05                # M3's 49-point grid step, unchanged
ROW_3_DIFF_TOL = 0.10           # Sec.2.2 ROW 1/3 boundary -- same value as THETA, different role
ROW_0B_MIN_ROWS = 500
ROW_0B_MIN_CLUSTERS = 200
ROW_0D_LO, ROW_0D_HI = 0.01, 0.15
ROW_0E_MIN_OVERLAP = 400

# AO1's own sanity-check numbers (results/ao1_run.log line 16 / ao1_report.json
# primary_sample) -- used ONLY to log a corroboration, never to gate; ROW 0e is
# the mechanical gate, this is a second, independent look at the same claim.
AO1_KNOWN_N_MEASURED = 551
AO1_KNOWN_N_CLUSTERS_MEASURED = 519


def steps(x: float) -> int:
    """Sec.2.4 float discipline: every comparison in INTEGER GRID-STEP UNITS."""
    return round(x / GRID_STEP)


# =============================================================================
# HK-025 -- independent re-classification, per Sec.2.3's own instruction to test
# the spec's claim ("I assert no row is diagnostic") rather than adopt it.
# =============================================================================

def hk025_check() -> dict:
    """Re-derived fresh against Sec.2.3's table, not copied from it.

    0a: fires -> unidentified binary, every downstream number describes an
        unknown build. Clears -> pinned build. VALIDITY, differ, not diagnostic.
    0b: fires -> too few rows/clusters loaded from wsjt-x/wav/ to resolve K_ref
        against a 0.10s bound at all. Clears -> powered to resolve it. PRECISION,
        differ (STOP-as-underpowered vs proceed-to-sweep), not diagnostic.
    0c: fires -> the sign convention this run's own extraction exercises is
        unverified, and every main row (1-4) depends on the SIGN of K_ref and of
        K_ref-K_ours. Clears -> verified. VALIDITY, differ, not diagnostic.
    0d: fires -> K_ref's argmin reads noise on wsjt-x/wav/, not a position -- the
        whole discriminator is then comparing a position (K_ours) against noise,
        which answers nothing. Clears -> K_ref is a position. VALIDITY, differ.
    0e: fires -> the wsjt-x-wav sweep and the owsfz-wav sweep that produced
        K_ours are not the same cycle set -- ROW 1 vs ROW 2 would then be
        confounded by population, not locus. Clears -> like-for-like. VALIDITY,
        differ, not diagnostic.

    No row evaluates to the same downstream action on both branches -> no
    HK-021(k) diagnostic row, no HK-025 refusal. Concurs with Sec.2.3."""
    reasons = {
        "0a": ("VALIDITY", "unidentified binary invalidates every downstream number"),
        "0b": ("PRECISION", "underpowered to resolve K_ref against theta -- "
               "escalate vs proceed to sweep"),
        "0c": ("VALIDITY", "sign convention unverified, and sign drives every main row"),
        "0d": ("VALIDITY", "K_ref's argmin would be noise, not a position"),
        "0e": ("VALIDITY", "K_ref vs K_ours confounded by population, not locus, if not like-for-like"),
    }
    classification = {k: {"class": c, "reason": r} for k, (c, r) in reasons.items()}
    return {"classification": classification, "refusal": False, "concurs_with_spec": True}


# =============================================================================
# main
# =============================================================================

def main() -> int:
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("D1 -- which file carries the offset (locus discriminator)")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    bundle: dict = {"hk025": hk025}
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        bundle["final_row"] = "REFUSED"
        _write(bundle, log_lines)
        return 1

    # -- ROW 0a ---------------------------------------------------------------
    log("\nLoading DLL: %s" % DEFAULT_DLL_PATH)
    try:
        ex = ExtractLLRs(DEFAULT_DLL_PATH, verify=True, expected_sha256=DEFAULT_DLL_SHA256,
                          expected_shim_version=EXPECTED_SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0a"
        bundle["row_0a"] = {"fires": True, "error": str(e)}
        _write(bundle, log_lines)
        return 2
    log("ROW 0a clear: DLL SHA256 asserted (%s...), shim version %d confirmed."
        % (DEFAULT_DLL_SHA256[:16], ex.version))
    bundle["row_0a"] = {"fires": False}

    # -- Build matched pairs on PRIMARY, same code AO1 used ---------------------
    log("\n" + "=" * 90)
    log("Building matched-pair population on PRIMARY (%s) -- same code, same corpus as AO1"
        % AO1.PRIMARY_CORPUS)
    log("=" * 90)
    pairs, diag = AO1C.build_matched_pairs(AO1.PRIMARY_CORPUS)
    log("  %s" % diag)
    bundle["primary_matched_pair_diagnostics"] = diag
    paths = AO1C.corpus_paths(AO1.PRIMARY_CORPUS)

    sample = deterministic_sample(pairs, min(AO1.SAMPLE_ROWS, len(pairs)), AO1.AO1_SEED)
    log("  drew the SAME seeded sample AO1 drew: seed=%d n=%d (AO1.AO1_SEED, AO1.SAMPLE_ROWS, "
        "unchanged)" % (AO1.AO1_SEED, len(sample)))

    # -- Load D1's own contexts from wsjt-x/wav/, reference's own (freq, dt) ---
    log("\n" + "=" * 90)
    log("Loading contexts from wsjt-x/wav/ (%s), anchored at the reference's own (freq, dt) -- "
        "run_ao1.load_contexts_for_sample, reused verbatim" % paths["wsjtx_wav_dir"])
    log("=" * 90)
    contexts_ref, drop_reasons_ref = AO1.load_contexts_for_sample(ex, paths["wsjtx_wav_dir"], sample, log)
    n_measured_ref = len(contexts_ref)
    n_clusters_measured_ref = len({c[0] for c in contexts_ref})
    bundle["ref_sample"] = {"n_rows": len(sample), "n_clusters": len({p["ts"] for p in sample}),
                             "n_measured": n_measured_ref, "n_clusters_measured": n_clusters_measured_ref,
                             "drop_reasons": drop_reasons_ref}

    # -- ROW 0b -----------------------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 0b -- power: n_measured/n_clusters_measured on the wsjt-x-wav load")
    log("=" * 90)
    row0b_fires = n_measured_ref < ROW_0B_MIN_ROWS or n_clusters_measured_ref < ROW_0B_MIN_CLUSTERS
    log("n_measured=%d (>=%d) n_clusters_measured=%d (>=%d) -> %s"
        % (n_measured_ref, ROW_0B_MIN_ROWS, n_clusters_measured_ref, ROW_0B_MIN_CLUSTERS,
           "FIRES" if row0b_fires else "clear"))
    bundle["row_0b"] = {"fires": row0b_fires, "n_measured": n_measured_ref,
                         "n_clusters_measured": n_clusters_measured_ref}
    if row0b_fires:
        log("\nROW 0b FIRES: underpowered to resolve theta=%.2fs. VALIDITY/PRECISION, STOP." % THETA)
        bundle["final_row"] = "0b"
        _write(bundle, log_lines)
        return 3

    # -- ROW 0c: mandatory sign unit test (Stage 2's construction, verbatim) ---
    sign_ok = run_sign_test(ex, contexts_ref, log)
    bundle["row_0c"] = {"fires": not sign_ok}
    if not sign_ok:
        log("\nROW 0c FIRES: sign unit test failed. VALIDITY, STOP. NO VERDICT.")
        bundle["final_row"] = "0c"
        _write(bundle, log_lines)
        return 4

    # -- Sweep K_ref --------------------------------------------------------------
    log("\n" + "=" * 90)
    log("Sweeping K_ref -- wsjt-x/wav/, M3's 49-point grid, reused verbatim")
    log("=" * 90)
    matrix = sweep_matrix(ex, contexts_ref, log, label="D1_ref(wsjt-x wav)")
    assert len(matrix["offsets"]) == 49, "grid must be the same 49-point M3 grid AO1 used"
    all_idx = list(range(len(contexts_ref)))
    pooled = pooled_curve(matrix, all_idx)
    best = argmin_curve(pooled)
    K_ref = best["dt_offset"] if best else None
    K_ref_ber = best["median_ber"] if best else None
    bundle["sweep_table_ref"] = pooled
    bundle["K_ref"] = K_ref
    bundle["K_ref_median_ber"] = K_ref_ber
    log("  K_ref: argmin=%s median_BER_V0=%s"
        % ("%+.3fs" % K_ref if K_ref is not None else "NONE",
           "%.2f%%" % (K_ref_ber * 100) if K_ref_ber is not None else "n/a"))

    # -- ROW 0d -------------------------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 0d -- median BER_V0 at K_ref's argmin, two-sided plausibility")
    log("=" * 90)
    row0d_fires = K_ref_ber is None or not (ROW_0D_LO <= K_ref_ber <= ROW_0D_HI)
    log("median_BER_V0(K_ref=%s)=%s outside [%.0f%%,%.0f%%] two-sided -> %s"
        % ("%+.3fs" % K_ref if K_ref is not None else "n/a",
           "%.2f%%" % (K_ref_ber * 100) if K_ref_ber is not None else "n/a",
           ROW_0D_LO * 100, ROW_0D_HI * 100, "FIRES" if row0d_fires else "clear"))
    bundle["row_0d"] = {"fires": row0d_fires, "k_ref": K_ref, "k_ref_median_ber": K_ref_ber,
                         "band": [ROW_0D_LO, ROW_0D_HI]}
    if row0d_fires:
        log("\nROW 0d FIRES: the sweep is not reading on wsjt-x/wav/. VALIDITY, STOP.")
        bundle["final_row"] = "0d"
        _write(bundle, log_lines)
        return 5

    # -- Recompute AO1's own context set (owsfz/wav/, same sample) -- cheap: ----
    # WAV load + true_codeword lookup only, NO re-sweep. Doubles as a sanity
    # cross-check against AO1's own stored counts.
    log("\n" + "=" * 90)
    log("Recomputing AO1's own context set (owsfz/wav/, same sample) for ROW 0e's overlap "
        "test -- cheap (no re-sweep), and a sanity cross-check against AO1's stored counts")
    log("=" * 90)
    contexts_ao1, drop_reasons_ao1 = AO1.load_contexts_for_sample(ex, paths["owsfz_wav_dir"], sample, log)
    n_measured_ao1 = len(contexts_ao1)
    n_clusters_measured_ao1 = len({c[0] for c in contexts_ao1})
    sanity_match = (n_measured_ao1 == AO1_KNOWN_N_MEASURED
                     and n_clusters_measured_ao1 == AO1_KNOWN_N_CLUSTERS_MEASURED
                     and drop_reasons_ao1 == {"no_true_codeword": 49})
    log("  recomputed: n_measured=%d n_clusters_measured=%d drop_reasons=%s"
        % (n_measured_ao1, n_clusters_measured_ao1, drop_reasons_ao1))
    log("  AO1's stored report (results/ao1_report.json / ao1_run.log line 16): "
        "n_measured=%d n_clusters_measured=%d drop_reasons={'no_true_codeword': 49}"
        % (AO1_KNOWN_N_MEASURED, AO1_KNOWN_N_CLUSTERS_MEASURED))
    log("  sanity cross-check (same seeded sample, independently confirmed): %s"
        % ("MATCH" if sanity_match else "MISMATCH -- pairs/sample may have changed since AO1 ran"))
    bundle["ao1_recompute_sanity"] = {
        "n_measured": n_measured_ao1, "n_clusters_measured": n_clusters_measured_ao1,
        "drop_reasons": drop_reasons_ao1, "matches_ao1_report": sanity_match,
    }

    # -- ROW 0e -------------------------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 0e -- cycle-set overlap (filename-matched), wsjt-x-wav contexts vs owsfz-wav contexts")
    log("=" * 90)
    ts_ref = {c[0] for c in contexts_ref}
    ts_ao1 = {c[0] for c in contexts_ao1}
    overlap = len(ts_ref & ts_ao1)
    row0e_fires = overlap < ROW_0E_MIN_OVERLAP
    log("overlap=%d (>=%d) [|ts_ref|=%d |ts_ao1|=%d] -> %s"
        % (overlap, ROW_0E_MIN_OVERLAP, len(ts_ref), len(ts_ao1), "FIRES" if row0e_fires else "clear"))
    bundle["row_0e"] = {"fires": row0e_fires, "overlap": overlap, "min_overlap": ROW_0E_MIN_OVERLAP,
                         "n_ts_ref": len(ts_ref), "n_ts_ao1": len(ts_ao1)}
    if row0e_fires:
        log("\nROW 0e FIRES: not the same cycle set AO1 swept -- K_ref vs K_ours is confounded "
            "by population. VALIDITY, STOP.")
        bundle["final_row"] = "0e"
        _write(bundle, log_lines)
        return 6

    # -- K_ours: read MECHANICALLY from AO1's own stored report, never hand-typed
    log("\n" + "=" * 90)
    log("Reading K_ours from AO1's own stored report (%s) -- MEMORY.md: never hardcode "
        "0.65/0.70s" % AO1_REPORT_PATH)
    log("=" * 90)
    with open(AO1_REPORT_PATH, encoding="ascii", errors="replace") as fh:
        ao1_report = json.load(fh)
    K_ours = ao1_report["K"]
    ao1_final_row = ao1_report.get("final_row")
    log("  K_ours=%+.3fs (AO1 final_row=%s, expected '3' per the contradiction this spec exists "
        "to resolve)" % (K_ours, ao1_final_row))
    bundle["K_ours"] = K_ours
    bundle["ao1_final_row_at_read_time"] = ao1_final_row

    # -- Main rows, strict order, INTEGER GRID-STEP UNITS (Sec.2.4) -------------
    log("\n" + "=" * 90)
    log("MAIN ROWS -- strict order, theta=%.2fs=%d steps, grid=%.2fs, all comparisons in "
        "integer grid-step units" % (THETA, steps(THETA), GRID_STEP))
    log("=" * 90)
    k_ref_steps = steps(K_ref)
    k_ours_steps = steps(K_ours)
    diff_steps = abs(k_ref_steps - k_ours_steps)
    theta_steps = steps(THETA)
    row3_tol_steps = steps(ROW_3_DIFF_TOL)
    log("K_ref=%+.3fs (%+d steps)  K_ours=%+.3fs (%+d steps)  |K_ref-K_ours|=%d steps "
        "(theta=%d steps, ROW3 tol=%d steps)"
        % (K_ref, k_ref_steps, K_ours, k_ours_steps, diff_steps, theta_steps, row3_tol_steps))

    abs_k_ref_steps = abs(k_ref_steps)
    abs_k_ours_steps = abs(k_ours_steps)

    if abs_k_ref_steps >= theta_steps and diff_steps <= row3_tol_steps:
        final_row = "1"
        log("\nROW 1 FIRES: |K_ref|>=theta AND |K_ref-K_ours|<=0.10s. Locus (A): SHARED. Both "
            "files carry the same offset. CycleFramer's window placement is NOT the defect -- "
            "the 12:17Z Developer recommendation is WITHDRAWN IN FULL. No OpenSpec change on "
            "this branch.")
    elif abs_k_ref_steps < theta_steps and abs_k_ours_steps >= theta_steps:
        final_row = "2"
        log("\nROW 2 FIRES: |K_ref|<theta AND |K_ours|>=theta. Locus (B): OURS. The reference's "
            "file is clean, ours is displaced. F1 must be explained, not ignored. OpenSpec "
            "change proceeds per Sec.3.")
    elif abs_k_ref_steps >= theta_steps and diff_steps > row3_tol_steps:
        final_row = "3"
        log("\nROW 3 FIRES: |K_ref|>=theta AND |K_ref-K_ours|>0.10s. TWO EFFECTS, not one. Both "
            "files displaced, by different amounts. NO single fix. Escalate.")
    else:
        final_row = "4"
        log("\nROW 4 FIRES: |K_ref|<theta AND |K_ours|<theta. Contradicts AO1's own published K "
            "on the same corpus and sample. Instrument failure, not a finding. Escalate.")

    bundle["final_row"] = final_row
    bundle["theta"] = THETA
    bundle["grid_step"] = GRID_STEP

    # -- Predictions scored, Sec.5 -----------------------------------------------
    log("\n" + "=" * 90)
    log("Sec.5 predictions, scored against this run")
    log("=" * 90)
    predictions = {
        "row": {"call": "1 (P~=0.80)", "hit": final_row == "1"},
        "k_ref_in_0.60_0.70": {"call": "[+0.60,+0.70]s",
                                "hit": (K_ref is not None and 0.60 <= K_ref <= 0.70)},
        "abs_diff_0.00": {"call": "0.00s (bit-identical argmin)",
                           "hit": (K_ref is not None and steps(abs(K_ref - K_ours)) == 0)},
    }
    for name, p in predictions.items():
        log("  %s: predicted %s -> %s" % (name, p["call"], "HIT" if p["hit"] else "MISS"))
    bundle["predictions_scored"] = predictions

    log("\n" + "=" * 90)
    log("FINAL ROW: %s" % final_row)
    log("=" * 90)

    _write(bundle, log_lines)
    log("\nWrote results/d1_report.json, results/d1_run.log")
    return 0


def _write(bundle: dict, log_lines: list[str]) -> None:
    out_dir = os.path.join(HERE, "results")
    P.write_json(os.path.join(out_dir, "d1_report.json"), bundle)
    with open(os.path.join(out_dir, "d1_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
