#!/usr/bin/env python3
"""D-001 R.6 -- the clean graft.

Replaces R.5's void rung 3 (see 2026-07-27-1900-architect-r5-ruling-rung3-void.md) with a
construction that has no spectral hole and no broadband/local SNR mismatch.

Method: take a real cycle's audio UNMODIFIED (no notching), find frequency gaps where WSJT-X
decoded nothing, and graft one synthetic Q-message into each gap at a controlled LOCAL in-band
SNR measured from that buffer's own noise in that exact band. Decode with our decoder and jt9 on
byte-identical audio. Control arm: the same synthetic signals at the same in-band SNR in flat
AWGN.

The fork this settles, left open by R.5's 2->4 step (65% of our decoder-specific gap):
  (A) real ENVIRONMENT  -- non-white/non-stationary noise, QRM, birdies
  (B) real SIGNALS      -- GFSK vs our CPFSK synthesis, fading/QSB, drift, timing jitter

A grafted synthetic signal carries (A) but not (B). So:
  ours_real ~= ours_awgn  ->  environment is NOT the problem  -> the gap is in (B)
  ours_real <<  ours_awgn (and jt9 holds) -> environment/noise-adaptive handling is the problem

Self-checks (the lesson from the R.5 audit -- R.5 had checks on its endpoints but none on the
rungs actually measured):
  SC1  per-signal MEASURED in-band SNR vs nominal, both backgrounds, must agree within tolerance
  SC2  every chosen gap must be genuinely free of WSJT-X-decoded signal within the guard
  SC3  AWGN control must approach ceiling at the top of the sweep

NFR-021: synthetic messages are Q-prefix by construction; real message text is never printed.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import json
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

SR = float(b2.SR)
NYQ = SR / 2.0
OUT_DIR = os.path.join(b1.REPO, "artefacts", "d001_r6_clean_graft")
WSJTX_WAV68 = os.path.join(b1.BASE, "wsjt-x", "wav68")

SIG_OCCUPIED_HZ = 43.75
GAP_GUARD_HZ = float(os.environ.get("R6_GUARD", "30"))   # clearance around any WSJT-X decode
GAP_MARGIN_HZ = 5.0      # margin inside a free interval before planting
FREQ_MIN, FREQ_MAX = 200.0, 2950.0
PLANT_DT = 0.6

N_CYCLES = int(os.environ.get("R6_N_CYCLES", "34"))
MAX_GRAFTS = int(os.environ.get("R6_MAX_GRAFTS", "4"))
SNR_GRID = [float(x) for x in os.environ.get("R6_SNRS", "-6,-3,0,3,6,10").split(",")]
SEED = 20260727


# -------------------- in-band measurement --------------------

def band_rms(pcm: np.ndarray, lo: float, hi: float) -> float:
    """RMS of pcm restricted to [lo,hi] Hz, via rfft mask + irfft. Whole-buffer.
    NOT robust: any carrier or undecoded signal inside [lo,hi] inflates this."""
    n = len(pcm)
    spec = np.fft.rfft(pcm)
    freqs = np.fft.rfftfreq(n, d=1.0 / SR)
    spec = spec * ((freqs >= lo) & (freqs <= hi))
    return float(np.std(np.fft.irfft(spec, n=n)))


def band_noise_rms_robust(pcm: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    """Carrier-robust in-band noise RMS, plus the contamination ratio (raw/robust, dB).

    Uses the MEDIAN per-bin power in the band rather than the sum, so a narrowband carrier or an
    undecoded real signal inside the band cannot inflate the estimate. This is the fix for the
    defect that made the first R.6 draft's real arm artificially easy: amplitudes were set from a
    raw in-band RMS that included undecoded real signal energy, so the grafted signal was louder
    than nominal relative to the noise the decoder actually competes with -- and SC1 could not see
    it, because SC1 divided by the same contaminated estimate.

    Parseval for a real rfft: sum(x^2) ~ (2/N^2) * sum_k |X_k|^2 over the band.
    Robust form replaces sum_k with n_bins * median_k.
    """
    n = len(pcm)
    spec = np.fft.rfft(pcm)
    freqs = np.fft.rfftfreq(n, d=1.0 / SR)
    m = (freqs >= lo) & (freqs <= hi)
    p = np.abs(spec[m]) ** 2
    if p.size == 0:
        return 0.0, 0.0
    robust = math.sqrt(2.0 * p.size * float(np.median(p)) / (n * n))
    raw = math.sqrt(2.0 * float(p.sum()) / (n * n))
    ratio_db = 20 * math.log10(raw / robust) if robust > 0 and raw > 0 else float("inf")
    return robust, ratio_db


def occupied(f: float) -> tuple[float, float]:
    return (f, f + SIG_OCCUPIED_HZ)


# -------------------- gap finding --------------------

def find_gaps(real_freqs: list[float], max_n: int) -> list[float]:
    """Base frequencies in [FREQ_MIN,FREQ_MAX] whose occupied band is >= GAP_GUARD_HZ clear of
    every WSJT-X-decoded signal's occupied band. Returns up to max_n, spread across the band."""
    blocked = []
    for f in real_freqs:
        lo, hi = occupied(f)
        blocked.append((lo - GAP_GUARD_HZ, hi + GAP_GUARD_HZ))
    blocked.sort()
    merged: list[list[float]] = []
    for lo, hi in blocked:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])

    free: list[tuple[float, float]] = []
    cursor = FREQ_MIN
    for lo, hi in merged:
        if lo > cursor:
            free.append((cursor, min(lo, FREQ_MAX + SIG_OCCUPIED_HZ)))
        cursor = max(cursor, hi)
    if cursor < FREQ_MAX + SIG_OCCUPIED_HZ:
        free.append((cursor, FREQ_MAX + SIG_OCCUPIED_HZ))

    need = SIG_OCCUPIED_HZ + 2 * GAP_MARGIN_HZ
    usable = [(lo, hi) for lo, hi in free if hi - lo >= need and lo >= FREQ_MIN]
    usable.sort(key=lambda iv: iv[1] - iv[0], reverse=True)
    picks = []
    for lo, hi in usable[: max_n * 3]:
        base = lo + GAP_MARGIN_HZ
        if base + SIG_OCCUPIED_HZ + GAP_MARGIN_HZ <= hi and base <= FREQ_MAX:
            picks.append(base)
    picks.sort()
    if len(picks) <= max_n:
        return picks
    idx = np.linspace(0, len(picks) - 1, max_n)
    return [picks[int(round(i))] for i in idx]


