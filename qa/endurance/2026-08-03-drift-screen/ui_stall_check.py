#!/usr/bin/env python3
"""Pre-registered check: does opening the 8080 decoder-settings page stall the heartbeat?

WRITTEN AND COMMITTED BEFORE THE REPRODUCTION ATTEMPT, outcome unknown. Per HK-021 the
rule is mechanical: hard thresholds, consequence as an assertion, rows mutually exclusive
and evaluated in strict order, first match wins. Report the row it fires verbatim.

Background. On 2026-08-03 the 8080 daemon (PID 14600, up 1h45m, no [ERR]/[FTL]) went silent
while the Captain viewed the decoder-settings page; the supervisor detected a >90 s heartbeat
stall at 18:58:09Z and restarted it, costing 4 cycles and resetting the drift-screen epoch.
config.json was unmodified, so nothing was written -- a read-only page appeared to stall the
capture heartbeat. One occurrence is correlation, not cause. This check tests the second.

Baseline cadence measured before the attempt: heartbeat every 5.00 s, eleven consecutive
intervals, zero jitter beyond 10 ms.

    python ui_stall_check.py --log <daemon.log> --open-time 2026-08-03T19:12:00Z

ROWS (strict order, first match wins):

  1 VOID          a gap >= STALL_SECONDS occurs in the BASELINE window before --open-time.
                  The daemon was already unstable, so nothing after it can be attributed to
                  the page. No verdict. Re-run on a clean baseline.

  2 CONFIRMED     no such baseline gap, AND a gap >= STALL_SECONDS begins within
                  ATTRIB_SECONDS after --open-time.
                  ==> the page is implicated; file the defect.

  3 SUSPICIOUS    no such baseline gap, AND the largest gap in the attribution window is
                  >= SOFT_SECONDS but < STALL_SECONDS.
                  ==> a real perturbation that did not reach the supervisor's bar. Not a
                  confirmation. Needs a third attempt; do NOT file on this alone.

  4 NOT REPRODUCED  none of the above within WATCH_SECONDS of --open-time.
                  ==> one negative does NOT clear the daemon. The first event still happened.

Deliberately no row votes "the page is safe". The strongest available negative is
NOT REPRODUCED, because a single non-recurrence cannot disprove an intermittent hang.
"""

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone

# The supervisor's own bar: >90 s without a heartbeat is what triggered the restart.
STALL_SECONDS = 90.0
# A perturbation worth naming but below the supervisor's bar. 6x the 5.00 s cadence.
SOFT_SECONDS = 30.0
# A stall must BEGIN within this long after the page opens to be attributable to it.
ATTRIB_SECONDS = 180.0
# Total window examined after the page opens.
WATCH_SECONDS = 300.0
# Baseline window before the page opens, which must be clean for attribution to be possible.
BASELINE_SECONDS = 900.0

TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) ([+-]\d{2}:\d{2})")


def heartbeat_times(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "Heartbeat:" not in line:
                continue
            m = TS.match(line)
            if not m:
                continue
            stamp = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
            sign = 1 if m.group(2)[0] == "+" else -1
            oh, om = int(m.group(2)[1:3]), int(m.group(2)[4:6])
            out.append((stamp - sign * timedelta(hours=oh, minutes=om)).replace(tzinfo=timezone.utc))
    return sorted(out)


def gaps(times, lo, hi):
    """Gaps whose START falls in [lo, hi). Returns (start, seconds) list."""
    found = []
    for a, b in zip(times, times[1:]):
        if lo <= a < hi:
            found.append((a, (b - a).total_seconds()))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, action="append",
                    help="daemon log; repeat for the log the stall began in plus its successor")
    ap.add_argument("--open-time", required=True, help="UTC instant the settings page was opened")
    args = ap.parse_args()

    t0 = datetime.strptime(args.open_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    times = []
    for p in args.log:
        times.extend(heartbeat_times(p))
    times.sort()
    if len(times) < 2:
        print("ROW 1 VOID -- fewer than 2 heartbeats found; nothing to measure.")
        return 1

    base = gaps(times, t0 - timedelta(seconds=BASELINE_SECONDS), t0)
    attrib = gaps(times, t0, t0 + timedelta(seconds=ATTRIB_SECONDS))
    watch = gaps(times, t0, t0 + timedelta(seconds=WATCH_SECONDS))

    base_max = max((g for _, g in base), default=0.0)
    attrib_max = max((g for _, g in attrib), default=0.0)
    watch_max = max((g for _, g in watch), default=0.0)

    print(f"page opened      : {t0:%Y-%m-%dT%H:%M:%SZ}")
    print(f"heartbeats read  : {len(times)}")
    print(f"baseline  ({BASELINE_SECONDS:.0f}s) max gap : {base_max:6.1f}s   ({len(base)} intervals)")
    print(f"attribution ({ATTRIB_SECONDS:.0f}s) max gap : {attrib_max:6.1f}s   ({len(attrib)} intervals)")
    print(f"watch     ({WATCH_SECONDS:.0f}s) max gap : {watch_max:6.1f}s   ({len(watch)} intervals)")
    print()

    if base_max >= STALL_SECONDS:
        print(f"ROW 1 VOID -- baseline already carried a {base_max:.1f}s gap (>= {STALL_SECONDS}s). "
              f"Attribution impossible; no verdict.")
        return 0
    if attrib_max >= STALL_SECONDS:
        print(f"ROW 2 CONFIRMED -- {attrib_max:.1f}s stall (>= {STALL_SECONDS}s) began within "
              f"{ATTRIB_SECONDS:.0f}s of the page opening, on a clean baseline. "
              f"==> the settings page is implicated; file the defect.")
        return 0
    if watch_max >= SOFT_SECONDS:
        print(f"ROW 3 SUSPICIOUS -- largest gap {watch_max:.1f}s is >= {SOFT_SECONDS}s but below "
              f"the {STALL_SECONDS}s bar. A real perturbation, NOT a confirmation. "
              f"==> third attempt required; do not file on this alone.")
        return 0
    print(f"ROW 4 NOT REPRODUCED -- no gap >= {SOFT_SECONDS}s within {WATCH_SECONDS:.0f}s "
          f"(largest {watch_max:.1f}s). This does NOT clear the daemon: the 18:58Z event "
          f"still occurred and remains unexplained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
