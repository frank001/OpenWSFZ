#!/usr/bin/env python3
"""f2_station_poller.py - 1 Hz poll of the station daemon's capture-loss and third-pass counters for an endurance run (QA 2026-10-18).

    f2_station_poller.py --port 8080 --out CORPUS/f2_status.jsonl --until-epoch 1792400000 [--stop-file FILE] [--hz 1]

One JSON line per poll: t (epoch s), overruns (captureOverrunCount; Linux arecord only, 0 on Windows), drops (captureChannelDroppedChunks),
restarts (watchdogRestartCount), and when the build has them depth + the third-pass counters. null where the call failed.
Read-only, counters only (HK-037). Stops at --until-epoch or when --stop-file exists, so it cannot outlive the run.
The sibling of qa/rr-study/linux/status_poller.py (same keys); that one is left untouched because sol runs a copy.
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
    ap.add_argument("--until-epoch", type=float, required=True)
    ap.add_argument("--stop-file", default=None)
    a = ap.parse_args()
    nxt = time.monotonic()
    with open(a.out, "a", encoding="utf8", newline="\n") as out:
        while time.time() < a.until_epoch and not (a.stop_file and os.path.exists(a.stop_file)):
            rec = {"t": round(time.time(), 3), "overruns": None, "drops": None, "restarts": None}
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/api/v1/status" % a.port, timeout=2) as r:
                    s = json.loads(r.read().decode("utf-8"))
                rec.update(overruns=s.get("captureOverrunCount"), drops=s.get("captureChannelDroppedChunks"),
                           restarts=s.get("watchdogRestartCount"))
                tp = s.get("thirdPass")
                if isinstance(tp, dict):
                    rec.update(depth=tp.get("decodingDepth"), tp_runs=tp.get("runs"), tp_skipped_no_new=tp.get("skippedNoNew"),
                               tp_skipped_abandoned=tp.get("skippedAbandoned"), tp_abandoned=tp.get("abandoned"),
                               tp_failed=tp.get("failed"), tp_decodes=tp.get("decodes"))
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
