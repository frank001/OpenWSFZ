"""Regression tests for `_unexplained_decode_events` (Ask A, Architect -> QA,
Captain-directed, 2026-09-12: "I did notice a FP that was not even reported at
all.").

The report's only false-positive metric was `_fp_rate`, scoped to S5's
signal-free slots. A decode in S1-S4/S7/S8 that matched no injected message
in its own cycle was never counted anywhere. This whole-battery INFO metric
closes that gap by reading truth.csv + the raw ALL.TXT logs directly (not the
per-scenario *_matched.csv files, whose own pass-2 FP rows are inflated by
construction -- see the function's own docstring / module comment in
analyse.py), using the harness's own match predicates.

Live-sweep reproduction (25/16/2 OpenWSFZ, 0/0/0 WSJT-X across
2026-09-06-4c7d5ad / 2026-09-07-4cc1984 / 2026-09-12-fbf8c0b) was verified
by hand against the three committed sweeps the Architect cited; not repeated
here as an automated test since it would require committing those sweeps'
raw ALL.TXT content to this test file (NFR-021 -- those logs carry
decoder-hallucinated callsign-shaped text) or reading committed run
directories from a test (fragile, and outside what a fast unit test should
touch). This file's synthetic fixtures below exercise the same code path.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

# Make qa/rr-study importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.analyse import _unexplained_decode_events

TRUTH_FIELDS = [
    "scenario_id", "part_index", "trial_index", "seed",
    "true_snr_db", "true_dt_s", "true_freq_hz", "message_text", "cycle_utc",
]


def _write_truth(run_dir: Path, rows: list[dict]) -> None:
    path = run_dir / "truth.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRUTH_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _all_txt_line(ts: str, freq_hz: int, dt_s: float, snr_db: int, message: str) -> str:
    """Format A (test-fixture) ALL.TXT line -- see harness/common.py's parser
    docstring: 8-digit date, 'UTC', freq, dt, snr, mode, message."""
    return f"{ts}   UTC  {freq_hz}  {dt_s}  {snr_db}  FT8  {message}\n"


def _truth_row(scenario_id, cycle, message_text, freq_hz, snr=0.0, dt=0.0,
               part_index=0, trial_index=0, seed=1):
    return {
        "scenario_id": scenario_id, "part_index": part_index,
        "trial_index": trial_index, "seed": seed,
        "true_snr_db": snr, "true_dt_s": dt, "true_freq_hz": freq_hz,
        "message_text": message_text, "cycle_utc": cycle,
    }


def test_unexplained_decode_in_non_s5_cycle_is_counted(tmp_path: Path):
    """The Ask's own regression case: a synthetic truth + ALL.TXT pair with
    exactly one decode that matches no injected message, inside a non-S5
    (here: S3) cycle. It must be counted -- this is the exact gap the report
    was blind to before this metric existed."""
    run_dir = tmp_path
    cycle = "2026-09-12T12:17:00Z"
    _write_truth(run_dir, [
        _truth_row("S3", cycle, "CQ Q1ABC FN42", freq_hz=1500.0),
    ])
    # OpenWSFZ decodes the genuine signal AND emits one unexplained decode
    # (garbage text, near the real signal but not a text match) in the same
    # cycle.
    (run_dir / "owsfz-all.txt").write_text(
        _all_txt_line("20260912_121700", 1500, 0.0, -10, "CQ Q1ABC FN42")
        + _all_txt_line("20260912_121700", 1506, 0.0, -22, "CQ Q9GARBAGE FN42"),
        encoding="utf-8",
    )
    (run_dir / "wsjt-all.txt").write_text("", encoding="utf-8")

    result = _unexplained_decode_events(run_dir)
    assert result is not None
    assert result["OpenWSFZ"]["total"] == 1
    assert result["WSJT-X"]["total"] == 0

    s3 = result["OpenWSFZ"]["by_scenario"]["S3"]
    assert s3["count"] == 1
    # Distance to the nearest injected signal in the same cycle: |1506-1500| = 6 Hz.
    assert s3["distances_hz"] == [pytest.approx(6.0)]


def test_matched_decode_is_not_counted(tmp_path: Path):
    """A decode whose text AND frequency both match a truth row (harness
    matcher semantics) must not appear in the unexplained count at all."""
    run_dir = tmp_path
    cycle = "2026-09-12T12:17:00Z"
    _write_truth(run_dir, [
        _truth_row("S1", cycle, "CQ Q1ABC FN42", freq_hz=1500.0),
    ])
    (run_dir / "owsfz-all.txt").write_text(
        _all_txt_line("20260912_121700", 1500, 0.0, -10, "CQ Q1ABC FN42"),
        encoding="utf-8",
    )
    (run_dir / "wsjt-all.txt").write_text("", encoding="utf-8")

    result = _unexplained_decode_events(run_dir)
    assert result["OpenWSFZ"]["total"] == 0
    assert result["OpenWSFZ"]["by_scenario"] == {}


def test_text_match_at_wrong_frequency_is_still_unexplained(tmp_path: Path):
    """Harness matcher semantics require BOTH text and frequency (within
    matcher.FREQ_TOLERANCE_HZ) to explain a decode -- a text-only match (the
    Architect's own cross-check script's criterion) is not enough. This is
    the documented divergence from that script, not a bug."""
    run_dir = tmp_path
    cycle = "2026-09-12T12:17:00Z"
    _write_truth(run_dir, [
        _truth_row("S2", cycle, "CQ Q1ABC FN42", freq_hz=1500.0),
    ])
    # Same text, but 50 Hz away -- well outside the +/-4 Hz matcher tolerance.
    (run_dir / "owsfz-all.txt").write_text(
        _all_txt_line("20260912_121700", 1550, 0.0, -10, "CQ Q1ABC FN42"),
        encoding="utf-8",
    )
    (run_dir / "wsjt-all.txt").write_text("", encoding="utf-8")

    result = _unexplained_decode_events(run_dir)
    assert result["OpenWSFZ"]["total"] == 1
    assert result["OpenWSFZ"]["by_scenario"]["S2"]["distances_hz"] == [pytest.approx(50.0)]


def test_s5_signal_free_cycle_unexplained_decode_has_no_distance(tmp_path: Path):
    """A genuine S5 noise-floor decode (signal-free slot, true_freq_hz='')
    must still be counted under S5, but with distance None -- there is no
    injected signal in that cycle to measure a distance to."""
    run_dir = tmp_path
    cycle = "2026-09-12T12:28:00Z"
    _write_truth(run_dir, [
        _truth_row("S5", cycle, "", freq_hz=""),
    ])
    (run_dir / "owsfz-all.txt").write_text(
        _all_txt_line("20260912_122800", 900, 0.0, -19, "CQ Q9NOISE FN42"),
        encoding="utf-8",
    )
    (run_dir / "wsjt-all.txt").write_text("", encoding="utf-8")

    result = _unexplained_decode_events(run_dir)
    assert result["OpenWSFZ"]["total"] == 1
    s5 = result["OpenWSFZ"]["by_scenario"]["S5"]
    assert s5["count"] == 1
    assert s5["distances_hz"] == [None]


def test_decode_outside_any_truth_cycle_is_excluded_entirely(tmp_path: Path):
    """A decode whose cycle_utc does not appear in truth.csv at all (e.g. a
    pre-run warm-up line, per the Architect's own script's treatment of the
    11:54:00 preflight line) must not be counted under any scenario."""
    run_dir = tmp_path
    _write_truth(run_dir, [
        _truth_row("S3", "2026-09-12T12:17:00Z", "CQ Q1ABC FN42", freq_hz=1500.0),
    ])
    (run_dir / "owsfz-all.txt").write_text(
        # Warm-up decode well before the run's own first truth cycle.
        _all_txt_line("20260912_115400", 900, 0.0, -18, "CQ Q9WARMUP FN42")
        + _all_txt_line("20260912_121700", 1500, 0.0, -10, "CQ Q1ABC FN42"),
        encoding="utf-8",
    )
    (run_dir / "wsjt-all.txt").write_text("", encoding="utf-8")

    result = _unexplained_decode_events(run_dir)
    assert result["OpenWSFZ"]["total"] == 0


def test_no_truth_csv_returns_none(tmp_path: Path):
    assert _unexplained_decode_events(tmp_path) is None
