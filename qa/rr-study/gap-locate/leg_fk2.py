#!/usr/bin/env python3
"""GAP-LOCATE Amendment 4: forced-decode driver for ROW 0c' (K') and spec sec.2 Leg F (M).

Unlike leg_fk.py (ROW 0c, retired -- VOID under the registered spec, superseded by
Amendment 4): position is Amendment 2's corrected convention (REF_DT + delta, RAW, no
+0.16s) unconditionally, and success is comparator.payload_match (sec.1's RR73-equivalence
rule) instead of bit-equality. Grouped by cycle timestamp; checkpointed; resumable.

NFR-021/HK-037: X, Y and all 77-bit arrays live only inside the row loop below. Persisted
records carry ts, freq/snr/dt, found/cell/path/ldpc_errors/f_wrong booleans and counts only
-- never bit values or message text.
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
import comparator as CMP  # noqa: E402

CHECKPOINT_EVERY_CYCLES = 100


def run_leg(dec, corpus_dir: str, pop_keys: list, ref: dict, delta: float, v_star: tuple,
            out_json: str, log, cycle_wav_path_fn) -> dict:
    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        records = state["records"]
        done_n = len(records)
        log("leg resume: %s already has %d/%d rows" % (out_json, done_n, len(pop_keys)))
    else:
        records = []
        state = {"delta": delta, "v_star": list(v_star), "n_pop": len(pop_keys),
                  "records": records, "wall_s_total": 0.0}
        done_n = 0

    if done_n >= len(pop_keys):
        log("leg already complete: %d rows" % done_n)
        return state

    remaining_keys = pop_keys[done_n:]
    remaining_by_ts = collections.OrderedDict()
    for k in remaining_keys:
        remaining_by_ts.setdefault(k[0], []).append(k)

    t0 = time.perf_counter()
    wall_baseline = state.get("wall_s_total", 0.0)
    n_cycles_done = 0
    total_cycles = len(remaining_by_ts)

    def save():
        state["records"] = records
        state["wall_s_total"] = wall_baseline + (time.perf_counter() - t0)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, out_json)

    for ts, keys_here in remaining_by_ts.items():
        pcm = wavio.load_cycle_pcm(cycle_wav_path_fn(corpus_dir, ts))
        for k in keys_here:
            snr, ref_dt, freq_hz = ref[k]
            msg = k[1]
            row = {"ts": ts, "freq_hz": freq_hz, "snr": snr, "ref_dt": ref_dt,
                   "found": False, "cell": None, "path": None, "ldpc_errors": None,
                   "f_wrong": False, "n_crc_ok_wrong_payload": 0, "n_harness_fault": 0,
                   "excluded_unencodable": False}
            x_true = dec.true_codeword(msg)
            if x_true is None:
                row["excluded_unencodable"] = True
                records.append(row)
                continue
            X = x_true[:DC.FT8_PAYLOAD_BITS]

            nominal_t = ref_dt + delta  # Amendment 2: RAW, no +0.16
            cells = lattice.snap_and_neighbours(freq_hz, nominal_t)
            for i, cell in enumerate(cells):
                rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
                if rc != 0:
                    row["n_harness_fault"] += 1
                    continue
                res = dec.ldpc_decode_llrs(llr, max_iters=DC.K_LDPC_ITERATIONS, osd_depth=DC.OSD_DEPTH)
                if res["a91"] is None:
                    continue
                if res["crc_ok"] != 1:
                    continue
                Y = a91_to_bits(res["a91"], DC.FT8_PAYLOAD_BITS)
                if CMP.payload_match(X, Y, msg, v_star):
                    row["found"] = True
                    row["cell"] = "centre" if cell["is_centre"] else "neighbour"
                    row["path"] = res["path"]
                    row["ldpc_errors"] = res["ldpc_errors"]
                    break
                else:
                    row["n_crc_ok_wrong_payload"] += 1
            row["f_wrong"] = (not row["found"]) and row["n_crc_ok_wrong_payload"] > 0
            records.append(row)
        n_cycles_done += 1
        if n_cycles_done % CHECKPOINT_EVERY_CYCLES == 0:
            save()
            elapsed = time.perf_counter() - t0
            rate = n_cycles_done / elapsed
            eta_s = (total_cycles - n_cycles_done) / rate if rate > 0 else float("nan")
            log("  [%d/%d cycles, %d/%d rows] elapsed=%.0fs eta=%.0fs"
                % (n_cycles_done, total_cycles, len(records), len(pop_keys), elapsed, eta_s))

    save()
    log("leg done: %d rows -> %s (wall=%.0fs)" % (len(records), out_json, state["wall_s_total"]))
    return state
