#!/usr/bin/env python3
"""COH-FALLBACK Stage 1 acceptance A2 (a)-(c): native port vs the Python reference (spec section 5.1; Amendment tolerances unchanged).

Rows: the G-fail rows of the persisted COH-GAIN fresh samples (ext, r1, r2, r4, r6, r8, r9; 27,571 expected), at WSJT-X's positions exactly as the offline harness anchored them
(anchor f = ws_freq, t = WS_DT + 0.7, cg_common.anchor_time). The Python reference values are the PERSISTED ones (rows.csv of each sample, produced by the pinned DLL 2fa6d993 + the
Python C3): C3_df, C3_dt, C3_edge, C3_crc, C3_path, C3_ok. The F1b reference values are gate_features.csv (4,949 rows). The native call is ft8_coherent_fallback_at with FORCE_C3.
  (a) BP outcome: native "CRC-valid BP output" (c3 ran, bp_rc 0, path 0, crc ok) == Python (C3_crc 1 and C3_path 0; a Python path-1 row counts as NO output); where both have an output,
      the native payload is RIGHT (cg comparator.payload_match against the truth) iff Python C3_ok.  >= 99.5 % of rows.
  (b) (df, dt) estimate equals the Python grid argmax (|d| < 1e-6)  >= 99 % of rows.
  (c) F1b within +-0.25 dB on >= 99 % of the gate rows; the gate decision (F1b <= 17.552446) equal on >= 99.5 %.
Also reported (descriptive): edge-flag agreement; a direct Python re-run of C3 on a 1,000-row subsample for payload EQUALITY (not only rightness).
HK-037: text and bits live only inside _work; numbers persisted.   python cf_a2.py <out dir> --dll <dll> [--workers 6]
"""
import argparse
import collections
import csv
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
COH = os.path.join(HERE, "..", "coh-gain")
sys.path.insert(0, COH)
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_rows as ROWS  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_wrongid as W  # noqa: E402
import comparator as CMP  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402
import cf_native as N  # noqa: E402

NEW_DLL_PIN = "7af6f893122aae009f60c18920339dc8c4e3882908a7e3d60ab888a83a92a4d3"     # Developer's Stage 1 libft8.dll, 44f0df4e (verified by QA before the run)
T1 = 17.552446
GATE_CSV = os.path.join(SEL.ART, "rr_2026-10-07_coh_gain_gate", "gate_features.csv")
_NAT = _REF = _WS = None


def _init(dll):
    global _NAT, _REF, _WS
    _NAT = N.Native(dll, NEW_DLL_PIN)
    _REF = CG.load_decoder(os.path.join(SEL.ART, "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll"))      # truth encoder + the Python reference's decoder
    _WS = SEL.read_alltxt(SEL.WS_ALLTXT)


