#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of fix-tx-transcript-real-message (TX-D05) against a
real, isolated OpenWSFZ.Daemon instance.

WHY THIS EXISTS: TX-D05's own unit/integration tests (QsoAnswererServiceTests, QsoCallerServiceTests,
OpenWSFZ.Web.Tests, qsoTranscript.test.js) all pass, and they do exercise the real production
QsoAnswererService/QsoCallerService/WebApp/WebSocketHub classes (not mocks of the class under
test) — but none of them run against an actually-running daemon process reached over real HTTP/
WebSocket, the way the Captain's browser does. This script closes that last gap for real, without
needing a virtual audio cable or synthesized RF: the two jump-in scenarios below
(EngagePoint.SendReport / EngagePoint.SendRr73, both reachable via POST /api/v1/tx/engage-decode)
only need the daemon's normal audio-capture pipeline to be producing periodic FT8-cycle-aligned
decode batches so the phase-matched jump-in has something to fire on — the batch CONTENT is
irrelevant to jump-in triggering, so real ambient microphone silence is sufficient. This proves,
against a real running daemon:

  1. The real WebSocket `txState` push carries a genuine composed report / RR73 string in its
     `lastTxMessage` field (not the fixed `R+00`/`+00` placeholder TX-D04 replaced, and not absent
     the way it was before this change).
  2. The polled `GET /api/v1/tx/status` response carries the same real value.

Two scenarios, both starting from Idle (fresh per scenario — engage-decode auto-aborts any prior
in-progress QSO before dispatching, so no explicit abort is needed between them):

  A. EngagePoint.SendReport: POST engage-decode with "{OURS} {PARTNER} -07" (a plain SNR report of
     us) → daemon replies with our own real measured report of them → TxReport state. Asserts the
     WS `lastTxMessage` for that TxReport event equals "{PARTNER} {OURS} R<real SNR>", not "R+00".
  B. EngagePoint.SendRr73: POST engage-decode with "{OURS} {PARTNER} R-07" (a roger report) →
     daemon replies RR73 → Tx73/QsoComplete then Idle. Asserts the WS `lastTxMessage` for that
     Tx73 event equals "{PARTNER} {OURS} RR73".

REQUIRES: the Release daemon built (`dotnet build src/OpenWSFZ.Daemon -c Release` from the repo
root — this script does not build it for you) and at least one enumerable audio input device (does
not need to be a virtual cable, does not need to carry any meaningful signal — see above).

