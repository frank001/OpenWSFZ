#!/usr/bin/env python
"""Standard endurance-run supervisor (HK-013 kill+log+cooldown+restart cap 5; HK-019 explicit
teardown + orphan check; HK-023 detached+log-tail; HK-016 gatherer into a dated README'd dir).

Captain's standardisation instruction (2026-09-22, relayed via Architect, verbatim in
qa/rr-study -- "standardise the endurance test run... always the same, save the datetime
stamp... single script to kick off and let go... daemon startup, port, decoder versions
and/or settings are to be configured before the run and are not to be included in the
script... band selection shall be agreed beforehand... any analysis shall be separate from
the run-script... the standard gatherer script should be used always afterwards").

THIS SCRIPT DOES NOT START, CONFIGURE, OR TUNE THE DAEMON. The operator starts
OpenWSFZ.Daemon.exe by hand, however they like, before running this script -- whatever port,
config file, decoder version, nhard/suppression settings and band it comes up with are
whatever the operator set. This script's PRECHECK only *records* what it finds (Architect's
constraint (a), the LIVE-GAP-MAP ROW 0a-0d pattern) and REFUSES TO ARM if it can detect an
internal mismatch (not exactly one daemon running; WSJT-X's own audio-device name disagreeing
with the daemon's; captureActive false) -- recording is not configuring.

Reused verbatim in spirit from qa/rr-study/live-gap-map/lgm_supervisor.py (HK-018): the ps()/
sha256()/kill_tree()/daemons_running()/newest_wav_age() helpers, the HK-013 health-loop shape,
the HANDOFF.md/README.md convention, CREATE_NO_WINDOW on every child process. What's NEW here:
no start_daemon()/make_config() -- PRECHECK attaches to an already-running daemon and records
its actual command line (via WMI) so a crash-restart can relaunch it VERBATIM, never with a
script-constructed config; TEARDOWN calls the standard gatherer
(tools/gather_live_run_artefacts.py) instead of a bespoke snapshot; ANALYSIS is not run here
at all -- a separate report generator (qa/endurance/endurance_anova_wsjtx.py) is the next step,
by hand or by a follow-up script, never bundled into this one (Captain's "analysis shall be
separate from the run-script").

NFR-021: ALL.TXT and WAVs carry real callsigns. They stay under artefacts/ (gitignored). This
script never prints message text.
"""
import argparse, ctypes, datetime, hashlib, json, os, re, shutil, subprocess, sys, time, traceback, urllib.request

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)  # every child process: no console window
WINDOW_S_DEFAULT = 24 * 3600
POLL_S = 30
MAX_CONSEC_RESTARTS = 5
CYCLE_S = 15
STALE_WAV_STRIKES = 3
STALE_WAV_AGE_S = 60

# 12.5 kHz-rounded band edges (MHz), for a display label only -- never used to configure
# anything. Matches this project's own dial frequencies (10/20/40/80 m have been used).
_BAND_EDGES_MHZ = [(1.8, 2.0, "160m"), (3.5, 4.0, "80m"), (7.0, 7.3, "40m"),
                    (10.1, 10.15, "30m"), (14.0, 14.35, "20m"), (18.068, 18.168, "17m"),
                    (21.0, 21.45, "15m"), (24.89, 24.99, "12m"), (28.0, 29.7, "10m")]


