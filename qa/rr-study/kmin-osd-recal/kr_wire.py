#!/usr/bin/env python3
"""KMIN-OSD-RECAL V-WIRE, part (ii) (spec `arch/kmin-osd-recal` Amendment 1 A1.2): an in-process NATIVE check, outside the arms, that the two parameter pairs actually change what the library does.
QA tooling, no src/ or native/ change, no station, no replay, no arm output. DLL = the pin (asserted).

    python kr_wire.py [dll]

10 non-arm cycles: the 3 dry-run cycles (selection_3n_dry.json) and cycles 401-407 of L1's 800-cycle selection (selection_3n.json FULL[400:407]; the arms use the first 400).
For each cycle, in ONE process and one thread, A then B: ft8_set_decode_params(kmin, osd_corr, nhard 24); ft8_decode_all; then ft8_get_last_candidate_counts (pass-1 candidates BEFORE any LDPC) and
ft8_get_last_osd_diag (accepted OSD candidates and the OSD candidates rejected by the correlation gate, per pass). Decode counts are recorded too.
  A = kMinScorePass2 10, osdCorrThreshold 0.10;  B = 5, 0.05;  nhard 24 (OSD sign fix 1) in both.
Predicates (frozen here, before any output):
  V-WIRE-CAND : pass-1 candidates B > A in 10 of 10 cycles.
  V-WIRE-OSD  : accepted OSD candidates B >= A in 10 of 10 AND B > A in at least one; if the accepted count is 0 in ALL ten cycles (both arms), this wire is reported UNTESTED, not passed.
  (descriptive) rejected-by-correlation OSD candidates A vs B (the gate's own counter: a looser gate must reject fewer), decodes A vs B.
HK-037: no message text is read or written; counts only."""
from __future__ import annotations

import ctypes as C
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(RR, "coh-fallback"))
sys.path.insert(0, os.path.join(RR, "gap-relocate-run"))
import cf_native as N       # noqa: E402
import gr_forced as F       # noqa: E402  (its wavio loader)

PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
SHIM = 20260071
LS = "D:/Projects/claude/_qa-scratch/late-sub"
WAV_DIR = "D:/Projects/claude/OpenWSFZ/artefacts/20260930_1930_endurance_run-gathered/owsfz/wav"
RUN = "20260930_1930"
CAP, PASSES, NHARD = 256, 2, 24
ARMS = (("A", 10, 0.10), ("B", 5, 0.05))
assert (CAP, PASSES, NHARD) == (256, 2, 24)


def stamps():
    dry = json.load(open(LS + "/selection_3n_dry.json"))["runs"][RUN]["FULL"]
    full = json.load(open(LS + "/selection_3n.json"))["runs"][RUN]["FULL"]
    out = list(dry) + list(full[400:407])
    first400 = set(full[:400])
    assert len(out) == 10 and not (set(out) & first400), "the check cycles must be outside the arms' 400"
    return out


def main():
    dll = sys.argv[1] if len(sys.argv) > 1 else "D:/Projects/claude/_qa-scratch/kmin-osd-recal/bin/libft8.dll"
    sha0 = hashlib.sha256(open(dll, "rb").read()).hexdigest()
    assert sha0 == PIN, sha0
    nat = N.Native(dll, PIN, expected_shim=SHIM, nhard=NHARD)
    d = nat.dll
    d.ft8_get_last_candidate_counts.restype = C.c_int
    d.ft8_get_last_candidate_counts.argtypes = [C.POINTER(C.c_int), C.c_int]
    d.ft8_get_last_osd_diag.restype = C.c_int
    d.ft8_get_last_osd_diag.argtypes = [C.c_int, C.POINTER(C.c_int), C.POINTER(C.c_float), C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_int),
                                        C.POINTER(C.c_int), C.POINTER(C.c_int), C.c_int]
    d.ft8_set_decode_params.argtypes = [C.c_int, C.c_float, C.c_int]
    rows = []
    for st in stamps():
        pcm = np.ascontiguousarray(F.wavio.load_cycle_pcm(os.path.join(WAV_DIR, st + ".wav")), dtype=np.float32)
        rec = {"stamp": st}
        for name, kmin, osd in ARMS:
            d.ft8_set_decode_params(kmin, C.c_float(osd), NHARD)
            n, _arr = nat.decode_all(pcm)
            cc = (C.c_int * PASSES)()
            got = d.ft8_get_last_candidate_counts(cc, PASSES)
            nh, cn, dp, bt = (C.c_int * CAP)(), (C.c_float * CAP)(), (C.c_int * CAP)(), (C.c_int * CAP)()
            total, rn, rc = C.c_int(0), (C.c_int * PASSES)(), (C.c_int * PASSES)()
            stored = d.ft8_get_last_osd_diag(CAP, nh, cn, dp, bt, C.byref(total), rn, rc, PASSES)
            rec[name] = {"decodes": n, "cand_p1": cc[0], "cand_got": got, "osd_accepted_total": total.value, "osd_stored": stored, "rej_corr": [rc[0], rc[1]], "rej_nhard": [rn[0], rn[1]]}
        rows.append(rec)
    cand_ok = sum(1 for r in rows if r["B"]["cand_p1"] > r["A"]["cand_p1"])
    acc_ge = sum(1 for r in rows if r["B"]["osd_accepted_total"] >= r["A"]["osd_accepted_total"])
    acc_gt = sum(1 for r in rows if r["B"]["osd_accepted_total"] > r["A"]["osd_accepted_total"])
    all_zero = all(r["A"]["osd_accepted_total"] == 0 and r["B"]["osd_accepted_total"] == 0 for r in rows)
    osd_status = "UNTESTED" if all_zero else ("PASS" if acc_ge == 10 and acc_gt >= 1 else "FAIL")
    res = {"dll_sha256_start": sha0, "dll_sha256_end": hashlib.sha256(open(dll, "rb").read()).hexdigest(), "cycles": len(rows),
           "V-WIRE-CAND": {"B_gt_A_cycles": cand_ok, "of": 10, "PASS": cand_ok == 10},
           "V-WIRE-OSD": {"B_ge_A_cycles": acc_ge, "B_gt_A_cycles": acc_gt, "of": 10, "status": osd_status},
           "descriptive": {"rej_corr_A_total": sum(sum(r["A"]["rej_corr"]) for r in rows), "rej_corr_B_total": sum(sum(r["B"]["rej_corr"]) for r in rows),
                           "decodes_A": sum(r["A"]["decodes"] for r in rows), "decodes_B": sum(r["B"]["decodes"] for r in rows),
                           "cand_p1_A": sum(r["A"]["cand_p1"] for r in rows), "cand_p1_B": sum(r["B"]["cand_p1"] for r in rows),
                           "osd_accepted_A": sum(r["A"]["osd_accepted_total"] for r in rows), "osd_accepted_B": sum(r["B"]["osd_accepted_total"] for r in rows)},
           "rows": rows}
    out = "D:/Projects/claude/_qa-scratch/kmin-osd-recal/wire_check.json"
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
