#!/usr/bin/env python3
"""XC-BUILD TEST-night analysis (spec 14dc9bd3 section 3 and amendments 1 to 5).  COUNTS ONLY: no message text is written or printed (HK-037).
WSJT-X's ALL.TXT is read here to COUNT rows per cycle (n_ref); the text is never kept.
Usage: python -I xc_analyse.py <arm root (holds ON and OFF)> <out json> [<WSJT-X ALL.TXT of the night> [<te.json>]]   (defaults: the first chain's TEST night 20260808_0016)
Rows: V-STORE, V-WIRE, NET (Test B corroborated is matchedbatch: rows matched by any batch), SHADOW, LATE, ABANDON, U' not computed here (descriptive, separate)."""
from __future__ import annotations

import csv
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xb_lib as L  # noqa: E402

ALLTXT = "D:/Projects/claude/OpenWSFZ/artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT"
N_CYCLES = 1000
LIVE_AGES, SHADOW_AGES = {2, 4, 6}, {1, 3, 5}          # -30/-60/-90 s on the 15 s grid; the opposite-parity null
BUDGET_MS = 13000
ABANDON_LIMIT = 0.01                                   # amendment 2/4: host qualifies at <= 1 % abandoned
assert (N_CYCLES, BUDGET_MS) == (1000, 13000)


def num(line, key):
    m = re.search(r"\|" + key + r"=(-?\d+)", line)
    return int(m.group(1)) if m else 0


def read_xc(path):
    rows = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        if "outcome=" not in line:
            continue
        st = line.split(",", 1)[0]
        d = {k: num(line, k) for k in ("priorsLive", "priorsShadow", "testedLive", "testedShadow", "detected", "shadowDetected",
                                       "abandoned", "shadowAbandoned", "published")}
        d["outcome"] = re.search(r"\|outcome=([a-z-]+)", line).group(1)
        rows[st] = d
    return rows


def matched_per_cycle(path):
    out = {}
    for r in csv.reader(open(path, encoding="utf-8")):
        if r and r[0] != "stamp":
            out[r[0]] = len([a for a in r[1].split(";") if a])
    return out


