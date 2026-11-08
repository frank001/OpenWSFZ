#!/usr/bin/env python3
"""COH-FALLBACK Stage 1 acceptance A0 (cost gate), A2(d) (anchor convention) and A2(e) (order equivalence), on the first 100 selected cycles of 20261009_1752.
Spec: section 8 (A1.3) + section 10 (Amendment 3: output-first order, row A2(e)).  Reworked build only (shim 20260067, d926bdc6).

A0: per cycle, f_i = the diagnostic export's wall time (ft8_coherent_fallback_cycle, DEFAULT flags = output-first: estimate + C3 + BP on every eligible candidate, F1b only on a new CRC-valid output),
measured serially after the cycle's ordinary ft8_decode_all (the spec's serial worst case), single native thread, no deadline. s_i = the committed OFF slack of the same cycle
(qa/rr-study/results/2026-10-20-coh-fallback-a0-slack/slack_OFF_first100.csv, committed BEFORE any Stage 1 timing was seen). PASS iff #(f_i > s_i) <= 5 of the 100 cycles;
a cycle with s_i <= 0 counts as a fail whatever f_i is (none in the committed note).
A2(d): flags INCLUDE_DECODED | ESTIMATE_ONLY: on candidates the ordinary decode DID decode, the estimate's dt offset from the anchor has a median within +-0.02 s of zero and the window-edge rate is <= 2 %.
A2(e): the same cycles, export in GATE-FIRST mode (flag 16, the old order) and in OUTPUT-FIRST mode: the published payload multiset per cycle identical, N/N (rows with published == 1, payload = the first 10 bytes of a91).
Numbers only (HK-037).   python cf_a0.py <out dir> --dll <dll> --pin <sha256> --shim 20260067 [--limit N]
"""
import argparse
import csv
import json
import os
import statistics
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "coh-gain"))
sys.path.insert(0, HERE)
import cg_common  # noqa: E402,F401  (puts the reference-code directories on sys.path)
import wavio  # noqa: E402
import cf_native as N  # noqa: E402

SLACK_CSV = os.path.join(HERE, "..", "results", "2026-10-20-coh-fallback-a0-slack", "slack_OFF_first100.csv")
WAV_DIR = r"D:\Projects\claude\OpenWSFZ\artefacts\20261009_1752_endurance_run-gathered\owsfz\wav"
A0_MAX_FAIL_CYCLES = 5


