#!/usr/bin/env python3
"""M1 -- run harness: one ft8_refine_candidate call per manifest row.

Spec S5. Not a sweep -- one call per row, anchored at the manifest's
(anchor_freq_hz, anchor_dt_s). `coarse_time_offset_s`'s convention is asserted
directly from ft8_shim.h's own doc comment (src/OpenWSFZ.Ft8/Native/ft8_shim.h
~line 630): "coarse candidate time offset (s) from cycle start" -- byte-identical
to WSJT-X's own DT convention (FT8Result.dt: "Time offset from cycle start,
seconds"), so the manifest's anchor_dt_s (WSJT-X's own reported DT) is passed
straight through with no adjustment. This IS the derivation spec S5's warning
asks for, not an assumption.

Rows are grouped and processed by cycle_id so each 15s WAV is loaded from disk
exactly once regardless of how many rows (HIT/MISS/NULL) share that cycle.

No src/ change (spec S8) -- drives the already-exported, already-P/Invoked
diagnostic export exactly as r1-sync-refiner's harness does.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "r1-sync-refiner"))

from m1_common import (  # noqa: E402
    DLL_PATH, DLL_SHA256, SHIM_VERSION, owsfz_wav_path, read_wav_12k_15s, write_json,
)
from refiner_ctypes import Refiner  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
MANIFEST_PATH = os.path.join(RESULTS_DIR, "m1_manifest.json")
OUTPUT_PATH = os.path.join(RESULTS_DIR, "m1_results.json")

SAT_FREQ_HZ = 2.5
SAT_COARSE_SAMP = 12
SAT_FINE_SAMP = 20
EPS = 1e-4


def is_saturated(delta_freq_hz, coarse_dt_samp, fine_dt_samp) -> bool:
    return (abs(delta_freq_hz) >= SAT_FREQ_HZ - EPS
            or abs(coarse_dt_samp) >= SAT_COARSE_SAMP
            or abs(fine_dt_samp) >= SAT_FINE_SAMP)


def main():
    import json
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        manifest = json.load(fh)
    rows = manifest["rows"]
    print("loaded manifest: %d rows, SHA256-pinning DLL..." % len(rows))

    refiner = Refiner(DLL_PATH, verify=True, expected_sha256=DLL_SHA256,
                       expected_shim_version=SHIM_VERSION, check_version=True)
    print("DLL verified: SHA256=%s shim_version=%d" % (DLL_SHA256, refiner.version))

    # Group row indices by cycle_id, preserving manifest order within each cycle,
    # iterating cycles in sorted (deterministic) order -- never a raw dict/set walk.
    by_cycle: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by_cycle.setdefault(r["cycle_id"], []).append(i)
    cycle_ids = sorted(by_cycle.keys())

    results = [None] * len(rows)
    t0 = time.time()
    n_done = 0
    n_wav_errors = 0
    stopped = False

    for ci, ts in enumerate(cycle_ids):
        wav_path = owsfz_wav_path(ts)
        try:
            pcm = read_wav_12k_15s(wav_path)
        except RuntimeError as e:
            # Spec S3: stop and report on any format mismatch, do not resample.
            print("\nFATAL: %s" % e)
            stopped = True
            break

        for i in by_cycle[ts]:
            row = rows[i]
            coarse_freq_hz = int(round(row["anchor_freq_hz"]))
            coarse_time_offset_s = float(row["anchor_dt_s"])
            delta_f, delta_t, score, coarse_dt_samp, fine_dt_samp, rc = refiner.refine(
                pcm, coarse_freq_hz, coarse_time_offset_s)
            if rc != 0:
                n_wav_errors += 1
            results[i] = {
                "trial_index": row["trial_index"], "cycle_id": ts, "arm": row["arm"],
                "snr_db": row["snr_db"], "anchor_freq_hz": row["anchor_freq_hz"],
                "anchor_dt_s": row["anchor_dt_s"],
                "score": score, "delta_freq_hz": delta_f, "delta_time_s": delta_t,
                "coarse_dt_samp": coarse_dt_samp, "fine_dt_samp": fine_dt_samp,
                "rc": rc, "saturated": is_saturated(delta_f, coarse_dt_samp, fine_dt_samp),
            }
            n_done += 1

        if ci % 200 == 0 or ci == len(cycle_ids) - 1:
            elapsed = time.time() - t0
            rate = n_done / elapsed if elapsed > 0 else 0.0
            eta_s = (len(rows) - n_done) / rate if rate > 0 else float("nan")
            print("cycle %d/%d  rows %d/%d  %.1f rows/s  ETA %.0fs"
                  % (ci + 1, len(cycle_ids), n_done, len(rows), rate, eta_s), flush=True)

    elapsed = time.time() - t0
    print("\ndone: %d/%d rows in %.1fs (%.2f ms/row)  rc!=0 count=%d  stopped_early=%s"
          % (n_done, len(rows), elapsed, 1000.0 * elapsed / max(n_done, 1), n_wav_errors, stopped))

    out = {
        "spec": manifest["spec"], "seed": manifest["seed"], "window": manifest["window"],
        "dll_sha256": DLL_SHA256, "shim_version": refiner.version,
        "n_rows_manifest": len(rows), "n_rows_done": n_done,
        "n_rc_nonzero": n_wav_errors, "stopped_early": stopped,
        "results": [r for r in results if r is not None],
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(OUTPUT_PATH, out)
    print("results written: %s" % OUTPUT_PATH)


if __name__ == "__main__":
    main()
