#!/usr/bin/env python
"""DT-MISS -- counts-only REF-DT miss-rate split on C3 (Amendment 3 cut).  PRE-REGISTERED.

Spec: qa/rr-study/2026-09-22-1754-architect-to-qa-spec-dt-miss-rate.md (arch/live-gap-map, commit
      1d927f00). Captain-authorised follow-up to LIVE-GAP-MAP's M1 (spec 2026-09-21-1555 sec 3.10).
Usage: dtmiss.py --corpus <C3 dir> [--out F] [--draws N] [--chart F.png]
       dtmiss.py --selftest-c2      D-d shape replication on C2, no row -- NEVER cite as a result

DEFINITIONS, predicates as code (HK-021(r)):
  REF DT = ALL.TXT column [5] (0-indexed split fields; [4] is SNR, [6] is freq_hz -- swapping
           5/6 inverts results, architecture-ft8-lib.md).
  H10 population = REF rows with REF SNR >= -10 dB (the harness's own strong-miss population).
  miss(B) = misses / rows in band B (a fraction), over the H10 population unless "all REF rows" is
            reported alongside (D-a).
  CORE = REF DT in [0.0, 1.0).  LATE = REF DT >= 1.5.
  Delta_pp = 100 * (miss(LATE) - miss(CORE)).  Excess_pp = Delta_pp * n(LATE) / n(pop)  (pp of pop).
  CI: 95% freq-clustered bootstrap on Delta_pp, N=2000, seed=20260921 (same scheme+seed as the
      harness's H10; resampled over the CORE|LATE frequency universe, paired per draw).
ROWS (first match wins, mutually exclusive):
  T0  n(LATE) < 300                                    -> underpowered, report the table, route nothing
  T1  CI_lo(Delta_pp) > 0  and  Excess_pp >= GAIN_BAR   -> timing costs a material share of decodes
  T1b CI_lo(Delta_pp) > 0  and  Excess_pp <  GAIN_BAR   -> real but small, no fix licensed on this alone
  T2  otherwise                                         -> no measurable late-start penalty
GAIN_BAR = 0.5 pp (the project's existing materiality bar, not new).
ROW 0a: the Amendment-3-cut harness reproduces n_ref 127,482 / H10 19.2686 before any split, else STOP.
ROW 0b: median REF DT over C3 (all REF rows, parseable only) in [0.0, 0.6] s, else STOP.
ROW 0c: band n's (7 numeric bands + "unparsable") sum to n(pop) exactly. No row dropped silently.
NFR-021: counts, rates, DT/SNR/freq values only. No message text, no callsign.
"""
import argparse, io, json, os, sys, time

REPO = os.environ.get("LGM_REPO", r"D:\Projects\claude\OpenWSFZ\worktrees\qa")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ("qa/rr-study/live-gap-now", "qa/rr-study/density-live", "qa/cycleframer-alignment-replay"):
    sys.path.insert(0, os.path.join(REPO, *p.split("/")))
import numpy as np  # noqa: E402
import lgm_harness as LGM  # noqa: E402  (load_c3, load_c2, core -- the Amendment-3-cut code path)
import corpus as CORPUS  # noqa: E402  (C2 paths, for D-d only)

N_BOOT, SEED = 2000, 20260921
GAIN_BAR = 0.5
SNR_STRONG = -10
BANDS = [("<-0.5", -10**6, -0.5), ("[-0.5,0.0)", -0.5, 0.0), ("[0.0,0.5)", 0.0, 0.5), ("[0.5,1.0)", 0.5, 1.0),
         ("[1.0,1.5)", 1.0, 1.5), ("[1.5,2.0)", 1.5, 2.0), (">=2.0", 2.0, 10**6)]
CORE_LO, CORE_HI = 0.0, 1.0   # [0.0, 1.0)
LATE_LO = 1.5                 # >= 1.5
AMD3_EXPECT = {"n_ref": 127482, "H10_4dp": 19.2686}


def band_of(dt):
    for name, lo, hi in BANDS:
        if lo <= dt < hi:
            return name
    return "?"


