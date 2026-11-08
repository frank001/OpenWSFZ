#!/usr/bin/env python3
"""COH-FB-AUDIO B2: DESCRIPTIVE three-arm table (Original / Residual / Both) and the differences Residual - Original, Both - Residual (spec Amendments 2 and 3). Counts only (HK-037). NO BAR, NO VERDICT.

  python cfr_b2.py <raw dir with orig/ res/ both/> <u dir with uprime_{orig,res,both}.json.*> <scratch dir with {orig,res,both}/nc_dump.tsv> <probe raw dir with ref/ res/ (the earlier PC probe)> <out json>

Bootstrap: mb_analysis's (blocks of 40 cycles, B 10,000, seed 20261025), imported unchanged; its D/U bars are not applied.
nc_dump text is read only inside cfr_union.load(); only counts leave it.
U' numerator parts reported separately (Amendment 3): tested_absent / hashed_or_unencodable / untestable_class, and tested_present.
"""
import collections
import csv
import json
import re
import sys

import cfr_union as C
import mb_analysis as A

ARMS = ("orig", "res", "both")
BANDS = "ABCD"


def main(raw, u, scr, probe, out):
    R = {a: A.load_arm(raw, a) for a in ARMS}
    stamps = sorted(R["orig"]["run"])
    assert all(sorted(R[a]["run"]) == stamps for a in ARMS) and len(stamps) == 400
    ws = R["orig"]["tb"][0]
    cyc = [s for s in stamps if ws.get(s, (0, 0))[0] > 0]
    W = {s: ws[s][0] for s in cyc}
    res = {"cycles": len(stamps), "cycles_with_ws": len(cyc), "sum_W": sum(W.values())}
    M = {a: {s: R[a]["tb"][0][s][1] for s in cyc} for a in ARMS}
    L = {a: C.load(f"{scr}/{a}/nc_dump.tsv") for a in ARMS}

    arms = {}
    for a in ARMS:
        coh = R[a]["coh"]
        tot = lambda f: sum(int(coh[s][f] or 0) for s in stamps if coh.get(s, {}).get(f) not in ("", None))
        n4, c4 = collections.Counter(), collections.Counter()
        for r in A.rows(f"{raw}/{a}/testb.csv"):
            if r["kind"] == "b4" and r["band"] in BANDS:
                n4[r["band"]] += int(r["n"]); c4[r["band"]] += int(r["corroborated"])
        wall = [float(coh[s]["fb_wall_ms"]) for s in stamps if coh.get(s, {}).get("fb_wall_ms") not in ("", None)]
        pub4 = [float(coh[s]["batch4_publish_ms"]) for s in stamps if coh.get(s, {}).get("batch4_published") == "1"]
        b4n = sum(1 for s in stamps for (k, *_r) in R[a]["out"].get(s, []) if k == "b4")
        log = R[a]["log"]
        both = [tuple(map(int, m)) for m in re.findall(r"fromOriginal=(\d+), fromResidual=(\d+), inBoth=(\d+)", log)]
        arms[a] = dict(
            b4_decodes=b4n, b4_published_cycles=len(pub4), b4_confirmed=sum(c4.values()), b4_not_confirmed=sum(n4.values()) - sum(c4.values()),
            b4_by_band={b: {"n": n4[b], "confirmed": c4[b], "not_confirmed": n4[b] - c4[b]} for b in BANDS},
            corroborated_pct_of_W=100 * sum(M[a].values()) / sum(W.values()),
            T1=dict(eligible=tot("eligible"), attempted=tot("attempted"), crc_ok=tot("crc_ok"), f1b_computed=tot("f1b_computed"), gated_out=tot("gated"), passed_T1_published=tot("published")),
            audio_labels=dict(collections.Counter(re.findall(r"Coherent fallback:.*?audio=([a-z0-9()-]+)", log))),
            both_contribution=(None if not both else {"cycles": len(both), "fromOriginal": sum(x[0] for x in both), "fromResidual": sum(x[1] for x in both), "inBoth": sum(x[2] for x in both)}),
            abandon=dict(ordinary_cycles=sum(1 for s in stamps if A.ord_ab(R, a, s)), fallback_cycles=sum(1 for s in stamps if A.fb_ab(R, a, s)),
                         fallback_candidates_abandoned=tot("abandoned"), exceptions=sum(1 for r in R[a]["run"].values() if r["exception"])),
            cost=dict(fb_wall_ms=dict(median=A.pct(wall, 50), p95=A.pct(wall, 95), max=max(wall)),
                      batch4_publish_ms=dict(median=A.pct(pub4, 50), p95=A.pct(pub4, 95), max=max(pub4)),
                      min_margin_to_13s_ms=A.CYCLE_BUDGET_MS - max(pub4)),
            status_ok="preflight_end_ok=1" in R[a]["status"])
    res["arms"] = arms

    def net(x, y):
        d = {s: M[x][s] - M[y][s] for s in cyc}
        b = A.boot_ratio(d, W, cyc)
        return {"point": 100 * b[0], "lo": 100 * b[1], "hi": 100 * b[2], "sum_dM": sum(d.values())}
    res["NET_pp"] = {"res_minus_orig": net("res", "orig"), "both_minus_res": net("both", "res"), "both_minus_orig": net("both", "orig")}
    res["offline_union_estimate_pp_vs_REF"] = {"point": 4.5612, "lo": 4.2442, "hi": 4.8809, "source": "pc_union.json, QA 19:31Z"}

    # U' with parts
    uu = {}
    for a in ARMS:
        ur = A.load_uprime(f"{u}/uprime_{a}.json.percycle.csv")
        tot = collections.Counter()
        band = {b: collections.Counter() for b in BANDS}
        for r in A.rows(f"{u}/uprime_{a}.json.byband.csv"):
            for k in ("tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present", "not_confirmed"):
                tot[k] += int(r[k]); band[r["band"]][k] += int(r[k])
        uu[a] = dict(per_cycle=ur, U_prime_per_cycle=sum(ur.get(s, 0) for s in cyc) / len(cyc), totals=dict(tot), by_band={b: dict(band[b]) for b in BANDS})
    def du(x, y):
        b = A.boot_ratio({s: float(uu[x]["per_cycle"].get(s, 0) - uu[y]["per_cycle"].get(s, 0)) for s in cyc}, {s: 1.0 for s in cyc}, cyc)
        parts = {k: uu[x]["totals"].get(k, 0) - uu[y]["totals"].get(k, 0) for k in ("tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present")}
        bands = {bd: {k: uu[x]["by_band"][bd].get(k, 0) - uu[y]["by_band"][bd].get(k, 0) for k in ("tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present")} for bd in BANDS}
        return {"dU_prime": {"point": b[0], "lo": b[1], "hi": b[2]}, "parts_diff": parts, "by_band_diff": bands}
    res["U_prime"] = {"per_arm": {a: {k: v for k, v in uu[a].items() if k != "per_cycle"} for a in ARMS},
                      "res_minus_orig": du("res", "orig"), "both_minus_res": du("both", "res"), "both_minus_orig": du("both", "orig")}

    # payload-level (text read inside C.load only): Both vs union of the Original and Residual arms of THIS run
    b4 = {a: L[a][0] for a in ARMS}
    only = collections.Counter()
    for s in stamps:
        o, r_, b = set(b4["orig"].get(s, {})), set(b4["res"].get(s, {})), set(b4["both"].get(s, {}))
        u_ = o | r_
        only["union"] += len(u_); only["both"] += len(b); only["both_minus_union"] += len(b - u_); only["union_minus_both"] += len(u_ - b)
    res["both_vs_union_of_orig_res_payloads"] = dict(only)
    # reproducibility against the earlier probe (same machine, same night): batch-4 payload sets and corroborated totals
    Lp = {a: C.load(f"D:/Projects/claude/_qa-scratch/coh-fb-residual/scratch400/{a}/nc_dump.tsv") for a in ("ref", "res")}
    rep = {}
    for new, old in (("orig", "ref"), ("res", "res")):
        diff = sum(1 for s in stamps if set(b4[new].get(s, {})) != set(Lp[old][0].get(s, {})))
        rep[f"{new}_vs_probe_{old}"] = {"cycles_with_different_batch4_payload_set": diff,
                                       "run_csv_decodes_equal": all(R[new]["run"][s]["decodes"] == A.rows(f"{probe}/{old}/run.csv")[i]["decodes"] for i, s in enumerate(stamps))}
    res["reproducibility_vs_probe"] = rep
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, separators=(",", ":"), default=float))


if __name__ == "__main__":
    main(*sys.argv[1:6])
