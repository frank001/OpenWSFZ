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
        contents.md             mechanical facts filled in; narrative sections left as TODO
        contents.html           rendered copy of contents.md (Captain's standing instruction,
                                 2026-07-27 — every live-run folder needs both)

    With --split-owsfz-by-band (a multiband instance, e.g. an SDR retuned across several
    bands within one session), the owsfz/ layout above becomes:

        owsfz/
            <band>/             one subfolder per band actually seen this session (e.g.
                                 20m/, 80m/, 10m/, unknown-band/), band derived per-cycle
                                 from the manifest's dial_mhz column / each ALL.TXT line's
                                 own frequency field -- never from the folder/port name
                wav/            this band's WAVs only
                ALL.TXT         this band's decode-log lines only
                cycle-archive.csv   this band's manifest rows only
            cycle-archive.csv   full unsplit manifest (all bands), the cross-reference
                                 source of truth
            openswfz-*.log      daemon log file(s) (not split -- one process, all bands)

<HHMM> is the session START time, matching the existing artefacts/ naming convention. Nothing
in this layout is ever named after the band/frequency in use — that's just an adjustable run
parameter (Captain, 2026-07-27) that can change mid-session, so it never belongs in a path.

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

    # Also render a companion incident/session report to HTML in the same pass (Captain's
    # standing instruction, 2026-07-27 — contents.html and a report's own .html should both
    # come out of one gather, not one automatic and one remembered-by-hand afterwards):
    python tools/gather_live_run_artefacts.py --report-md qa/endurance/2026-07-26-f283844/report.md

    # Multiband instance (e.g. SDR Uno retuned across several bands in one session) --
    # splits owsfz/ into a per-band subfolder each, instead of one flat owsfz/ folder
    # (Captain, 2026-07-30). Folder *naming* stays date/port-based as always -- only the
    # content inside is organized by band:
    python tools/gather_live_run_artefacts.py \
        --owsfz-alltxt ".../OpenWSFZ-20m-capture/ALL.TXT" \
        --owsfz-log-dir ".../OpenWSFZ-20m-capture/logs" \
        --owsfz-cycle-audio-dir ".../OpenWSFZ-20m-capture/cycle-audio" \
        --split-owsfz-by-band \
        --name "20260730_live_run_1821-8081"

Only stdlib is used deliberately — this needs to run on a QA/Developer workstation with no
project virtualenv guaranteed to be active.
"""

from __future__ import annotations

import argparse
import csv
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


# ── Band-name mapping (for --split-owsfz-by-band) ──────────────────────────────────────


# Standard amateur HF/6m band edges (MHz), region-generic (IARU Region 1/2/3 common core).
# Good enough to label FT8 dial frequencies correctly regardless of which band an SDR (or any
# other radio) happens to be tuned to during a session -- written specifically because a live
# SDR-fed instance moved through 20m -> 80m -> 10m -> 20m again in one night, and the artefact
# gather needs to reflect the actual band per cycle, not whatever band the instance's
# folder/port happened to be named after at session start (Captain, 2026-07-30: "I said
# specifically at the start it would be a multiband session with sdr uno").
BAND_RANGES: list[tuple[float, float, str]] = [
    (1.8, 2.0, "160m"),
    (3.5, 4.0, "80m"),
    (5.06, 5.45, "60m"),
    (7.0, 7.3, "40m"),
    (10.1, 10.15, "30m"),
    (14.0, 14.35, "20m"),
    (18.068, 18.168, "17m"),
    (21.0, 21.45, "15m"),
    (24.89, 24.99, "12m"),
    (28.0, 29.7, "10m"),
    (50.0, 54.0, "6m"),
]


def freq_to_band(mhz: float) -> str:
    """Map a dial frequency (MHz) to its amateur band label. Falls back to a raw '<freq>MHz'
    label (never silently drops or mislabels data) for anything outside the standard HF/6m
    ranges above -- e.g. a VHF/UHF SDR session, or an off-plan/typo'd dial frequency."""
    for lo, hi, label in BAND_RANGES:
        if lo <= mhz <= hi:
            return label
    return f"{mhz:g}MHz"