def load_all_dt(path, lo, hi, dial_prefix="14.074"):
    """(ts, message) -> dt (float) or None if column [5] is unparseable. Same inclusion criteria as
    matcher.load() (snr/freq_hz must parse, else the line is skipped entirely, exactly as ref/live
    were built) so keys align 1:1 with the harness's own ref/live dicts. A DT-parse failure does NOT
    drop the row -- it is kept with dt=None and counted (ROW 0c)."""
    out, bad = {}, 0
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(dial_prefix):
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                int(f[4]); int(f[6])
            except ValueError:
                continue
            key = (ts, " ".join(f[7:]))
            try:
                dt = float(f[5])
            except ValueError:
                dt, bad = None, bad + 1
            out[key] = dt
    return out, bad


def row0a(d, n, H10):
    got = {"n_ref": n, "H10_4dp": round(H10, 4)}
    ok = got == AMD3_EXPECT
    return {"expected": AMD3_EXPECT, "got": got, "pass": ok}


def band_delta_bootstrap(ref, core_keys, late_keys, miss_set, n_draws, seed):
    scope = core_keys | late_keys
    byf = {}
    for k in scope:
        byf.setdefault(ref[k][1], []).append(k)
    freqs = list(byf)
    rng = np.random.default_rng(seed)
    deltas, cores, lates = [], [], []
    for _ in range(n_draws):
        pick = rng.choice(len(freqs), size=len(freqs), replace=True)
        keys = []
        for i in pick:
            keys.extend(byf[freqs[i]])
        c = [k for k in keys if k in core_keys]
        l = [k for k in keys if k in late_keys]
        if not c or not l:
            continue
        mc = 100.0 * sum(1 for k in c if k in miss_set) / len(c)
        ml = 100.0 * sum(1 for k in l if k in miss_set) / len(l)
        deltas.append(ml - mc); cores.append(mc); lates.append(ml)
    dv = np.array(deltas)
    return {"delta_pp_ci95": [float(np.percentile(dv, 2.5)), float(np.percentile(dv, 97.5))],
            "delta_pp_bootstrap_mean": float(dv.mean()), "core_miss_pct_bootstrap_mean": float(np.mean(cores)),
            "late_miss_pct_bootstrap_mean": float(np.mean(lates)), "n_draws": len(dv), "n_distinct_freq": len(freqs), "seed": seed}


def d_a_table(ref, ref_dt, miss_set, scope_keys):
    """Per-band n / misses / miss(B) / share-of-all-misses, over scope_keys."""
    total_misses = sum(1 for k in scope_keys if k in miss_set)
    rows, unparsable_n, unparsable_miss = [], 0, 0
    for name, lo, hi in BANDS:
        ks = [k for k in scope_keys if ref_dt.get(k) is not None and lo <= ref_dt[k] < hi]
        m = sum(1 for k in ks if k in miss_set)
        rows.append({"band": name, "n": len(ks), "misses": m, "miss_pct": (100.0 * m / len(ks)) if ks else None,
                      "share_of_all_misses_pct": (100.0 * m / total_misses) if total_misses else None})
    up = [k for k in scope_keys if ref_dt.get(k) is None]
    unparsable_n, unparsable_miss = len(up), sum(1 for k in up if k in miss_set)
    n_sum = sum(r["n"] for r in rows) + unparsable_n
    return {"by_band": rows, "unparsable_dt": {"n": unparsable_n, "misses": unparsable_miss},
            "n_scope": len(scope_keys), "n_sum_check_bands_plus_unparsable": n_sum,
            "row0c_pass": n_sum == len(scope_keys), "total_misses_in_scope": total_misses}


def d_b_curve(ref_dt, miss_set, scope_keys, lo=-1.0, hi=2.5, step=0.1):
    n_bins = int(round((hi - lo) / step))
    out = []
    for i in range(n_bins):
        blo, bhi = round(lo + i * step, 2), round(lo + (i + 1) * step, 2)
        ks = [k for k in scope_keys if ref_dt.get(k) is not None and blo <= ref_dt[k] < bhi]
        m = sum(1 for k in ks if k in miss_set)
        out.append({"dt_lo": blo, "dt_hi": bhi, "n": len(ks), "misses": m, "miss_pct": (100.0 * m / len(ks)) if ks else None})
    return out


