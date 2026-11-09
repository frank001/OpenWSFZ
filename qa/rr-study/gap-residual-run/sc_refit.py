#!/usr/bin/env python3
"""CS-REFIT builder (spec `arch/cs-refit` ad74a8a0 + Amendment 1 5a971659). QA tooling, no src/ or native/ change, no replay, no station. Reuses sc_build.py (SUB-COVER v1) unchanged.

    python sc_refit.py repro     L-REPRO, BEFORE any S or I output: the builder with the procedure "as the product" (batch 1 fitted on O all at once -> R2; batch 2 fitted on R2 all at once -> R3)
                                 against the stored R3 (382 cycles; bit-identical or max |diff| <= 1e-5 x peak) and the stored R2 (400); writes the R3 baseline buffers (R3B = stored R3, or stored R2
                                 in the 18 cycles without R3, A1.1/A1.2); reports the 18 cycles' batch-2 candidate count (descriptive). STOP on failure, no retries.
    python sc_refit.py legs      the two legs on the stored inputs:
        S : the whole set ordered by OUR published snr descending (ties freq ascending, then batch); start from O; for each signal the analytic signal of the CURRENT residual is recomputed, that
            signal is fitted on it and subtracted.
        I : start from the stored R3 (R2 in the 18 cycles); every signal of the set fitted once more on R3's analytic signal at the same tones and natives, all corrections subtracted together.
Set (A1.1 + Amendment 2 A2.1): exactly what the product subtracted = batch-1 natives of O (re-encodable, encodable, native order) + the batch-2 set = the R2-buffer natives that EncodeMessage accepts, are
NOT SameQso (ported unchanged from SubfeasPayload.cs:152-168) with the payload of any batch-1 candidate, and then pass IsReencodable + EncodeMessage (SubtractionPass.cs:457-491, :331-343); in the 18 cycles
without a stored R3 batch 1 ONLY. The FIRST L-REPRO run (batch-2 set = every re-encodable R2 native) FAILED, see the freeze record.
Fit return codes counted (-3 = fit-zero). Per-cycle wall time of the product-procedure rebuild and of S on the SAME worker (A1.4: only the ratio is reported).
HK-037: message text is read in memory and never written; outputs are float32 buffers and counts under _qa-scratch\\cs-refit."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import sc_build as B        # noqa: E402  (SUB-COVER v1, unchanged)
import nrtax_defs as D      # noqa: E402

CS = "D:/Projects/claude/_qa-scratch/cs-refit"
CAPB = B.CAP + "/buffers"
REL_TOL = 1e-5
assert REL_TOL == 1e-5 and B.PCM == 180000


COSTAS = ((0, 7), (36, 43), (72, 79))          # SubfeasPayload.CostasBlocks
GRAY_MAP = (0, 1, 3, 2, 5, 6, 4, 7)            # SubfeasPayload.GrayMap
INV_GRAY = [0] * 8
for _v, _t in enumerate(GRAY_MAP):
    INV_GRAY[_t] = _v
MAX_GRID4 = 32400
RR73_STD_IGRID4 = MAX_GRID4 + 3                # SubfeasPayload.Rr73Std (ir false, igrid4 MaxGrid4 + 3)
RR73_ONAIR_IGRID4 = 32373                      # SubfeasPayload.Rr73OnAirIgrid4
assert INV_GRAY == [0, 1, 3, 2, 6, 4, 5, 7] and RR73_STD_IGRID4 == 32403


def payload77(tones):
    """SubfeasPayload.ExtractPayload77: the first 77 of the 174 codeword bits (Costas symbols skipped, inverse Gray, 3 bits per data symbol MSB first)."""
    bits = []
    for sym in range(79):
        if any(a <= sym < b for a, b in COSTAS):
            continue
        v = INV_GRAY[tones[sym]]
        bits += [bool((v >> 2) & 1), bool((v >> 1) & 1), bool(v & 1)]
    return bits[:77]


def _pack(bits, lo, hi):
    v = 0
    for i in range(lo, hi):
        v = (v << 1) | (1 if bits[i] else 0)
    return v


def std_fields(bits):
    """SubfeasPayload.ExtractStdFields: (I3, Call1, Call2, Ir, Igrid4)."""
    return (_pack(bits, 74, 77), _pack(bits, 0, 29), _pack(bits, 29, 58), bool(bits[58]), _pack(bits, 59, 74))


def same_qso(ref, cand):
    """SubfeasPayload.SameQso, ported unchanged (SubfeasPayload.cs:152-168): exact 77-bit match, or ref is our own RR73-standard encoding and cand carries the on-air RR73 sentinel
    with the same call1/call2 (and I3 = 1, Ir false)."""
    if ref == cand:
        return True
    r = std_fields(ref)
    if not (r[0] == 1 and r[3] is False and r[4] == RR73_STD_IGRID4):
        return False
    c = std_fields(cand)
    return c[0] == 1 and c[1] == r[1] and c[2] == r[2] and c[3] is False and c[4] == RR73_ONAIR_IGRID4


def cands(nat, kind, batch):
    """batch 1: the re-encodable decodes of the O buffer that EncodeMessage accepts (SubtractionPass.cs:331-343)."""
    out = []
    for freq, dt, snr, text in nat.get(kind, []):
        t = text.rstrip()
        if not D.reencodable(t):
            continue
        tones = B.encode(t)
        if tones is None:
            continue
        out.append({"tones": tones, "dt": dt, "f": freq, "snr": snr, "b": batch, "bits": payload77(tones)})
    return out


def cands2(nat, c1):
    """Amendment 2 (A2.1), the product's batch-2 set = the residual pass's NEW decodes (SubtractionPass.cs:457-491, then :331-343):
    (1) EncodeMessage accepts the native's text; (2) its payload is NOT SameQso with the payload of any batch-1 CANDIDATE; (3) then IsReencodable + EncodeMessage."""
    out = []
    refs = [c["bits"] for c in c1]
    for freq, dt, snr, text in nat.get("R2", []):
        t = text.rstrip()
        tones = B.encode(t)
        if tones is None:
            continue
        bits = payload77(tones)
        if any(same_qso(r, bits) for r in refs):
            continue
        if not D.reencodable(t):
            continue
        out.append({"tones": tones, "dt": dt, "f": freq, "snr": snr, "b": 2, "bits": bits})
    return out


