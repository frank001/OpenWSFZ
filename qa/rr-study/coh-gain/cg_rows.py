#!/usr/bin/env python3
"""COH-GAIN: the pre-registered rows and statistics, computed AFTER the run, as code.

Spec (PRE-REGISTERED, Architect 2026-10-06 16:22Z): qa/rr-study/2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md (branch arch/coherent-limb2).
BAR_G = 1.0 pp, ratified by the Captain ~16:26Z, FROZEN. Every threshold below is the spec's (section quoted); none is QA's.
Predicates are pure functions so tests/test_cg_rows.py can show that each fires and does not fire on synthetic inputs (HK-021 (k)).

Loaders, the ratio-estimator block bootstrap, the autocorrelation-free Wilson interval and the clustering report are REUSED from the closed
onoff_replay_rows.py / nhard_rep_rows.py: here the bootstrap unit is the CYCLE (the S3c section-2 lesson): each cycle is one element carrying
(rows, successes_G, successes_X), blocks are 8 consecutive sampled cycles, numerator and denominator are resampled together.

Inputs (numeric only, HK-037): rows.csv (meta + per-arm fields, cg_common.ROW_FIELDS), synthetic.csv (V2), v5.csv (V5), pins.jsonl (V1).
"""
from __future__ import annotations

import collections
import csv
import datetime
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "sub-feas"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "nhard-rep"))
sys.path.insert(0, HERE)
import onoff_replay_rows as O  # noqa: E402
import nhard_rep_rows as NR  # noqa: E402
import cg_common as CG  # noqa: E402

META = ["cycle_index", "widx", "ws_snr", "ws_load", "live_hit"]
CSV_COLUMNS = META + CG.ROW_FIELDS
SNR_BANDS = (("<=-16", -99, -16), ("-15..-6", -15, -6), ("-5..+4", -5, 4), (">=+5", 5, 99))   # section 5
LEVELS = (0.3, 0.5, 0.7)                                                                      # section 5: success levels for the dB shift
MIN_BIN_N = 20


# =====================================================================================================================
# loading
# =====================================================================================================================
def load_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({k: (float(v) if v not in ("", None) else float("nan")) for k, v in r.items()})
    rows.sort(key=lambda r: (r["cycle_index"], r["widx"]))
    return rows


def load_pins(path):
    return O.load_pins(path)


# =====================================================================================================================
# estimand, interval, verdict
# =====================================================================================================================
def per_cycle(rows, arm_x, arm_base="G"):
    """Cycle-level arrays in cycle order: n rows, successes of the base arm, successes of arm X."""
    by = collections.OrderedDict()
    for r in rows:
        c = by.setdefault(int(r["cycle_index"]), [0, 0, 0])
        c[0] += 1
        c[1] += int(r[f"{arm_base}_ok"])
        c[2] += int(r[f"{arm_x}_ok"])
    arr = np.array(list(by.values()), dtype=float).reshape(-1, 3)
    return list(by.keys()), arr[:, 0], arr[:, 1], arr[:, 2]


def net_with_ci(rows, arm_x, arm_base="G", block=CG.BLOCK_CYCLES):
    ids, n, base, x = per_cycle(rows, arm_x, arm_base)
    net = O.net_pp(n, base, x)
    lo, hi, nb = O.block_bootstrap_ci(n, base, x, block=block, B=CG.B_RESAMPLES, seed=CG.SEED)
    return {"NET_pp": net, "ci95": [lo, hi], "n_cycles": len(ids), "n_rows": int(n.sum()), "n_blocks": nb, "block": block}


def verdict_row(ci_lo, ci_hi, bar=CG.BAR_G):
    """Exclusive rows, first match wins (spec section 6)."""
    if ci_lo >= bar:
        return "COH-GO"
    if ci_hi < bar:
        return "COH-STOP"
    return "COH-OPEN"


# =====================================================================================================================
# validity rows (pure predicates; spec section 6)
# =====================================================================================================================
def _median(xs):
    return float(np.median(np.asarray(xs, dtype=float))) if len(xs) else float("nan")


