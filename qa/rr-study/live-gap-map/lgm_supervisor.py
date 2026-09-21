#!/usr/bin/env python
"""LIVE-GAP-MAP supervisor (HK-013: kill + log + cooldown + restart, cap 5 consecutive; HK-019 explicit teardown; HK-016 README'd corpus dir).

Spec: qa/rr-study/2026-09-21-1555-architect-to-qa-spec-live-gap-map-24h-20m.md (arch/live-gap-map, Amendments 1-2).
DESIGNED TO RUN WITH NO SESSION ATTACHED. Everything it does is logged to <corpus>/supervisor.log; a HANDOFF.md is written at start and rewritten at every phase.

Phases:  PRECHECK (ROW 0a-0d, as code)  ->  WAIT_WSJTX (flag file tells the Captain to turn WSJT-X monitoring on)  ->  WINDOW (24 h wall clock, health loop)
         ->  TEARDOWN (stop daemon, snapshot WSJT-X ALL.TXT APPENDED BYTES ONLY)  ->  ANALYSIS (the committed harness, if present)  ->  DONE.
NFR-021: ALL.TXT and WAVs carry real callsigns. They stay under artefacts/ (gitignored). This script never prints message text.
"""
import argparse, ctypes, datetime, hashlib, json, os, shutil, subprocess, sys, time, traceback, urllib.request