def sanitize_band_label(label: str) -> str:
    """Band labels are used as directory names -- keep them filesystem-safe."""
    return re.sub(r"[^A-Za-z0-9.]+", "_", label)


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


# ── Band-split variants (--split-owsfz-by-band) ─────────────────────────────────────────


def read_manifest_rows(cycle_dir: Path) -> list[dict]:
    """Read cycle-archive.csv (if present) into a list of row dicts. Returns [] if the
    manifest doesn't exist -- callers must treat that as 'no band attribution available for
    WAVs', not an error (cycleAudioArchive.writeManifest may be off, or the feature unused)."""
    manifest = cycle_dir / "cycle-archive.csv"
    if not manifest.is_file():
        return []
    with manifest.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def band_by_filename_from_rows(rows: list[dict]) -> dict[str, str]:
    """Build a WAV filename -> band label lookup from manifest rows' dial_mhz column."""
    out: dict[str, str] = {}
    for row in rows:
        try:
            mhz = float(row.get("dial_mhz", ""))
        except (TypeError, ValueError):
            continue
        out[row["filename"]] = freq_to_band(mhz)
    return out


def filter_alltxt_split_by_band(
    src: Path, dst_root: Path, start: datetime, end: datetime
) -> dict[str, int]:
    """Like filter_alltxt, but splits output into dst_root/<band>/ALL.TXT by each line's own
    frequency field (field 2, whitespace-separated -- e.g. '260729_183130     14.074 Rx FT8
    ...'). Returns {band_label: line_count}. A line with no parseable frequency field is
    counted under 'unknown-band' rather than dropped, so the total line count always
    reconciles with a plain (non-split) filter_alltxt() call over the same window."""
    counts: dict[str, int] = {}
    if not src.is_file():
        print(f"  (skip) {src} not found")
        return counts
    handles: dict[str, object] = {}
    try:
        with src.open("r", encoding="utf-8", errors="replace") as fin:
            for line in fin:
                m = TS_RE.match(line)
                if not m:
                    continue
                ts = parse_cycle_ts(m.group(1))
                if ts is None or not (start <= ts <= end):
                    continue
                fields = line.split()
                band = "unknown-band"
                if len(fields) >= 2:
                    try:
                        band = freq_to_band(float(fields[1]))
                    except ValueError:
                        pass
                band = sanitize_band_label(band)
                if band not in handles:
                    band_dir = dst_root / band
                    band_dir.mkdir(parents=True, exist_ok=True)
                    handles[band] = (band_dir / "ALL.TXT").open(
                        "w", encoding="utf-8", newline=""
                    )
                handles[band].write(line)
                counts[band] = counts.get(band, 0) + 1
    finally:
        for fh in handles.values():
            fh.close()
    for band, n in sorted(counts.items()):
        print(f"  {src} -> {dst_root / band / 'ALL.TXT'} ({n} lines in window)")
    return counts


def copy_wav_window_split_by_band(
    src_dir: Path,
    dst_root: Path,
    start: datetime,
    end: datetime,
    pad: timedelta,
    band_by_filename: dict[str, str],
) -> dict[str, int]:
    """Like copy_wav_window, but splits output into dst_root/<band>/wav/ using the manifest-
    derived band_by_filename lookup. A WAV in the time window but absent from the manifest
    (e.g. writeManifest was off for part of the session) is copied under 'unknown-band' rather
    than silently dropped, with a summary warning printed once."""
    counts: dict[str, int] = {}
    if not src_dir.is_dir():
        print(f"  (skip) {src_dir} not found")
        return counts
    lo, hi = start - pad, end + pad
    unattributed = 0
    for wav in sorted(src_dir.glob("*.wav")):
        ts = parse_cycle_ts(wav.stem)
        if ts is None or not (lo <= ts <= hi):
            continue
        band = band_by_filename.get(wav.name)
        if band is None:
            band = "unknown-band"
            unattributed += 1
        band = sanitize_band_label(band)
        band_wav_dir = dst_root / band / "wav"
        band_wav_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wav, band_wav_dir / wav.name)
        counts[band] = counts.get(band, 0) + 1
    for band, n in sorted(counts.items()):
        print(f"  {src_dir} -> {dst_root / band / 'wav'} ({n} WAV files in window)")
    if unattributed:
        print(
            f"  warning: {unattributed} WAV file(s) in the window had no matching manifest "
            f"row (no dial_mhz to attribute) -- filed under 'unknown-band'."
        )
    return counts


