#!/usr/bin/env python
"""SUB-FEAS offline flag-OFF/ON replay: the pre-registered rows, computed AFTER the run, as code.

Spec (PRE-REGISTERED, Architect 2026-10-01 19:35Z): qa/rr-study/2026-10-01-1935-architect-to-qa-spec-sub-feas-offline-onoff-replay.md

Nothing here can be tuned while a run is going: onoff_replay_run.py only records raw per-cycle rows. Every threshold below is the
spec's, quoted with its section; none is QA's. Predicates are pure functions so tests/test_onoff_replay_rows.py can show that each
fires and does not fire on synthetic inputs (HK-021 (k): a row that fires the same way on both branches is decorative).

Inputs (all NUMERIC; written by the harness, no message text anywhere, HK-037):
  run_<ARM>.csv       run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n
  testb_<ARM>.csv     run,stamp,kind,band,n,corroborated        (kind b1 / b2 per SNR band A-D, and ws = WSJT-X rows of the cycle)
  outcomes_<ARM>.csv  stamp,kind,idx,freqHz,dt,snr              (kind b1 / b2)
  log_<ARM>.log       harness log: '# readback' lines and the aggregate 'Sub-feas residual pass' lines
  pins.jsonl          libft8.dll SHA-256 at the start and end of every arm
  selection.json      the frozen cycle list (LF-normalised SHA pinned)

Definitions (spec section 5, 6):
  W_i      WSJT-X decodes of cycle i (the 'ws' row of the testb file, 'counted as Test B counts its ws rows')
  M_off,i  matched decodes of the OFF arm;  M_on,i = matched decodes of the ON arm, the UNION of batch 1 and batch 2, matched one-to-one
           as a single set. In the testb file that is the 'ws' row's corroborated count (WSJT-X decodes matched), which equals the
           sum of the corroborated counts of b1 and b2 (checked as an instrument-consistency condition).
  NET (pp) = 100 * sum(M_on - M_off) / sum(W)
  CI       95 % percentile interval, non-overlapping BLOCK bootstrap over the frozen ordered list: block 40, the last partial block
           kept, numerator and denominator resampled together (ratio estimator), B = 10 000, seed 20261001.
  Verdict  D1 REPLICATED iff CI_lo >= 1.0; D2 NOT REPLICATED iff CI_hi < 1.0; D3 INCONCLUSIVE otherwise (the Stage 2 replication bar,
           NOT re-tuned). Validity rows V1..V6: any FAIL => no verdict is issued.

  python qa/rr-study/sub-feas/onoff_replay_rows.py [--out <artefacts rr_2026-10-01_onoff_replay>] [--results <tracked results dir>]
"""
import collections
import datetime
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# ---- spec constants (section and wording quoted; none is QA's) -----------------------------------------------------
SEED = 20261001            # section 5
B_RESAMPLES = 10_000       # section 5
BLOCK_REGISTERED = 40      # section 5: registered
BLOCKS_REPORTED = (20, 160)  # section 5: reported, not used for the verdict
ACF_LAGS = (1, 4, 40)      # section 5
ALPHA = 0.05               # 95 % interval
BAR_PP = 1.0               # section 6: the Stage 2 replication bar, set 2026-09-28, NOT re-tuned
V5_MAX_ABANDON = 0.05      # section 6, V5
V6_CYCLES = 160            # section 6, V6
BANDS = ("A", "B", "C", "D")   # Test B's SNR bands: A >= 0, B -10..-1, C -15..-11, D <= -16 dB
DLL_PIN = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
SELECTION_SHA256 = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"
WILSON_Z = 1.959963984540054
ARM_FILES = {"OFF": "OFF", "ON": "ON", "ONREP": "ONREP"}

SUBFEAS_RE = re.compile(r"Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(\w+) "
                        r"containedException=(\w+)", re.I)
READBACK_RE = re.compile(r"# readback (start|end) subtractionEnabled=(\w+) threadsConfigured=(\S+) threadsResolved=(\S+) "
                         r"cores=(\d+) nhard=(\d+)", re.I)
STAMP = re.compile(r"^\d{6}_\d{6}$")


