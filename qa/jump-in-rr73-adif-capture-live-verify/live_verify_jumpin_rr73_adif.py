#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of `fix-jump-in-rr73-adif-capture` against a real,
isolated OpenWSFZ.Daemon instance — task 6.5 in this change's tasks.md.

WHY THIS EXISTS: the source defect (dev-tasks/2026-07-16-jump-in-sendrr73-no-adif-record.md) was
found against a real QSO, not a unit test — `EngagePoint.SendRr73`'s mid-exchange jump-in
transmitted RR73 and aborted to Idle without ever writing a `QsoRecord`, even for a genuinely
completed exchange. tasks.md task 6.5 asks for exactly this shape to be recreated against a real
running daemon and a real audio device, with `ADIF.log` inspected afterwards, rather than trusted
from unit tests (which mock `IAdifLogWriter`/`ITxEventBus` and can't prove the file actually gets
written). Modelled on `qa/engage-window-live-verify/live_verify_engage_window.py`'s scaffolding
(same daemon-process/WebSocket/report-writer pattern).

WHAT IT PROVES, IN TWO PHASES:

  Phase 1 (recreate the incident's precondition): switch to Caller role via `POST
    /api/v1/tx/call-cq`, let the caller's own CQ session run with nobody answering, and let its
    watchdog (the minimum real value, 1 minute — `Math.Clamp(tx.WatchdogMinutes, 1, 60)`) expire
    mid-session. Confirms (a) the caller session is genuinely lost to its own watchdog (matching
    the original incident's "no response ... watchdog fires" shape) and (b) `QsoControllerRouter`
    auto-reverts the active role back to Answerer once Idle (D-CALLER-012's `OnBecameIdle`).

  Phase 2 (the actual fix under test): with the daemon back at Idle/Answerer, POST
    `/api/v1/tx/engage-decode` with a bare `"RRR"` payload — the exact payload type from the
    original incident (the Captain's real reply was a bare RRR, not a numeric report; see the
    dev-task's "Evidence" log excerpt) — simulating the double-click on the partner's reply row.
    This must: transmit a real RR73 over the configured audio output device (proves the jump-in
    still fires), and — the regression under test — write a real, well-formed record to
    `ADIF.log` with `RST_RCVD=RRR` (not a fabricated `+00` placeholder) and no `GRIDSQUARE` field
    (PartnerGrid correctly stays null on this path — not a gap, see the dev-task's "Aside"). A
    second sub-case repeats Phase 2 with a numeric roger report (`"R-05"`) against a different
    partner callsign, confirming `RST_RCVD=-05` (leading `R` stripped), the more general case
    covered by the new automated unit tests.

REQUIRES: the Release daemon built (`dotnet build OpenWSFZ.slnx -c Release` from the repo root —
this script does not build it for you) and a real audio output device (does not need to be
audible or a virtual cable; an input device is used too, for realism, but the jump-in phase
correctness does not depend on any real decode content — see the phase-alignment trick below).

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

PORT = 18771   # distinct scratch port from the other live_verify_*.py scripts (18765/67/68/69/70)
BASE = f"http://127.0.0.1:{PORT}"

OUR_CALLSIGN     = "Q1OFZ"
OUR_GRID         = "JO33"
RRR_PARTNER      = "Q7GHK"   # bare-RRR case — matches the original incident's actual payload shape
NUMERIC_PARTNER  = "Q9NUM"   # numeric roger-report case — the more general path the unit tests cover

WATCHDOG_MINUTES = 1   # daemon clamps tx.watchdogMinutes to [1, 60] — this is the real minimum
FT8_SIGNAL_DURATION_S = 12.64   # 79 symbols x 160 ms — an RR73 transmission runs this long


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
        "# fix-jump-in-rr73-adif-capture — SendRr73 jump-in ADIF capture live verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/jump-in-rr73-adif-capture-live-verify/live_verify_jumpin_rr73_adif.py`",
        f"- **Change:** `openspec/changes/fix-jump-in-rr73-adif-capture` tasks.md task 6.5",
        "",
    ]

    if environment_note:
        lines += ["## Environment", "", environment_note, ""]

    if timestamp_table:
        lines += ["## WebSocket `txState` events received (UTC wall clock)", "",
                   "| # | Wall-clock (UTC) | role | state | partner | keying | abortReason |",
                   "|---|---|---|---|---|---|---|"]
        for i, (t, ev) in enumerate(timestamp_table, start=1):
            lines.append(
                f"| {i} | `{t.isoformat(timespec='milliseconds')}` | `{ev.get('role')}` | "
                f"`{ev.get('state')}` | `{ev.get('partner')}` | `{ev.get('keying')}` | "
                f"`{ev.get('abortReason')}` |")
        lines.append("")

    lines += ["## Result", "", f"**{status}**", ""]

    if extra_notes:
        lines += ["## Notes", "", extra_notes, ""]

    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname


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


