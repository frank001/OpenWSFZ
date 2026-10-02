#!/usr/bin/env python
"""R&R S1-S8 PRECHECK -- daemon lifecycle for a standardised battery run.

Architect, 2026-09-22 (reading commit f9166b52, the first R&R standardisation pass): "'Do the
same' includes the daemon: the Captain's endurance correction was 'the daemon start needs to
be part of the script', plus 'always the latest binary, build and test it yourself'. The R&R
daemon lifecycle is the part you flagged and skipped." This module is that piece, built the
second pass.

Reuses qa/endurance/endurance_supervisor.py's already-built-and-validated daemon-lifecycle
primitives directly (import, not a rewrite): Run, ps/sha256/pid_alive/ini_value,
load_build_provenance, start_daemon/stop_daemon/wait_ready. Those are generic over "a daemon
started from a given exe/config/port, with a build_provenance.json next to the exe" -- nothing
in them is endurance-specific. What's NEW here is the set of checks R&R itself cares about,
which differs from the endurance ROW 0:

- Identity (DLL SHA-256/shim/version), device-name agreement, captureActive/decodingEnabled,
  build provenance present + build-inputs clean -- same shape as endurance's PRECHECK.
- cycleAudioArchive.mode in the GIVEN config must actually be enabled ("all"), and RECORDED,
  and REFUSED if not -- per the Captain's "R&R keeps WAVs" decision (2026-09-22): without the
  daemon's own cycle-audio archive on, there is no captured audio to gather afterward, which
  would silently violate that decision. This is the R&R-specific gate endurance's own PRECHECK
  has no equivalent of (endurance's cycle-audio archiving was already assumed/checked via a
  different path).
- WSJT-X NDepth/AP bit -- RECORDED, not gated. Unlike LIVE-GAP-MAP (which pre-registered
  NDepth=3/no-AP as a hard requirement), neither STUDY-SPEC.md nor RUNBOOK.md name a required
  NDepth/AP for R&R -- there is no established bar to refuse against, so this follows the same
  "record when there's no established bar, gate only what's genuinely known-wrong" principle
  already used for build branch/commit this session.

NOT touched: run_scenario.py, harness/analyse.py, harness/matcher.py, run_study.py,
resume_study.py -- this module only decides whether to arm and records what came up; the
battery itself still runs exactly as before once PRECHECK passes.

NFR-021: counts, hashes, paths and config values only. No message text, no callsign.
"""
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENDURANCE_DIR = os.path.normpath(os.path.join(_HERE, "..", "endurance"))
if _ENDURANCE_DIR not in sys.path:
    sys.path.insert(0, _ENDURANCE_DIR)
import endurance_supervisor as ES  # noqa: E402  (reused verbatim: Run, ps, sha256, pid_alive,
                                    # ini_value, load_build_provenance, start_daemon,
                                    # stop_daemon, wait_ready -- see module docstring)

import urllib.request  # noqa: E402


