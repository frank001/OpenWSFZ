"""E4-STAGE2 Amendment B15 (spec Sec.21.2), phi computation -- CONDITIONAL on
ROW 0m returning H1, on GRID_A ONLY.

Reuses the already-established results rather than re-deriving them: ROW 0h
PASS (n=992, wide-grid locatability -- unaffected by the grid defect, per B12/
B13/B14) and ROW 0i PASS on the CORRECT grid (n=849-855 across independent
re-runs, median ~0.886, well above rho*=0.577's 0.80 bar) are both already
confirmed by three independent passes (Item 1(a), B10's wide-vs-narrow test,
the narrow-only spread check). This script does NOT re-run that gate; it runs
ONLY if this session's own record shows 0m returned H1 (checked in main()
before any computation, refuses to proceed otherwise -- HK-025/mechanical
gate, not a formality).

Binding conditions (spec Sec.21.2), applied literally:
  - GRID_A = [DT_ref+0.20, DT_ref+0.80], Costas-only location, full-message
    rho1 (Sec.12.6). Nothing else.
  - rho* = 0.577, unchanged, no re-referencing.
  - 0j' = J1 -> NO band. phi over re-encodable rows only, CI widened by using
    n_kept (not the full 5000) in the Wilson interval -- no other adjustment.
  - BAR5 = 0.25, BAR10 = 0.05, BOTH read off the SAME single phi_upper(>=5Hz)
    measurement (B3 Sec.10.3). E1: 95% upper < BAR10. E2: BAR10 <= upper <
    BAR5. E3: otherwise.
  - Required reporting (Sec.21.3): phi stratified by SNR band as well as
    pooled. Does not gate anything.

NFR-021: ts/snr/dt/freq/rho1/hit only, numeric, under artefacts/.
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
    SAMPLE_SEED, RHO_STAR, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS,
    wilson_upper_95, wilson_lower_95,
)

OUT_DIR = str(_QA_ROOT.parent.parent / "artefacts" / "e4-stage2-phi")
os.makedirs(OUT_DIR, exist_ok=True)

BAR_10 = 0.05
BAR_5 = 0.25

SNR_BANDS = [(-10, -1), (0, 4), (5, 9), (10, 14), (15, 19), (20, 200)]


def require_h1_confirmed():
    """Mechanical gate, not a formality (HK-025): refuses to compute phi unless
    this session's own ROW 0m result file says H1."""
    p = os.path.join(str(_QA_ROOT.parent.parent / "artefacts" / "e4-stage2-row0m"), "row0m_result.json")
    if not os.path.exists(p):
        raise SystemExit(f"REFUSED: ROW 0m result not found at {p}. phi is authorised ONLY on an H1.")
    with open(p, encoding="utf-8") as f:
        r0m = json.load(f)
    if not r0m.get("h1"):
        raise SystemExit(f"REFUSED: ROW 0m did not return H1 ({r0m.get('reading')}). "
                          f"phi is NOT authorised per spec Sec.21.1.")
    return r0m


