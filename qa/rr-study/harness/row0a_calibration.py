"""E4-STAGE2 Sec.3.0 -- ROW 0a: calibrate the channel-gain estimator on the
bench's own FADE renders, where B (Doppler spread) is known by construction,
before it ever touches live audio.

Usage:
    python harness/row0a_calibration.py [--trials 50] [--out <path.json>]

No station time, no live audio, no `src/`/`native/` change (HK-011). Not
NFR-021-sensitive -- MSG-01 is an existing Q-prefix synthetic message already
committed elsewhere in this study; nothing here is a real callsign.
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
from synth.estimator import drift_hz, extract_channel_gains, rho1

MESSAGE = "CQ Q1ABC FN42"          # existing gate message (MSG-01), synthetic Q-callsign
BASE_FREQ_HZ = 1500.0              # isolated single-station render, arbitrary mid-band
FADE_DOSES_HZ = [0.1, 0.25, 0.5, 1, 2, 5, 10, 20]     # Stage-2 spec Sec.3.0, bench's own ladder
SNRS_DB = [-8.0, 0.0]
DRIFT_DOSES_HZ = [0, 0.5, 1, 2, 4, 8, 16]              # bench's own DRIFT ladder (bonus check)
DEFAULT_TRIALS = 50                # spec's own floor ("N >= 50 trials per cell")


def _fade_trial(dose_hz: float, snr_db: float, trial: int, tones, fs: int) -> "tuple[float, float]":
    fade_seed = compute_seed(f"E4-STAGE2-0A-FADE-{dose_hz}-{snr_db}", 0, trial)
    noise_seed = compute_seed(f"E4-STAGE2-0A-NOISE-{dose_hz}-{snr_db}", 0, trial)
    clean = fade.modulate_faded(tones, BASE_FREQ_HZ, dose_hz, dt_s=0.0,
                                 sample_rate_hz=fs, seed=fade_seed)
    noisy = channel.add_noise(clean, snr_db, noise_seed, sample_rate_hz=fs)
    g = extract_channel_gains(noisy, tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)
    return rho1(g), drift_hz(g, sample_rate_hz=fs)


def _undistorted_trial(snr_db: float, trial: int, tones, fs: int) -> "tuple[float, float]":
    noise_seed = compute_seed(f"E4-STAGE2-0A-NULL-NOISE-{snr_db}", 0, trial)
    clean = modulator.modulate(tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)
    noisy = channel.add_noise(clean, snr_db, noise_seed, sample_rate_hz=fs)
    g = extract_channel_gains(noisy, tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)
    return rho1(g), drift_hz(g, sample_rate_hz=fs)


def _drift_ladder_trial(dose_hz: float, snr_db: float, trial: int, tones, fs: int) -> float:
    """Bonus check, NOT required by ROW 0a as written: validate drift_hz()
    against a KNOWN nonzero DRIFT dose (the bench's own ladder), not just the
    drift=0 null 0a(iv) checks. Motivation: estimator.drift_hz's own
    Nyquist-aliasing caveat predicts failure above ~6.25 Hz total drift, and
    Sec.3.2's E4/E5 rows depend on this SAME estimator reading live drift
    correctly up to and past 8 Hz.
    """
    noise_seed = compute_seed(f"E4-STAGE2-0A-DRIFTLADDER-NOISE-{dose_hz}-{snr_db}", 0, trial)
    clean = modulator.modulate(tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs, drift_hz=dose_hz)
    noisy = channel.add_noise(clean, snr_db, noise_seed, sample_rate_hz=fs)
    g = extract_channel_gains(noisy, tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)
    return drift_hz(g, sample_rate_hz=fs)


def run(trials: int) -> dict:
    tones = encoder.message_to_tones(MESSAGE)
    fs = DEFAULT_SAMPLE_RATE_HZ

    fade_rho: "dict[tuple[float, float], list[float]]" = {}
    fade_drift: "dict[tuple[float, float], list[float]]" = {}
    for dose in FADE_DOSES_HZ:
        for snr in SNRS_DB:
            rhos, drifts = [], []
            for t in range(trials):
                r, d = _fade_trial(dose, snr, t, tones, fs)
                rhos.append(r)
                drifts.append(d)
            fade_rho[(dose, snr)] = rhos
            fade_drift[(dose, snr)] = drifts

    null_rho, null_drift = [], []
    for t in range(trials):
        r, d = _undistorted_trial(-8.0, t, tones, fs)
        null_rho.append(r)
        null_drift.append(d)

    drift_ladder: "dict[float, list[float]]" = {}
    for dose in DRIFT_DOSES_HZ:
        drift_ladder[dose] = [_drift_ladder_trial(dose, -8.0, t, tones, fs) for t in range(trials)]

    return {
        "trials_per_cell": trials,
        "message": MESSAGE,
        "base_freq_hz": BASE_FREQ_HZ,
        "fade_rho": {f"{d}|{s}": v for (d, s), v in fade_rho.items()},
        "fade_drift": {f"{d}|{s}": v for (d, s), v in fade_drift.items()},
        "null_rho_m8db": null_rho,
        "null_drift_m8db": null_drift,
        "drift_ladder_m8db": {str(d): v for d, v in drift_ladder.items()},
    }


def analyse(data: dict) -> dict:
    trials = data["trials_per_cell"]
    fade_rho = {tuple(float(x) for x in k.split("|")): v for k, v in data["fade_rho"].items()}

    # --- 0a(i): monotone -- median rho1 strictly decreasing in B, 0.1 -> 2 Hz, -8 dB
    mono_doses = [d for d in FADE_DOSES_HZ if d <= 2]
    medians_m8 = [float(np.median(fade_rho[(d, -8.0)])) for d in mono_doses]
    monotone = all(medians_m8[i] > medians_m8[i + 1] for i in range(len(medians_m8) - 1))

    # --- 0a(ii): separation -- exists rho* with P(rho1<rho*|B=5,-8dB)>=0.90 and
    # P(rho1<rho*|B<=1,-8dB)<=0.10. A valid rho* exists iff the 90th percentile of
    # the B=5 Hz sample is <= the 10th percentile of the pooled B<=1 Hz sample
    # (rho* set to either bound is then admissible; report the interval and its
    # midpoint as the fixed operating threshold).
    b5 = np.asarray(fade_rho[(5, -8.0)])
    b_le1_pool = np.concatenate([np.asarray(fade_rho[(d, -8.0)]) for d in [0.1, 0.25, 0.5, 1]])
    p90_b5 = float(np.percentile(b5, 90))
    p10_ble1 = float(np.percentile(b_le1_pool, 10))
    separable = p90_b5 <= p10_ble1
    rho_star = (p90_b5 + p10_ble1) / 2.0 if separable else None
    p_lt_star_b5 = float(np.mean(b5 < rho_star)) if separable else None
    p_lt_star_ble1 = float(np.mean(b_le1_pool < rho_star)) if separable else None

    # --- 0a(iii): saturation point -- smallest B where median rho1 is within 10%
    # of the B=20 Hz median (disclosure only, no STOP).
    medians_all_m8 = {d: float(np.median(fade_rho[(d, -8.0)])) for d in FADE_DOSES_HZ}
    ref20 = medians_all_m8[20]
    sat_dose = None
    for d in FADE_DOSES_HZ:
        if ref20 != 0 and abs(medians_all_m8[d] - ref20) / abs(ref20) <= 0.10:
            sat_dose = d
            break

    # --- 0a(iv): null passes where it holds -- undistorted renders, -8 dB:
    # median rho1 >= 0.90, drift estimator |delta_f| < 0.5 Hz.
    null_rho_med = float(np.median(data["null_rho_m8db"]))
    null_drift_med = float(np.median(np.abs(data["null_drift_m8db"])))
    null_drift_max = float(np.max(np.abs(data["null_drift_m8db"])))
    null_pass = (null_rho_med >= 0.90) and (null_drift_med < 0.5)

    # --- bonus: drift-ladder recovery (not required by 0a as written)
    drift_ladder = {float(k): v for k, v in data["drift_ladder_m8db"].items()}
    drift_recovery = {}
    for dose, vals in drift_ladder.items():
        arr = np.asarray(vals)
        drift_recovery[dose] = {
            "median_recovered_hz": float(np.median(arr)),
            "mean_recovered_hz": float(np.mean(arr)),
            "std_hz": float(np.std(arr)),
            "median_abs_error_hz": float(np.median(np.abs(arr - dose))),
        }

    row0a_i_pass = monotone
    row0a_ii_pass = separable
    row0a_iv_pass = null_pass
    overall_stop = not (row0a_i_pass and row0a_ii_pass and row0a_iv_pass)

    return {
        "0a_i_monotone": {
            "pass": row0a_i_pass,
            "doses": mono_doses,
            "median_rho1_m8db": medians_m8,
        },
        "0a_ii_separation": {
            "pass": row0a_ii_pass,
            "p90_rho1_B5Hz_m8db": p90_b5,
            "p10_rho1_Ble1Hz_m8db": p10_ble1,
            "rho_star": rho_star,
            "P_lt_rho_star_given_B5": p_lt_star_b5,
            "P_lt_rho_star_given_Ble1": p_lt_star_ble1,
        },
        "0a_iii_saturation": {
            "median_rho1_by_dose_m8db": medians_all_m8,
            "saturation_dose_hz": sat_dose,
        },
        "0a_iv_null": {
            "pass": row0a_iv_pass,
            "median_rho1": null_rho_med,
            "median_abs_drift_hz": null_drift_med,
            "max_abs_drift_hz": null_drift_max,
            "n": trials,
        },
        "row0a_overall": "STOP" if overall_stop else "PASS",
        "bonus_drift_ladder_m8db": drift_recovery,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    data = run(args.trials)
    result = analyse(data)

    out_path = args.out or str(_QA_ROOT / "row0a_calibration_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"raw": data, "analysis": result}, f, indent=2)

    print(f"ROW 0a overall: {result['row0a_overall']}")
    print(f"  0a(i)  monotone 0.1->2Hz @-8dB: {result['0a_i_monotone']['pass']} "
          f"{result['0a_i_monotone']['median_rho1_m8db']}")
    ii = result["0a_ii_separation"]
    print(f"  0a(ii) separation @-8dB: {ii['pass']}  p90(B=5)={ii['p90_rho1_B5Hz_m8db']:.4f} "
          f"p10(B<=1)={ii['p10_rho1_Ble1Hz_m8db']:.4f}  rho*={ii['rho_star']}")
    print(f"  0a(iii) saturation dose: {result['0a_iii_saturation']['saturation_dose_hz']} Hz")
    print(f"  0a(iv) null @-8dB: pass={result['0a_iv_null']['pass']} "
          f"median_rho1={result['0a_iv_null']['median_rho1']:.4f} "
          f"median|drift|={result['0a_iv_null']['median_abs_drift_hz']:.4f}Hz "
          f"max|drift|={result['0a_iv_null']['max_abs_drift_hz']:.4f}Hz")
    print("  bonus drift-ladder recovery (median recovered Hz / median abs error Hz):")
    for dose, stats in sorted(result["bonus_drift_ladder_m8db"].items()):
        print(f"    dose={dose:>5} -> recovered={stats['median_recovered_hz']:+.3f}  "
              f"abs_err={stats['median_abs_error_hz']:.3f}  std={stats['std_hz']:.3f}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
