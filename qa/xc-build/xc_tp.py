#!/usr/bin/env python3
"""XC-BUILD remedy, TR2: freeze T_P (and re-check T_E) from the TRAIN arm.  Spec section 13 A6.3 and QA's (k) review K1 to K4.  COUNTS ONLY out (HK-037): text is read inside functions, never written.
Usage:  python -I xc_tp.py run <TR2 arm dir> <TRAIN ALL.TXT> <out te.json> [<TR1 te.json for V-TE>]
        python -I xc_tp.py selftest
The TR2 arm dir holds probe.csv (the sink, one row per tested template), nc.tsv (the arm's decodes) and xc.csv.

THE RULE, fixed before any TR2 data (A6.3 + K2):
  population  live tests with S_E* >= T_E   (T_E from the shadow tests by xc_chain_tools.cmd_te rule: FA* = 0.021 / K, K = A5's tested median)
  unit        (cycle, text); its S_P = max S_P over that text's live tests in the population; its position = the argmax of that max test
  COR-like    a WSJT-X row of the cycle with the SAME text and |df| <= 10 Hz of the unit's argmax
  SUP-like    not COR-like, and a WSJT-X row of the cycle with a DIFFERENT text at |df| <= 3.125 Hz and |ddt - offset| <= 0.2 s (offset measured, K3)
  FREE-like   neither
  offset      median of (our dt - WSJT-X DT) over the COR-like units' matched rows; asserted within 0.05 s of 0.6 (K3); the window is centred on it
  T_P         numpy percentile(S_P of COR-like units, 10), linear interpolation
  V-TR-P      n(COR-like units) >= 100 else VOID
  V-TE (K4)   |T_E - 3.076041980658299| <= 1e-6 and 23,219 shadow tests, else STOP
Sink columns are named once, in COLUMNS, to be reconciled with the Developer's build (the first chain's sink had stamp, kind, s_e_star, prior_age_cycles, argmax_df_hz, argmax_dt_s)."""
from __future__ import annotations

import collections
import csv
import datetime
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xb_lib as XB  # noqa: E402

COLUMNS = {"stamp": "stamp", "kind": "kind", "s_e": "s_e_star", "s_p": "s_p", "age": "prior_age_cycles", "prior_f": "prior_freq_hz", "prior_dt": "prior_dt_s",
           "prior_batch": "prior_batch", "vetoed": "vetoed", "arg_df": "argmax_df_hz", "arg_dt": "argmax_dt_s"}
CYCLE_S = 15
DF_SUP, DDT_SUP, DF_COR = 3.125, 0.2, 10.0
DT_CONV, DT_CONV_TOL = 0.6, 0.05
JOIN_DT_TOL = 0.06                               # the sink's prior dt is the store's unrounded value; nc.tsv carries the published dt rounded to 0.1 s (error <= 0.05): found on the remedy dry run
PCTL_KEEP = 10                                   # T_P = the 10th percentile: keeps 90 % (a decision value, the keep fraction that sized the build, A6.3)
N_COR_MIN = 100                                  # V-TR-P
TE_TR1, N_SHADOW_TR1, TE_TOL = 3.076041980658299, 23219, 1e-6
assert (DF_SUP, DDT_SUP, DF_COR, DT_CONV, PCTL_KEEP, N_COR_MIN) == (3.125, 0.2, 10.0, 0.6, 10, 100)


def stamp_minus(stamp, cycles):
    t = datetime.datetime.strptime(stamp, "%y%m%d_%H%M%S") - datetime.timedelta(seconds=CYCLE_S * cycles)
    return t.strftime("%y%m%d_%H%M%S")


def load_wsjtx(alltxt, stamps):
    ref = collections.defaultdict(list)           # stamp -> [(freq, dt, text)]
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or f[0] not in stamps:
                continue
            try:
                int(f[4]); dt = float(f[5]); fr = int(f[6])
            except ValueError:
                continue
            ref[f[0]].append((fr, dt, " ".join(f[7:]).strip()))
    return ref


