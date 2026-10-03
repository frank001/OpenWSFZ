"""Per-call decode time inside versus outside a UTC window, for one arm's log (aggregate lines only; no message text).

The harness log has one line per decode call: `<UTC ISO timestamp> [Information] Cycle HH:MM:SS: N decode(s) found, elapsed=MS ms.`
(the timestamp is when the call ended). Used for the gate 4a report: "did the Engineer's small tests, run while an arm
was being timed, move that arm's decode times?" (Architect, 2026-10-03).

  python timing_window.py _out/x17/log_T.txt 2026-10-03T13:54:17Z 2026-10-03T13:55:48Z
"""
import re
import statistics
import sys
from datetime import datetime, timezone

LINE = re.compile(r"^(\S+Z) \[Information\] Cycle \S+: \d+ decode\(s\) found, elapsed=(\d+) ms\.")


def ts(s: str) -> datetime:
    s = s.rstrip("Z")
    return datetime.fromisoformat(s[:26] if "." in s else s).replace(tzinfo=timezone.utc)


def p95(v):
    v = sorted(v)
    return v[max(0, int(0.95 * len(v)) - 1)]


def main() -> int:
    log, lo, hi = sys.argv[1], ts(sys.argv[2]), ts(sys.argv[3])
    inside, outside = [], []
    for line in open(log, encoding="utf-8", errors="replace"):
        m = LINE.match(line)
        if not m:
            continue
        t, ms = ts(m.group(1)), int(m.group(2))
        (inside if lo <= t <= hi else outside).append(ms)
    for name, v in (("inside", inside), ("outside", outside)):
        if v:
            print(f"{name}: n={len(v)} median={statistics.median(v):.0f} ms p95={p95(v)} ms")
        else:
            print(f"{name}: n=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
