#!/usr/bin/env python3
"""COH-FB-RESIDUAL probe: DESCRIPTIVE table, REF vs RES (Architect spec bc9abc8f + Amendment 1 90ed3a89). Numbers only; no message text is read (HK-037).

  python cfr_desc.py <raw dir with ref/ res/ ref_status.txt res_status.txt> <out json> <label>

NO BAR, NO VERDICT. The bootstrap is mb_analysis's (blocks of 40 consecutive cycles, B 10,000, seed 20261025), imported unchanged; its D/U bars are NOT applied here.
'Not confirmed' here is the Test-B count (batch decodes minus those WSJT-X corroborated), the descriptive stand-in; the full U' stage (cf_uprime.py) is a separate instrument and is not part of this table.
"""
import collections
import json
import re
import sys

import mb_analysis as A

BANDS = "ABCD"


def main(raw, out, label):
    R = {a: A.load_arm(raw, a) for a in ("ref", "res")}
    stamps = sorted(R["ref"]["run"])
    assert stamps == sorted(R["res"]["run"]) and len(stamps) == 400, "cycle sets differ or not 400"
    ws = R["ref"]["tb"][0]
    cyc = [s for s in stamps if ws.get(s, (0, 0))[0] > 0]
    W = {s: ws[s][0] for s in cyc}
    res = {"label": label, "cycles": len(stamps), "cycles_with_ws": len(cyc), "sum_W": sum(W.values())}

    def band_b4(arm):
        n = collections.Counter()
        c = collections.Counter()
        for r in A.rows(f"{raw}/{arm}/testb.csv"):
            if r["kind"] == "b4" and r["band"] in BANDS:
                n[r["band"]] += int(r["n"])
                c[r["band"]] += int(r["corroborated"])
        return n, c

    arms = {}
    for a in ("ref", "res"):
        coh = R[a]["coh"]
        tot = lambda f: sum(int(coh[s][f] or 0) for s in stamps if coh.get(s, {}).get(f) not in ("", None))
        n4, c4 = band_b4(a)
        b4_decodes = sum(1 for s in stamps for (k, *_rest) in R[a]["out"].get(s, []) if k == "b4")
        audio = collections.Counter(re.findall(r"Coherent fallback:.*?audio=([a-z0-9-]+)\.", R[a]["log"]))
        M = {s: R[a]["tb"][0][s][1] for s in cyc}
        wall = [float(coh[s]["fb_wall_ms"]) for s in stamps if coh.get(s, {}).get("fb_wall_ms") not in ("", None)]
        pub4 = [float(coh[s]["batch4_publish_ms"]) for s in stamps if coh.get(s, {}).get("batch4_published") == "1"]
        arms[a] = dict(
            b4_decodes=b4_decodes, b4_published_cycles=len(pub4),
            b4_by_band={b: {"n": n4[b], "confirmed": c4[b], "not_confirmed": n4[b] - c4[b]} for b in BANDS},
            b4_confirmed=sum(c4.values()), b4_not_confirmed=sum(n4.values()) - sum(c4.values()),
            not_confirmed_per_cycle=(sum(n4.values()) - sum(c4.values())) / len(cyc),
            corroborated_total_pct_of_W=100 * sum(M.values()) / sum(W.values()),
            T1=dict(eligible=tot("eligible"), attempted=tot("attempted"), crc_ok=tot("crc_ok"), f1b_computed=tot("f1b_computed"),
                    gated_out=tot("gated"), pass_T1_published=tot("published")),
            audio_levels=dict(audio),
            abandon=dict(ordinary_cycles=sum(1 for s in stamps if A.ord_ab(R, a, s)), fallback_cycles=sum(1 for s in stamps if A.fb_ab(R, a, s)),
                         fallback_candidates_abandoned=tot("abandoned"), exceptions=sum(1 for r in R[a]["run"].values() if r["exception"]),
                         third_pass_outcomes=dict(collections.Counter(R[a]["th"][s]["outcome"] for s in stamps if s in R[a]["th"]))),
            cost=dict(fb_wall_ms=dict(median=A.pct(wall, 50), p95=A.pct(wall, 95), max=max(wall)),
                      batch4_publish_ms=dict(median=A.pct(pub4, 50), max=max(pub4) if pub4 else None),
                      min_margin_to_13s_ms=(A.CYCLE_BUDGET_MS - max(pub4)) if pub4 else None),
            status_ok="preflight_end_ok=1" in R[a]["status"])
        arms[a]["_M"] = M
    res["arms"] = {a: {k: v for k, v in d.items() if k != "_M"} for a, d in arms.items()}
    dM = {s: arms["res"]["_M"][s] - arms["ref"]["_M"][s] for s in cyc}
    net = A.boot_ratio(dM, W, cyc)
    res["NET_RES_minus_REF_pp"] = {"point": 100 * net[0], "lo": 100 * net[1], "hi": 100 * net[2], "sum_dM": sum(dM.values())}
    # cycles in which the batch-4 decodes differ at all (multiset of freq/dt/snr/path)
    def b4set(a, s):
        return collections.Counter(tuple(it) for (k, *it) in R[a]["out"].get(s, []) if k == "b4")
    diff = [s for s in stamps if b4set("ref", s) != b4set("res", s)]
    res["cycles_with_different_batch4"] = len(diff)
    res["b4_decodes_only_in_RES"] = sum(sum((b4set("res", s) - b4set("ref", s)).values()) for s in stamps)
    res["b4_decodes_only_in_REF"] = sum(sum((b4set("ref", s) - b4set("res", s)).values()) for s in stamps)
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