# =====================================================================================================================
# loading (numeric files only)
# =====================================================================================================================
def load_testb(path):
    """stamp -> {'W': int, 'M': int, 'b1': {band: (n, c)}, 'b2': {band: (n, c)}}"""
    cyc = {}
    if not os.path.exists(path):
        return cyc
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        p = line.split(",")
        if len(p) < 6:
            continue
        _run, stamp, kind, band, n, c = p[:6]
        d = cyc.setdefault(stamp, {"W": 0, "M": 0, "b1": {b: (0, 0) for b in BANDS}, "b2": {b: (0, 0) for b in BANDS}})
        if kind == "ws":
            d["W"], d["M"] = int(n), int(c)
        elif kind in ("b1", "b2") and band in BANDS:
            d[kind][band] = (int(n), int(c))
    return cyc


def load_outcomes(path):
    """stamp -> {'b1': Counter((freq, dt, snr)), 'b2': Counter(...)}"""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8").read().splitlines():
        p = line.split(",")
        if len(p) < 6 or p[1] not in ("b1", "b2"):
            continue
        d = out.setdefault(p[0], {"b1": collections.Counter(), "b2": collections.Counter()})
        d[p[1]][(p[3], p[4], p[5])] += 1
    return out


def load_run_csv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        p = line.split(",")
        if len(p) >= 8:
            rows.append({"stamp": p[2], "flag": p[4], "elapsed_ms": float(p[5]), "decodes": int(p[6]), "exception": p[7],
                         "b1_n": int(p[9]) if len(p) > 9 and p[9] else -1, "b2_n": int(p[10]) if len(p) > 10 and p[10] else -1})
    return rows


def parse_log(path):
    """Aggregate lines only: the residual-pass abandon/contained counts and the '# readback' lines (flag, threads, nhard)."""
    res = {"passes": 0, "abandoned": 0, "contained": 0, "readback": []}
    if not os.path.exists(path):
        return res
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    # The harness decodes ONE discarded warm-up cycle per process start BEFORE it logs '# readback start'. Its residual-pass
    # line is not an included cycle, so counting begins at the start read-back (a log without one is counted whole).
    first = next((i for i, ln in enumerate(lines) if READBACK_RE.search(ln) and "# readback start" in ln), 0)
    for i, line in enumerate(lines):
        m = SUBFEAS_RE.search(line)
        if m and i < first:
            continue
        if "WARN-TEMPLATE Sub-feas residual pass failed" in line and i < first:
            continue
        if m:
            res["passes"] += 1
            res["abandoned"] += m.group(3).lower() == "true"
            res["contained"] += m.group(4).lower() == "true"
            continue
        if "WARN-TEMPLATE Sub-feas residual pass failed" in line:
            res["contained"] += 1
            continue
        m = READBACK_RE.search(line)
        if m:
            res["readback"].append({"when": m.group(1), "subtractionEnabled": m.group(2).lower() == "true",
                                    "threadsConfigured": m.group(3), "threadsResolved": m.group(4),
                                    "cores": int(m.group(5)), "nhard": int(m.group(6))})
    return res


def load_abandon(path):
    """stamp -> {'ran': bool, 'abandoned': bool, 'contained': bool}; written by the harness, one row per decoded cycle."""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        p = line.split(",")
        if len(p) >= 4 and STAMP.match(p[0]):
            out[p[0]] = {"ran": p[1] == "1", "abandoned": p[2] == "1", "contained": p[3] == "1"}
    return out


def load_pins(path):
    pins = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8").read().splitlines():
            if line.strip():
                pins.append(json.loads(line))
    return pins


def count_stamps_in_alltxt(path, stamps):
    """Counts per cycle from an ALL.TXT, reading ONLY the first field (the stamp). No text is read or kept (HK-037)."""
    want = set(stamps)
    c = collections.Counter()
    if not os.path.exists(path):
        return c
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            head = line.split(None, 1)
            if head and head[0] in want and STAMP.match(head[0]):
                c[head[0]] += 1
    return c


# =====================================================================================================================
# estimand, interval, diagnostics (pure)
# =====================================================================================================================
def net_pp(W, M_off, M_on):
    W, M_off, M_on = (np.asarray(x, dtype=float) for x in (W, M_off, M_on))
    return 100.0 * float((M_on - M_off).sum()) / float(W.sum())


