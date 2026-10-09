#!/usr/bin/env python
"""COH-GAIN Amendment 8 (Architect 2026-10-07, spec sections 17 + 17.1): FIELD-ID. What ARE the unexplained outputs? Offline, no gate is re-scored.

Rows (selected by NUMERIC fields from the persisted wrongid_rows.csv, before any re-extraction; list committed with its SHA first):
  X set   : C3 BP (path 0) rows with cls in {M-NONE, M-OWS}                 expected 912 + 5 = 917
  OSD set : C3 OSD (path 1) CRC-valid wrongs, the negative control          expected 215
Each row is re-extracted exactly as WRONG-ID did (same estimate, V3 LLR, decode), G is re-run on the row for E-G2, and everything that needs message text happens INSIDE _work (HK-037):
  i3x/n3x/i3t/n3t   message-type numbers of the decoded X and of the truth T (the re-encoded WSJT-X text)         (packing-type numbers, not text; accepted in 17.1 E)
  layout            std (both i3 in 1/2) | nonstd (both i3 = 4) | other                                          (descriptive)
  c1_eq c2_eq rpt_eq  field equality X vs T, only when the layout is std or nonstd (else 0)
  adj               -2/-1/+1/+2/none : X equals an ENCODABLE WSJT-X decode of cycle i+d within |df| <= 12.5 Hz, |dt| <= 0.32 s of the row's own WS_freq / WS_DT
  n_unenc_near      UNENCODABLE WSJT-X decodes of cycle i inside that same window
  t_alt_eq          X equals an alternative packing of T OTHER THAN the one that produced T (17.1 C)
  x3_ok             the identity packing round-trips T (17.1 C: checked separately from t_alt_eq)
  g2                G returned the SAME payload as X on the row (E-G2; NOT in E's numerator, 17.1 B)
  w1_ok / w1g_ok    the C3 / G reproduction of the persisted row (X1)
No text, bits or text-derived hash is persisted.

ABI LIMIT (reported to the Architect before the run): the pinned DLL's only packing entry point is ft8_encode_message (one packing per text). The alternative-packing set for T is therefore
{the RR73 (ir, igrid4) variant of T}; the identity packing is excluded from t_alt_eq by rule. That variant is already absorbed by comparator.payload_match, so t_alt_eq is 0 on rows that reached M-NONE by construction:
E-ENC cannot fire from this enumerator and its count is a property of the instrument, not a finding.

  python qa/rr-study/coh-gain/cg_field.py --select
  python qa/rr-study/coh-gain/cg_field.py --run [--workers 4]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
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
import cg_wrongid as W  # noqa: E402
import cg_wrongid_rows as WR  # noqa: E402
import comparator as CMP  # noqa: E402
import pack77_fields as PF  # noqa: E402
import wavio  # noqa: E402

ART = SEL.ART
SAMPLES = W.SAMPLES
LIST_PATH = os.path.join(SEL.OUT_DIR, "field_rows.json")
OUT_CSV = os.path.join(ART, "rr_2026-10-07_coh_gain_fieldid", "field_rows.csv")
LIST_COLUMNS = ["sample", "cycle_index", "stamp", "widx", "kind", "G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe"]
OUT_COLUMNS = ["sample", "cycle_index", "widx", "kind", "w1_ok", "w1g_ok", "i3x", "n3x", "i3t", "n3t", "layout", "c1_eq", "c2_eq", "rpt_eq", "adj", "n_unenc_near", "t_alt_eq", "x3_ok", "g2"]
NEAR_DF_HZ, NEAR_DT_S = W.NEAR_DF_HZ, W.NEAR_DT_S
ADJ_OFFSETS = (-2, -1, 1, 2)
CYCLE_SECONDS = 15
assert NEAR_DF_HZ == 12.5 and abs(NEAR_DT_S - 0.32) < 1e-12 and CYCLE_SECONDS == 15


# ------------------------------------------------------------------------------------------------------------------ selection (numeric only)
def select_rows(wrongid_csv=None):
    keep = {}
    for r in WR.load_out(wrongid_csv or W.OUT_CSV):
        if r["set"] != "C3":
            continue
        if r["path"] == 0 and r["cls"] in ("M-NONE", "M-OWS"):
            keep[(r["sample"], r["cycle_index"], r["widx"])] = "X"
        elif r["path"] == 1:
            keep[(r["sample"], r["cycle_index"], r["widx"])] = "OSD"
    out = []
    for res, d in sorted(SAMPLES.items()):
        stamp_of = ROWS.stamp_map(SEL.rows_path(res))
        for x in ROWS.load_rows(os.path.join(ART, d, "rows.csv")):
            key = (res, int(x["cycle_index"]), int(x["widx"]))
            if x["fault"] or key not in keep:
                continue
            out.append({"sample": res, "cycle_index": key[1], "stamp": stamp_of[key[1]], "widx": key[2], "kind": keep[key],
                        **{k: int(x[k]) for k in ("G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe")}})
    out.sort(key=lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]))
    return out


def counts(rows):
    return {"X": sum(1 for r in rows if r["kind"] == "X"), "OSD": sum(1 for r in rows if r["kind"] == "OSD")}


def serialise(rows):
    return (json.dumps({"spec": "COH-GAIN section 17 / 17.1 (Amendment 8, FIELD-ID) rows", "columns": LIST_COLUMNS, "counts": counts(rows),
                        "rows": [[r[c] for c in LIST_COLUMNS] for r in rows]}, sort_keys=True, indent=0) + "\n").encode("utf-8")


def load_list(path=LIST_PATH):
    spec = json.loads(open(path, "rb").read().replace(b"\r\n", b"\n"))
    return [dict(zip(spec["columns"], r)) for r in spec["rows"]]


# ------------------------------------------------------------------------------------------------------------------ pure per-row logic (tested)
def n3_of(bits77):
    b = bits77[71:74]
    return (b[0] << 2) | (b[1] << 1) | b[2]


def layout_of(i3x, i3t):
    if i3x in (1, 2) and i3t in (1, 2):
        return "std"
    if i3x == 4 and i3t == 4:
        return "nonstd"
    return "other"


def field_flags(x, t):
    """(layout, c1_eq, c2_eq, rpt_eq) for two 77-bit payloads. std: the 28-bit callsign words (suffix flag excluded) and the 16-bit report/grid; nonstd (i3 = 4): h12 and c58. Otherwise 0, 0, 0."""
    i3x, i3t = PF.i3_of(x), PF.i3_of(t)
    lay = layout_of(i3x, i3t)
    if lay == "std":
        return lay, int(x[0:28] == t[0:28]), int(x[29:57] == t[29:57]), int(x[58:74] == t[58:74])
    if lay == "nonstd":
        return lay, int(x[0:12] == t[0:12]), int(x[12:70] == t[12:70]), int(x[70:74] == t[70:74])
    return lay, 0, 0, 0


def alt_packings(t):
    """Alternative packings of T other than T itself (17.1 C), as far as the pinned ABI allows (see module docstring): the RR73 (ir, igrid4) variant of a std T."""
    out = []
    if PF.i3_of(t) == 1:
        f = PF.std_fields(t)
        if (f.ir, f.igrid4) == CG.RR73_STD:
            v = list(t)
            v[58] = CG.V_STAR[0]
            g = CG.V_STAR[1]
            v[59:74] = [(g >> (14 - k)) & 1 for k in range(15)]
            out.append(v)
    return [v for v in out if v != list(t)]


def identity_roundtrip(t, t_again):
    """X3 (17.1 C): re-packing the same text gives the same payload, so the identity packing is in the enumerator's domain and is NOT counted as an alternative."""
    return list(t) == list(t_again) and list(t) not in alt_packings(t)


