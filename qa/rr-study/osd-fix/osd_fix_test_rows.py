#!/usr/bin/env python
"""OSD-FIX TEST verdict and descriptive rows (spec section 5.3; ruling 2026-10-09 0615). Numbers only (HK-037): Test B files hold counts, no text.

  python qa/rr-study/osd-fix/osd_fix_test_rows.py [TEST|SAMPLE]

Run ONLY after both arms are complete (the script refuses otherwise). It reuses osd_fix_train_rows.load_arm / compare / boot UNCHANGED (the committed statistics script,
eb1c242b): NET = 100 x sum(M_fix - M_ref) / sum(W); dU = mean over cycles of (not-confirmed FIX - REF); 95 % non-overlapping block bootstrap, blocks of 40, B 10,000,
seed 20261007, ratio estimator for NET.

Verdict rows, exclusive, first match wins (the spec's predicates as code, committed before any FIX decode on TEST):
  F-FAIL     : CI_lo(dU) > 0
  F-GO       : CI_lo(NET) > 0 and CI_hi(dU) <= 0
  F-NEUTRAL  : otherwise
BLIND INSTRUMENT (HK-025(k)): if the FIX arm's per-cycle numbers are identical to REF's in every cycle (NET = dU = 0 exactly, CI [0, 0]) the switch was ignored; that is
reported as a blind instrument and NEVER as F-GO or as an honest F-NEUTRAL.

Validity: V1 pin, V2 read-back / selection SHA, V3 faults, V6 abandon <= 5 %: from the runner's per-process process_ok.json (every process ok); V5: false decodes on the 200 noise WAVs
at FIX(24) (0 => PASS; >= 1 => FLAG to the Architect, not an automatic FAIL); V4 (A-SIGN', A-OFF) is a precondition recorded from the Architect's acceptance.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import osd_fix_test as X  # noqa: E402
import osd_fix_train_rows as R  # noqa: E402
import osd_fix_train as T  # noqa: E402
import onoff_replay_rows as O  # noqa: E402

BANDS = O.BANDS


def classify(net, du, blind=False):
    """net, du: {'point', 'ci': [lo, hi]}. -> verdict string. Pure (tested)."""
    if blind:
        return "BLIND-INSTRUMENT (the FIX arm equals REF in every cycle; not a verdict)"
    if du["ci"][0] > 0:
        return "F-FAIL"
    if net["ci"][0] > 0 and du["ci"][1] <= 0:
        return "F-GO"
    return "F-NEUTRAL"


def is_blind(ref, fix):
    keys = ("W", "M", "n1", "c1", "n2", "c2")
    return all(all(a[k] == b[k] for k in keys) for a, b in zip(ref, fix))


def per_band(rounds, name):
    """-> list per cycle of {band: not-confirmed count (batch 1 + batch 2)} in TEST order, plus batch-1 and batch-2 splits."""
    rows = []
    for r in rounds:
        cyc = O.load_testb(os.path.join(T.OUT, f"r{r}", name, "testb.csv"))
        chunk = json.load(open(os.path.join(T.CHUNK_DIR, f"chunk_{r}.json")))
        for s in chunk["runs"][chunk["run"]]["A"]:
            d = cyc[s]
            rows.append({"W": d["W"], "M": d["M"],
                         "nc": {b: (d["b1"][b][0] - d["b1"][b][1]) + (d["b2"][b][0] - d["b2"][b][1]) for b in BANDS},
                         "dec": {b: d["b1"][b][0] + d["b2"][b][0] for b in BANDS},
                         "conf": {b: d["b1"][b][1] + d["b2"][b][1] for b in BANDS}})
    return rows


def band_rows(ref_b, fix_b, ref, fix):
    out = {}
    for b in BANDS:
        dM = [f["conf"][b] - r["conf"][b] for r, f in zip(ref_b, fix_b)]
        W = [r["W"] for r in ref_b]
        net = 100.0 * sum(dM) / sum(W)
        lo, hi, nb = R.boot(dM, W)
        dUb = [f["nc"][b] - r["nc"][b] for r, f in zip(ref_b, fix_b)]
        ulo, uhi, _ = R.boot(dUb)
        rlo, rhi, _ = R.boot([r["nc"][b] for r in ref_b])
        flo, fhi, _ = R.boot([f["nc"][b] for f in fix_b])
        out[b] = {"NET": {"point": net, "ci": [100.0 * lo, 100.0 * hi]}, "dU": {"point": float(np.mean(dUb)), "ci": [ulo, uhi]},
                  "not_confirmed_per_cycle_REF": {"point": float(np.mean([r["nc"][b] for r in ref_b])), "ci": [rlo, rhi]},
                  "not_confirmed_per_cycle_FIX": {"point": float(np.mean([f["nc"][b] for f in fix_b])), "ci": [flo, fhi]},
                  "FP_WATCH_FLAG": bool(flo > rhi)}
    return out


def v5_false_decodes():
    p = os.path.join(X.OUT, "v5", "outcomes.csv")
    if not os.path.exists(p):
        return None
    o = O.load_outcomes(p)
    return int(sum(sum(v["b1"].values()) + sum(v["b2"].values()) for v in o.values()))


def main(listname="TEST"):
    X.configure(listname)
    rounds = list(range(1, T.N_ROUNDS + 1))
    for r in rounds:
        for name, _s, _n in X.ARMS:
            if not os.path.exists(os.path.join(T.OUT, f"r{r}", name, "process_ok.json")):
                print(f"TEST is not complete (round {r} arm {name}); the verdict is not computed.")
                return 1
    st = json.load(open(os.path.join(T.OUT, "status.json")))
    ref = R.load_arm(rounds, "REF")
    fix = R.load_arm(rounds, "FIX24")
    n = len(ref)
    assert n == X.LISTS[listname], (n, X.LISTS[listname])
    cmp_ = R.compare(ref, fix)
    blind = is_blind(ref, fix)
    verdict = classify(cmp_["NET"], cmp_["dU"], blind)
    res = {"list": listname, "cycles": n, "rounds": rounds, "block": R.BLOCK, "B": R.B_RES, "seed": R.SEED, "FIX24_vs_REF": cmp_, "blind_instrument": blind, "verdict": verdict}
    val = {"processes_ok": True, "abandon": {}, "V4": "A-SIGN' and A-OFF PASS (QA reports; accepted by the Architect 2026-10-08)"}
    ab = {x[0]: 0 for x in X.ARMS}
    for r in rounds:
        for name, rec in st["rounds"][str(r)]["arms"].items():
            val["processes_ok"] &= bool(rec.get("ok")) and rec.get("attempt") == 1
            ab[name] += rec.get("abandoned", 0)
    val["abandon"] = {k: {"cycles": v, "share": v / n, "V6_ok": v / n <= T.V6_MAX_ABANDON} for k, v in ab.items()}
    fd = v5_false_decodes()
    val["V5_false_decodes"] = fd
    val["V5"] = "NOT RUN" if fd is None else ("PASS" if fd == 0 else "FLAG to the Architect (>= 1 false decode)")
    res["validity"] = val
    ref_b, fix_b = per_band(rounds, "REF"), per_band(rounds, "FIX24")
    res["by_band"] = band_rows(ref_b, fix_b, ref, fix)
    res["first_pass"] = {"batch1_not_confirmed_per_cycle": {"REF": float(np.mean([a["n1"] - a["c1"] for a in ref])), "FIX24": float(np.mean([a["n1"] - a["c1"] for a in fix]))},
                         "batch2_confirmed_per_cycle": {"REF": float(np.mean([a["c2"] for a in ref])), "FIX24": float(np.mean([a["c2"] for a in fix]))}}
    wall = {x[0]: [] for x in X.ARMS}
    for r in rounds:
        for name, rec in st["rounds"][str(r)]["arms"].items():
            wall[name].append(rec["wall_s"])
    res["wall_s_per_arm_process"] = {k: {"median": float(np.median(v)), "all": v} for k, v in wall.items()}
    res["limits"] = ("one band, one night's audio, replay not live; Test B's not-confirmed count is an upper bound on false decodes; the OSD-accept nhard histogram of confirmed vs "
                     "not-confirmed accepts is NOT available here (the native diagnostics are thread-local and Replay81 decodes on pool threads)")
    p = os.path.join(X.RESULTS, f"test_result_{listname.lower()}.json")
    json.dump(res, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: res[k] for k in ("list", "cycles", "verdict", "blind_instrument", "FIX24_vs_REF", "validity")}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "TEST"))
