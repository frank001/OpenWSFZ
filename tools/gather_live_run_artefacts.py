#!/usr/bin/env python3
"""Gather a live run's artefacts into the normalized artefacts/ layout (HK-016).

Every live run (QA-run, Developer-run, endurance, diagnostic) ends with its raw evidence
gathered into a single, uniformly-structured directory under artefacts/ before the run is
reported done — not as a follow-up nice-to-have (see memory/hk016-...md). This script does
the mechanical part of that: locating both sides' ALL.TXT, the daemon log(s), and both WAV
sets, filtering each to the session's time window (so a source directory that accumulates
WAVs/log lines across many sessions doesn't get dragged in wholesale), and laying them out
identically every time:

    artefacts/<YYYYMMDD>_live_run_<HHMM>/
        wsjt-x/
            wav/                WSJT-X save/ WAVs for the session window
            ALL.TXT             WSJT-X's decode log, filtered to the session window
        owsfz/
            wav/                cycle-audio-archive WAVs for the session window (if any;
                                 the subfolder is always created, even empty, for future use)
            ALL.TXT             OpenWSFZ's decode log, filtered to the session window
            openswfz-*.log      daemon log file(s) covering the session window
            cycle-archive.csv   cycle-audio-archive manifest, if the feature was in use
        README.md               mechanical facts filled in; narrative sections left as TODO

<HHMM> is the session START time, matching the existing artefacts/ naming convention.

Usage:
    # Common case: run immediately after ending a live session. Auto-detects the session
    # window from the live OpenWSFZ ALL.TXT's own first/last line timestamps (this assumes
    # the usual practice of wiping ALL.TXT clean before a session starts, but filtering is
    # applied regardless, so a non-wiped file is still handled correctly).
    python tools/gather_live_run_artefacts.py

    # Explicit window (e.g. ALL.TXT has since been overwritten by a later run, or you're
    # backfilling from timestamps noted during the session):
    python tools/gather_live_run_artefacts.py --start 18:04 --end 18:27:30

    # Preview without copying anything:
    python tools/gather_live_run_artefacts.py --dry-run

Only stdlib is used deliberately — this needs to run on a QA/Developer workstation with no
project virtualenv guaranteed to be active.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TS_RE = re.compile(r"^(\d{6}_\d{6})")
TS_FMT = "%y%m%d_%H%M%S"


# ── Session-window helpers ──────────────────────────────────────────────────────────────


def parse_cycle_ts(token: str) -> datetime | None:
    """Parse a WSJT-X/OpenWSFZ cycle timestamp token (`YYMMDD_HHMMSS`)."""
    try:
        return datetime.strptime(token, TS_FMT)
    except ValueError:
        return None


def first_last_cycle_ts(path: Path) -> tuple[datetime, datetime] | None:
    """Return (first, last) cycle timestamps found in an ALL.TXT-format file's lines."""
    if not path.is_file():
        return None
    first: datetime | None = None
    last: datetime | None = None
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = TS_RE.match(line)
            if not m:
                continue
            ts = parse_cycle_ts(m.group(1))
            if ts is None:
                continue
            if first is None:
                first = ts
            last = ts
    if first is None or last is None:
        return None
    return first, last