def block_bootstrap_ci(W, M_off, M_on, block=BLOCK_REGISTERED, B=B_RESAMPLES, seed=SEED, alpha=ALPHA):
    """Non-overlapping block bootstrap of the ratio estimator, numerator and denominator resampled TOGETHER; the last partial
    block is kept as its own block. Returns (lo, hi) percentile bounds and the block count."""
    W, M_off, M_on = (np.asarray(x, dtype=float) for x in (W, M_off, M_on))
    d = M_on - M_off
    n = len(d)
    edges = list(range(0, n, block))
    num = np.array([d[i:i + block].sum() for i in edges])
    den = np.array([W[i:i + block].sum() for i in edges])
    nb = len(edges)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nb, size=(B, nb))
    ratio = 100.0 * num[idx].sum(axis=1) / den[idx].sum(axis=1)
    lo, hi = np.percentile(ratio, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi), nb


def acf(d, lags=ACF_LAGS):
    d = np.asarray(d, dtype=float)
    d = d - d.mean()
    den = float((d * d).sum())
    return {int(k): (float((d[:-k] * d[k:]).sum()) / den if den > 0 and len(d) > k else float("nan")) for k in lags}


def wilson(k, n, z=WILSON_Z):
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def verdict_row(ci_lo, ci_hi, bar=BAR_PP):
    """Exclusive rows D1/D2/D3 (spec section 6)."""
    if ci_lo >= bar:
        return "D1"
    if ci_hi < bar:
        return "D2"
    return "D3"


def fp_watch(b1, b2):
    """Per SNR band: FLAG iff CI_lo(batch-2 not-corroborated rate) > CI_hi(batch-1 not-corroborated rate) (Wilson 95 %).
    b1, b2: {band: (n, corroborated)} summed over cycles. A band with no decodes in either batch cannot flag."""
    out = {}
    for band in BANDS:
        n1, c1 = b1[band]
        n2, c2 = b2[band]
        w1 = wilson(n1 - c1, n1)
        w2 = wilson(n2 - c2, n2)
        flag = bool(n1 > 0 and n2 > 0 and w2[0] > w1[1])
        out[band] = {"b1_n": n1, "b1_notcorr": n1 - c1, "b2_n": n2, "b2_notcorr": n2 - c2,
                     "b1_ci": [round(w1[0], 4), round(w1[1], 4)] if n1 else None,
                     "b2_ci": [round(w2[0], 4), round(w2[1], 4)] if n2 else None, "FLAG": flag}
    return out


# =====================================================================================================================
# validity rows (pure predicates; spec section 6)
# =====================================================================================================================
def row_v1(pins, arms=("OFF", "ON", "ONREP")):
    """V1: DLL actual == pinned, start and end, all three runs."""
    seen = {(p["arm"], p["when"]): p["libft8_sha256"] == DLL_PIN and p.get("pinned", DLL_PIN) == DLL_PIN for p in pins}
    need = [(a, w) for a in arms for w in ("start", "end")]
    bad = [f"{a}:{w}" for a, w in need if not seen.get((a, w), False)]
    return (not bad), {"checked": len(need), "failed_or_missing": bad}


def row_v2(readbacks, selection_sha, arms_expected, threads="8", nhard=40):
    """V2: flags as in section 2 read back in every run; selection.json SHA identical in every run.
    readbacks: {arm: [readback dicts]}; OFF must read subtractionEnabled False, ON/ONREP True, threads 8, nhard 40, at start AND end."""
    bad = []
    for arm in arms_expected:
        rb = readbacks.get(arm, [])
        whens = {r["when"] for r in rb}
        if whens != {"start", "end"}:
            bad.append(f"{arm}: readback lines {sorted(whens)}")
            continue
        for r in rb:
            if r["subtractionEnabled"] != (arm != "OFF"):
                bad.append(f"{arm}:{r['when']}: subtractionEnabled={r['subtractionEnabled']}")
            if r["threadsConfigured"] != threads or r["nhard"] != nhard:
                bad.append(f"{arm}:{r['when']}: threads={r['threadsConfigured']} nhard={r['nhard']}")
    if selection_sha != SELECTION_SHA256:
        bad.append("selection.json SHA differs from the frozen value")
    return (not bad), {"problems": bad}


def row_v3(run_rows_by_arm, restarts_by_arm, contained_by_arm):
    """V3: 0 access violations, 0 contained exceptions, 0 non-zero exits, every run.
    exceptions: any row with a non-empty exception column (the harness catches and records the type)."""
    exc = {a: sum(1 for r in rows if r["exception"]) for a, rows in run_rows_by_arm.items()}
    bad = {a: {"exception_rows": exc[a], "restarts": restarts_by_arm.get(a, 0), "contained": contained_by_arm.get(a, 0)}
           for a in run_rows_by_arm if exc[a] or restarts_by_arm.get(a, 0) or contained_by_arm.get(a, 0)}
    return (not bad), {"nonzero": bad}


