#!/usr/bin/env python3
"""GAP-LOCATE Leg F / Leg K -- forced decode at REF's own position, 9-cell lattice
neighbourhood (spec sec.2). Shared driver: Leg F runs on M-minus-S (non-S strong
misses, decided by Leg R first); Leg K runs on the control population.

Grouped by cycle timestamp (many REF rows per cycle) so each WAV is read and
RMS-normalised exactly once regardless of how many rows share that cycle.

Checkpointed to out_json every CHECKPOINT_EVERY cycles -- resumable (HK-013/023 spirit:
a multi-hour offline job should survive an interruption without redoing finished work).

NFR-021: persisted records carry (ts, freq_hz, snr, ref_dt, found, cell, path,
ldpc_errors, f_wrong) only -- no message text, no callsign. Message text lives in the
`ref` dict passed in-process and is never written to `out_json`.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import lattice  # noqa: E402
import wavio  # noqa: E402
import gl_dll_pin as DC  # noqa: E402
from forced_success import _forced_success  # noqa: E402

CHECKPOINT_EVERY_CYCLES = 100


def run_leg(dec, corpus_dir: str, pop_keys: list, ref: dict, delta: float,
            out_json: str, log, cycle_wav_path_fn, apply_symbol_correction: bool = True) -> dict:
    """pop_keys: list of (ts, message) tuples, the population to force-decode.
    ref: {(ts,message): (snr, dt, freq_hz)}.

    apply_symbol_correction: spec sec.2's literal instruction is t = REF_DT + delta,
    fed through row0._forced_success, which adds dll_common's own +SYMBOL_PERIOD_S on
    top (True, the default / spec-literal path). ROW 0c's own pilot (this session)
    found that convention reproduces ~0% of KNOWN-decodable control positions, while
    REF_DT + delta used RAW (no extra +0.16) reproduces the great majority -- see the
    ROW 0 report. False disables the extra correction so the two conventions can be
    compared at full population size before ROW 0c is called."""
    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        records = state["records"]
        done_n = len(records)
        log("leg resume: %s already has %d/%d rows" % (out_json, done_n, len(pop_keys)))
    else:
        records = []
        state = {"delta": delta, "n_pop": len(pop_keys), "records": records,
                  "wall_s_total": 0.0}
        done_n = 0

    if done_n >= len(pop_keys):
        log("leg already complete: %d rows" % done_n)
        return state

    by_ts = collections.OrderedDict()
    for k in pop_keys:
        by_ts.setdefault(k[0], []).append(k)

    # Figure out which (ts groups) are already fully recorded, by count, since pop_keys
    # is deterministic (sorted) and records are appended in pop_keys order.
    remaining_keys = pop_keys[done_n:]
    remaining_by_ts = collections.OrderedDict()
    for k in remaining_keys:
        remaining_by_ts.setdefault(k[0], []).append(k)

    t0 = time.perf_counter()
    wall_baseline = state.get("wall_s_total", 0.0)
    n_cycles_done_this_call = 0
    total_cycles = len(remaining_by_ts)

    def save():
        state["records"] = records
        state["wall_s_total"] = wall_baseline + (time.perf_counter() - t0)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, out_json)

    for ts, keys_here in remaining_by_ts.items():
        wav_path = cycle_wav_path_fn(corpus_dir, ts)
        pcm = wavio.load_cycle_pcm(wav_path)
        for k in keys_here:
            snr, ref_dt, freq_hz = ref[k]
            msg = k[1]
            row = {"ts": ts, "freq_hz": freq_hz, "snr": snr, "ref_dt": ref_dt,
                   "found": False, "cell": None, "path": None, "ldpc_errors": None,
                   "f_wrong": False, "n_crc_ok_wrong_payload": 0, "n_harness_fault": 0,
                   "excluded_unencodable": False}
            # DISCLOSED correction (not in the spec, mechanically necessary): some REF
            # rows have no unique true_codeword -- ft8_encode_message returns None for
            # them. Confirmed two distinct causes, checked directly against
            # dec.true_codeword(), NOT inferred from a "<...>" substring search alone
            # (that undercounts): (a) a WSJT-X hash-placeholder ("<...>", an unresolved
            # callsign) -- 22/2000 in K; (b) free-text / non-standard-format messages the
            # encoder's grammar does not cover (skews toward longer message strings,
            # 16-23 chars observed) -- 77/2000 more in K. Combined: 99/2000 (4.95%) of K
            # excluded this way (checked at full K size, this session). Text match is
            # impossible to score either way for these rows, so they are EXCLUDED from
            # F/N (and from Leg K's P_ctrl denominator), not silently scored as N -- that
            # would bias R_F/P_ctrl downward for a reason that has nothing to do with
            # candidate search or bit recovery. Counted and reported.
            if dec.true_codeword(msg) is None:
                row["excluded_unencodable"] = True
                records.append(row)
                continue
            nominal_t = ref_dt + delta + (DC.SYMBOL_PERIOD_S if apply_symbol_correction else 0.0)
            cells = lattice.snap_and_neighbours(freq_hz, nominal_t)
            for cell in cells:
                true_dt_s = cell["time_offset_s"] - DC.SYMBOL_PERIOD_S
                r = _forced_success(dec, pcm, cell["freq_hz"], msg, true_dt_s=true_dt_s)
                if r.get("harness_fault"):
                    row["n_harness_fault"] += 1
                    continue
                if r["success"]:
                    row["found"] = True
                    row["cell"] = "centre" if cell["is_centre"] else "neighbour"
                    row["path"] = r["path"]
                    row["ldpc_errors"] = r["ldpc_errors"]
                    break
                if r.get("crc_ok") == 1:
                    row["n_crc_ok_wrong_payload"] += 1
            row["f_wrong"] = (not row["found"]) and row["n_crc_ok_wrong_payload"] > 0
            records.append(row)
        n_cycles_done_this_call += 1
        if n_cycles_done_this_call % CHECKPOINT_EVERY_CYCLES == 0:
            save()
            elapsed = time.perf_counter() - t0
            rate = n_cycles_done_this_call / elapsed
            eta_s = (total_cycles - n_cycles_done_this_call) / rate if rate > 0 else float("nan")
            log("  [%d/%d cycles, %d/%d rows] elapsed=%.0fs eta=%.0fs"
                % (n_cycles_done_this_call, total_cycles, len(records), len(pop_keys),
                   elapsed, eta_s))

    save()
    log("leg done: %d rows -> %s (wall=%.0fs)" % (len(records), out_json, state["wall_s_total"]))
    return state
