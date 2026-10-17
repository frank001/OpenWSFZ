"""Pipe-wrapper check block: rows C1-C4 (QA tooling; Architect reliable-capture spec amendment 1 + A1.1, 2026-10-17).

    python f2_rows.py --run DIR --daemon-log LOG --out JSON

Unit: the OpenWSFZ window of each of the 60 plays (own-window `Window emitted` line: cycle = the play's boundary), [boundary, +15 s).
  C1  overrun Warning lines in the 60 windows (counter delta must agree)                                                        PASS <= 1
  C2  windows with |wanted| > 600 samples, EXCLUDING the windows from the overrun's own window to 10 windows after it            PASS <= 2 of 60
  C3  windows at the clamp (|applied| >= 3000), same exclusion                                                                  PASS 0
  C4  own-window wanted: median and 5th / 95th percentiles (descriptive)
The exclusion is stated here so that nobody has to infer it: window j is excluded when an overrun fell in play window i with 0 <= j - i <= 10.
If C2 or C3 fail while C1 passes (A1.1: backlog mis-steps count, there is no separate bar), the listed sequences are in `c2_c3_windows`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone

OVR_RE = re.compile(r"arecord overrun at (\d\d):(\d\d):(\d\d)\.(\d{3}) UTC")
WIN_RE = re.compile(r"Window emitted \(\d+ samples, cycle (\d\d):(\d\d):(\d\d)\); wanted (-?\d+), applied (-?\d+) samples")
OFF_GRID, CLAMP, EXCLUDE_AFTER = 600, 3000, 10
BARS = {"C1": 1, "C2": 2, "C3": 0}


def epoch(iso: str) -> float:
    return datetime.strptime(iso.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def pct(vals: list, q: float) -> float:
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--run", "--daemon-log", "--out"):
        ap.add_argument(a, required=True)
    a = ap.parse_args()
    plays = []
    for line in open(os.path.join(a.run, "s6", "pass-o", "s6_playlog.jsonl"), encoding="utf8"):
        d = json.loads(line)
        if d.get("kind") == "play":
            plays.append({"i": d["play_index"], "t": epoch(d.get("boundary_utc_o") or d["boundary_utc"])})
    plays.sort(key=lambda p: p["i"])
    day0 = plays[0]["t"] - (plays[0]["t"] % 86400)
    ov, win = [], {}
    for line in open(a.daemon_log, encoding="utf8", errors="replace"):
        m = OVR_RE.search(line)
        if m:
            ov.append(day0 + int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0)
            continue
        m = WIN_RE.search(line)
        if m:
            win[day0 + int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))] = (int(m.group(4)), int(m.group(5)))
    n = len(plays)
    in_win = [[o for o in ov if p["t"] <= o < p["t"] + 15] for p in plays]
    c1 = sum(len(x) for x in in_win)
    excluded = set()
    for i, x in enumerate(in_win):
        if x:
            excluded.update(range(i, min(i + EXCLUDE_AFTER, n - 1) + 1))
    own = [win.get(p["t"]) for p in plays]
    wanted = [x[0] for x in own if x]
    kept = [i for i in range(n) if i not in excluded and own[i]]
    c2_w = [i for i in kept if abs(own[i][0]) > OFF_GRID]
    c3_w = [i for i in kept if abs(own[i][1]) >= CLAMP]
    res = {"plays": n, "windows_with_framer_line": len(wanted), "overruns_total_in_log": len(ov),
           "C1_overruns_in_play_windows": c1, "C1_windows_with_overrun": sum(1 for x in in_win if x),
           "excluded_windows": len(excluded), "windows_scored_for_C2_C3": len(kept),
           "C2_off_grid_gt_600_excl": len(c2_w), "C3_clamp_excl": len(c3_w),
           "C2_C3_windows": [{"play": i, "wanted": own[i][0], "applied": own[i][1]} for i in sorted(set(c2_w) | set(c3_w))],
           "C2_off_grid_gt_600_all_windows_unexcluded": sum(1 for x in own if x and abs(x[0]) > OFF_GRID),
           "C3_clamp_all_windows_unexcluded": sum(1 for x in own if x and abs(x[1]) >= CLAMP),
           "C4_wanted_samples": {"median": pct(wanted, 0.5), "p5": pct(wanted, 0.05), "p95": pct(wanted, 0.95)} if wanted else None,
           "bars": {"C1": "<= 1", "C2": "<= 2 of 60 (excluding)", "C3": "0 (excluding)"}}
    res["C1_pass"] = c1 <= BARS["C1"]
    res["C2_pass"] = len(c2_w) <= BARS["C2"]
    res["C3_pass"] = len(c3_w) == BARS["C3"]
    # C5 (amendment 2, descriptive): channel drops per play window from the 1 Hz status poll, and each C2/C3 window's distance (in windows) from its batch's first slot (20-play batches)
    sp = os.path.join(a.run, "statuspoll.jsonl")
    if os.path.isfile(sp):
        polls = [json.loads(l) for l in open(sp, encoding="utf8")]
        polls = [x for x in polls if x.get("drops") is not None]

        def drops_at(t):
            before = [x for x in polls if x["t"] <= t]
            return before[-1]["drops"] if before else None
        per = []
        for p in plays:
            d0, d1 = drops_at(p["t"]), drops_at(p["t"] + 15)
            per.append(None if d0 is None or d1 is None else d1 - d0)
        bad = sorted(set(c2_w) | set(c3_w))
        res["C5"] = {"polls": len(polls), "drops_per_play_window": per, "plays_with_drops": sum(1 for x in per if x), "drops_total_in_play_windows": sum(x for x in per if x),
                     "batch_size_plays": 20, "distance_from_batch_first_slot_of_each_C2_C3_window": [plays[i]["i"] % 20 for i in bad],
                     "first_window_with_drops_distance_from_its_batch_first_slot": next((plays[i]["i"] % 20 for i, x in enumerate(per) if x), None)}
    cb, ca = os.path.join(a.run, "counters_before.txt"), os.path.join(a.run, "counters_after.txt")
    if os.path.isfile(cb) and os.path.isfile(ca):
        b0, a0 = [int(x) for x in open(cb).read().split()], [int(x) for x in open(ca).read().split()]
        res["counter_delta"] = {"overruns": a0[0] - b0[0], "channel_drops": a0[1] - b0[1], "watchdog_restarts": a0[2] - b0[2]}
    with open(a.out, "w", encoding="utf8", newline="\n") as fh:
        json.dump(res, fh, indent=1)
    print("C1 %d (%s) C2 %d (%s) C3 %d (%s); excluded %d windows" % (c1, "PASS" if res["C1_pass"] else "FAIL", len(c2_w), "PASS" if res["C2_pass"] else "FAIL",
                                                                   len(c3_w), "PASS" if res["C3_pass"] else "FAIL", len(excluded)))


if __name__ == "__main__":
    main()
