#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of the #tx-enable-btn `Keying` signal
(dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A) against a real,
isolated OpenWSFZ.Daemon instance.

WHY THIS EXISTS: the prior redo (commit c5de90e) was handed back because it closed out a
live-verification requirement on the strength of "1008/1008 tests green" alone — every one of
those tests mocks IPttController, so none of them exercise real WASAPI timing or real
WebSocket delivery. This script does, for real:

  1. Locates the Release daemon binary and records its last-write time (proves the binary
     under test actually postdates the Keying source change, not a stale build).
  2. Starts a throwaway isolated instance just long enough to enumerate real audio devices
     (own scratch port/config directory — never touches the Captain's real
     %APPDATA%\\OpenWSFZ\\config.json).
  3. Writes an isolated config.json (own port, own decode-log directory, tx.autoAnswer=false
     initially — armed at runtime via POST /api/v1/tx/call-cq, the simplest real trigger that
     starts transmitting an actual CQ on the next FT8 cycle boundary with no decode input
     required).
  4. Starts the real daemon against that isolated config and opens a minimal, dependency-free
     WebSocket client (raw RFC 6455 handshake + frame parsing — no external package needed,
     since this repo's shared qa/rr-study venv does not carry a websocket client and this
     script should not need to touch it) against /api/v1/ws, recording the wall-clock
     timestamp and `keying` value of every `txState` event received.
  5. POSTs /api/v1/tx/call-cq once ready, then waits for a full Keying bracket (a `true` event
     followed by a `false` event) to arrive over the WebSocket, or times out.
  6. Independently parses the daemon's own stdout log for the
     "TX KeyDown — starting playback" and "TX KeyDown — playback completed." /
     "TX KeyUp — stopping playback." lines and their Serilog `HH:mm:ss` timestamps.
  7. Cross-checks: the WS `keying: true` event must arrive at or before (allowing ±1s for the
     log's second-only timestamp granularity) the "starting playback" log line, and the WS
     `keying: false` event must arrive at or after the matching completion/KeyUp log line.
  8. Writes a timestamped Markdown report to qa/tx-keying-live-verify/live-reports/, including
     the git commit this was run against and the full timestamp table, and tears everything
     down — the isolated daemon process and its scratch temp directory.

REQUIRES: the Release daemon built (`dotnet build src/OpenWSFZ.Daemon -c Release` from the
repo root — this script does not build it for you) and a real audio output device (does not
need to be audible or a virtual cable — CQ transmission does not require a decode input).

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
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "live-reports"

PORT = 18767   # distinct scratch port from decode-filter-synth-verify's 18765
BASE = f"http://127.0.0.1:{PORT}"

OUR_CALLSIGN = "Q1OFZ"
OUR_GRID     = "JO33"

# The source (AudioOnlyPttController.cs) logs these with an em dash ("—"), but the Windows
# console's best-fit fallback encoding (Console.OutputEncoding is the OEM code page, which
# cannot represent U+2014) silently substitutes a plain ASCII hyphen when Serilog writes to
# the console sink — confirmed against a real captured log during this script's own
# development. Match on the surrounding words only, tolerant of whatever punctuation actually
# lands between them, rather than pinning to one dash character.
KEYDOWN_START_RE  = re.compile(r"^\[(\d{2}:\d{2}:\d{2}) INF\] TX KeyDown.*starting playback", re.MULTILINE)
KEYDOWN_DONE_RE   = re.compile(r"^\[(\d{2}:\d{2}:\d{2}) INF\] TX KeyDown.*playback completed\.", re.MULTILINE)
KEYUP_RE          = re.compile(r"^\[(\d{2}:\d{2}:\d{2}) INF\] TX KeyUp.*stopping playback\.", re.MULTILINE)


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def http_get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(path, body=None):
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

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
    """Prefers a real virtual-cable/voicemeeter/speakers device (known-good, confirmed present
    on this machine per qa/decode-filter-synth-verify's precedent) over devices[0], which can be
    a stale/disconnected virtual device (e.g. an Oculus VR audio endpoint with no headset
    attached) that silently fails to open and produces zero decode batches — the actual root
    cause of this script's first failed run."""
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
# Loopback connections bypass the SEC-002B passphrase gate server-side (see
# WebApp.cs's auth middleware), so no auth frame is required here.

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

        # Read until end of HTTP headers.
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
        """Returns decoded text payload of the next complete text frame, or None if none
        is available right now (non-blocking-ish — caller should poll). Handles ping frames
        transparently (responds with pong); close frames set self._closed and return None."""
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
            # binary/pong/continuation — ignore, loop for next frame
            continue

    def _send_frame(self, opcode, payload=b""):
        # Client-to-server frames MUST be masked per RFC 6455.
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
    """Continuously polls the WS client for text frames, parsing txState events into
    `events` as (wall_clock_utc, parsed_dict) tuples. Runs until stop_flag['stop'] is set.
    Any exception is captured into `errors` (a list) rather than crashing the thread silently,
    so the main thread can surface it in the report instead of it vanishing into stderr."""
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


# ── Daemon process management ─────────────────────────────────────────────────

def resolve_daemon_binary():
    exe_name = "OpenWSFZ.Daemon.exe" if platform.system() == "Windows" else "OpenWSFZ.Daemon"
    candidate = REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "bin" / "Release" / "net10.0" / exe_name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        "Release daemon binary not found. Build it first: "
        "dotnet build src/OpenWSFZ.Daemon -c Release")

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
        "# tx-enable-btn Keying signal — live verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/tx-keying-live-verify/live_verify_keying.py`",
        f"- **Dev-task:** `dev-tasks/2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md` item A",
        "",
    ]

    if environment_note:
        lines += ["## Environment", "", environment_note, ""]

    if timestamp_table:
        lines += ["## WebSocket `txState` events received (UTC wall clock)", "",
                   "| # | Wall-clock (UTC) | state | role | keying |",
                   "|---|---|---|---|---|"]
        for i, (t, ev) in enumerate(timestamp_table, start=1):
            lines.append(
                f"| {i} | `{t.isoformat(timespec='milliseconds')}` | "
                f"`{ev.get('state')}` | `{ev.get('role')}` | `{ev.get('keying')}` |")
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

    # Rule out "stale binary" explicitly: the QsoAnswererService.cs/QsoCallerService.cs source
    # edits that add the Keying signal must predate the binary compiled from them. (main.js is
    # a separate, non-compiled static asset copied alongside the binary on every build — it is
    # checked independently below, not folded into this compiled-source check.)
    compiled_source_files = [
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "QsoAnswererService.cs",
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "QsoCallerService.cs",
    ]
    newest_source_mtime = max(
        (datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) for p in compiled_source_files if p.exists()),
        default=None)

    # The frontend asset is copied verbatim into the binary's output directory on every build —
    # confirm the copy actually happened by comparing it against the source file, independent of
    # the compiled-binary check above.
    web_main_js_src = REPO_ROOT / "web" / "js" / "main.js"
    web_main_js_copy = binary.parent / "web" / "js" / "main.js"
    web_asset_synced = (
        web_main_js_copy.exists()
        and web_main_js_src.exists()
        and web_main_js_copy.stat().st_mtime >= web_main_js_src.stat().st_mtime
    )

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-keying-verify-"))
    config_path = scratch / "config.json"
    logs_dir = scratch / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    daemon_log_path = scratch / "daemon.log"

    proc = None
    log_file = None
    ws_client = None
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
            "logLevel": "Information",
            "decodeLog": {
                "enabled": True,
                "path": str(logs_dir / "ALL.TXT").replace("\\", "/"),
                "dialFrequencyMHz": 7.074,
            },
            "tx": {
                "autoAnswer": False,   # armed at runtime via POST /tx/call-cq below
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

        # ── Phase 4: trigger a real CQ transmission ──────────────────────────
        http_post("/api/v1/tx/call-cq")

        # Wait for a full Keying bracket: a `true` event followed by a `false` event.
        deadline = time.time() + 40  # up to ~2 FT8 cycles of slack
        saw_true = False
        saw_true_to_false = False
        while time.time() < deadline:
            snapshot = list(events)
            true_idxs = [i for i, (_, e) in enumerate(snapshot) if e.get("keying") is True]
            if true_idxs:
                saw_true = True
                first_true = true_idxs[0]
                false_after = [i for i, (_, e) in enumerate(snapshot)
                                if i > first_true and e.get("keying") is False]
                if false_after:
                    saw_true_to_false = True
                    break
            time.sleep(0.2)

        # Give the log file a brief moment to receive/flush the matching lines.
        time.sleep(0.5)
        stop_flag["stop"] = True

        # ── Phase 5: parse the daemon's own log for the ground-truth lines ──
        log_text = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
        start_match = KEYDOWN_START_RE.search(log_text)
        done_match  = KEYDOWN_DONE_RE.search(log_text) or KEYUP_RE.search(log_text)

        http_post("/api/v1/tx/abort")

        timestamp_table = list(events)

        notes = [
            f"Binary under test: `{binary}`",
            f"Binary last-write time (UTC): `{binary_mtime.isoformat()}`",
            f"Newest of QsoAnswererService.cs/QsoCallerService.cs last-write time (UTC): "
            f"`{newest_source_mtime.isoformat() if newest_source_mtime else 'unknown'}`",
            f"Daemon process start time (UTC): `{proc_start_time.isoformat()}`",
            f"Rebuild check: compiled binary postdates the Keying source edits = "
            f"`{binary_mtime >= newest_source_mtime if newest_source_mtime else 'unknown'}`; "
            f"process started after binary was built = `{proc_start_time >= binary_mtime}`; "
            f"copied web/js/main.js asset is in sync with its source = `{web_asset_synced}`",
            "",
        ]
        if reader_errors:
            notes.append("**WS reader thread raised an exception:**")
            notes.append("```")
            notes.extend(reader_errors)
            notes.append("```")
        notes += [
            f"Log line 'TX KeyDown — starting playback' found: `{bool(start_match)}`"
            + (f", timestamp `{start_match.group(1)}`" if start_match else ""),
            f"Log line 'TX KeyDown — playback completed.' / 'TX KeyUp — stopping playback.' found: "
            f"`{bool(done_match)}`" + (f", timestamp `{done_match.group(1)}`" if done_match else ""),
            "",
            f"WS events observed: {len(timestamp_table)} total; "
            f"saw a `keying: true` event: `{saw_true}`; "
            f"saw a `keying: true` followed later by a `keying: false` event: `{saw_true_to_false}`",
        ]

        # ── Phase 6: the actual cross-check ──────────────────────────────────
        ok = bool(start_match) and bool(done_match) and saw_true_to_false

        if not ok:
            # Diagnostic aid: include the daemon's own log tail so a failure (e.g. no CQ ever
            # fired because the chosen audio device could not be opened) is debuggable directly
            # from the report rather than requiring a re-run with manual instrumentation.
            log_lines = log_text.splitlines()
            tail = log_lines[-60:] if len(log_lines) > 60 else log_lines
            notes.append("")
            notes.append("**Daemon log tail (last 60 lines) — diagnostic aid on failure:**")
            notes.append("```")
            notes.extend(tail)
            notes.append("```")

        if ok:
            true_events  = [(t, e) for t, e in timestamp_table if e.get("keying") is True]
            false_events = [(t, e) for t, e in timestamp_table if e.get("keying") is False]
            first_true_ts = true_events[0][0]
            # First keying:false AFTER the first keying:true.
            false_after_true = [t for t, _ in false_events if t > first_true_ts]

            # Reconstruct today's date for the log's HH:mm:ss (local time, no date/ms) so it is
            # directly comparable to the WS event's wall-clock timestamp. Both this script and
            # the daemon run on the same machine/local clock.
            local_today = datetime.now().date()

            def to_local_dt(hhmmss):
                h, m, s = (int(x) for x in hhmmss.split(":"))
                return datetime.combine(local_today, datetime.min.time()).replace(hour=h, minute=m, second=s)

            start_local = to_local_dt(start_match.group(1))
            done_local  = to_local_dt(done_match.group(1))

            first_true_local = first_true_ts.astimezone().replace(tzinfo=None)
            first_false_after_local = (
                false_after_true[0].astimezone().replace(tzinfo=None) if false_after_true else None
            )

            # ±1s tolerance: the daemon's console log line has only second-level (HH:mm:ss)
            # granularity, while the WS event has millisecond precision.
            tolerance = 1.0
            true_before_start = (
                first_true_local <= start_local + timedelta(seconds=tolerance)
            )
            false_after_done = (
                first_false_after_local is not None
                and first_false_after_local >= done_local - timedelta(seconds=tolerance)
            )

            notes.append("")
            notes.append(
                f"First `keying: true` WS event (local): `{first_true_local.isoformat()}` — "
                f"at or before 'starting playback' log line (`{start_local.isoformat()}`, "
                f"±{tolerance}s tolerance for the log's second-only precision): `{true_before_start}`"
            )
            notes.append(
                f"First `keying: false` WS event after that (local): "
                f"`{first_false_after_local.isoformat() if first_false_after_local else 'none'}` — "
                f"at or after the completion/KeyUp log line (`{done_local.isoformat()}`, "
                f"±{tolerance}s tolerance): `{false_after_done}`"
            )

            ok = ok and true_before_start and false_after_done

        status = "PASS" if ok else "FAIL"
        fname = write_report(status, timestamp_table, extra_notes="\n".join(notes))
        print(f"{status} — report written to {fname}")
        for line in notes:
            print(line)
        return 0 if ok else 1

    finally:
        if ws_client is not None:
            stop_flag["stop"] = True
            ws_client.close()
        if proc is not None and log_file is not None:
            stop_daemon(proc, log_file)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
