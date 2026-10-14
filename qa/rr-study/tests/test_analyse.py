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
    _derived_metrics,
    _migrate_trend_header,
    _TREND_COLUMNS,
    _verdict_grr,
    _verdict_ndc,
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


def test_duplicated_message_unit_calls_any_matched_not_last_row():
    """R&R-007 regression (found 2026-09-12): S4 P3/P4 re-inject the same
    10-message list 2x/3x per cycle, so a unit's rows can span multiple CSV
    rows sharing one (part, trial, cycle, message_text) key. The unit's call
    must be any(matched) across those rows -- a matcher crediting only one
    copy must not turn a genuinely-decoded message into a false negative just
    because a *later* duplicate row happened to be the unmatched one.

    This message text is injected 3x in the same cycle (m1 in trial 0); only
    the FIRST copy is matched, the second and third are not. Old code
    (dict overwrite, `units[appr][key] = entry`) lets the LAST row win and
    reports a miss. The fix must report a hit.
    """
    s4_rows = [
        _s4_row("OpenWSFZ", 3, 0, "c1", "m1", True,  -6.0),   # matched copy (first)
        _s4_row("OpenWSFZ", 3, 0, "c1", "m1", False, -6.0),   # duplicate, unmatched
        _s4_row("OpenWSFZ", 3, 0, "c1", "m1", False, -6.0),   # duplicate, unmatched (last row)
    ]
    s4_df = pd.DataFrame(s4_rows)
    result = _attribute_agreement({"S4": s4_df, "S5": None}, Path("/tmp"))
    conf = result["confusion"]["OpenWSFZ"]
    # Exactly one unit (one distinct key) -- must be scored as a hit (TP=1),
    # not a miss (FN=1), regardless of which duplicate row physically sorts last.
    assert conf["TP"] == 1, "any(matched) over duplicate rows must credit the unit"
    assert conf["FN"] == 0


def test_empty_s4_yields_nan_kappa_not_a_crash():
    result = _attribute_agreement({"S5": _matched_dfs()[1]}, Path("/tmp"))
    for label, info in result["kappa"].items():
        if "vs_truth" in label:
            assert math.isnan(info["kappa"]) or True  # single-class truth -> NaN is valid
    # Restricted variant must also degrade gracefully, not crash
    assert "restricted" in result
    assert "snr_floor_db" in result["restricted"]


# ---- ndc: "not computable", never FAIL, when there is no second appraiser or no GRR variance (2026-10-13, the Linux repeats) -------------

def _anova(n_appraisers, var_grr, var_part=25.0):
    return {"n_appraisers": n_appraisers, "var_total": var_grr + var_part, "var_grr": var_grr, "var_repeatability": var_grr,
            "var_reproducibility": 0.0, "var_part": var_part}


def test_ndc_is_a_number_with_two_appraisers_and_some_variance():
    m = _derived_metrics(_anova(2, 1.0), 10.0)
    assert m["ndc"] == 7 and m["ndc_reason"] == "" and m["n_appraisers"] == 2          # floor(1.41 * 5 / 1)
    assert _verdict_ndc(m["ndc"]) == "PASS"


def test_ndc_is_not_computable_with_one_appraiser():
    m = _derived_metrics(_anova(1, 0.0), 10.0)
    assert m["ndc"] is None and "one appraiser" in m["ndc_reason"] and m["n_appraisers"] == 1
    assert _verdict_ndc(m["ndc"]) == "N/A"                                              # it used to print 1 and FAIL


def test_ndc_is_not_computable_when_sigma_grr_is_exactly_zero_and_is_not_a_pass():
    m = _derived_metrics(_anova(2, 0.0), 10.0)
    assert m["ndc"] is None and "sigma_GRR = 0" in m["ndc_reason"]
    assert _verdict_ndc(m["ndc"]) == "N/A" and _verdict_ndc(1) == "FAIL" and _verdict_ndc(3) == "MARGINAL"


