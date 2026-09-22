#!/usr/bin/env python
"""LIVE-GAP-MAP harness  --  PRE-REGISTERED (commit this file BEFORE any C3 datum is read).

Spec : qa/rr-study/2026-09-21-1555-architect-to-qa-spec-live-gap-map-24h-20m.md (arch/live-gap-map), Amendment 1 (build pinned by DLL SHA) and
       Amendment 2 (ROW 0e' replaces ROW 0e; 0c/0a record extras; D4 over cycles with >= 1 REF row), Captain's Q1 = YES (D7 runs, descriptive, this arm only).
Usage: lgm_harness.py --corpus <C3 dir>                 the real analysis (the supervisor runs this after teardown)
       lgm_harness.py --selftest-c2 [--out F] [--draws N]   the SAME code path on C2 as if it were C3 (proves the pipeline against known numbers; NOT a result)

DEFINITIONS (predicates as code, HK-021(r)):
  R3   = matcher.recovery(live_openwsfz, REF) over the included cycles -> R_wild, R_base, n_ref.       miss = a REF row not recovered under R_wild (exact U wildcard).
  H10  = 100 * |{miss : REF snr >= -10}| / n_ref                     (pp).  CI = frequency-clustered bootstrap over REF's distinct freq_hz, N_BOOT=2000, seed=20260921, 2.5/97.5 pct.
  Included cycles = cycles with an archived OpenWSFZ WAV whose start is inside the window and dial == 14.074 (as C2).  REF rows and live rows are restricted to them.
ROW 0e' (Amendment 2, all three must hold else every M-row is VOID):
  (i)   archived cycles / wall-clock cycles in the window >= 0.99   (plus captureActive at arm, read from row0.json)
  (ii)  among included cycles with >= 5 REF rows, share with >= 1 OpenWSFZ live decode >= 0.99
  (iii) in EVERY UTC hour where OpenWSFZ's own live log has >= 240 decodes: share of that hour's cycles with >= 1 REF row within +-1 cycle >= 0.99
ROW 0f  the pipeline, pointed at C2, returns n_ref 91,046, R_wild 61.09 (2 dp), H10 17.96 (2 dp), 35,430 misses, 16,355 strong, and E4 0.2's eight-band REF-row counts.  Else STOP.
ROW 0g  n_ref(C3) >= 40,000  else M4 (underpowered, not VOID).
GATE ROWS (first match wins): VOID (0e' fails) ; M4 (0g fails) ; M1 CI_lo(H10) >= 10.0 ; M2 CI_hi(H10) < 5.0 ; M3 otherwise.
NFR-021: this file and its output carry COUNTS, rates, frequencies and SNRs only. No message text, no callsign.
"""
import argparse, collections, csv, datetime, hashlib, json, os, sys, time

REPO = os.environ.get("LGM_REPO", r"D:\Projects\claude\OpenWSFZ\worktrees\qa")
for p in ("qa/rr-study/live-gap-now", "qa/rr-study/density-live", "qa/cycleframer-alignment-replay"):
    sys.path.insert(0, os.path.join(REPO, *p.split("/")))
import numpy as np  # noqa: E402
import corpus as CORPUS  # noqa: E402  (C2 paths)
import matcher  # noqa: E402
import analyse as AN  # noqa: E402  (C2 loaders)
import density_live as DL  # noqa: E402  (D7 classifier, UNCHANGED)
import p23_common  # noqa: E402  (cluster_bootstrap)

N_BOOT, SEED = 2000, 20260921
BAR_M1, BAR_M2, POWER_MIN = 10.0, 5.0, 40000
SNR_STRONG = -10
E4_BANDS = [("<= -21", -10**6, -21), ("-20..-16", -20, -16), ("-15..-11", -15, -11), ("-10..-6", -10, -6), ("-5..-1", -5, -1), ("0..+4", 0, 4), ("+5..+9", 5, 9), (">= +10", 10, 10**6)]
C2_EXPECT = {"n_ref": 91046, "R_wild_2dp": 61.09, "H10_2dp": 17.96, "misses": 35430, "strong_misses": 16355,
             "band_rows": [6600, 10136, 14071, 15110, 13777, 11351, 8113, 11888]}
QUALIFIERS = ("binary libft8.dll SHA-256 38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba / shim 20260054 / decoding_improvement fa8a56ae or its docs-only descendant 84cac119, "
              "nhard 40, 20m (14.074), REF = WSJT-X FT991A alone (NDepth 3), one radio and one audio stream")

