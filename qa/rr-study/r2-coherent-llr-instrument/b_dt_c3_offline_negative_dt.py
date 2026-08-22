#!/usr/bin/env python3
"""Arm B-dt-C3 (2026-08-22 14:33Z Architect spec, supersedes TASK 2 / B-dt-C2):
`qa/rr-study/2026-08-22-1433-architect-to-qa-spec-b-dt-c3-offline-negative-dt.md`.

Offline sweep over NEGATIVE `true_dt` (the side B-dt-C1 §2.5 showed this instrument has
never measured: offline `reported_dt - true_dt` sits at +0.14..+0.24 s at every part, so
`true_dt == 0` alone never drives `time_offset < 0` offline -- only genuinely early audio
can). Ten parts, DESCENDING `true_dt` (p0 = +0.08 .. p9 = -1.20), rendered `extended=True`
then truncated to the last 180,000 samples -- exactly the live decoder's own boundary-
aligned 15 s window (Sec.2.2 of the spec; `Ft8Decoder.cs:50` `ExpectedSampleCount`).

Reuses `b_dt_c1_offline_dt_check.py`'s decode/match/report skeleton (HK-018) and, through
it, `ac_n5_dt_stratified_measurement.py`'s own construction of `synth.encoder`/
`synth.channel` -- no code path is reimplemented, only the sweep and the two checks
(cross-correlation placement, fixed-once sigma) this spec's Sec.3.2/6 add.
"""
from __future__ import annotations

import os
import statistics as st
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_QA_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, _QA_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))  # p23_common.write_json
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from scipy import signal as _sig  # noqa: E402

import p23_common as P  # noqa: E402
from harness.common import compute_seed  # noqa: E402
from harness.run_scenario import _load_messages  # noqa: E402
from results_guard import guard_paths  # noqa: E402 -- N14
from snr_terms_ctypes import SnrTermsDecoder, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

SCENARIOS_DIR = Path(_QA_ROOT) / "scenarios"
SAMPLE_RATE_HZ = 12_000
BUFFER_SAMPLES = 180_000
BASE_FREQ_HZ = 1500.0
TRUE_SNR_DB = 0.0
SNR_FORMULA_OFFSET = 26.5
FREQ_MATCH_TOLERANCE_HZ = 30.0  # identical to B-dt-C1/AC-N5 -- single signal, no ambiguity
N_TRIALS = 5

# Spec Sec.3.1 -- pre-registered here, no scenario JSON file. Ordered by DESCENDING
# true_dt so increasing part index means "the signal arrives earlier".
PARTS = [
    {"part_index": 0, "true_dt": +0.08},
    {"part_index": 1, "true_dt": 0.00},
    {"part_index": 2, "true_dt": -0.08},
    {"part_index": 3, "true_dt": -0.16},
    {"part_index": 4, "true_dt": -0.24},
    {"part_index": 5, "true_dt": -0.32},
    {"part_index": 6, "true_dt": -0.48},
    {"part_index": 7, "true_dt": -0.72},
    {"part_index": 8, "true_dt": -0.96},
    {"part_index": 9, "true_dt": -1.20},
]
P1_INDEX = 1  # true_dt == 0.00 -- the sigma reference AND the exact-reproduction limb

# Spec Sec.2.3 -- rival hypothesis ("signal falls partly outside the decode window"),
# computed IN ADVANCE from the transmission length (79 * 0.16 s = 12.64 s). Reported
# alongside the measured deficit, never gated on (Sec.7 item 2).
RIVAL_DB = {
    0: 0.000, 1: 0.000, 2: -0.028, 3: -0.055, 4: -0.083, 5: -0.111,
    6: -0.168, 7: -0.255, 8: -0.343, 9: -0.433,
}

# Spec Sec.6 thresholds -- mechanical, pre-registered
ROW0A_MIN_MATCHED = 3          # per part, parts p0..p5 only (p6..p9 exempt, Sec.4)
ROW0A_CHECK_UP_TO_PART = 5
# B-dt-C1's own part-0 (true_dt=0.0, seeds compute_seed("S3",0,trial) trial 0..2) result,
# read from qa/rr-study/r2-coherent-llr-instrument/results/b_dt_c1_report.json --
# byte-identical render/decode path, so this arm's p1 trials 0-2 must reproduce it exactly.
ROW0B_SNR_REF_PRINTED = 2.000
ROW0B_DT_REF_PRINTED = 0.160
ROW0B_SIGDB_REF = -7.576
ROW0B_SIGDB_TOL = 0.001
ROW0C_LAG_TOL_SAMPLES = 1
STEP_THRESHOLD_DB = 8.0        # Sec.6 ROW 1/2/3 gate, HK-021(m) justified in the spec


