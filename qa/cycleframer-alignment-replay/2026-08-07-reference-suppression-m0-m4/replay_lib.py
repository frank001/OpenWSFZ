"""Shared daemon lifecycle + live audio-playback machinery for M3/M4.

Daemon lifecycle, boundary-aligned playback, and device selection are ported UNMODIFIED in
substance from
`qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/run_cross_decode_replay.py`
(itself traced back to the 07-23 original, `run_isolated_replay_generic.py`) -- per the
Architect spec SS1.1, this machinery is to be REUSED, not rewritten.

The one substantive addition here, over the inherited code, is `play_pass_guarded()`: a
preflight-abort check partway through each pass. Tonight's (2026-08-06) first live-replay
attempt was aborted mid-run because WSJT-X's Monitor was switched on late -- caught only by
a human watching the console. `play_pass_guarded()` makes that check mechanical: after
`PREFLIGHT_CYCLES` + 1 cycles of a pass have played, it checks whether WSJT-X's own ALL.TXT
has grown at all since the pass started -- the 15s occupied by that extra cycle's own
playback is the decode-latency slack, so the check costs zero timing budget. If it hasn't
grown, the pass is aborted immediately (not run to completion blind) and `PreflightAbort` is
raised with enough detail for the orchestrator to escalate rather than silently record a
zero/garbage result. This is a proxy, not a certainty -- any growth (even from unrelated
traffic) satisfies it, and it cannot detect "WSJT-X is listening but decoding badly" -- but
it converts a class of failure that used to require a human staring at a console into one
the orchestrator itself will refuse to walk through.

CORRECTED 2026-08-06 22:49 UTC (Architect,
`2026-08-06-2249-architect-to-qa-m3-void-preflight-desync.md`): the original version of this
check inserted a 10.0s blocking `time.sleep()` between two `play()` calls to cover the
decode-latency wait, which desynchronised every cycle afterward from the 15s UTC slot grid
by that same 10s (each `play()` call is itself phase-locked, occupying exactly 15.000s -- a
sleep between two of them is dead time the grid does not expect). This VOIDed the first M3
run (see the correction note). `play_pass_guarded()` also now asserts, at the end of every
pass, that total playback time did not exceed 20 cycles' worth of grid time by more than
`DTtol` (3.0s) -- see the assertion at the end of this function -- so this class of defect
cannot recur silently.

NFR-021: no message text is ever read, printed, or written by this module; it never opens
ALL.TXT for anything other than `os.stat()` (size/mtime), which carries no message content.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import wavfile

REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_EXE = (REPO_ROOT / "src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish"
              / "OpenWSFZ.Daemon.exe")

SLOT_SECONDS = 15
SAMPLE_RATE_HZ = 12000
OUTPUT_DEVICE_SUBSTR = "CABLE Input"
INPUT_DEVICE_SUBSTR = "CABLE Output"
PLAYBACK_PEAK = 0.9
FLUSH_WAIT_S = 3.0
STARTUP_WARMUP_S = 4.0

# CORRECTED 2026-08-06 22:49 UTC (Architect,
# 2026-08-06-2249-architect-to-qa-m3-void-preflight-desync.md): the original preflight
# check inserted a 10.0s time.sleep() (WSJTX_DECODE_LATENCY_SLACK_S + PREFLIGHT_EXTRA_WAIT_S)
# INSIDE the playback loop, after cycle 2. play() is phase-locked to the 15s UTC slot grid
# (each call occupies exactly 15.000s); a blocking sleep between two play() calls pushes
# every subsequent cycle 10s late relative to that grid, far outside WSJT-X's DTtol=3.0s.
# This silently desynchronised every M3 run from cycle 3 onward and produced the VOIDed
# "s_low=0.217 / instrument suspect" result. Fix: no sleep at all -- the 15s occupied by
# playing the NEXT cycle already covers WSJT-X's decode latency at zero timing cost, so the
# liveness check simply moves one cycle later. WSJTX_DECODE_LATENCY_SLACK_S and
# PREFLIGHT_EXTRA_WAIT_S are deleted, not zeroed, so a later edit cannot reintroduce a
# nonzero sleep here by accident.
PREFLIGHT_CYCLES = 2  # cycles played before the liveness check begins watching

WSJTX_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")


class PreflightAbort(RuntimeError):
    """Raised by play_pass_guarded() when WSJT-X shows no sign of life partway through a
    pass. Carries enough state for the caller to log/escalate without re-deriving it."""

    def __init__(self, label: str, cycles_played: int, baseline_size: int, observed_size: int):
        super().__init__(
            f"[{label}] WSJT-X ALL.TXT did not grow after {cycles_played} cycles "
            f"({baseline_size} -> {observed_size} bytes). Monitor may not be enabled, or "
            f"WSJT-X is not listening on {INPUT_DEVICE_SUBSTR}. Aborting this pass rather "
            f"than playing the remaining cycles blind."
        )
        self.label = label
        self.cycles_played = cycles_played
        self.baseline_size = baseline_size
        self.observed_size = observed_size


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Machine facts (mechanical, per spec SS6.1 -- shell out to the exact command named there
# so the recorded C is traceable to the spec text, not to Python's own cpu_count()).
# ---------------------------------------------------------------------------
def get_logical_processor_count() -> int:
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        c = int(out.stdout.strip())
        if c > 0:
            return c
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: PowerShell CIM query for logical processor count failed ({exc}); "
            f"falling back to os.cpu_count()")
    c = os.cpu_count()
    if not c:
        raise RuntimeError("Could not determine logical processor count by any method")
    return c


def get_cpu_utilization_percent() -> float | None:
    """Point-in-time total CPU utilisation via WMI, for the 'record actual achieved CPU
    utilisation' requirement in M4 SS6.1. Best-effort: returns None on any failure rather
    than aborting a run over a metrics-collection hiccup."""
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage "
             "-Average).Average"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        return float(out.stdout.strip())
    except Exception as exc:  # noqa: BLE001
        log(f"WARNING: CPU utilisation sample failed ({exc})")
        return None


# ---------------------------------------------------------------------------
# Daemon lifecycle (unmodified from run_cross_decode_replay.py)
# ---------------------------------------------------------------------------
def start_daemon(run_dir: Path, port: int) -> subprocess.Popen:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "config.json"
    stdout_path = run_dir / "daemon_stdout.log"
    proc = subprocess.Popen(
        [str(DAEMON_EXE), "--config", str(config_path), "--port", str(port)],
        stdout=open(stdout_path, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    log(f"Daemon launched, pid={proc.pid}, port={port}, stdout -> {stdout_path}")
    return proc


def wait_ready(base_url: str, timeout: float = 45.0) -> None:
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/api/v1/status", timeout=2)
            if r.status_code == 200:
                log(f"Daemon ready: {r.json()}")
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Daemon did not become ready in time")


def configure_daemon(base_url: str, log_dir: Path, all_txt_path: Path) -> None:
    import requests
    devices = requests.get(f"{base_url}/api/v1/audio/devices", timeout=5).json()
    match = next((d for d in devices if INPUT_DEVICE_SUBSTR.lower() in d["name"].lower()), None)
    if match is None:
        names = [d["name"] for d in devices]
        raise RuntimeError(f"No capture device matching '{INPUT_DEVICE_SUBSTR}': {names}")
    log(f"Capture device: {match['name']} ({match['id']})")

    cfg = requests.get(f"{base_url}/api/v1/config", timeout=5).json()
    cfg["audioDeviceId"] = match["id"]
    cfg["audioDeviceFriendlyName"] = match["name"]
    cfg["logging"]["fileEnabled"] = True
    cfg["logging"]["fileLogLevel"] = "Debug"
    cfg["logging"]["directory"] = str(log_dir)
    cfg["decodeLog"]["enabled"] = True
    cfg["decodeLog"]["path"] = str(all_txt_path)
    cfg["decodeLog"]["dialFrequencyMHz"] = 14.074

    r = requests.post(f"{base_url}/api/v1/config", json=cfg, timeout=10)
    r.raise_for_status()
    log("Config applied (CABLE Output + Debug file logging + ALL.TXT logging).")

    r = requests.post(f"{base_url}/api/v1/decode/start", timeout=10)
    r.raise_for_status()
    log("Decode started.")


def stop_daemon(base_url: str, proc: subprocess.Popen) -> None:
    import requests
    try:
        requests.post(f"{base_url}/api/v1/decode/stop", timeout=5)
    except Exception as exc:  # noqa: BLE001
        log(f"decode/stop call failed (continuing shutdown): {exc}")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    log(f"Daemon (pid={proc.pid}) stopped.")


def port_in_use(port: int) -> bool:
    """Per HK-019 (check for orphans before arming): refuse to start a run against a port
    that is already bound, rather than silently colliding with a leaked prior instance."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ---------------------------------------------------------------------------