def parse_manifest_ts(value: str) -> datetime | None:
    """Parse cycle-archive.csv's cycle_start_utc column ('2026-07-30T09:20:15.000Z') into a
    naive UTC datetime, comparable against the same start/end used for ALL.TXT/WAV
    filtering."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def write_band_manifests(
    rows: list[dict], dst_root: Path, start: datetime, end: datetime
) -> None:
    """Split cycle-archive.csv into a per-band slice under each dst_root/<band>/ directory,
    filtered to [start, end] so these slices agree with the ALL.TXT/wav/ output alongside them
    (the manifest itself may span many sessions, not just this one). The full, unfiltered
    manifest is separately copied whole to dst_root by copy_cycle_archive_manifest(), kept
    there as the single cross-reference source of truth for the whole corpus."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    by_band: dict[str, list[dict]] = {}
    for row in rows:
        ts = parse_manifest_ts(row.get("cycle_start_utc", ""))
        if ts is None or not (start <= ts <= end):
            continue
        try:
            band = freq_to_band(float(row.get("dial_mhz", "")))
        except (TypeError, ValueError):
            band = "unknown-band"
        by_band.setdefault(sanitize_band_label(band), []).append(row)
    for band, band_rows in by_band.items():
        band_dir = dst_root / band
        band_dir.mkdir(parents=True, exist_ok=True)
        out_path = band_dir / "cycle-archive.csv"
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(band_rows)
        print(f"  wrote per-band manifest slice: {out_path} ({len(band_rows)} rows)")


# ── contents.md / contents.html generation ─────────────────────────────────────────────


