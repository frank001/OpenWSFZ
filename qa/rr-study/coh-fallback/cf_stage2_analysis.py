#!/usr/bin/env python3
"""COH-FALLBACK step 3, Stage 2 decision replay: validity rows, A3', NET, DeltaU (spec 5.3, 8 A1.5-A1.7, 9 A2.2-A2.3, 11).
Numbers only: no message text is read (outcomes carry freq/dt/snr/path; Test B counts carry n/corroborated).
  python cf_stage2_analysis.py <raw dir with off2/ on/ onrep/> <out json>
Bars (all pre-registered in the spec): BAR_G 1.0 pp; U_max 0.078 (frozen, section 11); V5 <= 5 %; V6 unexplained = 0 and abandon-explained <= 5 %;
A3' (b) p95(ON-OFF tb2) <= 50 ms, (c) p95(ON-OFF tb3) <= 250 ms; bootstrap: non-overlapping blocks of 40 consecutive selected cycles, B 10,000, seed 20261007, ratio estimator for NET.
"""
import collections
import csv
import hashlib
import json
import math
import re
import sys

import numpy as np

BAR_G_PP = 1.0
U_MAX = 0.078
V5_MAX = 0.05
TB2_BAR_MS = 50.0
TB3_BAR_MS = 250.0
BLOCK = 40
B_BOOT = 10000
SEED = 20261007
PINNED_SHA = "581331da9383bc2d690e0b4146d8737b7f35738917839534d9f88ce72e85f5d1"
PATH_FALLBACK = "2"


def rows(p):
    return list(csv.DictReader(open(p, newline="", encoding="utf-8")))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def pct(a, q):
    return float(np.percentile(np.array(a, float), q)) if len(a) else float("nan")


def load_outcomes(path):
    d = collections.defaultdict(list)
    for r in csv.reader(open(path, newline="", encoding="utf-8")):
        if len(r) < 7:
            continue
        d[r[0]].append((r[1], r[3], r[4], r[5], r[6]))        # kind, freq, dt, snr, path
    return d


def load_testb(path):
    nc = collections.defaultdict(float)
    nc_band = collections.defaultdict(float)
    n_kind = collections.defaultdict(float)
    ws = {}
    for r in rows(path):
        s, k, b, n, c = r["stamp"], r["kind"], r["band"], int(r["n"]), int(r["corroborated"])
        if k == "ws":
            ws[s] = (n, c)
        elif b in "ABCD" and len(b) == 1:
            nc[s] += n - c
            nc_band[(s, b)] += n - c
            n_kind[(s, k)] += n
    return ws, nc, nc_band, n_kind


def load_run(path):
    return {r["stamp"]: r for r in rows(path)}


def boot(vals_num, vals_den, stamps):
    """Non-overlapping blocks of BLOCK consecutive selected cycles; ratio estimator sum(num)/sum(den); returns point, lo, hi."""
    num = np.array([vals_num[s] for s in stamps], float)
    den = np.array([vals_den[s] for s in stamps], float)
    nb = int(math.ceil(len(stamps) / BLOCK))
    bn = np.array([num[i * BLOCK:(i + 1) * BLOCK].sum() for i in range(nb)])
    bd = np.array([den[i * BLOCK:(i + 1) * BLOCK].sum() for i in range(nb)])
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, nb, size=(B_BOOT, nb))
    est = bn[idx].sum(1) / bd[idx].sum(1)
    return num.sum() / den.sum(), float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))