def parse_datetime_arg(value: str, date_arg: str | None) -> datetime:
    """Accept either a full `YYYY-MM-DD HH:MM[:SS]` or a bare `HH:MM[:SS]` combined with
    --date (defaulting to today)."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    base_date = date_arg or datetime.now().strftime("%Y%m%d")
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(value, fmt).time()
            return datetime.combine(datetime.strptime(base_date, "%Y%m%d").date(), t)
        except ValueError:
            pass
    raise SystemExit(
        f"error: could not parse '{value}' as a time — use HH:MM[:SS] (with --date) "
        f"or 'YYYY-MM-DD HH:MM[:SS]'"
    )


# ── Config lookup (best-effort — used to find where this install actually writes things) ──


def platform_appdata_root() -> Path:
    import os

    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".config"


def platform_localappdata_root() -> Path:
    import os

    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
    return platform_appdata_root()


def load_owsfz_config() -> dict:
    import os

    candidates = []
    env_override = os.environ.get("OPENWSFZ_CONFIG")
    if env_override:
        candidates.append(Path(os.path.expandvars(env_override)))
    candidates.append(platform_appdata_root() / "OpenWSFZ" / "config.json")

    for path in candidates:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"warning: could not read config at {path}: {exc}", file=sys.stderr)
    return {}


# ── Git facts (mechanical "build under test" info) ─────────────────────────────────────


def git_build_info() -> str:
    def run(*args: str) -> str | None:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    sha = run("rev-parse", "--short", "HEAD") or "unknown"
    branch = run("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    dirty = run("status", "--porcelain")
    if dirty is None:
        dirty_note = "unknown (git status failed)"
    elif dirty == "":
        dirty_note = "clean working tree"
    else:
        dirty_note = (
            "**uncommitted changes present** — run `git status`/`git diff` to record "
            "what was actually in play"
        )
    return f"`{branch}` at `{sha}` ({dirty_note})."


# ── Copy helpers ─────────────────────────────────────────────────────────────────────────


def filter_alltxt(src: Path, dst: Path, start: datetime, end: datetime) -> int:
    """Copy only the lines of an ALL.TXT-format file whose leading timestamp falls within
    [start, end]. Returns the number of lines written."""
    if not src.is_file():
        print(f"  (skip) {src} not found")
        return 0
    kept = 0
    with src.open("r", encoding="utf-8", errors="replace") as fin, dst.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        for line in fin:
            m = TS_RE.match(line)
            if not m:
                continue
            ts = parse_cycle_ts(m.group(1))
            if ts is None or not (start <= ts <= end):
                continue
            fout.write(line)
            kept += 1
    print(f"  {src} -> {dst} ({kept} lines in window)")
    return kept


def copy_wav_window(
    src_dir: Path, dst_dir: Path, start: datetime, end: datetime, pad: timedelta
) -> int:
    """Copy WAVs named `YYMMDD_HHMMSS.wav` whose timestamp falls within [start-pad, end+pad]."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    if not src_dir.is_dir():
        print(f"  (skip) {src_dir} not found")
        return 0
    lo, hi = start - pad, end + pad
    count = 0
    for wav in sorted(src_dir.glob("*.wav")):
        ts = parse_cycle_ts(wav.stem)
        if ts is None or not (lo <= ts <= hi):
            continue
        shutil.copy2(wav, dst_dir / wav.name)
        count += 1
    print(f"  {src_dir} -> {dst_dir} ({count} WAV files in window)")
    return count


def copy_log_files(
    src_dirs: list[Path], dst_dir: Path, start: datetime, end: datetime, pad: timedelta
) -> list[Path]:
    """Copy *.log files whose mtime overlaps [start-pad, end+pad] from any of src_dirs.

    `start`/`end` are naive datetimes parsed from ALL.TXT/WAV timestamps, which are always
    UTC (WSJT-X convention, matched by our own AllTxtWriter/CycleArchiveService). Filesystem
    mtimes, however, are wall-clock and reflect the OS's local timezone. Calling
    `.timestamp()` on a *naive* datetime assumes it's already local time — silently wrong
    here by the local UTC offset. Marking start/end as UTC-aware first makes `.timestamp()`
    return the correct epoch value regardless of the machine's local timezone or DST state.
    """
    lo = (start.replace(tzinfo=timezone.utc) - pad).timestamp()
    hi = (end.replace(tzinfo=timezone.utc) + pad).timestamp()
    copied: list[Path] = []
    for src_dir in src_dirs:
        if not src_dir.is_dir():
            continue
        for log in sorted(src_dir.glob("*.log")):
            mtime = log.stat().st_mtime
            if not (lo <= mtime <= hi):
                continue
            dest = dst_dir / log.name
            shutil.copy2(log, dest)
            copied.append(dest)
    if copied:
        for c in copied:
            print(f"  copied log: {c.name}")
    else:
        print("  (no daemon log files found in the session window)")
    return copied


def copy_cycle_archive_manifest(cycle_dir: Path, dst_dir: Path) -> bool:
    manifest = cycle_dir / "cycle-archive.csv"
    if manifest.is_file():
        shutil.copy2(manifest, dst_dir / manifest.name)
        print(f"  copied manifest: {manifest.name}")
        return True
    return False


# ── README generation ───────────────────────────────────────────────────────────────────