# Audio (unmodified from run_cross_decode_replay.py)
# ---------------------------------------------------------------------------
def select_output_device() -> int:
    import sounddevice as sd
    devices = sd.query_devices()
    matches = [(i, d) for i, d in enumerate(devices)
               if OUTPUT_DEVICE_SUBSTR.lower() in d["name"].lower()
               and d["max_output_channels"] > 0]
    if not matches:
        raise RuntimeError(f"No output device matching '{OUTPUT_DEVICE_SUBSTR}'")
    idx, d = matches[0]
    log(f"Output device: [{idx}] {d['name']}")
    return idx


def load_wav_normalised(path: Path) -> np.ndarray:
    sr, data = wavfile.read(path)
    if sr != SAMPLE_RATE_HZ:
        raise RuntimeError(f"{path}: unexpected sample rate {sr} (expected {SAMPLE_RATE_HZ})")
    x = data.astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0.0:
        x = x * (PLAYBACK_PEAK / peak)
    return x.astype(np.float32)


def play(samples: np.ndarray, device_idx: int) -> None:
    import sounddevice as sd
    sd.play(samples, samplerate=SAMPLE_RATE_HZ, device=device_idx, blocking=True)
    sd.wait()


def next_boundary() -> float:
    now_s = int(time.time())
    rem = now_s % SLOT_SECONDS
    if rem == 0:
        return float(now_s + SLOT_SECONDS)
    return float(now_s + (SLOT_SECONDS - rem))


