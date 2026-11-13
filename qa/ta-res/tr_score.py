#!/usr/bin/env python3
"""TA-RES scorer (spec cae3015c + A1 ef0b6e51).  Reuses TA-CHECK's frozen groups, TA-MASK's pilot exclusion list and the capture replay of arm B (`_qa-scratch\\ta-res\\cap_run`).  QA tooling; not PC-exclusive.
    python tr_score.py prep      V-REPRO (replay vs arm B's matchedbatch), the matching of WSJT-X rows to our decodes, provenance (tr_prov), source buffer per row, subtracted-neighbour flags, V-PROV
                                 -> frozen\\tr_rows.json, prep.json     (NO tone score is computed)
    python tr_score.py pilot     TA-MASK's 60 pilot rows scored with R (own, K_NULL nulls on the row's own source buffer, ghost, residue ghost)            -> pilot.json
    python tr_score.py null      K_NULL nulls of every acceptance row of B1m u T (pilot excluded) -> T_R = max(pooled p99, T_bur-only p99)                 -> nulls.json, frozen\\tr.json (NO own S_R)
    python tr_score.py own       REFUSES without frozen\\tr.json: own S_R, ghost, residue ghost, our-position descriptive, V-O sample                       -> own.json
HK-037: text is read in this process to tie rows together and for tones only; every file written holds stamp:index keys, labels and numbers."""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "..", "rr-study")
for p in (HERE, os.path.join(HERE, "..", "ta-check"), os.path.join(HERE, "..", "ta-mask"), os.path.join(RR, "gap-relocate-run"), os.path.join(RR, "gap-residual-run")):
    sys.path.insert(0, p)
import tr_lib as L          # noqa: E402
import tr_prov as P         # noqa: E402
import tc_groups as G       # noqa: E402
import tm_lib as M          # noqa: E402
import gr_forced as GF      # noqa: E402

U = G.U
OUT = "D:/Projects/claude/_qa-scratch/ta-res"
CAPRUN = OUT + "/cap_run"
CAP = CAPRUN + "/cap"
ARMB = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2/arms/B"
TCOUT = G.OUT
TMOUT = "D:/Projects/claude/_qa-scratch/ta-mask"
V_O_SAMPLE = 200


def csv_lines(path):
    d = {}
    for r in csv.reader(open(path)):
        if r and r[0] != "stamp":
            d[r[0]] = r[1]
    return d


def setup():
    grp = json.load(open(TCOUT + "/frozen/tc_groups.json"))
    c_off = float(json.load(open(TCOUT + "/frozen/tc_calib.json"))["start_minus_dt_median_s"])
    assert abs(c_off - L.CALIB_S) < 1e-9
    F, blob = U.load_instrument()
    assert blob == grp["summary"]["blob_cf_fbid"]
    enc = F.encoder(G.DLL)
    ref = G.load_ref_night(set(grp["stamps"]))
    pil = json.load(open(TMOUT + "/frozen/tm_pilot_rows.json"))
    pilset = {tuple(k) for k in pil["T_bur"]} | {tuple(k) for k in pil["B1m"]}
    return {"grp": grp, "c_off": c_off, "F": F, "enc": enc, "ref": ref, "pilset": pilset, "pil": pil, "pcms": {}}


