#!/usr/bin/env python3
"""PASSBAND-140 core measurement: section 3.1 definitions, 3.3 resolution,
3.5 descriptives, 3.6 gate.

REF is restricted to the decoded cycle set (spec section 1: "ts in the
cycles every leg decoded, so a cycle with no WAV is not a miss for either
leg"). Bands (Amendment 1, five terms): sub<=137, low 138-199, in 200-2959,
hi 2960-3034, beyond>=3035.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# APPEND, not insert(0, ...): this script's own directory (passband-140/) is
# already sys.path[0] and must stay first, or "import corpus" below resolves
# to live-gap-now's own corpus.py instead of this directory's -- the same
# module-name collision documented in corpus.py and decode_leg.py.
sys.path.append(os.path.join(_HERE, "..", "live-gap-now"))
sys.path.append(os.path.join(_HERE, "..", "..", "cycleframer-alignment-replay"))

import dll_pin  # noqa: E402
import corpus  # noqa: E402  (THIS directory's own corpus.py)
import matcher  # noqa: E402  (live-gap-now's own, reused verbatim -- no local name collision)
import bootstrap  # noqa: E402  (THIS directory's own bootstrap.py)
from h1_hash_token_contamination import load as load_all_txt  # noqa: E402

REPO_ROOT = dll_pin.REPO_ROOT
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "passband-140", "_out")

DIAL_PREFIX = "14.074"

C2_REF_PATH = os.path.join(
    REPO_ROOT, "artefacts", "20260908_live_run_1827-fp-floor-live-2",
    "wsjtx-1-ft991a", "ALL.TXT")
C2_LO, C2_HI = "260908_193645", "269999_999999"

C1P_REF_PATH = os.path.join(
    REPO_ROOT, "artefacts", "20260808_live_run_0016-8080", "wsjt-x", "ALL.TXT")

BANDS = [
    ("sub", lambda f: f <= 137),
    ("low", lambda f: 138 <= f <= 199),
    ("in", lambda f: 200 <= f <= 2959),
    ("hi", lambda f: 2960 <= f <= 3034),
    ("beyond", lambda f: f >= 3035),
]

BAR_G = 0.25
BAR_H = 0.25


def load_chained(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            ts = rec["ts"]
            for r in rec["results"]:
                out[(ts, r["message"])] = (r["snr"], r["freq_hz"])
    return out


def restricted_ref(all_ref: dict, decoded_ts: set) -> dict:
    return {k: v for k, v in all_ref.items() if k[0] in decoded_ts}


def band_of(freq_hz):
    for name, pred in BANDS:
        if pred(freq_hz):
            return name
    raise ValueError("freq_hz %s matches no band" % freq_hz)


def compute_corpus(corpus_id, ref_path, decoded_ts, b40_path, w40_path, ref_lo=None, ref_hi=None):
    print("=== %s ===" % corpus_id)
    if ref_lo is not None:
        all_ref = load_all_txt(ref_path, ref_lo, ref_hi, DIAL_PREFIX)
    else:
        # C1': window already matches the decode corpus; use a wide bound and
        # restrict to decoded_ts below (same discipline as C2, belt+braces).
        all_ref = load_all_txt(ref_path, "000000_000000", "999999_999999", DIAL_PREFIX)
    ref = restricted_ref(all_ref, decoded_ts)
    print("|REF| (restricted to decoded cycle set) = %d (raw file had %d in window)" %
          (len(ref), len(all_ref)))

    b40 = load_chained(b40_path)
    w40 = load_chained(w40_path)

    rec_b40 = matcher.recovery(b40, ref)
    rec_w40 = matcher.recovery(w40, ref)

    print("B40: R_base=%.4f R_wild=%.4f M=%.4f n_ambiguous=%d (%.4f%%)" %
          (rec_b40["R_base"], rec_b40["R_wild"], rec_b40["M"],
           rec_b40["n_ambiguous"], 100 * rec_b40["ambiguous_frac"]))
    print("W40: R_base=%.4f R_wild=%.4f M=%.4f n_ambiguous=%d (%.4f%%)" %
          (rec_w40["R_base"], rec_w40["R_wild"], rec_w40["M"],
           rec_w40["n_ambiguous"], 100 * rec_w40["ambiguous_frac"]))

    D = rec_w40["R_wild"] - rec_b40["R_wild"]
    print("D(%s) = %.4f pp" % (corpus_id, D))

    # Per-band D, additive identity check
    ref_band = {k: band_of(v[1]) for k, v in ref.items()}
    n_ref = len(ref)
    hit_b40 = rec_b40["hit_set"]
    hit_w40 = rec_w40["hit_set"]
    d_band = {}
    for name, _ in BANDS:
        band_keys = [k for k, b in ref_band.items() if b == name]
        s = sum((1 if k in hit_w40 else 0) - (1 if k in hit_b40 else 0) for k in band_keys)
        d_band[name] = 100.0 * s / n_ref if n_ref else float("nan")
        print("  D_%s(%s) = %.4f pp (%d REF rows in band)" % (name, corpus_id, d_band[name], len(band_keys)))

    d_sum = sum(d_band.values())
    print("  sum of D_bands = %.9f  (D = %.9f)  |diff| = %.2e" %
          (d_sum, D, abs(d_sum - D)))
    assert abs(d_sum - D) < 1e-6, "additive identity broken: %r vs %r" % (d_sum, D)

    return {
        "corpus_id": corpus_id,
        "ref": ref,
        "ref_band": ref_band,
        "n_ref": n_ref,
        "rec_b40": rec_b40,
        "rec_w40": rec_w40,
        "D": D,
        "d_band": d_band,
    }


def bootstrap_ci(result):
    ref = result["ref"]
    ref_band = result["ref_band"]
    hit_b40 = result["rec_b40"]["hit_set"]
    hit_w40 = result["rec_w40"]["hit_set"]

    ref_freq_cluster = {k: v[1] for k, v in ref.items()}
    ref_cycle_cluster = {k: k[0] for k in ref}

    member_sets = {"B40": hit_b40, "W40": hit_w40}

    bt_freq = bootstrap.paired_cluster_bootstrap(ref_freq_cluster, member_sets)
    bt_cyc = bootstrap.paired_cluster_bootstrap(ref_cycle_cluster, member_sets)

    d_freq = bootstrap.delta_summary(bt_freq["per_draw"], "W40", "B40")
    d_cyc = bootstrap.delta_summary(bt_cyc["per_draw"], "W40", "B40")

    ci_d = bootstrap.wider_ci(d_freq["ci95"], d_cyc["ci95"])

    print("D CI (freq clusters, n=%d): [%.4f, %.4f] SE=%.4f" %
          (bt_freq["n_distinct_clusters"], d_freq["ci95"][0], d_freq["ci95"][1], d_freq["se"]))
    print("D CI (cycle clusters, n=%d): [%.4f, %.4f] SE=%.4f" %
          (bt_cyc["n_distinct_clusters"], d_cyc["ci95"][0], d_cyc["ci95"][1], d_cyc["se"]))
    print("D CI (wider governs): [%.4f, %.4f]" % (ci_d[0], ci_d[1]))

    # D_in bootstrap: restrict member sets/hit to the "in" band only, same cluster mapping
    in_keys = {k for k, b in ref_band.items() if b == "in"}
    hit_b40_in = hit_b40 & in_keys
    hit_w40_in = hit_w40 & in_keys
    ref_freq_cluster_in = {k: v for k, v in ref_freq_cluster.items() if k in in_keys}
    ref_cycle_cluster_in = {k: v for k, v in ref_cycle_cluster.items() if k in in_keys}
    member_sets_in = {"B40": hit_b40_in, "W40": hit_w40_in}

    bt_freq_in = bootstrap.paired_cluster_bootstrap(ref_freq_cluster_in, member_sets_in)
    bt_cyc_in = bootstrap.paired_cluster_bootstrap(ref_cycle_cluster_in, member_sets_in)
    d_freq_in = bootstrap.delta_summary(bt_freq_in["per_draw"], "W40", "B40")
    d_cyc_in = bootstrap.delta_summary(bt_cyc_in["per_draw"], "W40", "B40")
    ci_d_in = bootstrap.wider_ci(d_freq_in["ci95"], d_cyc_in["ci95"])

    print("D_in CI (freq, n=%d): [%.4f, %.4f] SE=%.4f" %
          (bt_freq_in["n_distinct_clusters"], d_freq_in["ci95"][0], d_freq_in["ci95"][1], d_freq_in["se"]))
    print("D_in CI (cycle, n=%d): [%.4f, %.4f] SE=%.4f" %
          (bt_cyc_in["n_distinct_clusters"], d_cyc_in["ci95"][0], d_cyc_in["ci95"][1], d_cyc_in["se"]))
    print("D_in CI (wider governs): [%.4f, %.4f]" % (ci_d_in[0], ci_d_in[1]))

    return {
        "D_ci": ci_d, "D_se_freq": d_freq["se"], "D_se_cyc": d_cyc["se"],
        "D_in_ci": ci_d_in, "D_in_se_freq": d_freq_in["se"], "D_in_se_cyc": d_cyc_in["se"],
    }


def main():
    c2_ts, dup = corpus.c2_cycles()
    c2_ts = {ts for ts, _ in c2_ts}
    c1p_ts = {ts for ts, _ in corpus.c1_prime_cycles()}

    c2 = compute_corpus(
        "C2", C2_REF_PATH, c2_ts,
        os.path.join(OUT_DIR, "B40_C2_chained.jsonl"),
        os.path.join(OUT_DIR, "W40_C2_chained.jsonl"),
        ref_lo=C2_LO, ref_hi=C2_HI)

    c1p = compute_corpus(
        "C1P", C1P_REF_PATH, c1p_ts,
        os.path.join(OUT_DIR, "B40_C1P_chained.jsonl"),
        os.path.join(OUT_DIR, "W40_C1P_chained.jsonl"))

    print()
    ci = bootstrap_ci(c2)

    print()
    print("=== Gate (BAR_G=%.2f, BAR_H=%.2f -- PROVISIONAL, Q1 not yet confirmed by the Captain) ===" %
          (BAR_G, BAR_H))
    ci_lo_d, ci_hi_d = ci["D_ci"]
    ci_lo_d_in, ci_hi_d_in = ci["D_in_ci"]
    d_c1p_positive = c1p["D"] > 0

    print("CI_lo(D(C2)) = %.4f, CI_hi(D(C2)) = %.4f" % (ci_lo_d, ci_hi_d))
    print("CI_lo(D_in(C2)) = %.4f" % ci_lo_d_in)
    print("D(C1') = %.4f (point, >0 = %s)" % (c1p["D"], d_c1p_positive))

    if ci_lo_d >= BAR_G and ci_lo_d_in >= -BAR_H and d_c1p_positive:
        gate = "G1 -- ship-eligible"
    elif ci_lo_d >= BAR_G and ci_lo_d_in < -BAR_H and d_c1p_positive:
        gate = "G2 -- net gain, in-band cost"
    elif ci_hi_d < BAR_G:
        gate = "G3 -- no material gain"
    else:
        gate = "G4 -- unresolved"
    print("GATE:", gate)


if __name__ == "__main__":
    main()