def d_c_offset(ref_dt, ows_dt, hit, gained, scope_keys):
    """OWS DT - REF DT for matched pairs, per band. exact_matched: direct (ts,msg) lookup in ows_dt.
    gained (wildcard) with exactly one candidate: look up that candidate's OWS DT. Ambiguous (>=2
    candidates) gained pairs are excluded (no single OWS DT to attribute)."""
    pairs = []
    for k in scope_keys:
        ts, _ = k
        if ref_dt.get(k) is None:
            continue
        odt = None
        if k in ows_dt:  # exact match: same (ts, msg) key exists in OWS's own ALL.TXT
            odt = ows_dt[k]
        elif k in gained and len(gained[k]) == 1:
            cand_key = (ts, gained[k][0])
            odt = ows_dt.get(cand_key)
        if odt is not None:
            pairs.append((band_of(ref_dt[k]), odt - ref_dt[k]))
    by_band = {}
    for b, off in pairs:
        by_band.setdefault(b, []).append(off)
    return {b: {"n": len(v), "mean_offset_s": round(float(np.mean(v)), 4), "sd_s": round(float(np.std(v, ddof=1)), 4) if len(v) > 1 else None}
            for b, v in sorted(by_band.items())}


def analyse(corpus_dir, n_draws, chart_path=None):
    d = LGM.load_c3(corpus_dir, cut_amendment3=True)
    rec, hit, miss, strong, n = LGM.core(d["ref"], d["live"])
    H10 = 100.0 * len(strong) / n
    a0 = row0a(d, n, H10)
    if not a0["pass"]:
        return {"verdict_row": "STOP_0a", "ROW_0a": a0, "note": "Amendment-3-cut figures do not reproduce; nothing else computed"}

    # Re-derive the same [lo,hi] cycle-id bounds load_c3 used, from the cut-included cycle list.
    W = d["cycles"]
    lo_ts, hi_ts = min(W), max(W)
    ref_dt_raw, bad_ref = load_all_dt(os.path.join(corpus_dir, "wsjtx-1-ft991a", "ALL.TXT"), lo_ts, hi_ts)
    ows_dt_raw, bad_ows = load_all_dt(os.path.join(corpus_dir, "openwsfz", "ALL.TXT"), lo_ts, hi_ts)
    S = set(W)
    ref_dt = {k: v for k, v in ref_dt_raw.items() if k[0] in S}
    ows_dt = {k: v for k, v in ows_dt_raw.items() if k[0] in S}
    key_align = set(ref_dt) == set(d["ref"])

    parsed = [v for v in ref_dt.values() if v is not None]
    median_dt = float(np.median(parsed)) if parsed else float("nan")
    b0 = {"median_REF_DT_s": median_dt, "n_parsed": len(parsed), "n_unparsed": sum(1 for v in ref_dt.values() if v is None),
          "pass": bool(0.0 <= median_dt <= 0.6)}
    if not b0["pass"]:
        return {"verdict_row": "STOP_0b", "ROW_0a": a0, "ROW_0b": b0, "note": "median REF DT outside [0.0,0.6]s; nothing else computed"}

    pop = {k for k in d["ref"] if d["ref"][k][0] >= SNR_STRONG}  # H10 population
    all_ref = set(d["ref"])
    miss_set = set(miss)

    core_keys = {k for k in pop if ref_dt.get(k) is not None and CORE_LO <= ref_dt[k] < CORE_HI}
    late_keys = {k for k in pop if ref_dt.get(k) is not None and ref_dt[k] >= LATE_LO}
    n_core, n_late, n_pop = len(core_keys), len(late_keys), len(pop)
    miss_core = 100.0 * sum(1 for k in core_keys if k in miss_set) / n_core if n_core else float("nan")
    miss_late = 100.0 * sum(1 for k in late_keys if k in miss_set) / n_late if n_late else float("nan")
    delta_pp = miss_late - miss_core
    excess_pp = delta_pp * n_late / n_pop if n_pop else float("nan")

    if n_late < 300:
        verdict = "T0"
    else:
        bs = band_delta_bootstrap(d["ref"], core_keys, late_keys, miss_set, n_draws, SEED)
        ci_lo = bs["delta_pp_ci95"][0]
        if ci_lo > 0 and excess_pp >= GAIN_BAR:
            verdict = "T1"
        elif ci_lo > 0 and excess_pp < GAIN_BAR:
            verdict = "T1b"
        else:
            verdict = "T2"

    out = {"ROW_0a": a0, "ROW_0b": b0, "key_alignment_ref_dt_vs_ref": key_align,
           "unparsed_lines_skipped_for_other_reasons": {"ref": bad_ref, "ows": bad_ows},
           "verdict_row": verdict, "bars": {"GAIN_BAR_pp": GAIN_BAR},
           "core_late": {"n_core": n_core, "n_late": n_late, "n_pop": n_pop, "miss_core_pct": miss_core,
                         "miss_late_pct": miss_late, "delta_pp": delta_pp, "excess_pp": excess_pp}}
    if n_late >= 300:
        out["core_late"]["bootstrap"] = bs

    out["D_a_H10_population"] = d_a_table(d["ref"], ref_dt, miss_set, pop)
    out["D_a_all_ref_rows"] = d_a_table(d["ref"], ref_dt, miss_set, all_ref)
    out["D_b_curve_H10_population"] = d_b_curve(ref_dt, miss_set, pop)
    out["D_c_ows_ref_dt_offset"] = d_c_offset(ref_dt, ows_dt, hit, rec["gained"], pop)

    out["prediction_inputs_Architect"] = {"T1_fires": verdict == "T1", "T1b_fires": verdict == "T1b",
                                          "T2_fires": verdict == "T2", "T0_fires": verdict == "T0"}
    out["window"] = d["window"]; out["amendment3"] = {"cut_applied": True, "removed_cycles": d["removed_cycles"], "removed_ref_n": d["removed_ref_n"]}

    if chart_path:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            curve = out["D_b_curve_H10_population"]
            xs = [(c["dt_lo"] + c["dt_hi"]) / 2 for c in curve if c["n"] > 0]
            ys = [c["miss_pct"] for c in curve if c["n"] > 0]
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot(xs, ys, marker="o", ms=3, lw=1)
            ax.axvline(1.71, color="grey", ls="--", lw=1, label="predicted window edge (+1.71 s)")
            ax.axvspan(CORE_LO, CORE_HI, color="tab:blue", alpha=0.08, label="CORE [0.0,1.0)")
            ax.axvspan(LATE_LO, 2.5, color="tab:red", alpha=0.08, label="LATE >=1.5")
            ax.set_xlabel("REF DT (s)"); ax.set_ylabel("miss rate (%), H10 population")
            ax.set_title("DT-MISS: 0.1s miss-rate curve, C3 (Amendment 3 cut)")
            ax.legend(fontsize=8)
            fig.tight_layout(); fig.savefig(chart_path, dpi=130); plt.close(fig)
            out["chart"] = chart_path
        except Exception as e:  # noqa: BLE001
            out["chart_error"] = str(e)
    return out


