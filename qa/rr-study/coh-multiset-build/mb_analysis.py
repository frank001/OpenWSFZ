#!/usr/bin/env python3
"""COH-MULTISET-BUILD replay analysis (Architect spec sections 6.2-6.7 with Amendments 1-3). Numbers only: no message text is read.

  python mb_analysis.py <raw dir with ref/ ms/ msrep/ and ref_status.txt ms_status.txt msrep_status.txt> <out json> --pin <libft8 sha256> --v5-max <0.05 PC | 0.01 sol>
  python mb_analysis.py compare <raw dir A> <raw dir B> <out json>        # V8: per cycle, machine A's outcomes (all kinds incl. provenance fields) equal machine B's

COMMITTED BEFORE ANY DECODE OF ANY ARM. THE BARS ARE THE CAPTAIN'S AND FROZEN (set by him 2026-10-24 before any decode, relayed in the Architect's Amendment 3; never moved):
    D_BAR_PP = 0.5   NET:  D-GO if CI_lo(NET) >= 0.5 pp; D-STOP if CI_hi(NET) < 0.5 pp; else D-OPEN.
    U_BAR    = 0.021 per cycle:  U'-OK if CI_hi(dU') <= 0.021; U'-FAIL if CI_lo(dU') > 0.021; else U'-OPEN.
  Statistics: block bootstrap, blocks of 40 consecutive cycles, B 10,000, seed 20261025; NET is a ratio estimator; dU' is the paired mean over cycles with ws > 0.
Rows:
  V1  DLL/.so pin equal at the start and end of every arm (status files: preflight_end_ok=1 and the pin).       V2  flags read back at start and end: REF cohfb=True cohms=False; MS and MS-repeat cohfb=True cohms=True; Deep; nhard 24; sign fix 1.
  V3  0 exceptions in every arm (run.csv).      V4  batches 1, 2, 3 identical MS vs REF per cycle, except cycles where an ORDINARY pass hit the cycle budget in exactly one arm.
  V5  cycles with any abandoned work <= --v5-max (0.05 on the PC, 0.01 on sol) in MS AND, on sol, in REF.
  V6  MS-repeat vs MS on the repeated cycles: the per-cycle outcome multiset identical, 0 unexplained (cycles explained by abandonment in either run are counted).
  V7  V3 untouched, as far as the replay can see it: per cycle, every batch-4 decode REF published is also published by MS (multiset inclusion), except abandonment-explained cycles; N/N.
      LIMIT: the replay's decodes carry no per-decode provenance (DecodeResult.Path is 2 for every fallback decode and Replay81 cannot reach the fallback rows), so 'MS has no V3-provenance decode REF lacks' is
      checked as: MS-only batch-4 decodes are reported (count) and the per-set CRC-valid counters (crcC1..N1) bound how many of them can come from a set.
Descriptive: NET and dU' by Test-B band, set wins per cycle by provenance counter, R10 counters, cost lines (fallback wall time per cycle median/p95/max, batch-4 publish time median/p95, margin to the 13 s budget), MS-repeat timing.
"""
import collections
import csv
import json
import math
import re
import sys

import numpy as np

D_BAR_PP = 0.5
U_BAR = 0.021
BLOCK = 40
B_BOOT = 10000
SEED = 20261025
CYCLE_BUDGET_MS = 13000.0
ORDINARY_ABANDON_THIRD = ("abandoned", "skipped-abandoned")
SHIM = 20260071
assert (D_BAR_PP, U_BAR, BLOCK, B_BOOT, SEED, SHIM) == (0.5, 0.021, 40, 10000, 20261025, 20260071)


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


def blocks_of(stamps):
    return {s: i // BLOCK for i, s in enumerate(stamps)}, int(math.ceil(len(stamps) / BLOCK))


def boot_ratio(num, den, stamps):
    bmap, nb = blocks_of(stamps)
    bn, bd = np.zeros(nb), np.zeros(nb)
    for s in stamps:
        bn[bmap[s]] += num[s]
        bd[bmap[s]] += den[s]
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, nb, size=(B_BOOT, nb))
    est = bn[idx].sum(1) / bd[idx].sum(1)
    return bn.sum() / bd.sum(), float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))


def d_row(ci_lo_pp, ci_hi_pp):
    return "D-GO" if ci_lo_pp >= D_BAR_PP else ("D-STOP" if ci_hi_pp < D_BAR_PP else "D-OPEN")


