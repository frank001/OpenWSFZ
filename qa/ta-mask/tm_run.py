#!/usr/bin/env python3
"""TA-MASK scorer (spec 104f197f + Amendment 1 0777c9b9).  Reuses TA-CHECK's frozen groups (`_qa-scratch\\ta-check\\frozen\\tc_groups.json`) and calibration (`tc_calib.json`).  QA tooling; no PC window.
    python tm_run.py pilot     30 T_bur + 30 B1m rows (seed 20261113, EXCLUDED from every acceptance rate afterwards): own S_M, n_s, null (K_NULL each), the two ghosts, the unmasked comparators,
                               mask statistics, pilot null p99s                                              -> _qa-scratch\\ta-mask\\pilot.json, frozen\\tm_pilot_rows.json
    python tm_run.py null      K_NULL null sequences of every ACCEPTANCE row of B1m u T (pilot rows excluded) -> T_M = max(pooled p99, T_bur-only p99)  -> nulls.json, frozen\\tm.json   (NO own S_M is computed)
    python tm_run.py own       REFUSES unless frozen\\tm.json exists: own S_M of every acceptance row (B1, B1m, T), the ghosts of T_bur rows              -> own.json
HK-037: text is read in this process for tones only and never written; every file holds stamp:index keys and numbers."""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TC = os.path.join(HERE, "..", "ta-check")
for p in (HERE, TC):
    sys.path.insert(0, p)
import tm_lib as M          # noqa: E402
import tc_lib as TCL        # noqa: E402
import tc_groups as G       # noqa: E402

U = G.U
OUT = "D:/Projects/claude/_qa-scratch/ta-mask"
TCOUT = G.OUT
N_PILOT = 30
CE = None


def setup():
    global CE
    grp = json.load(open(TCOUT + "/frozen/tc_groups.json"))
    c_off = float(json.load(open(TCOUT + "/frozen/tc_calib.json"))["start_minus_dt_median_s"])
    F, blob = U.load_instrument()
    assert blob == grp["summary"]["blob_cf_fbid"]
    assert (F.DF_GRID_HZ, F.DT_HALF_WINDOW_S, F.DT_STEP_S, F.N_SYM, F.N_TONES) == (M.DF_GRID_HZ, M.DT_HALF_S, M.DT_STEP_S, M.N_SYM, M.N_TONES)
    assert G.D.OVERLAP_HZ == M.OVERLAP_HZ and (U.K_NULL, U.MIN_PRESENT_RATE) == (M.K_NULL, M.BAR_PRESENT)
    CE = F.CE
    enc = F.encoder(G.DLL)
    ref = G.load_ref_night(set(grp["stamps"]))
    mb = {}
    for r in csv.reader(open(G.MATCHED)):
        if r and r[0] != "stamp":
            mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    ctl = []
    for s in grp["stamps"]:
        for i, (snr, dt, f, text) in enumerate(ref.get(s, [])):
            if mb[s].get(i) is not None:
                t = enc(text)
                if t is not None:
                    ctl.append((s, np.array(t)))
    return {"grp": grp, "c_off": c_off, "F": F, "enc": enc, "ref": ref, "ctl_stamp": np.array([c[0] for c in ctl]), "ctl_data": np.array([c[1][F.DATA_IDX] for c in ctl]), "ctl_tones": [c[1] for c in ctl],
            "pcms": {}}


def pcm_of(W, s):
    if s not in W["pcms"]:
        W["pcms"][s] = W["F"].wavio.load_cycle_pcm(os.path.join(G.WAVS, s + ".wav"))
    return W["pcms"][s]


def row_ctx(W, s, i):
    """own tones, neighbour list [(f, dt, tones|None, snr)] within 50 Hz (any SNR), the strongest overlapping neighbour's index per the T_bur predicate."""
    rows = W["ref"][s]
    snr, dt, f, text = rows[i]
    own = W["enc"](text)
    neigh, strong = [], None
    for j, (s2, d2, f2, t2) in enumerate(rows):
        if j != i and abs(f2 - f) < M.OVERLAP_HZ:
            neigh.append({"j": j, "f": f2, "dt": d2, "snr": s2, "tones": W["enc"](t2)})
    cand = [n for n in neigh if n["snr"] >= snr]
    if cand:
        strong = max(cand, key=lambda n: (n["snr"], -abs(n["f"] - f)))
    return own, (snr, dt, f), neigh, strong