def main():
    raw, out = sys.argv[1], sys.argv[2]
    R = {}
    for arm in ("off2", "on", "onrep"):
        R[arm] = dict(out=load_outcomes(f"{raw}/{arm}/outcomes.csv"), tb=load_testb(f"{raw}/{arm}/testb.csv"), run=load_run(f"{raw}/{arm}/run.csv"),
                      ab={r["stamp"]: r for r in rows(f"{raw}/{arm}/abandon.csv")}, coh={r["stamp"]: r for r in rows(f"{raw}/{arm}/coh.csv")},
                      log=open(f"{raw}/{arm}/log.log", encoding="utf-8", errors="replace").read())
    res = {}
    stamps_all = sorted(R["off2"]["out"].keys() | R["off2"]["run"].keys())
    stamps_on = sorted(R["on"]["run"].keys())
    res["cycles_off"], res["cycles_on"] = len(R["off2"]["run"]), len(stamps_on)
    res["cycle_sets_equal"] = set(R["off2"]["run"]) == set(R["on"]["run"])
    stamps = sorted(R["off2"]["run"].keys())                                   # selection order = chronological stamp order (same day, hhmmss)
    ws_off = R["off2"]["tb"][0]
    ref = [s for s in stamps if ws_off.get(s, (0, 0))[0] > 0]                  # section 11 A11.1: ws = 0 cycles are out of every Test-B row, both arms
    res["cycles_with_ws_reference"] = len(ref)

    # V1/V2/V3
    res["V1_pin"] = {"pinned": PINNED_SHA}
    res["V2_flags"] = {a: sorted(set(re.findall(r"cohfb=(True|False)", R[a]["log"]))) for a in R}
    res["V3"] = {a: {"contained_exc_true": R[a]["log"].count("containedException=True"), "run_csv_exception_nonempty": sum(1 for r in R[a]["run"].values() if r["exception"]),
                     "access_violation_mentions": len(re.findall(r"(?i)access violation|0xC0000005", R[a]["log"]))} for a in R}

    # V4 / A3
    def multi(arm, kind, s, drop_path=None):
        return collections.Counter((f, d, n) for (k, f, d, n, p) in R[arm]["out"].get(s, []) if k == kind and p != drop_path)
    v4 = [s for s in stamps if multi("off2", "b1", s) != multi("on", "b1", s)]
    res["V4_A3_batch1"] = {"differing_cycles": len(v4), "first": v4[:5], "verdict": "PASS" if not v4 else "FAIL"}

    # V5
    ab_on = [s for s in stamps if int(R["on"]["ab"][s]["abandoned"] or 0) or int(R["on"]["coh"][s]["abandoned"] or 0)
            ]
    k5 = len(ab_on)
    w5 = wilson(k5, len(stamps))
    res["V5"] = {"abandoned_cycles": k5, "n": len(stamps), "rate": k5 / len(stamps), "wilson": w5, "verdict": "PASS" if k5 / len(stamps) <= V5_MAX else "FAIL",
                 "log_deadlineAbandoned_true": R["on"]["log"].count("deadlineAbandoned=True")}

    # A3' (a)
    ab_off = {s for s in stamps if int(R["off2"]["ab"][s]["abandoned"] or 0)}
    ab_either = set(ab_on) | ab_off
    b2d = [s for s in stamps if multi("off2", "b2", s) != multi("on", "b2", s)]
    b3d = [s for s in stamps if multi("off2", "b3", s) != multi("on", "b3", s, drop_path=PATH_FALLBACK)]
    b2u = [s for s in b2d if s not in ab_either]
    b3u = [s for s in b3d if s not in ab_either]
    # (b), (c)
    # run.csv writes -1 (or blank) for a batch that was not published: only cycles where BOTH arms published the batch enter a delay (Architect E10, spec 13)
    def pubd(arm, s, col):
        v = R[arm]["run"][s][col]
        return float(v) if v != "" and float(v) >= 0 else None
    def delays(col, a, b):
        return [pubd(a, s, col) - pubd(b, s, col) for s in stamps if s in R[a]["run"] and s in R[b]["run"] and pubd(a, s, col) is not None and pubd(b, s, col) is not None]
    d2, d3 = delays("tb2_ms", "on", "off2"), delays("tb3_ms", "on", "off2")
    n2, n3 = delays("tb2_ms", "onrep", "on"), delays("tb3_ms", "onrep", "on")
    only_on_b3 = sum(1 for s in stamps if pubd("on", s, "tb3_ms") is not None and pubd("off2", s, "tb3_ms") is None)
    dist = lambda a: {"n": len(a), "p50": pct(a, 50), "p95": pct(a, 95), "max": max(a) if a else None}
    a3b, a3c = pct(d2, 95) <= TB2_BAR_MS, pct(d3, 95) <= TB3_BAR_MS
    res["A3prime"] = {"a_batch2_differing": len(b2d), "a_batch2_unexplained": len(b2u), "a_batch3_minus_path2_differing": len(b3d), "a_batch3_unexplained": len(b3u),
                      "abandon_explained_cycles": len(ab_either), "b_tb2_on_minus_off_ms": dist(d2), "noise_tb2_onrep_minus_on_ms": dist(n2), "noise_tb3_onrep_minus_on_ms": dist(n3), "on_only_batch3_cycles": only_on_b3, "b_bar_ms": TB2_BAR_MS, "b_pass": a3b,
                      "c_tb3_on_minus_off_ms": dist(d3), "c_bar_ms": TB3_BAR_MS, "c_pass": a3c,
                      "guard_count": "NOT REPORTED: the replay records per-batch time from decode start, not the live decode-start offset (A2.2)",
                      "verdict": "PASS" if (not b2u and not b3u and a3b and a3c) else "FAIL"}

    # V6
    rep = sorted(R["onrep"]["run"].keys())
    def union(arm, s, with_path):
        return collections.Counter((k, f, d, n, p) if with_path else (f, d, n) for (k, f, d, n, p) in R[arm]["out"].get(s, []))
    v6 = {}
    for wp in (True, False):
        diff = [s for s in rep if union("on", s, wp) != union("onrep", s, wp)]
        un = [s for s in diff if s not in ab_either and int(R["onrep"]["ab"][s]["abandoned"] or 0) == 0]
        v6["with_kind_path" if wp else "freq_dt_snr_only"] = {"differing": len(diff), "unexplained": len(un), "first": diff[:5]}
    v6["n_repeated"] = len(rep)
    v6["wilson_upper_for_0"] = wilson(0, len(rep))[1]
    v6["verdict"] = "PASS" if v6["with_kind_path"]["unexplained"] == 0 else "FAIL"
    res["V6"] = v6

    # NET, DeltaU (paired against the Stage 2 OFF arm, section 11 A11.3)
    W = {s: ws_off[s][0] for s in ref}
    Moff = {s: R["off2"]["tb"][0][s][1] for s in ref}
    Mon = {s: R["on"]["tb"][0][s][1] for s in ref}
    dM = {s: Mon[s] - Moff[s] for s in ref}
    net = boot(dM, W, ref)
    res["NET_pp"] = {"point": 100 * net[0], "lo": 100 * net[1], "hi": 100 * net[2], "sum_dM": sum(dM.values()), "sum_W": sum(W.values()),
                     "Moff_pct": 100 * sum(Moff.values()) / sum(W.values()), "Mon_pct": 100 * sum(Mon.values()) / sum(W.values()),
                     "verdict": "D-GO" if 100 * net[1] >= BAR_G_PP else ("D-STOP" if 100 * net[2] < BAR_G_PP else "D-OPEN")}
    ncoff, ncon = R["off2"]["tb"][1], R["on"]["tb"][1]
    dU = {s: ncon[s] - ncoff[s] for s in ref}
    one = {s: 1.0 for s in ref}
    u = boot(dU, one, ref)
    u0 = sum(ncoff[s] for s in ref) / len(ref)
    res["DeltaU"] = {"point": u[0], "lo": u[1], "hi": u[2], "U_max": U_MAX, "U0_stage2_off": u0, "U0_in_0.30_0.65_guard_n_a": "section 8 replaced the guard by U_max",
                     "verdict": "U-OK" if u[2] <= U_MAX else ("U-FAIL" if u[1] > U_MAX else "U-OPEN")}
    # by band
    band = {}
    for b in "ABCD":
        nb_off, nb_on = R["off2"]["tb"][2], R["on"]["tb"][2]
        d = {s: nb_on[(s, b)] - nb_off[(s, b)] for s in ref}
        band[b] = {"DeltaU_mean": sum(d.values()) / len(ref), "sum_dNC": sum(d.values())}
    res["DeltaU_by_band"] = band
    res["NET_by_band"] = "NOT REPORTED: matched.csv carries WSJT-X indices, not the SNR band of the matched decode"

    # descriptive: fallback activity
    c = R["on"]["coh"]
    tot = lambda f: sum(int(c[s][f] or 0) for s in ref)
    ext = {s: sum(1 for (k, f, d, n, p) in R["on"]["out"].get(s, []) if p == PATH_FALLBACK) for s in stamps}
    nfb = sum(ext[s] for s in ref)
    pub = tot("published")
    res["fallback"] = {"eligible": tot("eligible"), "gated": tot("gated"), "attempted": tot("attempted"), "crc_ok": tot("crc_ok"), "published_log": pub,
                       "path2_rows_in_outcomes": nfb, "published_per_cycle": pub / len(ref), "published_edge": tot("published_edge"),
                       "edge_share_of_published": tot("published_edge") / pub if pub else None,
                       "abandoned": tot("abandoned"), "elapsed_ms_median": pct([float(c[s]["elapsed_ms"]) for s in ref], 50), "elapsed_ms_p95": pct([float(c[s]["elapsed_ms"]) for s in ref], 95),
                       "delta_decodes_on_minus_off": sum(len(R["on"]["out"].get(s, [])) - len(R["off2"]["out"].get(s, [])) for s in ref)}
    dnc = sum(dU.values())
    res["fallback"]["confirmed_share_of_path2"] = (1 - dnc / nfb) if nfb else None
    # FP-watch: CI_lo(fallback not-confirmed rate) > CI_hi(batch-1 not-confirmed rate)
    nb1 = sum(R["off2"]["tb"][3][(s, "b1")] for s in ref)
    nc_b1 = 0
    for r in rows(f"{raw}/off2/testb.csv"):
        if r["kind"] == "b1" and r["stamp"] in set(ref) and len(r["band"]) == 1:
            nc_b1 += int(r["n"]) - int(r["corroborated"])
    fb = wilson(max(int(round(dnc)), 0), nfb) if nfb else (0, 1)
    b1w = wilson(nc_b1, int(nb1))
    res["FP_watch"] = {"fallback_nc_rate": dnc / nfb if nfb else None, "fallback_wilson": fb, "batch1_nc_rate": nc_b1 / nb1, "batch1_wilson": b1w, "flag": bool(fb[0] > b1w[1])}
    res["OFF_arm_not_confirmed_per_cycle_U0"] = u0
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