# Amendment 3 (arch/live-gap-map c1c59c65, Captain's ruling 2026-09-22T17:30Z): C3 is not voided; the
# 23:00-00:15Z interference episode is cut and the rows are read on the rest. Bounds are QA's report
# §4 full-run scan (episode starts in the 23:00 bin, tapers to zero by 00:10-00:15Z); the cut takes the
# WHOLE failing hour, not just the 9 failing cycles. Pre-registered as code here -- do not hand-filter.
AMD3_EXCLUDE = (datetime.datetime(2026, 9, 21, 23, 0, 0, tzinfo=datetime.timezone.utc),
                 datetime.datetime(2026, 9, 22, 0, 15, 0, tzinfo=datetime.timezone.utc))


def _in_amd3_window(cycle_ts):
    t = datetime.datetime.strptime(cycle_ts[:13], "%y%m%d_%H%M%S").replace(tzinfo=datetime.timezone.utc)
    return AMD3_EXCLUDE[0] <= t < AMD3_EXCLUDE[1]


def cyc_index(ts):
    return int(datetime.datetime.strptime(ts[:13], "%y%m%d_%H%M%S").replace(tzinfo=datetime.timezone.utc).timestamp()) // 15


def hour_key(i):
    return datetime.datetime.fromtimestamp(i * 15, datetime.timezone.utc).strftime("%Y%m%d %H")


def band_of(snr):
    for name, lo, hi in E4_BANDS:
        if lo <= snr <= hi:
            return name
    return "?"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ------------------------------------------------------------------ inputs
def load_c2():
    ref = AN.load_ref_c2(); live = AN.load_live_c2_openwsfz()
    cycles, _ = CORPUS.c2_cycles()
    W = sorted(ts for ts, _ in cycles)
    idx = [cyc_index(t) for t in W]
    return {"ref": ref, "live": live, "cycles": W, "wall_cycles": idx[-1] - idx[0] + 1, "row0": None, "window": {"start": W[0], "end": W[-1]}, "label": "C2 (SELFTEST, not a result)"}