PIN_SHA = "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba"
PIN_SHIM = 20260054
PIN_VERSION_PREFIX = "0.50+"
BIN = r"C:\Users\Frank\lgm-bin"
EXE = os.path.join(BIN, "OpenWSFZ.Daemon.exe")
PORT = 8080
WSJTX_DIR = os.path.expandvars(r"%LOCALAPPDATA%\WSJT-X - FT991A")
WSJTX_ALL = os.path.join(WSJTX_DIR, "ALL.TXT")
WSJTX_INI = os.path.join(WSJTX_DIR, "WSJT-X - FT991A.ini")
WSJTX_EXE = r"D:\WSJT\wsjtx\bin\wsjtx.exe"
USER_CFG = os.path.expandvars(r"%APPDATA%\OpenWSFZ\config.json")
WINDOW_S = 24 * 3600
POLL_S = 30
MAX_CONSEC_RESTARTS = 5
WSJTX_WAIT_S = 3 * 3600          # how long to wait for the Captain to switch monitoring on
CYCLE_S = 15
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)   # every child process: no console window (a detached parent has no console, so each child would otherwise open a visible one)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class Run:
    def __init__(self, corpus):
        self.c = corpus
        self.logf = os.path.join(corpus, "supervisor.log")
        self.evf = os.path.join(corpus, "events.jsonl")
        self.state_f = os.path.join(corpus, "state.json")
        self.state = {}
        self.proc = None

    def log(self, m):
        line = "%s %s" % (iso(utcnow()), m)
        with open(self.logf, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def event(self, kind, **kw):
        kw.update(t=iso(utcnow()), kind=kind)
        with open(self.evf, "a", encoding="utf-8") as f:
            f.write(json.dumps(kw) + "\n")

    def save(self):
        with open(self.state_f, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1)

    def handoff(self, phase, extra=""):
        s = self.state
        txt = """# LIVE-GAP-MAP run HANDOFF  (rewritten at every phase; last write %s)

**Phase now: %s**  %s

This run is UNATTENDED. Corpus dir: `%s`
- Window (UTC): start `%s`, end `%s` (24 h wall clock). WSJT-X ALL.TXT byte offset at arm: %s.
- Everything is in `supervisor.log` + `events.jsonl` (restarts, health strikes). `heartbeat.json` = last loop tick.
- Result, when the supervisor finishes: `results/lgm_result.json` (counts only; from the committed harness) and `results/lgm_stdout.txt`.

## If you are the next QA session
1. `Get-Content <corpus>\\heartbeat.json`, `Get-Content <corpus>\\supervisor.log -Tail 40` - is it alive, which phase.
2. If phase is DONE: read `results/lgm_result.json`. The verdict row (M1..M4) is computed by the harness, not by you. Commit the harness output (counts only), scan the report PROSE with `nfr021_pre_merge_scan.scan()`, write the report in the standing format, and route it per the spec (section 3.7). HK-033: nothing is pushed without the Captain.
3. If the supervisor is DEAD before DONE: the daemon may still be capturing. Do NOT delete anything. `python <corpus>\\tools\\lgm_supervisor.py --resume <corpus>` re-attaches from `state.json`.
4. HK-019 at the end: no OpenWSFZ.Daemon.exe left running, port 8080 free.

Never do: re-run a replay, compare C3 to C2 as a build effect, quote R without its qualifiers (binary 38a21f84.../shim 20260054/decoding_improvement fa8a56ae or 84cac119, nhard 40, 20m, REF = WSJT-X FT991A alone, window dates).
""" % (iso(utcnow()), phase, extra, self.c, s.get("window_start"), s.get("window_end"), s.get("wsjtx_offset0"))
        with open(os.path.join(self.c, "HANDOFF.md"), "w", encoding="utf-8") as f:
            f.write(txt)


# ---------------------------------------------------------------- helpers
def http_json(path, timeout=6):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, path), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ps(cmd, timeout=60):
    """Never raises: a hung/failed PowerShell call returns '' so a transient error cannot end supervision (a check that needs the value then FAILS, which is the safe direction)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
        return r.stdout.strip()
    except Exception:
        return ""


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True, creationflags=NOWIN)


def daemons_running():
    out = ps("(Get-Process -Name OpenWSFZ.Daemon -ErrorAction SilentlyContinue | Measure-Object).Count")
    try:
        return int(out)
    except ValueError:
        return -1


def ini_value(key):
    try:
        with open(WSJTX_INI, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def make_config(run):
    """A COPY of the user's config with safe run-specific overrides. The user's own config is never touched."""
    j = json.load(open(USER_CFG, encoding="utf-8"))
    c = run.c.replace("\\", "/")
    j["port"] = PORT
    j["decodingEnabled"] = True
    j["logging"].update({"fileEnabled": True, "directory": c + "/daemon-logs", "maxFiles": 50})
    j["decodeLog"].update({"enabled": True, "path": c + "/openwsfz/ALL.TXT", "dialFrequencyMHz": 14.074})
    j["cycleAudioArchive"].update({"mode": "all", "directory": c + "/cycle-audio", "maxSizeMb": 16384, "maxAgeHours": 240, "writeManifest": True})
    j["cat"]["enabled"] = False                       # WSJT-X owns the rig's serial port
    j["externalReporting"]["enabled"] = False
    j["ptt"]["method"] = "AudioVox"                   # never open a PTT serial line
    j["tx"]["autoAnswer"] = False
    j["remoteAccess"]["enabled"] = False              # loopback only for this run
    j["remoteAccess"]["passphrase"] = ""
    os.makedirs(os.path.join(run.c, "run-config"), exist_ok=True)
    p = os.path.join(run.c, "run-config", "config.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(j, f, indent=2)
    return p, j


def start_daemon(run, cfg):
    out = open(os.path.join(run.c, "daemon.stdout.log"), "ab")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    run.proc = subprocess.Popen([EXE, "--config", cfg, "--port", str(PORT)], stdout=out, stderr=subprocess.STDOUT, cwd=run.c, creationflags=flags)
    run.state["daemon_pid"] = run.proc.pid
    run.save()
    run.log("daemon started pid %d" % run.proc.pid)
    run.event("daemon_start", pid=run.proc.pid)


def wait_ready(run, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if run.proc is not None and run.proc.poll() is not None:
            return False
        try:
            s = http_json("/api/v1/status", 4)
            if s.get("captureActive") and s.get("decodingEnabled"):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


# ---------------------------------------------------------------- ROW 0a-0d
def precheck(run, cfgobj):
    res = {}
    st = http_json("/api/v1/status")
    pid = run.proc.pid
    # 0a identity: the DLL the running process actually mapped, hashed; shim; product version
    dll = None
    for _ in range(24):                                   # the native library is mapped on first use; allow up to ~2 min
        mod = ps("(Get-Process -Id %d).Modules | Where-Object { $_.ModuleName -eq 'libft8.dll' } | Select-Object -ExpandProperty FileName" % pid).splitlines()
        if mod:
            dll = mod[0].strip(); break
        time.sleep(5)
    dll_sha = sha256(dll) if dll and os.path.exists(dll) else None
    prodver = ps("(Get-Item '%s').VersionInfo.ProductVersion" % EXE)
    res["0a"] = {"loaded_dll": dll, "sha256": dll_sha, "pin": PIN_SHA, "shim_reported": st.get("shimVersion"), "product_version": prodver, "daemon_version": st.get("version"),
                 "pass": bool(dll_sha == PIN_SHA and st.get("shimVersion") == PIN_SHIM and str(prodver).startswith(PIN_VERSION_PREFIX))}
    # 0b params
    ent = {e["name"]: e for e in http_json("/api/v1/decoder/params").get("entries", [])}
    trip = [ent.get(n, {}).get("value") for n in ("supp_snr_min_db", "supp_snr_max_db", "supp_side_weight")]
    dflt = [ent.get(n, {}).get("default") for n in ("supp_snr_min_db", "supp_snr_max_db", "supp_side_weight")]
    res["0b"] = {"osd_nhard_max": ent.get("osd_nhard_max", {}).get("value"), "supp_triple": trip, "supp_default": dflt,
                 "pass": bool(ent.get("osd_nhard_max", {}).get("value") == 40 and trip == [-5, 15, 1] and trip == dflt)}
    # 0c one audio stream (names AND the recorded extras the Amendment asks for)
    wname = ini_value("SoundInName")
    res["0c"] = {"daemon_audioDeviceFriendlyName": cfgobj.get("audioDeviceFriendlyName"), "daemon_status_audioDevice": st.get("audioDevice"), "wsjtx_SoundInName": wname,
                 "daemon_audioDeviceId": cfgobj.get("audioDeviceId"), "wsjtx_device_id": "not stored in the ini (name only)",
                 "wsjtx_SoundInChan": ini_value("SoundInChan") or "ABSENT (WSJT-X default applies)", "captureActive": st.get("captureActive"),
                 "pass": bool(cfgobj.get("audioDeviceFriendlyName") == wname and st.get("audioDevice") == wname and st.get("captureActive"))}
    # 0d reference depth
    res["0d"] = {"NDepth": ini_value("NDepth"), "DialFreq": ini_value("DialFreq"), "Mode": ini_value("Mode"),
                 "wsjtx_version": ps("(Get-Item '%s').VersionInfo.ProductVersion" % WSJTX_EXE),
                 "pass": bool(ini_value("NDepth") == "3" and ini_value("DialFreq") == "14074000")}
    res["all_pass"] = all(res[k]["pass"] for k in ("0a", "0b", "0c", "0d"))
    with open(os.path.join(run.c, "row0.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return res


def stop_daemon(run, why):
    if run.proc is not None and run.proc.poll() is None:
        run.log("stopping daemon pid %d (%s)" % (run.proc.pid, why))
        kill_tree(run.proc.pid)
        try:
            run.proc.wait(timeout=30)
        except Exception:
            pass
    run.event("daemon_stop", why=why)


def newest_wav_age(cyc_dir):
    try:
        best = 0.0
        with os.scandir(cyc_dir) as it:
            for e in it:
                if e.name.lower().endswith(".wav"):
                    best = max(best, e.stat().st_mtime)
        return time.time() - best if best else 1e9
    except OSError:
        return 1e9


# ---------------------------------------------------------------- main flow
def first_row_cycle_start(path, offset0):
    """Timestamp token (YYMMDD_HHMMSS) of the first row APPENDED after offset0, or None. Reads bytes, never prints text."""
    try:
        if os.path.getsize(path) <= offset0:
            return None
        with open(path, "rb") as f:
            f.seek(offset0)
            for raw in f:
                tok = raw.split(None, 1)[0].decode("ascii", "replace") if raw.strip() else ""
                if len(tok) >= 13 and tok[6] == "_":
                    return datetime.datetime.strptime(tok[:13], "%y%m%d_%H%M%S").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None
    return None


def main():
    global PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--port", type=int, default=8080)               # only so the resume path can be tested on a scratch corpus without touching the live daemon's port
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--harness", default=None, help="path to the committed lgm_harness.py (default: <corpus>/tools/lgm_harness.py)")
    a = ap.parse_args()
    PORT = a.port
    run = Run(a.corpus)
    for d in ("openwsfz", "cycle-audio", "daemon-logs", "wsjtx-1-ft991a", "results", "tools"):
        os.makedirs(os.path.join(a.corpus, d), exist_ok=True)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)      # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: no idle sleep while we run
    except Exception:
        pass
    if a.resume and os.path.exists(run.state_f):
        run.state = json.load(open(run.state_f, encoding="utf-8"))
        run.log("RESUME from state.json: %s" % json.dumps({k: run.state.get(k) for k in ("phase", "window_start", "window_end")}))
    run.log("supervisor start pid %d, corpus %s" % (os.getpid(), a.corpus))
    cfg_path, cfgobj = make_config(run)
    harness = a.harness or os.path.join(a.corpus, "tools", "lgm_harness.py")
    try:
        # ---------------- PRECHECK
        if run.state.get("phase") not in ("WINDOW", "TEARDOWN", "ANALYSIS", "DONE"):
            run.state["phase"] = "PRECHECK"; run.save(); run.handoff("PRECHECK")
            if daemons_running() > 0:
                run.log("ABORT: an OpenWSFZ.Daemon.exe is already running; refusing to start a second (port %d)" % PORT); run.state["phase"] = "ABORTED"; run.save(); run.handoff("ABORTED", "a daemon was already running"); return 3
            start_daemon(run, cfg_path)
            if not wait_ready(run):
                run.log("ABORT: daemon not ready (captureActive/decodingEnabled) within timeout"); stop_daemon(run, "not ready"); run.state["phase"] = "ABORTED"; run.save(); run.handoff("ABORTED", "daemon never became ready"); return 4
            r0 = precheck(run, cfgobj)
            run.log("ROW 0 " + json.dumps({k: r0[k].get("pass") for k in ("0a", "0b", "0c", "0d")}))
            if not r0["all_pass"]:
                stop_daemon(run, "ROW 0 failed"); run.state["phase"] = "ROW0_FAILED"; run.save(); run.handoff("ROW0_FAILED", "see row0.json"); return 5
        else:
            # RESUME: we hold no process handle for a daemon a previous supervisor started, so stop any stray one and start our own (a short, logged gap)
            old = run.state.get("daemon_pid")                      # ONLY the daemon this run recorded, and only if that pid still IS an OpenWSFZ.Daemon (never by image name, never a reused pid)
            if old and ps("(Get-Process -Id %d -ErrorAction SilentlyContinue).ProcessName" % int(old)) == "OpenWSFZ.Daemon":
                run.log("RESUME: stopping the recorded daemon pid %s" % old); kill_tree(int(old))
            time.sleep(5)
            run.event("resume_restart")
            start_daemon(run, cfg_path); wait_ready(run)
        # ---------------- WAIT_WSJTX
        if run.state.get("phase") in (None, "PRECHECK"):
            off0 = os.path.getsize(WSJTX_ALL) if os.path.exists(WSJTX_ALL) else 0
            run.state.update(phase="WAIT_WSJTX", wsjtx_offset0=off0, wsjtx_ini_sha256=sha256(WSJTX_INI)); run.save()
            flag = os.path.join(a.corpus, "WAITING_FOR_WSJTX_MONITOR.flag")
            with open(flag, "w", encoding="utf-8") as f:
                f.write("ROW 0 PASSED at %s. Turn WSJT-X MONITORING ON now. The 24 h window opens at the first full cycle after its first decode.\n" % iso(utcnow()))
            run.log("ROW 0 passed; waiting for WSJT-X monitoring (ALL.TXT offset0=%d). Flag file written." % off0); run.handoff("WAIT_WSJTX", "ROW 0 passed; waiting for the Captain to turn WSJT-X monitoring on")
            t0 = time.time(); first = None
            while time.time() - t0 < WSJTX_WAIT_S:
                first = first_row_cycle_start(WSJTX_ALL, off0)
                if first is not None:
                    break
                if run.proc.poll() is not None:
                    run.log("daemon died while waiting for WSJT-X"); start_daemon(run, cfg_path); wait_ready(run)
                time.sleep(5)
            if first is None:
                run.log("ABORT: WSJT-X produced no decode within %d s of ROW 0" % WSJTX_WAIT_S); stop_daemon(run, "WSJT-X never live"); run.state["phase"] = "ABORTED"; run.save(); run.handoff("ABORTED", "WSJT-X never produced a decode"); return 6
            ws = first + datetime.timedelta(seconds=2 * CYCLE_S)          # first full cycle after WSJT-X's first decode's cycle
            we = ws + datetime.timedelta(seconds=WINDOW_S)
            run.state.update(phase="WINDOW", window_start=iso(ws), window_end=iso(we), wsjtx_first_row_cycle=iso(first)); run.save()
            try:
                os.remove(flag)
            except OSError:
                pass
            run.log("WINDOW OPEN: %s -> %s (WSJT-X first decode cycle %s)" % (iso(ws), iso(we), iso(first))); run.event("window_open", start=iso(ws), end=iso(we))
            run.handoff("WINDOW")
        # ---------------- WINDOW loop
        we = datetime.datetime.strptime(run.state["window_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        consec = 0; healthy_since = time.time(); cap_false_since = None; stale_strikes = 0; cyc_dir = os.path.join(a.corpus, "cycle-audio")
        while utcnow() < we:
            time.sleep(POLL_S)
            alive = run.proc is not None and run.proc.poll() is None
            problem = None
            if not alive:
                problem = "daemon process exited"
            else:
                try:
                    s = http_json("/api/v1/status", 5)
                    if not s.get("captureActive"):
                        cap_false_since = cap_false_since or time.time()
                        if time.time() - cap_false_since > 90:
                            problem = "captureActive false for > 90 s"
                    else:
                        cap_false_since = None
                    if not s.get("decodingEnabled"):
                        problem = "decodingEnabled false"
                except Exception as e:
                    problem = "status endpoint failed: %s" % type(e).__name__
                age = newest_wav_age(cyc_dir)
                if age > 60:
                    stale_strikes += 1
                    if stale_strikes >= 3:
                        problem = problem or "no new cycle WAV for %.0f s" % age
                else:
                    stale_strikes = 0
            hb = {"t": iso(utcnow()), "phase": "WINDOW", "alive": alive, "problem": problem, "consecutive_restarts": consec,
                  "wav_age_s": round(newest_wav_age(cyc_dir), 1), "wsjtx_running": bool(ps("(Get-Process -Name wsjtx -ErrorAction SilentlyContinue | Measure-Object).Count") not in ("", "0")),
                  "free_gb_D": round(shutil.disk_usage("D:\\").free / 1e9, 1)}
            with open(os.path.join(a.corpus, "heartbeat.json"), "w", encoding="utf-8") as f:
                json.dump(hb, f)
            if problem:
                run.log("PROBLEM: %s -> restart (consecutive %d)" % (problem, consec + 1)); run.event("problem", what=problem)
                if consec >= MAX_CONSEC_RESTARTS:
                    run.log("GIVING UP: %d consecutive restarts; leaving the window as is" % consec); run.event("giving_up"); break
                stop_daemon(run, problem); time.sleep(20)
                start_daemon(run, cfg_path); ok = wait_ready(run); consec += 1; stale_strikes = 0; cap_false_since = None; healthy_since = time.time()
                run.event("restart", ok=ok, consecutive=consec)
            elif consec and time.time() - healthy_since > 600:
                consec = 0
        # ---------------- TEARDOWN
        run.state["phase"] = "TEARDOWN"; run.save(); run.handoff("TEARDOWN")
        time.sleep(35)                                                      # let the last cycle's row land in both logs
        stop_daemon(run, "window end")
        off0 = int(run.state["wsjtx_offset0"])
        with open(WSJTX_ALL, "rb") as src, open(os.path.join(a.corpus, "wsjtx-1-ft991a", "ALL.TXT"), "wb") as dst:
            src.seek(off0); shutil.copyfileobj(src, dst)
        shutil.copy2(WSJTX_INI, os.path.join(a.corpus, "wsjtx-1-ft991a", "WSJT-X - FT991A.ini"))
        run.log("WSJT-X ALL.TXT snapshot: appended bytes only from offset %d" % off0)
        n = daemons_running()
        run.log("teardown: OpenWSFZ.Daemon processes left = %s" % n)
        write_readme(run)
        # ---------------- ANALYSIS
        run.state["phase"] = "ANALYSIS"; run.save(); run.handoff("ANALYSIS")
        if os.path.exists(harness):
            run.log("running harness %s" % harness)
            r = subprocess.run([sys.executable, harness, "--corpus", a.corpus], capture_output=True, text=True, timeout=6 * 3600, creationflags=NOWIN)
            with open(os.path.join(a.corpus, "results", "lgm_stdout.txt"), "w", encoding="utf-8") as f:
                f.write(r.stdout + "\n--- stderr ---\n" + r.stderr)
            run.log("harness exit %d" % r.returncode)
        else:
            run.log("HARNESS NOT FOUND at %s - analysis must be run by hand" % harness)
        run.state["phase"] = "DONE"; run.save(); run.handoff("DONE")
        run.log("DONE")
        return 0
    except Exception:
        run.log("UNEXPECTED ERROR (daemon left RUNNING so the capture is not lost):\n" + traceback.format_exc())
        run.state["phase"] = run.state.get("phase", "?") + "+SUPERVISOR_ERROR"; run.save(); run.handoff("SUPERVISOR_ERROR", "see supervisor.log; the daemon may still be capturing")
        return 9


def write_readme(run):
    s = run.state
    txt = """# %s  (HK-016)

