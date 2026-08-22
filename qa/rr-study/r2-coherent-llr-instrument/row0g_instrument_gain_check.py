#!/usr/bin/env python3
"""B2 Phase 1 -- ROW 0g, the instrument-gain check (mandatory precondition on task 4.3).

Spec: qa/rr-study/2026-08-21-1038-architect-to-qa-spec-b2-phase1-row0g-instrument-gain-
check.md. Runs BEFORE any evaluation of f_net/C_ber (tasks.md Sec.4.3 is pre-registered
BLOCKED on this task). Both limbs run against the CURRENT MERGED binary (shim 20260043,
PR #128, a420016) -- no native change, no Developer session, HK-011 not engaged.

Two limbs, both must PASS (plus the stub-degeneracy guard) for ROW 0g to clear:
  0g-1  clean-signal ceiling: M=20 noise-free synthetic signals, time_offset_s swept
        over m3_common.TIME_ANCHOR_OFFSETS_S (49 points), each path (grid, coherent)
        minimised independently over the sweep. Bars:
          0g-1a: median(n_err_coh_min) <= 5
          0g-1b: d_clean = median(n_err_grid_min - n_err_coh_min) >= 0 (signed, HK-021(l))
        Plus two-sided degenerate-limit guards (HK-021(n)): floor degeneracy (both paths
        read exactly 0 on every trial -- re-run with added noise) and stub degeneracy
        (coherent output bit-identical to grid output on >=95% of trials -- FIRES).
  0g-2  paired on 200 real P-HIT rows at the +0.65s anchor, d_real cluster-bootstrapped
        by ts (HK-021(i)). Fires if CI_hi(d_real) < 0.

Consequence (HK-021, stated as an assertion, per the spec Sec.2.4):
  PASSES -> the Phase 1 gate (task 4.3) may be evaluated exactly as pre-registered.
  FIRES  -> the Phase 1 gate is VOID. No ROW 1/2/3/4 may be read. ROW 3 MUST NOT be
            declared and Route B2 MUST NOT be called dead. STOP, report which limb
            fired, escalate for a native fix under HK-011.

NFR-021: message text touches this module only in-process (ex.true_codeword calls) and
is never written to any row dict, JSON field, or log line emitted here.
"""
from __future__ import annotations

import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
_SYNTH_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, _SYNTH_ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import FTX_LDPC_N, hard_decision_ber  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH  # noqa: E402 -- path only; SHA/version pin is this module's own
from plive_population import PRIMARY_CORPUS, build_p_hit_population, corpus_paths  # noqa: E402
from run_stage1 import WavCache  # noqa: E402
from run_stage1r import deterministic_sample  # noqa: E402 -- seeded, sort-stabilised (HK-018)
from n1_stats import cluster_bootstrap_median_diff  # noqa: E402 -- reused verbatim (HK-018)
from m3_common import TIME_ANCHOR_OFFSETS_S  # noqa: E402 -- reused verbatim (HK-018)
from results_guard import guard_paths  # noqa: E402 -- N14

import r2_population as R2POP  # noqa: E402
from r2_sign_test import _message_for_trial  # noqa: E402 -- reused verbatim (HK-018)
from coherent_llr_ctypes import CoherentExtractLLRs, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

SEED = 20260821  # this session's date (HK-017-style provenance), fixed before running

# -- 0g-1 clean-signal ceiling -------------------------------------------------------
M_CLEAN_TRIALS = 20
BASE_FREQ_HZ = 1500.0  # nominal grid frequency; lattice-snap is byte-identical between
                        # the two exports (QA verified at merge) -- frequency convention
                        # is not swept, per the spec's own scoping.
SAMPLE_RATE_HZ = 12000

BAR_0G1A_MAX = 5        # median(n_err_coh_min) <= 5
BAR_0G1B_MIN = 0.0      # d_clean >= 0 (signed)
STUB_DEGENERACY_FRAC = 0.95

# -- 0g-2 paired on real data ---------------------------------------------------------
N_REAL_SAMPLE = 200
FLOOR_MIN_ROWS = 100
FLOOR_MIN_CLUSTERS = 60


def _n_err(llr, true_bits) -> int:
    """Same convention as r2_ber_grid.py: ber is an exact k/174 by construction."""
    return int(round(hard_decision_ber(llr, true_bits) * FTX_LDPC_N))


