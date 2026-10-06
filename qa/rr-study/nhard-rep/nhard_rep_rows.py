#!/usr/bin/env python
"""NHARD-REP: the pre-registered rows, computed AFTER the run, as code.

Spec (PRE-REGISTERED, Architect 2026-10-06 14:31Z + Amendment 1 15:01Z): qa/rr-study/2026-10-06-1430-architect-to-qa-spec-nhard-replication.md
(branch arch/nhard-replication). BAR_N = 0.5 pp was RATIFIED by the Captain 2026-10-06 ~14:34Z, before any datum, and is FROZEN.

Nothing here can be tuned while a run is going: nhard_rep_run.py only records raw per-cycle rows. Every threshold below is the
spec's, quoted with its section; none is QA's. Predicates are pure functions so tests/test_nhard_rep_rows.py can show that each
fires and does not fire on synthetic inputs (HK-021 (k): a row that fires the same way on both branches is decorative).

Loaders, the ratio-estimator block bootstrap, the autocorrelation and the Wilson interval are REUSED unchanged from the closed
onoff_replay_rows.py (same Test B file formats); only the constants, rows and verdict differ.

Arms (each a fresh process): N40, N60 (the sample), AA (second 40 over the first 200 sampled). AMENDMENT 2 (Architect 15:18Z): the
noise-based V2 FAILED validly (0 vs 0 decodes) and is RETIRED; row V2' probes the native OSD gate in each arm's own process instead.

Definitions (spec sections 4, 6, Amendment 1):
  W_i         WSJT-X decodes of sampled cycle i                (the 'ws' row of the testb file)
  M40_i, M60_i  matched WSJT-X decodes, batch 1 UNION batch 2, one-to-one (the 'ws' row's corroborated count)
  NET (pp)    = 100 * sum(M60 - M40) / sum(W);  95 % percentile NON-overlapping block bootstrap, block = 8 SAMPLED cycles, the last
                partial block kept, numerator and denominator resampled together, B = 10 000, seed 20261006.
  Verdict     N-LEVER iff CI_lo >= BAR_N;  N-CLOSED iff CI_hi < BAR_N;  N-OPEN otherwise. Exclusive, first match wins.
                Any validity-row FAIL => NO VERDICT, the rows are named.

  python qa/rr-study/nhard-rep/nhard_rep_rows.py [--out <artefacts rr_2026-10-06_nhard_rep>] [--results <tracked results dir>]
"""
import collections
import datetime
import hashlib
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "sub-feas"))
import onoff_replay_rows as O  # noqa: E402

# ---- spec constants (section and wording quoted; none is QA's) -----------------------------------------------------
BAR_N = 0.5                  # section 9 Q1, ratified by the Captain 2026-10-06: FROZEN for this arm
SEED = 20261006              # section 4
B_RESAMPLES = 10_000         # section 4
BLOCK_REGISTERED = 8         # Amendment 1: 8 sampled cycles
BLOCKS_REPORTED = (4, 16)    # Amendment 1: reported, not used for the verdict
ACF_LAGS = (1, 2, 8)         # Amendment 1
NOISE_CYCLES = 200           # the retired V2's noise set: descriptive only (Amendment 2)
V5_MAX_ABANDON = 0.05        # section 5 V5 (of SAMPLED cycles under Amendment 1)
V6_CYCLES = 200              # Amendment 1: the first 200 sampled cycles
V6_HALF_WINDOW = BAR_N / 2   # section 5 V6: CI(NET_AA) strictly inside (-BAR_N/2, +BAR_N/2)
TOP_BLOCKS = 5               # section 4 clustering report
CLUSTER_SHARE_FLAG = 0.5     # "more than half"
THREADS = "8"
DLL_PIN = "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365"   # shim 20260058 (libft8.version.txt, origin/main be3cc5ac)
SELECTION_SHA256 = "3cf04abb6b653bac5df70ce587ad48bd5d3bef7205eee6c040f8e2951cb13872"   # LF-normalised bytes of selection.json
PROBE_SHA256 = "bc914e99513a57f09b93f146ad18423d9836333eba41958174468b29b31e27b8"   # LF bytes of probe_vectors.json (Amendment 2)
ARMS = ("N40", "N60", "AA")
ARM_NHARD = {"N40": 40, "N60": 60, "AA": 40}
BANDS = O.BANDS
STAMP = re.compile(r"^\d{6}_\d{6}$")


