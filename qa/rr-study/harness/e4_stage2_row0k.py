"""E4-STAGE2 Amendment B8 (spec Sec.15.7), ROW 0k -- does rho1 discriminate a
KNOWN change in fading on REAL audio, at the SAME starting point real rows sit
at (B_pre, matched from the census's own measured median), avoiding the
saturation confound a clean bench arm would introduce?

Design (disclosed, since the spec left the exact composition mechanism open):
Rather than reconstructing a Hilbert-transform audio-domain multiplicative
fade on real PCM, the additional B_add dose is injected directly on the
EXTRACTED per-symbol complex gain sequence g[0..78] -- an independent
zero-mean complex Gaussian process with the bench's own Doppler-spread
generator (synth.fade._wrapped_shaped_gaussian_process), called at n=79,
sample_rate_hz=1/SYMBOL_PERIOD_S (i.e. the SAME generator, same normalisation
derivation, just evaluated at the symbol rate instead of the audio rate),
normalised to unit average power and multiplied elementwise into g. This
composes two independent fading contributions exactly where rho1 reads them
(g is the physical quantity the statistic is built from), for BOTH arms
identically:
  - real arm:  g_final = g_real_row  * g_add(B_add)
  - bench arm: g_final = g_pre(B_pre) * g_add(B_add)
No audio reconstruction, no image-frequency risk, one injection mechanism for
both arms. B_add=0 is a no-op (identity), never calls the generator (spread=0
is degenerate for it -- see its own buffer_s = n/fs + 2/spread_hz).

Real arm uses the SAME Sec.12.6 estimator (Costas-only origin search on the
ORIGINAL, un-injected audio, located ONCE per row and reused across all five
doses -- injecting a slowly-varying gain factor does not move the symbol
timing origin, and locating once removes origin-search noise as a confound on
the dose comparison). Bench arm uses direct extraction at known truth (dt=0),
matching the original row0a_calibration.py methodology, since truth is known
by construction and no location step is being tested here (that is Sec.13.5's
job, run separately).

NFR-021: real-row per-row output is snr/dt/freq/rho1 only, numeric, under
artefacts/ only. Bench trials are 100% synthetic Q-prefix (MSG-01, "CQ Q1ABC
FN42", already used elsewhere in this study).
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
from synth import channel, encoder, fade, modulator  # noqa: E402
from synth.constants import DEFAULT_SAMPLE_RATE_HZ, NUM_SYMBOLS, SYMBOL_PERIOD_S  # noqa: E402
from synth.estimator import extract_channel_gains, rho1 as rho1_fn  # noqa: E402
from synth.modulator import instantaneous_phase  # noqa: E402
from harness.common import compute_seed  # noqa: E402
from harness.e4_stage2_census_b5 import (  # noqa: E402
    build_frame, _tones_for, locate_origin, CALIBRATION_SNR_FLOOR, SAMPLE_SEED,
    NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS,
)

OUT_DIR = str(_QA_ROOT.parent / "artefacts" / "e4-stage2-b8-row0k")
os.makedirs(OUT_DIR, exist_ok=True)

REAL_MEDIAN_TARGET = 0.7537  # this study's own n=855 pre-registered ROW 0i figure
REAL_N_ROWS = 120            # >= spec's n>=100, deterministic prefix of calib_keys
BENCH_N_TRIALS = 150         # >= spec's n>=100
B_ADD_LADDER = [0.0, 1.0, 2.0, 5.0, 10.0]
MESSAGE = "CQ Q1ABC FN42"    # MSG-01, existing Q-prefix synthetic gate message
BASE_FREQ_HZ = 1500.0
SYMBOL_RATE_HZ = 1.0 / SYMBOL_PERIOD_S  # 6.25 Hz


def gain_domain_add_fade(g: np.ndarray, spread_hz: float, seed: int) -> np.ndarray:
    """Multiply an independent unit-power complex Gaussian process (Doppler
    spread `spread_hz`, generated at the SYMBOL rate) elementwise into `g`.
    spread_hz<=0 is a no-op (the generator is degenerate at B=0)."""
    if spread_hz <= 0:
        return g
    rng = np.random.default_rng(seed)
    g_add = fade._wrapped_shaped_gaussian_process(len(g), spread_hz, SYMBOL_RATE_HZ, rng)
    g_add = g_add / np.sqrt(0.5)  # module's own E|g|^2=0.5 -> unit average power
    return g * g_add


# ------------------------- REAL arm -----------------------------------------

def full_message_gains_at(audio, fs, tones, dt_star, freq_star) -> "np.ndarray | None":
    sps = int(round(SYMBOL_PERIOD_S * fs))
    n_tx = NUM_SYMBOLS * sps
    audio = np.asarray(audio, dtype=np.float64)
    phase_ref = instantaneous_phase(list(tones), freq_star, fs)
    z_ref = np.exp(1j * phase_ref)
    start = int(round(dt_star * fs))
    seg = audio[start:start + n_tx]
    if len(seg) < n_tx:
        return None
    mixed = seg * np.conj(z_ref)
    return 2.0 * mixed.reshape(NUM_SYMBOLS, sps).mean(axis=1)


def run_real_arm(log):
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
    real_keys = calib_keys[:REAL_N_ROWS]  # deterministic prefix, not outcome-chosen
    log(f"real arm: {len(real_keys)} rows (deterministic prefix of the pre-registered "
        f">= {CALIBRATION_SNR_FLOOR}dB calibration subset)")

    tones_cache = {}
    snrs_used = []
    per_dose_rho1 = {b: [] for b in B_ADD_LADDER}
    n_skipped = 0
    for i, (ts, msg) in enumerate(real_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        tones = _tones_for(msg, tones_cache)
        if tones is None:
            n_skipped += 1
            continue
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            n_skipped += 1
            continue
        audio, fs = read_wav(wav_path)
        loc = locate_origin(audio, fs, float(freq_ref), dt_ref, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS)
        if loc is None:
            n_skipped += 1
            continue
        dt_star, freq_star, _, _ = loc
        g_real = full_message_gains_at(audio, fs, tones, dt_star, freq_star)
        if g_real is None:
            n_skipped += 1
            continue
        snrs_used.append(snr)
        for b_add in B_ADD_LADDER:
            seed = compute_seed(f"E4-STAGE2-0K-REAL-ADD-{b_add}", 0, i)
            g_final = gain_domain_add_fade(g_real, b_add, seed)
            per_dose_rho1[b_add].append(rho1_fn(g_final))
        if (i + 1) % 20 == 0:
            log(f"  real arm: {i + 1}/{len(real_keys)}")

    medians = {b: float(np.median(v)) for b, v in per_dose_rho1.items()}
    log(f"real arm done: n_used={len(snrs_used)} n_skipped={n_skipped} "
        f"median_snr_db={float(np.median(snrs_used)):.1f}")
    for b in B_ADD_LADDER:
        log(f"  B_add={b:>5}: n={len(per_dose_rho1[b])} median_rho1={medians[b]:.4f}")
    return {
        "n_used": len(snrs_used), "n_skipped": n_skipped,
        "median_snr_db": float(np.median(snrs_used)) if snrs_used else None,
        "medians_by_dose": medians,
        "per_dose_rho1": {str(b): v for b, v in per_dose_rho1.items()},
    }


# ------------------------- BENCH arm -----------------------------------------

def bench_trial_rho1(b_pre: float, snr_db: float, trial: int, tones, fs: int) -> float:
    fade_seed = compute_seed(f"E4-STAGE2-0K-BENCH-PRE-{b_pre}-{snr_db}", 0, trial)
    noise_seed = compute_seed(f"E4-STAGE2-0K-BENCH-NOISE-{b_pre}-{snr_db}", 0, trial)
    clean = fade.modulate_faded(tones, BASE_FREQ_HZ, b_pre, dt_s=0.0, sample_rate_hz=fs, seed=fade_seed)
    noisy = channel.add_noise(clean, snr_db, noise_seed, sample_rate_hz=fs)
    g_pre = extract_channel_gains(noisy, tones, BASE_FREQ_HZ, dt_s=0.0, sample_rate_hz=fs)
    return g_pre


def solve_b_pre(target_median: float, snr_db: float, tones, fs: int, log,
                 n_trials: int = 150, tol: float = 0.02, max_iter: int = 12) -> "tuple[float, float]":
    """Bisect B_pre so the bench arm's median rho1(B_add=0) matches
    `target_median` within `tol`. Bracket from the study's own bench table
    (row0a_calibration_result.json: B=1 -> ~0.86, B=2 -> ~0.64 at both -8/0dB),
    which already brackets 0.7537."""
    lo, hi = 1.0, 2.0

    def median_at(b_pre):
        rhos = [float(rho1_fn(bench_trial_rho1(b_pre, snr_db, t, tones, fs))) for t in range(n_trials)]
        return float(np.median(rhos))

    m_lo, m_hi = median_at(lo), median_at(hi)
    log(f"  bisect bracket: B={lo} -> median={m_lo:.4f}   B={hi} -> median={m_hi:.4f}  "
        f"(target {target_median:.4f})")
    assert m_hi <= target_median <= m_lo, "target not bracketed by [1,2] Hz -- widen the bracket"

    for it in range(max_iter):
        mid = (lo + hi) / 2.0
        m_mid = median_at(mid)
        log(f"  bisect it={it}: B={mid:.4f} -> median={m_mid:.4f} (diff={m_mid - target_median:+.4f})")
        if abs(m_mid - target_median) <= tol:
            return mid, m_mid
        if m_mid > target_median:
            lo = mid
        else:
            hi = mid
    return mid, m_mid


def run_bench_arm(b_pre: float, snr_db: float, log):
    tones = encoder.message_to_tones(MESSAGE)
    fs = DEFAULT_SAMPLE_RATE_HZ
    medians = {}
    per_dose_rho1 = {}
    for b_add in B_ADD_LADDER:
        vals = []
        for t in range(BENCH_N_TRIALS):
            g_pre = bench_trial_rho1(b_pre, snr_db, t, tones, fs)
            seed = compute_seed(f"E4-STAGE2-0K-BENCH-ADD-{b_add}", 0, t)
            g_final = gain_domain_add_fade(g_pre, b_add, seed)
            vals.append(float(rho1_fn(g_final)))
        medians[b_add] = float(np.median(vals))
        per_dose_rho1[b_add] = vals
        log(f"  bench B_add={b_add:>5}: n={len(vals)} median_rho1={medians[b_add]:.4f}")
    return {"medians_by_dose": medians, "per_dose_rho1": {str(b): v for b, v in per_dose_rho1.items()}}


def main():
    t0 = time.time()

    def log(msg):
        print(f"[{time.time()-t0:6.0f}s] {msg}", flush=True)

    log("=" * 78)
    log("REAL ARM")
    log("=" * 78)
    real = run_real_arm(log)

    log("=" * 78)
    log("Solving B_pre against this study's own n=855 target "
        f"(median_rho1={REAL_MEDIAN_TARGET}), at the real arm's own median SNR")
    log("=" * 78)
    tones = encoder.message_to_tones(MESSAGE)
    fs = DEFAULT_SAMPLE_RATE_HZ
    bench_snr_db = round(real["median_snr_db"]) if real["median_snr_db"] is not None else 15.0
    b_pre, b_pre_median = solve_b_pre(REAL_MEDIAN_TARGET, bench_snr_db, tones, fs, log)
    log(f"B_pre = {b_pre:.4f} Hz  (bench median at B_add=0: {b_pre_median:.4f}, "
        f"target {REAL_MEDIAN_TARGET}, snr={bench_snr_db}dB)")

    log("=" * 78)
    log("BENCH ARM")
    log("=" * 78)
    bench = run_bench_arm(b_pre, bench_snr_db, log)

    delta_real = real["medians_by_dose"][0.0] - real["medians_by_dose"][10.0]
    delta_bench = bench["medians_by_dose"][0.0] - bench["medians_by_dose"][10.0]
    ratio = abs(delta_real - delta_bench) / delta_bench if delta_bench != 0 else float("inf")
    compressed = delta_real < 0.5 * delta_bench

    if ratio <= 0.20:
        reading = "K1 -- rho1 DISCRIMINATES fading on real audio. Census proceeds; rho* re-referenced by the measured offset."
    elif compressed:
        reading = "K2 -- response COMPRESSED. Stop-loss fires: FADE exposure limb CLOSES."
    else:
        reading = "K3 -- report only, do not interpret."

    log("=" * 78)
    log("RESULT")
    log("=" * 78)
    log(f"Delta_real  = median(0)-median(10) = {real['medians_by_dose'][0.0]:.4f} - "
        f"{real['medians_by_dose'][10.0]:.4f} = {delta_real:.4f}")
    log(f"Delta_bench = median(0)-median(10) = {bench['medians_by_dose'][0.0]:.4f} - "
        f"{bench['medians_by_dose'][10.0]:.4f} = {delta_bench:.4f}")
    log(f"|Delta_real - Delta_bench| / Delta_bench = {ratio:.4f}  (K1 bar <= 0.20)")
    log(f"Delta_real < 0.5*Delta_bench ({0.5*delta_bench:.4f})? {compressed}  (K2 bar)")
    log(f"READING: {reading}")

    out = {
        "b_pre_hz": b_pre, "b_pre_median_check": b_pre_median, "bench_snr_db": bench_snr_db,
        "real_arm": real, "bench_arm": bench,
        "delta_real": delta_real, "delta_bench": delta_bench, "ratio": ratio,
        "compressed": compressed, "reading": reading,
        "wall_time_s": time.time() - t0,
    }
    with open(os.path.join(OUT_DIR, "row0k_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    log(f"Wrote {OUT_DIR}/row0k_result.json")


if __name__ == "__main__":
    main()
