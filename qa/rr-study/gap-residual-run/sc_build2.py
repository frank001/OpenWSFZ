#!/usr/bin/env python3
"""SUB-COVER v2 (#273) builder (spec `arch/sub-coverage` f68f4ce9 + Amendment 1 50149101). QA tooling, no src/ or native/ change, no station, no replay. sc_build.py (v1) is NOT changed.

    python sc_build2.py calib      BEFORE any O*v2 output: c, tau_f, tau_t from this night's text-equal pairs (spec 1.2); STOP if tau_f > 6.25 Hz or tau_t > 0.16 s. Writes v2/calib.json
    python sc_build2.py ceiling    A1.4: of the 112 #273-proper rows, how many have >= 1 route-1-rejected neighbour (pp of n_ref). Needs calib.json. Writes v2/ceiling.json
    python sc_build2.py selftest   encode -> payload -> unpack round trip on synthetic Q-calls (no real message text)
    python sc_build2.py ov1        O-V1: route 2 OFF and the IsReencodable pre-filter ON reproduces the stored O*v1 buffers bit-identically in 400/400 cycles. Needs no O*v2 output.
    python sc_build2.py ov1cmp     O-V1 comparison only: the written v2/buffers/*_OSTAR1V.f32 against the stored O*v1 buffers (cap/buffers/*_OSTAR.f32), rewrites v2/ov1.json's verdict
    python sc_build2.py ostar2     O*v2: route 1 without the pre-filter, route 2 = the position oracle (spec 1.2). Writes v2 buffers + v2/ostar2.json (+ route2.jsonl of candidate rows for the forced legs)

Route 2, per decode that route 1 rejects (EncodeMessage fails on our text with NO pre-filter), at its placement (native freq/dt where stored, else the published value, as v1) (f, t):
  candidates = this cycle's WSJT-X rows with |f_W - f| <= tau_f and |(t_W - c) - t| <= tau_t, EXCLUDING rows text-matched to a DIFFERENT decode of ours (A1.3);
  consistent(candidate) = strip '<' '>' from its text -> EncodeMessage -> 77 payload bits (as SubfeasPayload.ExtractPayload77) -> ft8_coherent_fallback_unpack, the whole step bracketed with
  ft8_hash_state_save / restore; equal to OUR text after replacing every bracketed token by '<...>' in BOTH strings (nothing else normalised);
  exactly one consistent candidate -> use its encoded tones (route=oracle); none -> inconsistent (no_candidate if there were no candidates at all); two or more -> ambiguous.
HK-037: message text is read in memory inside this script and never written; outputs are float32 buffers, counts, and (stamp, idx, numbers) records."""
from __future__ import annotations

import collections
import ctypes
import json
import multiprocessing as mp
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import sc_build as B        # noqa: E402  (v1, unchanged)
import gr_common as C       # noqa: E402
import nrtax_defs as D      # noqa: E402

SC = B.SC
V2 = SC + "/v2"
GR, CAP = B.GR, B.CAP
TAU_F_MAX_HZ, TAU_T_MAX_S = 6.25, 0.16        # spec 1.2: one FT8 tone / one symbol; a wider tolerance could admit a different transmission
COSTAS = ((0, 7), (36, 43), (72, 79))          # SubfeasPayload.CostasBlocks (start, len) = (0,7) (36,7) (72,7)
GRAY_MAP = (0, 1, 3, 2, 5, 6, 4, 7)            # SubfeasPayload.GrayMap
INV_GRAY = [0] * 8
for _v, _t in enumerate(GRAY_MAP):
    INV_GRAY[_t] = _v
assert INV_GRAY == [0, 1, 3, 2, 6, 4, 5, 7] and TAU_F_MAX_HZ == 6.25 and TAU_T_MAX_S == 0.16
BRACKET = re.compile(r"<[^>]*>")
N_REF_EXPECTED = 12124


def _init2():
    B._init()
    dll = B._W["dll"]
    dll.ft8_coherent_fallback_unpack.restype = ctypes.c_int
    dll.ft8_coherent_fallback_unpack.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    dll.ft8_hash_state_size.restype = ctypes.c_int
    dll.ft8_hash_state_size.argtypes = []
    dll.ft8_hash_state_save.restype = ctypes.c_int
    dll.ft8_hash_state_save.argtypes = [ctypes.c_void_p, ctypes.c_int]
    dll.ft8_hash_state_restore.restype = ctypes.c_int
    dll.ft8_hash_state_restore.argtypes = [ctypes.c_void_p, ctypes.c_int]
    B._W["hsz"] = dll.ft8_hash_state_size()
    assert B._W["hsz"] > 0