# =====================================================================================
# 0g-1 -- clean-signal ceiling
# =====================================================================================

def _run_clean_trials(ex: CoherentExtractLLRs, snr_db, seed_base: int, log,
                       label: str) -> dict:
    """Runs M_CLEAN_TRIALS clean(-or-noisy) synthetic signals through both paths,
    sweeping TIME_ANCHOR_OFFSETS_S and minimising each path independently. Returns
    per-trial mins plus the stub-degeneracy comparison at coherent's own best offset."""
    from synth import encoder  # noqa: PLC0415 -- lazy, matches this thread's own convention

    trials = []
    stub_identical = 0
    stub_comparable = 0

    for i in range(M_CLEAN_TRIALS):
        msg = _message_for_trial(i)
        true_bits = ex.true_codeword(msg)
        assert true_bits is not None, "encode/true_codeword mismatch on trial %d" % i

        pcm = encoder.encode_message(msg, base_freq_hz=BASE_FREQ_HZ, dt_s=0.0,
                                      snr_db=snr_db, seed=seed_base + i,
                                      sample_rate_hz=SAMPLE_RATE_HZ)
        pcm = np.ascontiguousarray(pcm, dtype=np.float32)
        assert pcm.shape == (180_000,), pcm.shape

        best_grid = None   # (n_err, offset)
        best_coh = None
        coh_at_offset: dict[float, list] = {}
        grid_at_offset: dict[float, list] = {}

        for off in TIME_ANCHOR_OFFSETS_S:
            rc_g, llr_g = ex.extract_at(pcm, BASE_FREQ_HZ, off)
            if rc_g == 0 and llr_g is not None:
                ne_g = _n_err(llr_g, true_bits)
                grid_at_offset[off] = llr_g
                if best_grid is None or ne_g < best_grid[0]:
                    best_grid = (ne_g, off)

            rc_c, llr_c = ex.coherent_extract_at(pcm, BASE_FREQ_HZ, off)
            if rc_c == 0 and llr_c is not None:
                ne_c = _n_err(llr_c, true_bits)
                coh_at_offset[off] = llr_c
                if best_coh is None or ne_c < best_coh[0]:
                    best_coh = (ne_c, off)

        assert best_grid is not None, "grid path never succeeded on trial %d (%s)" % (i, label)
        assert best_coh is not None, "coherent path never succeeded on trial %d (%s)" % (i, label)

        # Stub-degeneracy comparison: at coherent's own best offset, is its output
        # bit-identical to the grid path's output at the SAME offset?
        best_coh_off = best_coh[1]
        if best_coh_off in grid_at_offset:
            stub_comparable += 1
            if grid_at_offset[best_coh_off] == coh_at_offset[best_coh_off]:
                stub_identical += 1

        trials.append({"n_err_grid_min": best_grid[0], "grid_off": best_grid[1],
                        "n_err_coh_min": best_coh[0], "coh_off": best_coh[1]})

    n_err_grid_mins = [t["n_err_grid_min"] for t in trials]
    n_err_coh_mins = [t["n_err_coh_min"] for t in trials]
    d_clean_per_trial = [g - c for g, c in zip(n_err_grid_mins, n_err_coh_mins)]

    median_coh_min = float(st.median(n_err_coh_mins))
    median_grid_min = float(st.median(n_err_grid_mins))
    d_clean = float(st.median(d_clean_per_trial))
    stub_frac = (stub_identical / stub_comparable) if stub_comparable else 0.0
    floor_degenerate = all(g == 0 and c == 0 for g, c in zip(n_err_grid_mins, n_err_coh_mins))

    log("  [%s] median(n_err_coh_min)=%.2f median(n_err_grid_min)=%.2f d_clean=%.2f "
        "stub_identical=%d/%d (%.1f%%) floor_degenerate=%s"
        % (label, median_coh_min, median_grid_min, d_clean, stub_identical, stub_comparable,
           stub_frac * 100, floor_degenerate))
    log("    per-trial n_err_coh_min: %s" % n_err_coh_mins)
    log("    per-trial n_err_grid_min: %s" % n_err_grid_mins)

    return {
        "label": label, "snr_db": snr_db,
        "median_n_err_coh_min": median_coh_min, "median_n_err_grid_min": median_grid_min,
        "d_clean": d_clean, "n_err_coh_mins": n_err_coh_mins, "n_err_grid_mins": n_err_grid_mins,
        "stub_identical": stub_identical, "stub_comparable": stub_comparable,
        "stub_frac": stub_frac, "floor_degenerate": floor_degenerate,
    }


