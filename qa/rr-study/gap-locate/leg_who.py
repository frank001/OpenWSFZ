#!/usr/bin/env python3
"""GAP-LOCATE Amendment 3: Leg K-WHO -- is the K-OWN centre-cell ceiling co-channel
physics (CO) or a comparator artefact (ART)?

Spec: qa/rr-study/2026-09-27-1415-architect-to-qa-gap-locate-ko-a-ruling-and-amendment-3.md
(arch/gap-locate 8ca12ef0). Population: the 236 rows failing BOTH K-REF and K-OWN (same
population as leg_ko.py's own run, re-derived deterministically -- ko_result.json does not
store message text, by design). Cell: K-OWN's own centre cell only (production's own
reported position). Re-runs extract_at + ldpc_decode_llrs there (deterministic).

NFR-021/HK-037: X, Y, O and all 77-bit arrays are payload bits -- they encode callsigns and
are message text. They live ONLY inside run_who()'s own stack; only the classification
label (W0-W3), the field-diff NAMES (not bit values), and count-level splits are returned
to the caller and persisted.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import wavio  # noqa: E402
import gl_dll_pin as DC  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402
import pack77_fields as PF  # noqa: E402
from leg_ko import classify_message  # noqa: E402

CHECKPOINT_EVERY = 40


def _who_class(x77, y_crc_ok, y77, other_set):
    if y_crc_ok != 1 or y77 is None:
        return "W0", None, None
    if y77 == x77:
        # Should not occur for a both-fail-at-every-cell population (would mean the
        # centre cell actually succeeds) -- guarded, not assumed.
        return "ANOMALY_Y_EQUALS_X", None, None
    if tuple(y77) in other_set:
        return "W2", None, None
    ix, iy = PF.i3_of(x77), PF.i3_of(y77)
    if ix in (1, 2) and iy in (1, 2):
        F = PF.std_field_diff(x77, y77)
        if len(F) <= 1 and iy == ix:
            return "W1", sorted(F), None
        return "W3", sorted(F), None
    # non-standard layout on one or both sides -- field diff not decomposable from the
    # vendored std encode/decode path alone (disclosed limitation, not silently guessed)
    return "W3", None, "layout_not_std(i3_x=%d,i3_y=%d)" % (ix, iy)


def run_who(dec, corpus_dir: str, both_fail_keys: list, ref: dict, live: dict,
            out_json: str, log, cycle_wav_path_fn) -> dict:
    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        records = state["records"]
        done_n = len(records)
    else:
        records = []
        state = {"n_pop": len(both_fail_keys), "records": records, "wall_s_total": 0.0}
        done_n = 0

    if done_n >= len(both_fail_keys):
        log("K-WHO already complete: %d rows" % done_n)
        return state

    remaining = both_fail_keys[done_n:]
    by_ts = collections.OrderedDict()
    for k in remaining:
        by_ts.setdefault(k[0], []).append(k)

    # For O: every message logged by EITHER decoder in a given cycle (any freq), keyed by
    # ts for fast lookup, built once from the full ref/live dicts (not just the population).
    msgs_by_ts = collections.defaultdict(set)
    for (t, m) in ref:
        msgs_by_ts[t].add(m)
    for (t, m) in live:
        msgs_by_ts[t].add(m)

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
            msg_class = classify_message(msg)

            x_true = dec.true_codeword(msg)
            x77 = x_true[:DC.FT8_PAYLOAD_BITS] if x_true is not None else None

            # O: every OTHER logged message in this cycle (any freq), encodable, != REF text
            other_msgs = msgs_by_ts.get(ts, set()) - {msg}
            other_set = set()
            for m in other_msgs:
                ob = dec.true_codeword(m)
                if ob is not None:
                    other_set.add(tuple(ob[:DC.FT8_PAYLOAD_BITS]))

            # K-OWN centre cell, re-extracted (deterministic)
            rc, llr = dec.extract_at(pcm, freq_own, dt_own)
            y77 = None
            crc_ok = None
            path = None
            ldpc_errors = None
            if rc == 0:
                res = dec.ldpc_decode_llrs(llr, max_iters=DC.K_LDPC_ITERATIONS, osd_depth=DC.OSD_DEPTH)
                crc_ok = res["crc_ok"]
                path = res["path"]
                ldpc_errors = res["ldpc_errors"]
                if res["a91"] is not None:
                    y77 = a91_to_bits(res["a91"], DC.FT8_PAYLOAD_BITS)

            if x77 is None:
                w, fields, note = "W0_X_UNENCODABLE", None, "REF text itself unencodable (should not occur post-exclusion)"
            else:
                w, fields, note = _who_class(x77, crc_ok, y77, other_set)

            records.append({
                "ts": ts, "ref_freq": freq_ref, "ref_snr": snr_ref, "own_freq": freq_own,
                "msg_class": msg_class, "rc": rc, "crc_ok": crc_ok, "path": path,
                "ldpc_errors": ldpc_errors, "freq_offset": freq_own - freq_ref,
                "w_class": w, "fields_diff": fields, "note": note,
            })
        n_cyc += 1
        if n_cyc % CHECKPOINT_EVERY == 0:
            save()
            elapsed = time.perf_counter() - t0
            log("  [%d/%d cycles, %d/%d rows] elapsed=%.0fs"
                % (n_cyc, total_cycles, len(records), len(both_fail_keys), elapsed))

    save()
    log("K-WHO done: %d rows -> %s (wall=%.0fs)" % (len(records), out_json, state["wall_s_total"]))
    return state
