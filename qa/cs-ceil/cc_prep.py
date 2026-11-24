#!/usr/bin/env python3
"""CS-CEIL freeze-time preparation (no relocated output exists at any point here; no copy is built).  Amendment 2 slot rule (arch/cs-model-ceiling e3e5feca).
    python cc_prep.py            groups (V-CAT against NR-TAX's tags), the F1 dt measurement and the in-window window, the no-copy pilot: cycle floor, per-row slot table under BOTH rules,
                                 V-SLOT per group, the mechanical fallback decision (two-sided unless any group < 90 %, then upper) -> D:\\Projects\\claude\\_qa-scratch\\cs-ceil\\frozen\\cc_groups.json (stamps, indices, numbers only)
HK-037: our decoded text and WSJT-X text stay in memory, used only for IsReencodable and the matching."""
from __future__ import annotations

import collections
import hashlib
import json
import math
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
    # F1 (A2.1): the in-window PSD window from the measured dt range.  Product offset: signal start = dt + 0.6, end = start + 12.64.  The next period's earliest signal starts at
    # 15 + dt_min + 0.6 in this buffer; the previous period's latest signal ends at dt_max + 0.6 + 12.64 - 15.  The window is the spec's [0.5, 13.1] narrowed (never widened) to exclude both.
    dts = [r["dt"] for r in rows]
    dt_min, dt_max = min(dts), max(dts)
    in_hi = min(L.IN_HI, math.floor((15.0 + dt_min + L.DELTA_P) * 10) / 10.0)
    in_lo = max(L.IN_LO, math.ceil((dt_max + L.DELTA_P + L.SIGNAL_S - 15.0) * 10) / 10.0)
    assert 0.0 < in_lo < in_hi <= L.IN_HI
    f1 = {"dt_min": dt_min, "dt_max": dt_max, "window_s": [in_lo, in_hi], "spec_default_window_s": [L.IN_LO, L.IN_HI]}
    # ---------- the no-copy pilot: cycle floor and slot table under BOTH rules ----------
    union = sorted(set(cs_nr) | set(ctrl) | set(weak))
    per_cycle = collections.defaultdict(list)
    for k in union:
        per_cycle[k[0]].append(k)
    grid = L.slot_grid()
    S_NR, S_PU, S_HI, S_WE = set(cs_nr), set(pure), set(ctrl), set(weak)
    out_rows, floors = [], {}
    for s in stamps:
        if s not in per_cycle:
            continue
        buf, kind = load_buf(s)
        pin, binw = L.hann_psd_prefix(buf[int(round(in_lo * L.FS)):int(round(in_hi * L.FS))])
        in_slot = {f: L.band_db(pin, binw, f, f + L.SLOT_W) for f in grid}
        freqs_block = [n["freq"] for n in by_cycle[s]] + our_freqs[s]
        for k in per_cycle[s]:
            r = rowd[k]
            rec = {"stamp": s, "idx": k[1], "buf": kind, "snr": r["snr"], "freq": r["freq"], "dt": r["dt"], "band": r["band"], "cat": tags[k]["cat"], "pop": tags[k]["pop"],
                   "mixed": info[k]["mixed"], "nbr_dsnr": info[k]["nbr_dsnr"], "nbr_df": info[k]["nbr_df"], "n_cycle_ref": len(by_cycle[s]),
                   "in_CS_NR": k in S_NR, "in_pure": k in S_PU, "in_CTRL_HIT": k in S_HI, "in_CTRL_WEAK": k in S_WE}
            for rule in ("two-sided", "upper"):
                f_s, floor = L.choose_slot(r["freq"], in_slot, freqs_block, rule)
                rec["f_s_" + rule] = f_s
                rec["delta_hz_" + rule] = None if f_s is None else L.relocation_delta(f_s, r["freq"])
            rec["cycle_floor_db"] = floor
            rb = L.band_db(pin, binw, r["freq"] - L.ROW_LO, r["freq"] + L.ROW_HI)          # A2.2: row-band in-window PSD minus the cycle floor (upper bound on the residue floor)
            rec["row_band_minus_floor_db"] = None if (rb is None or floor is None) else rb - floor
            sl = rec["f_s_two-sided"]
            rec["slot_minus_floor_db_two_sided"] = None if sl is None else in_slot[sl] - floor
            su = rec["f_s_upper"]
            rec["slot_minus_floor_db_upper"] = None if su is None else in_slot[su] - floor
            out_rows.append(rec)
    GN = (("CS-NR", "in_CS_NR"), ("CS-pure", "in_pure"), ("CTRL-HIT", "in_CTRL_HIT"), ("CTRL-WEAK", "in_CTRL_WEAK"))
    cov = {}
    for rule in ("two-sided", "upper"):
        cov[rule] = {}
        for g, flag in GN:
            rs = [x for x in out_rows if x[flag]]
            n_slot = sum(1 for x in rs if x["f_s_" + rule] is not None)
            cov[rule][g] = {"rows": len(rs), "slot": n_slot, "no_slot": len(rs) - n_slot, "V_SLOT_share": n_slot / len(rs),
                            "abs_df_pctl_5_25_50_75_95": [float(v) for v in np.percentile([abs(x["delta_hz_" + rule]) for x in rs if x["f_s_" + rule] is not None], [5, 25, 50, 75, 95])],
                            "slot_minus_floor_db_pctl_5_25_50_75_95": [float(v) for v in np.percentile([x["slot_minus_floor_db_" + ("two_sided" if rule == "two-sided" else "upper")] for x in rs if x["f_s_" + rule] is not None], [5, 25, 50, 75, 95])]}
    cyc_floor = {x["stamp"]: x["cycle_floor_db"] for x in out_rows if x["cycle_floor_db"] is not None}
    two_ok = all(c["V_SLOT_share"] >= L.V_SLOT for c in cov["two-sided"].values())
    rule = "two-sided" if two_ok else "upper"                                              # the pre-registered mechanical fallback
    upper_ok = all(c["V_SLOT_share"] >= L.V_SLOT for c in cov["upper"].values())
    for x in out_rows:
        x["f_s"] = x["f_s_" + rule]
        x["delta_hz"] = x["delta_hz_" + rule]
    summary = {"rule_that_runs": rule, "V_SLOT_two_sided_all_groups_ge_0.90": two_ok, "V_SLOT_upper_all_groups_ge_0.90": upper_ok, "slot_coverage_no_copy": cov,
               "V-CAT": {"rows_checked": n_vcat, "PASS": True}, "CS_NR": len(cs_nr), "CS_pure": len(pure), "CS_mixed": mixed_n, "CTRL_HIT": len(ctrl), "CTRL_WEAK": len(weak),
               "band_mix_CS_NR": dict(collections.Counter(rowd[k]["band"] for k in cs_nr)), "band_mix_CTRL_HIT": dict(collections.Counter(rowd[k]["band"] for k in ctrl)),
               "band_mix_CTRL_WEAK": dict(collections.Counter(rowd[k]["band"] for k in weak)), "ctrl_hit_quota": quota, "ctrl_hit_eligible": len(elig), "F1": f1,
               "cycle_floor_db_pctl_0_25_50_75_100_over_cycles": [float(v) for v in np.percentile(list(cyc_floor.values()), [0, 25, 50, 75, 100])],
               "inputs": {"deltas_json_sha256": sha(C.S + "/deltas.json"), "tags_sha256": sha(GR + "/nrtax_row_tags.jsonl"), "forced_all_sha256": sha(GR + "/forced_all.jsonl"),
                          "population_sha256": sha(C.S + "/population.json")}}
    L.IN_LO, L.IN_HI = in_lo, in_hi
    json.dump({"summary": summary, "rows": out_rows}, open(OUT + "/frozen/cc_groups.json", "w"))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