def u_row(ci_lo, ci_hi):
    return "U'-OK" if ci_hi <= U_BAR else ("U'-FAIL" if ci_lo > U_BAR else "U'-OPEN")


def load_outcomes(path):
    d = collections.defaultdict(list)
    for r in csv.reader(open(path, newline="", encoding="utf-8")):
        if len(r) >= 7:
            d[r[0]].append((r[1], r[3], r[4], r[5], r[6]))            # kind, freq, dt, snr, path
    return d


def load_testb(path):
    nc, nc_band = collections.defaultdict(float), collections.defaultdict(float)
    ws = {}
    for r in rows(path):
        s, k, b, n, c = r["stamp"], r["kind"], r["band"], int(r["n"]), int(r["corroborated"])
        if k == "ws":
            ws[s] = (n, c)
        elif len(b) == 1 and b in "ABCD":
            nc[s] += n - c
            nc_band[(s, b)] += n - c
    return ws, nc, nc_band


def load_uprime(path):
    return {r["stamp"]: int(r["tested_absent"]) + int(r["hashed_or_unencodable"]) + int(r["untestable_class"]) for r in rows(path)}


def load_arm(raw, arm):
    return dict(out=load_outcomes(f"{raw}/{arm}/outcomes.csv"), tb=load_testb(f"{raw}/{arm}/testb.csv"), run={r["stamp"]: r for r in rows(f"{raw}/{arm}/run.csv")},
                ab={r["stamp"]: r for r in rows(f"{raw}/{arm}/abandon.csv")}, th={r["stamp"]: r for r in rows(f"{raw}/{arm}/third.csv")},
                coh={r["stamp"]: r for r in rows(f"{raw}/{arm}/coh.csv")}, log=open(f"{raw}/{arm}/log.log", encoding="utf-8", errors="replace").read(),
                status=open(f"{raw}/{arm}_status.txt").read())


def ord_ab(R, a, s):
    return int(R[a]["ab"].get(s, {}).get("abandoned") or 0) == 1 or R[a]["th"].get(s, {}).get("outcome") in ORDINARY_ABANDON_THIRD


def fb_ab(R, a, s):
    return int(R[a]["coh"].get(s, {}).get("abandoned") or 0) > 0


