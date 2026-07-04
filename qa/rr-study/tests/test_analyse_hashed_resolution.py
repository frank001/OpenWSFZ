"""Unit tests for harness/analyse.py's _analyse_hashed_callsign_resolution
(rr-linked-cycle-effectiveness-scenario, task 3.4).

Builds a small synthetic run directory (truth.csv pair rows + two ALL.TXT
logs, Format A per harness/common.py) rather than driving a live run, so
these tests are independent of any live-rig time.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.analyse import (
    APPRAISERS,
    _analyse_hashed_callsign_resolution,
    _hcr_load_pair_truth,
)
from harness.run_scenario import _TRUTH_COLUMNS, UNRESOLVED_CALLSIGN_PLACEHOLDER

SCEN_ID = "S9"
ANNOUNCE_TEXT = "CQ Q0ABCDEF"
REFERENCE_TEXT = "Q1TST Q0ABCDEF RR73"
CALLSIGN = "Q0ABCDEF"
PLACEHOLDER_TEXT = REFERENCE_TEXT.replace(CALLSIGN, UNRESOLVED_CALLSIGN_PLACEHOLDER)
# The REAL shape a resolved reference decodes to (confirmed 2026-07-04 against a
# live-rig S9 run and the recovered ft8_lib reference source: message.c's
# lookup_callsign() calls add_brackets() for EVERY hash-lookup result, resolved
# or not — only the placeholder vs. the real callsign differs inside the
# brackets). Both WSJT-X and OpenWSFZ decoded "Q1TST <Q0ABCDEF> RR73" on the
# live run, never the bare form. The bare REFERENCE_TEXT above is kept only as
# a defensive fallback match in _analyse_hashed_callsign_resolution, not the
# expected shape.
RESOLVED_BRACKETED_TEXT = REFERENCE_TEXT.replace(CALLSIGN, f"<{CALLSIGN}>")


def _write_truth_csv(run_dir: Path, rows: list[dict]) -> None:
    truth_path = run_dir / "truth.csv"
    with open(truth_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TRUTH_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _pair_truth_row(pair_index: int, trial_index: int,
                    announce_cycle: str, reference_cycle: str) -> dict:
    return {
        "scenario_id": SCEN_ID,
        "part_index": pair_index,
        "trial_index": trial_index,
        "seed": 1,
        "true_snr_db": "",
        "true_dt_s": "",
        "true_freq_hz": "",
        "message_text": f"{ANNOUNCE_TEXT}; {REFERENCE_TEXT}",
        "cycle_utc": announce_cycle,
        "gap_cycles": 1,
        "resolved_expected": True,
        "announce_text": ANNOUNCE_TEXT,
        "announce_freq_hz": 1500.0,
        "announce_snr_db": 0.0,
        "announce_cycle_utc": announce_cycle,
        "reference_text": REFERENCE_TEXT,
        "reference_freq_hz": 1500.0,
        "reference_snr_db": 0.0,
        "reference_cycle_utc": reference_cycle,
        "resolved_callsign": CALLSIGN,
        "unresolved_placeholder": UNRESOLVED_CALLSIGN_PLACEHOLDER,
    }


def _all_txt_line(cycle_utc: str, freq_hz: int, message: str) -> str:
    # Format A (harness/common.py): 8-digit date, "UTC", freqHz, dt, snr, mode, message.
    ts = cycle_utc.replace("-", "").replace(":", "").replace("T", "_").rstrip("Z")
    return f"{ts}   UTC  {freq_hz}  0.1  -10  FT8  {message}"


class TestHashedCallsignResolutionAnalysis:
    def test_resolved_and_placeholder_are_distinguished(self, tmp_path: Path):
        """WSJT-X resolves the callsign; OpenWSFZ shows the unresolved placeholder."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        ann_cycle = "2026-07-04T13:00:00Z"
        ref_cycle = "2026-07-04T13:00:15Z"
        _write_truth_csv(run_dir, [_pair_truth_row(0, 0, ann_cycle, ref_cycle)])

        (run_dir / "wsjt-all.txt").write_text(
            _all_txt_line(ann_cycle, 1500, ANNOUNCE_TEXT) + "\n"
            + _all_txt_line(ref_cycle, 1500, REFERENCE_TEXT) + "\n",
            encoding="utf-8",
        )
        (run_dir / "owsfz-all.txt").write_text(
            _all_txt_line(ann_cycle, 1500, ANNOUNCE_TEXT) + "\n"
            + _all_txt_line(ref_cycle, 1500, PLACEHOLDER_TEXT) + "\n",
            encoding="utf-8",
        )

        results = _analyse_hashed_callsign_resolution(run_dir, SCEN_ID)
        assert results is not None

        wsjt = results["rates"]["WSJT-X"]
        assert wsjt["n_pairs"] == 1
        assert wsjt["n_announce_decoded"] == 1
        assert wsjt["n_resolved"] == 1
        assert wsjt["resolution_rate"] == pytest.approx(100.0)

        owsfz = results["rates"]["OpenWSFZ"]
        assert owsfz["n_announce_decoded"] == 1
        assert owsfz["n_resolved"] == 0
        assert owsfz["n_placeholder"] == 1
        assert owsfz["resolution_rate"] == pytest.approx(0.0)
        assert owsfz["placeholder_rate"] == pytest.approx(100.0)

        assert results["per_pair"][0]["WSJT-X"] == "resolved"
        assert results["per_pair"][0]["OpenWSFZ"] == "not_resolved_placeholder"

    def test_bracketed_resolved_form_is_recognised(self, tmp_path: Path):
        """Regression test for the 2026-07-04 live-rig finding: a genuinely
        resolved reference decodes as "<CALLSIGN>" (angle-bracketed), NOT bare
        "CALLSIGN" — both WSJT-X and OpenWSFZ produced this real shape on an
        actual VB-CABLE run of S9, and the analyser originally scored 0/10
        resolved (misclassified as reference_not_decoded) before this was
        fixed, because it only matched the bare form. ft8_lib's own
        lookup_callsign()/add_brackets() confirm this is the correct,
        ratified-reference shape, not an app-side bug."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        ann_cycle = "2026-07-04T13:00:00Z"
        ref_cycle = "2026-07-04T13:00:15Z"
        _write_truth_csv(run_dir, [_pair_truth_row(0, 0, ann_cycle, ref_cycle)])

        for appr_file in ("wsjt-all.txt", "owsfz-all.txt"):
            (run_dir / appr_file).write_text(
                _all_txt_line(ann_cycle, 1500, ANNOUNCE_TEXT) + "\n"
                + _all_txt_line(ref_cycle, 1500, RESOLVED_BRACKETED_TEXT) + "\n",
                encoding="utf-8",
            )

        results = _analyse_hashed_callsign_resolution(run_dir, SCEN_ID)
        assert results is not None
        for appr in APPRAISERS:
            r = results["rates"][appr]
            assert r["n_resolved"] == 1
            assert r["resolution_rate"] == pytest.approx(100.0)
            assert results["per_pair"][0][appr] == "resolved"

    def test_announce_not_decoded_excluded_from_resolution_denominator(self, tmp_path: Path):
        """Spec: resolution rate's denominator excludes pairs where the
        announcement was never decoded — it must not be conflated with a
        low resolution rate (D1/D3)."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        ann_cycle = "2026-07-04T13:00:00Z"
        ref_cycle = "2026-07-04T13:00:15Z"
        _write_truth_csv(run_dir, [_pair_truth_row(0, 0, ann_cycle, ref_cycle)])

        # Neither appraiser decodes the announce cycle at all.
        (run_dir / "wsjt-all.txt").write_text("", encoding="utf-8")
        (run_dir / "owsfz-all.txt").write_text("", encoding="utf-8")

        results = _analyse_hashed_callsign_resolution(run_dir, SCEN_ID)
        assert results is not None
        for appr in APPRAISERS:
            r = results["rates"][appr]
            assert r["n_announce_decoded"] == 0
            assert r["announce_decode_rate"] == pytest.approx(0.0)
            # resolution_rate is NaN (undefined), not 0% — must not be
            # conflated with "decoded but didn't resolve".
            assert r["resolution_rate"] != r["resolution_rate"] or r["n_announce_decoded"] == 0
            assert results["per_pair"][0][appr] == "announce_not_decoded"

    def test_reference_not_decoded_is_distinguished_from_placeholder(self, tmp_path: Path):
        """A reference cycle that decodes nothing at all (vs. a decoded
        placeholder text) must be its own distinguishable outcome."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        ann_cycle = "2026-07-04T13:00:00Z"
        ref_cycle = "2026-07-04T13:00:15Z"
        _write_truth_csv(run_dir, [_pair_truth_row(0, 0, ann_cycle, ref_cycle)])

        # Announce decodes; reference cycle decodes nothing at all.
        for appr_file in ("wsjt-all.txt", "owsfz-all.txt"):
            (run_dir / appr_file).write_text(
                _all_txt_line(ann_cycle, 1500, ANNOUNCE_TEXT) + "\n",
                encoding="utf-8",
            )

        results = _analyse_hashed_callsign_resolution(run_dir, SCEN_ID)
        assert results is not None
        for appr in APPRAISERS:
            r = results["rates"][appr]
            assert r["n_announce_decoded"] == 1
            assert r["n_resolved"] == 0
            assert r["n_placeholder"] == 0
            assert r["n_not_decoded"] == 1
            assert r["not_decoded_rate"] == pytest.approx(100.0)
            assert results["per_pair"][0][appr] == "reference_not_decoded"

    def test_no_pair_truth_rows_returns_none(self, tmp_path: Path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "truth.csv").write_text(
            ",".join(_TRUTH_COLUMNS) + "\n", encoding="utf-8"
        )
        assert _analyse_hashed_callsign_resolution(run_dir, SCEN_ID) is None

    def test_missing_all_txt_returns_none(self, tmp_path: Path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_truth_csv(run_dir, [_pair_truth_row(0, 0, "2026-07-04T13:00:00Z",
                                                    "2026-07-04T13:00:15Z")])
        # No wsjt-all.txt / owsfz-all.txt written.
        assert _analyse_hashed_callsign_resolution(run_dir, SCEN_ID) is None

    def test_hcr_load_pair_truth_filters_by_scenario_and_flag(self, tmp_path: Path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        pair_row = _pair_truth_row(0, 0, "2026-07-04T13:00:00Z", "2026-07-04T13:00:15Z")
        non_pair_row = {col: "" for col in _TRUTH_COLUMNS}
        non_pair_row.update({
            "scenario_id": "S1", "part_index": 0, "trial_index": 0, "seed": 1,
            "true_snr_db": -10.0, "true_dt_s": 0.0, "true_freq_hz": 1500.0,
            "message_text": "CQ Q1ABC FN42", "cycle_utc": "2026-07-04T13:00:00Z",
            "resolved_expected": "",
        })
        _write_truth_csv(run_dir, [pair_row, non_pair_row])

        rows = _hcr_load_pair_truth(run_dir, SCEN_ID)
        assert len(rows) == 1
        assert rows[0]["scenario_id"] == SCEN_ID
