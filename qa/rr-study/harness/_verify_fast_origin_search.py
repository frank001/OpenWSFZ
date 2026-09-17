"""Verifies e4_stage2_census_b5.locate_origin()'s fast path is numerically
identical to calling synth.estimator.extract_channel_gains() directly at every
grid point (the slow, unoptimised, already-trusted path used by the earlier
b5_02/b5_04 ad-hoc scripts). Numbers only (NFR-021).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_QA_ROOT))
sys.path.insert(0, str(_QA_ROOT / "live-gap-now"))

from synth.constants import NUM_SYMBOLS  # noqa: E402
from synth.estimator import extract_channel_gains  # noqa: E402
from synth.wavio import read_wav  # noqa: E402
from harness.e4_stage2_census_b5 import (  # noqa: E402
    COSTAS_IDX, _COSTAS_TONES, locate_origin, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS,
)

R = "D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/"


def load(p):
    rows = {}
    for ln in open(p, encoding="utf-8", errors="replace"):
        f = ln.split()
        if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
            continue
        try:
            snr = float(f[4]); dt = float(f[5]); fr = float(f[6])
        except ValueError:
            continue
        rows.setdefault((f[0], " ".join(f[7:]).strip()), (snr, dt, fr))
    return rows


w = load(R + "wsjtx-1-ft991a/ALL.TXT")
keys = sorted(k for k in w if k[0] >= "260908_193645" and w[k][0] >= 10.0)
sample = [keys[i] for i in (5, 50, 150, 300, 450)]

worst_power_reldiff = 0.0
worst_dt_diff = 0.0
worst_freq_diff = 0.0

for (ts, msg) in sample:
    snr, dtw, frw = w[(ts, msg)]
    audio, fs = read_wav(R + "cycle-audio/%s.wav" % ts)

    fast = locate_origin(audio, fs, frw, dtw, NARROW_DT_OFFSETS, NARROW_FREQ_OFFSETS)
    assert fast is not None
    dt_star_fast, freq_star_fast, p_fast, sharp_fast = fast

    best_slow = None
    for ddt in NARROW_DT_OFFSETS:
        dt = dtw + ddt
        if dt < 0 or dt > 2.36:
            continue
        for df in NARROW_FREQ_OFFSETS:
            g = extract_channel_gains(np.asarray(audio, dtype=np.float64), _COSTAS_TONES,
                                       frw + df, dt_s=dt, sample_rate_hz=fs)
            p = float(np.sum(np.abs(g[COSTAS_IDX]) ** 2))
            if best_slow is None or p > best_slow[0]:
                best_slow = (p, dt, frw + df)

    p_slow, dt_star_slow, freq_star_slow = best_slow
    reldiff = abs(p_fast - p_slow) / p_slow if p_slow > 0 else abs(p_fast - p_slow)
    dt_diff = abs(dt_star_fast - dt_star_slow)
    freq_diff = abs(freq_star_fast - freq_star_slow)
    worst_power_reldiff = max(worst_power_reldiff, reldiff)
    worst_dt_diff = max(worst_dt_diff, dt_diff)
    worst_freq_diff = max(worst_freq_diff, freq_diff)
    print(f"{ts}: fast best_power={p_fast:.10g} @ dt={dt_star_fast:.2f} f={freq_star_fast:.2f}  "
          f"slow best_power={p_slow:.10g} @ dt={dt_star_slow:.2f} f={freq_star_slow:.2f}  "
          f"reldiff={reldiff:.2e}")

print(f"\nworst power reldiff={worst_power_reldiff:.2e}  worst dt diff={worst_dt_diff:.4f} "
      f"worst freq diff={worst_freq_diff:.4f}")
assert worst_power_reldiff < 1e-9, "fast path power does not match slow path"
assert worst_dt_diff == 0.0, "fast path picked a different dt* than the slow grid search"
assert worst_freq_diff == 0.0, "fast path picked a different freq* than the slow grid search"
print("PASS: fast origin search is numerically identical to the slow reference on all 5 rows.")
