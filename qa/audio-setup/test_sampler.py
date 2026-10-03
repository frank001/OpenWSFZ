"""Unit tests for the #194 sampler (no station access needed except where marked)."""
import json
import re
import time
from pathlib import Path

import pytest

import sampler
import summarize

HERE = Path(__file__).parent
POLL_STEP_S = 0.25
POLL_DEADLINE_S = 60.0              # generous: a build elsewhere on the PC slows Python start-up
POLL_STEPS = int(POLL_DEADLINE_S / POLL_STEP_S)
# Setter APIs that must NEVER appear in the sampler: it is read-only by construction (spec section 1).
FORBIDDEN = ["SetParameter", "SetMasterVolume", "SetMute", "SetDefaultDevice", "SetDefaultEndpoint",
             "VBVMR_SetParameters", "SetChannelVolume", "SetVolumeRange"]


def test_sampler_source_contains_no_setter_api():
    text = (HERE / "sampler.py").read_text(encoding="utf-8")
    hits = [f for f in FORBIDDEN if f in text]
    assert hits == [], f"read-only guarantee broken: {hits}"
    assert re.findall(r"VBVMR_\w+", text) and set(re.findall(r"VBVMR_\w+", text)) <= {
        "VBVMR_Login", "VBVMR_Logout", "VBVMR_IsParametersDirty", "VBVMR_GetParameterFloat",
        "VBVMR_GetParameterStringA", "VBVMR_GetVoicemeeterType", "VBVMR_GetVoicemeeterVersion"}


def test_vm_type_table_is_keyed_by_reported_type_with_known_banana_shape():
    # Voicemeeter Banana (type 2): 5 strips, 5 buses (A1-A3, B1-B2). Asserted in code, not prose.
    name, strips, buses, routes = sampler.VM_TYPES[2]
    assert (name, strips, buses, routes) == ("Banana", 5, 5, ("A1", "A2", "A3", "B1", "B2"))
    assert sampler.VM_A_BUS_COUNT[2] + 2 == buses            # three A buses and two B buses


def test_diff_states_reports_field_old_new_and_ignores_unchanged():
    a = {"vm": {"strips": [{"gain": -30.0, "mute": 0.0}]}, "x": 1}
    b = {"vm": {"strips": [{"gain": -29.0, "mute": 0.0}]}, "x": 1}
    assert sampler.diff_states(a, b) == [("vm.strips[0].gain", -30.0, -29.0)]
    assert sampler.diff_states(a, a) == []


def test_diff_states_reports_added_and_removed_fields():
    d = sampler.diff_states({"a": 1}, {"b": 2})
    assert ("a", 1, None) in d and ("b", None, 2) in d


def test_state_hash_is_order_independent_and_sensitive():
    assert sampler.state_hash({"a": 1, "b": 2}) == sampler.state_hash({"b": 2, "a": 1})
    assert sampler.state_hash({"a": 1}) != sampler.state_hash({"a": 2})


def test_wsjtx_ini_reader_extracts_only_audio_keys_and_hash(tmp_path):
    ini = tmp_path / "w.ini"
    ini.write_bytes(b"[Configuration]\nMyCall=Q1ABC\nSoundInName=Mic X\nAudioInputChannel=Mono\n"
                    b"SoundOutName=Spk Y\nAudioOutputChannel=Mono\n")
    out = sampler.read_wsjtx_ini(str(ini))
    assert set(out) == {"ini_sha256", "SoundInName", "AudioInputChannel", "SoundOutName", "AudioOutputChannel"}
    assert "MyCall" not in out and "Q1ABC" not in json.dumps(out)   # NFR-021: nothing else leaves


def test_voicemeeter_missing_dll_logs_unavailable_and_windows_continues(tmp_path):
    """AS5 in miniature: a missing DLL must not raise and must not stop the other sources."""
    s = sampler.Sampler(tmp_path / "o.jsonl", vm_dll=str(tmp_path / "nope.dll"))
    st = s._sample()
    assert st["voicemeeter"] == "unavailable"
    assert isinstance(st["windows"], dict) and st["wsjtx"].startswith("unavailable")


def test_stopfile_ends_the_loop_and_writes_end_snapshot(tmp_path):
    stop = tmp_path / "stop"
    stop.write_text("")
    s = sampler.Sampler(tmp_path / "o.jsonl", vm_dll=str(tmp_path / "nope.dll"), period=0.05, stopfile=str(stop))
    s.run()
    recs = [json.loads(l) for l in (tmp_path / "o.jsonl").read_text().splitlines()]
    kinds = [(r["type"], r.get("kind")) for r in recs]
    assert kinds[0] == ("snapshot", "start") and kinds[-1] == ("snapshot", "end")