def load_nc_prior(path):
    """(stamp, kind, freq) -> [(published dt, text)] for the batch 1 to 5 rows; text stays here."""
    idx = collections.defaultdict(list)
    for line in open(path, encoding="utf-8", errors="replace"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 11 or int(f[1]) not in (1, 2, 3, 4, 5):
            continue
        idx[(f[0], int(f[1]), int(f[3]))].append((float(f[4]), f[10].strip()))
    return idx


def find_prior_text(idx, pstamp, batch, freq, dt):
    """K1 join: the distinct texts of the batch 1 to 5 rows of the prior's cycle at the same integer frequency whose published dt is within JOIN_DT_TOL of the sink's prior dt."""
    return sorted({t for d, t in idx.get((pstamp, batch, int(round(freq))), []) if abs(d - dt) <= JOIN_DT_TOL})


def units_from_sink(probe_csv, nc_index, t_e):
    """K1 + K2: one unit per (cycle, text) with the max S_P over its live tests at S_E* >= T_E.  Returns (units, mapping stats)."""
    best = {}
    stats = collections.Counter()
    for r in csv.DictReader(open(probe_csv, encoding="utf-8")):
        if r[COLUMNS["kind"]] != "live" or float(r[COLUMNS["s_e"]]) < t_e:
            continue
        stats["live_ge_te"] += 1
        pstamp = stamp_minus(r[COLUMNS["stamp"]], int(r[COLUMNS["age"]]))
        texts = find_prior_text(nc_index, pstamp, int(r[COLUMNS["prior_batch"]]), float(r[COLUMNS["prior_f"]]), float(r[COLUMNS["prior_dt"]]))
        if len(texts) != 1:
            stats["mapping_not_unique" if texts else "mapping_missing"] += 1
            continue
        stats["mapped"] += 1
        u = (r[COLUMNS["stamp"]], texts[0])
        sp = float(r[COLUMNS["s_p"]])
        if u not in best or sp > best[u]["s_p"]:
            best[u] = {"stamp": r[COLUMNS["stamp"]], "text": texts[0], "s_p": sp, "s_e": float(r[COLUMNS["s_e"]]),
                       "f": float(r[COLUMNS["prior_f"]]) + float(r[COLUMNS["arg_df"]]), "dt": float(r[COLUMNS["prior_dt"]]) + float(r[COLUMNS["arg_dt"]])}
    return list(best.values()), stats


def classify_units(units, ref):
    """K2/K3: COR-like, then the measured offset, then SUP-like / FREE-like.  Returns (class per unit, offset, offset check)."""
    cls, offs = [], []
    for u in units:
        w = ref.get(u["stamp"], [])
        same = [x for x in w if x[2] == u["text"] and abs(x[0] - u["f"]) <= DF_COR]
        if same:
            best = min(same, key=lambda x: abs(x[0] - u["f"]))
            offs.append(u["dt"] - best[1])
            cls.append("COR")
        else:
            cls.append(None)
    offset = float(np.median(offs)) if offs else float("nan")
    ok = bool(offs) and abs(offset - DT_CONV) <= DT_CONV_TOL
    for i, u in enumerate(units):
        if cls[i] == "COR":
            continue
        w = ref.get(u["stamp"], [])
        diff = [x for x in w if x[2] != u["text"] and abs(x[0] - u["f"]) <= DF_SUP and abs((u["dt"] - x[1]) - offset) <= DDT_SUP]
        cls[i] = "SUP" if diff else "FREE"
    return cls, offset, ok


def freeze(units, cls, offset, offset_ok, mapping, n_shadow, t_e, tr1_te=None):
    cor = np.array([u["s_p"] for u, c in zip(units, cls) if c == "COR"])
    sup = np.array([u["s_p"] for u, c in zip(units, cls) if c == "SUP"])
    free = np.array([u["s_p"] for u, c in zip(units, cls) if c == "FREE"])
    res = {"T_E": t_e, "n_shadow_tests": n_shadow, "mapping": dict(mapping), "units": len(units),
           "n_COR_like": int(cor.size), "n_SUP_like": int(sup.size), "n_FREE_like": int(free.size),
           "dt_offset_median_s": offset, "dt_offset_ok": offset_ok}
    res["V_TE"] = None if tr1_te is None else bool(abs(t_e - tr1_te) <= TE_TOL and n_shadow == N_SHADOW_TR1)
    res["V_TR_P"] = bool(cor.size >= N_COR_MIN)
    res["mapping_complete"] = bool(mapping.get("mapping_missing", 0) == 0 and mapping.get("mapping_not_unique", 0) == 0)
    if cor.size:
        tp = float(np.percentile(cor, PCTL_KEEP))
        res["T_P"] = tp
        res["descriptive"] = {"COR_kept": float((cor >= tp).mean()),
                              "SUP_removed": float((sup < tp).mean()) if sup.size else None,
                              "FREE_removed": float((free < tp).mean()) if free.size else None}
    else:
        res["T_P"] = None
    res["valid"] = bool(res["V_TR_P"] and offset_ok and res["mapping_complete"] and res["V_TE"] in (True, None))
    return res


# ------------------------------------------------------------------------------------------------ driver
def run(arm, alltxt, out, tr1_te_json=None):
    import xc_chain_tools as CT
    te_tmp = out + ".te_only.json"
    CT.cmd_te(arm, te_tmp)                                           # T_E, K, FA*, V-TR-N from the shadow tests (the same code as TR1)
    te = json.load(open(te_tmp))
    t_e = float(te["T_E"])
    idx = load_nc_prior(os.path.join(arm, "nc.tsv"))
    units, stats = units_from_sink(os.path.join(arm, "probe.csv"), idx, t_e)
    ref = load_wsjtx(alltxt, {u["stamp"] for u in units})
    cls, offset, ok = classify_units(units, ref)
    tr1 = json.load(open(tr1_te_json))["T_E"] if tr1_te_json else None
    res = freeze(units, cls, offset, ok, stats, int(te.get("n_shadow_tests", 0)), t_e, tr1)
    res.update({"K": te.get("K"), "FA_star": te.get("FA_star"), "V_TR_N": te.get("V_TR_N"), "version": 2})
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0 if res["valid"] else 3


# ------------------------------------------------------------------------------------------------ self-test (synthetic; a check that can fail)
def selftest():
    rng = np.random.default_rng(20261114)
    d = tempfile.mkdtemp(prefix="xc_tp_selftest_")
    stamps = [(datetime.datetime(2026, 11, 10, 18, 0, 0) + datetime.timedelta(seconds=15 * i)).strftime("%y%m%d_%H%M%S") for i in range(120)]
    nc, probe, wsj = [], [], []
    expect = {"COR": 0, "SUP": 0, "FREE": 0}
    for i in range(6, 120):
        s = stamps[i]
        for j in range(3):                                           # three live tests per cycle, ages 2, 4, 6
            age = 2 * (j + 1)
            ps = stamps[i - age]
            f, dt = 1000 + 50 * j, 0.5 + 0.1 * j
            text = f"Q{i - age}AAA Q{j}BBB -10"
            nc.append("\t".join([ps, "1", "1", str(f), f"{round(dt, 1):.2f}", "-12", "1", "0", "5", "0", text, "0"]))   # published dt: rounded to 0.1 s
            kind = (i + j) % 3                                       # 0 COR-like, 1 SUP-like, 2 FREE-like
            sp = float(rng.uniform(2.0, 6.0)) if kind == 0 else float(rng.uniform(0.3, 1.5))
            probe.append(f"{s},live,{4.0 + rng.uniform(0, 1):.4f},{sp:.4f},{age},{f},{dt + 0.04:.2f},1,0,0.00,0")   # the sink's prior dt is unrounded
            if kind == 0:
                wsj.append(f"{s} 7.074 Rx FT8 -10 {dt - 0.6:.1f} {f + 2} {text}")
                expect["COR"] += 1
            elif kind == 1:
                wsj.append(f"{s} 7.074 Rx FT8 -10 {dt - 0.6:.1f} {f + 1} Q9ZZZ Q{j}BBB R-05")
                expect["SUP"] += 1
            else:
                expect["FREE"] += 1
    p = os.path.join(d, "probe.csv")
    open(p, "w").write(",".join(COLUMNS[k] for k in ("stamp", "kind", "s_e", "s_p", "age", "prior_f", "prior_dt", "prior_batch", "vetoed", "arg_dt", "arg_df")) + "\n" + "\n".join(probe) + "\n")
    open(os.path.join(d, "nc.tsv"), "w").write("\n".join(nc) + "\n")
    open(os.path.join(d, "ALL.TXT"), "w").write("\n".join(wsj) + "\n")
    idx = load_nc_prior(os.path.join(d, "nc.tsv"))
    units, stats = units_from_sink(p, idx, 3.0)
    ref = load_wsjtx(os.path.join(d, "ALL.TXT"), {u["stamp"] for u in units})
    cls, offset, ok = classify_units(units, ref)
    got = collections.Counter(cls)
    assert stats["mapped"] == stats["live_ge_te"] and stats["mapping_missing"] == 0, stats
    assert dict(got) == expect, (dict(got), expect)
    assert ok and abs(offset - 0.6) < 0.06, offset
    res = freeze(units, cls, offset, ok, stats, N_SHADOW_TR1, TE_TR1, TE_TR1)
    assert res["valid"] and res["V_TR_P"] and res["V_TE"], res
    cor_sp = [u["s_p"] for u, c in zip(units, cls) if c == "COR"]
    assert abs(res["T_P"] - float(np.percentile(cor_sp, 10))) < 1e-12
    assert res["descriptive"]["SUP_removed"] == 1.0 and abs(res["descriptive"]["COR_kept"] - 0.9) < 0.03, res["descriptive"]
    # a check that must FAIL: a wrong offset (WSJT-X rows shifted by 0.3 s) trips K3
    bad = [x for x in units]
    ref_bad = {k: [(a, b + 0.3, c) for a, b, c in v] for k, v in ref.items()}
    _, off2, ok2 = classify_units(bad, ref_bad)
    assert not ok2, off2
    # a missing sink link trips mapping_complete (K1)
    stats2 = collections.Counter(stats); stats2["mapping_missing"] = 1
    assert not freeze(units, cls, offset, ok, stats2, N_SHADOW_TR1, TE_TR1, TE_TR1)["valid"]
    # V-TE moves: a different T_E is not valid
    assert not freeze(units, cls, offset, ok, stats, N_SHADOW_TR1, TE_TR1 + 0.01, TE_TR1)["valid"]
    # V-TR-P: too few COR-like units
    few = [c for c in cls]
    assert freeze(units[:40], few[:40], offset, ok, stats, N_SHADOW_TR1, TE_TR1, TE_TR1)["V_TR_P"] is False
    print("xc_tp self-test ALL PASS: units", len(units), dict(got), "offset", round(offset, 3), "T_P", round(res["T_P"], 3))
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        sys.exit(selftest())
    sys.exit(run(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None))
