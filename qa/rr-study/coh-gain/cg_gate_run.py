#!/usr/bin/env python
"""COH-GAIN Amendment 7 (Architect 2026-10-07 10:54Z, spec section 16): Q-GATE, step 1 of the mechanical order: the ROW LIST and the FEATURES.

  python qa/rr-study/coh-gain/cg_gate_run.py --select               # freeze the row list (numeric selection from the persisted rows.csv files; no decode)
  python qa/rr-study/coh-gain/cg_gate_run.py --features [--workers 4]   # re-extract + compute F1b / F2 / F3 for every listed row -> gate_features.csv

Rows (fresh samples = ext 5, r1, r2, r4, r6, r8, r9): every G-fail row on which C3's BP (path 0) output is CRC-valid (RIGHT + wrong; the fallback's output exists), expected 3,382 + 1,352 = 4,734, plus the sign-inverted
OSD (path 1) CRC-valid wrongs, expected 215, whose F2 is reported (descriptive: a path-1 output counts as NO output). A G-fail row with no BP CRC-valid output yields no fallback output whatever a gate does, so it needs no feature.

Features are computed from the audio, the anchor, C3's own estimate and C3's own DECODED payload ONLY (cg_gate_features). The truth text is read inside the worker for Q1 (reproduction of the persisted C3_ok / C3_crc /
C3_path / C3_nbe) AFTER the features are computed and never reaches a feature. NO LABEL (RIGHT / M-NEAR / UNEXPLAINED) is read here. HK-037: only numbers are persisted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_gate_features as GF  # noqa: E402
import cg_rows as ROWS  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_wrongid as W  # noqa: E402
import comparator as CMP  # noqa: E402
import fine_sync as FS  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402

ART = SEL.ART
SAMPLES = W.SAMPLES
LIST_PATH = os.path.join(SEL.OUT_DIR, "gate_rows.json")
FEATURES_CSV = os.path.join(ART, "rr_2026-10-07_coh_gain_gate", "gate_features.csv")
TRAIN = (5, 1, 2, 4)
TEST = (6, 8, 9)
U_MAX = 0.15          # RATIFIED by the Captain 2026-10-07 (Architect's window), FROZEN
LIST_COLUMNS = ["sample", "cycle_index", "stamp", "widx", "kind", "C3_ok", "C3_crc", "C3_path", "C3_nbe"]
FEATURE_COLUMNS = ["sample", "cycle_index", "widx", "kind", "q1_ok", "f1b", "f2", "f3"]
assert set(TRAIN) | set(TEST) == set(SAMPLES) and not (set(TRAIN) & set(TEST))


def select_rows():
    out = []
    for res, d in sorted(SAMPLES.items()):
        stamp_of = ROWS.stamp_map(SEL.rows_path(res))
        for x in ROWS.load_rows(os.path.join(ART, d, "rows.csv")):
            if x["fault"] or int(x["G_ok"]) or int(x["C3_crc"]) != 1:
                continue
            kind = "bp" if int(x["C3_path"]) == 0 else ("osd" if int(x["C3_path"]) == 1 else None)
            if kind is None:
                continue
            out.append({"sample": res, "cycle_index": int(x["cycle_index"]), "stamp": stamp_of[int(x["cycle_index"])], "widx": int(x["widx"]), "kind": kind,
                        **{k: int(x[k]) for k in ("C3_ok", "C3_crc", "C3_path", "C3_nbe")}})
    out.sort(key=lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]))
    return out


def counts(rows):
    return {"bp": sum(1 for r in rows if r["kind"] == "bp"), "bp_right": sum(1 for r in rows if r["kind"] == "bp" and r["C3_ok"]),
            "bp_wrong": sum(1 for r in rows if r["kind"] == "bp" and not r["C3_ok"]), "osd": sum(1 for r in rows if r["kind"] == "osd")}


def serialise(rows):
    return (json.dumps({"spec": "COH-GAIN section 16 (Amendment 7, Q-GATE) 16.1", "columns": LIST_COLUMNS, "counts": counts(rows),
                        "rows": [[r[c] for c in LIST_COLUMNS] for r in rows]}, sort_keys=True, indent=0) + "\n").encode("utf-8")


def load_list(path=LIST_PATH):
    spec = json.loads(open(path, "rb").read().replace(b"\r\n", b"\n"))
    return [dict(zip(spec["columns"], r)) for r in spec["rows"]]


_DEC = None
_WS = None


def _init(dll):
    global _DEC, _WS
    _DEC = CG.load_decoder(dll)
    _WS = SEL.read_alltxt(SEL.WS_ALLTXT)


def compute_row_features(dec, pcm, anchor_f, anchor_t):
    """Everything a feature may use: pcm, anchor, C3's estimate, C3's decoded payload. Returns (features dict or None, llr, decode result). No truth, no label."""
    est = FS.estimate(pcm, anchor_f, anchor_t)
    llr = CG.coherent_llrs(pcm, anchor_f, anchor_t, est)["V3"]
    res = CG._decode_llr(dec, llr)
    if not (res["rc"] == 0 and res["a91"] is not None and res["crc_ok"] == 1):
        return None, llr, res
    payload = a91_to_bits(res["a91"], CG.PAYLOAD_BITS)
    f = GF.tone_features(pcm, anchor_f, anchor_t, est, payload)
    f["f1b"] = GF.costas_snr_noise_ref_db(pcm, anchor_f, anchor_t)
    return f, llr, res


def _work(task):
    stamp, rows = task
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    lines = _WS.get(stamp, [])
    out = []
    for r in rows:
        snr, dt, freq, text = lines[r["widx"]]
        feats, llr, res = compute_row_features(_DEC, pcm, float(freq), CG.anchor_time(dt))
        # Q1 (reproduction), AFTER the features exist; the truth never reaches a feature
        truth_bits = _DEC.true_codeword(text)
        payload_ok = feats is not None and CMP.payload_match(truth_bits[:CG.PAYLOAD_BITS], a91_to_bits(res["a91"], CG.PAYLOAD_BITS), text, CG.V_STAR)
        import numpy as np
        nbe = int(np.sum((np.asarray(llr, dtype=np.float64) > 0).astype(int) != np.asarray(truth_bits)))
        q1 = (int(bool(payload_ok)), int(res["crc_ok"]), int(res["path"]), nbe) == (r["C3_ok"], r["C3_crc"], r["C3_path"], r["C3_nbe"])
        out.append({"sample": r["sample"], "cycle_index": r["cycle_index"], "widx": r["widx"], "kind": r["kind"], "q1_ok": int(q1),
                    "f1b": "" if feats is None else round(feats["f1b"], 6), "f2": "" if feats is None else round(feats["tone_match_fraction"], 6),
                    "f3": "" if feats is None else round(feats["tone_energy_ratio"], 6)})
    return out


def run(workers, dll):
    rows = load_list()
    by = {}
    for r in rows:
        by.setdefault((r["sample"], r["cycle_index"], r["stamp"]), []).append(r)
    tasks = [(st, rs) for (_s, _c, st), rs in sorted(by.items())]
    os.makedirs(os.path.dirname(FEATURES_CSV), exist_ok=True)
    recs, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dll,)) as ex:
        for k, res in enumerate(ex.map(_work, tasks, chunksize=2)):
            recs.extend(res)
            if (k + 1) % 200 == 0:
                print(f"  {k + 1}/{len(tasks)} cycles, {round(time.time() - t0)} s", flush=True)
    recs.sort(key=lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]))
    with open(FEATURES_CSV, "w", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(FEATURE_COLUMNS)
        for r in recs:
            w.writerow([r[c] for c in FEATURE_COLUMNS])
    return recs, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--features", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dll", default=os.path.join(ART, "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll"))
    a = ap.parse_args()
    if a.select:
        rows = select_rows()
        data = serialise(rows)
        open(LIST_PATH, "wb").write(data)
        print("wrote", LIST_PATH, counts(rows), "sha256(LF)", hashlib.sha256(data).hexdigest())
        return 0
    if a.features:
        assert CG.file_sha256(a.dll) == CG.DLL_PIN, "DLL differs from the pin"
        recs, secs = run(a.workers, a.dll)
        print("done:", len(recs), "rows in", round(secs), "s ->", FEATURES_CSV, "| q1 not reproduced:", sum(1 for r in recs if not r["q1_ok"]))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
