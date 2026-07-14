#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of D-CALLER-018/016
(dev-task 2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md) against a real, isolated
OpenWSFZ.Daemon instance.

WHY THIS EXISTS: dev-task section 5 states plainly that this defect was only caught by reading a
real operating log, not by unit tests — every existing D-CALLER-013 unit test passed the whole
time this was broken, because none of them exercised "Abort while a target is armed but the
service is already Idle." This script reproduces that exact production sequence
(logs/openswfz-20260712T211150Z.log, CX1RL/23:18:30-23:19:00) against a real running daemon over
its real HTTP/WebSocket API, with a real background service loop and real wall-clock FT8 cycle
timing (no FakeTimeProvider) — not a mock. Modelled on
qa/tx-keying-live-verify/live_verify_keying.py's precedent (real isolated daemon, real audio
device via AudioOnlyPttController, no CAT/serial rig or virtual-audio-cable required since this
defect lives entirely in QsoAnswererService's Idle-state bookkeeping, not the decoder).

WHAT IT PROVES, IN TWO PHASES:

  Phase A (sanity control + AC-3 live regression): arms a pending CQ target timely (< 2.0 s into
    its answer window) so it fires immediately — proving the harness can produce a REAL keyed
    transmission (ruling out "audio device silently failed to open" as a false PASS) — then
    calls the dedicated Abort endpoint mid-transmission and confirms KeyUp/Idle follow promptly.
    This is the AC-3 regression: AbortAsync while genuinely mid-TX must keep working exactly as
    before the fix.

  Phase B (the actual bug, AC-1 live): arms a second, different pending CQ target late (> 2.0 s
    into its answer window) so the late-start guard defers it — reproducing "pending target ...
    late start ... deferring to next occurrence" from the log while the service sits Idle with
    the target still armed. Then hammers the dedicated Abort endpoint (matching the log's 14
    no-op clicks) while Idle, then waits past the next occurrence of that target's matching-phase
    window (~30 s later) and confirms NO transmission fires and the partner never appears in any
    txState broadcast — the exact "no recourse" defect from the log, now fixed.

  AC-2 (jump-in / EngageAtAsync) is deliberately NOT exercised live here: AbortAsync's fix clears
  _pendingTargetCallsign and _jumpPartner in the same unconditional lock block (same code path,
  same guard removed), and the jump-in unit test
  (AbortAsync_WhileIdleWithDeferredJumpInTarget_ClearsTarget_NoSubsequentTx) was confirmed to FAIL
  against the pre-fix code and PASS against the fix (see PR description) — reproducing it live via
  engage-decode's directed-message dispatch would materially lengthen this script for coverage
  that unit tests already prove is code-identical to Phase B below.

REQUIRES: the Release daemon built (`dotnet build OpenWSFZ.slnx -c Release` from the repo root —
this script does not build it for you) and a real audio output device (does not need to be
audible or a virtual cable — CQ transmission via AudioOnlyPttController does not require a decode
input).

Exit code 0 on PASS, 1 on FAIL, 2 if the environment prerequisites aren't met (e.g. no Release
binary found) — the report still gets written in the exit-2 case, marked
ENVIRONMENT-UNAVAILABLE, so a CI-less environment doesn't produce a false PASS or a
silently-missing report.
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

# Windows console default (cp1252/OEM) cannot encode the — / ≤ characters used in this script's
# own notes strings; reconfigure stdout/stderr to UTF-8 so `print()` never crashes mid-report
# (the report FILE is always UTF-8 regardless — this only affects console echo).
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

PORT = 18768   # distinct scratch port from decode-filter-synth-verify's 18765 / tx-keying's 18767
BASE = f"http://127.0.0.1:{PORT}"

OUR_CALLSIGN   = "Q1OFZ"
OUR_GRID       = "JO33"
PHASE_A_TARGET = "Q9CTRL"   # sanity-control target, timely arm, aborted mid-TX (AC-3 live)
PHASE_B_TARGET = "Q9BUG"    # the actual D-CALLER-018 repro target, late arm, hammered while Idle

MAX_LATE_START_SECONDS = 2.0   # must track QsoAnswererService.cs's MaxLateStartSeconds (D-CALLER-016)

