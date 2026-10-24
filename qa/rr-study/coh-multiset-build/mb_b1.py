#!/usr/bin/env python3
"""COH-MULTISET-BUILD row B1 (port fidelity): the native diagnostic export ft8_coherent_fallback_sets_at (Developer f5bf099a, DLL SHA-256 pinned below)
against QA's Python reference (ms_metrics.py @ 96aa80d4 + the fine-sync estimate + BP only through the arm's pinned DLL aaf6b03e) on the COH-MULTISET consulted rows
(`consulted = 1` in results/2026-10-24-coh-multiset/main_rows.csv: 7,498 rows), anchors as the arm (f = ws_freq, t = ws_dt + 0.7).

Rows (Architect spec section 5 B1 + Amendment 1 M2; thresholds frozen here before the first native call):
  per set (C1, J2, J3, N1) and for the walk:  overall agreement >= 99.5 %  (CRC-valid y/n equal, and payload equal when both are valid; the walk: same set and payload)
  positive class:  among rows where the PYTHON output is CRC-valid, native agrees (CRC-valid, same payload) >= 99 %   (J3: at most 4 of 401)
  union:           among rows where EITHER side has an output, agreement >= 99 %
  V3 outcome agrees >= 99.5 % (it must not have moved).
Descriptive: max |native raw - Python raw| per set, rows where the estimate differs, wall time.
HK-037: message text is never read here (no ALL.TXT); payloads are compared as bit arrays inside the worker and only counts are persisted.

  python qa/rr-study/coh-multiset-build/mb_b1.py --dll-new <new libft8.dll> --out <b1.json> [--workers 6]
"""
from __future__ import annotations

import argparse
import csv
import ctypes as C
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "coh-multiset"))
import ms_run as R  # noqa: E402  (arm pins, decoder loader)
import ms_metrics as MM  # noqa: E402
import fine_sync as FS  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402

CG = R.CG
NEW_DLL_PIN = "15e8e436f6cd9b83468499b6b0020aace61e21e1f1eea0e5a59de720e91ac40e"       # Developer f5bf099a, shim 20260071
NEW_SHIM = 20260071
MAIN_ROWS = os.path.join(CG.REPO_ROOT, "qa", "rr-study", "results", "2026-10-24-coh-multiset", "main_rows.csv")
ROWS_JSON = os.path.join(CG.REPO_ROOT, "qa", "rr-study", "results", "2026-10-24-coh-multiset", "rows_sample.json")
OVERALL_MIN, POSITIVE_MIN, UNION_MIN, V3_MIN = 0.995, 0.99, 0.99, 0.995
assert (OVERALL_MIN, POSITIVE_MIN, UNION_MIN, V3_MIN) == (0.995, 0.99, 0.99, 0.995)
NAMES = ("C1", "J2", "J3", "N1")


class Outcome(C.Structure):
    _fields_ = [("bp_rc", C.c_int32), ("bp_path", C.c_int32), ("bp_crc_ok", C.c_int32), ("bp_ldpc_errors", C.c_int32), ("a91", C.c_uint8 * 12), ("reserved", C.c_int32)]


class SetsResult(C.Structure):
    _fields_ = [("est_df_hz", C.c_double), ("est_dt_s", C.c_double), ("peak", C.c_double), ("dt_step", C.c_int32), ("edge", C.c_int32),
                ("walk_entered", C.c_int32), ("walk_set", C.c_int32), ("walk_a91", C.c_uint8 * 12), ("reserved", C.c_int32), ("v3", Outcome), ("sets", Outcome * 4)]


assert C.sizeof(Outcome) == 32 and C.sizeof(SetsResult) == 216
_DEC = _NEW = _ROWS = None


def _init(dll_new, dll_old):
    global _DEC, _NEW, _ROWS
    assert CG.file_sha256(dll_new) == NEW_DLL_PIN, "new DLL differs from its pin"
    _DEC = R.load_decoder(dll_old)                                  # BP for the Python reference: the arm's pinned DLL (aaf6b03e)
    _NEW = C.CDLL(dll_new)
    _NEW.ft8_lib_version_check.restype = C.c_int
    assert _NEW.ft8_lib_version_check() == NEW_SHIM
    _NEW.ft8_set_decode_params.argtypes = [C.c_int, C.c_float, C.c_int]
    _NEW.ft8_set_decode_params(10, 0.10, 24)
    fp, dp = C.POINTER(C.c_float), C.POINTER(C.c_double)
    _NEW.ft8_coherent_fallback_sets_at.restype = C.c_int
    _NEW.ft8_coherent_fallback_sets_at.argtypes = [fp, C.c_int, C.c_double, C.c_double, C.c_int, C.POINTER(SetsResult), dp]


def _payload(a91_bytes):
    return tuple(a91_to_bits(bytes(a91_bytes), CG.PAYLOAD_BITS))


def _py_outcome(llr):
    res = R.decode(_DEC, llr, -1)
    if res["rc"] == 0 and res["crc_ok"] == 1 and res["a91"] is not None:
        return 1, _payload(res["a91"])
    return 0, None


def _native_outcome(o):
    if o.bp_rc == 0 and o.bp_crc_ok == 1:
        return 1, _payload(o.a91)
    return 0, None


