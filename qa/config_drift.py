#!/usr/bin/env python3
"""config_drift.py -- watch a running daemon's config for drift during a measurement run.

Part E of the OpenSpec change `config-save-preserves-unsent-settings` (#193).

Why: #193 showed that a setting a run depends on (cycleAudioArchive.mode) can change mid-run and
nobody notices until the data is bad. The daemon already reports its config (HK-027), so this reads
`GET /api/v1/config`, takes a start snapshot of the watched keys, re-reads on an interval, and reports
any difference. It NEVER restores anything: a silent repair would hide the event.

Privacy (NFR-021 / HK-037): values are printed only for VALUE_ALLOWLIST (enum, boolean and numeric
decoder settings). Every other watched key, e.g. cycleAudioArchive.directory, is reported by PATH only.

Usage (detached, HK-023: `nohup ... & disown` plus a disposable `tail -f`):
    python qa/config_drift.py --base-url http://127.0.0.1:8080 --log run/config-drift.log \
        --snapshot run/config-snapshot.json --report run/config-drift-rows.jsonl [--abort-on-drift]

Exit codes: 0 stopped cleanly, 2 could not take the start snapshot, 3 drift seen with --abort-on-drift.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# What PRECHECK enforces at run start (spec section 6, minimum set). A key ending in ".*" is a prefix.
DEFAULT_WATCH: tuple[str, ...] = (
    "cycleAudioArchive.mode",
    "cycleAudioArchive.directory",
    "decodingEnabled",
    "decoder.*",
)

# Only these may have their VALUES written to a log or report. Everything else: path only.
VALUE_ALLOWLIST: tuple[str, ...] = (
    "cycleAudioArchive.mode",
    "decodingEnabled",
    "decoder.*",
)

DEFAULT_INTERVAL_S = 60.0
MAX_INTERVAL_S = 300.0  # spec: at most 5 minutes
HTTP_TIMEOUT_S = 5.0

EXIT_OK = 0
EXIT_NO_SNAPSHOT = 2
EXIT_DRIFT = 3

_MISSING = object()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested JSON objects to dotted paths. Lists and scalars are leaves."""
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict) and value:
                out.update(flatten(value, path))
            else:
                out[path] = value
    else:
        out[prefix] = obj
    return out


def _matches(path: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if pat.endswith(".*"):
            if path.startswith(pat[:-1]):
                return True
        elif path == pat:
            return True
    return False


def watched_view(config: dict, watch: Iterable[str] = DEFAULT_WATCH) -> dict[str, Any]:
    """The watched leaves of a config, as {dotted path: value}."""
    watch = tuple(watch)
    return {p: v for p, v in flatten(config).items() if _matches(p, watch)}


@dataclass(frozen=True)
class Drift:
    path: str
    old: Any  # _MISSING when the key was absent
    new: Any

    def render(self) -> str:
        if _matches(self.path, VALUE_ALLOWLIST):
            def show(v: Any) -> str:
                return "<absent>" if v is _MISSING else json.dumps(v)
            return f"{self.path} ({show(self.old)}->{show(self.new)})"
        return self.path

    def as_row(self, ts: str) -> dict:
        row: dict[str, Any] = {"utc": ts, "event": "CONFIG-DRIFT", "path": self.path}
        if _matches(self.path, VALUE_ALLOWLIST):
            row["old"] = None if self.old is _MISSING else self.old
            row["new"] = None if self.new is _MISSING else self.new
        return row


def compare(start: dict[str, Any], current: dict[str, Any]) -> list[Drift]:
    """Every watched path whose value differs from the start snapshot, sorted by path."""
    drifts = []
    for path in sorted(set(start) | set(current)):
        old, new = start.get(path, _MISSING), current.get(path, _MISSING)
        if old != new:
            drifts.append(Drift(path, old, new))
    return drifts


def fetch_config(base_url: str) -> dict:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/v1/config", timeout=HTTP_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8"))


class DriftWatcher:
    """Polls, compares to the start snapshot, and reports each change once (not every poll)."""

    def __init__(self, fetch: Callable[[], dict], log: Callable[[str], None],
                 report: Callable[[dict], None] | None = None,
                 watch: Iterable[str] = DEFAULT_WATCH) -> None:
        self._fetch, self._log, self._report = fetch, log, report
        self._watch = tuple(watch)
        self.start: dict[str, Any] = {}
        self._reported: dict[str, Any] = {}  # path -> current value last reported as drifted
        self.drift_seen = False
        self.poll_failures = 0

    def snapshot(self) -> dict[str, Any]:
        self.start = watched_view(self._fetch(), self._watch)
        self._log(f"CONFIG-SNAPSHOT watching {len(self.start)} keys: {', '.join(sorted(self.start))}")
        return self.start

    def poll(self) -> list[Drift]:
        """One poll. Returns the drifts NEWLY reported by this poll."""
        ts = utc_now()
        try:
            current = watched_view(self._fetch(), self._watch)
        except Exception as exc:  # daemon down or unreadable: not drift, but never silent
            self.poll_failures += 1
            self._log(f"CONFIG-POLL-FAILED {type(exc).__name__} (failure #{self.poll_failures})")
            return []
        new_reports: list[Drift] = []
        drifts = {d.path: d for d in compare(self.start, current)}
        for path, d in drifts.items():
            if path not in self._reported or self._reported[path] != d.new:
                self._reported[path] = d.new
                new_reports.append(d)
                self.drift_seen = True
                self._log(f"CONFIG-DRIFT {d.render()}")
                if self._report:
                    self._report(d.as_row(ts))
        for path in [p for p in self._reported if p not in drifts]:
            del self._reported[path]
            self._log(f"CONFIG-RESTORED {path}")
            if self._report:
                self._report({"utc": ts, "event": "CONFIG-RESTORED", "path": path})
        return new_reports

    def run(self, interval_s: float, stop: threading.Event, abort_on_drift: bool = False) -> int:
        while not stop.wait(interval_s):
            self.poll()
            if abort_on_drift and self.drift_seen:
                return EXIT_DRIFT
        return EXIT_OK


def _clamp_interval(value: float) -> float:
    return max(1.0, min(value, MAX_INTERVAL_S))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                    help=f"seconds between polls (clamped to 1..{MAX_INTERVAL_S:.0f})")
    ap.add_argument("--log", required=True, help="append CONFIG-* lines here (also echoed to stdout)")
    ap.add_argument("--snapshot", help="write the start snapshot (watched keys only) as JSON")
    ap.add_argument("--report", help="append one JSON row per drift event (for the run report)")
    ap.add_argument("--watch", action="append", help="extra dotted path or prefix.* to watch")
    ap.add_argument("--abort-on-drift", action="store_true", help="exit 3 on the first drift")
    args = ap.parse_args(argv)

    def log(msg: str) -> None:
        line = f"{utc_now()} {msg}"
        print(line, flush=True)
        with open(args.log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def report(row: dict) -> None:
        if args.report:
            with open(args.report, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")

    watcher = DriftWatcher(lambda: fetch_config(args.base_url), log, report,
                           tuple(DEFAULT_WATCH) + tuple(args.watch or ()))
    try:
        snap = watcher.snapshot()
    except Exception as exc:
        log(f"CONFIG-SNAPSHOT-FAILED {type(exc).__name__}: no start snapshot, drift cannot be checked")
        return EXIT_NO_SNAPSHOT
    if args.snapshot:
        with open(args.snapshot, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2, sort_keys=True)

    stop = threading.Event()
    try:
        return watcher.run(_clamp_interval(args.interval), stop, args.abort_on_drift)
    except KeyboardInterrupt:
        stop.set()
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
