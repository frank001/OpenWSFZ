#!/usr/bin/env python
"""COH-GAIN Amendment 9 (Architect 2026-10-07, spec sections 18 + 18.1): ENC-ID. Is the truth mis-packed on non-standard-call messages? Offline, no new DLL.

Rows: the 795 FIELD-ID X rows with i3x = 4 (selected from field_rows.csv by numeric fields; list committed with its SHA first); negative control Y2: the 19 OSD rows with i3x = 4.
Per row, ALL inside the function that reads ALL.TXT (HK-037): re-extract (same as WRONG-ID / FIELD-ID), unpack X's type-4 fields in Python (a port of the vendored MIT ftx_message_decode_nonstd: n12, n58, iflip,
nrpt, icq) and compare with the WSJT-X text T:
  call_eq   X's full call (n58, base-38, trimmed) equals one of T's call tokens
  hash_eq   X's n12 equals the 12-bit hash (save_callsign, constant 47055833459) of a DIFFERENT call token of T; with icq = 1 it holds iff T is a CQ message
  t_has_placeholder  T contains "<...>" (an unresolved hash: the hash cannot be checked)
  enc_match = call_eq AND (hash_eq OR t_has_placeholder)                      (18.1 item 1)
Call tokens of T (18.1 item 2): its words after dropping CQ, QRZ, DE, DX and a CQ modifier word (letters only, 1-4 long, or three digits, right after CQ), reports ([R][+-]NN), 4-character grids,
RR73 / RRR / 73; then stripping <>; /R and /P compounds kept whole. Mutants (shown to move rows): m1 keeps RR73 as a token, m2 drops /P suffixes.
Y4 (18.1 item 3): each of the 795 X payloads is matched against the T of a DIFFERENT row (a fixed seeded derangement, seed 20261007) pairing only rows at least 120 cycles = 1,800 s apart.
Persisted per row, NUMBERS AND FLAGS ONLY: enc_match, call_eq, hash_eq, icq, nrpt, t_has_placeholder, m1, m2, y4_match, w1_ok. n58, the decoded call, hashes and T's tokens never leave _work.

  python qa/rr-study/coh-gain/cg_encid.py --select | --run [--workers 4]
  python qa/rr-study/coh-gain/cg_encid.py --select-reach | --reach [--workers 4]   # descriptive i3-pair table over all CRC-valid C3 and G outputs (18.1 item 4)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_field as FD  # noqa: E402
import cg_rows as ROWS  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_wrongid as W  # noqa: E402
import pack77_fields as PF  # noqa: E402
import wavio  # noqa: E402

ART = SEL.ART
SAMPLES = W.SAMPLES
LIST_PATH = os.path.join(SEL.OUT_DIR, "encid_rows.json")
REACH_LIST_PATH = os.path.join(SEL.OUT_DIR, "encid_reach_rows.json")
OUT_CSV = os.path.join(ART, "rr_2026-10-07_coh_gain_encid", "encid_rows.csv")
REACH_CSV = os.path.join(ART, "rr_2026-10-07_coh_gain_encid", "encid_reach.csv")
LIST_COLUMNS = ["sample", "cycle_index", "stamp", "widx", "kind", "p_stamp", "p_widx", "G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe"]
OUT_COLUMNS = ["sample", "cycle_index", "widx", "kind", "w1_ok", "enc_match", "call_eq", "hash_eq", "icq", "nrpt", "t_has_placeholder", "m1", "m2", "y4_match"]
REACH_LIST_COLUMNS = ["sample", "cycle_index", "stamp", "widx", "set", "G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe"]
REACH_COLUMNS = ["sample", "cycle_index", "widx", "set", "w1_ok", "ok", "i3x", "i3t"]
DERANGE_SEED = 20261007
MIN_APART_S = 120 * 15                       # 120 cycles = 30 min (18.1 item 3)
HASH_MULT = 47055833459                       # message.c:576
BASE = 38
CHARS = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"      # FT8_CHAR_TABLE_ALPHANUM_SPACE_SLASH (text.c charn)
DROP_WORDS = ("CQ", "QRZ", "DE", "DX")
Y4_TOLERANCE = 0.02
P_CONFIRMED, P_REJECTED = 0.80, 0.50
N_X, N_OSD = 795, 19
assert len(CHARS) == BASE and MIN_APART_S == 1800 and HASH_MULT == 47055833459


# ------------------------------------------------------------------------------------------------------------------ the port (tested by Y3)
def _bits_to_int(bits):
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def unpack_type4(payload77):
    """(n12, n58, iflip, nrpt, icq, call) of a type-4 payload, bit-for-bit as ftx_message_decode_nonstd lays it out: 12 + 58 + 1 + 2 + 1 + 3 = 77 bits (message.c:257-263 / 405-421)."""
    assert len(payload77) == 77
    n12 = _bits_to_int(payload77[0:12])
    n58 = _bits_to_int(payload77[12:70])
    iflip, nrpt, icq = payload77[70], _bits_to_int(payload77[71:73]), payload77[73]
    chars, v = [], n58
    for _ in range(11):
        chars.append(CHARS[v % BASE])
        v //= BASE
    call = "".join(reversed(chars)).strip()
    return n12, n58, int(iflip), int(nrpt), int(icq), call


def hash12(callsign: str):
    """save_callsign's 12-bit hash (message.c:557-577); None if a character is outside the table. Only the first 11 characters count, padded with spaces."""
    n58 = 0
    for ch in callsign[:11]:
        j = CHARS.find(ch)
        if j < 0:
            return None
        n58 = n58 * BASE + j
    for _ in range(11 - min(len(callsign), 11)):
        n58 *= BASE
    n22 = ((HASH_MULT * n58) & 0xFFFFFFFFFFFFFFFF) >> (64 - 22) & 0x3FFFFF
    return n22 >> 10