def write_readme(
    out_dir: Path,
    name: str,
    start: datetime,
    end: datetime,
    owsfz_lines: int,
    owsfz_wavs: int,
    owsfz_logs: list[Path],
    wsjtx_lines: int,
    wsjtx_wavs: int,
    config: dict,
) -> Path:
    decoder = config.get("decoder", {})
    decode_log = config.get("decodeLog", {})
    dial_mhz = decode_log.get("dialFrequencyMHz")
    audio_device = config.get("audioDeviceFriendlyName") or "TODO"
    log_names = ", ".join(f"`{p.name}`" for p in owsfz_logs) or "(none found in window)"

    body = f"""# Live run artefacts — {start:%Y-%m-%d} (session {start:%H:%M:%S} → {end:%H:%M:%S} UTC)

Gathered automatically by `tools/gather_live_run_artefacts.py` (HK-016). Not committed to
VCS (git-ignored, `artefacts/` — NFR-021/GDPR: these files contain real third-party
callsigns).

**TODO (QA/Developer to fill in before closing out the run):** link the analysis this run
supports and fill in the "Headline result" section below.

## Contents

- `owsfz/ALL.TXT` — OpenWSFZ's decoded-message log, filtered to the session window
  ({owsfz_lines} lines).
- `owsfz/` daemon log file(s): {log_names}.
- `owsfz/wav/` — {owsfz_wavs} WAV file(s) from the cycle-audio-archive feature (0 is normal
  if the feature was off this session — the folder is kept for future use regardless).
- `wsjt-x/ALL.TXT` — WSJT-X's decoded-message log, filtered to the session window
  ({wsjtx_lines} lines).
- `wsjt-x/wav/` — {wsjtx_wavs} WAV recordings from WSJT-X's own `save/` directory.

## Build under test

{git_build_info()}

## Device / session metadata

Audio device: {audio_device}. Dial frequency: {dial_mhz if dial_mhz else "TODO"} MHz.
Decoder settings: `kMinScorePass2={decoder.get("kMinScorePass2", "TODO")}`,
`osdCorrThreshold={decoder.get("osdCorrThreshold", "TODO")}`,
`osdNhardMax={decoder.get("osdNhardMax", "TODO")}`.
Session duration: {end - start} ({start:%H:%M:%S} → {end:%H:%M:%S}).

## Headline result

TODO — one-line pointer to wherever the actual analysis/report for this run lives.
"""
    readme_path = out_dir / "README.md"
    if readme_path.exists():
        readme_path = out_dir / "README.autogen.md"
        print(
            f"  note: README.md already exists — writing mechanical facts to "
            f"{readme_path.name} instead so your hand-edited notes aren't clobbered"
        )
    readme_path.write_text(body, encoding="utf-8")
    return readme_path


# ── Main ─────────────────────────────────────────────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", help="Session start (HH:MM[:SS], or 'YYYY-MM-DD HH:MM[:SS]'). "
                                    "Default: auto-detect from the live owsfz ALL.TXT's first line.")
    p.add_argument("--end", help="Session end, same formats as --start. "
                                  "Default: auto-detect from the live owsfz ALL.TXT's last line.")
    p.add_argument("--date", help="Date (YYYYMMDD) to combine with a bare HH:MM --start/--end. "
                                   "Default: today.")
    p.add_argument("--name", help="Override the output folder name "
                                   "(default: <YYYYMMDD>_live_run_<HHMM start>).")
    p.add_argument("--out-root", default=str(REPO_ROOT / "artefacts"),
                    help="Root artefacts/ directory (default: %(default)s).")
    p.add_argument("--owsfz-alltxt", help="Path to OpenWSFZ's live ALL.TXT "
                                           "(default: repo root ALL.TXT, or decodeLog.path from config.json).")
    p.add_argument("--owsfz-log-dir", action="append", dest="owsfz_log_dirs",
                    help="Directory to search for daemon *.log files. Repeatable. "
                         "Default: <repo root>/logs and <repo root>/logs-linux.")
    p.add_argument("--owsfz-cycle-audio-dir", help="Override the cycle-audio-archive directory "
                                                     "(default: config.json's cycleAudioArchive.directory, "
                                                     "or the platform default).")
    p.add_argument("--wsjtx-root", help="WSJT-X's data directory "
                                         "(default: %%LOCALAPPDATA%%\\WSJT-X on Windows).")
    p.add_argument("--pad-seconds", type=int, default=30,
                    help="Slack applied to WAV/ALL.TXT timestamp filtering, each side of the "
                         "window, to absorb clock offset between the two apps (default: %(default)s).")
    p.add_argument("--log-pad-seconds", type=int, default=300,
                    help="Slack applied to daemon *.log file mtime filtering (default: %(default)s).")
    p.add_argument("--dry-run", action="store_true", help="Print what would happen; copy nothing.")
    return p