def precheck(run_dir, daemon_exe, config_path, port, wsjtx_ini, allow_existing=False):
    """Starts the daemon with the GIVEN exe/config/port (never constructed), then RECORDS
    everything about what came up and REFUSES on a detected mismatch. Writes
    <run_dir>/arm_config.json. Returns (run, arm) -- `run` is the ES.Run instance (so the
    caller can stop_daemon() on it later, same object, same daemon_pid), `arm` is the
    dict written to arm_config.json.

    allow_existing: for --resume only. A battery interrupted mid-run may have left its own
    daemon still alive (the crash was in run_study.py/run_scenario.py, not necessarily the
    daemon) -- when True and exactly one daemon is already running, ATTACH to it (skip
    start_daemon()) instead of refusing on "no_other_daemon_running". Still runs every other
    check (identity, device match, captureActive, cycleAudioArchive.mode from the given
    config) against whatever is actually running. Default False for the primary battery
    start, matching the Architect's "start the daemon... before scenario 1" instruction --
    resume is the one case where reuse-if-alive is the more useful behaviour.

    Mirrors qa/endurance/endurance_supervisor.py's own precheck() shape closely -- see that
    function's comments for the reasoning behind each check; this docstring only notes what's
    R&R-specific (cycleAudioArchive, no NDepth/AP gate)."""
    os.makedirs(run_dir, exist_ok=True)
    run = ES.Run(run_dir)
    res = {"recorded_utc": ES.iso(ES.utcnow()), "checks": {}}

    existing = ES.daemon_processes()
    attach_existing = allow_existing and len(existing) == 1
    if existing and not attach_existing:
        res["checks"]["no_other_daemon_running"] = False
        res["checks"]["all_pass"] = False
        res["daemon_pids_found_before_start"] = existing
        _write(run_dir, res)
        return run, res
    res["checks"]["no_other_daemon_running"] = not existing
    res["checks"]["attached_existing_daemon"] = attach_existing

    if not os.path.isfile(daemon_exe):
        res["checks"]["daemon_exe_exists"] = False
        res["checks"]["all_pass"] = False
        _write(run_dir, res)
        return run, res
    if not os.path.isfile(config_path):
        res["checks"]["config_exists"] = False
        res["checks"]["all_pass"] = False
        _write(run_dir, res)
        return run, res
    res["checks"]["daemon_exe_exists"] = True
    res["checks"]["config_exists"] = True

    # Build provenance -- required, recorded, NOT a branch gate (Captain, direct, URGENT
    # reversal, 2026-09-22: "I really don't want that hard check on the branch. It should be
    # able to run on whatever we want."). The build-inputs dirty gate DOES still apply --
    # that objection was about the branch check specifically, not this one.
    provenance, prov_error, prov_path = ES.load_build_provenance(daemon_exe)
    res["checks"]["build_provenance_present"] = provenance is not None
    res["build_provenance_path"] = prov_path
    if provenance is None:
        res["checks"]["build_provenance_error"] = prov_error
        res["checks"]["all_pass"] = False
        _write(run_dir, res)
        return run, res
    if "build_dirty" not in provenance:
        res["checks"]["build_provenance_present"] = False
        res["checks"]["build_provenance_error"] = "stale format (no build_dirty field) -- re-run tools/capture_build_provenance.py"
        res["checks"]["all_pass"] = False
        _write(run_dir, res)
        return run, res
    res["build"] = {"branch": provenance.get("branch"), "commit": provenance.get("commit"),
                     "dirty": provenance.get("dirty"), "dirty_files": provenance.get("dirty_files", []),
                     "build_dirty": provenance.get("build_dirty"),
                     "build_dirty_files": provenance.get("build_dirty_files", []),
                     "captured_utc": provenance.get("captured_utc")}
    res["checks"]["build_tree_clean"] = not provenance.get("build_dirty")
    if provenance.get("build_dirty"):
        res["checks"]["all_pass"] = False
        _write(run_dir, res)
        return run, res

    # cycleAudioArchive must be ON in the GIVEN config -- R&R-specific gate, see module
    # docstring. Checked from the config file itself, before starting anything (cheap,
    # fast-fail): no point starting a daemon whose config can't produce the captured audio
    # the Captain's "R&R keeps WAVs" decision requires.
    try:
        cfgobj_pre = json.load(open(config_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfgobj_pre = {}
    archive_mode = (cfgobj_pre.get("cycleAudioArchive") or {}).get("mode")
    res["checks"]["cycle_audio_archive_enabled"] = (archive_mode == "all")
    res["cycle_audio_archive_mode"] = archive_mode
    if archive_mode != "all":
        res["checks"]["all_pass"] = False
        _write(run_dir, res)
        return run, res

    if attach_existing:
        run.daemon_pid = existing[0]
        run.log("RESUME: attaching to already-running daemon pid %d instead of starting a new one" % run.daemon_pid)
    else:
        ES.start_daemon(run, daemon_exe, config_path, port)
    if not ES.wait_ready(run, port):
        res["checks"]["became_ready"] = False
        res["checks"]["all_pass"] = False
        if not attach_existing:
            ES.stop_daemon(run, "PRECHECK: never became ready")
        _write(run_dir, res)
        return run, res
    res["checks"]["became_ready"] = True

    pid = run.daemon_pid
    res["daemon"] = {"pid": pid, "exe": daemon_exe, "config_path": config_path, "port": port}

    dll = None
    for _ in range(24):
        mod = ES.ps("(Get-Process -Id %d).Modules | Where-Object { $_.ModuleName -eq "
                     "'libft8.dll' } | Select-Object -ExpandProperty FileName" % pid).splitlines()
        if mod:
            dll = mod[0].strip(); break
        time.sleep(5)
    res["daemon"]["dll_path"] = dll
    res["daemon"]["dll_sha256"] = ES.sha256(dll) if dll and os.path.exists(dll) else None
    res["daemon"]["build_branch"] = res["build"]["branch"]
    res["daemon"]["build_commit"] = res["build"]["commit"]

    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % port, timeout=6) as r:
            st = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        res["checks"]["status_endpoint_ok"] = False
        res["checks"]["status_endpoint_error"] = type(e).__name__
        res["checks"]["all_pass"] = False
        if not attach_existing:
            ES.stop_daemon(run, "PRECHECK: status endpoint failed")
        _write(run_dir, res)
        return run, res
    res["checks"]["status_endpoint_ok"] = True
    res["daemon"]["shim_version"] = st.get("shimVersion")
    res["daemon"]["daemon_version"] = st.get("version")
    res["daemon"]["audio_device"] = st.get("audioDevice")
    res["daemon"]["captureActive"] = st.get("captureActive")
    res["daemon"]["decodingEnabled"] = st.get("decodingEnabled")

    cfgobj = cfgobj_pre
    res["daemon"]["config_audio_device_friendly_name"] = cfgobj.get("audioDeviceFriendlyName")
    res["daemon"]["config_audio_device_id"] = cfgobj.get("audioDeviceId")
    res["daemon"]["config_decode_log_path"] = (cfgobj.get("decodeLog") or {}).get("path")
    res["daemon"]["config_cycle_audio_dir"] = (cfgobj.get("cycleAudioArchive") or {}).get("directory")
    res["daemon"]["config_log_dir"] = (cfgobj.get("logging") or {}).get("directory")

    wname = ES.ini_value(wsjtx_ini, "SoundInName")
    res["wsjtx"] = {
        "ini_path": wsjtx_ini,
        "NDepth": ES.ini_value(wsjtx_ini, "NDepth"),          # recorded, not gated -- see module docstring
        "ap_enabled": ES.ini_value(wsjtx_ini, "aprioriEnabled"),  # recorded, not gated
        "dial_freq_hz": ES.ini_value(wsjtx_ini, "DialFreq"),
        "mode": ES.ini_value(wsjtx_ini, "Mode"),
        "sound_in_name": wname,
        "sound_in_chan": ES.ini_value(wsjtx_ini, "SoundInChan") or "ABSENT (WSJT-X default applies)",
    }

    device_match = bool(res["daemon"].get("config_audio_device_friendly_name") == wname)
    res["checks"]["device_names_match"] = device_match
    res["checks"]["captureActive"] = bool(res["daemon"].get("captureActive"))
    res["checks"]["decodingEnabled"] = bool(res["daemon"].get("decodingEnabled"))
    res["checks"]["dll_readable"] = bool(res["daemon"].get("dll_sha256"))
    res["checks"]["all_pass"] = all([device_match, res["checks"]["captureActive"],
                                      res["checks"]["decodingEnabled"], res["checks"]["dll_readable"]])

    _write(run_dir, res)
    if not res["checks"]["all_pass"] and not attach_existing:
        ES.stop_daemon(run, "PRECHECK: mismatch detected, see arm_config.json")
    return run, res


def _write(run_dir, res):
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "arm_config.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
