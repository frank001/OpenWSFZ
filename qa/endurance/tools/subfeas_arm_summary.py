#!/usr/bin/env python
"""SUB-FEAS on-air arm: aggregate report from the daemon logs and the sampler output. Aggregates only.

Reads <run-dir>/daemon-logs/*.log and <run-dir>/subfeas_arm/{memory_samples,events}.jsonl and prints/writes JSON:
  * per UTC hour and overall: cycles, decodes, Sub-feas residual pass lines (count, abandoned, contained,
    residualDecodes total/mean, elapsedMs p50/p95/max), the per-cycle "elapsed=" (time to batch 1) p50/p95/max
  * every [WRN]/[ERR]/[FTL] line as a COUNT by template head (digits masked, 60 characters; never message text)
  * memory: working set and private bytes at start, at each sample and at the end; growth per hour by least squares over
    the samples after the first 30 minutes; the fraction of consecutive samples that increased (a monotonic-growth tell)
  * the sampler's events (flag mismatches, PID changes)

HK-037 / NFR-021: the daemon logs carry only aggregate lines for the templates parsed here; nothing else is read into
the output. HK-036: this is NOT Section 4 (the live-WSJT-X comparison); that is read separately from the gatherer output.

Usage: python subfeas_arm_summary.py <run-dir>
"""
import collections
import glob
import json
import math
import os
import re
import sys

SUB = re.compile(r"\[INF\] Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(True|False) "
                 r"containedException=(True|False) fittedSignals=(\d+)")
CYC = re.compile(r"\[INF\] Cycle (\d\d:\d\d:\d\d): (\d+) decode\(s\) found, elapsed=(\d+) ms")
LVL = re.compile(r"\[(WRN|ERR|FTL)\] (.*)")
TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\.\d+ ([+-]\d\d:\d\d) ")


def pct(v, p):
    s = sorted(v)
    return s[max(0, min(len(s) - 1, math.ceil(p * len(s)) - 1))] if s else None


def stats(v):
    return {"n": len(v), "p50": pct(v, .5), "p95": pct(v, .95), "max": max(v) if v else None}


def utc_hour(line):
    m = TS.match(line)
    if not m:
        return None
    import datetime
    t = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    sign = 1 if m.group(2)[0] == "+" else -1
    off = datetime.timedelta(hours=int(m.group(2)[1:3]), minutes=int(m.group(2)[4:6])) * sign
    return (t - off).strftime("%Y-%m-%dT%H")


def main():
    run = sys.argv[1]
    out = {"run_dir": run}
    per_hour = collections.defaultdict(lambda: {"cycles": 0, "decodes": 0, "sub": [], "elapsed": []})
    sub_all, el_all = [], []
    warn = collections.Counter()
    for f in sorted(glob.glob(os.path.join(run, "daemon-logs", "*.log"))):
        for line in open(f, encoding="utf-8", errors="replace"):
            h = utc_hour(line)
            m = SUB.search(line)
            if m:
                rec = {"res": int(m.group(1)), "ms": int(m.group(2)), "ab": m.group(3) == "True",
                       "co": m.group(4) == "True", "fit": int(m.group(5))}
                sub_all.append(rec)
                if h:
                    per_hour[h]["sub"].append(rec)
                continue
            m = CYC.search(line)
            if m:
                n, e = int(m.group(2)), int(m.group(3))
                el_all.append(e)
                if h:
                    per_hour[h]["cycles"] += 1
                    per_hour[h]["decodes"] += n
                    per_hour[h]["elapsed"].append(e)
                continue
            m = LVL.search(line)
            if m:
                head = re.sub(r"\d", "#", m.group(2))[:60]
                warn[m.group(1) + " " + head] += 1

    def sub_summary(recs):
        ms = [r["ms"] for r in recs]
        res = [r["res"] for r in recs]
        return {"lines": len(recs), "abandoned": sum(r["ab"] for r in recs), "contained": sum(r["co"] for r in recs),
                "abandon_fraction": (sum(r["ab"] for r in recs) / len(recs)) if recs else None,
                "residualDecodes_total": sum(res), "residualDecodes_mean": (sum(res) / len(res)) if res else None,
                "elapsedMs": stats(ms), "fittedSignals_mean": (sum(r["fit"] for r in recs) / len(recs)) if recs else None}

    # HEADLINE (Architect, 2026-09-30): the live abandon rate, split by the number of signals selected for fitting.
    def band(f):
        return "<=25" if f <= 25 else "26-28" if f <= 28 else "29+"
    by_band = {}
    for b in ("<=25", "26-28", "29+"):
        recs = [r for r in sub_all if band(r["fit"]) == b]
        by_band[b] = {"lines": len(recs), "abandoned": sum(r["ab"] for r in recs),
                      "abandon_fraction": (sum(r["ab"] for r in recs) / len(recs)) if recs else None,
                      "elapsedMs": stats([r["ms"] for r in recs])}
    out["HEADLINE_abandon_by_signal_count"] = by_band
    out["overall"] = {"cycles": len(el_all), "time_to_batch1_or_whole_ms_per_cycle_line": stats(el_all),
                      "sub_feas": sub_summary(sub_all)}
    out["per_utc_hour"] = {h: {"cycles": v["cycles"], "decodes": v["decodes"], "elapsed_line_ms": stats(v["elapsed"]),
                               "sub_feas": sub_summary(v["sub"])} for h, v in sorted(per_hour.items())}
    out["warn_err_ftl_by_template_head"] = dict(warn.most_common(30))

    sd = os.path.join(run, "subfeas_arm")
    samples = []
    p = os.path.join(sd, "memory_samples.jsonl")
    if os.path.exists(p):
        samples = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    mem = [s for s in samples if s.get("private_bytes") is not None]
    if mem:
        import datetime
        t0 = datetime.datetime.strptime(mem[0]["utc"], "%Y-%m-%dT%H:%M:%SZ")
        pts = [((datetime.datetime.strptime(s["utc"], "%Y-%m-%dT%H:%M:%SZ") - t0).total_seconds() / 3600.0,
                s["private_bytes"], s["working_set_bytes"]) for s in mem]
        late = [x for x in pts if x[0] >= 0.5]

        def slope(ys):
            if len(late) < 3:
                return None
            xs = [x[0] for x in late]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            den = sum((x - mx) ** 2 for x in xs)
            return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None
        inc = sum(1 for a, b in zip(pts, pts[1:]) if b[1] > a[1])
        out["memory"] = {"samples": len(mem), "start_private_mb": mem[0]["private_bytes"] / 1e6,
                         "end_private_mb": mem[-1]["private_bytes"] / 1e6, "start_ws_mb": mem[0]["working_set_bytes"] / 1e6,
                         "end_ws_mb": mem[-1]["working_set_bytes"] / 1e6, "max_private_mb": max(x[1] for x in pts) / 1e6,
                         "private_growth_mb_per_hour_after_30min": (slope([x[1] for x in late]) or 0) / 1e6 if slope([x[1] for x in late]) is not None else None,
                         "ws_growth_mb_per_hour_after_30min": (slope([x[2] for x in late]) or 0) / 1e6 if slope([x[2] for x in late]) is not None else None,
                         "fraction_of_steps_increasing": inc / max(1, len(pts) - 1),
                         "series_private_mb": [round(x[1] / 1e6, 1) for x in pts]}
    ep = os.path.join(sd, "events.jsonl")
    out["sampler_events"] = [json.loads(l) for l in open(ep, encoding="utf-8") if l.strip()] if os.path.exists(ep) else []
    json.dump(out, open(os.path.join(sd, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
