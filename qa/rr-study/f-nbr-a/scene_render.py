"""F-NBR-A: deterministic offline S8HN scene rendering at the decoder's native
12 kHz rate.

Reuses harness.run_scenario._render_band_scene's own BODY verbatim (HK-018) --
same station loop (encode clean, scale via mix_to_shared_floor's snr_db, one
shared seeded AWGN floor) -- but parameterised to DECODE_SAMPLE_RATE_HZ = 12000
instead of synth.constants.DEFAULT_SAMPLE_RATE_HZ = 48000. This is NOT a novel
construction: it is the exact pattern already established by
qa/rr-study/r2-coherent-llr-instrument/ac_n5_dt_stratified_measurement.py's
run_s8() (see that module's own "RATE CORRECTION" docstring paragraph) and by
row0g_instrument_gain_check.py's _run_clean_trials before it. _render_band_scene
itself cannot be called unmodified here for the same reason ac_n5 could not:
it hardcodes the 48 kHz playback rate, which produces a 720,000-sample buffer
ft8_decode_all (fixed 180,000 samples @ 12 kHz) cannot consume.

Provides scene-mutation helpers (remove_station / move_station_freq /
set_station_snr) for Part C's ablation and sweeps -- pure list-of-dict edits,
no rendering logic duplicated a second time.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_QA_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
if _QA_ROOT not in sys.path:
    sys.path.insert(0, _QA_ROOT)

from harness.common import compute_seed  # noqa: E402

SCENARIOS_DIR = Path(_QA_ROOT) / "scenarios"
S8HN_PATH = SCENARIOS_DIR / "s8hn-band-scene-highn.json"

DECODE_SAMPLE_RATE_HZ = 12_000   # ft8_decode_all's own native rate; see module docstring
NOISE_CUTOFF_HZ = 4700.0         # identical to run_scenario.py's own _NOISE_CUTOFF_HZ
BUFFER_SAMPLES = 180_000

STATION_F = "F"
STATION_E = "E"
F_TRUE_FREQ_HZ = 1162.0
F_TRUE_MESSAGE = "Q1ABC Q1AW RR73"
E_FREQ_HZ = 1150.0
E_SNR_DB = -5.0


def load_s8hn_signals() -> list[dict]:
    """Load S8HN's 'signals' array verbatim (list of station dicts)."""
    data = json.loads(S8HN_PATH.read_text(encoding="utf-8"))
    assert data["id"] == "S8HN", data.get("id")
    return copy.deepcopy(data["signals"])


def remove_station(signals: list[dict], station: str) -> list[dict]:
    out = [s for s in signals if s.get("station") != station]
    assert len(out) == len(signals) - 1, "expected exactly one station %r removed" % station
    return out


def move_station_freq(signals: list[dict], station: str, new_freq_hz: float) -> list[dict]:
    out = copy.deepcopy(signals)
    hit = 0
    for s in out:
        if s.get("station") == station:
            s["freq_hz"] = float(new_freq_hz)
            hit += 1
    assert hit == 1, "expected exactly one station %r" % station
    return out


def set_station_snr(signals: list[dict], station: str, new_snr_db: float) -> list[dict]:
    out = copy.deepcopy(signals)
    hit = 0
    for s in out:
        if s.get("station") == station:
            s["snr_db"] = float(new_snr_db)
            hit += 1
    assert hit == 1, "expected exactly one station %r" % station
    return out


def render_scene(signals: list[dict], seed: int):
    """Mirrors _render_band_scene's own body exactly (encode each station clean,
    scale/sum/single-shared-floor via mix_to_shared_floor), parameterised to the
    decoder's native 12 kHz rate instead of the 48 kHz playback rate. Returns a
    (BUFFER_SAMPLES,) float64 ndarray."""
    from synth import channel, encoder  # noqa: PLC0415 -- lazy per this programme's own convention

    if not signals:
        raise ValueError("empty signals list")

    clean_signals = []
    snr_list: list[float] = []
    for s in signals:
        clean_signals.append(encoder.encode_message(
            s["message_text"], base_freq_hz=float(s["freq_hz"]), dt_s=float(s["dt_s"]),
            snr_db=None, sample_rate_hz=DECODE_SAMPLE_RATE_HZ))
        snr_list.append(float(s["snr_db"]))

    samples = channel.mix_to_shared_floor(
        clean_signals, snr_list, seed, sample_rate_hz=DECODE_SAMPLE_RATE_HZ,
        noise_cutoff_hz=NOISE_CUTOFF_HZ)
    if len(samples) != BUFFER_SAMPLES:
        raise ValueError("scene produced %d samples, expected %d" % (len(samples), BUFFER_SAMPLES))
    return samples


def trial_seed(trial_index: int, part_index: int = 0) -> int:
    """compute_seed('S8HN', part_index, trial_index) -- part_index 0 for the
    unmodified scene (Part A, ROW 0b/0c, C1 baseline+ablation); Part C's sweeps
    (C2/C3) use a distinct part_index per swept condition so no condition shares
    a noise draw with another (an implementation-only convention, not a gated
    methodology choice -- disclosed in the report)."""
    return compute_seed("S8HN", part_index, trial_index)
