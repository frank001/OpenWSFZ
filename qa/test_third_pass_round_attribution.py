"""E122 / COH-RES-CAND spec section 6: the LATE-SUB round writes its own inner 'Third pass:' line, and three QA scripts counted it as a second third pass.
One synthetic log per script: one cycle with the round OFF (no round line) and one with it ON (inner line, then the round line). The third-pass counts must equal
the counts from the third pass's own line; the round's counts are reported separately. Synthetic text only (NFR-021): no callsigns, no message text."""
import importlib.util
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, HERE / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


f2 = load("endurance/f2_station_count.py", "f2_station_count_t")
sweep = load("rr-study/linux/sweep_f2_record.py", "sweep_f2_record_t")
tpc = load("rr-study/linux/third_pass_counters.py", "third_pass_counters_t")

THIRD_RAN = "Third pass: newDecodes=2 elapsedMs=1500 outcome=ran fittedSignals=3"
INNER_ABANDONED = "Third pass: newDecodes=0 elapsedMs=2100 outcome=abandoned fittedSignals=4"
INNER_RAN = "Third pass: newDecodes=1 elapsedMs=900 outcome=ran fittedSignals=4"
ROUND_RAN = ("Late subtraction round: outcome=ran, buffer=R3, fit=4, refused=0, new=1, published=1, fbEndMs=9000, startMs=9100, elapsedMs=900, "
             "endMs=10000, batch=5, batch5PublishMs=10000.")
ROUND_ABANDONED = ("Late subtraction round: outcome=abandoned, buffer=R3, fit=4, refused=0, new=0, published=0, fbEndMs=9000, startMs=9100, elapsedMs=2100, "
                   "endMs=11200, batch=5, batch5PublishMs=-1.")
ROUND_SKIPPED = ("Late subtraction round: outcome=skipped-no-residual, buffer=-, fit=0, refused=0, new=0, published=0, fbEndMs=9000, startMs=9000, elapsedMs=0, "
                 "endMs=9000, batch=5, batch5PublishMs=-1.")

OFF = ["[10:00:00 INF] Cycle 10:00:00: 5 decode(s) found",
       "Sub-feas residual pass: residualDecodes=2 elapsedMs=800 deadlineAbandoned=False containedException=False", THIRD_RAN]
ON = ["[10:00:15 INF] Cycle 10:00:15: 6 decode(s) found",
      "Sub-feas residual pass: residualDecodes=2 elapsedMs=800 deadlineAbandoned=False containedException=False", THIRD_RAN, INNER_RAN, ROUND_RAN]
ON_ABANDONED = ON[:3] + [INNER_ABANDONED, ROUND_ABANDONED]
ON_SKIPPED = ON[:3] + [ROUND_SKIPPED]          # round skipped: writes no inner line


def test_f2_station_count_round_off_and_on():
    own, inner, rounds = f2.split_third_pass(OFF + ON)
    assert len(own) == 2 and [m.group(3) for m in own] == ["ran", "ran"]     # one per cycle, from the third pass's own line
    assert len(inner) == 1 and inner[0].group(3) == "ran"
    assert [r[0] for r in rounds] == ["ran"]


def test_f2_station_count_abandoned_round_is_not_a_third_pass_abandon():
    own, inner, rounds = f2.split_third_pass(ON_ABANDONED)
    assert [m.group(3) for m in own] == ["ran"]          # the third pass itself did not abandon
    assert [m.group(3) for m in inner] == ["abandoned"]


def test_f2_station_count_skipped_round_claims_nothing():
    own, inner, rounds = f2.split_third_pass(ON_SKIPPED)
    assert len(own) == 1 and inner == [] and [r[0] for r in rounds] == ["skipped-no-residual"]


def test_f2_station_count_round_off_equals_plain_count():
    own_off, inner_off, rounds_off = f2.split_third_pass(OFF)
    assert len(own_off) == 1 and inner_off == [] and rounds_off == []


def test_third_pass_counters_round_off_and_on():
    own, inner, rounds = tpc.split_third_pass(OFF + ON)
    assert [g[2] for g in own] == ["ran", "ran"] and [g[2] for g in inner] == ["ran"] and [r[0] for r in rounds] == ["ran"]
    own, inner, rounds = tpc.split_third_pass(ON_ABANDONED)
    assert [g[2] for g in own] == ["ran"] and [g[2] for g in inner] == ["abandoned"]
    own, inner, rounds = tpc.split_third_pass(ON_SKIPPED)
    assert len(own) == 1 and inner == []


def test_third_pass_counters_summary_reports_round_separately(capsys):
    tpc.summarise("t", OFF + ON)
    out = capsys.readouterr().out
    assert "cycles with a line 2" in out and "started 2" in out      # two third passes, not three
    assert "late round (t): lines 1" in out and "NOT counted as third passes" in out


def test_sweep_walk_log_round_off_and_on():
    per_cycle, drops = sweep.walk_log(OFF + ON)
    off, on = per_cycle[10 * 3600], per_cycle[10 * 3600 + 15]
    assert off["third"] == ("ran", 1500, 2) and off["late_third"] is None and off["late_outcome"] is None
    assert on["third"] == ("ran", 1500, 2)                          # the third pass's own line, not the round's inner one
    assert on["late_third"] == ("ran", 900, 1) and on["late_outcome"] == "ran"


def test_sweep_walk_log_abandoned_and_skipped_rounds():
    on = sweep.walk_log(ON_ABANDONED)[0][10 * 3600 + 15]
    assert on["third"] == ("ran", 1500, 2) and on["late_third"][0] == "abandoned"
    sk = sweep.walk_log(ON_SKIPPED)[0][10 * 3600 + 15]
    assert sk["third"] == ("ran", 1500, 2) and sk["late_third"] is None and sk["late_outcome"] == "skipped-no-residual"


def test_sweep_walk_log_third_pass_skip_lines_still_count_as_third_pass():
    log = ["[10:00:30 INF] Cycle 10:00:30: 4 decode(s) found",
           "Third pass: newDecodes=0 elapsedMs=0 outcome=skipped-no-new fittedSignals=0",
           ROUND_SKIPPED]
    c = sweep.walk_log(log)[0][10 * 3600 + 30]
    assert c["third"] == ("skipped-no-new", 0, 0) and c["late_third"] is None
