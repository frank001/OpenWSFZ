#!/usr/bin/env python3
"""LIVE-GAP-NOW analysis: ROW 0d-0g, gate rows B1-B4, sections 3.5 A1-A5.

Reads decode_leg.py's JSONL outputs from artefacts/live-gap-now/_out/ and the
corpora's own ALL.TXT files. ROW 0a/0b/0c were separate, already-passed static
checks (dll_pin.row0a, manual header diff, and the direct H1-reproduction
check) -- not re-checked here.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import corpus  # noqa: E402
import matcher  # noqa: E402
import seam  # noqa: E402
import bootstrap as BS  # noqa: E402
import leg_output as LO  # noqa: E402
import dll_pin  # noqa: E402

OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "live-gap-now", "_out")
BAR_D = 2.0
ROW0G_SE_MAX = 0.75
MAX_RESULTS = 200

LEGS = ("L08", "NOW", "NOW40")


def out_path(leg, corpus_id):
    return os.path.join(OUT_DIR, "%s_%s.jsonl" % (leg, corpus_id))


def load_ref_c1():
    lo, hi = corpus.C1_WINDOW
    wsjtx_a = matcher.load_all(os.path.join(corpus.C1_DIR, "wsjt-x", "ALL.TXT"), lo, hi)
    replayed_ts = {ts for ts, _ in corpus.c1_cycles()}
    return {k: v for k, v in wsjtx_a.items() if k[0] in replayed_ts}


def load_ref_c2():
    c2_cycles, _ = corpus.c2_cycles()
    replayed_ts = {ts for ts, _ in c2_cycles}
    lo = min(replayed_ts)
    hi = max(replayed_ts)
    wsjtx_a = matcher.load_all(os.path.join(corpus.C2_DIR, "wsjtx-1-ft991a", "ALL.TXT"), lo, hi)
    return {k: v for k, v in wsjtx_a.items() if k[0] in replayed_ts}


def load_live_c2_openwsfz():
    c2_cycles, _ = corpus.c2_cycles()
    replayed_ts = {ts for ts, _ in c2_cycles}
    lo, hi = min(replayed_ts), max(replayed_ts)
    d = matcher.load_all(os.path.join(corpus.C2_DIR, "openwsfz", "ALL.TXT"), lo, hi)
    return {k: v for k, v in d.items() if k[0] in replayed_ts}


def load_live_c1_owsfz():
    lo, hi = corpus.C1_WINDOW
    d = matcher.load_all(os.path.join(corpus.C1_DIR, "owsfz", "ALL.TXT"), lo, hi)
    replayed_ts = {ts for ts, _ in corpus.c1_cycles()}
    return {k: v for k, v in d.items() if k[0] in replayed_ts}


def truncation_report(log):
    total_trunc = 0
    for leg in LEGS:
        for cid in ("C1", "C2"):
            p = out_path(leg, cid)
            if not os.path.exists(p):
                continue
            n_trunc, n_cycles = LO.check_truncation(p, MAX_RESULTS)
            if n_trunc:
                log("TRUNCATION GUARD: %s/%s: %d/%d cycles hit MAX_RESULTS=%d" %
                    (leg, cid, n_trunc, n_cycles, MAX_RESULTS))
            total_trunc += n_trunc
    return total_trunc


def freq_band(f):
    if f < 200:
        return "<200Hz"
    if f < 3000:
        return "200-3000Hz"
    return ">=3000Hz"


def snr_bin(snr):
    return 2 * (snr // 2)  # 2 dB bins, floor


def per_bin_recovery(ref, hit_set, binfn, key_of):
    """ref: {key:(snr,freq)}. hit_set: set of matched keys. binfn: value->bin.
    key_of: 'snr' or 'freq' selects which ref value feeds binfn."""
    idx = 0 if key_of == "snr" else 1
    totals = {}
    hits = {}
    for k, v in ref.items():
        b = binfn(v[idx])
        totals[b] = totals.get(b, 0) + 1
        if k in hit_set:
            hits[b] = hits.get(b, 0) + 1
    return {b: (100.0 * hits.get(b, 0) / n) for b, n in totals.items()}, totals


def main():
    def log(msg):
        print(msg, flush=True)

    result = {}

    # --- load REF (A-only, restricted to replayed cycles) ---
    ref_c1 = load_ref_c1()
    ref_c2 = load_ref_c2()
    log("REF(C1, A-only, restricted) = %d" % len(ref_c1))
    log("REF(C2, A-only, restricted) = %d" % len(ref_c2))

    # --- truncation guard, all legs/corpora ---
    n_trunc = truncation_report(log)
    result["truncation_total"] = n_trunc

    # --- load leg outputs ---
    leg_out = {(leg, cid): LO.load_leg_jsonl(out_path(leg, cid))
               for leg in LEGS for cid in ("C1", "C2")}

    # --- recovery per leg per corpus ---
    rec = {}
    for cid, ref in (("C1", ref_c1), ("C2", ref_c2)):
        for leg in LEGS:
            r = matcher.recovery(leg_out[(leg, cid)], ref)
            rec[(leg, cid)] = r
            log("R(%s, %s): R_base=%.4f%% R_wild=%.4f%% n_ref=%d exact=%d wild_gained=%d" %
                (leg, cid, r["R_base"], r["R_wild"], r["n_ref"], r["n_exact"], r["n_wild_gained"]))

    # --- ROW 0d: NOW's C2 replay vs C2 LIVE openwsfz ALL.TXT ---
    live_c2 = load_live_c2_openwsfz()
    row0d = seam.seam_fidelity(live_c2, leg_out[("NOW", "C2")])
    row0d_pass = row0d["F_live"] >= 0.99 and row0d["F_rep"] >= 0.99
    log("ROW 0d: F_live=%.4f (n=%d) F_rep=%.4f (n=%d) -> %s" %
        (row0d["F_live"], row0d["n_live_total"], row0d["F_rep"], row0d["n_rep_total"],
         "PASS" if row0d_pass else "FAIL -- B-rows VOID"))
    result["row0d"] = {**row0d, "pass": row0d_pass}

    # --- ROW 0e: L08's C1 replay vs C1 LIVE owsfz ALL.TXT (report only) ---
    live_c1 = load_live_c1_owsfz()
    row0e = seam.seam_fidelity(live_c1, leg_out[("L08", "C1")])
    log("ROW 0e (report only, stand-in fidelity): F_live=%.4f (n=%d) F_rep=%.4f (n=%d)" %
        (row0e["F_live"], row0e["n_live_total"], row0e["F_rep"], row0e["n_rep_total"]))
    result["row0e"] = row0e

    # --- ROW 0f: L08 vs NOW full tuples on C1, must NOT be identical everywhere ---
    full_l08 = LO.load_leg_full(out_path("L08", "C1"))
    full_now = LO.load_leg_full(out_path("NOW", "C1"))
    row0f = seam.seam_sensitivity(full_l08, full_now)
    row0f_pass = not row0f["identical_everywhere"]
    log("ROW 0f: %d/%d cycles differ between L08 and NOW -> %s" %
        (row0f["n_cycles_differing"], row0f["n_cycles"],
         "PASS (seam not blind)" if row0f_pass else "FAIL -- instrument blind, VOID, never B2"))
    result["row0f"] = {**row0f, "pass": row0f_pass}

    if not row0d_pass:
        log("STOPPING: ROW 0d failed, sec 3.6 B-rows are VOID. (sec 3.5 A1 still stands.)")
    if not row0f_pass:
        log("STOPPING: ROW 0f failed, instrument blind, VOID.")

    # --- bootstrap: Delta(C1) = R(NOW,C1) - R(L08,C1), paired, frequency-clustered ---
    ref_freq_c1 = {k: v[1] for k, v in ref_c1.items()}
    member_sets_c1 = {leg: rec[(leg, "C1")]["hit_set"] for leg in LEGS}
    bs_c1 = BS.paired_cluster_bootstrap(ref_freq_c1, member_sets_c1)
    delta_c1 = BS.delta_summary(bs_c1["per_draw"], "NOW", "L08")
    log("Delta(C1) = R(NOW)-R(L08): mean=%.3f pp SE=%.3f pp CI95=[%.3f,%.3f] n_freq=%d" %
        (delta_c1["mean"], delta_c1["se"], delta_c1["ci95"][0], delta_c1["ci95"][1], bs_c1["n_distinct_freq"]))

    ref_freq_c2 = {k: v[1] for k, v in ref_c2.items()}
    member_sets_c2 = {leg: rec[(leg, "C2")]["hit_set"] for leg in LEGS}
    bs_c2 = BS.paired_cluster_bootstrap(ref_freq_c2, member_sets_c2)
    delta_c2 = BS.delta_summary(bs_c2["per_draw"], "NOW", "L08")
    log("Delta(C2) = R(NOW)-R(L08): mean=%.3f pp SE=%.3f pp CI95=[%.3f,%.3f] n_freq=%d" %
        (delta_c2["mean"], delta_c2["se"], delta_c2["ci95"][0], delta_c2["ci95"][1], bs_c2["n_distinct_freq"]))

    result["delta_c1"] = delta_c1
    result["delta_c2"] = delta_c2

    # --- ROW 0g: power ---
    row0g_pass = delta_c1["se"] <= ROW0G_SE_MAX
    log("ROW 0g: SE(Delta(C1))=%.3f pp (need <= %.2f) -> %s" %
        (delta_c1["se"], ROW0G_SE_MAX, "PASS" if row0g_pass else "underpowered -> B4"))
    result["row0g_pass"] = row0g_pass

    # --- Gate rows B1-B4 (first match wins) ---
    ci_lo, ci_hi = delta_c1["ci95"]
    c2_sign = delta_c2["mean"]
    if row0d_pass and row0f_pass and row0g_pass:
        if ci_lo >= BAR_D and c2_sign > 0:
            gate = "B1"
        elif ci_hi <= -BAR_D and c2_sign < 0:
            gate = "B3"
        elif ci_lo > -BAR_D and ci_hi < BAR_D:
            gate = "B2"
        else:
            gate = "B4"
    elif not row0d_pass or not row0f_pass:
        gate = "VOID"
    else:
        gate = "B4"  # row0g failed -> underpowered
    log(">>> GATE: %s <<<" % gate)
    result["gate"] = gate

    # --- A1: current-binary live figure (NOW leg via H1 R_wild code path on live C2 openwsfz) ---
    a1 = matcher.recovery(live_c2, ref_c2)
    log("\nA1 (current live figure, C2, NOW's live decodes vs REF A-only): R_wild=%.4f%% R_base=%.4f%% n_ref=%d" %
        (a1["R_wild"], a1["R_base"], a1["n_ref"]))
    result["A1"] = {"R_wild": a1["R_wild"], "R_base": a1["R_base"], "n_ref": a1["n_ref"]}

    # --- A2: R for every leg x corpus, plus R(NOW,C1,A∩B) beside 57.79% ---
    a2 = {"%s_%s" % (leg, cid): {"R_base": rec[(leg, cid)]["R_base"], "R_wild": rec[(leg, cid)]["R_wild"]}
          for leg in LEGS for cid in ("C1", "C2")}
    result["A2"] = a2
    for k, v in a2.items():
        log("A2 %s: R_base=%.4f%% R_wild=%.4f%%" % (k, v["R_base"], v["R_wild"]))

    # --- A3: R(NOW40,C) - R(NOW,C), both corpora, paired bootstrap ---
    a3_c1 = BS.delta_summary(bs_c1["per_draw"], "NOW40", "NOW")
    a3_c2 = BS.delta_summary(bs_c2["per_draw"], "NOW40", "NOW")
    log("A3 Delta(NOW40-NOW, C1): mean=%.3f SE=%.3f CI95=%s" % (a3_c1["mean"], a3_c1["se"], a3_c1["ci95"]))
    log("A3 Delta(NOW40-NOW, C2): mean=%.3f SE=%.3f CI95=%s" % (a3_c2["mean"], a3_c2["se"], a3_c2["ci95"]))
    result["A3"] = {"C1": a3_c1, "C2": a3_c2}
    if a3_c1["ci95"][1] < -0.5 or a3_c2["ci95"][1] < -0.5:
        log("A3 FLAG: CI_hi < -0.5pp on at least one corpus -- flag to the Architect the same day (spec 3.5).")

    # --- A4: recovery by reference SNR (2dB bins) and by frequency band, per leg/corpus, with per-bin Delta ---
    log("\nA4: recovery by reference SNR bin (L08 vs NOW), and by frequency band")
    a4 = {}
    for cid, ref in (("C1", ref_c1), ("C2", ref_c2)):
        snr_l08, totals_snr = per_bin_recovery(ref, rec[("L08", cid)]["hit_set"], snr_bin, "snr")
        snr_now, _ = per_bin_recovery(ref, rec[("NOW", cid)]["hit_set"], snr_bin, "snr")
        band_l08, totals_band = per_bin_recovery(ref, rec[("L08", cid)]["hit_set"], freq_band, "freq")
        band_now, _ = per_bin_recovery(ref, rec[("NOW", cid)]["hit_set"], freq_band, "freq")
        a4[cid] = {"by_snr_L08": snr_l08, "by_snr_NOW": snr_now, "n_by_snr": totals_snr,
                   "by_band_L08": band_l08, "by_band_NOW": band_now, "n_by_band": totals_band}
        log("  [%s] by freq band: L08=%s NOW=%s n=%s" % (cid, band_l08, band_now, totals_band))
    result["A4"] = a4

    # --- A5: Delta(C2) already computed above ---
    result["A5_delta_c2"] = delta_c2

    out_path_json = os.path.join(OUT_DIR, "..", "analysis.json")
    with open(out_path_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    log("\nWrote %s" % os.path.abspath(out_path_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
