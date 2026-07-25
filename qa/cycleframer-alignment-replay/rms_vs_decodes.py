#!/usr/bin/env python3
"""Architect probe 2, 2026-07-25: per-cycle PCM RMS vs decode yield.

Established by probe 1 + line-type census:
  - the capture path loses no samples (windows fill in 14.995 s, flat all night)
  - 2682 'Window emitted' == 2682 'Starting decode' == 2682 'N decode(s) found'
    => ZERO windows dropped at framerOutput; every window was decoded.

So the 1050 zero-decode cycles are cycles where the decoder RAN and found nothing.
The daemon already logs the window's PCM RMS at decode entry. If RMS collapses in
the collapsed deciles, the audio handed to the decoder was bad -- and alignment,
which is what five live rounds have chased, is not the mechanism.

ASCII-only output per HK-009.
"""
import re, os, statistics as st
from datetime import datetime

LOGS = ["openswfz-20260724T202531Z.log", "openswfz-20260724T210711Z.log"]
BASE = os.path.join(os.path.dirname(__file__), "..", "..",
                    "artefacts", "20260724_live_run_2227")
TS = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \+\d{2}:00 "

RE_RMS = re.compile(TS + r"\[DBG\] Starting decode for cycle (\d{2}:\d{2}:\d{2}); "
                         r"pcm = (\d+) samples, RMS = ([\d.eE+-]+)\.")
RE_DEC = re.compile(TS + r"\[INF\] Cycle (\d{2}:\d{2}:\d{2}): (\d+) decode\(s\) found, "
                         r"elapsed=(\d+) ms")
RE_NF = re.compile(TS + r"\[INF\] Cycle (\d{2}:\d{2}:\d{2}): noise_floor=([-\d.]+) dB")

rms, dec, nf = {}, {}, {}
order = []
for name in LOGS:
    with open(os.path.join(BASE, name), "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = RE_RMS.match(line)
            if m:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
                rms[(name, m.group(2))] = (dt, float(m.group(4)), int(m.group(3)))
                order.append((dt, name, m.group(2)))
                continue
            m = RE_DEC.match(line)
            if m:
                dec[(name, m.group(2))] = (int(m.group(3)), int(m.group(4)))
                continue
            m = RE_NF.match(line)
            if m:
                nf[(name, m.group(2))] = float(m.group(3))

order.sort()
recs = []
for dt, name, cyc in order:
    k = (name, cyc)
    if k not in dec:
        continue
    r = rms[k]
    d, el = dec[k]
    recs.append((dt, r[1], r[2], d, el, nf.get(k)))

N = len(recs)
print("cycles with RMS + decode-count : %d" % N)
_nz = sum(1 for r in recs if r[3] == 0)
print("zero-decode cycles             : %d (%.1f%% of %d)" % (_nz, 100.0 * _nz / N, N))
print("")

print("dec |  window (local)  |   n | med RMS   | p10 RMS   | med dec | zero-dec | med noise | med ms | med smp")
print("----+------------------+-----+-----------+-----------+---------+----------+-----------+--------+--------")
per = N // 10
for i in range(10):
    lo, hi = i * per, ((i + 1) * per if i < 9 else N)
    seg = recs[lo:hi]
    rs = sorted(x[1] for x in seg)
    ds = [x[3] for x in seg]
    nfs = [x[5] for x in seg if x[5] is not None]
    print("%3d | %s -> %s | %3d | %9.3e | %9.3e | %7.1f | %7.1f%% | %9s | %6.0f | %7d"
          % (i + 1, seg[0][0].strftime("%m-%d %H:%M"), seg[-1][0].strftime("%H:%M"),
             len(seg), st.median(rs), rs[int(0.1 * (len(rs) - 1))],
             st.median(ds), 100.0 * sum(1 for d in ds if d == 0) / len(ds),
             ("%.1f" % st.median(nfs)) if nfs else "n/a",
             st.median([x[4] for x in seg]), st.median([x[2] for x in seg])))

print("")
# The decisive split: RMS on zero-decode cycles vs decoding cycles.
zero = sorted(r[1] for r in recs if r[3] == 0)
some = sorted(r[1] for r in recs if r[3] > 0)
print("RMS on ZERO-decode cycles : n=%d  med=%.4e  p10=%.4e  p90=%.4e"
      % (len(zero), st.median(zero), zero[int(0.1 * (len(zero) - 1))], zero[int(0.9 * (len(zero) - 1))]))
print("RMS on DECODING cycles    : n=%d  med=%.4e  p10=%.4e  p90=%.4e"
      % (len(some), st.median(some), some[int(0.1 * (len(some) - 1))], some[int(0.9 * (len(some) - 1))]))
print("ratio of medians (decoding / zero) = %.2f x" % (st.median(some) / st.median(zero)))

# How many zero-decode cycles are explained by a low-RMS threshold?
thr = st.median(some) / 4.0
print("")
print("threshold = 1/4 of decoding-cycle median RMS = %.4e" % thr)
print("  zero-decode cycles BELOW threshold : %d / %d (%.1f%%)"
      % (sum(1 for x in zero if x < thr), len(zero), 100.0 * sum(1 for x in zero if x < thr) / len(zero)))
print("  decoding   cycles BELOW threshold : %d / %d (%.1f%%)"
      % (sum(1 for x in some if x < thr), len(some), 100.0 * sum(1 for x in some if x < thr) / len(some)))