def entries(W, neigh):
    return M.neighbour_entries([(n["f"], n["dt"], n["tones"]) for n in neigh if n["tones"] is not None], W["c_off"])


def score_at(W, s, f, dt, ent, sync_tones, seqs):
    """the Costas-only search with the mask, then S_M and n_s for every tone sequence in seqs at the best position.  Returns (list[(S, n_s)], mask stats dict)."""
    F, CEm = W["F"], CE
    pcm = pcm_of(W, s)
    best, best_am, best_mask = -2.0, None, None
    centre = dt + W["c_off"]
    starts = np.arange(centre - M.DT_HALF_S, centre + M.DT_HALF_S + 1e-9, M.DT_STEP_S)
    for dfz in M.DF_GRID_HZ:
        bb = CEm.downconvert_decimate(pcm, round(f + dfz, 3))
        for st in starts:
            smp = int(round(st * F.FS_OUT))
            X = np.abs(CEm.correlate_symbols(bb, smp))
            mask = M.mask_matrix(f + dfz, smp / F.FS_OUT, ent)
            am = M.masked_argmax(X, mask)
            h = M.sync_share(am, mask, F.SYNC_IDX, sync_tones)
            if h > best:
                best, best_am, best_mask = h, am, mask
    outs = [M.data_score(best_am, best_mask, sq, F.DATA_IDX) for sq in seqs]
    stats = {"sync": best, "masked_bins_per_symbol": float(best_mask.sum(axis=1).mean())}
    return outs, stats


def nulls_for(W, s, own, rng):
    own = np.array(own)
    agree = (W["ctl_data"] == own[W["F"].DATA_IDX][None, :]).mean(axis=1)
    cand = np.where((W["ctl_stamp"] != s) & (agree <= M.AGREE_MAX))[0]
    return [list(W["ctl_tones"][j]) for j in rng.choice(cand, size=M.K_NULL, replace=False)]


def score_row(W, s, i, rng, want_null, want_own, ghosts):
    F = W["F"]
    own, (snr, dt, f), neigh, strong = row_ctx(W, s, i)
    ent = entries(W, neigh)
    sync_tones = [own[k] for k in F.SYNC_IDX]
    nl = nulls_for(W, s, own, rng) if want_null else []
    seqs = ([own] if want_own else []) + nl
    gh1 = strong["tones"] if (ghosts and strong is not None and strong["tones"] is not None) else None
    if gh1 is not None:
        seqs.append(gh1)
    outs, stats = score_at(W, s, f, dt, ent, sync_tones, seqs)
    rec = {"unencodable_neighbours": sum(1 for n in neigh if n["tones"] is None), "n_neighbours": len(neigh), "stats": stats}
    k = 0
    if want_own:
        rec["own"] = outs[0]
        k = 1
    rec["null"] = outs[k:k + len(nl)]
    if gh1 is not None:
        rec["ghost1"] = outs[-1]
    if ghosts and strong is not None:
        rec["ghost1_status"] = "scored" if gh1 is not None else "neighbour_unencodable"
        if strong["tones"] is not None:                       # ghost 2 (descriptive): the neighbour's sequence at the neighbour's OWN position, scored with this row's mask
            o2, _ = score_at(W, s, strong["f"], strong["dt"], ent, [strong["tones"][k_] for k_ in F.SYNC_IDX], [strong["tones"]])
            rec["ghost2"] = o2[0]
        # unmasked comparator (the unmasked instrument at the row's position, the neighbour's sequence)
        if gh1 is not None:
            _, uo = F.locate_and_score({}, pcm_of(W, s), f, dt + W["c_off"], F.DT_HALF_WINDOW_S, sync_tones, [gh1])
            rec["ghost1_unmasked"] = uo[0]
    if want_own:
        _, uo = F.locate_and_score({}, pcm_of(W, s), f, dt + W["c_off"], F.DT_HALF_WINDOW_S, sync_tones, [own])
        rec["own_unmasked"] = uo[0]
    return rec