def write_contents(
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
    owsfz_band_breakdown: dict[str, dict[str, int]] | None = None,
) -> Path:
    decoder = config.get("decoder", {})
    decode_log = config.get("decodeLog", {})
    dial_mhz = decode_log.get("dialFrequencyMHz")
    audio_device = config.get("audioDeviceFriendlyName") or "TODO"
    log_names = ", ".join(f"`{p.name}`" for p in owsfz_logs) or "(none found in window)"

    if owsfz_band_breakdown:
        band_lines = "\n".join(
            f"  - **{band}**: `owsfz/{band}/ALL.TXT` ({counts['lines']} lines), "
            f"`owsfz/{band}/wav/` ({counts['wavs']} WAV file(s)), "
            f"`owsfz/{band}/cycle-archive.csv` (per-band manifest slice)."
            for band, counts in sorted(owsfz_band_breakdown.items())
        )
        owsfz_section = (
            f"- OpenWSFZ corpus split by band (multiband session, `--split-owsfz-by-band`) — "
            f"{owsfz_lines} total decode-log lines, {owsfz_wavs} total WAV file(s) across "
            f"{len(owsfz_band_breakdown)} band(s):\n"
            f"{band_lines}\n"
            f"  - Any `unknown-band` entries above mean a WAV in the time window had no "
            f"matching `cycle-archive.csv` row to attribute a dial frequency to — check "
            f"`cycleAudioArchive.writeManifest` was on throughout the session if so.\n"
            f"- `owsfz/cycle-archive.csv` — full unsplit manifest (all bands), kept as the "
            f"single cross-reference source of truth.\n"
            f"- `owsfz/` daemon log file(s): {log_names}."
        )
    else:
        owsfz_section = (
            f"- `owsfz/ALL.TXT` — OpenWSFZ's decoded-message log, filtered to the session "
            f"window ({owsfz_lines} lines).\n"
            f"- `owsfz/` daemon log file(s): {log_names}.\n"
            f"- `owsfz/wav/` — {owsfz_wavs} WAV file(s) from the cycle-audio-archive feature "
            f"(0 is normal if the feature was off this session — the folder is kept for "
            f"future use regardless)."
        )

    # Note (Captain's standing instruction, 2026-07-27): the band/frequency is just an
    # adjustable run parameter, not part of the run's identity — it appears below only as
    # descriptive metadata about what happened during the session, never in the folder name,
    # this file's name, or any filename under it (naming is date/time-only throughout).
    body = f"""# Live run contents — {start:%Y-%m-%d} (session {start:%H:%M:%S} → {end:%H:%M:%S} UTC)

Gathered automatically by `tools/gather_live_run_artefacts.py` (HK-016). Not committed to
VCS (git-ignored, `artefacts/` — NFR-021/GDPR: these files contain real third-party
callsigns).

**TODO (QA/Developer to fill in before closing out the run):** link the analysis this run
supports and fill in the "Headline result" section below.

## Contents

{owsfz_section}
- `wsjt-x/ALL.TXT` — WSJT-X's decoded-message log, filtered to the session window
  ({wsjtx_lines} lines).
- `wsjt-x/wav/` — {wsjtx_wavs} WAV recordings from WSJT-X's own `save/` directory.

## Build under test

{git_build_info()}

## Device / session metadata

Audio device: {audio_device}. Dial frequency at time of gathering: {dial_mhz if dial_mhz else "TODO"} MHz
(a run parameter, may have changed during the session — check the ALL.TXT frequency column
for the actual per-line value, not this single snapshot).
Decoder settings: `kMinScorePass2={decoder.get("kMinScorePass2", "TODO")}`,
`osdCorrThreshold={decoder.get("osdCorrThreshold", "TODO")}`,
`osdNhardMax={decoder.get("osdNhardMax", "TODO")}`.
Session duration: {end - start} ({start:%H:%M:%S} → {end:%H:%M:%S}).

## Headline result

TODO — one-line pointer to wherever the actual analysis/report for this run lives.
"""
    contents_path = out_dir / "contents.md"
    if contents_path.exists():
        contents_path = out_dir / "contents.autogen.md"
        print(
            f"  note: contents.md already exists — writing mechanical facts to "
            f"{contents_path.name} instead so your hand-edited notes aren't clobbered"
        )
    contents_path.write_text(body, encoding="utf-8")
    render_markdown_html(contents_path)
    return contents_path


