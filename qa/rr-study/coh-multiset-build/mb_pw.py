#!/usr/bin/env python3
"""COH-MULTISET-BUILD Stage 2 acceptance extension (QA, HK-039): the PRODUCT walk (ft8_coherent_fallback_run with FT8_COH_RUN_MULTISET) against the Stage-1 EXPORT walk
(ft8_coherent_fallback_sets_at) on real audio, because B1 checked the export against the Python reference but the product loop in cf_process_one is separate code.

Cycles: the first N sampled cycles of the COH-MULTISET arm's night 20261022_1949 (owsfz/wav; NOT the replay night 20260925_2010: nothing here is an arm decode).
Per cycle: ft8_decode_all, the snapshot, then ft8_coherent_fallback_run with flags 0 (OFF) and FT8_COH_RUN_MULTISET (ON), budget -1 (no deadline). For every attempted ON row the export is
called at the row's own anchor (freq_hz, dt_s as doubles, exactly what the product passes) and compared:
  P1  provenance == the export's walk_set (0 when V3 is CRC-valid, 1..4, -1 none) and, when a set won, the row's payload == the export's walk payload
  P2  order: on rows where >= 2 sets are CRC-valid in the export, provenance == the lowest-numbered valid set (the fixed order C1 > J2 > J3 > N1 on real data)
  P3  OFF: every provenance 0 and walk_entered 0; every ON row with provenance 0 equals the OFF row (state, payload, snr, f1b)
  P4  ON walk_entered == number of ON rows whose OFF state is NO_CRC
Only counts are persisted (HK-037). Run with the Stage 2 DLL pinned below.

  python qa/rr-study/coh-multiset-build/mb_pw.py --dll <ea2c1d14 libft8.dll> --out <json> [--cycles 150] [--workers 4]
"""
from __future__ import annotations

import argparse
import collections
import ctypes as C
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "coh-multiset"))
sys.path.insert(0, os.path.join(HERE, "..", "coh-fallback"))
import ms_run as R  # noqa: E402
import wavio  # noqa: E402

PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"       # Developer ea2c1d14, shim 20260071
SHIM = 20260071
NO_CRC, KNOWN, GATED_OUT, NEW_GATED, ABANDONED = 1, 2, 3, 4, 0
sys.path.insert(0, os.path.join(HERE))
import mb_b1 as B1  # noqa: E402  (SetsResult / Outcome structs)


class Out(C.Structure):
    _fields_ = [("freq_hz", C.c_float), ("dt_s", C.c_float), ("out_freq_hz", C.c_float), ("out_dt_s", C.c_float), ("pass_", C.c_int32), ("edge", C.c_int32),
                ("state", C.c_int32), ("snr_db", C.c_int32), ("f1b_db", C.c_double), ("payload", C.c_uint8 * 12), ("provenance", C.c_int32)]


class Stats(C.Structure):
    _fields_ = [(n, C.c_int32) for n in ("n_candidates", "n_decoded", "n_dup_position", "n_eligible", "n_attempted", "n_crc_ok", "n_crc_new", "n_f1b_computed",
                                         "n_gated", "n_published", "n_abandoned", "n_edge", "n_decoded_estimated", "n_rows", "n_walk_entered", "reserved1")] + \
               [(n, C.c_double) for n in ("estimate_ms", "f1b_ms", "c3_bp_ms", "total_ms")]


class Cand(C.Structure):
    _fields_ = [("freq_hz", C.c_int), ("dt", C.c_float), ("snr", C.c_int), ("message", C.c_char * 36)]


assert C.sizeof(Out) == 56 and C.sizeof(Stats) == 96
_D = None


def _init(dll, pin):
    global _D
    assert R.CG.file_sha256(dll) == pin
    d = C.CDLL(dll)
    d.ft8_lib_version_check.restype = C.c_int
    assert d.ft8_lib_version_check() == SHIM
    fp = C.POINTER(C.c_float)
    d.ft8_set_decode_params.argtypes = [C.c_int, C.c_float, C.c_int]
    d.ft8_set_decode_params(10, 0.10, 24)
    d.ft8_set_osd_sign_fix.argtypes = [C.c_int]
    d.ft8_set_osd_sign_fix(1)
    d.ft8_decode_all.restype = C.c_int
    d.ft8_decode_all.argtypes = [fp, C.c_int, C.POINTER(Cand), C.c_int]
    d.ft8_coherent_fallback_snapshot_size.restype = C.c_int
    d.ft8_coherent_fallback_snapshot.restype = C.c_int
    d.ft8_coherent_fallback_snapshot.argtypes = [C.c_void_p, C.c_int]
    d.ft8_coherent_fallback_run.restype = C.c_int
    d.ft8_coherent_fallback_run.argtypes = [fp, C.c_int, C.c_void_p, C.c_int, C.c_int, C.c_double, C.c_void_p, C.POINTER(Stats), C.POINTER(Out), C.c_int]
    d.ft8_coherent_fallback_sets_at.restype = C.c_int
    d.ft8_coherent_fallback_sets_at.argtypes = [fp, C.c_int, C.c_double, C.c_double, C.c_int, C.POINTER(B1.SetsResult), C.POINTER(C.c_double)]
    _D = d


