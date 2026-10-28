#!/usr/bin/env python3
"""GAP-RELOCATE item 2: population, pilot and forced legs (spec 690e8cb5 + Amendments 1-2).

  prep   : rebuild the BOTH arm's matching in Python (asserted == Replay81's matchedbatch.csv), define M / K, tag K paths, write rows.json
  pilot  : delta_p / delta_c from the PILOT cycles' K pairs (median of production - REF position), force the pilot's K rows, P_ctrl; STOP if < 0.90
  main   : the remaining K rows and every M row (forced primary on 9 cells, forced coherent V3 + the multi-set walk)

Only counts, positions, booleans and F1b values are written; message text is read in memory (REF text for true_codeword) and never persisted.
The records file holds stamp + index + numbers; the population file holds stamp + index + numbers + class flags.
Bars/constants are assertions in code (HK rule), not prose.
"""
from __future__ import annotations

import collections
import ctypes
import json
import math
import multiprocessing as mp
import os
import random
import statistics
import sys
import time

import numpy as np

import gr_common as C

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-locate"))
sys.path.insert(0, os.path.join(HERE, "..", "r2-coherent-llr-instrument"))
sys.path.insert(0, os.path.join(HERE, "..", "n1-extract-llrs-at-position"))
import comparator as CMP        # noqa: E402
import lattice                  # noqa: E402
import wavio                    # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs, a91_to_bits  # noqa: E402

DLL = os.path.join(C.S, "bin", "libft8.dll")
DLL_PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
SHIM = 20260071
NHARD = 24
K_MIN_SCORE_PASS2, OSD_CORR_THRESHOLD = 10, 0.10
LDPC_ITERS, OSD_DEPTH = 50, 2
FT8_PAYLOAD_BITS = 77
V_STAR = (0, 32373)             # RR73 as on-air tokens pack (GAP-LOCATE ROW 0f / Amendment 4: 122/122 rows)
T1_DB = 17.552446               # header: gated = F1b <= T1
SEED = 20261028
K_N = 2000
K_ORIG_MIN = 1500               # A1.1
PILOT_CYCLES = 40               # A1.2
P_CTRL_BAR = 0.90               # 0c, source: GAP-LOCATE 0c' 95.96 % (spec section 4)
CORROB_HZ = 10                  # Replay81 CorroborationDeltaHz
FLAG_FORCE_C3 = 1
assert T1_DB == 17.552446 and V_STAR == (0, 32373) and PILOT_CYCLES == 40


class CohResult(ctypes.Structure):          # FT8CohFallbackResult, sizeof 112
    _fields_ = [("est_df_hz", ctypes.c_double), ("est_dt_s", ctypes.c_double), ("peak", ctypes.c_double), ("f1b_db", ctypes.c_double),
                ("estimate_ms", ctypes.c_double), ("f1b_ms", ctypes.c_double), ("c3_bp_ms", ctypes.c_double), ("elapsed_ms", ctypes.c_double),
                ("dt_step", ctypes.c_int32), ("edge", ctypes.c_int32), ("n_refs", ctypes.c_int32), ("gated", ctypes.c_int32),
                ("c3_ran", ctypes.c_int32), ("bp_rc", ctypes.c_int32), ("bp_path", ctypes.c_int32), ("bp_crc_ok", ctypes.c_int32),
                ("bp_ldpc_errors", ctypes.c_int32), ("a91", ctypes.c_uint8 * 12)]


class SetOutcome(ctypes.Structure):         # FT8CohSetOutcome, sizeof 32
    _fields_ = [("bp_rc", ctypes.c_int32), ("bp_path", ctypes.c_int32), ("bp_crc_ok", ctypes.c_int32), ("bp_ldpc_errors", ctypes.c_int32),
                ("a91", ctypes.c_uint8 * 12), ("reserved", ctypes.c_int32)]


class SetsResult(ctypes.Structure):         # FT8CohSetsResult, sizeof 216
    _fields_ = [("est_df_hz", ctypes.c_double), ("est_dt_s", ctypes.c_double), ("peak", ctypes.c_double),
                ("dt_step", ctypes.c_int32), ("edge", ctypes.c_int32), ("walk_entered", ctypes.c_int32), ("walk_set", ctypes.c_int32),
                ("walk_a91", ctypes.c_uint8 * 12), ("reserved", ctypes.c_int32),
                ("v3", SetOutcome), ("sets", SetOutcome * 4)]


assert ctypes.sizeof(CohResult) == 112 and ctypes.sizeof(SetOutcome) == 32 and ctypes.sizeof(SetsResult) == 216


