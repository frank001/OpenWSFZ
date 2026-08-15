#!/usr/bin/env python3
"""M3 -- run harness: 49-call time-only anchor sweep per row (df fixed at 0),
winner = argmax out_sync_score over the 49 calls, EVERY call recorded (spec S7.2:
"M2 could not answer 'what does score look like across the sweep within a row'
because only winners were stored").

Combines the real HIT/NULL population (m3_population_manifest.json) with the
UNCHANGED M2 positive-control manifest (m2-anchor-sweep/results/m2_control_manifest.json
-- spec S7.2: reused, not rebuilt) so both share the identical sweep code path.

No src/ change -- drives the same already-exported, already-pinned diagnostic export
as M1/M2/R1b.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from m3_common import (  # noqa: E402
    DLL_PATH, DLL_SHA256, M2_CONTROL_MANIFEST_PATH, RESULTS_DIR, SHIM_VERSION,
    SWEEP_ORDER, owsfz_wav_path, read_wav_12k_15s, write_json,
)
from m2_synth import render_control_pcm  # noqa: E402
from refiner_ctypes import Refiner  # noqa: E402

POP_MANIFEST_PATH = os.path.join(RESULTS_DIR, "m3_population_manifest.json")
OUTPUT_PATH = os.path.join(RESULTS_DIR, "m3_results.json")

LOG_EVERY_N_CYCLES = 50

# Score-plateau equality tolerance. M2 observed FLOAT-IDENTICAL scores across
# nearby anchors that reach the same absolute peak within the refiner's own
# internal aperture -- ties are real, not numerical noise, so exact float
# equality is the correct test (no epsilon smearing that could silently absorb
# a genuine near-tie into the wrong bucket).
def _sweep_winner(calls: list[dict]):
    """calls: 49 dicts, one per dt_offset, each with a 'score' key.

    Returns (dt_win, tied, winner_call). Tie-break (spec S5.1 / S7.3): a genuine
    score plateau is resolved toward the offset NEAREST TO ZERO DISPLACEMENT --
    symmetric in sign, unlike M2's fixed-visitation-order tie-break which silently
    favoured the more-negative offset on every mirror-image tie. If the
    nearest-to-zero member of the plateau is ITSELF not unique (the only way that
    happens on a symmetric 1-D grid is a true mirror pair dt=-k / dt=+k both at
    the row's maximum, equidistant from zero) the row is TIED and excluded from
    every signed statistic (dt_win is recorded as None), per spec S5.1's second
    permitted resolution.
    """
    max_score = max(c["score"] for c in calls)
    tied_calls = [c for c in calls if c["score"] == max_score]
    if len(tied_calls) == 1:
        return tied_calls[0]["dt_offset"], False, tied_calls[0]
    min_abs = min(abs(c["dt_offset"]) for c in tied_calls)
    nearest = [c for c in tied_calls if abs(abs(c["dt_offset"]) - min_abs) < 1e-9]
    if len(nearest) == 1:
        return nearest[0]["dt_offset"], False, nearest[0]
    # Genuine mirror-image (or higher-order symmetric) tie: excluded from signed
    # stats. Report the lexicographically-first tied call as the "representative"
    # call for non-signed fields (score, coarse_dt_samp magnitude, rc) only;
    # dt_win itself is None.
    representative = sorted(nearest, key=lambda c: c["dt_offset"])[0]
    return None, True, representative


def load_rows():
    with open(POP_MANIFEST_PATH, encoding="utf-8") as fh:
        pop = json.load(fh)
    with open(M2_CONTROL_MANIFEST_PATH, encoding="utf-8") as fh:
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
    return rows, pop["spec"], ctrl["spec"]


def sweep_one_row(refiner: Refiner, pcm, base_freq_hz: float, base_dt_s: float):
    """Runs all 49 dt_offset calls (df fixed at 0), records every call, resolves
    the winner via _sweep_winner. Returns (dt_win, tied, winner_call, all_calls)."""
    base_freq_int = int(round(base_freq_hz))
    base_dt = float(base_dt_s)
    calls = []
    for dt_off in SWEEP_ORDER:
        coarse_time_offset_s = base_dt + dt_off
        delta_f, delta_t, score, coarse_dt_samp, fine_dt_samp, rc = refiner.refine(
            pcm, base_freq_int, coarse_time_offset_s)
        calls.append({
            "dt_offset": dt_off, "score": score,
            "delta_freq_hz": delta_f, "delta_time_s": delta_t,
            "coarse_dt_samp": coarse_dt_samp, "fine_dt_samp": fine_dt_samp, "rc": rc,
        })
    dt_win, tied, winner = _sweep_winner(calls)
    return dt_win, tied, winner, calls


def main():
    rows, pop_spec, ctrl_spec = load_rows()
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
    n_tied = 0
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

            dt_win, tied, winner, calls = sweep_one_row(refiner, pcm, row["base_freq_hz"], row["base_dt_s"])
            if winner["rc"] != 0:
                n_rc_nonzero += 1
            if tied:
                n_tied += 1

            results[i] = {
                "trial_index": i, "kind": row["kind"], "arm": row["arm"],
                "cycle_id": ts, "snr_db": row["snr_db"],
                "base_freq_hz": row["base_freq_hz"], "base_dt_s": row["base_dt_s"],
                "dt_win": dt_win, "tied": tied,
                "score": winner["score"], "delta_freq_hz": winner["delta_freq_hz"],
                "delta_time_s": winner["delta_time_s"],
                "coarse_dt_samp": winner["coarse_dt_samp"],
                "fine_dt_samp": winner["fine_dt_samp"], "rc": winner["rc"],
                # Every call, compact tuple form (dt_offset, score, coarse_dt_samp,
                # fine_dt_samp, delta_freq_hz, rc) -- spec S7.2's "record every call".
                "calls": [[c["dt_offset"], c["score"], c["coarse_dt_samp"],
                           c["fine_dt_samp"], c["delta_freq_hz"], c["rc"]] for c in calls],
            }
            n_done += 1

        if ci % LOG_EVERY_N_CYCLES == 0 or ci == len(cycle_ids) - 1:
            elapsed = time.time() - t0
            rate = n_done / elapsed if elapsed > 0 else 0.0
            eta_s = (len(rows) - n_done) / rate if rate > 0 else float("nan")
            print("cycle %d/%d  rows %d/%d  %.2f rows/s  ETA %.0fs  tied=%d"
                  % (ci + 1, len(cycle_ids), n_done, len(rows), rate, eta_s, n_tied), flush=True)

    elapsed = time.time() - t0
    print("\ndone: %d/%d rows in %.1fs (%.2f ms/row)  rc!=0=%d  tied=%d  stopped_early=%s"
          % (n_done, len(rows), elapsed, 1000.0 * elapsed / max(n_done, 1), n_rc_nonzero, n_tied, stopped))

    out = {
        "spec": "2026-08-15-1545-architect-to-qa-m2-row0c-ruling-and-m3-anchor-timebase-spec.md",
        "population_spec": pop_spec, "control_spec": ctrl_spec,
        "control_manifest_path": M2_CONTROL_MANIFEST_PATH,
        "dll_sha256": DLL_SHA256, "shim_version": refiner.version,
        "n_rows_total": len(rows), "n_rows_done": n_done,
        "n_rc_nonzero": n_rc_nonzero, "n_tied": n_tied, "stopped_early": stopped,
        "sweep_grid_dt_offsets_s": list(SWEEP_ORDER),
        "results": [r for r in results if r is not None],
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(OUTPUT_PATH, out)
    print("results written: %s" % OUTPUT_PATH)


if __name__ == "__main__":
    main()
