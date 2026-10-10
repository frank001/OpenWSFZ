"""LATENESS / EDGE test: the playback driver (NOT run before the freeze; never run concurrently with
any other station use: the slot is booked through QA).

    python play_session.py --manifest M --renders <dir> --log <playback_log.csv> [--device "Voicemeeter AUX Input"] [--dry-run]

Playback mechanics are the harness's own, imported not rewritten:
  run_scenario._select_device (:143), _wait_for_cycle (:217, arms _CYCLE_PREWARM_S = 0.5 s before
  `boundary - early_by_s`), sd.play + sd.wait as in _flush_batch (:1186) and the early-arm path (:1349-1375).
  So the offset between a buffer's sample 0 and the slot boundary is exactly the R&R harness's, which is what
  P7 measures.

LATE block: ordinary 15 s buffers, played as CONTINUOUS batches of at most 20 cycles (the harness's own
  _MAX_BATCH_TRIALS = 20: a single sd.play stopped by the next call would clip the cut end of a late signal,
  and an unbounded stream has been seen to collapse). A new batch waits for a fresh boundary, so a slot may
  be skipped between batches; the log records every cycle's actual boundary, never an assumed one.
EARLY block: (idle, planted) pairs; each planted buffer is armed `early_by_s` = 3.0 s early and played alone.
`playback_log.csv`: cycle_index, boundary_utc, planted, play_started_utc (the wall clock when sd.play was
called; the arm instant, 0.5 s + early_by_s before the boundary).
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import design as D  # noqa: E402

MAX_BATCH = 20                      # run_scenario._MAX_BATCH_TRIALS
SLOT = 15
LEAD_S = 120                        # warm-up lead before the first boundary
assert MAX_BATCH == 20 and SLOT == 15


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def isoms(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--renders", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--device", default="Voicemeeter AUX Input")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from harness import run_scenario as rs
    assert rs._CYCLE_PREWARM_S == 0.5 and rs._MAX_BATCH_TRIALS == MAX_BATCH
    design = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    cycles = design["cycles"]
    rdir = Path(a.renders)
    dev = None
    sd = None
    if not a.dry_run:
        import sounddevice as sd  # noqa: F811
        dev = rs._select_device(a.device)

    now = time.time()
    next_b = float(int(now + LEAD_S) // SLOT * SLOT + SLOT)
    rows: list[dict] = []

    def play(buf, first_b: float, early_by: float) -> float:
        started = time.time()
        if not a.dry_run:
            rs._wait_for_cycle(first_b, early_by)
            started = time.time()
            sd.play(buf, samplerate=D.FS, device=dev, blocking=False)
            sd.wait()
        return started

    # LATE block, continuous batches of <= 20 planted cycles
    for lo in range(0, D.LATE_CYCLES, MAX_BATCH):
        idx = list(range(lo, min(lo + MAX_BATCH, D.LATE_CYCLES)))
        assert all(cycles[i]["planted"] and cycles[i]["block"] == "LATE" for i in idx)
        buf = np.concatenate([np.load(rdir / f"cycle_{i:03d}.npy") for i in idx])
        first_b = next_b
        if not a.dry_run:
            while first_b - rs._CYCLE_PREWARM_S <= time.time():
                first_b += SLOT
        started = play(buf, first_b, 0.0)
        for j, i in enumerate(idx):
            rows.append({"cycle_index": i, "boundary_utc": iso(first_b + j * SLOT), "planted": 1,
                         "play_started_utc": isoms(started)})
        next_b = first_b + len(idx) * SLOT
        print(f"LATE batch {lo}-{idx[-1]} boundary {iso(first_b)}", flush=True)

    # EARLY block: (idle, planted) x 52
    for m in range(D.EARLY_PLANTED):
        idle_i, pl_i = D.LATE_CYCLES + 2 * m, D.LATE_CYCLES + 2 * m + 1
        assert not cycles[idle_i]["planted"] and cycles[pl_i]["planted"] and cycles[pl_i]["block"] == "EARLY"
        b = next_b + SLOT
        if not a.dry_run:
            while b - D.EARLY_ARM_S - rs._CYCLE_PREWARM_S <= time.time():
                b += SLOT
        buf = np.load(rdir / f"cycle_{pl_i:03d}.npy")
        started = play(buf, b, D.EARLY_ARM_S)
        rows.append({"cycle_index": idle_i, "boundary_utc": iso(b - SLOT), "planted": 0, "play_started_utc": ""})
        rows.append({"cycle_index": pl_i, "boundary_utc": iso(b), "planted": 1, "play_started_utc": isoms(started)})
        next_b = b + SLOT
        if m % 10 == 0:
            print(f"EARLY pair {m} boundary {iso(b)}", flush=True)

    rows.sort(key=lambda r: r["cycle_index"])
    assert [r["cycle_index"] for r in rows] == list(range(D.TOTAL_CYCLES))
    with open(a.log, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["cycle_index", "boundary_utc", "planted", "play_started_utc"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)
    print("done; log", a.log)


if __name__ == "__main__":
    main()
