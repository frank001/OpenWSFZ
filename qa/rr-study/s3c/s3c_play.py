"""S3c: the playback step (~3 min, 12 cycles) run INSIDE a battery, after S8, in the same daemon session.

    python s3c_play.py --scenario ../scenarios/s3c-edge-guard.json --run-dir <dir> --device "Voicemeeter AUX Input" [--dry-run]

Renders the 8 planted cycles, VERIFIES each cycle's SHA-256 against the scenario JSON's renders index
(a mismatch aborts before any sound), then plays them with the edge test's playback mechanics (the
harness's own `_select_device`, `_wait_for_cycle`, `sd.play` + `sd.wait`; same logic as
lateness-edge/play_session.py, which is imported for its constants, never rewritten):
  LATE block: one continuous 4-cycle batch (<= the harness's _MAX_BATCH_TRIALS = 20);
  EARLY block: (idle, planted) x 4, each planted buffer armed 3.0 s before its boundary.
Writes <run-dir>/s3c/playback_log.csv (cycle_index, boundary_utc, planted, play_started_utc): the
ACTUAL boundaries, never assumed ones.  Stdout carries counts only (NFR-021).
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
RR = HERE.parent
for p in (str(HERE), str(RR), str(RR / "lateness-edge")):
    if p not in sys.path:
        sys.path.insert(0, p)

import s3c_design as S  # noqa: E402
import s3c_render as R  # noqa: E402
import design as ED  # noqa: E402

SLOT = 15
LEAD_S = 45                          # lead before the first boundary (renders are done by then)
assert SLOT == 15


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def isoms(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--device", default="Voicemeeter AUX Input")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    scen = json.loads(Path(a.scenario).read_text(encoding="utf-8"))
    design = scen["design"]
    cycles = design["cycles"]
    bufs, index = R.render_all(design)
    bad = [i for i in index if index[i] != scen["renders_index"].get(i)]
    if bad:
        print(f"S3c ABORT: render SHA-256 differs from the frozen index in cycles {bad}", flush=True)
        sys.exit(2)
    print(f"S3c: {len(bufs)} planted cycles rendered, SHA-256 identical to the frozen index", flush=True)

    from harness import run_scenario as rs
    assert rs._CYCLE_PREWARM_S == 0.5 and rs._MAX_BATCH_TRIALS >= S.LATE_CYCLES
    sd, dev = None, None
    if not a.dry_run:
        import sounddevice as sd  # noqa: F811
        dev = rs._select_device(a.device)

    out_dir = Path(a.run_dir) / "s3c"
    out_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    next_b = float(int(now + LEAD_S) // SLOT * SLOT + SLOT)
    rows: list[dict] = []

    def play(buf, first_b: float, early_by: float) -> float:
        started = time.time()
        if not a.dry_run:
            rs._wait_for_cycle(first_b, early_by)
            started = time.time()
            sd.play(buf, samplerate=ED.FS, device=dev, blocking=False)
            sd.wait()
        return started

    late_idx = list(range(S.LATE_CYCLES))
    assert all(cycles[i]["planted"] and cycles[i]["block"] == "LATE" for i in late_idx)
    first_b = next_b
    if not a.dry_run:
        while first_b - rs._CYCLE_PREWARM_S <= time.time():
            first_b += SLOT
    started = play(np.concatenate([bufs[i] for i in late_idx]), first_b, 0.0)
    for j, i in enumerate(late_idx):
        rows.append({"cycle_index": i, "boundary_utc": iso(first_b + j * SLOT), "planted": 1,
                     "play_started_utc": isoms(started)})
    next_b = first_b + len(late_idx) * SLOT
    print(f"S3c LATE batch boundary {iso(first_b)}", flush=True)

    for m in range(S.EARLY_PLANTED):
        idle_i, pl_i = S.LATE_CYCLES + 2 * m, S.LATE_CYCLES + 2 * m + 1
        assert not cycles[idle_i]["planted"] and cycles[pl_i]["planted"] and cycles[pl_i]["block"] == "EARLY"
        b = next_b + SLOT
        if not a.dry_run:
            while b - ED.EARLY_ARM_S - rs._CYCLE_PREWARM_S <= time.time():
                b += SLOT
        started = play(bufs[pl_i], b, ED.EARLY_ARM_S)
        rows.append({"cycle_index": idle_i, "boundary_utc": iso(b - SLOT), "planted": 0, "play_started_utc": ""})
        rows.append({"cycle_index": pl_i, "boundary_utc": iso(b), "planted": 1, "play_started_utc": isoms(started)})
        next_b = b + SLOT
        print(f"S3c EARLY pair {m} boundary {iso(b)}", flush=True)

    rows.sort(key=lambda r: r["cycle_index"])
    assert [r["cycle_index"] for r in rows] == list(range(S.TOTAL_CYCLES))
    with open(out_dir / "playback_log.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["cycle_index", "boundary_utc", "planted", "play_started_utc"],
                            lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)
    print("S3c: playback done; log", out_dir / "playback_log.csv", flush=True)


if __name__ == "__main__":
    main()
