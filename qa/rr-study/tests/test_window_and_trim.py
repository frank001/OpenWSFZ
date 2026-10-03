"""Gate A-W names its window's members; a battery's ALL.TXT copies are trimmed to its own window
(Architect follow-ups, 2026-10-03)."""
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

RR = Path(__file__).resolve().parents[1]
for p in (str(RR), str(RR / "harness")):
    if p not in sys.path:
        sys.path.insert(0, p)

from harness import analyse as A  # noqa: E402
import run_study as RS  # noqa: E402


def test_window_members_are_named_with_the_mixed_flag_caveat(tmp_path):
    with open(tmp_path / "trend.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(["run_date", "git_sha", "fp_events_s5", "fp_slots_s5"])
        wr.writerow(["2026-09-29", "0d6b19377febf2a2aa5c2477742d543e27625407", 0, 120])
    used = [("96077a0", 0, 120), ("0d6b193", 0, 120), ("4cc1984", 3, 120)]
    text = "\n".join(A._window_member_lines(used, tmp_path))
    assert "this run `96077a0` 0/120" in text
    assert "2026-09-29 `0d6b193` 0/120" in text
    assert "seed `4cc1984` 3/120" in text
    assert "MIXED" in text and "same SHA7" in text


def _line(stamp, rest="14.074 Rx FT8 -8 0.1 1500 X"):
    return f"{stamp}    {rest}\n"


def test_trim_drops_only_earlier_dated_lines_and_keeps_undatable_ones(tmp_path):
    f = tmp_path / "all.txt"
    f.write_text(_line("261002_231600") + "garbage line without a stamp\n" + _line("261003_011700")
                 + _line("261003_011715"), encoding="utf-8")
    start = datetime(2026, 10, 3, 1, 16, 24, tzinfo=timezone.utc)
    kept, dropped = RS._trim_log_to_window(f, start)
    assert (kept, dropped) == (3, 1)
    out = f.read_text(encoding="utf-8")
    assert "261002_231600" not in out and "garbage line" in out and "261003_011715" in out


def test_trim_keeps_lines_within_the_margin_before_the_start(tmp_path):
    f = tmp_path / "all.txt"
    f.write_text(_line("261003_011500"), encoding="utf-8")                  # 84 s before the start: inside the margin
    kept, dropped = RS._trim_log_to_window(f, datetime(2026, 10, 3, 1, 16, 24, tzinfo=timezone.utc))
    assert (kept, dropped) == (1, 0)