def analyse(raw, out, pin, v5_max):
    R = {a: load_arm(raw, a) for a in ("ref", "ms", "msrep")}
    res = {"bars": {"D_bar_pp": D_BAR_PP, "U_bar": U_BAR}, "block": BLOCK, "B": B_BOOT, "seed": SEED, "pin": pin, "v5_max": v5_max}
    stamps = sorted(R["ref"]["run"])
    res["cycles"] = {a: len(R[a]["run"]) for a in R}
    res["cycle_sets_equal_ref_ms"] = set(R["ref"]["run"]) == set(R["ms"]["run"])
    ws_ref = R["ref"]["tb"][0]
    ref = [s for s in stamps if ws_ref.get(s, (0, 0))[0] > 0]
    res["cycles_with_ws_reference"] = len(ref)

    res["V1_pin"] = {a: {"preflight_end_ok": "preflight_end_ok=1" in R[a]["status"], "pin_in_status": pin in R[a]["status"]} for a in R}
    want = {"ref": ("True", "False"), "ms": ("True", "True"), "msrep": ("True", "True")}
    v2 = {}
    for a in R:
        ok = True
        for tag in ("start", "end"):
            m = re.search(rf"# readback {tag}[^\n]*", R[a]["log"])
            line = m.group(0) if m else ""
            ok &= (bool(line) and f"cohfb={want[a][0]}" in line and f"cohms={want[a][1]}" in line and "decodingDepth=Deep" in line and "nhard=24" in line
                   and "osdSignFixRead=1" in line and f"shim={SHIM}" in line)
        v2[a] = ok
    res["V2_readbacks"] = v2
    res["V3_exceptions"] = {a: sum(1 for r in R[a]["run"].values() if r["exception"]) for a in R}

    def rate_ab(a):
        k = [s for s in stamps if ord_ab(R, a, s) or fb_ab(R, a, s)]
        return {"abandoned_cycles": len(k), "n": len(stamps), "rate": len(k) / len(stamps), "wilson": wilson(len(k), len(stamps)),
                "ordinary_abandoned": sum(1 for s in stamps if ord_ab(R, a, s)), "fallback_abandoned": sum(1 for s in stamps if fb_ab(R, a, s))}
    v5 = {"ref": rate_ab("ref"), "ms": rate_ab("ms")}
    ref_needed = v5_max <= 0.01                      # sol: <= 1 % in REF and in MS (Amendment 3); the PC: <= 5 % in MS (step-4 V5)
    v5["verdict"] = "PASS" if (v5["ms"]["rate"] <= v5_max and (not ref_needed or v5["ref"]["rate"] <= v5_max)) else "FAIL"
    res["V5"] = v5

    def multi(arm, kind, s):
        return collections.Counter((f, d, n, p) for (k, f, d, n, p) in R[arm]["out"].get(s, []) if k == kind)
    exc = [s for s in stamps if ord_ab(R, "ref", s) != ord_ab(R, "ms", s)]
    diff = {k: [s for s in stamps if multi("ref", k, s) != multi("ms", k, s)] for k in ("b1", "b2", "b3")}
    unexpl = {k: [s for s in v if s not in set(exc)] for k, v in diff.items()}
    res["V4"] = {"differing_cycles": {k: len(v) for k, v in diff.items()}, "unexplained": {k: len(v) for k, v in unexpl.items()}, "ordinary_abandon_exception_cycles": len(exc),
                 "verdict": "PASS" if not any(unexpl.values()) else "FAIL"}

    rep = sorted(R["msrep"]["run"])
    def union(arm, s):
        return collections.Counter(R[arm]["out"].get(s, []))
    v6diff = [s for s in rep if union("ms", s) != union("msrep", s)]
    v6un = [s for s in v6diff if not (ord_ab(R, "ms", s) or ord_ab(R, "msrep", s) or fb_ab(R, "ms", s) or fb_ab(R, "msrep", s))]
    res["V6"] = {"n_repeated": len(rep), "differing": len(v6diff), "unexplained": len(v6un), "first": v6diff[:5], "verdict": "PASS" if not v6un else "FAIL"}

    def b4(arm, s):
        return collections.Counter((f, d, n, p) for (k, f, d, n, p) in R[arm]["out"].get(s, []) if k == "b4")
    missing, ms_only, v7_exc = [], 0, 0
    for s in stamps:
        r_, m_ = b4("ref", s), b4("ms", s)
        lost = r_ - m_
        ms_only += sum((m_ - r_).values())
        if lost:
            if fb_ab(R, "ref", s) != fb_ab(R, "ms", s) or ord_ab(R, "ref", s) != ord_ab(R, "ms", s):
                v7_exc += 1
            else:
                missing.append(s)
    res["V7"] = {"ref_b4_decodes_missing_in_ms_cycles": len(missing), "first": missing[:5], "abandonment_explained_cycles": v7_exc, "ms_only_b4_decodes": ms_only,
                 "verdict": "PASS" if not missing else "FAIL",
                 "limit": "no per-decode provenance in the replay: inclusion is checked, MS-only decodes are counted, not attributed"}

    W = {s: ws_ref[s][0] for s in ref}
    Mref = {s: R["ref"]["tb"][0][s][1] for s in ref}
    Mms = {s: R["ms"]["tb"][0][s][1] for s in ref}
    dM = {s: Mms[s] - Mref[s] for s in ref}
    net = boot_ratio(dM, W, ref)
    res["NET_pp"] = {"point": 100 * net[0], "lo": 100 * net[1], "hi": 100 * net[2], "sum_dM": sum(dM.values()), "sum_W": sum(W.values()),
                     "Mref_pct": 100 * sum(Mref.values()) / sum(W.values()), "Mms_pct": 100 * sum(Mms.values()) / sum(W.values()), "verdict": d_row(100 * net[1], 100 * net[2])}

    uref, ums = load_uprime(f"{raw}/ref/uprime_ref.json.percycle.csv"), load_uprime(f"{raw}/ms/uprime_ms.json.percycle.csv")
    ones = {s: 1.0 for s in ref}
    u = boot_ratio({s: float(ums.get(s, 0) - uref.get(s, 0)) for s in ref}, ones, ref)
    ncref, ncms = R["ref"]["tb"][1], R["ms"]["tb"][1]
    old = boot_ratio({s: ncms[s] - ncref[s] for s in ref}, ones, ref)
    res["U_prime"] = {"delta_point": u[0], "lo": u[1], "hi": u[2], "U_bar": U_BAR, "verdict": u_row(u[1], u[2]),
                      "U_prime_0_ref": sum(uref.get(s, 0) for s in ref) / len(ref), "U_prime_ms": sum(ums.get(s, 0) for s in ref) / len(ref),
                      "old_testb_delta_U_descriptive": {"point": old[0], "lo": old[1], "hi": old[2]},
                      "projected_half_width": 1.96 * math.sqrt(2 * max(sum(uref.get(s, 0) for s in ref) / len(ref), 1e-9) / len(ref))}
    res["delta_notconfirmed_by_band_descriptive"] = {b: {"sum": sum(R["ms"]["tb"][2][(s, b)] - R["ref"]["tb"][2][(s, b)] for s in ref)} for b in "ABCD"}

    def cost(a):
        coh = R[a]["coh"]
        pub4 = [s for s in stamps if coh.get(s, {}).get("batch4_published") == "1"]
        t4 = [float(coh[s]["batch4_publish_ms"]) for s in pub4]
        wall = [float(coh[s]["fb_wall_ms"]) for s in stamps if coh.get(s, {}).get("fb_wall_ms") not in ("", None)]
        return {"cycles_with_fallback_run": len(wall), "fb_wall_ms": {"median": pct(wall, 50), "p95": pct(wall, 95), "max": max(wall) if wall else None},
                "batch4_published_cycles": len(pub4), "batch4_publish_ms": {"median": pct(t4, 50), "p95": pct(t4, 95), "max": max(t4) if t4 else None},
                "margin_to_budget_ms_min": (CYCLE_BUDGET_MS - max(t4)) if t4 else None}
    res["cost"] = {a: cost(a) for a in R}
    coh = R["ms"]["coh"]
    tot = lambda f: sum(int(coh[s][f] or 0) for s in stamps if coh.get(s, {}).get(f) not in ("", None))
    res["R10_counters_ms"] = {"walk_entered": tot("walk_entered"), "crc_c1": tot("crc_c1"), "crc_j2": tot("crc_j2"), "crc_j3": tot("crc_j3"), "crc_n1": tot("crc_n1"),
                              "eligible": tot("eligible"), "attempted": tot("attempted"), "crc_ok": tot("crc_ok"), "gated": tot("gated"), "published": tot("published")}
    res["validity_all_pass"] = bool(all(v["preflight_end_ok"] and v["pin_in_status"] for v in res["V1_pin"].values()) and all(res["V2_readbacks"].values())
                                    and not any(res["V3_exceptions"].values()) and res["V4"]["verdict"] == "PASS" and res["V5"]["verdict"] == "PASS"
                                    and res["V6"]["verdict"] == "PASS" and res["V7"]["verdict"] == "PASS")
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return 0


