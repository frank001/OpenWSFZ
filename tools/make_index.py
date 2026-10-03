"""Generate artefacts/INDEX.md: one line per top-level entry of the artefacts folder.

Folder names only plus a date: no file counting (the folders hold tens of thousands of WAVs) and no
file contents (some hold real third-party callsigns, NFR-021). The gatherer calls ``write_index`` as
its last step, so a newly gathered run is indexed at once; it can also be run by hand:

    python tools/make_index.py [--root <artefacts folder>]

Moved here from ``_qa-scratch/make_index.py`` (Captain, 2026-10-03), which nothing ever called.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_NAME = "INDEX.md"

RULES = [
    (r"endurance_run-gathered$", "endurance run: gathered (WAVs, ALL.TXT, ANOVA, reports)"),
    (r"endurance_run$", "endurance run: raw run folder (daemon logs, state, config)"),
    (r"rr[-_]study", "R&R study run"),
    (r"live_run", "live on-air run"),
    (r"sub[-_]?feas", "SUB-FEAS work (harness runs, profiles, acceptance)"),
    (r"onoff_replay", "SUB-FEAS offline flag-OFF/ON replay"),
    (r"gap_locate|live-gap|gap[-_]map", "live-gap-map / GAP-LOCATE"),
    (r"nhard", "nhard 40 work"),
    (r"passband", "passband-140 work"),
    (r"d001|d-001", "D-001 work"),
    (r"\.out$|\.log$", "log or captured output"),
]

HEADER = [
    "# Artefacts index",
    "",
    "**This is the one artefacts folder for every worktree** (since 2026-10-02). `worktrees\\qa\\artefacts`,",
    "`worktrees\\eng\\artefacts` and `worktrees\\dev\\artefacts` are directory junctions to it, so a path",
    "typed from any checkout resolves to the same files. Git ignores the junctions (`artefacts/` is",
    "blanket-ignored: real third-party callsigns, NFR-021). Never copy these folders into a branch.",
    "",
]


def kind(name: str) -> str:
    for pat, label in RULES:
        if re.search(pat, name, re.I):
            return label
    return ""


def build_rows(root: Path) -> list[tuple[str, str, str]]:
    rows = []
    for entry in sorted(os.listdir(root)):
        if entry == INDEX_NAME:
            continue
        p = root / entry
        m = re.match(r"(\d{8})", entry)
        date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else \
            datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d") + " (mtime)"
        rows.append((date, entry + ("/" if p.is_dir() else ""), kind(entry)))
    rows.sort()
    return rows


def render(rows: list[tuple[str, str, str]], today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    out = HEADER + [
        f"Generated {today.isoformat()} by `tools/make_index.py` from folder names and modification dates only.",
        "Entries are listed oldest first.",
        "",
        "| Date | Folder | Kind |",
        "|---|---|---|",
    ]
    out += [f"| {date} | `{name}` | {k} |" for date, name, k in rows]
    return "\n".join(out) + "\n"


def write_index(root: Path) -> int:
    """Write ``<root>/INDEX.md``; returns the number of entries."""
    root = Path(root)
    rows = build_rows(root)
    (root / INDEX_NAME).write_text(render(rows), encoding="utf-8")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(REPO_ROOT / "artefacts"), help="the artefacts folder to index")
    a = ap.parse_args(argv)
    print(f"{INDEX_NAME} written: {write_index(Path(a.root))} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