def row_v1(pins, whens=("start", "end")):
    """V1: DLL SHA-256 == the pin (2fa6d993...f365), recorded at start and at end. A missing record FAILS."""
    seen = {p["when"]: p.get("libft8_sha256") == CG.DLL_PIN for p in pins if p.get("mode") == "main"}
    bad = [w for w in whens if not seen.get(w, False)]
    return (not bad), {"failed_or_missing": bad}


def load_synth(csv_path, spec_path):
    """synthetic.csv joined to the frozen synthetic_set.json by signal index i, so the SIGNED errors (C3 estimate minus the TRUE offset) can be formed
    from the stored estimates with NO re-render (Amendment 1 item 1)."""
    spec = {s["i"]: s for s in json.load(open(spec_path))}
    out = []
    for r in csv.DictReader(open(csv_path, newline="", encoding="utf-8")):
        d = {k: (float(v) if v not in ("", None) else float("nan")) for k, v in r.items()}
        s = spec.get(int(d["i"]))
        if not d.get("fault") and "C3_df" in d and s is not None and "err_df_signed" not in d:
            d["err_df_signed"] = d["C3_df"] - s["df_off"]
            d["err_dt_signed"] = d["C3_dt"] - s["dt_off"]
        out.append(d)
    return out


def row_v2(synth):
    """V2 (synthetic alignment; AMENDMENT 1's (b')): over exactly 200 off-lattice signals PASS iff (a) C3 success >= 0.95, (b') median |est_df - true_df|
    <= 0.20 Hz AND |median signed (est_df - true_df)| <= 0.05 Hz AND median |est_dt - true_dt| <= 7.5 ms, (c) G success >= 0.90. A faulted signal
    counts as a FAILURE in (a) and (c), never as 'absent'. Descriptive (no bar): the quantiles of both errors, C1 and C3S success, the oracle's errors."""
    n = len(synth)
    ok_rows = [s for s in synth if not s.get("fault")]
    c3 = sum(int(s["C3_ok"]) for s in ok_rows) / CG.V2_N if CG.V2_N else float("nan")
    g = sum(int(s["G_ok"]) for s in ok_rows) / CG.V2_N
    med_df = _median([s["err_df"] for s in ok_rows])
    med_dt = _median([s["err_dt"] for s in ok_rows])
    a = n == CG.V2_N and c3 >= CG.V2_C3_MIN
    signed = _median([s["err_df_signed"] for s in ok_rows]) if ok_rows else float("nan")
    b = (n == CG.V2_N and med_df <= CG.V2_MEDIAN_DF_MAX_HZ and med_dt <= CG.V2_MEDIAN_DT_MAX_S
         and abs(signed) <= CG.V2_SIGNED_MEDIAN_DF_MAX_HZ)
    c = n == CG.V2_N and g >= CG.V2_G_MIN
    q = lambda key: [float(x) for x in np.quantile([s[key] for s in ok_rows], [0.1, 0.5, 0.9, 0.99])] if ok_rows else None
    det = {"n": n, "n_faults": n - len(ok_rows), "a_C3_success": c3, "a_pass": a, "b_median_err_df_hz": med_df, "b_signed_median_err_df_hz": signed, "b_median_err_dt_s": med_dt,
           "b_pass": b, "c_G_success": g, "c_pass": c,
           "descriptive": {"err_df_quantiles_10_50_90_99": q("err_df"), "err_dt_quantiles_10_50_90_99": q("err_dt"),
                           "C1_success": sum(int(s["C1_ok"]) for s in ok_rows) / CG.V2_N,
                           "C3S_success": sum(int(s["C3S_ok"]) for s in ok_rows) / CG.V2_N,
                           "oracle_median_err_df_hz": _median([s["err_df_oracle"] for s in ok_rows]),
                           "oracle_median_err_dt_s": _median([s["err_dt_oracle"] for s in ok_rows])}}
    return (a and b and c), det


