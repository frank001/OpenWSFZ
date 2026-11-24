#!/usr/bin/env python3
"""SUB-COVER v2 (#273) analysis (spec f68f4ce9 + Amendment 1 50149101). Rows and the decision rule are the code below; v1's analysis (sc_analyse.py) is reused, not changed.

    python sc_analyse2.py main      after O*v2 and both forced runs: O-V1 / O-BUILD / O-REPRO (recheck), O-CTRL (as v1 A2.1), O-ORC (A1.1), O-ENC (report only, A1.2), G*v2, G273v2, strata,
                                    route counts, wrong payloads, and the decision on delta-273p.

Rows (frozen):
  O-REPRO, O-BUILD : from freeze_figures.json (unchanged v1 rows; both PASS on file).
  O-V1  : v2/ov1.json, route 2 OFF + pre-filter ON: bit-identical to the stored O*v1 buffers in 400/400 cycles.
  O-CTRL: v1's, unchanged: CI_hi(share_O*v2 - share_R2) <= +2.0 pp on the 7,239 batch-1 hits and CI_hi(share_O*v2 - share_R3) <= +2.0 pp on the 1,339 batch-2 hits (paired, cycle bootstrap).
  O-ORC : among the decodes subtracted by route 2, the share that still decodes at its own position on O*v2 (forced primary found OR coherent v3_match, the row's text = the verified consistent text).
          FAILS ONLY IF CI_lo > 5.44 % (= 3.44 % + 2.0 pp, A1.1); otherwise it passes and is reported with its CI. If route 2 subtracted fewer than 50 decodes, reported, not gated.
  O-ENC : REPORT ONLY (A1.2): (unencodable-after-both-routes + fit-zero) / decodes; figures read as '>='.
  delta-273p (the decision): NR rows of the #273-proper stratum (112) decodable on O*v2 (primary OR coherent OR walk, GAP-RESIDUAL's classes) and NOT decodable on O*v1 u R2 u R3; pp of n_ref 12,124.
  DECISION on delta-273p: BUILD-WORTH if CI_lo >= 0.40 pp; CLOSE if CI_hi < 0.25 pp; BETWEEN otherwise. Valid only if O-V1, O-CTRL, O-REPRO, O-BUILD pass and O-ORC does not fail.
Bootstrap: B = 2000, seed 20261109 (cycles). Counts only leave this script (HK-037)."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import sc_analyse as A      # noqa: E402

SC, V2, GR = A.SC, A.SC + "/v2", A.GR
A.SEED = 20261109
BUILD_WORTH_LO, CLOSE_HI, ORC_BAR_PCT, ORC_MIN_N, CTRL_MARGIN_PP = 0.40, 0.25, 5.44, 50, 2.0
assert (A.B, A.SEED, BUILD_WORTH_LO, CLOSE_HI, ORC_BAR_PCT, ORC_MIN_N, CTRL_MARGIN_PP) == (2000, 20261109, 0.40, 0.25, 5.44, 50, 2.0)


def main():
    pop, tags = A.pop_and_tags()
    stamps = pop["stamps"]
    boot = A.Boot(stamps)
    rows = pop["rows"]
    n_ref = len(rows)
    fall = A.load_forced(GR + "/forced_all.jsonl")
    fo1 = A.load_forced(f"{SC}/forced_OSTAR.jsonl")
    fo2 = A.load_forced(f"{V2}/forced_OSTAR2.jsonl")
    forc = A.load_forced(f"{V2}/forced_ORC.jsonl")
    ff = json.load(open(f"{SC}/freeze_figures.json"))
    ov1 = json.load(open(f"{V2}/ov1.json"))["summary"]
    o2 = json.load(open(f"{V2}/ostar2.json"))
    s2 = o2["summary"]
    res = {"n_ref": n_ref, "freeze": {k: ff[k] for k in ("O-BUILD", "O-REPRO") if k in ff}, "O-V1": ov1["O-V1"] | {"bit_identical_cycles": ov1["bit_identical_cycles"]}}
    # O-CTRL
    b1 = [r for r in rows if r["matched"] and r["kind"] == 1]
    b2 = [r for r in rows if r["matched"] and r["kind"] == 2]
    c1 = A.share_pair(b1, fall, fo2, "R2", "OSTAR2", boot)
    c2 = A.share_pair(b2, fall, fo2, "R3", "OSTAR2", boot)
    res["O-CTRL"] = {"batch1_vs_R2": c1, "batch2_vs_R3": c2, "margin_pp": CTRL_MARGIN_PP, "PASS": c1["diff_pp"]["CI"][1] <= CTRL_MARGIN_PP and c2["diff_pp"]["CI"][1] <= CTRL_MARGIN_PP}
    # O-ORC
    den, num, unenc = collections.Counter(), collections.Counter(), 0
    for c in o2["cycles"]:
        for r in c["route2"]:
            rec = forc.get((c["stamp"], r["idx"]), {}).get("OSTAR2")
            if rec is None or rec.get("unencodable"):
                unenc += 1
                continue
            den[c["stamp"]] += 1
            num[c["stamp"]] += A.either(rec)
    d, n = boot.arr(den), boot.arr(num)
    orc = {"route2_subtracted": s2["route2_subtracted"], "tested": int(d.sum()), "untestable_rows": unenc, "still_decode": int(n.sum())}
    if d.sum() > 0:
        orc.update(boot.pp(n, d))
        lo = orc["CI"][0]
        orc["bar_pct"] = ORC_BAR_PCT
        orc["FAIL"] = bool(s2["route2_subtracted"] >= ORC_MIN_N and lo > ORC_BAR_PCT)
        orc["gated"] = bool(s2["route2_subtracted"] >= ORC_MIN_N)
    else:
        orc["FAIL"], orc["gated"] = False, False
    res["O-ORC"] = orc
    # O-ENC (report only)
    unenc_both = sum(v for c in o2["cycles"] for k, v in c["route"].items() if k not in ("own", "oracle"))
    res["O-ENC_report_only"] = {"decodes": s2["decodes"], "not_subtracted_after_both_routes": unenc_both, "fit_zero": s2["fit_zero"], "share": (unenc_both + s2["fit_zero"]) / s2["decodes"], "reading": ">="}
    res["routes"] = s2["route"]
    res["by_kind_subtracted"] = s2["by_kind_subtracted"]
    # strata, G*, G273, delta-273p
    by_cycle = collections.defaultdict(list)
    for r in rows:
        by_cycle[r["stamp"]].append({"idx": r["idx"], "snr": r["snr"], "freq": r["freq"], "decoded": bool(r["matched"]), "batch": r["kind"] if r["matched"] else 0})
    nr = [r for r in rows if tags.get((r["stamp"], r["idx"]), {}).get("pop") == "NR"]
    assert len(nr) == 1589
    strata = collections.defaultdict(lambda: {"den": collections.Counter(), "dec": collections.Counter(), "wrong": collections.Counter(), "new": collections.Counter()})
    denall = boot.arr(collections.Counter(r["stamp"] for r in rows))
    for r in nr:
        k = (r["stamp"], r["idx"])
        cat = tags[k]["cat"]
        if cat == "CU-d":
            st = [x for x in by_cycle[r["stamp"]] if x["idx"] != r["idx"] and abs(x["freq"] - r["freq"]) < 50.0 and x["snr"] >= r["snr"] and x["decoded"]]
            cat = "CU-d:batch34-neighbour(L1p-territory)" if any(x["batch"] in (3, 4) for x in st) else "CU-d:batch12-only(#273-proper)"
        rec2 = fo2.get(k, {}).get("OSTAR2")
        d2, w2 = A.anyleg(rec2), A.anywrong(rec2)
        old = A.anyleg(fo1.get(k, {}).get("OSTAR")) or A.anyleg(fall.get(k, {}).get("R2")) or A.anyleg(fall.get(k, {}).get("R3"))
        for key in (cat, "ALL"):
            strata[key]["den"][r["stamp"]] += 1
            strata[key]["dec"][r["stamp"]] += d2
            strata[key]["wrong"][r["stamp"]] += w2
            strata[key]["new"][r["stamp"]] += (d2 and not old)
    res["strata"] = {}
    for key, v in sorted(strata.items()):
        res["strata"][key] = {"nr_rows": int(boot.arr(v["den"]).sum()), "decodable_on_Ostar2": int(boot.arr(v["dec"]).sum()), "new_vs_Ostar1_R2_R3": int(boot.arr(v["new"]).sum()),
                              "gain": boot.pp(boot.arr(v["dec"]), denall), "rows_with_wrong_payload_output": int(boot.arr(v["wrong"]).sum())}
    g_all = boot.arr(strata["ALL"]["dec"])
    pk = "CU-d:batch12-only(#273-proper)"
    l1p_key = "CU-d:batch34-neighbour(L1p-territory)"
    l1p = boot.arr(strata[l1p_key]["dec"]) if l1p_key in strata else np.zeros(len(stamps))
    res["G_star_v2"] = boot.pp(g_all, denall)
    res["G273_v2"] = boot.pp(g_all - l1p, denall)
    dp = boot.arr(strata[pk]["new"])
    res["delta_273p"] = boot.pp(dp, denall)
    res["delta_273p_rows"] = int(dp.sum())
    lo, hi = res["delta_273p"]["CI"]
    decision = "BUILD-WORTH" if lo >= BUILD_WORTH_LO else "CLOSE" if hi < CLOSE_HI else "BETWEEN"
    valid = res["freeze"]["O-REPRO"]["PASS"] and res["freeze"]["O-BUILD"]["PASS"] and res["O-V1"]["PASS"] and res["O-CTRL"]["PASS"] and not res["O-ORC"]["FAIL"]
    res["decision"] = decision if valid else f"NO DECISION (a validity row failed); numbers would read {decision}"
    json.dump(res, open(f"{V2}/sc2_result.json", "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