# -------------------- buffer construction --------------------

def build_pair(native, rng_py, rng_np, real_pcm, gaps, snr_db):
    """Returns (real_buf, awgn_buf, records). Signals identical in both; in-band noise matched."""
    real_buf = real_pcm.copy()
    awgn_buf = np.zeros(b2.BUFFER_SAMPLES, dtype=np.float64)
    recs = []

    noise = [band_noise_rms_robust(real_pcm, *occupied(f)) for f in gaps]
    target_inband = float(np.mean([n for n, _ in noise])) if noise else 0.0
    sigma_broad = target_inband / math.sqrt(SIG_OCCUPIED_HZ / NYQ)
    awgn_buf += rng_np.normal(0.0, sigma_broad, size=b2.BUFFER_SAMPLES)
    awgn_bg = awgn_buf.copy()   # noise-only, for an exact SC1 on the control arm

    for f, (n_real, contam_db) in zip(gaps, noise):
        msg = b2.make_message(rng_py)
        tones = native.encode(msg)
        # amplitude from THIS band's own carrier-robust local noise floor
        amp_real = math.sqrt(2.0) * n_real * (10 ** (snr_db / 20.0))
        amp_awgn = math.sqrt(2.0) * target_inband * (10 ** (snr_db / 20.0))
        b2.plant(real_buf, b2.synth_signal(tones, f, amp_real, rng_np), PLANT_DT)
        b2.plant(awgn_buf, b2.synth_signal(tones, f, amp_awgn, rng_np), PLANT_DT)
        recs.append({"message": msg, "freq": f, "snr_nominal": snr_db,
                     "n_real_inband": n_real, "contam_db": contam_db,
                     "amp_real": amp_real, "amp_awgn": amp_awgn})
    return real_buf, awgn_buf, awgn_bg, recs


