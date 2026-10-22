#!/usr/bin/env python3
"""f2_station_count.py - the F2 station count for one finished endurance run (QA 2026-10-18). Aggregates only (HK-037: counts, times, milliseconds; no message text).

    python f2_station_count.py <corpus-dir> [--out FILE.json]

Reads <corpus>/daemon-logs/*.log and <corpus>/f2_status.jsonl and reports:
  - clamped cycle windows: 'Cycle-grid realignment clamped' lines (the F2 trigger the Architect asked the station to count), total and per UTC hour;
  - 'Capture channel dropped a chunk' lines (total, per UTC hour) and the 1 Hz poll's last/max drop counter, overruns (0 on Windows by construction), restarts;
  - residual pass: lines, deadlineAbandoned=True count, max elapsedMs; third pass: outcome counts, started, abandoned/started, ms median/p90/max, batch-3 decodes;
  - poll health: polls, polls with a failed call, largest gap between polls, depth values seen (must be only 'Deep').
A zero is not proof that nothing was lost: the WASAPI source has no loss counter (F2 Option B would add it); the per-window 'wanted' lines are the loss-agnostic check.
"""
import argparse
import glob
import json
import os
import re
import statistics
from collections import Counter

CLAMP = re.compile(r"Cycle-grid realignment clamped")
DROP = re.compile(r"Capture channel dropped a chunk at (\d\d):(\d\d):(\d\d)\.\d+ UTC")
PASS = re.compile(r"Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(True|False)")
THIRD = re.compile(r"Third pass: newDecodes=(\d+) elapsedMs=(\d+) outcome=(ran|skipped-no-new|skipped-abandoned|abandoned|failed)")
STAMP = re.compile(r"^\[?(\d{4}-\d\d-\d\d)[ T](\d\d):\d\d:\d\d")


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines = []
    for f in sorted(glob.glob(os.path.join(a.corpus, "daemon-logs", "*.log"))):
        lines += open(f, encoding="utf-8", errors="replace").read().splitlines()
    res = {"log_lines": len(lines)}
    per_hour_clamp, per_hour_drop = Counter(), Counter()
    clamps = drops = 0
    resid, third = [], []
    last_hour = "unknown"
    for ln in lines:
        m = STAMP.match(ln)
        if m:
            last_hour = m.group(1) + " " + m.group(2) + "h local(+02:00)"
        if CLAMP.search(ln):
            clamps += 1
            per_hour_clamp[last_hour] += 1
        if DROP.search(ln):
            drops += 1
            per_hour_drop[last_hour] += 1
        m = PASS.search(ln)
        if m:
            resid.append((int(m.group(2)), m.group(3) == "True"))
        m = THIRD.search(ln)
        if m:
            third.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    res["clamped_windows"] = clamps
    res["clamped_per_hour"] = dict(sorted(per_hour_clamp.items()))
    res["channel_drop_lines"] = drops
    res["channel_drop_per_hour"] = dict(sorted(per_hour_drop.items()))
    res["residual_pass"] = {"lines": len(resid), "deadline_abandoned": sum(1 for r in resid if r[1]),
                            "max_elapsed_ms": max((r[0] for r in resid), default=None)}
    oc = Counter(t[2] for t in third)
    started = oc["ran"] + oc["abandoned"] + oc["failed"]
    ran_ms = [t[1] for t in third if t[2] == "ran"]
    res["third_pass"] = {"lines": len(third), "outcomes": dict(oc), "started": started,
                         "abandoned_over_started": (oc["abandoned"] / started) if started else None,
                         "ran_ms_median": statistics.median(ran_ms) if ran_ms else None,
                         "ran_ms_p90": pct(ran_ms, 0.9), "ran_ms_max": max(ran_ms, default=None),
                         "batch3_decodes": sum(t[0] for t in third)}
    pol = os.path.join(a.corpus, "f2_status.jsonl")
    recs = []
    if os.path.exists(pol):
        for ln in open(pol, encoding="utf-8"):
            try:
                recs.append(json.loads(ln))
            except ValueError:
                pass
    if recs:
        ts = [r["t"] for r in recs]
        ok = [r for r in recs if r.get("drops") is not None]
        res["poll"] = {"polls": len(recs), "failed_polls": len(recs) - len(ok),
                       "max_gap_s": round(max((b - a_ for a_, b in zip(ts, ts[1:])), default=0), 1),
                       "overruns_max": max((r["overruns"] for r in ok), default=None),
                       "drops_max": max((r["drops"] for r in ok), default=None),
                       "restarts_max": max((r["restarts"] for r in ok if r.get("restarts") is not None), default=None),
                       "depth_values": sorted({str(r.get("depth")) for r in ok}),
                       "tp_last": {k: ok[-1].get(k) for k in ("tp_runs", "tp_skipped_no_new", "tp_skipped_abandoned",
                                                              "tp_abandoned", "tp_failed", "tp_decodes")} if ok else None}
    else:
        res["poll"] = "no f2_status.jsonl"
    txt = json.dumps(res, indent=1)
    print(txt)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
