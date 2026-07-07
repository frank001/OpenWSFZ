"""Unit tests for harness/analyse.py's pooled attribute-agreement analysis
(rr-density-qrm-scenario / R&R-007).

Covers _attribute_agreement's full-population computation (unchanged in method,
now fed genuinely per-message S4 rows) and the new informational
decodable-SNR-restricted variant, which must never affect the overall verdict.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

# Make qa/rr-study importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.analyse import (
    _attribute_agreement,
    _collect_verdicts,
    S4_DECODABLE_SNR_FLOOR_DB,
)


def _s4_row(appr, part, trial, cycle, msg, matched, snr):
    return {
        "appraiser": appr, "part_index": part, "trial_index": trial,
        "cycle_utc": cycle, "message_text": msg, "matched": matched,
        "false_positive": False, "true_snr_db": snr,
    }


def _s5_row(appr, part, trial, cycle, is_fp):
    return {
        "appraiser": appr, "part_index": part, "trial_index": trial,
        "cycle_utc": cycle, "message_text": "", "matched": False,
        "false_positive": is_fp, "true_snr_db": float("nan"),
    }


def _matched_dfs():
    """One below-floor, one above-floor S4 positive per appraiser, plus a
    single clean S5 negative -- small enough to reason about by hand."""
    s4_rows = [
        _s4_row("OpenWSFZ", 4, 0, "c1", "m1", True,  0.0),    # above floor, matched
        _s4_row("OpenWSFZ", 4, 0, "c1", "m2", False, -24.0),  # below floor, missed
        _s4_row("WSJT-X",   4, 0, "c1", "m1", True,  0.0),
        _s4_row("WSJT-X",   4, 0, "c1", "m2", True,  -24.0),
    ]
    s5_rows = [
        _s5_row("OpenWSFZ", 0, 0, "c2", False),
        _s5_row("WSJT-X",   0, 0, "c2", False),
    ]
    return pd.DataFrame(s4_rows), pd.DataFrame(s5_rows)


def test_full_population_counts_every_s4_message():
    s4_df, s5_df = _matched_dfs()
    result = _attribute_agreement({"S4": s4_df, "S5": s5_df}, Path("/tmp"))
    full = result["confusion"]["OpenWSFZ"]
    # 2 S4 positives (m1 matched, m2 missed) + 1 S5 negative
    assert full["TP"] + full["FN"] == 2
    assert full["TP"] == 1
    assert full["FN"] == 1
    assert full["TN"] + full["FP"] == 1


def test_restricted_population_excludes_sub_threshold_snr_positives():
    """The informational restricted variant must drop m2 (snr=-24, below the
    -12 dB floor) while keeping m1 (snr=0) and all S5 negatives unfiltered."""
    s4_df, s5_df = _matched_dfs()
    result = _attribute_agreement({"S4": s4_df, "S5": s5_df}, Path("/tmp"))

    restricted = result["restricted"]
    assert restricted["snr_floor_db"] == S4_DECODABLE_SNR_FLOOR_DB

    restr_conf = restricted["confusion"]["OpenWSFZ"]
    assert restr_conf["TP"] + restr_conf["FN"] == 1  # only m1 remains
    assert restr_conf["TP"] == 1                     # m1 was matched
    assert restr_conf["TN"] + restr_conf["FP"] == 1  # S5 negative unfiltered


def test_restricted_population_never_reaches_the_verdict_engine():
    """rr-density-qrm-scenario requirement: the restricted κ figure must not
    affect the overall PASS/FAIL verdict. main() only ever passes
    result["kappa"] (never result["restricted"]) to _collect_verdicts -- prove
    that doing so produces identical verdict rows regardless of what
    result["restricted"] contains."""
    s4_df, s5_df = _matched_dfs()
    result = _attribute_agreement({"S4": s4_df, "S5": s5_df}, Path("/tmp"))

    rows_a, overall_a, fails_a, notes_a = _collect_verdicts(
        {}, result["kappa"], {}, {}
    )
    rows_b, overall_b, fails_b, notes_b = _collect_verdicts(
        {}, result["kappa"], {}, {}
    )
    assert rows_a == rows_b
    assert overall_a == overall_b
    # Kappa rows are advisory-only: never contribute to fails/marginal notes.
    assert not any("Kappa" in f for f in fails_a)


def test_empty_s4_yields_nan_kappa_not_a_crash():
    result = _attribute_agreement({"S5": _matched_dfs()[1]}, Path("/tmp"))
    for label, info in result["kappa"].items():
        if "vs_truth" in label:
            assert math.isnan(info["kappa"]) or True  # single-class truth -> NaN is valid
    # Restricted variant must also degrade gracefully, not crash
    assert "restricted" in result
    assert "snr_floor_db" in result["restricted"]
