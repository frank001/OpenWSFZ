#!/usr/bin/env python
"""DENSITY-REMEDY Stage 0 -- live regime census (NO build): how much of the live ~4.30 pp near-neighbour cost can each
suppression lever (the ramp's FLOOR, the +-1-bin FOOTPRINT) reach?

================================================================================
PRE-REGISTRATION -- committed BEFORE any Stage 0 share is computed (HK-021: mechanical bars)
================================================================================
Spec   : qa/rr-study/2026-09-19-1228-architect-to-qa-spec-density-remedy-suppression.md Sec.3 + Sec.10
         (arch/density 2f6ba3e2). REACH_BAR = 0.5 pp RATIFIED and FROZEN (Sec.10.1): moving it after any share exists VOIDs Stage 0.
Go     : Sec.10 quotes the Captain: "Go for stage 1, 0.5 pp confirmed. 2. hold after stage 1 lands, ...". The Architect records that
         his "stage 1" is this spec's STAGE 0 (the census) and his "2" is the spec's Stage 1 (the build). QA reads it the CONSERVATIVE way
         (census only, no build, no Developer contact) and asks the Captain to confirm; the census is required either way, so the
         reading cannot cause harm.
Corpus : C2 (artefacts/20260908_live_run_1827-fp-floor-live-2/), live-gap-now corpus.c2_cycles() window (5,222 cycles), REF = WSJT-X FT991A
         via analyse.load_ref_c2() (91,046 rows), TEST = OpenWSFZ LIVE ALL.TXT via analyse.load_live_c2_openwsfz() (57,969 rows).
         Classes: density_live.classify() VERBATIM. C2 qualifiers travel with every number: binary 6b2e16a6 (shim 20260050), nhard 60,
         pre-PASSBAND-140. C = 4.30 pp (DENSITY-LIVE C2). Message text is never re-emitted (NFR-021): outputs are counts, rates, shares.

PER MISSED EXPOSED VICTIM v (v in EXPOSED, v NOT in recovery(test, ref)["hit_set"]):
  1. dominant neighbour n = among REF rows in v's cycle (FULL pool, v excluded) with |f_n - f_v| <= 18 and snr_n - snr_v >= 0, the one with the
     highest REF SNR; ties -> smaller |df|, then lower frequency. (EXPOSED guarantees one exists.)
  2. did we decode n?  n in hit_set.  our row: exact_matched -> test[n]; gained[n] with exactly ONE candidate -> that row; gained[n] with >=2
     candidates -> AMBIGUOUS (excluded from the share denominator, counted).
  3. applied factor f = 1 - clamp((snr_ours + 5)/20, 0, 1) on our ALL.TXT SNR (int). IMPLEMENTED AS INTEGER PREDICATES, asserted equal to
     the float formula: RA <=> snr_ours <= -3 ; RB <=> snr_ours >= 5 ; RM otherwise (-2..4).
  4. bucket, first match wins:  N0: n not decoded | RA: f >= 0.90 (floor) | RM: 0.50 < f < 0.90 (both) | RB: f <= 0.50 (footprint).
  s_X = n_X / (n_missed - n_ambiguous).

ROW 0 (any fires => STOP, report, NO re-cut)
  0a  reproduction: density_live's REF-only class table (its own hard gate) AND R_wild == 61.0856 (4 dp), n_EXPOSED == 5363, EXPOSED hits == 278.
  0b  AMBIGUOUS share = n_ambiguous / n_missed > 0.05.
  0c  the SNR in ALL.TXT is the ramp's input: the 50-cycle sample in results/stage0_0c_sample.json (FIXED and committed BEFORE any share; rule below),
      replayed on the Stage 1 DLL (SHA-256 50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7, shim 20260053) with
      ft8_set_decode_params(10, 0.10, 60) SET (read-back impossible: no getter) and PCM = p23_common.read_wav -> normalise_rms(PROD_TARGET_RMS
      0.20), the audited production-mirroring path. Each live decode is paired with the replay decode in the same cycle with wildcard_match
      (symmetric) and |df| <= 3 Hz, choosing the smallest |df| then the lower replay frequency. Fires when exact agreement of the INTEGER SNR
      (FT8Result.snr == live ALL.TXT SNR) < 0.90 OR when fewer than 200 live decodes pair (the row cannot be evaluated => cannot pass).
      The one KNOWN source of disagreement that is not a defect: live 20260050 vs replay 20260053 (the 0.90 bar allows for it).
  0c sample rule: eligible = C2 cycles with >= 8 REF rows AND >= 8 live TEST rows; numpy.random.default_rng(20260919).choice(eligible, 50,
      replace=False); sorted chronologically. Depends only on per-cycle row COUNTS, never on any bucket or share.

READING (mechanical, independent, C = 4.30 pp, REACH_BAR = 0.5 pp; predicate is the code below, verbatim from Sec.3.4)
  reach_floor = (s_RA + s_RM) * C ; reach_footprint = (s_RB + s_RM) * C ; floor_in / footprint_in = reach >= REACH_BAR
  neither in => "STOP: suppression route cannot reach REACH_BAR" ; else "floor", "footprint" or "floor+footprint".
  A lever that is OUT is removed from Stages 1-3 of the arm.

READING NOTE (QA, not a gate): Sec.3.4 calls the reach "a ceiling". s_X * C is a PROPORTIONAL ATTRIBUTION of the 4.30 pp, not a ceiling: recovering EVERY
  missed victim in bucket X would gain n_X / n_REF pp, which is larger (C counts only the excess over the matched-PL baseline). Both are REPORTED; only
  s_X * C gates, exactly as ratified. The predicate does fire either way (it depends on the shares), so it is not decorative.

REPORTING ONLY (gates nothing): (1) bucket shares by df band 0-6 / 7-12 / 13-18 Hz; (2) SNR-input check: median (ours - REF) SNR for decoded dominant
  neighbours vs decoded CLEAR-class rows, directly standardised over 1-dB REF-SNR cells (density_live.cell_index, MIN_CELL_N 20) to the neighbours' mix;
  (3) pass attribution on the 0c sample: share of decoded dominant neighbours the replay decodes in PASS 0 (a neighbour decoded only in pass 1 suppressed
  nothing before the victim's pass-1 search, so RA/RM/RB overstate the reach by that share); (4) the same buckets for the 278 HIT victims;
  (5) the full-recovery figure n_X / n_REF * 100 per bucket.

WHAT THIS CANNOT SEE: it measures the live census on C2 only (one band, one binary, pre-PASSBAND-140, nhard 60); a bucket assignment uses OUR INTEGER
  ALL.TXT SNR (rounded), so a factor near a bucket boundary carries +-0.025; it does not say a lever WORKS, only where it could act; it cannot separate
  "n suppressed too little" from "n suppressed and v still lost" within a bucket; the two known bench regimes came from ONE synthetic scene and message pair.
PREDICTIONS: the Architect's (Sec.8). QA writes none.
"""
import argparse
import ctypes
import hashlib
import json
import os
import statistics as st
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
QA_RR = os.path.join(REPO_ROOT, "qa", "rr-study")
for _p in (os.path.join(QA_RR, "live-gap-now"), os.path.join(QA_RR, "density-live"),
           os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"), os.path.join(QA_RR, "density-p1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import corpus  # noqa: E402  (live-gap-now, verbatim)
import analyse  # noqa: E402  (live-gap-now, verbatim)
import matcher  # noqa: E402  (live-gap-now, verbatim)
import density_live as DL  # noqa: E402  (classify(), gate, cell_index: verbatim)
import p23_common as P23  # noqa: E402  (read_wav, normalise_rms: the audited production-mirroring path)
import stage1_acceptance as S1  # noqa: E402  (Shim over the pinned Stage 1 DLL)
from h1_hash_token_contamination import wildcard_match  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "results")
SAMPLE_JSON = os.path.join(RESULTS_DIR, "stage0_0c_sample.json")
RESULT_JSON = os.path.join(RESULTS_DIR, "stage0_result.json")
ART_DIR = os.path.join(REPO_ROOT, "artefacts", "density-remedy-stage0")
NEW_DLL = os.path.join(S1.BIN_DIR, "libft8_NEW.dll")

