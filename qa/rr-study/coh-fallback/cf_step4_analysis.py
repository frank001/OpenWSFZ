#!/usr/bin/env python3
"""COH-FALLBACK step 4 replay analysis (spec section 14 A14.4, 15 A15.1-A15.3, 16, 17, 18). Numbers only: no message text is read.
  python cf_step4_analysis.py <raw dir with off/ on/ onrep/> <out json> <U_prime_max>

COMMITTED BEFORE ANY ON DECODE. Every bar is pre-registered in the spec; U_prime_max is a REQUIRED argument (the Captain's frozen value, from the freeze note) and is echoed in the output.
Rows:
  V1  pins: status.txt of each arm has preflight_end_ok=1 and the same DLL hash at start.      V2  flags read back (log.log '# readback' start/end): OFF False, ON/ON-repeat True; Deep; nhard 24; OSD fix 1.
  V3  0 exceptions (run.csv) in every arm.                                                      V5  abandonment <= 5 % of ON cycles (ordinary pass, third pass or fallback), Wilson CI.
  V6  ON-repeat vs ON on the repeated cycles: outcomes (kind, freq, dt, snr, path) identical, 0 unexplained (abandonment-explained counted).
  A3'' (a)  batches 1, 2, 3 identical ON vs OFF per cycle; the ONLY exception: an ORDINARY pass (residual or third) hit the cycle budget in exactly one arm (abandon.csv / third.csv), counted and listed.
  A3'' (b)  median of the SIGNED (ON - OFF) publish time, batch 2 and batch 3 separately, on cycles where BOTH arms published that batch; block-40 bootstrap, B 10,000, seed 20261007;
            FAIL if CI_lo > 50 ms for either batch; PASS if CI_hi <= 50 ms for both; else OPEN. p95 with its CI is descriptive, beside the ON-repeat vs ON p95.
  S4-T      descriptive: batch-4 publish time from decode start (median, p95, max, margin to the 13 s budget) and the fallback wall time; population counts (both / ON-only / OFF-only / neither).
  D-GO'     CI_lo(NET) >= 1.0 pp (BAR_G): ratio estimator, paired, ws > 0 cycles.     D-STOP: CI_hi < 1.0.    else D-OPEN.
  U'        Delta-U' = mean over ws > 0 cycles of (U'_on - U'_off), paired, block-40 bootstrap: U'-OK if CI_hi <= U_prime_max; U'-FAIL if CI_lo > U_prime_max; else U'-OPEN.
            The old Test-B Delta-U is reported beside it, descriptive only.
"""
import collections
import csv
import json
import math
import re
import sys

import numpy as np

BAR_G_PP = 1.0
V5_MAX = 0.05
A3B_BAR_MS = 50.0
BLOCK = 40
B_BOOT = 10000
SEED = 20261007
PATH_FALLBACK = "2"
CYCLE_BUDGET_MS = 13000.0
ORDINARY_ABANDON_THIRD = ("abandoned", "skipped-abandoned")
EXPECT_PIN_START = "aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef"


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


def boot_stat(per_cycle, stamps, stat):
    """per_cycle: stamp -> list of values (may be empty). Resample whole blocks of BLOCK consecutive selected cycles; stat over the pooled values."""
    bmap, nb = blocks_of(stamps)
    pools = [[] for _ in range(nb)]
    for s in stamps:
        pools[bmap[s]].extend(per_cycle.get(s, []))
    allv = [v for p in pools for v in p]
    if not allv:
        return (float("nan"),) * 3
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, nb, size=(B_BOOT, nb))
    est = np.empty(B_BOOT)
    for i in range(B_BOOT):
        pooled = [v for j in idx[i] for v in pools[j]]
        est[i] = stat(pooled) if pooled else np.nan
    return stat(allv), float(np.nanpercentile(est, 2.5)), float(np.nanpercentile(est, 97.5))


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


def load_outcomes(path):
    d = collections.defaultdict(list)
    for r in csv.reader(open(path, newline="", encoding="utf-8")):
        if len(r) >= 7:
            d[r[0]].append((r[1], r[3], r[4], r[5], r[6]))            # kind, freq, dt, snr, path
    return d


