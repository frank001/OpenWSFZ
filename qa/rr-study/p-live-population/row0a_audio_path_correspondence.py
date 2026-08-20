#!/usr/bin/env python3
"""P-LIVE ROW 0a -- audio-path correspondence, per corpus.

Spec: qa/rr-study/2026-08-17-1806-architect-to-qa-p-live-population-and-n-series-
replication-spec.md Sec.3 ROW 0a (VALIDITY, load-bearing).

The N-series anchor (WSJT-X's reported freq/dt) and the miss-judgement (our own
ALL.TXT) are read from two different ALL.TXT files, one per leg. If the two legs sat
on different receivers, WSJT-X's frequency does not describe our audio -- and every
downstream N-series statistic on this corpus is *about* anchor accuracy, so a cross-
chain offset would corrupt the whole measurement. This is that check, standalone.

Method reused, not re-derived, from measure_capture_alignment.py (the "method already
proven on this corpus" the spec cites for 08-03's own median |r|=0.987, lag<=34ms
figure): exact-Pearson FFT cross-correlation over the full +/-LAG_LIMIT window, for
EVERY filename-matched WAV pair a corpus offers -- not merely the spec's own >=8-cycle
floor. More pairs is strictly more evidence and the algorithm is cheap enough to
afford the full population (see the per-corpus elapsed_s the report prints).

FIRES per corpus if median |r| < 0.90 OR median |lag_ms| > 50 -- evaluated per corpus,
inheriting no verdict from another (spec: "do NOT inherit 08-03's verdict").

NFR-021: reads WAV PCM only. Filenames are UTC timestamps (ts), never callsigns or
message text -- no ALL.TXT is opened anywhere in this module. Emitted JSON rows carry
only {ts, lag_samples, lag_ms, sub_sample_lag, corr}.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys
import time
import wave

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ARTEFACTS = os.path.join(REPO_ROOT, "artefacts")

SAMPLE_RATE = 12000
LAG_LIMIT = 5 * SAMPLE_RATE  # +/- 5 s, matches the proven method
MIN_OVERLAP_FRAC = 0.5
FIRE_MEDIAN_R = 0.90
FIRE_MEDIAN_LAG_MS = 50.0

# The five corpora spec Sec.1/Sec.6 names for P-LIVE (07-31 excluded -- the genuinely
# hardlinked wsjt-x leg; 07-29 excluded -- pre-drift-fix; both per spec Sec.6).
CORPORA = [
    "20260803_live_run_1713",
    "20260808_live_run_0016-8080",
    "20260808_live_run_0016-8081",
    "20260808_live_run_1154-8080-17m",
    "20260809_live_run_0155-8080-80m",
]


def read_pcm(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        assert w.getframerate() == SAMPLE_RATE, "%s: rate %d" % (path, w.getframerate())
        assert w.getnchannels() == 1, "%s: channels %d" % (path, w.getnchannels())
        assert w.getsampwidth() == 2, "%s: width %d" % (path, w.getsampwidth())
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float64)


def ncc_full(a: np.ndarray, b: np.ndarray, lag_limit: int):
    """Verbatim algorithm from measure_capture_alignment.py:ncc_full -- exact Pearson
    correlation over the overlap window, every integer lag in [-lag_limit, +lag_limit],
    computed via FFT cross-correlation with cumulative-sum per-lag normalisers."""
    n = len(a)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    fa = np.fft.rfft(a, size)
    fb = np.fft.rfft(b, size)
    r_pos = np.fft.irfft(np.conj(fa) * fb, size)[: lag_limit + 1]
    r_neg = np.fft.irfft(np.conj(fb) * fa, size)[: lag_limit + 1]

    ca = np.concatenate(([0.0], np.cumsum(a)))
    caa = np.concatenate(([0.0], np.cumsum(a * a)))
    cb = np.concatenate(([0.0], np.cumsum(b)))
    cbb = np.concatenate(([0.0], np.cumsum(b * b)))

    def pearson(raw, a_lo, a_hi, b_lo, b_hi):
        m = a_hi - a_lo
        sa = ca[a_hi] - ca[a_lo]
        saa = caa[a_hi] - caa[a_lo]
        sb = cb[b_hi] - cb[b_lo]
        sbb = cbb[b_hi] - cbb[b_lo]
        num = raw - sa * sb / m
        den = np.sqrt(np.maximum(saa - sa * sa / m, 0) * np.maximum(sbb - sb * sb / m, 0))
        return np.where(den > 0, num / np.maximum(den, 1e-30), 0.0)

    lags = np.arange(-lag_limit, lag_limit + 1)
    corr = np.zeros(lags.shape, dtype=np.float64)
    ls = np.arange(0, lag_limit + 1)
    corr[lag_limit:] = pearson(r_pos, 0, n - ls, ls, n)
    ms = np.arange(0, lag_limit + 1)
    corr[: lag_limit + 1] = pearson(r_neg, ms, n, 0, n - ms)[::-1]

    keep = (n - np.abs(lags)) >= MIN_OVERLAP_FRAC * n
    corr[~keep] = -2.0
    return lags, corr


def refine(lags, corr, idx):
    """Parabolic sub-sample interpolation around the peak."""
    if idx <= 0 or idx >= len(corr) - 1:
        return float(lags[idx])
    y0, y1, y2 = corr[idx - 1], corr[idx], corr[idx + 1]
    denom = y0 - 2 * y1 + y2
    if denom == 0:
        return float(lags[idx])
    return float(lags[idx]) + 0.5 * (y0 - y2) / denom


def measure_corpus(name: str, sample_every: int = 1) -> dict:
    root = os.path.join(ARTEFACTS, name)
    ours_dir = os.path.join(root, "owsfz", "wav")
    wsjtx_dir = os.path.join(root, "wsjt-x", "wav")
    if not (os.path.isdir(ours_dir) and os.path.isdir(wsjtx_dir)):
        return {"corpus": name, "error": "wav dir(s) missing", "ours_dir": ours_dir,
                "wsjtx_dir": wsjtx_dir}

    ours_names = {f for f in os.listdir(ours_dir) if f.endswith(".wav")}
    wsjtx_names = {f for f in os.listdir(wsjtx_dir) if f.endswith(".wav")}
    common = sorted(ours_names & wsjtx_names)[::sample_every]

    t0 = time.time()
    rows = []
    for fname in common:
        a = read_pcm(os.path.join(ours_dir, fname))
        b = read_pcm(os.path.join(wsjtx_dir, fname))
        n = min(len(a), len(b))
        if n < SAMPLE_RATE:  # <1s of audio -- degenerate, skip
            continue
        a, b = a[:n], b[:n]
        lags, corr = ncc_full(a, b, min(LAG_LIMIT, n - 1))
        idx = int(np.argmax(corr))
        lag = int(lags[idx])
        sub = refine(lags, corr, idx)
        peak = float(corr[idx])
        rows.append({"ts": fname[:-4], "lag_samples": lag,
                     "lag_ms": lag / SAMPLE_RATE * 1000.0,
                     "sub_sample_lag": sub, "corr": peak})
    elapsed = time.time() - t0

    if not rows:
        return {"corpus": name, "error": "no filename-matched pairs", "n_common": len(common)}

    corrs = [r["corr"] for r in rows]
    abs_lags_ms = [abs(r["lag_ms"]) for r in rows]
    median_r = float(st.median(corrs))
    median_abs_lag_ms = float(st.median(abs_lags_ms))
    fires = median_r < FIRE_MEDIAN_R or median_abs_lag_ms > FIRE_MEDIAN_LAG_MS

    return {
        "corpus": name,
        "sample_every": sample_every,
        "n_common_wav_pairs": len(common),
        "n_measured": len(rows),
        "elapsed_s": elapsed,
        "median_abs_corr": median_r,
        "median_abs_lag_ms": median_abs_lag_ms,
        "min_corr": float(min(corrs)),
        "max_corr": float(max(corrs)),
        "corr_gt_0p9_frac": float(sum(1 for c in corrs if c > 0.9) / len(corrs)),
        "fires": fires,
        "rows": rows,
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-every", type=int, default=1,
                     help="use every Nth filename-matched pair (1 = full population)")
    ap.add_argument("--corpus", action="append", default=None,
                     help="restrict to this corpus (repeatable); default = all 5")
    args = ap.parse_args()

    corpora = args.corpus if args.corpus else CORPORA

    print("=" * 90)
    print("P-LIVE ROW 0a -- audio-path correspondence, per corpus")
    print("=" * 90)

    results = {}
    any_fire = False
    for name in corpora:
        print("\n-- %s --" % name)
        r = measure_corpus(name, sample_every=args.sample_every)
        results[name] = r
        if "error" in r:
            print("  ERROR: %s" % r["error"])
            continue
        print("  n_common=%d n_measured=%d (%.1fs)"
              % (r["n_common_wav_pairs"], r["n_measured"], r["elapsed_s"]))
        print("  median |r|=%.4f  median |lag|=%.2fms  min_r=%.4f max_r=%.4f  frac(r>0.9)=%.3f"
              % (r["median_abs_corr"], r["median_abs_lag_ms"], r["min_corr"], r["max_corr"],
                 r["corr_gt_0p9_frac"]))
        verdict = ("FIRES (different chains -- same-leg-only or drop)" if r["fires"]
                   else "clear (single verified path)")
        print("  -> %s" % verdict)
        any_fire = any_fire or r["fires"]

    print("\n" + "=" * 90)
    print("SUMMARY: at least one corpus fires ROW 0a: %s" % any_fire)
    print("=" * 90)

    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "row0a_results.json"), "w",
              encoding="ascii", errors="replace") as fh:
        json.dump({"corpora": results, "any_fire": any_fire}, fh, indent=2, sort_keys=True)
    print("\nWrote results/row0a_results.json")
    return 1 if any_fire else 0


if __name__ == "__main__":
    raise SystemExit(main())
