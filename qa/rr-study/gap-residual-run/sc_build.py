#!/usr/bin/env python3
"""SUB-COVER (#273) oracle-buffer builder (spec 871e163f + Amendment 1 0cd47417). QA tooling, no src/ or native/ change, no station, no replay.

    python sc_build.py obuild            O-BUILD: the builder given ONLY the batch-1 re-encodable natives reproduces the stored R2 (400 cycles; STOP on failure)
    python sc_build.py oround            O-ROUND: the same set with dt rounded to 0.1 s; writes the rounded buffers (R2R) for the forced-leg comparison
    python sc_build.py ostar             O-STAR: O minus the fit of EVERY decode the product published (batches 1-4); writes the O* buffers

How the product builds R2 (SubtractionPass.RunCoreUnguarded, read for this file): candidates = the pass-0 natives (in native order) that pass IsReencodable (no '<', >= 3 tokens) and
EncodeMessage; ONE analytic signal of O; each candidate fitted on it (ft8_subfeas_fit_signal(xaRe, xaIm, tones, native dt, native freq)); residual = O copied, then residual[s] -= shat[s]
candidate by candidate in float32 (rc 0 or -3, the latter an all-zero shat). The builder repeats exactly that.
Natives: the capture already stored the product's OWN natives per buffer (cap/off/native/<stamp>.tsv: buf, freq, dt UNROUNDED, snr, text, in native order), so nothing is re-decoded
(Amendment 1 A1.1 proposed a re-decode; the stored natives are better: same hash state, same order). Batch 4 (the fallback rows) has no stored natives: it is placed from the published values.
Oracle part: a decode whose own text is not re-encodable (hashed '<...>', < 3 tokens, or EncodeMessage refuses it) is re-encoded from the matched WSJT-X text for that decode; neither -> `unencodable`.
HK-037: message text is read in memory here and never written; outputs are float32 buffers and counts under _qa-scratch."""
from __future__ import annotations

import collections
import ctypes
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import nrtax_defs as D      # noqa: E402

GR = "D:/Projects/claude/_qa-scratch/gap-residual"
CAP = GR + "/cap/off"
SC = "D:/Projects/claude/_qa-scratch/sub-cover"
NC_DUMP = GR + "/scratch/off/nc_dump.tsv"
PCM = 180000
KIND_BUF = {1: "O", 2: "R2", 3: "R3"}
MAX_REL_DIFF = 1e-5            # O-BUILD tolerance (spec A1.2): max |diff| <= 1e-5 x the buffer's peak, bit-identical preferred and reported
assert PCM == 180000 and MAX_REL_DIFF == 1e-5


class FT8Result(ctypes.Structure):
    _fields_ = [("freq_hz", ctypes.c_int), ("dt", ctypes.c_float), ("snr", ctypes.c_int), ("message", ctypes.c_char * 36)]


assert ctypes.sizeof(FT8Result) == 48

_W = {}


def _init():
    dec = F.load_dec()
    f32p = ctypes.POINTER(ctypes.c_float)
    u8p = ctypes.POINTER(ctypes.c_uint8)
    dll = dec.dll
    dll.ft8_encode_message.restype = ctypes.c_int
    dll.ft8_encode_message.argtypes = [ctypes.c_char_p, u8p, ctypes.c_int]
    dll.ft8_subfeas_compute_analytic.restype = ctypes.c_int
    dll.ft8_subfeas_compute_analytic.argtypes = [f32p, f32p, f32p]
    dll.ft8_subfeas_fit_signal.restype = ctypes.c_int
    dll.ft8_subfeas_fit_signal.argtypes = [f32p, f32p, u8p, ctypes.c_float, ctypes.c_float, f32p, ctypes.c_void_p]
    dll.ft8_subfeas_pool_configure.restype = None
    dll.ft8_subfeas_pool_configure.argtypes = [ctypes.c_int]
    dll.ft8_subfeas_pool_configure(1)
    _W["dll"] = dll


def _p(a):
    return a.ctypes.data_as(ctypes.POINTER(ctypes.c_float))


def encode(text):
    t = (ctypes.c_uint8 * 79)()
    rc = _W["dll"].ft8_encode_message(text.encode("ascii", "replace"), t, 79)
    return bytes(t) if rc == 79 else None


def analytic(pcm):
    re_, im_ = np.empty(PCM, np.float32), np.empty(PCM, np.float32)
    rc = _W["dll"].ft8_subfeas_compute_analytic(_p(pcm), _p(re_), _p(im_))
    assert rc == 0, rc
    return re_, im_