def _worker_pids(parent_pid):
    import subprocess
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"Get-CimInstance Win32_Process -Filter 'ParentProcessId={parent_pid}' | Select-Object -ExpandProperty ProcessId"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return [int(x) for x in out.split() if x.strip().isdigit()]


def test_supervisor_logs_worker_crash_and_restarts_then_stops_cleanly(tmp_path):
    """The 2026-10-03 crash class: a worker killed natively must be logged and replaced, not end the run."""
    import subprocess, sys, time
    log, stop, pid = tmp_path / "o.jsonl", tmp_path / "o.stop", tmp_path / "o.pid"
    sup = subprocess.Popen([sys.executable, str(HERE / "sampler.py"), "--out", str(log), "--period", "0.3",
                            "--vm-dll", str(tmp_path / "nope.dll"), "--stopfile", str(stop), "--pidfile", str(pid)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        victim = None
        for _ in range(POLL_STEPS):
            kids = _worker_pids(sup.pid)
            if kids and log.exists() and '"kind": "start"' in log.read_text():
                victim = kids[0]               # only once the worker has logged its start snapshot
                break
            time.sleep(POLL_STEP_S)
        assert victim is not None
        killed = subprocess.run(["taskkill", "/F", "/PID", str(victim)], capture_output=True, stdin=subprocess.DEVNULL)
        assert killed.returncode == 0
        for _ in range(POLL_STEPS):
            if log.exists() and any(json.loads(l)["type"] == "snapshot" and json.loads(l)["kind"] == "restart"
                                    for l in log.read_text().splitlines()):
                break
            time.sleep(POLL_STEP_S)
    finally:
        stop.write_text("")
        rc = sup.wait(timeout=40)
    recs = [json.loads(l) for l in log.read_text().splitlines()]
    kinds = [(r["type"], r.get("kind")) for r in recs]
    assert ("worker_crash", None) in kinds and ("snapshot", "restart") in kinds
    assert kinds[-1] == ("snapshot", "end") and rc == 0 and not pid.exists()
    assert next(r for r in recs if r["type"] == "worker_crash")["exit_code"] != 0


# ------------------------------------------------------------------ ruling 2026-10-03 behaviours
def _scripted(sampler_obj, states):
    it = iter(states)
    sampler_obj._sample = lambda: next(it)


def _read_log(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines()]


def test_start_state_is_unverified_until_two_ticks_agree_and_diff_is_not_a_change(tmp_path):
    s0, s1 = {"v": {"gain": -30}}, {"v": {"gain": -33}}
    s = sampler.Sampler(tmp_path / "o.jsonl")
    _scripted(s, [s0, s1, s1, {"v": {"gain": -32}}])
    for i in range(4):
        s._tick(first=(i == 0))
    recs = _read_log(tmp_path / "o.jsonl")
    types = [r["type"] for r in recs if r["type"] != "heartbeat"]
    assert types == ["snapshot", "verified", "unverified_start_diff", "change"]
    assert recs[0]["verified"] is False
    diff = next(r for r in recs if r["type"] == "unverified_start_diff")
    assert (diff["field"], diff["old"], diff["new"]) == ("v.gain", -30, -33)
    change = next(r for r in recs if r["type"] == "change")
    assert (change["old"], change["new"]) == (-33, -32) and "detected_utc" in change


def test_unknown_voicemeeter_type_logs_unverified_and_never_guesses_counts(tmp_path, monkeypatch):
    class Fake:
        def __init__(self, *_):
            pass

        def read(self):
            raise sampler.TypeTableUnverified("type 9")

        def close(self):
            pass

    monkeypatch.setattr(sampler, "VoicemeeterReader", Fake)
    s = sampler.Sampler(tmp_path / "o.jsonl")
    st = s._sample()
    assert st["voicemeeter"] == "unavailable: type table unverified"
    assert isinstance(st["windows"], dict)               # Windows keeps being sampled
    monkeypatch.setattr(sampler, "VoicemeeterReader", None)   # would raise if the sampler retried
    assert s._sample()["voicemeeter"] == "unavailable: type table unverified"


def test_summary_reports_crashes_restarts_coverage_and_partial_label():
    def rec(t, typ, **kw):
        return {"schema": 1, "utc": f"2026-10-03T10:{t // 60:02d}:{t % 60:02d}.000000Z", "type": typ, **kw}
    ok = [rec(0, "snapshot", kind="start", cold_sample_ms=1100), rec(0, "heartbeat"), rec(60, "heartbeat"),
          rec(120, "heartbeat"), rec(120, "snapshot", kind="end")]
    sm = summarize.summarise(ok)
    assert sm["label"] == "OK" and sm["worker_crashes"] == 0 and sm["coverage"]["coverage"] == 1.0
    bad = [rec(0, "snapshot", kind="start", cold_sample_ms=900), rec(0, "heartbeat"), rec(60, "heartbeat"),
           rec(100, "worker_crash", exit_code=1, restarts_so_far=0, stderr_tail=""),
           rec(160, "snapshot", kind="restart", cold_sample_ms=2600), rec(160, "heartbeat"),
           rec(220, "heartbeat"), rec(280, "snapshot", kind="end")]
    sm = summarize.summarise(bad)
    assert sm["worker_crashes"] == 1 and sm["worker_restarts"] == 1
    assert sm["slow_restart_cold_samples"] == [{"utc": "2026-10-03T10:02:40.000000Z", "cold_sample_ms": 2600}]
    assert sm["coverage"]["max_gap_s"] == 100.0 and sm["label"] == "PARTIAL"   # the 100 s crash hole is not covered


def test_coverage_below_98_percent_is_labelled_partial():
    def rec(t, typ, **kw):
        return {"schema": 1, "utc": f"2026-10-03T10:{t // 60:02d}:{t % 60:02d}.000000Z", "type": typ, **kw}
    recs = [rec(0, "snapshot", kind="start"), rec(0, "heartbeat"), rec(60, "heartbeat"),
            rec(200, "heartbeat"), rec(260, "heartbeat"), rec(260, "snapshot", kind="end")]   # a 140 s hole
    sm = summarize.summarise(recs)
    assert sm["coverage"]["coverage"] < summarize.COVERAGE_PARTIAL_BELOW and sm["label"] == "PARTIAL"


def test_join_window_is_minus30_plus40_and_excludes_unverified_start_diff():
    def ch(utc, typ="change"):
        return {"schema": 1, "utc": utc, "type": typ, "field": "f", "old": 1, "new": 2, "detected_utc": utc}
    recs = [ch("2026-10-03T10:00:29.000000Z"), ch("2026-10-03T10:00:30.000000Z"), ch("2026-10-03T10:01:40.000000Z"),
            ch("2026-10-03T10:01:40.500000Z"), ch("2026-10-03T10:01:00.000000Z", typ="unverified_start_diff")]
    got = [r["detected_utc"] for r in summarize.join_slot(recs, "2026-10-03T10:01:00.000000Z")]
    assert got == ["2026-10-03T10:00:30.000000Z", "2026-10-03T10:01:40.000000Z"]   # [S-30, S+40], both ends inclusive


def test_parse_utc_accepts_scan_cycle_stamps():
    assert summarize.parse_utc("2026-09-23T10:33:45Z") == summarize.parse_utc("2026-09-23T10:33:45.000000Z")


def test_run_hook_start_stop_finish_end_to_end(tmp_path):
    """The hook the run tooling calls: start with a lead, explicit teardown, orphan check, gathered files."""
    import run_hook
    h = run_hook.start(tmp_path / "run", None, lead_s=1.0, period=0.5)
    assert h is not None
    time.sleep(3)
    info = run_hook.stop(h)
    assert info["returncode"] == 0 and not info["force_killed"] and info["pidfile_removed"] and info["orphans"] == []
    md = run_hook.finish(h, tmp_path / "gathered")
    assert "Audio-setup sampler" in md and (tmp_path / "gathered" / "audio_setup.jsonl").exists()
    assert (tmp_path / "gathered" / "audio_setup_summary.md").read_text(encoding="utf-8") == md


def test_run_hook_never_raises_when_the_sampler_cannot_start(tmp_path, monkeypatch):
    import run_hook
    monkeypatch.setattr(run_hook.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    assert run_hook.start(tmp_path / "x", None, lead_s=0.0) is None
    assert run_hook.stop(None) is None and run_hook.finish(None, tmp_path) is None


def test_join_falls_back_to_utc_for_change_records_written_before_detected_utc_existed():
    old = {"schema": 1, "utc": "2026-10-03T10:01:10.000000Z", "type": "change", "field": "f", "old": 1, "new": 2}
    assert summarize.join_slot([old], "2026-10-03T10:01:00Z") == [old]
