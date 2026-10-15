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


# ---- sequential S6 driver (Captain 2026-10-15) ------------------------------------------------------------------------------------------------

class _R:
    def __init__(self, rc):
        self.returncode = rc


def _drive(monkeypatch, tmp_path, phase_rc=None, play_rc=None, stall_on_first_play=False, merge_rc=0):
    calls = []
    phase_rc, play_rc = phase_rc or {}, play_rc or {}
    stall = {"reading": None}

    def fake_phase(cmd, phase, timeout_s=900, run_dir=None):
        calls.append(("phase", phase))
        return phase_rc.get(phase, 0)

    def fake_py(*a, check=True):
        who = a[a.index("--appraiser") + 1] if "--appraiser" in a else None
        calls.append(("py", a[0], who))
        if who == "wsjtx" and stall_on_first_play:
            stall["reading"] = object()
            return _R(-15)
        return _R(merge_rc if a[0].endswith("s6_merge.py") else play_rc.get(who, 0))

    monkeypatch.setattr(RS, "_s6_phase", fake_phase)
    monkeypatch.setattr(RS, "_py", fake_py)
    stopped = []
    args = Namespace(s6_tier="quick", s6_corpus=str(tmp_path), s6_scratch=None, device="D", s6_ows_lib=None, s6_phase_cmd="hook")
    rc = RS._run_s6_sequential(args, tmp_path, None, stall, lambda: stopped.append(len(calls)))
    return rc, calls, stopped


def test_the_sequential_driver_runs_w_then_o_then_merges_and_stops_the_gate_between(monkeypatch, tmp_path):
    rc, calls, stopped = _drive(monkeypatch, tmp_path)
    assert rc == 0
    assert calls == [("phase", "w"), ("py", "s6/s6_play.py", "wsjtx"), ("phase", "o"), ("py", "s6/s6_play.py", "owsfz"), ("py", "s6/s6_merge.py", None)]
    assert stopped == [2]                       # the gate was stopped after pass W and BEFORE the phase that switches WSJT-X off


def test_a_wsjtx_stall_in_pass_w_returns_at_once_for_the_scenario_retry(monkeypatch, tmp_path):
    rc, calls, stopped = _drive(monkeypatch, tmp_path, stall_on_first_play=True)
    assert rc == -15 and calls == [("phase", "w"), ("py", "s6/s6_play.py", "wsjtx")] and stopped == []      # no phase o, no pass O, no merge, the gate left to the caller


def test_a_failed_phase_stops_the_driver_before_any_playback(monkeypatch, tmp_path):
    rc, calls, _ = _drive(monkeypatch, tmp_path, phase_rc={"w": 1})
    assert rc == 1 and calls == [("phase", "w")]
    rc2, calls2, _ = _drive(monkeypatch, tmp_path, phase_rc={"o": 1})
    assert rc2 == 1 and calls2 == [("phase", "w"), ("py", "s6/s6_play.py", "wsjtx"), ("phase", "o")]       # pass W was played; the daemon did not come up: no pass O, no merge


def test_a_pass_that_reports_a_nonzero_exit_still_merges_and_the_worst_code_is_returned(monkeypatch, tmp_path):
    rc, calls, _ = _drive(monkeypatch, tmp_path, play_rc={"owsfz": 4})
    assert rc == 4 and calls[-1] == ("py", "s6/s6_merge.py", None)
    rc2, _, _ = _drive(monkeypatch, tmp_path, merge_rc=1)
    assert rc2 == 1


def test_the_phase_hook_gets_the_run_folder_in_its_environment(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, shell, timeout, env):
        seen.update(cmd=cmd, env=env)
        return Namespace(returncode=0)

    monkeypatch.setattr(RS.subprocess, "run", fake_run)
    assert RS._s6_phase("hook", "o", run_dir=tmp_path) == 0
    assert seen["cmd"] == "hook o" and seen["env"]["S6_RUN_DIR"] == str(tmp_path)
    monkeypatch.delenv("S6_RUN_DIR", raising=False)
    assert RS._s6_phase("hook", "restore") == 0 and "S6_RUN_DIR" not in seen["env"]            # no run_dir given, none invented