def _mean(vals: "list[float]") -> "float | None":
    return float(st.mean(vals)) if vals else None


def cross_corr_lag(a: np.ndarray, b: np.ndarray) -> int:
    """Integer sample lag maximizing correlation of `a` against `b`, in the sense
    a[i] ~= b[i - lag] (i.e. lag > 0 means a's content is delayed relative to b's).
    FFT-based (scipy), full mode -- verified against a synthetic shifted pulse before use.
    """
    corr = _sig.correlate(a, b, mode="full", method="fft")
    return int(np.argmax(corr)) - (len(b) - 1)


def render_clean(encoder, text: str, true_dt: float) -> np.ndarray:
    """Sec.3.2(1): extended render, then truncate to the slot the live decoder sees."""
    buffer, _buffer_start_s = encoder.encode_message(
        text, base_freq_hz=BASE_FREQ_HZ, dt_s=true_dt, snr_db=None,
        sample_rate_hz=SAMPLE_RATE_HZ, extended=True)
    clean = buffer[-BUFFER_SAMPLES:]
    assert len(clean) == BUFFER_SAMPLES, (
        "part true_dt=%.2f produced an unexpected truncated length %d" % (true_dt, len(clean)))
    return clean


def run_sweep(dec: SnrTermsDecoder, log) -> tuple[list[dict], dict, float]:
    from synth import channel, encoder  # noqa: PLC0415 -- lazy, matches B-dt-C1's convention

    messages = _load_messages(SCENARIOS_DIR)
    text = messages["MSG-01"]

    # Render every part's clean (pre-noise) buffer once -- Sec.3.2(1).
    clean_by_part: dict[int, np.ndarray] = {}
    for part in PARTS:
        clean_by_part[part["part_index"]] = render_clean(encoder, text, part["true_dt"])
    clean_dt0 = clean_by_part[P1_INDEX]

    # Sec.3.2(2) -- fix sigma ONCE from the p1 (true_dt=0) untruncated render. Do NOT let
    # add_noise re-derive it per part (that would quietly null the rival hypothesis, Sec.6
    # item 2, by rescaling noise down with the lost signal energy on the negative side).
    sigma = channel.noise_sigma_for_snr(clean_dt0, TRUE_SNR_DB, sample_rate_hz=SAMPLE_RATE_HZ)
    log("Fixed noise sigma (from p1, true_dt=0.0, untruncated 180000-sample render): %.6f" % sigma)

    # Sec.6 ROW 0(c) -- placement. Cross-correlation lag of each part's clean against p1's,
    # compared to round(true_dt * fs) samples, tolerance 1 sample.
    placement_rows = []
    for part in PARTS:
        p = part["part_index"]
        true_dt = part["true_dt"]
        expected_lag = int(round(true_dt * SAMPLE_RATE_HZ))
        if p == P1_INDEX:
            measured_lag = 0  # trivial, skip the O(n log n) self-correlation
        else:
            measured_lag = cross_corr_lag(clean_by_part[p], clean_dt0)
        placement_rows.append({
            "part_index": p, "true_dt": true_dt, "expected_lag_samples": expected_lag,
            "measured_lag_samples": measured_lag,
            "lag_err_samples": measured_lag - expected_lag,
        })
        log("  placement part %d (true_dt=%+.2f): expected_lag=%d measured_lag=%d err=%d"
            % (p, true_dt, expected_lag, measured_lag, measured_lag - expected_lag))

    rows: list[dict] = []
    for part in PARTS:
        p = part["part_index"]
        true_dt = part["true_dt"]
        clean = clean_by_part[p]
        for trial in range(N_TRIALS):
            if p == P1_INDEX and trial < 3:
                seed = compute_seed("S3", 0, trial)  # Sec.3.2(3) -- identical to B-dt-C1 part 0
            else:
                seed = compute_seed("B-dt-C3", p, trial)

            samples = channel.add_awgn(clean, sigma, seed, sample_rate_hz=SAMPLE_RATE_HZ)
            assert len(samples) == BUFFER_SAMPLES, (
                "part %d trial %d produced an unexpected buffer length %d"
                % (p, trial, len(samples)))

            results = dec.decode_all(samples)
            if not results:
                rows.append({"part_index": p, "trial": trial, "true_dt": true_dt,
                              "seed": seed, "matched": False, "reason": "no_decode"})
                continue
            n, sig, noise = dec.get_last_snr_terms(capacity=max(50, len(results) + 10))
            assert n == len(results), (
                "AC-N3's own contract -- a mismatch here means the pinned binary changed "
                "between runs; STOP: n=%d len(results)=%d" % (n, len(results)))

            i = min(range(len(results)), key=lambda k: abs(results[k]["freq_hz"] - BASE_FREQ_HZ))
            freq_err = abs(results[i]["freq_hz"] - BASE_FREQ_HZ)
            recon_snr = sig[i] - noise[i] - SNR_FORMULA_OFFSET
            rows.append({
                "part_index": p, "trial": trial, "true_dt": true_dt, "seed": seed,
                "true_freq_hz": BASE_FREQ_HZ,
                "reported_freq_hz": results[i]["freq_hz"], "freq_err_hz": freq_err,
                "reported_snr": results[i]["snr"], "signal_db": sig[i], "local_noise_db": noise[i],
                "reported_dt": results[i]["dt"], "reconstructed_snr": recon_snr,
                "n_decodes_this_trial": len(results),
                "matched": freq_err <= FREQ_MATCH_TOLERANCE_HZ,
            })
    n_matched = sum(1 for r in rows if r.get("matched"))
    log("\nSweep: %d/%d (part,trial) cells produced a matched decode" % (n_matched, len(rows)))
    placement = {"rows": placement_rows,
                 "max_abs_err_samples": max(abs(r["lag_err_samples"]) for r in placement_rows)}
    return rows, placement, sigma