def v2t_descriptive(synth):
    """AMENDMENT 1: the -20 dB tier, DESCRIPTIVE only (no row, never cited as the gain): success of every arm and the estimator's errors."""
    ok = [s for s in synth if not s.get("fault")]
    n = len(synth)
    if not n:
        return None
    rate = lambda arm: sum(int(s[f"{arm}_ok"]) for s in ok) / n
    return {"n": n, "n_faults": n - len(ok), "success": {a: rate(a) for a in CG.ARMS},
            "median_err_df_hz": _median([s["err_df"] for s in ok]), "median_err_dt_s": _median([s["err_dt"] for s in ok]),
            "oracle_median_err_df_hz": _median([s["err_df_oracle"] for s in ok]), "oracle_median_err_dt_s": _median([s["err_dt_oracle"] for s in ok])}


def row_v3(rows):
    """V3 (window): on real rows the share of C3 estimates on the EDGE of the df or dt window must be <= 5 %. Faulted rows are excluded from the
    denominator and counted. NB (HK-026): edge share is SUFFICIENT evidence of a too-narrow window, not necessary: the histograms are in the report."""
    ok = [r for r in rows if not r["fault"]]
    edge = sum(int(r["C3_edge"]) for r in ok)
    share = edge / len(ok) if ok else float("nan")
    return (bool(ok) and share <= CG.V3_MAX_EDGE_SHARE), {"edge": edge, "n": len(ok), "share": share, "faulted_rows": len(rows) - len(ok)}


def row_v4(rows):
    """V4 (control reproduces): on real rows with live_hit == 1, G success >= 0.90."""
    hit = [r for r in rows if not r["fault"] and int(r["live_hit"]) == 1]
    k = sum(int(r["G_ok"]) for r in hit)
    rate = k / len(hit) if hit else float("nan")
    return (bool(hit) and rate >= CG.V4_G_MIN), {"G_success_on_live_hits": rate, "n_live_hits": len(hit)}


def row_v5(main_rows, v5_rows, n=CG.V5_ROWS):
    """V5 (determinism): a second fresh process over the first 300 rows (in (cycle_index, widx) order): EVERY per-row field identical.
    NaN compares equal to NaN. A short or missing second run FAILS."""
    first = main_rows[:n]
    if len(first) != n or len(v5_rows) != n:
        return False, {"n_main": len(first), "n_v5": len(v5_rows), "reason": "wrong row count"}
    diffs = []
    for a, b in zip(first, v5_rows):
        for col in CSV_COLUMNS:
            x, y = a[col], b[col]
            if not (x == y or (isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y))):
                diffs.append((int(a["cycle_index"]), int(a["widx"]), col))
    return (not diffs), {"n": n, "differing_fields": len(diffs), "first_differences": diffs[:5]}


# =====================================================================================================================
# descriptive statistics
# =====================================================================================================================
def gains_losses(rows, arm_x, arm_base="G"):
    g = sum(1 for r in rows if int(r[f"{arm_x}_ok"]) and not int(r[f"{arm_base}_ok"]))
    l = sum(1 for r in rows if int(r[f"{arm_base}_ok"]) and not int(r[f"{arm_x}_ok"]))
    n = len(rows)
    out = {"gains": g, "losses": l, "n": n, "gains_pct_of_rows": 100.0 * g / n if n else None, "losses_pct_of_rows": 100.0 * l / n if n else None}
    for name, key in (("gains", "gain"), ("losses", "loss")):
        by = collections.OrderedDict()
        for r in rows:
            c = by.setdefault(int(r["cycle_index"]), [0, 0])
            c[0] += 1
            xo, bo = int(r[f"{arm_x}_ok"]), int(r[f"{arm_base}_ok"])
            c[1] += int(xo and not bo) if key == "gain" else int(bo and not xo)
        arr = np.array(list(by.values()), dtype=float)
        lo, hi, _ = O.block_bootstrap_ci(arr[:, 0], np.zeros(len(arr)), arr[:, 1], block=CG.BLOCK_CYCLES, B=CG.B_RESAMPLES, seed=CG.SEED)
        out[f"{name}_ci95_pct"] = [lo, hi]
    return out


