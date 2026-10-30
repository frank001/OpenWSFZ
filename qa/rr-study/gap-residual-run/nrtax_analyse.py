#!/usr/bin/env python3
"""NR-TAX analysis (spec 4179a1e3 + Amendment 1 section 8, 001bf76e). Descriptive; associations, not causes. Counts, shares and CIs only; message text is read in memory
(our decoded text, only to evaluate IsReencodable) and never persisted.  The category code is nrtax_defs.py, frozen in commit cebd2acf BEFORE this script computes anything."""
from __future__ import annotations

import collections
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import gr_item2 as I2       # noqa: E402
import nrtax_defs as D      # noqa: E402

NEW = "D:/Projects/claude/_qa-scratch/gap-residual"
MAIN_TREE = NEW + "/main-tree"
FREEZE = "cebd2acfadfeee269e0f6eff6fd8f2c274dfb815"
SEED, B = 20261029, 2000
BAR_L_PP = 0.5
EXCL_MAX = 0.05
assert (SEED, B, BAR_L_PP) == (20261029, 2000, 0.5)
POPS = ["NR", "hit", "reach"]


def git(*a):
    return subprocess.run(["git", "-C", os.path.join(HERE, "..", "..", ".."), *a], capture_output=True, text=True).stdout.strip()


def v3_freeze_check():
    """V3: nrtax_defs.py is exactly the frozen blob and the freeze commit is an ancestor of HEAD, older than this analysis's output."""
    path = "qa/rr-study/gap-residual-run/nrtax_defs.py"
    blob_frozen = git("rev-parse", f"{FREEZE}:{path}")
    blob_now = git("hash-object", path)
    anc = subprocess.run(["git", "-C", os.path.join(HERE, "..", "..", ".."), "merge-base", "--is-ancestor", FREEZE, "HEAD"]).returncode == 0
    assert blob_frozen == blob_now and anc, ("V3 FAILED", blob_frozen, blob_now, anc)
    return {"freeze_commit": FREEZE, "defs_blob": blob_now, "unchanged_since_freeze": True}


def load_forced_all():
    d = collections.defaultdict(dict)
    for line in open(NEW + "/forced_all.jsonl", encoding="utf-8"):
        r = json.loads(line)
        d[(r["stamp"], r["idx"])][r["buf"]] = r
    return d


def rec_wrong(rec):
    return (rec["fp"]["wrong"] > 0 and not rec["fp"]["found"]) or rec["fc"]["v3_wrong"] or rec["walk"]["wrong"]


def quart(v):
    return [float(x) for x in np.percentile(v, [25, 50, 75])] if len(v) else None


