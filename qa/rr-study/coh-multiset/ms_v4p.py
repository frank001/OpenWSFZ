#!/usr/bin/env python3
"""COH-MULTISET V4' (Architect Amendment 1.10 = COH-GAIN Amendment 3). Evaluated only AFTER the replay's batch-labelled matched output and manifest were committed (167ddd07).

P1 = the encodable sampled rows that the replay matched in BATCH 1 (decodes the live path gets from the ORIGINAL audio, which is what G reads).
PASS iff P1 is non-empty AND G success on P1 >= 0.90 AND the replay's per-cycle WSJT-X line count equals the row list's ws_load for every sampled cycle
(the row index widx is only meaningful if both read the same lines). The 0.90 bar is unchanged; the control is not renamed.
Descriptive (no bar): G on rows matched only in batch 2+, the batch-1 share, G on rows the replay did not match.

  python qa/rr-study/coh-multiset/ms_v4p.py --rows <rows_sample.json> --main <main_rows.csv> --mb <matchedbatch.csv> --testb <testb.csv> --out <v4p.json>
Numbers only (stamps and indices); no message text.
"""
from __future__ import annotations

import argparse
import csv
import json

V4P_MIN = 0.90
assert V4P_MIN == 0.90


def parse_mb(path):
    out = {}
    for row in csv.reader(open(path, newline="", encoding="utf-8")):
        if not row or row[0] == "stamp":
            continue
        d = {}
        for item in (row[1] if len(row) > 1 else "").split(";"):
            if ":" in item:
                i, b = item.split(":")
                d[int(i)] = int(b)
        out[row[0]] = d
    return out


def ws_counts(testb_path):
    out = {}
    for r in csv.DictReader(open(testb_path, newline="", encoding="utf-8")):
        if r["kind"] == "ws":
            out[r["stamp"]] = int(r["n"])
    return out


def evaluate(recs, mb, replay_ws, load_of_stamp):
    """recs: dicts with stamp, widx, g_right, fault; mb: stamp -> {idx: batch}; replay_ws: stamp -> WSJT-X line count; load_of_stamp: stamp -> ws_load from the row list."""
    ok = [r for r in recs if not int(float(r["fault"] or 0))]
    p1, later, none = [], [], []
    for r in ok:
        b = mb.get(r["stamp"], {}).get(int(float(r["widx"])))
        (p1 if b == 1 else later if b else none).append(r)
    g = lambda xs: (sum(int(float(r["g_right"] or 0)) for r in xs) / len(xs)) if xs else float("nan")
    bad = [s for s, load in load_of_stamp.items() if replay_ws.get(s) != load]
    matched = len(p1) + len(later)
    det = {"P1_n": len(p1), "G_success_on_P1": g(p1), "bar": V4P_MIN, "G_success_on_batch2plus_only": g(later), "batch2plus_rows_n": len(later),
           "batch1_share_of_matches": (len(p1) / matched) if matched else float("nan"), "replay_unmatched_rows_n": len(none), "G_success_on_replay_unmatched": g(none),
           "ws_count_mismatch_cycles": len(bad), "ws_count_mismatch_examples": bad[:5]}
    det["pass"] = bool(p1) and g(p1) >= V4P_MIN and not bad
    return det


def main():
    ap = argparse.ArgumentParser()
    for k in ("rows", "main", "mb", "testb", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    spec = json.load(open(a.rows))
    load_of = {}
    for r in spec["rows"]:
        load_of[r[1]] = r[6]
    recs = list(csv.DictReader(open(a.main, newline="", encoding="utf-8")))
    out = evaluate(recs, parse_mb(a.mb), ws_counts(a.testb), load_of)
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