def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("B-dt-C3 -- OFFLINE NEGATIVE true_dt SWEEP (spec 2026-08-22-1433)")
    log("=" * 90)

    dll_path = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
    log("Loading DLL: %s (pinned, shim %d)" % (dll_path, CURRENT_SHIM_VERSION))
    try:
        dec = SnrTermsDecoder(dll_path, verify=True, expected_sha256=CURRENT_DLL_SHA256,
                               expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("DLL PIN/EXPORT CHECK FAILED: %s" % e)
        _write(out_dir, {"final": "dll_pin_fail", "error": str(e)}, log_lines)
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], dec.version))

    log("\n" + "-" * 90)
    log("RENDER + PLACEMENT (Sec.3.2, Sec.6 ROW 0(c))")
    log("-" * 90)
    rows, placement, sigma = run_sweep(dec, log)
    matched = [r for r in rows if r.get("matched")]

    per_part: dict[int, dict] = {}
    for part in PARTS:
        p = part["part_index"]
        true_dt = part["true_dt"]
        prows = [r for r in matched if r["part_index"] == p]
        per_part[p] = {
            "true_dt": true_dt,
            "n": len(prows),
            "n_trials": N_TRIALS,
            "E": _mean([r["reported_snr"] - TRUE_SNR_DB for r in prows]),
            "T": _mean([r["reported_dt"] for r in prows]),
            "signal_db": _mean([r["signal_db"] for r in prows]),
            "local_noise_db": _mean([r["local_noise_db"] for r in prows]),
            "rival_db": RIVAL_DB[p],
        }
        pp = per_part[p]
        pp["T_minus_true_dt"] = (pp["T"] - true_dt) if pp["T"] is not None else None

    log("\n" + "=" * 90)
    log("ROW 0 -- VALIDITY")
    log("=" * 90)

    # (a) decode floor, p0..p5 only
    limb_a_parts = [p for p in range(0, ROW0A_CHECK_UP_TO_PART + 1) if per_part[p]["n"] < ROW0A_MIN_MATCHED]
    limb_a = bool(limb_a_parts)
    log("  (a) decode floor p0..p5: %s"
        % (", ".join("p%d n=%d" % (p, per_part[p]["n"]) for p in range(0, ROW0A_CHECK_UP_TO_PART + 1))))
    log("      fires: %s%s" % (limb_a, (" -- parts %s below %d" % (limb_a_parts, ROW0A_MIN_MATCHED)) if limb_a else ""))

    # (b) exact reproduction, p1 trials 0-2 (S3-part-0-identical seeds)
    p1_repro_rows = [r for r in matched if r["part_index"] == P1_INDEX and r["trial"] < 3]
    repro_snr = _mean([r["reported_snr"] for r in p1_repro_rows])
    repro_dt = _mean([r["reported_dt"] for r in p1_repro_rows])
    repro_sigdb = _mean([r["signal_db"] for r in p1_repro_rows])
    limb_b = (
        len(p1_repro_rows) != 3
        or repro_snr is None or round(repro_snr, 3) != ROW0B_SNR_REF_PRINTED
        or repro_dt is None or round(repro_dt, 3) != ROW0B_DT_REF_PRINTED
        or repro_sigdb is None or abs(repro_sigdb - ROW0B_SIGDB_REF) > ROW0B_SIGDB_TOL
    )
    log("  (b) exact reproduction (p1 trials 0-2, B-dt-C1 part-0 seeds):")
    log("      n=%d  reported_snr=%s (ref %.3f)  reported_dt=%s (ref %.3f)  signal_db=%s (ref %.3f +/- %.3f)"
        % (len(p1_repro_rows),
           "%.6f" % repro_snr if repro_snr is not None else "n/a", ROW0B_SNR_REF_PRINTED,
           "%.6f" % repro_dt if repro_dt is not None else "n/a", ROW0B_DT_REF_PRINTED,
           "%.6f" % repro_sigdb if repro_sigdb is not None else "n/a", ROW0B_SIGDB_REF, ROW0B_SIGDB_TOL))
    log("      fires: %s" % limb_b)

    # (c) placement
    limb_c = placement["max_abs_err_samples"] > ROW0C_LAG_TOL_SAMPLES
    log("  (c) placement: max |measured_lag - expected_lag| = %d sample(s) (tol %d)"
        % (placement["max_abs_err_samples"], ROW0C_LAG_TOL_SAMPLES))
    log("      fires: %s" % limb_c)

    # (d) straddle -- evaluated over the ANALYSIS SET, defined below; but per spec Sec.6
    # ROW 0(d) it is a validity precondition, so compute the analysis set first (Sec.4 is
    # itself mechanical and does not depend on ROW 0's outcome).
    p_max = -1
    for part in PARTS:
        p = part["part_index"]
        if per_part[p]["n"] >= 3:
            p_max = p
        else:
            break
    analysis_set = list(range(0, p_max + 1)) if p_max >= 0 else []
    has_nonneg = any(per_part[p]["T"] is not None and per_part[p]["T"] >= 0.0 for p in analysis_set)
    has_neg = any(per_part[p]["T"] is not None and per_part[p]["T"] < 0.0 for p in analysis_set)
    limb_d = not (has_nonneg and has_neg)
    log("  (d) straddle: analysis set = %s; has T(p)>=0: %s; has T(p)<0: %s"
        % (analysis_set, has_nonneg, has_neg))
    log("      fires: %s" % limb_d)

    row0_fires = limb_a or limb_b or limb_c or limb_d
    verdict = None
    p_step = p_sign = max_delta = None
    deltas: dict[int, float] = {}

    if row0_fires:
        fired = [name for name, v in (("a", limb_a), ("b", limb_b), ("c", limb_c), ("d", limb_d)) if v]
        verdict = "ROW_0_VALIDITY_FAILED"
        log("\n=> ROW 0 FIRES on limb(s) %s. STOP, escalate. ROW 1/2/3 NOT evaluated." % fired)
    else:
        log("\nROW 0 clear (all four limbs). Analysis set = parts %s (p_max = %d)."
            % (analysis_set, p_max))

        for p in analysis_set:
            if p == 0:
                continue
            e_prev = per_part[p - 1]["E"]
            e_cur = per_part[p]["E"]
            if e_prev is not None and e_cur is not None:
                deltas[p] = e_prev - e_cur
        if deltas:
            p_step = max(deltas, key=lambda k: deltas[k])
            max_delta = deltas[p_step]
        neg_parts_in_set = [p for p in analysis_set if per_part[p]["T"] is not None and per_part[p]["T"] < 0.0]
        p_sign = min(neg_parts_in_set) if neg_parts_in_set else None

        log("\n" + "=" * 90)
        log("ROW 1 / 2 / 3 -- max_p Delta(p) = %s dB at p_step = %s; p_sign = %s"
            % ("%.3f" % max_delta if max_delta is not None else "n/a", p_step, p_sign))
        log("=" * 90)

        if max_delta is None or max_delta < STEP_THRESHOLD_DB:
            verdict = "ROW_1_NO_STEP"
            log("=> ROW 1: max Delta(p) < %.1f dB -- NO STEP." % STEP_THRESHOLD_DB)
            log("   The collapse did not reproduce offline even with reported_dt driven")
            log("   negative. Clamp mechanism is NOT the explanation. STOP, escalate.")
        elif p_step == p_sign:
            verdict = "ROW_2_MECHANISM_CONFIRMED"
            log("=> ROW 2: step >= %.1f dB AND p_step == p_sign -- CO-LOCATED." % STEP_THRESHOLD_DB)
            log("   Recommend the Sec.1.1 fix (ft8_shim.c:1491-1498) to the Captain as a")
            log("   Developer session, carrying the Sec.8 regression check. QA does not open it.")
        else:
            verdict = "ROW_3_MECHANISM_REFUTED"
            log("=> ROW 3: step >= %.1f dB but p_step != p_sign -- SEPARATED." % STEP_THRESHOLD_DB)
            log("   The SNR step and the sign change are distinguishable events. STOP, escalate.")

    log("\n" + "-" * 90)
    log("SEC.7 -- REPORTED, NOT GATED")
    log("-" * 90)
    for part in PARTS:
        p = part["part_index"]
        pp = per_part[p]
        log("  part %d (true_dt=%+.2f): n=%d/%d  E=%s  T=%s  T-true_dt=%s  signal_db=%s  "
            "local_noise_db=%s  rival=%.3f dB"
            % (p, pp["true_dt"], pp["n"], N_TRIALS,
               "%.3f" % pp["E"] if pp["E"] is not None else "n/a",
               "%.3f" % pp["T"] if pp["T"] is not None else "n/a",
               "%.3f" % pp["T_minus_true_dt"] if pp["T_minus_true_dt"] is not None else "n/a",
               "%.3f" % pp["signal_db"] if pp["signal_db"] is not None else "n/a",
               "%.3f" % pp["local_noise_db"] if pp["local_noise_db"] is not None else "n/a",
               pp["rival_db"]))

    noise_means = [per_part[p]["local_noise_db"] for p in range(10) if per_part[p]["local_noise_db"] is not None]
    noise_spread = (max(noise_means) - min(noise_means)) if noise_means else None
    log("\nlocal_noise_db spread across all parts with >=1 matched decode: %s dB"
        % ("%.3f" % noise_spread if noise_spread is not None else "n/a"))

    neg_side_flatness = None
    if not row0_fires and analysis_set:
        neg_e = [per_part[p]["E"] for p in analysis_set
                 if per_part[p]["T"] is not None and per_part[p]["T"] < 0.0 and per_part[p]["E"] is not None]
        if neg_e:
            neg_side_flatness = max(neg_e) - min(neg_e)
    log("Negative-side (T(p)<0, analysis set) flatness max(E)-min(E): %s dB"
        % ("%.3f" % neg_side_flatness if neg_side_flatness is not None else "n/a (no qualifying parts)"))

    n_unmatched = len([r for r in rows if not r.get("matched")])
    if n_unmatched:
        log("\n%d row(s) failed to match within %.0f Hz -- excluded from stats above."
            % (n_unmatched, FREQ_MATCH_TOLERANCE_HZ))
    log("=" * 90)

    bundle = {
        "final": verdict,
        "sigma": sigma,
        "row0": {
            "limb_a_fires": limb_a, "limb_a_parts": limb_a_parts,
            "limb_b_fires": limb_b, "limb_b_n": len(p1_repro_rows),
            "limb_b_reported_snr_mean": repro_snr, "limb_b_reported_dt_mean": repro_dt,
            "limb_b_signal_db_mean": repro_sigdb,
            "limb_c_fires": limb_c, "limb_c_max_abs_err_samples": placement["max_abs_err_samples"],
            "limb_d_fires": limb_d, "limb_d_has_nonneg": has_nonneg, "limb_d_has_neg": has_neg,
        },
        "placement": placement["rows"],
        "analysis_set": analysis_set, "p_max": p_max,
        "deltas": deltas, "p_step": p_step, "p_sign": p_sign, "max_delta": max_delta,
        "per_part": per_part,
        "noise_spread_db": noise_spread,
        "neg_side_flatness_db": neg_side_flatness,
        "n_rows": len(rows), "n_matched": len(matched), "n_unmatched": n_unmatched,
        "rows": rows,
    }
    _write(out_dir, bundle, log_lines)
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    report_path = os.path.join(out_dir, "b_dt_c3_report.json")
    log_path = os.path.join(out_dir, "b_dt_c3_run.log")
    guard_paths([report_path, log_path], REPO_ROOT)  # N14
    P.write_json(report_path, bundle)
    with open(log_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
