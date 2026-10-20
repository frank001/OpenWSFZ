#!/usr/bin/env python3
"""COH-FALLBACK Stage 1 acceptance A0 (cost gate, spec section 8 A1.3) and A2(d) (anchor convention), on the first 100 selected cycles of 20261009_1752.

A0: per cycle, f_i = the Stage 1 diagnostic export's wall time (ft8_coherent_fallback_cycle, default flags: every eligible candidate, gate + C3 + BP where gated), measured serially
after the cycle's ordinary ft8_decode_all (the spec's serial worst case), single native thread. s_i = the committed OFF slack of the same cycle
(qa/rr-study/results/2026-10-20-coh-fallback-a0-slack/slack_OFF_first100.csv, committed BEFORE any Stage 1 timing was seen). PASS iff #(f_i > s_i) <= 5 of the 100 cycles.
A cycle with s_i <= 0 counts as a fail whatever f_i is (none in the committed note).
A2(d): on the same 100 cycles, with INCLUDE_DECODED | ESTIMATE_ONLY, the estimate's dt offset on candidates the ordinary decode DID decode: median within +-0.02 s of zero (the lattice anchor is
centred on the decode's own position), and the window-edge rate <= 2 %.  (The "decode's own refined position" is read as the true signal position the decode locked on; the estimate's dt offset
from the anchor is the measured distance to it.)  Reported also: df offset median, and the counts per cycle.
Numbers only (HK-037).   python cf_a0.py <out dir> --dll <dll> [--reps 1]
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

NEW_DLL_PIN = "7af6f893122aae009f60c18920339dc8c4e3882908a7e3d60ab888a83a92a4d3"
SLACK_CSV = os.path.join(HERE, "..", "results", "2026-10-20-coh-fallback-a0-slack", "slack_OFF_first100.csv")
WAV_DIR = r"D:\Projects\claude\OpenWSFZ\artefacts\20261009_1752_endurance_run-gathered\owsfz\wav"
A0_MAX_FAIL_CYCLES = 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--dll", required=True)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="smoke test only: first N cycles (no verdict is meaningful)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    nat = N.Native(a.dll, NEW_DLL_PIN)
    slack = [(r["stamp"], float(r["s_i_ms"])) for r in csv.DictReader(open(SLACK_CSV, newline=""))]
    assert len(slack) == 100
    if a.limit:
        slack = slack[:a.limit]
    rows_out, dt_off, df_off, edge_n, dec_n = [], [], [], 0, 0
    t_start = time.time()
    for stamp, s_i in slack:
        pcm = np.ascontiguousarray(wavio.load_cycle_pcm(os.path.join(WAV_DIR, stamp + ".wav")), dtype=np.float32)
        n_dec, _ = nat.decode_all(pcm)
        best = None
        for _ in range(a.reps):
            n, st, rows = nat.cycle(pcm, 0)
            f = st.total_ms
            best = f if best is None else min(best, f)           # reps > 1 only for a sanity repeat; the verdict uses rep 1 unless stated
            if _ == 0:
                first = (n, st)
        n, st = first
        rec = {"stamp": stamp, "ordinary_decodes": n_dec, "s_i_ms": s_i, "f_i_ms": round(st.total_ms, 3), "f_best_of_reps_ms": round(best, 3), "fail": int(st.total_ms > s_i or s_i <= 0),
               "n_candidates": st.n_candidates, "n_decoded": st.n_decoded, "n_eligible": st.n_eligible, "n_dup_position": st.n_dup_position, "n_gated": st.n_gated,
               "n_attempted": st.n_attempted, "n_crc_ok": st.n_crc_ok, "n_crc_new": st.n_crc_new, "n_edge": st.n_edge,
               "estimate_ms": round(st.estimate_ms, 3), "f1b_ms": round(st.f1b_ms, 3), "c3_bp_ms": round(st.c3_bp_ms, 3)}
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
          "eligible_per_cycle_median": statistics.median(r["n_eligible"] for r in rows_out), "gated_per_cycle_median": statistics.median(r["n_gated"] for r in rows_out),
          "crc_ok_total": sum(r["n_crc_ok"] for r in rows_out), "crc_new_total": sum(r["n_crc_new"] for r in rows_out),
          "stage_ms_median": {"estimate": statistics.median(r["estimate_ms"] for r in rows_out), "f1b": statistics.median(r["f1b_ms"] for r in rows_out),
                              "c3_bp": statistics.median(r["c3_bp_ms"] for r in rows_out)}}
    d = {"decoded_candidates": dec_n, "dt_offset_median_s": statistics.median(dt_off) if dt_off else None, "dt_offset_abs_median_s": statistics.median(abs(x) for x in dt_off) if dt_off else None,
         "df_offset_median_hz": statistics.median(df_off) if df_off else None, "edge_rate": edge_n / dec_n if dec_n else None,
         "bar_dt_median_abs_s": 0.02, "bar_edge_rate": 0.02}
    d["result"] = "PASS" if dec_n and abs(d["dt_offset_median_s"]) <= 0.02 and d["edge_rate"] <= 0.02 else "FAIL"
    res = {"dll_sha256": nat.sha, "wall_s": round(time.time() - t_start), "A0": a0, "A2d": d}
    json.dump(res, open(os.path.join(a.out, "a0_a2d.json"), "w"), indent=1)
    with open(os.path.join(a.out, "a0_per_cycle.csv"), "w", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
        w.writeheader(); w.writerows(rows_out)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