def load_testb(path):
    nc, nc_band, n_kind, nc_kind, band_kind = (collections.defaultdict(float) for _ in range(5))
    ws = {}
    for r in rows(path):
        s, k, b, n, c = r["stamp"], r["kind"], r["band"], int(r["n"]), int(r["corroborated"])
        if k == "ws":
            ws[s] = (n, c)
        elif len(b) == 1 and b in "ABCD":
            nc[s] += n - c
            nc_band[(s, b)] += n - c
            n_kind[(s, k)] += n
            nc_kind[(s, k)] += n - c
            band_kind[(k, b, "n")] += n
            band_kind[(k, b, "nc")] += n - c
    return ws, nc, nc_band, n_kind, nc_kind, band_kind


def load_uprime(path):
    d = {}
    for r in rows(path):
        d[r["stamp"]] = int(r["tested_absent"]) + int(r["hashed_or_unencodable"]) + int(r["untestable_class"])
    return d


def main():
    raw, out, u_max = sys.argv[1], sys.argv[2], float(sys.argv[3])
    R = {}
    for arm in ("off", "on", "onrep"):
        R[arm] = dict(out=load_outcomes(f"{raw}/{arm}/outcomes.csv"), tb=load_testb(f"{raw}/{arm}/testb.csv"), run={r["stamp"]: r for r in rows(f"{raw}/{arm}/run.csv")},
                      ab={r["stamp"]: r for r in rows(f"{raw}/{arm}/abandon.csv")}, th={r["stamp"]: r for r in rows(f"{raw}/{arm}/third.csv")},
                      coh={r["stamp"]: r for r in rows(f"{raw}/{arm}/coh.csv")}, log=open(f"{raw}/{arm}/log.log", encoding="utf-8", errors="replace").read(),
                      status=open(f"{raw}/{arm}_status.txt").read())
    res = {"U_prime_max": u_max, "block": BLOCK, "B": B_BOOT, "seed": SEED}
    stamps = sorted(R["off"]["run"])
    res["cycles"] = {a: len(R[a]["run"]) for a in R}
    res["cycle_sets_equal_off_on"] = set(R["off"]["run"]) == set(R["on"]["run"])
    ws_off = R["off"]["tb"][0]
    ref = [s for s in stamps if ws_off.get(s, (0, 0))[0] > 0]
    res["cycles_with_ws_reference"] = len(ref)

    # V1 / V2 / V3
    res["V1_pin"] = {a: {"preflight_end_ok": "preflight_end_ok=1" in R[a]["status"], "dll_at_start_equals_pin": EXPECT_PIN_START in R[a]["status"]} for a in R}
    want = {"off": "False", "on": "True", "onrep": "True"}
    v2 = {}
    for a in R:
        ok = True
        for tag in ("start", "end"):
            m = re.search(rf"# readback {tag}[^\n]*", R[a]["log"])
            line = m.group(0) if m else ""
            ok &= bool(line) and f"cohfb={want[a]}" in line and "decodingDepth=Deep" in line and "nhard=24" in line and "osdSignFixRead=1" in line and "shim=20260069" in line
        v2[a] = ok
    res["V2_readbacks"] = v2
    res["V3_exceptions"] = {a: sum(1 for r in R[a]["run"].values() if r["exception"]) for a in R}

    # ordinary-pass budget abandonment and any-abandonment per arm
    def ord_ab(a, s):
        return int(R[a]["ab"].get(s, {}).get("abandoned") or 0) == 1 or R[a]["th"].get(s, {}).get("outcome") in ORDINARY_ABANDON_THIRD
    def fb_ab(a, s):
        return int(R[a]["coh"].get(s, {}).get("abandoned") or 0) > 0
    # V5
    k5 = [s for s in stamps if ord_ab("on", s) or fb_ab("on", s)]
    res["V5"] = {"abandoned_cycles": len(k5), "n": len(stamps), "rate": len(k5) / len(stamps), "wilson": wilson(len(k5), len(stamps)),
                 "ordinary_abandoned": sum(1 for s in stamps if ord_ab("on", s)), "fallback_abandoned": sum(1 for s in stamps if fb_ab("on", s)),
                 "verdict": "PASS" if len(k5) / len(stamps) <= V5_MAX else "FAIL"}

    # A3'' (a)
    def multi(arm, kind, s):
        return collections.Counter((f, d, n, p) for (k, f, d, n, p) in R[arm]["out"].get(s, []) if k == kind)
    exc = [s for s in stamps if ord_ab("off", s) != ord_ab("on", s)]
    diff = {k: [s for s in stamps if multi("off", k, s) != multi("on", k, s)] for k in ("b1", "b2", "b3")}
    unexpl = {k: [s for s in v if s not in set(exc)] for k, v in diff.items()}
    a3a_ok = not any(unexpl.values())
    # A3'' (b): signed ON - OFF publish time, both-published cycles
    def pub(arm, s, col):
        v = R[arm]["run"].get(s, {}).get(col, "")
        return float(v) if v not in ("", None) and float(v) >= 0 else None
    def deltas(col, a, b):
        return {s: ([pub(a, s, col) - pub(b, s, col)] if pub(a, s, col) is not None and pub(b, s, col) is not None else []) for s in stamps}
    pop = {}
    b_rows = {}
    for batch, col in (("batch2", "tb2_ms"), ("batch3", "tb3_ms")):
        d = deltas(col, "on", "off")
        n_both = sum(1 for s in stamps if d[s])
        pop[batch] = {"both": n_both, "on_only": sum(1 for s in stamps if pub("on", s, col) is not None and pub("off", s, col) is None),
                      "off_only": sum(1 for s in stamps if pub("off", s, col) is not None and pub("on", s, col) is None),
                      "neither": sum(1 for s in stamps if pub("on", s, col) is None and pub("off", s, col) is None)}
        med = boot_stat(d, stamps, lambda v: float(np.median(v)))
        p95 = boot_stat(d, stamps, lambda v: float(np.percentile(v, 95)))
        dn = deltas(col, "onrep", "on")
        p95n = boot_stat(dn, stamps, lambda v: float(np.percentile(v, 95))) if any(dn[s] for s in stamps) else (float("nan"),) * 3
        b_rows[batch] = {"n_both_published": n_both, "median_on_minus_off_ms": med[0], "median_ci": [med[1], med[2]],
                         "p95_on_minus_off_ms_descriptive": p95[0], "p95_ci": [p95[1], p95[2]], "p95_onrep_minus_on_ms_descriptive": p95n[0], "p95_noise_ci": [p95n[1], p95n[2]]}
    fail_b = any(b_rows[b]["median_ci"][0] > A3B_BAR_MS for b in b_rows)
    pass_b = all(b_rows[b]["median_ci"][1] <= A3B_BAR_MS for b in b_rows)
    a3b = "FAIL" if fail_b else ("PASS" if pass_b else "OPEN")
    res["A3pp"] = {"a_differing_cycles": {k: len(v) for k, v in diff.items()}, "a_unexplained": {k: len(v) for k, v in unexpl.items()},
                   "ordinary_abandon_exception_cycles": len(exc), "ordinary_abandon_exception_stamps": exc[:20], "a_verdict": "PASS" if a3a_ok else "FAIL",
                   "b": b_rows, "b_bar_ms": A3B_BAR_MS, "b_verdict": a3b, "population": pop,
                   "verdict": "FAIL" if (not a3a_ok or a3b == "FAIL") else ("PASS" if a3b == "PASS" else "OPEN")}

    # S4-T
    coh = R["on"]["coh"]
    pub4 = [s for s in stamps if coh.get(s, {}).get("batch4_published") == "1"]
    t4 = [float(coh[s]["batch4_publish_ms"]) for s in pub4]
    wall = [float(coh[s]["fb_wall_ms"]) for s in stamps if coh.get(s, {}).get("fb_wall_ms") not in ("", None)]
    st = [float(coh[s]["fb_start_ms"]) for s in stamps if coh.get(s, {}).get("fb_start_ms") not in ("", None)]
    res["S4T"] = {"cycles_with_fallback_run": len(wall), "batch4_published_cycles": len(pub4), "batch4_not_published_cycles": len(wall) - len(pub4),
                  "batch4_publish_ms_from_decode_start": {"median": pct(t4, 50), "p95": pct(t4, 95), "max": max(t4) if t4 else None},
                  "margin_to_budget_ms_min": (CYCLE_BUDGET_MS - max(t4)) if t4 else None,
                  "fb_wall_ms": {"median": pct(wall, 50), "p95": pct(wall, 95), "max": max(wall) if wall else None},
                  "fb_start_ms": {"median": pct(st, 50), "p95": pct(st, 95)},
                  "workers": sorted(set(coh[s]["workers"] for s in stamps if coh.get(s, {}).get("workers"))),
                  "SG2_median_wall_le_500ms": (pct(wall, 50) <= 500.0) if wall else None,
                  "reply_guard_misses": "NOT REPORTED: the replay records time from decode start, not the live decode-start offset (A14.4/A2.2)"}

    # V6
    rep = sorted(R["onrep"]["run"])
    def union(arm, s):
        return collections.Counter(R[arm]["out"].get(s, []))
    v6diff = [s for s in rep if union("on", s) != union("onrep", s)]
    v6un = [s for s in v6diff if not (ord_ab("on", s) or ord_ab("onrep", s) or fb_ab("on", s) or fb_ab("onrep", s))]
    res["V6"] = {"n_repeated": len(rep), "differing": len(v6diff), "unexplained": len(v6un), "first": v6diff[:5], "verdict": "PASS" if not v6un else "FAIL"}

    # D-GO': NET paired against the OFF arm
    W = {s: ws_off[s][0] for s in ref}
    Moff = {s: R["off"]["tb"][0][s][1] for s in ref}
    Mon = {s: R["on"]["tb"][0][s][1] for s in ref}
    dM = {s: Mon[s] - Moff[s] for s in ref}
    net = boot_ratio(dM, W, ref)
    res["NET_pp"] = {"point": 100 * net[0], "lo": 100 * net[1], "hi": 100 * net[2], "sum_dM": sum(dM.values()), "sum_W": sum(W.values()),
                     "Moff_pct": 100 * sum(Moff.values()) / sum(W.values()), "Mon_pct": 100 * sum(Mon.values()) / sum(W.values()),
                     "verdict": "D-GO'" if 100 * net[1] >= BAR_G_PP else ("D-STOP" if 100 * net[2] < BAR_G_PP else "D-OPEN")}

    # U'
    uoff, uon = load_uprime(f"{raw}/off/uprime_off.json.percycle.csv"), load_uprime(f"{raw}/on/uprime_on.json.percycle.csv")
    dU = {s: [uon.get(s, 0) - uoff.get(s, 0)] for s in ref}
    bmap, nb = blocks_of(ref)
    ones = {s: 1.0 for s in ref}
    num = {s: float(dU[s][0]) for s in ref}
    u = boot_ratio(num, ones, ref)
    verdict = "U'-OK" if u[2] <= u_max else ("U'-FAIL" if u[1] > u_max else "U'-OPEN")
    ncoff, ncon = R["off"]["tb"][1], R["on"]["tb"][1]
    old = boot_ratio({s: ncon[s] - ncoff[s] for s in ref}, ones, ref)
    res["U_prime"] = {"delta_point": u[0], "lo": u[1], "hi": u[2], "U_prime_max": u_max, "verdict": verdict,
                      "U_prime_0_off": sum(uoff.get(s, 0) for s in ref) / len(ref), "U_prime_on": sum(uon.get(s, 0) for s in ref) / len(ref),
                      "old_testb_delta_U_descriptive": {"point": old[0], "lo": old[1], "hi": old[2]}}
    band = {}
    for b in "ABCD":
        d = {s: R["on"]["tb"][2][(s, b)] - R["off"]["tb"][2][(s, b)] for s in ref}
        band[b] = {"delta_notconfirmed_per_cycle": sum(d.values()) / len(ref), "sum": sum(d.values())}
    res["delta_notconfirmed_by_band_descriptive"] = band

    # descriptive: batch 4 content, R12' counters, FP-watch (batch 4 not-confirmed rate against batch 1's)
    tot = lambda f: sum(int(coh[s][f] or 0) for s in ref if coh.get(s, {}).get(f) not in ("", None))
    n4 = sum(R["on"]["tb"][3][(s, "b4")] for s in ref)
    nc4 = sum(R["on"]["tb"][4][(s, "b4")] for s in ref)
    n1 = sum(R["off"]["tb"][3][(s, "b1")] for s in ref)
    nc1 = sum(R["off"]["tb"][4][(s, "b1")] for s in ref)
    w4, w1 = wilson(int(nc4), int(n4)), wilson(int(nc1), int(n1))
    res["fallback"] = {"eligible": tot("eligible"), "attempted": tot("attempted"), "crc_ok": tot("crc_ok"), "gated": tot("gated"), "published": tot("published"),
                       "published_edge": tot("published_edge"), "abandoned": tot("abandoned"),
                       "batch4_decodes_scored": n4, "batch4_not_confirmed": nc4, "batch4_by_band": {b: {"n": R["on"]["tb"][5][("b4", b, "n")], "nc": R["on"]["tb"][5][("b4", b, "nc")]} for b in "ABCD"}}
    res["FP_watch_descriptive"] = {"batch4_nc_rate": nc4 / n4 if n4 else None, "batch4_wilson": w4, "batch1_nc_rate": nc1 / n1, "batch1_wilson": w1, "flag": bool(n4 and w4[0] > w1[1])}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
