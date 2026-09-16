"""DIAGNOSTIC, not part of the pre-registered pipeline: quantify how much of
raw (unrefined) rho1 on LIVE rows is WSJT-X DT-quantization artefact rather
than real fading. Compares raw rho1 (using REF's reported, 0.1 s-quantized
DT directly) against a small local DT/frequency refinement search (maximise
|g|^2) on the SAME sampled rows.

Usage:
    python harness/e4_stage2_dt_diagnostic.py --n 40

No callsigns or message text printed -- ts/snr/dt/freq/rho1 only.
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

from corpus import c2_cycles
from e4_stage2_census import build_frame, SAMPLE_SEED
from synth import encoder
from synth.estimator import extract_channel_gains, rho1 as rho1_fn
from synth.wavio import read_wav

DT_GRID = np.arange(-0.05, 0.0501, 0.005)
FREQ_GRID = np.arange(-0.5, 0.501, 0.1)


def refine(audio, tones, base_freq, dt_center, fs):
    best = None
    for ddt in DT_GRID:
        dt = dt_center + ddt
        if dt < 0:
            continue
        for dfreq in FREQ_GRID:
            f = base_freq + dfreq
            try:
                g = extract_channel_gains(audio, tones, f, dt_s=dt, sample_rate_hz=fs)
            except Exception:
                continue
            power = float(np.sum(np.abs(g) ** 2))
            if best is None or power > best[0]:
                best = (power, dt, f, g)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    cycles, _ = c2_cycles()
    wav_by_ts = dict(cycles)
    c2_dir = str(Path(list(wav_by_ts.values())[0]).parent.parent)
    ref_path = str(Path(c2_dir) / "wsjtx-1-ft991a" / "ALL.TXT")
    ref, frame_keys, lo, hi = build_frame(ref_path, cycles)

    rng = np.random.default_rng(SAMPLE_SEED)
    idx = rng.choice(len(frame_keys), size=min(args.n, len(frame_keys)), replace=False)
    idx.sort()
    keys = [frame_keys[i] for i in idx]

    raw_vals, refined_vals, dt_shift, freq_shift = [], [], [], []
    for (ts, msg) in keys:
        snr, dt_s, freq_hz = ref[(ts, msg)]
        try:
            tones = encoder.message_to_tones(msg)
        except Exception:
            continue
        wav_path = wav_by_ts.get(ts)
        if wav_path is None:
            continue
        audio, fs = read_wav(wav_path)
        try:
            g_raw = extract_channel_gains(audio, tones, float(freq_hz), dt_s=dt_s, sample_rate_hz=fs)
        except Exception:
            continue
        r_raw = rho1_fn(g_raw)
        best = refine(audio, tones, float(freq_hz), dt_s, fs)
        if best is None:
            continue
        _, dt_hat, f_hat, g_ref = best
        r_ref = rho1_fn(g_ref)
        raw_vals.append(r_raw)
        refined_vals.append(r_ref)
        dt_shift.append(dt_hat - dt_s)
        freq_shift.append(f_hat - freq_hz)

    raw_vals = np.array(raw_vals)
    refined_vals = np.array(refined_vals)
    dt_shift = np.array(dt_shift)
    freq_shift = np.array(freq_shift)

    print(f"n={len(raw_vals)}")
    print(f"RAW      median rho1={np.median(raw_vals):.4f}  share<0.577={np.mean(raw_vals < 0.577):.3f}")
    print(f"REFINED  median rho1={np.median(refined_vals):.4f}  share<0.577={np.mean(refined_vals < 0.577):.3f}")
    print(f"median |dt shift|={np.median(np.abs(dt_shift)):.4f}s  "
          f"share |dt shift|>=0.03s={np.mean(np.abs(dt_shift) >= 0.03):.3f}")
    print(f"median |freq shift|={np.median(np.abs(freq_shift)):.3f}Hz")


if __name__ == "__main__":
    main()
