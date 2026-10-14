#!/usr/bin/env python
"""COH-GAIN Amendment 6 (Architect 2026-10-07 10:30Z, spec section 15): WRONG-ID. What are the fallback's "wrong payloads"?

Rows (selected from the PERSISTED rows.csv files by NUMERIC fields alone, before any re-extraction; the list is committed with its SHA first). Fresh samples = ext + r1/r2/r4/r6/r8/r9:
  C3 set : G_ok = 0, C3_crc = 1, C3_ok = 0        (C3 returned a CRC-valid payload that is not the truth on a G-fail row; expected 1,567 = 1,352 BP + 215 OSD)
  G set  : G_crc = 1, G_ok = 0                    (G returned a CRC-valid payload that is not the truth; expected 645 = 533 BP + 112 OSD)
Each row is re-extracted with the SAME harness, pin and parameters (cg_common.evaluate_signal's own arms, reproduced here so the recovered payload can be read; W1 proves the reproduction is exact).
Inside the function that reads ALL.TXT (HK-037, the leg_fk2.py discipline) the recovered 77-bit payload is compared, with the same V_STAR equivalence as the truth, against EVERY WSJT-X decode
of the same cycle and then against the night's OpenWSFZ live decodes of that cycle:
  M-NEAR  equals a WSJT-X decode with |df| <= 12.5 Hz and |dt| <= 0.32 s of the row's own WS_freq / WS_DT      (a different real signal AT the anchor)
  M-FAR   equals a WSJT-X decode of that cycle outside that window
  M-OWS   no WSJT-X match but equals an OWS live decode of that cycle
  M-NONE  no match            (first match wins, in that order)
Persisted per row, NUMBERS ONLY: cls, the matched row's widx / df / dt / snr / in_sample, dist (payload Hamming distance to the truth, 77 bits), the arm's own numeric fields, the number of
UNENCODABLE decodes in that cycle (a blind spot of the matcher), and w1_ok. No text, bits or text-derived hash is written.

  python qa/rr-study/coh-gain/cg_wrongid.py --select            # freeze the row list (numeric, no decode)
  python qa/rr-study/coh-gain/cg_wrongid.py --run [--workers 2]   # re-extract + classify -> wrongid_rows.csv
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
import cg_rows as ROWS  # noqa: E402
import cg_select as SEL  # noqa: E402
import comparator as CMP  # noqa: E402
import fine_sync as FS  # noqa: E402
import lattice  # noqa: E402
import wavio  # noqa: E402
from ldpc_decode_ctypes import a91_to_bits  # noqa: E402

ART = SEL.ART
SAMPLES = {5: "rr_2026-10-06_coh_gain_ext", **{r: f"rr_2026-10-06_coh_gain_r{r}" for r in CG.FRESH_RESIDUES}}
LIST_PATH = os.path.join(SEL.OUT_DIR, "wrongid_rows.json")
OUT_CSV = os.path.join(ART, "rr_2026-10-07_coh_gain_wrongid", "wrongid_rows.csv")
NEAR_DF_HZ = 12.5            # two tone bins (spec 15.2)
NEAR_DT_S = 0.32             # two symbol steps
LIST_COLUMNS = ["sample", "cycle_index", "stamp", "widx", "set", "G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe"]
OUT_COLUMNS = ["sample", "cycle_index", "widx", "set", "w1_ok", "ok", "crc", "path", "nbe", "cls", "m_widx", "m_df", "m_dt", "m_snr", "in_sample", "dist", "n_ws_unenc", "n_ows_unenc"]
CLASSES = ("M-NEAR", "M-FAR", "M-OWS", "M-NONE")
assert NEAR_DF_HZ == 2 * 6.25 and abs(NEAR_DT_S - 2 * 0.16) < 1e-12      # inherited constants asserted in code: 2 tone bins, 2 symbol steps


# ------------------------------------------------------------------------------------------------------------------ selection (numeric only)
def select_rows():
    out = []
    for res, d in sorted(SAMPLES.items()):
        stamp_of = ROWS.stamp_map(SEL.rows_path(res))
        for x in ROWS.load_rows(os.path.join(ART, d, "rows.csv")):
            if x["fault"]:
                continue
            base = {"sample": res, "cycle_index": int(x["cycle_index"]), "stamp": stamp_of[int(x["cycle_index"])], "widx": int(x["widx"]),
                    **{k: int(x[k]) for k in ("G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe")}}
            if not int(x["G_ok"]) and int(x["C3_crc"]) == 1 and not int(x["C3_ok"]):
                out.append({**base, "set": "C3"})
            if int(x["G_crc"]) == 1 and not int(x["G_ok"]):
                out.append({**base, "set": "G"})
    out.sort(key=lambda r: (r["set"], r["sample"], r["cycle_index"], r["widx"]))
    return out


def counts(rows):
    c = {}
    for r in rows:
        c.setdefault(r["set"], {}).setdefault(r["C3_path"] if r["set"] == "C3" else r["G_path"], 0)
        c[r["set"]][r["C3_path"] if r["set"] == "C3" else r["G_path"]] += 1
    return {k: {str(p): n for p, n in sorted(v.items())} | {"total": sum(v.values())} for k, v in c.items()}


def serialise(rows):
    return (json.dumps({"spec": "COH-GAIN section 15 (Amendment 6, WRONG-ID) 15.2 item 1", "columns": LIST_COLUMNS, "counts": counts(rows),
                        "rows": [[r[c] for c in LIST_COLUMNS] for r in rows]}, sort_keys=True, indent=0) + "\n").encode("utf-8")


def load_list(path=LIST_PATH):
    spec = json.loads(open(path, "rb").read().replace(b"\r\n", b"\n"))
    return [dict(zip(spec["columns"], r)) for r in spec["rows"]]


# ------------------------------------------------------------------------------------------------------------------ re-extraction + classification
def _decode_payload(dec, llr, truth_bits, text, truth_payload):
    """As cg_common._arm_result, plus the recovered 77-bit payload when the CRC is valid (it never leaves the caller)."""
    res = CG._decode_llr(dec, llr)
    crc = res["rc"] == 0 and res["a91"] is not None and res["crc_ok"] == 1
    payload = a91_to_bits(res["a91"], CG.PAYLOAD_BITS) if crc else None
    ok = bool(crc and CMP.payload_match(truth_payload, payload, text, CG.V_STAR))
    import numpy as np
    nbe = int(np.sum((np.asarray(llr, dtype=np.float64) > 0).astype(int) != np.asarray(truth_bits)))
    return {"ok": int(ok), "path": int(res["path"]), "crc": int(res["crc_ok"]), "ldpc": int(res["ldpc_errors"]), "nbe": nbe}, payload


def reproduce_c3(dec, pcm, anchor_f, anchor_t, text, truth_bits, truth_payload):
    est = FS.estimate(pcm, anchor_f, anchor_t)
    v = CG.coherent_llrs(pcm, anchor_f, anchor_t, est)
    return _decode_payload(dec, v["V3"], truth_bits, text, truth_payload)


def reproduce_g(dec, pcm, anchor_f, anchor_t, text, truth_bits, truth_payload):
    """G's chosen cell exactly as cg_common.evaluate_signal chooses it: a success if any cell succeeds (the first), else the best by (ok, -nbe)."""
    best, best_pl, won, won_pl = None, None, None, None
    for cell in lattice.snap_and_neighbours(anchor_f, anchor_t):
        rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
        if rc != 0:
            continue
        r, pl = _decode_payload(dec, llr, truth_bits, text, truth_payload)
        if best is None or (r["ok"], -r["nbe"]) > (best["ok"], -best["nbe"]):
            best, best_pl = r, pl
        if r["ok"] and won is None:
            won, won_pl = r, pl
    return (won, won_pl) if won is not None else (best, best_pl)


