#!/usr/bin/env python3
"""CS-CEIL freeze-time preparation (no relocated output exists at any point here; no copy is built).
    python cc_prep.py            groups (V-CAT against NR-TAX's tags), the F1 dt measurement, the no-copy pilot for X (A1.3), the per-row slot table, V-SLOT per group (descriptive here:
                                 the validity row is evaluated again on the run's own table) -> D:\\Projects\\claude\\_qa-scratch\\cs-ceil\\frozen\\cc_groups.json (stamps, indices, numbers only)
HK-037: our decoded text and WSJT-X text stay in memory, used only for IsReencodable and the matching."""
from __future__ import annotations

import collections
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "..", "rr-study")
for p in (HERE, os.path.join(RR, "gap-relocate-run"), os.path.join(RR, "gap-residual-run")):
    sys.path.insert(0, p)
import cc_lib as L          # noqa: E402
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import nrtax_defs as D      # noqa: E402

GR = "D:/Projects/claude/_qa-scratch/gap-residual"
CAP = GR + "/cap/off"
OUT = "D:/Projects/claude/_qa-scratch/cs-ceil"
RESULT_NRTAX = os.path.join(RR, "results", "2026-10-29-nr-tax", "result_nrtax.json")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_buf(stamp):
    """the stored R3, or the stored R2 in the 18 cycles without one (CS-REFIT A1.1)."""
    p3 = f"{CAP}/buffers/{stamp}_R3.f32"
    p = p3 if os.path.isfile(p3) else f"{CAP}/buffers/{stamp}_R2.f32"
    a = np.fromfile(p, dtype=np.float32)
    assert a.shape == (L.PCM,)
    return a, ("R3" if p == p3 else "R2")


