"""Unit tests for the #194 sampler (no station access needed except where marked)."""
import json
import re
from pathlib import Path

import pytest

import sampler

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
