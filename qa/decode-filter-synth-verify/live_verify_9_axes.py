#!/usr/bin/env python3
"""Live, hardware-in-the-loop verification of all nine decode-panel-filtering axes
against a real, isolated OpenWSFZ.Daemon instance, routed through a virtual audio
cable (VB-CABLE or Voicemeeter).

WHY THIS EXISTS (see MEMORY.md / decode-panel-filtering-live-verification-policy.md):
any change that touches decode-panel-filtering (DecodeFilterState, DecodeFilterEvaluator,
IDecodeFilterStore, or the QsoAnswererService/QsoCallerService filtering gate) must have
this script re-run against a real daemon before merge, and the report it produces must be
committed alongside the change. This script is intentionally self-contained and leaves no
trace outside a scratch temp directory and the report file it writes.

WHAT IT DOES, for real, against a real running daemon (not in-process, not a mock):
  1. Builds/locates the Release daemon binary.
  2. Starts a throwaway isolated instance just long enough to enumerate real audio devices.
  3. Writes an isolated config.json (own port, own decode-log directory), an isolated
     ADIF.log pre-seeded with one prior QSO for Q1AAA (so the worked-before axes have
     something real to filter on), and an isolated callsign-regions.json giving Q1AAA/
     Q1BBB two distinct, non-synthetic entities/continents/CQ-zones/ITU-zones (still
     Q-prefix per NFR-021 — this is an isolated-instance-only override, never touching
     the shared production region data).
  4. Starts the real daemon against that isolated config.
  5. Synthesises three clean FT8 CQ signals fresh via qa/rr-study/synth_wav.py (freq apart,
     never a stale fixture) and plays them, summed, into the cable's input side, timed to
     the real FT8 15-second cycle boundary — once per axis (9 rounds), each preceded by
     POST /api/v1/decode-filter for that axis and POST /api/v1/tx/abort + /tx/enable to
     return to a clean Idle/armed state, plus one further round (Phase 7,
     fix-decode-filter-new-value-admission) that narrows AllowedEntities to exclude an
     already-seen entity, then decodes a third, genuinely never-before-seen entity on that
     same narrowed-but-non-empty axis and confirms the daemon auto-admits and engages it on
     the same decode cycle.
  6. Polls the real GET /api/v1/tx/status after each round and independently greps the
     daemon's own log for "CQ detected from ..." to cross-check the API result.
  7. Writes a timestamped Markdown report to qa/decode-filter-synth-verify/live-reports/,
     including the git commit this was run against, and tears everything down — the
     isolated daemon process, its temp directory, and the WAV files.

REQUIRES: a virtual audio cable (VB-CABLE or Voicemeeter) installed on this machine, the
qa/rr-study Python venv set up (see docs/rr-synth-cli-guide.md), and the Release daemon
built (`dotnet build src/OpenWSFZ.Daemon -c Release` from the repo root — this script does
not build it for you, to avoid a surprise multi-minute build on every invocation).

Exit code 0 on PASS, 1 on FAIL, 2 if the environment prerequisites aren't met (e.g. no
virtual cable found) — the report still gets written in the exit-2 case, marked
ENVIRONMENT-UNAVAILABLE, so a CI-less environment doesn't produce a false PASS or a
silently-missing report.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd

REPO_ROOT = Path(__file__).resolve().parents[2]
RR_STUDY_DIR = REPO_ROOT / "qa" / "rr-study"
REPORTS_DIR = Path(__file__).resolve().parent / "live-reports"

PORT = 18765
BASE = f"http://127.0.0.1:{PORT}"
SLOT_SECONDS = 15
PREWARM_S = 0.5
INPUT_DEVICE_SUBSTRINGS = ("cable output", "voicemeeter out")
OUTPUT_DEVICE_SUBSTRINGS = ("cable input", "voicemeeter in", "speakers")

CALLSIGN_ALPHA, CALLSIGN_BRAVO = "Q1AAA", "Q1BBB"
ENTITY_ALPHA, ENTITY_BRAVO = "Testland Alpha", "Testland Bravo"
CQ_MESSAGE_ALPHA = f"CQ {CALLSIGN_ALPHA} JO22"
CQ_MESSAGE_BRAVO = f"CQ {CALLSIGN_BRAVO} KP20"

# fix-decode-filter-new-value-admission: a third station, deliberately never sent during the
# 9-axis loop above, so it is genuinely never-before-seen this session when it first appears in
# the new-value-admission phase below (Phase 7).
CALLSIGN_CHARLIE = "Q1CCC"
ENTITY_CHARLIE = "Testland Charlie"
CQ_MESSAGE_CHARLIE = f"CQ {CALLSIGN_CHARLIE} RE78"

AXES = [
    ("AllowedEntities",   {"allowedEntities":   [ENTITY_BRAVO]}),
    ("AllowedContinents", {"allowedContinents": ["NA"]}),
    ("AllowedCqZones",    {"allowedCqZones":    [33]}),
    ("AllowedItuZones",   {"allowedItuZones":   [10]}),
    ("ContactStates",     {"contactStates":     ["never"]}),
    ("CountryStates",     {"countryStates":     ["never"]}),
    ("ContinentStates",   {"continentStates":   ["never"]}),
    ("CqZoneStates",      {"cqZoneStates":      ["never"]}),
    ("ItuZoneStates",     {"ituZoneStates":     ["never"]}),
]


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


# ── Audio device resolution ──────────────────────────────────────────────────

def resolve_devices():
    devices = http_get("/api/v1/audio/devices")
    outputs = http_get("/api/v1/audio/output-devices")

    input_dev = next(
        (d for sub in INPUT_DEVICE_SUBSTRINGS for d in devices if sub in d["name"].lower()),
        None)
    output_dev = next(
        (d for sub in OUTPUT_DEVICE_SUBSTRINGS for d in outputs if sub in d["name"].lower()),
        None)
    return input_dev, output_dev

def select_playback_device(substring="CABLE Input"):
    matches = [i for i, d in enumerate(sd.query_devices())
               if substring.lower() in d["name"].lower() and d["max_output_channels"] > 0]
    return matches[0] if matches else None


# ── FT8 cycle alignment ──────────────────────────────────────────────────────

def next_cycle_boundary():
    now_s = int(time.time())
    rem = now_s % SLOT_SECONDS
    return float(now_s + SLOT_SECONDS) if rem == 0 else float(now_s + (SLOT_SECONDS - rem))

def wait_for_cycle(boundary_ts):
    remaining = (boundary_ts - PREWARM_S) - time.time()
    if remaining > 0:
        time.sleep(remaining)
    return datetime.fromtimestamp(boundary_ts, tz=timezone.utc).replace(microsecond=0)


# ── WAV I/O ──────────────────────────────────────────────────────────────────

def load_wav_float(path):
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, rate

def synth_wav(python_exe, message, freq_hz, seed, out_path):
    cmd = [str(python_exe), "synth_wav.py", message,
           "--freq", str(freq_hz), "--rate", "48000", "--snr", "none",
           "--seed", str(seed), "--out", str(out_path)]
    result = subprocess.run(cmd, cwd=str(RR_STUDY_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"synth_wav.py failed for '{message}':\n{result.stdout}\n{result.stderr}")


# ── Main ─────────────────────────────────────────────────────────────────────

def resolve_python_exe():
    venv = RR_STUDY_DIR / ".venv"
    win = venv / "Scripts" / "python.exe"
    posix = venv / "bin" / "python"
    return win if win.exists() else posix

def resolve_daemon_binary():
    import platform
    exe_name = "OpenWSFZ.Daemon.exe" if platform.system() == "Windows" else "OpenWSFZ.Daemon"
    # Prefer a self-contained publish if present; fall back to the framework-dependent build.
    for candidate in [
        REPO_ROOT / "src" / "OpenWSFZ.Daemon" / "bin" / "Release" / "net10.0" / exe_name,
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Release daemon binary not found. Build it first: "
        "dotnet build src/OpenWSFZ.Daemon -c Release")

def start_daemon(config_path, log_path):
    binary = resolve_daemon_binary()
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

def write_report(results, environment_note=None, extra_notes=None):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip() or "unknown"
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_ROOT),
                             capture_output=True, text=True).stdout.strip() or "unknown"
    fname = REPORTS_DIR / f"{ts.strftime('%Y-%m-%dT%H%M%SZ')}-{sha}.md"

    lines = [
        f"# decode-panel-filtering — live 9-axis verification",
        "",
        f"- **Run at (UTC):** {ts.isoformat()}",
        f"- **Git commit:** `{sha}` (branch `{branch}`)",
        f"- **Script:** `qa/decode-filter-synth-verify/live_verify_9_axes.py`",
        "",
    ]

    if environment_note:
        lines += ["## Environment", "", environment_note, ""]

    if results:
        lines += ["## Results", "", "| Axis | Result | Partner | Daemon state |",
                  "|---|---|---|---|"]
        all_ok = True
        for axis_name, ok, partner, state in results:
            all_ok &= ok
            lines.append(f"| {axis_name} | {'PASS' if ok else 'FAIL'} | `{partner}` | `{state}` |")
        lines += ["", f"**Overall: {'PASS' if all_ok else 'FAIL'}**", ""]

    if extra_notes:
        lines += ["## Notes", "", extra_notes, ""]

    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname, (all(ok for _, ok, _, _ in results) if results else False)


def main():
    python_exe = resolve_python_exe()
    if not python_exe.exists():
        note = (f"R&R study venv Python not found at `{python_exe}`. "
                 "Set it up per docs/rr-synth-cli-guide.md, then re-run this script.")
        fname, _ = write_report([], environment_note=note)
        print(f"ENVIRONMENT UNAVAILABLE — report written to {fname}")
        return 2

    scratch = Path(tempfile.mkdtemp(prefix="owsfz-live-verify-"))
    config_path = scratch / "config.json"
    logs_dir = scratch / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    daemon_log_path = scratch / "daemon.log"

    proc = None
    log_file = None
    try:
        # ── Phase 0: throwaway start, just to enumerate real audio devices ──
        config_path.write_text("{}", encoding="utf-8")  # daemon creates full defaults
        proc, log_file = start_daemon(config_path, daemon_log_path)
        wait_for_daemon_ready()
        input_dev, output_dev = resolve_devices()
        stop_daemon(proc, log_file)

        if input_dev is None or output_dev is None:
            note = (f"No virtual audio cable found (looked for one of {INPUT_DEVICE_SUBSTRINGS} "
                     f"as the daemon's RX input, one of {OUTPUT_DEVICE_SUBSTRINGS} as its TX "
                     "output). Install VB-CABLE or Voicemeeter and re-run.")
            fname, _ = write_report([], environment_note=note)
            print(f"ENVIRONMENT UNAVAILABLE — report written to {fname}")
            return 2

        playback_device_idx = select_playback_device()
        if playback_device_idx is None:
            note = "sounddevice could not find a matching playback device for injection."
            fname, _ = write_report([], environment_note=note)
            print(f"ENVIRONMENT UNAVAILABLE — report written to {fname}")
            return 2

        # ── Phase 1: pre-seed ADIF.log (Q1AAA worked-before) ────────────────
        (logs_dir / "ADIF.log").write_text(
            "<adif_ver:5>3.1.4\n<eoh>\n\n"
            f"<call:{len(CALLSIGN_ALPHA)}>{CALLSIGN_ALPHA}<band:3>20m"
            "<qso_date:8>20260101<time_on:6>120000<mode:3>FT8<eor>\n",
            encoding="utf-8")

        # ── Phase 2: isolated, non-synthetic region override (still Q-prefix, ─
        # NFR-021-compliant; isolated-instance-only, never touches production data) ─
        (scratch / "callsign-regions.json").write_text(json.dumps({
            "entries": [
                {"prefixStart": CALLSIGN_ALPHA, "prefixEnd": CALLSIGN_ALPHA,
                 "entity": ENTITY_ALPHA, "continent": "EU", "cqZone": 14, "ituZone": 27,
                 "synthetic": False},
                {"prefixStart": CALLSIGN_BRAVO, "prefixEnd": CALLSIGN_BRAVO,
                 "entity": ENTITY_BRAVO, "continent": "NA", "cqZone": 33, "ituZone": 10,
                 "synthetic": False},
                {"prefixStart": CALLSIGN_CHARLIE, "prefixEnd": CALLSIGN_CHARLIE,
                 "entity": ENTITY_CHARLIE, "continent": "AS", "cqZone": 24, "ituZone": 44,
                 "synthetic": False},
                {"prefixStart": "Q", "prefixEnd": "Q", "entity": "Synthetic (R&R Study)",
                 "continent": None, "cqZone": None, "ituZone": None, "synthetic": True},
            ]
        }, indent=2), encoding="utf-8")

        # ── Phase 3: write the FINAL config up front (avoids the two-restart
        # dance — decodeLog.path/audio devices are all correct from the first
        # real start) ────────────────────────────────────────────────────────
        config = {
            "audioDeviceId": input_dev["id"],
            "audioDeviceFriendlyName": input_dev["name"],
            "audioOutputDeviceId": output_dev["id"],
            "audioOutputFriendlyName": output_dev["name"],
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
                "callsign": "Q1OFZ",
                "grid": "JO33",
                "retryCount": 3,
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

        # ── Phase 4: the real, correctly-configured daemon start ────────────
        proc, log_file = start_daemon(config_path, daemon_log_path)
        wait_for_daemon_ready()

        # Sanity-check region resolution before spending any cycles on it.
        lookup_a = http_get(f"/api/v1/region-data/lookup?callsign={CALLSIGN_ALPHA}")
        lookup_b = http_get(f"/api/v1/region-data/lookup?callsign={CALLSIGN_BRAVO}")
        lookup_c = http_get(f"/api/v1/region-data/lookup?callsign={CALLSIGN_CHARLIE}")
        if (lookup_a.get("entity") != ENTITY_ALPHA or lookup_b.get("entity") != ENTITY_BRAVO
                or lookup_c.get("entity") != ENTITY_CHARLIE):
            note = (f"Region override did not take effect as expected: "
                     f"{CALLSIGN_ALPHA} -> {lookup_a}, {CALLSIGN_BRAVO} -> {lookup_b}, "
                     f"{CALLSIGN_CHARLIE} -> {lookup_c}.")
            fname, _ = write_report([], environment_note=note)
            print(f"SETUP FAILED — report written to {fname}")
            return 1

        # ── Phase 5: synthesise the CQ signals fresh ─────────────────────────
        alpha_wav = scratch / "cq_alpha.wav"
        bravo_wav = scratch / "cq_bravo.wav"
        charlie_wav = scratch / "cq_charlie.wav"
        synth_wav(python_exe, CQ_MESSAGE_ALPHA, 800, 1, alpha_wav)
        synth_wav(python_exe, CQ_MESSAGE_BRAVO, 1800, 2, bravo_wav)
        synth_wav(python_exe, CQ_MESSAGE_CHARLIE, 2800, 3, charlie_wav)
        alpha_pcm, rate_a = load_wav_float(alpha_wav)
        bravo_pcm, rate_b = load_wav_float(bravo_wav)
        charlie_pcm, rate_c = load_wav_float(charlie_wav)
        assert rate_a == rate_b == rate_c and len(alpha_pcm) == len(bravo_pcm) == len(charlie_pcm)
        combined = alpha_pcm + bravo_pcm

        # ── Phase 6: the 9-axis loop ─────────────────────────────────────────
        http_post("/api/v1/tx/abort")
        time.sleep(0.5)
        http_post("/api/v1/tx/enable")

        results = []
        for axis_name, filter_body in AXES:
            http_post("/api/v1/tx/abort")
            time.sleep(0.5)
            http_post("/api/v1/tx/enable")
            http_post("/api/v1/decode-filter", filter_body)

            boundary_ts = next_cycle_boundary()
            wait_for_cycle(boundary_ts)
            sd.play(combined, samplerate=rate_a, device=playback_device_idx, blocking=False)
            sd.wait()

            deadline = time.time() + 8
            status = {}
            while time.time() < deadline:
                status = http_get("/api/v1/tx/status")
                if status.get("partner"):
                    break
                time.sleep(0.3)

            partner = status.get("partner")
            state = status.get("state")
            ok = partner == CALLSIGN_BRAVO
            results.append((axis_name, ok, partner, state))
            print(f"[{axis_name}] partner={partner} state={state} {'OK' if ok else 'FAIL'}")

        # ── Phase 7: fix-decode-filter-new-value-admission ───────────────────
        # Narrow AllowedEntities to a set that EXCLUDES the already-seen ENTITY_ALPHA (Alpha
        # was decoded on every one of the nine axis-loop cycles above, so it is unambiguously
        # "seen this session"). Then decode CALLSIGN_CHARLIE — an entity that has never once
        # appeared this run — summed with a repeat CQ from the still-excluded CALLSIGN_ALPHA.
        # Confirms, against the real daemon: (a) Alpha stays excluded, exactly as the earlier
        # AllowedEntities scenario already proved, and (b) Charlie — brand-new on this
        # narrowed-but-non-empty axis — is auto-admitted by the daemon and engaged on the very
        # same decode cycle it first appears in, not one cycle later. This is the defect this
        # change fixes: previously Charlie would have been silently and permanently excluded.
        http_post("/api/v1/tx/abort")
        time.sleep(0.5)
        http_post("/api/v1/tx/enable")
        http_post("/api/v1/decode-filter", {"allowedEntities": [ENTITY_BRAVO]})

        admission_combined = alpha_pcm + charlie_pcm
        boundary_ts = next_cycle_boundary()
        wait_for_cycle(boundary_ts)
        sd.play(admission_combined, samplerate=rate_a, device=playback_device_idx, blocking=False)
        sd.wait()

        deadline = time.time() + 8
        status = {}
        while time.time() < deadline:
            status = http_get("/api/v1/tx/status")
            if status.get("partner"):
                break
            time.sleep(0.3)

        partner = status.get("partner")
        state = status.get("state")
        admission_engage_ok = partner == CALLSIGN_CHARLIE
        results.append(("NewValueAdmission(Engaged)", admission_engage_ok, partner, state))
        print(f"[NewValueAdmission(Engaged)] partner={partner} state={state} "
              f"{'OK' if admission_engage_ok else 'FAIL'}")

        # Independent confirmation: the daemon's own decode-filter state must now list
        # Charlie's entity in AllowedEntities — proof the admission actually mutated
        # IDecodeFilterStore, not just that this one decode happened to slip through.
        filter_after = http_get("/api/v1/decode-filter")
        admitted_entities = filter_after.get("allowedEntities") or []
        admission_state_ok = ENTITY_CHARLIE in admitted_entities and ENTITY_ALPHA not in admitted_entities
        results.append((
            "NewValueAdmission(FilterStateUpdated)", admission_state_ok,
            ENTITY_CHARLIE if admission_state_ok else "(not admitted)",
            json.dumps(admitted_entities)))
        print(f"[NewValueAdmission(FilterStateUpdated)] admitted={admission_state_ok} "
              f"allowedEntities={admitted_entities}")

        http_post("/api/v1/tx/abort")
        http_post("/api/v1/decode-filter", {})

        # Independent cross-check against the daemon's own log.
        log_text = daemon_log_path.read_text(encoding="utf-8", errors="ignore")
        cq_detections = log_text.count("QsoAnswererService: CQ detected from")
        bravo_detections = log_text.count(f"CQ detected from {CALLSIGN_BRAVO}")
        alpha_detections = log_text.count(f"CQ detected from {CALLSIGN_ALPHA}")
        charlie_detections = log_text.count(f"CQ detected from {CALLSIGN_CHARLIE}")
        cross_check_note = (
            f"Independent log cross-check: {cq_detections} total CQ-detected log lines, "
            f"{bravo_detections} for {CALLSIGN_BRAVO}, {alpha_detections} for {CALLSIGN_ALPHA}, "
            f"{charlie_detections} for {CALLSIGN_CHARLIE} "
            f"(expected: {len(AXES) + 1}, {len(AXES)}, 1 [Phase 7's excluded-Alpha decode], "
            "1 respectively)."
        )
        print(cross_check_note)

        fname, all_ok = write_report(
            results,
            extra_notes=cross_check_note + (
                "\n\nIsolated region override (this run only, never touching production "
                f"`callsign-regions.json`): `{CALLSIGN_ALPHA}` -> `{ENTITY_ALPHA}` (EU/14/27), "
                f"`{CALLSIGN_BRAVO}` -> `{ENTITY_BRAVO}` (NA/33/10), "
                f"`{CALLSIGN_CHARLIE}` -> `{ENTITY_CHARLIE}` (AS/24/44). Isolated ADIF pre-seed: "
                f"one prior QSO for `{CALLSIGN_ALPHA}` so the worked-before axes have something "
                "real to filter on. Phase 7 (fix-decode-filter-new-value-admission): "
                f"`{CALLSIGN_CHARLIE}` is never decoded before Phase 7, proving genuine "
                "never-before-seen-this-session admission, not a pre-warmed seen-set."
            ))
        print(f"Report written to {fname}")
        return 0 if all_ok else 1

    finally:
        if proc is not None and log_file is not None:
            stop_daemon(proc, log_file)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
