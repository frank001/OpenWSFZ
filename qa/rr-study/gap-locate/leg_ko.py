#!/usr/bin/env python3
"""GAP-LOCATE Amendment 2: Leg K-OWN (diagnostic).

Spec: qa/rr-study/2026-09-27-1352-architect-to-qa-gap-locate-row0c-ruling-and-amendment-2.md
(arch/gap-locate 04feb5e1). Two runs over the SAME restricted population (the 1,901 scored K
rows, further restricted to exact (ts,message) matches in openwsfz/ALL.TXT):

  K-REF: t = REF_DT + delta (raw, no +0.16), freq = REF freq   -- QA's corrected ROW 0c convention
  K-OWN: t = OWS's own reported DT (raw), freq = OWS's own reported freq_hz

Same 9-cell lattice, same _forced_success, no +0.16 anywhere (Amendment 1's correction, now
adopted per the ruling). Logs EVERY cell (rc, crc_ok, path, ldpc_errors, payload_match), not
just first success -- first success still decides `found`.

Message CLASS is derived in-process from `msg` and only the class label is persisted
(NFR-021/HK-037: message text never leaves this function). Classes mirror the Architect's own
join (ruling sec.1.4): plain_cq (CQ CALL GRID, 3 tokens starting "CQ"), slash_call (any token
contains "/"), 3tok_standard (any other 3-token message), other.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lattice  # noqa: E402
import wavio  # noqa: E402
import gl_dll_pin as DC  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402

CHECKPOINT_EVERY_CYCLES = 50


def classify_message(msg: str) -> str:
    toks = msg.split()
    if any("/" in t for t in toks):
        return "slash_call"
    if len(toks) == 3 and toks[0] == "CQ":
        return "plain_cq"
    if len(toks) == 3:
        return "3tok_standard"
    return "other"


def _try_all_cells(dec, pcm, freq_hz, time_offset_nominal, msg, true_bits):
    """Runs the 9-cell search, logging every cell (not early-break). Returns
    (found, found_cell_idx, cell_records) -- cell_records[i] = {rc, crc_ok, path,
    ldpc_errors, payload_match}."""
    cells = lattice.snap_and_neighbours(freq_hz, time_offset_nominal)
    cell_records = []
    found = False
    found_cell_idx = None
    for i, cell in enumerate(cells):
        rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
        if rc != 0:
            cell_records.append({"rc": rc, "crc_ok": None, "path": None,
                                  "ldpc_errors": None, "payload_match": None})
            continue
        res = dec.ldpc_decode_llrs(llr, max_iters=DC.K_LDPC_ITERATIONS, osd_depth=DC.OSD_DEPTH)
        payload_match = None
        if res["a91"] is not None and true_bits is not None:
            recovered = a91_to_bits(res["a91"], DC.FT8_PAYLOAD_BITS)
            payload_match = (recovered == true_bits[:DC.FT8_PAYLOAD_BITS])
        cell_records.append({"rc": rc, "crc_ok": res["crc_ok"], "path": res["path"],
                              "ldpc_errors": res["ldpc_errors"], "payload_match": payload_match})
        if (not found) and res["crc_ok"] == 1 and payload_match:
            found = True
            found_cell_idx = i
    return found, found_cell_idx, cell_records


def run_ko(dec, corpus_dir: str, pop_keys: list, ref: dict, live: dict, delta: float,
           out_json: str, log, cycle_wav_path_fn) -> dict:
    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        records = state["records"]
        done_n = len(records)
        log("K-OWN resume: %s already has %d/%d rows" % (out_json, done_n, len(pop_keys)))
    else:
        records = []
        state = {"delta": delta, "n_pop": len(pop_keys), "records": records, "wall_s_total": 0.0}
        done_n = 0

    if done_n >= len(pop_keys):
        log("K-OWN already complete: %d rows" % done_n)
        return state

    remaining = pop_keys[done_n:]
    by_ts = collections.OrderedDict()
    for k in remaining:
        by_ts.setdefault(k[0], []).append(k)

    t0 = time.perf_counter()
    wall_baseline = state.get("wall_s_total", 0.0)
    n_cyc = 0
    total_cycles = len(by_ts)

    def save():
        state["records"] = records
        state["wall_s_total"] = wall_baseline + (time.perf_counter() - t0)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, out_json)

    for ts, keys_here in by_ts.items():
        pcm = wavio.load_cycle_pcm(cycle_wav_path_fn(corpus_dir, ts))
        for k in keys_here:
            msg = k[1]
            snr_ref, dt_ref, freq_ref = ref[k]
            snr_own, dt_own, freq_own = live[k]
            true_bits = dec.true_codeword(msg)
            msg_class = classify_message(msg)

            t_ref = dt_ref + delta  # RAW, corrected convention, no +0.16
            found_ref, cell_ref, cells_ref = _try_all_cells(dec, pcm, freq_ref, t_ref, msg, true_bits)

            t_own = dt_own  # RAW, OWS's own reported position, no +0.16
            found_own, cell_own, cells_own = _try_all_cells(dec, pcm, freq_own, t_own, msg, true_bits)

            records.append({
                "ts": ts, "ref_freq": freq_ref, "ref_dt": dt_ref, "ref_snr": snr_ref,
                "own_freq": freq_own, "own_dt": dt_own, "dt_offset_rounded": round(dt_own - dt_ref, 1),
                "freq_offset": freq_own - freq_ref, "msg_class": msg_class,
                "found_ref": found_ref, "cell_ref": cell_ref, "cells_ref": cells_ref,
                "found_own": found_own, "cell_own": cell_own, "cells_own": cells_own,
            })
        n_cyc += 1
        if n_cyc % CHECKPOINT_EVERY_CYCLES == 0:
            save()
            elapsed = time.perf_counter() - t0
            rate = n_cyc / elapsed
            eta = (total_cycles - n_cyc) / rate if rate > 0 else float("nan")
            log("  [%d/%d cycles, %d/%d rows] elapsed=%.0fs eta=%.0fs"
                % (n_cyc, total_cycles, len(records), len(pop_keys), elapsed, eta))

    save()
    log("K-OWN done: %d rows -> %s (wall=%.0fs)" % (len(records), out_json, state["wall_s_total"]))
    return state
