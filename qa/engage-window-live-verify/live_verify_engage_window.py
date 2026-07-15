#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of D-CALLER-021 ("engage-window" change) against a
real, isolated OpenWSFZ.Daemon instance.

WHY THIS EXISTS: design.md's own Risks/Trade-offs section flags that "today's evidence
characterises the old defer bug but never exercised an actual overrun scenario, since every fired
engage in the 2026-07-14 session was well within its window" — i.e. the window-boundary
truncation half of this change (TransmitAsync never keying past the window boundary) has NEVER
been exercised against real wall-clock timing, real audio playback duration, or a real running
daemon. Unit tests mock IPttController and a FakeTimeProvider, which proves the sample-buffer
arithmetic is correct but cannot prove the actual keyed transmission on a real audio device
respects the window boundary. tasks.md §6 (this project's standing convention for QSO-timing
defects, see D-CALLER-018 dev-task §5) requires this before the change is considered done.
Modelled directly on qa/d-caller-018-abort-hard-stop-live-verify/live_verify_abort_hardstop.py's
precedent (same daemon-process/WebSocket/report-writer scaffolding); only a real audio OUTPUT
device is required (CQ/answer transmission does not require a decode input or virtual-audio-cable
loopback — same posture as that script).

WHAT IT PROVES, IN THREE PHASES:

  Phase A (sanity control): a pending CQ target armed timely (0.3 s into its answer window) fires
    immediately with a FULL, untruncated transmission (~12.64 s keying:true -> keying:false). This
    rules out "audio device silently failed to open" as a false PASS and is the AC-4 regression
    (on-time transmissions are unaffected).

  Phase B (the actual fix, AC-1 + AC-3 live): a second, different pending CQ target armed LATE
    (7 s into its answer window — comfortably past the old MaxLateStartSeconds=2.0 s ceiling this
    change removed, comfortably short of the 15 s window) must fire IMMEDIATELY in that SAME
    window (no "late start ... deferring" log line, no 30 s wait) AND the resulting transmission
    must be TRUNCATED to fit the remaining ~8 s of window (measured keying:true -> keying:false
    duration must be materially shorter than Phase A's full-length duration, and must not overrun
    past the window boundary).

  Phase C (AC-2 regression, wrong-phase still waits): a third pending CQ target is armed for a
    phase that does NOT match the very next real decode-cycle boundary, confirming the phase check
    itself (untouched by this change) still correctly retains the target and waits for the next
    matching-phase window rather than firing early or being confused by the truncation logic.

REQUIRES: the Release daemon built (`dotnet build OpenWSFZ.slnx -c Release` from the repo root —
this script does not build it for you) and a real audio output device (does not need to be
audible or a virtual cable).