def as_cands(lst):
    return [(c["tones"], c["dt"], c["f"]) for c in lst]


def product(o, c1, c2):
    """the product's procedure: batch 1 on O's analytic signal all at once -> R2; batch 2 on R2's analytic signal all at once -> R3."""
    z = 0
    if c1:
        re_, im_ = B.analytic(o)
        r2, z1 = B.subtract_all(o, as_cands(c1), re_, im_)
        z += z1
    else:
        r2 = o.copy()
    if c2:
        re_, im_ = B.analytic(r2)
        r3, z2 = B.subtract_all(r2, as_cands(c2), re_, im_)
        z += z2
    else:
        r3 = r2
    return r2, r3, z


def job(args):
    stamp, mode = args
    o = B.load_buf(stamp, "O")
    r2s = B.load_buf(stamp, "R2")
    r3s = B.load_buf(stamp, "R3")
    has_r3 = r3s is not None
    nat = B.load_natives(stamp)
    c1 = cands(nat, "O", 1)
    c2 = cands2(nat, c1)
    rec = {"stamp": stamp, "has_r3": has_r3, "n_c1": len(c1), "n_c2_candidates": len(c2), "n_c2_used": len(c2) if has_r3 else 0}
    t0 = time.perf_counter()
    r2, r3, z = product(o, c1, c2 if has_r3 else [])
    rec["t_product_s"] = time.perf_counter() - t0
    rec["fits_product"], rec["fit_zero_product"] = len(c1) + (len(c2) if has_r3 else 0), z
    if mode == "repro":
        d2 = float(np.max(np.abs(r2 - r2s)))
        pk2 = float(np.max(np.abs(r2s)))
        rec["r2_rel"], rec["r2_bitident"] = (d2 / pk2 if pk2 else 0.0), bool(np.array_equal(r2, r2s))
        if has_r3:
            d3 = float(np.max(np.abs(r3 - r3s)))
            pk3 = float(np.max(np.abs(r3s)))
            rec["r3_rel"], rec["r3_bitident"] = (d3 / pk3 if pk3 else 0.0), bool(np.array_equal(r3, r3s))
        base = r3s if has_r3 else r2s
        base.tofile(f"{CS}/buffers/{stamp}_R3B.f32")               # the R3 baseline: stored R3, or stored R2 (A1.1)
        return rec
    base = r3s if has_r3 else r2s
    members = c1 + (c2 if has_r3 else [])
    order = sorted(members, key=lambda c: (-c["snr"], c["f"], c["b"]))
    t0 = time.perf_counter()
    cur, zs = o.copy(), 0
    for c in order:
        re_, im_ = B.analytic(cur)
        rc, shat = B.fit(re_, im_, c["tones"], np.float32(c["dt"]), np.float32(c["f"]))
        zs += (rc == -3)
        cur -= shat
    rec["t_S_s"] = time.perf_counter() - t0
    cur.tofile(f"{CS}/buffers/{stamp}_S.f32")
    t0 = time.perf_counter()
    re_, im_ = B.analytic(base)
    cur_i, zi = B.subtract_all(base, as_cands(members), re_, im_)
    rec["t_I_s"] = time.perf_counter() - t0
    cur_i.tofile(f"{CS}/buffers/{stamp}_I.f32")
    rec.update({"members": len(members), "fit_zero_S": zs, "fit_zero_I": zi})
    return rec