def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def payloads_of(dec, lines):
    """[(snr, dt, freq, payload or None)] for a cycle's decodes; returns (list, n_unencodable). TEXT STAYS HERE."""
    out, unenc = [], 0
    for (snr, dt, freq, text) in lines:
        bits = dec.true_codeword(text)
        if bits is None or CG.encode_tones(dec, text) is None:
            unenc += 1
            out.append((snr, dt, freq, None, text))
        else:
            out.append((snr, dt, freq, bits[:CG.PAYLOAD_BITS], text))
    return out, unenc


def classify(recovered, own_widx, row_f, row_dt, ws_pl, ows_pl):
    """The M-class of a recovered payload. ws_pl / ows_pl: payloads_of() lists of the same cycle. Pure given its inputs (tested). Returns a numbers-only dict."""
    near, far = [], []
    for j, (snr, dt, freq, pl, text) in enumerate(ws_pl):
        if pl is None or not CMP.payload_match(pl, recovered, text, CG.V_STAR):
            continue
        df, ddt = freq - row_f, dt - row_dt
        (near if abs(df) <= NEAR_DF_HZ and abs(ddt) <= NEAR_DT_S else far).append((abs(df) / NEAR_DF_HZ + abs(ddt) / NEAR_DT_S, j, df, ddt, snr))
    if near or far:
        cls, pick = ("M-NEAR", min(near)) if near else ("M-FAR", min(far))
        return {"cls": cls, "m_widx": pick[1], "m_df": round(pick[2], 3), "m_dt": round(pick[3], 3), "m_snr": pick[4]}
    for (snr, dt, freq, pl, text) in ows_pl:
        if pl is not None and CMP.payload_match(pl, recovered, text, CG.V_STAR):
            return {"cls": "M-OWS", "m_widx": "", "m_df": "", "m_dt": "", "m_snr": ""}
    return {"cls": "M-NONE", "m_widx": "", "m_df": "", "m_dt": "", "m_snr": ""}