# ------------------------------------------------------------------------------------------------ prep
def prep():
    W = setup()
    grp, ref = W["grp"], W["ref"]
    stamps = grp["stamps"]
    mb_arm, mb_rep = csv_lines(ARMB + "/matchedbatch.csv"), csv_lines(CAPRUN + "/matchedbatch.csv")
    same = {s: (mb_arm.get(s) == mb_rep.get(s)) for s in stamps}
    v_repro = sum(same.values()) / len(stamps)
    # our rows of the replay, matched to WSJT-X rows as ScoreTestB does (text stays in memory)
    nc = collections.defaultdict(list)
    for r in G.csv.reader(open(CAPRUN + "/nc.tsv", encoding="utf-8"), delimiter="\t"):
        if len(r) >= 11:
            nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    match = GF.rebuild_matching(ref, nc)                 # stamp -> {wsjtx_idx: (kind, freq, dt, snr, our_text)}
    found, utext = P.read_stage_dump(CAPRUN + "/stage_dump.tsv")
    cap = P.read_capture_index(CAP + "/capture_index.tsv")
    mbmap = {}
    for s in stamps:
        mbmap[s] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in (mb_rep.get(s) or "").split(";") if a}
    out_rows, stat = [], collections.Counter()
    multi_all = collections.Counter()
    # multi-source counts over EVERY published batch-4 row of the 500 cycles (V-PROV report)
    for s in stamps:
        for idx, (kind, f, dt, snr, text) in match.get(s, {}).items():
            if kind == 4:
                lab, multi, st = P.resolve_published(s, text, found, utext, cap)
                stat["b4_all:" + st] += 1
                if st == "ok":
                    multi_all[multi] += 1
                    stat["b4_all_source:" + lab] += 1
    for r in grp["rows"]:
        k = (r["stamp"], r["idx"])
        s, i = k
        rec = {"stamp": s, "idx": i, "batch_arm": r["batch"], "pilot": k in W["pilset"], "excluded": None}
        if not same[s]:
            rec["excluded"] = "cycle_differs_from_arm_B"
        elif mbmap[s].get(i) != r["batch"]:
            rec["excluded"] = "batch_differs_in_replay"
        else:
            m = match[s].get(i)
            if m is None:
                rec["excluded"] = "no_our_row"
            else:
                kind, f, dt, snr, text = m
                rec.update({"our_f": f, "our_dt": dt})
                lab, multi, st = (None, 0, "n/a")
                if r["batch"] == 4:
                    lab, multi, st = P.resolve_published(s, text, found, utext, cap)
                    rec["prov_status"], rec["multi"] = st, multi
                    if st != "ok":
                        rec["excluded"] = "prov_" + st
                src = L.source_file(r["batch"], lab, cap.get(s, {}).get("level", "none"), cap.get(s, {}).get("calls", 0))
                rec["source"] = src
                if src is None and rec["excluded"] is None:
                    rec["excluded"] = "no_source_buffer"
        # strongest overlapping neighbour (T_bur predicate) and whether it was subtracted before the source buffer
        if r["in_Tbur"] and rec["excluded"] is None:
            rows = ref[s]
            snr_r, dt_r, f_r, _ = rows[i]
            cand = [(rows[j][0], -abs(rows[j][2] - f_r), j) for j in range(len(rows)) if j != i and abs(rows[j][2] - f_r) < 50 and rows[j][0] >= snr_r]
            _, _, jn = max(cand)
            rec["nbr_idx"] = jn
            nb = mbmap[s].get(jn)
            mt = match[s].get(jn)
            re_ok = bool(mt) and L.reencodable(mt[4]) and W["enc"](mt[4]) is not None
            rec["nbr_batch"], rec["nbr_reencodable"] = nb, re_ok
            rec["nbr_subtracted_before"] = L.subtracted_before(nb, re_ok, rec["source"])
        out_rows.append(rec)
    inc = [r for r in out_rows if r["excluded"] is None]
    v_prov_fail = [r for r in out_rows if r["batch_arm"] in (4, 5) and (r["excluded"] or "").startswith(("prov_", "no_source"))]
    summ = {"V_REPRO": {"cycles_identical": int(sum(same.values())), "cycles": len(stamps), "share": v_repro, "PASS": bool(v_repro >= L.V_REPRO)},
            "V_PROV": {"unresolved_rows_in_T": len(v_prov_fail), "PASS": len(v_prov_fail) == 0}, "b4_all_rows_provenance": dict(stat), "multi_source_counts_all_batch4_rows": dict(sorted(multi_all.items())),
            "excluded": dict(collections.Counter(r["excluded"] for r in out_rows if r["excluded"])), "included_rows": len(inc),
            "source_mix_included_by_group": {g: dict(collections.Counter(r["source"] for r in out_rows if r["excluded"] is None and gr_flag(grp, r, g))) for g in ("B1", "B1m", "T_bur", "T_iso")},
            "T_bur_neighbour_subtracted_before": {"eligible": sum(1 for r in inc if r.get("nbr_subtracted_before")), "T_bur_included": sum(1 for r in inc if "nbr_idx" in r)}}
    json.dump({"rows": out_rows}, open(OUT + "/frozen/tr_rows.json", "w"))
    json.dump(summ, open(OUT + "/prep.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))


def gr_flag(grp, rec, g):
    row = GROW[(rec["stamp"], rec["idx"])]
    return {"B1": row["in_B1"], "B1m": row["in_B1m"], "T_bur": row["in_Tbur"], "T_iso": row["in_T"] and not row["bur"]}[g]


GROW = {}


# ------------------------------------------------------------------------------------------------ scoring
def buf(W, s, kind):
    k = (s, kind)
    if k not in W["pcms"]:
        W["pcms"][k] = np.fromfile(f"{CAP}/buffers/{s}_{kind}.f32", dtype=np.float32)
    return W["pcms"][k]


def share(W, pcm, f, dt, sync_tones, seqs):
    F = W["F"]
    _, outs = F.locate_and_score({}, pcm, f, dt + W["c_off"], F.DT_HALF_WINDOW_S, sync_tones, seqs)
    return outs


def nulls_for(W, ctl, s, own, rng):
    own = np.array(own)
    agree = (ctl["data"] == own[W["F"].DATA_IDX][None, :]).mean(axis=1)
    cand = np.where((ctl["stamp"] != s) & (agree <= M.AGREE_MAX))[0]
    return [list(ctl["tones"][j]) for j in rng.choice(cand, size=L.K_NULL, replace=False)]


def controls(W):
    mbarm = {}
    for r in csv.reader(open(G.MATCHED)):
        if r and r[0] != "stamp":
            mbarm[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    tones, stamp = [], []
    for s in W["grp"]["stamps"]:
        for i, (snr, dt, f, text) in enumerate(W["ref"].get(s, [])):
            if mbarm[s].get(i) is not None:
                t = W["enc"](text)
                if t is not None:
                    tones.append(np.array(t))
                    stamp.append(s)
    F = W["F"]
    return {"stamp": np.array(stamp), "tones": tones, "data": np.array([t[F.DATA_IDX] for t in tones])}


def row_ctx(W, rec):
    s, i = rec["stamp"], rec["idx"]
    snr, dt, f, text = W["ref"][s][i]
    own = W["enc"](text)
    ghost = res = None
    if "nbr_idx" in rec:
        n = W["ref"][s][rec["nbr_idx"]]
        nt = W["enc"](n[3])
        if nt is not None:
            ghost = nt
            if rec.get("nbr_subtracted_before"):
                res = (nt, n[2], n[1])               # the neighbour's own sequence at its own WSJT-X position
    return own, (snr, dt, f), ghost, res


def score_row(W, ctl, rec, rng, want_null, want_own, ghosts):
    F = W["F"]
    own, (snr, dt, f), ghost, res = row_ctx(W, rec)
    pcm = buf(W, rec["stamp"], rec["source"])
    sync = [own[k] for k in F.SYNC_IDX]
    nl = nulls_for(W, ctl, rec["stamp"], own, rng) if want_null else []
    seqs = ([own] if want_own else []) + nl + ([ghost] if (ghosts and ghost is not None) else [])
    outs = share(W, pcm, f, dt, sync, seqs)
    r = {}
    k = 0
    if want_own:
        r["own"] = outs[0]
        k = 1
    r["null"] = outs[k:k + len(nl)]
    if ghosts and ghost is not None:
        r["ghost1"] = outs[-1]
    if ghosts and res is not None:                      # A-RESIDUE: the subtracted neighbour's own sequence at ITS position on this row's source buffer
        nt, nf, ndt = res
        r["residue"] = share(W, pcm, nf, ndt, [nt[k_] for k_ in F.SYNC_IDX], [nt])[0]
    return r


def key(r):
    return (r["stamp"], r["idx"])


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("prep", "pilot", "null", "own"):
        sys.exit(__doc__)
    os.makedirs(OUT + "/frozen", exist_ok=True)
    grp = json.load(open(TCOUT + "/frozen/tc_groups.json"))
    for r in grp["rows"]:
        GROW[(r["stamp"], r["idx"])] = r
    if stage == "prep":
        prep()
        return
    W = setup()
    rows = {key(r): r for r in json.load(open(OUT + "/frozen/tr_rows.json"))["rows"] if r["excluded"] is None}
    ctl = controls(W)
    pil = W["pilset"]
    if stage == "pilot":
        rng = np.random.default_rng(L.SEED)
        res = {}
        for k in sorted(pil):
            if k in rows:
                g = "T_bur" if GROW[k]["in_Tbur"] and k in {tuple(x) for x in W["pil"]["T_bur"]} else "B1m"
                res[f"{k[0]}:{k[1]}"] = dict(score_row(W, ctl, rows[k], rng, True, True, g == "T_bur"), group=g, source=rows[k]["source"])
        json.dump({"rows": res, "pilot_rows_missing": len(pil) - len(res)}, open(OUT + "/pilot.json", "w"))
        print("pilot rows scored:", len(res), "of", len(pil))
        return
    if stage == "null":
        acc = sorted(k for k in rows if k not in pil and (GROW[k]["in_B1m"] or GROW[k]["in_T"]))
        rng = np.random.default_rng(L.SEED + 1)
        nulls = {f"{k[0]}:{k[1]}": score_row(W, ctl, rows[k], rng, True, False, False)["null"] for k in acc}
        pooled = [x for v in nulls.values() for x in v]
        tbur = [x for kk, v in nulls.items() for x in v if GROW[(kk.split(":")[0], int(kk.split(":")[1]))]["in_Tbur"]]
        t_r, p, b = M.threshold_tm(pooled, tbur)
        out = {"T_R": t_r, "p99_pooled_B1m_u_T": p, "p99_T_bur_only": b, "null_sequences": len(pooled), "rows": len(nulls)}
        json.dump({"nulls": nulls}, open(OUT + "/nulls.json", "w"))
        json.dump(out, open(OUT + "/frozen/tr.json", "w"), indent=1)
        print(json.dumps(out, indent=1))
        return
    if not os.path.isfile(OUT + "/frozen/tr.json"):
        sys.exit("REFUSED: frozen/tr.json (T_R) does not exist")
    acc = sorted(k for k in rows if k not in pil and (GROW[k]["in_B1"] or GROW[k]["in_B1m"] or GROW[k]["in_T"]))
    rng = np.random.default_rng(L.SEED + 2)
    own = {}
    for k in acc:
        r = score_row(W, ctl, rows[k], rng, False, True, GROW[k]["in_Tbur"])
        rec = rows[k]
        # our-position descriptive (T rows): the own sequence at OUR published position on the same source buffer
        if GROW[k]["in_T"] and "our_f" in rec:
            o, _, _, _ = row_ctx(W, rec)
            r["own_at_our_position"] = share(W, buf(W, k[0], rec["source"]), rec["our_f"], rec["our_dt"], [o[q] for q in W["F"].SYNC_IDX], [o])[0]
        own[f"{k[0]}:{k[1]}"] = dict(r, source=rec["source"])
    # V-O (descriptive): the captured O against the WAV-derived PCM TA-CHECK scored, on a seeded sample of B1 rows
    b1 = sorted(k for k in acc if GROW[k]["in_B1"])
    pick = [b1[j] for j in sorted(np.random.default_rng(L.SEED + 3).permutation(len(b1))[:V_O_SAMPLE])]
    vo = []
    for k in pick:
        o, (snr, dt, f), _, _ = row_ctx(W, rows[k])
        sy = [o[q] for q in W["F"].SYNC_IDX]
        a = share(W, buf(W, k[0], "O"), f, dt, sy, [o])[0]
        wavpcm = W["F"].wavio.load_cycle_pcm(os.path.join(G.WAVS, k[0] + ".wav"))
        b = share(W, wavpcm, f, dt, sy, [o])[0]
        vo.append(abs(a - b))
    json.dump({"rows": own, "V_O": {"rows": len(vo), "max_abs_share_diff": float(max(vo)), "mean_abs_share_diff": float(np.mean(vo))}}, open(OUT + "/own.json", "w"))
    print("acceptance rows scored:", len(own), "V-O max diff", max(vo))


if __name__ == "__main__":
    main()