# =====================================================================================================================
# loading
# =====================================================================================================================
def load_matched(path):
    """stamp -> frozenset of matched WSJT-X line indices (numeric; no text). Absent file => {}."""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        stamp, _, idx = line.partition(",")
        if STAMP.match(stamp):
            out[stamp] = frozenset(int(x) for x in idx.split(";") if x != "")
    return out


def arm_paths(out_dir, arm):
    return {k: os.path.join(out_dir, f"{k}_{arm}.{ext}") for k, ext in
            (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("probe", "csv"), ("log", "log"))}


def load_probe(path):
    """Rows of a harness probe file: when, vec, rc, path, crc_ok, payload_match (all numeric). Absent file => []."""
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        p = line.split(",")
        if len(p) >= 6 and p[2].lstrip("-").isdigit():
            out.append({"when": p[0], "vec": p[1], "rc": int(p[2]), "path": int(p[3]), "crc_ok": int(p[4]), "payload_match": p[5] == "1"})
    return out


# =====================================================================================================================
# estimand, interval, diagnostics
# =====================================================================================================================
def net_pp(W, M_base, M_arm):
    return O.net_pp(W, M_base, M_arm)


def ci(W, M_base, M_arm, block=BLOCK_REGISTERED):
    lo, hi, nb = O.block_bootstrap_ci(W, M_base, M_arm, block=block, B=B_RESAMPLES, seed=SEED)
    return lo, hi, nb


def verdict_row(ci_lo, ci_hi, bar=BAR_N):
    """Exclusive rows, first match wins (spec section 6)."""
    if ci_lo >= bar:
        return "N-LEVER"
    if ci_hi < bar:
        return "N-CLOSED"
    return "N-OPEN"


def cluster_report(d, block=BLOCK_REGISTERED, top=TOP_BLOCKS):
    """Spec section 4 (Amendment 1): distinct cycles with d != 0; the largest |sum d| in one block; the share of a POSITIVE sum d
    carried by the top-5 blocks (by block sum). share is None unless sum d > 0. flag iff share > 1/2."""
    d = [int(x) for x in d]
    sums = [sum(d[i:i + block]) for i in range(0, len(d), block)]
    total = sum(d)
    share = None
    if total > 0:
        share = sum(sorted(sums, reverse=True)[:top]) / total
    return {"distinct_cycles_nonzero": sum(1 for x in d if x != 0), "largest_abs_block_sum": max((abs(s) for s in sums), default=0),
            "n_blocks": len(sums), "sum_d": total, "top5_share_of_positive_sum": share,
            "flag_gt_half": bool(share is not None and share > CLUSTER_SHARE_FLAG)}


# =====================================================================================================================
# validity rows (pure predicates; spec section 5 + Amendment 1)
# =====================================================================================================================
def row_v1(pins, arms=ARMS):
    """V1: DLL actual == recorded, start and end, every arm. A missing record FAILS."""
    seen = {(p["arm"], p["when"]): p["libft8_sha256"] == DLL_PIN and p.get("pinned", DLL_PIN) == DLL_PIN for p in pins}
    need = [(a, w) for a in arms for w in ("start", "end")]
    bad = [f"{a}:{w}" for a, w in need if not seen.get((a, w), False)]
    return (not bad), {"checked": len(need), "failed_or_missing": bad}


def row_v2p(probes_by_arm, arms=ARMS):
    """V2' (Amendment 2; REPLACES the retired noise V2): the native OSD gate, probed through ft8_ldpc_decode_llrs INSIDE each corpus
    arm's own process after SetDecodeParams + warm-up ('start') and again after the last cycle ('end').
    PASS iff, at BOTH points, in EVERY arm: P_lo is accepted (rc 0, path 1, CRC 1, payload matches); and P_hi is accepted (same four
    conditions) in N60 and rejected (rc 0, path -1) in N40 and AA. Every row present must satisfy it (a restarted arm adds rows), and
    each (point, vector) must be present at least once: an arm that did not probe must never read as 'passed'.
    HK-025(k): if the cap did not reach the native gate, P_hi reads the same in N40 and N60 and this FAILS; if OSD were broken, P_lo FAILS."""
    bad, seen = [], {}
    for arm in arms:
        rows = probes_by_arm.get(arm, [])
        for r in rows:
            accepted = r["rc"] == 0 and r["path"] == 1 and r["crc_ok"] == 1 and r["payload_match"]
            if r["vec"] == "P_lo":
                ok = accepted
            elif r["vec"] == "P_hi":
                ok = accepted if ARM_NHARD[arm] == 60 else (r["rc"] == 0 and r["path"] == -1)
            else:
                ok = False
            if not ok:
                bad.append(f"{arm}:{r['when']}:{r['vec']} rc={r['rc']} path={r['path']} crc={r['crc_ok']} match={int(r['payload_match'])}")
        have = {(r["when"], r["vec"]) for r in rows}
        for w in ("start", "end"):
            for v in ("P_lo", "P_hi"):
                if (w, v) not in have:
                    bad.append(f"{arm}:{w}:{v} missing")
        seen[arm] = len(rows)
    return (not bad), {"problems": bad, "probe_rows": seen}


