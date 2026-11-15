"""Remove the Captain-ruled monitoring-test windows from the gathered ALL.TXT pair.

Lines are matched by their leading YYMMDD_HHMMSS timestamp only. Message text is never
printed. A 15 s cycle is dropped if it overlaps any window.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

G = Path(r"D:\Projects\claude\OpenWSFZ\artefacts\20261004_1634_endurance_run-gathered")
OUT = G / "excl"
D = "2026-10-04 "
WINDOWS = [("18:14:31", "18:16:17"), ("18:36:20", "18:36:58"),
           ("18:40:21", "18:42:14"), ("18:48:15", "18:50:00")]
W = [(datetime.fromisoformat(D + a), datetime.fromisoformat(D + b)) for a, b in WINDOWS]


def hit(t):
    return any(t + timedelta(seconds=15) > a and t < b for a, b in W)


for app in ("owsfz", "wsjt-x"):
    src = G / app / "ALL.TXT"
    (OUT / app).mkdir(parents=True, exist_ok=True)
    kept = dropped = 0
    dropped_cycles = set()
    with open(src, encoding="utf-8", errors="replace", newline="") as f, \
            open(OUT / app / "ALL.TXT", "w", encoding="utf-8", newline="") as o:
        for line in f:
            try:
                t = datetime.strptime(line[:13], "%y%m%d_%H%M%S")
            except ValueError:
                o.write(line); kept += 1; continue
            if hit(t):
                dropped += 1; dropped_cycles.add(line[:13])
            else:
                o.write(line); kept += 1
    print(app, "kept", kept, "dropped lines", dropped, "dropped cycles", len(dropped_cycles))
