#!/usr/bin/env python3
"""Full-corpus spectral anomaly scan for an endurance run's cycle-audio WAVs.

STANDARD ROUTINE (Captain's instruction, 2026-09-24): after every endurance run, BEFORE
reading the decode-rate/ANOVA comparison, run this scan over the run's full WAV corpus. It
is step 1 of a three-step pipeline:
    1. spectrum_scan.py          -- this script. Full-corpus anomaly scan -> <out>.json
    2. spectrum_scan_report.py   -- charts + auto spur-resolve + auto hum-control check
    3. render_dossier.py         -- assembles the full HTML dossier (all ANOVA sections +
                                     spectrum scan + spectral trace + HK-036 historical
                                     table), the artifact-quality report Claude publishes.

Reads every 15s cycle WAV in a run's owsfz/wav/ directory in full (no subsampling -- a 24h
corpus at 12kHz mono is ~2GB, a few minutes to scan, tractable). No message text or
callsign is ever read (NFR-021 is not implicated -- audio only, never ALL.TXT here).

Checks: format consistency, clipping, dropouts/silence, saturation/hot spikes, level
stability, sub-passband hum-band power (below the FT8 decode passband -- would catch a
ground-loop/mains-hum artefact from a capture-chain change), and in-band (FT8 passband)
narrowband spur candidates (a >40dB-over-local-median peak -- NOTE: this is also exactly
what a strong, correctly-decoded station's tone looks like, so a candidate here is NOT by
itself an anomaly; spectrum_scan_report.py's spur-resolve step is what tells the two apart,
by cross-referencing against the run's own ALL.TXT).

Origin: built live 2026-09-24 for the 24h direct-USB-CODEC endurance run
(artefacts/20260923_1730_endurance_run-gathered), generalised into standing tooling per the
Captain's instruction the same day. See qa/rr-study/gap-census-a/wav_spectrum.py for a
narrower, single-purpose precedent (ROW 0f's sub-f_min band check) -- this script is the
general-purpose successor for endurance runs, not a replacement for that one.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import wave

import numpy as np

FS_EXPECT = 12000
CLIP_THRESH = 32760  # int16 full scale is 32767/-32768

# Bands, in Hz, evaluated on the rfft of each cycle WAV.
FT8_BAND = (200.0, 2900.0)          # the audio passband FT8 content lives in
HUM_FUND = (45.0, 65.0)             # 50/60 Hz mains fundamental
HUM_H2 = (95.0, 125.0)              # 2nd harmonic
NOISE_FLOOR_HZ = (5000.0, 5900.0)   # near-Nyquist bucket, matches gap-census-a convention

# Anomaly-flag thresholds (HK-021: predicate as code, not prose).
SILENCE_BELOW_MEDIAN_DB = 20.0   # dropout candidate
HOT_ABOVE_MEDIAN_DB = 20.0       # saturation/hot-spike candidate (non-clipped)
HUM_OVER_FLOOR_FLAG_DB = 20.0    # hum band this far over the floor bucket = flagged
SPUR_OVER_LOCAL_MEDIAN_DB = 40.0  # in-band peak this far above local median = spur candidate

NAME_RE = re.compile(r"^(\d{6})_(\d{6})\.wav$")


def parse_ts(fname: str) -> str | None:
    m = NAME_RE.match(fname)
    if not m:
        return None
    d, t = m.groups()
    return f"20{d[0:2]}-{d[2:4]}-{d[4:6]}T{t[0:2]}:{t[2:4]}:{t[4:6]}Z"


def band_power_db(freqs: np.ndarray, power: np.ndarray, lo: float, hi: float, eps: float = 1e-9) -> float:
    mask = (freqs >= lo) & (freqs < hi)
    if not mask.any():
        return float("nan")
    return float(10.0 * np.log10(power[mask].mean() + eps))


def analyse_file(path: str) -> dict:
    with wave.open(path, "rb") as w:
        nch, sw, fs, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    if nch != 1 or sw != 2:
        return {"error": "unexpected format", "nch": nch, "sw": sw}
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if x.size == 0:
        return {"error": "empty"}

    peak = float(np.max(np.abs(x)))
    clip_frac = float(np.mean(np.abs(x) >= CLIP_THRESH))
    dc = float(np.mean(x))
    rms = float(np.sqrt(np.mean(x * x)))
    dbfs = float(20.0 * np.log10(rms / 32768.0)) if rms > 0 else -999.0

    window = np.hanning(len(x))
    xw = (x - dc) * window
    spec = np.fft.rfft(xw)
    power = (spec.real ** 2 + spec.imag ** 2)
    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)

    floor_db = band_power_db(freqs, power, *NOISE_FLOOR_HZ)
    ft8_db = band_power_db(freqs, power, *FT8_BAND)
    hum1_db = band_power_db(freqs, power, *HUM_FUND)
    hum2_db = band_power_db(freqs, power, *HUM_H2)

    mask = (freqs >= FT8_BAND[0]) & (freqs < FT8_BAND[1])
    band_p = power[mask]
    band_f = freqs[mask]
    if band_p.size:
        med = np.median(band_p) + 1e-9
        peak_idx = int(np.argmax(band_p))
        peak_to_med_db = float(10.0 * np.log10(band_p[peak_idx] / med))
        peak_freq = float(band_f[peak_idx])
    else:
        peak_to_med_db = float("nan")
        peak_freq = float("nan")

    return {
        "fs": fs, "nframes": nframes,
        "peak": peak, "clip_frac": clip_frac,
        "dc": dc, "rms": rms, "dbfs": dbfs,
        "floor_db": floor_db, "ft8_band_db": ft8_db,
        "hum1_db": hum1_db, "hum2_db": hum2_db,
        "hum1_over_floor_db": hum1_db - floor_db,
        "hum2_over_floor_db": hum2_db - floor_db,
        "peak_to_med_db": peak_to_med_db, "peak_freq_hz": peak_freq,
    }


def scan(wav_dir: str, progress: bool = True) -> tuple[list[dict], dict]:
    files = sorted(f for f in os.listdir(wav_dir) if f.lower().endswith(".wav"))
    n = len(files)
    if progress:
        print(f"Found {n} WAV files in {wav_dir}", file=sys.stderr)

    rows = []
    for i, fn in enumerate(files):
        ts = parse_ts(fn)
        path = os.path.join(wav_dir, fn)
        try:
            r = analyse_file(path)
        except Exception as e:
            r = {"error": f"{type(e).__name__}: {e}"}
        r["file"] = fn
        r["ts"] = ts
        rows.append(r)
        if progress and (i + 1) % 1000 == 0:
            print(f"  ...{i+1}/{n}", file=sys.stderr)

    good = [r for r in rows if "error" not in r]
    errors = [r for r in rows if "error" in r]

    dbfs = np.array([r["dbfs"] for r in good]) if good else np.array([])
    fs_vals = set(r["fs"] for r in good)
    nframes_vals = set(r["nframes"] for r in good)
    hum1_over = np.array([r["hum1_over_floor_db"] for r in good]) if good else np.array([])
    hum2_over = np.array([r["hum2_over_floor_db"] for r in good]) if good else np.array([])

    med_dbfs = float(np.median(dbfs)) if dbfs.size else float("nan")

    clipping_files = [r["file"] for r in good if r["clip_frac"] > 0.0]
    silence_thresh_db = med_dbfs - SILENCE_BELOW_MEDIAN_DB
    silent_files = [r for r in good if r["dbfs"] < silence_thresh_db]
    hot_thresh_db = med_dbfs + HOT_ABOVE_MEDIAN_DB
    hot_files = [r for r in good if r["dbfs"] > hot_thresh_db and r["clip_frac"] == 0.0]
    hum_files = [r for r in good if r["hum1_over_floor_db"] > HUM_OVER_FLOOR_FLAG_DB
                 or r["hum2_over_floor_db"] > HUM_OVER_FLOOR_FLAG_DB]
    spur_files = [r for r in good if r["peak_to_med_db"] > SPUR_OVER_LOCAL_MEDIAN_DB]

    from collections import Counter
    spur_bins = Counter(int(round(r["peak_freq_hz"] / 5.0) * 5) for r in spur_files)
    top_spur_bins = spur_bins.most_common(10)

    format_ok = (fs_vals == {FS_EXPECT}) and (len(nframes_vals) <= 2)

    summary = {
        "wav_dir": wav_dir,
        "n_files": n, "n_ok": len(good), "n_errors": len(errors),
        "errors": errors[:20],
        "format_fs_values": sorted(fs_vals),
        "format_nframes_values": sorted(nframes_vals),
        "format_consistent": format_ok,
        "dbfs_median": med_dbfs,
        "dbfs_mad": float(np.median(np.abs(dbfs - med_dbfs))) if dbfs.size else float("nan"),
        "dbfs_min": float(np.min(dbfs)) if dbfs.size else float("nan"),
        "dbfs_max": float(np.max(dbfs)) if dbfs.size else float("nan"),
        "clipping_file_count": len(clipping_files),
        "clipping_files_sample": clipping_files[:20],
        "silence_thresh_db": silence_thresh_db,
        "silent_file_count": len(silent_files),
        "silent_files_sample": [(r["file"], r["ts"], r["dbfs"]) for r in silent_files[:20]],
        "hot_thresh_db": hot_thresh_db,
        "hot_file_count": len(hot_files),
        "hot_files_sample": [(r["file"], r["ts"], r["dbfs"]) for r in hot_files[:20]],
        "hum_thresh_db": HUM_OVER_FLOOR_FLAG_DB,
        "hum_file_count": len(hum_files),
        "hum1_over_floor_median_db": float(np.median(hum1_over)) if hum1_over.size else float("nan"),
        "hum2_over_floor_median_db": float(np.median(hum2_over)) if hum2_over.size else float("nan"),
        "spur_thresh_db": SPUR_OVER_LOCAL_MEDIAN_DB,
        "spur_file_count": len(spur_files),
        "top_spur_frequency_bins_hz": top_spur_bins,
        "bands_hz": {"ft8": FT8_BAND, "hum_fund": HUM_FUND, "hum_h2": HUM_H2, "floor": NOISE_FLOOR_HZ},
    }
    return rows, summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wav-dir", required=True, help="Run's owsfz/wav/ cycle-audio directory")
    ap.add_argument("--out-json", required=True, help="Path to write the full scan (summary + per-file rows)")
    args = ap.parse_args()

    rows, summary = scan(args.wav_dir)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f)
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {args.out_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
