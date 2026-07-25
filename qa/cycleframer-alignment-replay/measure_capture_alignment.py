#!/usr/bin/env python3
"""Full-range FFT cross-correlation of OpenWSFZ vs WSJT-X cycle WAVs.

Supersedes compare_raw_audio.py's +/-600-sample (+/-50 ms) brute-force lag search, which
was truncating: the locked subset's lags already reached -524 with 19/57 unlocked pairs
reporting |lag| > 500 and one pair hitting the wall exactly.

Differences vs. the 21:00 script:
  1. Lag search covers +/- LAG_LIMIT samples (default 5 s) instead of +/- 50 ms, via FFT
     cross-correlation -- O(N log N) instead of O(N * lags), so wider AND faster.
  2. Exact Pearson correlation over the *overlap window* at each lag (per-lag means and
     energies via cumulative sums), instead of one global normalizer. The global normalizer
     was harmless at 0.33% overlap loss but is badly wrong once lags reach seconds.
  3. Sub-sample lag refinement by parabolic interpolation of the correlation peak.
  4. Reports frame counts explicitly for every pair rather than only on mismatch.

NFR-021: reads only .wav PCM. No ALL.TXT, no message text, no callsigns.
"""
import sys
import wave
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2] / "artefacts" / "20260725_live_run_1806"
OURS_DIR = ROOT / "owsfz" / "wav"
WSJTX_DIR = ROOT / "wsjt-x" / "wav"

SAMPLE_RATE = 12000
LAG_LIMIT = 5 * SAMPLE_RATE      # +/- 5 s
MIN_OVERLAP_FRAC = 0.5           # ignore lags leaving < 50% overlap (normalizer gets noisy)


def read_pcm(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SAMPLE_RATE, f"{path}: rate {w.getframerate()}"
        assert w.getnchannels() == 1, f"{path}: channels {w.getnchannels()}"
        assert w.getsampwidth() == 2, f"{path}: width {w.getsampwidth()}"
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float64)


def rms_dbfs(x: np.ndarray) -> float:
    return 20.0 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12 / 32768.0)


def ncc_full(a: np.ndarray, b: np.ndarray, lag_limit: int):
    """Exact normalized cross-correlation over the overlap window, for every integer lag
    in [-lag_limit, +lag_limit]. Convention matches the 21:00 script: at lag L >= 0 we
    compare a[0:N-L] against b[L:N]; at L < 0 we compare a[-L:N] against b[0:N+L].
    Returns (lags, corr)."""
    n = len(a)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    fa = np.fft.rfft(a, size)
    fb = np.fft.rfft(b, size)
    # r_pos[L] = sum_i a[i] * b[i+L]  (L >= 0)
    r_pos = np.fft.irfft(np.conj(fa) * fb, size)[: lag_limit + 1]
    # r_neg[M] = sum_i a[i+M] * b[i]  (M >= 0)
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


def main() -> int:
    common = sorted({p.name for p in OURS_DIR.glob("*.wav")} & {p.name for p in WSJTX_DIR.glob("*.wav")})
    print(f"filename-matched pairs: {len(common)}   lag search: +/-{LAG_LIMIT} samples "
          f"(+/-{LAG_LIMIT/SAMPLE_RATE:.1f} s)")
    print()
    print(f"{'file':<16} {'n_ours':>7} {'n_wsjt':>7} {'lag_smp':>9} {'lag_ms':>10} "
          f"{'sub_smp':>9} {'corr':>7} {'mod120':>7}")

    rows = []
    for name in common:
        a = read_pcm(OURS_DIR / name)
        b = read_pcm(WSJTX_DIR / name)
        na, nb = len(a), len(b)
        n = min(na, nb)
        a, b = a[:n], b[:n]
        lags, corr = ncc_full(a, b, min(LAG_LIMIT, n - 1))
        idx = int(np.argmax(corr))
        lag = int(lags[idx])
        sub = refine(lags, corr, idx)
        peak = float(corr[idx])
        rows.append((name, na, nb, lag, sub, peak))
        print(f"{name[:-4]:<16} {na:7d} {nb:7d} {lag:9d} {lag/12.0:10.3f} "
              f"{sub:9.3f} {peak:7.3f} {lag % 120:7d}")

    lag_arr = np.array([r[3] for r in rows], dtype=float)
    sub_arr = np.array([r[4] for r in rows], dtype=float)
    corr_arr = np.array([r[5] for r in rows], dtype=float)

    print()
    print("--- summary ---")
    print(f"pairs: {len(rows)}")
    for thr in (0.9, 0.7, 0.5):
        print(f"  peak corr > {thr}: {int(np.sum(corr_arr > thr))} / {len(rows)}")
    print(f"peak corr: mean={corr_arr.mean():.3f} median={np.median(corr_arr):.3f} "
          f"min={corr_arr.min():.3f} max={corr_arr.max():.3f}")

    strong = corr_arr > 0.9
    if strong.any():
        s = lag_arr[strong]
        print()
        print(f"locked pairs (corr>0.9): {int(strong.sum())}")
        print(f"  lag samples: min={s.min():.0f} max={s.max():.0f} "
              f"mean={s.mean():.1f} stdev={s.std():.1f}")
        print(f"  lag ms:      min={s.min()/12:.3f} max={s.max()/12:.3f}")
        residues = np.mod(s, 120)
        uniq, counts = np.unique(residues, return_counts=True)
        print(f"  lag mod 120 (10 ms grid) residues: {dict(zip(uniq.astype(int), counts))}")
        print(f"  on-grid fraction: {int(np.sum(residues == residues[0]))}/{int(strong.sum())}")
        print(f"  sub-sample refined residual (mod 120): "
              f"mean={np.mod(sub_arr[strong], 120).mean():.3f}")

        # drift regression: lag vs. elapsed seconds within the session
        def secs(nm):
            hh, mm, ss = int(nm[7:9]), int(nm[9:11]), int(nm[11:13])
            return hh * 3600 + mm * 60 + ss
        t = np.array([secs(r[0]) for r in rows], dtype=float)[strong]
        t = t - t.min()
        if len(t) > 2:
            slope, intercept = np.polyfit(t, s, 1)
            resid = s - (slope * t + intercept)
            print()
            print(f"  drift regression (lag samples vs elapsed s), locked subset:")
            print(f"    slope = {slope:+.5f} samples/s  = {slope/12*1000:+.3f} ms per 1000 s")
            print(f"    implied clock-rate error = {slope/SAMPLE_RATE*1e6:+.2f} ppm")
            print(f"    residual stdev = {resid.std():.1f} samples ({resid.std()/12:.2f} ms)")
            if resid.std() > 0.5 * s.std():
                print("    NOTE: residual stdev is comparable to the raw spread -- the lag is")
                print("          NOT a linear drift (it is a sawtooth: ramp + periodic reset),")
                print("          so this slope is meaningless. See the per-cycle table.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
