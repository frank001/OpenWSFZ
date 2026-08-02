#!/usr/bin/env python3
"""Generate `qa/ARTEFACT_INVENTORY.md` -- the "what have we already collected?" lookup.

WHY THIS EXISTS
---------------
HK-018 says "check the data already gathered before concluding". It is a
disposition, not an address: it says to check, not where. Across ~30 GB and 40+
run folders that is an open-ended search, and open-ended searches get skipped
under momentum -- four times in the 2026-08-02 session alone, most expensively
by recommending a multi-day capture run for a corpus that had been sitting in
`artefacts/` for two days.

This turns the rule into a lookup. One table, one row per run, answer in
seconds.

MECHANICAL vs INTERPRETIVE
--------------------------
Every column except `notes` is measured from disk on each run, so it cannot go
stale silently. `notes` is hand-written, lives in NOTES below (version
controlled, survives regeneration), and is rendered in a separate column marked
as interpretive -- so a stale note looks like a note, not like a fact.

A hand-maintained inventory would drift, and a stale inventory is worse than
none: it produces confident false negatives ("we don't have that"), which is
the same failure with the sign flipped.

USAGE
-----
    python qa/artefact_inventory.py            # regenerate qa/ARTEFACT_INVENTORY.md
    python qa/artefact_inventory.py --check    # exit 1 if the file is out of date

Only `ALL.TXT` files are stat'd (for hardlink detection); WAVs are counted by
name via os.scandir, so a full pass is seconds, not the minutes `du` takes.
Output is ASCII-only (HK-009). NFR-021: counts and paths only, no callsigns.
"""

from __future__ import annotations

import argparse
import datetime
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # HK-009
except AttributeError:  # pragma: no cover
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTEFACTS = os.path.join(REPO, "artefacts")
# NOT inside artefacts/ -- that directory is git-ignored (.gitignore:105), so an
# inventory written there would be invisible to QA and to review. It lives in
# qa/ so drift is caught in a diff like any other tracked file.
OUTPUT = os.path.join(REPO, "qa", "ARTEFACT_INVENTORY.md")

_TS = re.compile(r"^(\d{6}_\d{6})")

# ---------------------------------------------------------------------------
# INTERPRETIVE. Hand-written, one line each. Keyed by run folder name.
# Say what question the run can answer and what has already consumed it.
# Leave a run out rather than guess -- a blank cell is honest, a wrong note
# is the failure this file exists to prevent.
# ---------------------------------------------------------------------------
NOTES: dict[str, str] = {
    "20260731_live_run_2004-8080":
        "**D-001 Angle 1 corpus.** One WSJT-X instance (hardlinked into the -8081 "
        "folder too -- one capture, not two). Feeds legs A/B/C and null N3, which "
        "needs exactly this: jt9 over WSJT-X's own WAVs vs its own live count. "
        "N3 runnable offline, no capture needed. T4 unauthorised as of 2026-08-02.",
    "20260731_live_run_2004-8081":
        "Same WSJT-X capture as -8080 (hardlinked ALL.TXT + wav/). The owsfz leg "
        "IS distinct. Do not treat the two wsjt-x legs as independent captures.",
    "20260729_live_run_1831-8080":
        "Pre-drift-fix. Superseded by the 07-31 run for D-001 work.",
    "d001_wav_source_cross_decode_2026-07-30":
        "Capture-chain cross-decode; source of the ~10-13% capture-chain effect.",
    "d001_b1b_second_corpus":
        "Second corpus for the B.3 costed menu (2026-07-27). Menu decision still open.",
}

SKIP_DIRS = {".git"}


def cycle_stats(path: str) -> tuple[int, str, str]:
    """(distinct cycle count, first ts, last ts) from an ALL.TXT."""
    seen: set[str] = set()
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _TS.match(line)
                if m:
                    seen.add(m.group(1))
    except OSError:
        return 0, "", ""
    if not seen:
        return 0, "", ""
    s = sorted(seen)
    return len(seen), s[0], s[-1]


def count_wavs(root: str) -> int:
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        n += sum(1 for f in filenames if f.lower().endswith(".wav"))
    return n