def payload10(tones):
    """77 payload bits (the first 77 of the 174 codeword bits, Costas symbols skipped, inverse Gray, MSB first) packed MSB-first into 10 bytes, last 3 bits zero."""
    bits = []
    for sym in range(79):
        if any(a <= sym < b for a, b in COSTAS):
            continue
        v = INV_GRAY[tones[sym]]
        bits += [(v >> 2) & 1, (v >> 1) & 1, v & 1]
        if len(bits) >= 77:
            break
    bits = bits[:77]
    assert len(bits) == 77
    out = bytearray(10)
    for i, b in enumerate(bits):
        if b:
            out[i // 8] |= 0x80 >> (i % 8)
    return bytes(out)


def unpack(payload):
    buf = ctypes.create_string_buffer(64)
    rc = B._W["dll"].ft8_coherent_fallback_unpack(payload, buf, 64)
    return None if rc != 0 else buf.value.decode("ascii", "replace")


def norm(s):
    return BRACKET.sub("<...>", s.strip())


def consistent_tones(cand_text, our_text):
    """spec 1.2 consistency check for one candidate; hash state saved and restored around it. Returns the tones or None."""
    dll = B._W["dll"]
    sz = B._W["hsz"]
    img = ctypes.create_string_buffer(sz)
    assert dll.ft8_hash_state_save(img, sz) == sz
    try:
        tones = B.encode(cand_text.replace("<", "").replace(">", "").strip())
        if tones is None:
            return None
        txt = unpack(payload10(tones))
        if txt is None:
            return None
        return tones if norm(txt) == norm(our_text) else None
    finally:
        assert dll.ft8_hash_state_restore(img, sz) == 0


def selftest():
    """Round trip on synthetic Q-calls only: encode(text) -> payload10 -> unpack == text; a bracketed text must NOT encode."""
    _init2()
    for t in ("CQ Q1ABC AA00", "Q2DEF Q1ABC -10", "Q1ABC Q3GHI RR73", "Q1ABC Q3GHI 73"):
        tones = B.encode(t)
        assert tones is not None, t
        got = unpack(payload10(tones))
        assert got is not None and got.strip() == t, (t, got)
    assert B.encode("<Q1ABC> Q2DEF -10") is None
    print("selftest PASS: 4 synthetic texts round-trip; a bracketed text does not encode")


# ---- shared per-cycle data --------------------------------------------------------------------------------------------------

def load_all():
    stamps = [l.split("\t")[0] for l in open(CAP + "/capture_index.tsv", encoding="utf-8")]
    assert len(stamps) == 400
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    assert len(pop["rows"]) == N_REF_EXPECTED
    ref = C.load_ref(set(stamps))
    pubs = B.load_published()
    dec_idx, idx_dec = {}, {}
    for r in pop["rows"]:
        if r["matched"]:
            key = (r["stamp"], r["kind"], r["ows_freq"], round(r["ows_dt"], 1), r["ows_snr"])
            dec_idx[key] = r["idx"]
            idx_dec.setdefault((r["stamp"], r["idx"]), []).append(key)
    return stamps, pop, ref, pubs, dec_idx, idx_dec


def placements(stamp, pubs_cycle):
    """For each published decode: ((dt, f) placement as v1: native where found, else published, key (k, f, dt1, snr), text)."""
    nat = B.load_natives(stamp)
    used = collections.defaultdict(set)
    out = []
    for pk in pubs_cycle:
        k = pk["kind"]
        place = (pk["dt"], pk["f"])
        native = False
        if k in B.KIND_BUF:
            for i, (freq, dt, snr, text) in enumerate(nat.get(B.KIND_BUF[k], [])):
                if i not in used[k] and freq == pk["f"] and snr == pk["snr"] and abs(round(dt, 1) - round(pk["dt"], 1)) < 1e-6:
                    used[k].add(i)
                    place = (dt, freq)
                    native = True
                    break
        out.append((place, (k, pk["f"], round(pk["dt"], 1), pk["snr"]), pk["text"].rstrip(), native))
    return out


def pct(a, p):
    return float(np.percentile(np.asarray(a, dtype=float), p))


def calib():
    stamps, pop, ref, pubs, dec_idx, idx_dec = load_all()
    df, dt_off, kinds = [], [], collections.Counter()
    pairs = []
    for s in stamps:
        for place, key, text, native in placements(s, pubs.get(s, [])):
            idx = dec_idx.get((s,) + key)
            if idx is None:
                continue
            snr_w, dt_w, f_w, text_w = ref[s][idx]
            pairs.append((place[1], place[0], f_w, dt_w, key[0], native))
    f_o = np.array([p[0] for p in pairs], float)
    t_o = np.array([p[1] for p in pairs], float)
    f_w = np.array([p[2] for p in pairs], float)
    t_w = np.array([p[3] for p in pairs], float)
    c = float(np.median(t_w - t_o))
    af = np.abs(f_w - f_o)
    at = np.abs((t_w - c) - t_o)
    res = {"N": len(pairs), "by_kind": dict(collections.Counter(p[4] for p in pairs)), "n_native_placement": int(sum(1 for p in pairs if p[5])),
           "c_s": c, "tau_f_hz": pct(af, 99), "tau_t_s": pct(at, 99), "f_max_hz": float(af.max()), "t_max_s": float(at.max()),
           "tau_f_median": pct(af, 50), "tau_t_median": pct(at, 50),
           "STOP": bool(pct(af, 99) > TAU_F_MAX_HZ or pct(at, 99) > TAU_T_MAX_S)}
    os.makedirs(V2, exist_ok=True)
    json.dump(res, open(V2 + "/calib.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


def ceiling():
    _init2()
    stamps, pop, ref, pubs, dec_idx, idx_dec = load_all()
    tags = {}
    for line in open(GR + "/nrtax_row_tags.jsonl", encoding="utf-8"):
        r = json.loads(line)
        tags[(r["stamp"], r["idx"])] = r
    rows = pop["rows"]
    by_cycle = collections.defaultdict(list)
    for r in rows:
        by_cycle[r["stamp"]].append({"idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "decoded": bool(r["matched"]), "batch": r["kind"] if r["matched"] else 0})
    pub_text = {}
    for s in stamps:
        for pk in pubs.get(s, []):
            pub_text[(s, pk["kind"], pk["f"], round(pk["dt"], 1), pk["snr"])] = pk["text"].rstrip()
    n112 = with_rej = 0
    nbr_total = nbr_rej = 0
    for r in rows:
        k = (r["stamp"], r["idx"])
        if tags.get(k, {}).get("pop") != "NR" or tags[k]["cat"] != "CU-d":
            continue
        st = [n for n in by_cycle[r["stamp"]] if n["idx"] != r["idx"] and abs(n["freq"] - r["freq"]) < 50.0 and n["snr"] >= r["snr"] and n["decoded"]]
        if any(n["batch"] in (3, 4) for n in st):
            continue
        n112 += 1
        rej_here = False
        for n in st:
            for key in idx_dec.get((r["stamp"], n["idx"]), []):
                txt = pub_text.get(key)
                nbr_total += 1
                if txt is not None and B.encode(txt) is None:          # route 1 without the pre-filter
                    nbr_rej += 1
                    rej_here = True
        with_rej += rej_here
    res = {"stratum_rows": n112, "rows_with_route1_rejected_neighbour": with_rej, "n_ref": len(rows), "true_ceiling_pp": 100.0 * with_rej / len(rows),
           "ceiling_pp_stated_by_spec": 100.0 * 112 / len(rows), "neighbour_decodes_checked": nbr_total, "neighbour_decodes_route1_rejected": nbr_rej,
           "BUILD_WORTH_can_fire": bool(100.0 * with_rej / len(rows) >= 0.40)}
    assert n112 == 112, n112
    json.dump(res, open(V2 + "/ceiling.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


# ---- the builder ------------------------------------------------------------------------------------------------------------

def job_o(args):
    stamp, pubs_cycle, refrows, dec_idx_c, idx_dec_c, par, mode = args      # mode "v1" = pre-filter ON, route 2 OFF (O-V1); "v2" = pre-filter OFF, route 2 ON
    c, tf, tt = par
    o = B.load_buf(stamp, "O")
    cands = []
    rec = {"stamp": stamp, "decodes": len(pubs_cycle), "route": collections.Counter(), "by_kind_subtracted": collections.Counter(), "route2": []}
    matched_to_other = {}
    for idx, keys in idx_dec_c.items():
        matched_to_other[idx] = set(keys)
    for place, key, text, native in placements(stamp, pubs_cycle):
        tones = None
        if mode == "v1":
            tones = B.encode(text) if D.reencodable(text) else None
            route = "own" if tones is not None else "unencodable"
        else:
            tones = B.encode(text)
            route = "own" if tones is not None else None
            if tones is None:
                ok, nc = [], 0
                for idx, (snr_w, dt_w, f_w, text_w) in refrows.items():
                    if abs(f_w - place[1]) > tf or abs((dt_w - c) - place[0]) > tt:
                        continue
                    owners = matched_to_other.get(idx, set())
                    if owners and key not in owners:
                        continue            # A1.3: text-matched to a DIFFERENT decode of ours
                    nc += 1
                    t2 = consistent_tones(text_w, text)
                    if t2 is not None:
                        ok.append((idx, t2))
                if len(ok) == 1:
                    tones, route = ok[0][1], "oracle"
                    rec["route2"].append({"idx": ok[0][0], "k": key[0], "f": key[1], "dt1": key[2], "snr": key[3]})
                elif len(ok) >= 2:
                    route = "ambiguous"
                elif nc == 0:
                    route = "no_candidate"
                else:
                    route = "inconsistent"
        rec["route"][route] += 1
        if tones is None:
            continue
        cands.append((tones, place[0], place[1]))
        rec["by_kind_subtracted"][key[0]] += 1
    re_, im_ = B.analytic(o)
    res, zero = B.subtract_all(o, cands, re_, im_)
    name = "OSTAR2" if mode == "v2" else "OSTAR1V"
    res.tofile(f"{V2}/buffers/{stamp}_{name}.f32")
    rec["fit_zero"] = zero
    rec["route"] = dict(rec["route"])
    rec["by_kind_subtracted"] = dict(rec["by_kind_subtracted"])
    if mode == "v1":
        op = f"{SC}/cap/buffers/{stamp}_OSTAR.f32"          # the stored O*v1 buffer (v1's output folder, NOT the capture folder B.CAP)
        old = np.fromfile(op, dtype=np.float32) if os.path.isfile(op) else None
        rec["bitident_v1"] = bool(old is not None and np.array_equal(old, res))
    return rec


def run(mode):
    _init2()
    stamps, pop, ref, pubs, dec_idx, idx_dec = load_all()
    cal = json.load(open(V2 + "/calib.json"))
    assert not cal["STOP"], "calibration STOP row fired"
    par = (cal["c_s"], cal["tau_f_hz"], cal["tau_t_s"])
    os.makedirs(V2 + "/buffers", exist_ok=True)
    jobs = []
    for s in stamps:
        refrows = {i: row for i, row in enumerate(ref.get(s, []))}
        ic = {idx: keys for (st, idx), keys in idx_dec.items() if st == s}
        # keys carry the stamp-less (k, f, dt1, snr) tuples
        ic = {idx: [k[1:] for k in keys] for idx, keys in ic.items()}
        jobs.append((s, pubs.get(s, []), refrows, {}, ic, par, mode))
    out, secs = _pool(job_o, jobs)
    out = sorted(out, key=lambda r: r["stamp"])
    tot = collections.Counter()
    for r in out:
        tot.update(r["route"])
    summ = {"mode": mode, "cycles": len(out), "seconds": round(secs), "decodes": sum(r["decodes"] for r in out), "route": dict(tot),
            "fit_zero": sum(r["fit_zero"] for r in out), "by_kind_subtracted": dict(sum((collections.Counter(r["by_kind_subtracted"]) for r in out), collections.Counter())),
            "route2_subtracted": sum(len(r["route2"]) for r in out)}
    if mode == "v1":
        summ["bit_identical_cycles"] = sum(1 for r in out if r["bitident_v1"])
        summ["O-V1"] = {"PASS": summ["bit_identical_cycles"] == len(out) == 400}
    json.dump({"summary": summ, "cycles": out}, open(f"{V2}/{'ostar2' if mode == 'v2' else 'ov1'}.json", "w"))
    print(json.dumps(summ, indent=1))


def ov1cmp():
    stamps = [l.split("	")[0] for l in open(CAP + "/capture_index.tsv", encoding="utf-8")]
    n_ok = 0
    for s in stamps:
        a = np.fromfile(f"{V2}/buffers/{s}_OSTAR1V.f32", dtype=np.float32)
        b = np.fromfile(f"{SC}/cap/buffers/{s}_OSTAR.f32", dtype=np.float32)
        n_ok += bool(a.shape == b.shape and np.array_equal(a, b))
    j = json.load(open(V2 + "/ov1.json"))
    j["summary"]["bit_identical_cycles"] = n_ok
    j["summary"]["O-V1"] = {"PASS": n_ok == len(stamps) == 400}
    j["summary"]["note"] = "bit_identical_cycles recomputed by ov1cmp: the first run compared against the wrong folder (B.CAP), see the freeze record"
    json.dump(j, open(V2 + "/ov1.json", "w"))
    print(json.dumps(j["summary"]["O-V1"]), n_ok, "of", len(stamps))


def _pool(fn, jobs, workers=8):
    import time
    t0 = time.time()
    with mp.Pool(workers, initializer=_init2) as pool:
        out = list(pool.imap_unordered(fn, jobs, chunksize=2))
    return out, time.time() - t0


if __name__ == "__main__":
    mp.freeze_support()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "calib":
        calib()
    elif cmd == "ceiling":
        ceiling()
    elif cmd == "selftest":
        selftest()
    elif cmd == "ov1":
        run("v1")
    elif cmd == "ov1cmp":
        ov1cmp()
    elif cmd == "ostar2":
        run("v2")
    else:
        sys.exit(__doc__)