def row_v3(runrows, restarts, contained):
    return O.row_v3(runrows, restarts, contained)


def row_v4(readbacks, selection_sha, arms=ARMS, threads=THREADS, probe_sha=PROBE_SHA256):
    """V4: subtraction flag ON, thread count 8 and nhard (40/60 per arm) read back at START and END of every arm; selection.json
    SHA identical to the frozen value."""
    bad = []
    for arm in arms:
        rb = readbacks.get(arm, [])
        whens = {r["when"] for r in rb}
        if whens != {"start", "end"}:
            bad.append(f"{arm}: readback lines {sorted(whens)}")
            continue
        for r in rb:
            if r["subtractionEnabled"] is not True:
                bad.append(f"{arm}:{r['when']}: subtractionEnabled={r['subtractionEnabled']}")
            if r["threadsConfigured"] != threads or r["nhard"] != ARM_NHARD[arm]:
                bad.append(f"{arm}:{r['when']}: threads={r['threadsConfigured']} nhard={r['nhard']} (expected {ARM_NHARD[arm]})")
    if selection_sha != SELECTION_SHA256:
        bad.append("selection.json SHA differs from the frozen value")
    if probe_sha != PROBE_SHA256:
        bad.append("probe_vectors.json SHA differs from the frozen value")
    return (not bad), {"problems": bad}


def row_v5(abandon_by_arm, stamps):
    """V5: residual passes abandoned <= 5 % of SAMPLED cycles IN EACH corpus arm (N40, N60). A cycle missing from an abandon file
    FAILS the row (an absent file must never read as 'nothing abandoned')."""
    det, ok = {}, True
    for arm in ("N40", "N60"):
        a_ok, d = O.row_v5(abandon_by_arm.get(arm, {}), stamps)
        det[arm] = d
        ok = ok and a_ok
    return ok, det


def multiset_differences(out40, outAA, aa_stamps, ab40, abAA):
    """Amendment 2 (Architect, item 5): REPORTED, not gated. Per cycle, does the union (batch 1 + batch 2) numeric multiset of N40 differ
    from AA's? EXPLAINED = the residual pass was abandoned in exactly one of the two runs; anything else is UNEXPLAINED and goes in the
    report's FIRST paragraph."""
    empty = collections.Counter()
    expl, unexpl = [], []
    for s in aa_stamps:
        if out40.get(s, empty) == outAA.get(s, empty):
            continue
        a, b = ab40.get(s), abAA.get(s)
        (expl if (a is not None and b is not None and a["abandoned"] != b["abandoned"]) else unexpl).append(s)
    return {"n": len(aa_stamps), "differing": len(expl) + len(unexpl), "explained": len(expl), "unexplained": len(unexpl),
            "unexplained_stamps": unexpl}