def analyse_c2_replication():
    """D-d: D-a's band shape on C2, no row, NEVER cite the level (C2 is nhard 60, a different day)."""
    d = LGM.load_c2()
    ref_dt_raw, _ = load_all_dt(os.path.join(CORPUS.C2_DIR, "wsjtx-1-ft991a", "ALL.TXT"), d["cycles"][0], d["cycles"][-1])
    S = set(d["cycles"])
    ref_dt = {k: v for k, v in ref_dt_raw.items() if k[0] in S}
    rec, hit, miss, strong, n = LGM.core(d["ref"], d["live"])
    miss_set = set(miss)
    pop = {k for k in d["ref"] if d["ref"][k][0] >= SNR_STRONG}
    return {"note": "C2, SELFTEST/replication -- shape only, never cite the level", "D_a_H10_population": d_a_table(d["ref"], ref_dt, miss_set, pop)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus"); ap.add_argument("--selftest-c2", action="store_true")
    ap.add_argument("--out"); ap.add_argument("--draws", type=int, default=N_BOOT); ap.add_argument("--chart")
    a = ap.parse_args()
    if a.selftest_c2:
        res = analyse_c2_replication()
        out = a.out or os.path.join(os.environ.get("TEMP", "."), "dtmiss_c2_replication.json")
    else:
        if not a.corpus:
            sys.exit("need --corpus or --selftest-c2")
        t0 = time.time()
        res = analyse(a.corpus, a.draws, chart_path=a.chart)
        res["seconds"] = round(time.time() - t0, 1)
        out = a.out or os.path.join(a.corpus, "results", "dtmiss_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print("wrote", out, "| verdict row:", res.get("verdict_row"), flush=True)


if __name__ == "__main__":
    main()