def wait_for_boundary(ts: float, prewarm: float = 0.5) -> None:
    remaining = (ts - prewarm) - time.time()
    if remaining > 0:
        time.sleep(remaining)


def _wsjtx_size() -> int:
    try:
        return WSJTX_ALL_TXT.stat().st_size
    except FileNotFoundError:
        return 0


def play_pass_guarded(wav_dir: Path, output_device_idx: int, label: str,
                       window: list[str]) -> tuple[datetime.datetime, datetime.datetime]:
    """Plays `window` (list of .wav filenames) out to output_device_idx, boundary-aligned.
    Raises PreflightAbort if WSJT-X shows no sign of life after PREFLIGHT_CYCLES cycles."""
    baseline_size = _wsjtx_size()
    boundary = next_boundary()
    log(f"[{label}] waiting for cycle boundary at {boundary} (in {boundary - time.time():.1f}s)")
    wait_for_boundary(boundary)
    pass_start = datetime.datetime.now(datetime.timezone.utc)
    log(f"[{label}] playback starting, {len(window)} cycles ({len(window) * SLOT_SECONDS}s), "
        f"WSJT-X ALL.TXT baseline size={baseline_size}")

    for i, fname in enumerate(window):
        samples = load_wav_normalised(wav_dir / fname)
        play(samples, output_device_idx)              # 15.000s, phase-locked -- no sleep
                                                        # is ever inserted between play()
                                                        # calls, so the loop stays locked to
                                                        # the UTC slot grid throughout.

        # Check one full cycle AFTER the preflight cycles have played. The 15s of the
        # cycle just played is itself the decode-latency slack -- no sleep, so playback
        # stays locked to the UTC slot grid. (Architect fix, 22:49 UTC note, SS5.)
        if i == PREFLIGHT_CYCLES:
            observed = _wsjtx_size()
            if observed <= baseline_size:
                raise PreflightAbort(label, i + 1, baseline_size, observed)
            log(f"[{label}] preflight OK after {i + 1} cycles: WSJT-X ALL.TXT grew "
                f"{baseline_size} -> {observed} bytes")

    pass_end = datetime.datetime.now(datetime.timezone.utc)
    log(f"[{label}] playback done: {pass_start.isoformat()} -> {pass_end.isoformat()}")

    # Mandatory post-fix assertion (SS5.1): DTtol is 3.0s -- if playback ever again drifts
    # this far off the UTC slot grid, every cycle past the drift is misaligned and no count
    # extracted from it means anything. This alone would have caught the original defect on
    # run 1, rather than needing three full runs and an Architect review to surface it.
    excess = (pass_end - pass_start).total_seconds() - len(window) * SLOT_SECONDS
    assert excess < 3.0, (
        f"[{label}] playback ran {excess:.2f}s over {len(window)} x {SLOT_SECONDS}s -- "
        f"playback has drifted off the UTC slot grid and every cycle after the drift is "
        f"misaligned"
    )
    log(f"[{label}] phase-lock OK: {excess:.2f}s excess over {len(window) * SLOT_SECONDS}s "
        f"nominal (< 3.0s DTtol)")

    time.sleep(FLUSH_WAIT_S)
    return pass_start, pass_end


