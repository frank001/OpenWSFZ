"""Unit tests for R&R-011 -- the S5 Gate A trailing-window gate.

Spec: qa/rr-study/2026-09-08-1452-architect-to-qa-spec-rr-011-s5-trailing-window-gate.md
Ruling: qa/rr-study/2026-09-08-1429-architect-to-qa-ruling-s5-gate-a-first-point-and-gate-form.md

Section 8 task 3: "Reproduce Sec.5 exactly before the next sweep, as an
implementation test... If your implementation returns anything else, the
implementation is wrong -- escalate, do not adjust the spec." This file is
that test, plus coverage of the ROW 0 preconditions (Sec.3) and the standing
prohibition against pooling Gate A / Gate A-W / Gate A-Delta into one S5 line.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.analyse import (
    S5_WINDOW_SEED,
    S5_WINDOW_SLOTS,
    S5_WINDOW_ALPHA_CHANGE,
    S5_AWGN_PARTS,
    _verdict_s5_window,
    _verdict_s5_change,
    _s5_window_loo,
    _s5_row0a_void,
    _s5_row0b_scoping_ok,
    _s5_window_history,
    _s5_window_gate,
    _verdict_fp,
    _collect_verdicts,
    _append_trend,
    _cp_upper_95,
    _TREND_S5_EVENTS_COL,
    _TREND_S5_SLOTS_COL,
    _TREND_COLUMNS,
    THRESH_FP_UB95,
)


# ---------------------------------------------------------------------------
# Section 5 worked example -- the implementation test the spec demands
# ---------------------------------------------------------------------------

class TestSection5WorkedExample:
    def test_gate_a_w_reproduces_exactly(self):
        verdict, k, n, used = _verdict_s5_window(S5_WINDOW_SEED)
        assert (k, n) == (15, 480)
        assert verdict == "PASS"
        ub = 100.0 * _cp_upper_95(k, n)
        assert abs(ub - 4.771) < 0.001
        assert used == S5_WINDOW_SEED  # nothing truncated -- the seed fills the window exactly

    def test_gate_a_delta_reproduces_exactly(self):
        _, _, _, used = _verdict_s5_window(S5_WINDOW_SEED)
        verdict, p, (k1, n1), (k0, n0) = _verdict_s5_change(used)
        assert (k1, n1) == (3, 120)
        assert (k0, n0) == (12, 360)
        assert abs(p - 0.7682) < 0.0001
        assert verdict == "PASS"

    def test_loo_all_seven_deletions_pass_not_fragile(self):
        _, _, _, used = _verdict_s5_window(S5_WINDOW_SEED)
        fragile, deletions = _s5_window_loo(used)
        assert len(deletions) == 7
        assert all(d["verdict"] == "PASS" for d in deletions)
        assert fragile is False

    def test_seed_totals_match_the_spec_prose(self):
        # Section 5's own numbers, restated as a test rather than trusted as prose.
        assert sum(ev for _, ev, _ in S5_WINDOW_SEED) == 15
        assert sum(sl for _, _, sl in S5_WINDOW_SEED) == 480
        assert S5_WINDOW_SEED[0] == ("4cc1984", 3, 120)


# ---------------------------------------------------------------------------
# ROW 0 preconditions (spec Sec.3) -- must pre-empt BOTH gates, mechanically
# ---------------------------------------------------------------------------

class TestRow0Preconditions:
    def test_row0a_void_when_s4_recall_is_zero(self):
        attr = {"confusion": {"OpenWSFZ": {"TP": 0, "FN": 5, "FP": 0, "TN": 100}}}
        fires, detail = _s5_row0a_void(attr)
        assert fires is True
        assert "recall == 0" in detail

    def test_row0a_void_when_s4_did_not_run(self):
        fires, detail = _s5_row0a_void(None)
        assert fires is True
        assert "did not run" in detail

    def test_row0a_void_when_s4_injected_nothing(self):
        attr = {"confusion": {"OpenWSFZ": {"TP": 0, "FN": 0, "FP": 0, "TN": 60}}}
        fires, detail = _s5_row0a_void(attr)
        assert fires is True

    def test_row0a_clears_when_recall_positive(self):
        attr = {"confusion": {"OpenWSFZ": {"TP": 4, "FN": 1, "FP": 0, "TN": 100}}}
        fires, detail = _s5_row0a_void(attr)
        assert fires is False
        assert "4/5" in detail

    def _s5_matched_df(self, awgn_events_openwsfz=0):
        """Minimal S5 matched frame: 120 AWGN (parts 0/1) truth slots per
        appraiser, plus `awgn_events_openwsfz` OpenWSFZ FP decodes scoped
        inside that AWGN window."""
        rows = []
        for appr in ("WSJT-X", "OpenWSFZ"):
            for part in (0, 1):
                for i in range(60):
                    cyc = f"c-{part}-{i}"
                    rows.append({
                        "appraiser": appr, "part_index": part, "trial_index": i,
                        "cycle_utc": cyc, "false_positive": False,
                    })
            for i in range(awgn_events_openwsfz if appr == "OpenWSFZ" else 0):
                rows.append({
                    "appraiser": appr, "part_index": float("nan"), "trial_index": i,
                    "cycle_utc": f"c-0-{i}", "false_positive": True,
                })
        return pd.DataFrame(rows)

    def test_row0b_clears_when_scoping_matches(self):
        df = self._s5_matched_df(awgn_events_openwsfz=3)
        fp_info = {"n_fp_events": 3}
        ok, unscoped, scoped = _s5_row0b_scoping_ok(df, fp_info)
        assert ok is True
        assert (unscoped, scoped) == (3, 3)

    def test_row0b_fires_on_a_mismatched_count(self):
        df = self._s5_matched_df(awgn_events_openwsfz=3)
        fp_info = {"n_fp_events": 99}  # deliberately wrong
        ok, unscoped, scoped = _s5_row0b_scoping_ok(df, fp_info)
        assert ok is False

    def test_row0c_info_when_window_not_yet_full(self):
        short_window = [("aaaaaaa", 1, 60)]
        verdict, k, n, used = _verdict_s5_window(short_window)
        assert verdict == "INFO"
        assert (k, n) == (1, 60)

    def test_gate_a_delta_info_on_single_sweep_window(self):
        verdict, p, (k1, n1), (k0, n0) = _verdict_s5_change([("aaaaaaa", 1, 480)])
        assert verdict == "INFO"
        assert k1 is None and n1 is None and k0 is None and n0 is None


# ---------------------------------------------------------------------------
# Full orchestration (_s5_window_gate) -- ROW 0 pre-empts the gates in order
# ---------------------------------------------------------------------------

class TestS5WindowGateOrchestration:
    def _clean_attr(self, tp=5, fn=0):
        return {"confusion": {"OpenWSFZ": {"TP": tp, "FN": fn, "FP": 0, "TN": 100}}}

    def _s5_df(self, n_events):
        rows = []
        for appr in ("WSJT-X", "OpenWSFZ"):
            for part in (0, 1):
                for i in range(60):
                    rows.append({
                        "appraiser": appr, "part_index": part, "trial_index": i,
                        "cycle_utc": f"c-{part}-{i}", "false_positive": False,
                    })
            for i in range(n_events if appr == "OpenWSFZ" else 0):
                rows.append({
                    "appraiser": appr, "part_index": float("nan"), "trial_index": i,
                    "cycle_utc": f"c-0-{i}", "false_positive": True,
                })
        return pd.DataFrame(rows)

    def test_void_on_row0a_skips_both_gates(self, tmp_path):
        fp_results = {"OpenWSFZ": {"n_fp_events": 3, "n_slots": 120}}
        result = _s5_window_gate(
            tmp_path, "deadbeef", fp_results, self._clean_attr(tp=0, fn=5), self._s5_df(3),
        )
        assert result["status"] == "VOID"
        assert result["row"] == "0a"

    def test_scored_when_row0_clears_and_seed_alone_reaches_480(self, tmp_path):
        # No trend.csv history at all: window = [today] + seed. Today's own
        # 120 slots plus the 480-slot seed exceeds S5_WINDOW_SLOTS immediately,
        # so this is SCORED on the first call, never blocked on missing state.
        fp_results = {"OpenWSFZ": {"n_fp_events": 3, "n_slots": 120}}
        result = _s5_window_gate(
            tmp_path, "0000000", fp_results, self._clean_attr(), self._s5_df(3),
        )
        assert result["status"] == "SCORED"
        assert result["window"]["used"][0] == ("0000000", 3, 120)

    def test_not_run_when_s5_awgn_produced_no_reading(self, tmp_path):
        fp_results = {"OpenWSFZ": {"n_fp_events": float("nan"), "n_slots": 0}}
        result = _s5_window_gate(
            tmp_path, "0000000", fp_results, self._clean_attr(), self._s5_df(0),
        )
        assert result["status"] == "NOT_RUN"


# ---------------------------------------------------------------------------
# trend.csv persistence -- "seed from Sec.2, derive the rest" (Sec.8 task 2)
# ---------------------------------------------------------------------------

class TestWindowHistoryPersistence:
    def _write_trend(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=_TREND_COLUMNS)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    def test_history_skips_seed_shas_and_incomplete_rows(self, tmp_path):
        rows = [
            {"run_date": "2026-09-07", "git_sha": "4cc1984" + "0" * 33,
             _TREND_S5_EVENTS_COL: "3", _TREND_S5_SLOTS_COL: "120"},  # in the seed -> skipped
            {"run_date": "2026-06-01", "git_sha": "abc0000" + "0" * 33,
             _TREND_S5_EVENTS_COL: "", _TREND_S5_SLOTS_COL: ""},      # incomplete -> skipped
            {"run_date": "2026-09-09", "git_sha": "eeeeee1" + "0" * 33,
             _TREND_S5_EVENTS_COL: "5", _TREND_S5_SLOTS_COL: "120"},  # new -> kept
        ]
        self._write_trend(tmp_path / "trend.csv", rows)
        history = _s5_window_history(tmp_path)
        assert history == [("eeeeee1", 5, 120)]

    def test_history_empty_when_no_trend_file(self, tmp_path):
        assert _s5_window_history(tmp_path) == []

    def test_newest_sweep_slides_the_oldest_seed_entry_out(self, tmp_path):
        rows = [{"run_date": "2026-09-09", "git_sha": "eeeeee1" + "0" * 33,
                  _TREND_S5_EVENTS_COL: "0", _TREND_S5_SLOTS_COL: "120"}]
        self._write_trend(tmp_path / "trend.csv", rows)
        history = _s5_window_history(tmp_path)
        window = history + list(S5_WINDOW_SEED)
        verdict, k, n, used = _verdict_s5_window(window)
        assert n == 480
        # The oldest seed entry (22b749c, last in the newest-first list) must
        # have aged out once a new 120-slot sweep pushed the trailing sum
        # past 480 -- that is the entire point of a TRAILING window.
        assert ("22b749c", 0, 60) not in used


# ---------------------------------------------------------------------------
# Amendment 1 (2026-09-08): a VOIDed/NOT_RUN sweep contributes ZERO slots to
# the window; an INFO sweep's counts MUST still persist. One test per branch.
# ---------------------------------------------------------------------------

class TestAmendment1TrendWriteGatedOnStatus:
    _COMMON_ARGS = dict(continuous_results={}, kappa_results={}, bias_results={})

    def _fp_results(self, k=3, n=120):
        return {"OpenWSFZ": {"n_fp_events": k, "n_slots": n, "event_rate_ub95": 6.0}}

    def _read_s5_cols(self, trend_path):
        with open(trend_path, newline="", encoding="utf-8") as fh:
            row = list(csv.DictReader(fh))[0]
        return row[_TREND_S5_EVENTS_COL], row[_TREND_S5_SLOTS_COL]

    def test_void_run_writes_empty_s5_columns(self, tmp_path):
        _append_trend(tmp_path, Path("2026-09-09-deadbeef"), "deadbeef",
                      fp_results=self._fp_results(), s5_window_result={"status": "VOID", "row": "0a"},
                      **self._COMMON_ARGS)
        events, slots = self._read_s5_cols(tmp_path / "trend.csv")
        assert (events, slots) == ("", "")

    def test_not_run_writes_empty_s5_columns(self, tmp_path):
        _append_trend(tmp_path, Path("2026-09-09-deadbeef"), "deadbeef",
                      fp_results=self._fp_results(), s5_window_result={"status": "NOT_RUN"},
                      **self._COMMON_ARGS)
        events, slots = self._read_s5_cols(tmp_path / "trend.csv")
        assert (events, slots) == ("", "")

    def test_missing_window_result_writes_empty_s5_columns(self, tmp_path):
        """No `s5_window_result` at all (e.g. a caller that never ran the
        orchestration) must not be treated as license to write raw counts --
        the same fail-closed default as NOT_RUN."""
        _append_trend(tmp_path, Path("2026-09-09-deadbeef"), "deadbeef",
                      fp_results=self._fp_results(), s5_window_result=None,
                      **self._COMMON_ARGS)
        events, slots = self._read_s5_cols(tmp_path / "trend.csv")
        assert (events, slots) == ("", "")

    def test_info_run_persists_its_counts(self, tmp_path):
        """ROW 0c INFO means the WINDOW is short, not that the run is bad --
        its counts must still land in trend.csv or the fill stalls forever."""
        _append_trend(tmp_path, Path("2026-09-09-deadbeef"), "deadbeef",
                      fp_results=self._fp_results(k=1, n=120),
                      s5_window_result={"status": "INFO", "k": 1, "n": 120}, **self._COMMON_ARGS)
        events, slots = self._read_s5_cols(tmp_path / "trend.csv")
        assert (events, slots) == ("1", "120")

    def test_scored_run_persists_its_counts(self, tmp_path):
        _append_trend(tmp_path, Path("2026-09-09-deadbeef"), "deadbeef",
                      fp_results=self._fp_results(k=3, n=120),
                      s5_window_result={"status": "SCORED", "window": {}, "change": {}, "loo": {}},
                      **self._COMMON_ARGS)
        events, slots = self._read_s5_cols(tmp_path / "trend.csv")
        assert (events, slots) == ("3", "120")

    def test_void_run_does_not_appear_in_the_next_window(self, tmp_path):
        _append_trend(tmp_path, Path("2026-09-09-deadvoid"), "deadv0i",
                      fp_results=self._fp_results(k=0, n=120),
                      s5_window_result={"status": "VOID", "row": "0a"}, **self._COMMON_ARGS)
        assert _s5_window_history(tmp_path) == []

    def test_info_run_does_appear_in_the_next_window(self, tmp_path):
        _append_trend(tmp_path, Path("2026-09-09-goodinfo"), "600d1nf",
                      fp_results=self._fp_results(k=1, n=120),
                      s5_window_result={"status": "INFO", "k": 1, "n": 120}, **self._COMMON_ARGS)
        assert _s5_window_history(tmp_path) == [("600d1nf", 1, 120)]


# ---------------------------------------------------------------------------
# Standing prohibition: three separate lines, never combined into one S5 verdict
# ---------------------------------------------------------------------------

class TestThreeSeparateLinesNeverCombined:
    def test_collect_verdicts_reports_three_distinct_rows_never_pooled(self):
        fp_results = {
            "WSJT-X":   {"n_fp_events": 0, "event_rate": 0.0, "event_rate_ub95": 2.0,
                         "decode_rate": 0.0, "n_slots": 120},
            "OpenWSFZ": {"n_fp_events": 3, "event_rate": 2.5, "event_rate_ub95": 6.334,
                         "decode_rate": 2.5, "n_slots": 120},
        }
        window = list(S5_WINDOW_SEED)
        window[0] = ("today01", 3, 120)
        verdict_w, k, n, used = _verdict_s5_window(window)
        verdict_c, p, (k1, n1), (k0, n0) = _verdict_s5_change(used)
        fragile, deletions = _s5_window_loo(used)
        s5_window_result = {
            "status": "SCORED",
            "window": {"verdict": verdict_w, "k": k, "n": n,
                       "ub": 100.0 * k / n if n else float("nan"), "used": used},
            "change": {"verdict": verdict_c, "p": p, "k1": k1, "n1": n1, "k0": k0, "n0": n0},
            "loo": {"fragile": fragile, "deletions": deletions},
        }
        verdict_rows, overall, fails, notes = _collect_verdicts(
            continuous_results={}, kappa_results={}, fp_results=fp_results,
            bias_results={}, s5_window_result=s5_window_result,
        )
        # Per-sweep Gate A never appears as a gated row (always INFO -> notes).
        assert not any(row[0] == "FP event rate (95% UB), Gate A" for row in verdict_rows)
        assert any("not gated" in n for n in notes)
        # Gate A-W and Gate A-Δ are two SEPARATE rows -- never a single pooled
        # "S5" line, and neither name collides with the other or with Gate A.
        row_names = [row[0] for row in verdict_rows]
        assert "FP event rate (95% UB), Gate A-W" in row_names
        assert "FP event rate change, Gate A-Δ" in row_names
        assert len(set(row_names)) == len(row_names)  # no duplicate row identity