def main(argv: list[str] | None = None) -> int:
    # This repo's Windows workstation runs Python with a cp1252 console encoding by default;
    # the docstrings/messages below use em dashes and arrows, which cp1252 can't encode.
    # Reconfigure to UTF-8 up front rather than restricting every message to ASCII (HK-009).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

    args = build_arg_parser().parse_args(argv)
    config = load_owsfz_config()

    owsfz_alltxt = Path(args.owsfz_alltxt) if args.owsfz_alltxt else (
        REPO_ROOT / config.get("decodeLog", {}).get("path", "ALL.TXT")
    )
    owsfz_log_dirs = [Path(d) for d in args.owsfz_log_dirs] if args.owsfz_log_dirs else [
        REPO_ROOT / config.get("logging", {}).get("directory", "logs"),
        REPO_ROOT / "logs-linux",
    ]
    cycle_audio_dir = Path(args.owsfz_cycle_audio_dir) if args.owsfz_cycle_audio_dir else (
        Path(config.get("cycleAudioArchive", {}).get("directory") or
             (platform_appdata_root() / "OpenWSFZ" / "cycle-audio"))
    )
    wsjtx_root = Path(args.wsjtx_root) if args.wsjtx_root else (platform_localappdata_root() / "WSJT-X")
    wsjtx_alltxt = wsjtx_root / "ALL.TXT"
    wsjtx_wav_dir = wsjtx_root / "save"

    # ── Determine the session window ──
    if args.start:
        start = parse_datetime_arg(args.start, args.date)
    else:
        bounds = first_last_cycle_ts(owsfz_alltxt)
        if bounds is None:
            print(f"error: --start not given and could not auto-detect from {owsfz_alltxt} "
                  f"(missing or no parseable timestamp lines) — pass --start explicitly.",
                  file=sys.stderr)
            return 1
        start = bounds[0]

    if args.end:
        end = parse_datetime_arg(args.end, args.date)
    else:
        bounds = first_last_cycle_ts(owsfz_alltxt)
        end = bounds[1] if bounds else datetime.now()

    if end < start:
        print(f"error: end ({end}) is before start ({start})", file=sys.stderr)
        return 1

    pad = timedelta(seconds=args.pad_seconds)
    log_pad = timedelta(seconds=args.log_pad_seconds)

    name = args.name or f"{start:%Y%m%d}_live_run_{start:%H%M}"
    out_dir = Path(args.out_root) / name
    owsfz_dir = out_dir / "owsfz"
    owsfz_wav_dir = owsfz_dir / "wav"
    wsjtx_dir = out_dir / "wsjt-x"
    wsjtx_wav_out = wsjtx_dir / "wav"

    print(f"Session window: {start} -> {end}  (pad {args.pad_seconds}s / log pad {args.log_pad_seconds}s)")
    print(f"Output folder:  {out_dir}")
    print(f"Sources:")
    print(f"  owsfz ALL.TXT        = {owsfz_alltxt}")
    print(f"  owsfz log dir(s)     = {', '.join(str(d) for d in owsfz_log_dirs)}")
    print(f"  owsfz cycle-audio    = {cycle_audio_dir}")
    print(f"  wsjt-x ALL.TXT       = {wsjtx_alltxt}")
    print(f"  wsjt-x save/ wav dir = {wsjtx_wav_dir}")

    if args.dry_run:
        print("\n--dry-run: no files copied, no directories created.")
        return 0

    for d in (owsfz_wav_dir, wsjtx_wav_out):
        d.mkdir(parents=True, exist_ok=True)

    print("\nCopying:")
    owsfz_lines = filter_alltxt(owsfz_alltxt, owsfz_dir / "ALL.TXT", start, end)
    owsfz_logs = copy_log_files(owsfz_log_dirs, owsfz_dir, start, end, log_pad)
    owsfz_wavs = copy_wav_window(cycle_audio_dir, owsfz_wav_dir, start, end, pad)
    copy_cycle_archive_manifest(cycle_audio_dir, owsfz_dir)

    wsjtx_lines = filter_alltxt(wsjtx_alltxt, wsjtx_dir / "ALL.TXT", start, end)
    wsjtx_wavs = copy_wav_window(wsjtx_wav_dir, wsjtx_wav_out, start, end, pad)

    readme_path = write_readme(
        out_dir, name, start, end, owsfz_lines, owsfz_wavs, owsfz_logs, wsjtx_lines, wsjtx_wavs, config
    )
    print(f"\nWrote {readme_path} — fill in the TODO sections before closing out the run.")
    print(f"Done: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
