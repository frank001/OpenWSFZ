#!/usr/bin/env python
"""Detached launcher for the R&R S1-S8 study (HK-023: detached + a disposable log tail is
how you watch an unattended run, not a durable scheduler; HK-016 dated output dir; HK-013-
style PRECHECK + logged status, adapted for R&R's own failure model -- see below).

WHY THIS EXISTS: a full S1-S8 battery, and especially --scenarios S3b/S8HN, runs unattended
for hours (S3b alone is ~4.2h at its corrected sizing) -- run_study.py's own code comment has
said since 2026-08-19 that this "needs an HK-013 supervisor -- not something the default
batch should trigger blind", and none existed until this script.

SECOND PASS (Architect, 2026-09-22, reading the first cut): the first cut only supervised an
ALREADY-RUNNING daemon. Two things were missing, both now here:
  1. The daemon lifecycle: this script now STARTS the daemon itself, from the GIVEN
     --daemon-exe/--config/--port (never constructed -- see qa/rr-study/rr_precheck.py),
     records build_provenance (branch/commit, recorded only, no branch gate -- the Captain's
     URGENT reversal on the endurance side applies here too) and the build-inputs dirty gate
     (unchanged), and runs PRECHECK ROW 0 (identity, device names, captureActive,
     cycleAudioArchive.mode, WSJT-X NDepth/AP) before scenario 1.
  2. Captured audio: the Captain's "R&R keeps WAVs" decision (2026-09-22) means the
     daemon's own cycle-audio archive and WSJT-X's save/*.wav for the battery window get
     gathered via the STANDARD gatherer (tools/gather_live_run_artefacts.py) after the
     battery finishes -- same tool the endurance side uses, same principle ("always the
     standard gatherer"). The battery's run_dir is predicted BEFORE launching run_study.py by
     calling the identical harness.common.make_run_dir() it will call internally
     (deterministic: results_root/<date>-<git-sha7>, no random/incrementing component, so two
     independent calls on the same day/commit resolve to the SAME directory) -- no change to
     run_study.py needed to make this line up.

This wraps run_study.py (or resume_study.py, via --resume) as a DETACHED background process
so the battery survives the terminal/session closing, and logs everything so it can be
checked on later without babysitting it.

WHAT THIS DELIBERATELY DOES NOT DO: automatic restart-on-crash of the BATTERY (the daemon
itself is started fresh every invocation, per item 1 above -- that part IS "the daemon start
is part of the script", matching the endurance correction). The endurance-run supervisor
restarts a crashed DAEMON because a live capture session has one long-lived process whose job
is "keep listening" -- restarting it loses at most a few seconds. An R&R BATTERY is different:
run_scenario.py plays a precisely-timed synthesized scene into a live decoder, and truth.csv
is built incrementally, scenario by scenario. A battery crash mid-scenario needs a human (or
at least a deliberate decision) to pick the correct resume point, which is exactly what
resume_study.py already does, reading truth.csv back to find out which scenarios actually
landed rather than assuming. Blindly restarting the whole run_study.py process would re-run
already-completed scenarios and/or diverge from the project's own established handoff
convention (see qa/rr-study/2026-08-15-1931-qa-session-handoff-s1s8-restart-required.md for a
real incident this shape). So: this script supervises the BATTERY (detached, logged, a clear
DONE/FAILED status, captured audio gathered either way), it does not decide how to recover a
crashed one -- that stays a human call, using --resume, same as today.

Application settings, audio routing and the RUNBOOK's one-time/per-session setup are NOT this
script's business -- see qa/rr-study/RUNBOOK.md sections 1-2 for the current, authoritative
procedure; this script does not duplicate or embed a snapshot of it.

Usage (from qa/rr-study/):
    python run_study_detached.py --daemon-exe <path> --config <path> --port 8080 \\
        --wsjtx-ini "C:\\...\\WSJT-X - FT991A.ini" [-- args forwarded to run_study.py]
    python run_study_detached.py --daemon-exe ... --config ... --port ... --wsjtx-ini ... \\
        --resume -- --from-scenario S4                          # forwarded to resume_study.py

    powershell -Command "Get-Content <printed supervisor.log path> -Wait -Tail 20"   # HK-023 watch
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SUPERVISOR_RUNS_DIR = os.path.join(HERE, "results", "_supervisor_runs")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rr_precheck  # noqa: E402  (imports endurance_supervisor as ES internally)
from rr_precheck import ES  # noqa: E402  (utcnow/iso/daemon_processes/stop_daemon)
from harness.common import make_run_dir  # noqa: E402  (same call run_study.py makes internally --
                                          # deterministic, so calling it here first predicts
                                          # run_study.py's own run_dir exactly)

_RESULTS = Path(HERE) / "results"  # make_run_dir (harness.common) does path-object "/" joins,
                                    # not os.path.join -- found live, first collision-check test


def run_gatherer(sup_dir, arm, start_dt, end_dt, out_name):
    """The standard gatherer (tools/gather_live_run_artefacts.py) -- always this one, per the
    Captain's instruction, same as the endurance side. Repo root is a fixed two levels up from
    THIS file's own location (qa/rr-study/), which -- unlike endurance_supervisor.py -- is
    never copied elsewhere, so a __file__-relative path is safe here."""
    repo = os.path.normpath(os.path.join(HERE, "..", ".."))
    gatherer = os.path.join(repo, "tools", "gather_live_run_artefacts.py")
    if not os.path.isfile(gatherer):
        return {"ok": False, "error": "gatherer not found at %s" % gatherer}
    cmd = [sys.executable, gatherer,
           "--start", start_dt.strftime("%Y-%m-%d %H:%M:%S"),
           "--end", end_dt.strftime("%Y-%m-%d %H:%M:%S"),
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
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=3600)
    with open(os.path.join(sup_dir, "gatherer.stdout.log"), "w", encoding="utf-8") as f:
        f.write(r.stdout + "\n--- stderr ---\n" + r.stderr)
    return {"ok": r.returncode == 0, "exit_code": r.returncode, "out_name": out_name}


def _write_status(path, status):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=1)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daemon-exe", required=True, help="path to OpenWSFZ.Daemon.exe -- INPUT, never hardcoded")
    ap.add_argument("--config", required=True, help="path to an ALREADY-PREPARED config.json; "
                     "cycleAudioArchive.mode must be \"all\" (Captain's 'R&R keeps WAVs' decision) "
                     "or PRECHECK refuses")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--wsjtx-ini", required=True, help="path to the WSJT-X .ini this battery should read")
    ap.add_argument("--resume", action="store_true",
                     help="launch resume_study.py instead of run_study.py; PRECHECK will attach "
                          "to an already-running daemon if exactly one is found, instead of "
                          "refusing/starting a new one")
    ap.add_argument("--poll", action="store_true",
                     help="internal: this is what the detached child actually runs; not for interactive use")
    ap.add_argument("--supervisor-dir", default=None, help="internal: paired with --poll")
    a, forwarded = ap.parse_known_args()
    target = "resume_study.py" if a.resume else "run_study.py"

    if a.poll:
        sup_dir = a.supervisor_dir
        status_path = os.path.join(sup_dir, "status.json")
        log_path = os.path.join(sup_dir, "supervisor.log")
        status = {"phase": "PRECHECK", "target": target, "started_utc": ES.iso(ES.utcnow()),
                  "pid": os.getpid(), "args": forwarded}
        _write_status(status_path, status)

        # Predict run_study.py's own run_dir (deterministic -- see module docstring) and
        # REFUSE on a collision BEFORE touching the daemon at all (Architect, 2026-09-22,
        # reading this file before it was live-tested): make_run_dir's determinism is a
        # COLLISION risk, not only a convenience -- a second battery on the same UTC day AND
        # the same commit resolves to the SAME dir as the first, silently, and this has
        # already happened in practice (results/2026-09-13-4584900{,-2,-3,-4,-5} -- six
        # sweeps in one day, the -N suffixes added by hand afterwards because nothing caught
        # it at the time). A standard script makes repeat runs routine, so this needs to
        # refuse, not just predict -- and checking it FIRST (before PRECHECK/daemon start)
        # means a refusal never spins up a daemon just to tear it down again, and this whole
        # check is independently testable without any daemon at all.
        # make_run_dir() itself already created predicted_run_dir if it didn't exist (its own
        # mkdir(exist_ok=True)) -- it adds no content, so any entries found here mean a PRIOR
        # run left them, not this call. --resume is the deliberate exception: there the dir is
        # SUPPOSED to already exist and hold the interrupted run's own data.
        predicted_run_dir = make_run_dir(_RESULTS)
        if not a.resume and os.path.isdir(predicted_run_dir) and os.listdir(predicted_run_dir):
            status.update(phase="ABORTED", ended_utc=ES.iso(ES.utcnow()),
                          predicted_run_dir=str(predicted_run_dir),
                          note=("run_dir collision: %s already exists and is non-empty (same "
                                "UTC day + same commit as an earlier run -- make_run_dir has "
                                "no counter). Rename/move that directory, wait for a new "
                                "commit, or wait for the next UTC day, then re-run. If this IS "
                                "that earlier run continuing, use --resume instead."
                                % predicted_run_dir))
            _write_status(status_path, status)
            return 3

        run, arm = rr_precheck.precheck(sup_dir, a.daemon_exe, a.config, a.port, a.wsjtx_ini,
                                         allow_existing=a.resume)
        if not arm["checks"].get("all_pass"):
            status.update(phase="ABORTED", ended_utc=ES.iso(ES.utcnow()),
                          note="PRECHECK failed, see arm_config.json in this directory")
            _write_status(status_path, status)
            return 3

        d = arm.get("daemon", {})
        wsjtx_all_txt = os.path.join(os.path.dirname(a.wsjtx_ini), "ALL.TXT")
        owsfz_all_txt = d.get("config_decode_log_path")
        extra = []
        if "--wsjt-all-txt" not in forwarded and os.path.isfile(wsjtx_all_txt):
            extra += ["--wsjt-all-txt", wsjtx_all_txt]
        if "--owsfz-all-txt" not in forwarded and owsfz_all_txt:
            extra += ["--owsfz-all-txt", owsfz_all_txt]

        battery_start = ES.utcnow()
        status.update(phase="RUNNING", predicted_run_dir=str(predicted_run_dir),
                      battery_started_utc=ES.iso(battery_start))
        _write_status(status_path, status)

        with open(log_path, "ab") as logf:
            rc = subprocess.call([sys.executable, target] + forwarded + extra, cwd=HERE,
                                  stdout=logf, stderr=subprocess.STDOUT)
        battery_end = ES.utcnow()

        # ---------------- TEARDOWN: stop the daemon, orphan check, gather captured audio
        pre_teardown_others = [p for p in ES.daemon_processes() if p != run.daemon_pid]
        ES.stop_daemon(run, "battery finished, rc=%d" % rc)
        time.sleep(3)
        orphans = [p for p in ES.daemon_processes() if p not in pre_teardown_others]

        gather_out_name = os.path.basename(sup_dir) + "-gathered"
        gathered = run_gatherer(sup_dir, arm, battery_start, battery_end, gather_out_name)

        status.update(phase="DONE" if rc == 0 else "FAILED", exit_code=rc,
                      ended_utc=ES.iso(battery_end), orphans_after_teardown=orphans,
                      gathered=gathered)
        _write_status(status_path, status)
        return rc

    # ---------------- launcher: spawn the --poll child, fully detached
    os.makedirs(SUPERVISOR_RUNS_DIR, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    sup_dir = os.path.join(SUPERVISOR_RUNS_DIR, now.strftime("%Y%m%d_%H%M") + ("_resume" if a.resume else "_run"))
    os.makedirs(sup_dir, exist_ok=True)

    cmd = [sys.executable, os.path.abspath(__file__), "--poll", "--supervisor-dir", sup_dir,
           "--daemon-exe", a.daemon_exe, "--config", a.config, "--port", str(a.port),
           "--wsjtx-ini", a.wsjtx_ini]
    if a.resume:
        cmd.append("--resume")
    cmd += forwarded

    log_path = os.path.join(sup_dir, "supervisor.log")
    out = open(log_path, "ab")
    DETACHED, NEWGROUP, BREAKAWAY = 0x00000008, 0x00000200, 0x01000000
    try:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=HERE, creationflags=DETACHED | NEWGROUP | BREAKAWAY, close_fds=True)
        how = "detached + job breakaway"
    except OSError:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=HERE, creationflags=DETACHED | NEWGROUP, close_fds=True)
        how = "detached (no job breakaway available)"

    with open(os.path.join(sup_dir, "launcher.pid"), "w") as f:
        f.write(str(p.pid))
    print("SUPERVISOR_DIR=" + sup_dir)
    print("LAUNCHER_PID=%d (%s)" % (p.pid, how))
    print("TARGET=" + target + (" (forwarded args: %s)" % " ".join(forwarded) if forwarded else ""))
    print("watch: powershell -Command \"Get-Content '%s' -Wait -Tail 20\"" % log_path)
    print()
    print("PRECHECK runs first (arm_config.json in the supervisor dir) -- if it refuses, the")
    print("battery never starts. This does NOT auto-restart on a battery crash (see module")
    print("docstring). If it dies mid-battery, check status.json + supervisor.log, find the")
    print("actual run dir under results/, and resume deliberately:")
    print("    python run_study_detached.py --daemon-exe ... --config ... --port ... --wsjtx-ini ... --resume ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
