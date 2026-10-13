"""Mechanical warm-up check, run before scenario 1 (QA tooling, 2026-10-13; the decode half of the "WSJT-X alive and decoding" PRECHECK).

The battery's own warm-up asks the operator "did both apps decode?" and the supervised (detached) runs pass --skip-warmup, so nothing checked it:
the Linux repeats of 2026-10-11 ran with WSJT-X silent. This plays the same synthetic Q-prefix warm-up cycle and demands that BOTH ALL.TXT files
gain at least one line stamped with that cycle's slot (up to 3 attempts), otherwise the battery STOPS before scenario 1 and says which appraiser
was silent. Counts only; no text is read beyond the first token (the slot stamp) of each new line.

    ok, result = mechanical_warmup(play, wsjt_all_txt, owsfz_all_txt)

`play(buf, boundary_ts)` starts the sound at the slot boundary (injected, so the logic is testable without audio); `render()` returns the cycle.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

SLOT_S = 15
SETTLE_S = 22.0            # after the slot's end: both decoders have written their lines (the S6 player's figure)
ATTEMPTS = 3
LEAD_S = 20                # the next boundary at least this far ahead


def slot_stamp(boundary_ts: float) -> str:
    return datetime.fromtimestamp(boundary_ts, tz=timezone.utc).strftime("%y%m%d_%H%M%S")


def next_boundary(now: float) -> float:
    return float(int(now) // SLOT_S * SLOT_S + SLOT_S)


def size(path: str) -> int:
    return os.path.getsize(path) if os.path.isfile(path) else 0


def lines_for_slot(path: str, pos: int, stamp: str) -> int:
    if not os.path.isfile(path):
        return 0
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(pos)
        for line in fh:
            t = line.split(None, 1)
            if t and t[0] == stamp:
                n += 1
    return n


def mechanical_warmup(play, wsjt_all: str, owsfz_all: str, attempts: int = ATTEMPTS, clock=time.time, sleep=time.sleep) -> tuple:
    """-> (ok, result dict). `play(boundary_ts)` must start the warm-up cycle's sound at that boundary and return when it has finished."""
    rows = []
    for attempt in range(1, attempts + 1):
        wpos, opos = size(wsjt_all), size(owsfz_all)
        b = next_boundary(clock() + LEAD_S)
        d = b - clock()
        if d > 0:
            sleep(d)
        play(b)
        end = b + SLOT_S + SETTLE_S
        d = end - clock()
        if d > 0:
            sleep(d)
        stamp = slot_stamp(b)
        cw, co = lines_for_slot(wsjt_all, wpos, stamp), lines_for_slot(owsfz_all, opos, stamp)
        rows.append({"attempt": attempt, "slot_stamp": stamp, "wsjtx_lines": cw, "owsfz_lines": co})
        if cw >= 1 and co >= 1:
            return True, {"ok": True, "attempts": rows}
    silent = [name for name, key in (("WSJT-X", "wsjtx_lines"), ("OpenWSFZ", "owsfz_lines")) if all(r[key] == 0 for r in rows)]
    return False, {"ok": False, "attempts": rows, "silent_appraisers": silent,
                   "message": "the warm-up cycle was not decoded by %s after %d attempt(s); the battery stops before scenario 1" % (" and ".join(silent) or "both", len(rows))}
