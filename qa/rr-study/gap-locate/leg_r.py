#!/usr/bin/env python3
"""GAP-LOCATE spec sec.2 Leg R (raw replay) + ROW 0e.

Single process, cycles in strict chronological order (the callsign hash table is
process-global and order-dependent -- G2A-REMEASURE-A's own standing lesson, reused here:
never chunk/parallelise this leg). ft8_decode_all at production params (nhard 40, k=10,
corr=0.10 -- gl_dll_pin.PROD_PARAMS, already set at decoder load) on every included cycle's
WAV.

A row of M is S if the replay's decode set for that cycle contains a message that
wildcard-matches the REF text (matcher.wildcard_match, same-cycle only, no freq check --
identical convention to matcher.recovery's own "gained" construction, HK-018, reused for
consistency with H10's own R_wild definition).

ROW 0e: per included cycle, replay decode count vs live (openwsfz ALL.TXT) decode count;
pass if replay >= live in >= 0.95 of cycles.

Checkpointed by cycle index; resumable. NFR-021/HK-037: message text never leaves this
module's own functions -- callers pass M rows as (ts, INDEX) pairs (the index into M's own
deterministic sorted order, never the message), and persisted per-cycle records carry counts
and a set of INTEGER indices (which M-rows matched), never text or a text-keyed string.
"""
from __future__ import annotations

import json
import os
import sys
import time
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, HERE)

import wavio  # noqa: E402
from h1_hash_token_contamination import wildcard_match  # noqa: E402  (reused verbatim, HK-018)

CHECKPOINT_EVERY = 200


def run_leg_r(dec, corpus_dir: str, cycles: list, ref_by_ts: dict, live_counts_by_ts: dict,
              cycle_wav_path_fn, out_json: str, log) -> dict:
    """cycles: sorted list of included-cycle ts strings, STRICT chronological order.
    ref_by_ts: {ts: [(m_index, message), ...]} for M rows in that cycle -- m_index is the
      row's position in M's own deterministic sorted order (row0.load_population's `M`),
      NEVER persisted; message is used in-process only, for wildcard_match, and discarded.
    live_counts_by_ts: {ts: int} -- live (openwsfz) decode count per cycle, for 0e.
    Returns state with per-cycle replay decode counts and the set of M-row INDICES for
    which S fired (NFR-021/HK-037: no message text in the returned/persisted state)."""
    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        done_n = state["n_cycles_done"]
        log("Leg R resume: %s already has %d/%d cycles" % (out_json, done_n, len(cycles)))
    else:
        state = {
            "n_cycles_done": 0, "wall_s_total": 0.0,
            "per_cycle_counts": {},   # ts -> replay decode count
            "s_hit_indices": [],      # sorted list of M-row indices for which S fired
        }
        done_n = 0

    if done_n >= len(cycles):
        log("Leg R already complete: %d cycles" % done_n)
        return state

    per_cycle_counts = state["per_cycle_counts"]
    s_hit_set = set(state["s_hit_indices"])

    t0 = time.perf_counter()
    wall_baseline = state.get("wall_s_total", 0.0)

    def save(i):
        state["n_cycles_done"] = i
        state["s_hit_indices"] = sorted(s_hit_set)
        state["wall_s_total"] = wall_baseline + (time.perf_counter() - t0)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, out_json)

    remaining = cycles[done_n:]
    for local_i, ts in enumerate(remaining):
        i = done_n + local_i
        pcm = wavio.load_cycle_pcm(cycle_wav_path_fn(corpus_dir, ts))
        decodes = dec.decode_all(pcm)
        if decodes is None:
            per_cycle_counts[ts] = -1  # native AV
            decoded_msgs = []
        else:
            per_cycle_counts[ts] = len(decodes)
            decoded_msgs = [d["message"] for d in decodes]

        for (m_index, ref_msg) in ref_by_ts.get(ts, []):
            if any(wildcard_match(ref_msg, m) for m in decoded_msgs):
                s_hit_set.add(m_index)

        if (i + 1) % CHECKPOINT_EVERY == 0:
            save(i + 1)
            elapsed = time.perf_counter() - t0
            rate = (local_i + 1) / elapsed
            eta = (len(cycles) - (i + 1)) / rate if rate > 0 else float("nan")
            log("  [%d/%d cycles] elapsed=%.0fs eta=%.0fs rate=%.2f cyc/s"
                % (i + 1, len(cycles), elapsed, eta, rate))

    save(len(cycles))
    log("Leg R done: %d cycles -> %s (wall=%.0fs)" % (len(cycles), out_json, state["wall_s_total"]))
    return state


def row0e(state: dict, live_counts_by_ts: dict, cycles: list, log) -> dict:
    ok_cycles = 0
    total = 0
    for ts in cycles:
        rc = state["per_cycle_counts"].get(ts)
        if rc is None:
            continue
        lc = live_counts_by_ts.get(ts, 0)
        total += 1
        if rc >= lc:
            ok_cycles += 1
    share = ok_cycles / total if total else float("nan")
    ok = share >= 0.95
    log("ROW 0e: replay >= live in %d/%d cycles (%.4f) -> %s"
        % (ok_cycles, total, share, "PASS" if ok else "VOID"))
    return {"ok_cycles": ok_cycles, "total": total, "share": share, "pass": ok}
