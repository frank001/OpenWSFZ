"""#194 validation rows AS1-AS5. Run ONCE, on a quiet station, no run active.

    python validate.py --out <dir> --wsjtx-ini <ini> as1 | as2 | as5 | as34

AS2 is the ONLY code that writes to the station, and only: Strip[3].Gain +1 dB (through the
Voicemeeter API) and one unused endpoint's volume -0.10 (Core Audio), each restored in a
``finally`` and confirmed by read-back. The sampler itself is read-only (test_sampler.py).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path

import jsonschema

import sampler

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "audio_setup.schema.json").read_text(encoding="utf-8"))
AS2_DETECT_BOUND_S = 10.0          # spec AS2: change and restore each appear within <= 10 s
AS2_GAIN_STEP_DB = 1.0
AS2_STRIP = 3
AS2_ENDPOINT_PREFIX = "Voicemeeter In 5"
AS2_VOLUME_STEP = -0.10
AS2_GAIN_TOL = 0.01
READBACK_SETTLE_S = 1.5
AS3_DURATION_S = 600
AS3_CPU_MAX_FRACTION = 0.01        # <= 1 % of one core
AS3_SAMPLE_MAX_MS = 500.0
AS4_HEARTBEAT_GAP_MAX_S = sampler.MAX_HEARTBEAT_GAP_S
BUSY_PROCESS_MARKERS = ("run_study", "run_scenario", "endurance", "OpenWSFZ.Host", "OpenWSFZ.Daemon")


def active_run_processes() -> list[str]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          r"Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|dotnet|OpenWSFZ.*)\.exe$' } | Select-Object -ExpandProperty CommandLine"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    me = Path(__file__).name
    return [l.strip()[:120] for l in out.splitlines()
            if any(m in l for m in BUSY_PROCESS_MARKERS) and me not in l]


def refuse_if_busy() -> None:
    busy = active_run_processes()
    if busy:
        sys.exit(f"REFUSED: a run appears active (no validation on a busy station): {busy}")


def start_sampler(out: Path, extra=(), ini=None, period=sampler.SAMPLE_PERIOD_S):
    stop, pid = out.with_suffix(".stop"), out.with_suffix(".pid")
    for f in (stop, pid, out):
        f.unlink(missing_ok=True)
    cmd = [sys.executable, "-X", "faulthandler", str(HERE / "sampler.py"), "--out", str(out), "--stopfile", str(stop),
           "--pidfile", str(pid), "--period", str(period), *extra]
    if ini:
        cmd += ["--wsjtx-ini", ini]
    errf = open(out.with_suffix(".stderr"), "w+", encoding="utf-8")   # a file, not a pipe: survives a crash
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errf, text=True)
    proc.errf = errf
    return proc, stop, pid


def stop_sampler(proc, stop: Path, pid: Path, timeout=30) -> dict:
    stop.write_text("")
    try:
        rc = proc.wait(timeout=timeout)
        killed = False
    except subprocess.TimeoutExpired:
        proc.kill()
        rc, killed = None, True
    proc.errf.flush()
    proc.errf.seek(0)
    err = proc.errf.read()
    proc.errf.close()
    return {"returncode": rc, "force_killed": killed, "stderr_bytes": len(err), "stderr_head": err[:1500], "pidfile_removed": not pid.exists()}


def records(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def parse_utc(s: str) -> float:
    import datetime as dt
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.timezone.utc).timestamp()


# ------------------------------------------------------------------ AS1
def as1(out: Path, ini: str) -> dict:
    s = sampler.Sampler(out / "as1.jsonl", wsjtx_ini=ini)
    state = s._sample()
    rec = {"schema": 1, "utc": sampler.utc_now(), "type": "snapshot", "kind": "start", "state": state}
    jsonschema.validate(rec, SCHEMA)
    vm = state["voicemeeter"]
    name, n_strip, n_bus, routes = sampler.VM_TYPES[vm["type_id"]]
    complete = (len(vm["strips"]) == n_strip and len(vm["buses"]) == n_bus
                and all(r in st for st in vm["strips"] for r in routes))
    none_fields = sorted(k for k, v in sampler.flatten(state).items() if v is None)
    res = {"row": "AS1", "schema_valid": True, "vm_type": vm["type"], "vm_version": vm["version"],
           "strips": len(vm["strips"]), "buses": len(vm["buses"]), "complete_vs_type_table": complete,
           "endpoints": len(state["windows"]["endpoints"]), "sessions": len(state["windows"]["sessions"]),
           "fields_read_as_null": none_fields, "wsjtx_keys": sorted(state["wsjtx"]),
           "PASS": bool(complete)}
    (out / "as1_state.json").write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    return res


# ------------------------------------------------------------------ AS2 (the only writes)
class VmWriter:
    """Test-only. Lives in validate.py, never in the sampler."""
    def __init__(self):
        self.dll = ctypes.WinDLL(sampler.DEFAULT_VM_DLL)
        assert self.dll.VBVMR_Login() == 0
        self.dll.VBVMR_GetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_float)]
        self.dll.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]

    def get(self, name: str) -> float:
        self.dll.VBVMR_IsParametersDirty()
        v = ctypes.c_float()
        assert self.dll.VBVMR_GetParameterFloat(name.encode(), ctypes.byref(v)) == 0
        return v.value

    def set(self, name: str, value: float) -> None:
        assert self.dll.VBVMR_SetParameterFloat(name.encode(), value) == 0

    def close(self):
        self.dll.VBVMR_Logout()


def _endpoint(prefix: str):
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    enum = AudioUtilities.GetDeviceEnumerator()
    defaults = {enum.GetDefaultAudioEndpoint(f, r).GetId() for f in (0, 1) for r in (0, 2)}
    coll = enum.EnumAudioEndpoints(0, sampler.DEVICE_STATE_ACTIVE)
    for i in range(coll.GetCount()):
        d = coll.Item(i)
        if AudioUtilities.CreateDevice(d).FriendlyName.startswith(prefix):
            assert d.GetId() not in defaults, "chosen endpoint is a default device: refusing"
            return cast(d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume)), d.GetId()[-12:]
    raise SystemExit(f"endpoint {prefix!r} not found")


def _wait_change(path: Path, field_sub: str, t_set: float, new_value, tol: float, deadline_s: float):
    """Poll the log for a change record on ``field_sub`` with ``new`` ~= new_value, written after t_set."""
    t_end = time.time() + deadline_s + 1.0
    while time.time() < t_end:
        for r in records(path):
            if r["type"] == "change" and field_sub in r["field"] and r["new"] is not None \
                    and abs(r["new"] - new_value) <= tol and parse_utc(r["utc"]) >= t_set - 0.001:
                return r
        time.sleep(0.5)
    return None


def as2(out: Path, ini: str) -> dict:
    refuse_if_busy()
    log = out / "as2.jsonl"
    proc, stop, pid = start_sampler(out / "as2.jsonl", ini=ini)
    time.sleep(sampler.SAMPLE_PERIOD_S + 2)               # baseline sample in place
    vm = VmWriter()
    ev, ep_tail = _endpoint(AS2_ENDPOINT_PREFIX)
    gname = f"Strip[{AS2_STRIP}].Gain"
    g0, v0 = vm.get(gname), round(ev.GetMasterVolumeLevelScalar(), 3)
    v1 = round(v0 + AS2_VOLUME_STEP, 3)
    assert v1 >= 0.0, "endpoint volume too low to lower by 0.10"
    res = {"row": "AS2", "gain_before": g0, "endpoint": AS2_ENDPOINT_PREFIX, "endpoint_tail": ep_tail,
           "volume_before": v0}
    try:
        t = time.time(); vm.set(gname, g0 + AS2_GAIN_STEP_DB)
        res["gain_change"] = _wait_change(log, f"strips[{AS2_STRIP}].gain", t, g0 + AS2_GAIN_STEP_DB, AS2_GAIN_TOL, AS2_DETECT_BOUND_S)
        res["gain_change_latency_s"] = None if res["gain_change"] is None else round(parse_utc(res["gain_change"]["utc"]) - t, 2)
        t = time.time(); vm.set(gname, g0)
        res["gain_restore"] = _wait_change(log, f"strips[{AS2_STRIP}].gain", t, g0, AS2_GAIN_TOL, AS2_DETECT_BOUND_S)
        res["gain_restore_latency_s"] = None if res["gain_restore"] is None else round(parse_utc(res["gain_restore"]["utc"]) - t, 2)

        t = time.time(); ev.SetMasterVolumeLevelScalar(v1, None)
        # endpoint fields are list-indexed: _find_endpoint_change resolves the index from the start snapshot
        res["vol_change"] = _find_endpoint_change(log, ep_tail, t, v1)
        res["vol_change_latency_s"] = None if res["vol_change"] is None else round(parse_utc(res["vol_change"]["utc"]) - t, 2)
        t = time.time(); ev.SetMasterVolumeLevelScalar(v0, None)
        res["vol_restore"] = _find_endpoint_change(log, ep_tail, t, v0)
        res["vol_restore_latency_s"] = None if res["vol_restore"] is None else round(parse_utc(res["vol_restore"]["utc"]) - t, 2)
    finally:                                              # restore regardless of what happened above
        vm.set(gname, g0)
        ev.SetMasterVolumeLevelScalar(v0, None)
        time.sleep(READBACK_SETTLE_S)                  # a read straight after a set returns the OLD value
        vm.get(gname)
        time.sleep(READBACK_SETTLE_S)
        res["gain_after"], res["volume_after"] = vm.get(gname), round(ev.GetMasterVolumeLevelScalar(), 3)
        vm.close()
        res["teardown"] = stop_sampler(proc, stop, pid)
    res["restored_by_readback"] = abs(res["gain_after"] - g0) <= AS2_GAIN_TOL and abs(res["volume_after"] - v0) <= 0.002
    lat = [res.get(k) for k in ("gain_change_latency_s", "gain_restore_latency_s", "vol_change_latency_s", "vol_restore_latency_s")]
    res["PASS"] = all(x is not None and x <= AS2_DETECT_BOUND_S for x in lat) and res["restored_by_readback"]
    return res


def _find_endpoint_change(log: Path, ep_tail: str, t_set: float, new_value, tol=0.002) -> dict | None:
    """Endpoint fields are list-indexed; resolve the index of ``ep_tail`` from the latest snapshot/heartbeat state."""
    start = next(r for r in records(log) if r["type"] == "snapshot" and r["kind"] == "start")
    idx = next(i for i, e in enumerate(start["state"]["windows"]["endpoints"]) if e["id_tail"] == ep_tail)
    return _wait_change(log, f"windows.endpoints[{idx}].volume", t_set, new_value, tol, AS2_DETECT_BOUND_S)


# ------------------------------------------------------------------ AS3 + AS4 (one 10-minute run)
def _cpu_seconds(pid: int) -> float:
    import ctypes.wintypes as w
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = w.HANDLE
    h = k.OpenProcess(0x1000, False, pid)                 # PROCESS_QUERY_LIMITED_INFORMATION
    c, e, kt, ut = (w.FILETIME() for _ in range(4))
    k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
    k.CloseHandle(h)
    ft = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7
    return ft(kt) + ft(ut)


def _children(pid: int) -> list[int]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}' | Select-Object -ExpandProperty ProcessId"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return [int(x) for x in out.split() if x.strip().isdigit()]


class TreeCpu:
    """CPU seconds consumed by the sampler parent + every worker that lived during the window."""
    def __init__(self, parent_pid: int):
        self.parent, self.first, self.last = parent_pid, {}, {}
        self.sample()

    def sample(self) -> None:
        for pid in [self.parent, *_children(self.parent)]:
            try:
                c = _cpu_seconds(pid)
            except Exception:
                continue
            self.first.setdefault(pid, c)
            self.last[pid] = c

    def total(self) -> float:
        return sum(self.last[p] - self.first[p] for p in self.last)


def as34(out: Path, ini: str, duration: float = AS3_DURATION_S) -> dict:
    refuse_if_busy()
    log = out / "as34.jsonl"
    proc, stop, pid = start_sampler(log, ini=ini)
    time.sleep(3)
    tree, t0 = TreeCpu(proc.pid), time.time()
    while time.time() - t0 < duration:
        time.sleep(5)
        tree.sample()
    t1 = time.time()
    cpu_frac = tree.total() / (t1 - t0)
    td = stop_sampler(proc, stop, pid)
    recs = records(log)
    for r in recs:
        jsonschema.validate(r, SCHEMA)
    hb = [parse_utc(r["utc"]) for r in recs if r["type"] == "heartbeat"]
    gaps = [round(b - a, 1) for a, b in zip(hb, hb[1:])]
    sm = [r["sample_ms_max"] for r in recs if r["type"] == "heartbeat"]
    orphans = active_sampler_orphans()
    res = {"row": "AS3+AS4", "duration_s": round(t1 - t0), "cpu_fraction_of_one_core": round(cpu_frac, 5),
           "sample_ms_max_over_run": max(sm), "heartbeats": len(hb), "max_heartbeat_gap_s": max(gaps),
           "changes_logged": sum(r["type"] == "change" for r in recs),
           "worker_crashes": sum(r["type"] == "worker_crash" for r in recs),
           "worker_pids_measured": len(tree.last), "records_schema_valid": len(recs),
           "teardown": td, "orphans": orphans}
    res["AS3_PASS"] = cpu_frac <= AS3_CPU_MAX_FRACTION and max(sm) <= AS3_SAMPLE_MAX_MS
    res["AS4_PASS"] = (res["worker_crashes"] == 0 and max(gaps) <= AS4_HEARTBEAT_GAP_MAX_S and not td["force_killed"] and td["returncode"] == 0
                       and td["pidfile_removed"] and not orphans and recs[-1]["type"] == "snapshot" and recs[-1]["kind"] == "end")
    return res


def active_sampler_orphans() -> list[str]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Select-Object -ExpandProperty CommandLine"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return [l.strip()[:100] for l in out.splitlines() if "sampler.py" in l]


# ------------------------------------------------------------------ AS5
def as5(out: Path, ini: str) -> dict:
    log = out / "as5.jsonl"
    proc, stop, pid = start_sampler(log, extra=("--vm-dll", str(out / "missing" / "VoicemeeterRemote64.dll")), ini=ini, period=2)
    time.sleep(9)
    td = stop_sampler(proc, stop, pid)
    recs = records(log)
    for r in recs:
        jsonschema.validate(r, SCHEMA)
    start = recs[0]["state"]
    unav = [r for r in recs if r["type"] == "unavailable" and r["source"] == "voicemeeter"]
    res = {"row": "AS5", "vm_state": start["voicemeeter"], "unavailable_records": len(unav),
           "windows_endpoints": len(start["windows"]["endpoints"]), "teardown": td,
           "snapshots": [r["kind"] for r in recs if r["type"] == "snapshot"]}
    res["PASS"] = (start["voicemeeter"] == "unavailable" and len(unav) >= 1 and len(start["windows"]["endpoints"]) > 0
                   and td["returncode"] == 0 and not td["force_killed"] and td["stderr_bytes"] == 0)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("row", choices=["as1", "as2", "as34", "as5"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--wsjtx-ini", required=True)
    ap.add_argument("--duration", type=float, default=AS3_DURATION_S)
    a = ap.parse_args()
    o = Path(a.out)
    o.mkdir(parents=True, exist_ok=True)
    fn = {"as1": as1, "as2": as2, "as5": as5}.get(a.row)
    r = fn(o, a.wsjtx_ini) if fn else as34(o, a.wsjtx_ini, a.duration)
    (o / f"{a.row}_result.json").write_text(json.dumps(r, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(r, indent=1, sort_keys=True, default=str))