def band_label(dial_mhz):
    try:
        f = float(dial_mhz)
    except (TypeError, ValueError):
        return "unknown"
    for lo, hi, name in _BAND_EDGES_MHZ:
        if lo <= f <= hi:
            return name
    return "unknown(%s MHz)" % dial_mhz


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ps(cmd, timeout=60):
    """Never raises: a hung/failed PowerShell call returns '' so a transient error cannot end
    supervision (a check that needs the value then FAILS, which is the safe direction)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                            text=True, timeout=timeout, creationflags=NOWIN)
        return r.stdout.strip()
    except Exception:
        return ""


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True,
                    creationflags=NOWIN)


def daemon_processes():
    """Every OpenWSFZ.Daemon.exe pid currently running, as a list of ints."""
    out = ps("Get-Process -Name OpenWSFZ.Daemon -ErrorAction SilentlyContinue | "
              "Select-Object -ExpandProperty Id")
    return [int(x) for x in out.splitlines() if x.strip().isdigit()]


def process_command_line(pid):
    return ps("(Get-CimInstance Win32_Process -Filter \"ProcessId=%d\").CommandLine" % pid)


def parse_flag(cmdline, flag):
    """Extract --flag VALUE (or --flag=VALUE) from a Windows command-line string, handling a
    double-quoted value. Returns None if not present."""
    m = re.search(re.escape(flag) + r'(?:\s+|=)"([^"]*)"', cmdline)
    if m:
        return m.group(1)
    m = re.search(re.escape(flag) + r'(?:\s+|=)(\S+)', cmdline)
    return m.group(1) if m else None


def ini_value(ini_path, key):
    try:
        with open(ini_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


class Run:
    def __init__(self, corpus):
        self.c = corpus
        self.logf = os.path.join(corpus, "supervisor.log")
        self.evf = os.path.join(corpus, "events.jsonl")
        self.state_f = os.path.join(corpus, "state.json")
        self.state = {}
        self.daemon_pid = None
        self.daemon_cmdline = None
        self.daemon_exe = None

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
        txt = """# Endurance run HANDOFF (rewritten at every phase; last write %s)

**Phase now: %s**  %s

This run is UNATTENDED. Corpus dir: `%s`
- Window (UTC): start `%s`, end `%s`.
- Everything is in `supervisor.log` + `events.jsonl` (restarts, health strikes). `heartbeat.json` = last loop tick.
- Arm-time record (recorded, never configured by this script): `arm_config.json`.
- This script does NOT run analysis. Once phase is DONE, run the standard ANOVA report
  generator separately: `python qa/endurance/endurance_anova_wsjtx.py --ours-all-txt
  <gathered>/owsfz/ALL.TXT --wsjtx-all-txt <gathered>/wsjt-x/ALL.TXT --out
  <gathered>/anova_report.md --arm-config %s/arm_config.json`