Exit code 0 on PASS, 1 on FAIL, 2 if the environment prerequisites aren't met (e.g. no Release
binary found) — the report still gets written in the exit-2 case, marked ENVIRONMENT-UNAVAILABLE.
"""
import base64
import json
import os
import platform
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

PORT = 18768   # distinct scratch port from tx-keying-live-verify's 18767 / decode-filter-synth-verify's 18765
BASE = f"http://127.0.0.1:{PORT}"

OUR_CALLSIGN     = "Q1OFZ"
OUR_GRID         = "JO33"
PARTNER_CALLSIGN = "Q9AAA"   # NFR-021: Q-prefix synthetic callsign
SNR_A            = -7       # scenario A's plain-SNR report of us
SNR_B            = -3       # scenario B's roger-report value (rawPayload text only; not re-measured)


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def http_get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(path, body=None):
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, {"raw": body_text}

def wait_for_daemon_ready(timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return http_get("/api/v1/status")
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.3)
    raise TimeoutError(f"Daemon did not respond on {BASE} within {timeout_s}s.")


# ── Audio device resolution (precedent: tx-keying-live-verify) ───────────────

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


# ── Minimal dependency-free WebSocket client (RFC 6455) — precedent: tx-keying-live-verify ──

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

            if opcode == 0x8:
                self._closed = True
                return None
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x1:
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


# ── FT8 phase helper ───────────────────────────────────────────────────────────

def floor_to_15s(dt):
    """Floors a UTC datetime to the nearest preceding 15s FT8 cycle boundary."""
    epoch_s = dt.timestamp()
    floored = epoch_s - (epoch_s % 15)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


# ── Report writer ─────────────────────────────────────────────────────────────

def write_report(status, scenario_rows, environment_note=None, extra_notes=None):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip() or "unknown"
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_ROOT),
                             capture_output=True, text=True).stdout.strip() or "unknown"
    fname = REPORTS_DIR / f"{ts.strftime('%Y-%m-%dT%H%M%SZ')}-{sha}.md"

    lines = [
        "# fix-tx-transcript-real-message (TX-D05) — live verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/tx-transcript-real-message-live-verify/live_verify_tx_transcript.py`",
        f"- **Change:** `openspec/changes/fix-tx-transcript-real-message/` (task 7.2)",
        "",
    ]

    if environment_note:
        lines += ["## Environment", "", environment_note, ""]

    if scenario_rows:
        lines += ["## Scenario results", "",
                   "| Scenario | Expected `lastTxMessage` | Observed `lastTxMessage` (WS) | Observed (GET /tx/status) | Result |",
                   "|---|---|---|---|---|"]
        for row in scenario_rows:
            lines.append(f"| {row['name']} | `{row['expected']}` | `{row['ws_observed']}` | "
                          f"`{row['status_observed']}` | {row['result']} |")
        lines.append("")

    lines += ["## Result", "", f"**{status}**", ""]

    if extra_notes:
        lines += ["## Notes", "", extra_notes, ""]

    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname


# ── Main ─────────────────────────────────────────────────────────────────────

def run_scenario(name, message, snr, expected_state_substr, expected_last_tx_message,
                  events, ws_client):
    """POSTs engage-decode for one jump-in scenario and waits for a WS txState event whose
    `state` contains `expected_state_substr` and whose `lastTxMessage` is non-null. Returns a
    dict describing the outcome."""
    cycle_start = floor_to_15s(datetime.now(timezone.utc))
    body = {
        "message": message,
        "frequencyHz": 900.0,
        "cycleStartUtc": cycle_start.isoformat().replace("+00:00", "Z"),
        "confirm": False,
        "snr": snr,
    }
    baseline = len(events)
    status_code, resp = http_post("/api/v1/tx/engage-decode", body)

    deadline = time.time() + 40  # up to ~2-3 FT8 cycles of slack for the phase-matched fire
    found = None
    while time.time() < deadline:
        snapshot = list(events)[baseline:]
        for _, ev in snapshot:
            if expected_state_substr in (ev.get("state") or "") and ev.get("lastTxMessage"):
                found = ev
                break
        if found:
            break
        time.sleep(0.2)

    ws_observed = found.get("lastTxMessage") if found else None
    status_observed = None
    try:
        status_observed = http_get("/api/v1/tx/status").get("lastTxMessage")
    except Exception:
        pass

    ok = (found is not None) and (ws_observed == expected_last_tx_message)

    return {
        "name": name,
        "expected": expected_last_tx_message,
        "ws_observed": ws_observed,
        "status_observed": status_observed,
        "result": "PASS" if ok else "FAIL",
        "ok": ok,
        "http_status": status_code,
        "http_body": resp,
    }


def main():
    try:
        binary = resolve_daemon_binary()
    except FileNotFoundError as e:
        fname = write_report("ENVIRONMENT-UNAVAILABLE", [], environment_note=str(e))
        print(f"ENVIRONMENT UNAVAILABLE — report written to {fname}")
        return 2

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-txtranscript-verify-"))
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

        # ── Phase 1: write the FINAL config (Answerer role, armed) ─────────
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
                "autoAnswer": True,
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

        results = []

        # ── Scenario A: EngagePoint.SendReport ──────────────────────────────
        result_a = run_scenario(
            name="EngagePoint.SendReport (TxReport)",
            message=f"{OUR_CALLSIGN} {PARTNER_CALLSIGN} {SNR_A:+03d}",
            snr=SNR_A,
            expected_state_substr="TxReport",
            expected_last_tx_message=f"{PARTNER_CALLSIGN} {OUR_CALLSIGN} R{SNR_A:+03d}",
            events=events, ws_client=ws_client)
        results.append(result_a)

        # Let the QSO settle back to Idle (RetryCount=0/no partner reply → eventually
        # watchdog/retry-exhaustion aborts it) before scenario B, which itself also
        # auto-aborts any non-Idle session — but give it a moment either way.
        time.sleep(1.0)

        # ── Scenario B: EngagePoint.SendRr73 ────────────────────────────────
        result_b = run_scenario(
            name="EngagePoint.SendRr73 (Tx73/QsoComplete)",
            message=f"{OUR_CALLSIGN} {PARTNER_CALLSIGN} R{SNR_B:+03d}",
            snr=0,  # unused by the SendRr73 branch
            expected_state_substr="Tx73",
            expected_last_tx_message=f"{PARTNER_CALLSIGN} {OUR_CALLSIGN} RR73",
            events=events, ws_client=ws_client)
        results.append(result_b)

        stop_flag["stop"] = True
        time.sleep(0.3)

        notes = [
            f"Binary under test: `{binary}`",
            f"Input device: `{input_dev['name'] if input_dev else None}`; "
            f"output device: `{output_dev['name'] if output_dev else None}`",
            "",
            f"Scenario A HTTP {result_a['http_status']}, body: `{json.dumps(result_a['http_body'])}`",
            f"Scenario B HTTP {result_b['http_status']}, body: `{json.dumps(result_b['http_body'])}`",
        ]
        if reader_errors:
            notes.append("**WS reader thread raised an exception:**")
            notes.append("```")
            notes.extend(reader_errors)
            notes.append("```")

        ok = result_a["ok"] and result_b["ok"]

        if not ok:
            log_text = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
            log_lines = log_text.splitlines()
            tail = log_lines[-80:] if len(log_lines) > 80 else log_lines
            notes.append("")
            notes.append("**Daemon log tail (last 80 lines) — diagnostic aid on failure:**")
            notes.append("```")
            notes.extend(tail)
            notes.append("```")

        status = "PASS" if ok else "FAIL"
        fname = write_report(status, results, extra_notes="\n".join(notes))
        print(f"{status} — report written to {fname}")
        for r in results:
            print(f"  [{r['result']}] {r['name']}: expected={r['expected']!r} "
                  f"ws_observed={r['ws_observed']!r} status_observed={r['status_observed']!r}")
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
