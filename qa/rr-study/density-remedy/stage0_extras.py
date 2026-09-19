#!/usr/bin/env python
"""DENSITY-REMEDY Stage 0 -- DESCRIPTIVE EXTRAS. NOT PRE-REGISTERED, gate nothing, cannot move the verdict.

Written AFTER the pre-registered census (stage0_census.py, 77e129ee) had produced its verdict, to test how robust that verdict is.
Every figure here is labelled as post-hoc. Same data, same buckets, same loaders; no new decode except the ROW 0c replay repeated
solely to keep the per-pair SNR differences (which the pre-registered row reduced to one agreement fraction).

  A. victim recovery rate by neighbour bucket (hits / (hits + misses))                 [re-cut of the census counts]
  B. SENSITIVITY: shift OUR integer SNR by -1 / +1 dB and recompute the buckets, shares, reach and verdict
  C. ROW 0c disagreement structure: distribution of (replay SNR - live ALL.TXT SNR) over the paired decodes
  D. ambiguity, matcher's BROADER definition, among the decoded dominant neighbours
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage0_census as S0  # noqa: E402

OUT = os.path.join(HERE, "results", "stage0_extras.json")


def bucket_shift(snr, delta):
    return S0.bucket_of(int(snr) + delta)


def main():
    R = json.load(open(S0.RESULT_JSON))
    out = {"note": "DESCRIPTIVE, POST-HOC, NOT pre-registered. Gates nothing."}
    m, h = R["missed_exposed"]["counts"], R["reporting"]["hit_exposed"]["counts"]
    out["A_recovery_rate_by_bucket"] = {b: {"hits": h[b], "misses": m[b], "rate": h[b] / (h[b] + m[b])} for b in S0.BUCKETS}

    S0.log("re-loading REF / TEST (no census quantity is recomputed except via the stored per-victim rows) ...")
    ref_all = S0.analyse.load_ref_c2()
    by_cycle = S0.DL.build_by_cycle(ref_all)
    classes, _c, _b = S0.DL.deliverable1_gate(ref_all, by_cycle)
    test = S0.analyse.load_live_c2_openwsfz()
    rec = S0.matcher.recovery(test, ref_all)
    hit_set = rec["hit_set"]
    exposed = sorted(k for k, c in classes.items() if c == "EXPOSED")
    missed = [k for k in exposed if k not in hit_set]
    rows, cnt, amb = S0.census(missed, ref_all, by_cycle, rec, test)

    # B. sensitivity to +-1 dB error in our integer SNR (bucket boundaries are integers: RA <= -3, RB >= 5)
    sens = {}
    for delta in (-1, 0, 1):
        c = {b: 0 for b in S0.BUCKETS}
        for r in rows:
            if r["bucket"] == "AMBIGUOUS":
                continue
            c["N0" if r["ours_snr"] is None else bucket_shift(r["ours_snr"], delta)] += 1
        sh, d = S0.shares(c)
        rf, rfp = (sh["RA"] + sh["RM"]) * S0.C_PP, (sh["RB"] + sh["RM"]) * S0.C_PP
        sens[str(delta)] = {"counts": c, "shares": sh, "reach_floor_pp": rf, "reach_footprint_pp": rfp,
                            "floor_in": rf >= S0.REACH_BAR, "footprint_in": rfp >= S0.REACH_BAR}
    out["B_sensitivity_our_snr_shift_db"] = sens
    # how far would the shares have to move to flip a lever out? (margin to the bar, in share points)
    out["B_margin_to_bar"] = {"floor_share_needed": S0.REACH_BAR / S0.C_PP, "footprint_share_needed": S0.REACH_BAR / S0.C_PP}

    # D. broader ambiguity among decoded dominant neighbours: a single candidate shared by >= 2 refs
    cand_refs = collections.defaultdict(list)
    for k, cs in rec["gained"].items():
        for c in cs:
            cand_refs[(k[0], c)].append(k)
    shared = 0
    seen = set()
    for r in rows:
        nk = r["n"]["key"]
        if nk in seen or nk not in rec["gained"]:
            continue
        seen.add(nk)
        cs = rec["gained"][nk]
        if len(cs) == 1 and len(cand_refs[(nk[0], cs[0])]) >= 2:
            shared += 1
    out["D_broad_ambiguity_among_neighbours"] = {"n_neighbours_via_wildcard_single": sum(1 for r in rows if r["n"]["key"] in rec["gained"]),
                                                  "n_shared_candidate": shared, "n_missed": len(missed), "share_of_missed": shared / len(missed),
                                                  "matcher_n_ambiguous_whole_corpus": rec["n_ambiguous"],
                                                  "spec_predicate_ge2_candidates_whole_corpus": sum(1 for c in rec["gained"].values() if len(c) >= 2),
                                                  "n_gained_whole_corpus": len(rec["gained"])}

    # C. ROW 0c disagreement structure (same replay as the pre-registered row, keeping the per-pair differences)
    smp = json.load(open(S0.SAMPLE_JSON))["sample"]
    cyc, _ = S0.corpus.c2_cycles()
    paths = dict(cyc)
    tbt = {}
    for (ts, mm), (s, f) in test.items():
        tbt.setdefault(ts, []).append((mm, s, f))
    sh_ = S0.S1.Shim(S0.NEW_DLL, "NEW", has_probe=False)
    sh_.dll.ft8_set_decode_params(S0.REPLAY_PARAMS[0], S0.ctypes.c_float(S0.REPLAY_PARAMS[1]), S0.REPLAY_PARAMS[2])
    diffs, unmatched_live, extra_replay = collections.Counter(), 0, 0
    for ts in sorted(smp):
        pcm = S0.P23.normalise_rms(S0.P23.read_wav(paths[ts]), S0.P23.PROD_TARGET_RMS)
        rows_r, _pcl = S0.replay_decode(sh_, pcm)
        used = set()
        for (lm, ls, lf) in tbt.get(ts, []):
            cands = [(abs(rf - lf), rf, i) for i, (rf, rs, rm) in enumerate(rows_r) if abs(rf - lf) <= S0.MATCH_DF and S0.wildcard_match(lm, rm)]
            if not cands:
                unmatched_live += 1
                continue
            _d, _rf, i = min(cands)
            used.add(i)
            diffs[int(rows_r[i][1]) - int(ls)] += 1
        extra_replay += len(rows_r) - len(used)
    out["C_row0c_snr_difference_replay_minus_live"] = {"histogram": {str(k): v for k, v in sorted(diffs.items())},
                                                        "n_pairs": sum(diffs.values()), "n_live_unmatched": unmatched_live,
                                                        "n_replay_decodes_not_in_live": extra_replay}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=str)
    S0.log("wrote " + OUT)


if __name__ == "__main__":
    main()