def _row(task):
    stamp, freq, dt = task
    pcm = wavio.load_cycle_pcm(os.path.join(R.WAV_DIR, stamp + ".wav"))
    f, t = float(freq), CG.anchor_time(dt)
    t0 = time.process_time()
    est = FS.estimate(pcm, f, t)
    X = MM.spectra(pcm, f, t, est)
    py_v3 = CG.coherent_llrs(pcm, f, t, est)["V3"]
    py = {"V3": (_py_outcome(py_v3), py_v3)}
    for n in NAMES:
        v = MM.SETS[n](X)
        py[n] = (_py_outcome(v), v)
    py_walk, py_walk_pl = -1, None
    if py["V3"][0][0] == 1:
        py_walk, py_walk_pl = 0, py["V3"][0][1]
    else:
        for k, n in enumerate(NAMES):
            if py[n][0][0] == 1:
                py_walk, py_walk_pl = k + 1, py[n][0][1]
                break
    t_py = time.process_time() - t0
    p32 = np.ascontiguousarray(pcm, dtype=np.float32)
    res = SetsResult()
    raw = (C.c_double * (5 * 174))()
    t0 = time.process_time()
    rc = _NEW.ft8_coherent_fallback_sets_at(p32.ctypes.data_as(C.POINTER(C.c_float)), 180000, f, t, 0, C.byref(res), raw)
    t_nat = time.process_time() - t0
    if rc != 0:
        return {"fault": 1}
    nat = {"V3": _native_outcome(res.v3)}
    for k, n in enumerate(NAMES):
        nat[n] = _native_outcome(res.sets[k])
    nat_walk = res.walk_set
    nat_walk_pl = _payload(res.walk_a91) if nat_walk >= 0 else None
    out = {"fault": 0, "est_equal": int(abs(res.est_df_hz - est["est_df_hz"]) < 1e-6 and abs(res.est_dt_s - est["est_dt_s"]) < 1e-6),
           "t_py": t_py, "t_nat": t_nat}
    agree = lambda a, b: int(a[0] == b[0] and (a[0] == 0 or a[1] == b[1]))
    for k, n in enumerate(("V3",) + NAMES):
        out[f"{n}_py"], out[f"{n}_nat"] = py[n][0][0], nat[n][0]
        out[f"{n}_agree"] = agree(py[n][0], nat[n])
        npraw = np.asarray(raw[k * 174:(k + 1) * 174], dtype=np.float64)
        out[f"{n}_maxd"] = float(np.max(np.abs(npraw - np.asarray(py[n][1], dtype=np.float64))))
    out["walk_py"], out["walk_nat"] = py_walk, nat_walk
    out["walk_agree"] = int(py_walk == nat_walk and (py_walk < 0 or py_walk_pl == nat_walk_pl))
    return out


def rate(k, n):
    return k / n if n else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll-new", required=True)
    ap.add_argument("--dll-old", default=r"D:\Projects\claude\_qa-scratch\coh-multiset\bin\libft8.dll")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    assert CG.file_sha256(a.dll_new) == NEW_DLL_PIN
    assert CG.file_sha256(a.dll_old) == R.DLL_PIN
    rows_all = json.load(open(ROWS_JSON))["rows"]
    key = {(r[0], r[2]): r for r in rows_all}
    tasks = []
    for r in csv.DictReader(open(MAIN_ROWS, newline="", encoding="utf-8")):
        if int(float(r["consulted"] or 0)):
            row = key[(int(r["cycle_index"]), int(r["widx"]))]
            tasks.append((row[1], row[3], row[4]))
    if a.limit:
        tasks = tasks[:a.limit]
    assert a.limit or len(tasks) == 7498, len(tasks)
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll_new, a.dll_old)) as ex:
        res = list(ex.map(_row, tasks, chunksize=16))
    ok = [r for r in res if not r["fault"]]
    n = len(ok)
    out = {"rows": len(tasks), "evaluated": n, "faults": len(res) - n, "new_dll_pin": NEW_DLL_PIN, "old_dll_pin": R.DLL_PIN, "estimate_equal": sum(r["est_equal"] for r in ok),
           "thresholds": {"overall": OVERALL_MIN, "positive_class": POSITIVE_MIN, "union": UNION_MIN, "v3": V3_MIN}, "sets": {}}
    allpass = n == len(tasks)
    for name in NAMES + ("walk",):
        py_k = "walk_py" if name == "walk" else f"{name}_py"
        ag = [r[f"{name}_agree"] for r in ok]
        pos = [r for r in ok if (r["walk_py"] >= 0 if name == "walk" else r[py_k] == 1)]
        nat_k = "walk_nat" if name == "walk" else f"{name}_nat"
        uni = [r for r in ok if ((r["walk_py"] >= 0 or r["walk_nat"] >= 0) if name == "walk" else (r[py_k] == 1 or r[nat_k] == 1))]
        d = {"overall": [sum(ag), n, rate(sum(ag), n)], "positive_class": [sum(r[f"{name}_agree"] for r in pos), len(pos), rate(sum(r[f"{name}_agree"] for r in pos), len(pos))],
             "union": [sum(r[f"{name}_agree"] for r in uni), len(uni), rate(sum(r[f"{name}_agree"] for r in uni), len(uni))]}
        if name != "walk":
            d["max_abs_raw_diff"] = max(r[f"{name}_maxd"] for r in ok)
        d["pass"] = bool(d["overall"][2] >= OVERALL_MIN and d["positive_class"][2] >= POSITIVE_MIN and d["union"][2] >= UNION_MIN)
        out["sets"][name] = d
        allpass = allpass and d["pass"]
    v3 = [r["V3_agree"] for r in ok]
    out["V3"] = {"agree": [sum(v3), n, rate(sum(v3), n)], "max_abs_raw_diff": max(r["V3_maxd"] for r in ok), "pass": bool(rate(sum(v3), n) >= V3_MIN)}
    out["wall_cpu_s_median_per_row"] = {"python_reference": float(np.median([r["t_py"] for r in ok])), "native_export": float(np.median([r["t_nat"] for r in ok]))}
    out["B1"] = {"pass": bool(allpass and out["V3"]["pass"])}
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