def run(mode):
    stamps = [l.split("\t")[0] for l in open(B.CAP + "/capture_index.tsv", encoding="utf-8")]
    assert len(stamps) == 400
    os.makedirs(CS + "/buffers", exist_ok=True)
    t0 = time.time()
    with mp.Pool(8, initializer=B._init) as pool:
        out = sorted(pool.imap_unordered(job, [(s, mode) for s in stamps], chunksize=2), key=lambda r: r["stamp"])
    summ = {"mode": mode, "cycles": len(out), "seconds": round(time.time() - t0), "cycles_with_r3": sum(r["has_r3"] for r in out),
            "fits_product": sum(r["fits_product"] for r in out), "fit_zero_product": sum(r["fit_zero_product"] for r in out)}
    if mode == "repro":
        r2ok = sum(r["r2_bitident"] for r in out)
        r3 = [r for r in out if r["has_r3"]]
        r3ok = sum(r["r3_bitident"] for r in r3)
        summ.update({"R2_bit_identical": r2ok, "R2_max_rel": max(r["r2_rel"] for r in out), "R3_cycles": len(r3), "R3_bit_identical": r3ok, "R3_max_rel": max(r["r3_rel"] for r in r3),
                     "R3_cycles_rel_gt_tol": sum(1 for r in r3 if r["r3_rel"] > REL_TOL), "R2_cycles_rel_gt_tol": sum(1 for r in out if r["r2_rel"] > REL_TOL),
                     "no_r3_cycles": len(out) - len(r3), "no_r3_batch2_candidates_descriptive": sum(r["n_c2_candidates"] for r in out if not r["has_r3"]),
                     "r3_cycles_batch2_candidates": sum(r["n_c2_candidates"] for r in r3)})
        summ["L-REPRO"] = {"PASS": summ["R3_cycles_rel_gt_tol"] == 0 and summ["R2_cycles_rel_gt_tol"] == 0 and len(r3) == 382}
    else:
        tp = sum(r["t_product_s"] for r in out)
        summ.update({"members_total": sum(r["members"] for r in out), "fit_zero_S": sum(r["fit_zero_S"] for r in out), "fit_zero_I": sum(r["fit_zero_I"] for r in out),
                     "t_product_s_total": tp, "t_S_s_total": sum(r["t_S_s"] for r in out), "t_I_s_total": sum(r["t_I_s"] for r in out),
                     "ratio_S_over_product": sum(r["t_S_s"] for r in out) / tp, "ratio_I_over_product": sum(r["t_I_s"] for r in out) / tp})
    json.dump({"summary": summ, "cycles": out}, open(f"{CS}/{mode}.json", "w"))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    mp.freeze_support()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in ("repro", "legs"):
        run(cmd)
    else:
        sys.exit(__doc__)
