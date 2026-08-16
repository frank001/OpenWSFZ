#!/usr/bin/env python3
"""M2 -- re-run ONLY the positive control leg after the offset-grid correction
(see m2_common.py's CONTROL_FREQ_OFFSETS_HZ/CONTROL_TIME_OFFSETS_S docstring: the
first control run's grid produced a ROW 0a fire that traced to the control's own
construction, not the sweep/harness wiring -- the real HIT/NULL sweep code path is
unaffected and is NOT re-run here).

Backs up the prior m2_results.json (which carries the still-valid real-row sweep)
before overwriting, keeps its "real" rows verbatim, replaces the "control" rows with
a fresh sweep against the corrected m2_control_manifest.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from m2_common import DLL_PATH, DLL_SHA256, RESULTS_DIR, SHIM_VERSION, owsfz_wav_path, read_wav_12k_15s, write_json  # noqa: E402
from m2_run_harness import sweep_one_row  # noqa: E402
from m2_synth import render_control_pcm  # noqa: E402
from refiner_ctypes import Refiner  # noqa: E402

RESULTS_PATH = os.path.join(RESULTS_DIR, "m2_results.json")
CONTROL_MANIFEST_PATH = os.path.join(RESULTS_DIR, "m2_control_manifest.json")
BACKUP_PATH = os.path.join(RESULTS_DIR, "m2_results.PRE-CONTROL-FIX.json")


def main():
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(RESULTS_PATH, BACKUP_PATH)
        print("backed up prior results to %s" % BACKUP_PATH)

    with open(RESULTS_PATH, encoding="utf-8") as fh:
        prior = json.load(fh)
    real_results = [r for r in prior["results"] if r["kind"] == "real"]
    print("kept %d real-row results unchanged" % len(real_results))

    with open(CONTROL_MANIFEST_PATH, encoding="utf-8") as fh:
        ctrl = json.load(fh)
    ctrl_rows = ctrl["rows"]
    print("re-running %d control rows against corrected offset grid" % len(ctrl_rows))

    refiner = Refiner(DLL_PATH, verify=True, expected_sha256=DLL_SHA256,
                       expected_shim_version=SHIM_VERSION, check_version=True)
    print("DLL verified: SHA256=%s shim_version=%d" % (DLL_SHA256, refiner.version))

    new_control_results = []
    t0 = time.time()
    n_rc_nonzero = 0
    for i, row in enumerate(ctrl_rows):
        raw_pcm = read_wav_12k_15s(owsfz_wav_path(row["cycle_id"]))
        pcm = render_control_pcm(row, raw_pcm)
        winner = sweep_one_row(refiner, pcm, row["base_freq_hz"], row["base_dt_s"])
        if winner["rc"] != 0:
            n_rc_nonzero += 1
        new_control_results.append({
            "trial_index": len(real_results) + i, "kind": "control", "arm": "CONTROL",
            "cycle_id": row["cycle_id"], "snr_db": row["target_snr_db"],
            "base_freq_hz": row["base_freq_hz"], "base_dt_s": row["base_dt_s"],
            **winner,
        })
        if (i + 1) % 50 == 0 or i == len(ctrl_rows) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0.0
            print("control row %d/%d  %.2f rows/s  ETA %.0fs"
                  % (i + 1, len(ctrl_rows), rate, (len(ctrl_rows) - i - 1) / max(rate, 1e-9)), flush=True)

    elapsed = time.time() - t0
    print("\ncontrol re-run done: %d rows in %.1fs  rc!=0=%d" % (len(ctrl_rows), elapsed, n_rc_nonzero))

    combined = {
        "spec": prior["spec"], "dll_sha256": DLL_SHA256, "shim_version": refiner.version,
        "n_rows_total": len(real_results) + len(new_control_results),
        "n_rows_done": len(real_results) + len(new_control_results),
        "n_rc_nonzero": n_rc_nonzero, "stopped_early": False,
        "note": "control leg re-run after offset-grid correction; real-row results carried "
                "over unchanged from the prior run (backup: m2_results.PRE-CONTROL-FIX.json)",
        "results": real_results + new_control_results,
    }
    write_json(RESULTS_PATH, combined)
    print("results written: %s" % RESULTS_PATH)


if __name__ == "__main__":
    main()
