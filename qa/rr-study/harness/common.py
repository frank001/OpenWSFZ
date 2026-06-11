"""Shared utilities for the R&R study harness.

Provides:
  - compute_seed()    — deterministic trial seed
  - normalise_slot()  — floor a datetime to its FT8 15-second cycle boundary
  - make_run_dir()    — resolve / create the versioned results directory
  - parse_all_txt()   — parse an ALL.TXT decode log into records + skipped count
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

# ── Windows terminal encoding (NFR-022) ───────────────────────────────────────
# Windows consoles default to cp1252, which cannot encode Greek letters, Unicode
# minus signs, or other non-ASCII characters used in study output.  Reconfigure
# stdout to UTF-8 with replacement so a missing glyph shows as '?' rather than
# raising UnicodeEncodeError and aborting a running study.  This executes
# automatically for every harness script that imports from harness.common.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Seed computation
# ---------------------------------------------------------------------------

def compute_seed(scenario_id: str, part_index: int, trial_index: int) -> int:
    """Return the deterministic seed for a given (scenario, part, trial) triple.

    Uses SHA-256 so the result is stable across Python sessions regardless of
    PYTHONHASHSEED. The 2**31 modulus keeps seeds in numpy's default int32 range.
    """
    key = f"{scenario_id},{part_index},{trial_index}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest(), 16) % (2 ** 31)


# ---------------------------------------------------------------------------
# FT8 cycle slot normalisation
# ---------------------------------------------------------------------------

SLOT_SECONDS = 15


def normalise_slot(dt: datetime) -> datetime:
    """Floor *dt* to the nearest FT8 15-second UTC cycle boundary.

    Timestamps within ±1 s of a boundary are treated as belonging to the
    correct slot:

      second % 15 == 0   → on boundary           → floor to current slot
      second % 15 == 1   → 1 s after boundary     → floor to current slot
      second % 15 == 14  → 1 s before next slot   → snap forward to next slot
      otherwise           → floor to lower boundary
    """
    dt = dt.replace(microsecond=0)
    rem = dt.second % SLOT_SECONDS
    if rem == 14:
        dt = dt + timedelta(seconds=1)
    new_sec = (dt.second // SLOT_SECONDS) * SLOT_SECONDS
    return dt.replace(second=new_sec)


# ---------------------------------------------------------------------------
# Run directory resolution
# ---------------------------------------------------------------------------

def _git_sha7() -> str:
    """Return the first 7 characters of HEAD SHA, or 'unknown' if git unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:7]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def make_run_dir(results_root: Path) -> Path:
    """Resolve and create the versioned run directory.

    Returns ``results_root/<YYYY-MM-DD>-<git-sha7>/``, creating it if needed.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sha7 = _git_sha7()
    run_dir = results_root / f"{date_str}-{sha7}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------------------
# ALL.TXT line parser
# ---------------------------------------------------------------------------

# Two ALL.TXT line formats are supported:
#
# Format A — test-fixture / synthetic (YYYYMMDD 8-digit date, UTC keyword,
#             audio-freq-Hz first, then dt, then snr):
#   20260606_123500   UTC  1502  0.2  -12  FT8  CQ Q1ABC FN42
#
# Format B — real WSJT-X / OpenWSFZ (YYMMDD 6-digit date, dial-MHz, Rx keyword,
#             mode, then snr, then dt, then audio-freq-Hz):
#   260606_102100     7.074 Rx FT8    -20 -0.3 1500 CQ Q1ABC FN42
#
# Both formats end with FT8 mode and the decoded message.

# Format A: 8-digit date, "UTC", freqHz int, dt float, snr int, mode, message
_ALL_TXT_RE_A = re.compile(
    r"^(\d{8}_\d{6})\s{2,}UTC\s{2,}(\d+)\s+([-\d.]+)\s+([-\d]+)\s+(\w+)\s+(.+?)\s*$"
)
_TIMESTAMP_FMT_A = "%Y%m%d_%H%M%S"

# Format B: 6-digit date, dial-MHz float, "Rx", mode, snr int, dt float,
#           audioFreqHz int, message
_ALL_TXT_RE_B = re.compile(
    r"^(\d{6}_\d{6})\s+([\d.]+)\s+Rx\s+(FT8)\s+([-\d]+)\s+([-\d.]+)\s+(\d+)\s+(.+?)\s*$"
)
_TIMESTAMP_FMT_B = "%y%m%d_%H%M%S"


class AllTxtRecord(NamedTuple):
    utc: datetime    # normalised to slot boundary (UTC, no microseconds)
    freq_hz: float
    dt_s: float
    snr_db: float
    message: str


def _parse_line(line: str) -> "AllTxtRecord | None":
    """Try to parse one ALL.TXT line in Format A or B.  Returns None on failure."""
    # --- Format A ---
    m = _ALL_TXT_RE_A.match(line)
    if m:
        ts_str, freq_str, dt_str, snr_str, mode, message = m.groups()
        if mode.upper() != "FT8":
            return None
        try:
            dt_naive = datetime.strptime(ts_str, _TIMESTAMP_FMT_A)
            dt_utc = dt_naive.replace(tzinfo=timezone.utc)
            return AllTxtRecord(
                utc=normalise_slot(dt_utc),
                freq_hz=float(freq_str),
                dt_s=float(dt_str),
                snr_db=float(snr_str),
                message=" ".join(message.split()),
            )
        except (ValueError, OverflowError):
            return None

    # --- Format B ---
    m = _ALL_TXT_RE_B.match(line)
    if m:
        ts_str, _dial_mhz, mode, snr_str, dt_str, freq_str, message = m.groups()
        # mode is always FT8 (captured by the literal in the regex)
        try:
            dt_naive = datetime.strptime(ts_str, _TIMESTAMP_FMT_B)
            dt_utc = dt_naive.replace(tzinfo=timezone.utc)
            return AllTxtRecord(
                utc=normalise_slot(dt_utc),
                freq_hz=float(freq_str),
                dt_s=float(dt_str),
                snr_db=float(snr_str),
                message=" ".join(message.split()),
            )
        except (ValueError, OverflowError):
            return None

    return None


def parse_all_txt(path: Path) -> tuple[list[AllTxtRecord], int]:
    """Parse an ALL.TXT decode log, returning (records, skipped_line_count).

    Supports both Format A (test-fixture/synthetic, 8-digit YYYYMMDD date with
    UTC keyword) and Format B (real WSJT-X / OpenWSFZ, 6-digit YYMMDD date with
    dial-MHz and Rx keyword).  Only FT8 lines are returned.
    """
    records: list[AllTxtRecord] = []
    skipped = 0

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                skipped += 1
                continue
            rec = _parse_line(line)
            if rec is None:
                skipped += 1
            else:
                records.append(rec)

    return records, skipped
