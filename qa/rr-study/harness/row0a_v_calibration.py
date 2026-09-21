"""E4-STAGE2 amendment B1 (spec Sec.8.5) -- ROW 0a(v)/(vi): calibrate the
split-window drift estimator (Sec.8.4) against the bench's own known DRIFT
ladder, and (disclosure only) drift-under-fade.

Usage:
    python harness/row0a_v_calibration.py [--trials 50] [--out <path.json>]

No station time, no live audio, no `src/`/`native/` change (HK-011). Not
NFR-021-sensitive (synthetic Q-callsign message only).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import compute_seed
from synth import channel, encoder, fade, modulator
from synth.constants import DEFAULT_SAMPLE_RATE_HZ
from synth.estimator import split_window_drift_hz

MESSAGE = "CQ Q1ABC FN42"
BASE_FREQ_HZ = 1500.0
SNR_DB = -8.0
DRIFT_DOSES_HZ = [0, 0.5, 1, 2, 4, 8, 16]      # bench's own DRIFT ladder, Sec.8.5
DEFAULT_TRIALS = 50
NULL_DOSE_ABS_BAR_HZ = 0.5                      # 0a(v): |Delta_f| < 0.5 Hz at dose 0
FADE_DOSES_FOR_0A_VI = [1, 5]                   # Sec.8.5: B = 1 Hz and 5 Hz
DRIFT_UNDER_FADE_HZ = 8.0                       # Sec.8.5: "injected 8 Hz combined with FADE"


def _tolerance_hz(dose: float) -> float:
    return max(0.5, 0.10 * dose)


def _drift_trial(dose_hz: float, trial: int, tones, fs: int) -> "tuple[float, bool]":
    noise_seed = compute_seed(f"E4-STAGE2-0A-V-NOISE-{dose_hz}", 0, trial)
    clean = modulator.modulate(tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs, drift_hz=dose_hz)
    noisy = channel.add_noise(clean, SNR_DB, noise_seed, sample_rate_hz=fs)
    return split_window_drift_hz(noisy, tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)


def _drift_under_fade_trial(fade_b_hz: float, trial: int, tones, fs: int) -> "tuple[float, bool]":
    fade_seed = compute_seed(f"E4-STAGE2-0A-VI-FADE-{fade_b_hz}", 0, trial)
    noise_seed = compute_seed(f"E4-STAGE2-0A-VI-NOISE-{fade_b_hz}", 0, trial)
    clean = fade.modulate_faded(tones, BASE_FREQ_HZ, fade_b_hz, dt_s=0.0, sample_rate_hz=fs,
                                 seed=fade_seed, drift_hz=DRIFT_UNDER_FADE_HZ)
    noisy = channel.add_noise(clean, SNR_DB, noise_seed, sample_rate_hz=fs)
    return split_window_drift_hz(noisy, tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)


def run(trials: int) -> dict:
    tones = encoder.message_to_tones(MESSAGE)
    fs = DEFAULT_SAMPLE_RATE_HZ

    drift_ladder = {}
    for dose in DRIFT_DOSES_HZ:
        vals, oor = [], []
        for t in range(trials):
            v, o = _drift_trial(dose, t, tones, fs)
            vals.append(v)
            oor.append(o)
        drift_ladder[dose] = {"recovered": vals, "out_of_range": oor}

    drift_under_fade = {}
    for b in FADE_DOSES_FOR_0A_VI:
        vals, oor = [], []
        for t in range(trials):
            v, o = _drift_under_fade_trial(b, t, tones, fs)
            vals.append(v)
            oor.append(o)
        drift_under_fade[b] = {"recovered": vals, "out_of_range": oor}

    return {
        "trials_per_cell": trials,
        "message": MESSAGE,
        "base_freq_hz": BASE_FREQ_HZ,
        "snr_db": SNR_DB,
        "drift_ladder": {str(k): v for k, v in drift_ladder.items()},
        "drift_under_fade": {str(k): v for k, v in drift_under_fade.items()},
    }


def analyse(data: dict) -> dict:
    ladder = {float(k): v for k, v in data["drift_ladder"].items()}
    per_dose = {}
    all_pass = True
    for dose in DRIFT_DOSES_HZ:
        cell = ladder[dose]
        vals = np.asarray(cell["recovered"])
        oor = np.asarray(cell["out_of_range"], dtype=bool)
        in_range_vals = vals[~oor]
        n_oor = int(np.sum(oor))
        if dose == 0:
            median_abs = float(np.median(np.abs(in_range_vals))) if len(in_range_vals) else float("nan")
            cell_pass = (len(in_range_vals) > 0) and (median_abs < NULL_DOSE_ABS_BAR_HZ)
            per_dose[dose] = {
                "n_in_range": int(len(in_range_vals)), "n_out_of_range": n_oor,
                "median_abs_recovered_hz": median_abs, "pass": cell_pass,
            }
        else:
            median_rec = float(np.median(in_range_vals)) if len(in_range_vals) else float("nan")
            tol = _tolerance_hz(dose)
            err = abs(median_rec - dose) if len(in_range_vals) else float("inf")
            cell_pass = (len(in_range_vals) > 0) and (err <= tol)
            per_dose[dose] = {
                "n_in_range": int(len(in_range_vals)), "n_out_of_range": n_oor,
                "median_recovered_hz": median_rec, "tolerance_hz": tol,
                "abs_error_hz": err, "pass": cell_pass,
            }
        all_pass = all_pass and cell_pass

    dof = {float(k): v for k, v in data["drift_under_fade"].items()}
    dof_summary = {}
    for b, cell in dof.items():
        vals = np.asarray(cell["recovered"])
        oor = np.asarray(cell["out_of_range"], dtype=bool)
        in_range_vals = vals[~oor]
        dof_summary[b] = {
            "n_in_range": int(len(in_range_vals)), "n_out_of_range": int(np.sum(oor)),
            "median_recovered_hz": float(np.median(in_range_vals)) if len(in_range_vals) else float("nan"),
            "injected_drift_hz": DRIFT_UNDER_FADE_HZ,
        }

    return {
        "0a_v_per_dose": per_dose,
        "0a_v_overall": "PASS" if all_pass else "STOP",
        "0a_vi_drift_under_fade_disclosure": dof_summary,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    data = run(args.trials)
    result = analyse(data)

    out_path = args.out or str(_QA_ROOT / "row0a_v_calibration_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"raw": data, "analysis": result}, f, indent=2)

    print(f"ROW 0a(v) overall: {result['0a_v_overall']}")
    for dose in DRIFT_DOSES_HZ:
        c = result["0a_v_per_dose"][dose]
        if dose == 0:
            print(f"  dose=0   median|recovered|={c['median_abs_recovered_hz']:.4f}Hz "
                  f"(bar <0.5)  oor={c['n_out_of_range']}  pass={c['pass']}")
        else:
            print(f"  dose={dose:>4}  median_recovered={c['median_recovered_hz']:+.4f}Hz  "
                  f"err={c['abs_error_hz']:.4f}  tol={c['tolerance_hz']:.4f}  "
                  f"oor={c['n_out_of_range']}  pass={c['pass']}")
    print("ROW 0a(vi) drift-under-fade (disclosure, injected drift=8Hz):")
    for b, c in result["0a_vi_drift_under_fade_disclosure"].items():
        print(f"  FADE B={b}Hz -> median_recovered={c['median_recovered_hz']:+.4f}Hz  "
              f"oor={c['n_out_of_range']}/{c['n_in_range']+c['n_out_of_range']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
