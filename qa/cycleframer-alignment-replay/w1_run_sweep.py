#!/usr/bin/env python3
"""D-001 W1 -- driver: runs Arm A / Arm B, bins the curves, computes E against THE 135.

See `w1_sec5_calibration.py` for the harness/design docstring. This script just wires it
together, reports progress, and writes raw + summary JSON to
`artefacts/d001_w1_sec5_calibration/` (git-ignored, NFR-021-safe).
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import w1_sec5_calibration as w1  # noqa: E402

os.makedirs(w1.OUT_DIR, exist_ok=True)

SEED = 20260807
N_BUFFERS_ARM_A = int(os.environ.get("W1_N_BUFFERS_A", "200"))
N_BUFFERS_ARM_B = int(os.environ.get("W1_N_BUFFERS_B", "200"))
N_SIGNALS_ARM_A = 9   # within the spec's 8-10 range
DELTAS = [0.0, 3.0, 7.0, 15.0]


def sample_snr(rng: random.Random) -> float:
    """Stratified SNR sampler: 70% concentrated over the transition-informed range (recon:
    BER spans ~0% to ~55% across SNR approx -14..-30 dB, 2500 Hz reference), 30% wide to
    characterise the plateaus and support B10/B90. Recon: single-buffer/9-anchor pilot run
    logged in the dated findings doc Sec.3."""
    if rng.random() < 0.70:
        return rng.uniform(-27.0, -15.0)
    return rng.uniform(-33.0, -12.0)


def run_arm_a(native: w1.Native, n_buffers: int, seed: int) -> tuple[list[dict], dict]:
    rng_py = random.Random(seed)
    rng_np = np.random.default_rng(seed)
    measurements: list[dict] = []
    n_av_fail = 0
    n_clipped = 0
    for i in range(n_buffers):
        snr_list = [sample_snr(rng_py) for _ in range(N_SIGNALS_ARM_A)]
        buf, planted = w1.build_buffer_arm_a(native, rng_py, rng_np, snr_list)
        try:
            rows = w1.measure_buffer(native, buf, planted, "A")
        except Exception as e:  # noqa: BLE001 -- decode-call robustness, logged not swallowed silently
            print(f"[WARN] Arm A buffer {i}: decode raised {e!r}", file=sys.stderr)
            n_av_fail += 1
            continue
        n_clipped += sum(1 for r in rows if r.get("peak_scaled"))
        measurements.extend(rows)
        if (i + 1) % 25 == 0:
            n_loc = sum(1 for m in measurements if m.get("located"))
            print(f"  Arm A: {i + 1}/{n_buffers} buffers, {len(measurements)} planted, "
                  f"{n_loc} located")
    return measurements, {"n_av_fail": n_av_fail, "n_buffers_clipped": n_clipped}


def run_arm_b(native: w1.Native, n_buffers: int, seed: int) -> tuple[list[dict], dict]:
    rng_py = random.Random(seed)
    rng_np = np.random.default_rng(seed)
    measurements: list[dict] = []
    n_av_fail = 0
    n_clipped = 0
    for i in range(n_buffers):
        pair_snrs = [sample_snr(rng_py) for _ in range(len(DELTAS))]
        buf, planted = w1.build_buffer_arm_b(native, rng_py, rng_np, pair_snrs, DELTAS)
        try:
            rows = w1.measure_buffer(native, buf, planted, "B")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Arm B buffer {i}: decode raised {e!r}", file=sys.stderr)
            n_av_fail += 1
            continue
        n_clipped += sum(1 for r in rows if r.get("peak_scaled"))
        measurements.extend(rows)
        if (i + 1) % 25 == 0:
            n_loc = sum(1 for m in measurements if m.get("located"))
            print(f"  Arm B: {i + 1}/{n_buffers} buffers, {len(measurements)} planted, "
                  f"{n_loc} located")
    return measurements, {"n_av_fail": n_av_fail, "n_buffers_clipped": n_clipped}


def main() -> None:
    t0 = time.time()
    print(f"Loading diagnostic DLL: {w1.DLL_PATH}")
    native = w1.Native(w1.DLL_PATH)
    print(f"shim version: {native.version} (expected {w1.EXPECTED_SHIM_VERSION})")
    assert native.version == w1.EXPECTED_SHIM_VERSION, "shim version mismatch -- STOP"

    print(f"\nArm A: {N_BUFFERS_ARM_A} buffers x {N_SIGNALS_ARM_A} signals/buffer")
    t1 = time.time()
    arm_a, meta_a = run_arm_a(native, N_BUFFERS_ARM_A, SEED)
    dt_a = time.time() - t1
    n_loc_a = sum(1 for m in arm_a if m.get("located"))
    print(f"  done in {dt_a:.1f}s: {len(arm_a)} planted, {n_loc_a} located "
          f"({meta_a['n_av_fail']} buffer decode failures, "
          f"{meta_a['n_buffers_clipped']} clipped-scale measurements)")

    print(f"\nArm B: {N_BUFFERS_ARM_B} buffers x {len(DELTAS)} pairs (2x) /buffer")
    t1 = time.time()
    arm_b, meta_b = run_arm_b(native, N_BUFFERS_ARM_B, SEED + 1)
    dt_b = time.time() - t1
    n_loc_b = sum(1 for m in arm_b if m.get("located"))
    print(f"  done in {dt_b:.1f}s: {len(arm_b)} planted, {n_loc_b} located "
          f"({meta_b['n_av_fail']} buffer decode failures, "
          f"{meta_b['n_buffers_clipped']} clipped-scale measurements)")

    with open(os.path.join(w1.OUT_DIR, "arm_a_raw.json"), "w") as fh:
        json.dump(arm_a, fh)
    with open(os.path.join(w1.OUT_DIR, "arm_b_raw.json"), "w") as fh:
        json.dump(arm_b, fh)

    curve_a = w1.bin_curve(arm_a)
    curve_b = w1.bin_curve(arm_b)

    def print_curve(label: str, curve: list[dict]) -> None:
        print(f"\n{label} -- P(decode | measured BER)")
        print(f"{'BER bin':>14} {'n':>5} {'k':>5} {'P':>7} {'Wilson CI':>18}")
        for row in curve:
            print(f"{row['ber_lo']:>6.1f}-{row['ber_hi']:<6.1f} {row['n']:>5} {row['k']:>5} "
                  f"{row['p']:>6.1%}   [{row['ci_lo']:>5.1%}, {row['ci_hi']:>5.1%}]")

    print_curve("ARM A (isolated)", curve_a)
    print_curve("ARM B (co-channel, pooled deltas)", curve_b)

    trans_a = w1.transition_coverage(curve_a)
    trans_b = w1.transition_coverage(curve_b)
    short_a = [r for r in trans_a if r["n"] < 40]
    short_b = [r for r in trans_b if r["n"] < 40]
    print(f"\nSample-size target check (>=40/bin through the transition region, 0.05<P<0.95):")
    print(f"  Arm A: {len(trans_a)} transition bins, {len(short_a)} short of 40 "
          f"{[(r['ber_lo'], r['n']) for r in short_a]}")
    print(f"  Arm B: {len(trans_b)} transition bins, {len(short_b)} short of 40 "
          f"{[(r['ber_lo'], r['n']) for r in short_b]}")

    with open(os.path.join(w1.OUT_DIR, "curve_a.json"), "w") as fh:
        json.dump(curve_a, fh, indent=2)
    with open(os.path.join(w1.OUT_DIR, "curve_b.json"), "w") as fh:
        json.dump(curve_b, fh, indent=2)

    # -- Arm A vs Arm B divergence check --
    print("\n" + "=" * 78)
    print("Arm A vs Arm B divergence (same measured-BER-bin comparison)")
    print("=" * 78)
    by_bin_a = {(r["ber_lo"], r["ber_hi"]): r for r in curve_a}
    by_bin_b = {(r["ber_lo"], r["ber_hi"]): r for r in curve_b}
    common_bins = sorted(set(by_bin_a) & set(by_bin_b))
    max_abs_diff = 0.0
    for lo, hi in common_bins:
        ra, rb = by_bin_a[(lo, hi)], by_bin_b[(lo, hi)]
        diff = rb["p"] - ra["p"]
        max_abs_diff = max(max_abs_diff, abs(diff))
        print(f"  {lo:>5.1f}-{hi:<5.1f}  A={ra['p']:>6.1%} (n={ra['n']:>4})  "
              f"B={rb['p']:>6.1%} (n={rb['n']:>4})  diff={diff:+.1%}")
    print(f"  max |P_B - P_A| over shared bins = {max_abs_diff:.1%}")

    # -- E estimator against THE 135 (self-check + population reused, not re-derived) --
    print("\n" + "=" * 78)
    print("SELF-CHECK + THE 135 population (c2_phase2c_ber_measurement.py, reused not re-derived)")
    print("=" * 78)
    sys.path.insert(0, HERE)
    import c2_phase2c_ber_measurement as ber_mod

    cycles = sorted(os.path.splitext(f)[0]
                     for f in os.listdir(ber_mod.WAV68_DIR) if f.endswith(".wav"))
    encoder = ber_mod.Encoder(ber_mod.DLL_PATH)

    control = ber_mod.compute_matched_hit_control(cycles, limit=200)
    k10_cand_by_cycle = ber_mod.load_candidate_diag_with_llr(
        os.path.join(ber_mod.K10_CAP_DIR, "candidate_diag.csv"))
    control_bers = ber_mod.measure_population("matched-hit control", control, k10_cand_by_cycle,
                                               encoder, require_decoded=True)
    import statistics as st
    self_check_ok = bool(control_bers) and st.median(control_bers) < 0.05
    print(f"[SELF-CHECK {'PASS' if self_check_ok else 'FAIL'}] matched-hit control: "
          f"n={len(control_bers)} median={st.median(control_bers):.1%} "
          f"(threshold: < 5%)" if control_bers else "[SELF-CHECK FAIL] no control data")
    if not self_check_ok:
        print("[STOP] Self-check failed. E below is NOT trustworthy.")

    pop135 = ber_mod.compute_135_population(cycles)
    bers135 = ber_mod.measure_population("THE 135", pop135, k10_cand_by_cycle, encoder,
                                          require_decoded=False)
    print(f"THE 135: n measured = {len(bers135)} of {len(pop135)}")

    diverge = max_abs_diff >= 0.05  # 5 percentage points on a shared bin -- "meaningfully" diverge
    curve_for_e = curve_b if diverge else curve_a
    which = "Arm B" if diverge else "Arm A"
    print(f"\nArms {'DIVERGE' if diverge else 'agree closely'} "
          f"(max diff {max_abs_diff:.1%}) -- using {which}'s curve for E, per the pre-registered rule.")

    e_interp = sum(w1.p_decode_interp(curve_for_e, b) for b in bers135)
    e_nearest = sum(w1.p_decode_nearest(curve_for_e, b) for b in bers135)
    e_from_a = sum(w1.p_decode_interp(curve_a, b) for b in bers135)
    e_from_b = sum(w1.p_decode_interp(curve_b, b) for b in bers135)

    b50 = w1.curve_crossing(curve_for_e, 0.50)
    b10 = w1.curve_crossing(curve_for_e, 0.10)
    b90 = w1.curve_crossing(curve_for_e, 0.90)
    n_below_b50 = sum(1 for b in bers135 if b <= b50) if not (b50 != b50) else None

    print(f"\nE (interpolated, {which}) = {e_interp:.2f}")
    print(f"E (nearest-bin,   {which}) = {e_nearest:.2f}  (method-choice sensitivity check)")
    print(f"E (Arm A curve, for comparison) = {e_from_a:.2f}")
    print(f"E (Arm B curve, for comparison) = {e_from_b:.2f}")
    print(f"B10={b10:.1%} B50={b50:.1%} B90={b90:.1%}  N(BER<=B50)={n_below_b50}")

    reading = "UNKNOWN"
    if e_interp < 1:
        reading = "< 1: front-end limited (E is a LOWER bound; do not read as proof beyond "
        "'not detected by this instrument')"
    elif e_interp <= 15:
        reading = "1-15: a real but small decode-path residue"
    else:
        reading = "> 15: dropping correctable codewords at material scale -- a defect"
    print(f"\nReading-rule row: {reading}")

    summary = {
        "shim_version": native.version,
        "n_buffers_arm_a": N_BUFFERS_ARM_A, "n_buffers_arm_b": N_BUFFERS_ARM_B,
        "n_signals_arm_a_per_buffer": N_SIGNALS_ARM_A, "deltas_arm_b": DELTAS,
        "meta_a": meta_a, "meta_b": meta_b,
        "n_planted_a": len(arm_a), "n_located_a": n_loc_a,
        "n_planted_b": len(arm_b), "n_located_b": n_loc_b,
        "curve_a": curve_a, "curve_b": curve_b,
        "transition_bins_short_of_40_a": short_a, "transition_bins_short_of_40_b": short_b,
        "max_abs_diff_shared_bins": max_abs_diff, "diverge": diverge, "curve_used_for_e": which,
        "self_check_pass": self_check_ok,
        "control_n": len(control_bers), "control_median_ber": st.median(control_bers) if control_bers else None,
        "n_135_measured": len(bers135), "n_135_total": len(pop135),
        "e_interp": e_interp, "e_nearest": e_nearest, "e_from_a": e_from_a, "e_from_b": e_from_b,
        "b10": b10, "b50": b50, "b90": b90, "n_below_b50": n_below_b50,
        "bers135": bers135,
        "reading": reading,
        "wall_time_s": time.time() - t0,
    }
    with open(os.path.join(w1.OUT_DIR, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\nTotal wall time: {time.time() - t0:.1f}s")
    print(f"Raw + summary data: {w1.OUT_DIR}")


if __name__ == "__main__":
    main()