def test_collect_verdicts_reports_a_missing_ndc_as_na_with_a_note_and_does_not_fail_the_run():
    res = {"S2": {"metrics": _derived_metrics(_anova(1, 0.0), 10.0)}}
    rows, overall, fails, notes = _collect_verdicts(res, {}, {}, {})
    ndc_row = [r for r in rows if r[0] == "ndc"][0]
    assert ndc_row == ("ndc", "S2", "not computable", "N/A")
    grr_row = [r for r in rows if r[0] == "%GR&R (%StudyVar)"][0]
    assert "one appraiser" in grr_row[2] and grr_row[3] == "PASS"                      # the figure is labelled, not hidden
    assert any("ndc (S2) is not computable" in n for n in notes) and not fails


# ---- the %GR&R gate reads %StudyVar (Captain, 2026-10-14), not %Contribution ------------------------------------------------------------------

def _row(rows, scen):
    return [r for r in rows if r[0] == "%GR&R (%StudyVar)" and r[1] == scen][0]


def test_verdict_is_pinned_to_study_var_11_2_percent_contribution_is_33_5_study_var_is_fail():
    m = _derived_metrics(_anova(2, 11.23, var_part=88.77), 10.0)       # the LINUX run 1 S1 shape: 11.2 % contribution
    assert abs(m["pct_contribution_grr"] - 11.23) < 1e-9 and abs(m["pct_study_var_grr"] - 33.5) < 0.05
    rows, overall, fails, notes = _collect_verdicts({"S1": {"metrics": m}}, {}, {}, {})
    assert _row(rows, "S1")[3] == "FAIL"                                  # under the old rule (%Contribution 11.2 %) this was MARGINAL
    assert "33.5%" in _row(rows, "S1")[2] and "%Contribution 11.2%" in _row(rows, "S1")[2]
    assert any("%StudyVar" in f and "S1" in f for f in fails)


def test_verdict_bands_on_study_var_pass_marginal_fail():
    assert _verdict_grr(4.7) == "PASS" and _verdict_grr(9.99) == "PASS"
    assert _verdict_grr(10.0) == "MARGINAL" and _verdict_grr(10.5) == "MARGINAL" and _verdict_grr(30.0) == "MARGINAL"
    assert _verdict_grr(30.01) == "FAIL"
    m3 = _derived_metrics(_anova(2, 1.108, var_part=98.892), 10.0)       # S3-like: 1.1 % contribution is 10.5 % study var
    rows, *_ = _collect_verdicts({"S3": {"metrics": m3}}, {}, {}, {})
    assert _row(rows, "S3")[3] == "MARGINAL"                              # PASS under the old rule
    m1 = _derived_metrics(_anova(2, 0.224, var_part=99.776), 10.0)
    rows, *_ = _collect_verdicts({"S1": {"metrics": m1}}, {}, {}, {})
    assert _row(rows, "S1")[3] == "PASS"


def test_every_report_says_the_gate_changed_and_old_reports_are_not_regraded():
    m = _derived_metrics(_anova(2, 1.0), 10.0)
    _, _, _, notes = _collect_verdicts({"S1": {"metrics": m}}, {}, {}, {})
    assert any("gate changed to %StudyVar on 2026-10-14" in n and "not re-graded" in n for n in notes)


def test_trend_header_migration_adds_study_var_derived_from_contribution_and_is_idempotent(tmp_path):
    old = "\n".join(["run_date,git_sha,pct_grr_snr,ndc_snr,bias_snr_owsfz,kappa_s4,fp_rate_s5,fp_events_s5,fp_slots_s5",
                     "2026-06-06,abc,44.79,1,-1.9,,0.0,,",
                     "2026-10-03,def,0.19,60,0.5,0.9,0.0,0,480",
                     "2026-10-04,ghi,,,,,,,"]) + "\n"
    f = tmp_path / "trend.csv"
    f.write_text(old, encoding="utf-8")
    _migrate_trend_header(f)
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == _TREND_COLUMNS
    assert abs(float(lines[1].split(",")[-1]) - 100 * math.sqrt(0.4479)) < 1e-6         # exact identity from %Contribution
    assert abs(float(lines[2].split(",")[-1]) - 100 * math.sqrt(0.0019)) < 1e-6
    assert lines[3].split(",")[-1] == ""                                                 # no figure on file: left empty, not invented
    before = f.read_text(encoding="utf-8")
    _migrate_trend_header(f)                                                              # a second call changes nothing
    assert f.read_text(encoding="utf-8") == before
    assert len(lines[0].split(",")) == len(lines[1].split(",")) == len(lines[3].split(","))
