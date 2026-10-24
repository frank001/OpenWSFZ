#!/usr/bin/env python3
"""COH-MULTISET V1(b) (Architect Amendment 1.10): every OSD accept in the SHIPPED diagnostics has nhard <= 24 (decode.c:735 / :1158), and the reason-0 nhard-cap rejects counted.

The shipped diagnostic is ft8_get_last_osd_diag (osd-sign-fix R6, shim 20260060): per ft8_decode_all call on a thread, the nhard of every accepted OSD candidate and, per pass, the
number rejected by the nhard cap (reason 0) and by corr/norm (reason 1). It does NOT record ft8_ldpc_decode_llrs calls (ft8_shim.h:1139-1140), so it cannot read QA's G arm;
it reads the ordinary decode path of the SAME DLL in a process configured exactly as ms_run configures it (ft8_set_decode_params(10, 0.10, 24), sign fix 1), over the SAME 975 sampled
cycles' audio. The nhard cap is one process-global parameter shared by both paths, so an accept above 24 here would falsify the cap for the run; a clean result shows the cap in force.
This is the limit of what (b) can show and the report says so.

  python qa/rr-study/coh-multiset/ms_osd_diag.py run  --out <dir> [--workers 6]       # writes osd_diag.csv (numbers only); commit it BEFORE evaluating
  python qa/rr-study/coh-multiset/ms_osd_diag.py eval --csv <osd_diag.csv> --out <json>
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
sys.path.insert(0, HERE)
import ms_run as R  # noqa: E402  (pins, paths)

CAP = 256
PASSES = 2          # K_MAX_PASSES, ft8_shim.c:532
NHARD_MAX = 24
assert (CAP, PASSES, NHARD_MAX) == (256, 2, 24) and R.PARAMS[2] == NHARD_MAX
COLUMNS = ["stamp", "decodes", "accepts_total", "accepts_stored", "max_nhard", "n_over_24", "rej_nhard_p0", "rej_nhard_p1", "rej_corr_p0", "rej_corr_p1"] + [f"h{k}" for k in range(0, 25)]
_NAT = None


def _init(dll):
    global _NAT
    import cf_native as N
    _NAT = N.Native(dll, R.DLL_PIN, expected_shim=R.SHIM, nhard=NHARD_MAX)
    d = _NAT.dll
    d.ft8_get_last_osd_diag.restype = C.c_int
    d.ft8_get_last_osd_diag.argtypes = [C.c_int, C.POINTER(C.c_int), C.POINTER(C.c_float), C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_int),
                                        C.POINTER(C.c_int), C.POINTER(C.c_int), C.c_int]


def _cycle(stamp):
    import wavio
    pcm = np.ascontiguousarray(wavio.load_cycle_pcm(os.path.join(R.WAV_DIR, stamp + ".wav")), dtype=np.float32)
    n, _arr = _NAT.decode_all(pcm)
    nh, cn, dp, bt = (C.c_int * CAP)(), (C.c_float * CAP)(), (C.c_int * CAP)(), (C.c_int * CAP)()
    total, rn, rc = C.c_int(0), (C.c_int * PASSES)(), (C.c_int * PASSES)()
    stored = _NAT.dll.ft8_get_last_osd_diag(CAP, nh, cn, dp, bt, C.byref(total), rn, rc, PASSES)
    vals = [nh[i] for i in range(stored)]
    hist = [sum(1 for v in vals if v == k) for k in range(0, 25)]
    return [stamp, n, total.value, stored, max(vals) if vals else -1, sum(1 for v in vals if v > NHARD_MAX), rn[0], rn[1], rc[0], rc[1]] + hist


def run(a):
    sel = json.load(open(R.SELECTION))
    stamps = [s for _, s in sel["sample"]]
    os.makedirs(a.out, exist_ok=True)
    pin0 = R.CG.file_sha256(a.dll)
    assert pin0 == R.DLL_PIN
    with open(os.path.join(a.out, "osd_diag.csv"), "w", newline="\n") as fh, ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll,)) as ex:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for row in ex.map(_cycle, stamps, chunksize=8):
            w.writerow(row)
    assert R.CG.file_sha256(a.dll) == R.DLL_PIN
    json.dump({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "dll_sha256_start_end": pin0, "cycles": len(stamps), "nhard_set": NHARD_MAX}, open(os.path.join(a.out, "osd_diag_info.json"), "w"))
    print("done", len(stamps), "cycles")


def evaluate(csv_path):
    rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
    i = lambda r, k: int(r[k])
    accepts = sum(i(r, "accepts_total") for r in rows)
    stored = sum(i(r, "accepts_stored") for r in rows)
    over = sum(i(r, "n_over_24") for r in rows)
    mx = max(i(r, "max_nhard") for r in rows)
    hist = {k: sum(i(r, f"h{k}") for r in rows) for k in range(0, 25)}
    rej0 = sum(i(r, "rej_nhard_p0") + i(r, "rej_nhard_p1") for r in rows)
    rej1 = sum(i(r, "rej_corr_p0") + i(r, "rej_corr_p1") for r in rows)
    truncated = sum(1 for r in rows if i(r, "accepts_total") > i(r, "accepts_stored"))
    return {"cycles": len(rows), "decodes_total": sum(i(r, "decodes") for r in rows), "osd_accepts_total": accepts, "osd_accepts_stored": stored, "cycles_with_truncated_store": truncated,
            "max_nhard_among_accepts": mx, "accepts_with_nhard_over_24": over, "reason0_nhard_cap_rejects": rej0, "reason1_corr_rejects": rej1, "nhard_histogram_0_to_24": hist,
            "V1b": {"rule": "every OSD accept has nhard <= 24 (an accept above 24 makes the verdict VOID)", "pass": bool(accepts > 0 and over == 0 and mx <= NHARD_MAX and truncated == 0)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "eval"])
    ap.add_argument("--out")
    ap.add_argument("--csv")
    ap.add_argument("--dll", default=R.CG.os.path.join(r"D:\Projects\claude\_qa-scratch\coh-multiset\bin", "libft8.dll"))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.mode == "run":
        run(a)
    else:
        out = evaluate(a.csv)
        json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
        print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