_REPORT = re.compile(r"^R?[+-]\d{2}$")
_GRID = re.compile(r"^[A-R]{2}\d{2}$")
_MODIFIER = re.compile(r"^([A-Z]{1,4}|\d{3})$")


def call_tokens(text: str, mutant=None):
    """T's call tokens per 18.1 item 2 (a list; '<...>' is not a token). mutant 'm1': keep RR73 as a token; 'm2': drop /P suffixes. TEXT STAYS WITH THE CALLER."""
    words = text.split()
    out = []
    for i, w in enumerate(words):
        if w in DROP_WORDS:
            continue
        if i == 1 and words[0] == "CQ" and _MODIFIER.match(w) and len(words) > 2:
            continue                                   # a CQ modifier word
        if w == "RR73":
            if mutant != "m1":
                continue                               # (RR73 also matches the grid pattern, so it is handled before it)
        elif _REPORT.match(w) or _GRID.match(w) or w in ("RRR", "73"):
            continue
        w = w.replace("<", "").replace(">", "")
        if w in ("...", ""):
            continue
        if mutant == "m2" and w.endswith("/P"):
            w = w[:-2]
        out.append(w)
    return out


def has_placeholder(text: str) -> bool:
    return "<...>" in text.split()


def enc_flags(payload77, text, mutant=None):
    """The numbers and flags for one (X, T) pair. Pure; X must be a type-4 payload, else all flags are 0."""
    zero = {"enc_match": 0, "call_eq": 0, "hash_eq": 0, "icq": 0, "nrpt": 0, "t_has_placeholder": int(has_placeholder(text))}
    if PF.i3_of(payload77) != 4:
        return zero
    n12, n58, iflip, nrpt, icq, call = unpack_type4(payload77)
    toks = call_tokens(text, mutant)
    ph = has_placeholder(text)
    call_eq = int(bool(call) and call in toks)
    if icq:
        hash_eq = int(text.split()[:1] == ["CQ"])
    else:
        others = [t for t in toks if t != call]
        hash_eq = int(any(hash12(t) == n12 for t in others if hash12(t) is not None))
    return {"enc_match": int(call_eq and (hash_eq or ph)), "call_eq": call_eq, "hash_eq": hash_eq, "icq": icq, "nrpt": nrpt, "t_has_placeholder": int(ph)}


# ------------------------------------------------------------------------------------------------------------------ derangement and selection
def stamp_seconds(stamp):
    return dt.datetime.strptime(stamp, "%y%m%d_%H%M%S").timestamp()


