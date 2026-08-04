#!/usr/bin/env python3
"""Per-cycle drift measurement across the full 24h `20260729_live_run_1831-8080` session,
feeding Measurements B (S6) and C (S6b) of the 2026-07-30-2253 Architect ruling.

Reuses `measure_capture_alignment.py`'s already-validated FFT cross-correlation machinery
(read_pcm/ncc_full/refine) rather than reimplementing it -- that tool was built and used for
the 2026-07-25 alignment-replay work and its lag convention is exercised here again.

SIGN CONVENTION -- validated against a synthetic control before trusting real data, per the
explicit instruction in both the ruling (S6.2) and the defect report (S2.1):

  measure_capture_alignment.ncc_full(a, b, ...) finds L maximizing sum_i a[i]*b[i+L], i.e. the
  L for which a[i] ~ b[i+L] -- a (OpenWSFZ) at index i matches b (WSJT-X) at index i+L. If
  L > 0, the same real-world event sits at a SMALLER index in OpenWSFZ's file than WSJT-X's,
  i.e. OpenWSFZ's capture window started LATER in absolute time.

  The defect report defines `lag_seconds = t0_wsjtx - t0_owsfz` (NEGATIVE when OpenWSFZ starts
  later). That is the OPPOSITE sign of this script's raw L. So:

      lag_seconds (defect-report convention) = -L / SAMPLE_RATE

  This is verified below by SELF_TEST() before any real file is touched: a synthetic "OpenWSFZ"
  copy is built by delaying a synthetic "WSJT-X" reference by a KNOWN number of samples (i.e.
  OpenWSFZ starts later, by construction), and the script must recover a NEGATIVE lag_seconds
  of the correct magnitude, or it aborts.

NFR-021: reads only .wav PCM. No ALL.TXT, no message text, no callsigns, ever.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_capture_alignment as mca  # noqa: E402  -- reused, not reimplemented

SAMPLE_RATE = mca.SAMPLE_RATE
ROOT = Path(__file__).resolve().parents[2] / "artefacts" / "20260729_live_run_1831-8080"
OURS_DIR = ROOT / "owsfz" / "wav"
WSJTX_DIR = ROOT / "wsjt-x" / "wav"

LAG_LIMIT = int(6 * SAMPLE_RATE)  # +/- 6 s -- session reaches ~4.4 s drift at worst
STRIDE = 15  # every 15th matched cycle (~1 sample every 3.75 min) -- coarse pass for the
             # full-session curve; specific windows get resampled at STRIDE=1 as needed


def self_test() -> None:
    """Synthetic control: build a coloured-noise 'WSJT-X' signal, delay it by a KNOWN amount
    to build a synthetic 'OpenWSFZ' signal (OpenWSFZ started later, by construction), and
    confirm the recovered lag_seconds is NEGATIVE with the correct magnitude. Aborts the
    whole run (raises) if this does not hold -- per the ruling S6.2 / defect report S2.1
    instruction to validate the convention before trusting real data."""
    rng = np.random.default_rng(20260730)
    n = 180000
    KNOWN_DELAY_SAMPLES = 1000  # OpenWSFZ starts 1000 samples (83.3 ms) later than WSJT-X

    base = rng.standard_normal(n + KNOWN_DELAY_SAMPLES + 2000)
    wsjtx_synth = base[1000:1000 + n]                              # "b"
    owsfz_synth = base[1000 + KNOWN_DELAY_SAMPLES:1000 + KNOWN_DELAY_SAMPLES + n]  # "a", later start

    lags, corr = mca.ncc_full(owsfz_synth, wsjtx_synth, LAG_LIMIT)
    idx = int(np.argmax(corr))
    L = int(lags[idx])
    peak = float(corr[idx])
    lag_seconds = -L / SAMPLE_RATE

    expected_lag_seconds = -KNOWN_DELAY_SAMPLES / SAMPLE_RATE
    print(f"[self-test] known delay = {KNOWN_DELAY_SAMPLES} samples "
          f"({KNOWN_DELAY_SAMPLES/SAMPLE_RATE*1000:.1f} ms), OpenWSFZ starts later (synthetic)")
    print(f"[self-test] recovered raw L = {L} samples, peak corr = {peak:.4f}")
    print(f"[self-test] recovered lag_seconds (defect-report convention) = {lag_seconds:+.4f} s "
          f"(expected {expected_lag_seconds:+.4f} s)")

    assert peak > 0.99, f"self-test peak correlation too low ({peak:.4f}) -- noise construction bug"
    assert L == KNOWN_DELAY_SAMPLES, (
        f"self-test FAILED: recovered raw lag {L} != known delay {KNOWN_DELAY_SAMPLES}. "
        f"Sign/magnitude convention is not validated -- ABORTING, do not trust real-data output.")
    print("[self-test] PASSED -- sign convention confirmed: lag_seconds = -L/SAMPLE_RATE, "
          "negative == OpenWSFZ starts later, matching the defect report's convention.\n")


def cycle_ts_to_seconds(name: str) -> int:
    # name like '260730_064015.wav' or '260730_064015' -- HHMMSS after the underscore
    stem = name[:-4] if name.endswith(".wav") else name
    date_part, time_part = stem.split("_")
    hh, mm, ss = int(time_part[0:2]), int(time_part[2:4]), int(time_part[4:6])
    # This collapses EVERY non-260729 date to a single day offset, so it is correct only for
    # the two-day session ROOT points at. Repointed at any other corpus it would silently
    # return wrong elapsed times (a 3-day run's day 3 would read as day 2), which would
    # corrupt every drift slope computed from them. Fail loudly instead of quietly.
    # For any other corpus use qa/endurance/2026-08-03-drift-screen/drift_screen.py, which
    # takes --corpus and parses full dates.
    assert date_part in ("260729", "260730"), (
        f"cycle_ts_to_seconds() is hardcoded to the 260729->260730 session but got "
        f"'{date_part}'. This script's ROOT is not repointable -- use drift_screen.py.")
    day_offset = 0 if date_part == "260729" else 1  # session spans 260729 -> 260730 only
    return day_offset * 86400 + hh * 3600 + mm * 60 + ss


def main() -> int:
    self_test()

    common = sorted({p.name for p in OURS_DIR.glob("*.wav")} & {p.name for p in WSJTX_DIR.glob("*.wav")})
    print(f"Matched filename pairs available: {len(common)}")
    sampled = common[::STRIDE]
    print(f"Stride {STRIDE} -> sampling {len(sampled)} pairs for the full-session drift curve\n")

    rows = []
    t0 = cycle_ts_to_seconds(sampled[0])
    for i, name in enumerate(sampled):
        a = mca.read_pcm(OURS_DIR / name)
        b = mca.read_pcm(WSJTX_DIR / name)
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
        lags, corr = mca.ncc_full(a, b, min(LAG_LIMIT, n - 1))
        idx = int(np.argmax(corr))
        L = int(lags[idx])
        sub = mca.refine(lags, corr, idx)
        peak = float(corr[idx])
        lag_seconds = -L / SAMPLE_RATE
        lag_seconds_sub = -sub / SAMPLE_RATE
        elapsed = cycle_ts_to_seconds(name) - t0
        rows.append((name[:-4], elapsed, lag_seconds, lag_seconds_sub, peak))
        if i % 50 == 0:
            print(f"  [{i+1}/{len(sampled)}] {name[:-4]}  elapsed={elapsed/3600:6.2f}h  "
                  f"lag={lag_seconds:+.3f}s  peak_corr={peak:.3f}")

    out_path = Path(__file__).resolve().parent / "measurement_bc_drift_curve.csv"
    with open(out_path, "w", encoding="ascii") as fh:
        fh.write("cycle_stem,elapsed_s,lag_seconds,lag_seconds_subsample,peak_corr\n")
        for stem, elapsed, lag_s, lag_sub, peak in rows:
            fh.write(f"{stem},{elapsed},{lag_s:.5f},{lag_sub:.5f},{peak:.4f}\n")
    print(f"\nWrote drift curve: {out_path} ({len(rows)} rows)")

    lag_arr = np.array([r[2] for r in rows])
    elapsed_arr = np.array([r[1] for r in rows]) / 3600.0
    peak_arr = np.array([r[4] for r in rows])
    strong = peak_arr > 0.5
    print(f"\npeak_corr > 0.5: {int(strong.sum())}/{len(rows)}")
    if strong.sum() > 2:
        slope, intercept = np.polyfit(elapsed_arr[strong], lag_arr[strong], 1)
        ppm = slope / 3600.0 / SAMPLE_RATE * 1e6 * SAMPLE_RATE  # slope is s/h already -> ppm = slope(s/h)/3600 *1e6
        ppm = (slope / 3600.0) * 1e6
        print(f"drift regression (locked subset): {slope:+.4f} s/h ({ppm:+.2f} ppm), "
              f"intercept {intercept:+.4f} s")
        # cliff bracket: first elapsed hour where |lag| crosses 2.4s
        cliff_candidates = [(e, l) for e, l, p in zip(elapsed_arr, lag_arr, peak_arr) if p > 0.3]
        crossed = [(e, l) for e, l in cliff_candidates if abs(l) >= 2.4]
        if crossed:
            print(f"first sampled cycle with |lag| >= 2.4s: elapsed={crossed[0][0]:.2f}h, "
                  f"lag={crossed[0][1]:+.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