C_PP = 4.30
REACH_BAR = 0.5                       # RATIFIED, FROZEN (spec Sec.10.1)
R_WILD_TARGET, N_EXPOSED_TARGET, HITS_TARGET = 61.0856, 5363, 278
AMBIG_BAR = 0.05
AGREE_BAR, MIN_PAIRS = 0.90, 200
SAMPLE_N, SAMPLE_SEED, SAMPLE_MIN_ROWS = 50, 20260919, 8
REPLAY_PARAMS = (10, 0.10, 60)
DF_NEIGHBOUR = 18
MATCH_DF = 3
BUCKETS = ("N0", "RA", "RM", "RB")


def log(m):
    print(m, flush=True)


# ── the factor and the buckets ─────────────────────────────────────────────────
def factor(snr_int):
    return 1.0 - max(0.0, min(1.0, (snr_int + 5) / 20.0))


def bucket_of(snr_ours):
    """Integer predicates (exact), asserted equal to the spec's float formula."""
    if snr_ours <= -3:
        b = "RA"
    elif snr_ours >= 5:
        b = "RB"
    else:
        b = "RM"
    f = factor(snr_ours)
    assert (b == "RA") == (f >= 0.90 - 1e-12) and (b == "RB") == (f <= 0.50 + 1e-12), (snr_ours, f, b)
    return b