_DEC = None
_WS = None
_OWS = None


def _init(dll):
    global _DEC, _WS, _OWS
    _DEC = CG.load_decoder(dll)
    _WS, _OWS = SEL.read_alltxt(SEL.WS_ALLTXT), SEL.read_alltxt(SEL.OWS_ALLTXT)


def _work(task):
    """task = (stamp, [list rows of that cycle], sample_keys). Returns numeric records. Message text exists only in this function."""
    stamp, rows, keys_by_sample = task
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    ws_lines = _WS.get(stamp, [])
    ws_pl, n_ws_unenc = payloads_of(_DEC, ws_lines)
    ows_pl, n_ows_unenc = payloads_of(_DEC, _OWS.get(stamp, []))
    out = []
    for r in rows:
        snr, dt, freq, _pl, text = ws_pl[r["widx"]]
        truth_bits = _DEC.true_codeword(text)
        truth_payload = truth_bits[:CG.PAYLOAD_BITS]
        anchor_f, anchor_t = float(freq), CG.anchor_time(dt)
        if r["set"] == "C3":
            fields, rec = reproduce_c3(_DEC, pcm, anchor_f, anchor_t, text, truth_bits, truth_payload)
            w1 = (fields["ok"], fields["crc"], fields["path"], fields["nbe"]) == (r["C3_ok"], r["C3_crc"], r["C3_path"], r["C3_nbe"])
        else:
            fields, rec = reproduce_g(_DEC, pcm, anchor_f, anchor_t, text, truth_bits, truth_payload)
            w1 = (fields["ok"], fields["crc"], fields["path"], fields["nbe"]) == (r["G_ok"], r["G_crc"], r["G_path"], r["G_nbe"])
        rec_out = {"sample": r["sample"], "cycle_index": r["cycle_index"], "widx": r["widx"], "set": r["set"], "w1_ok": int(w1), "ok": fields["ok"], "crc": fields["crc"],
                   "path": fields["path"], "nbe": fields["nbe"], "n_ws_unenc": n_ws_unenc, "n_ows_unenc": n_ows_unenc}
        if rec is None:      # the persisted row said CRC-valid; a reproduction that is not is a W1 failure, classified as nothing
            rec_out.update({"cls": "NO-PAYLOAD", "m_widx": "", "m_df": "", "m_dt": "", "m_snr": "", "in_sample": "", "dist": ""})
        else:
            c = classify(rec, r["widx"], float(freq), dt, ws_pl, ows_pl)
            rec_out.update(c)
            rec_out["in_sample"] = (int((r["sample"], r["cycle_index"], c["m_widx"]) in keys_by_sample) if c["m_widx"] != "" else "")
            rec_out["dist"] = hamming(rec, truth_payload)
        out.append(rec_out)
    return out


def run(workers, dll):
    rows = load_list()
    keys = set()
    for res in SAMPLES:
        for rr in json.load(open(SEL.rows_path(res)))["rows"]:
            keys.add((res, rr[0], rr[2]))
    by = {}
    for r in rows:
        by.setdefault((r["sample"], r["cycle_index"], r["stamp"]), []).append(r)
    tasks = [(st, rs, keys) for (_s, _c, st), rs in sorted(by.items())]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    recs = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dll,)) as ex:
        for k, res in enumerate(ex.map(_work, tasks, chunksize=4)):
            recs.extend(res)
            if (k + 1) % 200 == 0:
                print(f"  {k + 1}/{len(tasks)} cycles", flush=True)
    recs.sort(key=lambda r: (r["set"], r["sample"], r["cycle_index"], r["widx"]))
    with open(OUT_CSV, "w", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(OUT_COLUMNS)
        for r in recs:
            w.writerow([r.get(c, "") for c in OUT_COLUMNS])
    return recs, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--dll", default=os.path.join(ART, "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll"))
    a = ap.parse_args()
    if a.select:
        rows = select_rows()
        data = serialise(rows)
        open(LIST_PATH, "wb").write(data)
        print("wrote", LIST_PATH, counts(rows), "sha256(LF)", hashlib.sha256(data).hexdigest())
        return 0
    if a.run:
        assert CG.file_sha256(a.dll) == CG.DLL_PIN, "DLL differs from the pin"
        recs, secs = run(a.workers, a.dll)
        print("done:", len(recs), "rows in", round(secs), "s ->", OUT_CSV)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