def key(r):
    return (r["stamp"], r["idx"])


def pilot_rows(grp):
    rows = grp["rows"]
    tb = sorted(key(r) for r in rows if r["in_Tbur"])
    bm = sorted(key(r) for r in rows if r["in_B1m"])
    pil_t = TCL.draw(tb, N_PILOT, M.SEED)
    pil_m = TCL.draw(bm, N_PILOT, M.SEED)
    return pil_t, pil_m


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("pilot", "null", "own"):
        sys.exit(__doc__)
    os.makedirs(OUT + "/frozen", exist_ok=True)
    W = setup()
    grp = W["grp"]
    rows = grp["rows"]
    pil_t, pil_m = pilot_rows(grp)
    pil = set(pil_t) | set(pil_m)
    if stage == "pilot":
        json.dump({"T_bur": [list(k) for k in pil_t], "B1m": [list(k) for k in pil_m], "seed": M.SEED}, open(OUT + "/frozen/tm_pilot_rows.json", "w"))
        rng = np.random.default_rng(M.SEED)
        res = {}
        for name, ks, gh in (("T_bur", pil_t, True), ("B1m", pil_m, False)):
            for (s, i) in ks:
                res[f"{s}:{i}"] = dict(score_row(W, s, i, rng, True, True, gh), group=name)
        json.dump({"c_off": W["c_off"], "rows": res}, open(OUT + "/pilot.json", "w"))
        print("pilot rows scored:", len(res))
        return
    ex = json.load(open(OUT + "/frozen/tm_pilot_rows.json"))
    assert {tuple(k) for k in ex["T_bur"]} | {tuple(k) for k in ex["B1m"]} == pil
    if stage == "null":
        acc = sorted(key(r) for r in rows if (r["in_B1m"] or r["in_T"]) and key(r) not in pil)
        rng = np.random.default_rng(M.SEED + 1)
        nulls = {}
        for (s, i) in acc:
            nulls[f"{s}:{i}"] = score_row(W, s, i, rng, True, False, False)["null"]
        grp_of = {key(r): r for r in rows}
        pooled = [S for k, v in nulls.items() for (S, n) in v if n >= M.MIN_SCORABLE]
        def parse(k):
            a_, b_ = k.split(":")
            return (a_, int(b_))
        tbur = [S for k, v in nulls.items() if grp_of[parse(k)]["in_Tbur"] for (S, n) in v if n >= M.MIN_SCORABLE]
        t_m, p, b = M.threshold_tm(pooled, tbur)
        excl = sum(1 for v in nulls.values() for (S, n) in v if n < M.MIN_SCORABLE)
        out = {"T_M": t_m, "p99_pooled_B1m_u_T": p, "p99_T_bur_only": b, "null_sequences_scored": int(sum(len(v) for v in nulls.values())), "null_sequences_unscorable_excluded": int(excl),
               "rows": len(nulls), "T_frozen_unmasked": 0.276}
        json.dump({"nulls": nulls}, open(OUT + "/nulls.json", "w"))
        json.dump(out, open(OUT + "/frozen/tm.json", "w"), indent=1)
        print(json.dumps(out, indent=1))
        return
    tm_path = OUT + "/frozen/tm.json"
    if not os.path.isfile(tm_path):
        sys.exit("REFUSED: frozen/tm.json (T_M) does not exist: the null stage must run and be committed first")
    acc = sorted(key(r) for r in rows if (r["in_B1"] or r["in_B1m"] or r["in_T"]) and key(r) not in pil)
    tb = {key(r) for r in rows if r["in_Tbur"]}
    rng = np.random.default_rng(M.SEED + 2)
    own = {}
    for (s, i) in acc:
        own[f"{s}:{i}"] = score_row(W, s, i, rng, False, True, (s, i) in tb)
    json.dump({"rows": own}, open(OUT + "/own.json", "w"))
    print("acceptance rows scored:", len(own))


if __name__ == "__main__":
    main()