# Tolerant of whatever dash character actually lands in the console sink: the source uses an
# em dash (—), but Windows console best-fit fallback encoding can silently substitute a plain
# ASCII hyphen (confirmed precedent: qa/tx-keying-live-verify/live_verify_keying.py's own
# KEYDOWN_START_RE comment) — match on the surrounding words only, not the punctuation.
LATE_START_LOG_RE = re.compile(
    r"pending target '(?P<callsign>\S+)'.*?late start \((?P<secs>[\d.]+) s into window\).*?"
    r"deferring to next occurrence")
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
    """Prefers a real virtual-cable/voicemeeter/speakers device over devices[0], which can be a
    stale/disconnected virtual device that silently fails to open — see
    qa/tx-keying-live-verify/live_verify_keying.py's precedent for why devices[0] is unsafe."""
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
        "# D-CALLER-018/016 — Abort hard-stop live verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/d-caller-018-abort-hard-stop-live-verify/live_verify_abort_hardstop.py`",
        f"- **Dev-task:** `dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md` §5",
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


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    try:
        binary = resolve_daemon_binary()
    except FileNotFoundError as e:
        fname = write_report("ENVIRONMENT-UNAVAILABLE", [], environment_note=str(e))
        print(f"ENVIRONMENT UNAVAILABLE — report written to {fname}")
        return 2

    binary_mtime = datetime.fromtimestamp(binary.stat().st_mtime, tz=timezone.utc)
    source_file = REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "QsoAnswererService.cs"
    source_mtime = (datetime.fromtimestamp(source_file.stat().st_mtime, tz=timezone.utc)
                     if source_file.exists() else None)

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-abort-hardstop-verify-"))
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
            "logLevel": "Debug",   # Debug so the "late start ... deferring" line is captured
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
        notes.append(f"QsoAnswererService.cs last-write time (UTC): "
                      f"`{source_mtime.isoformat() if source_mtime else 'unknown'}`")
        notes.append(f"Daemon process start time (UTC): `{proc_start_time.isoformat()}`")
        notes.append(
            f"Rebuild check: compiled binary postdates the source edits = "
            f"`{binary_mtime >= source_mtime if source_mtime else 'unknown'}`; "
            f"process started after binary was built = `{proc_start_time >= binary_mtime}`")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase A: sanity control + AC-3 live regression — timely arm fires
        # immediately (proves the harness produces a real keyed transmission),
        # then Abort mid-TX must stop it promptly exactly as before the fix.
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase A — sanity control (timely arm) + AC-3 live regression (abort mid-TX)")
        notes.append("")

        nb = next_boundary()
        sleep_until(nb + timedelta(milliseconds=150))
        arm_a_time = datetime.now(timezone.utc)
        window_a_start = floor15(arm_a_time)
        cq_cycle_a = window_a_start - timedelta(seconds=15)
        secs_in_a = (arm_a_time - window_a_start).total_seconds()

        notes.append(
            f"Arming `{PHASE_A_TARGET}` at `{iso_z(arm_a_time)}` — {secs_in_a:.2f} s into window "
            f"`{iso_z(window_a_start)}` (timely, ≤ {MAX_LATE_START_SECONDS} s) — expect immediate fire.")

        status_a, _ = http_post("/api/v1/tx/answer-cq", {
            "callsign": PHASE_A_TARGET,
            "frequencyHz": 1500.0,
            "cqCycleStartUtc": iso_z(cq_cycle_a),
        })
        notes.append(f"POST /api/v1/tx/answer-cq ({PHASE_A_TARGET}) → HTTP {status_a}")

        # Wait for a real keying:true event for PHASE_A_TARGET.
        deadline = time.time() + 5
        saw_keying_true_a = False
        while time.time() < deadline:
            for t, e in events:
                if t >= arm_a_time and e.get("keying") is True and e.get("partner") == PHASE_A_TARGET:
                    saw_keying_true_a = True
                    break
            if saw_keying_true_a:
                break
            time.sleep(0.1)
        notes.append(f"Real `keying: true` observed for `{PHASE_A_TARGET}`: `{saw_keying_true_a}`")

        # Abort mid-TX (AC-3 live regression).
        abort_mid_tx_time = datetime.now(timezone.utc)
        status_abort_a, _ = http_post("/api/v1/tx/abort")
        notes.append(f"POST /api/v1/tx/abort (mid-TX, at `{iso_z(abort_mid_tx_time)}`) → HTTP {status_abort_a}")

        deadline = time.time() + 5
        saw_keying_false_after_abort_a = False
        while time.time() < deadline:
            for t, e in events:
                if t >= abort_mid_tx_time and e.get("keying") is False:
                    saw_keying_false_after_abort_a = True
                    break
            if saw_keying_false_after_abort_a:
                break
            time.sleep(0.1)
        notes.append(
            f"`keying: false` observed after mid-TX abort: `{saw_keying_false_after_abort_a}`")

        time.sleep(0.5)
        status_a_final = http_get("/api/v1/tx/status")
        notes.append(f"GET /api/v1/tx/status after Phase A abort: `{status_a_final}`")
        phase_a_ok = (
            saw_keying_true_a
            and saw_keying_false_after_abort_a
            and status_a_final.get("state") == "Idle"
        )
        notes.append(f"**Phase A result: {'PASS' if phase_a_ok else 'FAIL'}**")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase B: the actual D-CALLER-018 defect — late arm defers, then the
        # dedicated Abort button is hammered while Idle with the target still
        # armed. Before the fix this was a no-op and the target fired anyway
        # ~30 s later; after the fix it must never fire.
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase B — D-CALLER-018 repro: hammer Abort while Idle with a deferred target")
        notes.append("")

        nb2 = next_boundary()
        late_offset = 7.0   # comfortably > MaxLateStartSeconds (2.0 s), comfortably < window (15 s)
        sleep_until(nb2 + timedelta(seconds=late_offset))
        arm_b_time = datetime.now(timezone.utc)
        window_b_start = floor15(arm_b_time)
        cq_cycle_b = window_b_start - timedelta(seconds=15)
        secs_in_b = (arm_b_time - window_b_start).total_seconds()

        notes.append(
            f"Arming `{PHASE_B_TARGET}` at `{iso_z(arm_b_time)}` — {secs_in_b:.2f} s into window "
            f"`{iso_z(window_b_start)}` (late, > {MAX_LATE_START_SECONDS} s) — expect deferral, no fire.")

        status_b, _ = http_post("/api/v1/tx/answer-cq", {
            "callsign": PHASE_B_TARGET,
            "frequencyHz": 1600.0,
            "cqCycleStartUtc": iso_z(cq_cycle_b),
        })
        notes.append(f"POST /api/v1/tx/answer-cq ({PHASE_B_TARGET}) → HTTP {status_b}")

        # Give the wakeup channel a moment to be processed, then check for the deferral log line.
        time.sleep(1.0)
        log_text_mid = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
        defer_match = None
        for m in LATE_START_LOG_RE.finditer(log_text_mid):
            if m.group("callsign") == PHASE_B_TARGET:
                defer_match = m
        notes.append(
            f"Late-start deferral log line found for `{PHASE_B_TARGET}`: `{bool(defer_match)}`"
            + (f" ({defer_match.group('secs')} s into window)" if defer_match else ""))

        # Confirm no fire happened yet.
        no_fire_yet = not any(
            t >= arm_b_time and e.get("partner") == PHASE_B_TARGET and e.get("keying") is True
            for t, e in events)
        notes.append(f"No transmission for `{PHASE_B_TARGET}` fired on the first (late) window: `{no_fire_yet}`")

        # Hammer the dedicated Abort button while Idle with the target still armed — matches the
        # log's 14 no-op clicks.
        hammer_start = datetime.now(timezone.utc)
        hammer_statuses = []
        for _ in range(14):
            st, _ = http_post("/api/v1/tx/abort")
            hammer_statuses.append(st)
            time.sleep(0.1)
        hammer_end = datetime.now(timezone.utc)
        notes.append(
            f"Hammered POST /api/v1/tx/abort x14 while Idle ({iso_z(hammer_start)} .. "
            f"{iso_z(hammer_end)}) — statuses: {hammer_statuses}")

        # Wait past the NEXT occurrence of the matching-phase window (~30 s later) plus a buffer.
        next_matching_window = window_b_start + timedelta(seconds=30)
        wait_until = next_matching_window + timedelta(seconds=3)
        notes.append(
            f"Waiting until `{iso_z(wait_until)}` (next matching-phase window "
            f"`{iso_z(next_matching_window)}` + 3 s buffer) to confirm no re-engagement...")
        sleep_until(wait_until)

        log_text_final = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
        answering_match_after_hammer = None
        for m in ANSWERING_LOG_RE.finditer(log_text_final):
            if m.group("callsign") == PHASE_B_TARGET:
                answering_match_after_hammer = m
        no_fire_after_hammer = not any(
            t >= hammer_end and e.get("partner") == PHASE_B_TARGET
            for t, e in events)

        status_b_final = http_get("/api/v1/tx/status")
        notes.append(f"GET /api/v1/tx/status after wait: `{status_b_final}`")
        notes.append(
            f"'answering at ... phase' log line ever appeared for `{PHASE_B_TARGET}` "
            f"(would prove re-engagement): `{bool(answering_match_after_hammer)}`")
        notes.append(
            f"No WS txState event names `{PHASE_B_TARGET}` as partner after the abort hammer: "
            f"`{no_fire_after_hammer}`")

        phase_b_ok = (
            bool(defer_match)
            and no_fire_yet
            and all(s == 200 for s in hammer_statuses)
            and not answering_match_after_hammer
            and no_fire_after_hammer
            and status_b_final.get("state") == "Idle"
            and status_b_final.get("partner") is None
        )
        notes.append(f"**Phase B result: {'PASS' if phase_b_ok else 'FAIL'}**")
        notes.append("")

        stop_flag["stop"] = True
        if reader_errors:
            notes.append("**WS reader thread raised an exception:**")
            notes.append("```")
            notes.extend(reader_errors)
            notes.append("```")

        ok = phase_a_ok and phase_b_ok

        if not ok:
            log_lines = log_text_final.splitlines()
            tail = log_lines[-120:] if len(log_lines) > 120 else log_lines
            notes.append("")
            notes.append("**Daemon log tail (last 120 lines) — diagnostic aid on failure:**")
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
            stop_flag = locals().get("stop_flag")
            if stop_flag is not None:
                stop_flag["stop"] = True
            ws_client.close()
        if proc is not None and log_file is not None:
            stop_daemon(proc, log_file)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
