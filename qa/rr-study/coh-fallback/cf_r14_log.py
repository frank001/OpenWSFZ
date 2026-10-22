"""COH-FALLBACK step 4, R14 live check (spec 2026-10-22-1430-qa-r14-live-check-spec-step4.md, amended 1334bbec): reads the daemon's FILE log.

Usage: python -I cf_r14_log.py <daemon file log> <window_start_utc> <window_end_utc> <out.json> <ALL.TXT>      (times: 2026-10-22T15:07:30Z)

Reads ONLY these line shapes, and prints counts, times and outcome tokens (HK-037: no message text is read into the output):
  'Cycle hh:mm:ss: N decode(s) found'   the cycle (UTC cycle start); the cycle's batch 2/3/4 events follow it until the next Cycle line
  'Sub-feas residual pass: residualDecodes=N'      batch 2 published iff N > 0
  'Third pass: newDecodes=N'                        batch 3 published iff N > 0
  'Coherent fallback: ... batch4Published=0/1 ...'  batch 4 published iff 1 (also the R12' counters and the L3 timings)
  'QsoAnswererService|QsoCallerService: late batch N <outcome>.'   one line per supplementary batch a running service processed
The file log has millisecond timestamps and a +02:00 offset; everything is converted to UTC.

L1a: per service and per cycle, the sorted batch numbers of the NON-superseded 'late batch' lines equal the published batches {2,3,4}.
     Superseded lines are counted and reported separately and never enter the comparison.
L2 : batch-4 'applied-immediate' whose line time is later than (cycle start + 15 s + 2.36 s + 50 ms) is a defect; within +-50 ms is listed, not scored.
     applied-deferred on batch 4 shows the deferral path was exercised.
L3 : descriptive.
Cycles at the two ends of the window are excluded (their events may be cut).
"""
import collections, datetime as dt, json, re, sys

CYCLE_S = 15.0
GUARD_S = 2.36
TOL_S = 0.05
RX = {
    "ts": re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+) ([+-]\d\d:\d\d) "),
    "cycle": re.compile(r"Cycle (\d\d:\d\d:\d\d): (\d+) decode\(s\) found, elapsed=(\d+) ms"),
    "resid": re.compile(r"Sub-feas residual pass: residualDecodes=(\d+)"),
    "third": re.compile(r"Third pass: newDecodes=(\d+)"),
    "coh": re.compile(r"Coherent fallback: eligible=(\d+), attempted=(\d+), crcOk=(\d+), f1bComputed=(\d+), gated=(\d+), published=(\d+), abandoned=(\d+), elapsedMs=(\d+), publishedEdge=(\d+), path=\d+, workers=(\d+), fbStartMs=(\d+), fbWallMs=(\d+), batch=(\d+), batch4Published=(\d), batch4PublishMs=(-?\d+)"),
    "late": re.compile(r"(QsoAnswererService|QsoCallerService): late batch (\d) ([a-z-]+)\."),
}


def parse_ts(line):
    m = RX["ts"].match(line)
    if not m:
        return None
    t = dt.datetime.strptime(m.group(1)[:26], "%Y-%m-%d %H:%M:%S.%f")
    sign = 1 if m.group(2)[0] == "+" else -1
    off = dt.timedelta(hours=int(m.group(2)[1:3]), minutes=int(m.group(2)[4:6])) * sign
    return (t - off).replace(tzinfo=dt.timezone.utc)


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round((p / 100) * (len(v) - 1))))] if v else None


