"""LR-FULL FRESH NIGHT (derived from xcon-usbcodec-endurance-arm.py, QA 2026-11-18; Captain: "arm night 1, PSK Reporter off, WSJT-X is running on 40 m" and, tonight, "wsjt-x is running. I cleaned the
wav files and all.txt. band is 40m, audio device USB Codec. It's waiting for me to turn decoding on"). A LIVE RECORDING of the station's radio for the fresh-night corpus of the LR-FULL arm: nothing is
replayed here. PSK Reporter OFF, CAT OFF, auto-answer OFF, external reporting OFF, remote access OFF, no TX. DIFFERENCE from the XC script: WSJT-X's saved `DialFreq` is not asserted (it reads 0 until WSJT-X
rewrites it); the dial is verified from WSJT-X's own first ALL.TXT lines instead (field 2, MHz), and the run is aborted if it is not --dial-mhz. The night is RESERVED for LR-FULL: never reuse it in another verdict.
Original docstring follows. Arm the "XC ON" PC endurance run on the station: the `main` build `66b3ddf1` (v0.72, shim 20260072, DLL pin bbde6eb6...6528) as deployed in `_run-main`, the STATION's decoder section
verbatim (cross-cycle prior ON, shadow OFF, v2 residual candidates, CQ-AP, late round, multi-set, Deep, nhard 24, K 5 / OSD 0.05, subtractionMaxThreads as the station has it), the audio device the USB
Audio CODEC DIRECTLY (no Voicemeeter in the path: WSJT-X FT991A reads the same device), 40 m, dial 7.074 MHz. Derived from rf4on-endurance-arm.py (QA 2026-11-15; Captain: "setup an endurance run.
unattended. band is 40m. end time about 12:00 local time sunday. Audio device is USB Codec. wsjt-x FT991A is cleaned and waiting for monitor"). The account is `frans`: every per-account path comes from
station_paths (the running account's %LOCALAPPDATA% / %APPDATA%), and the supervisor's gatherer is handed --wsjtx-root = the directory of the WSJT-X ini this script was given, so the gather cannot fall
back to another account's frozen log.
ERA: "XC ON" (on top of "v2 ON" and "CQ-AP ON"; the interaction is unmeasured). Every figure of this run belongs to it; never pooled with an earlier night or series. ERA.txt in the corpus says so.
Pre-launch asserts (any failure aborts before a single decode): DLL SHA (the pin), provenance commit + clean, port free, decoder values, safety fields (CAT off, auto-answer off, external reporting off,
PSK off, remote access off), WSJT-X device == daemon device, WSJT-X dial == --dial-mhz.
Read-back after launch: /api/v1/config shows crossCyclePrior TRUE, depth Deep, capture active on the USB CODEC; the first `Cross-cycle prior: outcome=` log line must appear (else the run is aborted).
One command; --dry prints the plan and writes nothing.
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
sys.path.insert(0, str(QA_WT / "qa"))  # station_paths (per-account paths)
import station_paths as _sp  # noqa: E402
PY = r"D:\Projects\claude\_qa-scratch\rr-main\tree\qa\rr-study\.venv\Scripts\python.exe"
PUB = Path(r"D:\Projects\claude\_run-main\src\OpenWSFZ.Daemon\bin\Release\net10.0\win-x64\publish")
EXE = str(PUB / "OpenWSFZ.Daemon.exe")
DLL_SHA = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"
COMMIT = "66b3ddf1229ee5cd2aea3d868e7c0d95ec1f2037"
CODEC_NAME = "Microphone (2- USB Audio CODEC )"
BASE_CFG = Path(r"D:\Projects\claude\_qa-scratch\rr-main\config")
STATION_CFG = _sp.station_config()     # READ ONLY: its decoder section and audio device are the template (running account's %APPDATA%)
WSJTX_INI = str(_sp.wsjtx_ini("FT991A"))   # running account's %LOCALAPPDATA%
CFG_DIR = QA_WT / "qa" / "endurance" / "lrfull-night-config"
WSJTX_ALL = Path(WSJTX_INI).parent / "ALL.TXT"   # the WSJT-X FT991A profile's decode log (cleaned before the run)
PORT = 8080
LEAD_S = 75
ARCHIVE_MAX_MB = 16384
ARCHIVE_MAX_AGE_H = 48
STAGE_RX = re.compile(r"Cross-cycle prior: outcome=")


def port_free(port: int) -> bool:
    s = socket.socket()
    try:
        return s.connect_ex(("127.0.0.1", port)) != 0
    finally:
        s.close()


def abort_run(reason: str, pids: list) -> None:
    """Stop everything this script started (daemon, supervisor, poller) and exit non-zero."""
    print("*** ABORT:", reason, "***")
    ps = ("Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'endurance_supervisor|run_endurance|f2_station_poller' -or $_.Name -eq 'OpenWSFZ.Daemon.exe') -and $_.ProcessId -ne $PID } "
          "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
    print("run stopped; exit 3")
    sys.exit(3)


def first_stage_line(corpus: str, wait_s: int = 180) -> bool:
    """True when a `Cross-cycle prior: outcome=` line appears in the daemon log (the stage is ON and running)."""
    end = time.time() + wait_s
    while time.time() < end:
        for lf in sorted(Path(corpus, "daemon-logs").glob("*.log")):
            try:
                for ln in open(lf, encoding="utf-8", errors="replace"):
                    if STAGE_RX.search(ln):
                        return True
            except OSError:
                pass
        time.sleep(5)
    return False


def wsjtx_dial_mhz(all_txt: Path, wait_s: int = 300):
    """The dial frequency (MHz) from the first Rx FT8 line of WSJT-X's own ALL.TXT (field 2); None if no line appears within wait_s (decoding not turned on)."""
    end = time.time() + wait_s
    while time.time() < end:
        try:
            for ln in open(all_txt, encoding="utf-8", errors="replace"):
                f = ln.split()
                if len(f) >= 4 and f[2] == "Rx" and f[3] == "FT8":
                    return float(f[1])
        except (OSError, ValueError):
            pass
        time.sleep(5)
    return None


