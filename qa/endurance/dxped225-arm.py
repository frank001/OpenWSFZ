"""Arm the #225 DXPEDITION (type 0.1) 40 m endurance run on the candidate build 87beed94 (QA 2026-10-19; Captain: "run it as late as possible with a
deadline of finishing at 16:30" local = 14:30Z; the Architect approved the build and the plan). One command; --dry prints the plan and writes nothing.

Build under test: _qa-scratch/endur-225/tree at 87beed94 (feat/dxpedition-decode-225 on main 5229beec = Deep default, late batches, shim 20260064), published
self-contained; libft8.dll SHA-256 51a28ff6...f37f (asserted). decoder.decodingDepth = Deep (asserted, read back from /api/v1/status thirdPass.decodingDepth).
AUDIO ROUTE (Captain, 2026-10-19): the radio is on Voicemeeter Stereo Input 1 (Strip[0]) routed to B1; BOTH WSJT-X and the daemon read "Voicemeeter Out B1".
Strip[0] is UNMUTED here just before the run starts and MUTED again at the end by a detached watcher (qa/endurance/vm_strip.py, every write read back and logged).
Strip[4] (AUX, the WAV-replay input) stays muted; Strip[2] must not feed B1 (asserted). Decoder section = the station's own (Architect: no other change).
Pre-launch asserts (any failure aborts before a single decode): DLL SHA, provenance commit + clean, port free, decoder section values, Voicemeeter strips, WSJT-X device.
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
PUB = Path(r"D:\Projects\claude\_qa-scratch\endur-225\tree\src\OpenWSFZ.Daemon\bin\Release\net10.0\win-x64\publish")
EXE = str(PUB / "OpenWSFZ.Daemon.exe")
DLL_SHA = "51a28ff6df38714b72b92607139d10372e4e19b3d44f466450c7f3357cc0f37f"
COMMIT = "87beed9472b211e9df3050eb7c4d8cff09687050"
B1_ID = "{0.0.1.00000000}.{8dbb88e8-fd07-44b8-9ee9-88b906b8d11f}"
B1_NAME = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
RADIO_STRIP = 0
VM = QA_WT / "qa" / "endurance" / "vm_strip.py"
BASE_CFG = Path(r"D:\Projects\claude\_qa-scratch\rr-main\config")
STATION_CFG = Path(r"C:\Users\Frank\AppData\Roaming\OpenWSFZ\config.json")     # READ ONLY: its decoder section is the template
WSJTX_INI = r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\WSJT-X - FT991A.ini"
CFG_DIR = QA_WT / "qa" / "endurance" / "dxped225-config"
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
    cfg["decodeLog"]["dialFrequencyMHz"] = DIAL_MHZ
    cfg["cycleAudioArchive"].update(mode="all", directory=f"{corpus}/cycle-audio", maxSizeMb=ARCHIVE_MAX_MB,
                                    maxAgeHours=ARCHIVE_MAX_AGE_H, writeManifest=True)
    cfg["decoder"]["subtractionMaxThreads"] = SUB_THREADS
    cfg["decoder"]["decodingDepth"] = "Deep"
    d = cfg["decoder"]
    assert cfg["cat"]["enabled"] is False and cfg["tx"]["autoAnswer"] is False and cfg["externalReporting"]["enabled"] is False
    assert d["osdNhardMax"] == 24 and d["nhard24MigrationApplied"] is True and d["nhard40MigrationApplied"] is True, d
    assert d["decodingDepth"] == "Deep"
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