def render_markdown_html(md_path: Path) -> None:
    """Render a Markdown file to HTML alongside it, via the shared renderer
    (qa/rr-study/render_report.py — generic despite its name/location; single source of truth
    for this repo's Markdown->HTML styling rather than a second copy here). Used for this
    script's own contents.md, and (via --report-md) for a companion incident/session report.md
    living elsewhere (e.g. qa/endurance/<date>-<sha>/report.md) — the Captain's standing
    instruction, 2026-07-27, after report.md got gathered without its report.html once and had
    to be rendered as an afterthought. Best-effort: a rendering failure (e.g. no network for the
    renderer's one-time 'markdown' package bootstrap) is warned about, not fatal — the .md file,
    which is the primary artefact, is already written by the time this runs.
    """
    renderer = REPO_ROOT / "qa" / "rr-study" / "render_report.py"
    if not renderer.is_file():
        print(f"  warning: {renderer} not found — skipping {md_path.name} HTML render")
        return
    if not md_path.is_file():
        print(f"  warning: {md_path} not found — skipping HTML render")
        return
    try:
        subprocess.run(
            [sys.executable, str(renderer), str(md_path)],
            check=True, capture_output=True, text=True,
        )
        print(f"  rendered {md_path.with_suffix('.html').name}")
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"  warning: {md_path.name} HTML render failed: {detail}")


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
    p.add_argument("--split-owsfz-by-band", action="store_true",
                    help="Split the OpenWSFZ ALL.TXT/wav/manifest output into per-band "
                         "subfolders (owsfz/<band>/...) instead of one flat owsfz/ folder. "
                         "For a multiband instance (e.g. an SDR retuned across several bands "
                         "within one session) -- band is derived per-cycle from the "
                         "manifest's dial_mhz column (WAVs) and each ALL.TXT line's own "
                         "frequency field (decode log), never from the instance's folder/port "
                         "name. Requires cycleAudioArchive.writeManifest=true for WAV "
                         "attribution; WAVs with no matching manifest row are filed under "
                         "'unknown-band' rather than dropped.")
    p.add_argument("--wsjtx-root", help="WSJT-X's data directory "
                                         "(default: %%LOCALAPPDATA%%\\WSJT-X on Windows).")
    p.add_argument("--pad-seconds", type=int, default=30,
                    help="Slack applied to WAV/ALL.TXT timestamp filtering, each side of the "
                         "window, to absorb clock offset between the two apps (default: %(default)s).")
    p.add_argument("--log-pad-seconds", type=int, default=300,
                    help="Slack applied to daemon *.log file mtime filtering (default: %(default)s).")
    p.add_argument("--dry-run", action="store_true", help="Print what would happen; copy nothing.")
    p.add_argument("--report-md", action="append", dest="report_md_paths", metavar="PATH",
                    help="Also render this Markdown file to HTML (e.g. a companion "
                         "qa/endurance/<date>-<sha>/report.md incident write-up), alongside "
                         "this run's own contents.md/contents.html. Repeatable.")
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

    dirs_to_make = [wsjtx_wav_out]
    if not args.split_owsfz_by_band:
        dirs_to_make.append(owsfz_wav_dir)
    for d in dirs_to_make:
        d.mkdir(parents=True, exist_ok=True)

    print("\nCopying:")
    owsfz_band_breakdown: dict[str, dict[str, int]] | None = None
    if args.split_owsfz_by_band:
        manifest_rows = read_manifest_rows(cycle_audio_dir)
        band_by_filename = band_by_filename_from_rows(manifest_rows)
        if not manifest_rows:
            print(
                f"  warning: no cycle-archive.csv found under {cycle_audio_dir} -- WAVs will "
                f"all be filed under 'unknown-band' (band split still applies to ALL.TXT, "
                f"which carries its own frequency field independent of the manifest)."
            )
        line_counts = filter_alltxt_split_by_band(owsfz_alltxt, owsfz_dir, start, end)
        owsfz_logs = copy_log_files(owsfz_log_dirs, owsfz_dir, start, end, log_pad)
        wav_counts = copy_wav_window_split_by_band(
            cycle_audio_dir, owsfz_dir, start, end, pad, band_by_filename
        )
        copy_cycle_archive_manifest(cycle_audio_dir, owsfz_dir)
        write_band_manifests(manifest_rows, owsfz_dir, start, end)

        bands = sorted(set(line_counts) | set(wav_counts))
        owsfz_band_breakdown = {
            b: {"lines": line_counts.get(b, 0), "wavs": wav_counts.get(b, 0)} for b in bands
        }
        owsfz_lines = sum(line_counts.values())
        owsfz_wavs = sum(wav_counts.values())
    else:
        owsfz_lines = filter_alltxt(owsfz_alltxt, owsfz_dir / "ALL.TXT", start, end)
        owsfz_logs = copy_log_files(owsfz_log_dirs, owsfz_dir, start, end, log_pad)
        owsfz_wavs = copy_wav_window(cycle_audio_dir, owsfz_wav_dir, start, end, pad)
        copy_cycle_archive_manifest(cycle_audio_dir, owsfz_dir)

    wsjtx_lines = filter_alltxt(wsjtx_alltxt, wsjtx_dir / "ALL.TXT", start, end)
    wsjtx_wavs = copy_wav_window(wsjtx_wav_dir, wsjtx_wav_out, start, end, pad)

    contents_path = write_contents(
        out_dir, name, start, end, owsfz_lines, owsfz_wavs, owsfz_logs, wsjtx_lines, wsjtx_wavs,
        config, owsfz_band_breakdown,
    )
    print(f"\nWrote {contents_path} — fill in the TODO sections before closing out the run.")

    if args.report_md_paths:
        print("\nRendering companion report(s):")
        for report_md in args.report_md_paths:
            render_markdown_html(Path(report_md))

    print(f"Done: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
