#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of the JsonConfigStore concurrent-save-race fix
(dev-tasks/2026-07-10-config-store-concurrent-save-race.md) against a real, isolated
OpenWSFZ.Daemon instance.

WHY THIS EXISTS: the bug was a real HTTP 500 on POST /api/v1/tx/abort caused by
System.IO.FileSystem.MoveFile throwing UnauthorizedAccessException when WebApp.cs's own
explicit JsonConfigStore.SaveAsync call raced QsoCallerService/QsoAnswererService's
independent SaveAsync call inside SafeAbortToIdleAsync -- both call File.Move onto the same
destination path at nearly the same instant when abort lands while the service is parked in a
Wait* state. The new JsonConfigStoreTests regression test proves the store-level fix
(SemaphoreSlim serializing SaveAsync) under synthetic concurrent calls in-process; this script
proves it end-to-end against the real HTTP surface and the real QsoCallerService state
machine, the same code path the Captain hit during live abort-cycling.

WHAT IT DOES:
  1. Locates the Release daemon binary and confirms it postdates JsonConfigStore.cs (proves
     the binary under test actually contains the fix, not a stale build).
  2. Starts a throwaway isolated instance to enumerate real audio devices, then a real
     isolated instance (own scratch port/config directory -- never touches the Captain's real
     %APPDATA%\\OpenWSFZ\\config.json).
  3. Repeats an abort-cycling pattern several times: POST /api/v1/tx/call-cq (arms Caller
     role and starts a real CQ transmission), poll GET /api/v1/tx/status until the state
     reaches WaitAnswer (the exact Wait* state implicated in one of the two original
     incidents -- QsoCallerService's SafeAbortToIdleAsync race with WebApp.cs's own save),
     then POST /api/v1/tx/abort and record its HTTP status code.
  4. Independently parses the daemon's own stdout log for "[ERR]" lines and for
     UnauthorizedAccessException, the exact signature of the original bug.
  5. Writes a timestamped Markdown report to
     qa/config-store-concurrent-save-race-live-verify/live-reports/, including the git commit
     this was run against and a per-cycle table, and tears everything down.

