#!/usr/bin/env python3
"""TASK 1 -- arm B-dt-C1 (2026-08-22 Architect spec, Sec.4):
`qa/rr-study/2026-08-22-1411-architect-to-qa-spec-b-dt-c-reported-dt-sign.md`.

Fills the off-diagonal cell the existing corpora cannot: does `true_dt == 0` with a
NON-negative `time_offset` (i.e. offline, no playback/capture displacement) reproduce
the `true_dt == 0` SNR collapse, or not?

This is `ac_n5_dt_stratified_measurement.py`'s own S3 arm (HK-018 -- reused, not
reimplemented) with exactly one addition: `results[i]["dt"]` (already a field of the
ctypes FT8Result struct, `extract_llrs_ctypes.py:37`/`:112` -- precedent
`c5a_waterfall.py:109`) is now recorded per row as `reported_dt`, alongside
`signal_db`/`local_noise_db`. S8 is out of scope for this arm (spec Sec.4.1 -- adds
only the scenario confound Sec.2 named, not needed to fill the off-diagonal cell).

No code change, no live run, no new binary -- offline synthesis through the SAME
Amendment 2/3 pinned DLL AC-N5 used, called via the SAME direct
synth.encoder/synth.channel construction (HK-018, HK-022's own recorded rate fix).
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

import p23_common as P  # noqa: E402 -- write_json only
from harness.common import compute_seed  # noqa: E402
from harness.run_scenario import _load_messages, _load_scenario  # noqa: E402
from snr_terms_ctypes import SnrTermsDecoder, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

SCENARIOS_DIR = Path(_QA_ROOT) / "scenarios"
S3_MAX_PART_DT_S = 2.1  # parts 0-7 only, per spec Sec.4.1 -- same scope as AC-N5
SNR_FORMULA_OFFSET = 26.5
FREQ_MATCH_TOLERANCE_HZ = 30.0  # identical to AC-N5 -- S3 is single-signal, generous
                                 # against FT8's 6.25 Hz tone spacing, no S8 ambiguity here

DECODE_SAMPLE_RATE_HZ = 12_000  # decoder-native rate -- identical to AC-N5 (HK-018/HK-022)

# Spec Sec.4.4 pre-registered thresholds
ROW0_MIN_PART0 = 3
ROW0_MIN_PARTS_1_7 = 12
ROW0_D_OFF_REF = 2.0     # AC-N5's own part-0 reported SNR value (Sec.4.2/4.3)
ROW0_D_OFF_TOL = 1.0     # dB, one readout quantum
TRUE_SNR = 0.0           # scenario fixed.snr_db


def run_s3(dec: SnrTermsDecoder, log) -> list[dict]:
    from synth import channel, encoder  # noqa: PLC0415 -- lazy, matches AC-N5's own convention

    messages = _load_messages(SCENARIOS_DIR)
    scenario = _load_scenario(SCENARIOS_DIR / "s3-dt-offset.json", messages)
    parts = [p for p in scenario["parts"] if float(p["dt_s"]) <= S3_MAX_PART_DT_S]
    n_trials = scenario["trials"]
    log("S3: %d/%d parts in scope (dt_s <= %.1f), %d trials each, rendered at %d Hz"
        % (len(parts), len(scenario["parts"]), S3_MAX_PART_DT_S, n_trials, DECODE_SAMPLE_RATE_HZ))

    msg_ids = list(scenario["message_texts"].keys())
    text = scenario["message_texts"][msg_ids[0]]
    fixed = scenario["fixed"]
    true_freq_hz = float(fixed["base_freq_hz"])
    snr_db = float(fixed["snr_db"])
    assert snr_db == TRUE_SNR, "scenario fixed.snr_db drifted from spec precondition 4.2(2)"

    rows: list[dict] = []
    for part in parts:
        true_dt = float(part["dt_s"])
        for trial in range(n_trials):
            seed = compute_seed("S3", part["part_index"], trial)
            clean = encoder.encode_message(
                text, base_freq_hz=true_freq_hz, dt_s=true_dt, snr_db=None,
                sample_rate_hz=DECODE_SAMPLE_RATE_HZ, extended=False)
            samples = channel.add_noise(clean, snr_db, seed, sample_rate_hz=DECODE_SAMPLE_RATE_HZ)
            assert len(samples) == 180_000, (
                "part %d produced an unexpected buffer length %d" % (part["part_index"], len(samples)))

            results = dec.decode_all(samples)
            if not results:
                rows.append({"scenario": "S3", "part_index": part["part_index"], "trial": trial,
                              "true_dt": true_dt, "true_freq_hz": true_freq_hz, "matched": False,
                              "reason": "no_decode"})
                continue
            n, sig, noise = dec.get_last_snr_terms(capacity=max(50, len(results) + 10))
            assert n == len(results), (
                "AC-N3 already gated this contract -- a mismatch here means the pinned "
                "binary changed between runs; STOP: n=%d len(results)=%d" % (n, len(results)))

            i = min(range(len(results)), key=lambda k: abs(results[k]["freq_hz"] - true_freq_hz))
            freq_err = abs(results[i]["freq_hz"] - true_freq_hz)
            recon_snr = sig[i] - noise[i] - SNR_FORMULA_OFFSET
            rows.append({
                "scenario": "S3", "part_index": part["part_index"], "trial": trial,
                "true_dt": true_dt, "true_freq_hz": true_freq_hz,
                "reported_freq_hz": results[i]["freq_hz"], "freq_err_hz": freq_err,
                "reported_snr": results[i]["snr"], "signal_db": sig[i], "local_noise_db": noise[i],
                "reported_dt": results[i]["dt"],  # <-- the one addition this arm makes over AC-N5
                "reconstructed_snr": recon_snr, "n_decodes_this_trial": len(results),
                "matched": freq_err <= FREQ_MATCH_TOLERANCE_HZ,
            })
    n_matched = sum(1 for r in rows if r.get("matched"))
    log("S3: %d/%d (part,trial) cells produced a matched decode" % (n_matched, len(rows)))
    return rows


def _mean(vals: list[float]) -> "float | None":
    return float(st.mean(vals)) if vals else None


def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("B-dt-C1 -- OFFLINE reported_dt SIGN CHECK AT true_dt == 0 (spec 2026-08-22-1411)")
    log("=" * 90)

    dll_path = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
    log("Loading DLL: %s (pinned to Amendment 2/3, shim %d)" % (dll_path, CURRENT_SHIM_VERSION))
    try:
        dec = SnrTermsDecoder(dll_path, verify=True, expected_sha256=CURRENT_DLL_SHA256,
                               expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("DLL PIN/EXPORT CHECK FAILED: %s" % e)
        _write(out_dir, {"final": "dll_pin_fail", "error": str(e)}, log_lines)
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], dec.version))

    log("\n" + "-" * 90)
    rows = run_s3(dec, log)

    matched = [r for r in rows if r.get("matched")]
    part0 = [r for r in matched if r["part_index"] == 0]
    parts_1_7 = [r for r in matched if r["part_index"] >= 1]

    D_off = _mean([r["reported_snr"] - TRUE_SNR for r in part0])
    dt_off_0 = _mean([r["reported_dt"] for r in part0])

    log("\n" + "=" * 90)
    log("ROW 0 -- VALIDITY")
    log("=" * 90)
    limb_a = (len(part0) < ROW0_MIN_PART0) or (len(parts_1_7) < ROW0_MIN_PARTS_1_7)
    limb_b = (D_off is None) or (abs(D_off - ROW0_D_OFF_REF) > ROW0_D_OFF_TOL)
    log("  part0 matched = %d (need >= %d)" % (len(part0), ROW0_MIN_PART0))
    log("  parts1-7 matched = %d (need >= %d)" % (len(parts_1_7), ROW0_MIN_PARTS_1_7))
    log("  D_off = %s (ref %.1f +/- %.1f dB)" % ("%.3f" % D_off if D_off is not None else "n/a",
                                                   ROW0_D_OFF_REF, ROW0_D_OFF_TOL))
    log("  limb (a) fires: %s" % limb_a)
    log("  limb (b) fires: %s" % limb_b)

    row0_fires = limb_a or limb_b
    verdict = None
    if row0_fires:
        verdict = "ROW_0_VALIDITY_FAILED"
        log("\n=> ROW 0 FIRES. STOP, escalate. ROW 1/ROW 2 NOT evaluated per spec Sec.4.4.")
    else:
        log("\nROW 0 clear (both limbs). Proceeding to ROW 1/ROW 2.")
        log("\n" + "=" * 90)
        log("ROW 1 / ROW 2 -- dt_off_0 = %.4f s" % dt_off_0)
        log("=" * 90)
        if dt_off_0 >= 0.0:
            verdict = "ROW_1_MECHANISM_SUPPORTED"
            log("=> ROW 1: dt_off_0 >= 0.0 -- MECHANISM SUPPORTED.")
            log("   Same true_dt (0.0), opposite time_offset sign, opposite outcome.")
            log("   Proceed to TASK 2 (B-dt-C2); recommend Sec.1.1 fix as a Developer session.")
        else:
            verdict = "ROW_2_MECHANISM_REFUTED"
            log("=> ROW 2: dt_off_0 < 0.0 -- MECHANISM REFUTED AS STATED.")
            log("   STOP, escalate to the Architect. Do NOT run TASK 2, do NOT recommend a")
            log("   Developer session.")

    log("\n" + "-" * 90)
    log("4.5 REPORTED, NOT GATED")
    log("-" * 90)
    per_part = {}
    for p in range(8):
        prows = [r for r in matched if r["part_index"] == p]
        per_part[p] = {
            "n": len(prows),
            "reported_dt_mean": _mean([r["reported_dt"] for r in prows]),
            "signal_db_mean": _mean([r["signal_db"] for r in prows]),
            "local_noise_db_mean": _mean([r["local_noise_db"] for r in prows]),
            "reported_snr_mean": _mean([r["reported_snr"] for r in prows]),
        }
        pp = per_part[p]
        log("  part %d: n=%d  reported_dt=%s  signal_db=%s  local_noise_db=%s  reported_snr=%s"
            % (p, pp["n"],
               "%.3f" % pp["reported_dt_mean"] if pp["reported_dt_mean"] is not None else "n/a",
               "%.3f" % pp["signal_db_mean"] if pp["signal_db_mean"] is not None else "n/a",
               "%.3f" % pp["local_noise_db_mean"] if pp["local_noise_db_mean"] is not None else "n/a",
               "%.3f" % pp["reported_snr_mean"] if pp["reported_snr_mean"] is not None else "n/a"))

    n_unmatched = len([r for r in rows if not r.get("matched")])
    if n_unmatched:
        log("\n%d row(s) failed to match within %.0f Hz -- excluded from stats above."
            % (n_unmatched, FREQ_MATCH_TOLERANCE_HZ))

    log("=" * 90)

    bundle = {
        "final": verdict,
        "row0": {"part0_matched": len(part0), "parts_1_7_matched": len(parts_1_7),
                 "D_off": D_off, "limb_a_fires": limb_a, "limb_b_fires": limb_b},
        "dt_off_0": dt_off_0,
        "per_part": per_part,
        "n_rows": len(rows), "n_matched": len(matched), "n_unmatched": n_unmatched,
        "rows": rows,
    }
    _write(out_dir, bundle, log_lines)
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "b_dt_c1_report.json"), bundle)
    with open(os.path.join(out_dir, "b_dt_c1_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