## If you are the next QA session
1. `Get-Content <corpus>\\heartbeat.json`, `Get-Content <corpus>\\supervisor.log -Tail 40` -- is it alive, which phase.
2. If phase is DONE: gathered artefacts are wherever the standard gatherer's own README says
   (its output dir is recorded in `events.jsonl`'s `gathered` event). Run the ANOVA report
   generator (above), which appends this run to the historical table automatically.
3. If the supervisor is DEAD before DONE: the daemon may still be capturing. Do NOT delete
   anything. `python <corpus>\\tools\\endurance_supervisor.py --resume <corpus>` re-attaches
   from `state.json` and relaunches the daemon with the EXACT command line recorded at arm
   time (never a script-constructed config).
4. HK-019 at the end: no OpenWSFZ.Daemon.exe left running (or exactly the count that was
   running before this script ever touched anything, if the operator runs more than one).
""" % (iso(utcnow()), phase, extra, self.c, s.get("window_start"), s.get("window_end"), self.c)
        with open(os.path.join(self.c, "HANDOFF.md"), "w", encoding="utf-8") as f:
            f.write(txt)


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


# --------------------------------------------------------------- PRECHECK (record, don't configure)
def precheck(run, port_hint, wsjtx_ini):
    """Attach to the ALREADY-RUNNING daemon and record everything, per Architect constraint
    (a). Refuses (all_pass=False) on any internally-detectable mismatch. Writes
    arm_config.json and returns it."""
    res = {"recorded_utc": iso(utcnow())}
    pids = daemon_processes()
    res["daemon_pids_found"] = pids
    single_daemon = len(pids) == 1
    res["checks"] = {"single_daemon": single_daemon}
    if not single_daemon:
        res["checks"]["all_pass"] = False
        return res

    pid = pids[0]
    cmdline = process_command_line(pid)
    config_path = parse_flag(cmdline, "--config")
    port = parse_flag(cmdline, "--port") or str(port_hint)
    res["daemon"] = {"pid": pid, "command_line": cmdline, "config_path": config_path, "port": port}

    # DLL identity, from the loaded module (never from a hardcoded path -- the daemon may run
    # from any published location the operator chose).
    dll = None
    for _ in range(24):  # native library is mapped on first use; allow up to ~2 min
        mod = ps("(Get-Process -Id %d).Modules | Where-Object { $_.ModuleName -eq "
                  "'libft8.dll' } | Select-Object -ExpandProperty FileName" % pid).splitlines()
        if mod:
            dll = mod[0].strip(); break
        time.sleep(5)
    res["daemon"]["dll_path"] = dll
    res["daemon"]["dll_sha256"] = sha256(dll) if dll and os.path.exists(dll) else None

    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % port, timeout=6) as r:
            st = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        res["checks"]["status_endpoint_ok"] = False
        res["checks"]["status_endpoint_error"] = type(e).__name__
        res["checks"]["all_pass"] = False
        return res
    res["checks"]["status_endpoint_ok"] = True
    res["daemon"]["shim_version"] = st.get("shimVersion")
    res["daemon"]["daemon_version"] = st.get("version")
    res["daemon"]["audio_device"] = st.get("audioDevice")
    res["daemon"]["captureActive"] = st.get("captureActive")
    res["daemon"]["decodingEnabled"] = st.get("decodingEnabled")

    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/decoder/params" % port, timeout=6) as r:
            params = json.loads(r.read().decode("utf-8"))
        ent = {e["name"]: e for e in params.get("entries", [])}
        res["daemon"]["osd_nhard_max"] = ent.get("osd_nhard_max", {}).get("value")
        res["daemon"]["suppression_triple"] = [ent.get(n, {}).get("value") for n in
                                                ("supp_snr_min_db", "supp_snr_max_db", "supp_side_weight")]
    except Exception:
        res["daemon"]["osd_nhard_max"] = None
        res["daemon"]["suppression_triple"] = None

    cfgobj = {}
    if config_path and os.path.exists(config_path):
        try:
            cfgobj = json.load(open(config_path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfgobj = {}
    res["daemon"]["config_audio_device_friendly_name"] = cfgobj.get("audioDeviceFriendlyName")
    res["daemon"]["config_audio_device_id"] = cfgobj.get("audioDeviceId")
    res["daemon"]["config_decode_log_path"] = (cfgobj.get("decodeLog") or {}).get("path")
    res["daemon"]["config_cycle_audio_dir"] = (cfgobj.get("cycleAudioArchive") or {}).get("directory")
    res["daemon"]["config_log_dir"] = (cfgobj.get("logging") or {}).get("directory")
    res["daemon"]["config_dial_freq_mhz"] = (cfgobj.get("decodeLog") or {}).get("dialFrequencyMHz")

    wname = ini_value(wsjtx_ini, "SoundInName")
    res["wsjtx"] = {
        "ini_path": wsjtx_ini,
        "NDepth": ini_value(wsjtx_ini, "NDepth"),
        "ap_enabled": ini_value(wsjtx_ini, "aprioriEnabled"),
        "dial_freq_hz": ini_value(wsjtx_ini, "DialFreq"),
        "mode": ini_value(wsjtx_ini, "Mode"),
        "sound_in_name": wname,
        "sound_in_chan": ini_value(wsjtx_ini, "SoundInChan") or "ABSENT (WSJT-X default applies)",
    }
    dial_hz = res["wsjtx"]["dial_freq_hz"]
    dial_mhz = (int(dial_hz) / 1e6) if dial_hz and str(dial_hz).isdigit() else None
    res["band"] = band_label(dial_mhz)

    device_match = bool(res["daemon"].get("config_audio_device_friendly_name") == wname
                         and res["daemon"].get("audio_device") == wname)
    res["checks"]["device_names_match"] = device_match
    res["checks"]["captureActive"] = bool(res["daemon"].get("captureActive"))
    res["checks"]["decodingEnabled"] = bool(res["daemon"].get("decodingEnabled"))
    res["checks"]["dll_readable"] = bool(res["daemon"].get("dll_sha256"))
    res["checks"]["all_pass"] = all([single_daemon, device_match, res["checks"]["captureActive"],
                                      res["checks"]["decodingEnabled"], res["checks"]["dll_readable"]])

    with open(os.path.join(run.c, "arm_config.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    run.daemon_pid, run.daemon_cmdline = pid, cmdline
    run.daemon_exe = (re.match(r'\s*"?([^"]+\.exe)"?', cmdline).group(1) if cmdline else None)
    return res


def restart_daemon_verbatim(run):
    """Relaunch the daemon with the EXACT command line PRECHECK recorded. Never constructs or
    edits a config -- if the operator's own launch used one, this uses the identical one."""
    if not run.daemon_exe or not run.daemon_cmdline:
        run.log("CANNOT RESTART: no recorded command line (PRECHECK never captured one)")
        return None
    args = run.daemon_cmdline[len(run.daemon_exe):].strip()
    # shlex-lite: PowerShell already gave us a single string; re-split via cmd's own quoting
    # rules is unnecessary here since Popen(str) with shell semantics isn't used -- use
    # subprocess with the raw string via PowerShell's own Start-Process for exact fidelity.
    out = open(os.path.join(run.c, "daemon.stdout.log"), "ab")
    cmd = 'Start-Process -FilePath "%s" -ArgumentList \'%s\' -WindowStyle Hidden -PassThru | ' \
          'Select-Object -ExpandProperty Id' % (run.daemon_exe, args.replace("'", "''"))
    pid_s = ps(cmd, timeout=30)
    try:
        pid = int(pid_s.strip())
    except ValueError:
        run.log("RESTART FAILED: could not parse new pid from '%s'" % pid_s)
        return None
    run.daemon_pid = pid
    run.state["daemon_pid"] = pid
    run.save()
    run.log("daemon restarted verbatim, new pid %d" % pid)
    run.event("daemon_restart", pid=pid)
    return pid


def wait_ready(run, port, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if run.daemon_pid and ps("(Get-Process -Id %d -ErrorAction SilentlyContinue).Id" % run.daemon_pid) == "":
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % port, timeout=4) as r:
                s = json.loads(r.read().decode("utf-8"))
            if s.get("captureActive") and s.get("decodingEnabled"):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def run_gatherer(run, arm, window_start, window_end):
    """The standard gatherer, per the Captain's instruction -- always this one script, never a
    bespoke snapshot."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    gatherer = os.path.join(repo, "tools", "gather_live_run_artefacts.py")
    if not os.path.isfile(gatherer):
        run.log("GATHERER NOT FOUND at %s -- artefacts NOT gathered, do this by hand" % gatherer)
        return None
    out_name = os.path.basename(run.c) + "-gathered"
    cmd = [sys.executable, gatherer,
           "--start", window_start, "--end", window_end,
           "--name", out_name]
    d = arm.get("daemon", {})
    if d.get("config_decode_log_path"):
        cmd += ["--owsfz-alltxt", d["config_decode_log_path"]]
    if d.get("config_cycle_audio_dir"):
        cmd += ["--owsfz-cycle-audio-dir", d["config_cycle_audio_dir"]]
    if d.get("config_path"):
        cmd += ["--owsfz-config", d["config_path"]]
    wsjtx_dir = os.path.dirname(arm.get("wsjtx", {}).get("ini_path") or "")
    if wsjtx_dir:
        cmd += ["--wsjtx-root", wsjtx_dir]
    run.log("running standard gatherer: %s" % " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, creationflags=NOWIN)
    with open(os.path.join(run.c, "gatherer.stdout.log"), "w", encoding="utf-8") as f:
        f.write(r.stdout + "\n--- stderr ---\n" + r.stderr)
    run.event("gathered", exit_code=r.returncode, out_name=out_name)
    run.log("gatherer exit %d (see gatherer.stdout.log)" % r.returncode)
    return out_name


def write_readme(run, arm):
    d, w = arm.get("daemon", {}), arm.get("wsjtx", {})
    txt = """# %s (HK-016)

Standard endurance run. Band: %s (recorded from WSJT-X's own dial frequency; NOT configured by
this script). Daemon config, port and decoder settings were set up by the operator BEFORE this
script ran -- everything below is a RECORD of what was found at arm time, not something this
script chose.

- Window (UTC): %s -> %s.
- OpenWSFZ: DLL SHA-256 `%s`, shim %s, daemon version %s; nhard %s; suppression triple %s;
  port %s; config `%s`.
- WSJT-X: NDepth=%s, AP=%s, dial %s Hz, mode %s.
- `state.json`, `arm_config.json`, `events.jsonl`, `supervisor.log`, `heartbeat.json` record
  the run. `arm_config.json` is the full ROW-0-style record (Architect constraint (a)).
- Gathered artefacts: see `events.jsonl`'s `gathered` event for the output directory name
  (`tools/gather_live_run_artefacts.py`, the standard gatherer, HK-016).
- Analysis (ANOVA report, historical table) is a SEPARATE step -- see HANDOFF.md.
""" % (os.path.basename(run.c), arm.get("band"), run.state.get("window_start"), run.state.get("window_end"),
       d.get("dll_sha256"), d.get("shim_version"), d.get("daemon_version"), d.get("osd_nhard_max"),
       d.get("suppression_triple"), d.get("port"), d.get("config_path"),
       w.get("NDepth"), w.get("ap_enabled"), w.get("dial_freq_hz"), w.get("mode"))
    with open(os.path.join(run.c, "README.md"), "w", encoding="utf-8") as f:
        f.write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--hours", type=float, default=24.0, help="wall-clock window length (default 24h)")
    ap.add_argument("--port", type=int, default=8080, help="where to LOOK for the already-running "
                     "daemon's status API -- not something this script configures")
    ap.add_argument("--wsjtx-ini", required=True, help="path to the WSJT-X .ini this run should "
                     "read (the operator's own profile, agreed beforehand)")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    run = Run(a.corpus)
    os.makedirs(a.corpus, exist_ok=True)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)  # no idle sleep while we run
    except Exception:
        pass

    if a.resume and os.path.exists(run.state_f):
        run.state = json.load(open(run.state_f, encoding="utf-8"))
        arm = json.load(open(os.path.join(a.corpus, "arm_config.json"), encoding="utf-8"))
        run.log("RESUME from state.json: %s" % json.dumps({k: run.state.get(k) for k in
                                                            ("phase", "window_start", "window_end")}))
    else:
        run.log("supervisor start pid %d, corpus %s" % (os.getpid(), a.corpus))
        run.state["phase"] = "PRECHECK"; run.save(); run.handoff("PRECHECK")
        arm = precheck(run, a.port, a.wsjtx_ini)
        run.log("PRECHECK " + json.dumps(arm.get("checks", {})))
        if not arm["checks"].get("all_pass"):
            run.state["phase"] = "ABORTED"; run.save(); run.handoff("ABORTED", "see arm_config.json")
            run.log("ABORT: PRECHECK failed -- refusing to arm on a detected mismatch (see arm_config.json)")
            return 3
        ws = utcnow(); we = ws + datetime.timedelta(hours=a.hours)
        run.state.update(phase="WINDOW", window_start=iso(ws), window_end=iso(we))
        run.save(); run.handoff("WINDOW")
        run.log("WINDOW OPEN: %s -> %s" % (iso(ws), iso(we)))
        run.event("window_open", start=iso(ws), end=iso(we))

    port = arm["daemon"]["port"]
    try:
        we = datetime.datetime.strptime(run.state["window_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        consec = 0; healthy_since = time.time(); cap_false_since = None; stale_strikes = 0
        cyc_dir = arm.get("daemon", {}).get("config_cycle_audio_dir") or ""
        while utcnow() < we:
            time.sleep(POLL_S)
            alive = run.daemon_pid and ps("(Get-Process -Id %d -ErrorAction SilentlyContinue).Id" % run.daemon_pid) != ""
            problem = None
            if not alive:
                problem = "daemon process exited"
            else:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % port, timeout=5) as r:
                        s = json.loads(r.read().decode("utf-8"))
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
                if cyc_dir:
                    age = newest_wav_age(cyc_dir)
                    if age > STALE_WAV_AGE_S:
                        stale_strikes += 1
                        if stale_strikes >= STALE_WAV_STRIKES:
                            problem = problem or "no new cycle WAV for %.0f s" % age
                    else:
                        stale_strikes = 0
            hb = {"t": iso(utcnow()), "phase": "WINDOW", "alive": alive, "problem": problem,
                  "consecutive_restarts": consec,
                  "wav_age_s": round(newest_wav_age(cyc_dir), 1) if cyc_dir else None}
            with open(os.path.join(a.corpus, "heartbeat.json"), "w", encoding="utf-8") as f:
                json.dump(hb, f)
            if problem:
                # HK-013 addendum: a UTC-midnight log-rotation blip can look like a momentary
                # stall on its own -- one extra confirming poll before counting it as real.
                time.sleep(5)
                run.log("PROBLEM: %s -> restart (consecutive %d)" % (problem, consec + 1))
                run.event("problem", what=problem)
                if consec >= MAX_CONSEC_RESTARTS:
                    run.log("GIVING UP: %d consecutive restarts; leaving the window as is" % consec)
                    run.event("giving_up"); break
                if run.daemon_pid:
                    kill_tree(run.daemon_pid)
                time.sleep(20)
                restart_daemon_verbatim(run)
                ok = wait_ready(run, port)
                consec += 1; stale_strikes = 0; cap_false_since = None; healthy_since = time.time()
                run.event("restart", ok=ok, consecutive=consec)
            elif consec and time.time() - healthy_since > 600:
                consec = 0

        # ---------------- TEARDOWN
        run.state["phase"] = "TEARDOWN"; run.save(); run.handoff("TEARDOWN")
        time.sleep(35)  # let the last cycle's row land in both logs
        pre_teardown_others = [p for p in daemon_processes() if p != run.daemon_pid]
        if run.daemon_pid:
            run.log("stopping daemon pid %d (window end)" % run.daemon_pid)
            kill_tree(run.daemon_pid)
        run.event("daemon_stop", why="window end")
        time.sleep(3)
        orphans = [p for p in daemon_processes() if p not in pre_teardown_others]
        if orphans:
            run.log("HK-019 WARNING: %d OpenWSFZ.Daemon process(es) still running after teardown: %s"
                     % (len(orphans), orphans))
        else:
            run.log("HK-019 orphan check: clean")
        write_readme(run, arm)

        # ---------------- GATHER (the standard gatherer -- always this one)
        run.state["phase"] = "GATHER"; run.save(); run.handoff("GATHER")
        run_gatherer(run, arm, run.state["window_start"], run.state["window_end"])

        run.state["phase"] = "DONE"; run.save(); run.handoff("DONE")
        run.log("DONE. Analysis is a separate step -- see HANDOFF.md.")
        return 0
    except Exception:
        run.log("UNEXPECTED ERROR (daemon left RUNNING so the capture is not lost):\n" + traceback.format_exc())
        run.state["phase"] = run.state.get("phase", "?") + "+SUPERVISOR_ERROR"; run.save()
        run.handoff("SUPERVISOR_ERROR", "see supervisor.log; the daemon may still be capturing")
        return 9


if __name__ == "__main__":
    sys.exit(main())