def row_v4(off_b1, on_b1, stamps):
    """V4: per included cycle, ON batch-1 numeric multiset (freqHz, dt, snr) == OFF multiset. PASS iff N/N."""
    empty = collections.Counter()
    equal = sum(1 for s in stamps if off_b1.get(s, empty) == on_b1.get(s, empty))
    return equal == len(stamps), {"equal": equal, "n": len(stamps)}


def row_v5(abandon_on, stamps):
    """V5: ON-arm residual passes abandoned <= 5 % of included cycles. Counted from the harness's per-cycle abandon file.
    A cycle missing from that file FAILS the row (an absent file must never read as 'nothing abandoned')."""
    n = len(stamps)
    missing = [s for s in stamps if s not in abandon_on]
    abandoned = sum(1 for s in stamps if abandon_on.get(s, {}).get("abandoned"))
    frac = abandoned / n if n else float("nan")
    ok = n > 0 and not missing and frac <= V5_MAX_ABANDON
    return ok, {"abandoned": abandoned, "included": n, "fraction": frac, "missing_from_abandon_file": len(missing)}


V6_MAX_EXPLAINED = 8   # Amendment 1 (Architect 2026-10-01, spec 9a): V5's 5 % of 160


def row_v6(on_union, rep_union, first160, abandon_on, abandon_rep):
    """V6 (AMENDMENT 1): over the first 160 included cycles, classify each cycle whose per-cycle UNION (b1 + b2 numeric multiset)
    differs between the ON arm and the ON-repeat.
      EXPLAINED   = the residual pass was deadline-abandoned in EXACTLY ONE of the two runs;
      UNEXPLAINED = anything else (both abandoned, neither abandoned, or no abandon record).
    PASS iff there are exactly 160 cycles AND unexplained == 0 AND explained <= 8."""
    empty = collections.Counter()
    mism = []
    for s in first160:
        if on_union.get(s, empty) == rep_union.get(s, empty):
            continue
        a, b = abandon_on.get(s), abandon_rep.get(s)
        flags = {"on_abandoned": None if a is None else a["abandoned"], "rep_abandoned": None if b is None else b["abandoned"]}
        explained = a is not None and b is not None and (a["abandoned"] != b["abandoned"])
        mism.append({"stamp": s, "class": "explained" if explained else "unexplained", **flags})
    n_expl = sum(1 for m in mism if m["class"] == "explained")
    n_unexpl = len(mism) - n_expl
    ok = len(first160) == V6_CYCLES and n_unexpl == 0 and n_expl <= V6_MAX_EXPLAINED
    return ok, {"n": len(first160), "identical": len(first160) - len(mism), "explained": n_expl, "unexplained": n_unexpl,
                "mismatching": mism, "explained_stamps": [m["stamp"] for m in mism if m["class"] == "explained"]}


def union(outcomes, stamps):
    out = {}
    for s in stamps:
        d = outcomes.get(s)
        out[s] = (d["b1"] + d["b2"]) if d else collections.Counter()
    return out


# =====================================================================================================================
# assembly
# =====================================================================================================================
def per_cycle_table(off, on, stamps):
    rows = []
    for s in stamps:
        o, n = off.get(s), on.get(s)
        if o is None or n is None:
            rows.append(None)
            continue
        rows.append({"stamp": s, "W": n["W"], "W_off": o["W"],
                     "n_off": sum(v[0] for v in o["b1"].values()),
                     "n_on_b1": sum(v[0] for v in n["b1"].values()), "n_on_b2": sum(v[0] for v in n["b2"].values()),
                     "M_off": o["M"], "M_on": n["M"],
                     "M_on_b1": sum(v[1] for v in n["b1"].values()), "M_on_b2": sum(v[1] for v in n["b2"].values()),
                     "off": o, "on": n})
    return rows


def sum_bands(table, arm, kind):
    tot = {b: [0, 0] for b in BANDS}
    for r in table:
        for b in BANDS:
            n, c = r[arm][kind][b]
            tot[b][0] += n
            tot[b][1] += c
    return {b: tuple(v) for b, v in tot.items()}