LIVE-GAP-MAP corpus C3: 24 h live capture on 20m (14.074 MHz), ONE radio (Yaesu FT-991A) feeding BOTH decoders through the same Windows capture endpoint. No SDR Uno, no second WSJT-X.
Real third-party callsigns are in `openwsfz/ALL.TXT`, `wsjtx-1-ft991a/ALL.TXT` and `cycle-audio/`: this directory is gitignored (NFR-021); only counts may leave it.

- Window (UTC): %s -> %s (24 h wall clock). `state.json`, `row0.json`, `events.jsonl`, `supervisor.log`, `heartbeat.json` record the run.
- OpenWSFZ: published from `decoding_improvement` 84cac119 (contains fa8a56ae); `libft8.dll` SHA-256 `%s`, shim %d, product version 0.50+84cac119; nhard 40; suppression triple default (-5,+15,1.0). Config used: `run-config/config.json` (a copy; the operator's own config was never modified).
- WSJT-X 2.7.0, profile `- FT991A`, NDepth=3, no AP. `wsjtx-1-ft991a/ALL.TXT` is a snapshot of ONLY the bytes appended after offset %s (contamination guard).
- `cycle-audio/` is the daemon's cycle archive (mode all) so a LATER arm can replay this corpus. This arm does not.
""" % (os.path.basename(run.c), s.get("window_start"), s.get("window_end"), PIN_SHA, PIN_SHIM, s.get("wsjtx_offset0"))
    with open(os.path.join(run.c, "README.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    with open(os.path.join(run.c, "contents.md"), "w", encoding="utf-8") as f:
        f.write("layout: contents.md, README.md, cycle-audio/, openwsfz/ALL.TXT, wsjtx-1-ft991a/ALL.TXT, run-config/, daemon-logs/, results/, tools/\n")


if __name__ == "__main__":
    sys.exit(main())
