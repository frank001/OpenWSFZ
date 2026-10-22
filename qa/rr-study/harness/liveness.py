"""WSJT-X liveness (M2) and per-scenario coverage (M3) for the R&R battery (QA tooling; no message text is read or written).

Why (2026-10-14, qa/rr-study/2026-10-14-1830-qa-plan-wsjtx-stall-monitoring-and-gate.md, drafted with the Architect): WSJT-X 2.7.0 on `sol` twice
stopped taking in audio mid-battery (11 Oct idle; 14 Oct in scenario S4) with no trace in any log; the start-up warm-up check ran once and could not see it.
The signal used here is the one the 14 Oct stall showed: WSJT-X's own per-cycle `save/` WAVs (SaveAll true in the `rr` profile) stop arriving. A WAV is
written for EVERY 15 s cycle whether or not anything decodes (S5 has no signals, so ALL.TXT cannot be the evidence), and OpenWSFZ's cycle-audio archive
uses the same `yymmdd_HHMMSS.wav` names, so the same code covers both appraisers.

Rules (the Architect, 2026-10-14):
  * stall = no new save WAV for more than `STALL_S` seconds (3 cycles, 45 s), or no `wsjtx` process (taken from /proc by the real binary name, never the
    `xvfb-run` wrapper);
  * the battery STOPS AND FLAGS (no automatic restart, no silent recovery);
  * coverage FAIL = a scenario whose number of cycles with data is below (expected cycles - 1) for an appraiser; that makes the sweep INVALID, triggered by
    missing data and never by a result.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

STALL_S = 45.0               # 3 cycles (the Architect's rule)
POLL_S = 15.0                # one cycle
COVERAGE_SLACK = 1           # a scenario passes with at least (expected - 1) cycles with data
WSJTX_COMM = "wsjtx"         # /proc/<pid>/comm of the real binary (the xvfb-run wrapper is a different comm)
JT9_COMM = "jt9"


def stamp_to_iso(stem: str) -> str | None:
    """'261014_110930' -> '2026-10-14T11:09:30Z' (None if the name is not a cycle stamp)."""
    try:
        d = datetime.strptime(stem[:13], "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def list_wav_slots(directory: str, start_utc: datetime | None = None, end_utc: datetime | None = None) -> set[str]:
    """The cycle slots (ISO, UTC) for which `directory` holds a WAV, optionally restricted to [start_utc, end_utc]. Names only, no content."""
    out: set[str] = set()
    try:
        names = os.listdir(directory)
    except OSError:
        return out
    for n in names:
        if not n.lower().endswith(".wav"):
            continue
        iso = stamp_to_iso(n)
        if iso is None:
            continue
        t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if (start_utc is None or t >= start_utc) and (end_utc is None or t <= end_utc):
            out.add(iso)
    return out


def newest_wav_age_s(directory: str, now: float) -> float | None:
    """Seconds since the newest WAV in `directory` was last written (None if there is none or the folder is unreadable)."""
    newest = None
    try:
        with os.scandir(directory) as it:
            for e in it:
                if e.name.lower().endswith(".wav"):
                    m = e.stat().st_mtime
                    if newest is None or m > newest:
                        newest = m
    except OSError:
        return None
    return None if newest is None else max(0.0, now - newest)


def pids_by_comm(comm: str, proc_root: str = "/proc") -> list[int]:
    """PIDs whose /proc/<pid>/comm equals `comm` exactly (the real binary, not a shell wrapper whose command line merely mentions it)."""
    out: list[int] = []
    try:
        names = os.listdir(proc_root)
    except OSError:
        return out
    for n in names:
        if not n.isdigit():
            continue
        try:
            with open(os.path.join(proc_root, n, "comm"), encoding="utf-8", errors="replace") as fh:
                if fh.read().strip() == comm:
                    out.append(int(n))
        except OSError:
            continue
    return sorted(out)


@dataclass
class Liveness:
    ok: bool
    reason: str
    age_s: float | None
    pids: list


def check_liveness(save_dir: str, stall_s: float = STALL_S, now: float | None = None, proc_root: str = "/proc", require_process: bool = True) -> Liveness:
    """One reading: alive and a WAV newer than `stall_s`. `now` and `proc_root` are injectable for tests."""
    now = time.time() if now is None else now
    pids = pids_by_comm(WSJTX_COMM, proc_root) if require_process else []
    age = newest_wav_age_s(save_dir, now)
    if require_process and not pids:
        return Liveness(False, "no wsjtx process", age, pids)
    if age is None:
        return Liveness(False, "no save WAV found in %s" % save_dir, age, pids)
    if age > stall_s:
        return Liveness(False, "no new save WAV for %.0f s (limit %.0f s)" % (age, stall_s), age, pids)
    return Liveness(True, "ok", age, pids)


class Watchdog(threading.Thread):
    """Polls `check_liveness` every `poll_s`; on the first failed reading it records the reading, calls `on_stall(reading)` once and stops.
    It never restarts or kills anything itself: the caller decides (the battery stops and flags)."""

    def __init__(self, save_dir: str, on_stall: Callable[[Liveness], None], stall_s: float = STALL_S, poll_s: float = POLL_S,
                 clock: Callable[[], float] = time.time, proc_root: str = "/proc", require_process: bool = True):
        super().__init__(daemon=True, name="wsjtx-liveness-watchdog")
        self.save_dir, self.on_stall, self.stall_s, self.poll_s = save_dir, on_stall, stall_s, poll_s
        self.clock, self.proc_root, self.require_process = clock, proc_root, require_process
        self.stop_event = threading.Event()
        self.stalled: Liveness | None = None

    def run(self) -> None:
        while not self.stop_event.is_set():
            r = check_liveness(self.save_dir, self.stall_s, self.clock(), self.proc_root, self.require_process)
            if not r.ok:
                self.stalled = r
                self.on_stall(r)
                return
            self.stop_event.wait(self.poll_s)

    def stop(self) -> None:
        self.stop_event.set()


# ----------------------------------------------------------------------------------------------------------------------------- coverage (M3)
def coverage_rows(expected: dict[str, Iterable[str]], slots: set[str], appraiser: str, slack: int = COVERAGE_SLACK) -> list[dict]:
    """Per scenario: expected distinct cycles (from truth.csv) against the cycles with data. FAIL when with_data < expected - slack."""
    rows = []
    for scen in sorted(expected):
        cyc = sorted(set(expected[scen]))
        have = [c for c in cyc if c in slots]
        need = max(0, len(cyc) - slack)
        rows.append({"appraiser": appraiser, "scenario": scen, "expected": len(cyc), "with_data": len(have), "required": need, "result": "PASS" if len(have) >= need else "FAIL"})
    return rows


def write_slots(path: str, slots: set[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sorted(slots)) + ("\n" if slots else ""))


def read_slots(path: str) -> set[str] | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return {l.strip() for l in fh if l.strip()}
    except OSError:
        return None
