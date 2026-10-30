#!/usr/bin/env python3
"""LATE-SUB L1' third acceptance night (build spec section 4): the selection for night 20260930_1930, on the PC, BEFORE anything is replayed.
Rule = R-F4 A1.4's, as selection_2n.json was made: systematic sample, stride 3, offset 1, the first 800 slots of the gap-inclusive 15 s grid
(grid = every 15 s slot from the first to the last WAV stamp of the night); outage slots (no WAV) are dropped AFTER selection and counted; the warm-up key is grid slot 0.
usage: python mk_selection_3n.py [out.json]   -> writes the JSON (same shape as selection_2n.json) and prints counts + the file's SHA-256 (for the freeze commit)."""
import datetime as dt
import hashlib
import json
import os
import sys

RUN = "20260930_1930"
WAVDIR = f"D:/Projects/claude/OpenWSFZ/artefacts/{RUN}_endurance_run-gathered/owsfz/wav"
STRIDE, OFFSET, SLOTS = 3, 1, 800
STEP = dt.timedelta(seconds=15)
FMT = "%y%m%d_%H%M%S"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "D:/Projects/claude/_qa-scratch/late-sub/selection_3n.json"
    have = sorted(f[:-4] for f in os.listdir(WAVDIR) if f.endswith(".wav"))
    t0, t1 = dt.datetime.strptime(have[0], FMT), dt.datetime.strptime(have[-1], FMT)
    grid, t = [], t0
    while t <= t1:
        grid.append(t.strftime(FMT))
        t += STEP
    present = set(have)
    slots = [grid[i] for i in range(OFFSET, len(grid), STRIDE)][:SLOTS]
    assert len(slots) == SLOTS, f"the grid has only {len(grid)} slots"
    full = [s for s in slots if s in present]
    dropped = len(slots) - len(full)
    warm = grid[0]
    assert warm in present, "the warm-up slot has no WAV"
    d = {"note": f"L1' third night: systematic sample, stride {STRIDE}, offset {OFFSET}, first {SLOTS} slots of the gap-inclusive 15 s grid; outage slots dropped after selection",
         "outage_dropped": dropped, "run": RUN, "runs": {RUN: {"FULL": full, "warmup": warm}}}
    json.dump(d, open(out, "w"), indent=1, sort_keys=True)
    sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
    print(json.dumps({"out": out, "wavs": len(have), "grid_slots": len(grid), "first_slot": grid[0], "last_slot": grid[-1], "selected_slots": len(slots),
                      "outage_dropped": dropped, "cycles": len(full), "first": full[0], "last": full[-1], "warmup": warm, "sha256": sha}, indent=1))


if __name__ == "__main__":
    main()