def run_0g1(ex: CoherentExtractLLRs, log) -> dict:
    log("\n" + "=" * 90)
    log("ROW 0g-1 -- clean-signal ceiling (%d noise-free synthetic signals, %d-point sweep)"
        % (M_CLEAN_TRIALS, len(TIME_ANCHOR_OFFSETS_S)))
    log("=" * 90)

    primary = _run_clean_trials(ex, snr_db=None, seed_base=SEED, log=log, label="noiseless")

    bar_1a_pass = primary["median_n_err_coh_min"] <= BAR_0G1A_MAX
    bar_1b_pass = primary["d_clean"] >= BAR_0G1B_MIN
    stub_fires = (primary["stub_comparable"] > 0
                  and primary["stub_frac"] >= STUB_DEGENERACY_FRAC)

    log("  0g-1a: median(n_err_coh_min)=%.2f <= %d -> %s"
        % (primary["median_n_err_coh_min"], BAR_0G1A_MAX, "PASS" if bar_1a_pass else "FAIL"))
    log("  0g-1b: d_clean=%.2f >= %.1f (signed) -> %s"
        % (primary["d_clean"], BAR_0G1B_MIN, "PASS" if bar_1b_pass else "FAIL"))
    log("  stub degeneracy: %.1f%% identical (fires at >= %.0f%%) -> %s"
        % (primary["stub_frac"] * 100, STUB_DEGENERACY_FRAC * 100,
           "FIRES" if stub_fires else "clear"))

    result = {
        "primary": primary,
        "bar_1a_pass": bar_1a_pass, "bar_1b_pass": bar_1b_pass,
        "stub_fires": stub_fires,
        "floor_degeneracy_rerun": None,
    }

    if primary["floor_degenerate"]:
        log("\n  FLOOR DEGENERACY: both paths read exactly 0 on every trial -- sub-bar "
            "(b) cannot discriminate. Re-running limb (b) only, adding seeded noise "
            "until median(n_err_grid_min) lands in [5, 25].")
        rerun = None
        for snr_db in (-4.0, -8.0, -12.0, -16.0, -18.0, -19.0, -20.0, -21.0, -22.0, -24.0, -28.0):
            # Empirically probed before wiring this ladder in (2026-08-21): symbol-level
            # coherent/incoherent integration over each ~0.16s FT8 symbol gives roughly
            # 20-25dB of processing gain relative to the 2500Hz reference bandwidth
            # noise_sigma_for_snr's snr_db is defined against, so snr_db in the ordinary
            # 0-30dB range (ROW 0c's own NOISE sub-check convention) reads essentially
            # noiseless here; median(n_err_grid_min) only enters [5,25] around -20dB.
            # Recorded honestly per HK-018/HK-022, not silently discovered a second time.
            trial = _run_clean_trials(ex, snr_db=snr_db, seed_base=SEED + 500_000, log=log,
                                       label="noisy snr=%.0fdB" % snr_db)
            if 5.0 <= trial["median_n_err_grid_min"] <= 25.0:
                rerun = trial
                break
        if rerun is None:
            log("  Could not land median(n_err_grid_min) in [5,25] across the tried SNR "
                "sweep -- ESCALATE, do not silently accept the noiseless floor reading.")
            result["floor_degeneracy_rerun"] = {"landed": False}
            bar_1b_pass = False
        else:
            rerun_1b_pass = rerun["d_clean"] >= BAR_0G1B_MIN
            log("  Floor-degeneracy re-run landed at snr_db=%.0f: median(n_err_grid_min)=%.2f "
                "d_clean=%.2f -> 0g-1b %s"
                % (rerun["snr_db"], rerun["median_n_err_grid_min"], rerun["d_clean"],
                   "PASS" if rerun_1b_pass else "FAIL"))
            result["floor_degeneracy_rerun"] = rerun
            bar_1b_pass = rerun_1b_pass
        result["bar_1b_pass"] = bar_1b_pass

    result["passed"] = bar_1a_pass and result["bar_1b_pass"] and not stub_fires
    log("\nROW 0g-1 RESULT: %s" % ("PASS" if result["passed"] else "FAIL"))
    return result


