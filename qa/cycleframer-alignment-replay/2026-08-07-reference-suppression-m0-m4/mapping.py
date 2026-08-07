"""The cross-session timestamp mapping (SS1.2) -- one implementation, shared by M1/M2's
offline analysis and M3/M4's live replay-count extraction, so there is exactly one place
this arithmetic can go wrong rather than two copies drifting apart.

Never derive this mapping by sorting distinct observed timestamps and zipping them
positionally against a window -- that only works while every cycle yields >=1 decode, and
fails silently (shifting every subsequent cycle) the first time one does not. Always derive
it arithmetically from the recorded pass start, per SS1.2.
"""
from __future__ import annotations

import datetime
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "endurance"))
from anova_common import parse_cycle_ts  # noqa: E402

SLOT_SECONDS = 15


def epoch_of(ts_token: str) -> float | None:
    dt = parse_cycle_ts(ts_token)
    if dt is None:
        return None
    return dt.replace(tzinfo=datetime.timezone.utc).timestamp()


def build_slot_map(pass_start_iso: str, window_cycles: list[str]) -> tuple[int, dict[float, str]]:
    """SS1.2's arithmetic, verbatim: snap UP to the first 15s boundary at or after pass
    start (play_pass()/play_pass_guarded() record pass_start 0.5s BEFORE the boundary they
    waited for, so snapping up recovers it). `window_cycles` is an ordered list of bare
    cycle tokens (no `.wav`), slot i is assumed to have played window_cycles[i]."""
    start = datetime.datetime.fromisoformat(pass_start_iso)
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    b0_epoch = math.ceil(start.timestamp() / SLOT_SECONDS) * SLOT_SECONDS
    slot_of = {b0_epoch + i * SLOT_SECONDS: window_cycles[i] for i in range(len(window_cycles))}
    return b0_epoch, slot_of


def map_rows_to_cycles(rows: list[dict], pass_start_iso: str,
                        window_cycles: list[str]) -> tuple[list[dict], int]:
    """Returns (mapped_rows, b0_epoch). Each mapped row gains `corpus_cycle` and `_epoch`.
    Rows whose epoch does not land on one of this pass's 20 slots are dropped silently here
    -- callers that need the SS1.3 assertions (M1/M2) run them explicitly on the result;
    M3/M4's live single-session counts don't require the full assertion set (no cross-
    session ambiguity to guard against there) but reuse the same arithmetic for consistency.
    """
    b0_epoch, slot_map = build_slot_map(pass_start_iso, window_cycles)
    mapped = []
    for r in rows:
        t = epoch_of(r["ts"])
        if t is None:
            continue
        cycle = slot_map.get(t)
        if cycle is not None:
            mapped.append({**r, "corpus_cycle": cycle, "_epoch": t})
    return mapped, b0_epoch


def assert_mandatory(run_label: str, mapped_rows: list[dict], b0_epoch: int,
                      window_cycles: list[str], normalize_fn) -> None:
    """SS1.3's four mandatory assertions, applied to an already-mapped row set."""
    mapped_cycles = [m["corpus_cycle"] for m in mapped_rows]
    keys = [(m["corpus_cycle"], normalize_fn(m["message"])) for m in mapped_rows]
    window_set = set(window_cycles)

    assert set(mapped_cycles) <= window_set, (
        f"{run_label}: mapped cycle(s) outside the window -- mapping is broken")
    assert len(set(mapped_cycles)) == len(window_cycles), (
        f"{run_label}: only {len(set(mapped_cycles))}/{len(window_cycles)} cycles "
        f"represented in the mapped decodes")
    assert all((m["_epoch"] - b0_epoch) % SLOT_SECONDS == 0 for m in mapped_rows), (
        f"{run_label}: a mapped decode's epoch is off the 15s grid -- arithmetic error")
    assert len(mapped_rows) == len(set(keys)), (
        f"{run_label}: duplicate (cycle, message) pair(s) in mapped decodes -- the exact "
        f"defect that invalidated jt9 -d 3 and VOIDed Angle 1; re-assert mechanically")