def dominant_neighbour(k, ref_all, by_cycle):
    ts, msg = k
    v_snr, v_f = ref_all[k]
    best = None
    for (s, f, m) in by_cycle[ts]:
        if m == msg and s == v_snr and f == v_f:
            continue
        if abs(f - v_f) <= DF_NEIGHBOUR and (s - v_snr) >= 0:
            key = (s, -abs(f - v_f), -f)               # highest SNR; ties: smaller |df|, then lower frequency
            if best is None or key > best[0]:
                best = (key, (ts, m), s, f)
    return None if best is None else {"key": best[1], "snr": best[2], "f": best[3], "df": abs(best[3] - v_f)}


def our_row(nkey, rec, test):
    """Returns ('exact'|'single', (snr, f), live_key) or ('amb', None, None) or ('none', None, None)."""
    if nkey in rec["exact_matched"]:
        return "exact", test[nkey], nkey
    if nkey in rec["gained"]:
        c = rec["gained"][nkey]
        if len(c) == 1:
            lk = (nkey[0], c[0])
            return "single", test[lk], lk
        return "amb", None, None
    return "none", None, None


def df_band(df):
    d = int(round(df))
    return "0-6" if d <= 6 else "7-12" if d <= 12 else "13-18"


def census(victims, ref_all, by_cycle, rec, test):
    rows, cnt, amb = [], {b: 0 for b in BUCKETS}, 0
    for k in victims:
        n = dominant_neighbour(k, ref_all, by_cycle)
        assert n is not None, "EXPOSED victim without a dominant neighbour: %r" % (k,)
        kind, our, lk = our_row(n["key"], rec, test)
        if kind == "amb":
            amb += 1
            rows.append({"k": k, "n": n, "bucket": "AMBIGUOUS", "band": df_band(n["df"]), "ours_snr": None, "live_key": None})
            continue
        b = "N0" if kind == "none" else bucket_of(int(our[0]))
        cnt[b] += 1
        rows.append({"k": k, "n": n, "bucket": b, "band": df_band(n["df"]), "ours_snr": (None if our is None else int(our[0])), "live_key": lk})
    return rows, cnt, amb


def shares(cnt):
    d = sum(cnt.values())
    return {b: (cnt[b] / d if d else float("nan")) for b in BUCKETS}, d


# ── ROW 0c: replay ─────────────────────────────────────────────────────────────
def replay_decode(sh, pcm):
    buf = np.ascontiguousarray(pcm, dtype=np.float32)
    res = (S1.FT8Result * S1.MAX_RESULTS)()
    n = sh.dll.ft8_decode_all(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), S1.N_SAMPLES, res, S1.MAX_RESULTS)
    rows = [(res[i].freq_hz, res[i].snr, res[i].message.decode("ascii", "replace").strip()) for i in range(max(n, 0))]
    pc = (ctypes.c_int * 8)()
    k = sh.dll.ft8_get_last_pass_counts(pc, 8)
    return rows, [pc[i] for i in range(max(0, min(k, 8)))]


