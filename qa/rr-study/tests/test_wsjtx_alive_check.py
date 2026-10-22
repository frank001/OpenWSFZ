"""Tests for the 'WSJT-X alive and decoding' startup checks (2026-10-13): the process row of PRECHECK and the mechanical warm-up before scenario 1."""
import json
import os
import sys
from pathlib import Path

RR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RR))

import wsjtx_alive  # noqa: E402
from harness import warmup_check as W  # noqa: E402


# ---------------- the process row
def test_linux_scan_finds_only_wsjtx_comm(tmp_path):
    for pid, comm in ((101, "wsjtx"), (102, "jt9"), (103, "wsjtx"), (104, "OpenWSFZ.Daemon")):
        (tmp_path / str(pid)).mkdir()
        (tmp_path / str(pid) / "comm").write_text(comm + "\n")
    (tmp_path / "self").mkdir()
    assert wsjtx_alive._linux_pids(str(tmp_path)) == [101, 103]


def test_windows_tasklist_parse():
    class R:
        stdout = '"wsjtx.exe","4242","Console","1","120,000 K"\n"wsjtx.exe","4300","Console","1","99,000 K"\n'
    assert wsjtx_alive._windows_pids(run=lambda *a, **k: R()) == [4242, 4300]

    class N:
        stdout = "INFO: No tasks are running which match the specified criteria.\n"
    assert wsjtx_alive._windows_pids(run=lambda *a, **k: N()) == []


def test_precheck_refuses_before_starting_the_daemon_when_wsjtx_is_not_running(tmp_path, monkeypatch):
    import rr_precheck
    monkeypatch.setattr(wsjtx_alive, "check", lambda: {"wsjtx_running": False, "count": 0, "pids": []})
    monkeypatch.setattr(rr_precheck.ES, "daemon_processes", lambda: [])
    exe, cfg = tmp_path / "daemon.exe", tmp_path / "config.json"
    exe.write_text("x")
    cfg.write_text("{}")
    run, res = rr_precheck.precheck(str(tmp_path / "run"), str(exe), str(cfg), 8080, str(tmp_path / "w.ini"))
    assert res["checks"]["wsjtx_running"] is False and res["checks"]["all_pass"] is False and "start WSJT-X" in res["checks"]["wsjtx_refusal"]
    assert "became_ready" not in res["checks"]                        # the daemon was never started
    assert json.load(open(tmp_path / "run" / "arm_config.json"))["checks"]["wsjtx_running"] is False


def test_both_precheck_twins_carry_the_same_row():
    for f in ("rr_precheck.py", "rr_precheck_linux.py"):
        t = (RR / f).read_text(encoding="utf-8")
        assert "wsjtx_alive.check()" in t and 'res["checks"]["decodingEnabled"], res["checks"]["dll_readable"], res["checks"]["wsjtx_running"]' in t, f


# ---------------- the mechanical warm-up
class Clock:
    def __init__(self, t=1_760_000_000.0):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, s)


def run_warmup(tmp_path, wsjtx_decodes_on, owsfz_decodes_on):
    """wsjtx_decodes_on / owsfz_decodes_on: the attempt numbers (1-based) on which that appraiser writes a line for the slot."""
    ck = Clock()
    wsjt, ows = tmp_path / "w.txt", tmp_path / "o.txt"
    wsjt.write_text("")
    ows.write_text("")
    n = {"i": 0}

    def play(b):
        n["i"] += 1
        stamp = W.slot_stamp(b)
        ck.t = max(ck.t, b + 15.0)                                    # the playback takes the slot
        if n["i"] in wsjtx_decodes_on:
            wsjt.open("a").write(stamp + "     14.074 Rx FT8   6  0.1 1500 CQ QWARM FN42\n")
        if n["i"] in owsfz_decodes_on:
            ows.open("a").write(stamp + "     14.074 Rx FT8   6  0.1 1500 CQ QWARM FN42\n")
    return W.mechanical_warmup(play, str(wsjt), str(ows), clock=ck.now, sleep=ck.sleep)


def test_warmup_passes_when_both_decode(tmp_path):
    ok, r = run_warmup(tmp_path, {1}, {1})
    assert ok and r["ok"] and len(r["attempts"]) == 1 and r["attempts"][0]["wsjtx_lines"] == 1 and r["attempts"][0]["owsfz_lines"] == 1


def test_warmup_fails_naming_the_silent_appraiser(tmp_path):
    ok, r = run_warmup(tmp_path, set(), {1, 2, 3})                    # WSJT-X never decodes: the Linux repeats of 2026-10-11
    assert not ok and r["silent_appraisers"] == ["WSJT-X"] and len(r["attempts"]) == 3
    assert "WSJT-X" in r["message"] and "stops before scenario 1" in r["message"]


def test_warmup_names_both_when_both_are_silent_and_openwsfz_when_it_is(tmp_path):
    assert run_warmup(tmp_path, set(), set())[1]["silent_appraisers"] == ["WSJT-X", "OpenWSFZ"]
    assert run_warmup(tmp_path, {1, 2, 3}, set())[1]["silent_appraisers"] == ["OpenWSFZ"]


def test_warmup_tolerates_a_first_attempt_that_one_appraiser_missed(tmp_path):
    ok, r = run_warmup(tmp_path, {2}, {1, 2})                         # WSJT-X misses attempt 1 and decodes attempt 2
    assert ok and len(r["attempts"]) == 2 and r["attempts"][0]["wsjtx_lines"] == 0 and r["attempts"][1]["wsjtx_lines"] == 1


def test_lines_are_counted_only_after_the_start_position_and_by_slot_stamp(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("260101_000000 x\n")
    pos = f.stat().st_size
    with open(f, "a") as fh:
        fh.write("260101_000015 x\n260101_000015 y\n260101_000030 z\n")
    assert W.lines_for_slot(str(f), pos, "260101_000015") == 2 and W.lines_for_slot(str(f), 0, "260101_000000") == 1
    assert W.lines_for_slot(str(tmp_path / "none"), 0, "x") == 0
