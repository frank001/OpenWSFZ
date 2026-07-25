#!/usr/bin/env python3
"""Architect probe, 2026-07-25: is the live path LOSING samples?

The 8.1 instrumentation logged 'real inter-window elapsed' per window and it was
read for flatness. It was never differenced against the discard schedule.

Physics: the capture device delivers 12000 samples/sec of real time. CycleFramer
closes a window when it has ACCUMULATED 180000 samples. So:

    real_elapsed = (180000 + discarded + lost) / 12000

=> lost = (real_elapsed - 15.000) * 12000 - discarded

where 'discarded' is the framer's own pendingSkipSamples for that window (known
exactly from the 'Cycle boundary resync' lines).

A positive residual after subtracting the framer's own discards is audio the
framer never received -- silently dropped by one of the DropOldest channels or
the BufferedWaveProvider. ASCII-only output per HK-009.
"""
import re, sys, os
from datetime import datetime, timedelta

LOGS = [
    "openswfz-20260724T202531Z.log",
    "openswfz-20260724T210711Z.log",
]
BASE = os.path.join(os.path.dirname(__file__), "..", "..",
                    "artefacts", "20260724_live_run_2227")

TS = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \+\d{2}:00 "
RE_TIMING = re.compile(
    TS + r"\[DBG\] Cycle boundary pipeline timing: .*?real inter-window elapsed = "
    r"(n/a \(first window\)|[-\d.]+) s?.*?n=(\d+), avg=([\d.]+) ms, max=([\d.]+) ms")
RE_RESYNC = re.compile(
    TS + r"\[INF\] Cycle boundary resync: accumulated deviation = ([-\d.]+) samples "
    r".*?applying (-?\d+) sample correction")
RE_START = re.compile(TS + r"\[INF\] CycleFramer started")

rows = []          # (dt, elapsed_or_None, n, avg, max)
corrections = []   # (dt, correction)

for name in LOGS:
    path = os.path.join(BASE, name)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = RE_TIMING.match(line)
            if m:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
                el = None if m.group(2).startswith("n/a") else float(m.group(2))
                rows.append([dt, el, int(m.group(3)), float(m.group(4)), float(m.group(5))])
                continue
            m = RE_RESYNC.match(line)
            if m:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
                corrections.append((dt, int(m.group(3))))

print("windows with timing line : %d" % len(rows))
print("corrections parsed       : %d" % len(corrections))
if not rows:
    sys.exit("no timing rows -- check log level / regex")

# Attribute each correction to the window that CONSUMED it: the correction is
# logged at window k's close and the discard happens while filling window k+1.
corr_by_idx = {}
ci = 0
for i, r in enumerate(rows):
    while ci < len(corrections) and corrections[ci][0] <= r[0] + timedelta(milliseconds=5):
        # this correction fired at or before window i's close -> consumed by i+1
        corr_by_idx[i + 1] = corr_by_idx.get(i + 1, 0) + corrections[ci][1]
        ci += 1

print("corrections attributed   : %d" % sum(1 for v in corr_by_idx.values() if v))
print("")

# Per-window residual.
recs = []
for i, (dt, el, n, avg, mx) in enumerate(rows):
    if el is None:
        continue
    discarded = corr_by_idx.get(i, 0)
    if discarded < 0:
        discarded = 0   # a replay ADDs samples from the previous tail; handled below
    replayed = -corr_by_idx.get(i, 0) if corr_by_idx.get(i, 0) < 0 else 0
    # samples the framer had to receive to close this window
    received_needed = 180000 + discarded - replayed
    implied_received = el * 12000.0
    lost = implied_received - received_needed
    recs.append((dt, el, n, avg, mx, discarded, replayed, lost))

recs.sort(key=lambda r: r[0])
N = len(recs)
print("scored windows           : %d" % N)
print("")

# Decile summary, equal-count, matching the decomposition doc's framing.
print("dec |    window (local)     |    n |  med elapsed | med chunks | med lost | p90 lost | max lost | n_lost>3000")
print("----+-----------------------+------+--------------+------------+----------+----------+----------+------------")
import statistics as st
per = N // 10
for d in range(10):
    lo = d * per
    hi = (d + 1) * per if d < 9 else N
    seg = recs[lo:hi]
    if not seg:
        continue
    els = [r[1] for r in seg]
    ns = [r[2] for r in seg]
    lost = sorted(r[7] for r in seg)
    p90 = lost[int(0.9 * (len(lost) - 1))]
    nbad = sum(1 for x in lost if x > 3000)
    print("%3d | %s -> %s | %4d | %12.3f | %10d | %8.0f | %8.0f | %8.0f | %11d"
          % (d + 1, seg[0][0].strftime("%m-%d %H:%M"), seg[-1][0].strftime("%H:%M"),
             len(seg), st.median(els), st.median(ns), st.median(lost), p90,
             max(lost), nbad))

allost = sorted(r[7] for r in recs)
print("")
print("SESSION  median lost/window = %.0f samples (%.1f ms)" % (st.median(allost), st.median(allost) / 12.0))
print("SESSION  p90    lost/window = %.0f samples (%.1f ms)" % (allost[int(0.9 * (N - 1))], allost[int(0.9 * (N - 1))] / 12.0))
print("SESSION  max    lost/window = %.0f samples (%.1f ms)" % (allost[-1], allost[-1] / 12.0))
print("SESSION  total  lost        = %.0f samples (%.1f s of audio)" % (sum(allost), sum(allost) / 12000.0))
print("SESSION  windows losing >1 chunk (750 smp) = %d / %d (%.1f%%)"
      % (sum(1 for x in allost if x > 750), N, 100.0 * sum(1 for x in allost if x > 750) / N))

# Chunk-count check: n should be ~240 if every 62.5ms chunk arrives.
ns_all = sorted(r[2] for r in recs)
print("")
print("chunks/window  median=%d  p10=%d  min=%d  max=%d"
      % (st.median(ns_all), ns_all[int(0.1 * (N - 1))], ns_all[0], ns_all[-1]))
