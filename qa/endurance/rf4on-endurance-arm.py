"""Arm the RF4ON 'new era' endurance run on the station PC: PR #271 build (qa/coh-gate-r-f4-pr, fa119fe0, v0.67) with decoder.coherentFallbackResidualUngated = true (COH-GATE-G R-F4),
Both audio mode, multi-set ON, Deep, nhard 24 (QA 2026-10-28; Captain: "prepare for an endurance run with the pc and wsjt-x FT991A (cleaned) ... be sure to switch the setting on and that it counts
against the new era (just like sol should)"). Derived from di7-endurance-arm.py; the audio route and the strip handling are unchanged (Voicemeeter Stereo Input 1 -> B1; WSJT-X and the daemon both read B1).
ERA: every figure of this run belongs to the RF4ON era (setting ON); the corpus folder gets ERA.txt with that label and the run never pools with an earlier night. One command; --dry prints the plan and writes nothing.
Pre-launch asserts (any failure aborts before a single decode): DLL SHA (Windows pin 1ba8dc3d...), provenance commit + clean, port free, decoder section values (incl. the new setting), Voicemeeter strips, WSJT-X device.
Read-back after launch: /api/v1/config must show the setting TRUE, and the first fallback log line must carry ungated=N (else the run is aborted, K6).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

QA_WT = Path(r"D:\Projects\claude\OpenWSFZ\worktrees\qa")
sys.path.insert(0, str(QA_WT / "qa"))  # station_paths (per-account paths, 2026-11-02)
import station_paths as _sp  # noqa: E402
PY = r"D:\Projects\claude\_qa-scratch\rr-main\tree\qa\rr-study\.venv\Scripts\python.exe"
PUB = Path(r"D:\Projects\claude\_qa-scratch\coh-gate-r-f4-prwt\src\OpenWSFZ.Daemon\bin\Release\net10.0\win-x64\publish")
EXE = str(PUB / "OpenWSFZ.Daemon.exe")
DLL_SHA = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
COMMIT = "fa119fe085cb6fa17c06e39ed12c80747aa58eac"
B1_ID = "{0.0.1.00000000}.{8dbb88e8-fd07-44b8-9ee9-88b906b8d11f}"
B1_NAME = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
RADIO_STRIP = 0
VM = QA_WT / "qa" / "endurance" / "vm_strip.py"
BASE_CFG = Path(r"D:\Projects\claude\_qa-scratch\rr-main\config")
STATION_CFG = _sp.station_config()     # READ ONLY: its decoder section is the template; running account's %APPDATA% (QA_STATION_CONFIG overrides)
WSJTX_INI = str(_sp.wsjtx_ini("FT991A"))   # running account's %LOCALAPPDATA% (QA_WSJTX_INI overrides)
CFG_DIR = QA_WT / "qa" / "endurance" / "rf4on-endurance-config"
PORT = 8080
LEAD_S = 75
SUB_THREADS = 8
ARCHIVE_MAX_MB = 16384
ARCHIVE_MAX_AGE_H = 48


def port_free(port: int) -> bool:
    s = socket.socket()
    try:
        return s.connect_ex(("127.0.0.1", port)) != 0
    finally:
        s.close()


def abort_run(reason: str, vmlog: str, pids: list) -> None:
    """K6: stop everything this script started and exit non-zero. Mutes the radio strip first (the unmute is the first side effect), then stops the daemon,
    the supervisor, the mute-at watcher and the F2 poller."""
    print("*** ABORT:", reason, "***")
    subprocess.run([sys.executable, "-I", str(VM), "mute", "--strip", str(RADIO_STRIP), "--log", vmlog], capture_output=True, text=True)
    ps = ("Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'endurance_supervisor|run_endurance' -or $_.Name -eq 'OpenWSFZ.Daemon.exe') -and $_.ProcessId -ne $PID } "
          "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
    print("run stopped; radio strip muted; exit 3")
    sys.exit(3)


def first_workers(corpus: str, wait_s: int = 150):
    """The resolved worker count from the first R12' line (counts only)."""
    end = time.time() + wait_s
    rx = re.compile(r"Coherent fallback: .* workers=(\d+),")
    while time.time() < end:
        for lf in sorted(Path(corpus, "daemon-logs").glob("*.log")):
            try:
                for ln in open(lf, encoding="utf-8", errors="replace"):
                    m = rx.search(ln)
                    if m:
                        return int(m.group(1))
            except OSError:
                pass
        time.sleep(5)
    return None