def load_dec():
    import hashlib
    h = hashlib.sha256(open(DLL, "rb").read()).hexdigest()
    assert h == DLL_PIN, h
    dec = LdpcDecodeLLRs(DLL, verify=True, expected_sha256=DLL_PIN, expected_shim_version=SHIM, check_version=True)
    dec.dll.ft8_set_decode_params(K_MIN_SCORE_PASS2, ctypes.c_float(OSD_CORR_THRESHOLD), NHARD)
    dec.dll.ft8_set_osd_sign_fix(1)
    f32p = ctypes.POINTER(ctypes.c_float)
    dec.dll.ft8_coherent_fallback_at.restype = ctypes.c_int
    dec.dll.ft8_coherent_fallback_at.argtypes = [f32p, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_int,
                                                 ctypes.POINTER(CohResult), f32p]
    dec.dll.ft8_coherent_fallback_sets_at.restype = ctypes.c_int
    dec.dll.ft8_coherent_fallback_sets_at.argtypes = [f32p, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_int,
                                                      ctypes.POINTER(SetsResult), ctypes.POINTER(ctypes.c_double)]
    return dec


def coh_at(dec, pcm, freq, t, flags):
    r = CohResult()
    rc = dec.dll.ft8_coherent_fallback_at(pcm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 180000, freq, t, flags, ctypes.byref(r), None)
    return rc, r


def sets_at(dec, pcm, freq, t):
    r = SetsResult()
    rc = dec.dll.ft8_coherent_fallback_sets_at(pcm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), 180000, freq, t, 0, ctypes.byref(r), None)
    return rc, r


# ── population ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def rebuild_matching(ref, nc):
    """Replay81.ScoreTestB's one-to-one nearest-first text match across batches 1-4; returns stamp -> {ref_idx: (kind, freq, dt, snr, text)}."""
    out = {}
    for s, w in ref.items():
        ows = nc.get(s, [])
        cands = []
        for i, o in enumerate(ows):
            for j, r in enumerate(w):
                df = abs(o[2] - r[2])
                if df <= CORROB_HZ and o[6] == r[3]:
                    cands.append((df, i, j))
        cands.sort()
        uo, uw, m = set(), set(), {}
        for _, oi, wi in cands:
            if oi in uo or wi in uw:
                continue
            uo.add(oi)
            uw.add(wi)
            o = ows[oi]
            m[wi] = (o[0], o[2], o[3], o[4], o[6])
        out[s] = m
    return out


def prep():
    import gr_item1 as I1
    stamps = C.selection_stamps()
    ref = C.load_ref(set(stamps))
    both = I1.load_arm("both")
    mb = both["mb"]
    match = rebuild_matching(ref, both["nc"])
    # assertion: the Python matching reproduces Replay81's matchedbatch.csv exactly
    bad = 0
    for s in stamps:
        mine = {i: v[0] for i, v in match.get(s, {}).items()}
        if mine != mb.get(s, {}):
            bad += 1
    assert bad == 0, f"matching differs from matchedbatch.csv in {bad} cycles"
    rows, hits = [], []
    for s in stamps:
        evs = both["ev"].get(s, [])
        dtexts = {(e[1] if len(e) > 1 else "") for e in evs if e[0] == "D"}
        # origin of fallback payloads (A1.1): in a two-run cycle run 1 is the original audio; in a one-run cycle the single run is original
        rr = both["R"].get(s, [])
        nruns = len({r[0] for r in rr}) if rr else 0
        stage = both["stage"].get(s)
        k = list(stage.keys())
        runs_s = stage[k[1]]
        n_runs = 0 if runs_s == "-" else len(runs_s.split("|"))
        orig_runs = {1} if n_runs == 2 else {0}
        orig_payloads = {p for (r, p, *_x) in rr if r in orig_runs}
        text2payload = {t: p for (p, t) in both["U"].get(s, []) if t}
        for j, (snr, dt, freq, text) in enumerate(ref.get(s, [])):
            row = {"stamp": s, "idx": j, "snr": snr, "dt": dt, "freq": freq, "band": C.band_of(snr),
                   "n_cycle_ref": len(ref[s]), "p_flag": text in dtexts}
            if j in match[s]:
                kind, ofreq, odt, osnr, otext = match[s][j]
                row.update(matched=True, kind=kind, ows_freq=ofreq, ows_dt=odt, ows_snr=osnr)
                if kind == 4:
                    p = text2payload.get(otext)
                    row["tag"] = "fb_orig" if p in orig_payloads else "fb_res"
                else:
                    row["tag"] = "b123"
                hits.append(len(rows))
            else:
                row.update(matched=False, kind=0, tag="miss")
            rows.append(row)
    rng = random.Random(SEED)
    perm = sorted(hits)
    rng.shuffle(perm)
    kidx = perm[:K_N]
    norig = sum(1 for i in kidx if rows[i]["tag"] != "fb_res")
    extended = 0
    nxt = K_N
    while norig < K_ORIG_MIN and nxt < len(perm):
        kidx.append(perm[nxt])
        if rows[perm[nxt]]["tag"] != "fb_res":
            norig += 1
        nxt += 1
        extended += 1
    kset = set(kidx)
    for i, r in enumerate(rows):
        r["K"] = i in kset
        r["pilot"] = r["stamp"] in set(stamps[:PILOT_CYCLES])
    pop = {"stamps": stamps, "n_ref": len(rows), "n_hits": len(hits), "n_miss": len(rows) - len(hits), "K_n": len(kidx),
           "K_orig_path": norig, "K_extended_by": extended, "rows": rows}
    json.dump(pop, open(C.S + "\\population.json", "w"))
    cnt = collections.Counter((r["K"], r["tag"]) for r in rows)
    print(json.dumps({k: v for k, v in pop.items() if k != "rows"}), dict((str(k), v) for k, v in cnt.items()))