def main():
    path, w0, w1, outp, alltxt = sys.argv[1:6]
    w0 = dt.datetime.fromisoformat(w0.replace("Z", "+00:00"))
    w1 = dt.datetime.fromisoformat(w1.replace("Z", "+00:00"))
    cycles, cur = [], None
    for line in open(path, encoding="utf-8", errors="replace"):
        t = parse_ts(line)
        if t is None or t < w0 or t > w1:
            continue
        m = RX["cycle"].search(line)
        if m:
            hh, mm, ss = map(int, m.group(1).split(":"))
            cs = t.replace(hour=hh, minute=mm, second=ss, microsecond=0)
            if cs > t:
                cs -= dt.timedelta(days=1)
            cur = dict(cs=cs, batch1=int(m.group(2)), pub=set(), sz={}, late={"QsoAnswererService": [], "QsoCallerService": []}, sup={"QsoAnswererService": 0, "QsoCallerService": 0}, coh=None)
            cycles.append(cur)
            continue
        if cur is None:
            continue
        m = RX["resid"].search(line)
        if m and int(m.group(1)) > 0:
            cur["nominal"] = cur.get("nominal", {}); cur["nominal"][2] = int(m.group(1))
        m = RX["third"].search(line)
        if m and int(m.group(1)) > 0:
            cur["nominal"] = cur.get("nominal", {}); cur["nominal"][3] = int(m.group(1))
        m = RX["coh"].search(line)
        if m:
            g = [int(x) for x in m.groups()]
            cur["coh"] = dict(zip(["eligible", "attempted", "crc_ok", "f1b", "gated", "published", "abandoned", "elapsed_ms", "published_edge", "workers", "fb_start_ms", "fb_wall_ms", "batch", "b4pub", "b4_ms"], g), t=t)
            if g[13] == 1:
                cur["nominal"] = cur.get("nominal", {}); cur["nominal"][4] = g[5]
        m = RX["late"].search(line)
        if m:
            svc, n, tok = m.group(1), int(m.group(2)), m.group(3)
            if tok == "superseded":
                cur["sup"][svc] += 1
            else:
                cur["late"][svc].append((n, tok, t))
    body = cycles[1:-1]                         # drop the two end cycles
    # Pilot finding (2026-10-22): 'newDecodes>0' / 'residualDecodes>0' over-count, because the pump publishes a batch only if it still has a
    # decode after the earlier batches' text dedup (a cycle with newDecodes=1 had NO batch 3: ALL.TXT held batch 1 + 2 only). The published set is
    # therefore reconciled against ALL.TXT line counts: lines(stamp) = batch1 + the sizes of the batches actually published. ALL.TXT is read here for
    # the first 13 characters of each line (the stamp) ONLY and nothing else leaves this function (HK-037).
    want = {c["cs"].strftime("%y%m%d_%H%M%S") for c in body}
    lines = collections.Counter()
    for ln in open(alltxt, encoding="utf-8", errors="replace"):
        k = ln[:13]
        if k in want:
            lines[k] += 1
    import itertools
    cls = collections.Counter()
    for c in body:
        nom = c.get("nominal", {})
        extra_lines = lines[c["cs"].strftime("%y%m%d_%H%M%S")] - c["batch1"]
        ks = sorted(nom)
        hit = [set(sub) for r in range(len(ks) + 1) for sub in itertools.combinations(ks, r) if sum(nom[k] for k in sub) == extra_lines]
        if len(hit) == 1:
            c["pub"] = hit[0]; c["recon"] = "determined"
        elif len(hit) == 0:
            c["pub"] = None; c["recon"] = "unreconciled"
        else:
            c["pub"] = None; c["recon"] = "ambiguous"
        cls[c["recon"]] += 1
    res_recon = dict(cls)
    res = {"window": [w0.isoformat(), w1.isoformat()], "cycles_total": len(cycles), "cycles_scored": len(body), "published_set_vs_ALLTXT": res_recon}
    body_all = body
    body = [c for c in body if c["pub"] is not None]
    res["cycles_with_determined_published_set"] = len(body)

    pubc = collections.Counter()
    for c in body:
        for n in c["pub"]:
            pubc[n] += 1
    res["published_cycles_by_batch"] = {str(k): pubc[k] for k in (2, 3, 4)}
    l1 = {}
    for svc in ("QsoAnswererService", "QsoCallerService"):
        miss, extra, ok, ordered = collections.Counter(), collections.Counter(), 0, True
        missing_cycles = []
        for c in body:
            got = [n for n, _, _ in c["late"][svc]]
            if got != sorted(got):
                ordered = False
            for n in (2, 3, 4):
                have, want = got.count(n), 1 if n in c["pub"] else 0
                if have < want:
                    miss[n] += 1
                    missing_cycles.append((c["cs"].strftime("%H:%M:%S"), n))
                elif have > want:
                    extra[n] += 1
            if sorted(got) == sorted(c["pub"]):
                ok += 1
        l1[svc] = {"cycles_matching": ok, "missing_by_batch": {str(k): miss[k] for k in (2, 3, 4)}, "extra_by_batch": {str(k): extra[k] for k in (2, 3, 4)},
                   "in_order": ordered, "superseded_lines_reported_separately": sum(c["sup"][svc] for c in body), "first_missing": missing_cycles[:10],
                   "lines": sum(len(c["late"][svc]) for c in body)}
    res["L1a"] = l1
    cov = len(body) / len(body_all) if body_all else 0.0
    res["determined_coverage"] = cov
    ok = all(v["cycles_matching"] == len(body) and v["in_order"] for v in l1.values()) and len(body) > 0
    # coverage bar 0.90: the pilot reconciled 23 of 24 scored cycles (0.958); one unreconciled cycle in 24 is tolerated, a night where more than 10 % cannot be reconciled is not read
    res["L1a_verdict"] = "FAIL" if not ok else ("PASS" if cov >= 0.90 else "INCONCLUSIVE (coverage below 0.90)")

    out = collections.Counter()
    l2_defects, l2_ambiguous = [], []
    miss_guard = guard_n = 0
    for c in body:
        S = c["cs"] + dt.timedelta(seconds=CYCLE_S)
        for svc in ("QsoAnswererService", "QsoCallerService"):
            for n, tok, t in c["late"][svc]:
                if n != 4:
                    continue
                out[(svc, tok)] += 1
                late = (t - S).total_seconds()
                guard_n += 1
                if late > GUARD_S:
                    miss_guard += 1
                if tok == "applied-immediate":
                    if late > GUARD_S + TOL_S:
                        l2_defects.append((svc, c["cs"].strftime("%H:%M:%S"), round(late, 3)))
                    elif late > GUARD_S - TOL_S:
                        l2_ambiguous.append((svc, c["cs"].strftime("%H:%M:%S"), round(late, 3)))
    res["batch4_outcomes"] = {f"{k[0]}:{k[1]}": v for k, v in sorted(out.items())}
    res["L2"] = {"defects": l2_defects, "ambiguous_within_50ms_not_scored": l2_ambiguous,
                 "applied_deferred_on_batch4": sum(v for k, v in out.items() if k[1] == "applied-deferred"),
                 "applied_immediate_on_batch4": sum(v for k, v in out.items() if k[1] == "applied-immediate")}
    ex = res["L2"]["applied_deferred_on_batch4"] + res["L2"]["applied_immediate_on_batch4"]
    res["L2_verdict"] = "FAIL" if l2_defects else ("NOT EXERCISED" if ex == 0 else ("PASS" if res["L2"]["applied_deferred_on_batch4"] > 0 else "NOT EXERCISED (immediate only, none late)"))

    cohs = [c["coh"] for c in body if c["coh"]]
    b4 = [c for c in body if c["coh"] and c["coh"]["b4pub"] == 1]
    off = [(c["coh"]["t"] - (c["cs"] + dt.timedelta(seconds=CYCLE_S))).total_seconds() * 1000 for c in b4]
    res["L3"] = {
        "cycles_with_fallback_line": len(cohs), "batch4_cycles": len(b4), "batch4_rate": (len(b4) / len(cohs) if cohs else None),
        "batch4_publish_ms_from_decode_start": {"median": pct([c["coh"]["b4_ms"] for c in b4], 50), "p95": pct([c["coh"]["b4_ms"] for c in b4], 95), "max": max([c["coh"]["b4_ms"] for c in b4], default=None)},
        "fallback_line_after_slot_start_ms": {"median": pct(off, 50), "p95": pct(off, 95), "max": max(off, default=None)},
        "reply_guard": {"batch4_service_lines": guard_n, "after_2.36s": miss_guard, "rate": (miss_guard / guard_n if guard_n else None)},
        "fb_wall_ms": {"median": pct([c["fb_wall_ms"] for c in cohs], 50), "p95": pct([c["fb_wall_ms"] for c in cohs], 95), "max": max([c["fb_wall_ms"] for c in cohs], default=None)},
        "workers": sorted(set(c["workers"] for c in cohs)),
        "R12": {k: sum(c[k] for c in cohs) for k in ("eligible", "attempted", "crc_ok", "published", "abandoned", "published_edge")},
        "abandoned_cycles": sum(1 for c in cohs if c["abandoned"] > 0),
    }
    json.dump(res, open(outp, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
