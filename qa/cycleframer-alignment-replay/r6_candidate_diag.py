#!/usr/bin/env python3
"""D-001 R.6 diagnostic -- candidate-population comparison, real vs AWGN arm.

Follow-up to r6_level_sweep.py. That sweep showed R.6's AWGN control is 0% flat across 45 dB of
absolute level at a fixed nominal in-band SNR -- level is not the cause. After fixing
band_noise_rms_robust's ln(2) bias (handoff Sec.6), a fresh r6_clean_graft.py smoke run
(R6_N_CYCLES=6, R6_SNRS=-14,-10,-6) shows the two arms are now matched to within +0.06 dB measured
in-band SNR (SC1), yet: ours 62.5% real vs 0.0% awgn, jt9 79.2% real vs 0.0% awgn at -6 dB. All
three of the handoff's Sec.5 fallbacks (write_wav peak norm, 16-bit quantisation, amplitude-vs-SNR
convention) are now excluded: "ours" bypasses the WAV/quantisation path entirely and still reads
0% on awgn, and SC1 shows the convention IS delivering matched measured SNR.

This script checks one more candidate mechanism using instrumentation the shim already exports
(ft8_get_last_candidate_diag, used unmodified in b2_synthetic_calibration.Native.decode_all):
does flat AWGN -- being uniformly "loud" at the local target density across the ENTIRE spectrum,
vs real audio where most of the spectrum away from actual transmissions may be much quieter --
produce a much larger sync-candidate population that could crowd out or outscore the planted
signal's own candidate? Reports, per arm: total candidate count, score distribution, and whether a
candidate exists near each planted (freq, dt) at all, with its score/decoded flag.

NFR-021: Q-prefix synthetic messages only, message text never printed. ASCII-only console output
(HK-009).
"""
from __future__ import annotations

import math
import os
import random
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b2_synthetic_calibration as b2
import b1_jt9_ablation as b1
import r5_hybrid_ladder as r5
import r6_clean_graft as r6

SNR_DB = -6.0
N_CYCLES_TO_CHECK = 4


def decode_candidates_only(native: "b2.Native", pcm: np.ndarray) -> list[dict]:
    """Like b2.Native.decode_all, but does not read out LLRs and does not assert n_llr==n_cand --
    that assert fires when n_cand hits the K_MAX_CANDIDATES cap (140) in this diagnostic (the
    shim's LLR-capture buffer appears not to size-match at the cap); candidate freq/dt/score/
    decoded is all this script needs."""
    import ctypes
    assert pcm.shape == (b2.BUFFER_SAMPLES,)
    pcm_c = (ctypes.c_float * b2.BUFFER_SAMPLES)(*pcm.astype(np.float32))
    results = (native.FT8Result * 200)()
    n = native.dll.ft8_decode_all(pcm_c, b2.BUFFER_SAMPLES, results, 200)
    if n < 0:
        print(f"  [WARN] ft8_decode_all returned {n}", file=sys.stderr)

    cap = b2.K_MAX_CANDIDATES
    out_freq = (ctypes.c_float * cap)()
    out_dt = (ctypes.c_float * cap)()
    out_score = (ctypes.c_int16 * cap)()
    out_decoded = (ctypes.c_uint8 * cap)()
    out_prenorm = (ctypes.c_float * cap)()
    out_postnorm = (ctypes.c_float * cap)()
    n_cand = native.dll.ft8_get_last_candidate_diag(out_freq, out_dt, out_score, out_decoded,
                                                     out_prenorm, out_postnorm, cap)
    return [{"freq_hz": out_freq[i], "dt": out_dt[i], "score": out_score[i],
             "decoded": bool(out_decoded[i])} for i in range(n_cand)]


def describe(label: str, cands: list[dict], planted: list[dict]) -> None:
    scores = [c["score"] for c in cands]
    print(f"  {label}: n_candidates={len(cands)}"
          + (f"  score min/mean/max={min(scores)}/{np.mean(scores):.1f}/{max(scores)}"
             if scores else "  (no candidates)"))
    for p in planted:
        best = b2.nearest_candidate(p["freq"], p["dt"], cands)
        if best is None:
            print(f"    planted @ {p['freq']:.1f}Hz dt={p['dt']:.2f}: NO candidate within "
                  f"tolerance (freq_tol={b2.FREQ_TOL_HZ}, dt_tol={b2.DT_TOL_S})")
        else:
            print(f"    planted @ {p['freq']:.1f}Hz dt={p['dt']:.2f}: nearest candidate "
                  f"freq={best['freq_hz']:.1f} dt={best['dt']:.2f} score={best['score']} "
                  f"decoded={best['decoded']}")


def main() -> int:
    rng_py = random.Random(r6.SEED)
    rng_np = np.random.default_rng(r6.SEED)

    print(f"Loading DLL: {b2.DLL_PATH}")
    native = b2.Native(b2.DLL_PATH)

    rows = list(b1.parse_all_txt(b1.WSJTX_ALL_TXT))
    by_cycle: dict[str, list[dict]] = {}
    for r in rows:
        by_cycle.setdefault(r["ts"], []).append(r)
    wav_names = sorted(os.path.splitext(f)[0] for f in os.listdir(r6.WSJTX_WAV68)
                        if f.endswith(".wav"))
    cyc = [t for t in wav_names if t in by_cycle][:N_CYCLES_TO_CHECK]

    for ts in cyc:
        real_pcm = r5.read_real_wav_float(os.path.join(r6.WSJTX_WAV68, ts + ".wav"))
        real_freqs = [float(r["freq"]) for r in by_cycle[ts]]
        gaps = r6.find_gaps(real_freqs, r6.MAX_GRAFTS)
        if not gaps:
            continue
        real_buf, awgn_buf, awgn_bg, recs = r6.build_pair(
            native, rng_py, rng_np, real_pcm, gaps, SNR_DB)

        planted = [{"freq": rec["freq"], "dt": r6.PLANT_DT} for rec in recs]

        print(f"\n=== {ts} -- {len(gaps)} grafts @ SNR={SNR_DB:+.0f} dB ===")
        cands_real = decode_candidates_only(native, real_buf)
        cands_awgn = decode_candidates_only(native, awgn_buf)
        cands_awgn_bg = decode_candidates_only(native, awgn_bg)  # noise-only: baseline flood check
        describe("REAL", cands_real, planted)
        describe("AWGN", cands_awgn, planted)
        print(f"  AWGN (noise-only background, no grafts): n_candidates={len(cands_awgn_bg)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