def ini_value(ini: str, key: str):
    for ln in open(ini, encoding="utf-8", errors="replace"):
        if ln.startswith(key + "="):
            return ln.strip().split("=", 1)[1]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hours", type=float)
    g.add_argument("--end-utc", help="ISO UTC end time, e.g. 2026-11-15T11:00:00Z; hours are derived from the real start minute")
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
    for _need in (STATION_CFG, Path(WSJTX_INI)):
        if not _need.is_file():
            sys.exit(f"ERROR: {_need} not found for the running account. Point at it with {_sp.ENV_STATION_CONFIG} / {_sp.ENV_WSJTX_INI}.")
    st = json.loads(STATION_CFG.read_text(encoding="utf-8"))
    cfg["decoder"] = dict(st["decoder"])
    # AUDIO ROUTE: the USB Audio CODEC directly; the device id is the station's own (the one the daemon captured on all day), the name asserted.
    assert st["audioDeviceFriendlyName"] == CODEC_NAME, st["audioDeviceFriendlyName"]
    cfg["audioDeviceId"] = st["audioDeviceId"]
    cfg["audioDeviceFriendlyName"] = st["audioDeviceFriendlyName"]
    ini_in = ini_value(WSJTX_INI, "SoundInName")
    assert ini_in == CODEC_NAME, ("WSJT-X is not on the USB Audio CODEC", ini_in)
    dial_ini = ini_value(WSJTX_INI, "DialFreq")      # informational only: stale until WSJT-X rewrites its ini; the live dial is verified from ALL.TXT after the start
    assert WSJTX_ALL.is_file() and WSJTX_ALL.stat().st_size == 0, ("WSJT-X ALL.TXT is not clean (cleaned before the run, as the Captain said)", WSJTX_ALL.exists() and WSJTX_ALL.stat().st_size)
    assert ini_value(WSJTX_INI, "MonitorOFF") == "false", ini_value(WSJTX_INI, "MonitorOFF")
    cfg["port"] = PORT
    cfg["logging"]["directory"] = f"{corpus}/daemon-logs"
    cfg["decodeLog"]["path"] = f"{corpus}/ALL.TXT"
    cfg["decodeLog"]["dialFrequencyMHz"] = a.dial_mhz
    cfg["cycleAudioArchive"].update(mode="all", directory=f"{corpus}/cycle-audio", maxSizeMb=ARCHIVE_MAX_MB,
                                    maxAgeHours=ARCHIVE_MAX_AGE_H, writeManifest=True)
    d = cfg["decoder"]
    assert cfg["cat"]["enabled"] is False and cfg["tx"]["autoAnswer"] is False
    assert cfg["externalReporting"]["enabled"] is False and not (cfg.get("pskReporter") or {}).get("enabled") and cfg["remoteAccess"]["enabled"] is False
    assert d["crossCyclePrior"] is True and not d.get("crossCyclePriorShadow"), d
    assert d["osdNhardMax"] == 24 and d["nhard24MigrationApplied"] is True and d["nhard40MigrationApplied"] is True, d
    assert d["decodingDepth"] == "Deep" and d["coherentFallbackEnabled"] is True and d["coherentFallbackMultiSet"] is True, d
    assert d["cqApEnabled"] is True and d["lateSubtractionRound"] is True and d["coherentFallbackResidualCandidates"] is True, d
    assert d["subtractionEnabled"] is True and d.get("earlyDecodeEnabled") is True, d
    assert not d.get("diagThirdRunUngated") and not d.get("diagLateFallbackOnResidual"), ("the shipped stack must have both LR-FULL diag switches absent or OFF", d)
    if a.end_utc:
        end = dt.datetime.fromisoformat(a.end_utc.replace("Z", "+00:00"))
        a.hours = round((end - start).total_seconds() / 3600.0 - 0.005, 3)
    assert 0.5 <= a.hours <= 48, a.hours
    end = start + dt.timedelta(hours=a.hours)
    print(f"start {start.isoformat()}  corpus {corpus}  hours {a.hours}  end {end.isoformat()}  DLL {sha[:8]}  commit {COMMIT[:8]}")
    print("decoder:", json.dumps(d))
    print("audio:", cfg["audioDeviceFriendlyName"], "| WSJT-X:", ini_in, "| dial", a.dial_mhz, "| WSJT-X ini:", WSJTX_INI)
    if a.dry:
        return
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    for fn in ("callsign-grammar.json", "callsign-regions.json", "frequencies.json", "prop-modes.json"):
        shutil.copy2(BASE_CFG / fn, CFG_DIR / fn)
    (CFG_DIR / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    wait = (start - dt.datetime.now(dt.timezone.utc)).total_seconds()
    assert wait > 5, "too late; rerun"
    time.sleep(max(0.0, wait))
    r = subprocess.run([PY, "-X", "utf8", str(QA_WT / "qa" / "endurance" / "run_endurance.py"), "--daemon-exe", EXE,
                        "--config", str(CFG_DIR / "config.json"), "--port", str(PORT), "--wsjtx-ini", WSJTX_INI,
                        "--hours", str(a.hours)], capture_output=True, text=True)
    print(r.stdout, r.stderr)
    assert f"{stamp}_endurance_run" in r.stdout, "the runner named a different corpus dir than the config: STOP and fix"
    time.sleep(20)
    rb = {}
    for ep in ("config", "status"):
        try:
            rb[ep] = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/{ep}", timeout=10).read())
        except Exception as ex:   # noqa: BLE001
            rb[ep] = f"unreadable: {type(ex).__name__}"
    Path(corpus).mkdir(parents=True, exist_ok=True)
    (Path(corpus) / "ERA.txt").write_text("LR-FULL FRESH NIGHT 1: a live recording of the station radio on the SHIPPED stack (build 66b3ddf1, v0.72, shim 20260072; XC ON shadow OFF, v2 + R-F4, CQ-AP, late round, multi-set, Deep, nhard 24), 40 m dial 7.074 MHz, USB Audio CODEC direct, PSK Reporter OFF, CAT OFF, no TX. RESERVED for the LR-FULL arm (spec b2d9883a + Amendments): never use this night in another verdict. Nothing replayed here.", encoding="utf-8")
    (Path(corpus) / "arm_readback.json").write_text(json.dumps(rb, indent=1), encoding="utf-8")
    cf = rb.get("config") if isinstance(rb.get("config"), dict) else {}
    stt = rb.get("status") if isinstance(rb.get("status"), dict) else {}
    dec = cf.get("decoder", {}) or {}
    xc_rb, shadow_rb = dec.get("crossCyclePrior"), dec.get("crossCyclePriorShadow")
    tp = stt.get("thirdPass")
    depth_rb = tp.get("decodingDepth") if isinstance(tp, dict) else None
    cap_rb, dev_rb = stt.get("captureActive"), str(stt.get("audioDevice"))
    print("READ-BACK: crossCyclePrior", xc_rb, "| shadow", shadow_rb, "| depth", depth_rb, "| captureActive", cap_rb, "| audioDevice", dev_rb)
    if xc_rb is not True or shadow_rb is True or depth_rb != "Deep" or cap_rb is not True or "USB Audio CODEC" not in dev_rb:
        abort_run(f"read-back mismatch: crossCyclePrior {xc_rb!r} (want True), shadow {shadow_rb!r} (want not True), depth {depth_rb!r} (want 'Deep'), captureActive {cap_rb!r}, audioDevice {dev_rb!r}", [])
    live_dial = wsjtx_dial_mhz(WSJTX_ALL)
    print("LIVE DIAL from WSJT-X ALL.TXT:", live_dial, "MHz (expected", a.dial_mhz, ")")
    if live_dial is None or abs(live_dial - a.dial_mhz) > 1e-6:
        abort_run(f"WSJT-X live dial {live_dial!r} MHz differs from --dial-mhz {a.dial_mhz}, or WSJT-X decoding was not turned on within 300 s", [])
    stage = first_stage_line(corpus)
    print("FIRST `Cross-cycle prior: outcome=` line in the log:", stage)
    if not stage:
        abort_run("no `Cross-cycle prior: outcome=` line within 180 s: the stage is not running", [])
    (Path(corpus) / "arm_readback_summary.json").write_text(json.dumps({"crossCyclePrior": xc_rb, "shadow": shadow_rb, "depth": depth_rb, "captureActive": cap_rb, "audioDevice": dev_rb, "stage_line_seen": stage, "era": "XC ON"}), encoding="utf-8")
    until = (end + dt.timedelta(minutes=10)).timestamp()
    pol = subprocess.Popen([PY, "-X", "utf8", str(QA_WT / "qa" / "endurance" / "f2_station_poller.py"), "--port", str(PORT),
                            "--out", str(Path(corpus) / "f2_status.jsonl"), "--until-epoch", str(until),
                            "--stop-file", str(Path(corpus) / "f2_poller.stop")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200 | 0x01000000)
    (Path(corpus) / "f2_poller.pid").write_text(str(pol.pid))
    print("F2 poller pid", pol.pid, "until", dt.datetime.fromtimestamp(until, dt.timezone.utc).isoformat())
    print("readback written; decoder section:", json.dumps(dec))


if __name__ == "__main__":
    main()