def find_all_txt(root: str) -> dict[str, str]:
    """Map leg name -> ALL.TXT path, for legs that have one."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.upper() == "ALL.TXT":
                leg = os.path.relpath(dirpath, root).replace("\\", "/")
                out["(root)" if leg == "." else leg] = os.path.join(dirpath, f)
    return out


def scan() -> list[dict]:
    rows: list[dict] = []
    # inode -> [(run, leg), ...] across ALL runs. A shared inode means one
    # capture gathered into several folders. This MUST be mechanical: the
    # 2026-08-02 session lost an afternoon to a cross-folder hardlink that was
    # only ever recorded in prose.
    global_inodes: dict[int, list[tuple[str, str]]] = {}
    for name in sorted(os.listdir(ARTEFACTS)):
        run = os.path.join(ARTEFACTS, name)
        if not os.path.isdir(run):
            continue
        legs = find_all_txt(run)
        wavs = {}
        for sub in sorted(os.listdir(run)):
            p = os.path.join(run, sub)
            if os.path.isdir(p):
                c = count_wavs(p)
                if c:
                    wavs[sub] = c
        leg_info = {}
        inodes = {}
        for leg, path in sorted(legs.items()):
            n, first, last = cycle_stats(path)
            leg_info[leg] = n
            try:
                ino = os.stat(path).st_ino
                inodes[leg] = ino
                global_inodes.setdefault(ino, []).append((name, leg))
            except OSError:
                pass
        span = ("", "")
        for leg, path in sorted(legs.items()):
            n, first, last = cycle_stats(path)
            if n:
                span = (first, last)
                break
        if not legs and not wavs:
            continue
        rows.append(dict(name=name, legs=leg_info, wavs=wavs, span=span,
                         inodes=inodes, hardlinked=[],
                         total_wavs=sum(wavs.values())))

    # second pass: annotate every leg whose inode is shared with another leg,
    # in this run or any other.
    for r in rows:
        shared = []
        for leg, ino in r["inodes"].items():
            others = [(n, l) for (n, l) in global_inodes.get(ino, [])
                      if not (n == r["name"] and l == leg)]
            if others:
                shared.append("`%s` = %s" % (
                    leg, ", ".join("`%s`/`%s`" % o for o in others)))
        r["hardlinked"] = shared
    return rows


def render(rows: list[dict]) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out: list[str] = []
    out.append("# Artefact inventory -- what has already been collected")
    out.append("")
    out.append("**GENERATED FILE -- do not hand-edit.** Regenerate with")
    out.append("`python qa/artefact_inventory.py`. Hand-written notes live in that")
    out.append("script's `NOTES` dict and survive regeneration.")
    out.append("")
    out.append("Read this **before** concluding that data for a question does not")
    out.append("exist, and before proposing any capture run (HK-018, HK-004).")
    out.append("")
    out.append("Every column except **notes** is measured from disk on each run and")
    out.append("cannot go stale silently. **notes** is interpretive and hand-written --")
    out.append("treat it as a claim to verify, not a fact.")
    out.append("")
    out.append("Scanned: %s | %d runs | %s total WAVs"
               % (now, len(rows), f"{sum(r['total_wavs'] for r in rows):,}"))
    out.append("")
    out.append("| run | UTC span | legs (distinct cycles) | WAVs | notes *(interpretive)* |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        span = "%s -> %s" % r["span"] if r["span"][0] else "-"
        legs = "<br>".join("`%s` %s" % (k, f"{v:,}") for k, v in r["legs"].items()) or "-"
        if r["hardlinked"]:
            legs += "<br>**HARDLINKED** " + "; ".join(r["hardlinked"])
        wavs = "<br>".join("`%s` %s" % (k, f"{v:,}") for k, v in r["wavs"].items()) or "-"
        note = NOTES.get(r["name"], "")
        out.append("| `%s` | %s | %s | %s | %s |" % (r["name"], span, legs, wavs, note))
    out.append("")
    out.append("## How to read the `legs` column")
    out.append("")
    out.append("`owsfz` is our daemon's `ALL.TXT`; `wsjt-x` is the comparison decoder's.")
    out.append("**HARDLINKED** means two leg paths resolve to the same inode -- one")
    out.append("capture gathered into two folders, not two independent captures. That")
    out.append("is fine for anything needing a single instrument and fatal for anything")
    out.append("assuming two.")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if ARTEFACT_INVENTORY.md is out of date")
    args = ap.parse_args()

    if not os.path.isdir(ARTEFACTS):
        print("no artefacts/ directory at %s" % ARTEFACTS)
        return 2

    text = render(scan())

    if args.check:
        try:
            cur = io.open(OUTPUT, "r", encoding="utf-8").read()
        except OSError:
            print("ARTEFACT_INVENTORY.md missing")
            return 1
        strip = lambda s: "\n".join(l for l in s.splitlines()
                                    if not l.startswith("Scanned:"))
        if strip(cur) != strip(text):
            print("ARTEFACT_INVENTORY.md is out of date -- run: python qa/artefact_inventory.py")
            return 1
        print("ARTEFACT_INVENTORY.md up to date")
        return 0

    with io.open(OUTPUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s" % OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
