#!/usr/bin/env python
"""SUB-FEAS offline flag-OFF/ON replay of the 2026-09-30 on-air night: unattended orchestrator (detached, resumable).

Spec (PRE-REGISTERED, Architect 2026-10-01 19:35Z): qa/rr-study/2026-10-01-1935-architect-to-qa-spec-sub-feas-offline-onoff-replay.md

This script RUNS the three arms and records raw per-cycle rows. It does NOT analyse them: validity rows V1..V6, the NET, its
interval and the verdict D1/D2/D3 are computed afterwards by onoff_replay_rows.py, so nothing can be tuned while a run is going.

Arms (each a FRESH process, cycles in ascending stamp order, numeric outputs only, spec section 2 and 7):
  OFF    harness --mode two0  --stratum ALL   flag OFF, DecodeTwoStageAsync, one call per cycle
  ON     harness --mode two1  --stratum ALL   flag ON,  DecodeTwoStageAsync, one call per cycle, subtractionMaxThreads 8
  ONREP  harness --mode two1  --stratum V6    a second fresh ON process over the first 160 included cycles (row V6)
Run order OFF, ON, ONREP (spec section 7). Every arm uses the SAME decoder config (nhard 40, kMinScorePass2 10,
osdCorrThreshold 0.10, threads 8): the flag is the only difference.

Pre-flight (all asserted; any failure aborts before a single decode):
  - selection.json LF-normalised SHA-256 == the pinned value (git converts line endings, so the pin is over LF bytes);
  - the harness sources, scripts and selection are COMMITTED (git status of GUARDED is empty): no decode before the commit;
  - the build under test is the checkout at 247ac391, the harness builds against it, and libft8.dll == the pin ee00d118...990e4c;
  - nothing competing is running (wsjtx, jt9, OpenWSFZ, testhost, MSBuild, other dotnet): WSJT-X is CLOSED (spec section 7.3);
  - the artefact directory is gitignored (no data can be committed by accident).
Per arm: the DLL SHA is checked at the START and at the END (row V1), a sampler records any competing process every 30 min
(spec 7.3), a heartbeat is written to status.json, and a crashed harness is restarted up to 3 times after dropping any partial
rows of the interrupted cycle (rows are resumable; the harness skips cycles already in its CSV).

HK-037 / NFR-021: ALL.TXT is passed to the harness (it reads it INSIDE the matching function) and is otherwise only read by
onoff_replay_rows.py for stamp counts. No message text is written by any file this script touches.
HK-013 / HK-019 / HK-023: detached launch, supervised, teardown with an orphan check; sleep is prevented for the process lifetime.

  OPENWSFZ_ARTEFACTS=<dir> overrides the artefacts directory (the data is in the QA worktree; it does not travel between worktrees).
"""
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_run as R   # noqa: E402  (log, status, sha256, env_snapshot, now)

REPO = R.REPO
ART = os.environ.get("OPENWSFZ_ARTEFACTS", R.ART)
R.ART = ART
RUN = "20260930_1930"
OUT = os.path.join(ART, "rr_2026-10-01_onoff_replay")
R.OUT = OUT

SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-01-sub-feas-offline-onoff-replay", "selection.json")
SELECTION_SHA256 = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"   # LF-normalised bytes
CHECKOUT = r"C:\Users\Frank\w-twostage-review"
BUILD_COMMIT = "247ac391"
HOUT = r"C:\Users\Frank\w-onoff-out"
DLL = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
WAV_DIR = os.path.join(ART, f"{RUN}_endurance_run", "cycle-audio")
WS_ALLTXT = os.path.join(ART, f"{RUN}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
THREADS = "8"
MAX_RESTARTS = 3
SAMPLER_PERIOD_S = 1800
COMPETITOR_RE = r"^(wsjtx|jt9|OpenWSFZ|testhost|MSBuild|dotnet|VBCSCompiler)"
GUARDED = [
    "qa/rr-study/sub-feas/replay81",
    "qa/rr-study/sub-feas/select_onoff.py",
    "qa/rr-study/sub-feas/onoff_replay_run.py",
    "qa/rr-study/sub-feas/onoff_replay_rows.py",
    "qa/tests/test_onoff_replay_rows.py",
    "qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/selection.json",
]
# (arm label, harness mode, selection stratum, csv flag label)
ARMS = [("OFF", "two0", "ALL", "OFF"), ("ON", "two1", "ALL", "ON"), ("ONREP", "two1", "V6", "ON")]


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def sha256_lf(path):
    """SHA-256 over the file with CRLF folded to LF: git's autocrlf must not change a pin."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def competitors(exclude_pid=None):
    ps = ("Get-Process | Where-Object { $_.ProcessName -match '" + COMPETITOR_RE + "' } | "
          "ForEach-Object { '{0},{1}' -f $_.ProcessName, $_.Id }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        if "," not in line:
            continue
        name, pid = line.strip().rsplit(",", 1)
        if exclude_pid is not None and pid == str(exclude_pid):
            continue
        rows.append((name, pid))
    return rows


class Sampler(threading.Thread):
    """Spec 7.3: every 30 min record any competing process other than the harness; names and pids only."""
    def __init__(self):
        super().__init__(daemon=True)
        self.pid = None
        self.stop = threading.Event()
        self.path = os.path.join(OUT, "cpu_sampler.csv")
        if not os.path.exists(self.path):
            open(self.path, "w").write("utc,arm,name,pid\n")
        self.arm = ""

    def run(self):
        while not self.stop.wait(SAMPLER_PERIOD_S):
            self.sample()

    def sample(self):
        for name, pid in competitors(self.pid):
            with open(self.path, "a") as fh:
                fh.write(f"{R.now()},{self.arm},{name},{pid}\n")


def preflight():
    os.makedirs(OUT, exist_ok=True)
    # The artefacts directory may belong to another worktree of this repository (the data does not travel between
    # worktrees), so its git checks run in THAT worktree's context.
    art_repo = os.path.dirname(ART)
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x"), cwd=art_repo).returncode == 0, "OUT not gitignored"
    assert sh("git", "ls-files", "--", OUT, cwd=art_repo).stdout.strip() == ""
    sel_sha = sha256_lf(SELECTION)
    assert sel_sha == SELECTION_SHA256, ("selection.json SHA mismatch", sel_sha)
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts/selection not committed"
    assert os.path.isfile(WS_ALLTXT) and os.path.isdir(WAV_DIR)
    head = sh("git", "rev-parse", "HEAD", cwd=CHECKOUT).stdout.strip()
    assert head.startswith(BUILD_COMMIT), head
    assert sh("git", "status", "--porcelain", cwd=CHECKOUT).stdout.strip() == "", "build checkout not clean"
    r = sh("dotnet", "build", os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj"), "-c", "Release",
           f"-p:RepoRoot={CHECKOUT}", "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-o", HOUT,
           "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-600:]
    sh("dotnet", "build-server", "shutdown")   # no lingering compiler servers to be mistaken for competitors
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    assert got == DLL, got
    comp = competitors()
    assert not comp, ("a competing process is running (WSJT-X closed, nothing else heavy)", comp)
    pre = {"utc": R.now(), "spec": "2026-10-01-1935", "selection_sha256_lf": sel_sha, "libft8_sha256": got,
           "build_commit": BUILD_COMMIT, "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(),
           "harness_dll_sha256": R.sha256(os.path.join(HOUT, "Replay81.dll")), "threads": THREADS,
           "arms": [a[0] for a in ARMS], "wav_dir": WAV_DIR.replace(ART, "<artefacts>"),
           "inherited_open_item": "wsjtx_ini_dial_freq_matches_daemon=false (not resolved; named in the report limits)"}
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    R.env_snapshot("env_start.txt")
    return pre


def files_for(arm):
    return {k: os.path.join(OUT, f"{k}_{arm}.{ext}") for k, ext in
            (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("log", "log"))}


def done_stamps(csv_path):
    s = set()
    if os.path.exists(csv_path):
        for line in open(csv_path, encoding="utf-8").read().splitlines()[1:]:
            p = line.split(",")
            if len(p) >= 5:
                s.add(p[2])
    return s


def repair_partial(arm):
    """After a crash, drop testb/outcome rows of a cycle that never reached its run-csv row (they are written first)."""
    f = files_for(arm)
    done = done_stamps(f["run"])
    for key, col in (("testb", 1), ("outcomes", 0)):
        p = f[key]
        if not os.path.exists(p):
            continue
        lines = open(p, encoding="utf-8").read().splitlines()
        keep = [lines[0]] if key == "testb" and lines else []
        for line in (lines[1:] if key == "testb" else lines):
            cells = line.split(",")
            if len(cells) > col and cells[col] in done:
                keep.append(line)
        open(p, "w", encoding="utf-8", newline="\n").write("\n".join(keep) + ("\n" if keep else ""))


def pin_record(arm, when):
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    with open(os.path.join(OUT, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": R.now(), "arm": arm, "when": when, "libft8_sha256": got, "pinned": DLL,
                             "match": got == DLL}) + "\n")
    return got == DLL


def run_arm(arm, mode, stratum, sampler):
    f = files_for(arm)
    n_expected = len(json.load(open(SELECTION))["runs"][RUN][stratum])
    sampler.arm = arm
    ok_start = pin_record(arm, "start")
    R.log(f"arm {arm} start: mode={mode} stratum={stratum} cycles={n_expected} dll_match={ok_start}")
    restarts = 0
    while True:
        repair_partial(arm)
        cmd = ["dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", SELECTION, "--run", RUN, "--stratum", stratum,
               "--wav-root", ART, "--wav-dir", WAV_DIR, "--out", f["run"], "--log", f["log"], "--mode", mode,
               "--threads", THREADS, "--label", f"{BUILD_COMMIT}:onoff_{arm}", "--wsjtx-alltxt", WS_ALLTXT,
               "--testb-out", f["testb"], "--outcomes", f["outcomes"]]
        t0 = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        sampler.pid = proc.pid
        while proc.poll() is None:
            R.status("ARM", arm=arm, cycles_done=len(done_stamps(f["run"])), cycles_expected=n_expected, restarts=restarts)
            time.sleep(60)
        rc = proc.returncode
        err = (proc.stderr.read() or "")[-300:]
        R.log(f"arm {arm} harness rc={rc} in {time.time() - t0:.0f}s (restart {restarts}) stderr_tail={err.strip()[:120]!r}")
        with open(os.path.join(OUT, "process_exits.log"), "a") as fh:
            fh.write(f"{R.now()} {arm} rc={rc} restart={restarts}\n")
        if rc == 0:
            break
        restarts += 1
        if restarts > MAX_RESTARTS:
            R.log(f"arm {arm}: giving up after {MAX_RESTARTS} restarts (rows V3 will show it)")
            break
    ok_end = pin_record(arm, "end")
    R.log(f"arm {arm} end: rows={len(done_stamps(f['run']))}/{n_expected} dll_match={ok_end}")
    return rc


def main():
    os.makedirs(OUT, exist_ok=True)
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # no sleep for the process lifetime
    R.log("orchestrator start (offline flag-OFF/ON replay)")
    pre = preflight()
    if "--preflight-only" in sys.argv:
        # Proves every arming assertion (clean commit, selection SHA, build, DLL pin, no competitors) WITHOUT decoding anything.
        R.log(f"preflight-only: all assertions passed (harness commit {pre['harness_commit'][:8]}); nothing decoded")
        R.status("PREFLIGHT_ONLY", harness_commit=pre["harness_commit"])
        return 0
    sampler = Sampler()
    sampler.start()
    sampler.sample()
    rcs = {}
    try:
        for arm, mode, stratum, _flag in ARMS:
            rcs[arm] = run_arm(arm, mode, stratum, sampler)
    finally:
        sampler.stop.set()
        sampler.sample()
    R.env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81' } | Select-Object Id | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", rcs=rcs, orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log(f"orchestrator DONE rcs={rcs} orphan_check={'empty' if not orphans else 'NON-EMPTY'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
