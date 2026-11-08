#!/usr/bin/env python3
"""SUB-COVER (#273) analysis (spec 871e163f + Amendment 1 0cd47417). Rows and the decision rule are the code below.

    python sc_analyse.py freeze     BEFORE any O* output: O-BUILD (from obuild.json), O-ROUND (forced legs on the rounded R2 vs the stored R2), the on-file R2 / R3 control figures, the R2 fit-zero share
                                    (the O-ENC bar's source), O-REPRO (GAP-RESIDUAL's classes from the stored R2/R3 forced results). Writes freeze_figures.json.
    python sc_analyse.py main       after O*: O-REPRO and O-BUILD recheck, O-CTRL (paired, stratified), O-ENC, G*, G273, strata, wrong payloads, the decision.

Definitions (frozen):
  "still decodes at its own position" (A1.4) = forced primary leg found OR forced coherent leg v3_match (either leg).
  "decodable on O*" for an NR row (G*) = primary found OR coherent v3_match (any gate) OR walk match: GAP-RESIDUAL's classes RP / RC / RG / RW. NR rows are by definition not decodable on R2 or R3.
  O-REPRO : the forced legs on the STORED R2 u R3 give GAP-RESIDUAL's class counts exactly: RC 133, RG 51, RW 77, RP-search 10 (classes as gres_main.py, on the 2,029 N rows).
  O-BUILD : max |O*-builder(batch-1 natives) - stored R2| <= 1e-5 x peak in every cycle (bit-identical reported).        STOP on failure, no retries.
  O-ROUND : |share(R2 rebuilt with dt rounded to 0.1 s) - share(stored R2)| on the 7,239 batch-1 hits > 0.5 pp  =>  the batch-4 stratum (placed from rounded values) reads as a lower bound.
  O-CTRL  : batch-1 hits (7,239): CI_hi(share_O* - share_R2) <= +2.0 pp;  batch-2 hits (1,339): CI_hi(share_O* - share_R3) <= +2.0 pp  (cycle bootstrap, paired on the same rows). Batches 3-4
            and oracle-rescued decodes: reported, not gated. Bar basis (Amendment 2, QA's CORRECTED figures keyed by (stamp, idx)): the reference shares are 2.8 % (R2) and 3.4 % (R3); a builder that
            failed to subtract a fraction f of the hits would show about 2.8 + 0.9 f pp (unsubtracted share 93 %); the on-file drift R3 - R2 is +0.10 pp [+0.03, +0.18] for +19 % signals.
  O-ENC   : (unencodable + fit-zero) / decodes to subtract <= the R2 fit-zero share on file (the freeze states it). If it fires the bound reads ">=" only.
  G*      = NR rows decodable on O* (pp of n_ref 12,124).  G273 = G* minus the L1'-territory stratum (CU-d with a batch-3/4 stronger overlapping decoded neighbour).
  DECISION: BUILD-WORTH if CI_lo(G273) >= 1.0 pp;  CLOSE if CI_hi(G273) < 0.5 pp;  BETWEEN otherwise (to the Captain). Valid only if O-REPRO, O-BUILD and O-CTRL pass.
Bootstrap: B = 2000 resamples of the 400 cycles, seed 20261108. Counts only leave this script (HK-037)."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gr_forced as F       # noqa: E402
import gres_main as G       # noqa: E402  (leg_flags only)

SC = "D:/Projects/claude/_qa-scratch/sub-cover"
GR = "D:/Projects/claude/_qa-scratch/gap-residual"
CAP = GR + "/cap/off"
B, SEED = 2000, 20261108
BUILD_WORTH_LO, CLOSE_HI, ROUND_PP, REL_TOL = 1.0, 0.5, 0.5, 1e-5
CTRL_MARGIN_PP = 2.0           # O-CTRL (Amendment 2, 4f3a477a): CI_hi(share_O* - share_ref) <= +2.0 pp
REPRO = {"RC": 133, "RG": 51, "RW": 77, "RP-search": 10}
assert (B, SEED, BUILD_WORTH_LO, CLOSE_HI, ROUND_PP, REL_TOL, CTRL_MARGIN_PP) == (2000, 20261108, 1.0, 0.5, 0.5, 1e-5, 2.0)


def load_forced(path):
    d = collections.defaultdict(dict)
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        d[(r["stamp"], r["idx"])][r["buf"]] = r
    return d


def either(rec):
    """primary found OR coherent v3_match; a record without legs (unencodable) is not decoded."""
    if rec is None or rec.get("unencodable"):
        return False
    return bool((rec.get("fp") or {}).get("found") or (rec.get("fc") or {}).get("v3_match"))


def anyleg(rec):
    if rec is None or rec.get("unencodable"):
        return False
    return bool(either(rec) or (rec.get("walk") or {}).get("match"))


def anywrong(rec):
    if rec is None or rec.get("unencodable"):
        return False
    return bool((rec.get("fp") or {}).get("wrong", 0) > 0 or (rec.get("fc") or {}).get("v3_wrong") or (rec.get("walk") or {}).get("wrong"))


class Boot:
    def __init__(self, stamps):
        self.stamps = stamps
        self.ix = {s: i for i, s in enumerate(stamps)}
        n = len(stamps)
        self.idx = np.random.default_rng(SEED).integers(0, n, size=(B, n))

    def arr(self, keyed):
        a = np.zeros(len(self.stamps))
        for s, v in keyed.items():
            a[self.ix[s]] += v
        return a

    def pp(self, num, den):
        """point and 95 % CI of 100 * sum(num) / sum(den) over cycles (paired resamples)."""
        pt = 100.0 * num.sum() / den.sum()
        d = den[self.idx].sum(axis=1)
        ci = 100.0 * num[self.idx].sum(axis=1) / np.where(d == 0, np.nan, d)
        return {"pp": float(pt), "CI": [float(np.nanpercentile(ci, 2.5)), float(np.nanpercentile(ci, 97.5))]}


def pop_and_tags():
    pop = json.load(open(C.S + "\\population.json", encoding="utf-8"))
    tags = {}
    for line in open(GR + "/nrtax_row_tags.jsonl", encoding="utf-8"):
        r = json.loads(line)
        tags[(r["stamp"], r["idx"])] = r
    return pop, tags


def share_pair(rows, fa, fb, bufa, bufb, boot):
    """paired still-decoded shares on the same rows; returns shares and the paired difference (b - a) in pp with CI."""
    na = collections.Counter(); da = collections.Counter(); db = collections.Counter()
    for r in rows:
        k = (r["stamp"], r["idx"])
        ra, rb = fa.get(k, {}).get(bufa), fb.get(k, {}).get(bufb)
        if ra is None or rb is None:
            continue
        na[r["stamp"]] += 1
        da[r["stamp"]] += either(ra)
        db[r["stamp"]] += either(rb)
    den, a, b = boot.arr(na), boot.arr(da), boot.arr(db)
    return {"rows": int(den.sum()), "share_a_pct": 100 * a.sum() / den.sum(), "share_b_pct": 100 * b.sum() / den.sum(), "diff_pp": boot.pp(b - a, den)}


def repro_classes(pop, tags, fall):
    dec = F.load_dec()
    nat = collections.defaultdict(list)
    for stamp in {r["stamp"] for r in pop["rows"]}:
        for line in open(f"{CAP}/native/{stamp}.tsv", encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 5 and p[0] in ("R2", "R3"):
                nat[stamp].append(p[4])
    ref = C.load_ref({r["stamp"] for r in pop["rows"]})
    cw_cache = {}

    def cw(text):
        if text not in cw_cache:
            x = dec.true_codeword(text)
            cw_cache[text] = None if x is None else x[:F.FT8_PAYLOAD_BITS]
        return cw_cache[text]

    def native_has(stamp, idx):
        snr, dt, freq, text = ref[stamp][idx]
        X = cw(text)
        if X is None:
            return False
        for nt in nat.get(stamp, []):
            Y = cw(nt)
            if Y is not None and F.CMP.payload_match(X, Y, text, F.V_STAR):
                return True
        return False

    import gr_item2 as I2       # GAP-RESIDUAL's N = the misses GAP-RELOCATE's legs classed "N" on the original audio (gres_main.py:136-137), not NR u reach
    _, old = G.load_old()
    cls = collections.Counter()
    for r in pop["rows"]:
        k = (r["stamp"], r["idx"])
        if r["matched"] or I2.classify(r, old.get(k)) != "N":
            continue
        bufs = {b: v for b, v in fall.get(k, {}).items() if b in ("R2", "R3")}
        f = G.leg_flags(bufs)
        if f["unenc"] or not bufs:
            cls["X"] += 1
        elif native_has(*k):
            cls["RP-native"] += 1
        elif f["fp"]:
            cls["RP-search"] += 1
        elif f["v3_g1"]:
            cls["RC"] += 1
        elif f["v3_g0"]:
            cls["RG"] += 1
        elif f["walk"]:
            cls["RW"] += 1
        else:
            cls["NR"] += 1
    return dict(cls)


def cmd_freeze():
    pop, tags = pop_and_tags()
    stamps = pop["stamps"]
    boot = Boot(stamps)
    fall = load_forced(GR + "/forced_all.jsonl")
    ob = json.load(open(f"{SC}/obuild.json"))["summary"]
    out = {"O-BUILD": {"cycles": ob["cycles"], "bit_identical_cycles": ob["bit_identical_cycles"], "max_rel_diff": ob["max_rel_diff"], "cycles_rel_gt_tol": ob["cycles_rel_gt_1e-5"],
                       "candidates_total": ob["candidates_total"], "PASS": bool(ob["O-BUILD"]["PASS"])}}
    b1 = [r for r in pop["rows"] if r["matched"] and r["kind"] == 1]
    b2 = [r for r in pop["rows"] if r["matched"] and r["kind"] == 2]
    out["R2_control_on_file"] = {"batch1_hits": share_pair(b1, fall, fall, "R2", "R3", boot), "note": "share_a = R2, share_b = R3, diff = R3 - R2 on the same rows (more neighbours subtracted)"}
    out["R3_control_on_file_batch2_hits"] = share_pair(b2, fall, fall, "R2", "R3", boot)
    out["O_ENC_bar_source"] = {"R2_fit_zero": ob["fit_zero_total"], "R2_fits": ob["candidates_total"], "fit_zero_share": ob["fit_zero_total"] / ob["candidates_total"]}
    if os.path.isfile(f"{SC}/forced_R2R.jsonl"):
        frr = load_forced(f"{SC}/forced_R2R.jsonl")
        rd = share_pair(b1, fall, frr, "R2", "R2R", boot)
        out["O-ROUND"] = {"batch1_hits": rd, "exceeds_0p5pp": abs(rd["diff_pp"]["pp"]) > ROUND_PP,
                          "reading": "batch-4 stratum is a LOWER BOUND" if abs(rd["diff_pp"]["pp"]) > ROUND_PP else "rounding does not matter at this size"}
    cls = repro_classes(pop, tags, fall)
    out["O-REPRO"] = {"classes": cls, "expected": REPRO, "PASS": all(cls.get(k) == v for k, v in REPRO.items())}
    json.dump(out, open(f"{SC}/freeze_figures.json", "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


def cmd_main():
    pop, tags = pop_and_tags()
    stamps = pop["stamps"]
    boot = Boot(stamps)
    rows = pop["rows"]
    n_ref = len(rows)
    fall = load_forced(GR + "/forced_all.jsonl")
    fos = load_forced(f"{SC}/forced_OSTAR.jsonl")
    ff = json.load(open(f"{SC}/freeze_figures.json"))
    ost = json.load(open(f"{SC}/ostar.json"))["summary"]
    res = {"n_ref": n_ref, "freeze": {k: ff[k] for k in ("O-BUILD", "O-REPRO", "O-ROUND", "O_ENC_bar_source") if k in ff}}
    # O-CTRL
    b1 = [r for r in rows if r["matched"] and r["kind"] == 1]
    b2 = [r for r in rows if r["matched"] and r["kind"] == 2]
    c1 = share_pair(b1, fall, fos, "R2", "OSTAR", boot)
    c2 = share_pair(b2, fall, fos, "R3", "OSTAR", boot)
    res["O-CTRL"] = {"batch1_vs_R2": c1, "batch2_vs_R3": c2, "margin_pp": CTRL_MARGIN_PP,
                     "PASS": c1["diff_pp"]["CI"][1] <= CTRL_MARGIN_PP and c2["diff_pp"]["CI"][1] <= CTRL_MARGIN_PP}
    rep = {}
    for kd in (3, 4):
        hs = [r for r in rows if r["matched"] and r["kind"] == kd]
        den = collections.Counter(); num = collections.Counter()
        for r in hs:
            rec = fos.get((r["stamp"], r["idx"]), {}).get("OSTAR")
            if rec is None:
                continue
            den[r["stamp"]] += 1
            num[r["stamp"]] += either(rec)
        d, n = boot.arr(den), boot.arr(num)
        rep[f"batch{kd}_hits_still_decoded_on_Ostar"] = {"rows": int(d.sum()), **boot.pp(n, d)}
    res["O-CTRL"]["reported_not_gated"] = rep
    # O-ENC
    bar = ff["O_ENC_bar_source"]["fit_zero_share"]
    share = (ost["unencodable"] + ost["fit_zero"]) / ost["decodes"]
    res["O-ENC"] = {"unencodable": ost["unencodable"], "fit_zero": ost["fit_zero"], "decodes": ost["decodes"], "share": share, "bar_R2_fit_zero_share": bar, "PASS": share <= bar,
                    "oracle_text_used": ost["oracle_text_used"], "native_unmatched_kinds123": ost["native_unmatched_kinds123"], "by_kind": ost["by_kind"]}
    nsub = sum(ost["by_kind"].values())
    r2fits = ff["O_ENC_bar_source"]["R2_fits"]
    res["signals_subtracted"] = {"Ostar": nsub, "R2": r2fits, "more_than_R2": nsub - r2fits, "ratio": nsub / r2fits, "Ostar_by_batch": ost["by_kind"]}
    # strata of the NR rows
    by_cycle = collections.defaultdict(list)
    for r in rows:
        by_cycle[r["stamp"]].append({"idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "decoded": bool(r["matched"]), "batch": r["kind"] if r["matched"] else 0})
    nr = [r for r in rows if tags.get((r["stamp"], r["idx"]), {}).get("pop") == "NR"]
    assert len(nr) == 1589
    strata = collections.defaultdict(lambda: {"den": collections.Counter(), "dec": collections.Counter(), "wrong": collections.Counter(), "decwrong": collections.Counter()})
    denall = boot.arr(collections.Counter(r["stamp"] for r in rows))
    never = 0
    for r in nr:
        k = (r["stamp"], r["idx"])
        cat = tags[k]["cat"]
        if cat == "CU-d":
            st = [n for n in by_cycle[r["stamp"]] if n["idx"] != r["idx"] and abs(n["freq"] - r["freq"]) < 50.0 and n["snr"] >= r["snr"] and n["decoded"]]
            cat = "CU-d:batch34-neighbour(L1p-territory)" if any(n["batch"] in (3, 4) for n in st) else "CU-d:batch12-only(#273-proper)"
        rec = fos.get(k, {}).get("OSTAR")
        d, w = anyleg(rec), anywrong(rec)
        if rec is None:
            never += 1
        for key in (cat, "ALL"):
            strata[key]["den"][r["stamp"]] += 1
            strata[key]["dec"][r["stamp"]] += d
            strata[key]["wrong"][r["stamp"]] += w
            strata[key]["decwrong"][r["stamp"]] += (d and w)
    res["NR_rows_without_Ostar_record"] = never
    res["strata"] = {}
    for key, v in sorted(strata.items()):
        dec = boot.arr(v["dec"])
        res["strata"][key] = {"nr_rows": int(boot.arr(v["den"]).sum()), "decodable_on_Ostar": int(dec.sum()), "gain": boot.pp(dec, denall), "rows_with_wrong_payload_output": int(boot.arr(v["wrong"]).sum())}
    g_all = boot.arr(strata["ALL"]["dec"])
    l1p = boot.arr(strata["CU-d:batch34-neighbour(L1p-territory)"]["dec"]) if "CU-d:batch34-neighbour(L1p-territory)" in strata else np.zeros(len(stamps))
    res["G_star"] = boot.pp(g_all, denall)
    res["G273"] = boot.pp(g_all - l1p, denall)
    lo, hi = res["G273"]["CI"]
    decision = "BUILD-WORTH" if lo >= BUILD_WORTH_LO else "CLOSE" if hi < CLOSE_HI else "BETWEEN"
    valid = res["freeze"]["O-REPRO"]["PASS"] and res["freeze"]["O-BUILD"]["PASS"] and res["O-CTRL"]["PASS"]
    res["decision"] = decision if valid else f"NO DECISION (validity rows failed); numbers would read {decision}"
    if not res["O-ENC"]["PASS"]:
        res["O-ENC_note"] = "O-ENC fires: the bound reads as '>=' only"
    if res.get("freeze", {}).get("O-ROUND", {}).get("exceeds_0p5pp"):
        res["O-ROUND_note"] = "the batch-4 stratum (placed from rounded values) reads as a lower bound"
    json.dump(res, open(f"{SC}/sc_result.json", "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        cmd_freeze()
    elif cmd == "main":
        cmd_main()
    else:
        sys.exit(__doc__)
