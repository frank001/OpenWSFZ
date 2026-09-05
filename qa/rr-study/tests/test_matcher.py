"""Unit tests for harness/matcher.py — per-message matching
(rr-density-qrm-scenario / R&R-007).

Prior to this change, S4 (Density/QRM) truth rows pooled every message injected
into a cycle into one row and scored a match as "decoded any one of N" — a
ceiling effect that made S4 unable to distinguish good QRM handling from bad
(see qa/rr-study/RR-007.md). The fix retires that special case and lets S4
flow through the same generic per-truth-row matching path S1-S3, S7, and S8
already use correctly. These tests exercise that generic path directly against
synthetic AllTxtRecord/truth-row fixtures, bypassing file I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

# Make qa/rr-study importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.common import AllTxtRecord
from harness.matcher import _apply_since, _match_appraiser, _parse_since

CYCLE = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)


def _truth_row(part_index, trial_index, message_text, freq_hz,
               snr_db=0.0, dt_s=0.0, cycle=CYCLE):
    return {
        "scenario_id":  "S4",
        "part_index":   part_index,
        "trial_index":  trial_index,
        "seed":         1,
        "message_text": message_text,
        "true_snr_db":  snr_db,
        "true_dt_s":    dt_s,
        "true_freq_hz": freq_hz,
        "cycle_utc":    cycle.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_cycle_dt":    cycle,
    }


def _record(message, freq_hz, cycle=CYCLE, snr_db=0.0, dt_s=0.0):
    return AllTxtRecord(utc=cycle, freq_hz=freq_hz, dt_s=dt_s, snr_db=snr_db, message=message)


def test_multi_message_s4_cycle_scores_each_message_independently():
    """A busy S4-style cycle with 3 truth messages, partial recovery (2/3), must
    produce 2 matched rows and 1 missed row -- not a single aggregate outcome
    for the whole cycle (the ceiling-effect defect RR-007 found)."""
    truth_rows = [
        _truth_row(4, 0, "CQ Q1ABC FN42",    freq_hz=500.0),
        _truth_row(4, 0, "Q4XYZ Q1ABC -07",  freq_hz=1000.0),
        _truth_row(4, 0, "Q3PQR Q1ABC RR73", freq_hz=1500.0),
    ]
    # Appraiser decodes messages 1 and 2 correctly, misses message 3 entirely.
    candidates = [
        _record("CQ Q1ABC FN42",   500.0),
        _record("Q4XYZ Q1ABC -07", 1000.0),
    ]
    rows = _match_appraiser(truth_rows, candidates, "OpenWSFZ", "S4")

    matched = [r for r in rows if r["matched"]]
    missed  = [r for r in rows if not r["matched"] and not r["false_positive"]]
    fps     = [r for r in rows if r["false_positive"]]

    assert len(matched) == 2
    assert len(missed) == 1
    assert len(fps) == 0
    assert missed[0]["message_text"] == "Q3PQR Q1ABC RR73"


def test_correctly_decoded_secondary_message_is_matched_not_false_positive():
    """A second, distinct correct decode in the same cycle must be recorded as
    its own matched row, never miscounted as a false positive (previously, only
    the first pool hit was consumed and every other correct decode fell through
    to Pass 2 as a spurious FP)."""
    truth_rows = [
        _truth_row(4, 0, "CQ Q1ABC FN42",   freq_hz=500.0),
        _truth_row(4, 0, "Q4XYZ Q1ABC -07", freq_hz=1000.0),
    ]
    candidates = [
        _record("CQ Q1ABC FN42",   500.0),
        _record("Q4XYZ Q1ABC -07", 1000.0),
    ]
    rows = _match_appraiser(truth_rows, candidates, "OpenWSFZ", "S4")
    assert sum(1 for r in rows if r["matched"]) == 2
    assert sum(1 for r in rows if r["false_positive"]) == 0


def test_no_signals_decoded_yields_all_misses():
    """Zero decodes in a busy cycle must yield one miss per truth row -- not one
    aggregate miss for the cycle."""
    truth_rows = [
        _truth_row(4, 0, "CQ Q1ABC FN42",   freq_hz=500.0),
        _truth_row(4, 0, "Q4XYZ Q1ABC -07", freq_hz=1000.0),
    ]
    rows = _match_appraiser(truth_rows, [], "OpenWSFZ", "S4")
    assert len(rows) == 2
    assert all(not r["matched"] and not r["false_positive"] for r in rows)


def test_extra_unconsumed_candidate_becomes_false_positive():
    """A candidate that doesn't correspond to any truth row is a genuine FP,
    unaffected by this change."""
    truth_rows = [_truth_row(4, 0, "CQ Q1ABC FN42", freq_hz=500.0)]
    candidates = [
        _record("CQ Q1ABC FN42", 500.0),
        _record("CQ Q9ZZZ AB12", 2000.0),  # not in truth -- genuine noise decode
    ]
    rows = _match_appraiser(truth_rows, candidates, "OpenWSFZ", "S4")
    matched = [r for r in rows if r["matched"]]
    fps     = [r for r in rows if r["false_positive"]]
    assert len(matched) == 1
    assert len(fps) == 1
    assert fps[0]["message_text"] == "CQ Q9ZZZ AB12"


def test_repeated_message_text_at_different_frequencies_matched_independently():
    """S4's message pool wraps for parts with more signals than pool entries
    (e.g. 30 signals drawn from a 10-message pool), so identical message_text
    can legitimately appear more than once in one cycle -- at different
    frequencies. Each occurrence must be matched to its own candidate by
    frequency, not double-consumed or conflated."""
    truth_rows = [
        _truth_row(4, 0, "CQ Q1ABC FN42", freq_hz=500.0),
        _truth_row(4, 0, "CQ Q1ABC FN42", freq_hz=2000.0),
    ]
    candidates = [
        _record("CQ Q1ABC FN42", 500.0),
        _record("CQ Q1ABC FN42", 2000.0),
    ]
    rows = _match_appraiser(truth_rows, candidates, "OpenWSFZ", "S4")
    matched = [r for r in rows if r["matched"]]
    assert len(matched) == 2
    reported_freqs = sorted(r["reported_freq_hz"] for r in matched)
    assert reported_freqs == [500.0, 2000.0]


def test_s5_signal_free_slot_yields_no_match_and_no_consumption():
    """S5's signal-free slots carry true_freq_hz='' and message_text=''; the
    matcher must not attempt to match them (regression guard: S5's own
    semantics are unaffected by retiring the S4 pool-matching branch), and any
    candidate present in that slot must fall through as a false positive."""
    truth_rows = [{
        "scenario_id":  "S5",
        "part_index":   0,
        "trial_index":  0,
        "seed":         1,
        "message_text": "",
        "true_snr_db":  "",
        "true_dt_s":    0.0,
        "true_freq_hz": "",
        "cycle_utc":    CYCLE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_cycle_dt":    CYCLE,
    }]
    candidates = [_record("CQ Q1ABC FN42", 500.0)]  # a birdie/false decode
    rows = _match_appraiser(truth_rows, candidates, "OpenWSFZ", "S5")
    misses = [r for r in rows if not r["matched"] and not r["false_positive"]]
    fps    = [r for r in rows if r["false_positive"]]
    assert len(misses) == 1  # the truth row itself: not matched, not an FP
    assert len(fps) == 1     # the candidate falls through as a genuine FP


def test_s7_s8_style_multi_signal_cycle_still_matches_correctly():
    """Regression guard: S7 and S8 already relied on the generic per-truth-row
    matching path this change generalises S4 onto. A 4-signal cycle (typical
    of S7 compounding pairs / S8 band-scene density) with mixed match/miss
    outcomes must still score independently and correctly."""
    truth_rows = [
        _truth_row(0, 0, "CQ Q1ABC FN42",     freq_hz=450.0),
        _truth_row(0, 0, "Q2DEF Q1ABC FN42",  freq_hz=900.0),
        _truth_row(0, 0, "Q3GHI Q1ABC -10",   freq_hz=1350.0),
        _truth_row(0, 0, "Q4JKL Q1ABC RR73",  freq_hz=1800.0),
    ]
    candidates = [
        _record("CQ Q1ABC FN42",    450.0),
        _record("Q3GHI Q1ABC -10", 1350.0),
    ]
    rows = _match_appraiser(truth_rows, candidates, "WSJT-X", "S8")
    matched = {r["message_text"] for r in rows if r["matched"]}
    missed  = {r["message_text"] for r in rows
               if not r["matched"] and not r["false_positive"]}
    assert matched == {"CQ Q1ABC FN42", "Q3GHI Q1ABC -10"}
    assert missed == {"Q2DEF Q1ABC FN42", "Q4JKL Q1ABC RR73"}


# ---------------------------------------------------------------------------
# --since cutoff (S5-STANDALONE 2026-09-05 finding, §6.1) — pass-2 has no
# time window of its own, so a pre-run warm-up decode left in either ALL.TXT
# gets counted as an in-scenario false positive. --since lets the operator
# drop it mechanically instead of hand-editing the log files.
# ---------------------------------------------------------------------------

def test_parse_since_returns_none_when_not_given():
    assert _parse_since(None) is None


def test_parse_since_parses_utc_and_rejects_bad_format():
    dt = _parse_since("2026-09-05T13:38:30Z")
    assert dt == datetime(2026, 9, 5, 13, 38, 30, tzinfo=timezone.utc)
    with pytest.raises(SystemExit):
        _parse_since("not-a-timestamp")


def test_apply_since_is_a_noop_when_cutoff_is_none():
    records = [_record("CQ Q1ABC FN42", 500.0)]
    assert _apply_since(records, None, "OpenWSFZ") == records


def test_apply_since_drops_only_records_strictly_before_cutoff():
    cutoff = datetime(2026, 9, 5, 13, 38, 30, tzinfo=timezone.utc)
    warmup = _record("CQ Q1ABC FN42", 700.0, cycle=datetime(2026, 9, 5, 13, 36, 45, tzinfo=timezone.utc))
    on_cutoff = _record("CQ Q2DEF FN42", 700.0, cycle=cutoff)
    after = _record("CQ Q3GHI FN42", 700.0, cycle=datetime(2026, 9, 5, 13, 38, 45, tzinfo=timezone.utc))
    kept = _apply_since([warmup, on_cutoff, after], cutoff, "OpenWSFZ")
    assert kept == [on_cutoff, after]


def test_since_end_to_end_reproduces_manual_warm_up_filter():
    """Regression guard for the S5-STANDALONE 2026-09-05 finding: feeding an
    unfiltered log (warm-up decode still present) through --since must yield
    the same FP count as manually cutting the warm-up line, for a signal-free
    S5-style scenario."""
    warmup_cycle = datetime(2026, 9, 5, 13, 36, 45, tzinfo=timezone.utc)
    first_run_cycle = datetime(2026, 9, 5, 13, 38, 30, tzinfo=timezone.utc)
    truth_rows = [{
        "scenario_id":  "S5",
        "part_index":   0,
        "trial_index":  0,
        "seed":         1,
        "message_text": "",
        "true_snr_db":  "",
        "true_dt_s":    0.0,
        "true_freq_hz": "",
        "cycle_utc":    first_run_cycle.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_cycle_dt":    first_run_cycle,
    }]
    unfiltered = [
        _record("CQ Q1ABC FN42", 700.0, cycle=warmup_cycle),   # pre-run warm-up
        _record("CQ Q9ZZZ AB12", 900.0, cycle=first_run_cycle),  # genuine in-run FP
    ]

    # Without --since: pass-2 has no window, so both fall through as FPs.
    unfiltered_rows = _match_appraiser(truth_rows, unfiltered, "OpenWSFZ", "S5")
    assert sum(1 for r in unfiltered_rows if r["false_positive"]) == 2

    # With --since set to the run's own first truth-row cycle: only the
    # genuine in-run FP survives -- matches the manual-filter result.
    filtered = _apply_since(unfiltered, first_run_cycle, "OpenWSFZ")
    filtered_rows = _match_appraiser(truth_rows, filtered, "OpenWSFZ", "S5")
    fps = [r for r in filtered_rows if r["false_positive"]]
    assert len(fps) == 1
    assert fps[0]["message_text"] == "CQ Q9ZZZ AB12"
