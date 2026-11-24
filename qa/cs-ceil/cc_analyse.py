#!/usr/bin/env python3
"""CS-CEIL analysis (spec arch/cs-model-ceiling 6d911263 + A1 + A2 e3e5feca).  Reads the frozen table, V-REPRO and the relocated rows; writes numbers only.
    python cc_analyse.py [--run DIR]      -> <run>/cc_result.json  and a printed verdict.  Run ONCE per relocated output (the verdict is mechanical, cc_lib.verdict)."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "..", "rr-study")
for p in (HERE, os.path.join(RR, "gap-relocate-run")):
    sys.path.insert(0, p)
import cc_lib as L          # noqa: E402
import gr_common as C       # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/cs-ceil"
GROUPS = (("CS-NR", "in_CS_NR"), ("CS-pure", "in_pure"), ("CTRL-HIT", "in_CTRL_HIT"), ("CTRL-WEAK", "in_CTRL_WEAK"))


def quart_labels(vals):
    q = np.percentile([v for v in vals if v is not None], [25, 50, 75])
    return q, (lambda v: None if v is None else int(np.searchsorted(q, v, side="right")))


def build_cyc(table, reloc, stamps, nref_by):
    """per-cycle arrays for cc_lib.readout.  A row 'has a copy' iff it has a slot, is encodable and its fit is not fit-zero.  no-slot and fit-zero rows are never counted as copies."""
    ix = {s: i for i, s in enumerate(stamps)}
    z = lambda: np.zeros(len(stamps))
    cyc = {k: z() for k in ("nref", "ns_dec", "ns_fitzero", "ns_noslot", "pure_dec", "pure_copy", "hit_dec", "hit_copy", "weak_dec", "weak_copy")}
    for s, i in ix.items():
        cyc["nref"][i] = nref_by[s]
    for r in table:
        i = ix[r["stamp"]]
        rl = reloc.get((r["stamp"], r["idx"]))
        slot = r["f_s"] is not None
        fz = bool(rl and rl["fit_zero"])
        copy = slot and rl is not None and not fz and not rl["unencodable"]
        dec = bool(copy and rl["decodable"])
        if r["in_CS_NR"]:
            cyc["ns_noslot"][i] += (not slot)
            cyc["ns_fitzero"][i] += (slot and fz)
            cyc["ns_dec"][i] += dec
        if r["in_pure"]:
            cyc["pure_dec"][i] += dec
            cyc["pure_copy"][i] += copy
        if r["in_CTRL_HIT"]:
            cyc["hit_dec"][i] += dec
            cyc["hit_copy"][i] += copy
        if r["in_CTRL_WEAK"]:
            cyc["weak_dec"][i] += dec
            cyc["weak_copy"][i] += copy
    return cyc


def share(rows, reloc):
    c = [r for r in rows if r["f_s"] is not None and (r["stamp"], r["idx"]) in reloc and not reloc[(r["stamp"], r["idx"])]["fit_zero"]]
    d = sum(1 for r in c if reloc[(r["stamp"], r["idx"])]["decodable"])
    return {"copies": len(c), "decodable": d, "RL": d / len(c) if c else None}


def descriptives(table, reloc):
    cs = [r for r in table if r["in_CS_NR"]]
    out = {"RL_CS_NR": share(cs, reloc), "RL_mixed": share([r for r in cs if r["mixed"]], reloc), "RL_pure": share([r for r in cs if not r["mixed"]], reloc)}
    out["share_CS_NR_abs_delta_gt_500Hz"] = sum(1 for r in cs if r["f_s"] is not None and abs(r["delta_hz"]) > 500) / max(sum(1 for r in cs if r["f_s"] is not None), 1)
    out["RL_by_band"] = {b: share([r for r in cs if r["band"] == b], reloc) for b in L.BANDS}
    for name, key in (("nbr_dsnr", "nbr_dsnr"), ("nbr_abs_df", "nbr_df")):
        vals = [r[key] for r in cs]
        if any(v is not None for v in vals):
            q, lab = quart_labels(vals)
            out["RL_by_" + name + "_quartile"] = {"cuts": [float(x) for x in q], "q": {str(k): share([r for r in cs if lab(r[key]) == k], reloc) for k in range(4)}}
    amp = {(r["stamp"], r["idx"]): reloc[(r["stamp"], r["idx"])].get("amp_rms") for r in cs if (r["stamp"], r["idx"]) in reloc}
    av = [v for v in amp.values() if v is not None]
    if av:
        q = np.percentile(av, [25, 50, 75])
        out["RL_by_fitted_amplitude_quartile_F2"] = {"cuts": [float(x) for x in q], "q": {str(k): share([r for r in cs if amp.get((r["stamp"], r["idx"])) is not None and int(np.searchsorted(q, amp[(r["stamp"], r["idx"])], side="right")) == k], reloc) for k in range(4)}}
    rb = [r["row_band_minus_floor_db"] for r in cs if r["row_band_minus_floor_db"] is not None]
    out["A2_2_median_row_band_minus_cycle_floor_db_UPPER_BOUND_on_residue_floor"] = float(np.median(rb)) if rb else None
    out["A2_2_pctl_5_25_50_75_95"] = [float(v) for v in np.percentile(rb, [5, 25, 50, 75, 95])] if rb else None
    return out


def main():
    run = sys.argv[sys.argv.index("--run") + 1] if "--run" in sys.argv else OUT + "/run"
    G = json.load(open(OUT + "/frozen/cc_groups.json"))
    table, summ = G["rows"], G["summary"]
    vr = json.load(open(OUT + "/frozen/v_repro.json"))
    reloc = {}
    for line in open(run + "/relocated.jsonl", encoding="utf-8"):
        r = json.loads(line)
        reloc[(r["stamp"], r["idx"])] = r
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    stamps = pop["stamps"]
    nref_by = collections.Counter(r["stamp"] for r in pop["rows"])
    assert sum(nref_by.values()) == L.N_REF and len(stamps) == L.N_CYCLES
    assert all(not r["unencodable"] for r in reloc.values()), "unencodable relocated rows: report"
    cyc = build_cyc(table, reloc, stamps, nref_by)
    rule = summ["rule_that_runs"]
    v_slot = {g: summ["slot_coverage_no_copy"][rule][g]["V_SLOT_share"] for g, _ in GROUPS}
    v_slot_ok = all(v >= L.V_SLOT for v in v_slot.values())
    res = L.readout(cyc, L.boot_indices())
    v_rel_ok = bool(res["RL_CTRL_HIT"] >= L.V_REL)
    v_repro_ok = bool(vr["V-REPRO"]["PASS"])
    verdict = L.verdict(res, v_repro_ok, v_slot_ok, v_rel_ok)
    cd = [r for r in table if r["in_pure"] and r["band"] in ("C", "D")]
    rlw = res["RL_CTRL_WEAK"]
    cd_copy = sum(1 for r in cd if r["f_s"] is not None and (r["stamp"], r["idx"]) in reloc and not reloc[(r["stamp"], r["idx"])]["fit_zero"])
    cd_dec = sum(1 for r in cd if r["f_s"] is not None and (r["stamp"], r["idx"]) in reloc and not reloc[(r["stamp"], r["idx"])]["fit_zero"] and reloc[(r["stamp"], r["idx"])]["decodable"])
    counts = {}
    for g, flag in GROUPS:
        rs = [r for r in table if r[flag]]
        counts[g] = {"rows": len(rs), "no_slot": sum(1 for r in rs if r["f_s"] is None), "fit_zero": sum(1 for r in rs if r["f_s"] is not None and reloc[(r["stamp"], r["idx"])]["fit_zero"]),
                     "copies": sum(1 for r in rs if r["f_s"] is not None and not reloc[(r["stamp"], r["idx"])]["fit_zero"]), "decodable_relocated": sum(1 for r in rs if r["f_s"] is not None and reloc[(r["stamp"], r["idx"])]["decodable"]),
                     "fit_rc_counts": dict(collections.Counter(reloc[(r["stamp"], r["idx"])]["fit_rc"] for r in rs if r["f_s"] is not None))}
    out = {"verdict": verdict, "rule_that_ran": rule, "V_REPRO_PASS": v_repro_ok, "V_SLOT": v_slot, "V_SLOT_both_rules_from_pilot": {k: {g: c["V_SLOT_share"] for g, c in v.items()} for k, v in summ["slot_coverage_no_copy"].items()},
           "V_REL": {"RL_CTRL_HIT": res["RL_CTRL_HIT"], "bar": L.V_REL, "PASS": v_rel_ok}, "readout": res,
           "NET_CEIL_descriptive_CS_pure_bands_C_D": {"rows": len(cd), "copies": cd_copy, "decodable": cd_dec, "NET_CEIL_pp": 100.0 * (cd_dec - rlw * cd_copy) / L.N_REF},
           "counts_per_group": counts, "descriptives": descriptives(table, reloc), "slot_distributions_per_group_from_pilot": {g: {k: c[k] for k in ("abs_df_pctl_5_25_50_75_95", "slot_minus_floor_db_pctl_5_25_50_75_95")} for g, c in summ["slot_coverage_no_copy"][rule].items()},
           "caveat_CTRL_WEAK": "73 rows, bands C and D only (A2.4): the optimism rate over-corrects A/B rows, which works against MODEL-STUDY"}
    json.dump(out, open(run + "/cc_result.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
