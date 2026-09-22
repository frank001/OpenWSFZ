#!/usr/bin/env python
"""Standard endurance-run supervisor (HK-013 kill+log+cooldown+restart cap 5; HK-019 explicit
teardown + orphan check; HK-023 detached+log-tail; HK-016 gatherer into a dated README'd dir).

Captain's standardisation instruction (2026-09-22, relayed via Architect, verbatim in
qa/rr-study -- "standardise the endurance test run... always the same, save the datetime
stamp... single script to kick off and let go... daemon startup, port, decoder versions
and/or settings are to be configured before the run and are not to be included in the
script... band selection shall be agreed beforehand... any analysis shall be separate from
the run-script... the standard gatherer script should be used always afterwards").
**CORRECTION (Captain, direct, after the first cut of this file): daemon startup IS part of
this script. What stays OUTSIDE the script is the CONFIGURATION -- the daemon exe path, the
config file, the port -- which are INPUT to the script (CLI args), not hardcoded constants the
way qa/rr-study/live-gap-map/lgm_supervisor.py baked in PIN_SHA/BIN/EXE/USER_CFG. The first cut
of this file had that backwards (attach-to-already-running, never start) and was rejected.**

This script starts OpenWSFZ.Daemon.exe itself, using EXACTLY the exe path, config file and port
it was given on the command line -- it never constructs, edits, or overrides the config (no
make_config()-style logic). Decoder version, nhard/suppression settings, audio device, band --
whatever the given config file says -- are entirely the operator's choice, prepared before this
script runs. PRECHECK then RECORDS what actually came up (Architect's constraint (a), the
LIVE-GAP-MAP ROW 0a-0d pattern) and REFUSES TO ARM if it can detect an internal mismatch
(another daemon already running; WSJT-X's own audio-device name disagreeing with the config's;
captureActive/decodingEnabled false after startup) -- recording is not configuring, and
refusing on a detected mismatch is not configuring either.

Reused verbatim in spirit from qa/rr-study/live-gap-map/lgm_supervisor.py (HK-018): the ps()/
sha256()/kill_tree()/daemons_running()/newest_wav_age() helpers, the start_daemon()/wait_ready()
shape, the HK-013 health-loop, the HANDOFF.md/README.md convention, CREATE_NO_WINDOW on every
child process. What's different here: daemon-exe/config/port are CLI inputs instead of hardcoded
module constants, so a crash-restart just calls start_daemon() again with the SAME given
arguments (no WMI command-line archaeology needed -- we already know exactly what we launched);
TEARDOWN calls the standard gatherer (tools/gather_live_run_artefacts.py) instead of a bespoke
snapshot; ANALYSIS is not run here at all -- a separate report generator
(qa/endurance/endurance_anova_wsjtx.py) is the next step, by hand or by a follow-up script,
never bundled into this one (Captain's "analysis shall be separate from the run-script").

NFR-021: ALL.TXT and WAVs carry real callsigns. They stay under artefacts/ (gitignored). This
script never prints message text.
"""
import argparse, ctypes, datetime, hashlib, json, os, shutil, subprocess, sys, time, traceback, urllib.request

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)  # every child process: no console window
POLL_S = 30
MAX_CONSEC_RESTARTS = 5
STALE_WAV_STRIKES = 3
STALE_WAV_AGE_S = 60
DAEMON_READY_TIMEOUT_S = 120

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


def pid_alive(pid):
    return pid is not None and ps(
        "(Get-Process -Id %d -ErrorAction SilentlyContinue).Id" % pid) != ""


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
        self.daemon_proc = None  # a live Popen handle, only for the process THIS instance started

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
   anything. `python <corpus>\\tools\\endurance_supervisor.py --resume <corpus> --daemon-exe
   ... --config ... --port ... --wsjtx-ini ...` (same arguments as the original arm) re-attaches
   from `state.json`.
4. HK-019 at the end: no OpenWSFZ.Daemon.exe left running.
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


# --------------------------------------------------------------- daemon lifecycle (script-owned)
def start_daemon(run, daemon_exe, config_path, port):
    """Starts the daemon with EXACTLY the given exe/config/port -- no construction, no edits.
    This is the one place in the whole script that launches a process on the operator's
    behalf; the values it launches with are 100% CLI input."""
    out = open(os.path.join(run.c, "daemon.stdout.log"), "ab")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | NOWIN
    proc = subprocess.Popen([daemon_exe, "--config", config_path, "--port", str(port)],
                             stdout=out, stderr=subprocess.STDOUT, creationflags=flags)
    run.daemon_pid = proc.pid
    run.daemon_proc = proc
    run.state["daemon_pid"] = proc.pid
    run.save()
    run.log("daemon started pid %d (exe=%s config=%s port=%d)" % (proc.pid, daemon_exe, config_path, port))
    run.event("daemon_start", pid=proc.pid, exe=daemon_exe, config=config_path, port=port)
    return proc


