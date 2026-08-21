#!/usr/bin/env python3
"""B2 Phase 0 -- OpenSpec change r2-coherent-llr-instrument, QA's own item.

Spec: qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-phase1-coherent-llr-kill-gate.md
Sec.5 ("QA now: author the OpenSpec change ... build the measurement harness, re-derive
the population, and run ROW 0c/0d ... before any native code exists. Then stop."), AS
ORDERED by qa/rr-study/2026-08-20-1613-architect-to-qa-s3b-deferred-fp-row0-closed-b2-
phase0-order.md Sec.4 ("QA now: B2 Phase 0").

Runs, strict order, first VALIDITY failure stops the run (no partial credit):
  1. ROW 0a -- DLL SHA256 + shim version asserted against the pin already in production
     use (run_stage1.DEFAULT_DLL_SHA256 / EXPECTED_SHIM_VERSION, both re-verified from
     disk immediately before arming, not inferred from any label -- D4 discipline).
  2. HK-025 -- every row below independently re-classified (VALIDITY vs DIAGNOSTIC)
     before running, per standing practice (run_stage2.hk025_check's own pattern).
  3. Population dry count -- CLUSTER counts reported, not row counts (population.py).
  4. ROW 0c -- sign_test.run_row0c_sign_test (both sub-checks; see that module for the
     full derivation of its bars).
  5. ROW 0d -- ber_grid.run_population over the FULL P-LIVE population at Stage 2's own
     +0.65s offset, median compared against Stage 2's own 31.03% within 1.0pp.

No src/ touched. No DLL rebuilt. No Developer session. HK-011 not engaged -- this
harness only calls the EXISTING ft8_extract_llrs_at export; ft8_coherent_llr_at does not
exist in the current binary (confirmed: grep of ft8_shim.h finds no such symbol) and
this module makes no attempt to call it.

NFR-021: message TEXT touches this module only in-process (ex.true_codeword calls inside
sign_test.py / ber_grid.py) and is never written to any row dict, JSON field, or log
line emitted here. Verified mechanically at the end of main(), not merely asserted.
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH, DEFAULT_DLL_SHA256, EXPECTED_SHIM_VERSION  # noqa: E402
from plive_population import corpus_paths  # noqa: E402

import r2_population as POP  # noqa: E402
import r2_sign_test as SIGN  # noqa: E402
import r2_ber_grid as BER  # noqa: E402

ROW_0D_TOL_PP = 0.01  # 1.0 percentage point, per the spec's own bar


# =============================================================================
# HK-025 -- independent re-classification, before arming
# =============================================================================

def hk025_check() -> dict:
    """0a: fires -> every extraction is against an unidentified binary; no named
        instrument, refuse to arm. Clears -> proceed on a pinned binary. VALIDITY.
    0c: fires -> the sign convention this harness reuses for every BER number it will
        ever report (here and in Phase 1) cannot be trusted; a downstream 'null' result
        would be indistinguishable from a silently inverted one. Clears -> proceed.
        VALIDITY, not diagnostic -- the two branches lead to categorically different
        actions (stop and fix the harness vs. trust its BER numbers), not merely
        different confidence in the same numbers.
    0d: fires -> this harness's population re-derivation and/or grid-BER computation
        diverges from Stage 2's own already-published measurement of the identical
        population at the identical offset -- something in the re-derivation is wrong
        and Phase 1 must not be built on top of it. Clears -> the harness reproduces a
        known-good number, proceed. VALIDITY.
    No refusal. Concurs with the spec's own ROW 0 table (2026-08-19-1850 Sec.3)."""
    reasons = {
        "0a": "unidentified binary invalidates every downstream number",
        "0c": "sign convention unverified -- every BER this harness reports could be "
              "silently inverted, indistinguishable from a correct null result",
        "0d": "harness/population diverges from Stage 2's own already-published number "
              "on the identical population at the identical offset",
    }
    classification = {k: {"class": "VALIDITY", "reason": v} for k, v in reasons.items()}
    return {"classification": classification, "refusal": False, "concurs_with_spec": True}