def first_ungated(corpus: str, wait_s: int = 150) -> bool:
    """True when a fallback log line carries ungated=N (printed only while the setting is effective: ON and Both mode)."""
    end = time.time() + wait_s
    rx = re.compile(r"Coherent fallback: .*, ungated=\d+\.")
    while time.time() < end:
        for lf in sorted(Path(corpus, "daemon-logs").glob("*.log")):
            try:
                for ln in open(lf, encoding="utf-8", errors="replace"):
                    if rx.search(ln):
                        return True
            except OSError:
                pass
        time.sleep(5)
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hours", type=float)
    g.add_argument("--end-utc", help="ISO UTC end time, e.g. 2026-10-10T09:00:00Z; hours are derived from the real start minute")
    ap.add_argument("--dial-mhz", type=float, required=True, help="the radio's / WSJT-X dial frequency in MHz (no default: say it)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    sha = hashlib.sha256((PUB / "libft8.dll").read_bytes()).hexdigest()
    assert sha == DLL_SHA, ("published DLL SHA", sha)
    prov = json.loads((PUB / "build_provenance.json").read_text(encoding="utf-8"))
    assert prov["commit"] == COMMIT and prov["build_dirty"] is False, prov
    assert port_free(PORT), f"port {PORT} is in use (stop the other daemon first)"
    now = dt.datetime.now(dt.timezone.utc)
    start = (now + dt.timedelta(seconds=LEAD_S)).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    stamp = start.strftime("%Y%m%d_%H%M")
    corpus = (QA_WT / "artefacts" / f"{stamp}_endurance_run").as_posix()
    cfg = json.loads((BASE_CFG / "config.json").read_text(encoding="utf-8"))
    for _need in (STATION_CFG, Path(WSJTX_INI)):   # a missing file under a fresh account is a message, not a traceback
        if not _need.is_file():
            sys.exit(f"ERROR: {_need} not found for the running account. Copy the station config / WSJT-X settings "
                     f"over, or point at them with {_sp.ENV_STATION_CONFIG} / {_sp.ENV_WSJTX_INI}.")
    st_dec = json.loads(STATION_CFG.read_text(encoding="utf-8"))["decoder"]
    cfg["decoder"] = dict(st_dec)
    # AUDIO ROUTE (Captain, 2026-10-19): both decoders on Voicemeeter Out B1 (the radio is on Stereo Input 1).
    cfg["audioDeviceId"] = B1_ID
    cfg["audioDeviceFriendlyName"] = B1_NAME
    ini_in = [ln.strip() for ln in open(WSJTX_INI, encoding="utf-8", errors="replace") if ln.startswith("SoundInName=")]
    assert ini_in and ini_in[0] == "SoundInName=" + B1_NAME, ("WSJT-X is not on Voicemeeter Out B1", ini_in)
    # Voicemeeter state (read-only here): the radio strip routes to B1, the AUX (replay) strip is muted, Strip[2] does not feed B1.
    vm = {}
    for i in (0, 2, 4):
        o = subprocess.run([sys.executable, "-I", str(VM), "status", "--strips", str(i)], capture_output=True, text=True)
        vm[i] = json.loads(o.stdout.strip().splitlines()[-1])
    assert vm[RADIO_STRIP]["B1"] == 1.0 and vm[2]["B1"] == 0.0 and vm[4]["mute"] == 1.0, vm
    cfg["port"] = PORT
    cfg["logging"]["directory"] = f"{corpus}/daemon-logs"
    cfg["decodeLog"]["path"] = f"{corpus}/ALL.TXT"
    cfg["decodeLog"]["dialFrequencyMHz"] = a.dial_mhz
    cfg["cycleAudioArchive"].update(mode="all", directory=f"{corpus}/cycle-audio", maxSizeMb=ARCHIVE_MAX_MB,
                                    maxAgeHours=ARCHIVE_MAX_AGE_H, writeManifest=True)
    cfg["decoder"]["subtractionMaxThreads"] = SUB_THREADS   # 8, the earlier parameter (Captain, relayed by the Architect 2026-10-22)
    cfg["decoder"]["decodingDepth"] = "Deep"
    cfg["decoder"]["coherentFallbackEnabled"] = True   # EXPLICIT: the station config carries an explicit false from the R14 teardown
    cfg["decoder"]["coherentFallbackMultiSet"] = True
    cfg["decoder"]["coherentFallbackAudio"] = "Both"
    cfg["decoder"]["coherentFallbackResidualUngated"] = True   # THE SETTING UNDER TEST (R-F4): switched ON, explicit
    # Captain 2026-10-28: 10 / 0.10 (code defaults = the sol series, the replays and the second night), NOT the station config's 5 / 0.05 of today (its decoder section is only the template).
    cfg["decoder"]["kMinScorePass2"] = 10
    cfg["decoder"]["osdCorrThreshold"] = 0.1
    d = cfg["decoder"]
    assert cfg["cat"]["enabled"] is False and cfg["tx"]["autoAnswer"] is False and cfg["externalReporting"]["enabled"] is False
    assert d["osdNhardMax"] == 24 and d["nhard24MigrationApplied"] is True and d["nhard40MigrationApplied"] is True, d
    assert d["decodingDepth"] == "Deep" and d["coherentFallbackEnabled"] is True and d["subtractionMaxThreads"] == SUB_THREADS == 8
    assert d["kMinScorePass2"] == 10 and abs(d["osdCorrThreshold"] - 0.1) < 1e-9, d
    assert d["coherentFallbackResidualUngated"] is True and d["coherentFallbackAudio"] == "Both" and d["coherentFallbackMultiSet"] is True, d
    assert d["subtractionEnabled"] is True and d.get("earlyDecodeEnabled") is True and cfg["audioDeviceFriendlyName"] == B1_NAME
    if a.end_utc:
        end = dt.datetime.fromisoformat(a.end_utc.replace("Z", "+00:00"))
        a.hours = round((end - start).total_seconds() / 3600.0 - 0.005, 3)
    assert 0.5 <= a.hours <= 48, a.hours
    end = start + dt.timedelta(hours=a.hours)
    print(f"start {start.isoformat()}  corpus {corpus}  hours {a.hours}  end {end.isoformat()}  DLL {sha[:8]}  commit {COMMIT[:8]}")
    print("decoder:", json.dumps(d))
    print("audio:", cfg["audioDeviceFriendlyName"], "| WSJT-X:", ini_in[0], "| Voicemeeter:", json.dumps(vm))
    if a.dry:
        return
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    for fn in ("callsign-grammar.json", "callsign-regions.json", "frequencies.json", "prop-modes.json"):
        shutil.copy2(BASE_CFG / fn, CFG_DIR / fn)
    (CFG_DIR / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    wait = (start - dt.datetime.now(dt.timezone.utc)).total_seconds()
    assert wait > 5, "too late; rerun"
    time.sleep(max(0.0, wait))
    vmlog = str(CFG_DIR / f"voicemeeter_actions_{stamp}.jsonl")
    u = subprocess.run([sys.executable, "-I", str(VM), "unmute", "--strip", str(RADIO_STRIP), "--log", vmlog], capture_output=True, text=True)
    print("VOICEMEETER unmute:", u.stdout.strip(), "rc", u.returncode)
    assert u.returncode == 0, "could not unmute the radio strip: STOP"
    r = subprocess.run([PY, "-X", "utf8", str(QA_WT / "qa" / "endurance" / "run_endurance.py"), "--daemon-exe", EXE,
                        "--config", str(CFG_DIR / "config.json"), "--port", str(PORT), "--wsjtx-ini", WSJTX_INI,
                        "--hours", str(a.hours)], capture_output=True, text=True)
    print(r.stdout, r.stderr)
    mute_at = (end + dt.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    wd = subprocess.Popen([sys.executable, "-I", str(VM), "mute-at", "--strip", str(RADIO_STRIP), "--utc", mute_at, "--log", vmlog],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200 | 0x01000000)
    print("VOICEMEETER mute-at watcher pid", wd.pid, "mutes strip", RADIO_STRIP, "at", mute_at, "log", vmlog)
    assert f"{stamp}_endurance_run" in r.stdout, "the runner named a different corpus dir than the config: STOP and fix"
    # read-back from the running daemon (best effort, written next to the corpus)
    time.sleep(20)
    rb = {}
    for ep in ("config", "status"):
        try:
            rb[ep] = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/{ep}", timeout=10).read())
        except Exception as ex:   # noqa: BLE001
            rb[ep] = f"unreadable: {type(ex).__name__}"
    Path(corpus).mkdir(parents=True, exist_ok=True)
    (Path(corpus) / "ERA.txt").write_text("RF4ON era: decoder.coherentFallbackResidualUngated = true, Both, multi-set ON, Deep, nhard 24. Build fa119fe0 (PR 271, v0.67). Never pooled with any earlier night or series.\n", encoding="utf-8")
    (Path(corpus) / "arm_readback.json").write_text(json.dumps(rb, indent=1), encoding="utf-8")
    thirdpass = rb.get("status", {}).get("thirdPass") if isinstance(rb.get("status"), dict) else None
    flag_rb = (rb.get("config", {}).get("decoder", {}) or {}).get("coherentFallbackEnabled") if isinstance(rb.get("config"), dict) else None
    ung_rb = (rb.get("config", {}).get("decoder", {}) or {}).get("coherentFallbackResidualUngated") if isinstance(rb.get("config"), dict) else None
    thr_rb = (rb.get("config", {}).get("decoder", {}) or {}).get("subtractionMaxThreads") if isinstance(rb.get("config"), dict) else None
    thirdpass = rb.get("status", {}).get("thirdPass") if isinstance(rb.get("status"), dict) else None
    depth_rb = thirdpass.get("decodingDepth") if isinstance(thirdpass, dict) else None
    print("READ-BACK: ungated setting", ung_rb, "| fallback flag", flag_rb, "| depth", depth_rb, "| subtractionMaxThreads", thr_rb)
    # K6: no run is left armed on a failed read-back (the F2 poller is not started yet; the mute watcher is)
    if ung_rb is not True or flag_rb is not True or depth_rb != "Deep" or thr_rb != SUB_THREADS:
        abort_run(f"read-back mismatch: ungated {ung_rb!r} (want True), flag {flag_rb!r} (want True), depth {depth_rb!r} (want 'Deep'), threads {thr_rb!r} (want {SUB_THREADS})", vmlog, [wd.pid])
    wk = first_workers(corpus)
    ung_line = first_ungated(corpus)
    print("FIRST FALLBACK LINE carries ungated=N:", ung_line)
    if not ung_line:
        abort_run("the first fallback log line carries no ungated=N: the setting is not effective (Both mode and the setting ON are both required)", vmlog, [wd.pid])
    print("FIRST R12' LINE: workers =", wk, "-> OK" if wk == SUB_THREADS else "-> *** NOT 8 (descriptive V-F reading; look at it) ***")
    (Path(corpus) / "arm_readback_summary.json").write_text(json.dumps({"flag": flag_rb, "depth": depth_rb, "subtractionMaxThreads": thr_rb, "first_r12_workers": wk, "ungated_in_first_fallback_line": ung_line, "ungated_setting": ung_rb, "era": "RF4ON"}), encoding="utf-8")
    # F2 counters: 1 Hz poller, detached, ends itself 10 min after the window closes
    until = (end + dt.timedelta(minutes=10)).timestamp()
    pol = subprocess.Popen([PY, "-X", "utf8", str(QA_WT / "qa" / "endurance" / "f2_station_poller.py"), "--port", str(PORT),
                            "--out", str(Path(corpus) / "f2_status.jsonl"), "--until-epoch", str(until),
                            "--stop-file", str(Path(corpus) / "f2_poller.stop")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200 | 0x01000000)
    (Path(corpus) / "f2_poller.pid").write_text(str(pol.pid))
    print("F2 poller pid", pol.pid, "until", dt.datetime.fromtimestamp(until, dt.timezone.utc).isoformat())
    print("readback written; decoder section:", json.dumps(rb.get("config", {}).get("decoder") if isinstance(rb.get("config"), dict) else rb.get("config")))


if __name__ == "__main__":
    main()