def compare(raw_a, raw_b, out):
    """V8: per cycle, machine A's outcomes equal machine B's, for ref and ms (all kinds b1..b4 with freq, dt, snr, path), except abandonment-explained cycles."""
    res = {"arms": {}}
    for arm in ("ref", "ms"):
        A, B = load_arm(raw_a, arm), load_arm(raw_b, arm)
        RA, RB = {arm: A}, {arm: B}
        sa, sb = set(A["run"]), set(B["run"])
        common = sorted(sa & sb)
        diff, explained = [], 0
        for s in common:
            if collections.Counter(A["out"].get(s, [])) != collections.Counter(B["out"].get(s, [])):
                if ord_ab(RA, arm, s) or ord_ab(RB, arm, s) or fb_ab(RA, arm, s) or fb_ab(RB, arm, s):
                    explained += 1
                else:
                    diff.append(s)
        res["arms"][arm] = {"cycles_a": len(sa), "cycles_b": len(sb), "common": len(common), "differing_unexplained": len(diff), "abandonment_explained": explained, "first_unexplained": diff[:5]}
    res["V8"] = "PASS" if all(v["differing_unexplained"] == 0 and v["common"] > 0 for v in res["arms"].values()) else "FAIL: unexplained differences go to the Architect"
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "compare":
        sys.exit(compare(sys.argv[2], sys.argv[3], sys.argv[4]))
    raw, out = sys.argv[1], sys.argv[2]
    pin = sys.argv[sys.argv.index("--pin") + 1]
    v5 = float(sys.argv[sys.argv.index("--v5-max") + 1])
    sys.exit(analyse(raw, out, pin, v5))