def find_event(events, since, predicate, timeout_s):
    """Polls `events` (appended to live by the WS reader thread) until one at/after `since`
    satisfies `predicate`, or times out. Returns the matching (time, event) tuple or None."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for t, e in events:
            if t >= since and predicate(e):
                return t, e
        time.sleep(0.1)
    return None


# ── ADIF.log parsing ──────────────────────────────────────────────────────────

def parse_adif_records(adif_path):
    """Splits ADIF.log's tag-per-line-terminated-by-<EOR> format into a list of dicts
    (field name -> value), one per record. Minimal parser — good enough for assertions."""
    if not adif_path.exists():
        return []
    text = adif_path.read_text(encoding="ascii", errors="replace")
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = {}
        for m in re.finditer(r"<([A-Za-z_]+):(\d+)>", line):
            name = m.group(1).upper()
            length = int(m.group(2))
            start = m.end()
            fields[name] = line[start:start + length]
        if fields:
            records.append(fields)
    return records


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
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "QsoCallerService.cs",
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "QsoControllerRouter.cs",
        REPO_ROOT / "src" / "OpenWSFZ.Web" / "WebApp.cs",
    ]
    source_mtime = max(
        (datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) for f in source_files if f.exists()),
        default=None)

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-jumpin-rr73-verify-"))
    config_path = scratch / "config.json"
    logs_dir = scratch / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    daemon_log_path = scratch / "daemon.log"
    adif_path = logs_dir / "ADIF.log"

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

        # ── Phase 1 setup: write the FINAL config ────────────────────────────
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
                "autoAnswer": False,   # armed at runtime via POST /tx/call-cq below
                "callsign": OUR_CALLSIGN,
                "grid": OUR_GRID,
                "retryCount": 0,               # unlimited — watchdog alone ends the caller session
                "watchdogMinutes": WATCHDOG_MINUTES,
                "rxAudioOffsetHz": 1500,
                "txAudioOffsetHz": 1500,
                "holdTxFreq": False,
                "role": "Answerer",            # configured/default role — router reverts here
                "callerPartnerSelect": "First",
                "qsoConfirmation": False,      # write ADIF directly, observable without a browser
            },
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        # ── Phase 2: the real, correctly-configured daemon start ────────────
        proc_start_time = datetime.now(timezone.utc)
        proc, log_file = start_daemon(binary, config_path, daemon_log_path)
        wait_for_daemon_ready()

        # ── WebSocket client + reader thread ─────────────────────────────────
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
            f"QsoAnswererService.cs/QsoCallerService.cs/QsoControllerRouter.cs/WebApp.cs last-write "
            f"time (UTC): `{source_mtime.isoformat() if source_mtime else 'unknown'}`")
        notes.append(f"Daemon process start time (UTC): `{proc_start_time.isoformat()}`")
        notes.append(
            f"Rebuild check: compiled binary postdates the source edits = "
            f"`{binary_mtime >= source_mtime if source_mtime else 'unknown'}`; "
            f"process started after binary was built = `{proc_start_time >= binary_mtime}`")
        notes.append(f"ADIF.log resolved path: `{adif_path}`")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase 1: recreate the incident's precondition — a caller-side session
        # loses the exchange to its own watchdog, and the router reverts the
        # active role back to Answerer once Idle (D-CALLER-012).
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase 1 — caller-side CQ session lost to its own watchdog")
        notes.append("")

        phase1_start = datetime.now(timezone.utc)
        status_callcq, body_callcq = http_post("/api/v1/tx/call-cq")
        notes.append(f"POST /api/v1/tx/call-cq → HTTP {status_callcq}, body: `{body_callcq}`")

        # Confirm the router actually switched to Caller (role in the WS event, or via status poll).
        switched = find_event(
            events, phase1_start,
            lambda e: e.get("role") == "caller",
            timeout_s=20)
        notes.append(
            f"Observed role=caller via WS within 20 s: `{switched is not None}`"
            + (f" (first at `{iso_z(switched[0])}`, state=`{switched[1].get('state')}`)"
               if switched else ""))

        # Confirm a real CQ transmission actually happened. keying_duration() filters by exact
        # partner match, but the caller has no partner while calling CQ (Partner is only set once
        # a responder answers) — so check the keying:true transition directly instead.
        cq_keyed = find_event(
            events, phase1_start,
            lambda e: e.get("role") == "caller" and e.get("keying") is True,
            timeout_s=20)
        notes.append(f"Observed a real caller-role keying:true (CQ transmission fired): `{cq_keyed is not None}`")

        # Now wait for the watchdog to expire. QsoCallerService.SafeAbortToIdleAsync publishes
        # FIRST (role="caller", a non-null abortReason — "Watchdog timeout"), and the router's
        # RevertToConfiguredRole() then publishes a SEPARATE, later synthetic event
        # (role="answerer", abortReason ALWAYS null by design — see QsoControllerRouter.cs's
        # RevertToConfiguredRole comment). These are two distinct broadcasts, not one event with
        # both fields set — check for each independently rather than a single compound predicate.
        # WATCHDOG_MINUTES (clamped minimum 1) + generous margin for retry/report cadence.
        watchdog_deadline_s = WATCHDOG_MINUTES * 60 + 30
        notes.append(
            f"Waiting up to {watchdog_deadline_s}s for the watchdog ({WATCHDOG_MINUTES} min) to expire "
            f"(caller-side abort) and the router to revert to Answerer/Idle...")
        watchdog_lost = find_event(
            events, phase1_start,
            lambda e: e.get("role") == "caller" and e.get("state") == "Idle"
                      and e.get("abortReason") is not None,
            timeout_s=watchdog_deadline_s)
        notes.append(
            f"Observed the caller session's own watchdog-loss broadcast "
            f"(role=caller, state=Idle, non-null abortReason) within {watchdog_deadline_s}s: "
            f"`{watchdog_lost is not None}`"
            + (f" at `{iso_z(watchdog_lost[0])}`, abortReason=`{watchdog_lost[1].get('abortReason')}`"
               if watchdog_lost else ""))

        reverted = find_event(
            events, watchdog_lost[0] if watchdog_lost else phase1_start,
            lambda e: e.get("state") == "Idle" and e.get("role") == "answerer",
            timeout_s=10)
        notes.append(
            f"Observed the router's subsequent revert-to-Answerer broadcast (state=Idle, "
            f"role=answerer) within 10s of the watchdog loss: `{reverted is not None}`"
            + (f" at `{iso_z(reverted[0])}`" if reverted else ""))

        phase1_ok = switched is not None and cq_keyed is not None and watchdog_lost is not None and reverted is not None
        notes.append(f"**Phase 1 result: {'PASS' if phase1_ok else 'FAIL'}**")
        notes.append("")

        # Confirm we're genuinely back at Idle/Answerer via the HTTP status endpoint too (belt
        # and suspenders — the WS event proves the transition happened; this proves it stuck).
        status_after_p1 = http_get("/api/v1/tx/status")
        notes.append(f"GET /api/v1/tx/status after Phase 1: `{status_after_p1}`")
        idle_confirmed = (
            status_after_p1.get("state") == "Idle" and status_after_p1.get("role") == "answerer")
        notes.append(f"Confirmed Idle/answerer via HTTP status: `{idle_confirmed}`")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase 2a: the actual fix under test — a bare "RRR" jump-in (the exact
        # payload shape from the original incident). Simulates the operator
        # double-clicking the partner's reply row in the decode panel.
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase 2a — SendRr73 jump-in with a bare RRR (matches the original incident)")
        notes.append("")

        # Phase-alignment trick (mirrors qa/engage-window-live-verify Phase A): arm just after a
        # real 15 s boundary, with theirCycleStart set to the PREVIOUS window. EngageAtAsync's own
        # synchronous wakeup push (computed from real UtcNow at call time) then self-matches the
        # phase check, firing near-instantly without needing to wait for a real decode batch.
        nb_a = next_boundary()
        sleep_until(nb_a + timedelta(milliseconds=300))
        arm_a_time = datetime.now(timezone.utc)
        window_a_start = floor15(arm_a_time)
        their_cycle_a = window_a_start - timedelta(seconds=15)

        notes.append(
            f"Arming SendRr73 jump-in for `{RRR_PARTNER}` at `{iso_z(arm_a_time)}` "
            f"(theirCycleStart=`{iso_z(their_cycle_a)}`) with payload `\"RRR\"` — expect immediate fire.")

        status_a, body_a = http_post("/api/v1/tx/engage-decode", {
            "message": f"{OUR_CALLSIGN} {RRR_PARTNER} RRR",
            "frequencyHz": 1500.0,
            "cycleStartUtc": iso_z(their_cycle_a),
        })
        notes.append(f"POST /api/v1/tx/engage-decode ({RRR_PARTNER}, RRR) → HTTP {status_a}, body: `{body_a}`")

        keyed_a = find_event(
            events, arm_a_time,
            lambda e: e.get("partner") == RRR_PARTNER and e.get("keying") is True,
            timeout_s=10)
        notes.append(f"Observed real RR73 keying:true for {RRR_PARTNER}: `{keyed_a is not None}`")

        # Timeout must exceed the full ~12.64 s RR73 transmission itself (keyed_a only observes
        # keying:true, which fires the instant TX starts — Idle is only reached after the full
        # clip plays out, KeyUp, QsoComplete, and the ADIF write).
        idle_a = find_event(
            events, arm_a_time,
            lambda e: e.get("state") == "Idle" and e.get("partner") is None,
            timeout_s=FT8_SIGNAL_DURATION_S + 8.0)
        notes.append(f"Observed return to Idle after the jump-in: `{idle_a is not None}`")

        # Give AppendQsoAsync (async file I/O) a brief moment after Idle before reading the file.
        time.sleep(0.5)
        records_after_a = parse_adif_records(adif_path)
        record_a = next((r for r in records_after_a if r.get("CALL") == RRR_PARTNER), None)
        notes.append(f"ADIF.log records so far: {len(records_after_a)}")
        notes.append(f"Record for {RRR_PARTNER}: `{record_a}`")

        phase2a_ok = (
            keyed_a is not None
            and idle_a is not None
            and record_a is not None
            and record_a.get("RST_RCVD") == "RRR"
            and "GRIDSQUARE" not in record_a
        )
        notes.append(f"**Phase 2a result: {'PASS' if phase2a_ok else 'FAIL'}**")
        notes.append("")

        # ═══════════════════════════════════════════════════════════════════
        # Phase 2b: numeric roger-report jump-in ("R-05") against a different
        # partner — the more general case the new unit tests cover; confirms
        # the leading "R" is stripped, not just that bare RRR works.
        # ═══════════════════════════════════════════════════════════════════
        notes.append("### Phase 2b — SendRr73 jump-in with a numeric roger report (R-05)")
        notes.append("")

        nb_b = next_boundary()
        sleep_until(nb_b + timedelta(milliseconds=300))
        arm_b_time = datetime.now(timezone.utc)
        window_b_start = floor15(arm_b_time)
        their_cycle_b = window_b_start - timedelta(seconds=15)

        notes.append(
            f"Arming SendRr73 jump-in for `{NUMERIC_PARTNER}` at `{iso_z(arm_b_time)}` "
            f"(theirCycleStart=`{iso_z(their_cycle_b)}`) with payload `\"R-05\"` — expect immediate fire.")

        status_b, body_b = http_post("/api/v1/tx/engage-decode", {
            "message": f"{OUR_CALLSIGN} {NUMERIC_PARTNER} R-05",
            "frequencyHz": 1500.0,
            "cycleStartUtc": iso_z(their_cycle_b),
        })
        notes.append(f"POST /api/v1/tx/engage-decode ({NUMERIC_PARTNER}, R-05) → HTTP {status_b}, body: `{body_b}`")

        keyed_b = find_event(
            events, arm_b_time,
            lambda e: e.get("partner") == NUMERIC_PARTNER and e.get("keying") is True,
            timeout_s=10)
        notes.append(f"Observed real RR73 keying:true for {NUMERIC_PARTNER}: `{keyed_b is not None}`")

        idle_b = find_event(
            events, arm_b_time,
            lambda e: e.get("state") == "Idle" and e.get("partner") is None,
            timeout_s=FT8_SIGNAL_DURATION_S + 8.0)
        notes.append(f"Observed return to Idle after the jump-in: `{idle_b is not None}`")

        time.sleep(0.5)
        records_after_b = parse_adif_records(adif_path)
        record_b = next((r for r in records_after_b if r.get("CALL") == NUMERIC_PARTNER), None)
        notes.append(f"ADIF.log records so far: {len(records_after_b)}")
        notes.append(f"Record for {NUMERIC_PARTNER}: `{record_b}`")

        phase2b_ok = (
            keyed_b is not None
            and idle_b is not None
            and record_b is not None
            and record_b.get("RST_RCVD") == "-05"
            and "GRIDSQUARE" not in record_b
        )
        notes.append(f"**Phase 2b result: {'PASS' if phase2b_ok else 'FAIL'}**")
        notes.append("")

        stop_flag["stop"] = True
        if reader_errors:
            notes.append("**WS reader thread raised an exception:**")
            notes.append("```")
            notes.extend(reader_errors)
            notes.append("```")

        ok = phase1_ok and idle_confirmed and phase2a_ok and phase2b_ok

        if not ok:
            log_text_final = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
            log_lines = log_text_final.splitlines()
            tail = log_lines[-200:] if len(log_lines) > 200 else log_lines
            notes.append("")
            notes.append("**Daemon log tail (last 200 lines) — diagnostic aid on failure:**")
            notes.append("```")
            notes.extend(tail)
            notes.append("```")

        notes.append("")
        notes.append("**Full ADIF.log contents at end of run:**")
        notes.append("```")
        notes.append(adif_path.read_text(encoding="ascii", errors="replace") if adif_path.exists() else "(file does not exist)")
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