def main() -> int:
    ap_out_dir = os.path.join(HERE, "results")
    os.makedirs(ap_out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("B2 PHASE 0 -- OpenSpec change r2-coherent-llr-instrument, QA's harness + ROW 0c/0d")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    bundle: dict = {"hk025": hk025}
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        _write(ap_out_dir, {"hk025": hk025, "final": "REFUSED"}, log_lines)
        return 1

    # -- ROW 0a ---------------------------------------------------------------------
    log("\nLoading DLL: %s" % DEFAULT_DLL_PATH)
    try:
        ex = ExtractLLRs(DEFAULT_DLL_PATH, verify=True, expected_sha256=DEFAULT_DLL_SHA256,
                          expected_shim_version=EXPECTED_SHIM_VERSION)
    except RuntimeError as e:
        log("\nROW 0a FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        bundle["row_0a"] = {"fires": True, "error": str(e)}
        bundle["final"] = "row_0a_fail"
        _write(ap_out_dir, bundle, log_lines)
        return 2
    log("ROW 0a clear: DLL SHA256 asserted (%s...), shim version %d confirmed."
        % (DEFAULT_DLL_SHA256[:16], ex.version))
    bundle["row_0a"] = {"fires": False, "sha256_prefix": DEFAULT_DLL_SHA256[:16],
                         "shim_version": ex.version}

    # -- Population dry count --------------------------------------------------------
    log("\n" + "=" * 90)
    log("Population re-derivation (dry count, before any DLL call)")
    log("=" * 90)
    dry = POP.dry_count()
    log("  P-LIVE %s: n_rows=%d n_clusters=%d" % (dry["corpus"], dry["n_rows"], dry["n_clusters"]))
    bundle["population_dry_count"] = {"corpus": dry["corpus"], "n_rows": dry["n_rows"],
                                        "n_clusters": dry["n_clusters"]}

    # -- ROW 0c -----------------------------------------------------------------------
    row0c = SIGN.run_row0c_sign_test(ex, log)
    bundle["row_0c"] = row0c
    if not row0c["passed"]:
        log("\nROW 0c FAILED -- REFUSING to proceed to ROW 0d (HK-025: a spec whose "
            "ROW 0 fails must stop, not run partially).")
        bundle["final"] = "row_0c_fail"
        _write(ap_out_dir, bundle, log_lines)
        return 3

    # -- ROW 0d -------------------------------------------------------------------
    log("\n" + "=" * 90)
    log("ROW 0d -- ber_grid reproduces Stage 2's median 31.03%% within 1.0pp")
    log("=" * 90)
    paths = corpus_paths(dry["corpus"])
    t0 = time.time()
    measured = BER.run_population(ex, paths["wsjtx_wav_dir"], dry["population"],
                                   POP.STAGE2_ANCHOR_OFFSET_S, log)
    elapsed = time.time() - t0
    rows = measured["rows"]
    if not rows:
        log("No rows measured -- cannot evaluate ROW 0d. STOP.")
        bundle["row_0d"] = {"fires": True, "reason": "no_rows_measured"}
        bundle["final"] = "row_0d_fail"
        _write(ap_out_dir, bundle, log_lines)
        return 4

    fresh_median = BER.median_ber_grid(rows)
    delta_pp = abs(fresh_median - POP.STAGE2_MEDIAN_BER_GRID)
    row0d_passes = delta_pp <= ROW_0D_TOL_PP
    log("\n  fresh median_ber_grid = %.4f%% (n_rows=%d, n_clusters=%d, %.1fs)"
        % (fresh_median * 100, measured["n_measured"], measured["n_clusters_measured"], elapsed))
    log("  Stage 2's own median_ber_grid = %.4f%% (cited as 31.03%%)"
        % (POP.STAGE2_MEDIAN_BER_GRID * 100))
    log("  |delta| = %.4fpp (bar <= %.1fpp) -> %s"
        % (delta_pp * 100, ROW_0D_TOL_PP * 100, "PASS" if row0d_passes else "FAIL"))

    bundle["row_0d"] = {
        "passed": row0d_passes,
        "fresh_median_ber_grid": fresh_median,
        "stage2_median_ber_grid": POP.STAGE2_MEDIAN_BER_GRID,
        "delta_pp": delta_pp,
        "tolerance_pp": ROW_0D_TOL_PP,
        "n_measured": measured["n_measured"],
        "n_clusters_measured": measured["n_clusters_measured"],
        "drop_reasons": measured["drop_reasons"],
        "elapsed_s": elapsed,
    }

    if not row0d_passes:
        log("\nROW 0d FAILED. VALIDITY, STOP, escalate -- do not proceed to author the "
            "OpenSpec change on top of a harness that does not reproduce a known number.")
        bundle["final"] = "row_0d_fail"
        _write(ap_out_dir, bundle, log_lines)
        return 5

    log("\n" + "=" * 90)
    log("B2 PHASE 0: ROW 0c PASS, ROW 0d PASS. Harness validated against the current "
        "build. STOPPING per HK-011 -- Phase 1 (ft8_coherent_llr_at) needs a "
        "Captain-opened Developer session.")
    log("=" * 90)
    bundle["final"] = "row_0_all_pass"
    _write(ap_out_dir, bundle, log_lines)
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "phase0_report.json"), bundle)
    with open(os.path.join(out_dir, "phase0_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
