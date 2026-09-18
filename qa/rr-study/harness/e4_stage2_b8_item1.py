"""E4-STAGE2 Amendment B8 (spec Sec.15.5/15.6), Item 1 -- one pass on the existing
sample, nearly free:

  (a) Sec.13.5 grid width: 0.20-0.80 (census normative, Sec.12.6) vs 0.40-0.60
      (b5_04's own grid) on the SAME 0i calibration rows -- does grid width
      explain (any of) the 0.7537-vs-0.793 gap?
  (b) ROW 0j' (spec Sec.14, B7): dropped vs kept rows' COSTAS-ONLY rho1 (message-
      independent, computable on all 5000 sampled rows including the 538 that
      don't re-encode). J1 = missing-at-random (medians AND share-below-rho*
      both within 0.05) -> no band, widen CI only. J2 = either exceeds 0.05 ->
      band stands, E1 unreachable regardless. J3 = unavailable -> stop.

Both reuse the pre-registered seed-20260916 sample and frame unchanged (no new
selection). NFR-021: numeric fields only, all output under artefacts/.
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
    build_frame, load_all_txt, _tones_for, locate_origin, full_message_rho1_at,
    CALIBRATION_SNR_FLOOR, SAMPLE_SEED, RHO_STAR, COSTAS_IDX, _COSTAS_TONES,
)
from synth.estimator import rho1 as rho1_fn  # noqa: E402
from synth.constants import NUM_SYMBOLS, SYMBOL_PERIOD_S  # noqa: E402
from synth.modulator import instantaneous_phase  # noqa: E402

OUT_DIR = str(_QA_ROOT.parent / "artefacts" / "e4-stage2-b8-item1")
os.makedirs(OUT_DIR, exist_ok=True)

# Sec.13.5's two widths, same freq range both times (only the DT range differs --
# that is the variable under test).
GRID_A_DT = np.arange(0.20, 0.8001, 0.01)   # census normative (Sec.12.6)
GRID_B_DT = np.arange(0.40, 0.6001, 0.01)   # b5_04's own grid
FREQ_OFFSETS = np.arange(-2.0, 2.001, 0.25)


def costas_only_rho1_at(audio, fs, dt_star, freq_star):
    """Message-independent rho1 computed from the Costas symbols only (3 blocks
    of 7, lag-1 pairs within each block -- same statistic as b5_04's costas_rho1,
    reused here so dropped (non-re-encodable) rows can still be scored."""
    sps = int(round(SYMBOL_PERIOD_S * fs))
    n_tx = NUM_SYMBOLS * sps
    audio = np.asarray(audio, dtype=np.float64)
    phase_ref = instantaneous_phase(list(_COSTAS_TONES), freq_star, fs)
    z_ref = np.exp(1j * phase_ref)
    start = int(round(dt_star * fs))
    seg = audio[start:start + n_tx]
    if len(seg) < n_tx:
        return None
    mixed = seg * np.conj(z_ref)
    g = 2.0 * mixed.reshape(NUM_SYMBOLS, sps).mean(axis=1)
    BLOCKS = [COSTAS_IDX[i:i + 7] for i in range(0, 21, 7)]
    num = 0j
    den = 0.0
    for b in BLOCKS:
        gg = g[b]
        num += np.sum(gg[1:] * np.conj(gg[:-1]))
        den += np.sum(np.abs(gg) ** 2)
    return float(abs(num) / den) if den > 0 else None


def main():
    t0 = time.time()
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
    print(f"sample={len(sample_keys)} calib(>= {CALIBRATION_SNR_FLOOR}dB)={len(calib_keys)}", flush=True)

    # ---------------- (a) grid width, same rows, both grids ------------------
    tones_cache = {}
    rows_a = []
    for i, (ts, msg) in enumerate(calib_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            continue
        tones = _tones_for(msg, tones_cache)
        if tones is None:
            continue
        audio, fs = read_wav(wav_path)
        loc_a = locate_origin(audio, fs, float(freq_ref), dt_ref, GRID_A_DT, FREQ_OFFSETS)
        loc_b = locate_origin(audio, fs, float(freq_ref), dt_ref, GRID_B_DT, FREQ_OFFSETS)
        if loc_a is None or loc_b is None:
            continue
        r1_a = full_message_rho1_at(audio, fs, tones, loc_a[0], loc_a[1])
        r1_b = full_message_rho1_at(audio, fs, tones, loc_b[0], loc_b[1])
        rows_a.append({"snr_db": snr, "rho1_wide020_080": r1_a, "rho1_narrow040_060": r1_b,
                        "same_origin": (abs(loc_a[0] - loc_b[0]) < 1e-9 and abs(loc_a[1] - loc_b[1]) < 1e-9)})
        if (i + 1) % 100 == 0:
            print(f"  (a) {i + 1}/{len(calib_keys)}  {time.time() - t0:.0f}s", flush=True)

    a_wide = np.array([r["rho1_wide020_080"] for r in rows_a])
    a_narrow = np.array([r["rho1_narrow040_060"] for r in rows_a])
    n_same = sum(1 for r in rows_a if r["same_origin"])
    print(f"\n(a) grid width: n={len(rows_a)}  same-origin-both-grids={n_same} "
          f"({n_same/len(rows_a):.1%})", flush=True)
    print(f"    median rho1 [0.20-0.80]={np.median(a_wide):.4f}   "
          f"median rho1 [0.40-0.60]={np.median(a_narrow):.4f}   "
          f"gap recovered by narrowing={np.median(a_narrow)-np.median(a_wide):+.4f}", flush=True)

    # ---------------- (b) ROW 0j': dropped vs kept, Costas-only rho1 ---------
    dropped_r1 = []
    kept_r1 = []
    for i, (ts, msg) in enumerate(sample_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            continue
        audio, fs = read_wav(wav_path)
        loc = locate_origin(audio, fs, float(freq_ref), dt_ref, GRID_A_DT, FREQ_OFFSETS)
        if loc is None:
            continue
        rc = costas_only_rho1_at(audio, fs, loc[0], loc[1])
        if rc is None:
            continue
        tones = _tones_for(msg, tones_cache)
        (dropped_r1 if tones is None else kept_r1).append(rc)
        if (i + 1) % 500 == 0:
            print(f"  (b) {i + 1}/{len(sample_keys)}  {time.time() - t0:.0f}s "
                  f"dropped_so_far={len(dropped_r1)} kept_so_far={len(kept_r1)}", flush=True)

    dropped_r1 = np.array(dropped_r1)
    kept_r1 = np.array(kept_r1)
    med_drop, med_keep = np.median(dropped_r1), np.median(kept_r1)
    share_drop = float((dropped_r1 < RHO_STAR).mean())
    share_keep = float((kept_r1 < RHO_STAR).mean())
    d_median = abs(med_drop - med_keep)
    d_share = abs(share_drop - share_keep)
    print(f"\n(b) ROW 0j': dropped n={len(dropped_r1)} median={med_drop:.4f} share<rho*={share_drop:.4f} | "
          f"kept n={len(kept_r1)} median={med_keep:.4f} share<rho*={share_keep:.4f}", flush=True)
    print(f"    |median diff|={d_median:.4f}  |share diff|={d_share:.4f}  (bar 0.05 each)", flush=True)
    if len(dropped_r1) == 0 or len(kept_r1) == 0:
        j_reading = "J3"
    elif d_median <= 0.05 and d_share <= 0.05:
        j_reading = "J1"
    else:
        j_reading = "J2"
    print(f"    READING: {j_reading}", flush=True)

    out = {
        "grid_width": {
            "n": len(rows_a), "n_same_origin": n_same,
            "median_rho1_wide_0.20_0.80": float(np.median(a_wide)),
            "median_rho1_narrow_0.40_0.60": float(np.median(a_narrow)),
            "gap_recovered": float(np.median(a_narrow) - np.median(a_wide)),
        },
        "row_0j_prime": {
            "n_dropped": int(len(dropped_r1)), "n_kept": int(len(kept_r1)),
            "median_dropped": float(med_drop), "median_kept": float(med_keep),
            "share_below_rho_star_dropped": share_drop, "share_below_rho_star_kept": share_keep,
            "median_diff": float(d_median), "share_diff": float(d_share),
            "reading": j_reading,
        },
        "wall_time_s": time.time() - t0,
    }
    with open(os.path.join(OUT_DIR, "b8_item1_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nDone in {out['wall_time_s']:.0f}s. Wrote {OUT_DIR}/b8_item1_result.json", flush=True)


if __name__ == "__main__":
    main()