def row0c(sample_ts, cyc_paths, test_by_ts):
    sh = S1.Shim(NEW_DLL, "NEW", has_probe=False)               # SHA + shim version pinned inside
    sh.dll.ft8_set_decode_params(REPLAY_PARAMS[0], ctypes.c_float(REPLAY_PARAMS[1]), REPLAY_PARAMS[2])
    pairs, agree, pass_of = 0, 0, {}
    n_live = 0
    for ts in sorted(sample_ts):
        pcm = P23.normalise_rms(P23.read_wav(cyc_paths[ts]), P23.PROD_TARGET_RMS)
        rows, pcl = replay_decode(sh, pcm)
        n_pass0 = pcl[0] if pcl else 0
        for (lm, ls, lf) in test_by_ts.get(ts, []):
            n_live += 1
            cands = [(abs(rf - lf), rf, i) for i, (rf, rs, rm) in enumerate(rows) if abs(rf - lf) <= MATCH_DF and wildcard_match(lm, rm)]
            if not cands:
                continue
            _d, _rf, i = min(cands)
            pairs += 1
            agree += int(int(rows[i][1]) == int(ls))
            pass_of[(ts, lm)] = 0 if i < n_pass0 else 1
    return {"n_live_in_sample": n_live, "n_pairs": pairs, "n_agree": agree,
            "agreement": (agree / pairs if pairs else None), "dll_sha": sh.sha, "shim": sh.version,
            "params_set": list(REPLAY_PARAMS), "params_readback": "IMPOSSIBLE: no getter export"}, pass_of


# ── commands ───────────────────────────────────────────────────────────────────
def cmd_sample(a):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    cyc, _ = corpus.c2_cycles()
    ref_all, test = analyse.load_ref_c2(), analyse.load_live_c2_openwsfz()
    n_ref, n_tst = {}, {}
    for (ts, _m) in ref_all:
        n_ref[ts] = n_ref.get(ts, 0) + 1
    for (ts, _m) in test:
        n_tst[ts] = n_tst.get(ts, 0) + 1
    eligible = sorted(ts for ts, _p in cyc if n_ref.get(ts, 0) >= SAMPLE_MIN_ROWS and n_tst.get(ts, 0) >= SAMPLE_MIN_ROWS)
    rng = np.random.default_rng(SAMPLE_SEED)
    pick = sorted(eligible[i] for i in rng.choice(len(eligible), size=SAMPLE_N, replace=False))
    out = {"note": "ROW 0c sample, fixed BEFORE any Stage 0 share. Depends only on per-cycle row counts.",
           "seed": SAMPLE_SEED, "n_cycles_in_window": len(cyc), "min_rows_each": SAMPLE_MIN_ROWS, "n_eligible": len(eligible),
           "sample": pick, "sample_sha256": hashlib.sha256("\n".join(pick).encode()).hexdigest()}
    with open(SAMPLE_JSON, "w") as f:
        json.dump(out, f, indent=1)
    log("eligible %d of %d cycles; sample of %d fixed; sha256 %s" % (len(eligible), len(cyc), len(pick), out["sample_sha256"][:16]))