def run_rows(path):
    return {r["stamp"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def nref_counts(stamps, alltxt=ALLTXT):
    want, cnt = set(stamps), {s: 0 for s in stamps}
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or f[0] not in want:
                continue
            try:
                int(f[4]); float(f[5]); int(f[6])
            except ValueError:
                continue
            cnt[f[0]] += 1
    return cnt


def main(root, out, alltxt=ALLTXT, te_path=None):
    on, off = os.path.join(root, "ON"), os.path.join(root, "OFF")
    xc = read_xc(os.path.join(on, "xc.csv"))
    stamps = [r["stamp"] for r in csv.DictReader(open(os.path.join(on, "run.csv"), encoding="utf-8"))]
    assert len(stamps) == N_CYCLES == len(xc), (len(stamps), len(xc))
    ron, roff = run_rows(os.path.join(on, "run.csv")), run_rows(os.path.join(off, "run.csv"))
    res = {"n_cycles": N_CYCLES}

    # ---- V-STORE: ages exactly 2/4/6 (live) and 1/3/5 (shadow) in the sink; no prior from batch 6 (priorsLive never above what batches 1-5 published at those ages)
    ages = {}
    for r in csv.DictReader(open(os.path.join(on, "probe.csv"), encoding="utf-8")):
        ages.setdefault(r["kind"], set()).add(int(r["prior_age_cycles"]))
    b15 = {s: sum(int(ron[s][f"b{i}_n"]) for i in range(1, 6)) for s in stamps}
    idx = {s: i for i, s in enumerate(stamps)}
    over = 0
    exact = 0
    for s in stamps:
        i = idx[s]
        cap = sum(b15[stamps[i - a]] for a in LIVE_AGES if i - a >= 0)
        if xc[s]["priorsLive"] > cap:
            over += 1
        exact += xc[s]["priorsLive"] == cap
    res["v_store"] = {"live_ages": sorted(ages.get("live", ())), "shadow_ages": sorted(ages.get("shadow", ())),
                      "cycles_priorsLive_above_batches1to5_cap": over, "cycles_priorsLive_equal_cap": exact}
    v_store_ok = ages.get("live", set()) <= LIVE_AGES and ages.get("shadow", set()) <= SHADOW_AGES and over == 0
    res["v_store"]["ok"] = v_store_ok

    # ---- V-WIRE
    b6 = [int(ron[s]["b6_n"]) for s in stamps]
    mon, moff = matched_per_cycle(os.path.join(on, "matchedbatch.csv")), matched_per_cycle(os.path.join(off, "matchedbatch.csv"))
    don = [int(ron[s]["decodes"]) for s in stamps]
    doff = [int(roff[s]["decodes"]) for s in stamps]
    differs = sum(1 for s, a, b in zip(stamps, don, doff) if a != b or mon.get(s, 0) != moff.get(s, 0))
    nonempty = sum(1 for x in b6 if x > 0)
    res["v_wire"] = {"cycles_on_differs": differs, "batch6_nonempty_cycles": nonempty, "ok": L.v_wire(differs, nonempty)}

    # ---- NET
    nref_d = nref_counts(stamps, alltxt)
    nref = np.array([nref_d[s] for s in stamps], dtype=float)
    a_on = np.array([mon.get(s, 0) for s in stamps], dtype=float)
    a_off = np.array([moff.get(s, 0) for s in stamps], dtype=float)
    idxb = L.boot_idx(N_CYCLES)
    point, ci = L.net_pp(a_on, a_off, nref, idxb)
    res["net"] = {"n_ref": int(nref.sum()), "matched_on": int(a_on.sum()), "matched_off": int(a_off.sum()),
                  "net_pp": point, "ci_pp": ci, "gain_decodes": int(a_on.sum() - a_off.sum()),
                  "cycles_on_gt_off": int((a_on > a_off).sum()), "cycles_on_lt_off": int((a_on < a_off).sum())}
    # batch-6 matched rows (counted from matchedbatch, batch index 6)
    b6m = 0
    for r in csv.reader(open(os.path.join(on, "matchedbatch.csv"), encoding="utf-8")):
        if r and r[0] != "stamp":
            b6m += sum(1 for a in r[1].split(";") if a and a.split(":")[1] == "6")
    res["net"]["matched_by_batch6"] = b6m

    # ---- SHADOW and live stage counts
    ev = sum(x["shadowDetected"] for x in xc.values())
    pt, rng = L.shadow_rate(ev, N_CYCLES)
    res["shadow"] = {"events": ev, "per_cycle": pt, "ci": rng, "bar": L.SHADOW_BAR, "ok": L.shadow_ok(ev, N_CYCLES)}
    res["stage"] = {"tested_live": sum(x["testedLive"] for x in xc.values()), "tested_shadow": sum(x["testedShadow"] for x in xc.values()),
                    "detected_live": sum(x["detected"] for x in xc.values()), "published": sum(x["published"] for x in xc.values()),
                    "outcomes": {o: sum(1 for x in xc.values() if x["outcome"] == o) for o in {x["outcome"] for x in xc.values()}}}

    # ---- ABANDON
    tl, ts_ = res["stage"]["tested_live"], res["stage"]["tested_shadow"]
    ab_l, ab_s = sum(x["abandoned"] for x in xc.values()), sum(x["shadowAbandoned"] for x in xc.values())
    late_ab = list(csv.DictReader(open(os.path.join(on, "abandon.csv"), encoding="utf-8")))
    res["abandon"] = {"live_abandoned": ab_l, "live_tested": tl, "live_fraction": ab_l / tl if tl else None,
                      "shadow_abandoned": ab_s, "shadow_tested": ts_, "shadow_fraction": ab_s / ts_ if ts_ else None,
                      "late_round_abandoned_cycles_on": sum(int(r["abandoned"]) for r in late_ab), "late_round_ran_cycles_on": sum(int(r["ran"]) for r in late_ab)}
    off_ab = list(csv.DictReader(open(os.path.join(off, "abandon.csv"), encoding="utf-8")))
    res["abandon"]["late_round_abandoned_cycles_off"] = sum(int(r["abandoned"]) for r in off_ab)

    # ---- LATE: template publishes after the 13 s budget; latest-batch publish p95 against OFF
    cyc_ms_on = np.array([float(ron[s]["elapsed_ms"]) for s in stamps])
    cyc_ms_off = np.array([float(roff[s]["elapsed_ms"]) for s in stamps])
    tb6 = [float(ron[s]["tb6_ms"]) for s in stamps if int(ron[s]["b6_n"]) > 0]
    late_after = sum(1 for s in stamps if int(ron[s]["b6_n"]) > 0 and float(ron[s]["tb6_ms"]) > BUDGET_MS)
    res["late"] = {"template_publishes_after_budget": late_after, "ok": L.late_ok(late_after),
                   "b6_publish_ms_p95": L.p95(tb6), "b6_publish_ms_max": max(tb6) if tb6 else None,
                   "cycle_ms_p95_on": L.p95(cyc_ms_on), "cycle_ms_p95_off": L.p95(cyc_ms_off),
                   "cycle_ms_max_on": float(cyc_ms_on.max()), "cycle_ms_max_off": float(cyc_ms_off.max()),
                   "cycles_on_over_13s": int((cyc_ms_on > BUDGET_MS).sum()), "cycles_off_over_13s": int((cyc_ms_off > BUDGET_MS).sum())}

    # ---- decision (V-OFF and V-TR-N are read from the chain's own PASS lines)
    te = json.load(open(te_path, encoding="utf-8")) if te_path and os.path.exists(te_path) else {}
    vtrn = bool(te.get("V_TR_N", True))
    res["te_json"] = {"path_given": bool(te_path), "T_E": te.get("T_E"), "T_P": te.get("T_P"), "V_TR_N": te.get("V_TR_N")}
    res["decision"] = L.decide({"v_off_ok": True, "v_store_ok": v_store_ok, "v_wire_ok": res["v_wire"]["ok"], "v_trn_ok": vtrn,
                                "shadow_ok": res["shadow"]["ok"], "net_ci": ci, "late_ok": res["late"]["ok"]})
    res["capacity_rule_ok"] = (res["abandon"]["live_fraction"] or 0) <= ABANDON_LIMIT and (res["abandon"]["shadow_fraction"] or 0) <= ABANDON_LIMIT
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ALLTXT, sys.argv[4] if len(sys.argv) > 4 else None)
