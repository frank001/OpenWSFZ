#!/usr/bin/env python
"""SUB-FEAS on-air run 2026-09-30/10-01: the two contention measures. AGGREGATES ONLY (HK-037): ALL.TXT lines are read for
their 13-character stamp prefix ONLY; no message text is parsed, stored or printed. Daemon log lines are read for the numeric
Sub-feas fields only.
Cycle key = UTC stamp 'YYMMDD_HHMMSS' of the cycle start. A Sub-feas line (local +02:00 stamp) belongs to the cycle whose start
is floor((t - 15 s) / 15 s) * 15 s (the pass runs after the 15 s of audio; max pass 9.4 s + 0.5 s < 15 s).
"""
import collections, datetime, glob, json, math, os, re, sys

RUN = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts\20260930_1930_endurance_run"
G = RUN + "-gathered"
OUT = sys.argv[1]
STAMP = re.compile(r"^(\d{6}_\d{6})")
SUB = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\.(\d+) ([+-]\d\d):(\d\d) \[INF\] Sub-feas residual pass: residualDecodes=(\d+) "
                 r"elapsedMs=(\d+) deadlineAbandoned=(true|false) containedException=(true|false) fittedSignals=(\d+)")


def counts(path):
    c = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = STAMP.match(line)
            if m:
                c[m.group(1)] += 1
    return c


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else None


ows = counts(G + r"\owsfz\ALL.TXT")
wsj = counts(G + r"\wsjt-x\ALL.TXT")
all_cycles = sorted(set(ows) | set(wsj))
# the cycle grid of the window (every 15 s between the first and last stamp) - cycles with no line in a file count as 0
t0 = datetime.datetime.strptime(all_cycles[0], "%y%m%d_%H%M%S")
t1 = datetime.datetime.strptime(all_cycles[-1], "%y%m%d_%H%M%S")
grid = []
t = t0
while t <= t1:
    grid.append(t.strftime("%y%m%d_%H%M%S"))
    t += datetime.timedelta(seconds=15)

res = {"cycles_on_grid": len(grid), "cycles_with_ows_lines": len(ows), "cycles_with_wsjtx_lines": len(wsj)}
res["A_wsjtx_zero_while_ows_ge10"] = sum(1 for c in grid if wsj.get(c, 0) == 0 and ows.get(c, 0) >= 10)
res["A_wsjtx_zero_total"] = sum(1 for c in grid if wsj.get(c, 0) == 0)
res["A_wsjtx_zero_while_ows_ge1"] = sum(1 for c in grid if wsj.get(c, 0) == 0 and ows.get(c, 0) >= 1)
res["A_ows_zero_while_wsjtx_ge10_(reverse)"] = sum(1 for c in grid if ows.get(c, 0) == 0 and wsj.get(c, 0) >= 10)
res["A_ows_zero_total"] = sum(1 for c in grid if ows.get(c, 0) == 0)
res["A_cycles_ows_ge10"] = sum(1 for c in grid if ows.get(c, 0) >= 10)
res["A_cycles_wsjtx_ge10"] = sum(1 for c in grid if wsj.get(c, 0) >= 10)

# residual passes keyed to cycles
rows = {}
dupes = 0
for f in sorted(glob.glob(RUN + r"\daemon-logs\*.log")):
    for line in open(f, encoding="utf-8", errors="replace"):
        m = SUB.match(line)
        if not m:
            continue
        local = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") + datetime.timedelta(microseconds=int(m.group(2).ljust(6, "0")[:6]))
        off = datetime.timedelta(hours=int(m.group(3)), minutes=int(m.group(4)) * (1 if m.group(3)[0] != "-" else -1))
        utc = local - off
        sec = utc.second + utc.microsecond / 1e6
        start_sec = int(math.floor((sec - 15.0) / 15.0) * 15)
        start = utc.replace(second=0, microsecond=0) + datetime.timedelta(seconds=start_sec)
        key = start.strftime("%y%m%d_%H%M%S")
        if key in rows:
            dupes += 1
        rows[key] = {"res": int(m.group(5)), "ms": int(m.group(6)), "ab": m.group(7) == "true", "fit": int(m.group(9))}
res["B_passes_keyed"] = len(rows)
res["B_key_collisions"] = dupes
keys = [k for k in sorted(rows) if k in set(grid)]
res["B_keyed_in_window"] = len(keys)
ms = [rows[k]["ms"] for k in keys]
w = [wsj.get(k, 0) for k in keys]
o = [ows.get(k, 0) for k in keys]
fit = [rows[k]["fit"] for k in keys]
res["B_spearman_elapsed_vs_wsjtx_n"] = spearman(ms, w)
res["B_spearman_elapsed_vs_ows_n"] = spearman(ms, o)
res["B_spearman_elapsed_vs_fitted"] = spearman(ms, fit)
res["B_spearman_wsjtx_n_vs_fitted"] = spearman(w, fit)
# within fitted-signal bands (the confounder), terciles of WSJT-X per-cycle count inside each band
bands = {"<=15": (0, 15), "16-20": (16, 20), "21-25": (21, 25), "26+": (26, 99)}
res["B_by_fitted_band"] = {}
for name, (lo, hi) in bands.items():
    idx = [i for i, f in enumerate(fit) if lo <= f <= hi]
    if len(idx) < 30:
        res["B_by_fitted_band"][name] = {"n": len(idx)}
        continue
    wb = [w[i] for i in idx]
    mb = [ms[i] for i in idx]
    srt = sorted(wb)
    q1, q2 = srt[len(srt) // 3], srt[2 * len(srt) // 3]
    lowi = [mb[j] for j, x in enumerate(wb) if x <= q1]
    midi = [mb[j] for j, x in enumerate(wb) if q1 < x <= q2]
    hii = [mb[j] for j, x in enumerate(wb) if x > q2]
    res["B_by_fitted_band"][name] = {"n": len(idx), "spearman_elapsed_vs_wsjtx_n": spearman(mb, wb),
                                     "wsjtx_n_tercile_cuts": [q1, q2],
                                     "median_elapsed_ms_low_mid_high_wsjtx_tercile": [med(lowi), med(midi), med(hii)],
                                     "n_low_mid_high": [len(lowi), len(midi), len(hii)]}
# time-of-run drift in elapsed (is the conclusion confounded by band conditions through the night?)
res["B_median_elapsed_ms_by_utc_hour"] = {}
byh = collections.defaultdict(list)
for k in keys:
    byh[k[7:9]].append(rows[k]["ms"])
res["B_median_elapsed_ms_by_utc_hour"] = {h: [len(v), med(v)] for h, v in sorted(byh.items())}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))
