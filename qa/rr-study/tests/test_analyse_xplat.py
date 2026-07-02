"""Unit tests for harness/analyse_xplat.py — three-appraiser extension.

Tests:
  1. 3-appraiser ANOVA path: all three pairs returned by _platform_bias_metrics_all
  2. Graceful degradation: WSJT-X rows absent → NaN pairs, no crash
  3. McNemar generalisation: returns {(A,B): ...} for all pairs
  4. Fisher FP parity generalisation: returns {(A,B): ...} for all pairs
  5. _attribute_agreement pairwise kappa: 3 vs-truth + 3 between-appraiser entries
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

# Make qa/rr-study importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.analyse_xplat import (
    APPRAISERS,
    _platform_bias_metrics_all,
    _mcnemar_test,
    _fp_parity_fisher,
    _attribute_agreement,
    _analyse_compounding,
    _decode_rate_report_lines,
    _compounding_report_lines,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_matched_df(
    appraisers: list[str],
    n_parts: int = 3,
    n_trials: int = 5,
    snr_offsets: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Return a synthetic matched DataFrame with continuous SNR data.

    Each (part, trial) cell is replicated for every appraiser. Optional
    *snr_offsets* lets callers introduce a systematic bias per appraiser
    so that _platform_bias_metrics_all returns non-NaN biases.
    """
    snr_offsets = snr_offsets or {}
    rows = []
    base_snr = -10.0
    cycle0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    for appr in appraisers:
        offset = snr_offsets.get(appr, 0.0)
        for part in range(n_parts):
            true_snr = base_snr + part * 3.0
            for trial in range(n_trials):
                rows.append({
                    "scenario_id":      "S1",
                    "part_index":       part,
                    "trial_index":      trial,
                    "appraiser":        appr,
                    "matched":          True,
                    "false_positive":   False,
                    "message_text":     "CQ Q1TEST FN42",
                    "true_snr_db":      true_snr,
                    "true_dt_s":        0.0,
                    "true_freq_hz":     1500.0,
                    "reported_snr_db":  true_snr + offset,
                    "reported_dt_s":    0.05 * (appraisers.index(appr) + 1),
                    "reported_freq_hz": 1500.0,
                    "cycle_utc":        cycle0.isoformat(),
                    "seed":             42,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Three-appraiser bias metrics — all pairs populated
# ---------------------------------------------------------------------------

class TestPlatformBiasMetricsAll:
    def test_all_three_pairs_returned(self):
        """_platform_bias_metrics_all returns N*(N-1)/2 = 3 pairs for 3 appraisers."""
        df = _make_matched_df(["Windows", "Linux", "WSJT-X"],
                              snr_offsets={"Linux": 0.5, "WSJT-X": -0.3})
        result = _platform_bias_metrics_all(df, "reported_snr_db")
        assert len(result) == 3
        expected_pairs = {
            ("Windows", "Linux"),
            ("Windows", "WSJT-X"),
            ("Linux",   "WSJT-X"),
        }
        assert set(result.keys()) == expected_pairs

    def test_bias_values_are_finite(self):
        """All three pairs have finite mean_bias when all appraisers are present."""
        df = _make_matched_df(["Windows", "Linux", "WSJT-X"],
                              snr_offsets={"Linux": 1.0, "WSJT-X": 2.0})
        result = _platform_bias_metrics_all(df, "reported_snr_db")
        for pair, metrics in result.items():
            assert not math.isnan(metrics["mean_bias"]), (
                f"Expected finite mean_bias for pair {pair}"
            )

    def test_bias_direction_correct(self):
        """Bias = B − A, so (Windows, Linux) should equal Linux_offset − Windows_offset."""
        df = _make_matched_df(["Windows", "Linux", "WSJT-X"],
                              snr_offsets={"Linux": 1.0, "WSJT-X": 2.0})
        result = _platform_bias_metrics_all(df, "reported_snr_db")
        assert abs(result[("Windows", "Linux")]["mean_bias"] - 1.0) < 0.01
        assert abs(result[("Windows", "WSJT-X")]["mean_bias"] - 2.0) < 0.01
        assert abs(result[("Linux",   "WSJT-X")]["mean_bias"] - 1.0) < 0.01


# ---------------------------------------------------------------------------
# 2. Graceful degradation — WSJT-X absent
# ---------------------------------------------------------------------------

class TestGracefulDegradationWithoutWsjtX:
    def test_two_appraiser_bias_finite(self):
        """When WSJT-X rows are absent, Windows/Linux pair still has finite bias."""
        df = _make_matched_df(["Windows", "Linux"],
                              snr_offsets={"Linux": 0.8})
        result = _platform_bias_metrics_all(df, "reported_snr_db",
                                            appraisers=("Windows", "Linux", "WSJT-X"))
        assert not math.isnan(result[("Windows", "Linux")]["mean_bias"])

    def test_wsjt_pairs_are_nan_when_absent(self):
        """Pairs involving WSJT-X return NaN when WSJT-X is absent from data."""
        df = _make_matched_df(["Windows", "Linux"],
                              snr_offsets={"Linux": 0.8})
        result = _platform_bias_metrics_all(df, "reported_snr_db",
                                            appraisers=("Windows", "Linux", "WSJT-X"))
        assert math.isnan(result[("Windows", "WSJT-X")]["mean_bias"])
        assert math.isnan(result[("Linux",   "WSJT-X")]["mean_bias"])

    def test_mcnemar_two_appraiser_no_crash(self):
        """_mcnemar_test runs without error when WSJT-X rows are absent."""
        df = _make_matched_df(["Windows", "Linux"])
        result = _mcnemar_test({"S1": df}, appraisers=("Windows", "Linux", "WSJT-X"))
        # Should still have 3 pair keys
        assert len(result) == 3
        # WSJT-X pairs have 0 discordant observations — valid PASS
        assert result[("Windows", "WSJT-X")]["verdict"] in ("PASS", "—")
        assert result[("Linux",   "WSJT-X")]["verdict"] in ("PASS", "—")

    def test_fp_parity_fisher_wsjt_absent_is_nan(self):
        """Fisher FP parity returns NaN p-value for WSJT-X pairs when absent."""
        fp_results = {
            "Windows": {"n_fp_events": 0, "n_slots": 50},
            "Linux":   {"n_fp_events": 1, "n_slots": 50},
            # WSJT-X absent
        }
        result = _fp_parity_fisher(fp_results, appraisers=("Windows", "Linux", "WSJT-X"))
        assert math.isnan(result[("Windows", "WSJT-X")]["p_value"])
        assert math.isnan(result[("Linux",   "WSJT-X")]["p_value"])

    def test_fp_parity_fisher_two_pair_is_finite(self):
        """Fisher FP parity for the Windows/Linux pair is finite when both have data."""
        fp_results = {
            "Windows": {"n_fp_events": 0, "n_slots": 50},
            "Linux":   {"n_fp_events": 1, "n_slots": 50},
        }
        result = _fp_parity_fisher(fp_results, appraisers=("Windows", "Linux", "WSJT-X"))
        assert not math.isnan(result[("Windows", "Linux")]["p_value"])


# ---------------------------------------------------------------------------
# 3. McNemar generalisation
# ---------------------------------------------------------------------------

class TestMcNemarGeneralisation:
    def test_returns_all_three_pairs(self):
        """_mcnemar_test returns 3 pair keys for 3 appraisers."""
        df = _make_matched_df(["Windows", "Linux", "WSJT-X"])
        result = _mcnemar_test({"S1": df})
        assert len(result) == 3

    def test_zero_discordants_gives_pass(self):
        """Identical decision sets → n_ab=0, n_ba=0 → PASS (or valid p-value path)."""
        df = _make_matched_df(["Windows", "Linux", "WSJT-X"])
        result = _mcnemar_test({"S1": df})
        for pair, mc in result.items():
            # All matched == True for all appraisers → 0 discordants
            assert mc["n_ab"] == 0 and mc["n_ba"] == 0
            assert mc["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# 4. Attribute agreement — pairwise kappas
# ---------------------------------------------------------------------------

class TestAttributeAgreementPairwiseKappa:
    def _make_s4_df(self, appraisers: list[str]) -> pd.DataFrame:
        """Synthetic S4 (positive only) dataframe."""
        rows = []
        for appr in appraisers:
            for part in range(2):
                for trial in range(4):
                    rows.append({
                        "scenario_id":    "S4",
                        "part_index":     part,
                        "trial_index":    trial,
                        "appraiser":      appr,
                        "matched":        True,
                        "false_positive": False,
                        "message_text":   "CQ Q2TEST FN43",
                        "cycle_utc":      f"2026-06-01T12:0{trial}:00+00:00",
                        "true_snr_db":    -5.0,
                        "true_freq_hz":   1500.0,
                    })
        return pd.DataFrame(rows)

    def test_three_vs_truth_entries(self):
        """3 appraisers → 3 *_vs_truth kappa entries."""
        df = self._make_s4_df(["Windows", "Linux", "WSJT-X"])
        result = _attribute_agreement({"S4": df}, Path("/tmp"))
        vs_truth = [k for k in result["kappa"] if "_vs_truth" in k]
        assert len(vs_truth) == 3

    def test_three_between_appraiser_entries(self):
        """3 appraisers → 3 between-appraiser kappa entries."""
        df = self._make_s4_df(["Windows", "Linux", "WSJT-X"])
        result = _attribute_agreement({"S4": df}, Path("/tmp"))
        between = [k for k in result["kappa"] if "_vs_truth" not in k]
        assert len(between) == 3

    def test_two_appraiser_fallback(self):
        """When WSJT-X absent, WSJT-X kappa entries are NaN (not missing/crash)."""
        df = self._make_s4_df(["Windows", "Linux"])
        result = _attribute_agreement({"S4": df}, Path("/tmp"))
        wsjt_entry = result["kappa"].get("Windows_vs_WSJT-X")
        assert wsjt_entry is not None, "Windows_vs_WSJT-X kappa entry must exist"
        assert math.isnan(wsjt_entry["kappa"])


# ---------------------------------------------------------------------------
# 5. Compounding / decode-rate report lines — dynamic columns
# ---------------------------------------------------------------------------

class TestDynamicColumnReports:
    def test_decode_rate_report_omits_absent_appraisers(self):
        """_decode_rate_report_lines omits appraisers with no data."""
        results = {
            "scenario_id": "S1b",
            "part_label": "True SNR (dB)",
            "per_part": [
                {"part_index": 0, "part_val": -15.0,
                 "Windows_decoded": 5, "Windows_total": 5, "Windows_rate": 100.0,
                 "Linux_decoded":   4, "Linux_total":   5, "Linux_rate":   80.0,
                 "WSJT-X_decoded":  0, "WSJT-X_total":  0, "WSJT-X_rate":  float("nan")},
            ],
            "overall": {"Windows": 100.0, "Linux": 80.0, "WSJT-X": float("nan")},
            "chart": None,
        }
        lines = _decode_rate_report_lines(results)
        joined = "\n".join(lines)
        assert "Windows" in joined
        assert "Linux" in joined
        # WSJT-X has 0 total → should be excluded from header
        assert "WSJT-X" not in joined

    def test_compounding_report_dynamic_columns(self):
        """_compounding_report_lines renders correct column count for 3 appraisers."""
        results = {
            "overall":       {"Windows": 80.0, "Linux": 75.0, "WSJT-X": 70.0},
            "by_type":       {"none": {"Windows": 80.0, "Linux": 75.0, "WSJT-X": 70.0}},
            "per_part":      [{"part_index": 0, "overlap_type": "none", "label": "",
                               "Windows": (8, 10), "Linux": (7, 10), "WSJT-X": (6, 10)}],
            "capture":       {},
            "between_app":   {"Windows vs Linux": 90.0, "Windows vs WSJT-X": 85.0,
                              "Linux vs WSJT-X": 88.0},
            "chart":         None,
            "appraisers_in": ["Windows", "Linux", "WSJT-X"],
        }
        lines = _compounding_report_lines(results)
        joined = "\n".join(lines)
        assert "Windows" in joined
        assert "Linux"   in joined
        assert "WSJT-X"  in joined
        # Three between-appraiser agreement lines
        assert "Windows vs Linux"   in joined
        assert "Windows vs WSJT-X"  in joined
        assert "Linux vs WSJT-X"    in joined
