"""F-NBR-A Part C (descriptive, NOT gated) -- is station E causally responsible
for F's loss, and how wide is the exclusion zone?

All three sub-parts use the UNMODIFIED PRODUCTION DECODER (ft8_decode_all) on
regenerated audio -- no forced positions, unlike Part A. A trial counts as
"F recovered" iff ft8_decode_all's result set contains a decode within
FREQ_TOLERANCE_HZ (matcher.py's own 4.0 Hz convention) of F's current
frequency, AND whose message text exactly (whitespace-normalised) equals F's
message. Both conditions matter: HK-026/scope discipline -- a text-only match
at the wrong frequency, or a frequency-only match with garbled text, is not a
station-F recovery.

Seed convention (implementation-only, not a gated methodology choice, spelled
out here per HK-021 identifiability): compute_seed('S8HN', part_index, trial)
with a distinct part_index per swept condition, so no two conditions share a
noise draw:
  part_index=0    -- unmodified scene (Part A's own baseline; C1's "with E")
  part_index=101  -- C1 ablation (station E removed)
  part_index=201..207 -- C2 separation sweep, one per Delta in
                     {6.25, 12, 18.75, 25, 31.25, 50, 100} Hz, in that order
  part_index=301..304 -- C3 level sweep, one per F SNR in
                     {-2, -5, -8, -11} dB, in that order
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_QA_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if _QA_ROOT not in sys.path:
    sys.path.insert(0, _QA_ROOT)

import dll_common as DC  # noqa: E402
import scene_render as SR  # noqa: E402
from harness.matcher import FREQ_TOLERANCE_HZ, _text_matches  # noqa: E402

N_TRIALS = 100
C2_DELTAS_HZ = [6.25, 12.0, 18.75, 25.0, 31.25, 50.0, 100.0]
C3_SNRS_DB = [-2.0, -5.0, -8.0, -11.0]


def _f_recovered(results, target_freq_hz: float, target_message: str) -> bool:
    if not results:
        return False
    return any(
        abs(r["freq_hz"] - target_freq_hz) <= FREQ_TOLERANCE_HZ
        and _text_matches(r["message"], target_message)
        for r in results
    )


def _run_condition(dec, signals, part_index: int, target_freq_hz: float, log_prefix: str, log):
    hits = 0
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, part_index)
        pcm = SR.render_scene(signals, seed)
        results = dec.decode_all(pcm)
        if _f_recovered(results, target_freq_hz, SR.F_TRUE_MESSAGE):
            hits += 1
    log("%s: %d/%d" % (log_prefix, hits, N_TRIALS))
    return hits


def run_c1(dec, log) -> dict:
    full_signals = SR.load_s8hn_signals()
    ablated_signals = SR.remove_station(full_signals, SR.STATION_E)

    r_baseline = _run_condition(dec, full_signals, 0, SR.F_TRUE_FREQ_HZ,
                                 "C1 baseline (E present)", log)
    r_ablate = _run_condition(dec, ablated_signals, 101, SR.F_TRUE_FREQ_HZ,
                               "C1 ablation (E removed)", log)
    return {"n_trials": N_TRIALS, "r_baseline": r_baseline, "r_ablate": r_ablate}


def run_c2(dec, log) -> dict:
    full_signals = SR.load_s8hn_signals()
    rows = []
    for i, delta in enumerate(C2_DELTAS_HZ):
        part_index = 201 + i
        new_freq = SR.E_FREQ_HZ + delta
        signals = SR.move_station_freq(full_signals, SR.STATION_F, new_freq)
        hits = _run_condition(dec, signals, part_index, new_freq,
                               "C2 delta=%.2fHz (F at %.2fHz)" % (delta, new_freq), log)
        rows.append({"delta_hz": delta, "f_freq_hz": new_freq, "hits": hits, "n_trials": N_TRIALS})
    return {"rows": rows}


def run_c3(dec, log) -> dict:
    full_signals = SR.load_s8hn_signals()
    rows = []
    for i, snr in enumerate(C3_SNRS_DB):
        part_index = 301 + i
        signals = SR.set_station_snr(full_signals, SR.STATION_F, snr)
        hits = _run_condition(dec, signals, part_index, SR.F_TRUE_FREQ_HZ,
                               "C3 snr_F=%.1fdB" % snr, log)
        rows.append({"snr_f_db": snr, "hits": hits, "n_trials": N_TRIALS})
    return {"rows": rows}


def run_part_c(dec, log) -> dict:
    return {
        "c1": run_c1(dec, log),
        "c2": run_c2(dec, log),
        "c3": run_c3(dec, log),
    }


if __name__ == "__main__":
    def _log(msg):
        print(msg)
    dec = DC.load_decoder()
    result = run_part_c(dec, _log)
    print(result)
