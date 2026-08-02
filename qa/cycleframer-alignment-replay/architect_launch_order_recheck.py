#!/usr/bin/env python3
"""Architect re-check of the 2026-08-02 WSJT-X launch-order diagnostic.

Produces the three tables cited in
`2026-08-02-2232-architect-to-qa-correction-launch-order-not-established.md`:

  TABLE 1  decodes per cycle, restricted to cycles logged by ALL THREE WSJT-X
           instances, with SDRUno as an external reference leg.
  TABLE 2  FT8 sequence-parity split (even/odd), per instance per 15-min block.
  TABLE 3  hash-token (`<...>`) decode share, OpenWSFZ vs WSJT-X.

Written by Architect, not QA. The figures in the note are hypotheses until QA
re-runs this; per the 1813 hand-off's standing note, QA's measurement wins over
the Architect's number where they disagree.

Paths below point at live artefacts OUTSIDE the repo (AppData profiles, capture
folders). They are session-specific and will not exist on a clean checkout --
edit PROFILES / OPENWSFZ_LOGS to re-point. Nothing here writes.

Output is ASCII-only aggregate counts (HK-009 console encoding, NFR-021: no
callsigns are printed, only counts).
"""

from __future__ import annotations

import datetime
import io
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # HK-009
except AttributeError:  # pragma: no cover
    pass

# --- session-specific artefact paths -------------------------------------

APPDATA = r"C:\Users\Frank\AppData\Local"

PROFILES = {
    "FT991A": APPDATA + r"\WSJT-X - FT991A\ALL.TXT",
    "FT991A-Copy": APPDATA + r"\WSJT-X - FT991A-Copy\ALL.TXT",
    "SDRUno": APPDATA + r"\WSJT-X - SDRUno\ALL.TXT",
}

OPENWSFZ_LOGS = {
    "8080 corpus (multiday 20m)":
        r"D:\Projects\claude\2026-08-02-multiday-20m-anova OpenWSFZ-8080-capture\ALL.TXT",
    "8081 corpus (multiday 20m)":
        r"D:\Projects\claude\2026-08-02-multiday-20m-anova OpenWSFZ-8081-capture\ALL.TXT",
    "8080 diagnostic (22 min)":
        r"D:\Projects\claude\OpenWSFZ-8080-capture\ALL.TXT",
    "8081 diagnostic (22 min)":
        r"D:\Projects\claude\OpenWSFZ-8081-capture\ALL.TXT",
}

MIN_COMMON_CYCLES = 40  # blocks thinner than this are dropped from TABLE 1
BLOCK_MINUTES = 15

_TS_RE = re.compile(r"^(\d{6})_(\d{6})\s")
_HASH_RE = re.compile(r"<[^>]*>")
_MYCALL = "PD2FZ"  # NFR-021 exception: the Captain's own callsign, counts only


def load_rx_timestamps(path: str) -> list[datetime.datetime]:
    """Cycle timestamps of every Rx decode line in a WSJT-X ALL.TXT."""
    out: list[datetime.datetime] = []
    with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _TS_RE.match(line)
            if not m or " Rx " not in line:
                continue
            d, t = m.group(1), m.group(2)
            out.append(datetime.datetime(
                2000 + int(d[0:2]), int(d[2:4]), int(d[4:6]),
                int(t[0:2]), int(t[2:4]), int(t[4:6])))
    return out


