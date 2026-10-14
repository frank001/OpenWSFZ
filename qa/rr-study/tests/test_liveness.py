"""M1/M2/M3 (2026-10-14): WSJT-X liveness gate, stall snapshot, per-scenario coverage. Synthetic folders only; nothing here touches a real /proc, a real
WSJT-X or any callsign (NFR-021)."""
from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "linux"))

from harness import liveness as LV  # noqa: E402
import wsjtx_monitor as MON  # noqa: E402


def make_wav(d: Path, stem: str, mtime: float) -> None:
    f = d / (stem + ".wav")
    f.write_bytes(b"RIFF")
    os.utime(f, (mtime, mtime))


def fake_proc(root: Path, pid: int, comm: str, wchan: str = "snd_pcm_read") -> None:
    p = root / str(pid)
    (p / "task" / str(pid)).mkdir(parents=True)
    (p / "comm").write_text(comm + "\n")
    (p / "status").write_text("Name:\t%s\nState:\tS (sleeping)\nVmRSS:\t12345 kB\nThreads:\t7\n" % comm)
    (p / "stat").write_text("%d (%s) S 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 7 0 12345 0 0 0\n" % (pid, comm))
    (p / "wchan").write_text(wchan)
    (p / "limits").write_text("Max core file size 0 0 bytes\n")
    t = p / "task" / str(pid)
    (t / "comm").write_text("audio-thread\n")
    (t / "wchan").write_text(wchan)
    (t / "syscall").write_text("0 0x7 0x0\n")
    (t / "stat").write_text("%d (audio-thread) S\n" % pid)


# ---------------------------------------------------------------------------------------------------------------------------- stamps and slots
def test_stamp_to_iso_and_rejects_other_names():
    assert LV.stamp_to_iso("261014_110930") == "2026-10-14T11:09:30Z"
    assert LV.stamp_to_iso("261014_110930.wav") == "2026-10-14T11:09:30Z"
    assert LV.stamp_to_iso("ALL") is None and LV.stamp_to_iso("readme") is None


def test_list_wav_slots_window_and_extension(tmp_path):
    for stem in ("261014_110900", "261014_110915", "261014_110930", "261014_110945"):
        make_wav(tmp_path, stem, 1000.0)
    (tmp_path / "notes.txt").write_text("x")
    s = LV.list_wav_slots(str(tmp_path))
    assert len(s) == 4 and "2026-10-14T11:09:30Z" in s
    t0 = datetime(2026, 10, 14, 11, 9, 15, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 14, 11, 9, 30, tzinfo=timezone.utc)
    assert LV.list_wav_slots(str(tmp_path), t0, t1) == {"2026-10-14T11:09:15Z", "2026-10-14T11:09:30Z"}
    assert LV.list_wav_slots(str(tmp_path / "missing")) == set()


# ---------------------------------------------------------------------------------------------------------------------------- liveness (M2)
def test_pids_by_comm_matches_the_real_binary_not_the_wrapper(tmp_path):
    fake_proc(tmp_path, 100, "xvfb-run")          # the wrapper the first watcher mistook for WSJT-X
    fake_proc(tmp_path, 200, "wsjtx")
    fake_proc(tmp_path, 300, "jt9")
    assert LV.pids_by_comm("wsjtx", str(tmp_path)) == [200]
    assert LV.pids_by_comm("jt9", str(tmp_path)) == [300]
    assert LV.pids_by_comm("wsjtx", str(tmp_path / "nope")) == []


def test_liveness_ok_stalled_and_dead(tmp_path):
    proc, save = tmp_path / "proc", tmp_path / "save"
    proc.mkdir()
    save.mkdir()
    fake_proc(proc, 200, "wsjtx")
    now = 10_000.0
    make_wav(save, "261014_110930", now - 12)
    r = LV.check_liveness(str(save), 45.0, now, str(proc))
    assert r.ok and r.pids == [200] and abs(r.age_s - 12) < 1e-6
    r = LV.check_liveness(str(save), 45.0, now + 40, str(proc))                      # 52 s old: stalled (the 14 Oct signature)
    assert not r.ok and "no new save WAV for 52 s" in r.reason
    r = LV.check_liveness(str(save), 45.0, now + 33, str(proc))                      # exactly at the limit is not yet a stall
    assert r.ok
    r = LV.check_liveness(str(save), 45.0, now, str(tmp_path / "noproc"))            # no wsjtx process
    assert not r.ok and r.reason == "no wsjtx process"
    r = LV.check_liveness(str(tmp_path / "emptysave"), 45.0, now, str(proc))
    assert not r.ok and "no save WAV found" in r.reason
    r = LV.check_liveness(str(save), 45.0, now, str(tmp_path / "noproc"), require_process=False)
    assert r.ok