def row_v6(W, M40, MAA, aa_stamps, ab40, abAA):
    """V6 (the instrument on real 'nothing': A/A). Over the first 200 sampled cycles, NET_AA = the section-4 statistic with AA in
    place of N60, against N40 on the same cycles, block bootstrap as in section 4.
    PASS iff exactly 200 cycles AND CI(NET_AA) lies STRICTLY inside (-BAR_N/2, +BAR_N/2) AND every per-cycle difference
    d_i = MAA_i - M40_i is either 0 or in a cycle whose residual pass was abandoned in EXACTLY ONE of the two runs ('explained').
    Any unexplained difference FAILS. A missing abandon record is unexplained."""
    n = len(aa_stamps)
    d = [int(b) - int(a) for a, b in zip(M40, MAA)]
    explained, unexplained = [], []
    for s, di in zip(aa_stamps, d):
        if di == 0:
            continue
        a, b = ab40.get(s), abAA.get(s)
        (explained if (a is not None and b is not None and a["abandoned"] != b["abandoned"]) else unexplained).append(s)
    lo, hi, nb = ci(W, M40, MAA)
    net = net_pp(W, M40, MAA)
    inside = (-V6_HALF_WINDOW < lo) and (hi < V6_HALF_WINDOW)
    ok = n == V6_CYCLES and inside and not unexplained
    return ok, {"n": n, "NET_AA_pp": net, "ci95": [lo, hi], "window": [-V6_HALF_WINDOW, V6_HALF_WINDOW], "ci_inside_window": inside,
                "n_blocks": nb, "cycles_d_nonzero": len(explained) + len(unexplained), "explained": len(explained),
                "unexplained": len(unexplained), "unexplained_stamps": unexplained, "explained_stamps": explained}


# =====================================================================================================================
# assembly
# =====================================================================================================================
def noise_descriptive(out_dir):
    """The RETIRED V2's result, kept as description (Amendment 2): decodes on the 200 white-noise cycles (RMS 0.20) at each cap, from the
    files moved to <out>/v2_retired/. None if they are absent."""
    res = {}
    for cap in (40, 60):
        rows = O.load_run_csv(os.path.join(out_dir, "v2_retired", f"run_V2N{cap}.csv"))
        res[f"n_false_{cap}"] = sum(r["decodes"] for r in rows if r["decodes"] > 0) if rows else None
        res[f"cycles_{cap}"] = len(rows)
    return res


def _sum_b(cy, kind, idx):
    return sum(cy[kind][b][idx] for b in BANDS)


