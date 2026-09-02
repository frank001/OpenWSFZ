#!/usr/bin/env python3
"""ROW 0c level-preserving re-render -- AWGN-FP arm, QA follow-up finding.

**Why this file exists (do not delete without reading this):**

The first ROW 0c attempt reused ``harness/run_scenario.py --dry-run --dump-wav-dir`` directly
(the obvious, "reuse the shipped generator" path) against two scratch scenario files whose only
change from ``scenarios/s5-noise.json`` was ``level_dbfs`` shifted +/-10 dB. That run produced
event counts identical to the baseline (6/6, both in [2,10]) -- which looked like a clean
"level_dependent=False" ROW 0c PASS, but is not a valid result: ``run_scenario.py``'s main loop
peak-normalises EVERY rendered slot to a fixed 0.9 peak amplitude (``_PLAYBACK_PEAK_LEVEL``)
*before* either live playback or ``--dump-wav-dir`` write out, purely to keep PortAudio from
clipping. For a pure-AWGN buffer this is not a cosmetic step: peak-normalising a Gaussian noise
buffer to a fixed target peak is *algebraically independent of the buffer's original amplitude*
(peak = amplitude x max(|standard_normal_draw|); normalising by 0.9/peak cancels the amplitude
term exactly, up to floating-point rounding) -- so the resulting delivered noise level is the
same for EVERY ``level_dbfs`` value, for the SAME seed. Measured directly: S5 part 0
(-20 dBFS nominal) and part 1 (-10 dBFS nominal) -- a supposed 10 dB gap the scenario file has
declared since 2026-06-20 -- deliver -20.47..-22.23 dBFS and -20.96..-22.4 dBFS RMS respectively
in the SAME baseline render: NOT 10 dB apart. This is not specific to the offline path; the
identical normalisation runs before live hardware playback too (same code, same call site,
unconditional) -- it is a pre-existing property of the shared S5 rendering path, not a defect this
arm's offline replay introduced. Out of scope to fix here (a ``qa/rr-study/harness/`` change is
its own change, not this arm's ROW 0 sizing question) -- flagged to the Architect/PO in this arm's
report instead.

**What this script does differently:** calls the SAME shipped ``harness.run_scenario._render_noise``
(identical RNG, identical ``amplitude = 10**(level_dbfs/20)`` formula -- not a second noise source)
directly, then downsamples 48kHz -> 12kHz with the SAME polyphase filter
``harness.run_scenario._dump_slot_wav`` uses, but WITHOUT the intervening peak-normalise-to-0.9
step -- so the delivered WAV actually carries the level_dbfs difference the scenario intends.
Clipping at +/-1.0 (int16 full scale) before quantising is kept, matching ``_dump_slot_wav``'s own
clip -- a real receiver's ADC would clip a 0 dBFS AWGN buffer's peaks too, so this is not a new
behaviour, just no longer masked by renormalisation.

Usage:
    python render_row0c_level_preserving.py
Writes three 60-slot WAV populations under ``_work/row0c_lp_{baseline,minus10,plus10}/`` using the
real ``scenarios/s5-noise.json`` seeds (parts 0/1, compute_seed('S5', part_index, trial_index)) at
level_dbfs {-20/-10} (baseline), {-30/-20} (minus10), {-10/0} (plus10).
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

_HERE = pathlib.Path(__file__).parent.resolve()
_QA_ROOT = _HERE.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import compute_seed          # noqa: E402
from harness.run_scenario import _render_noise    # noqa: E402  (reused verbatim, not reimplemented)
from synth.constants import DEFAULT_SAMPLE_RATE_HZ, SLOT_LENGTH_S  # noqa: E402

_DUMP_SAMPLE_RATE_HZ = 12_000
_DUMP_SLOT_SAMPLES = int(_DUMP_SAMPLE_RATE_HZ * SLOT_LENGTH_S)  # 180 000

_SCENARIO_ID = "S5"
_TRIALS = 30

# (label, part0_level_dbfs, part1_level_dbfs)
_CONDITIONS = [
    ("row0c_lp_baseline", -20, -10),   # matches scenarios/s5-noise.json exactly
    ("row0c_lp_minus10", -30, -20),    # baseline - 10 dB
    ("row0c_lp_plus10", -10, 0),       # baseline + 10 dB
]


def _dump_unnormalised(out_dir: pathlib.Path, part_index: int, trial_index: int,
                        seed: int, samples_48k: np.ndarray) -> None:
    """Downsample + quantise WITHOUT the peak-renormalise-to-0.9 step. Mirrors
    harness.run_scenario._dump_slot_wav's resample/clip/quantise exactly; the only
    deliberate difference is the missing normalisation call before this function."""
    out_dir.mkdir(parents=True, exist_ok=True)
    twelve = resample_poly(np.asarray(samples_48k, dtype="float64"), up=1, down=4)
    if len(twelve) < _DUMP_SLOT_SAMPLES:
        twelve = np.concatenate([twelve, np.zeros(_DUMP_SLOT_SAMPLES - len(twelve))])
    elif len(twelve) > _DUMP_SLOT_SAMPLES:
        twelve = twelve[:_DUMP_SLOT_SAMPLES]
    clipped = np.clip(twelve, -1.0, 1.0)
    pcm16 = np.round(clipped * 32767.0).astype("<i2")
    name = f"{_SCENARIO_ID}_p{part_index:03d}_t{trial_index:03d}_s{seed}.wav"
    wavfile.write(str(out_dir / name), _DUMP_SAMPLE_RATE_HZ, pcm16)


def main() -> None:
    for label, level_p0, level_p1 in _CONDITIONS:
        out_dir = _HERE / "_work" / label
        parts = [
            {"part_index": 0, "noise_type": "awgn", "level_dbfs": level_p0},
            {"part_index": 1, "noise_type": "awgn", "level_dbfs": level_p1},
        ]
        n_written = 0
        for part in parts:
            for trial_index in range(_TRIALS):
                seed = compute_seed(_SCENARIO_ID, part["part_index"], trial_index)
                samples = _render_noise(part, seed)
                _dump_unnormalised(out_dir, part["part_index"], trial_index, seed, samples)
                n_written += 1
        print(f"{label}: wrote {n_written} slots (part0={level_p0} dBFS, part1={level_p1} dBFS) -> {out_dir}")


if __name__ == "__main__":
    main()
