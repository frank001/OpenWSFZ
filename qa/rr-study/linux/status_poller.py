#!/usr/bin/env python3
"""status_poller.py - 1 Hz poll of the daemon's /api/v1/status counters (QA 2026-10-17; Architect amendment 2, row C5).

    status_poller.py --port 8080 --out FILE.jsonl [--hz 1] [--stop-file FILE]

One JSON line per poll: {"t": epoch s, "overruns": captureOverrunCount, "drops": captureChannelDroppedChunks, "restarts": watchdogRestartCount} (null where the call failed).
Read-only; counters only (HK-037).  Stops when --stop-file exists.
"""
import argparse
import json
import os
import time
import urllib.request


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hz", type=float, default=1.0)
    ap.add_argument("--stop-file", default=None)
    a = ap.parse_args()
    nxt = time.monotonic()
    with open(a.out, "w", encoding="utf8", newline="\n") as out:
        while not (a.stop_file and os.path.exists(a.stop_file)):
            rec = {"t": round(time.time(), 3), "overruns": None, "drops": None, "restarts": None}
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/api/v1/status" % a.port, timeout=2) as r:
                    s = json.loads(r.read().decode("utf-8"))
                rec.update(overruns=s.get("captureOverrunCount"), drops=s.get("captureChannelDroppedChunks"), restarts=s.get("watchdogRestartCount"))
            except Exception:
                pass
            out.write(json.dumps(rec) + "\n")
            out.flush()
            nxt += 1.0 / a.hz
            d = nxt - time.monotonic()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.monotonic()


if __name__ == "__main__":
    main()