def test_watchdog_fires_once_with_the_reading_and_kills_nothing(tmp_path):
    proc, save = tmp_path / "proc", tmp_path / "save"
    proc.mkdir()
    save.mkdir()
    fake_proc(proc, 200, "wsjtx")
    make_wav(save, "261014_110930", 1000.0)
    clock = {"t": 1010.0}
    hits = []
    done = threading.Event()

    def on_stall(r):
        hits.append(r)
        done.set()
    w = LV.Watchdog(str(save), on_stall, 45.0, 0.01, clock=lambda: clock["t"], proc_root=str(proc))
    w.start()
    time.sleep(0.1)
    assert not hits                                              # 10 s old: healthy
    clock["t"] = 1100.0                                          # 100 s without a new WAV
    assert done.wait(2.0)
    w.join(2.0)
    assert len(hits) == 1 and not hits[0].ok and w.stalled is hits[0]
    assert (proc / "200").is_dir()                               # nothing was touched


def test_watchdog_stop_ends_it_without_a_stall(tmp_path):
    proc, save = tmp_path / "proc", tmp_path / "save"
    proc.mkdir()
    save.mkdir()
    fake_proc(proc, 200, "wsjtx")
    make_wav(save, "261014_110930", 1000.0)
    hits = []
    w = LV.Watchdog(str(save), hits.append, 45.0, 0.01, clock=lambda: 1001.0, proc_root=str(proc))
    w.start()
    w.stop()
    w.join(2.0)
    assert not w.is_alive() and not hits and w.stalled is None


