#!/usr/bin/env python3
"""M4 -- run harness: ONE call per row at a FIXED, corrected anchor. No sweep,
no argmax over anchors (spec S5.2). Population is the ENTIRE M1 manifest (all
three arms, no subsampling, spec S5.1) plus M2's positive-control manifest
reused verbatim (spec S5.2).

Real (HIT/MISS/NULL) rows: coarse_time_offset_s = anchor_dt_s + 0.45 (THE
CORRECTION). Control rows: coarse_time_offset_s = base_dt_s, dt_offset=0 --
the control is ALREADY correctly anchored by construction; applying the
correction would break the one arm whose anchor is known-good and would
silently invalidate ROW 0a. Asserted in code below, not just in a comment.

No src/ change -- drives the same already-exported, already-pinned diagnostic
export as M1/M2/M3/R1b.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from m4_common import (  # noqa: E402
    ANCHOR_CORRECTION_S, DLL_PATH, DLL_SHA256, M1_MANIFEST_PATH,
    M2_CONTROL_MANIFEST_PATH, RESULTS_DIR, SHIM_VERSION, owsfz_wav_path,
    read_wav_12k_15s, write_json,
)
from m2_synth import render_control_pcm  # noqa: E402
from refiner_ctypes import Refiner  # noqa: E402

OUTPUT_PATH = os.path.join(RESULTS_DIR, "m4_results.json")
LOG_EVERY_N_CYCLES = 200


def load_rows():
    with open(M1_MANIFEST_PATH, encoding="utf-8") as fh:
        m1 = json.load(fh)
    with open(M2_CONTROL_MANIFEST_PATH, encoding="utf-8") as fh:
        ctrl = json.load(fh)

    rows = []
    for r in m1["rows"]:
        rows.append({
            "kind": "real", "arm": r["arm"], "cycle_id": r["cycle_id"],
            "snr_db": r["snr_db"],
            "anchor_freq_hz": r["anchor_freq_hz"], "anchor_dt_s": r["anchor_dt_s"],
            "src": r,
        })
    for r in ctrl["rows"]:
        rows.append({
            "kind": "control", "arm": "CONTROL", "cycle_id": r["cycle_id"],
            "snr_db": r["target_snr_db"],
            "anchor_freq_hz": r["base_freq_hz"], "anchor_dt_s": r["base_dt_s"],
            "src": r,
        })
    return rows, m1["spec"], ctrl["spec"]


def call_one_row(refiner: Refiner, pcm, anchor_freq_hz: float, anchor_dt_s: float, is_control: bool):
    """Spec S5.2: real/HIT/MISS/NULL rows get anchor_dt_s + 0.45 (THE CORRECTION);
    the positive control runs at dt_offset=0 -- assert it here, not just describe
    it, per the spec's own "assert it in code, with a comment saying why"."""
    coarse_freq_int = int(round(anchor_freq_hz))
    if is_control:
        dt_offset_applied = 0.0
        coarse_time_offset_s = float(anchor_dt_s)
    else:
        dt_offset_applied = ANCHOR_CORRECTION_S
        coarse_time_offset_s = float(anchor_dt_s) + ANCHOR_CORRECTION_S
    assert (dt_offset_applied == 0.0) == is_control, "control/correction routing bug"

    delta_f, delta_t, score, coarse_dt_samp, fine_dt_samp, rc = refiner.refine(
        pcm, coarse_freq_int, coarse_time_offset_s)
    return {
        "dt_offset_applied": dt_offset_applied,
        "coarse_time_offset_s": coarse_time_offset_s,
        "score": score, "delta_freq_hz": delta_f, "delta_time_s": delta_t,
        "coarse_dt_samp": coarse_dt_samp, "fine_dt_samp": fine_dt_samp, "rc": rc,
    }


def main():
    rows, m1_spec, ctrl_spec = load_rows()
    print("loaded %d rows (real+control), SHA256-pinning DLL..." % len(rows))
    n_real = sum(1 for r in rows if r["kind"] == "real")
    n_ctrl = sum(1 for r in rows if r["kind"] == "control")
    print("  real=%d control=%d" % (n_real, n_ctrl))

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
            is_control = row["kind"] == "control"
            pcm = render_control_pcm(row["src"], raw_pcm) if is_control else raw_pcm

            out = call_one_row(refiner, pcm, row["anchor_freq_hz"], row["anchor_dt_s"], is_control)
            if out["rc"] != 0:
                n_rc_nonzero += 1

            results[i] = {
                "trial_index": i, "kind": row["kind"], "arm": row["arm"],
                "cycle_id": ts, "snr_db": row["snr_db"],
                "anchor_freq_hz": row["anchor_freq_hz"], "anchor_dt_s": row["anchor_dt_s"],
                **out,
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
        "spec": "2026-08-15-1658-architect-to-qa-m4-corrected-anchor-spec.md",
        "m1_manifest_spec": m1_spec, "control_spec": ctrl_spec,
        "m1_manifest_path": M1_MANIFEST_PATH, "control_manifest_path": M2_CONTROL_MANIFEST_PATH,
        "anchor_correction_s": ANCHOR_CORRECTION_S,
        "dll_sha256": DLL_SHA256, "shim_version": refiner.version,
        "n_rows_total": len(rows), "n_rows_done": n_done,
        "n_rc_nonzero": n_rc_nonzero, "stopped_early": stopped,
        "results": [r for r in results if r is not None],
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(OUTPUT_PATH, out)
    print("results written: %s" % OUTPUT_PATH)


if __name__ == "__main__":
    main()
