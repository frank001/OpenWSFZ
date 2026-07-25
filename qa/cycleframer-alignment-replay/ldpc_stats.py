#!/usr/bin/env python3
"""Architect probe 3, 2026-07-25: candidates vs decodes vs LLR quality.

Probes 1 and 2 excluded, from data already on disk:
  - sample loss in the capture path (windows fill in 14.995 s, flat all night)
  - window drops at framerOutput (2682 emitted == 2682 decoded, exactly)
  - bad/absent audio (RMS and noise floor IDENTICAL on zero-decode vs decoding
    cycles: 1.29e-2 vs 1.31e-2, ratio 1.01)

The decoder's own log shows the real shape: e.g. '80 candidates found, 0 decoded'
with 'failCands=80'. Sync finds the signals; LDPC rejects all of them. That is a
demodulation-quality failure, not a window-timing failure -- misalignment would
cost CANDIDATES, not convert found candidates into LDPC failures.

This probe measures candidate yield and LLR quality across the session.
ASCII-only output per HK-009.
"""
import re, os, statistics as st
from datetime import datetime

LOGS = ["openswfz-20260724T202531Z.log", "openswfz-20260724T210711Z.log"]
BASE = os.path.join(os.path.dirname(__file__), "..", "..",
                    "artefacts", "20260724_live_run_2227")
TS = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \+\d{2}:00 "

RE_PASS = re.compile(TS + r"\[DBG\] Iterative subtraction: pass 1 of \d+, (\d+) candidates found, (\d+) decoded\.")
RE_LLR  = re.compile(TS + r"\[DBG\] Iterative subtraction: pass 1 LDPC fail stats — failCands=(\d+) "
                          r"meanAbsLLR=([\d.eE+-]+) prenormVar=([\d.eE+-]+)")
RE_DEC  = re.compile(TS + r"\[INF\] Cycle (\d{2}:\d{2}:\d{2}): (\d+) decode\(s\) found")

events = []   # (dt, kind, payload)
for name in LOGS:
    with open(os.path.join(BASE, name), "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = RE_PASS.match(line)
            if m:
                events.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f"),
                               "pass", (int(m.group(2)), int(m.group(3)))))
                continue
            m = RE_LLR.match(line)
            if m:
                events.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f"),
                               "llr", (int(m.group(2)), float(m.group(3)), float(m.group(4)))))
                continue
            m = RE_DEC.match(line)
            if m:
                events.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f"),
                               "dec", int(m.group(3))))

events.sort(key=lambda e: e[0])

# Walk in order: a cycle is 'pass' [+ optional 'llr'] then 'dec'.
recs, cur = [], None
for dt, kind, p in events:
    if kind == "pass":
        cur = {"dt": dt, "cand": p[0], "sub": p[1], "fail": None, "llr": None, "var": None}
    elif kind == "llr" and cur is not None:
        cur["fail"], cur["llr"], cur["var"] = p
    elif kind == "dec" and cur is not None:
        cur["dec"] = p
        recs.append(cur)
        cur = None

N = len(recs)
print("cycles reconstructed: %d" % N)
print("")
print("dec |  window (local)  |   n | med cand | med dec | cand/dec ratio | zero-dec | med failCands | med LLR | med preVar")
print("----+------------------+-----+----------+---------+----------------+----------+---------------+---------+-----------")
per = N // 10
for i in range(10):
    lo, hi = i * per, ((i + 1) * per if i < 9 else N)
    seg = recs[lo:hi]
    cand = [r["cand"] for r in seg]
    dc   = [r["dec"] for r in seg]
    fl   = [r["fail"] for r in seg if r["fail"] is not None]
    lr   = [r["llr"] for r in seg if r["llr"] is not None]
    vr   = [r["var"] for r in seg if r["var"] is not None]
    tot_c, tot_d = sum(cand), sum(dc)
    print("%3d | %s -> %s | %3d | %8.1f | %7.1f | %14.2f | %7.1f%% | %13s | %7s | %9s"
          % (i + 1, seg[0]["dt"].strftime("%m-%d %H:%M"), seg[-1]["dt"].strftime("%H:%M"),
             len(seg), st.median(cand), st.median(dc),
             (tot_d / tot_c if tot_c else 0),
             100.0 * sum(1 for d in dc if d == 0) / len(dc),
             ("%.1f" % st.median(fl)) if fl else "n/a",
             ("%.3f" % st.median(lr)) if lr else "n/a",
             ("%.1f" % st.median(vr)) if vr else "n/a"))

print("")
zc = [r["cand"] for r in recs if r["dec"] == 0]
sc = [r["cand"] for r in recs if r["dec"] > 0]
print("CANDIDATES on ZERO-decode cycles : n=%d med=%.1f p90=%.1f  (sync IS finding signals)"
      % (len(zc), st.median(zc), sorted(zc)[int(0.9 * (len(zc) - 1))]))
print("CANDIDATES on DECODING cycles    : n=%d med=%.1f p90=%.1f"
      % (len(sc), st.median(sc), sorted(sc)[int(0.9 * (len(sc) - 1))]))
print("")
zl = [r["llr"] for r in recs if r["dec"] == 0 and r["llr"] is not None]
sl = [r["llr"] for r in recs if r["dec"] > 0 and r["llr"] is not None]
zv = [r["var"] for r in recs if r["dec"] == 0 and r["var"] is not None]
sv = [r["var"] for r in recs if r["dec"] > 0 and r["var"] is not None]
if zl and sl:
    print("meanAbsLLR  zero-decode med=%.3f   decoding med=%.3f" % (st.median(zl), st.median(sl)))
if zv and sv:
    print("prenormVar  zero-decode med=%.1f   decoding med=%.1f" % (st.median(zv), st.median(sv)))
print("")
nz = sum(1 for r in recs if r["dec"] == 0 and r["cand"] >= 10)
print("zero-decode cycles that found >=10 candidates: %d (%.1f%% of all zero-decode cycles)"
      % (nz, 100.0 * nz / max(1, len(zc))))
