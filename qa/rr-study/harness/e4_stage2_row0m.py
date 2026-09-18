"""E4-STAGE2 Amendment B15 (spec Sec.21.1/19.4), ROW 0m -- is GRID_A's (Sec.12.6,
the census-normative narrow grid) own low tail real, or is even the correct
grid location-limited at the bottom?

Wide-vs-narrow (B10/B13) showed the WIDE grid mis-locates and that mis-location
concentrates in its low tail. It did NOT show the NARROW grid is trustworthy at
ITS OWN low tail -- ROW 0h's sharpness was measured on the wide grid by design.
This row closes that gap before phi is computed.

On GRID_A only: stratify rho1_full by decile, report (a) median Costas
sharpness and (b) edge-pinning rate (best origin within one grid step of
DT_ref+0.20 or DT_ref+0.80) for the bottom vs top decile.

  H1: bottom-decile median sharpness >= 0.7x top-decile's
      AND bottom-decile edge-pinning rate <= 0.10
      -> low-rho1 rows are confidently located -> phi computable
  H2: either fails -> narrow grid's low tail is also location-limited

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
    CALIBRATION_SNR_FLOOR, SAMPLE_SEED, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS,
)

OUT_DIR = str(_QA_ROOT.parent.parent / "artefacts" / "e4-stage2-row0m")  # repo root, fixed path bug
os.makedirs(OUT_DIR, exist_ok=True)

EDGE_MARGIN_S = 0.01  # one grid step, disclosed: "within one step of the boundary"
GRID_LO_OFFSET = float(NARROW_DT_OFFSETS[0])   # 0.20
GRID_HI_OFFSET = float(NARROW_DT_OFFSETS[-1])  # 0.80


def is_pinned(dt_off: float) -> bool:
    return (dt_off <= GRID_LO_OFFSET + EDGE_MARGIN_S) or (dt_off >= GRID_HI_OFFSET - EDGE_MARGIN_S)


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
    log(f"calibration population: {len(calib_keys)} rows, GRID_A (0.20-0.80) only")

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
        loc = locate_origin(audio, fs, float(freq_ref), dt_ref, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS)
        if loc is None:
            continue
        dt_star, freq_star, best_p, sharp = loc
        r1 = full_message_rho1_at(audio, fs, tones, dt_star, freq_star)
        if r1 is None:
            continue
        dt_off = dt_star - dt_ref
        rows.append({"snr_db": snr, "rho1_full": r1, "sharpness": sharp,
                     "dt_off": dt_off, "pinned": is_pinned(dt_off)})
        if (i + 1) % 100 == 0:
            log(f"  {i + 1}/{len(calib_keys)}")

    r1 = np.array([r["rho1_full"] for r in rows])
    sharp = np.array([r["sharpness"] for r in rows])
    pinned = np.array([r["pinned"] for r in rows])
    n_rows = len(rows)
    log(f"\nn={n_rows}")

    p10, p90 = np.percentile(r1, [10, 90])
    bottom = r1 <= p10
    top = r1 >= p90
    med_sharp_bottom = float(np.median(sharp[bottom]))
    med_sharp_top = float(np.median(sharp[top]))
    pin_rate_bottom = float(pinned[bottom].mean())
    pin_rate_top = float(pinned[top].mean())
    sharp_ratio = med_sharp_bottom / med_sharp_top if med_sharp_top > 0 else float("nan")

    log(f"bottom decile (rho1<={p10:.4f}, n={bottom.sum()}): median sharpness={med_sharp_bottom:.2f} "
        f"pinning_rate={pin_rate_bottom:.3f}")
    log(f"top decile    (rho1>={p90:.4f}, n={top.sum()}): median sharpness={med_sharp_top:.2f} "
        f"pinning_rate={pin_rate_top:.3f}")
    log(f"sharpness ratio (bottom/top) = {sharp_ratio:.3f}  (H1 bar: >= 0.7)")
    log(f"bottom-decile pinning rate = {pin_rate_bottom:.3f}  (H1 bar: <= 0.10)")

    h1 = (sharp_ratio >= 0.7) and (pin_rate_bottom <= 0.10)
    reading = "H1 -- low-rho1 rows confidently located; phi computable" if h1 else \
              "H2 -- narrow grid's low tail is also location-limited; phi NOT computable as specified"
    log(f"\nREADING: {reading}")

    out = {
        "n": n_rows, "p10_rho1": float(p10), "p90_rho1": float(p90),
        "bottom_decile_n": int(bottom.sum()), "top_decile_n": int(top.sum()),
        "bottom_median_sharpness": med_sharp_bottom, "top_median_sharpness": med_sharp_top,
        "sharpness_ratio": sharp_ratio,
        "bottom_pinning_rate": pin_rate_bottom, "top_pinning_rate": pin_rate_top,
        "h1": h1, "reading": reading,
        "wall_time_s": time.time() - t0,
    }
    with open(os.path.join(OUT_DIR, "row0m_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    log(f"Wrote {OUT_DIR}/row0m_result.json")


if __name__ == "__main__":
    main()