def main():
    out = {"v3": v3_freeze_check()}
    D.assert_native_constants(MAIN_TREE)
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    rows = pop["rows"]
    stamps = pop["stamps"]
    n_ref = pop["n_ref"]
    cyc_idx = {s: i for i, s in enumerate(stamps)}
    ncyc = len(stamps)
    ref = C.load_ref(set(stamps))
    old = {}
    for fn in ("forced_pilot.jsonl", "forced_main.jsonl"):
        for line in open(C.S + "\\" + fn, encoding="utf-8"):
            r = json.loads(line)
            old[(r["stamp"], r["idx"])] = r
    cls_old = {(r["stamp"], r["idx"]): I2.classify(r, old.get((r["stamp"], r["idx"]))) for r in rows if not r["matched"]}
    cls_new = {}
    for line in open(NEW + "/class_rows.jsonl", encoding="utf-8"):
        r = json.loads(line)
        cls_new[(r["stamp"], r["idx"])] = r["cls"]
    # ── our decoded text per hit (BOTH arm / OFF arm decode dump), for IsReencodable only ──
    nc = collections.defaultdict(list)
    for r in C.load_tsv(NEW + "/scratch/off/nc_dump.tsv"):
        if len(r) >= 11:
            nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    match = F.rebuild_matching(ref, nc)
    # ── populations ──
    pops = {}
    for r in rows:
        k = (r["stamp"], r["idx"])
        if r["matched"]:
            pops[k] = "hit"
        else:
            c = cls_old[k]
            if c == "XU":
                pops[k] = "U"
            elif c == "N":
                pops[k] = "NR" if cls_new[k] == "NR" else "reach"
            else:
                pops[k] = "reach"
    cnt = collections.Counter(pops.values())
    out["V1"] = {"NR": cnt["NR"], "hit": cnt["hit"], "U": cnt["U"], "reach": cnt["reach"], "reach_N": sum(1 for k, v in pops.items() if v == "reach" and cls_old.get(k) == "N"),
                 "reach_earlier": sum(1 for k, v in pops.items() if v == "reach" and cls_old.get(k) != "N"), "n_ref": len(rows)}
    assert (cnt["NR"], cnt["hit"], cnt["U"], cnt["reach"], len(rows)) == (1589, 9931, 164, 440, 12124) == (1589, 9931, 164, 440, n_ref), out["V1"]
    # V2: every REF row has snr / freq / dt; every hit has a batch 1..4 and our text
    v2_missing = sum(1 for r in rows if r["snr"] is None or r["freq"] is None or r["dt"] is None)
    v2_hit_no_batch = sum(1 for r in rows if r["matched"] and (r["kind"] not in (1, 2, 3, 4) or r["idx"] not in match.get(r["stamp"], {})))
    out["V2"] = {"rows_missing_field": v2_missing, "hits_without_batch_or_text": v2_hit_no_batch, "PASS": v2_missing == 0 and v2_hit_no_batch == 0}
    assert out["V2"]["PASS"], out["V2"]
    for r in rows:                                                  # the matching rebuilt here equals the population's own (kind per hit)
        if r["matched"]:
            assert match[r["stamp"]][r["idx"]][0] == r["kind"]
    # ── neighbour records, per cycle ──
    by_cycle = collections.defaultdict(list)
    for r in rows:
        k = (r["stamp"], r["idx"])
        dec = bool(r["matched"])
        batch = r["kind"] if dec else 0
        text = match[r["stamp"]][r["idx"]][4] if dec else ""
        reenc = D.reencodable(text) if dec else False
        by_cycle[r["stamp"]].append({"idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "dt": r["dt"], "decoded": dec, "batch": batch, "reenc": reenc,
                                     "subtracted": dec and batch in (1, 2) and reenc, "subtracted_noreenc": dec and batch in (1, 2)})
    # B1 counts
    b12 = [n for ns in by_cycle.values() for n in ns if n["decoded"] and n["batch"] in (1, 2)]
    out["B1"] = {"batch12_decoded_rows": len(b12), "batch12_failing_IsReencodable": sum(1 for n in b12 if not n["reenc"]),
                 "blind_spot": "a fit returning -3 leaves an all-zero subtraction; not visible in the files"}

    def neigh_of(r):
        return [n for n in by_cycle[r["stamp"]] if n["idx"] != r["idx"]]

    targets = [r for r in rows if pops[(r["stamp"], r["idx"])] in POPS]
    ties = {}

    def categorise_all(overlap=D.OVERLAP_HZ, much=D.MUCH_STRONGER_DB, delta_p=D.DELTA_P, late=False, b1_off=False):
        res = {}
        for r in targets:
            ns = neigh_of(r)
            if b1_off:
                ns = [dict(n, subtracted=n["subtracted_noreenc"]) for n in ns]
            res[(r["stamp"], r["idx"])] = D.categorise(r, ns, overlap, much, delta_p, late)
        return res

    base = categorise_all()
    cat = {k: v[0] for k, v in base.items()}
    # edge populations over ALL REF rows
    out["edge_populations_all_REF_rows"] = {"Edge_T": sum(1 for r in rows if D.edge_t(r["dt"])), "Edge_T_late_2.36": sum(1 for r in rows if D.edge_t(r["dt"], hi_margin=D.T_HI - D.LATE_LIMIT_S)),
                                            "Edge_F": sum(1 for r in rows if D.edge_f(r["freq"])),
                                            "REF_freq_range_hz": [min(r["freq"] for r in rows), max(r["freq"] for r in rows)]}
    # ── cross-tags ──
    fa = load_forced_all()
    W = {}
    n_unenc = collections.Counter()
    for r in targets:
        k = (r["stamp"], r["idx"])
        recs = fa.get(k, {})
        if not recs or any(x.get("unencodable") for x in recs.values()):
            W[k] = None
            n_unenc[pops[k]] += 1
        else:
            W[k] = any(rec_wrong(x) for x in recs.values())
    out["W_forced_coverage"] = {"unencodable_or_unforced_by_population": dict(n_unenc)}
    on_nc = collections.defaultdict(list)
    for r in C.load_tsv(NEW + "/scratch/on/nc_dump.tsv"):
        if len(r) >= 11:
            on_nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    match_on = F.rebuild_matching(ref, on_nc)
    d8 = {(s, i) for s, m in match_on.items() for i in m}
    loads = np.array([len(ref[s]) for s in stamps])
    qedges = np.percentile(loads, [20, 40, 60, 80])
    assert [float(x) for x in qedges] == [23.0, 28.0, 33.0, 37.0], qedges
    quint = lambda n: int(np.searchsorted(qedges, n, side="right")) + 1
    refc = np.array([float(len(ref[s])) for s in stamps])

    def table(catmap, tgt_rows):
        """counts[pop][cat], per-cycle arrays, by band, by quintile."""
        c = {p: collections.Counter() for p in POPS}
        cyc = {p: {x: np.zeros(ncyc) for x in D.CATEGORIES} for p in POPS}
        band = {p: collections.defaultdict(collections.Counter) for p in POPS}
        qn = {p: collections.defaultdict(collections.Counter) for p in POPS}
        for r in tgt_rows:
            k = (r["stamp"], r["idx"])
            p, x = pops[k], catmap[k][0] if isinstance(catmap[k], tuple) else catmap[k]
            c[p][x] += 1
            cyc[p][x][cyc_idx[r["stamp"]]] += 1
            band[p][x][r["band"]] += 1
            qn[p][x][quint(r["n_cycle_ref"])] += 1
        return c, cyc, band, qn
    cnts, cyc, band, qn = table(base, targets)

    # ── T1 with bootstrap ──
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, ncyc, size=(B, ncyc))
    den = refc[idx].sum(axis=1)
    tot_nr = sum(cyc["NR"][x] for x in D.CATEGORIES)
    tot_hit = sum(cyc["hit"][x] for x in D.CATEGORIES)
    t1 = {}
    for x in D.CATEGORIES:
        nr_r, hit_r = cyc["NR"][x][idx].sum(axis=1), cyc["hit"][x][idx].sum(axis=1)
        nr_pp = 100.0 * nr_r / den
        ok = hit_r > 0
        share_nr = nr_r / tot_nr[idx].sum(axis=1)
        share_hit = np.where(ok, hit_r / tot_hit[idx].sum(axis=1), np.nan)
        enr = np.where(ok, share_nr / np.where(ok, share_hit, 1), np.nan)
        excl = int((~ok).sum())
        pc = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] if np.isfinite(v).any() else [float("nan"), float("nan")]
        loss = np.where((nr_r + hit_r) > 0, nr_r / np.where((nr_r + hit_r) > 0, nr_r + hit_r, 1), np.nan)
        n_nr, n_hit, n_re = cnts["NR"][x], cnts["hit"][x], cnts["reach"][x]
        sh_nr, sh_hit = n_nr / cnt["NR"], n_hit / cnt["hit"]
        entry = {"NR": n_nr, "hit": n_hit, "reach": n_re, "NR_share": sh_nr, "hit_share": sh_hit, "reach_share": n_re / cnt["reach"],
                 "NR_pp": 100.0 * n_nr / n_ref, "NR_pp_CI": pc(nr_pp), "enrichment": (sh_nr / sh_hit) if sh_hit > 0 else None, "enrichment_CI": pc(enr),
                 "resamples_excluded": excl, "resamples_excluded_share": excl / B,
                 "loss_rate": n_nr / (n_nr + n_hit) if (n_nr + n_hit) else None, "loss_rate_CI": pc(loss)}
        prominent = (entry["NR_pp_CI"][0] >= BAR_L_PP and entry["enrichment_CI"][0] > 1 and entry["resamples_excluded_share"] <= EXCL_MAX)
        entry["prominent"] = bool(prominent)
        t1[x] = entry
    with open(NEW + "/nrtax_row_tags.jsonl", "w", encoding="utf-8") as fh:        # per-row category tags for the LATE-SUB TRAIN mechanism check (stamp + index + labels only; scratch)
        for r in targets:
            k = (r["stamp"], r["idx"])
            fh.write(json.dumps({"stamp": r["stamp"], "idx": r["idx"], "pop": pops[k], "cat": cat[k]}) + "\n")
    out["T1"] = t1
    out["T1_totals"] = {"NR": cnt["NR"], "hit": cnt["hit"], "reach": cnt["reach"]}
    out["co_channel_share_of_NR"] = sum(cnts["NR"][x] for x in ("CS", "CU-d", "CU-u", "CW")) / cnt["NR"]
    # ── T2 / T3 ──
    def split(tab, keys):
        o = {}
        for x in D.CATEGORIES:
            o[x] = {}
            for kk in keys:
                nr, ht, rc = tab["NR"][x][kk], tab["hit"][x][kk], tab["reach"][x][kk]
                o[x][str(kk)] = {"NR": nr, "hit": ht, "reach": rc, "loss_rate": nr / (nr + ht) if (nr + ht) else None}
        return o
    out["T2_by_band"] = split(band, list("ABCD"))
    out["T3_by_load_quintile"] = split(qn, [1, 2, 3, 4, 5])
    out["T3_quintile_edges"] = [float(x) for x in qedges]
    # ── T4: W and D8 per category ──
    t4 = {}
    for x in D.CATEGORIES:
        t4[x] = {}
        for p in POPS:
            ks = [(r["stamp"], r["idx"]) for r in targets if pops[(r["stamp"], r["idx"])] == p and cat[(r["stamp"], r["idx"])] == x]
            enc = [k for k in ks if W[k] is not None]
            t4[x][p] = {"n": len(ks), "n_forced": len(enc), "W": sum(1 for k in enc if W[k]), "W_share": (sum(1 for k in enc if W[k]) / len(enc)) if enc else None}
        t4[x]["D8_NR_rows_published_by_ON_arm"] = sum(1 for r in targets if pops[(r["stamp"], r["idx"])] == "NR" and cat[(r["stamp"], r["idx"])] == x and (r["stamp"], r["idx"]) in d8)
    out["T4"] = t4
    # ── T5: |df| and dSNR to the strongest overlapping neighbour (co-channel categories) ──
    t5 = {}
    for x in ("CS", "CU-d", "CU-u", "CW"):
        t5[x] = {}
        for p in ("NR", "hit"):
            df, ds = [], []
            for r in targets:
                k = (r["stamp"], r["idx"])
                if pops[k] != p or cat[k] != x:
                    continue
                ov = [n for n in neigh_of(r) if abs(n["freq"] - r["freq"]) < D.OVERLAP_HZ]
                s = max(ov, key=lambda n: (n["snr"], -abs(n["freq"] - r["freq"])))
                df.append(abs(s["freq"] - r["freq"]))
                ds.append(s["snr"] - r["snr"])
            t5[x][p] = {"n": len(df), "abs_df_hz_quartiles": quart(df), "dSNR_db_quartiles": quart(ds)}
    out["T5"] = t5
    # ── cross-tabs: CS mixed; CU-d reasons ──
    mixed = {p: [0, 0] for p in ("NR", "hit", "reach")}
    for r in targets:
        k = (r["stamp"], r["idx"])
        if cat[k] == "CS":
            mixed[pops[k]][1] += 1
            mixed[pops[k]][0] += bool(base[k][1]["mixed"])
    out["CS_mixed_with_undecoded_stronger_overlapping_neighbour"] = {p: {"CS_rows": v[1], "also_undecoded_stronger": v[0], "share": (v[0] / v[1]) if v[1] else None} for p, v in mixed.items()}
    cud = {p: collections.Counter() for p in POPS}
    for r in targets:
        k = (r["stamp"], r["idx"])
        if cat[k] != "CU-d":
            continue
        st = [n for n in neigh_of(r) if abs(n["freq"] - r["freq"]) < D.OVERLAP_HZ and n["snr"] >= r["snr"] and n["decoded"]]
        cud[pops[k]]["has_batch34_neighbour" if any(n["batch"] in (3, 4) for n in st) else "only_batch12_not_reencodable"] += 1
    out["CU_d_reasons"] = {p: dict(v) for p, v in cud.items()}
    # ── SUPPLEMENTARY (not in the spec; added after the freeze and labelled so; no category depends on it): what ARE the undecoded stronger overlapping neighbours of an NR row?
    #    Their own population: NR (unreached), reach (reachable miss), U (unencodable for comparison).  Points at "decode the neighbour first" only where the neighbour is reachable.
    supp = {}
    for x, label in (("CU-u", "CU-u"), ("CS", "CS_mixed")):
        c2 = collections.Counter()
        for r in targets:
            k = (r["stamp"], r["idx"])
            if pops[k] != "NR" or cat[k] != x or (x == "CS" and not base[k][1]["mixed"]):
                continue
            und = [n for n in neigh_of(r) if abs(n["freq"] - r["freq"]) < D.OVERLAP_HZ and n["snr"] >= r["snr"] and not n["decoded"]]
            kinds = {pops[(r["stamp"], n["idx"])] for n in und}
            c2["rows"] += 1
            c2["has_reachable_miss_neighbour"] += ("reach" in kinds)
            c2["only_NR_or_U_neighbours"] += (not ("reach" in kinds))
            c2["has_NR_neighbour"] += ("NR" in kinds)
        supp[label] = dict(c2)
    out["SUPPLEMENTARY_undecoded_stronger_neighbour_population"] = supp
    # ── sensitivity: categories whose NR pp changes by more than 0.5 pp of n_ref ──
    def pp_by_cat(catmap):
        c = collections.Counter(catmap[(r["stamp"], r["idx"])][0] if isinstance(catmap[(r["stamp"], r["idx"])], tuple) else catmap[(r["stamp"], r["idx"])]
                                for r in targets if pops[(r["stamp"], r["idx"])] == "NR")
        return {x: 100.0 * c[x] / n_ref for x in D.CATEGORIES}
    basepp = pp_by_cat(base)
    sens = {}
    variants = {"overlap_40": dict(overlap=40.0), "overlap_60": dict(overlap=60.0), "nc_6dB": dict(much=6.0), "nc_15dB": dict(much=15.0),
                "late_limit_2.36s": dict(late=True), "delta_p_0.5": dict(delta_p=0.5), "delta_p_0.7": dict(delta_p=0.7), "B1_off_(subtracted_ignores_IsReencodable)": dict(b1_off=True)}
    for name, kw in variants.items():
        pp = pp_by_cat(categorise_all(**kw))
        sens[name] = {"NR_pp": pp, "categories_changed_more_than_0.5pp": {x: pp[x] - basepp[x] for x in D.CATEGORIES if abs(pp[x] - basepp[x]) > BAR_L_PP}}
    out["sensitivity"] = sens
    out["NR_pp_base"] = basepp
    json.dump(out, open(NEW + "/result_nrtax.json", "w"), indent=1, sort_keys=True, default=str)
    print(json.dumps({k: out[k] for k in ("v3", "V1", "V2", "B1", "edge_populations_all_REF_rows", "co_channel_share_of_NR", "W_forced_coverage")}, indent=1, sort_keys=True, default=str))
    print(json.dumps({x: {k: t1[x][k] for k in ("NR", "hit", "reach", "NR_pp", "NR_pp_CI", "enrichment", "enrichment_CI", "resamples_excluded", "loss_rate", "prominent")} for x in D.CATEGORIES}, indent=1, default=str))


if __name__ == "__main__":
    main()