def block_of(ts: datetime.datetime) -> datetime.datetime:
    return ts.replace(minute=(ts.minute // BLOCK_MINUTES) * BLOCK_MINUTES,
                      second=0, microsecond=0)


def table1_common_cycles(data: dict[str, list[datetime.datetime]]) -> None:
    names = list(PROFILES)
    sets = {n: set(data[n]) for n in names}
    common = sets[names[0]] & sets[names[1]] & sets[names[2]]

    print("TABLE 1 -- decodes per cycle on cycles logged by ALL THREE instances")
    print("cycles common to all three: %d" % len(common))
    print("(blocks with fewer than %d common cycles are dropped)" % MIN_COMMON_CYCLES)
    print()
    print("%-8s | %5s | %8s %8s %8s | %8s %8s %8s"
          % ("block", "ncyc", "FT991A", "Copy", "SDRUno",
             "FT/Copy", "FT/SDR", "Copy/SDR"))
    print("-" * 76)

    for blk in sorted({block_of(c) for c in common}):
        end = blk + datetime.timedelta(minutes=BLOCK_MINUTES)
        cyc = {c for c in common if blk <= c < end}
        if len(cyc) < MIN_COMMON_CYCLES:
            continue
        n = len(cyc)
        per = {nm: sum(1 for t in data[nm] if t in cyc) / n for nm in names}
        ft, cp, sd = per["FT991A"], per["FT991A-Copy"], per["SDRUno"]
        print("%-8s | %5d | %8.2f %8.2f %8.2f | %8.3f %8.3f %8.3f"
              % (blk.strftime("%H:%M"), n, ft, cp, sd, ft / cp, ft / sd, cp / sd))
    print()
    print("Read: FT/Copy is the paired ratio QA's note reports. FT/SDR and")
    print("Copy/SDR add the external reference leg that decides which of the")
    print("pair actually moved.")
    print()


def table2_parity(data: dict[str, list[datetime.datetime]]) -> None:
    print("TABLE 2 -- FT8 sequence parity (even = ss in {00,30}, odd = {15,45})")
    print("A decoder dropping one sequence would show odd/even near 0 or near 2.")
    print()
    print("%-8s | %-14s | %7s %7s %7s | %8s"
          % ("block", "instance", "even", "odd", "total", "odd/even"))
    print("-" * 66)
    blocks = sorted({block_of(t) for n in PROFILES for t in data[n]})
    for blk in blocks:
        end = blk + datetime.timedelta(minutes=BLOCK_MINUTES)
        for name in PROFILES:
            sel = [t for t in data[name] if blk <= t < end]
            if not sel:
                continue
            ev = sum(1 for t in sel if t.second % 30 == 0)
            od = len(sel) - ev
            ratio = ("%.3f" % (od / ev)) if ev else "n/a"
            print("%-8s | %-14s | %7d %7d %7d | %8s"
                  % (blk.strftime("%H:%M"), name, ev, od, len(sel), ratio))
        print("-" * 66)
    print()


def table3_hash_share() -> None:
    print("TABLE 3 -- hash-recovered callsign decodes (`<...>` tokens)")
    print("Tests whether hash recovery is a WSJT-X-only capability. It is not.")
    print()
    print("%-28s | %8s | %8s %8s | %s"
          % ("log", "lines", "hash", "share", "hash+MyCall"))
    print("-" * 74)

    rows: list[tuple[str, str]] = []
    rows += [("WSJT-X " + n, p) for n, p in PROFILES.items()]
    rows += list(OPENWSFZ_LOGS.items())

    for name, path in rows:
        try:
            raw = io.open(path, "r", encoding="utf-8", errors="replace").read()
        except OSError as exc:
            print("%-28s | UNREADABLE (%s)" % (name, exc.__class__.__name__))
            continue
        is_wsjtx = name.startswith("WSJT-X ")
        lines = [l for l in raw.splitlines()
                 if _TS_RE.match(l) and (" Rx " in l or not is_wsjtx)]
        hashed = [l for l in lines if _HASH_RE.search(l)]
        mycall = [l for l in hashed if _MYCALL in l]
        print("%-28s | %8d | %8d %7.2f%% | %d"
              % (name, len(lines), len(hashed),
                 100.0 * len(hashed) / max(len(lines), 1), len(mycall)))
    print()
    print("Read: if OpenWSFZ's share is at or above WSJT-X's, hash recovery")
    print("cannot be inflating leg C against legs A/B, and no exclusion rule")
    print("is warranted on this mechanism.")
    print()


def main() -> int:
    data: dict[str, list[datetime.datetime]] = {}
    for name, path in PROFILES.items():
        try:
            data[name] = load_rx_timestamps(path)
        except OSError as exc:
            print("FATAL: cannot read %s (%s)" % (name, exc))
            print("Edit PROFILES at the top of this file to re-point.")
            return 2

    print("=" * 76)
    for name in PROFILES:
        rows = data[name]
        print("%-14s decodes=%6d  cycles=%5d  span %s -> %s"
              % (name, len(rows), len(set(rows)),
                 min(rows).strftime("%H:%M:%S") if rows else "-",
                 max(rows).strftime("%H:%M:%S") if rows else "-"))
    print("=" * 76)
    print()

    table1_common_cycles(data)
    table2_parity(data)
    table3_hash_share()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