def cmd_run(a):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(ART_DIR, exist_ok=True)
    with open(SAMPLE_JSON) as f:
        smp = json.load(f)
    assert hashlib.sha256("\n".join(smp["sample"]).encode()).hexdigest() == smp["sample_sha256"], "0c sample file was altered"
    R = {"spec": "2f6ba3e2 Sec.3+Sec.10", "C_pp": C_PP, "REACH_BAR": REACH_BAR, "row0": {}}

    log("Loading REF (C2) ...")
    ref_all = analyse.load_ref_c2()
    by_cycle = DL.build_by_cycle(ref_all)
    classes, ref_counts, _bands = DL.deliverable1_gate(ref_all, by_cycle)      # raises SystemExit on any class-table mismatch
    log("Loading TEST (C2 live ALL.TXT) ...")
    test = analyse.load_live_c2_openwsfz()
    rec = matcher.recovery(test, ref_all)
    hit_set = rec["hit_set"]
    exposed = sorted(k for k, c in classes.items() if c == "EXPOSED")
    e_hits = sum(1 for k in exposed if k in hit_set)
    R["row0"]["0a"] = bool(round(rec["R_wild"], 4) == R_WILD_TARGET and len(exposed) == N_EXPOSED_TARGET and e_hits == HITS_TARGET)
    R["row0_detail"] = {"R_wild": rec["R_wild"], "n_exposed": len(exposed), "exposed_hits": e_hits, "n_ref": rec["n_ref"]}

    missed = [k for k in exposed if k not in hit_set]
    hits = [k for k in exposed if k in hit_set]
    if a.smoke:      # PLUMBING ONLY: 40/10 victims, 3 cycles OUTSIDE the real 0c sample; prints NO number (see end of function)
        missed, hits = missed[:40], hits[:10]
    rows_m, cnt_m, amb_m = census(missed, ref_all, by_cycle, rec, test)
    rows_h, cnt_h, amb_h = census(hits, ref_all, by_cycle, rec, test)
    amb_share = amb_m / len(missed) if missed else 0.0
    R["row0"]["0b"] = bool(amb_share <= AMBIG_BAR)
    R["row0_detail"].update({"n_missed": len(missed), "n_ambiguous": amb_m, "ambiguous_share": amb_share})

    test_by_ts = {}
    for (ts, m), (s, f) in test.items():
        test_by_ts.setdefault(ts, []).append((m, s, f))
    cyc, _ = corpus.c2_cycles()
    cyc_paths = dict(cyc)
    sample_ts = smp["sample"]
    if a.smoke:
        sample_ts = [ts for ts, _p in cyc if ts not in set(smp["sample"]) and len(test_by_ts.get(ts, [])) >= SAMPLE_MIN_ROWS][:3]
    c0, pass_of = row0c(sample_ts, cyc_paths, test_by_ts)
    R["row0"]["0c"] = bool(c0["n_pairs"] >= MIN_PAIRS and c0["agreement"] is not None and c0["agreement"] >= AGREE_BAR)
    R["row0c_detail"] = c0

    sh_m, d_m = shares(cnt_m)
    R["missed_exposed"] = {"counts": cnt_m, "n_denominator": d_m, "shares": sh_m, "n_missed": len(missed), "n_ambiguous": amb_m}
    reach_floor = (sh_m["RA"] + sh_m["RM"]) * C_PP
    reach_footprint = (sh_m["RB"] + sh_m["RM"]) * C_PP
    floor_in, footprint_in = reach_floor >= REACH_BAR, reach_footprint >= REACH_BAR
    if not all(R["row0"].values()):
        R["verdict"] = "ROW 0 STOP: " + ",".join(x for x, v in R["row0"].items() if not v)
    elif not floor_in and not footprint_in:
        R["verdict"] = "STOP: suppression route cannot reach REACH_BAR"
    else:
        R["verdict"] = ("floor" if floor_in else "") + ("+footprint" if footprint_in else "")
        if R["verdict"].startswith("+"):
            R["verdict"] = R["verdict"][1:]
    R["reach"] = {"reach_floor_pp": reach_floor, "reach_footprint_pp": reach_footprint, "floor_in": bool(floor_in), "footprint_in": bool(footprint_in)}

    # ---- reporting only ----
    n_ref = rec["n_ref"]
    rep = {"full_recovery_pp_of_n_ref": {b: 100.0 * cnt_m[b] / n_ref for b in BUCKETS},
           "hit_exposed": {"counts": cnt_h, "n_ambiguous": amb_h, "shares": shares(cnt_h)[0], "n_denominator": shares(cnt_h)[1]}}
    bands = {}
    for band in ("0-6", "7-12", "13-18"):
        c = {b: 0 for b in BUCKETS}
        for r in rows_m:
            if r["bucket"] != "AMBIGUOUS" and r["band"] == band:
                c[r["bucket"]] += 1
        s, d = shares(c)
        bands[band] = {"counts": c, "n": d, "shares": s}
    rep["by_df_band"] = bands
    # SNR-input check (standardised over 1-dB REF-SNR cells)
    def diffs(keys):
        out = {}
        for (rk, live_k) in keys:
            if live_k is None:
                continue
            ci = DL.cell_index(ref_all[rk][0])
            out.setdefault(ci, []).append(int(test[live_k][0]) - int(ref_all[rk][0]))
        return out
    nb_seen, nb_keys = set(), []
    for r in rows_m + rows_h:
        if r["bucket"] not in ("N0", "AMBIGUOUS") and r["live_key"] is not None and r["n"]["key"] not in nb_seen:
            nb_seen.add(r["n"]["key"]); nb_keys.append((r["n"]["key"], r["live_key"]))
    clear_keys = []
    for k, c in classes.items():
        if c == "CLEAR" and k in hit_set:
            kind, our, lk = our_row(k, rec, test)
            if kind in ("exact", "single"):
                clear_keys.append((k, lk))
    dn, dc = diffs(nb_keys), diffs(clear_keys)
    ws, num, tot = [], 0.0, 0
    for ci, v in dn.items():
        if len(v) >= DL.MIN_CELL_N and len(dc.get(ci, [])) >= DL.MIN_CELL_N:
            num += len(v) * (st.median(v) - st.median(dc[ci])); tot += len(v)
    rep["snr_input_check"] = {"n_neighbours": len(nb_keys), "n_clear": len(clear_keys),
                              "median_ours_minus_ref_neighbours": (st.median([x for v in dn.values() for x in v]) if dn else None),
                              "median_ours_minus_ref_clear": (st.median([x for v in dc.values() for x in v]) if dc else None),
                              "standardised_diff_neighbour_minus_clear": (num / tot if tot else None), "n_standardised": tot}
    in_sample = [(r["n"]["key"], r["live_key"]) for r in rows_m if r["bucket"] in ("RA", "RM", "RB") and r["live_key"] in pass_of]
    seen_p, p0 = set(), 0
    for nk, lk in in_sample:
        if lk in seen_p:
            continue
        seen_p.add(lk); p0 += int(pass_of[lk] == 0)
    rep["pass_attribution_on_0c_sample"] = {"n_decoded_dominant_neighbours_paired": len(seen_p), "n_pass0": p0,
                                             "share_pass0": (p0 / len(seen_p) if seen_p else None)}
    R["reporting"] = rep
    if a.smoke:
        needed = {"row0", "row0_detail", "row0c_detail", "missed_exposed", "reach", "verdict", "reporting"}
        assert needed <= set(R), "smoke: missing keys"
        for band in ("0-6", "7-12", "13-18"):
            assert band in R["reporting"]["by_df_band"]
        log("SMOKE: plumbing OK (%d victims, %d hit-victims, %d smoke cycles). Nothing printed, nothing written." % (len(missed), len(hits), len(sample_ts)))
        return
    with open(RESULT_JSON, "w") as f:
        json.dump(R, f, indent=1, sort_keys=True, default=str)
    # per-victim rows (ts, bucket, band, our int SNR; NO message text) to the gitignored artefacts dir
    with open(os.path.join(ART_DIR, "victims_missed.csv"), "w", newline="\n") as f:
        f.write("ts,bucket,band,ours_snr\n")
        for r in rows_m:
            f.write("%s,%s,%s,%s\n" % (r["k"][0], r["bucket"], r["band"], "" if r["ours_snr"] is None else r["ours_snr"]))
    log(json.dumps({k: R[k] for k in ("row0", "row0_detail", "row0c_detail", "missed_exposed", "reach", "verdict")}, indent=1, sort_keys=True, default=str))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample").set_defaults(fn=cmd_sample)
    r = sub.add_parser("run"); r.add_argument("--smoke", action="store_true"); r.set_defaults(fn=cmd_run)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