def _work(task):
    stamp, rows = task
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    import numpy as np
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)
    lines = _WS.get(stamp, [])
    out = []
    for r in rows:
        widx = r["widx"]
        snr, dt, freq, text = lines[widx]
        t0 = CG.anchor_time(dt)
        rc, res, _ = _NAT.at(pcm, float(freq), t0, N.FLAG_FORCE_C3)
        rec = {"sample": r["sample"], "cycle_index": r["cycle_index"], "widx": widx, "rc": rc}
        if rc == 0:
            nat_out = int(res.c3_ran == 1 and res.bp_rc == 0 and res.bp_path == 0 and res.bp_crc_ok == 1)
            right = 0
            if nat_out:
                truth = _REF.true_codeword(text)[:CG.PAYLOAD_BITS]
                right = int(CMP.payload_match(truth, a91_to_bits(bytes(res.a91), CG.PAYLOAD_BITS), text, CG.V_STAR))
            rec.update({"nat_out": nat_out, "nat_right": right, "df": res.est_df_hz, "dt_est": res.est_dt_s, "edge": res.edge, "f1b": res.f1b_db,
                        "elapsed_ms": res.elapsed_ms})
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--dll", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit-cycles", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    gate = {(int(r["sample"]), int(r["cycle_index"]), int(r["widx"])): float(r["f1b"]) for r in csv.DictReader(open(GATE_CSV, newline=""))}
    persisted = {}
    tasks = []
    for res, d in sorted(W.SAMPLES.items()):
        stamp_of = ROWS.stamp_map(SEL.rows_path(res))
        by = collections.OrderedDict()
        for x in ROWS.load_rows(os.path.join(SEL.ART, d, "rows.csv")):
            if int(x["fault"]) or int(x["G_ok"]):
                continue
            k = (res, int(x["cycle_index"]), int(x["widx"]))
            persisted[k] = x
            by.setdefault(stamp_of[k[1]], []).append({"sample": res, "cycle_index": k[1], "widx": k[2]})
        tasks += list(by.items())
    if a.limit_cycles:
        tasks = tasks[:a.limit_cycles]
        persisted = {k: v for k, v in persisted.items() if any(k[1] == r["cycle_index"] and k[0] == r["sample"] and k[2] == r["widx"] for _s, rs in tasks for r in rs)}
    n_rows = sum(len(rs) for _s, rs in tasks)
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init, initargs=(a.dll,)) as ex:
        for recs in ex.map(_work, tasks, chunksize=8):
            results += recs
    assert len(results) == n_rows
    A = collections.Counter()
    for r in results:
        k = (r["sample"], r["cycle_index"], r["widx"])
        p = persisted[k]
        A["rows"] += 1
        if r["rc"] != 0:
            A["native_rc_nonzero"] += 1
            continue
        py_out = int(int(p["C3_crc"]) == 1 and int(p["C3_path"]) == 0)
        a_ok = (r["nat_out"] == py_out) and (not py_out or r["nat_right"] == int(p["C3_ok"]))
        A["a_agree"] += int(a_ok)
        A["a_outputs_both"] += int(bool(r["nat_out"] and py_out))
        A["a_py_out"] += py_out
        A["a_nat_out"] += r["nat_out"]
        b_ok = abs(r["df"] - float(p["C3_df"])) < 1e-6 and abs(r["dt_est"] - float(p["C3_dt"])) < 1e-6
        A["b_agree"] += int(b_ok)
        A["edge_agree"] += int(r["edge"] == int(float(p["C3_edge"])))
        if k in gate:
            A["c_rows"] += 1
            d = abs(r["f1b"] - gate[k]) if math.isfinite(r["f1b"]) and math.isfinite(gate[k]) else (0.0 if r["f1b"] == gate[k] else 1e9)
            A["c_within"] += int(d <= 0.25)
            A["c_gate_agree"] += int((r["f1b"] <= T1) == (gate[k] <= T1))
            A["c_maxdiff_x1e6"] = max(A["c_maxdiff_x1e6"], int(min(d, 1e3) * 1e6))
    n = A["rows"]
    out = {"dll_sha256": _sha(a.dll), "rows": n, "seconds": round(time.time() - t0),
           "A2a": {"agree": A["a_agree"], "share": round(A["a_agree"] / n, 5), "bar": 0.995, "native_outputs": A["a_nat_out"], "python_outputs": A["a_py_out"], "both": A["a_outputs_both"],
                   "result": "PASS" if A["a_agree"] / n >= 0.995 else "FAIL"},
           "A2b": {"agree": A["b_agree"], "share": round(A["b_agree"] / n, 5), "bar": 0.99, "result": "PASS" if A["b_agree"] / n >= 0.99 else "FAIL", "edge_flag_agree": A["edge_agree"]},
           "A2c": {"rows": A["c_rows"], "within_0.25dB": A["c_within"], "share_within": round(A["c_within"] / A["c_rows"], 5) if A["c_rows"] else None, "bar_within": 0.99,
                   "gate_decision_agree": A["c_gate_agree"], "share_gate": round(A["c_gate_agree"] / A["c_rows"], 5) if A["c_rows"] else None, "bar_gate": 0.995,
                   "max_abs_diff_dB": A["c_maxdiff_x1e6"] / 1e6,
                   "result": "PASS" if A["c_rows"] and A["c_within"] / A["c_rows"] >= 0.99 and A["c_gate_agree"] / A["c_rows"] >= 0.995 else "FAIL"},
           "native_rc_nonzero": A["native_rc_nonzero"]}
    json.dump(out, open(os.path.join(a.out, "a2_abc.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


def _sha(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


if __name__ == "__main__":
    main()
