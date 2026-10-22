"""Arm the THIRD-PASS (Deep) 40 m endurance run (QA 2026-10-18). One command; --dry prints the plan and writes nothing.

NOTHING is hard-coded about WHEN: it starts when QA runs it on the Captain's word ("It starts when I say so"), at the next full minute with
LEAD_S of lead, and it stops after --hours, which has no default and must be given.

Build under test: _qa-scratch/endur-tp/tree at a329cea9 (feat/third-pass-deep on main 535661a2 = B2 + shim 20260062; NOT decoding_improvement: the merge conflicts in WebApp.cs),
published self-contained; libft8.dll SHA-256 06e513a4...2613 (asserted below). decoder.decodingDepth = Deep (asserted, and read back from /api/v1/status thirdPass.decodingDepth).
F2 counters: f2_station_poller.py (1 Hz, capture-loss + third-pass counters) is started with the run; f2_station_count.py reads it and the daemon log afterwards. Decoder section = the station's current one (nhard 24 era):
osdNhardMax 24, both migration markers true, subtraction ON, early decode ON. Every other setting (audio device, receive-only, port) is the
2026-10-04 endurance config's (rr-main config), with paths rewritten; the AUDIO DEVICE is the direct USB CODEC (the station's own device fields) and WSJT-X must be on the same device (asserted from its ini) to the new corpus directory.

Pre-launch asserts (any failure aborts before a single decode): DLL SHA, provenance commit, clean provenance, port free, decoder section values.
Post-launch: GET /api/v1/config and /api/v1/status are read back into <corpus>/arm_readback.json (osdNhardMax 24, marker true, shim, version).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

QA_WT = Path(r"D:\Projects\claude\OpenWSFZ\worktrees\qa")
PY = r"D:\Projects\claude\_qa-scratch\rr-main\tree\qa\rr-study\.venv\Scripts\python.exe"
PUB = Path(r"D:\Projects\claude\_qa-scratch\endur-tp\tree\src\OpenWSFZ.Daemon\bin\Release\net10.0\win-x64\publish")
EXE = str(PUB / "OpenWSFZ.Daemon.exe")
DLL_SHA = "06e513a4384dd3da118fb02041b040a811cdf6157062de302de5397691f92613"
COMMIT = "a329cea9db29458c6f9f78e0b235ef1d65f30f34"
BASE_CFG = Path(r"D:\Projects\claude\_qa-scratch\rr-main\config")
STATION_CFG = Path(r"C:\Users\Frank\AppData\Roaming\OpenWSFZ\config.json")     # READ ONLY: its decoder section is the template
WSJTX_INI = r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\WSJT-X - FT991A.ini"
CFG_DIR = QA_WT / "qa" / "endurance" / "tp-deep-config"
PORT = 8080
DIAL_MHZ = 7.074
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


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hours", type=float)
    g.add_argument("--end-utc", help="ISO UTC end time, e.g. 2026-10-10T09:00:00Z; hours are derived from the real start minute")
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
    st_dec = json.loads(STATION_CFG.read_text(encoding="utf-8"))["decoder"]
    cfg["decoder"] = dict(st_dec)
    # AUDIO ROUTE (Captain, 2026-10-09): BOTH decoders on the direct USB CODEC (no Voicemeeter). The device fields are the station's own.
    st_all = json.loads(STATION_CFG.read_text(encoding="utf-8"))
    cfg["audioDeviceId"] = st_all["audioDeviceId"]
    cfg["audioDeviceFriendlyName"] = st_all["audioDeviceFriendlyName"]
    ini_in = [ln.strip() for ln in open(WSJTX_INI, encoding="utf-8", errors="replace") if ln.startswith("SoundInName=")]
    assert ini_in and "USB Audio CODEC" in ini_in[0] and "Voicemeeter" not in ini_in[0], ("WSJT-X is not on the direct CODEC yet", ini_in)
    cfg["port"] = PORT
    cfg["logging"]["directory"] = f"{corpus}/daemon-logs"
    cfg["decodeLog"]["path"] = f"{corpus}/ALL.TXT"
    cfg["decodeLog"]["dialFrequencyMHz"] = DIAL_MHZ
    cfg["cycleAudioArchive"].update(mode="all", directory=f"{corpus}/cycle-audio", maxSizeMb=ARCHIVE_MAX_MB,
                                    maxAgeHours=ARCHIVE_MAX_AGE_H, writeManifest=True)
    cfg["decoder"]["subtractionMaxThreads"] = SUB_THREADS
    cfg["decoder"]["decodingDepth"] = "Deep"
    d = cfg["decoder"]
    assert cfg["cat"]["enabled"] is False and cfg["tx"]["autoAnswer"] is False and cfg["externalReporting"]["enabled"] is False
    assert d["osdNhardMax"] == 24 and d["nhard24MigrationApplied"] is True and d["nhard40MigrationApplied"] is True, d
    assert d["decodingDepth"] == "Deep"
    assert d["subtractionEnabled"] is True and d.get("earlyDecodeEnabled") is True and cfg["audioDeviceFriendlyName"].startswith("Microphone (2- USB Audio CODEC")
    if a.end_utc:
        end = dt.datetime.fromisoformat(a.end_utc.replace("Z", "+00:00"))
        a.hours = round((end - start).total_seconds() / 3600.0 - 0.005, 3)
    assert 0.5 <= a.hours <= 48, a.hours
    end = start + dt.timedelta(hours=a.hours)
    print(f"start {start.isoformat()}  corpus {corpus}  hours {a.hours}  end {end.isoformat()}  DLL {sha[:8]}  commit {COMMIT[:8]}")
    print("decoder:", json.dumps(d))
    print("audio:", cfg["audioDeviceFriendlyName"], "| WSJT-X:", ini_in[0])
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
    # read-back from the running daemon (best effort, written next to the corpus)
    time.sleep(20)
    rb = {}
    for ep in ("config", "status"):
        try:
            rb[ep] = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/{ep}", timeout=10).read())
        except Exception as ex:   # noqa: BLE001
            rb[ep] = f"unreadable: {type(ex).__name__}"
    Path(corpus).mkdir(parents=True, exist_ok=True)
    (Path(corpus) / "arm_readback.json").write_text(json.dumps(rb, indent=1), encoding="utf-8")
    thirdpass = rb.get("status", {}).get("thirdPass") if isinstance(rb.get("status"), dict) else None
    print("THIRD PASS READ-BACK:", json.dumps(thirdpass), "-> OK" if isinstance(thirdpass, dict) and thirdpass.get("decodingDepth") == "Deep" else "-> *** NOT DEEP: STOP AND LOOK ***")
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
