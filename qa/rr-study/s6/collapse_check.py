"""Collapse check on a battery's daemon log (QA tooling, 2026-10-13; aggregates only, no message text): when does OpenWSFZ go blind after a busy cycle?

    python collapse_check.py --daemon-log <daemon.stdout.log> --tz-h 2 [--wsjtx-slice <wsjt-s6.txt> --owsfz-slice <owsfz-s6.txt>] --out <json>

From the daemon log (local time = UTC + tz-h): per cycle the decode count, the decode time, and the LAG of the log line after the slot's end;
the residual-pass lines (elapsed, fitted signals, abandoned); the cycle-grid realignment warnings and their `wanted` series. From the two ALL.TXT slices (when
given): rows per slot for each appraiser (only the stamp token of each line is read).
Definitions (descriptive, not bars): a LATE cycle = its log line came more than LATE_S after the slot's end; an EPISODE = a maximal run of consecutive late cycles;
its TRIGGER = the residual-pass line that ended last before the first late cycle. A BLIND cycle = WSJT-X has rows in the slot and OpenWSFZ has none.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

LATE_S = 3.0
SLOT_S = 15
CYCLE = re.compile(r"^\[(\d\d):(\d\d):(\d\d) INF\] Cycle (\d\d):(\d\d):(\d\d): (\d+) decode\(s\) found, elapsed=(\d+) ms\.")
CLAMP = re.compile(r"^\[(\d\d):(\d\d):(\d\d) WRN\] Cycle-grid realignment clamped: wanted (-?\d+) samples \((-?[\d.]+) s\), applied (-?\d+) \(")
PASS = re.compile(r"^\[(\d\d):(\d\d):(\d\d) INF\] Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(True|False) containedException=\w+ fittedSignals=(\d+)")
DROPISH = re.compile(r"overflow|dropp|xrun|overrun|backlog|discard|underrun|DropOldest|stall", re.I)


def sod(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse(path: str, tz_h: float) -> dict:
    cycles, clamps, passes, dropish = [], [], [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = CYCLE.match(line)
            if m:
                lh, lm, ls, ch, cm, cs, n, el = m.groups()
                t_log = sod(lh, lm, ls) - int(tz_h * 3600)
                slot = sod(ch, cm, cs)
                cycles.append({"slot": "%02d:%02d:%02d" % (int(ch), int(cm), int(cs)), "slot_sod": slot, "decodes": int(n), "elapsed_ms": int(el),
                               "lag_s": (t_log - (slot + SLOT_S)) % 86400 if (t_log - (slot + SLOT_S)) % 86400 < 43200 else (t_log - (slot + SLOT_S))})
                continue
            m = CLAMP.match(line)
            if m:
                h, mi, s, w, secs, ap = m.groups()
                clamps.append({"t_sod": sod(h, mi, s) - int(tz_h * 3600), "wanted_s": float(secs), "applied": int(ap)})
                continue
            m = PASS.match(line)
            if m:
                h, mi, s, rd, el, ab, fs = m.groups()
                passes.append({"t_sod": sod(h, mi, s) - int(tz_h * 3600), "elapsed_ms": int(el), "abandoned": ab == "True", "fitted": int(fs), "residual_decodes": int(rd)})
                continue
            if DROPISH.search(line):
                dropish.append(line.strip()[:160])
    return {"cycles": cycles, "clamps": clamps, "passes": passes, "dropish": dropish}


def slot_counts(path: str) -> dict:
    out = defaultdict(int)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            t = line.split(None, 1)
            if t and re.fullmatch(r"\d{6}_\d{6}", t[0]):
                out[t[0][7:9] + ":" + t[0][9:11] + ":" + t[0][11:13]] += 1
    return out


def episodes(cycles: list, passes: list) -> list:
    out, cur = [], None
    for c in cycles:
        if c["lag_s"] > LATE_S:
            if cur is None:
                prior = [p for p in passes if p["t_sod"] <= c["slot_sod"] + SLOT_S + c["lag_s"]]
                trig = prior[-1] if prior else None
                cur = {"first_late_slot": c["slot"], "cycles": 0, "max_lag_s": 0.0, "trigger_pass": ({k: trig[k] for k in ("elapsed_ms", "fitted", "abandoned")} if trig else None)}
            cur["cycles"] += 1
            cur["max_lag_s"] = max(cur["max_lag_s"], c["lag_s"])
        elif cur is not None:
            cur["last_late_slot"] = prev["slot"]
            out.append(cur)
            cur = None
        prev = c
    if cur is not None:
        cur["last_late_slot"] = prev["slot"]
        cur["still_late_at_end_of_log"] = True
        out.append(cur)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon-log", required=True)
    ap.add_argument("--tz-h", type=float, required=True)
    ap.add_argument("--wsjtx-slice")
    ap.add_argument("--owsfz-slice")
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-slot", default="00:00:00", help="HH:MM:SS UTC: ignore cycles before this slot (the first S6 slot)")
    a = ap.parse_args()
    d = parse(a.daemon_log, a.tz_h)
    lo = sod(*a.from_slot.split(":"))
    cyc = [c for c in d["cycles"] if c["slot_sod"] >= lo]
    clamps = [c for c in d["clamps"] if c["t_sod"] >= lo]
    res = {"cycles_logged": len(cyc), "late_cycles": sum(1 for c in cyc if c["lag_s"] > LATE_S), "late_threshold_s": LATE_S,
           "lag_s_median_all": statistics.median(c["lag_s"] for c in cyc) if cyc else None,
           "clamp_warnings": len(clamps), "clamp_warnings_positive": sum(1 for c in clamps if c["wanted_s"] > 0), "clamp_warnings_negative": sum(1 for c in clamps if c["wanted_s"] < 0),
           "wanted_s_series": [c["wanted_s"] for c in clamps],
           "wanted_step_per_warning_s": [round(clamps[i + 1]["wanted_s"] - clamps[i]["wanted_s"], 3) for i in range(len(clamps) - 1)],
           "clamp_applied_samples_distinct": sorted({c["applied"] for c in clamps}),
           "residual_passes": len(d["passes"]), "residual_abandoned": sum(1 for p in d["passes"] if p["abandoned"]),
           "residual_elapsed_ms_max": max((p["elapsed_ms"] for p in d["passes"]), default=None),
           "drop_or_overflow_like_lines": len(d["dropish"]), "drop_or_overflow_examples": d["dropish"][:3],
           "episodes": episodes(cyc, d["passes"])}
    if a.wsjtx_slice and a.owsfz_slice:
        w, o = slot_counts(a.wsjtx_slice), slot_counts(a.owsfz_slice)
        slots = sorted(set(w) | set(o))
        blind = [s for s in slots if w.get(s, 0) > 0 and o.get(s, 0) == 0]
        res["slots_with_any_row"] = len(slots)
        res["blind_slots_wsjtx_rows_openwsfz_none"] = len(blind)
        res["rows_total"] = {"wsjtx": sum(w.values()), "openwsfz": sum(o.values())}
        res["rows_in_slots_where_wsjtx_has_rows"] = {"wsjtx": sum(w[s] for s in slots if w.get(s, 0) > 0), "openwsfz": sum(o.get(s, 0) for s in slots if w.get(s, 0) > 0)}
        res["openwsfz_decoding_slots"] = sorted(s for s in slots if o.get(s, 0) > 0)
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("wanted_s_series", "wanted_step_per_warning_s", "openwsfz_decoding_slots")}, indent=1)[:2600])
    print("wanted series:", res["wanted_s_series"][:40])
    print("step per warning:", res["wanted_step_per_warning_s"][:40])


if __name__ == "__main__":
    main()