def run_single_pass(run_dir: Path, port: int, wav_dir: Path, window: list[str],
                     label: str) -> dict:
    """Full daemon-up / preflight-guarded-playback / daemon-down cycle for one pass. Returns
    a dict with pass_start/pass_end (isoformat) and our_all_txt path, or with an "aborted"
    key set (True) and no pass_start/pass_end if the preflight check fired.

    Raises for anything else that goes wrong (daemon failed to start, no capture device,
    etc.) -- those are not "the experiment produced an inconclusive result", they are "the
    experiment did not run", and the orchestrator must not treat them the same way."""
    if port_in_use(port):
        raise RuntimeError(f"port {port} already in use -- a prior instance may not have "
                            f"shut down cleanly; refusing to start (HK-019)")

    run_dir.mkdir(parents=True, exist_ok=True)
    our_all_txt = run_dir / "our_ALL.TXT"
    base_url = f"http://127.0.0.1:{port}"

    proc = start_daemon(run_dir, port)
    aborted = False
    pass_start = pass_end = None
    try:
        wait_ready(base_url)
        configure_daemon(base_url, run_dir / "logs", our_all_txt)
        time.sleep(STARTUP_WARMUP_S)
        output_device_idx = select_output_device()
        try:
            pass_start, pass_end = play_pass_guarded(wav_dir, output_device_idx, label, window)
        except PreflightAbort as exc:
            log(f"ABORT: {exc}")
            aborted = True
    finally:
        stop_daemon(base_url, proc)

    result = {
        "run_dir": str(run_dir),
        "our_all_txt": str(our_all_txt),
        "label": label,
        "port": port,
        "aborted": aborted,
    }
    if not aborted:
        result["pass_start"] = pass_start.isoformat()
        result["pass_end"] = pass_end.isoformat()
        (run_dir / "pass_window.json").write_text(json.dumps(
            {"label": label, "pass_start": pass_start.isoformat(),
             "pass_end": pass_end.isoformat(), "window": window}, indent=2))
    return result