def analyse(out_dir, results_dir=None, selection_path=None, ows_alltxt=None):
    selection_path = selection_path or os.path.join(REPO, "qa", "rr-study", "results", "2026-10-01-sub-feas-offline-onoff-replay", "selection.json")
    sel_bytes = open(selection_path, "rb").read().replace(b"\r\n", b"\n")
    import hashlib
    sel_sha = hashlib.sha256(sel_bytes).hexdigest()
    sel = json.loads(sel_bytes)
    run = sel["run"]
    stamps = sel["runs"][run]["ALL"]
    first160 = sel["runs"][run]["V6"]

    arm_paths = {a: {k: os.path.join(out_dir, f"{k}_{a}.{ext}") for k, ext in
                     (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("log", "log"))}
                 for a in ARM_FILES}
    abandon = {a: load_abandon(p["abandon"]) for a, p in arm_paths.items()}
    testb = {a: load_testb(p["testb"]) for a, p in arm_paths.items()}
    outcomes = {a: load_outcomes(p["outcomes"]) for a, p in arm_paths.items()}
    runrows = {a: load_run_csv(p["run"]) for a, p in arm_paths.items()}
    logs = {a: parse_log(p["log"]) for a, p in arm_paths.items()}
    pins = load_pins(os.path.join(out_dir, "pins.jsonl"))
    restarts = collections.Counter()
    pe = os.path.join(out_dir, "process_exits.log")
    if os.path.exists(pe):
        for line in open(pe):
            m = re.match(r"\S+ (\w+) rc=(-?\d+) restart=(\d+)", line)
            if m and (m.group(2) != "0"):
                restarts[m.group(1)] += 1

    table_raw = per_cycle_table(testb["OFF"], testb["ON"], stamps)
    missing = [s for s, r in zip(stamps, table_raw) if r is None]
    table = [r for r in table_raw if r is not None]

    # ---- validity rows ---------------------------------------------------------------------------------------------
    v = {}
    v["V1"] = row_v1(pins)
    v["V2"] = row_v2({a: logs[a]["readback"] for a in ARM_FILES}, sel_sha, ("OFF", "ON", "ONREP"))
    v["V3"] = row_v3({a: runrows[a] for a in ARM_FILES}, restarts, {a: logs[a]["contained"] for a in ARM_FILES})
    off_b1 = {s: outcomes["OFF"].get(s, {}).get("b1", collections.Counter()) for s in stamps}
    on_b1 = {s: outcomes["ON"].get(s, {}).get("b1", collections.Counter()) for s in stamps}
    v["V4"] = row_v4(off_b1, on_b1, stamps)
    v["V5"] = row_v5(abandon["ON"], stamps)
    v["V6"] = row_v6(union(outcomes["ON"], first160), union(outcomes["ONREP"], first160), first160,
                     abandon["ON"], abandon["ONREP"])
    # instrument-consistency conditions (not spec rows; any failure also withholds the verdict, and says why)
    consistency = {
        "all_cycles_present_in_both_arms": (not missing, {"missing": len(missing)}),
        "wsjtx_W_identical_in_both_arms": (all(r["W"] == r["W_off"] for r in table), {}),
        "M_equals_b1_plus_b2_matched": (all(r["M_on"] == r["M_on_b1"] + r["M_on_b2"] for r in table), {}),
    }

    rows = {"V1": v["V1"], "V2": v["V2"], "V3": v["V3"], "V4": v["V4"], "V5": v["V5"], "V6": v["V6"]}
    all_valid = all(ok for ok, _ in rows.values()) and all(ok for ok, _ in consistency.values())
    failing = [k for k, (ok, _) in {**rows, **consistency}.items() if not ok]

    result = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "numpy": np.__version__, "selection_sha256_lf": sel_sha, "n_included": len(stamps), "n_scored": len(table),
              "validity": {k: {"pass": ok, **d} for k, (ok, d) in rows.items()},
              "consistency": {k: {"pass": ok, **d} for k, (ok, d) in consistency.items()},
              "failing_rows": failing}

    if table:
        W = [r["W"] for r in table]
        Moff = [r["M_off"] for r in table]
        Mon = [r["M_on"] for r in table]
        d = [a - b for a, b in zip(Mon, Moff)]
        net = net_pp(W, Moff, Mon)
        lo, hi, nb = block_bootstrap_ci(W, Moff, Mon, BLOCK_REGISTERED)
        result["estimand"] = {"NET_pp": net, "ci95": [lo, hi], "block": BLOCK_REGISTERED, "n_blocks": nb, "B": B_RESAMPLES,
                              "seed": SEED, "sum_W": int(sum(W)), "sum_M_off": int(sum(Moff)), "sum_M_on": int(sum(Mon)),
                              "sum_M_on_b1": int(sum(r["M_on_b1"] for r in table)), "sum_M_on_b2": int(sum(r["M_on_b2"] for r in table))}
        result["reported_not_used"] = {
            "ci_by_block": {str(bk): list(block_bootstrap_ci(W, Moff, Mon, bk)[:2]) for bk in BLOCKS_REPORTED},
            "acf_of_d": acf(d)}
        # Amendment 1: if V6 found explained mismatches, also give NET with those cycles dropped from BOTH arms (descriptive only).
        dropped = set(v["V6"][1].get("explained_stamps", []))
        if dropped:
            kept = [r for r in table if r["stamp"] not in dropped]
            if kept:
                kW, kOff, kOn = [r["W"] for r in kept], [r["M_off"] for r in kept], [r["M_on"] for r in kept]
                klo, khi, _ = block_bootstrap_ci(kW, kOff, kOn, BLOCK_REGISTERED)
                result["reported_not_used"]["net_without_v6_explained_cycles"] = {
                    "dropped": len(dropped), "NET_pp": net_pp(kW, kOff, kOn), "ci95": [klo, khi]}
        # descriptive, no bar
        band_net = {}
        sW = float(sum(W))
        for b in BANDS:
            c_on = sum(r["on"]["b1"][b][1] + r["on"]["b2"][b][1] for r in table)
            c_off = sum(r["off"]["b1"][b][1] for r in table)
            band_net[b] = 100.0 * (c_on - c_off) / sW
        result["descriptive"] = {
            "NET_by_ows_snr_band_pp": band_net,
            "batch2_decodes_per_cycle_mean": sum(r["n_on_b2"] for r in table) / len(table),
            "matched_by_batch": {"b1": int(sum(r["M_on_b1"] for r in table)), "b2": int(sum(r["M_on_b2"] for r in table))},
            "replay_fidelity_off_vs_live_ows": None}
        if ows_alltxt and os.path.exists(ows_alltxt):
            live = count_stamps_in_alltxt(ows_alltxt, [r["stamp"] for r in table])
            diffs = [r["n_off"] - live.get(r["stamp"], 0) for r in table]
            result["descriptive"]["replay_fidelity_off_vs_live_ows"] = {
                "mean_diff_off_minus_live": sum(diffs) / len(diffs), "cycles_equal": sum(1 for x in diffs if x == 0),
                "n": len(diffs), "sum_off": int(sum(r["n_off"] for r in table)), "sum_live": int(sum(live.get(r["stamp"], 0) for r in table))}
        result["fp_watch"] = fp_watch(sum_bands(table, "on", "b1"), sum_bands(table, "on", "b2"))
        if all_valid:
            result["verdict"] = verdict_row(lo, hi)
        else:
            result["verdict"] = "NO VERDICT"
            result["verdict_withheld_because"] = failing
    else:
        result["verdict"] = "NO VERDICT"
        result["verdict_withheld_because"] = failing or ["no scored cycles"]

    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(result, open(os.path.join(results_dir, "rows.json"), "w"), indent=1, sort_keys=True, default=str)
    # numeric per-cycle table (gitignored artefacts directory)
    if table:
        cols = ["stamp", "W", "n_off", "n_on_b1", "n_on_b2", "M_off", "M_on", "M_on_b1", "M_on_b2"]
        with open(os.path.join(out_dir, "per_cycle.csv"), "w", newline="\n") as fh:
            fh.write(",".join(cols) + "\n")
            for r in table:
                fh.write(",".join(str(r[c]) for c in cols) + "\n")
    return result


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts")),
                                                  "rr_2026-10-01_onoff_replay"))
    ap.add_argument("--results", default=os.path.join(REPO, "qa", "rr-study", "results", "2026-10-01-sub-feas-offline-onoff-replay"))
    ap.add_argument("--ows-alltxt", default=os.path.join(os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts")),
                                                         "20260930_1930_endurance_run-gathered", "owsfz", "ALL.TXT"))
    a = ap.parse_args(argv)
    res = analyse(a.out, a.results, ows_alltxt=a.ows_alltxt)
    print(json.dumps({k: res[k] for k in ("verdict", "failing_rows", "estimand") if k in res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