def derange(seconds, seed=DERANGE_SEED, min_apart=MIN_APART_S):
    """perm with perm[i] != i and |s_i - s_perm[i]| >= min_apart for every i (a fixed seeded repair of a random permutation)."""
    n = len(seconds)
    s = np.asarray(seconds, dtype=float)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    for _ in range(100000):
        bad = [i for i in range(n) if perm[i] == i or abs(s[i] - s[perm[i]]) < min_apart]
        if not bad:
            return [int(p) for p in perm]
        for i in bad:
            j = int(rng.integers(0, n))
            perm[i], perm[j] = perm[j], perm[i]
    raise RuntimeError("no derangement found")


def select_rows(field_csv=None):
    import cg_field_rows as FR
    fl = {(r["sample"], r["cycle_index"], r["widx"]): r for r in FD.load_list()}
    rows = []
    for r in FR.load(field_csv):
        if r["i3x"] == 4:
            base = fl[(r["sample"], r["cycle_index"], r["widx"])]
            rows.append({**{k: base[k] for k in ("sample", "cycle_index", "stamp", "widx", "kind", "G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe")}})
    rows.sort(key=lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]))
    xs = [i for i, r in enumerate(rows) if r["kind"] == "X"]
    perm = derange([stamp_seconds(rows[i]["stamp"]) for i in xs])
    for k, i in enumerate(xs):
        j = xs[perm[k]]
        rows[i]["p_stamp"], rows[i]["p_widx"] = rows[j]["stamp"], rows[j]["widx"]
    for r in rows:
        r.setdefault("p_stamp", ""), r.setdefault("p_widx", -1)
    return rows


def counts(rows):
    return {"X": sum(1 for r in rows if r["kind"] == "X"), "OSD": sum(1 for r in rows if r["kind"] == "OSD")}


def serialise(rows, columns=LIST_COLUMNS, spec="COH-GAIN section 18 / 18.1 (Amendment 9, ENC-ID) rows"):
    return (json.dumps({"spec": spec, "columns": columns, "counts": counts(rows) if "kind" in columns else {"rows": len(rows)},
                        "rows": [[r[c] for c in columns] for r in rows]}, sort_keys=True, indent=0) + "\n").encode("utf-8")


def load_list(path=LIST_PATH):
    spec = json.loads(open(path, "rb").read().replace(b"\r\n", b"\n"))
    return [dict(zip(spec["columns"], r)) for r in spec["rows"]]


def select_reach():
    out = []
    for res, d in sorted(SAMPLES.items()):
        stamp_of = ROWS.stamp_map(SEL.rows_path(res))
        for x in ROWS.load_rows(os.path.join(ART, d, "rows.csv")):
            if x["fault"]:
                continue
            base = {"sample": res, "cycle_index": int(x["cycle_index"]), "stamp": stamp_of[int(x["cycle_index"])], "widx": int(x["widx"]),
                    **{k: int(x[k]) for k in ("G_ok", "G_crc", "G_path", "G_nbe", "C3_ok", "C3_crc", "C3_path", "C3_nbe")}}
            if int(x["C3_crc"]) == 1:
                out.append({**base, "set": "C3"})
            if int(x["G_crc"]) == 1:
                out.append({**base, "set": "G"})
    out.sort(key=lambda r: (r["set"], r["sample"], r["cycle_index"], r["widx"]))
    return out


# ------------------------------------------------------------------------------------------------------------------ workers
_DEC = None
_WS = None


def _init(dll):
    global _DEC, _WS
    _DEC = CG.load_decoder(dll)
    _WS = SEL.read_alltxt(SEL.WS_ALLTXT)


def _work(task):
    stamp, rows = task
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    ws_lines = _WS.get(stamp, [])
    out = []
    for r in rows:
        snr, ddt, freq, text = ws_lines[r["widx"]]
        truth_bits = _DEC.true_codeword(text)
        t = truth_bits[:CG.PAYLOAD_BITS]
        c3, x = W.reproduce_c3(_DEC, pcm, float(freq), CG.anchor_time(ddt), text, truth_bits, t)
        w1 = (c3["ok"], c3["crc"], c3["path"], c3["nbe"]) == (r["C3_ok"], r["C3_crc"], r["C3_path"], r["C3_nbe"])
        rec = {"sample": r["sample"], "cycle_index": r["cycle_index"], "widx": r["widx"], "kind": r["kind"], "w1_ok": int(w1)}
        if x is None:
            rec.update({"enc_match": 0, "call_eq": 0, "hash_eq": 0, "icq": 0, "nrpt": 0, "t_has_placeholder": int(has_placeholder(text)), "m1": 0, "m2": 0, "y4_match": ""})
        else:
            f = enc_flags(x, text)
            rec.update(f)
            rec["m1"] = enc_flags(x, text, "m1")["enc_match"]
            rec["m2"] = enc_flags(x, text, "m2")["enc_match"]
            rec["y4_match"] = ""
            if r["kind"] == "X":
                p_text = _WS[r["p_stamp"]][r["p_widx"]][3]
                rec["y4_match"] = enc_flags(x, p_text)["enc_match"]
        out.append(rec)
    return out