def analyse(out_dir, results_dir=None, selection_path=None, ows_alltxt=None):
    selection_path = selection_path or os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
    sel_bytes = open(selection_path, "rb").read().replace(b"\r\n", b"\n")
    sel_sha = hashlib.sha256(sel_bytes).hexdigest()
    probe_path = os.path.join(HERE, "probe_vectors.json")
    probe_sha = hashlib.sha256(open(probe_path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()
    sel = json.loads(sel_bytes)
    run = sel["run"]
    stamps = sel["runs"][run]["SAMPLE"]
    aa_stamps = sel["runs"][run]["AA"]
    assert aa_stamps == stamps[:V6_CYCLES], "AA list is not the first 200 sampled cycles"

    P = {a: arm_paths(out_dir, a) for a in ARMS}
    outcomes = {a: O.load_outcomes(P[a]["outcomes"]) for a in ARMS}
    probes = {a: load_probe(P[a]["probe"]) for a in ARMS}
    abandon = {a: O.load_abandon(P[a]["abandon"]) for a in ARMS}
    testb = {a: O.load_testb(P[a]["testb"]) for a in ARMS}
    runrows = {a: O.load_run_csv(P[a]["run"]) for a in ARMS}
    logs = {a: O.parse_log(P[a]["log"]) for a in ARMS}
    matched = {a: load_matched(P[a]["matched"]) for a in ARMS}
    pins = O.load_pins(os.path.join(out_dir, "pins.jsonl"))
    restarts = collections.Counter()
    pe = os.path.join(out_dir, "process_exits.log")
    if os.path.exists(pe):
        for line in open(pe):
            m = re.match(r"\S+ (\w+) rc=(-?\d+) restart=(\d+)", line)
            if m and m.group(2) != "0":
                restarts[m.group(1)] += 1

    v = {}
    v["V1"] = row_v1(pins)
    v["V2P"] = row_v2p(probes)
    v["V3"] = row_v3({a: runrows[a] for a in ARMS}, restarts, {a: logs[a]["contained"] for a in ARMS})
    v["V4"] = row_v4({a: logs[a]["readback"] for a in ARMS}, sel_sha, probe_sha=probe_sha)
    v["V5"] = row_v5(abandon, stamps)

    present = [s for s in stamps if s in testb["N40"] and s in testb["N60"]]
    missing = [s for s in stamps if s not in testb["N40"] or s not in testb["N60"]]
    c40, c60 = testb["N40"], testb["N60"]
    W = [c40[s]["W"] for s in present]
    M40 = [c40[s]["M"] for s in present]
    M60 = [c60[s]["M"] for s in present]

    aa_present = [s for s in aa_stamps if s in testb["AA"] and s in c40]
    v["V6"] = row_v6([c40[s]["W"] for s in aa_present], [c40[s]["M"] for s in aa_present],
                     [testb["AA"][s]["M"] for s in aa_present], aa_present, abandon["N40"], abandon["AA"])
    msd = multiset_differences(O.union(outcomes["N40"], aa_stamps), O.union(outcomes["AA"], aa_stamps), aa_stamps,
                               abandon["N40"], abandon["AA"])
    if len(aa_present) != len(aa_stamps):   # a missing AA cycle must FAIL V6 whatever else holds
        v["V6"] = (False, {**v["V6"][1], "missing_aa_cycles": len(aa_stamps) - len(aa_present)})

    # instrument-consistency conditions (not spec rows; any failure also withholds the verdict, and says why)
    kg_ok, K, G = True, 0, 0
    for s in present:
        m40, m60 = matched["N40"].get(s), matched["N60"].get(s)
        if m40 is None or m60 is None or len(m40) != c40[s]["M"] or len(m60) != c60[s]["M"]:
            kg_ok = False
            continue
        K += len(m60 - m40)
        G += len(m40 - m60)
    consistency = {
        "all_sampled_cycles_present_in_N40_and_N60": (not missing, {"missing": len(missing)}),
        "wsjtx_W_identical_in_N40_and_N60": (all(c40[s]["W"] == c60[s]["W"] for s in present), {}),
        "M_equals_b1_plus_b2_matched": (all(c[s]["M"] == _sum_b(c[s], "b1", 1) + _sum_b(c[s], "b2", 1)
                                            for c in (c40, c60) for s in present), {}),
        "matched_index_sets_present_and_size_equal_M": (kg_ok, {}),
        "K_minus_G_equals_sum_d": (kg_ok and (K - G) == (sum(M60) - sum(M40)), {"K": K, "G": G}),
    }

    rows = {k: v[k] for k in ("V1", "V2P", "V3", "V4", "V5", "V6")}
    all_valid = all(ok for ok, _ in rows.values()) and all(ok for ok, _ in consistency.values())
    failing = [k for k, (ok, _) in {**rows, **consistency}.items() if not ok]
    result = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "numpy": np.__version__, "selection_sha256_lf": sel_sha, "n_sampled": len(stamps), "n_scored": len(present),
              "validity": {k: {"pass": ok, **d} for k, (ok, d) in rows.items()},
              "consistency": {k: {"pass": ok, **d} for k, (ok, d) in consistency.items()},
              "failing_rows": failing, "BAR_N_pp": BAR_N, "v6_multiset_differences_reported_not_gated": msd,
              "first_paragraph_flags": ([f"{msd['unexplained']} UNEXPLAINED multiset difference(s) between N40 and AA"]
                                        if msd["unexplained"] else [])}

    if present:
        d = [b - a for a, b in zip(M40, M60)]
        net = net_pp(W, M40, M60)
        lo, hi, nb = ci(W, M40, M60)
        result["estimand"] = {"NET_pp": net, "ci95": [lo, hi], "block": BLOCK_REGISTERED, "n_blocks": nb, "B": B_RESAMPLES, "seed": SEED,
                              "sum_W": int(sum(W)), "sum_M40": int(sum(M40)), "sum_M60": int(sum(M60))}
        result["cluster"] = cluster_report(d)
        if result["cluster"]["flag_gt_half"]:
            result["first_paragraph_flags"].append("top-5 blocks carry more than half of the positive sum d")
        result["reported_not_used"] = {"ci_by_block": {str(bk): list(ci(W, M40, M60, bk)[:2]) for bk in BLOCKS_REPORTED},
                                       "acf_of_d": O.acf(d, ACF_LAGS)}
        sW = float(sum(W))
        n40 = [_sum_b(c40[s], "b1", 0) + _sum_b(c40[s], "b2", 0) for s in present]
        n60 = [_sum_b(c60[s], "b1", 0) + _sum_b(c60[s], "b2", 0) for s in present]
        nc40 = [a - b for a, b in zip(n40, M40)]
        nc60 = [a - b for a, b in zip(n60, M60)]
        band = {}
        for b in BANDS:
            row = {}
            for arm, c in (("40", c40), ("60", c60)):
                n = sum(c[s]["b1"][b][0] + c[s]["b2"][b][0] for s in present)
                m = sum(c[s]["b1"][b][1] + c[s]["b2"][b][1] for s in present)
                w = O.wilson(n - m, n)
                row[arm] = {"n": n, "not_confirmed": n - m, "not_confirmed_rate": ((n - m) / n if n else None),
                            "wilson95": [round(w[0], 4), round(w[1], 4)] if n else None}
            band[b] = row
        d_nc = sum(nc60) - sum(nc40)
        result["descriptive"] = {
            "K_confirmed_at_60_absent_at_40": K, "G_confirmed_at_40_absent_at_60": G, "K_minus_G": K - G,
            "not_confirmed_per_cycle": {"40": sum(nc40) / len(present), "60": sum(nc60) / len(present),
                                        "sum40": int(sum(nc40)), "sum60": int(sum(nc60))},
            "not_confirmed_by_ows_snr_band": band,
            "exchange_rate_extra_confirmed_per_extra_not_confirmed": ((sum(M60) - sum(M40)) / d_nc if d_nc > 0 else None),
            "NET_by_batch_pp": {kind: 100.0 * sum(c60[s][kind][b][1] - c40[s][kind][b][1] for s in present for b in BANDS) / sW
                                for kind in ("b1", "b2")},
            "retired_v2_noise_descriptive": noise_descriptive(out_dir),
            "replay_fidelity_N40_vs_live_ows": None}
        if ows_alltxt and os.path.exists(ows_alltxt):
            live = O.count_stamps_in_alltxt(ows_alltxt, present)
            diffs = [a - live.get(s, 0) for a, s in zip(n40, present)]
            result["descriptive"]["replay_fidelity_N40_vs_live_ows"] = {
                "mean_diff_replay_minus_live": sum(diffs) / len(diffs), "cycles_equal": sum(1 for x in diffs if x == 0),
                "n": len(diffs), "sum_replay": int(sum(n40)), "sum_live": int(sum(live.get(s, 0) for s in present))}
        if all_valid:
            result["verdict"] = verdict_row(lo, hi)
        else:
            result["verdict"] = "NO VERDICT"
            result["verdict_withheld_because"] = failing
        # numeric per-cycle table (spec section 8.4)
        cols = ["stamp", "W", "n40_b1", "n40_b2", "n60_b1", "n60_b2", "M40", "M60", "M40_b1", "M40_b2", "M60_b1", "M60_b2",
                "nc40", "nc60", "abandon40", "abandon60"]
        with open(os.path.join(out_dir, "per_cycle.csv"), "w", newline="\n") as fh:
            fh.write(",".join(cols) + "\n")
            for i, s in enumerate(present):
                x, y = c40[s], c60[s]
                fh.write(",".join(str(t) for t in (
                    s, W[i], _sum_b(x, "b1", 0), _sum_b(x, "b2", 0), _sum_b(y, "b1", 0), _sum_b(y, "b2", 0), M40[i], M60[i],
                    _sum_b(x, "b1", 1), _sum_b(x, "b2", 1), _sum_b(y, "b1", 1), _sum_b(y, "b2", 1), nc40[i], nc60[i],
                    int(bool(abandon["N40"].get(s, {}).get("abandoned"))), int(bool(abandon["N60"].get(s, {}).get("abandoned"))))) + "\n")
    else:
        result["verdict"] = "NO VERDICT"
        result["verdict_withheld_because"] = failing or ["no scored cycles"]

    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(result, open(os.path.join(results_dir, "rows.json"), "w"), indent=1, sort_keys=True, default=str)
    return result


def main(argv):
    import argparse
    art = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(art, "rr_2026-10-06_nhard_rep"))
    ap.add_argument("--results", default=os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep"))
    ap.add_argument("--ows-alltxt", default=os.path.join(art, "20261004_1634_endurance_run-gathered", "owsfz", "ALL.TXT"))
    a = ap.parse_args(argv)
    res = analyse(a.out, a.results, ows_alltxt=a.ows_alltxt)
    print(json.dumps({k: res[k] for k in ("verdict", "failing_rows", "estimand", "cluster") if k in res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
