"""E4-STAGE2 -- Amendment B5 (spec Sec.12): the census re-run with the time-origin
defect fixed. Replaces the old ROW 0a (circular, struck by B4) with ROW 0h/0i/0j
(Sec.12.7), a non-circular calibration on real, independently-transmitted audio,
then computes phi_upper on the full pre-registered 5,000-row sample using the
Sec.12.6 per-row origin-location procedure (Costas-only search, full-message rho1
at the located origin) instead of REF's raw (DT, freq).

Performance note (disclosed, not a methodology change): extract_channel_gains()
rebuilds the entire GFSK reference waveform (Gaussian-pulse convolution over the
full ~150k-sample transmission) on every grid point, which is correct but far
slower than necessary for a grid search. Sec.12.6's search varies frequency only
by a fixed offset from the row's own base frequency, and instantaneous_phase()'s
own arithmetic is linear in that offset (base_freq_hz enters only by being added,
pre-cumsum, to a per-sample instantaneous-frequency term), so
    z_ref(base_freq_hz + df) == z_ref(base_freq_hz) * exp(j*2*pi*df*t)
exactly (float arithmetic aside). This lets one build the message-independent
Costas carrier ONCE per row and obtain every frequency-grid point by a vector
multiply instead of a full re-synthesis. Verified byte-identical (to float
precision) against the unoptimised extract_channel_gains() call, per-grid-point,
before use here (qa/rr-study/harness/_verify_fast_origin_search.py). dt_s only
changes which audio SAMPLES are read (a slice), never the reference waveform, so
it was already free to vary in the slow path too; this fast path makes that
explicit by reusing one carrier across the whole dt grid as well.

NFR-021: all real callsigns/message text stay in-process; only ts/snr/dt/freq/
rho1/sharpness/hit (numeric or boolean) are ever written to disk, and only under
artefacts/ (gitignored).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))
_LGN_ROOT = str(_QA_ROOT / "live-gap-now")
if _LGN_ROOT not in sys.path:
    sys.path.insert(0, _LGN_ROOT)

from corpus import c2_cycles  # noqa: E402
from synth import encoder  # noqa: E402
from synth.constants import NUM_SYMBOLS, SYMBOL_PERIOD_S  # noqa: E402
from synth.estimator import rho1 as rho1_fn  # noqa: E402
from synth.modulator import instantaneous_phase  # noqa: E402
from synth.wavio import read_wav  # noqa: E402

DIAL_PREFIX = "14.074"
SNR_FLOOR_DB = -10
SAMPLE_N = 5000
SAMPLE_SEED = 20260916
RHO_STAR = 0.577          # spec Sec.8.1 (0a(ii)), fixed, never touched again
BAR_PHI = 0.12            # spec Sec.3.1 / Sec.5 Q1, ratified, movable until first phi

COSTAS = (3, 1, 4, 0, 6, 5, 2)
STARTS = (0, 36, 72)
COSTAS_IDX = [i for s in STARTS for i in range(s, s + 7)]

# Sec.12.6 step 3 -- the NORMATIVE (narrow) search used for the census itself,
# once the origin is known (from Sec.12.2) to sit inside it.
NARROW_DT_OFFSETS = np.arange(0.20, 0.8001, 0.01)
NARROW_FREQ_OFFSETS = np.arange(-2.0, 2.001, 0.25)

# Sec.12.7 -- "for 0h only, the search grid is the WIDE one", matching Sec.12.2(2)
# / b5_02's own grid exactly, so the sharpness threshold is transferable.
WIDE_DT_OFFSETS = np.arange(-0.30, 1.401, 0.02)
WIDE_FREQ_OFFSETS = np.arange(-3.0, 3.001, 0.5)

DT_MIN_S, DT_MAX_S = 0.0, 2.36  # audio-buffer bound, same as the b5 scripts

ROW_0H_IQR_MAX = 0.10
ROW_0H_SHARP_THRESH = 3.0
ROW_0H_SHARP_FRAC_MIN = 0.90
ROW_0I_MEDIAN_MIN = 0.80
CALIBRATION_SNR_FLOOR = 10  # dB, Sec.12.7's ">= +10 dB"
CALIBRATION_MIN_N = 25


def load_all_txt(path: str, lo: str, hi: str, dial_prefix: str = DIAL_PREFIX) -> dict:
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(dial_prefix):
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                snr = int(f[4])
                dt_s = float(f[5])
                freq_hz = int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, dt_s, freq_hz)
    return out


def build_frame(ref_all_txt: str, cycles: "list[tuple[str, str]]"):
    lo = min(ts for ts, _ in cycles)
    hi = max(ts for ts, _ in cycles)
    ref = load_all_txt(ref_all_txt, lo, hi)
    frame_keys = sorted(k for k, v in ref.items() if v[0] >= SNR_FLOOR_DB)
    return ref, frame_keys, lo, hi


def _tones_for(msg: str, cache: dict):
    if msg not in cache:
        try:
            cache[msg] = encoder.message_to_tones(msg)
        except Exception:
            cache[msg] = None
    return cache[msg]


def _costas_only_tones():
    t = [0] * NUM_SYMBOLS
    for s in STARTS:
        for j, v in enumerate(COSTAS):
            t[s + j] = v
    return t


_COSTAS_TONES = _costas_only_tones()


def locate_origin(
    audio: np.ndarray,
    fs: int,
    freq_ref: float,
    dt_ref: float,
    dt_offsets: np.ndarray,
    freq_offsets: np.ndarray,
):
    """Sec.12.6 steps 1-3: Costas-only grid search for (DT*, freq*).

    Fast path (see module docstring): the Costas reference carrier at
    freq_ref is built ONCE; every freq_offsets grid point is obtained by a
    vector multiply against a precomputed phase ramp instead of a full
    instantaneous_phase() resynthesis. Mathematically identical to calling
    extract_channel_gains(audio, COSTAS_TONES, freq_ref + df, dt_s=dt_ref + ddt, ...)
    at every (ddt, df) and taking sum(|g[COSTAS_IDX]|**2) as the score.

    Returns (dt_star, freq_star, best_power, sharpness) or None if no grid
    point fit inside the audio buffer.
    """
    sps = int(round(SYMBOL_PERIOD_S * fs))
    n_tx = NUM_SYMBOLS * sps
    audio = np.asarray(audio, dtype=np.float64)

    phase_ref = instantaneous_phase(list(_COSTAS_TONES), freq_ref, fs)
    z_base = np.exp(1j * phase_ref)
    t_arr = np.arange(n_tx, dtype=np.float64) / fs
    z_shift = {
        round(float(df), 6): z_base * np.exp(1j * 2.0 * np.pi * df * t_arr)
        for df in freq_offsets
    }

    powers = []
    best = None
    for ddt in dt_offsets:
        dt = dt_ref + float(ddt)
        if dt < DT_MIN_S or dt > DT_MAX_S:
            continue
        start = int(round(dt * fs))
        seg = audio[start:start + n_tx]
        if len(seg) < n_tx:
            continue
        for df in freq_offsets:
            z = z_shift[round(float(df), 6)]
            mixed = seg * np.conj(z)
            g = 2.0 * mixed.reshape(NUM_SYMBOLS, sps).mean(axis=1)
            p = float(np.sum(np.abs(g[COSTAS_IDX]) ** 2))
            powers.append(p)
            if best is None or p > best[0]:
                best = (p, dt, freq_ref + float(df))
    if best is None or not powers:
        return None
    med = float(np.median(powers))
    sharp = (best[0] / med) if med > 0 else float("inf")
    return best[1], best[2], best[0], sharp


def full_message_rho1_at(audio, fs, tones, dt_star, freq_star):
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
    g = 2.0 * mixed.reshape(NUM_SYMBOLS, sps).mean(axis=1)
    return rho1_fn(g)


def wilson_upper_95(k: int, n: int) -> float:
    """Upper end of the two-sided 95% Wilson score interval for k/n."""
    if n == 0:
        return float("nan")
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return float((centre + half) / denom)


def wilson_lower_95(k: int, n: int) -> float:
    if n == 0:
        return float("nan")
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return float((centre - half) / denom)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sample-n", type=int, default=SAMPLE_N)
    ap.add_argument("--limit", type=int, default=0, help="debug: cap rows processed, 0=all")
    ap.add_argument("--progress-every", type=int, default=100)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    cycles, dup_report = c2_cycles()
    wav_by_ts = dict(cycles)
    c2_dir = os.path.dirname(os.path.dirname(list(wav_by_ts.values())[0]))
    ref_path = os.path.join(c2_dir, "wsjtx-1-ft991a", "ALL.TXT")
    owsfz_path = os.path.join(c2_dir, "openwsfz", "ALL.TXT")

    ref, frame_keys, lo, hi = build_frame(ref_path, cycles)
    n_ref_total = len(ref)
    print(f"C2 window: {lo} .. {hi}  ({len(cycles)} cycles, dup report {dup_report})", flush=True)
    print(f"REF total rows (dial {DIAL_PREFIX}, window): {n_ref_total}", flush=True)
    print(f"Frame (SNR >= {SNR_FLOOR_DB} dB): {len(frame_keys)} rows (spec expects 60,239)", flush=True)

    from matcher import recovery  # noqa: E402
    ows = load_all_txt(owsfz_path, lo, hi)
    ows_pairs = {k: (v[0], v[2]) for k, v in ows.items()}
    ref_pairs = {k: (v[0], v[2]) for k, v in ref.items()}
    rec = recovery(ows_pairs, ref_pairs)
    hit_set = rec["hit_set"]
    print(f"D3 basis: matcher.recovery() R_wild={rec['R_wild']:.2f}% (n_ref={rec['n_ref']}) "
          f"-- reproduction check only", flush=True)

    rng = np.random.default_rng(SAMPLE_SEED)
    n = min(args.sample_n, len(frame_keys))
    sample_idx = rng.choice(len(frame_keys), size=n, replace=False)
    sample_idx.sort()
    sample_keys = [frame_keys[i] for i in sample_idx]
    if args.limit:
        sample_keys = sample_keys[: args.limit]
    print(f"Pre-registered sample: {len(sample_keys)} rows (seed {SAMPLE_SEED})", flush=True)

    tones_cache: dict = {}

    # ---- ROW 0h / 0i calibration set: the >=+10dB subset of THIS SAME seeded
    # sample (Sec.12.7: "drawn with the spec's own seed") -----------------------
    calib_keys = [k for k in sample_keys if ref[k][0] >= CALIBRATION_SNR_FLOOR]
    print(f"Calibration subset (SNR >= {CALIBRATION_SNR_FLOOR} dB) within the sample: "
          f"{len(calib_keys)} rows (spec floor n>={CALIBRATION_MIN_N})", flush=True)

    calib_rows = []
    for j, (ts, msg) in enumerate(calib_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            continue
        tones = _tones_for(msg, tones_cache)
        audio, fs = read_wav(wav_path)
        loc = locate_origin(audio, fs, float(freq_ref), dt_ref, WIDE_DT_OFFSETS, WIDE_FREQ_OFFSETS)
        if loc is None:
            continue
        dt_star, freq_star, best_p, sharp = loc
        r1 = None
        if tones is not None:
            r1 = full_message_rho1_at(audio, fs, tones, dt_star, freq_star)
        calib_rows.append({
            "snr_db": snr, "dt_off": dt_star - dt_ref, "sharpness": sharp,
            "rho1_full": r1, "re_encodable": tones is not None,
        })
        if (j + 1) % 5 == 0:
            print(f"  0h/0i calibration: {j + 1}/{len(calib_keys)} "
                  f"({time.time() - t_start:.0f}s elapsed)", flush=True)

    dt_offs = np.array([r["dt_off"] for r in calib_rows])
    sharps = np.array([r["sharpness"] for r in calib_rows])
    r1s = np.array([r["rho1_full"] for r in calib_rows if r["rho1_full"] is not None])

    row_0h_iqr = float(np.percentile(dt_offs, 75) - np.percentile(dt_offs, 25)) if len(dt_offs) else float("nan")
    row_0h_sharp_frac = float(np.mean(sharps >= ROW_0H_SHARP_THRESH)) if len(sharps) else 0.0
    row_0h_pass = (
        len(calib_rows) >= CALIBRATION_MIN_N
        and row_0h_iqr <= ROW_0H_IQR_MAX
        and row_0h_sharp_frac >= ROW_0H_SHARP_FRAC_MIN
    )
    row_0i_median = float(np.median(r1s)) if len(r1s) else float("nan")
    row_0i_pass = len(r1s) >= CALIBRATION_MIN_N and row_0i_median >= ROW_0I_MEDIAN_MIN

    print(f"\nROW 0h: n={len(calib_rows)} iqr(dt_off)={row_0h_iqr:.4f} "
          f"(bar <= {ROW_0H_IQR_MAX}) sharp>=3x frac={row_0h_sharp_frac:.3f} "
          f"(bar >= {ROW_0H_SHARP_FRAC_MIN}) -> {'PASS' if row_0h_pass else 'STOP'}", flush=True)
    print(f"ROW 0i: n={len(r1s)} median(rho1_full)={row_0i_median:.4f} "
          f"(bar >= {ROW_0I_MEDIAN_MIN}) -> {'PASS' if row_0i_pass else 'STOP'}", flush=True)

    calib_out = {
        "row_0h": {"n": len(calib_rows), "iqr_dt_off": row_0h_iqr,
                   "sharp_frac_ge_3x": row_0h_sharp_frac, "pass": row_0h_pass},
        "row_0i": {"n": int(len(r1s)), "median_rho1_full": row_0i_median, "pass": row_0i_pass},
        "calib_rows": calib_rows,
    }
    with open(os.path.join(args.out_dir, "e4_stage2_b5_calibration.json"), "w", encoding="utf-8") as f:
        json.dump(calib_out, f, indent=2)

    if not (row_0h_pass and row_0i_pass):
        print("\nSTOP: ROW 0h/0i did not both pass. Census NOT computed (spec Sec.12.7 STOP).",
              flush=True)
        return

    # ---- ROW 0j + phi_upper: the full pre-registered sample, corrected origin --
    print(f"\nProceeding to the full sample ({len(sample_keys)} rows), narrow grid "
          f"({len(NARROW_DT_OFFSETS)}x{len(NARROW_FREQ_OFFSETS)} = "
          f"{len(NARROW_DT_OFFSETS) * len(NARROW_FREQ_OFFSETS)} pts/row)...", flush=True)

    rows_out = []
    n_dropped = 0
    n_wav_missing = 0
    for i, (ts, msg) in enumerate(sample_keys):
        snr, dt_ref, freq_ref = ref[(ts, msg)]
        tones = _tones_for(msg, tones_cache)
        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            n_wav_missing += 1
            rows_out.append({"ts_present": True, "snr_db": snr, "re_encodable": tones is not None,
                              "rho1": None, "hit": None, "wav_missing": True})
            continue
        if tones is None:
            n_dropped += 1
            rows_out.append({"snr_db": snr, "re_encodable": False, "rho1": None, "hit": None})
            continue

        audio, fs = read_wav(wav_path)
        loc = locate_origin(audio, fs, float(freq_ref), dt_ref, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS)
        if loc is None:
            n_dropped += 1
            rows_out.append({"snr_db": snr, "re_encodable": False, "rho1": None, "hit": None,
                              "extract_error": "origin_not_locatable_in_narrow_grid"})
            continue
        dt_star, freq_star, best_p, sharp = loc
        r1 = full_message_rho1_at(audio, fs, tones, dt_star, freq_star)
        if r1 is None:
            n_dropped += 1
            rows_out.append({"snr_db": snr, "re_encodable": False, "rho1": None, "hit": None,
                              "extract_error": "full_message_extract_failed"})
            continue

        drift_hz_placeholder = None  # DRIFT (E4/E5) stays struck permanently (B2) -- not computed
        rows_out.append({
            "snr_db": snr, "re_encodable": True, "rho1": r1, "sharpness": sharp,
            "dt_off": dt_star - dt_ref, "hit": (ts, msg) in hit_set,
        })

        if (i + 1) % args.progress_every == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta_s = (len(sample_keys) - (i + 1)) / rate if rate > 0 else float("nan")
            print(f"  census: {i + 1}/{len(sample_keys)}  elapsed={elapsed:.0f}s  "
                  f"eta={eta_s:.0f}s  dropped={n_dropped}  wav_missing={n_wav_missing}", flush=True)
            # checkpoint so a killed run is not a total loss
            with open(os.path.join(args.out_dir, "e4_stage2_b5_sample_rows.partial.json"),
                      "w", encoding="utf-8") as f:
                json.dump({"n_done": i + 1, "rows": rows_out}, f)

    dropped_share = n_dropped / len(sample_keys) if sample_keys else float("nan")
    print(f"\nROW 0j: dropped (not re-encodable / extract error) = {n_dropped} "
          f"({dropped_share:.4%}) of {len(sample_keys)}. WAV missing: {n_wav_missing}.", flush=True)
    if dropped_share > 0.10:
        print("NOTE (Sec.12.7 ROW 0j): d > 0.10 -- phi must be reported as the band "
              "[phi*(1-d), phi*(1-d)+d]; a bar inside that band means that limb does not close.",
              flush=True)

    valid_rows = [r for r in rows_out if r.get("re_encodable") and r.get("rho1") is not None]
    n_valid = len(valid_rows)
    k_below = sum(1 for r in valid_rows if r["rho1"] < RHO_STAR)
    phi_upper = k_below / n_valid if n_valid else float("nan")
    ci_upper_95 = wilson_upper_95(k_below, n_valid)
    ci_lower_95 = wilson_lower_95(k_below, n_valid)

    if ci_upper_95 < BAR_PHI:
        reading = "E1"
    elif ci_lower_95 >= BAR_PHI:
        reading = "E2"
    else:
        reading = "E3"

    print(f"\nphi_upper = {phi_upper:.4f} (k={k_below}/{n_valid}), "
          f"95% CI [{ci_lower_95:.4f}, {ci_upper_95:.4f}], BAR_phi={BAR_PHI}", flush=True)
    print(f"READING: {reading}", flush=True)

    hit_rows = [r["rho1"] for r in valid_rows if r["hit"]]
    miss_rows = [r["rho1"] for r in valid_rows if r["hit"] is False]
    snr_bands = {}
    for r in valid_rows:
        b = r["snr_db"]
        snr_bands.setdefault(b, []).append(r["rho1"])

    summary = {
        "n_ref_total": n_ref_total,
        "n_frame": len(frame_keys),
        "n_sample": len(sample_keys),
        "n_dropped": n_dropped,
        "dropped_share": dropped_share,
        "n_wav_missing": n_wav_missing,
        "n_valid": n_valid,
        "rho_star": RHO_STAR,
        "bar_phi": BAR_PHI,
        "phi_upper": phi_upper,
        "k_below_rho_star": k_below,
        "ci95": [ci_lower_95, ci_upper_95],
        "reading": reading,
        "row_0h": calib_out["row_0h"],
        "row_0i": calib_out["row_0i"],
        "d1_rho1_percentiles": {
            str(p): float(np.percentile([r["rho1"] for r in valid_rows], p))
            for p in (5, 10, 25, 50, 75, 90, 95)
        } if n_valid else {},
        "d3_hit_median_rho1": float(np.median(hit_rows)) if hit_rows else None,
        "d3_miss_median_rho1": float(np.median(miss_rows)) if miss_rows else None,
        "d3_n_hit": len(hit_rows),
        "d3_n_miss": len(miss_rows),
        "wall_time_s": time.time() - t_start,
    }
    with open(os.path.join(args.out_dir, "e4_stage2_b5_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(args.out_dir, "e4_stage2_b5_sample_rows.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows_out}, f)
    partial = os.path.join(args.out_dir, "e4_stage2_b5_sample_rows.partial.json")
    if os.path.exists(partial):
        os.remove(partial)
    print(f"\nDone in {summary['wall_time_s']:.0f}s. Wrote e4_stage2_b5_summary.json "
          f"and e4_stage2_b5_sample_rows.json under {args.out_dir} (NFR-021: no callsigns, "
          f"numeric fields only).", flush=True)


if __name__ == "__main__":
    main()
