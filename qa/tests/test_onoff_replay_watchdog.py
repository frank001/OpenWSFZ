"""Live test of the replay watchdog's kill / log / cooldown / relaunch / confirm / teardown path (HK-013: never arm a supervisor blind).

The watchdog is run for REAL (a real process, real taskkill of a real process TREE) against a STUB orchestrator, so the path is proven
without touching a real run. The stub: launch 1 heartbeats then DIES; launch 2 heartbeats once, spawns a long-lived CHILD and then HANGS
(alive, status stale); launch 3 heartbeats and writes DONE. The test asserts every trigger, the event log, that the hung stub's child
was killed with it (tree kill), that no retry is wasted, and that the watchdog exits by itself on DONE. Synthetic and numeric only.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SUBFEAS = Path(__file__).resolve().parent.parent / "rr-study" / "sub-feas"
WATCHDOG = SUBFEAS / "onoff_replay_watchdog.py"

STUB = r'''
import datetime, json, os, subprocess, sys, time
out = sys.argv[1]
n_path = os.path.join(out, "launches.txt")
n = (int(open(n_path).read()) if os.path.exists(n_path) else 0) + 1
open(n_path, "w").write(str(n))
def beat(phase="ARM"):
    json.dump({"phase": phase, "updated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
              open(os.path.join(out, "status.json"), "w"))
if n == 1:                      # dies after a few heartbeats
    for _ in range(3): beat(); time.sleep(1)
    sys.exit(1)
if n == 2:                      # hangs, with a child that must die with it
    beat()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    open(os.path.join(out, "child.pid"), "w").write(str(child.pid))
    time.sleep(120)
    sys.exit(0)
for _ in range(4): beat(); time.sleep(1)     # healthy, completes
beat("DONE")
'''


def pid_alive(pid):
    out = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).Id"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
    return out == str(pid)


def test_watchdog_recovers_a_dead_then_a_hung_orchestrator_logs_every_event_and_tears_down_on_done(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    stub = tmp_path / "onoff_stub_orch_7f3a.py"
    stub.write_text(STUB)
    cmd = [sys.executable, str(WATCHDOG), "--out", str(out), "--cwd", str(tmp_path), "--match", "onoff_stub_orch_7f3a.py",
           "--orphan-match", "onoff_stub_orphan_never_5d7a", "--period", "1", "--stale", "4", "--cooldown", "1", "--confirm", "8", "--retries", "5", "--",
           sys.executable, str(stub), str(out)]
    # The stub writes no status before the first launch: the watchdog must see 'no orchestrator' and relaunch it.
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    elapsed = time.time() - t0
    log = (out / "watchdog.log").read_text()
    assert r.returncode == 0, (r.stdout, r.stderr)
    # 1. a dead orchestrator is detected and relaunched
    assert "TRIGGER: no orchestrator process" in log
    # 2. a hung one (process alive, status stale) is detected by SILENCE, not by an error
    assert "TRIGGER: orchestrator hung" in log and "status.json stale" in log
    # 3. every relaunch is logged with its health, and the tree kill is logged
    assert "relaunch 1/5" in log and "relaunch 2/5" in log and "relaunch 3/5" in log
    assert log.count("TRIGGER:") == 3 and log.count("killed orchestrator tree") == 3   # none running, died, hung
    # 4. teardown on DONE, by itself, within the retry cap (no wasted retry, no 'GIVING UP')
    assert "status DONE: run complete, watchdog exiting after 3 relaunch(es)" in log
    assert "GIVING UP" not in log
    assert int((out / "launches.txt").read_text()) == 3
    # 5. the hung stub's CHILD was killed with it (tree kill, no orphan)
    child = int((out / "child.pid").read_text())
    assert not pid_alive(child), "the hung orchestrator's child process survived the kill"
    assert elapsed < 110


def test_watchdog_gives_up_after_the_retry_cap_and_logs_it(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    dying = tmp_path / "onoff_stub_dead_9c1b.py"
    dying.write_text("import sys; sys.exit(1)\n")     # never produces a status: every relaunch fails
    cmd = [sys.executable, str(WATCHDOG), "--out", str(out), "--cwd", str(tmp_path), "--match", "onoff_stub_dead_9c1b.py",
           "--orphan-match", "onoff_stub_orphan_never_5d7a", "--period", "1", "--stale", "4", "--cooldown", "1", "--confirm", "3", "--retries", "2", "--",
           sys.executable, str(dying)]
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    log = (out / "watchdog.log").read_text()
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "GIVING UP after 2 relaunch(es)" in log
    assert log.count("NOT healthy") == 2


def test_watchdog_exits_on_the_stop_file_without_relaunching(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    (out / "watchdog.stop").write_text("")
    cmd = [sys.executable, str(WATCHDOG), "--out", str(out), "--cwd", str(tmp_path), "--match", "onoff_never_9e2d.py",
           "--orphan-match", "onoff_stub_orphan_never_5d7a", "--period", "1", "--stale", "4", "--cooldown", "1", "--confirm", "2", "--",
           sys.executable, "-c", "pass"]
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    assert r.returncode == 0
    assert "watchdog.stop present" in (out / "watchdog.log").read_text()
    assert "relaunch" not in (out / "watchdog.log").read_text()