def fit(re_, im_, tones, dt, freq):
    shat = np.empty(PCM, np.float32)
    t = (ctypes.c_uint8 * 79).from_buffer_copy(tones)
    rc = _W["dll"].ft8_subfeas_fit_signal(_p(re_), _p(im_), t, ctypes.c_float(dt), ctypes.c_float(freq), _p(shat), None)
    assert rc in (0, -3), f"unexpected fit rc {rc}"
    return rc, shat


def load_buf(stamp, kind):
    p = f"{CAP}/buffers/{stamp}_{kind}.f32"
    return np.fromfile(p, dtype=np.float32) if os.path.isfile(p) else None


def load_natives(stamp):
    out = collections.defaultdict(list)
    for line in open(f"{CAP}/native/{stamp}.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5:
            out[p[0]].append((int(p[1]), float(np.float32(p[2])), int(p[3]), p[4]))
    return out


def subtract_all(o, cands, re_, im_):
    """residual = O copy; sequential float32 subtraction in candidate order; returns (residual, n_fit_zero)."""
    res = o.copy()
    zero = 0
    for tones, dt, freq in cands:
        rc, shat = fit(re_, im_, tones, np.float32(dt), np.float32(freq))
        if rc == -3:
            zero += 1
        res -= shat
    return res, zero


def job_r2(args):
    """O-BUILD / O-ROUND for one cycle: batch-1 re-encodable natives only."""
    stamp, round_dt = args
    o = load_buf(stamp, "O")
    nat = load_natives(stamp)
    cands = []
    for freq, dt, snr, text in nat.get("O", []):
        if not D.reencodable(text.rstrip()):
            continue
        tones = encode(text.rstrip())
        if tones is None:
            continue
        cands.append((tones, round(dt, 1) if round_dt else dt, freq))
    stored = load_buf(stamp, "R2")
    if not cands:
        return {"stamp": stamp, "cands": 0, "stored_r2": stored is not None, "maxdiff": 0.0, "rel": 0.0, "bitident": stored is None or bool(np.array_equal(stored, o))}
    re_, im_ = analytic(o)
    res, zero = subtract_all(o, cands, re_, im_)
    if round_dt:
        res.tofile(f"{SC}/cap/buffers/{stamp}_R2R.f32")
    if stored is None:
        return {"stamp": stamp, "cands": len(cands), "stored_r2": False, "maxdiff": None, "rel": None, "bitident": False, "fit_zero": zero}
    d = float(np.max(np.abs(res - stored)))
    pk = float(np.max(np.abs(stored)))
    return {"stamp": stamp, "cands": len(cands), "stored_r2": True, "maxdiff": d, "rel": d / pk if pk else 0.0, "bitident": bool(np.array_equal(res, stored)), "fit_zero": zero}


def load_published():
    """stamp -> list of dict(kind, f, dt, snr, text) in nc_dump order (every output of the product, batches 1-4)."""
    d = collections.defaultdict(list)
    for r in C.load_tsv(NC_DUMP):
        if len(r) >= 11:
            d[r[0]].append(dict(kind=int(r[1]), f=int(r[3]), dt=float(r[4]), snr=int(r[5]), text="\t".join(r[10:])))
    return d


def oracle_texts(pop, ref):
    """(stamp, kind, f, round(dt,1), snr) -> WSJT-X text of the REF row that decode matched (population rows carry ows_freq / ows_dt / ows_snr / kind)."""
    m = {}
    for r in pop["rows"]:
        if r["matched"]:
            m[(r["stamp"], r["kind"], r["ows_freq"], round(r["ows_dt"], 1), r["ows_snr"])] = ref[r["stamp"]][r["idx"]][3]
    return m


def job_ostar(args):
    stamp, pubs, orac = args          # pubs: list of dict; orac: {(kind,f,dt1,snr): wsjtx_text}
    o = load_buf(stamp, "O")
    nat = load_natives(stamp)
    used = collections.defaultdict(set)
    cands, rec = [], {"stamp": stamp, "decodes": len(pubs), "unencodable": 0, "native_unmatched": 0, "oracle_text_used": 0, "by_kind": collections.Counter(), "subtracted": []}
    for pk in pubs:
        k = pk["kind"]
        place = (pk["dt"], pk["f"])
        if k in KIND_BUF:
            hit = None
            for i, (freq, dt, snr, text) in enumerate(nat.get(KIND_BUF[k], [])):
                if i not in used[k] and freq == pk["f"] and snr == pk["snr"] and abs(round(dt, 1) - round(pk["dt"], 1)) < 1e-6:
                    hit = i
                    break
            if hit is None:
                rec["native_unmatched"] += 1
            else:
                used[k].add(hit)
                place = (nat[KIND_BUF[k]][hit][1], nat[KIND_BUF[k]][hit][0])
        text = pk["text"].rstrip()
        tones = encode(text) if D.reencodable(text) else None
        if tones is None:
            otext = orac.get((k, pk["f"], round(pk["dt"], 1), pk["snr"]))
            if otext is not None and D.reencodable(otext.rstrip()):
                tones = encode(otext.rstrip())
                if tones is not None:
                    rec["oracle_text_used"] += 1
        if tones is None:
            rec["unencodable"] += 1
            continue
        cands.append((tones, place[0], place[1]))
        rec["by_kind"][k] += 1
        rec["subtracted"].append((k, pk["f"], round(pk["dt"], 1), pk["snr"]))
    re_, im_ = analytic(o)
    res, zero = subtract_all(o, cands, re_, im_)
    res.tofile(f"{SC}/cap/buffers/{stamp}_OSTAR.f32")
    rec["fit_zero"] = zero
    rec["by_kind"] = dict(rec["by_kind"])
    return rec


def run_pool(fn, jobs, workers=8):
    t0 = time.time()
    with mp.Pool(workers, initializer=_init) as pool:
        out = list(pool.imap_unordered(fn, jobs, chunksize=2))
    return out, time.time() - t0


def main():
    cmd = sys.argv[1]
    os.makedirs(SC + "/cap/buffers", exist_ok=True)
    stamps = [l.split("\t")[0] for l in open(CAP + "/capture_index.tsv", encoding="utf-8")]
    assert len(stamps) == 400
    if cmd in ("obuild", "oround"):
        out, secs = run_pool(job_r2, [(s, cmd == "oround") for s in stamps])
        rel = [r["rel"] for r in out if r["rel"] is not None]
        res = {"cmd": cmd, "cycles": len(out), "seconds": round(secs), "cycles_with_candidates": sum(1 for r in out if r["cands"]), "candidates_total": sum(r["cands"] for r in out),
               "bit_identical_cycles": sum(1 for r in out if r.get("bitident")), "stored_r2_missing_but_candidates": sum(1 for r in out if r["cands"] and not r["stored_r2"]),
               "max_rel_diff": max(rel) if rel else 0.0, "cycles_rel_gt_1e-5": sum(1 for x in rel if x > MAX_REL_DIFF), "fit_zero_total": sum(r.get("fit_zero", 0) for r in out)}
        if cmd == "obuild":
            res["O-BUILD"] = {"PASS": res["cycles_rel_gt_1e-5"] == 0 and res["stored_r2_missing_but_candidates"] == 0}
        json.dump({"summary": res, "cycles": sorted(out, key=lambda r: r["stamp"])}, open(f"{SC}/{cmd}.json", "w"), indent=1)
        print(json.dumps(res, indent=1))
    elif cmd == "ostar":
        pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
        ref = C.load_ref(set(stamps))
        orac = oracle_texts(pop, ref)
        pubs = load_published()
        jobs = []
        for s in stamps:
            oc = {(k[1], k[2], k[3], k[4]): v for k, v in orac.items() if k[0] == s}
            jobs.append((s, pubs.get(s, []), oc))
        out, secs = run_pool(job_ostar, jobs)
        dec_total = sum(r["decodes"] for r in out)
        bad = sum(r["unencodable"] for r in out) + sum(r["fit_zero"] for r in out)
        res = {"cycles": len(out), "seconds": round(secs), "decodes": dec_total, "unencodable": sum(r["unencodable"] for r in out), "fit_zero": sum(r["fit_zero"] for r in out),
               "oracle_text_used": sum(r["oracle_text_used"] for r in out), "native_unmatched_kinds123": sum(r["native_unmatched"] for r in out),
               "unencodable_plus_fit_zero_share": bad / dec_total, "by_kind": dict(sum((collections.Counter(r["by_kind"]) for r in out), collections.Counter()))}
        json.dump({"summary": res, "cycles": sorted(out, key=lambda r: r["stamp"])}, open(f"{SC}/ostar.json", "w"))
        print(json.dumps(res, indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    mp.freeze_support()
    main()
