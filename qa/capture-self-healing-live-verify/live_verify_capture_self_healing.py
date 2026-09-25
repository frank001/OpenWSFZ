#!/usr/bin/env python3
"""Live acceptance tests L1-L4 for #187 (capture-device-reresolution) and #188
(capture-stall-detection-unattended), against a real OpenWSFZ.Daemon instance on the
Captain's real station (the FT-991A capture chain), per
openspec/changes/capture-stall-detection-unattended/architect-to-qa-handoff.md Section 2
(pre-registered, mechanical predicates -- HK-021), QA handoff task 1.5.

This script OWNS the daemon lifecycle for the test it is asked to run (start/stop with
EXACTLY the given exe/config/port -- no construction, no edits it isn't explicitly testing;
same discipline as qa/endurance/*/tools/endurance_supervisor.py). L2 and L3 edit config.json
themselves (stop daemon first, HK-035 -- config POST is a full replace so a live edit while
running would be clobbered on the daemon's own next write); a byte-identical backup is taken
before the FIRST edit of any session and restored, daemon stopped, at teardown.

General conditions (handoff Section 2, all tests):
  - ws_accepted (count of "WebSocket connection accepted" in the daemon's file log across the
    test window) must be 0, else VOID. This script greps the daemon's own file-log directory,
    which is more reliable than trusting "no browser tab" by report alone.
  - Every status poll is UTC-timestamped (HK-017) and written to poll_log.jsonl.

NFR-021: this script never prints or writes message text or callsign content -- ALL.TXT and
cycle-audio stay under the given config's own output paths (artefacts/, gitignored), never
touched here.

Usage:
  python live_verify_capture_self_healing.py L1 --daemon-exe <exe> --config <config.json> \\
      --port 8080 --out-dir <dir>
  python live_verify_capture_self_healing.py L2 --daemon-exe <exe> --config <config.json> \\
      --port 8080 --out-dir <dir> --good-friendly-name "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
  python live_verify_capture_self_healing.py L3 --daemon-exe <exe> --config <config.json> \\
      --port 8080 --out-dir <dir>
  python live_verify_capture_self_healing.py L4-WAIT-UNPLUG --port 8080 --out-dir <dir>
  python live_verify_capture_self_healing.py L4-WAIT-RECOVERY --port 8080 --out-dir <dir> \\
      --friendly-name "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"

Exit code 0 = PASS/recorded, 1 = FAIL, 2 = VOID (precondition not met), 3 = environment error.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def utcnow():
    return datetime.now(timezone.utc)


def iso(t=None):
    return (t or utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(out_dir, msg):
    line = "%s %s" % (iso(), msg)
    print(line, flush=True)
    with open(os.path.join(out_dir, "test_run.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def status(port, timeout=5):
    with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % port, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def devices(port, timeout=5):
    with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/audio/devices" % port, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def daemon_pid_by_exe(exe_path):
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name OpenWSFZ.Daemon -ErrorAction SilentlyContinue | "
         "Select-Object -ExpandProperty Id"],
        capture_output=True, text=True, timeout=30, creationflags=NOWIN).stdout
    return [int(x) for x in out.splitlines() if x.strip().isdigit()]


def start_daemon(out_dir, daemon_exe, config_path, port):
    if daemon_pid_by_exe(daemon_exe):
        raise RuntimeError("an OpenWSFZ.Daemon.exe is already running -- stop it first "
                            "(this script refuses to arm alongside an unknown instance)")
    logf = open(os.path.join(out_dir, "daemon.stdout.log"), "ab")
    proc = subprocess.Popen([daemon_exe, "--config", config_path, "--port", str(port)],
                             stdout=logf, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | NOWIN)
    return proc


def stop_daemon(proc, out_dir, why):
    log(out_dir, "stopping daemon pid %d (%s)" % (proc.pid, why))
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True, text=True, creationflags=NOWIN)
    try:
        proc.wait(timeout=30)
    except Exception:
        pass


def wait_ready(port, timeout_s=120):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            s = status(port, timeout=4)
            if s.get("captureActive") is not None:
                return s
        except Exception:
            pass
        time.sleep(2)
    return None


def ws_accepted_count(log_dir):
    n = 0
    for p in glob.glob(os.path.join(log_dir, "*.log")):
        with open(p, encoding="utf-8", errors="replace") as f:
            n += sum(1 for line in f if "WebSocket connection accepted" in line)
    return n


def heartbeat_lines(log_dir, window_start_iso=None):
    """Returns the list of parsed timestamps (as datetime, log's own local-offset format
    Serilog writes: 'YYYY-MM-DD HH:MM:SS.fff +HH:MM') for every 'Heartbeat: captureActive='
    line across the log directory, sorted."""
    pat = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+ [+-]\d{2}:\d{2} \[INF\] Heartbeat: captureActive=")
    out = []
    for p in glob.glob(os.path.join(log_dir, "*.log")):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = pat.match(line)
                if m:
                    out.append(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
    return sorted(out)


def max_gap_s(timestamps):
    if len(timestamps) < 2:
        return None
    return max((b - a).total_seconds() for a, b in zip(timestamps, timestamps[1:]))


def poll_loop(out_dir, port, duration_s, poll_every_s=5):
    """Polls /api/v1/status every poll_every_s for duration_s, writing each UTC-timestamped
    poll to poll_log.jsonl (HK-017). Returns the list of polls."""
    polls = []
    t_end = time.time() + duration_s
    with open(os.path.join(out_dir, "poll_log.jsonl"), "a", encoding="utf-8") as pf:
        while time.time() < t_end:
            t = iso()
            try:
                s = status(port)
                rec = {"t": t, "ok": True, **s}
            except Exception as e:
                rec = {"t": t, "ok": False, "error": type(e).__name__}
            pf.write(json.dumps(rec) + "\n")
            pf.flush()
            polls.append(rec)
            time.sleep(poll_every_s)
    return polls


# --------------------------------------------------------------------------------------- L1
def run_l1(a):
    os.makedirs(a.out_dir, exist_ok=True)
    log_dir = os.path.join(a.out_dir, "daemon-logs")
    proc = start_daemon(a.out_dir, a.daemon_exe, a.config, a.port)
    s0 = wait_ready(a.port)
    result = {"test": "L1", "started_utc": iso()}
    if s0 is None:
        log(a.out_dir, "L1 VOID: daemon never became ready")
        result["verdict"] = "VOID"; result["reason"] = "daemon never became ready"
        stop_daemon(proc, a.out_dir, "L1 VOID")
        write_result(a.out_dir, result); return 2
    log(a.out_dir, "L1 armed: %s" % json.dumps(s0))
    log(a.out_dir, "L1 running for %d s (30 min = 1800 s)" % a.duration_s)
    polls = poll_loop(a.out_dir, a.port, a.duration_s, poll_every_s=5)
    stop_daemon(proc, a.out_dir, "L1 window complete")

    ws0 = ws_accepted_count(log_dir)
    result["ws_accepted"] = ws0
    result["l1_0_ws_accepted_zero"] = (ws0 == 0)

    hb = heartbeat_lines(log_dir)
    result["heartbeat_count"] = len(hb)
    gap = max_gap_s(hb)
    result["heartbeat_max_gap_s"] = gap
    result["l1_1"] = bool(330 <= len(hb) <= 370 and (gap is None or gap <= 7))

    after_10s = [p for p in polls if p.get("ok")][2:]  # first 10s ~= 2 polls at 5s cadence
    l1_2 = all(p.get("dataFlowing") is True and p.get("lastChunkAgeMs", 1e9) < 2000
               for p in after_10s) if after_10s else False
    result["l1_2"] = l1_2

    last_ok = [p for p in polls if p.get("ok")]
    wrc = last_ok[-1].get("watchdogRestartCount") if last_ok else None
    result["watchdogRestartCount_end"] = wrc
    result["l1_3"] = (wrc == 0)

    result["verdict"] = ("VOID" if not result["l1_0_ws_accepted_zero"] else
                          "PASS" if (result["l1_1"] and result["l1_2"] and result["l1_3"]) else "FAIL")
    write_result(a.out_dir, result)
    log(a.out_dir, "L1 verdict: %s -- %s" % (result["verdict"], json.dumps(result)))
    return {"PASS": 0, "FAIL": 1, "VOID": 2}[result["verdict"]]


# --------------------------------------------------------------------------------------- L2
def run_l2(a):
    """Stale ID at startup is adopted. Backs up config.json (once, if no backup already
    exists next to it), edits audioDeviceId to a bogus GUID (friendly name unchanged),
    starts the daemon, and checks adoption within 30 s."""
    os.makedirs(a.out_dir, exist_ok=True)
    log_dir = os.path.join(a.out_dir, "daemon-logs")
    backup_path = a.config + ".pristine_backup"
    if not os.path.exists(backup_path):
        shutil.copy2(a.config, backup_path)
        log(a.out_dir, "backed up pristine config to %s (HK-035)" % backup_path)

    cfg = json.load(open(a.config, encoding="utf-8"))
    good_name = cfg.get("audioDeviceFriendlyName")
    result = {"test": "L2", "started_utc": iso(), "good_friendly_name": good_name}

    devs = None
    proc = start_daemon(a.out_dir, a.daemon_exe, a.config, a.port)
    s0 = wait_ready(a.port)
    if s0 is not None:
        try:
            devs = devices(a.port)
        except Exception:
            devs = None
    stop_daemon(proc, a.out_dir, "L2 precondition probe complete")
    time.sleep(2)
    # Scope the adoption checks below to ONLY the log file the actual (post-edit) daemon
    # start produces -- the precondition probe above is a separate process with its own log
    # file in the same directory, and its own unrelated "Starting audio capture" line must
    # not be counted alongside the real test's.
    logs_before_real_start = set(glob.glob(os.path.join(log_dir, "*.log")))

    matches = [d for d in (devs or []) if d.get("name") == good_name and d.get("available")]
    result["l2_0_precondition"] = (len(matches) == 1)
    if len(matches) != 1:
        result["verdict"] = "VOID"
        result["reason"] = "friendly name '%s' does not match exactly one available device (%d matches)" % (
            good_name, len(matches))
        write_result(a.out_dir, result); return 2

    cfg["audioDeviceId"] = "{0.0.1.00000000}.{00000000-0000-0000-0000-000000000000}"
    json.dump(cfg, open(a.config, "w", encoding="utf-8"), indent=2)
    log(a.out_dir, "L2: set audioDeviceId to bogus GUID, friendly name unchanged ('%s')" % good_name)

    t_start = time.time()
    proc = start_daemon(a.out_dir, a.daemon_exe, a.config, a.port)
    adopted_within_30 = False
    s_final = None
    while time.time() - t_start < 30:
        try:
            s = status(a.port)
            s_final = s
            if s.get("captureState") == "Capturing" and s.get("dataFlowing"):
                adopted_within_30 = True
                break
        except Exception:
            pass
        time.sleep(2)
    result["l2_1"] = adopted_within_30
    result["status_at_check"] = s_final

    time.sleep(3)
    cfg_after = json.load(open(a.config, encoding="utf-8"))
    result["config_audio_device_id_after"] = cfg_after.get("audioDeviceId")
    result["config_friendly_name_after"] = cfg_after.get("audioDeviceFriendlyName")
    correct_id = [d["id"] for d in matches][0] if matches else None
    result["l2_2"] = (cfg_after.get("audioDeviceId") == correct_id and
                       cfg_after.get("audioDeviceFriendlyName") == good_name)

    stop_daemon(proc, a.out_dir, "L2 window complete")
    real_test_logs = [p for p in glob.glob(os.path.join(log_dir, "*.log"))
                       if p not in logs_before_real_start]
    warn_count = 0
    for p in real_test_logs:
        with open(p, encoding="utf-8", errors="replace") as f:
            warn_count += sum(1 for line in f if "[WRN]" in line and "re-resolved" in line.lower())
    start_count = 0
    for p in real_test_logs:
        with open(p, encoding="utf-8", errors="replace") as f:
            start_count += sum(1 for line in f if "Starting audio capture on device" in line)
    result["adoption_warning_count"] = warn_count
    result["capture_start_count_after_adoption"] = start_count
    result["l2_3"] = (warn_count == 1 and start_count == 1)

    ws0 = ws_accepted_count(log_dir)
    result["ws_accepted"] = ws0
    result["verdict"] = ("VOID" if ws0 != 0 or not result["l2_0_precondition"] else
                          "PASS" if (result["l2_1"] and result["l2_2"] and result["l2_3"]) else "FAIL")
    write_result(a.out_dir, result)
    log(a.out_dir, "L2 verdict: %s -- %s" % (result["verdict"], json.dumps(result)))

    log(a.out_dir, "restoring pristine config.json (daemon stopped, HK-035)")
    shutil.copy2(backup_path, a.config)
    return {"PASS": 0, "FAIL": 1, "VOID": 2}[result["verdict"]]


# --------------------------------------------------------------------------------------- L3
def run_l3(a):
    """Unresolvable device is loud, bounded, never guessed. Bogus GUID AND bogus friendly
    name; run 300 s."""
    os.makedirs(a.out_dir, exist_ok=True)
    log_dir = os.path.join(a.out_dir, "daemon-logs")
    backup_path = a.config + ".pristine_backup"
    if not os.path.exists(backup_path):
        shutil.copy2(a.config, backup_path)
        log(a.out_dir, "backed up pristine config to %s (HK-035)" % backup_path)

    cfg = json.load(open(a.config, encoding="utf-8"))
    cfg["audioDeviceId"] = "{0.0.1.00000000}.{00000000-0000-0000-0000-000000000000}"
    cfg["audioDeviceFriendlyName"] = "QA-NONEXISTENT-DEVICE"
    json.dump(cfg, open(a.config, "w", encoding="utf-8"), indent=2)
    log(a.out_dir, "L3: set audioDeviceId to bogus GUID AND audioDeviceFriendlyName to "
                   "'QA-NONEXISTENT-DEVICE'")

    result = {"test": "L3", "started_utc": iso()}
    t_start = time.time()
    proc = start_daemon(a.out_dir, a.daemon_exe, a.config, a.port)

    became_unavailable_within_30 = False
    s_at_30 = None
    while time.time() - t_start < 30:
        try:
            s = status(a.port)
            s_at_30 = s
            if s.get("captureState") == "DeviceUnavailable" and s.get("lastCaptureError"):
                became_unavailable_within_30 = True
                break
        except Exception:
            pass
        time.sleep(2)
    result["l3_1"] = became_unavailable_within_30
    result["status_at_30s"] = s_at_30

    remaining = 300 - (time.time() - t_start)
    if remaining > 0:
        time.sleep(remaining)
    try:
        s_at_300 = status(a.port)
    except Exception:
        s_at_300 = None
    result["status_at_300s"] = s_at_300
    crc = (s_at_300 or {}).get("captureRestartCount")
    result["captureRestartCount_at_300s"] = crc
    result["l3_2"] = (crc is not None and 5 <= crc <= 9)

    stop_daemon(proc, a.out_dir, "L3 window complete")
    cfg_after = json.load(open(a.config, encoding="utf-8"))
    result["config_unchanged"] = (cfg_after.get("audioDeviceId") == cfg["audioDeviceId"] and
                                   cfg_after.get("audioDeviceFriendlyName") == cfg["audioDeviceFriendlyName"])
    warn_count = 0
    for p in glob.glob(os.path.join(log_dir, "*.log")):
        with open(p, encoding="utf-8", errors="replace") as f:
            warn_count += sum(1 for line in f if "[WRN]" in line and "re-resolved" in line.lower())
    result["adoption_warning_count"] = warn_count
    result["l3_3"] = (result["config_unchanged"] and warn_count == 0)

    ws0 = ws_accepted_count(log_dir)
    result["ws_accepted"] = ws0
    result["verdict"] = ("VOID" if ws0 != 0 else
                          "PASS" if (result["l3_1"] and result["l3_2"] and result["l3_3"]) else "FAIL")
    write_result(a.out_dir, result)
    log(a.out_dir, "L3 verdict: %s -- %s" % (result["verdict"], json.dumps(result)))

    log(a.out_dir, "restoring pristine config.json (daemon stopped, HK-035)")
    shutil.copy2(backup_path, a.config)
    return {"PASS": 0, "FAIL": 1, "VOID": 2}[result["verdict"]]


# --------------------------------------------------------------------------------------- L4
def run_l4_wait_unplug(a):
    """Polls /api/v1/audio/devices + /api/v1/status every 5 s and reports the instant the
    configured device disappears (captureState in {Recovering, DeviceUnavailable}). Meant to
    be run WHILE the Captain physically unplugs the cable. Assumes the daemon is already
    running (this test does not restart it)."""
    os.makedirs(a.out_dir, exist_ok=True)
    log(a.out_dir, "L4-WAIT-UNPLUG: polling for the unplug to be observed (timeout %ds)" % a.timeout_s)
    t0 = time.time()
    seen = False
    t_seen = None
    while time.time() - t0 < a.timeout_s:
        t = iso()
        try:
            s = status(a.port)
            with open(os.path.join(a.out_dir, "poll_log.jsonl"), "a", encoding="utf-8") as pf:
                pf.write(json.dumps({"t": t, "phase": "L4-WAIT-UNPLUG", **s}) + "\n")
            if s.get("captureState") in ("Recovering", "DeviceUnavailable"):
                seen = True; t_seen = t
                break
        except Exception as e:
            with open(os.path.join(a.out_dir, "poll_log.jsonl"), "a", encoding="utf-8") as pf:
                pf.write(json.dumps({"t": t, "phase": "L4-WAIT-UNPLUG", "ok": False,
                                     "error": type(e).__name__}) + "\n")
        time.sleep(5)
    print(json.dumps({"seen": seen, "t_seen": t_seen}))
    log(a.out_dir, "L4-WAIT-UNPLUG result: seen=%s t_seen=%s" % (seen, t_seen))
    return 0 if seen else 2


def run_l4_wait_recovery(a):
    """Polls every 5 s for the configured friendly name to reappear (t_avail), then for
    captureState==Capturing and dataFlowing==true (t_rec). Run AFTER the Captain replugs."""
    os.makedirs(a.out_dir, exist_ok=True)
    log(a.out_dir, "L4-WAIT-RECOVERY: polling for '%s' to reappear (timeout %ds)"
        % (a.friendly_name, a.timeout_s))
    t0 = time.time()
    t_avail = None
    t_rec = None
    while time.time() - t0 < a.timeout_s:
        t = iso()
        try:
            devs = devices(a.port)
            s = status(a.port)
            with open(os.path.join(a.out_dir, "poll_log.jsonl"), "a", encoding="utf-8") as pf:
                pf.write(json.dumps({"t": t, "phase": "L4-WAIT-RECOVERY", "status": s,
                                     "device_available": any(
                                         d.get("name") == a.friendly_name and d.get("available")
                                         for d in devs)}) + "\n")
            if t_avail is None and any(d.get("name") == a.friendly_name and d.get("available")
                                        for d in devs):
                t_avail = time.time()
                log(a.out_dir, "t_avail at %s" % t)
            if t_avail is not None and s.get("captureState") == "Capturing" and s.get("dataFlowing"):
                t_rec = time.time()
                log(a.out_dir, "t_rec at %s" % t)
                break
        except Exception as e:
            with open(os.path.join(a.out_dir, "poll_log.jsonl"), "a", encoding="utf-8") as pf:
                pf.write(json.dumps({"t": t, "phase": "L4-WAIT-RECOVERY", "ok": False,
                                     "error": type(e).__name__}) + "\n")
        time.sleep(5)
    result = {"test": "L4", "t_avail_epoch": t_avail, "t_rec_epoch": t_rec,
              "recovery_s": (t_rec - t_avail) if (t_avail and t_rec) else None}
    if t_avail is None or t_rec is None:
        result["verdict"] = "VOID"; result["reason"] = "did not observe both t_avail and t_rec within timeout"
    else:
        try:
            s_final = status(a.port)
        except Exception:
            s_final = {}
        result["l4_1"] = (result["recovery_s"] is not None and result["recovery_s"] <= 70)
        result["l4_2"] = (s_final.get("consecutiveCaptureFailures") == 0 and
                          s_final.get("lastCaptureError") is not None)
        result["verdict"] = "PASS" if (result["l4_1"] and result["l4_2"]) else "FAIL"
    write_result(a.out_dir, result)
    log(a.out_dir, "L4 verdict: %s -- %s" % (result["verdict"], json.dumps(result)))
    return {"PASS": 0, "FAIL": 1, "VOID": 2}.get(result["verdict"], 1)


def write_result(out_dir, result):
    with open(os.path.join(out_dir, "result_%s.json" % result["test"]), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = dict()
    for name in ("L1", "L2", "L3"):
        p = sub.add_parser(name)
        p.add_argument("--daemon-exe", required=True)
        p.add_argument("--config", required=True)
        p.add_argument("--port", type=int, default=8080)
        p.add_argument("--out-dir", required=True)
        if name == "L1":
            p.add_argument("--duration-s", type=int, default=1800)
        if name == "L2":
            pass  # good_friendly_name is read from config.json itself

    p4a = sub.add_parser("L4-WAIT-UNPLUG")
    p4a.add_argument("--port", type=int, default=8080)
    p4a.add_argument("--out-dir", required=True)
    p4a.add_argument("--timeout-s", type=int, default=180)

    p4b = sub.add_parser("L4-WAIT-RECOVERY")
    p4b.add_argument("--port", type=int, default=8080)
    p4b.add_argument("--out-dir", required=True)
    p4b.add_argument("--friendly-name", required=True)
    p4b.add_argument("--timeout-s", type=int, default=180)

    a = ap.parse_args()
    dispatch = {"L1": run_l1, "L2": run_l2, "L3": run_l3,
                "L4-WAIT-UNPLUG": run_l4_wait_unplug, "L4-WAIT-RECOVERY": run_l4_wait_recovery}
    sys.exit(dispatch[a.cmd](a))


if __name__ == "__main__":
    main()
