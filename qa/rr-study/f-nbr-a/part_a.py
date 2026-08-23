"""F-NBR-A Part A (PRIMARY, gated) -- the locus split for station F.

N=100 trials, trial_index=0..99, seed = compute_seed('S8HN', 0, trial_index).
For each trial: regenerate the full unmodified 12-station scene, force-extract
LLRs at F's exact position (freq_hz=1162.0), decode through production's own
LDPC/OSD/CRC path, and check the recovered payload against the true encoding
of "Q1ABC Q1AW RR73".

DISCLOSED CORRECTION (see dll_common.py's own comment, and ROW 0c): time_offset_s
passed to ft8_extract_llrs_at is dt_true + SYMBOL_PERIOD_S (0.16s), not the
literal dt_true=0.0 the spec's prose names -- the confirmed one-symbol
waterfall-origin displacement (B-orig-A, 2026-08-21). Applying the spec's
literal 0.0 makes ROW 0c's own positive controls (station A, station E) fail
0/25, which would make ANY Part A result -- including a real one -- read as an
uninterpretable instrument failure. This correction is what makes ROW 0c pass
24-25/25 for both controls.
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
from row0 import _forced_success  # noqa: E402 -- reused verbatim, same forced-position pipeline

N_TRIALS = 100


def run_part_a(dec, log) -> dict:
    signals = SR.load_s8hn_signals()
    successes = 0
    faults = 0
    per_trial = []
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, 0)
        pcm = SR.render_scene(signals, seed)
        r = _forced_success(dec, pcm, SR.F_TRUE_FREQ_HZ, SR.F_TRUE_MESSAGE, true_dt_s=0.0)
        if r["harness_fault"]:
            faults += 1
            log("Part A: trial %d HARNESS FAULT rc=%d" % (t, r["rc"]))
            per_trial.append({"trial": t, "harness_fault": True, "rc": r["rc"]})
            continue
        if r["success"]:
            successes += 1
        per_trial.append({
            "trial": t, "harness_fault": False, "success": r["success"],
            "crc_ok": r["crc_ok"], "path": r["path"], "ldpc_errors": r["ldpc_errors"],
        })

    log("Part A: %d/%d successes (%d harness faults)" % (successes, N_TRIALS, faults))
    path_counts = {}
    for row in per_trial:
        if row.get("harness_fault"):
            continue
        path_counts[row["path"]] = path_counts.get(row["path"], 0) + 1
    log("Part A: path distribution (among non-fault trials): %s "
        "(path: -1=neither converged, 0=BP, 1=OSD, per decode.c ftx_ldpc_decode_llrs)" % path_counts)

    return {
        "n_trials": N_TRIALS,
        "successes": successes,
        "harness_faults": faults,
        "path_counts": path_counts,
        "per_trial": per_trial,
    }


if __name__ == "__main__":
    def _log(msg):
        print(msg)
    dec = DC.load_decoder()
    result = run_part_a(dec, _log)
    print(result["successes"], "/", result["n_trials"])
