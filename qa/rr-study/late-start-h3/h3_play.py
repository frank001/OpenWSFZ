"""H3 playback driver (runs on sol, ALSA loopback into the running WSJT-X profile `rr`). Never run concurrently with any
other use of sol's audio chain.

    PYTHONPATH=<rr-work-b2>/qa/rr-study/linux/shim RR_ALSA_PLAYBACK=plughw:0,0 \
      python h3_play.py --manifest M --renders <dir> --rr-study <rr-work-b2>/qa/rr-study --log <playback_log.csv>

Mechanics are the R&R harness's own (imported, not rewritten), exactly as lateness-edge/play_session.py: continuous
batches of at most 20 cycles (run_scenario._MAX_BATCH_TRIALS), a new batch waits for a fresh boundary, and the log
records every cycle's ACTUAL boundary. playback_log.csv: cycle_index, boundary_utc, play_started_utc.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MAX_BATCH = 20
SLOT = 15
LEAD_S = 60
FS = 48_000


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def isoms(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--renders", required=True)
    ap.add_argument("--rr-study", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--device", default="RR-ALSA")
    ap.add_argument("--cycles", default=None, help="a:b slice (default all)")
    a = ap.parse_args()
    sys.path.insert(0, a.rr_study)
    import sounddevice as sd
    from harness import run_scenario as rs
    assert rs._CYCLE_PREWARM_S == 0.5 and rs._MAX_BATCH_TRIALS == MAX_BATCH

    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    n = man["n_cycles"]
    lo_all, hi_all = (0, n) if not a.cycles else (int(v) for v in a.cycles.split(":"))
    dev = rs._select_device(a.device)
    rdir = Path(a.renders)
    next_b = float(int(time.time() + LEAD_S) // SLOT * SLOT + SLOT)
    rows = []
    for lo in range(lo_all, hi_all, MAX_BATCH):
        idx = list(range(lo, min(lo + MAX_BATCH, hi_all)))
        buf = np.concatenate([np.load(rdir / f"cycle_{i:03d}.npy") for i in idx])
        first_b = next_b
        while first_b - rs._CYCLE_PREWARM_S <= time.time():
            first_b += SLOT
        rs._wait_for_cycle(first_b, 0.0)
        started = time.time()
        sd.play(buf, samplerate=FS, device=dev, blocking=False)
        sd.wait()
        for j, i in enumerate(idx):
            rows.append({"cycle_index": i, "boundary_utc": iso(first_b + j * SLOT), "play_started_utc": isoms(started)})
        next_b = first_b + len(idx) * SLOT
        print(f"batch {lo}-{idx[-1]} boundary {iso(first_b)}", flush=True)
        with open(a.log, "w", newline="", encoding="utf-8") as fh:        # rewritten after every batch
            wr = csv.DictWriter(fh, fieldnames=["cycle_index", "boundary_utc", "play_started_utc"], lineterminator="\n")
            wr.writeheader()
            wr.writerows(rows)
    print("done; log", a.log, flush=True)


if __name__ == "__main__":
    main()