def _work_reach(task):
    stamp, rows = task
    pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, stamp + ".wav"))
    ws_lines = _WS.get(stamp, [])
    out = []
    for r in rows:
        snr, ddt, freq, text = ws_lines[r["widx"]]
        truth_bits = _DEC.true_codeword(text)
        t = truth_bits[:CG.PAYLOAD_BITS]
        fn = W.reproduce_c3 if r["set"] == "C3" else W.reproduce_g
        res, x = fn(_DEC, pcm, float(freq), CG.anchor_time(ddt), text, truth_bits, t)
        pk = ("C3_ok", "C3_crc", "C3_path", "C3_nbe") if r["set"] == "C3" else ("G_ok", "G_crc", "G_path", "G_nbe")
        w1 = (res["ok"], res["crc"], res["path"], res["nbe"]) == tuple(r[k] for k in pk)
        out.append({"sample": r["sample"], "cycle_index": r["cycle_index"], "widx": r["widx"], "set": r["set"], "w1_ok": int(w1), "ok": res["ok"],
                    "i3x": "" if x is None else PF.i3_of(x), "i3t": PF.i3_of(t)})
    return out


def _run(rows, worker, cols, path, workers, dll, sortkey, every):
    by = {}
    for r in rows:
        by.setdefault((r["sample"], r["cycle_index"], r["stamp"]), []).append(r)
    tasks = [(st, rs) for (_s, _c, st), rs in sorted(by.items())]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    recs, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dll,)) as ex:
        for k, res in enumerate(ex.map(worker, tasks, chunksize=2)):
            recs.extend(res)
            if (k + 1) % every == 0:
                print(f"  {k + 1}/{len(tasks)} cycles, {round(time.time() - t0)} s", flush=True)
    recs.sort(key=sortkey)
    with open(path, "w", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in recs:
            w.writerow([r.get(c, "") for c in cols])
    return recs, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    for f in ("--select", "--run", "--select-reach", "--reach"):
        ap.add_argument(f, action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dll", default=os.path.join(ART, "rr_2026-10-06_coh_gain", "bin", "libft8_20260058.dll"))
    a = ap.parse_args()
    if a.select:
        rows = select_rows()
        data = serialise(rows)
        open(LIST_PATH, "wb").write(data)
        print("wrote", LIST_PATH, counts(rows), "sha256(LF)", hashlib.sha256(data).hexdigest())
        return 0
    if a.select_reach:
        rows = select_reach()
        data = serialise(rows, REACH_LIST_COLUMNS, "COH-GAIN 18.1 item 4 (reach) rows")
        open(REACH_LIST_PATH, "wb").write(data)
        print("wrote", REACH_LIST_PATH, len(rows), "sha256(LF)", hashlib.sha256(data).hexdigest())
        return 0
    if a.run or a.reach:
        assert CG.file_sha256(a.dll) == CG.DLL_PIN, "DLL differs from the pin"
    if a.run:
        recs, secs = _run(load_list(), _work, OUT_COLUMNS, OUT_CSV, a.workers, a.dll, lambda r: (r["kind"], r["sample"], r["cycle_index"], r["widx"]), 100)
        print("done:", len(recs), "rows in", round(secs), "s ->", OUT_CSV, "| w1 not reproduced:", sum(1 for r in recs if not r["w1_ok"]))
        return 0
    if a.reach:
        recs, secs = _run(load_list(REACH_LIST_PATH), _work_reach, REACH_COLUMNS, REACH_CSV, a.workers, a.dll, lambda r: (r["set"], r["sample"], r["cycle_index"], r["widx"]), 500)
        print("done:", len(recs), "rows in", round(secs), "s ->", REACH_CSV, "| w1 not reproduced:", sum(1 for r in recs if not r["w1_ok"]))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