Exit code 0 on PASS, 1 on FAIL, 2 if the environment prerequisites aren't met (e.g. no Release
binary found) — the report still gets written in the exit-2 case, marked ENVIRONMENT-UNAVAILABLE.
"""
import base64
import json
import os
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "live-reports"

PORT = 18770   # distinct scratch port from the other live_verify_*.py scripts (18765/67/68/69)
BASE = f"http://127.0.0.1:{PORT}"

OUR_CALLSIGN   = "Q1OFZ"
OUR_GRID       = "JO33"
PHASE_A_TARGET = "Q9ONTM"   # sanity control — timely arm, expect full-length TX
PHASE_B_TARGET = "Q9LATE"   # the actual D-CALLER-021 repro — late arm, expect immediate+truncated
PHASE_C_TARGET = "Q9WRONG"  # AC-2 regression — wrong-phase arm, expect retained-then-fires

FT8_SIGNAL_DURATION_S = 12.64   # 79 symbols x 160 ms
WINDOW_S              = 15.0

# The exact log text this change REMOVES — if it ever appears, the old guard is somehow still
# present (regression against D-CALLER-021 §1).
OLD_LATE_START_LOG_RE = re.compile(r"late start \([\d.]+ s into window\).*?deferring to next occurrence")
ANSWERING_LOG_RE = re.compile(
    r"pending CQ target '(?P<callsign>\S+)' at \S+ Hz.*?answering at \S+ phase")


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def http_get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(path, body=None):
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def wait_for_daemon_ready(timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return http_get("/api/v1/status")
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.3)
    raise TimeoutError(f"Daemon did not respond on {BASE} within {timeout_s}s.")


# ── Audio device resolution (loopback-safe defaults — no cable required) ─────

INPUT_DEVICE_SUBSTRINGS  = ("cable output", "voicemeeter out")
OUTPUT_DEVICE_SUBSTRINGS = ("cable input", "voicemeeter in", "speakers")

def resolve_devices():
    devices = http_get("/api/v1/audio/devices")
    outputs = http_get("/api/v1/audio/output-devices")

    input_dev = next(
        (d for sub in INPUT_DEVICE_SUBSTRINGS for d in devices if sub in d["name"].lower()),
        devices[0] if devices else None)
    output_dev = next(
        (d for sub in OUTPUT_DEVICE_SUBSTRINGS for d in outputs if sub in d["name"].lower()),
        outputs[0] if outputs else None)
    return input_dev, output_dev


# ── Minimal dependency-free WebSocket client (RFC 6455) ──────────────────────
# Loopback connections bypass the SEC-002B passphrase gate server-side, so no auth frame needed.

class MinimalWsClient:
    def __init__(self, host, port, path):
        self._sock = socket.create_connection((host, port), timeout=10)
        self._sock.settimeout(1.0)
        self._buf = b""
        self._closed = False
        self._handshake(host, port, path)

    def _handshake(self, host, port, path):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")
        self._sock.sendall(req)

        self._sock.settimeout(10)
        while b"\r\n\r\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("Socket closed during WS handshake.")
            self._buf += chunk
        header_end = self._buf.index(b"\r\n\r\n") + 4
        headers = self._buf[:header_end].decode("iso-8859-1")
        self._buf = self._buf[header_end:]
        if " 101 " not in headers.split("\r\n")[0]:
            raise ConnectionError(f"WS handshake failed: {headers.splitlines()[0]!r}")
        self._sock.settimeout(1.0)

    def _recv_more(self):
        try:
            chunk = self._sock.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            self._closed = True
            return False
        self._buf += chunk
        return True

    def read_frame(self):
        while True:
            if len(self._buf) < 2:
                if not self._recv_more():
                    return None
                continue
            b0, b1 = self._buf[0], self._buf[1]
            opcode = b0 & 0x0F
            masked = (b1 & 0x80) != 0
            plen = b1 & 0x7F
            offset = 2
            if plen == 126:
                if len(self._buf) < offset + 2:
                    if not self._recv_more():
                        return None
                    continue
                plen = struct.unpack(">H", self._buf[offset:offset + 2])[0]
                offset += 2
            elif plen == 127:
                if len(self._buf) < offset + 8:
                    if not self._recv_more():
                        return None
                    continue
                plen = struct.unpack(">Q", self._buf[offset:offset + 8])[0]
                offset += 8
            mask_key = b""
            if masked:
                if len(self._buf) < offset + 4:
                    if not self._recv_more():
                        return None
                    continue
                mask_key = self._buf[offset:offset + 4]
                offset += 4
            if len(self._buf) < offset + plen:
                if not self._recv_more():
                    return None
                continue
            payload = self._buf[offset:offset + plen]
            if masked:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
            self._buf = self._buf[offset + plen:]

            if opcode == 0x8:   # close
                self._closed = True
                return None
            if opcode == 0x9:   # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x1:   # text
                return payload.decode("utf-8", errors="replace")
            continue

    def _send_frame(self, opcode, payload=b""):
        mask_key = os.urandom(4)
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        b0 = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", b0, 0x80 | length)
        elif length < 65536:
            header = struct.pack("!BBH", b0, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", b0, 0x80 | 127, length)
        self._sock.sendall(header + mask_key + masked_payload)

    def close(self):
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass


def ws_reader_thread(client, events, stop_flag, errors):
    import traceback
    try:
        while not stop_flag["stop"] and not client._closed:
            msg = client.read_frame()
            if msg is None:
                continue
            now = datetime.now(timezone.utc)
            try:
                parsed = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if parsed.get("type") == "txState":
                events.append((now, parsed))
    except Exception:
        errors.append(traceback.format_exc())


# ── FT8 15-second cycle helpers (must track QsoAnswererService.cs's IsAPhase/RoundDownTo15s) ─

def floor15(dt):
    sec = (dt.second // 15) * 15
    return dt.replace(second=sec, microsecond=0)

def is_a_phase(dt):
    return dt.second % 30 == 0

def next_boundary(now=None):
    now = now or datetime.now(timezone.utc)
    ws = floor15(now)
    nb = ws + timedelta(seconds=15)
    while nb <= now:
        nb += timedelta(seconds=15)
    return nb

def sleep_until(target_dt):
    now = datetime.now(timezone.utc)
    delta = (target_dt - now).total_seconds()
    if delta > 0:
        time.sleep(delta)

def iso_z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Daemon process management ─────────────────────────────────────────────────

def resolve_daemon_binary():
    exe_name = "OpenWSFZ.Daemon.exe" if platform.system() == "Windows" else "OpenWSFZ.Daemon"
    candidate = REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "bin" / "Release" / "net10.0" / exe_name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        "Release daemon binary not found. Build it first: "
        "dotnet build OpenWSFZ.slnx -c Release")

def start_daemon(binary, config_path, log_path):
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [str(binary), "--port", str(PORT), "--config", str(config_path)],
        stdout=log_file, stderr=subprocess.STDOUT, cwd=str(REPO_ROOT))
    return proc, log_file

def stop_daemon(proc, log_file):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    log_file.close()


# ── Report writer ─────────────────────────────────────────────────────────────

def write_report(status, timestamp_table, environment_note=None, extra_notes=None):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip() or "unknown"
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_ROOT),
                             capture_output=True, text=True).stdout.strip() or "unknown"
    fname = REPORTS_DIR / f"{ts.strftime('%Y-%m-%dT%H%M%SZ')}-{sha}.md"

    lines = [
        "# D-CALLER-021 (engage-window) — window-boundary truncation live verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/engage-window-live-verify/live_verify_engage_window.py`",
        f"- **Change:** `openspec/changes/engage-window` tasks.md §6",
        "",
    ]

    if environment_note:
        lines += ["## Environment", "", environment_note, ""]

    if timestamp_table:
        lines += ["## WebSocket `txState` events received (UTC wall clock)", "",
                   "| # | Wall-clock (UTC) | state | partner | keying |",
                   "|---|---|---|---|---|"]
        for i, (t, ev) in enumerate(timestamp_table, start=1):
            lines.append(
                f"| {i} | `{t.isoformat(timespec='milliseconds')}` | "
                f"`{ev.get('state')}` | `{ev.get('partner')}` | `{ev.get('keying')}` |")
        lines.append("")

    lines += ["## Result", "", f"**{status}**", ""]

    if extra_notes:
        lines += ["## Notes", "", extra_notes, ""]

    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname


def abort_and_wait_idle(timeout_s=10):
    """POSTs /tx/abort and polls /tx/status until State == 'Idle' (or timeout). Needed between
    phases: RetryCount=0 in this script's config means HandleWaitReportAsync's retry-exhaustion
    condition (`maxRetries > 0 && ...`) never trips on its own, so a completed transmission that
    nobody answers sits in WaitReport indefinitely unless explicitly aborted."""
    http_post("/api/v1/tx/abort")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st = http_get("/api/v1/tx/status")
        if st.get("state") == "Idle":
            return True
        time.sleep(0.1)
    return False


def keying_duration(events, target, since):
    """Finds the first keying:true -> keying:false pair for `target` occurring at/after `since`.
    Returns (true_time, false_time, duration_seconds) or (None, None, None) if not found."""
    true_time = None
    for t, e in events:
        if t < since or e.get("partner") != target:
            continue
        if true_time is None and e.get("keying") is True:
            true_time = t
            continue
        if true_time is not None and e.get("keying") is False:
            return true_time, t, (t - true_time).total_seconds()
    return None, None, None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    try:
        binary = resolve_daemon_binary()
    except FileNotFoundError as e:
        fname = write_report("ENVIRONMENT-UNAVAILABLE", [], environment_note=str(e))
        print(f"ENVIRONMENT UNAVAILABLE — report written to {fname}")
        return 2

    binary_mtime = datetime.fromtimestamp(binary.stat().st_mtime, tz=timezone.utc)
    source_files = [
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "QsoAnswererService.cs",
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "Ft8TimeHelper.cs",
    ]
    source_mtime = max(
        (datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) for f in source_files if f.exists()),
        default=None)

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-engage-window-verify-"))
    config_path = scratch / "config.json"
    logs_dir = scratch / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    daemon_log_path = scratch / "daemon.log"

    proc = None
    log_file = None
    ws_client = None
    notes = []
    ok = False

    try:
        # ── Phase 0: throwaway start, just to enumerate real audio devices ──
        config_path.write_text("{}", encoding="utf-8")
        proc, log_file = start_daemon(binary, config_path, daemon_log_path)
        wait_for_daemon_ready()
        input_dev, output_dev = resolve_devices()
        stop_daemon(proc, log_file)

        # ── Phase 1: write the FINAL config ──────────────────────────────────
        config = {
            "audioDeviceId": input_dev["id"] if input_dev else None,
            "audioOutputDeviceId": output_dev["id"] if output_dev else None,
            "port": PORT,
            "decodingEnabled": True,
            "logLevel": "Debug",
            "decodeLog": {
                "enabled": True,
                "path": str(logs_dir / "ALL.TXT").replace("\\", "/"),
                "dialFrequencyMHz": 7.074,
            },
            "tx": {
                "autoAnswer": False,   # armed at runtime via POST /tx/answer-cq below
                "callsign": OUR_CALLSIGN,
                "grid": OUR_GRID,
                "retryCount": 0,
                "watchdogMinutes": 4,
                "rxAudioOffsetHz": 1500,
                "txAudioOffsetHz": 1500,
                "holdTxFreq": False,
                "role": "Answerer",
                "callerPartnerSelect": "First",
                "qsoConfirmation": False,
            },
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        # ── Phase 2: the real, correctly-configured daemon start ────────────
        proc_start_time = datetime.now(timezone.utc)
        proc, log_file = start_daemon(binary, config_path, daemon_log_path)
        wait_for_daemon_ready()

        # ── Phase 3: WebSocket client + reader thread ────────────────────────
        ws_client = MinimalWsClient("127.0.0.1", PORT, "/api/v1/ws")
        events = []
        reader_errors = []
        stop_flag = {"stop": False}
        reader = threading.Thread(
            target=ws_reader_thread, args=(ws_client, events, stop_flag, reader_errors), daemon=True)
        reader.start()

        notes.append(f"Binary under test: `{binary}`")
        notes.append(f"Binary last-write time (UTC): `{binary_mtime.isoformat()}`")
        notes.append(
            f"QsoAnswererService.cs/Ft8TimeHelper.cs last-write time (UTC): "
            f"`{source_mtime.isoformat() if source_mtime else 'unknown'}`")
        notes.append(f"Daemon process start time (UTC): `{proc_start_time.isoformat()}`")
        notes.append(
            f"Rebuild check: compiled binary postdates the source edits = "
            f"`{binary_mtime >= source_mtime if source_mtime else 'unknown'}`; "
            f"process started after binary was built = `{proc_start_time >= binary_mtime}`")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase A: sanity control — timely arm fires immediately with a FULL,
        # untruncated transmission. Rules out "audio device silently failed to
        # open" as a false PASS, and is the AC-4 regression (on-time TX
        # unaffected).
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase A — sanity control (timely arm, 0.3 s in) — expect full-length TX")
        notes.append("")

        nb = next_boundary()
        sleep_until(nb + timedelta(milliseconds=300))
        arm_a_time = datetime.now(timezone.utc)
        window_a_start = floor15(arm_a_time)
        cq_cycle_a = window_a_start - timedelta(seconds=15)
        secs_in_a = (arm_a_time - window_a_start).total_seconds()

        notes.append(
            f"Arming `{PHASE_A_TARGET}` at `{iso_z(arm_a_time)}` — {secs_in_a:.2f} s into window "
            f"`{iso_z(window_a_start)}` — expect immediate fire, full ~{FT8_SIGNAL_DURATION_S} s TX.")

        status_a, _ = http_post("/api/v1/tx/answer-cq", {
            "callsign": PHASE_A_TARGET,
            "frequencyHz": 1500.0,
            "cqCycleStartUtc": iso_z(cq_cycle_a),
        })
        notes.append(f"POST /api/v1/tx/answer-cq ({PHASE_A_TARGET}) → HTTP {status_a}")

        # Wait for the full keying:true -> keying:false pair (up to ~16 s: full clip + margin).
        deadline = time.time() + 16
        true_a = false_a = dur_a = None
        while time.time() < deadline:
            true_a, false_a, dur_a = keying_duration(events, PHASE_A_TARGET, arm_a_time)
            if dur_a is not None:
                break
            time.sleep(0.1)
        notes.append(
            f"Phase A keying:true→false observed: `{true_a is not None and false_a is not None}`, "
            f"duration = `{dur_a:.2f}s`" if dur_a is not None else "Phase A keying pair NOT observed.")

        phase_a_ok = (
            dur_a is not None
            and dur_a >= (FT8_SIGNAL_DURATION_S - 1.0)   # full-length, generous jitter margin
        )
        notes.append(f"**Phase A result: {'PASS' if phase_a_ok else 'FAIL'}**")
        notes.append("")

        # RetryCount=0 means HandleWaitReportAsync's retry-exhaustion check never trips on its
        # own (maxRetries > 0 is false) — the completed TX sits in WaitReport (nobody answers a
        # scripted target) until explicitly aborted back to Idle before the next phase can arm.
        idle_after_a = abort_and_wait_idle()
        notes.append(f"Aborted back to Idle after Phase A: `{idle_after_a}`")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase B: the actual D-CALLER-021 fix — late arm (7 s into window,
        # comfortably past the old MaxLateStartSeconds=2.0 s ceiling) must fire
        # IMMEDIATELY in the SAME window (no deferral, no "late start ...
        # deferring" log line) AND the transmission must be truncated to fit
        # the remaining ~8 s of window.
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase B — late arm (7 s in) — expect immediate fire, TRUNCATED TX")
        notes.append("")

        nb2 = next_boundary()
        late_offset = 7.0
        sleep_until(nb2 + timedelta(seconds=late_offset))
        arm_b_time = datetime.now(timezone.utc)
        window_b_start = floor15(arm_b_time)
        cq_cycle_b = window_b_start - timedelta(seconds=15)
        secs_in_b = (arm_b_time - window_b_start).total_seconds()
        expected_remaining_b = WINDOW_S - secs_in_b

        notes.append(
            f"Arming `{PHASE_B_TARGET}` at `{iso_z(arm_b_time)}` — {secs_in_b:.2f} s into window "
            f"`{iso_z(window_b_start)}` (late — old guard would have deferred this ~30 s) — "
            f"expect immediate fire, TX truncated to ~{expected_remaining_b:.1f} s.")

        status_b, _ = http_post("/api/v1/tx/answer-cq", {
            "callsign": PHASE_B_TARGET,
            "frequencyHz": 1600.0,
            "cqCycleStartUtc": iso_z(cq_cycle_b),
        })
        notes.append(f"POST /api/v1/tx/answer-cq ({PHASE_B_TARGET}) → HTTP {status_b}")

        # Fires (if at all) within THIS window — wait up to ~expected_remaining_b + margin.
        deadline = time.time() + max(expected_remaining_b + 3.0, 5.0)
        true_b = false_b = dur_b = None
        while time.time() < deadline:
            true_b, false_b, dur_b = keying_duration(events, PHASE_B_TARGET, arm_b_time)
            if dur_b is not None:
                break
            time.sleep(0.1)

        fired_same_window = (
            true_b is not None and true_b < window_b_start + timedelta(seconds=WINDOW_S + 1.0))
        notes.append(
            f"Phase B keying:true observed: `{true_b is not None}`"
            + (f" at `{iso_z(true_b)}` (within window boundary + 1 s margin: `{fired_same_window}`)"
               if true_b is not None else ""))
        notes.append(
            f"Phase B keying:true→false duration: "
            f"`{dur_b:.2f}s`" if dur_b is not None else "Phase B keying pair NOT observed.")

        log_text_b = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
        old_guard_line_found = bool(OLD_LATE_START_LOG_RE.search(log_text_b))
        notes.append(
            f"Old 'late start ... deferring to next occurrence' log line ever appeared "
            f"(would prove the removed guard somehow still fires): `{old_guard_line_found}`")

        phase_b_ok = (
            true_b is not None
            and fired_same_window
            and dur_b is not None
            and dur_b < (FT8_SIGNAL_DURATION_S - 1.0)          # materially shorter than full-length
            and dur_b <= (expected_remaining_b + 1.5)           # did not overrun the window boundary
            and not old_guard_line_found
        )
        notes.append(f"**Phase B result: {'PASS' if phase_b_ok else 'FAIL'}**")
        notes.append("")

        idle_after_b = abort_and_wait_idle()
        notes.append(f"Aborted back to Idle after Phase B: `{idle_after_b}`")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase C: AC-2 regression — a target armed for a phase that mismatches
        # the window it's armed in must NOT fire via AnswerCqAsync's immediate
        # "wakeup" check, and must instead correctly wait for and fire on the
        # first (and, given only two alternating phases, necessarily the very
        # next) matching-phase boundary. Confirms the phase check itself
        # (untouched by this change) still works correctly alongside the new
        # truncation logic.
        #
        # NOTE on why this can only ever defer by ONE 15 s step, not two: with
        # only two phases (A/B), a mismatch against the CURRENT window's phase
        # is, by construction, a MATCH against the very next window's phase —
        # there is no way for AnswerCqAsync to arm a target that misses two
        # consecutive real-time opportunities in a row (unlike the old
        # unit-test-only TestSetPendingTarget path, which bypasses the wakeup
        # entirely and can be fed an arbitrarily-timed first batch). The
        # meaningful thing to prove live is narrower and still real: the
        # wakeup must NOT fire instantly just because a click landed on a
        # mismatching moment, and the very next boundary must still catch it.
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase C — wrong-phase arm — expect no instant fire, then fires at next boundary (AC-2)")
        notes.append("")

        # AnswerCqAsync computes pendingIsAPhase = !IsAPhase(cqCycleStart). ArmPendingTarget's
        # wakeup evaluates phase(window_c_start) (the window we're already 0.3 s into) — for that
        # check to MISMATCH (proving no instant fire), pendingIsAPhase must equal
        # !phase(window_c_start), i.e. IsAPhase(cq_cycle_c) must equal phase(window_c_start) — an
        # EVEN number of 15 s windows back (two windows / 30 s preserves phase).
        nb3 = next_boundary()
        sleep_until(nb3 + timedelta(milliseconds=300))
        arm_c_time = datetime.now(timezone.utc)
        window_c_start = floor15(arm_c_time)
        cq_cycle_c = window_c_start - timedelta(seconds=30)   # two windows back — same phase
        target_phase_is_a = not is_a_phase(cq_cycle_c)        # = pendingIsAPhase, per AnswerCqAsync
        secs_in_c = (arm_c_time - window_c_start).total_seconds()
        next_boundary_c = window_c_start + timedelta(seconds=15)

        notes.append(
            f"Arming `{PHASE_C_TARGET}` at `{iso_z(arm_c_time)}` — {secs_in_c:.2f} s into window "
            f"`{iso_z(window_c_start)}` (target phase = {'A' if target_phase_is_a else 'B'}, "
            f"mismatching the window we're already in — the wakeup must NOT fire instantly). Next "
            f"boundary `{iso_z(next_boundary_c)}` is the target's matching phase — expect it to "
            f"fire there, not before.")

        status_c, _ = http_post("/api/v1/tx/answer-cq", {
            "callsign": PHASE_C_TARGET,
            "frequencyHz": 1700.0,
            "cqCycleStartUtc": iso_z(cq_cycle_c),
        })
        notes.append(f"POST /api/v1/tx/answer-cq ({PHASE_C_TARGET}) → HTTP {status_c}")

        # Confirm no INSTANT fire via the wakeup — check shortly after arming, well before the
        # next real boundary.
        time.sleep(2.0)
        no_instant_fire = not any(
            t >= arm_c_time and e.get("partner") == PHASE_C_TARGET and e.get("keying") is True
            for t, e in events)
        notes.append(
            f"No transmission fired instantly (within 2 s of arming, i.e. via the mismatching "
            f"wakeup check): `{no_instant_fire}`")

        # Now wait for the next (matching-phase) boundary and confirm it DOES fire there. Deadline
        # must cover time-to-boundary PLUS the full ~12.64 s clip (this fires long enough after
        # arming that it is NOT truncated) plus margin — not just time-to-boundary alone.
        deadline = (time.time() + (next_boundary_c - datetime.now(timezone.utc)).total_seconds()
                    + FT8_SIGNAL_DURATION_S + 5.0)
        true_c = false_c = dur_c = None
        while time.time() < deadline:
            true_c, false_c, dur_c = keying_duration(events, PHASE_C_TARGET, arm_c_time)
            if dur_c is not None:
                break
            time.sleep(0.1)
        notes.append(
            f"Phase C keying:true observed at the matching-phase boundary: `{true_c is not None}`"
            + (f" at `{iso_z(true_c)}`" if true_c is not None else ""))

        phase_c_ok = (
            no_instant_fire
            and true_c is not None
            and true_c >= next_boundary_c - timedelta(milliseconds=500)   # small scheduling margin
        )
        notes.append(f"**Phase C result: {'PASS' if phase_c_ok else 'FAIL'}**")
        notes.append("")

        stop_flag["stop"] = True
        if reader_errors:
            notes.append("**WS reader thread raised an exception:**")
            notes.append("```")
            notes.extend(reader_errors)
            notes.append("```")

        ok = phase_a_ok and phase_b_ok and phase_c_ok

        if not ok:
            log_text_final = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
            log_lines = log_text_final.splitlines()
            tail = log_lines[-150:] if len(log_lines) > 150 else log_lines
            notes.append("")
            notes.append("**Daemon log tail (last 150 lines) — diagnostic aid on failure:**")
            notes.append("```")
            notes.extend(tail)
            notes.append("```")

        status = "PASS" if ok else "FAIL"
        timestamp_table = list(events)
        fname = write_report(status, timestamp_table, extra_notes="\n".join(notes))
        print(f"{status} — report written to {fname}")
        for line in notes:
            print(line)
        return 0 if ok else 1

    finally:
        if ws_client is not None:
            sf = locals().get("stop_flag")
            if sf is not None:
                sf["stop"] = True
            ws_client.close()
        if proc is not None and log_file is not None:
            stop_daemon(proc, log_file)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