def osd_arm_report(rows, arm, base_arm):
    """AMENDMENT 2 (descriptive, no row): a sign-corrected-OSD arm against its own base. Counts rows where BP-only failed and corrected OSD recovered the TRUE
    payload, rows where corrected OSD returned a CRC-valid WRONG payload (the at-position FP cost), and rows where the negated call returned path 0 (counted,
    treated as a failure)."""
    n = len(rows)
    bp_fail = [r for r in rows if not int(r[f"{arm}_bp_ok"])]
    rescued = sum(1 for r in bp_fail if int(r[f"{arm}_osd_ok"]))
    wrong = sum(1 for r in rows if int(r[f"{arm}_wrong"]))
    neg0 = sum(1 for r in rows if int(r[f"{arm}_neg0"]))
    return {"NET_vs_base": net_with_ci(rows, arm, arm_base=base_arm), "n_rows": n, "bp_only_success": sum(int(r[f"{arm}_bp_ok"]) for r in rows),
            "bp_fail_rows": len(bp_fail), "bp_fail_rows_recovered_true_payload_by_corrected_osd": rescued,
            "rows_corrected_osd_returned_crc_valid_wrong_payload": wrong,
            "wrong_pct_of_rows": 100.0 * wrong / n if n else None,
            "wrong_pct_of_bp_fail_rows": 100.0 * wrong / len(bp_fail) if bp_fail else None,
            "rows_negated_call_returned_path0": neg0}


def success_curve(rows, arm, min_n=MIN_BIN_N):
    """{ws_snr: success rate} for 1-dB bins with at least min_n rows, then made monotone non-decreasing in SNR (running max)."""
    cnt, suc = collections.Counter(), collections.Counter()
    for r in rows:
        s = int(r["ws_snr"])
        cnt[s] += 1
        suc[s] += int(r[f"{arm}_ok"])
    xs = sorted(s for s in cnt if cnt[s] >= min_n)
    ys = np.maximum.accumulate([suc[s] / cnt[s] for s in xs]) if xs else np.array([])
    return xs, [float(y) for y in ys]


def crossing(xs, ys, level):
    """Lowest SNR (linear interpolation between bins) at which the monotone curve first reaches `level`; None if it never does or starts above it."""
    for i, y in enumerate(ys):
        if y >= level:
            if i == 0:
                return None
            x0, y0, x1, y1 = xs[i - 1], ys[i - 1], xs[i], y
            return x0 + (level - y0) * (x1 - x0) / (y1 - y0) if y1 > y0 else float(x1)
    return None


def db_shift(rows, arm_x, arm_base="G", levels=LEVELS):
    """Horizontal shift (dB) between the base and arm-X success-vs-ws_snr curves, linear interpolation at each level, MEDIAN over the levels where both exist.
    Positive = arm X reaches the level at a lower SNR (better bits)."""
    xb, yb = success_curve(rows, arm_base)
    xx, yx = success_curve(rows, arm_x)
    per = {}
    for lv in levels:
        a, b = crossing(xb, yb, lv), crossing(xx, yx, lv)
        per[str(lv)] = None if a is None or b is None else a - b
    vals = [v for v in per.values() if v is not None]
    return {"per_level_db": per, "median_db": float(np.median(vals)) if vals else None}


def shift_estimator_gain_pp(rows, shift_db):
    """The review's section-4 SHIFT ESTIMATOR, reconstructed from its description (an UPPER bound: it credits the shift with every other failure mode
    too): the live-recall curve (2 dB bins of ws_snr, linear interpolation, clamped) is moved by shift_db and its gain is averaged over the WSJT-X
    population's SNR distribution. Descriptive, for comparison with the direct NET_C3."""
    if shift_db is None:
        return None
    snr = np.array([r["ws_snr"] for r in rows], dtype=float)
    hit = np.array([r["live_hit"] for r in rows], dtype=float)
    edges = np.arange(np.floor(snr.min() / 2) * 2, snr.max() + 2.01, 2.0)
    centres, rec = [], []
    for lo in edges[:-1]:
        m = (snr >= lo) & (snr < lo + 2)
        if m.sum() >= MIN_BIN_N:
            centres.append(lo + 1.0)
            rec.append(float(hit[m].mean()))
    if len(centres) < 2:
        return None
    r0 = np.interp(snr, centres, rec)
    r1 = np.interp(snr + shift_db, centres, rec)
    return float(100.0 * np.mean(r1 - r0))