def stop_daemon(run, why):
    if run.daemon_pid:
        run.log("stopping daemon pid %d (%s)" % (run.daemon_pid, why))
        kill_tree(run.daemon_pid)
        if run.daemon_proc is not None:
            try:
                run.daemon_proc.wait(timeout=30)
            except Exception:
                pass
    run.event("daemon_stop", why=why)


def wait_ready(run, port, timeout=DAEMON_READY_TIMEOUT_S):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if run.daemon_proc is not None and run.daemon_proc.poll() is not None:
            return False
        if run.daemon_proc is None and not pid_alive(run.daemon_pid):
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


# --------------------------------------------------------------- PRECHECK (record, don't configure)
def load_build_provenance(daemon_exe):
    """Reads <dirname(daemon_exe)>/build_provenance.json, written by
    tools/capture_build_provenance.py immediately after a publish. Architect, 2026-09-22
    (reading commit 85c43a77): "the latest binary" is ambiguous once more than one branch
    carries decoder-affecting work (qa/live-gap-map/main, shim 20260051, vs
    decoding_improvement, shim 20260054 + Stage 1 suppression -- both "latest" on their own
    branch, not the same decoder), and the running daemon's own /api/v1/status doesn't carry
    git provenance in this build (confirmed live: "0.49", no commit suffix). So this is a
    REQUIRED, independently-captured field, not optional metadata -- returns (None, "missing")
    if the file doesn't exist, (None, "unreadable") if it exists but won't parse, else the
    parsed dict."""
    p = os.path.join(os.path.dirname(os.path.abspath(daemon_exe)), "build_provenance.json")
    if not os.path.isfile(p):
        return None, "missing", p
    try:
        return json.load(open(p, encoding="utf-8")), None, p
    except (OSError, json.JSONDecodeError):
        return None, "unreadable", p