# =====================================================================================
# 0g-2 -- paired on real data
# =====================================================================================

def run_0g2(ex: CoherentExtractLLRs, log) -> dict:
    log("\n" + "=" * 90)
    log("ROW 0g-2 -- paired on %d real P-HIT rows at the +%.2fs anchor"
        % (N_REAL_SAMPLE, R2POP.STAGE2_ANCHOR_OFFSET_S))
    log("=" * 90)

    full_p_hit = build_p_hit_population(PRIMARY_CORPUS)
    sample = deterministic_sample(full_p_hit, N_REAL_SAMPLE, SEED)
    wav_cache = WavCache(corpus_paths(PRIMARY_CORPUS)["wsjtx_wav_dir"])
    log("  sampled %d rows (seed=%d) from a %d-row/%d-cluster population"
        % (len(sample), SEED, len(full_p_hit), len({r["ts"] for r in full_p_hit})))

    rows_out: list[dict] = []
    drop_reasons: dict[str, int] = {}

    def _drop(reason: str) -> None:
        drop_reasons[reason] = drop_reasons.get(reason, 0) + 1

    t0 = time.time()
    for row in sample:
        true_bits = ex.true_codeword(row["message"])
        if true_bits is None:
            _drop("no_true_codeword")
            continue
        try:
            pcm = wav_cache.get(row["ts"])
        except FileNotFoundError:
            _drop("no_wav")
            continue

        freq_int = round(row["anchor_freq_hz"])
        corrected_dt = float(row["anchor_dt"]) + R2POP.STAGE2_ANCHOR_OFFSET_S

        rc_g, llr_g = ex.extract_at(pcm, float(freq_int), corrected_dt)
        if rc_g != 0 or llr_g is None:
            _drop("grid_extract_rc_%d" % rc_g)
            continue
        rc_c, llr_c = ex.coherent_extract_at(pcm, float(freq_int), corrected_dt)
        if rc_c != 0 or llr_c is None:
            _drop("coh_extract_rc_%d" % rc_c)
            continue

        n_err_g = _n_err(llr_g, true_bits)
        n_err_c = _n_err(llr_c, true_bits)
        rows_out.append({"ts": row["ts"], "d_ber": float(n_err_g - n_err_c),
                          "n_err_grid": n_err_g, "n_err_coh": n_err_c})
    elapsed = time.time() - t0

    n_delivered = len(rows_out)
    n_clusters_delivered = len({r["ts"] for r in rows_out})
    log("  measured %d/%d rows (%.1fs), n_clusters_delivered=%d, drop_reasons=%s"
        % (n_delivered, len(sample), elapsed, n_clusters_delivered, drop_reasons))

    if n_delivered < FLOOR_MIN_ROWS or n_clusters_delivered < FLOOR_MIN_CLUSTERS:
        log("\n  FLOOR BREACH: delivered %d rows / %d clusters, below the [%d rows, %d "
            "clusters] floor -- STOP AND ESCALATE rather than run (spec Sec.2.3)."
            % (n_delivered, n_clusters_delivered, FLOOR_MIN_ROWS, FLOOR_MIN_CLUSTERS))
        return {"floor_breach": True, "n_delivered": n_delivered,
                "n_clusters_delivered": n_clusters_delivered, "drop_reasons": drop_reasons,
                "passed": False, "fires": None}

    boot = cluster_bootstrap_median_diff(rows_out)
    d_real = boot["point_estimate"]
    ci_hi = boot["ci95"][1]
    fires = ci_hi < 0.0
    log("  d_real (median n_err_grid - n_err_coh) = %.3f, cluster-bootstrap CI95=[%.3f, %.3f] "
        "(n_draws=%d, n_clusters=%d) -> %s"
        % (d_real, boot["ci95"][0], ci_hi, boot["n_draws"], boot["n_clusters"],
           "FIRES (CI_hi < 0)" if fires else "clear"))

    return {
        "floor_breach": False, "n_delivered": n_delivered,
        "n_clusters_delivered": n_clusters_delivered, "drop_reasons": drop_reasons,
        "bootstrap": boot, "d_real": d_real, "ci_hi": ci_hi,
        "fires": fires, "passed": not fires,
    }


# =====================================================================================
# main
# =====================================================================================

