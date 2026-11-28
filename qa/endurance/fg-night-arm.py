"""FG ON STATION NIGHT (QA 2026-11-28; the Captain: "prepare for a endurance run using the latest decoder build, all options on. Wsjt-x FT991A is cleaned, holds CAT and is waiting for me to start decoding.
band is 40m. audio device is USB Codec", then: run until 12:00 local Saturday, PSK Reporter ON from the start). Derived from lrbuild-night-arm.py (same shape, same checks) with these differences:
(1) the BUILD is `main` c6d54afb (PR #304: FINE-GRID shim 20260083, the lean engine's THIN + 4 x 4 search grid ON by default in Ft8Decoder, the lean engine the default engine, the interface hardening),
    published self-contained from `_run-main` by deploy-run-main.ps1 (provenance clean), DLL SHA256 0ef023d5... (the pin);
(2) the decoder section is the STATION's VERBATIM (Deep, multi-set, v2 residual candidates, residual ungated, CQ-AP, late round, early decode, cross-cycle prior ON / shadow OFF, nhard 24, K 5 / OSD 0.05,
    subtractionMaxThreads 0 = auto) and NOTHING else is added: the engine (absent key = lean), the threads (absent = auto = the most the PC supports) and the effort (absent = normal) are the product's defaults, asserted;
(3) NO LR-BUILD keys (they are not on main); instead the run is aborted unless a per-cycle `lean:` line and a `Cross-cycle prior: outcome=` line appear in the daemon log;
(4) PSK REPORTER ON from the start with the station's own pskReporter section and tx.callsign (the Captain's callsign: read from the station config at arm time, copied into the untracked arm config and
    never printed or written to the repo); the arm record carries the PSK start epoch (`flowStartSeconds` >= it) for the standing PSK analysis (qa/endurance/psk_report_fetcher.py).
CAT OFF (WSJT-X FT991A holds the radio's CAT), auto-answer OFF, external reporting OFF, remote access OFF, no TX. WSJT-X FT991A runs beside on the same radio and device (USB Audio CODEC, no Voicemeeter),
cleaned before the run. ERA "FG ON": every figure of this run belongs to it; never pooled with an earlier night or series (the earlier eras were classic or lean WITHOUT THIN + 4 x 4).
Pre-launch asserts (any failure aborts before a single decode): DLL SHA (the pin), provenance commit + clean, port free, decoder values, safety fields, WSJT-X device == daemon device.
Read-back after launch: /api/v1/config shows crossCyclePrior TRUE, PSK enabled, engine lean or absent; /api/v1/status depth Deep, capture active on the USB CODEC; WSJT-X's live dial (from its own ALL.TXT) == --dial-mhz;
the first `lean:` and `Cross-cycle prior: outcome=` log lines. One command; --dry prints the plan and writes nothing.
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
DLL_SHA = "0ef023d55a381db9da5ccd209d4b720f1b902ed1e1e55b9c8ea6cfd114d1d77b"
COMMIT = "c6d54afb4f3bef509493c383acf46f1ed83e422f"
CODEC_NAME = "Microphone (2- USB Audio CODEC )"
BASE_CFG = Path(r"D:\Projects\claude\_qa-scratch\rr-main\config")
STATION_CFG = _sp.station_config()     # READ ONLY: its decoder section, audio device, pskReporter section and tx.callsign are the template (running account's %APPDATA%)
WSJTX_INI = str(_sp.wsjtx_ini("FT991A"))   # running account's %LOCALAPPDATA%
CFG_DIR = QA_WT / "qa" / "endurance" / "fg-night-config"      # untracked: its config.json carries the callsign
WSJTX_ALL = Path(WSJTX_INI).parent / "ALL.TXT"
PORT = 8080
LEAD_S = 75
ARCHIVE_MAX_MB = 16384
ARCHIVE_MAX_AGE_H = 48
STAGE_RX = re.compile(r"Cross-cycle prior: outcome=")
LEAN_RX = re.compile(r"Cycle \d{2}:\d{2}:\d{2}: lean: candidates=\d+")   # the daemon logs the cycle time as HH:MM:SS (the first arm attempt aborted on a yymmdd_hhmmss pattern)


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


def first_line(corpus: str, rx, wait_s: int = 180) -> bool:
    """True when a line matching rx appears in the daemon log within wait_s."""
    end = time.time() + wait_s
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
    g.add_argument("--end-utc", help="ISO UTC end time, e.g. 2026-11-28T11:00:00Z; hours are derived from the real start minute")
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
    # AUDIO ROUTE: the USB Audio CODEC directly; the device id is the station's own, the name asserted.
    assert st["audioDeviceFriendlyName"] == CODEC_NAME, st["audioDeviceFriendlyName"]
    cfg["audioDeviceId"] = st["audioDeviceId"]
    cfg["audioDeviceFriendlyName"] = st["audioDeviceFriendlyName"]
    ini_in = ini_value(WSJTX_INI, "SoundInName")
    assert ini_in == CODEC_NAME, ("WSJT-X is not on the USB Audio CODEC", ini_in)
    assert WSJTX_ALL.is_file(), "WSJT-X ALL.TXT not found"   # cleaned by the operator; its size/line count at the daemon's start are recorded
    assert ini_value(WSJTX_INI, "MonitorOFF") == "false", ini_value(WSJTX_INI, "MonitorOFF")
    cfg["port"] = PORT
    cfg["logging"]["directory"] = f"{corpus}/daemon-logs"
    cfg["decodeLog"]["path"] = f"{corpus}/ALL.TXT"
    cfg["decodeLog"]["dialFrequencyMHz"] = a.dial_mhz
    cfg["cycleAudioArchive"].update(mode="all", directory=f"{corpus}/cycle-audio", maxSizeMb=ARCHIVE_MAX_MB,
                                    maxAgeHours=ARCHIVE_MAX_AGE_H, writeManifest=True)
    # PSK REPORTER ON: the station's own section and callsign (never printed or written to the repo).
    assert st["pskReporter"].get("enabled") is True and st["tx"].get("callsign"), "the station config has no enabled pskReporter section / callsign"
    cfg["pskReporter"] = dict(st["pskReporter"])
    cfg["tx"]["callsign"] = st["tx"]["callsign"]
    cfg["decodeNoiseSuppression"] = dict(st["decodeNoiseSuppression"])     # the station's own (both filters off); the base template carries a null for one of them
    d = cfg["decoder"]
    assert cfg["cat"]["enabled"] is False and cfg["tx"]["autoAnswer"] is False
    assert cfg["externalReporting"]["enabled"] is False and cfg["remoteAccess"]["enabled"] is False
    assert cfg["pskReporter"]["enabled"] is True
    assert d["crossCyclePrior"] is True and not d.get("crossCyclePriorShadow"), d
    assert d["osdNhardMax"] == 24 and d["nhard24MigrationApplied"] is True and d["nhard40MigrationApplied"] is True, d
    assert d["decodingDepth"] == "Deep" and d["coherentFallbackEnabled"] is True and d["coherentFallbackMultiSet"] is True, d
    assert d["cqApEnabled"] is True and d["lateSubtractionRound"] is True and d["coherentFallbackResidualCandidates"] is True, d
    assert d["coherentFallbackResidualUngated"] is True and d["coherentFallbackAudio"] == "Both", d
    assert d["subtractionEnabled"] is True and d.get("earlyDecodeEnabled") is True, d
    # the product's defaults for what the station section does not carry: lean engine, automatic threads, normal effort
    assert d.get("engine") in (None, "lean"), ("the engine must be lean (absent = the default)", d.get("engine"))
    assert d.get("threads") in (None, 0), ("threads must be automatic (absent or 0)", d.get("threads"))
    assert d.get("effort") in (None, "normal"), ("effort must be normal (absent = the default)", d.get("effort"))
    if a.end_utc:
        end = dt.datetime.fromisoformat(a.end_utc.replace("Z", "+00:00"))
        a.hours = round((end - start).total_seconds() / 3600.0 - 0.005, 3)
    assert 0.5 <= a.hours <= 48, a.hours
    end = start + dt.timedelta(hours=a.hours)
    print(f"start {start.isoformat()}  corpus {corpus}  hours {a.hours}  end {end.isoformat()}  DLL {sha[:8]}  commit {COMMIT[:8]}")
    print("decoder:", json.dumps(d))
    print("audio:", cfg["audioDeviceFriendlyName"], "| WSJT-X:", ini_in, "| dial", a.dial_mhz, "| WSJT-X ini:", WSJTX_INI)
    print("PSK Reporter: enabled", cfg["pskReporter"]["enabled"], "| host", cfg["pskReporter"].get("host"), "| port", cfg["pskReporter"].get("port"), "| callsign present", bool(cfg["tx"]["callsign"]))
    print("safety: CAT", cfg["cat"]["enabled"], "| autoAnswer", cfg["tx"]["autoAnswer"], "| externalReporting", cfg["externalReporting"]["enabled"], "| remoteAccess", cfg["remoteAccess"]["enabled"])
    if a.dry:
        return
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    for fn in ("callsign-grammar.json", "callsign-regions.json", "frequencies.json", "prop-modes.json"):
        shutil.copy2(STATION_CFG.parent / fn, CFG_DIR / fn)   # the STATION's files (the QA base template's callsign-regions.json is a 7.5 kB stub: the first FG ON night showed 'Unknown' regions for most decodes)
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
    (Path(corpus) / "ERA.txt").write_text(
        "ERA \"FG ON\": a live recording of the station radio on `main` c6d54afb (PR #304: FINE-GRID shim 20260083, the lean engine with THIN + a 4 x 4 search grid ON by default, the lean engine the default engine) "
        "with the station decoder section verbatim (Deep, multi-set, v2 residual candidates, residual ungated, CQ-AP, late round, early decode, cross-cycle prior ON / shadow OFF, nhard 24, K 5 / OSD 0.05, subtraction "
        "threads auto) and the product defaults for engine, threads and effort. PSK Reporter ON from the start (the station's own section; the Captain's callsign is in the untracked arm config only). CAT OFF "
        "(WSJT-X FT991A holds the radio), auto-answer OFF, external reporting OFF, remote access OFF, no TX. WSJT-X FT991A runs beside on the same radio and device. Every figure of this run belongs to this era: "
        "never pool it with an earlier night or series (earlier eras were classic, or lean without THIN + 4 x 4).\n", encoding="utf-8")
    (Path(corpus) / "arm_readback.json").write_text(json.dumps(rb, indent=1), encoding="utf-8")
    cf = rb.get("config") if isinstance(rb.get("config"), dict) else {}
    stt = rb.get("status") if isinstance(rb.get("status"), dict) else {}
    dec = cf.get("decoder", {}) or {}
    xc_rb, shadow_rb, eng_rb = dec.get("crossCyclePrior"), dec.get("crossCyclePriorShadow"), dec.get("engine")
    psk_rb = (cf.get("pskReporter") or {}).get("enabled")
    tp = stt.get("thirdPass")
    depth_rb = tp.get("decodingDepth") if isinstance(tp, dict) else None
    cap_rb, dev_rb = stt.get("captureActive"), str(stt.get("audioDevice"))
    print("READ-BACK: crossCyclePrior", xc_rb, "| shadow", shadow_rb, "| engine", eng_rb, "| psk enabled", psk_rb, "| depth", depth_rb, "| captureActive", cap_rb, "| audioDevice", dev_rb)
    if (xc_rb is not True or shadow_rb is True or eng_rb not in (None, "lean") or psk_rb is not True or depth_rb != "Deep" or cap_rb is not True or "USB Audio CODEC" not in dev_rb):
        abort_run(f"read-back mismatch: crossCyclePrior {xc_rb!r}, shadow {shadow_rb!r}, engine {eng_rb!r}, psk {psk_rb!r}, depth {depth_rb!r}, captureActive {cap_rb!r}, audioDevice {dev_rb!r}", [])
    wsjtx_at_start = {"size": WSJTX_ALL.stat().st_size, "lines": sum(1 for _ in open(WSJTX_ALL, "rb")), "utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    print("WSJT-X ALL.TXT at the daemon's start:", wsjtx_at_start)
    live_dial = wsjtx_dial_mhz(WSJTX_ALL)
    print("LIVE DIAL from WSJT-X ALL.TXT:", live_dial, "MHz (expected", a.dial_mhz, ")")
    if live_dial is None or abs(live_dial - a.dial_mhz) > 1e-6:
        abort_run(f"WSJT-X live dial {live_dial!r} MHz differs from --dial-mhz {a.dial_mhz}, or WSJT-X decoding was not turned on within 300 s", [])
    stage = first_line(corpus, STAGE_RX)
    print("FIRST `Cross-cycle prior: outcome=` line in the log:", stage)
    if not stage:
        abort_run("no `Cross-cycle prior: outcome=` line within 180 s: the stage is not running", [])
    lean_seen = first_line(corpus, LEAN_RX)
    print("FIRST per-cycle `lean:` line in the log:", lean_seen)
    if not lean_seen:
        abort_run("no per-cycle `lean:` line within 180 s: the lean engine is not running", [])
    # PROOF THAT THE 4 x 4 GRID IS ACTIVE LIVE: the per-cycle lean line carries the spectrogram stage's wall time. In QA's replays (H40, 240 cycles, one machine) its median was 17.8 ms on the shipped build
    # before FINE-GRID, 18.0 ms with THIN only and 73.9 ms with THIN + 4 x 4 (about 4.1 x). Recorded, with a WARNING (not an abort: the live PC is slower and loaded) when the median of the first cycles is under 40 ms.
    time.sleep(150)
    spec = []
    spec_rx = re.compile(r"Cycle \d{2}:\d{2}:\d{2}: lean: .*?wall_ms spectrogram=([\d.,]+)")
    for lf in sorted(Path(corpus, "daemon-logs").glob("*.log")):
        for ln in open(lf, encoding="utf-8", errors="replace"):
            m = spec_rx.search(ln)
            if m:
                spec.append(float(m.group(1).replace(",", ".")))
    spec_med = sorted(spec)[len(spec) // 2] if spec else None
    print(f"SPECTROGRAM wall_ms median over the first {len(spec)} lean cycles: {spec_med} (replay: 17.8 = shipped before, 73.9 = THIN + 4 x 4)")
    if spec_med is None or spec_med < 40.0:
        print("*** WARNING: the spectrogram time looks like the 2 x 2 grid (under 40 ms): the 4 x 4 grid may NOT be active. Tell the Captain before leaving the run unattended. ***")
    psk_epoch = int(start.timestamp())
    (Path(corpus) / "arm_readback_summary.json").write_text(json.dumps({"crossCyclePrior": xc_rb, "shadow": shadow_rb, "engine": eng_rb, "pskEnabled": psk_rb, "depth": depth_rb, "captureActive": cap_rb,
                                                                       "audioDevice": dev_rb, "stage_line_seen": stage, "lean_line_seen": lean_seen, "wsjtx_alltxt_at_start": wsjtx_at_start,
                                                                       "psk_flowStartSeconds_min": psk_epoch, "spectrogram_ms_median_first_cycles": spec_med, "spectrogram_cycles": len(spec), "commit": COMMIT, "era": "FG ON"}), encoding="utf-8")
    until = (end + dt.timedelta(minutes=10)).timestamp()
    pol = subprocess.Popen([PY, "-X", "utf8", str(QA_WT / "qa" / "endurance" / "f2_station_poller.py"), "--port", str(PORT),
                            "--out", str(Path(corpus) / "f2_status.jsonl"), "--until-epoch", str(until),
                            "--stop-file", str(Path(corpus) / "f2_poller.stop")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200 | 0x01000000)
    (Path(corpus) / "f2_poller.pid").write_text(str(pol.pid))
    # PSK REPORTER SIDE: PSK's retrieve API only returns about the last hour of reports (the first FG ON night, fetched after the run, got 118 reports from the last 55 min of 10.4 h), so the fetcher
    # MUST poll DURING the run (every 30 min, lookback 40 min). Detached like the poller; ends at the run's end + 10 min or when psk_fetch.stop appears.
    psk_until = (end + dt.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pskp = subprocess.Popen([PY, "-X", "utf8", str(QA_WT / "qa" / "endurance" / "psk_report_fetcher.py"), "--corpus", str(Path(corpus).resolve()), "--port", str(PORT),
                             "--until-utc", psk_until], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200 | 0x01000000)
    (Path(corpus) / "psk_fetcher.pid").write_text(str(pskp.pid))
    print("PSK fetcher pid", pskp.pid, "until", psk_until)
    print("F2 poller pid", pol.pid, "until", dt.datetime.fromtimestamp(until, dt.timezone.utc).isoformat())
    print("readback written; PSK flowStartSeconds >=", psk_epoch)


if __name__ == "__main__":
    main()