def stamp_shift(stamp, d_cycles):
    t = dt.datetime.strptime(stamp, "%y%m%d_%H%M%S") + dt.timedelta(seconds=CYCLE_SECONDS * d_cycles)
    return t.strftime("%y%m%d_%H%M%S")


def window(df_hz, ddt_s):
    return abs(df_hz) <= NEAR_DF_HZ and abs(ddt_s) <= NEAR_DT_S


def adj_of(x, row_f, row_dt, stamp, ws_by_stamp, encode):
    """-2/-1/1/2/'none': the nearest cycle offset (|d| ascending, earlier first) whose ENCODABLE decode equals X inside the window. `encode(text)` -> 77-bit payload or None. TEXT STAYS HERE."""
    for d in sorted(ADJ_OFFSETS, key=lambda v: (abs(v), v)):
        for (snr, ddt, freq, text) in ws_by_stamp.get(stamp_shift(stamp, d), []):
            if not window(freq - row_f, ddt - row_dt):
                continue
            pl = encode(text)
            if pl is not None and CMP.payload_match(pl, x, text, CG.V_STAR):
                return d
    return "none"


def n_unenc_near_of(row_f, row_dt, ws_lines, encode):
    return sum(1 for (snr, ddt, freq, text) in ws_lines if window(freq - row_f, ddt - row_dt) and encode(text) is None)