def strata(rows, arm_x="C3"):
    """NET_arm_x by ws_snr band, by ws_load quintile and on live misses only (descriptive, no row)."""
    out = {"by_ws_snr_band": {}, "by_ws_load_quintile": {}}
    for name, lo, hi in SNR_BANDS:
        sub = [r for r in rows if lo <= int(r["ws_snr"]) <= hi]
        out["by_ws_snr_band"][name] = net_with_ci(sub, arm_x) if len(sub) >= 50 else {"n_rows": len(sub), "note": "fewer than 50 rows"}
    loads = np.array([r["ws_load"] for r in rows], dtype=float)
    edges = np.quantile(loads, [0.2, 0.4, 0.6, 0.8]) if len(loads) else []
    idx = lambda v: int(np.searchsorted(edges, v, side="right"))
    for q in range(5):
        sub = [r for r in rows if idx(r["ws_load"]) == q]
        out["by_ws_load_quintile"][f"Q{q + 1}"] = net_with_ci(sub, arm_x) if len(sub) >= 50 else {"n_rows": len(sub), "note": "fewer than 50 rows"}
    miss = [r for r in rows if int(r["live_hit"]) == 0]
    out["live_misses_only"] = net_with_ci(miss, arm_x) if len(miss) >= 50 else {"n_rows": len(miss), "note": "fewer than 50 rows"}
    return out


def frozen_excluded(rows_json_path):
    """Rows excluded BEFORE extraction (the encoder could not pack them), from the frozen list's counts: {modulus: n_excluded_in_that_sample}."""
    spec = json.load(open(rows_json_path))
    return spec["counts"]


def rescaled_net(net, counts, modulus):
    """AMENDMENT 1 item 4: the verdict's denominator is the ENCODABLE rows. This ALSO gives NET_C3 rescaled to ALL WSJT-X decodes in the sampled cycles,
    with ZERO gain credited to the excluded rows: NET_all = NET * N_encodable / (N_encodable + N_excluded). Both are stated in the report.
    Only the mod-10 sample's exclusion count is frozen; for the mod-20 fallback the share is taken as the same fraction (stated, approximate)."""
    excluded10 = sum(counts["excluded_before_extraction"].values())
    n_enc10 = counts["rows_mod10"]
    frac_enc = n_enc10 / (n_enc10 + excluded10)
    f = frac_enc
    return {"NET_pp_encodable": net["NET_pp"], "ci95_encodable": net["ci95"], "encodable_share_of_all_decodes": f,
            "NET_pp_all_decodes": net["NET_pp"] * f, "ci95_all_decodes": [net["ci95"][0] * f, net["ci95"][1] * f],
            "excluded_rows_mod10": excluded10, "modulus": modulus,
            "note": "zero gain credited to the excluded rows; mod-20 uses the mod-10 exclusion share" if modulus == 20 else "zero gain credited to the excluded rows"}


def histogram(values, edges):
    cnt, _ = np.histogram(np.asarray(values, dtype=float), bins=edges)
    return [int(c) for c in cnt]


