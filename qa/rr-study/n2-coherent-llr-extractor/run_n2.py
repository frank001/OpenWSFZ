#!/usr/bin/env python3
"""N2 -- does a COHERENT MULTI-SYMBOL LLR extractor fix the reading? BER against the
same measured bar, mirroring N1's exact design (hold position constant, vary the metric).

Spec: qa/rr-study/2026-08-16-1408-architect-to-qa-N2-coherent-llr-extractor-spec.md

For each candidate-present-and-failed row (population.py, reused unchanged from N1),
extracts hard-decision LLRs at the SAME GRID anchor (N1's own _anchor(), reused, not
re-derived) via TWO independent front ends on the identical audio buffer:
  V0 -- ft8_extract_llrs_at (n1-extract-llrs-at-position, shim 20260042), the exact
        extraction code production uses, unmodified. Control/baseline.
  V1/V2/V3 -- coherent_extract.py's Python front end (Sec.4.1), computed together (they
        share one downconvert + per-symbol-correlation pass per row).

Runs the mandatory sign unit test FIRST and refuses to proceed if it fails (spec Sec.5).
Then ROW 0a (synthetic noiseless self-consistency, Python-only, no DLL), ROW 0b (control
population wiring check, both V0 and V1), ROW 0c (n>=200), ROW 0d (V0-vs-V3 hard-decision
disagreement floor), then the ROW 1/2/3/4 gate in strict pre-registered order (Sec.6.1),
then the pre-registered secondaries (Sec.7: V1/V2 attribution, frequency sweep, tight/
loose stratification).

NFR-021: message TEXT is used in-process only (recovering true bits either via the native
ft8_encode_message, for real rows, or directly from the Python synth's own tones, for
ROW 0a) and is NEVER written to a result file or printed. Per-row output carries ts +
numeric fields only.
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
N1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position")
# N1_DIR carries its OWN sign_unit_test.py (a same-named sibling to this dir's file) --
# insert HERE *last* so it sits at sys.path[0] and this module's own `import
# sign_unit_test` / `coherent_extract` / `n2_stats` resolve to N2's own files, not N1's.
# (`from run_n1 import ...` below still finds N1_DIR fine, several entries down; and
# run_n1.py's OWN internal `import sign_unit_test` is unaffected -- executing that
# module re-inserts N1_DIR at position 0 itself, ahead of anything set up here.)
sys.path.insert(0, N1_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r1-sync-refiner"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402
import sign_unit_test  # noqa: E402
import coherent_extract as CE  # noqa: E402
from extract_llrs_ctypes import ExtractLLRs, hard_decision_ber  # noqa: E402
from n2_stats import B50_THRESHOLD, cluster_bootstrap_median_diff, d_ber_row, f_cross_row  # noqa: E402
from population import build_matched_hit_control, build_paired_population  # noqa: E402
from run_n1 import WavCache, _anchor  # noqa: E402 -- reuse N1's loader/anchor verbatim

DEFAULT_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
DEFAULT_DLL_SHA256 = "6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672"
EXPECTED_SHIM_VERSION = 20260042

ROW_0B_V1_MEDIAN_MAX = 0.05           # 5% -- ROW 0b
ROW_0B_V0_MEDIAN_TARGET = 0.0287      # N1 Sec.3.1's independent reproduction
ROW_0B_V0_MEDIAN_TOL = 0.01           # +/-1pp
ROW_0C_MIN_PAIRED_ROWS = 200          # ROW 0c
ROW_0D_MIN_DISAGREE_BITS = 5          # ROW 0d, out of 174

ROW_1_CI_LO_MIN = 0.05                # 5pp -- ROW 1/2
ROW_1_F_CROSS_MIN = 0.20              # ROW 1
ROW_2_F_CROSS_MAX = 0.20              # ROW 2 (exclusive upper via "not ROW 1")
ROW_3_D_BER_ABS_MAX = 0.05            # 5pp -- ROW 3
ROW_3_CI_HI_MAX = 0.15                # 15pp -- ROW 3
ROW_3_F_CROSS_MAX = 0.02              # ROW 3

DF_SWEEP_HZ = (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0)   # Sec.7.2
TIGHT_MATCH_HZ = 2.0                                      # Sec.7.3

# ROW 0a synthetic parameters: dt is an exact multiple of 0.08s (the native lattice
# step) so the sample-alignment arithmetic (dt_s * 2000 Hz) lands on an exact integer,
# with no rounding residue that could itself cause a spurious ROW 0a failure.
SYNTH_MESSAGE = "CQ Q1AW JO22"   # NFR-021: synthetic Q-prefix callsign
SYNTH_FREQ_HZ = 1000.0
SYNTH_DT_S = 0.48


def hd_disagreement(llr_a, llr_b) -> int:
    hd_a = [1 if x > 0.0 else 0 for x in llr_a]
    hd_b = [1 if x > 0.0 else 0 for x in llr_b]
    return sum(1 for x, y in zip(hd_a, hd_b) if x != y)


def measure_row(ex: ExtractLLRs, wav_cache: WavCache, row: dict) -> dict | None:
    """Returns a result dict (message text NEVER included) or None if unmeasurable."""
    pcm = wav_cache.get(row["ts"])
    anchor_freq, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc0, llr_v0 = ex.extract_at(pcm, float(anchor_freq), anchor_dt)
    if rc0 != 0 or llr_v0 is None:
        return {"reason": "v0_extract_rc_%d" % rc0}

    variants = CE.extract_variants(np.asarray(pcm, dtype=np.float64), float(anchor_freq), anchor_dt)

    ber_v0 = hard_decision_ber(llr_v0, true_bits)
    ber_v1 = hard_decision_ber(list(variants["V1"]), true_bits)
    ber_v2 = hard_decision_ber(list(variants["V2"]), true_bits)
    ber_v3 = hard_decision_ber(list(variants["V3"]), true_bits)

    return {
        "ts": row["ts"],
        "population": row["population"],
        "ber_v0": ber_v0,
        "ber_v1": ber_v1,
        "ber_v2": ber_v2,
        "ber_v3": ber_v3,
        "d_ber": d_ber_row(ber_v0, ber_v3),
        "crosses": f_cross_row(ber_v0, ber_v3),
        "d_ber_v1": d_ber_row(ber_v0, ber_v1),
        "d_ber_v2": d_ber_row(ber_v0, ber_v2),
        "hd_disagree_v0_v3": hd_disagreement(llr_v0, list(variants["V3"])),
        "anchor_freq_hz": anchor_freq,
        "anchor_dt": anchor_dt,
        "wsjtx_freq_hz": row.get("wsjtx_freq_hz"),
        "true_bits": true_bits,  # stripped before write, kept only for the df sweep pass
        "pcm_key": row["ts"],
    }


def run_row_0a() -> dict:
    """Synthetic noiseless round-trip (spec Sec.6.0 ROW 0a). Python-only: renders a
    known message at a known (freq, dt) with the clean-room synth modulator (no DLL, no
    WAV corpus), extracts with V3, and checks hard-decision BER against the EXACT tones
    that PCM was rendered from (coherent_extract.true_bits_from_tones) -- not against the
    native encoder's own tones, so this check never depends on the native and Python
    encoders agreeing bit-for-bit (a separate, unrelated, already-flagged concern)."""
    from synth import encoder as synth_encoder  # noqa: PLC0415

    tones = synth_encoder.message_to_tones(SYNTH_MESSAGE)
    clean = synth_encoder.render_tones(tones, base_freq_hz=SYNTH_FREQ_HZ, dt_s=SYNTH_DT_S,
                                        snr_db=None, sample_rate_hz=int(CE.SAMPLE_RATE_HZ))
    pcm = np.asarray(clean, dtype=np.float32)
    assert pcm.shape == (CE.BUFFER_SAMPLES,), pcm.shape
    pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)

    true_bits = CE.true_bits_from_tones(tones)
    # extract_variants interprets anchor_dt_s in the REAL-CANDIDATE convention
    # (coherent_extract.TIME_ORIGIN_CORRECTION_SAMPLES_2K, an empirical ROW 0b finding:
    # real candidate_diag.csv-derived dt values read symbol 0 one full SYMBOL_PERIOD_S
    # later than modulator.py's own "dt_s*fs=sample index" placement convention). This
    # synthetic PCM was placed via modulator.py directly, so compensate by adding one
    # symbol period here -- after extract_variants' internal correction subtracts it
    # back out, the net position lands exactly on SYNTH_DT_S, where the signal actually
    # is. This keeps ROW 0a a genuine self-consistency check of the CORRECTED pipeline.
    variants = CE.extract_variants(np.asarray(pcm, dtype=np.float64), SYNTH_FREQ_HZ,
                                    SYNTH_DT_S + CE.SYMBOL_PERIOD_S)
    ber_v1 = hard_decision_ber(list(variants["V1"]), true_bits)
    ber_v2 = hard_decision_ber(list(variants["V2"]), true_bits)
    ber_v3 = hard_decision_ber(list(variants["V3"]), true_bits)

    fires = ber_v3 != 0.0
    return {"row": "0a", "fires": fires, "ber_v1": ber_v1, "ber_v2": ber_v2, "ber_v3": ber_v3}


def run_control_check(ex: ExtractLLRs, wav_cache: WavCache, control_rows: list[dict]) -> dict:
    """ROW 0b: on the matched-hit control population, V1 median BER must be <=5% AND V0
    median BER must be 2.87%+/-1pp (N1 Sec.3.1's own independent reproduction bound).
    Both arms exercised at the same GRID anchor, same rows -- this is a wiring check for
    the NEW Python front end against the ALREADY-validated native one, not a test of any
    coherent gain."""
    v0_bers: list[float] = []
    v1_bers: list[float] = []
    n_rc_nonzero = 0
    n_no_true_codeword = 0
    for row in control_rows:
        pcm = wav_cache.get(row["ts"])
        anchor_freq, anchor_dt = _anchor(row["grid_freq_hz"], row["grid_dt"])
        true_bits = ex.true_codeword(row["message"])
        if true_bits is None:
            n_no_true_codeword += 1
            continue
        rc, llr_v0 = ex.extract_at(pcm, float(anchor_freq), anchor_dt)
        if rc != 0 or llr_v0 is None:
            n_rc_nonzero += 1
            continue
        variants = CE.extract_variants(np.asarray(pcm, dtype=np.float64), float(anchor_freq), anchor_dt)
        v0_bers.append(hard_decision_ber(llr_v0, true_bits))
        v1_bers.append(hard_decision_ber(list(variants["V1"]), true_bits))

    med_v0 = float(st.median(v0_bers)) if v0_bers else float("nan")
    med_v1 = float(st.median(v1_bers)) if v1_bers else float("nan")
    v0_ok = (not np.isnan(med_v0)) and abs(med_v0 - ROW_0B_V0_MEDIAN_TARGET) <= ROW_0B_V0_MEDIAN_TOL
    v1_ok = (not np.isnan(med_v1)) and med_v1 <= ROW_0B_V1_MEDIAN_MAX
    fires = (not v0_bers) or (not v1_bers) or (not v0_ok) or (not v1_ok) or n_rc_nonzero > 0
    return {
        "row": "0b", "fires": fires,
        "n_control": len(control_rows), "n_measured": len(v0_bers),
        "n_rc_nonzero": n_rc_nonzero, "n_no_true_codeword": n_no_true_codeword,
        "median_ber_v0": med_v0, "median_ber_v1": med_v1,
        "v0_target": ROW_0B_V0_MEDIAN_TARGET, "v0_tol": ROW_0B_V0_MEDIAN_TOL,
        "v1_max": ROW_0B_V1_MEDIAN_MAX,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-path", default=DEFAULT_DLL_PATH)
    ap.add_argument("--dll-sha256", default=DEFAULT_DLL_SHA256)
    ap.add_argument("--limit", type=int, default=None,
                     help="cap the main population to this many rows (smoke runs only)")
    ap.add_argument("--n-draws", type=int, default=2000)
    ap.add_argument("--skip-freq-sweep", action="store_true",
                     help="smoke-run escape hatch; NOT valid for a real gate evaluation")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "results"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("N2 -- coherent multi-symbol LLR extractor vs. the grid-position baseline")
    log("=" * 90)

    log("\n[MANDATORY] Running the sign unit test first (spec Sec.5)...")
    sign_rc = sign_unit_test.main()
    if sign_rc != 0:
        log("SIGN UNIT TEST FAILED -- refusing to arm the real harness.")
        return 1
    log("Sign unit test PASSED. Arming.\n")

    log("=" * 90)
    log("ROW 0a -- synthetic noiseless round-trip (Python-only, no DLL)")
    log("=" * 90)
    row0a = run_row_0a()
    log("ROW 0a: V1_BER=%.2f%% V2_BER=%.2f%% V3_BER=%.2f%% (V3 must be exactly 0.0%%) -> %s"
        % (row0a["ber_v1"] * 100, row0a["ber_v2"] * 100, row0a["ber_v3"] * 100,
           "FIRES" if row0a["fires"] else "clear"))
    if row0a["fires"]:
        log("\nROW 0a FIRES: the extractor cannot read a signal it was handed perfectly. "
            "Fix the harness, re-run. NOT a result.")
        _write_report(args.out_dir, {"final_row": "0a", "row_0a": row0a}, log_lines)
        return 2
    log("ROW 0a clear.\n")

    log("Loading DLL: %s" % args.dll_path)
    ex = ExtractLLRs(args.dll_path, verify=True, expected_sha256=args.dll_sha256,
                      expected_shim_version=EXPECTED_SHIM_VERSION)
    log("DLL SHA256 asserted (%s...), shim version %d confirmed.\n"
        % (args.dll_sha256[:16], ex.version))

    wav_cache = WavCache()

    log("=" * 90)
    log("ROW 0b -- control-population wiring check (V0 and V1)")
    log("=" * 90)
    control_rows = build_matched_hit_control()
    row0b = run_control_check(ex, wav_cache, control_rows)
    log("ROW 0b: n_control=%d n_measured=%d n_rc_nonzero=%d median_ber_v0=%.2f%% "
        "(target %.2f%%+/-%.0fpp) median_ber_v1=%.2f%% (bound <=%.0f%%) -> %s"
        % (row0b["n_control"], row0b["n_measured"], row0b["n_rc_nonzero"],
           row0b["median_ber_v0"] * 100, row0b["v0_target"] * 100, row0b["v0_tol"] * 100,
           row0b["median_ber_v1"] * 100, row0b["v1_max"] * 100,
           "FIRES" if row0b["fires"] else "clear"))
    if row0b["fires"]:
        log("\nROW 0b FIRES: the Python front end is reading a different position or "
            "scaling than the C baseline. Harness invalid, NO VERDICT. QA fixes and re-runs.")
        _write_report(args.out_dir, {"final_row": "0b", "row_0a": row0a, "row_0b": row0b}, log_lines)
        return 3
    log("ROW 0b clear.\n")

    log("=" * 90)
    log("Building the candidate-present-and-failed population (THE 135 + THE 567)")
    log("=" * 90)
    population = build_paired_population()
    if args.limit is not None:
        population = population[: args.limit]
        log("--limit applied: n=%d (SMOKE RUN, not a valid gate evaluation)" % len(population))

    log("\n" + "=" * 90)
    log("Measuring V0 vs. V1/V2/V3 for each row")
    log("=" * 90)
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        result = measure_row(ex, wav_cache, row)
        if result is None or "reason" in result:
            reason = result["reason"] if result else "none"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        rows.append(result)
        if (i + 1) % 50 == 0:
            log("  ... %d/%d rows processed (%d measured, %.1fs elapsed)"
                % (i + 1, len(population), len(rows), time.time() - t0))
    log("\nMeasured %d/%d rows (%.1fs). Drop reasons: %s"
        % (len(rows), len(population), time.time() - t0, reasons))

    result_bundle: dict = {"n_population": len(population), "n_measured": len(rows),
                            "drop_reasons": reasons, "row_0a": row0a, "row_0b": row0b}

    log("\n" + "=" * 90)
    log("ROW 0c -- underpowered check")
    log("=" * 90)
    row0c_fires = len(rows) < ROW_0C_MIN_PAIRED_ROWS
    log("n_paired=%d (bound >=%d) -> %s" % (len(rows), ROW_0C_MIN_PAIRED_ROWS,
                                             "FIRES" if row0c_fires else "clear"))
    result_bundle["row_0c"] = {"row": "0c", "fires": row0c_fires, "n_paired": len(rows),
                                "min_required": ROW_0C_MIN_PAIRED_ROWS}
    if row0c_fires:
        log("\nROW 0c FIRES: instrument failure, NOT a null.")
        result_bundle["final_row"] = "0c"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 4

    log("\n" + "=" * 90)
    log("ROW 0d -- can the contrast move at all?")
    log("=" * 90)
    median_disagree = float(st.median(r["hd_disagree_v0_v3"] for r in rows))
    row0d_fires = median_disagree < ROW_0D_MIN_DISAGREE_BITS
    log("median hard-decision disagreement V0 vs V3 = %.1f bits/174 (floor %d) -> %s"
        % (median_disagree, ROW_0D_MIN_DISAGREE_BITS, "FIRES" if row0d_fires else "clear"))
    result_bundle["row_0d"] = {"row": "0d", "fires": row0d_fires,
                                "median_disagree_bits": median_disagree,
                                "floor_bits": ROW_0D_MIN_DISAGREE_BITS}
    if row0d_fires:
        log("\nROW 0d FIRES: V0 and V3 are the same reading; no contrast is possible. "
            "NO VERDICT, escalate.")
        result_bundle["final_row"] = "0d"
        _write_report(args.out_dir, result_bundle, log_lines)
        _write_rows(args.out_dir, rows)
        return 5

    log("\n" + "=" * 90)
    log("Primary/secondary statistics")
    log("=" * 90)
    bootstrap = cluster_bootstrap_median_diff(rows, n_draws=args.n_draws)
    f_cross = float(sum(1 for r in rows if r["crosses"]) / len(rows))
    log("d_ber (paired median BER_V0 - BER_V3): point_estimate=%+.2fpp mean=%+.2fpp "
        "se=%.2fpp CI95=[%+.2f, %+.2f]pp p=%.4f (n_rows=%d n_clusters=%d n_draws=%d)"
        % (bootstrap["point_estimate"] * 100, bootstrap["mean"] * 100, bootstrap["se"] * 100,
           bootstrap["ci95"][0] * 100, bootstrap["ci95"][1] * 100, bootstrap["p_two_sided"],
           bootstrap["n_rows"], bootstrap["n_clusters"], bootstrap["n_draws"]))
    log("f_cross (fraction crossing V0-above->V3-below B50=%.1f%%): %.1f%%"
        % (B50_THRESHOLD * 100, f_cross * 100))
    result_bundle["d_ber"] = bootstrap
    result_bundle["f_cross"] = f_cross

    log("\nPer-population breakdown (Sec.5: do NOT average to a verdict):")
    per_pop: dict[str, dict] = {}
    for label in sorted(set(r["population"] for r in rows)):
        sub = [r for r in rows if r["population"] == label]
        sub_bootstrap = cluster_bootstrap_median_diff(sub, n_draws=args.n_draws, seed=bootstrap["seed"])
        sub_fcross = float(sum(1 for r in sub if r["crosses"]) / len(sub)) if sub else float("nan")
        per_pop[label] = {"n": len(sub), "d_ber": sub_bootstrap, "f_cross": sub_fcross}
        log("  [%s] n=%d d_ber point_estimate=%+.2fpp CI95=[%+.2f,%+.2f]pp f_cross=%.1f%%"
            % (label, len(sub), sub_bootstrap["point_estimate"] * 100,
               sub_bootstrap["ci95"][0] * 100, sub_bootstrap["ci95"][1] * 100, sub_fcross * 100))
    result_bundle["per_population"] = per_pop

    log("\n" + "=" * 90)
    log("Sec.7.1 -- variant decomposition (V1/V2 vs V0, attribution only)")
    log("=" * 90)
    variant_attrib: dict[str, dict] = {}
    for vlabel, key in (("V1", "d_ber_v1"), ("V2", "d_ber_v2")):
        vrows = [{"ts": r["ts"], "d_ber": r[key]} for r in rows]
        vb = cluster_bootstrap_median_diff(vrows, n_draws=args.n_draws, seed=bootstrap["seed"])
        variant_attrib[vlabel] = vb
        log("  %s vs V0: point_estimate=%+.2fpp CI95=[%+.2f,%+.2f]pp"
            % (vlabel, vb["point_estimate"] * 100, vb["ci95"][0] * 100, vb["ci95"][1] * 100))
    result_bundle["variant_attribution"] = variant_attrib

    log("\n" + "=" * 90)
    log("Sec.7.3 -- tight/loose stratification on |f_candidate - f_WSJTX| (report only, "
        "gate reads the COMBINED population)")
    log("=" * 90)
    tight_loose: dict[str, dict] = {}
    for label, pred in (
        ("tight", lambda r: abs(r["anchor_freq_hz"] - (r["wsjtx_freq_hz"] or 0.0)) <= TIGHT_MATCH_HZ),
        ("loose", lambda r: abs(r["anchor_freq_hz"] - (r["wsjtx_freq_hz"] or 0.0)) > TIGHT_MATCH_HZ),
    ):
        sub = [r for r in rows if r["wsjtx_freq_hz"] is not None and pred(r)]
        if sub:
            sb = cluster_bootstrap_median_diff(sub, n_draws=args.n_draws, seed=bootstrap["seed"])
            sfc = float(sum(1 for r in sub if r["crosses"]) / len(sub))
        else:
            sb = {"point_estimate": float("nan"), "ci95": [float("nan"), float("nan")]}
            sfc = float("nan")
        tight_loose[label] = {"n": len(sub), "d_ber": sb, "f_cross": sfc}
        log("  [%s] n=%d d_ber point_estimate=%+.2fpp CI95=[%+.2f,%+.2f]pp f_cross=%.1f%%"
            % (label, len(sub), sb["point_estimate"] * 100,
               sb["ci95"][0] * 100, sb["ci95"][1] * 100, sfc * 100))
    result_bundle["tight_loose"] = tight_loose

    if not args.skip_freq_sweep:
        log("\n" + "=" * 90)
        log("Sec.7.2 -- frequency-sensitivity sweep (V3 only; requirement statement, NOT a "
            "verdict row, NOT R2's rehabilitation)")
        log("=" * 90)
        sweep: dict[str, float] = {}
        for df in DF_SWEEP_HZ:
            bers = []
            for r in rows:
                pcm = wav_cache.get(r["pcm_key"])
                variants = CE.extract_variants(np.asarray(pcm, dtype=np.float64),
                                                r["anchor_freq_hz"], r["anchor_dt"], df_hz=df)
                bers.append(hard_decision_ber(list(variants["V3"]), r["true_bits"]))
            med = float(st.median(bers))
            sweep["%+.2f" % df] = med
            log("  df=%+.2fHz -> median V3 BER=%.2f%%" % (df, med * 100))
        result_bundle["freq_sweep"] = sweep
    else:
        log("\n--skip-freq-sweep set: Sec.7.2 NOT run (smoke run only).")

    log("\n" + "=" * 90)
    log("ROW 1/2/3/4 -- the gate, strict order")
    log("=" * 90)
    d_ber_pt = bootstrap["point_estimate"]
    ci_lo, ci_hi = bootstrap["ci95"]
    row1_fires = ci_lo > ROW_1_CI_LO_MIN and f_cross >= ROW_1_F_CROSS_MIN
    row2_fires = (not row1_fires) and ci_lo > ROW_1_CI_LO_MIN and f_cross < ROW_2_F_CROSS_MAX
    row3_fires = (not row1_fires) and (not row2_fires) and \
        abs(d_ber_pt) <= ROW_3_D_BER_ABS_MAX and ci_hi < ROW_3_CI_HI_MAX and f_cross < ROW_3_F_CROSS_MAX

    if row1_fires:
        final_row = "1"
        log("ROW 1 FIRES: CI_lo=%+.2fpp (>%.0fpp) AND f_cross=%.1f%% (>=%.0f%%)."
            % (ci_lo * 100, ROW_1_CI_LO_MIN * 100, f_cross * 100, ROW_1_F_CROSS_MIN * 100))
        log("CONSEQUENCE: coherent multi-symbol extraction is a first-order D-001 term. "
            "The C integration round becomes SCOPEABLE, and a proper recall sizing is "
            "ORDERED (f_cross is NOT itself the sizing).")
    elif row2_fires:
        final_row = "2"
        log("ROW 2 FIRES: CI_lo=%+.2fpp (>%.0fpp) AND f_cross=%.1f%% (<%.0f%%)."
            % (ci_lo * 100, ROW_1_CI_LO_MIN * 100, f_cross * 100, ROW_2_F_CROSS_MAX * 100))
        log("CONSEQUENCE: real, but it does not convert. The metric genuinely extracts "
            "more information and it is not enough to cross the threshold on this "
            "population. Limb 2 is necessary-but-not-sufficient. Next work sizes what "
            "else is needed -- not integration.")
    elif row3_fires:
        final_row = "3"
        log("ROW 3 FIRES: |d_ber|=%.2fpp (<=%.0fpp) AND CI_hi=%+.2fpp (<%.0fpp) AND "
            "f_cross=%.1f%% (<%.1f%%)."
            % (abs(d_ber_pt) * 100, ROW_3_D_BER_ABS_MAX * 100, ci_hi * 100,
               ROW_3_CI_HI_MAX * 100, f_cross * 100, ROW_3_F_CROSS_MAX * 100))
        log("CONSEQUENCE: limb 2 is dead too. Both limbs of the 2026-08-11 root cause "
            "would then be closed on outcome evidence, and the diagnosis itself must be "
            "reopened from scratch.")
    else:
        final_row = "4"
        log("ROW 4 (residue -- none of ROW 1/2/3 fired): d_ber=%+.2fpp CI95=[%+.2f,%+.2f]pp "
            "f_cross=%.1f%%." % (d_ber_pt * 100, ci_lo * 100, ci_hi * 100, f_cross * 100))
        log("CONSEQUENCE: escalate with the full distribution and per-population table. "
            "Do not average to a verdict.")

    result_bundle["final_row"] = final_row
    _write_report(args.out_dir, result_bundle, log_lines)
    _write_rows(args.out_dir, rows)
    log("\nWrote results/n2_results.json, results/n2_gate_report.json, results/harness_run.log")
    return 0


def _strip_private_fields(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k not in ("message", "true_bits")} for r in rows]


def _write_rows(out_dir: str, rows: list[dict]) -> None:
    P.write_json(os.path.join(out_dir, "n2_results.json"), {"rows": _strip_private_fields(rows)})


def _write_report(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "n2_gate_report.json"), bundle)
    with open(os.path.join(out_dir, "harness_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