def hk025_check() -> dict:
    """Concurs with the spec's own Sec.2.1 classification: VALIDITY, not diagnostic --
    PASS and FIRE branches yield categorically different consequences (gate proceeds vs.
    gate is VOID), so this survives HK-021(k)/HK-025. No refusal."""
    return {
        "classification": {
            "row_0g": {
                "class": "VALIDITY",
                "reason": "a defective correlator produces a low f_net indistinguishable "
                          "from a true null, and the gate's ROW 3 consequence is to "
                          "declare D-001 routeless",
                "branch_pass": "gate proceeds; ROW 1/2/3/4 evaluated as pre-registered",
                "branch_fire": "gate is VOID; no ROW 1/2/3/4 may be read",
            }
        },
        "refusal": False, "concurs_with_spec": True,
    }


def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("B2 PHASE 1 -- ROW 0g, the instrument-gain check (task 4.4, precondition on 4.3)")
    log("=" * 90)

    hk025 = hk025_check()
    log("\nHK-025 independent re-classification: concurs_with_spec=%s refusal=%s"
        % (hk025["concurs_with_spec"], hk025["refusal"]))
    bundle: dict = {"hk025": hk025}
    if hk025["refusal"]:
        log("REFUSING TO ARM PER HK-025.")
        _write(out_dir, {"hk025": hk025, "final": "REFUSED"}, log_lines)
        return 1

    log("\nLoading DLL: %s (pinned to the CURRENT MERGED binary, shim %d)"
        % (DEFAULT_DLL_PATH, CURRENT_SHIM_VERSION))
    try:
        ex = CoherentExtractLLRs(DEFAULT_DLL_PATH, verify=True,
                                  expected_sha256=CURRENT_DLL_SHA256,
                                  expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("\nROW 0a-equivalent FIRES: %s" % e)
        log("VALIDITY, STOP. NO VERDICT.")
        bundle["final"] = "dll_pin_fail"
        bundle["error"] = str(e)
        _write(out_dir, bundle, log_lines)
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], ex.version))
    bundle["dll_pin"] = {"sha256_prefix": CURRENT_DLL_SHA256[:16], "shim_version": ex.version}

    row0g1 = run_0g1(ex, log)
    bundle["row_0g1"] = row0g1

    row0g2 = run_0g2(ex, log)
    bundle["row_0g2"] = row0g2

    if row0g2.get("floor_breach"):
        log("\nROW 0g-2 FLOOR BREACH -- cannot evaluate. STOP AND ESCALATE (do not run "
            "the bar on an underpowered sample).")
        bundle["final"] = "row_0g2_floor_breach"
        _write(out_dir, bundle, log_lines)
        return 3

    row0g_passed = row0g1["passed"] and row0g2["passed"]

    log("\n" + "=" * 90)
    if row0g_passed:
        log("ROW 0g: PASS (0g-1 PASS, 0g-2 PASS, no stub degeneracy). The Phase 1 gate "
            "(task 4.3) may now be evaluated exactly as pre-registered.")
        bundle["final"] = "row_0g_pass"
    else:
        which = []
        if not row0g1["bar_1a_pass"]:
            which.append("0g-1a (median n_err_coh_min > bar)")
        if not row0g1["bar_1b_pass"]:
            which.append("0g-1b (d_clean < 0)")
        if row0g1["stub_fires"]:
            which.append("stub degeneracy (coherent output bit-identical to grid)")
        if not row0g2["passed"]:
            which.append("0g-2 (CI_hi(d_real) < 0)")
        log("ROW 0g: FIRES -- %s." % "; ".join(which))
        log("CONSEQUENCE (per spec Sec.2.4): the Phase 1 gate is VOID. No ROW 1/2/3/4 "
            "may be read. ROW 3 MUST NOT be declared and Route B2 MUST NOT be called "
            "dead. Remedy is a native fix under HK-011, then a re-run -- not a re-read "
            "of this output with a different metric.")
        bundle["final"] = "row_0g_fires"
        bundle["fired_limbs"] = which
    log("=" * 90)

    bundle["row_0g_passed"] = row0g_passed
    _write(out_dir, bundle, log_lines)
    return 0 if row0g_passed else 4


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    report_path = os.path.join(out_dir, "row0g_report.json")
    log_path = os.path.join(out_dir, "row0g_run.log")
    guard_paths([report_path, log_path], REPO_ROOT)  # N14
    P.write_json(report_path, bundle)
    with open(log_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
