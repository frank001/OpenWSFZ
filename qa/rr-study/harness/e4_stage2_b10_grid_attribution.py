"""E4-STAGE2 Amendment B10 (spec Sec.17.5), pre-registered 19:46Z BEFORE this
script was run: is the WIDE-grid (0h/0i calibration) vs NARROW-grid (Sec.12.6
census-normative) origin mismatch concentrated in the low rho1 tail (mis-
location contaminating exactly what phi counts), or spread evenly (real
channel variation)?

Runs on the full pre-registered >=+10dB calibration population (n~993), not
the 40-row spot check that motivated this build -- that check is disclosed
separately as what triggered the investigation, not as this test's evidence.

For every row: WIDE grid (DT_ref-0.30..+1.40) and NARROW grid (DT_ref+0.20..
+0.80, Sec.12.6 normative) origins, each with its own Costas-only sharpness;
full-message rho1 at each. Reports:
  G-a: bottom-decile (by WIDE rho1) origin-mismatch rate <= 2x top-decile rate
       -> mis-location NOT concentrated in the low tail -> P1 confirmed
  G-b: bottom > 2x top AND those rows' rho1 rises materially on the narrow grid
       -> per-row instrument failure contaminates the low tail -> phi not
          computable as specified
  G-c: otherwise -> report, do not interpret
Per Sec.17.5(ii): for every mismatched row, record which grid's Costas-only
sharpness is higher -- identifies the better origin from the data, doesn't
assume the narrow grid is "right".

NFR-021: numeric per-row output only, under artefacts/.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_QA_ROOT))
sys.path.insert(0, str(_QA_ROOT / "live-gap-now"))

from corpus import c2_cycles  # noqa: E402
from synth.wavio import read_wav  # noqa: E402
from harness.e4_stage2_census_b5 import (  # noqa: E402
    build_frame, _tones_for, locate_origin, full_message_rho1_at,
    CALIBRATION_SNR_FLOOR, SAMPLE_SEED, RHO_STAR,
    WIDE_DT_OFFSETS, WIDE_FREQ_OFFSETS, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS,
)

OUT_DIR = str(_QA_ROOT.parent / "artefacts" / "e4-stage2-b10-grid-attribution")
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    t0 = time.time()

    def log(msg):
        print(f"[{time.time()-t0:6.0f}s] {msg}", flush=True)

    cycles, dup = c2_cycles()
    wav_by_ts = dict(cycles)
    c2_dir = os.path.dirname(os.path.dirname(list(wav_by_ts.values())[0]))
    ref_path = os.path.join(c2_dir, "wsjtx-1-ft991a", "ALL.TXT")
    ref, frame_keys, lo, hi = build_frame(ref_path, cycles)

    rng = np.random.default_rng(SAMPLE_SEED)
    n = min(5000, len(frame_keys))
    idx = rng.choice(len(frame_keys), size=n, replace=False)
    idx.sort()
    sample_keys = [frame_keys[i] for i in idx]
    calib_keys = [k for k in sample_keys if ref[k][0] >= CALIBRATION_SNR_FLOOR]
    log(f"calibration population: {len(calib_keys)} rows")

    tones_cache = {}
    rows = []
    for i, (ts, msg) in enumerate(calib_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            continue
        tones = _tones_for(msg, tones_cache)
        if tones is None:
            continue
        audio, fs = read_wav(wav_path)
        loc_w = locate_origin(audio, fs, float(freq_ref), dt_ref, WIDE_DT_OFFSETS, WIDE_FREQ_OFFSETS)
        loc_n = locate_origin(audio, fs, float(freq_ref), dt_ref, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS)
        if loc_w is None or loc_n is None:
            continue
        dt_w, fr_w, p_w, sharp_w = loc_w
        dt_n, fr_n, p_n, sharp_n = loc_n
        r1_w = full_message_rho1_at(audio, fs, tones, dt_w, fr_w)
        r1_n = full_message_rho1_at(audio, fs, tones, dt_n, fr_n)
        if r1_w is None or r1_n is None:
            continue
        same = abs(dt_w - dt_n) < 1e-9 and abs(fr_w - fr_n) < 1e-9
        rows.append({
            "snr_db": snr, "rho1_wide": r1_w, "rho1_narrow": r1_n,
            "sharpness_wide": sharp_w, "sharpness_narrow": sharp_n,
            "mismatch": not same,
            "narrow_has_higher_sharpness": sharp_n > sharp_w,
        })
        if (i + 1) % 100 == 0:
            log(f"  {i + 1}/{len(calib_keys)}")

    r1_wide = np.array([r["rho1_wide"] for r in rows])
    r1_narrow = np.array([r["rho1_narrow"] for r in rows])
    mismatch = np.array([r["mismatch"] for r in rows])
    n_rows = len(rows)
    log(f"\nn={n_rows}  overall mismatch rate={mismatch.mean():.1%}")
    log(f"median rho1 wide={np.median(r1_wide):.4f}  narrow={np.median(r1_narrow):.4f}  "
        f"share<rho* wide={(r1_wide<RHO_STAR).mean():.4f}  narrow={(r1_narrow<RHO_STAR).mean():.4f}")

    # Sec.17.6(2): the load-bearing spread figure on the CORRECT (narrow, Sec.12.6) grid --
    # replaces the suspect wide-grid IQR=0.2973 from the earlier spread check.
    narrow_q25, narrow_q50, narrow_q75 = np.percentile(r1_narrow, [25, 50, 75])
    narrow_p10, narrow_p90 = np.percentile(r1_narrow, [10, 90])
    narrow_iqr = narrow_q75 - narrow_q25
    p1_like = narrow_iqr >= 0.20
    p2_like = narrow_iqr <= 0.10
    spread_reading = "P1-like" if p1_like else ("P2-like" if p2_like else "ambiguous")
    log(f"\nGRID_A (narrow, Sec.12.6) rho1_full spread -- the load-bearing figure now: "
        f"n={n_rows} median={narrow_q50:.4f} IQR={narrow_iqr:.4f} p10={narrow_p10:.4f} p90={narrow_p90:.4f} "
        f"-> {spread_reading} (bar: IQR>=0.20 P1-like, IQR<=0.10 P2-like)")

    # Decile stratification by WIDE rho1 (what ROW 0i actually measured)
    p10, p90 = np.percentile(r1_wide, [10, 90])
    bottom = r1_wide <= p10
    top = r1_wide >= p90
    bottom_mismatch_rate = mismatch[bottom].mean() if bottom.sum() else float("nan")
    top_mismatch_rate = mismatch[top].mean() if top.sum() else float("nan")
    log(f"\nbottom decile (rho1_wide<={p10:.4f}, n={bottom.sum()}): mismatch rate={bottom_mismatch_rate:.1%}")
    log(f"top decile    (rho1_wide>={p90:.4f}, n={top.sum()}): mismatch rate={top_mismatch_rate:.1%}")
    ratio = bottom_mismatch_rate / top_mismatch_rate if top_mismatch_rate > 0 else float("inf")
    log(f"bottom/top mismatch ratio = {ratio:.2f}  (G-a bar: <= 2.0)")

    # Sec.17.5(ii): among MISMATCHED rows, does narrow rho1 rise materially,
    # and which grid has higher sharpness (per-row attribution, no assumption)
    mism_rows = [r for r in rows if r["mismatch"]]
    n_mism = len(mism_rows)
    narrow_higher_sharp = sum(1 for r in mism_rows if r["narrow_has_higher_sharpness"])
    rho1_rise = np.array([r["rho1_narrow"] - r["rho1_wide"] for r in mism_rows])
    bottom_mism = [r for r, b in zip(rows, bottom) if b and r["mismatch"]]
    bottom_rise = np.array([r["rho1_narrow"] - r["rho1_wide"] for r in bottom_mism]) if bottom_mism else np.array([])
    log(f"\namong {n_mism} mismatched rows: narrow grid has higher Costas sharpness in "
        f"{narrow_higher_sharp}/{n_mism} ({narrow_higher_sharp/n_mism:.1%})" if n_mism else "no mismatches")
    log(f"median rho1 rise (narrow-wide) over ALL mismatched rows: {np.median(rho1_rise):.4f}" if n_mism else "")
    log(f"median rho1 rise over BOTTOM-DECILE mismatched rows (n={len(bottom_mism)}): "
        f"{np.median(bottom_rise):.4f}" if len(bottom_mism) else "  bottom-decile mismatched rows: none")

    material_rise_bottom = len(bottom_mism) > 0 and np.median(bottom_rise) >= 0.10  # readout quantum, disclosed

    if ratio <= 2.0:
        reading = "G-a -- mis-location NOT concentrated in the low tail. Spread is the channel. P1 confirmed, gate clears."
    elif ratio > 2.0 and material_rise_bottom:
        reading = "G-b -- per-row instrument failure contaminates the low tail. Spread contaminated; phi NOT computable as specified."
    else:
        reading = "G-c -- report, do not interpret."
    log(f"\nREADING: {reading}")

    out = {
        "n": n_rows,
        "overall_mismatch_rate": float(mismatch.mean()),
        "median_rho1_wide": float(np.median(r1_wide)), "median_rho1_narrow": float(np.median(r1_narrow)),
        "narrow_grid_spread": {
            "n": n_rows, "median": float(narrow_q50), "iqr": float(narrow_iqr),
            "p10": float(narrow_p10), "p90": float(narrow_p90), "reading": spread_reading,
        },
        "share_below_rho_star_wide": float((r1_wide < RHO_STAR).mean()),
        "share_below_rho_star_narrow": float((r1_narrow < RHO_STAR).mean()),
        "p10_wide": float(p10), "p90_wide": float(p90),
        "bottom_decile_n": int(bottom.sum()), "top_decile_n": int(top.sum()),
        "bottom_decile_mismatch_rate": float(bottom_mismatch_rate),
        "top_decile_mismatch_rate": float(top_mismatch_rate),
        "bottom_top_ratio": float(ratio),
        "n_mismatched": n_mism,
        "narrow_higher_sharpness_share": float(narrow_higher_sharp / n_mism) if n_mism else None,
        "median_rho1_rise_all_mismatched": float(np.median(rho1_rise)) if n_mism else None,
        "median_rho1_rise_bottom_decile_mismatched": float(np.median(bottom_rise)) if len(bottom_rise) else None,
        "reading": reading,
        "wall_time_s": time.time() - t0,
    }
    with open(os.path.join(OUT_DIR, "b10_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    log(f"\nWrote {OUT_DIR}/b10_result.json")


if __name__ == "__main__":
    main()
