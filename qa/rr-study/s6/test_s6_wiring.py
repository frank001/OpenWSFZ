"""Wiring tests: the battery label, the corpus default, the S6 series table of the report, and the S6 entry in the registry."""
import os
import sys
from argparse import Namespace
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
sys.path.insert(0, RR)
import assemble_run_report as AR  # noqa: E402
import run_study as RS  # noqa: E402


def test_battery_is_called_s1_s8_only_when_s6_ran():
    default = list(RS._CONTROLLED_SCENARIO_IDS)
    assert "S6" in default and default[-1] == "S6" and default[-2] == "S3c"            # S6 after the existing scenarios, S3c stays before it
    assert RS._battery_label(default) == "S1-S8"
    no_s6 = [s for s in default if s != "S6"]
    assert RS._battery_label(no_s6).startswith("scenarios run: S1, S1b") and "S6" not in RS._battery_label(no_s6)
    assert RS._battery_label(["S6"]) == "scenarios run: S6"


def test_s6_is_registered_and_its_frozen_list_exists():
    assert RS._SCENARIO_REGISTRY["S6"].name == "s6-wavlist.json" and RS._SCENARIO_REGISTRY["S6"].is_file()


def test_corpus_and_scratch_defaults(tmp_path):
    a = Namespace(s6_corpus=None, s6_scratch=None)
    assert str(RS._s6_corpus(a)).endswith("rr-s6-refset-corpus")
    assert RS._s6_corpus(Namespace(s6_corpus=str(tmp_path), s6_scratch=None)) == tmp_path
    sc = RS._s6_scratch(a, Path("results/2026-10-14-abc1234"))
    assert sc.name == "s6-2026-10-14-abc1234" and "qa-scratch" in str(sc) and "OpenWSFZ" not in str(sc).replace("worktrees", "")


def test_s6_series_table_is_carried_and_extended():
    prior = ("## Section 6\n\nintro\n\n| run | x |\n|---|---|\n| 2026-10-11 | a |\n\n"
             + AR.S6_SERIES_HEAD + "\n| S6 | VALID | tier standard | first row | 61.0 % positive agreement |\n\nfootnote 1\n")
    rest, tbl = AR.s6_series(prior, "| S6 | VALID | tier standard | second row | 63.0 % positive agreement |\n")
    assert "S6 series" not in rest and "footnote 1" in rest and "| 2026-10-11 | a |" in rest
    assert tbl.count("| S6 | VALID") == 2 and tbl.index("first row") < tbl.index("second row")
    rest2, tbl2 = AR.s6_series("## Section 6\n\n| run | x |\n", None)           # no S6 ever: nothing is invented
    assert tbl2 == "" and "S6" not in rest2
    _, tbl3 = AR.s6_series("## Section 6\n\n| run | x |\n", "| S6 | VALID | tier quick | first | n/a |")
    assert tbl3.startswith("### S6 series") and tbl3.count("\n| S6 | VALID") == 1
