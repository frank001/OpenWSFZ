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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

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

# Format: YYYYMMDD_HHMMSS   UTC  <freq_hz>  <dt_s>  <snr_db>  <mode>  <message>
# Two or more spaces separate fields; freq_hz is in Hz (integer), dt_s and
# snr_db are decimals.
_ALL_TXT_RE = re.compile(
    r"^(\d{8}_\d{6})\s{2,}UTC\s{2,}(\d+)\s+([-\d.]+)\s+([-\d]+)\s+(\w+)\s+(.+?)\s*$"
)

_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"


class AllTxtRecord(NamedTuple):
    utc: datetime    # normalised to slot boundary (UTC, no microseconds)
    freq_hz: float
    dt_s: float
    snr_db: float
    message: str


def parse_all_txt(path: Path) -> tuple[list[AllTxtRecord], int]:
    """Parse an ALL.TXT decode log, returning (records, skipped_line_count).

    Only FT8 lines are returned. Lines that do not match the expected format
    or whose mode is not FT8 (case-insensitive) are counted as skipped.
    """
    records: list[AllTxtRecord] = []
    skipped = 0

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                skipped += 1
                continue
            m = _ALL_TXT_RE.match(line)
            if m is None:
                skipped += 1
                continue
            ts_str, freq_str, dt_str, snr_str, mode, message = m.groups()
            if mode.upper() != "FT8":
                skipped += 1
                continue
            try:
                dt_naive = datetime.strptime(ts_str, _TIMESTAMP_FMT)
                dt_utc = dt_naive.replace(tzinfo=timezone.utc)
                slot = normalise_slot(dt_utc)
                records.append(AllTxtRecord(
                    utc=slot,
                    freq_hz=float(freq_str),
                    dt_s=float(dt_str),
                    snr_db=float(snr_str),
                    message=" ".join(message.split()),  # whitespace-normalise
                ))
            except (ValueError, OverflowError):
                skipped += 1
                continue

    return records, skipped