# ── forced legs ────────────────────────────────────────────────────────────────────────────────────────────────────────
_W = {}


def _init():
    _W["dec"] = load_dec()
    _W["ref"] = None


def force_cycle(job):
    stamp, rowlist, dp, dc = job
    dec = _W["dec"]
    if _W.get("ref") is None:
        _W["ref"] = C.load_ref(set(C.selection_stamps()))
    ref = _W["ref"]
    pcm = wavio.load_cycle_pcm(os.path.join(C.WAVDIR, stamp + ".wav"))
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)
    assert pcm.shape == (180000,)
    out = []
    for r in rowlist:
        snr, dt, freq, text = ref[stamp][r["idx"]]
        rec = {"stamp": stamp, "idx": r["idx"], "unencodable": False}
        x_true = dec.true_codeword(text)
        if x_true is None:
            rec["unencodable"] = True
            out.append(rec)
            continue
        X = x_true[:FT8_PAYLOAD_BITS]
        # forced primary: 9 cells, centre first
        fp = {"found": False, "cell": None, "wrong": 0, "fault": 0, "path": None}
        for cell in lattice.snap_and_neighbours(freq, dt + dp):
            rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
            if rc != 0:
                fp["fault"] += 1
                continue
            res = dec.ldpc_decode_llrs(llr, max_iters=LDPC_ITERS, osd_depth=OSD_DEPTH)
            if res["a91"] is None or res["crc_ok"] != 1:
                continue
            Y = a91_to_bits(res["a91"], FT8_PAYLOAD_BITS)
            if CMP.payload_match(X, Y, text, V_STAR):
                fp.update(found=True, cell="centre" if cell["is_centre"] else "neighbour", path=res["path"])
                break
            fp["wrong"] += 1
        rec["fp"] = fp
        # forced coherent V3 (FORCE_C3) and the multi-set walk, anchored at the REF position
        t_c = dt + dc
        fc = {"v3_match": False, "gated": None, "f1b_db": None, "v3_crc": False, "v3_wrong": False, "fault": 0}
        rc, cr = coh_at(dec, pcm, float(freq), float(t_c), FLAG_FORCE_C3)
        if rc != 0:
            fc["fault"] += 1
        else:
            fc["gated"] = int(cr.gated)
            fc["f1b_db"] = None if (math.isnan(cr.f1b_db) or math.isinf(cr.f1b_db)) else float(cr.f1b_db)
            fc["f1b_inf"] = bool(math.isinf(cr.f1b_db))
            if cr.c3_ran and cr.bp_crc_ok == 1:
                fc["v3_crc"] = True
                Y = a91_to_bits(bytes(cr.a91), FT8_PAYLOAD_BITS)
                if CMP.payload_match(X, Y, text, V_STAR):
                    fc["v3_match"] = True
                else:
                    fc["v3_wrong"] = True
        rec["fc"] = fc
        wk = {"entered": False, "set": None, "match": False, "wrong": False, "fault": 0, "set_match": [False] * 4}
        rc, sr = sets_at(dec, pcm, float(freq), float(t_c))
        if rc != 0:
            wk["fault"] += 1
        else:
            wk["entered"] = bool(sr.walk_entered)
            wk["set"] = int(sr.walk_set)
            for si in range(4):
                so = sr.sets[si]
                if so.bp_crc_ok == 1:
                    Yb = a91_to_bits(bytes(so.a91), FT8_PAYLOAD_BITS)
                    wk["set_match"][si] = bool(CMP.payload_match(X, Yb, text, V_STAR))
            if sr.walk_entered and sr.walk_set > 0:
                Yw = a91_to_bits(bytes(sr.walk_a91), FT8_PAYLOAD_BITS)
                if CMP.payload_match(X, Yw, text, V_STAR):
                    wk["match"] = True
                else:
                    wk["wrong"] = True
        rec["walk"] = wk
        out.append(rec)
    return out