def load_c3(corpus_dir, cut_amendment3=False):
    st = json.load(open(os.path.join(corpus_dir, "state.json"), encoding="utf-8"))
    ws = datetime.datetime.strptime(st["window_start"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    we = datetime.datetime.strptime(st["window_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    W_all = []
    with open(os.path.join(corpus_dir, "cycle-audio", "cycle-archive.csv"), encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            t = datetime.datetime.strptime(row["cycle_start_utc"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            if ws <= t < we and row["dial_mhz"] == "14.074" and row["filename"].endswith(".wav") and not row["filename"].endswith("_2.wav"):
                W_all.append(row["filename"][:-4])
    W_all = sorted(set(W_all))
    removed = [w for w in W_all if _in_amd3_window(w)] if cut_amendment3 else []
    removed_set = set(removed)
    W = [w for w in W_all if w not in removed_set]
    S = set(W)
    lo, hi = min(W_all), max(W_all)
    ref = matcher.load_all(os.path.join(corpus_dir, "wsjtx-1-ft991a", "ALL.TXT"), lo, hi)
    live = matcher.load_all(os.path.join(corpus_dir, "openwsfz", "ALL.TXT"), lo, hi)
    removed_ref_n = sum(1 for k in ref if k[0] in removed_set)
    ref = {k: v for k, v in ref.items() if k[0] in S}
    live = {k: v for k, v in live.items() if k[0] in S}
    row0 = json.load(open(os.path.join(corpus_dir, "row0.json"), encoding="utf-8"))
    # Amendment 3: a removed cycle counts on neither side (same convention as the 19:05:00Z supervisor
    # swap) -- both the archived-cycle numerator and the wall-clock denominator drop the cut interval.
    wall_cycles = int(round((we - ws).total_seconds() / 15)) - len(removed)
    return {"ref": ref, "live": live, "cycles": W, "wall_cycles": wall_cycles, "row0": row0,
            "window": {"start": st["window_start"], "end": st["window_end"]}, "label": os.path.basename(corpus_dir),
            "cut_amendment3": cut_amendment3, "removed_cycles": len(removed), "removed_ref_n": removed_ref_n,
            "amd3_exclude_window_utc": [AMD3_EXCLUDE[0].strftime("%Y-%m-%dT%H:%M:%SZ"), AMD3_EXCLUDE[1].strftime("%Y-%m-%dT%H:%M:%SZ")]}


# ------------------------------------------------------------------ measures
def core(ref, live):
    rec = matcher.recovery(live, ref)
    hit = set(rec["exact_matched"]) | set(rec["gained"])
    miss = [k for k in ref if k not in hit]
    strong = set(k for k in miss if ref[k][0] >= SNR_STRONG)
    n = len(ref)
    return rec, hit, miss, strong, n


def row0f():
    d = load_c2()
    rec, hit, miss, strong, n = core(d["ref"], d["live"])
    H10 = 100.0 * len(strong) / n
    rows = collections.Counter(band_of(v[0]) for v in d["ref"].values())
    band_rows = [rows[b[0]] for b in E4_BANDS]
    got = {"n_ref": n, "R_wild_2dp": round(rec["R_wild"], 2), "H10_2dp": round(H10, 2), "misses": len(miss), "strong_misses": len(strong), "band_rows": band_rows}
    return {"expected": C2_EXPECT, "got": got, "pass": got == C2_EXPECT, "R_wild": rec["R_wild"], "H10": H10}


def row0e_prime(d, hit):
    ref, live, W = d["ref"], d["live"], d["cycles"]
    ref_c = collections.Counter(cyc_index(k[0]) for k in ref)
    ows_c = collections.Counter(cyc_index(k[0]) for k in live)
    idx = [cyc_index(t) for t in W]
    i_share = len(W) / float(d["wall_cycles"])
    rich = [i for i in idx if ref_c.get(i, 0) >= 5]
    ii_share = (sum(1 for i in rich if ows_c.get(i, 0) >= 1) / float(len(rich))) if rich else float("nan")
    byh = collections.defaultdict(list)
    for i in idx:
        byh[hour_key(i)].append(i)
    hours = {}
    for h, cs in byh.items():
        if sum(ows_c.get(i, 0) for i in cs) >= 240:
            ok = sum(1 for i in cs if any(ref_c.get(j, 0) for j in (i - 1, i, i + 1)))
            hours[h] = ok / float(len(cs))
    iii_min = min(hours.values()) if hours else float("nan")
    cap = None if d["row0"] is None else bool(d["row0"]["0c"].get("captureActive"))
    passed = {"i": bool(i_share >= 0.99 and (cap is None or cap)), "ii": bool(ii_share >= 0.99), "iii": bool(hours and iii_min >= 0.99)}
    unchecked_rows = sum(1 for k in ref if hour_key(cyc_index(k[0])) not in hours)
    return {"i_archive_share": i_share, "i_captureActive_at_arm": cap, "ii_cycles_with_ge5_REF": len(rich), "ii_share_with_ge1_decode": ii_share,
            "iii_checked_hours": len(hours), "iii_worst_hour_share": iii_min, "iii_REF_rows_in_unchecked_hours": unchecked_rows, "pass": passed, "all_pass": all(passed.values())}


def descriptives(d, hit, miss, strong, rec):
    ref, live = d["ref"], d["live"]
    n = len(ref)
    out = {}
    # D2 eight-band table, E4 0.2 columns
    tab = []
    for name, lo, hi in E4_BANDS:
        ks = [k for k, v in ref.items() if lo <= v[0] <= hi]
        h = sum(1 for k in ks if k in hit)
        tab.append({"band": name, "ref_rows": len(ks), "R_wild": (100.0 * h / len(ks)) if ks else None, "misses": len(ks) - h, "share_of_all_misses": (100.0 * (len(ks) - h) / len(miss)) if miss else None})
    out["D2_snr_bands"] = tab
    # D3 frequency bands
    def fb(f):
        return "<200" if f < 200 else ("200-3000" if f <= 3000 else ">3000")
    fr = collections.defaultdict(lambda: [0, 0])
    for k, v in ref.items():
        b = fb(v[1]); fr[b][0] += 1; fr[b][1] += (k in hit)
    out["D3_freq_bands_Hz"] = {b: {"ref_rows": r, "R_wild": 100.0 * h / r if r else None, "misses": r - h} for b, (r, h) in sorted(fr.items())}
    # D4 cycle load: quintiles fixed on C3's own REF counts, over cycles with >= 1 REF row (Amendment 2)
    per = collections.Counter(k[0] for k in ref)
    counts = sorted(per.values())
    edges = [float(np.quantile(counts, q)) for q in (0.2, 0.4, 0.6, 0.8)] if counts else []
    def q_of(c):
        return int(np.searchsorted(edges, c, side="right")) + 1
    qa = collections.defaultdict(lambda: [0, 0, 0])
    for k in ref:
        q = q_of(per[k[0]]); qa[q][0] += 1; qa[q][1] += (k in hit); qa[q][2] += 1 if k in strong else 0
    out["D4_cycle_load_quintiles"] = {"edges_REF_rows_per_cycle": edges, "note": "quintiles over cycles with >=1 REF row; this is a cycle COUNT axis (X1), not spectral locality",
                                      "by_quintile": {str(q): {"ref_rows": r, "R_wild": 100.0 * h / r, "strong_misses_pp_of_n_ref": 100.0 * s / n} for q, (r, h, s) in sorted(qa.items())}}
    # D5 UTC hour
    hh = collections.defaultdict(lambda: [0, 0, 0, set()])
    for k in ref:
        h = hour_key(cyc_index(k[0])); hh[h][0] += 1; hh[h][1] += (k in hit); hh[h][2] += (k in strong)
    out["D5_utc_hour"] = {h: {"ref_rows": r, "R_wild": 100.0 * hi_ / r, "strong_misses": s} for h, (r, hi_, s, _) in sorted(hh.items())}
    # D6 what we decoded that WSJT-X did not: COUNTS only, "uncorroborated, not false"
    ref_by_ts = collections.defaultdict(list)
    for (ts, m) in ref:
        ref_by_ts[ts].append(m)
    unc = 0
    for (ts, m) in live:
        if (ts, m) in ref:
            continue
        if not any(matcher.wildcard_match(rm, m) for rm in ref_by_ts.get(ts, [])):
            unc += 1
    out["D6_uncorroborated_not_false"] = {"our_live_decodes": len(live), "uncorroborated_by_REF": unc, "note": "counts only; uncorroborated is NOT false (REF is one decoder)"}
    # D7 (Captain's Q1 YES, this arm only): H10 split EXPOSED / not, DENSITY-LIVE classifier UNCHANGED, TEST = this corpus's live log; descriptive, gates nothing
    by_cycle = DL.build_by_cycle(ref)
    classes = DL.classify_population(ref, by_cycle)
    ex_pop = [k for k, c in classes.items() if c == "EXPOSED"]
    ex_miss = sum(1 for k in ex_pop if k in strong)
    out["D7_H10_by_exposure"] = {"H10_pp": 100.0 * len(strong) / n, "H10_EXPOSED_pp": 100.0 * ex_miss / n, "H10_not_EXPOSED_pp": 100.0 * (len(strong) - ex_miss) / n,
                                 "population_ge_minus10": len(classes), "EXPOSED_rows": len(ex_pop), "EXPOSED_miss_rate_pct": 100.0 * ex_miss / len(ex_pop) if ex_pop else None,
                                 "not_EXPOSED_miss_rate_pct": 100.0 * (len(strong) - ex_miss) / (len(classes) - len(ex_pop)) if len(classes) > len(ex_pop) else None,
                                 "status": "descriptive; gates nothing; licenses no further live stratification; TEST = this corpus's live log"}
    return out


def analyse(d, n_boot):
    ref = d["ref"]
    rec, hit, miss, strong, n = core(ref, d["live"])
    H10 = 100.0 * len(strong) / n
    ref_freq = {k: v[1] for k, v in ref.items()}
    t0 = time.time()
    bs = p23_common.cluster_bootstrap(ref_freq, {"R_wild": hit, "H10": strong}, n_draws=n_boot, seed=SEED)
    e = row0e_prime(d, hit)
    g_ok = n >= POWER_MIN
    lo, hi = bs["H10"]["ci95"]
    # the bar-only verdict, ignoring 0e'/0g -- used for Amendment 3 §3.9 item 3 (sensitivity: does the
    # cut decide the M-row, or would the full corpus have landed on the same one had 0e' passed?)
    bars_only_row = ("M1" if lo >= BAR_M1 else ("M2" if hi < BAR_M2 else "M3"))
    if not e["all_pass"]:
        verdict = "VOID"
    elif not g_ok:
        verdict = "M4"
    elif lo >= BAR_M1:
        verdict = "M1"
    elif hi < BAR_M2:
        verdict = "M2"
    else:
        verdict = "M3"
    D1 = {"R_wild": rec["R_wild"], "R_base": rec["R_base"], "n_ref": n, "misses": len(miss), "strong_misses": len(strong), "H10": H10, "H10_ci95": [lo, hi], "R_wild_ci95": bs["R_wild"]["ci95"],
          "bootstrap": {"n_draws": bs["H10"]["n_draws"], "n_distinct_freq": bs["H10"]["n_distinct_freq"], "seed": SEED, "seconds": round(time.time() - t0, 1)},
          "window": d["window"], "included_cycles": len(d["cycles"]), "qualifiers": QUALIFIERS,
          "never": "never compared with A1 (61.09%) as a build effect; C3-C2 differ by 13 days of propagation, density and band conditions"}
    res = {"label": d["label"], "harness_sha256": sha256_file(os.path.abspath(__file__)), "row0_supervisor": d["row0"], "ROW_0e_prime": e, "ROW_0g": {"n_ref": n, "bar": POWER_MIN, "pass": g_ok},
           "verdict_row": verdict, "verdict_meaning": {"VOID": "0e' failed: all gate rows void, report the gaps", "M4": "underpowered: report everything, route nothing", "M1": "strong-miss pool is still large: the next target",
                                                       "M2": "pool has largely closed: the question is the Captain's", "M3": "between the bars: report, route nothing on it alone"}[verdict],
           "bars": {"M1_CI_lo_ge": BAR_M1, "M2_CI_hi_lt": BAR_M2, "C2_baseline_H10": 17.96},
           "bars_only_row_ignoring_0e_prime_and_0g": bars_only_row,
           "amendment3": {"cut_applied": d.get("cut_amendment3", False), "removed_cycles": d.get("removed_cycles", 0),
                          "removed_ref_n": d.get("removed_ref_n", 0), "exclude_window_utc": d.get("amd3_exclude_window_utc")},
           "D1": D1}
    res.update(descriptives(d, hit, miss, strong, rec))
    res["prediction_inputs_Architect"] = {"L3_M1_fires": verdict == "M1", "L4_M2_fires": verdict == "M2", "L5_R_wild_in_[57,65]": bool(57.0 <= rec["R_wild"] <= 65.0),
                                          "note": "scored by the Architect at ruling time; L1 is scored on ROW_0f below"}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus"); ap.add_argument("--selftest-c2", action="store_true"); ap.add_argument("--out"); ap.add_argument("--draws", type=int, default=None)
    ap.add_argument("--amendment3-cut", action="store_true", help="apply spec Amendment 3 (arch/live-gap-map c1c59c65): cut the 23:00-00:15Z interference episode, "
                                                                    "then also run the full (uncut) corpus in the same invocation and attach it as amendment3_sensitivity_full_corpus (§3.9 item 3)")
    a = ap.parse_args()
    f = row0f()
    print("ROW 0f pass=%s got=%s" % (f["pass"], json.dumps(f["got"])), flush=True)
    if a.selftest_c2:
        out = a.out or os.path.join(os.environ.get("TEMP", "."), "lgm_selftest_c2.json")
        res = analyse(load_c2(), a.draws or 200)
        res["SELFTEST"] = "run on C2 with the C3 code path; NOT a result, never cite"
    else:
        if not a.corpus:
            sys.exit("need --corpus or --selftest-c2")
        out = a.out or os.path.join(a.corpus, "results", ("lgm_result_amendment3.json" if a.amendment3_cut else "lgm_result.json"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if not f["pass"]:
            res = {"verdict_row": "STOP_0f", "ROW_0f": f, "note": "the matcher does not reproduce C2's baseline: the metric is not the one A1 was computed with; nothing else is reported"}
        else:
            res = analyse(load_c3(a.corpus, cut_amendment3=a.amendment3_cut), a.draws or N_BOOT)
            if a.amendment3_cut:
                sens = analyse(load_c3(a.corpus, cut_amendment3=False), a.draws or N_BOOT)
                res["amendment3_sensitivity_full_corpus"] = {
                    "note": "full (uncut) C3, same code path, same seed, run fresh in this invocation -- spec §3.9 item 3: does the cut decide the M-row?",
                    "H10_ci95": sens["D1"]["H10_ci95"], "R_wild": sens["D1"]["R_wild"], "n_ref": sens["D1"]["n_ref"],
                    "bars_only_row_ignoring_0e_prime_and_0g": sens["bars_only_row_ignoring_0e_prime_and_0g"],
                    "same_M_row_as_cut": sens["bars_only_row_ignoring_0e_prime_and_0g"] == res["bars_only_row_ignoring_0e_prime_and_0g"]}
    res["ROW_0f"] = f
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print("wrote", out, "| verdict row:", res.get("verdict_row"), flush=True)
    sys.exit(0 if f["pass"] else 2)


if __name__ == "__main__":
    main()
