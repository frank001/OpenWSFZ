"""#194 audio-setup snapshot sampler (QA tooling; READ-ONLY by construction).

Every SAMPLE_PERIOD_S seconds it reads the Voicemeeter Remote API, Windows Core Audio and the
WSJT-X .ini, and appends to ``audio_setup.jsonl``:
  * ``snapshot`` (kind=start / end) - the full state
  * ``change``   - one record per field that changed (UTC, field, old, new)
  * ``heartbeat``- every HEARTBEAT_PERIOD_S: UTC + SHA-256 of the full state
  * ``unavailable`` - a source that could not be read (the sampler keeps going)

The sampler NEVER writes to the station. tests assert the module text contains no setter API.
NFR-021: hardware and application names only; no message text, no callsigns are read.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import signal
import sys
import threading
import time
from pathlib import Path

SCHEMA_VERSION = 1
VM_DIRTY_LOOP_MAX_CALLS = 10         # architect ruling 2026-10-03 3b: bounded 'call until it returns 0' before reading
VM_DIRTY_LOOP_INTERVAL_S = 0.05
UNVERIFIED_MAX_TICKS = 12            # start/restart state stays unverified until two consecutive ticks agree
COLD_SAMPLE_MAX_S = 2.0              # Amendment 1: cold first sample (and a restart's) <= 2 s
WARM_SAMPLE_MAX_MS = 500.0           # Amendment 1: every later sample
SAMPLE_PERIOD_S = 5.0
HEARTBEAT_PERIOD_S = 60.0
MAX_HEARTBEAT_GAP_S = 70.0           # AS4 bound
ENDPOINT_ID_TAIL_CHARS = 12          # spec section 3
VM_STRING_BUF_BYTES = 512            # VBVMR_GetParameterStringA buffer size
DEFAULT_VM_DLL = r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll"
WSJTX_AUDIO_KEYS = ("SoundInName", "AudioInputChannel", "SoundOutName", "AudioOutputChannel")

# Voicemeeter type reported by the API -> (name, strips, buses, routes per strip).
# The API has no count call; this table is keyed by the REPORTED type, never by a guess.
VM_TYPES = {
    1: ("Voicemeeter", 3, 2, ("A1", "B1")),
    2: ("Banana", 5, 5, ("A1", "A2", "A3", "B1", "B2")),
    3: ("Potato", 8, 8, ("A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3")),
}
# Bus index -> is a hardware (A) bus with a device name. Banana: buses 0-2 are A, 3-4 are B.
VM_A_BUS_COUNT = {1: 1, 2: 3, 3: 5}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def state_hash(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode("utf-8")).hexdigest()


def flatten(obj, prefix: str = "") -> dict:
    """Flatten nested dict/list state to {dotted.path: scalar} so change records name a field."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def diff_states(old: dict, new: dict) -> list[tuple[str, object, object]]:
    a, b = flatten(old), flatten(new)
    return [(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


# ---------------------------------------------------------------- Voicemeeter (read-only)
class TypeTableUnverified(OSError):
    """The API reported a Voicemeeter type our table has no verified row for. Never guess counts."""


class VoicemeeterReader:
    """ctypes over the installed Remote API, as an OS API. Only Login/Get*/IsParametersDirty/Logout."""

    def __init__(self, dll_path: str = DEFAULT_VM_DLL):
        self._dll = ctypes.WinDLL(dll_path)          # raises OSError if absent (AS5)
        if self._dll.VBVMR_Login() != 0:
            raise OSError("VBVMR_Login failed")
        self._open = True
        self.dirty_calls = 0            # per-heartbeat statistics of VBVMR_IsParametersDirty (ruling 3b)
        self.dirty_nonzero = 0
        self.dirty_loop_max = 0

    def _refresh(self) -> None:
        # IsParametersDirty returns 1 if parameters changed since the last call, 0 if not, <0 on error.
        # Its return value was previously discarded (the architect's lead). Log every value, and loop
        # (bounded) until it returns 0 so the cache is quiescent before we read.
        used = 0
        for _ in range(VM_DIRTY_LOOP_MAX_CALLS):
            rc = self._dll.VBVMR_IsParametersDirty()
            used += 1
            self.dirty_calls += 1
            if rc != 0:
                self.dirty_nonzero += 1
            if rc == 0:
                break
            time.sleep(VM_DIRTY_LOOP_INTERVAL_S)
        self.dirty_loop_max = max(self.dirty_loop_max, used)

    def take_dirty_stats(self) -> dict:
        out = {"vm_dirty_calls": self.dirty_calls, "vm_dirty_nonzero": self.dirty_nonzero,
               "vm_dirty_loop_max": self.dirty_loop_max}
        self.dirty_calls = self.dirty_nonzero = self.dirty_loop_max = 0
        return out

    def close(self) -> None:
        if self._open:
            self._dll.VBVMR_Logout()
            self._open = False

    def _float(self, name: str):
        v = ctypes.c_float()
        rc = self._dll.VBVMR_GetParameterFloat(name.encode(), ctypes.byref(v))
        return None if rc != 0 else round(v.value, 3)

    def _str(self, name: str):
        buf = ctypes.create_string_buffer(VM_STRING_BUF_BYTES)
        rc = self._dll.VBVMR_GetParameterStringA(name.encode(), buf)
        return None if rc != 0 else buf.value.decode("utf-8", "replace")

    def read(self) -> dict:
        self._refresh()
        t = ctypes.c_long()
        self._dll.VBVMR_GetVoicemeeterType(ctypes.byref(t))
        ver = ctypes.c_long()
        self._dll.VBVMR_GetVoicemeeterVersion(ctypes.byref(ver))
        vm_type = t.value
        if vm_type not in VM_TYPES:
            raise TypeTableUnverified(f"unknown Voicemeeter type {vm_type}")
        name, n_strip, n_bus, routes = VM_TYPES[vm_type]
        v = ver.value
        state = {
            "type": name, "type_id": vm_type,
            "version": f"{(v >> 24) & 255}.{(v >> 16) & 255}.{(v >> 8) & 255}.{v & 255}",
            "sample_rate": self._float("Option.sr"),
            "strips": [], "buses": [],
        }
        for i in range(n_strip):
            s = {"index": i, "label": self._str(f"Strip[{i}].Label"),
                 "gain": self._float(f"Strip[{i}].Gain"), "mute": self._float(f"Strip[{i}].Mute")}
            for r in routes:
                s[r] = self._float(f"Strip[{i}].{r}")
            state["strips"].append(s)
        for j in range(n_bus):
            b = {"index": j, "label": self._str(f"Bus[{j}].Label"),
                 "gain": self._float(f"Bus[{j}].Gain"), "mute": self._float(f"Bus[{j}].Mute")}
            if j < VM_A_BUS_COUNT[vm_type]:
                b["device"] = self._str(f"Bus[{j}].device.name")
            state["buses"].append(b)
        return state


# ---------------------------------------------------------------- Windows Core Audio (read-only)
_NAME_CACHE: dict = {}
DEVICE_STATE_ACTIVE = 1
FLOW_NAMES = {0: "eRender", 1: "eCapture"}


def read_windows() -> dict:
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    enum = AudioUtilities.GetDeviceEnumerator()
    defaults = {}
    for flow_name, flow in (("render", 0), ("capture", 1)):
        for role_name, role in (("console", 0), ("communications", 2)):
            try:
                defaults[f"{flow_name}_{role_name}"] = enum.GetDefaultAudioEndpoint(flow, role).GetId()[-ENDPOINT_ID_TAIL_CHARS:]
            except Exception:                      # no default device in this role
                defaults[f"{flow_name}_{role_name}"] = None
    endpoints = []
    for flow in (0, 1):                            # EnumAudioEndpoints is ~50x cheaper than GetAllDevices
        coll = enum.EnumAudioEndpoints(flow, DEVICE_STATE_ACTIVE)
        for i in range(coll.GetCount()):
            dev = coll.Item(i)
            dev_id = dev.GetId()
            if dev_id not in _NAME_CACHE:          # friendly names are cached per process (AS3 cost)
                _NAME_CACHE[dev_id] = AudioUtilities.CreateDevice(dev).FriendlyName
            try:
                ev = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
                vol, mute = round(ev.GetMasterVolumeLevelScalar(), 3), int(ev.GetMute())
            except Exception:
                vol, mute = None, None
            endpoints.append({"id_tail": dev_id[-ENDPOINT_ID_TAIL_CHARS:], "name": _NAME_CACHE[dev_id],
                              "flow": FLOW_NAMES[flow], "volume": vol, "mute": mute})
    endpoints.sort(key=lambda e: (e["flow"], e["id_tail"]))
    sessions = []
    for s in AudioUtilities.GetAllSessions():
        try:
            sv = s.SimpleAudioVolume
            sessions.append({"process": s.Process.name() if s.Process else "System Sounds",
                             "volume": round(sv.GetMasterVolume(), 3), "mute": int(sv.GetMute())})
        except Exception:
            continue
    sessions.sort(key=lambda s: s["process"])
    return {"defaults": defaults, "endpoints": endpoints, "sessions": sessions}


# ---------------------------------------------------------------- WSJT-X .ini (read-only)
def read_wsjtx_ini(path: str | None) -> dict:
    if not path:
        raise OSError("no WSJT-X ini configured")
    raw = Path(path).read_bytes()
    out = {"ini_sha256": hashlib.sha256(raw).hexdigest()}
    for line in raw.decode("utf-8", "replace").splitlines():
        m = re.match(r"^(\w+)=(.*)$", line)
        if m and m.group(1) in WSJTX_AUDIO_KEYS:
            out[m.group(1)] = m.group(2).strip()
    return out


# ---------------------------------------------------------------- sampler
class Sampler:
    def __init__(self, out_path: Path, vm_dll: str = DEFAULT_VM_DLL, wsjtx_ini: str | None = None,
                 period: float = SAMPLE_PERIOD_S, heartbeat: float = HEARTBEAT_PERIOD_S,
                 stopfile: str | None = None, start_kind: str = "start"):
        self.start_kind = start_kind
        self.stopfile = Path(stopfile) if stopfile else None
        self.out_path, self.vm_dll, self.wsjtx_ini = Path(out_path), vm_dll, wsjtx_ini
        self.period, self.heartbeat = period, heartbeat
        self._stop = threading.Event()
        self._vm = None
        self._vm_type_unverified = False
        self._prev: dict | None = None
        self._start_state: dict | None = None
        self._verified = False
        self._unverified_ticks = 0
        self.dirty_stats = {"vm_dirty_calls": 0, "vm_dirty_nonzero": 0, "vm_dirty_loop_max": 0}
        self._last_hb = 0.0
        self.sample_ms: list[float] = []

    def _emit(self, rec: dict) -> None:
        rec = {"schema": SCHEMA_VERSION, "utc": utc_now(), **rec}
        with open(self.out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _sample(self) -> dict:
        state: dict = {}
        if self._vm_type_unverified:
            state["voicemeeter"] = "unavailable: type table unverified"
        else:
            if self._vm is None:
                try:
                    self._vm = VoicemeeterReader(self.vm_dll)
                except OSError:
                    state["voicemeeter"] = "unavailable"
            if self._vm is not None:
                try:
                    state["voicemeeter"] = self._vm.read()
                except TypeTableUnverified:           # keep sampling Windows; never guess counts
                    state["voicemeeter"] = "unavailable: type table unverified"
                    self._vm_type_unverified = True
                    self._vm.close()
                    self._vm = None
                except Exception:
                    state["voicemeeter"] = "unavailable"
                    self._vm.close()
                    self._vm = None
        for key, fn in (("windows", read_windows), ("wsjtx", lambda: read_wsjtx_ini(self.wsjtx_ini))):
            try:
                state[key] = fn()
            except Exception as e:                  # a source failing must never crash the run
                state[key] = f"unavailable: {type(e).__name__}"
        return state

    def request_stop(self, *_):
        self._stop.set()

    def run(self) -> None:
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._tick(first=True)
            while not self._stop.wait(self.period):
                if self.stopfile is not None and self.stopfile.exists():
                    break                       # explicit teardown signal (HK-019)
                self._tick(first=False)
        finally:
            final = self._sample()
            self._emit({"type": "snapshot", "kind": "end", "state": final})
            if self._vm is not None:
                self._vm.close()

    def _tick(self, first: bool) -> None:
        t0 = time.perf_counter()
        state = self._sample()
        ms = (time.perf_counter() - t0) * 1000
        self.sample_ms.append(ms)
        if self._vm is not None:
            for k, v in self._vm.take_dirty_stats().items():
                self.dirty_stats[k] = max(self.dirty_stats[k], v) if k == "vm_dirty_loop_max" else self.dirty_stats[k] + v
        if first:
            # Ruling 3b: a start / restart snapshot is UNVERIFIED until two consecutive ticks agree.
            self._emit({"type": "snapshot", "kind": self.start_kind, "state": state, "verified": False,
                        "cold_sample_ms": round(ms, 1)})
            for src, v in state.items():
                if isinstance(v, str) and v.startswith("unavailable"):
                    self._emit({"type": "unavailable", "source": src, "detail": v})
            self._start_state, self._verified, self._unverified_ticks = state, False, 1
        elif not self._verified:
            self._unverified_ticks += 1
            agreed = state == self._prev
            if agreed or self._unverified_ticks >= UNVERIFIED_MAX_TICKS:
                self._verified = True
                self._emit({"type": "verified", "after_ticks": self._unverified_ticks, "agreed": agreed,
                            "state_sha256": state_hash(state)})
                for field, old, new in diff_states(self._start_state, state):
                    self._emit({"type": "unverified_start_diff", "field": field, "old": old, "new": new})
        else:
            for field, old, new in diff_states(self._prev, state):
                self._emit({"type": "change", "field": field, "old": old, "new": new, "detected_utc": utc_now()})
        self._prev = state
        now = time.monotonic()
        if first or now - self._last_hb >= self.heartbeat:
            msl, self.sample_ms = self.sample_ms, []
            self._emit({"type": "heartbeat", "state_sha256": state_hash(state), "samples": len(msl),
                        "sample_ms_max": round(max(msl), 1), "sample_ms_mean": round(sum(msl) / len(msl), 1),
                        "verified": self._verified, **self.dirty_stats})
            self.dirty_stats = {"vm_dirty_calls": 0, "vm_dirty_nonzero": 0, "vm_dirty_loop_max": 0}
            self._last_hb = now


SUPERVISOR_POLL_S = 0.5
WORKER_RESTART_DELAY_S = 1.0
WORKER_MAX_RESTARTS = 20
WORKER_STOP_WAIT_S = 30.0
STDERR_TAIL_CHARS = 400


def _flush_std() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError, AttributeError):   # a closed or invalid console must not fail the run
            pass


def _emit_line(out_path: Path, rec: dict) -> None:
    rec = {"schema": SCHEMA_VERSION, "utc": utc_now(), **rec}
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def supervise(a) -> int:
    """Parent process: runs the sampler as a worker and restarts it if it dies.

    2026-10-03: the worker crashed natively (access violation inside pycaw GetAllSessions, a COM
    Release during garbage collection) twice in 10-minute runs. A native fault cannot be caught in
    Python, so the run is protected by process isolation: a crash is logged as ``worker_crash`` and
    the worker restarted (``restart`` snapshot). The parent never touches COM.
    """
    import subprocess
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    stopfile = Path(a.stopfile) if a.stopfile else out.with_suffix(".stop")
    stop_flag = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", signal.SIGINT)):
        signal.signal(sig, lambda *_: stop_flag.set())
    if a.pidfile:
        Path(a.pidfile).write_text(str(os.getpid()))
    errpath = out.with_suffix(".worker_stderr")
    restarts, kind, rc = 0, "start", 0
    try:
        while True:
            cmd = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), "--worker",
                   "--out", str(out), "--period", str(a.period), "--vm-dll", a.vm_dll,
                   "--stopfile", str(stopfile), "--start-kind", kind]
            if a.wsjtx_ini:
                cmd += ["--wsjtx-ini", a.wsjtx_ini]
            with open(errpath, "a", encoding="utf-8") as errf:
                child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errf)
                while child.poll() is None:
                    if stop_flag.is_set() and not stopfile.exists():
                        stopfile.write_text("")
                    if stopfile.exists():
                        try:
                            child.wait(timeout=WORKER_STOP_WAIT_S)
                        except subprocess.TimeoutExpired:
                            child.kill()
                        break
                    time.sleep(SUPERVISOR_POLL_S)
            rc = child.returncode
            if stopfile.exists() or stop_flag.is_set():
                break
            tail = errpath.read_text(encoding="utf-8", errors="replace")[-STDERR_TAIL_CHARS:]
            _emit_line(out, {"type": "worker_crash", "exit_code": rc, "restarts_so_far": restarts,
                             "stderr_tail": tail})
            restarts += 1
            if restarts > WORKER_MAX_RESTARTS:
                _emit_line(out, {"type": "unavailable", "source": "sampler", "detail": "gave up after restarts"})
                break
            kind = "restart"
            time.sleep(WORKER_RESTART_DELAY_S)
    finally:
        if a.pidfile:
            Path(a.pidfile).unlink(missing_ok=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="audio_setup.jsonl path (appended)")
    ap.add_argument("--wsjtx-ini", default=None)
    ap.add_argument("--vm-dll", default=DEFAULT_VM_DLL)
    ap.add_argument("--period", type=float, default=SAMPLE_PERIOD_S)
    ap.add_argument("--stopfile", default=None, help="creating this file stops the sampler cleanly")
    ap.add_argument("--pidfile", default=None, help="written at start, removed at teardown (HK-019)")
    ap.add_argument("--worker", action="store_true", help="internal: run the sampling loop itself")
    ap.add_argument("--start-kind", default="start", choices=["start", "restart"])
    a = ap.parse_args(argv)
    if not a.worker:
        rc = supervise(a)
        _flush_std()
        os._exit(rc)
    import gc
    gc.disable()          # the crash stack was inside a cyclic-GC-triggered COM Release; refcounts still free
    s = Sampler(Path(a.out), a.vm_dll, a.wsjtx_ini, a.period, stopfile=a.stopfile, start_kind=a.start_kind)
    for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", signal.SIGINT)):
        signal.signal(sig, s.request_stop)
    s.run()
    # comtypes releases COM pointers during interpreter shutdown, after CoUninitialize, which prints
    # spurious 'Exception ignored' tracebacks. Everything is flushed and fsynced; leave directly.
    _flush_std()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
