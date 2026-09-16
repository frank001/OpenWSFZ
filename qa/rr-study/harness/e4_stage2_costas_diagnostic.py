"""DIAGNOSTIC (Stage-2 spec amendment B4, Sec.11.4) -- no bar, no reading.

Splits the "real rows don't correlate" finding in two, using the fact that
the Costas sync symbols (positions 0-6, 36-42, 72-78, tones (3,1,4,0,6,5,2))
are FIXED and MESSAGE-INDEPENDENT -- unlike the 58 data symbols, which depend
on this run's own message-to-tone re-encode of REF's text.

Correlates strong (>=+10 dB) real rows against the Costas symbols ONLY, over
the same wide (DT, freq) grid that found a sharp, unambiguous peak cold on a
bench gate WAV. The reference tones outside the Costas positions are a FIXED,
message-independent filler (not the row's own re-encoded message) so a wrong
re-encode cannot contaminate this test either way.

    Sharp Costas peak, full-message still fails -> re-encode is wrong, repairable.
    No Costas peak either                        -> waveform/timing model itself
                                                     doesn't match real audio; report
                                                     and stop, do not iterate further.

Usage:
    python harness/e4_stage2_costas_diagnostic.py --n 20 --snr-floor 10

No callsigns or message text printed -- ts/snr/dt/freq/power only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))
_LGN_ROOT = str(_QA_ROOT / "live-gap-now")
if _LGN_ROOT not in sys.path:
    sys.path.insert(0, _LGN_ROOT)
_HARNESS_ROOT = str(_QA_ROOT / "harness")
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)

from corpus import c2_cycles
from e4_stage2_census import build_frame, SAMPLE_SEED
from synth.estimator import extract_channel_gains
from synth.wavio import read_wav
from synth.constants import NUM_SYMBOLS

COSTAS_PATTERN = (3, 1, 4, 0, 6, 5, 2)
COSTAS_STARTS = (0, 36, 72)
COSTAS_INDICES = [i for start in COSTAS_STARTS for i in range(start, start + 7)]  # 21 symbols

DT_GRID = np.arange(-0.05, 0.0501, 0.005)
FREQ_GRID = np.arange(-10.0, 10.01, 0.5)


def costas_only_tones() -> "list[int]":
    """79-symbol tone array: the TRUE, message-independent Costas tones at
    their real positions, and a fixed (not row-dependent) filler of tone 0
    everywhere else -- deliberately NOT the row's own re-encoded message, so
    this test cannot be contaminated by a wrong re-encode either way."""
    tones = [0] * NUM_SYMBOLS
    for start in COSTAS_STARTS:
        for j, val in enumerate(COSTAS_PATTERN):
            tones[start + j] = val
    return tones


def costas_power(g: np.ndarray) -> float:
    return float(np.sum(np.abs(g[COSTAS_INDICES]) ** 2))


def grid_search_costas(audio, tones, base_freq_hz, dt_center, fs):
    """Returns (best_power, best_dt, best_freq, all_powers) over the grid."""
    powers = np.zeros((len(DT_GRID), len(FREQ_GRID)))
    best = None
    for i, ddt in enumerate(DT_GRID):
        dt = dt_center + ddt
        if dt < 0:
            powers[i, :] = np.nan
            continue
        for j, dfreq in enumerate(FREQ_GRID):
            f = base_freq_hz + dfreq
            try:
                g = extract_channel_gains(audio, tones, f, dt_s=dt, sample_rate_hz=fs)
            except Exception:
                powers[i, j] = np.nan
                continue
            p = costas_power(g)
            powers[i, j] = p
            if best is None or p > best[0]:
                best = (p, dt, f)
    return best, powers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--snr-floor", type=float, default=10.0)
    args = ap.parse_args()

    cycles, _ = c2_cycles()
    wav_by_ts = dict(cycles)
    c2_dir = str(Path(list(wav_by_ts.values())[0]).parent.parent)
    ref_path = str(Path(c2_dir) / "wsjtx-1-ft991a" / "ALL.TXT")
    ref, frame_keys, lo, hi = build_frame(ref_path, cycles)

    strong_keys = sorted(k for k in frame_keys if ref[k][0] >= args.snr_floor)
    rng = np.random.default_rng(SAMPLE_SEED + 1)  # distinct stream from the main sample
    idx = rng.choice(len(strong_keys), size=min(args.n, len(strong_keys)), replace=False)
    idx.sort()
    keys = [strong_keys[i] for i in idx]
    print(f"Strong rows available (SNR >= {args.snr_floor} dB): {len(strong_keys)}; "
          f"using {len(keys)}")

    tones = costas_only_tones()
    results = []
    for (ts, msg) in keys:
        snr, dt_s, freq_hz = ref[(ts, msg)]
        wav_path = wav_by_ts.get(ts)
        if wav_path is None:
            continue
        audio, fs = read_wav(wav_path)
        best, powers = grid_search_costas(audio, tones, float(freq_hz), dt_s, fs)
        if best is None:
            continue
        best_power, best_dt, best_freq = best
        finite = powers[np.isfinite(powers)]
        median_power = float(np.median(finite))
        p90_power = float(np.percentile(finite, 90))
        sharpness = best_power / median_power if median_power > 0 else float("inf")
        results.append({
            "ts": ts, "snr_db": snr, "dt_reported": dt_s, "freq_reported": freq_hz,
            "best_dt": best_dt, "dt_shift": best_dt - dt_s,
            "best_freq": best_freq, "freq_shift": best_freq - freq_hz,
            "best_power": best_power, "median_power": median_power,
            "p90_power": p90_power, "sharpness": sharpness,
            "pinned_freq_edge": abs(best_freq - freq_hz) >= (10.0 - 0.5),
            "pinned_dt_edge": abs(best_dt - dt_s) >= 0.0499,
        })
        print(f"  ts={ts} snr={snr:+.0f}dB  best_power={best_power:.3f} "
              f"median={median_power:.3f} p90={p90_power:.3f} sharpness(best/median)={sharpness:.2f}  "
              f"dt_shift={best_dt - dt_s:+.3f}s freq_shift={best_freq - freq_hz:+.2f}Hz  "
              f"{'PINNED-EDGE' if (abs(best_freq - freq_hz) >= 9.5 or abs(best_dt - dt_s) >= 0.0499) else ''}")

    sharpness_vals = np.array([r["sharpness"] for r in results])
    n_pinned = sum(1 for r in results if r["pinned_freq_edge"] or r["pinned_dt_edge"])
    print()
    print(f"n={len(results)}")
    print(f"sharpness (best/median power): median={np.median(sharpness_vals):.2f} "
          f"min={sharpness_vals.min():.2f} max={sharpness_vals.max():.2f}")
    print(f"rows pinned at a search edge (no interior peak found): {n_pinned}/{len(results)}")
    print("(compare: the gate-WAV control found best_power=4.10 vs next-best=1.10, "
          "sharpness ~3.7, no pinning, at a consistent, physically sane DT)")


if __name__ == "__main__":
    main()