REQUIRES: the Release daemon built (`dotnet build src/OpenWSFZ.Daemon -c Release` from the
repo root -- this script does not build it for you) and a real audio output device (does not
need to be audible or a virtual cable -- CQ transmission does not require a decode input,
confirmed by qa/tx-keying-live-verify's precedent).

Exit code 0 on PASS, 1 on FAIL, 2 if the environment prerequisites aren't met (e.g. no Release
binary found) -- the report still gets written in the exit-2 case, marked
ENVIRONMENT-UNAVAILABLE, so a CI-less environment doesn't produce a false PASS or a
silently-missing report.
"""
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "live-reports"

PORT = 18769   # distinct scratch port from decode-filter-synth-verify's 18765 and
               # tx-keying-live-verify's 18767
BASE = f"http://127.0.0.1:{PORT}"

OUR_CALLSIGN = "Q1OFZ"
OUR_GRID     = "JO33"

CYCLES = 6   # "several times back-to-back" per the dev-task's verification step 2

ERR_LINE_RE = re.compile(r"^\[ERR\]", re.MULTILINE)
UNAUTHORIZED_RE = re.compile(r"UnauthorizedAccessException")


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def http_get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def http_post(path, body=None):
    data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return e.code, body_text

def wait_for_daemon_ready(timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return http_get("/api/v1/status")
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.3)
    raise TimeoutError(f"Daemon did not respond on {BASE} within {timeout_s}s.")


# ── Audio device resolution ────────────────────────────────────────────────
# Both an input AND output device must be configured: the decode-cycle loop that drives
# ProcessBatchAsync (and therefore HandleIdleAsync, which is what actually checks
# tx.AutoAnswer and starts a CQ) only runs when a real capture pipeline is producing
# periodic DecodeBatch output on each 15s cycle boundary. Setting only the output device
# (as this script's first draft did) leaves the daemon parked in Idle forever — call-cq
# still returns 200 and flips the role/AutoAnswer flag, but nothing ever reads it.
INPUT_DEVICE_SUBSTRINGS  = ("cable output", "voicemeeter out")
OUTPUT_DEVICE_SUBSTRINGS = ("cable input", "voicemeeter in", "speakers")

def resolve_devices():
    devices = http_get("/api/v1/audio/devices")[1]
    outputs = http_get("/api/v1/audio/output-devices")[1]
    input_dev = next(
        (d for sub in INPUT_DEVICE_SUBSTRINGS for d in devices if sub in d["name"].lower()),
        devices[0] if devices else None)
    output_dev = next(
        (d for sub in OUTPUT_DEVICE_SUBSTRINGS for d in outputs if sub in d["name"].lower()),
        outputs[0] if outputs else None)
    return input_dev, output_dev


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

def write_report(status, cycle_table, environment_note=None, extra_notes=None):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip() or "unknown"
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_ROOT),
                             capture_output=True, text=True).stdout.strip() or "unknown"
    fname = REPORTS_DIR / f"{ts.strftime('%Y-%m-%dT%H%M%SZ')}-{sha}.md"

    lines = [
        "# JsonConfigStore concurrent-save race — live verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/config-store-concurrent-save-race-live-verify/live_verify_abort_race.py`",
        f"- **Dev-task:** `dev-tasks/2026-07-10-config-store-concurrent-save-race.md`",
        "",
    ]

    if environment_note:
        lines += ["## Environment", "", environment_note, ""]

    if cycle_table:
        lines += ["## Abort-cycling results", "",
                   "| Cycle | call-cq status | Reached WaitAnswer | abort HTTP status | abort body/error |",
                   "|---|---|---|---|---|"]
        for row in cycle_table:
            lines.append(
                f"| {row['cycle']} | `{row['callcq_status']}` | `{row['reached_wait_answer']}` | "
                f"`{row['abort_status']}` | `{row['abort_body']}` |")
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

    # Rule out "stale binary" explicitly: JsonConfigStore.cs's SemaphoreSlim fix must
    # predate the binary compiled from it.
    fix_source = REPO_ROOT / "src" / "OpenWSFZ.Config" / "JsonConfigStore.cs"
    fix_source_mtime = (
        datetime.fromtimestamp(fix_source.stat().st_mtime, tz=timezone.utc)
        if fix_source.exists() else None
    )
    fix_source_contains_lock = (
        "_saveLock" in fix_source.read_text(encoding="utf-8") if fix_source.exists() else False
    )

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-abort-race-verify-"))
    config_path = scratch / "config.json"
    logs_dir = scratch / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    daemon_log_path = scratch / "daemon.log"

    proc = None
    log_file = None
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
                "autoAnswer": False,   # armed at runtime via POST /tx/call-cq each cycle
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

        # ── Phase 3: abort-cycling pattern, several times back-to-back ──────
        cycle_table = []
        for cycle in range(1, CYCLES + 1):
            callcq_status, callcq_body = http_post("/api/v1/tx/call-cq")

            # Poll GET /tx/status until we reach the Wait* state (or Idle again, meaning the
            # session already finished/errored) — up to ~2 FT8 cycles of slack.
            #
            # NOTE ON STATE NAME: internally QsoCallerService's CallerState.WaitAnswer is the
            # state this reproduces (it's the exact Wait* state from the original incident
            # where the background loop is parked on a channel read and SafeAbortToIdleAsync's
            # save races WebApp.cs's own save). But the PUBLIC /tx/status API maps
            # CallerState.WaitAnswer -> QsoState.WaitReport ("nearest: waiting for partner" —
            # see QsoCallerService.cs's ToPublicState mapping), so that is the string this
            # script must poll for. Confirmed empirically against a real running daemon during
            # this script's own development (polling for the internal name "WaitAnswer" never
            # matched and the loop always timed out).
            # Do NOT break early on an observed "Idle" state here: call-cq's CQ transmission
            # does not start immediately — HandleIdleAsync only fires on the next FT8 cycle
            # boundary (up to ~15s away), so the state legitimately reads "Idle" for a few
            # seconds right after a successful call-cq before it moves to TxAnswer and then
            # WaitReport. (An earlier version of this script broke on that transient Idle
            # reading and never observed a single WaitReport in 6 cycles — confirmed by
            # rerunning with verbose per-poll logging during this script's own development.)
            reached_wait_state = False
            if callcq_status == 200:
                deadline = time.time() + 40
                while time.time() < deadline:
                    _, status_body = http_get("/api/v1/tx/status")
                    if status_body.get("state") == "WaitReport":
                        reached_wait_state = True
                        break
                    time.sleep(0.2)
            # else: call-cq itself was rejected (e.g. 409 — previous cycle's abort hadn't
            # finished unwinding yet); nothing will transition, so don't burn 40s waiting.

            abort_status, abort_body = http_post("/api/v1/tx/abort")
            cycle_table.append({
                "cycle": cycle,
                "callcq_status": callcq_status,
                "reached_wait_answer": reached_wait_state,
                "abort_status": abort_status,
                "abort_body": (json.dumps(abort_body) if isinstance(abort_body, dict) else str(abort_body))[:200],
            })

            # Let the abort fully settle (state machine unwinds, config save completes)
            # before starting the next cycle's call-cq.
            time.sleep(1.0)

        # Give the log a brief moment to flush any trailing lines.
        time.sleep(0.5)

        # ── Phase 4: parse the daemon's own log for the bug's exact signature ──
        log_text = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
        err_lines = ERR_LINE_RE.findall(log_text)
        has_unauthorized = bool(UNAUTHORIZED_RE.search(log_text))

        all_aborts_200 = all(row["abort_status"] == 200 for row in cycle_table)
        any_reached_wait_answer = any(row["reached_wait_answer"] for row in cycle_table)
        no_err_lines = len(err_lines) == 0
        no_unauthorized = not has_unauthorized

        ok = all_aborts_200 and any_reached_wait_answer and no_err_lines and no_unauthorized

        notes = [
            f"Binary under test: `{binary}`",
            f"Binary last-write time (UTC): `{binary_mtime.isoformat()}`",
            f"JsonConfigStore.cs last-write time (UTC): "
            f"`{fix_source_mtime.isoformat() if fix_source_mtime else 'unknown'}`",
            f"Rebuild check: compiled binary postdates JsonConfigStore.cs = "
            f"`{binary_mtime >= fix_source_mtime if fix_source_mtime else 'unknown'}`; "
            f"process started after binary was built = `{proc_start_time >= binary_mtime}`; "
            f"JsonConfigStore.cs contains the `_saveLock` fix = `{fix_source_contains_lock}`",
            "",
            f"Cycles run: {CYCLES}; cycles that reached WaitAnswer before abort: "
            f"{sum(1 for r in cycle_table if r['reached_wait_answer'])}",
            f"All abort calls returned HTTP 200: `{all_aborts_200}`",
            f"At least one cycle reached WaitAnswer (the Wait* state implicated in the "
            f"original QsoCallerService incident): `{any_reached_wait_answer}`",
            f"'[ERR]' lines found in daemon log: {len(err_lines)} (`{no_err_lines}` == none found)",
            f"'UnauthorizedAccessException' found in daemon log: `{has_unauthorized}` "
            f"(`{no_unauthorized}` == not found)",
        ]

        if not ok:
            log_lines = log_text.splitlines()
            tail = log_lines[-80:] if len(log_lines) > 80 else log_lines
            notes.append("")
            notes.append("**Daemon log tail (last 80 lines) — diagnostic aid on failure:**")
            notes.append("```")
            notes.extend(tail)
            notes.append("```")

        status = "PASS" if ok else "FAIL"
        fname = write_report(status, cycle_table, extra_notes="\n".join(notes))
        print(f"{status} — report written to {fname}")
        for line in notes:
            print(line)
        return 0 if ok else 1

    finally:
        if proc is not None and log_file is not None:
            stop_daemon(proc, log_file)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