def _cycle(stamp):
    pcm = np.ascontiguousarray(wavio.load_cycle_pcm(os.path.join(R.WAV_DIR, stamp + ".wav")), dtype=np.float32)
    p = pcm.ctypes.data_as(C.POINTER(C.c_float))
    cands = (Cand * 200)()
    _D.ft8_decode_all(p, 180000, cands, 200)
    size = _D.ft8_coherent_fallback_snapshot_size()
    snap = (C.c_uint8 * size)()
    assert _D.ft8_coherent_fallback_snapshot(snap, size) == size
    res = {}
    for flag in (0, 1):
        st = Stats()
        rows = (Out * 2000)()
        n = _D.ft8_coherent_fallback_run(p, 180000, snap, size, flag, -1.0, None, C.byref(st), rows, 2000)
        assert n >= 0, n
        res[flag] = (st, [rows[i] for i in range(n)])
    off_st, off_rows = res[0]
    on_st, on_rows = res[1]
    c = collections.Counter()
    c["cycles"] = 1
    c["rows"] = len(on_rows)
    if len(off_rows) != len(on_rows):
        c["row_count_mismatch"] += 1
        return c
    c["off_walk_entered_nonzero"] += int(off_st.n_walk_entered != 0)
    c["off_provenance_nonzero"] += sum(1 for r in off_rows if r.provenance != 0)
    c["no_crc_off"] += sum(1 for r in off_rows if r.state == NO_CRC)
    c["on_walk_entered"] += on_st.n_walk_entered
    for r_off, r_on in zip(off_rows, on_rows):
        if r_on.state == ABANDONED:
            continue
        c["attempted"] += 1
        if r_on.provenance == 0:
            same = (r_on.state == r_off.state and bytes(r_on.payload) == bytes(r_off.payload) and r_on.snr_db == r_off.snr_db
                    and (r_on.f1b_db == r_off.f1b_db or (r_on.f1b_db != r_on.f1b_db and r_off.f1b_db != r_off.f1b_db)))
            c["p3_prov0_rows"] += 1
            c["p3_prov0_unequal_to_off"] += int(not same)
        res_s = B1.SetsResult()
        rc = _D.ft8_coherent_fallback_sets_at(p, 180000, float(r_on.freq_hz), float(r_on.dt_s), 0, C.byref(res_s), None)
        assert rc == 0
        walk = res_s.walk_set
        c["p1_rows"] += 1
        ok = (r_on.provenance == walk) and (walk <= 0 or bytes(r_on.payload)[:10] == bytes(res_s.walk_a91)[:10])
        c["p1_disagree"] += int(not ok)
        valid = [k + 1 for k in range(4) if res_s.sets[k].bp_rc == 0 and res_s.sets[k].bp_crc_ok == 1]
        if res_s.v3.bp_rc == 0 and res_s.v3.bp_crc_ok == 1:
            c["v3_valid_rows"] += 1
        elif len(valid) >= 2:
            c["p2_multi_valid_rows"] += 1
            c["p2_order_violations"] += int(r_on.provenance != valid[0])
        if r_on.provenance > 0:
            c[f"won_by_{r_on.provenance}"] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cycles", type=int, default=150)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--pin", default=PIN, help="the DLL SHA-256 to require (QA mutation builds pass their own; the Developer build is the default)")
    a = ap.parse_args()
    assert R.CG.file_sha256(a.dll) == a.pin
    sel = json.load(open(R.SELECTION))
    stamps = [s for _, s in sel["sample"]][:a.cycles]
    tot = collections.Counter()
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll, a.pin)) as ex:
        for c in ex.map(_cycle, stamps, chunksize=4):
            tot.update(c)
    out = dict(sorted(tot.items()))
    out["P1"] = bool(tot["p1_rows"] > 0 and tot["p1_disagree"] == 0)
    out["P2"] = bool(tot["p2_multi_valid_rows"] > 0 and tot["p2_order_violations"] == 0)
    out["P3"] = bool(tot["off_provenance_nonzero"] == 0 and tot["off_walk_entered_nonzero"] == 0 and tot["p3_prov0_unequal_to_off"] == 0)
    out["P4"] = bool(tot["on_walk_entered"] == tot["no_crc_off"])
    out["dll_sha256"] = a.pin
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
