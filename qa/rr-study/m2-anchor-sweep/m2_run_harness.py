#!/usr/bin/env python3
"""M2 -- run harness: 63-call anchor sweep per row (21 freq offsets x 3 time offsets),
winner = argmax out_sync_score over the 63 calls.

Spec 4.1. Combines the real HIT/NULL population (m2_population_manifest.json) and the
mandatory positive control (m2_control_manifest.json) into one run so both share the
identical sweep code path (spec: "run through the identical M2 sweep path").

Real rows: PCM is the corpus WAV as-is, loaded once per cycle_id (same discipline as
m1_run_harness.py). Control rows: PCM is that same real WAV with a clean synthesised
tone added at a known position (m2_synth.render_control_pcm), rendered once per row
(not once per sweep-call).

No src/ change -- drives the same already-exported, already-pinned diagnostic export
as M1/R1b.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from m2_common import (  # noqa: E402
    DLL_PATH, DLL_SHA256, RESULTS_DIR, SHIM_VERSION, SWEEP_GRID_ORDERED,
    owsfz_wav_path, read_wav_12k_15s, write_json,
)
from m2_synth import render_control_pcm  # noqa: E402
from refiner_ctypes import Refiner  # noqa: E402

POP_MANIFEST_PATH = os.path.join(RESULTS_DIR, "m2_population_manifest.json")
CONTROL_MANIFEST_PATH = os.path.join(RESULTS_DIR, "m2_control_manifest.json")
OUTPUT_PATH = os.path.join(RESULTS_DIR, "m2_results.json")

LOG_EVERY_N_CYCLES = 50


def load_rows():
    with open(POP_MANIFEST_PATH, encoding="utf-8") as fh:
        pop = json.load(fh)
    with open(CONTROL_MANIFEST_PATH, encoding="utf-8") as fh:
        ctrl = json.load(fh)

    rows = []
    for r in pop["rows"]:
        rows.append({
            "kind": "real", "arm": r["arm"], "cycle_id": r["cycle_id"],
            "snr_db": r["snr_db"],
            "base_freq_hz": r["anchor_freq_hz"], "base_dt_s": r["anchor_dt_s"],
            "src": r,
        })
    for r in ctrl["rows"]:
        rows.append({
            "kind": "control", "arm": "CONTROL", "cycle_id": r["cycle_id"],
            "snr_db": r["target_snr_db"],
            "base_freq_hz": r["base_freq_hz"], "base_dt_s": r["base_dt_s"],
            "src": r,
        })
    return rows, pop["spec"]


def sweep_one_row(refiner: Refiner, pcm, base_freq_hz: float, base_dt_s: float):
    """Runs all 63 (df, dt_offset) calls, returns the winner dict (argmax score).

    Iterates SWEEP_GRID_ORDERED (nearest-to-zero-offset first) and keeps the first
    strictly-greatest score seen, so a tie/plateau resolves toward the anchor closest
    to zero offset rather than toward whichever offset a raw nested loop happened to
    visit first (see m2_common.SWEEP_GRID_ORDERED's docstring comment -- this is not
    cosmetic, it removes a directional artefact confirmed present during smoke-testing).
    """
    best = None
    base_freq_int = int(round(base_freq_hz))
    base_dt = float(base_dt_s)
    for df, dt_off in SWEEP_GRID_ORDERED:
        coarse_freq_hz = base_freq_int + df
        coarse_time_offset_s = base_dt + dt_off
        delta_f, delta_t, score, coarse_dt_samp, fine_dt_samp, rc = refiner.refine(
            pcm, coarse_freq_hz, coarse_time_offset_s)
        if best is None or score > best["score"]:
            best = {
                "df_anchor": df, "dt_anchor": dt_off,
                "score": score, "delta_freq_hz": delta_f, "delta_time_s": delta_t,
                "coarse_dt_samp": coarse_dt_samp, "fine_dt_samp": fine_dt_samp,
                "rc": rc,
            }
    return best


def main():
    rows, spec = load_rows()
    print("loaded %d rows (real+control), SHA256-pinning DLL..." % len(rows))

    refiner = Refiner(DLL_PATH, verify=True, expected_sha256=DLL_SHA256,
                       expected_shim_version=SHIM_VERSION, check_version=True)
    print("DLL verified: SHA256=%s shim_version=%d" % (DLL_SHA256, refiner.version))

    by_cycle: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by_cycle.setdefault(r["cycle_id"], []).append(i)
    cycle_ids = sorted(by_cycle.keys())
    print("distinct cycles to load: %d" % len(cycle_ids))

    results = [None] * len(rows)
    t0 = time.time()
    n_done = 0
    n_rc_nonzero = 0
    stopped = False

    for ci, ts in enumerate(cycle_ids):
        wav_path = owsfz_wav_path(ts)
        try:
            raw_pcm = read_wav_12k_15s(wav_path)
        except RuntimeError as e:
            print("\nFATAL: %s" % e)
            stopped = True
            break

        for i in by_cycle[ts]:
            row = rows[i]
            if row["kind"] == "control":
                pcm = render_control_pcm(row["src"], raw_pcm)
            else:
                pcm = raw_pcm

            winner = sweep_one_row(refiner, pcm, row["base_freq_hz"], row["base_dt_s"])
            if winner["rc"] != 0:
                n_rc_nonzero += 1

            results[i] = {
                "trial_index": i, "kind": row["kind"], "arm": row["arm"],
                "cycle_id": ts, "snr_db": row["snr_db"],
                "base_freq_hz": row["base_freq_hz"], "base_dt_s": row["base_dt_s"],
                **winner,
            }
            n_done += 1

        if ci % LOG_EVERY_N_CYCLES == 0 or ci == len(cycle_ids) - 1:
            elapsed = time.time() - t0
            rate = n_done / elapsed if elapsed > 0 else 0.0
            eta_s = (len(rows) - n_done) / rate if rate > 0 else float("nan")
            print("cycle %d/%d  rows %d/%d  %.2f rows/s  ETA %.0fs"
                  % (ci + 1, len(cycle_ids), n_done, len(rows), rate, eta_s), flush=True)

    elapsed = time.time() - t0
    print("\ndone: %d/%d rows in %.1fs (%.2f ms/row)  rc!=0=%d  stopped_early=%s"
          % (n_done, len(rows), elapsed, 1000.0 * elapsed / max(n_done, 1), n_rc_nonzero, stopped))

    out = {
        "spec": spec, "dll_sha256": DLL_SHA256, "shim_version": refiner.version,
        "n_rows_total": len(rows), "n_rows_done": n_done,
        "n_rc_nonzero": n_rc_nonzero, "stopped_early": stopped,
        "results": [r for r in results if r is not None],
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(OUTPUT_PATH, out)
    print("results written: %s" % OUTPUT_PATH)


if __name__ == "__main__":
    main()