def main():
    r0m = require_h1_confirmed()
    t0 = time.time()

    def log(msg):
        print(f"[{time.time()-t0:6.0f}s] {msg}", flush=True)

    log(f"ROW 0m confirmed H1 (n={r0m['n']}, sharpness_ratio={r0m['sharpness_ratio']:.3f}, "
        f"bottom_pinning={r0m['bottom_pinning_rate']:.3f}). Proceeding to phi on GRID_A.")

    cycles, dup = c2_cycles()
    wav_by_ts = dict(cycles)
    c2_dir = os.path.dirname(os.path.dirname(list(wav_by_ts.values())[0]))
    ref_path = os.path.join(c2_dir, "wsjtx-1-ft991a", "ALL.TXT")
    ref, frame_keys, lo, hi = build_frame(ref_path, cycles)
    log(f"frame: {len(frame_keys)} rows (spec expects 60,239)")

    rng = np.random.default_rng(SAMPLE_SEED)
    n = min(5000, len(frame_keys))
    idx = rng.choice(len(frame_keys), size=n, replace=False)
    idx.sort()
    sample_keys = [frame_keys[i] for i in idx]
    log(f"pre-registered sample: {len(sample_keys)} rows (seed {SAMPLE_SEED})")

    tones_cache = {}
    rows_out = []
    n_dropped = 0
    n_wav_missing = 0
    for i, (ts, msg) in enumerate(sample_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        tones = _tones_for(msg, tones_cache)
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            n_wav_missing += 1
            rows_out.append({"snr_db": snr, "re_encodable": tones is not None, "rho1": None})
            continue
        if tones is None:
            n_dropped += 1
            rows_out.append({"snr_db": snr, "re_encodable": False, "rho1": None})
            continue
        audio, fs = read_wav(wav_path)
        loc = locate_origin(audio, fs, float(freq_ref), dt_ref, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS)
        if loc is None:
            n_dropped += 1
            rows_out.append({"snr_db": snr, "re_encodable": False, "rho1": None,
                              "extract_error": "origin_not_locatable"})
            continue
        dt_star, freq_star, _, _ = loc
        r1 = full_message_rho1_at(audio, fs, tones, dt_star, freq_star)
        if r1 is None:
            n_dropped += 1
            rows_out.append({"snr_db": snr, "re_encodable": False, "rho1": None,
                              "extract_error": "extract_failed"})
            continue
        rows_out.append({"snr_db": snr, "re_encodable": True, "rho1": r1})
        if (i + 1) % 250 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(sample_keys) - (i + 1)) / rate if rate > 0 else float("nan")
            log(f"  {i + 1}/{len(sample_keys)}  eta={eta:.0f}s  dropped={n_dropped} wav_missing={n_wav_missing}")
            with open(os.path.join(OUT_DIR, "phi_sample_rows.partial.json"), "w", encoding="utf-8") as f:
                json.dump({"n_done": i + 1, "rows": rows_out}, f)

    dropped_share = n_dropped / len(sample_keys)
    log(f"\ndropped (not re-encodable/extract error): {n_dropped} ({dropped_share:.4%}) of "
        f"{len(sample_keys)}. wav_missing={n_wav_missing}. (0j'=J1 -> reported, NOT banded)")

    valid = [r for r in rows_out if r.get("re_encodable") and r.get("rho1") is not None]
    n_valid = len(valid)
    k_below = sum(1 for r in valid if r["rho1"] < RHO_STAR)
    phi_upper = k_below / n_valid if n_valid else float("nan")
    ci_lo = wilson_lower_95(k_below, n_valid)
    ci_hi = wilson_upper_95(k_below, n_valid)

    if ci_hi < BAR_10:
        reading = "E1 -- FADE CLOSES ENTIRELY."
    elif ci_hi < BAR_5:
        reading = "E2 -- the 5Hz effect closes; the 10Hz one does not."
    else:
        reading = "E3 -- UNRESOLVED. Per Sec.20.3/21.4: this is NOT evidence fading is a large contributor."

    log(f"\nPOOLED phi_upper = {phi_upper:.4f} (k={k_below}/{n_valid}), 95% CI [{ci_lo:.4f}, {ci_hi:.4f}]")
    log(f"BAR10={BAR_10}  BAR5={BAR_5}")
    log(f"READING: {reading}")

    band_results = {}
    log("\nphi STRATIFIED BY SNR BAND (Sec.21.3, reporting only, gates nothing):")
    for lo_b, hi_b in SNR_BANDS:
        band_rows = [r for r in valid if lo_b <= r["snr_db"] <= hi_b]
        nb = len(band_rows)
        if nb == 0:
            log(f"  [{lo_b:>4},{hi_b:>4}] dB: n=0")
            continue
        kb = sum(1 for r in band_rows if r["rho1"] < RHO_STAR)
        phib = kb / nb
        blo, bhi = wilson_lower_95(kb, nb), wilson_upper_95(kb, nb)
        band_results[f"{lo_b}_{hi_b}"] = {"n": nb, "k": kb, "phi_upper": phib, "ci95": [blo, bhi]}
        log(f"  [{lo_b:>4},{hi_b:>4}] dB: n={nb:>5}  phi_upper={phib:.4f}  95% CI=[{blo:.4f},{bhi:.4f}]")

    summary = {
        "row0m_h1_confirmed": True, "row0m_result": r0m,
        "n_sample": len(sample_keys), "n_dropped": n_dropped, "dropped_share": dropped_share,
        "n_wav_missing": n_wav_missing, "n_valid": n_valid,
        "rho_star": RHO_STAR, "bar_10": BAR_10, "bar_5": BAR_5,
        "phi_upper_pooled": phi_upper, "k_below_rho_star": k_below, "ci95_pooled": [ci_lo, ci_hi],
        "reading": reading,
        "phi_by_snr_band": band_results,
        "wall_time_s": time.time() - t0,
    }
    with open(os.path.join(OUT_DIR, "phi_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(OUT_DIR, "phi_sample_rows.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows_out}, f)
    partial = os.path.join(OUT_DIR, "phi_sample_rows.partial.json")
    if os.path.exists(partial):
        os.remove(partial)
    log(f"\nDone in {summary['wall_time_s']:.0f}s. Wrote phi_summary.json and phi_sample_rows.json "
        f"under {OUT_DIR}")


if __name__ == "__main__":
    main()