def published_multiset(n, rows):
    return sorted(bytes(rows[i].r.a91[:10]) for i in range(min(n, len(rows))) if rows[i].published == 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--dll", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--shim", type=int, default=20260067)
    ap.add_argument("--limit", type=int, default=0, help="smoke test only: first N cycles (no verdict is meaningful)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    nat = N.Native(a.dll, a.pin, expected_shim=a.shim)
    assert nat.v67, "this script needs the output-first export (shim >= 20260067)"
    slack = [(r["stamp"], float(r["s_i_ms"])) for r in csv.DictReader(open(SLACK_CSV, newline=""))]
    assert len(slack) == 100
    if a.limit:
        slack = slack[:a.limit]
    rows_out, dt_off, df_off, edge_n, dec_n, e_same, e_total = [], [], [], 0, 0, 0, 0
    e_diff = []
    t_start = time.time()
    for stamp, s_i in slack:
        pcm = np.ascontiguousarray(wavio.load_cycle_pcm(os.path.join(WAV_DIR, stamp + ".wav")), dtype=np.float32)
        n_dec, _ = nat.decode_all(pcm)
        # ---- A0: output-first, default flags, timed
        n, st, rows = nat.cycle(pcm, 0)
        pub_of = published_multiset(n, rows)
        rec = {"stamp": stamp, "ordinary_decodes": n_dec, "s_i_ms": s_i, "f_i_ms": round(st.total_ms, 3), "fail": int(st.total_ms > s_i or s_i <= 0),
               "n_candidates": st.n_candidates, "n_decoded": st.n_decoded, "n_eligible": st.n_eligible, "n_dup_position": st.n_dup_position, "n_attempted": st.n_attempted,
               "n_crc_ok": st.n_crc_ok, "n_crc_new": st.n_crc_new, "n_f1b_computed": st.n_f1b_computed, "n_gated": st.n_gated, "n_published": st.n_published, "n_edge": st.n_edge,
               "estimate_ms": round(st.estimate_ms, 3), "f1b_ms": round(st.f1b_ms, 3), "c3_bp_ms": round(st.c3_bp_ms, 3)}
        # ---- A2(e): gate-first, same cycle, no deadline
        ng, stg, rowsg = nat.cycle(pcm, N.FLAG_GATE_FIRST)
        same = published_multiset(ng, rowsg) == pub_of
        e_total += 1
        e_same += int(same)
        if not same:
            e_diff.append(stamp)
        rec["gate_first_total_ms"] = round(stg.total_ms, 3)
        rec["gate_first_f1b_computed"] = stg.n_f1b_computed
        rec["gate_first_published"] = stg.n_published
        rec["a2e_same"] = int(same)
        # ---- A2(d)
        n2, st2, rows2 = nat.cycle(pcm, N.FLAG_INCLUDE_DECODED | N.FLAG_ESTIMATE_ONLY)
        for i in range(min(n2, len(rows2))):
            r = rows2[i]
            if r.decoded == 1:
                dec_n += 1
                dt_off.append(r.r.est_dt_s)
                df_off.append(r.r.est_df_hz)
                edge_n += int(r.r.edge)
        rows_out.append(rec)
    f = [r["f_i_ms"] for r in rows_out]
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(round(p * (len(v) - 1))))]
    fails = sum(r["fail"] for r in rows_out)
    a0 = {"cycles": len(rows_out), "fail_cycles": fails, "bar_max_fail_cycles": A0_MAX_FAIL_CYCLES, "result": "PASS" if fails <= A0_MAX_FAIL_CYCLES else "FAIL",
          "f_i_ms_median_p95_max": [statistics.median(f), q(f, .95), max(f)], "s_i_ms_min_median": [min(s for _, s in slack), statistics.median(s for _, s in slack)],
          "cycles_with_s_le_0": sum(1 for _, s in slack if s <= 0),
          "per_cycle_median": {k: statistics.median(r[k] for r in rows_out) for k in ("n_eligible", "n_attempted", "n_crc_ok", "n_crc_new", "n_f1b_computed", "n_gated", "n_published")},
          "stage_ms_median": {"estimate": statistics.median(r["estimate_ms"] for r in rows_out), "f1b": statistics.median(r["f1b_ms"] for r in rows_out),
                              "c3_bp": statistics.median(r["c3_bp_ms"] for r in rows_out)}}
    d = {"decoded_candidates": dec_n, "dt_offset_median_s": statistics.median(dt_off) if dt_off else None, "dt_offset_abs_median_s": statistics.median(abs(x) for x in dt_off) if dt_off else None,
         "df_offset_median_hz": statistics.median(df_off) if df_off else None, "edge_rate": edge_n / dec_n if dec_n else None, "bar_dt_median_s": 0.02, "bar_edge_rate": 0.02}
    d["result"] = "PASS" if dec_n and abs(d["dt_offset_median_s"]) <= 0.02 and d["edge_rate"] <= 0.02 else "FAIL"
    e = {"cycles": e_total, "identical": e_same, "different_stamps": e_diff, "result": "PASS" if e_same == e_total else "FAIL",
         "gate_first_f_i_ms_median": statistics.median(r["gate_first_total_ms"] for r in rows_out)}
    res = {"dll_sha256": nat.sha, "shim": a.shim, "wall_s": round(time.time() - t_start), "A0": a0, "A2d": d, "A2e": e}
    json.dump(res, open(os.path.join(a.out, "a0_a2d_a2e.json"), "w"), indent=1)
    with open(os.path.join(a.out, "a0_per_cycle.csv"), "w", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
        w.writeheader(); w.writerows(rows_out)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