# =====================================================================================================================
# assembly
# =====================================================================================================================
def analyse(out_dir, results_dir=None, modulus=10):
    rows_all = load_rows(os.path.join(out_dir, "rows.csv"))
    synth_csv = os.path.join(out_dir, "synthetic.csv")
    synth = load_synth(synth_csv, os.path.join(HERE, "synthetic_set.json")) if os.path.exists(synth_csv) else []
    t_csv = os.path.join(out_dir, "synthetic_t.csv")
    synth_t = load_synth(t_csv, os.path.join(HERE, "synthetic_set_t.json")) if os.path.exists(t_csv) else []
    v5 = load_rows(os.path.join(out_dir, "v5.csv"))
    pins = load_pins(os.path.join(out_dir, "pins.jsonl"))
    rows = [r for r in rows_all if not r["fault"]]

    v = {"V1": row_v1(pins), "V2": row_v2(synth), "V3": row_v3(rows_all), "V4": row_v4(rows_all), "V5": row_v5(rows_all, v5)}
    all_valid = all(ok for ok, _ in v.values())
    failing = [k for k, (ok, _) in v.items() if not ok]
    result = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "BAR_G_pp": CG.BAR_G,
              "n_rows": len(rows_all), "n_faulted": len(rows_all) - len(rows), "n_cycles": len({int(r["cycle_index"]) for r in rows}),
              "validity": {k: {"pass": ok, **d} for k, (ok, d) in v.items()}, "failing_rows": failing, "first_paragraph_flags": []}
    if rows:
        est = {arm: net_with_ci(rows, arm) for arm in ("C3", "C1", "C3S")}
        result["estimand"] = {"NET_C3": est["C3"], "block_variants_not_used_for_verdict": {
            str(b): list(net_with_ci(rows, "C3", block=b)["ci95"]) for b in CG.BLOCKS_REPORTED}}
        result["rescaled_to_all_wsjtx_decodes"] = rescaled_net(est["C3"], frozen_excluded(os.path.join(REPO, "qa", "rr-study", "results",
                                                               "2026-10-06-coh-gain", "rows.json")), modulus)
        result["descriptive"] = {"NET_C1": est["C1"], "NET_C3S": est["C3S"], "v2t_minus20dB_descriptive": v2t_descriptive(synth_t),
                                 "gains_losses": {arm: gains_losses(rows, arm) for arm in ("C1", "C3", "C3S")},
                                 "amendment2_sign_corrected_osd_descriptive": {
                                     "GO_vs_G": osd_arm_report(rows, "GO", "G"),
                                     "C3O_vs_C3": osd_arm_report(rows, "C3O", "C3"),
                                     "C3O_vs_G": net_with_ci(rows, "C3O", arm_base="G")},
                                 "path_G_counts": dict(collections.Counter(int(r["G_path"]) for r in rows)),
                                 "estimate_histograms": {
                                     "C3_df_hz_edges_-2..2_step0.5": histogram([r["C3_df"] for r in rows], np.arange(-2.0, 2.01, 0.5)),
                                     "C3_dt_s_edges_-0.12..0.12_step0.03": histogram([r["C3_dt"] for r in rows], np.arange(-0.12, 0.1201, 0.03))},
                                 "strata_C3": strata(rows)}
        sh = db_shift(rows, "C3")
        result["descriptive"]["db_shift_C3_vs_G"] = sh
        result["descriptive"]["shift_estimator_upper_bound_pp"] = shift_estimator_gain_pp(rows, sh["median_db"])
        ids, n, base, x = per_cycle(rows, "C3")
        cl = NR.cluster_report([int(b - a) for a, b in zip(base, x)], block=CG.BLOCK_CYCLES)
        result["cluster"] = cl
        if cl["flag_gt_half"]:
            result["first_paragraph_flags"].append("top-5 blocks carry more than half of the positive net gain")
        lo, hi = est["C3"]["ci95"]
        if all_valid:
            result["verdict"] = verdict_row(lo, hi)
        else:
            result["verdict"] = "NO VERDICT"
            result["verdict_withheld_because"] = failing
    else:
        result["verdict"] = "NO VERDICT"
        result["verdict_withheld_because"] = failing or ["no real rows"]
    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(result, open(os.path.join(results_dir, "rows.json"), "w"), indent=1, sort_keys=True, default=str)
    return result


def main(argv):
    import argparse
    art = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(art, "rr_2026-10-06_coh_gain"))
    ap.add_argument("--results", default=os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-coh-gain"))
    a = ap.parse_args(argv)
    res = analyse(a.out, a.results)
    print(json.dumps({k: res[k] for k in ("verdict", "failing_rows", "estimand", "cluster", "first_paragraph_flags") if k in res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