def precheck(run, daemon_exe, config_path, port, wsjtx_ini):
    """Starts the daemon with the GIVEN (never constructed) exe/config/port, then RECORDS
    everything about what came up -- Architect constraint (a). Refuses (all_pass=False) on any
    internally-detectable mismatch. Writes arm_config.json and returns it. Does not leave a
    daemon it started running if PRECHECK itself fails."""
    res = {"recorded_utc": iso(utcnow()), "checks": {}}

    existing = daemon_processes()
    if existing:
        res["checks"]["no_other_daemon_running"] = False
        res["checks"]["all_pass"] = False
        res["daemon_pids_found_before_start"] = existing
        return res
    res["checks"]["no_other_daemon_running"] = True

    if not os.path.isfile(daemon_exe):
        res["checks"]["daemon_exe_exists"] = False
        res["checks"]["all_pass"] = False
        return res
    if not os.path.isfile(config_path):
        res["checks"]["config_exists"] = False
        res["checks"]["all_pass"] = False
        return res
    res["checks"]["daemon_exe_exists"] = True
    res["checks"]["config_exists"] = True

    # Build provenance -- REQUIRED (Architect, 2026-09-22, interim rule pending the Captain's
    # answer on which branch's binary is "the" standard one). Checked before starting anything,
    # so a missing/build-dirty build never even spins up the daemon. GATE SCOPE (Architect
    # ruling, 2026-09-22, narrowing the first cut's whole-tree check, HK-021(k) -- "a gate that
    # fires on irrelevant state gets bypassed"): only build_dirty (the src/native/build-input
    # subset tools/capture_build_provenance.py's own BUILD_RELEVANT_* lists compute) gates.
    # The WHOLE-tree dirty/dirty_files is still recorded below, every time, as disclosure only.
    provenance, prov_error, prov_path = load_build_provenance(daemon_exe)
    res["checks"]["build_provenance_present"] = provenance is not None
    res["build_provenance_path"] = prov_path
    if provenance is None:
        res["checks"]["build_provenance_error"] = prov_error
        res["checks"]["all_pass"] = False
        return res
    if "build_dirty" not in provenance:
        # Stale-format capture (pre-scoping ruling) -- can't tell which subset is build-relevant,
        # so don't guess either way. Re-capture, don't arm on an unreadable gate.
        res["checks"]["build_provenance_present"] = False
        res["checks"]["build_provenance_error"] = "stale format (no build_dirty field) -- re-run tools/capture_build_provenance.py"
        res["checks"]["all_pass"] = False
        return res
    res["build"] = {"branch": provenance.get("branch"), "commit": provenance.get("commit"),
                     "dirty": provenance.get("dirty"), "dirty_files": provenance.get("dirty_files", []),
                     "build_dirty": provenance.get("build_dirty"),
                     "build_dirty_files": provenance.get("build_dirty_files", []),
                     "captured_utc": provenance.get("captured_utc")}
    res["checks"]["build_tree_clean"] = not provenance.get("build_dirty")
    if provenance.get("build_dirty"):
        res["checks"]["all_pass"] = False
        return res

    start_daemon(run, daemon_exe, config_path, port)
    if not wait_ready(run, port):
        res["checks"]["became_ready"] = False
        res["checks"]["all_pass"] = False
        stop_daemon(run, "PRECHECK: never became ready")
        return res
    res["checks"]["became_ready"] = True

    pid = run.daemon_pid
    res["daemon"] = {"pid": pid, "exe": daemon_exe, "config_path": config_path, "port": port}

    # DLL identity, from the loaded module (never assumed from a fixed path -- read whatever
    # this daemon actually mapped).
    dll = None
    for _ in range(24):  # native library is mapped on first use; allow up to ~2 min
        mod = ps("(Get-Process -Id %d).Modules | Where-Object { $_.ModuleName -eq "
                  "'libft8.dll' } | Select-Object -ExpandProperty FileName" % pid).splitlines()
        if mod:
            dll = mod[0].strip(); break
        time.sleep(5)
    res["daemon"]["dll_path"] = dll
    res["daemon"]["dll_sha256"] = sha256(dll) if dll and os.path.exists(dll) else None
    # Build source branch/commit, next to the DLL SHA-256 (Architect, 2026-09-22): "the latest
    # binary" is ambiguous across branches that both carry decoder-affecting work. Already
    # validated clean/present above -- this just brings it alongside the hash it identifies.
    res["daemon"]["build_branch"] = res["build"]["branch"]
    res["daemon"]["build_commit"] = res["build"]["commit"]

    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % port, timeout=6) as r:
            st = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        res["checks"]["status_endpoint_ok"] = False
        res["checks"]["status_endpoint_error"] = type(e).__name__
        res["checks"]["all_pass"] = False
        stop_daemon(run, "PRECHECK: status endpoint failed")
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

    try:
        cfgobj = json.load(open(config_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfgobj = {}
    res["daemon"]["config_audio_device_friendly_name"] = cfgobj.get("audioDeviceFriendlyName")
    res["daemon"]["config_audio_device_id"] = cfgobj.get("audioDeviceId")
    res["daemon"]["config_decode_log_path"] = (cfgobj.get("decodeLog") or {}).get("path")
    res["daemon"]["config_cycle_audio_dir"] = (cfgobj.get("cycleAudioArchive") or {}).get("directory")
    res["daemon"]["config_log_dir"] = (cfgobj.get("logging") or {}).get("directory")

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

    # This IS the meaningful mismatch check now that the script starts the daemon itself:
    # is WSJT-X actually listening to the SAME physical device the daemon's own config names?
    device_match = bool(res["daemon"].get("config_audio_device_friendly_name") == wname)
    res["checks"]["device_names_match"] = device_match
    res["checks"]["captureActive"] = bool(res["daemon"].get("captureActive"))
    res["checks"]["decodingEnabled"] = bool(res["daemon"].get("decodingEnabled"))
    res["checks"]["dll_readable"] = bool(res["daemon"].get("dll_sha256"))
    res["checks"]["all_pass"] = all([device_match, res["checks"]["captureActive"],
                                      res["checks"]["decodingEnabled"], res["checks"]["dll_readable"]])

    with open(os.path.join(run.c, "arm_config.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    if not res["checks"]["all_pass"]:
        stop_daemon(run, "PRECHECK: mismatch detected, see arm_config.json")
    return res


def run_gatherer(run, arm, window_start, window_end):
    """The standard gatherer, per the Captain's instruction -- always this one script, never a
    bespoke snapshot.

    Repo root is derived from run.c (the corpus path), NOT from __file__ -- this script is
    COPIED into <corpus>/tools/ by run_endurance.py and runs from there (HK-018/branch-switch
    safety, same as the LIVE-GAP-MAP precedent), so a __file__-relative "../.." would resolve
    two levels up from the wrong depth once relocated (found live, first dry run,
    2026-09-22: it pointed at artefacts/tools/ instead of <repo>/tools/). run.c is always
    "<repo>/artefacts/<name>" (run_endurance.py's own construction), so its grandparent IS the
    repo root regardless of where this file itself was copied to."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(run.c)))
    gatherer = os.path.join(repo, "tools", "gather_live_run_artefacts.py")
    if not os.path.isfile(gatherer):
        run.log("GATHERER NOT FOUND at %s -- artefacts NOT gathered, do this by hand" % gatherer)
        return None
    out_name = os.path.basename(run.c) + "-gathered"
    # The gatherer takes "YYYY-MM-DD HH:MM:SS" (space, no "T"/"Z"), not this script's own ISO
    # 8601 "YYYY-MM-DDTHH:MM:SSZ" -- found live, first dry run, 2026-09-22 (its own
    # parse_datetime_arg rejected the ISO form outright).
    def _gatherer_ts(iso_ts):
        return iso_ts.replace("T", " ").rstrip("Z")
    cmd = [sys.executable, gatherer,
           "--start", _gatherer_ts(window_start), "--end", _gatherer_ts(window_end),
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
this script). Daemon exe/config/port were given to this script as input -- everything below is a
RECORD of what actually came up when they were used, not something this script decided.

- Window (UTC): %s -> %s.
- OpenWSFZ: DLL SHA-256 `%s`, built from branch `%s` commit `%s` (clean tree, required --
  PRECHECK refuses to arm on a dirty tree or a missing build_provenance.json); shim %s, daemon
  version %s; nhard %s; suppression triple %s; port %s; exe `%s`; config `%s`.
- WSJT-X: NDepth=%s, AP=%s, dial %s Hz, mode %s.
- `state.json`, `arm_config.json`, `events.jsonl`, `supervisor.log`, `heartbeat.json` record
  the run. `arm_config.json` is the full ROW-0-style record (Architect constraint (a)).
- Gathered artefacts: see `events.jsonl`'s `gathered` event for the output directory name
  (`tools/gather_live_run_artefacts.py`, the standard gatherer, HK-016).
- Analysis (ANOVA report, historical table) is a SEPARATE step -- see HANDOFF.md.
""" % (os.path.basename(run.c), arm.get("band"), run.state.get("window_start"), run.state.get("window_end"),
       d.get("dll_sha256"), d.get("build_branch"), d.get("build_commit"), d.get("shim_version"),
       d.get("daemon_version"), d.get("osd_nhard_max"),
       d.get("suppression_triple"), d.get("port"), d.get("exe"), d.get("config_path"),
       w.get("NDepth"), w.get("ap_enabled"), w.get("dial_freq_hz"), w.get("mode"))
    with open(os.path.join(run.c, "README.md"), "w", encoding="utf-8") as f:
        f.write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--daemon-exe", required=True, help="path to OpenWSFZ.Daemon.exe -- INPUT, "
                     "never hardcoded")
    ap.add_argument("--config", required=True, help="path to an ALREADY-PREPARED config.json -- "
                     "decoder settings, audio device etc. are whatever this file says; this "
                     "script never edits it")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--hours", type=float, default=24.0, help="wall-clock window length (default 24h)")
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
        run.daemon_pid = run.state.get("daemon_pid")
        if not pid_alive(run.daemon_pid):
            run.log("RESUME: recorded daemon pid %s is not running -- restarting" % run.daemon_pid)
            start_daemon(run, a.daemon_exe, a.config, a.port)
            wait_ready(run, a.port)
    else:
        run.log("supervisor start pid %d, corpus %s" % (os.getpid(), a.corpus))
        run.state["phase"] = "PRECHECK"; run.save(); run.handoff("PRECHECK")
        arm = precheck(run, a.daemon_exe, a.config, a.port, a.wsjtx_ini)
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

    port = a.port
    try:
        we = datetime.datetime.strptime(run.state["window_end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        consec = 0; healthy_since = time.time(); cap_false_since = None; stale_strikes = 0
        cyc_dir = arm.get("daemon", {}).get("config_cycle_audio_dir") or ""
        while utcnow() < we:
            time.sleep(POLL_S)
            alive = pid_alive(run.daemon_pid)
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
                stop_daemon(run, problem)
                time.sleep(20)
                start_daemon(run, a.daemon_exe, a.config, a.port)
                ok = wait_ready(run, port)
                consec += 1; stale_strikes = 0; cap_false_since = None; healthy_since = time.time()
                run.event("restart", ok=ok, consecutive=consec)
            elif consec and time.time() - healthy_since > 600:
                consec = 0

        # ---------------- TEARDOWN
        run.state["phase"] = "TEARDOWN"; run.save(); run.handoff("TEARDOWN")
        time.sleep(35)  # let the last cycle's row land in both logs
        pre_teardown_others = [p for p in daemon_processes() if p != run.daemon_pid]
        stop_daemon(run, "window end")
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