# ---------------------------------------------------------------------------------------------------------------------------- coverage (M3)
def test_coverage_threshold_is_expected_minus_one():
    cyc = ["2026-10-14T11:%02d:%02dZ" % (i // 4, (i % 4) * 15) for i in range(15)]
    assert len(set(cyc)) == 15
    full = set(cyc)
    r = LV.coverage_rows({"S4": cyc}, full, "WSJT-X")[0]
    assert (r["expected"], r["with_data"], r["required"], r["result"]) == (15, 15, 14, "PASS")
    r = LV.coverage_rows({"S4": cyc}, set(cyc[:14]), "WSJT-X")[0]
    assert r["with_data"] == 14 and r["result"] == "PASS"       # exactly expected - 1 passes
    r = LV.coverage_rows({"S4": cyc}, set(cyc[:13]), "WSJT-X")[0]
    assert r["with_data"] == 13 and r["result"] == "FAIL"       # expected - 2 fails
    r = LV.coverage_rows({"S4": cyc}, set(), "OpenWSFZ")[0]
    assert r["result"] == "FAIL" and r["appraiser"] == "OpenWSFZ"


def test_slots_roundtrip_and_missing_file(tmp_path):
    LV.write_slots(str(tmp_path / "s.txt"), {"2026-10-14T11:00:15Z", "2026-10-14T11:00:00Z"})
    assert LV.read_slots(str(tmp_path / "s.txt")) == {"2026-10-14T11:00:00Z", "2026-10-14T11:00:15Z"}
    assert LV.read_slots(str(tmp_path / "none.txt")) is None


def _run_dir(tmp_path, cycles_by_scen, slots_wsjtx=None, slots_owsfz=None):
    with open(tmp_path / "truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario_id", "part_index", "trial_index", "cycle_utc"])
        for scen, cyc in cycles_by_scen.items():
            for i, c in enumerate(cyc):
                w.writerow([scen, 0, i, c])
    if slots_wsjtx is not None:
        LV.write_slots(str(tmp_path / "coverage_slots_wsjtx.txt"), slots_wsjtx)
    if slots_owsfz is not None:
        LV.write_slots(str(tmp_path / "coverage_slots_owsfz.txt"), slots_owsfz)
    return tmp_path


def test_analyser_coverage_row_marks_a_silent_stretch_invalid(tmp_path):
    from harness.analyse import _coverage_check
    s1 = ["2026-10-14T10:%02d:00Z" % i for i in range(30)]
    s4 = ["2026-10-14T11:%02d:00Z" % i for i in range(15)]
    have = set(s1) | set(s4[:5])                                   # WSJT-X went silent in S4 after 5 cycles (the 14 Oct shape)
    rd = _run_dir(tmp_path, {"S1": s1, "S4": s4}, have, set(s1) | set(s4))
    rows, bad, notes = _coverage_check(rd)
    byk = {r[1]: r for r in rows}
    assert byk["S1/WSJT-X"][3] == "PASS" and byk["S4/WSJT-X"][3] == "INVALID" and byk["S4/OpenWSFZ"][3] == "PASS"
    assert len(bad) == 1 and "WSJT-X has data for only 5 of 15 cycles of S4" in bad[0] and not notes


def test_analyser_coverage_is_not_measured_without_slot_files_and_never_a_pass(tmp_path):
    from harness.analyse import _coverage_check
    rd = _run_dir(tmp_path, {"S1": ["2026-10-14T10:00:00Z"]})
    rows, bad, notes = _coverage_check(rd)
    assert rows == [] and bad == [] and len(notes) == 2 and all("NOT MEASURED" in n for n in notes)
    assert _coverage_check(tmp_path / "empty") is None            # no truth.csv at all


# ---------------------------------------------------------------------------------------------------------------------------- monitor (M1)
def test_sample_flags_a_stall_and_reads_state(tmp_path):
    proc, save, alsa = tmp_path / "proc", tmp_path / "save", tmp_path / "asound"
    proc.mkdir()
    save.mkdir()
    fake_proc(proc, 200, "wsjtx")
    fake_proc(proc, 300, "jt9")
    (alsa / "card0" / "pcm0c" / "sub0").mkdir(parents=True)
    (alsa / "card0" / "pcm0c" / "sub0" / "status").write_text("state: RUNNING\nowner_pid: 200\n")
    make_wav(save, "261014_110930", 1000.0)
    ok = MON.sample(str(save), None, 1010.0, 45.0, str(proc), str(alsa))
    assert ok["ok"] and ok["wav_count"] == 1 and ok["wsjtx"][0]["pid"] == 200 and ok["wsjtx"][0]["threads"] == "7" and ok["jt9"][0]["pid"] == 300
    assert ok["alsa"]["card0/pcm0c/sub0/status"] == "state: RUNNING"
    bad = MON.sample(str(save), None, 1100.0, 45.0, str(proc), str(alsa))
    assert not bad["ok"] and "no new save WAV" in bad["reason"]


def test_snapshot_writes_wait_channels_and_alsa_state_and_never_raises(tmp_path):
    proc, alsa, out = tmp_path / "proc", tmp_path / "asound", tmp_path / "out"
    proc.mkdir()
    out.mkdir()
    fake_proc(proc, 200, "wsjtx", wchan="snd_pcm_read")
    fake_proc(proc, 400, "Xvfb")
    (alsa / "card0" / "pcm0c" / "sub0").mkdir(parents=True)
    (alsa / "card0" / "pcm0c" / "sub0" / "status").write_text("state: XRUN\n")
    (alsa / "card0" / "pcm0c" / "sub0" / "hw_params").write_text("rate: 48000\n")
    d = Path(MON.snapshot(str(out), [{"t": "x", "ok": False}], str(proc), str(alsa)))
    assert d.name.startswith("stall-") and (d / "wsjtx-200" / "wchan.txt").read_text() == "snd_pcm_read"
    th = (d / "wsjtx-200" / "threads.txt").read_text()
    assert "comm=audio-thread" in th and "wchan=snd_pcm_read" in th
    assert (d / "Xvfb-400" / "status.txt").is_file()
    assert "state: XRUN" in (d / "alsa.txt").read_text() and "rate: 48000" in (d / "alsa.txt").read_text()
    assert (d / "ps.txt").is_file() and json.loads((d / "tail.jsonl").read_text().splitlines()[0])["ok"] is False
    assert (d / "wsjtx-200" / "fd.txt").read_text().startswith("<unreadable")   # no fd dir in the fake tree: recorded, not raised


def test_suspended_seconds_never_raises():
    v = MON.suspended_s()
    assert isinstance(v, float)
