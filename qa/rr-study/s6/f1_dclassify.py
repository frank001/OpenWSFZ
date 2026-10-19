"""D: classify each overrun as L1 / L2 / unclassified from the sampler's trace (QA tooling; Architect F1 amendment 1, section D).

    python f1_dclassify.py --samples FILE.jsonl --daemon-log LOG --out JSON [--from-epoch T0 --to-epoch T1]

Rule (the Architect's, decided before the data; the 50 % cut-offs are judgments, no prior data):
  window = the 3 s BEFORE the overrun Warning's UTC time (the time in the message text);
  L2 (arecord blocked writing to the pipe)  if >= 50 % of the window's samples have state S/D and a wchan containing 'pipe';
  L1 (arecord starved of the CPU)           elif >= 50 % of the samples are runnable (state R) AND the run-queue delay (schedstat wait_ns) rose by >= 50 % of the elapsed window time;
  else unclassified.
The classifier also reports how many samples the window held (a window with fewer than 20 of the expected 30 is 'no trace').  Counts and shares only.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone

OVR_RE = re.compile(r"arecord overrun at (\d\d):(\d\d):(\d\d)\.(\d{3}) UTC")
WINDOW_S = 3.0
SHARE = 0.5
MIN_SAMPLES = 20


def classify(samples: list, t_ov: float) -> dict:
    w = [s for s in samples if t_ov - WINDOW_S <= s["t"] <= t_ov and s.get("state")]
    n = len(w)
    if n < MIN_SAMPLES:
        return {"class": "no trace", "samples": n}
    pipe = sum(1 for s in w if s["state"] in ("S", "D") and "pipe" in s.get("wchan", ""))
    run = sum(1 for s in w if s["state"] == "R")
    elapsed_ns = (w[-1]["t"] - w[0]["t"]) * 1e9
    delay = (w[-1]["wait_ns"] - w[0]["wait_ns"]) if elapsed_ns > 0 else 0
    if pipe / n >= SHARE:
        c = "L2"
    elif run / n >= SHARE and elapsed_ns > 0 and delay >= SHARE * elapsed_ns:
        c = "L1"
    else:
        c = "unclassified"
    return {"class": c, "samples": n, "share_blocked_on_pipe": round(pipe / n, 3), "share_runnable": round(run / n, 3), "run_delay_share_of_window": round(delay / elapsed_ns, 3) if elapsed_ns > 0 else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--daemon-log", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-epoch", type=float, default=None)
    ap.add_argument("--to-epoch", type=float, default=None)
    a = ap.parse_args()
    samples = [json.loads(l) for l in open(a.samples, encoding="utf8")]
    day0 = samples[0]["t"] - (samples[0]["t"] % 86400)
    items = []
    for line in open(a.daemon_log, encoding="utf8", errors="replace"):
        m = OVR_RE.search(line)
        if m:
            t = day0 + int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0
            if (a.from_epoch is None or t >= a.from_epoch) and (a.to_epoch is None or t <= a.to_epoch):
                items.append({"t": t, **classify(samples, t)})
    counts = {}
    for it in items:
        counts[it["class"]] = counts.get(it["class"], 0) + 1
    json.dump({"overruns": len(items), "classes": counts, "items": items, "rule": "3 s before each overrun; L2 >= 50 % blocked on a pipe; L1 >= 50 % runnable and run delay >= 50 % of the window; else unclassified"},
              open(a.out, "w", encoding="utf8", newline="\n"), indent=1)
    print("overruns %d: %s" % (len(items), counts))


if __name__ == "__main__":
    main()