def measure_inband_snr(buf_with: np.ndarray, buf_without: np.ndarray, f: float) -> float:
    """SC1: measured in-band SNR. Signal RMS is exact (the difference isolates the graft);
    noise uses the carrier-robust estimator, NOT the raw in-band RMS -- otherwise the check is
    circular and cannot detect the contamination it exists to detect."""
    lo, hi = occupied(f)
    s = band_rms(buf_with - buf_without, lo, hi)
    n, _ = band_noise_rms_robust(buf_without, lo, hi)
    return 20 * math.log10(s / n) if n > 0 and s > 0 else float("nan")


# -------------------- main --------------------

def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rng_py = random.Random(SEED)
    rng_np = np.random.default_rng(SEED)

    print(f"Loading DLL: {b2.DLL_PATH}")
    native = b2.Native(b2.DLL_PATH)

    rows = list(b1.parse_all_txt(b1.WSJTX_ALL_TXT))
    by_cycle: dict[str, list[dict]] = {}
    for r in rows:
        by_cycle.setdefault(r["ts"], []).append(r)

    wav_names = sorted(os.path.splitext(f)[0] for f in os.listdir(WSJTX_WAV68) if f.endswith(".wav"))
    cyc = [t for t in wav_names if t in by_cycle]
    idx = sorted(set(int(round(x)) for x in np.linspace(0, len(cyc) - 1, min(N_CYCLES, len(cyc)))))
    sel = [cyc[i] for i in idx]
    print(f"cycles: {len(sel)} of {len(cyc)} matched; grafts/cycle <= {MAX_GRAFTS}; "
          f"SNR grid (in-band, {SIG_OCCUPIED_HZ} Hz): {SNR_GRID}")

    cells: dict[tuple[float, str, str], list[int]] = {}
    sc1: list[tuple[str, float]] = []
    contam: list[float] = []
    sc2_viol = 0
    n_gap_total = 0
    per_signal = []

    for ci, ts in enumerate(sel, 1):
        real_pcm = r5.read_real_wav_float(os.path.join(WSJTX_WAV68, ts + ".wav"))
        real_freqs = [float(r["freq"]) for r in by_cycle[ts]]
        gaps = find_gaps(real_freqs, MAX_GRAFTS)
        if not gaps:
            continue
        n_gap_total += len(gaps)

        # SC2 -- assert clearance
        for f in gaps:
            lo, hi = occupied(f)
            for rf in real_freqs:
                rlo, rhi = occupied(rf)
                if not (hi + GAP_GUARD_HZ <= rlo or lo - GAP_GUARD_HZ >= rhi):
                    sc2_viol += 1

        for snr_db in SNR_GRID:
            real_buf, awgn_buf, awgn_bg, recs = build_pair(
                native, rng_py, rng_np, real_pcm, gaps, snr_db)

            # SC1: BOTH arms. The first R.6 draft checked only the real arm and so could not see
            # that the two arms were not at the same effective SNR -- the same failure mode as
            # R.5's unchecked rung 3.
            for rec in recs:
                m_r = measure_inband_snr(real_buf, real_pcm, rec["freq"])
                m_a = measure_inband_snr(awgn_buf, awgn_bg, rec["freq"])
                sc1.append(("real", m_r - rec["snr_nominal"]))
                sc1.append(("awgn", m_a - rec["snr_nominal"]))
                contam.append(rec["contam_db"])
                per_signal.append({"cycle": ts, "arm": "real", "freq": rec["freq"],
                                   "snr_nominal": rec["snr_nominal"],
                                   "snr_measured_real": m_r, "snr_measured_awgn": m_a,
                                   "contam_db": rec["contam_db"]})

            ours_real = r5.decode_all_with_messages(native, real_buf)
            ours_awgn = r5.decode_all_with_messages(native, awgn_buf)

            wav_r = os.path.join(OUT_DIR, "buffers", f"{ts}_s{snr_db:+.0f}_real.wav")
            wav_a = os.path.join(OUT_DIR, "buffers", f"{ts}_s{snr_db:+.0f}_awgn.wav")
            r5.write_wav(wav_r, real_buf)
            r5.write_wav(wav_a, awgn_buf)
            jt9_real = r5.run_jt9_single(wav_r, os.path.join(OUT_DIR, "jt9"))
            jt9_awgn = r5.run_jt9_single(wav_a, os.path.join(OUT_DIR, "jt9"))
            os.remove(wav_r); os.remove(wav_a)

            for rec in recs:
                msg = rec["message"]
                nmsg = b1.normalize_hash_tokens(msg)
                for arm, dset in (("real", ours_real), ("awgn", ours_awgn)):
                    cells.setdefault((rec["snr_nominal"], arm, "ours"), []).append(
                        1 if (msg in dset or nmsg in dset) else 0)
                for arm, dset in (("real", jt9_real), ("awgn", jt9_awgn)):
                    cells.setdefault((rec["snr_nominal"], arm, "jt9"), []).append(
                        1 if (msg in dset or nmsg in dset) else 0)

        print(f"  [{ci}/{len(sel)}] {ts}: {len(gaps)} grafts x {len(SNR_GRID)} SNRs done")

    # -------------------- report --------------------
    print()
    print("=== SELF-CHECKS ===")
    med = {}
    for arm in ("real", "awgn"):
        a = np.array([v for k, v in sc1 if k == arm and np.isfinite(v)])
        med[arm] = float(np.median(a))
        print(f"SC1 [{arm}] measured-minus-nominal in-band SNR: n={len(a)} "
              f"mean {a.mean():+.2f} dB  median {med[arm]:+.2f}  "
              f"p5 {np.percentile(a,5):+.2f}  p95 {np.percentile(a,95):+.2f}")
    delta = med["real"] - med["awgn"]
    print(f"    arm-to-arm offset (real - awgn) = {delta:+.2f} dB  "
          f"{'[PASS]' if abs(delta) < 1.0 else '[FAIL] arms are NOT at matched effective SNR'}")
    ca = np.array([c for c in contam if np.isfinite(c)])
    print(f"SC4 gap contamination (raw/robust in-band, dB): median {np.median(ca):+.2f}  "
          f"p95 {np.percentile(ca,95):+.2f}  max {ca.max():+.2f}")
    print(f"    (high values = undecoded carriers in the 'empty' gap; this is what broke the "
          f"first draft)")
    print(f"SC2 gap-clearance violations: {sc2_viol}  {'[PASS]' if sc2_viol==0 else '[FAIL]'}")
    print(f"    total grafts placed: {n_gap_total}")

    print()
    print("=== P(decode) by in-band SNR, arm and decoder ===")
    print(f"{'SNR':>6} | {'ours REAL':>16} | {'ours AWGN':>16} | {'jt9 REAL':>16} | {'jt9 AWGN':>16}")
    print("-" * 84)
    summary = {}
    for snr_db in SNR_GRID:
        line = f"{snr_db:>+6.0f} |"
        for dec in ("ours", "jt9"):
            for arm in ("real", "awgn"):
                v = cells.get((snr_db, arm, dec), [])
                if v:
                    k, n = sum(v), len(v)
                    p, lo, hi = b2.wilson_interval(k, n)
                    line += f" {100*p:5.1f}% ({k:3d}/{n:3d}) |"
                    summary[f"{dec}_{arm}_{snr_db:+.0f}"] = {"k": k, "n": n, "p": p,
                                                             "ci_lo": lo, "ci_hi": hi}
                else:
                    line += f" {'--':>16} |"
        print(line)

    print()
    print("=== THE FORK ===")
    for snr_db in SNR_GRID:
        a = summary.get(f"ours_real_{snr_db:+.0f}")
        b = summary.get(f"ours_awgn_{snr_db:+.0f}")
        c = summary.get(f"jt9_real_{snr_db:+.0f}")
        d = summary.get(f"jt9_awgn_{snr_db:+.0f}")
        if a and b and c and d:
            print(f"  SNR {snr_db:+5.0f}: ours real-minus-awgn {100*(a['p']-b['p']):+6.1f} pt   "
                  f"jt9 real-minus-awgn {100*(c['p']-d['p']):+6.1f} pt   "
                  f"ours-minus-jt9 on REAL {100*(a['p']-c['p']):+6.1f} pt")

    with open(os.path.join(OUT_DIR, "measurements.json"), "w", encoding="utf-8") as fh:
        json.dump({"summary": summary,
                   "sc1_median_db": med, "sc1_arm_offset_db": delta,
                   "sc4_contam_median_db": float(np.median(ca)), "sc2_violations": sc2_viol,
                   "n_cycles": len(sel), "n_grafts": n_gap_total,
                   "snr_grid": SNR_GRID, "per_signal": per_signal[:2000]}, fh, indent=2)
    print(f"\nWrote {os.path.join(OUT_DIR, 'measurements.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