# ------------------------------------------------------------------------------------------------------------------ worker
_DEC = None
_WS = None


def _init(dll):
    global _DEC, _WS
    _DEC = CG.load_decoder(dll)
    _WS = SEL.read_alltxt(SEL.WS_ALLTXT)


def _encode(text):
    bits = _DEC.true_codeword(text)
    if bits is None or CG.encode_tones(_DEC, text) is None:
        return None
    return bits[:CG.PAYLOAD_BITS]


def _work(task):
    stamp, rows = task
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    ws_lines = _WS.get(stamp, [])
    out = []
    for r in rows:
        snr, ddt, freq, text = ws_lines[r["widx"]]
        truth_bits = _DEC.true_codeword(text)
        t = truth_bits[:CG.PAYLOAD_BITS]
        anchor_f, anchor_t = float(freq), CG.anchor_time(ddt)
        c3, x = W.reproduce_c3(_DEC, pcm, anchor_f, anchor_t, text, truth_bits, t)
        w1 = (c3["ok"], c3["crc"], c3["path"], c3["nbe"]) == (r["C3_ok"], r["C3_crc"], r["C3_path"], r["C3_nbe"])
        g, gpl = W.reproduce_g(_DEC, pcm, anchor_f, anchor_t, text, truth_bits, t)
        w1g = (g["ok"], g["crc"], g["path"], g["nbe"]) == (r["G_ok"], r["G_crc"], r["G_path"], r["G_nbe"])
        rec = {"sample": r["sample"], "cycle_index": r["cycle_index"], "widx": r["widx"], "kind": r["kind"], "w1_ok": int(w1), "w1g_ok": int(w1g)}
        if x is None:
            rec.update({"i3x": "", "n3x": "", "i3t": PF.i3_of(t), "n3t": n3_of(t), "layout": "none", "c1_eq": 0, "c2_eq": 0, "rpt_eq": 0, "adj": "none", "n_unenc_near": "", "t_alt_eq": 0, "x3_ok": "", "g2": 0})
        else:
            lay, c1, c2, rp = field_flags(x, t)
            t_again = _encode(text)
            rec.update({"i3x": PF.i3_of(x), "n3x": n3_of(x), "i3t": PF.i3_of(t), "n3t": n3_of(t), "layout": lay, "c1_eq": c1, "c2_eq": c2, "rpt_eq": rp,
                        "adj": adj_of(x, float(freq), ddt, stamp, _WS, _encode), "n_unenc_near": n_unenc_near_of(float(freq), ddt, ws_lines, _encode),
                        "t_alt_eq": int(list(x) in alt_packings(t)), "x3_ok": int(identity_roundtrip(t, t_again)),
                        "g2": int(gpl is not None and g["crc"] == 1 and list(gpl) == list(x))})
        out.append(rec)
    return out


def run(workers, dll):
    rows = load_list()
    by = {}
    for r in rows:
        by.setdefault((r["sample"], r["cycle_index"], r["stamp"]), []).append(r)
    tasks = [(st, rs) for (_s, _c, st), rs in sorted(by.items())]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    recs, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dll,)) as ex:
        for k, res in enumerate(ex.map(_work, tasks, chunksize=2)):
            recs.extend(res)
            if (k + 1) % 100 == 0:
                print(f"  {k + 1}/{len(tasks)} cycles, {round(time.time() - t0)} s", flush=True)
    recs.sort(key=lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]))
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
    ap.add_argument("--workers", type=int, default=4)
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
        print("done:", len(recs), "rows in", round(secs), "s ->", OUT_CSV, "| w1 not reproduced:", sum(1 for r in recs if not r["w1_ok"]), "| w1g not reproduced:", sum(1 for r in recs if not r["w1g_ok"]))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
