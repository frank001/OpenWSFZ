"""Scenario-level retry for the R&R battery (QA tooling; Captain 2026-10-14: "the 3-retry cap should be within trials, not as a whole. I don't care how long it takes,
only that it completes"; Architect amendment 3 item 5, arch/s6-in-battery a714d3d4).

The retry unit is the SCENARIO that stalled (S1-S8, S3c and S6 alike), never a single trial or play (a part's trials must come from ONE WSJT-X session: trial index and
play order are read). On an M2 stop, or a coverage failure (M3 for S1-S8, S6-V7 for S6), `run_study.py` restarts WSJT-X and reruns that one scenario with all its trials in the
SAME run folder; the failed attempt is KEPT as INVALID and a replacement is recorded; passed scenarios stay. At most `cap` retries PER SCENARIO: the next failure of the same
scenario halts and flags. Any non-stall failure still halts at once.

What "setting a failed attempt aside" means, so the INVALID data is neither lost nor mixed into the valid data:
  * its truth rows leave `truth.csv` (the seeds are fixed, so the rerun writes the same signals at new cycle times) and are kept in `truth_INVALID_<sid>_attempt<k>.csv`;
  * its own output folder (`s6/`, `s3c/`) is renamed `<name>-INVALID-attempt<k>`;
  * its cycles are remembered, and the run folder's COPIES of the two ALL.TXT logs are stripped of the lines stamped in them (the live logs stay untouched), so no decode
    of an INVALID attempt reaches the matcher, the analyser or the unexplained-decodes count. Aggregates only: no text is stored.
Every attempt is recorded in `scenario_retries.json` (the stall row's source: attempts / stalls / replacements per scenario and in total).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime, timezone

from harness import liveness as LV

SCENARIO_DIRS = {"S6": "s6", "S3c": "s3c"}          # scenarios that write their own output folder in the run folder; the others live in truth.csv


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_truth(run_dir: str):
    p = os.path.join(run_dir, "truth.csv")
    if not os.path.isfile(p):
        return None, []
    with open(p, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames, list(rd)


def _s6_playlogs(run_dir: str) -> list:
    """The S6 play logs of a run folder: the top-level one (a concurrent S6, or the MERGED log of a sequential S6) and the per-pass logs of a sequential S6
    (s6/pass-w, s6/pass-o), which exist even when a pass died before the merge."""
    base = os.path.join(run_dir, "s6")
    out = [os.path.join(base, "s6_playlog.jsonl")]
    try:
        out += [os.path.join(base, d, "s6_playlog.jsonl") for d in sorted(os.listdir(base)) if d.startswith("pass-")]
    except OSError:
        pass
    return [p for p in out if os.path.isfile(p)]


def scenario_cycles(run_dir: str, sid: str) -> list:
    """Distinct cycle stamps (ISO, UTC) of the scenario's rows in truth.csv; for S6 the slots of its playlog(s) (warm-up and plays; for a sequential S6 the slots of both passes)."""
    if sid == "S6":
        out = set()
        for p in _s6_playlogs(run_dir):
            try:
                with open(p, encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            r = json.loads(line)
                            for key in ("slot_stamp", "slot_stamp_o"):
                                iso = LV.stamp_to_iso(r.get(key, ""))
                                if iso:
                                    out.add(iso)
            except OSError:
                pass
        return sorted(out)
    _, rows = _read_truth(run_dir)
    return sorted({r["cycle_utc"] for r in rows if r.get("scenario_id") == sid and r.get("cycle_utc")})


def play_slots(run_dir: str, appraiser: str = "wsjtx") -> list:
    """S6: the play slots only (no warm-up), in order, of the MERGED / concurrent play log. A sequential S6 has two sets (the passes played the same plays in different slots):
    'wsjtx' = the WSJT-X pass's `slot_stamp`, 'owsfz' = the OpenWSFZ pass's `slot_stamp_o` (a concurrent S6 has no `slot_stamp_o`: both are the one slot)."""
    out = []
    key = "slot_stamp_o" if appraiser == "owsfz" else "slot_stamp"
    try:
        with open(os.path.join(run_dir, "s6", "s6_playlog.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    if r.get("kind") == "play":
                        iso = LV.stamp_to_iso(r.get(key) or r.get("slot_stamp", ""))
                        if iso:
                            out.append(iso)
    except OSError:
        pass
    return out


def coverage_failure(run_dir: str, sid: str, wsjtx_slots: set, owsfz_slots: set | None) -> dict | None:
    """After a scenario: None if both appraisers have data, else {"reason": ...}. S1-S8: fewer cycles with data than (expected - 1) (the M3 rule); S6: ANY play slot missing (S6-V7);
    S3c is not in truth.csv and is covered by the stall gate only."""
    if sid == "S6":
        want = play_slots(run_dir, "wsjtx")
        want_o = play_slots(run_dir, "owsfz")           # sequential S6: the OpenWSFZ pass's own slots
        if not want:
            return {"reason": "S6 wrote no play slots"}
        miss_w = [w for w in want if w not in wsjtx_slots]
        miss_o = [w for w in want_o if owsfz_slots is not None and w not in owsfz_slots]
        if miss_w or miss_o:
            return {"reason": "S6-V7: %d play slot(s) without a WSJT-X save WAV, %d without an OpenWSFZ archive cycle (bar 0)" % (len(miss_w), len(miss_o))}
        return None
    if sid == "S3c":
        return None
    exp = scenario_cycles(run_dir, sid)
    if not exp:
        return None
    bad = []
    for name, slots in (("WSJT-X", wsjtx_slots), ("OpenWSFZ", owsfz_slots)):
        if slots is None:
            continue
        for row in LV.coverage_rows({sid: exp}, slots, name):
            if row["result"] == "FAIL":
                bad.append("%s has data for only %d of %d cycles of %s (needs >= %d)" % (name, row["with_data"], row["expected"], sid, row["required"]))
    return {"reason": "coverage: " + "; ".join(bad)} if bad else None


def set_aside(run_dir: str, sid: str, attempt: int) -> dict:
    """Keep the failed attempt as INVALID and take it out of the data the matcher and analyser read. Returns what was moved."""
    cycles = scenario_cycles(run_dir, sid)
    moved: list = []
    n_rows = 0
    if sid in SCENARIO_DIRS:
        src = os.path.join(run_dir, SCENARIO_DIRS[sid])
        if os.path.isdir(src):
            dst = src + "-INVALID-attempt%d" % attempt
            shutil.move(src, dst)
            moved.append(os.path.basename(dst))
    fields, rows = _read_truth(run_dir)
    if rows and sid not in SCENARIO_DIRS:
        keep = [r for r in rows if r.get("scenario_id") != sid]
        gone = [r for r in rows if r.get("scenario_id") == sid]
        n_rows = len(gone)
        if gone:
            side = os.path.join(run_dir, "truth_INVALID_%s_attempt%d.csv" % (sid, attempt))
            with open(side, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(gone)
            moved.append(os.path.basename(side))
            with open(os.path.join(run_dir, "truth.csv"), "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(keep)
    return {"cycles": cycles, "truth_rows_set_aside": n_rows, "moved": moved}


def drop_cycles_from_log(path: str, cycles_iso: set) -> int:
    """Remove from a COPY of an ALL.TXT every line whose leading stamp (yymmdd_HHMMSS) is one of `cycles_iso`; returns the number of lines removed. Text is not kept."""
    if not cycles_iso or not os.path.isfile(path):
        return 0
    stamps = {c.replace("-", "")[2:].replace("T", "_").replace(":", "").rstrip("Z") for c in cycles_iso}      # 2026-10-14T11:09:30Z -> 261014_110930
    kept, dropped = [], 0
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            tok = line.split(None, 1)[0] if line.strip() else ""
            if tok in stamps:
                dropped += 1
            else:
                kept.append(line)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(kept)
    return dropped


class Ledger:
    """Attempts, failures and replacements per scenario; written to scenario_retries.json after every change."""

    def __init__(self, run_dir: str, cap: int):
        self.run_dir, self.cap = run_dir, cap
        self.sc: dict = {}
        self.invalid_cycles: set = set()

    def _s(self, sid: str) -> dict:
        return self.sc.setdefault(sid, {"attempts": 0, "failed": [], "retries_used": 0})

    def start(self, sid: str) -> int:
        s = self._s(sid)
        s["attempts"] += 1
        return s["attempts"]

    def retries_used(self, sid: str) -> int:
        return self._s(sid)["retries_used"]

    def fail(self, sid: str, kind: str, reason: str, aside: dict, will_retry: bool) -> None:
        s = self._s(sid)
        s["failed"].append({"attempt": s["attempts"], "kind": kind, "reason": reason, "utc": utc_now(), "set_aside": {k: v for k, v in aside.items() if k != "cycles"},
                            "cycles_set_aside": len(aside.get("cycles", [])), "replaced_by_attempt": (s["attempts"] + 1) if will_retry else None})
        if will_retry:
            s["retries_used"] += 1
        self.invalid_cycles |= set(aside.get("cycles", []))
        self.write()

    def write(self) -> None:
        tot_fail = sum(len(v["failed"]) for v in self.sc.values())
        doc = {"cap_retries_per_scenario": self.cap, "scenarios": self.sc,
               "totals": {"scenario_attempts": sum(v["attempts"] for v in self.sc.values()), "failed_attempts": tot_fail, "replacements": sum(v["retries_used"] for v in self.sc.values())}}
        with open(os.path.join(self.run_dir, "scenario_retries.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1)