def build_world():
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    rows, stamps = pop["rows"], pop["stamps"]
    assert len(rows) == L.N_REF == pop["n_ref"] and len(stamps) == L.N_CYCLES
    ref = C.load_ref(set(stamps))
    nc = collections.defaultdict(list)
    for r in C.load_tsv(GR + "/scratch/off/nc_dump.tsv"):
        if len(r) >= 11:
            nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    match = F.rebuild_matching(ref, nc)
    by_cycle = collections.defaultdict(list)
    for r in rows:
        dec = bool(r["matched"])
        batch = r["kind"] if dec else 0
        text = match[r["stamp"]][r["idx"]][4] if dec else ""
        reenc = D.reencodable(text) if dec else False
        by_cycle[r["stamp"]].append({"idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "dt": r["dt"], "decoded": dec, "batch": batch, "subtracted": dec and batch in (1, 2) and reenc})
    our_freqs = {s: [o[2] for o in nc.get(s, [])] for s in stamps}
    tags = {}
    for line in open(GR + "/nrtax_row_tags.jsonl", encoding="utf-8"):
        t = json.loads(line)
        tags[(t["stamp"], t["idx"])] = t
    return pop, rows, stamps, by_cycle, our_freqs, tags


def categorise_rows(rows, by_cycle, tags):
    """V-CAT: D.categorise (frozen nrtax_defs) on the rebuilt neighbours reproduces EVERY tag of NR-TAX (11,960 rows)."""
    info = {}
    bad = 0
    for r in rows:
        k = (r["stamp"], r["idx"])
        if k not in tags:
            continue
        ns = [n for n in by_cycle[r["stamp"]] if n["idx"] != r["idx"]]
        cat, extra = D.categorise(r, ns)
        if cat != tags[k]["cat"]:
            bad += 1
        st = [n for n in ns if abs(n["freq"] - r["freq"]) < D.OVERLAP_HZ and n["snr"] >= r["snr"] and n["subtracted"]]
        nb = max(st, key=lambda n: n["snr"]) if st else None
        info[k] = {"cat": cat, "mixed": bool(extra["mixed"]), "nbr_dsnr": (nb["snr"] - r["snr"]) if nb else None, "nbr_df": abs(nb["freq"] - r["freq"]) if nb else None}
    assert bad == 0, f"V-CAT FAILED: {bad} categories differ from NR-TAX's tags"
    return info, len(info)


def forced_all():
    d = collections.defaultdict(dict)
    for line in open(GR + "/forced_all.jsonl", encoding="utf-8"):
        r = json.loads(line)
        d[(r["stamp"], r["idx"])][r["buf"]] = r
    return d


def main():
    os.makedirs(OUT + "/frozen", exist_ok=True)
    deltas = json.load(open(C.S + "\\deltas.json", encoding="utf-8"))
    assert abs(deltas["delta_p"] - L.DELTA_P) < 1e-9 and abs(deltas["delta_c"] - L.DELTA_C) < 1e-9
    pop, rows, stamps, by_cycle, our_freqs, tags = build_world()
    info, n_vcat = categorise_rows(rows, by_cycle, tags)
    rowd = {(r["stamp"], r["idx"]): r for r in rows}
    res_nrtax = json.load(open(RESULT_NRTAX, encoding="utf-8"))
    cs_nr = sorted(k for k, t in tags.items() if t["pop"] == "NR" and t["cat"] == "CS")
    weak = sorted(k for k, t in tags.items() if t["pop"] == "NR" and t["cat"] == "IW")
    assert (len(cs_nr), len(weak)) == (700, 73), (len(cs_nr), len(weak))
    mixed_n = sum(1 for k in cs_nr if info[k]["mixed"])
    pure = [k for k in cs_nr if not info[k]["mixed"]]
    xt = res_nrtax["CS_mixed_with_undecoded_stronger_overlapping_neighbour"]["NR"]
    assert (mixed_n, len(cs_nr)) == (xt["also_undecoded_stronger"], xt["CS_rows"]), (mixed_n, xt)
    # CTRL-HIT: CS hits forced-decodable in place on R3 (R2 where there is none), band-matched to CS-NR, seed 20261112
    fa = forced_all()
    quota = L.band_quota(collections.Counter(rowd[k]["band"] for k in cs_nr), L.N_CTRL_HIT)
    elig = []
    for k, t in tags.items():
        if t["pop"] != "hit" or t["cat"] != "CS":
            continue
        recs = fa.get(k, {})
        base = recs.get("R3") or recs.get("R2")
        if base is not None and L.either(base):
            elig.append((k[0], k[1], rowd[k]["band"]))
    ctrl = [(s, i) for s, i, _ in L.draw_ctrl_hit(elig, quota)]
    groups = {"CS-NR": cs_nr, "CS-pure": pure, "CTRL-HIT": ctrl, "CTRL-WEAK": weak}
    # F1 dt measurement (aggregate): the latest signal end per cycle
    endmax = [max(r["dt"] for r in by_cycle[s]) + L.DELTA_P + L.SIGNAL_S for s in stamps]
    f1 = {"cycle_latest_end_s_pctl_0_25_50_75_100": [float(x) for x in np.percentile(endmax, [0, 25, 50, 75, 100])], "cycles_with_a_signal_ending_after_13.2": int(sum(e > 13.2 for e in endmax))}
    # ---------- the no-copy pilot: tail and in-window PSDs, then X ----------
    union = sorted(set(cs_nr) | set(ctrl) | set(weak))
    per_cycle = collections.defaultdict(list)
    for k in union:
        per_cycle[k[0]].append(k)
    grid = L.slot_grid()
    table, diffs = {}, []
    for s in stamps:
        if s not in per_cycle:
            continue
        buf, kind = load_buf(s)
        pin, binw_in = L.hann_psd_prefix(buf[int(L.IN_LO * L.FS):int(L.IN_HI * L.FS)])
        in_slot = {f: L.band_db(pin, binw_in, f, f + L.SLOT_W) for f in grid}
        ours = our_freqs[s]
        refs = [(n["freq"], n["dt"]) for n in by_cycle[s]]
        freqs_block = [f for f, _ in refs] + ours
        for k in per_cycle[s]:
            r = rowd[k]
            t0 = L.tail_start(r["freq"], refs)
            rec = {"stamp": s, "idx": k[1], "buf": kind, "tail_t0": t0, "tail_len": L.TAIL_END - t0}
            if L.TAIL_END - t0 >= L.TAIL_MIN_S:
                seg = buf[int(t0 * L.FS):int(L.TAIL_END * L.FS)]
                pt, binw_t = L.hann_psd_prefix(seg)
                tail_row = L.band_db(pt, binw_t, r["freq"] - L.ROW_LO, r["freq"] + L.ROW_HI)
                tail_slot = {f: L.band_db(pt, binw_t, f, f + L.SLOT_W) for f in grid}
                in_row = L.band_db(pin, binw_in, r["freq"] - L.ROW_LO, r["freq"] + L.ROW_HI)
                rec["row_floor_gap_db"] = None if (in_row is None or tail_row is None) else in_row - tail_row
                tmp = []
                L.choose_slot(r["freq"], tail_row, tail_slot, in_slot, freqs_block, None, collect=tmp)
                diffs += tmp
                rec["_args"] = (tail_row, tail_slot, in_slot, freqs_block)
            else:
                rec["row_floor_gap_db"] = None
                rec["_args"] = None
            table[k] = rec
    x_db = float(np.median(diffs)) + L.X_PLUS_DB
    x_dist = [float(v) for v in np.percentile(diffs, [5, 25, 50, 75, 95])]
    S_NR, S_PU, S_HI, S_WE = set(cs_nr), set(pure), set(ctrl), set(weak)
    out_rows, cov = [], {}
    for g, keys in (("CS-NR", cs_nr), ("CS-pure", pure), ("CTRL-HIT", ctrl), ("CTRL-WEAK", weak)):
        cov[g] = {"rows": len(keys), "slot": 0, "no_tail": 0, "no_slot": 0}
    for k in union:
        rec = table[k]
        r = rowd[k]
        a = rec.pop("_args")
        f_s = None
        if a is not None:
            f_s = L.choose_slot(r["freq"], a[0], a[1], a[2], a[3], x_db)
        rec.update({"f_s": f_s, "delta_hz": None if f_s is None else L.relocation_delta(f_s, r["freq"]), "snr": r["snr"], "freq": r["freq"], "dt": r["dt"], "band": r["band"],
                    "cat": tags[k]["cat"], "pop": tags[k]["pop"], "mixed": info[k]["mixed"], "nbr_dsnr": info[k]["nbr_dsnr"], "nbr_df": info[k]["nbr_df"],
                    "in_CS_NR": k in S_NR, "in_pure": k in S_PU, "in_CTRL_HIT": k in S_HI, "in_CTRL_WEAK": k in S_WE, "n_cycle_ref": len(by_cycle[k[0]])})
        out_rows.append(rec)
    for rec in out_rows:
        for g, flag in (("CS-NR", "in_CS_NR"), ("CS-pure", "in_pure"), ("CTRL-HIT", "in_CTRL_HIT"), ("CTRL-WEAK", "in_CTRL_WEAK")):
            if rec[flag]:
                if rec["f_s"] is not None:
                    cov[g]["slot"] += 1
                else:
                    cov[g]["no_slot"] += 1
                    if rec["tail_len"] < L.TAIL_MIN_S:
                        cov[g]["no_tail"] += 1
    for g, c in cov.items():
        c["slot_share"] = c["slot"] / c["rows"]
    summary = {"V-CAT": {"rows_checked": n_vcat, "PASS": True}, "CS_NR": len(cs_nr), "CS_pure": len(pure), "CS_mixed": mixed_n, "CTRL_HIT": len(ctrl), "CTRL_WEAK": len(weak),
               "band_mix_CS_NR": dict(collections.Counter(rowd[k]["band"] for k in cs_nr)), "band_mix_CTRL_HIT": dict(collections.Counter(rowd[k]["band"] for k in ctrl)),
               "band_mix_CTRL_WEAK": dict(collections.Counter(rowd[k]["band"] for k in weak)), "ctrl_hit_quota": quota, "ctrl_hit_eligible": len(elig),
               "F1": f1, "X_db": x_db, "X_pairs": len(diffs), "X_in_minus_tail_db_pctl_5_25_50_75_95": x_dist, "slot_coverage_no_copy": cov,
               "inputs": {"deltas_json_sha256": sha(C.S + "\\deltas.json"), "tags_sha256": sha(GR + "/nrtax_row_tags.jsonl"), "forced_all_sha256": sha(GR + "/forced_all.jsonl"),
                          "population_sha256": sha(C.S + "\\population.json")}}
    json.dump({"summary": summary, "rows": out_rows}, open(OUT + "/frozen/cc_groups.json", "w"))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