def run_forced(rows, dp, dc, out_path, workers=8):
    done = set()
    if os.path.isfile(out_path):
        for line in open(out_path, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["stamp"], r["idx"]))
    bycyc = collections.OrderedDict()
    for r in rows:
        if (r["stamp"], r["idx"]) not in done:
            bycyc.setdefault(r["stamp"], []).append(r)
    jobs = [(s, rl, dp, dc) for s, rl in bycyc.items()]
    t0 = time.time()
    n = 0
    with open(out_path, "a", encoding="utf-8") as fh, mp.Pool(workers, initializer=_init) as pool:
        for recs in pool.imap_unordered(force_cycle, jobs):
            for rec in recs:
                fh.write(json.dumps(rec) + "\n")
            fh.flush()
            n += 1
            if n % 20 == 0:
                print(f"  {n}/{len(jobs)} cycles, {time.time()-t0:.0f}s", flush=True)
    return len(jobs)


def load_pop():
    return json.load(open(C.S + "\\population.json", encoding="utf-8"))


def deltas_from_pilot(pop):
    pk = [r for r in pop["rows"] if r["K"] and r["pilot"]]
    dpv = [r["ows_dt"] - r["dt"] for r in pk if r["kind"] in (1, 2, 3)]
    dcv = [r["ows_dt"] - r["dt"] for r in pk if r["kind"] == 4]
    dp, dc = statistics.median(dpv), statistics.median(dcv) if dcv else statistics.median(dpv)
    return {"delta_p": dp, "delta_c": dc, "n_pairs_p": len(dpv), "n_pairs_c": len(dcv),
            "iqr_p": [float(np.percentile(dpv, 25)), float(np.percentile(dpv, 75))],
            "iqr_c": [float(np.percentile(dcv, 25)), float(np.percentile(dcv, 75))] if dcv else None}


def success(rec):
    if rec.get("unencodable"):
        return None
    return (rec["fp"]["found"], rec["fc"]["v3_match"] and rec["fc"]["gated"] is not None, rec["walk"]["match"])


def main():
    cmd = sys.argv[1]
    if cmd == "prep":
        prep()
        return
    pop = load_pop()
    if cmd == "pilot":
        d = deltas_from_pilot(pop)
        json.dump(d, open(C.S + "\\deltas.json", "w"), indent=1)
        print("deltas (frozen)", d)
        rows = [r for r in pop["rows"] if r["K"] and r["pilot"]]
        run_forced(rows, d["delta_p"], d["delta_c"], C.S + "\\forced_pilot.jsonl")
        recs = [json.loads(x) for x in open(C.S + "\\forced_pilot.jsonl", encoding="utf-8")]
        key = {(r["stamp"], r["idx"]): r for r in pop["rows"]}
        orig = [x for x in recs if not x["unencodable"] and key[(x["stamp"], x["idx"])]["tag"] != "fb_res"]
        pu = sum(1 for x in orig if x["fp"]["found"] or x["fc"]["v3_match"] or x["walk"]["match"])
        pp = sum(1 for x in orig if x["fp"]["found"])
        print(json.dumps({"pilot_K_original_path": len(orig), "P_ctrl_union": pu / len(orig), "P_ctrl_p": pp / len(orig),
                          "bar": P_CTRL_BAR, "STOP": pu / len(orig) < P_CTRL_BAR}))
        return
    if cmd == "main":
        d = json.load(open(C.S + "\\deltas.json"))
        rows = [r for r in pop["rows"] if (r["K"] and not r["pilot"]) or not r["matched"]]
        run_forced(rows, d["delta_p"], d["delta_c"], C.S + "\\forced_main.jsonl")
        return
    raise SystemExit("usage: gr_forced.py prep|pilot|main")


if __name__ == "__main__":
    mp.freeze_support()
    main()
