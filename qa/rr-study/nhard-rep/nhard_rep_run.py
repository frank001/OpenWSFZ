#!/usr/bin/env python
"""NHARD-REP: unattended orchestrator (detached, resumable).

Spec (PRE-REGISTERED, Architect 2026-10-06 14:31Z + Amendment 1 15:01Z; BAR_N = 0.5 pp ratified by the Captain 14:34Z, FROZEN):
  qa/rr-study/2026-10-06-1430-architect-to-qa-spec-nhard-replication.md   (branch arch/nhard-replication)

This script RUNS the arms and records raw per-cycle rows. It does NOT analyse them: V1..V6, NET, its interval and the verdict are
computed afterwards by nhard_rep_rows.py, so nothing can be tuned while a run is going. The ONE predicate it evaluates is V2,
because the spec makes it a gate on the corpus arms ("If V2 fails the Architect rules before anything else runs").

Arms (each a FRESH process; flag ON, subtractionMaxThreads 8, DecodeTwoStageAsync one call per cycle, harness mode two1):
  V2N40  noise positive control, nhard 40, 200 seeded pure-noise WAVs
  V2N60  the same noise, nhard 60            -> V2 gate: n_false(60) >= n_false(40) + 3, else STOP here
  N40    the 311 sampled cycles, nhard 40
  N60    the same cycles, nhard 60
  AA     a second fresh nhard-40 process over the first 200 sampled cycles (row V6)
The ONLY thing that differs between N40 and N60 is --nhard.

Pre-flight (all asserted; any failure aborts before a single decode):
  - selection.json LF-normalised SHA-256 == the pinned value; the noise WAVs on disk match the manifest inside it;
  - harness sources, scripts, tests and selection are COMMITTED (git status of GUARDED is empty): no decode before the commit;
  - the build under test is a clean checkout at BUILD_COMMIT, the harness builds against it, libft8.dll == the pinned SHA-256;
  - the harness REFUSES --nhard 50 (the setting is accepted only as 40 or 60);
  - WSJT-X, jt9 and the daemon are not running (the reference is the archived ALL.TXT); ordinary PC load is accepted (Captain).
Per arm: the DLL SHA is checked at the START and at the END (row V1); a sampler records competing processes every 30 min; a
heartbeat goes to status.json; a crashed harness is restarted up to 3 times after dropping partial rows of the interrupted cycle.

HK-037 / NFR-021: ALL.TXT is passed to the harness (read INSIDE the matching function); no message text is written by any file here.
HK-013 / HK-019 / HK-023: detached launch, supervised by onoff_replay_watchdog.py, teardown with an orphan check, sleep prevented.

  OPENWSFZ_ARTEFACTS=<dir> overrides the artefacts directory.   --preflight-only proves every assertion without decoding.
"""
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
sys.path.insert(0, HERE)
import replay81_run as R   # noqa: E402  (log, status, sha256, env_snapshot, now)
import nhard_rep_rows as ROWS   # noqa: E402

REPO = R.REPO
ART = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
R.ART = ART
RUN = "20261004_1634"
OUT = os.path.join(ART, "rr_2026-10-06_nhard_rep")
R.OUT = OUT

SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
SELECTION_SHA256 = ROWS.SELECTION_SHA256
CHECKOUT = r"D:\Projects\claude\_qa-scratch\nhard-rep\tree"
BUILD_COMMIT = "be3cc5ac"
HOUT = r"D:\Projects\claude\_qa-scratch\nhard-rep\out"
DLL = ROWS.DLL_PIN
WAV_DIR = os.path.join(ART, f"{RUN}_endurance_run-gathered", "owsfz", "wav")
NOISE_DIR = os.path.join(OUT, "noise")
WS_ALLTXT = os.path.join(ART, f"{RUN}_endurance_run-gathered", "wsjtx", "ALL.TXT")
THREADS = ROWS.THREADS
MAX_RESTARTS = 3
SAMPLER_PERIOD_S = 1800
BLOCKING_RE = r"^(wsjtx|jt9|OpenWSFZ)"                     # must NOT be running
RECORDED_RE = r"^(wsjtx|jt9|OpenWSFZ|testhost|MSBuild|dotnet|VBCSCompiler)"   # recorded by the sampler (names and pids only)
GUARDED = [
    "qa/rr-study/sub-feas/replay81",
    "qa/rr-study/nhard-rep",
    "qa/tests/test_nhard_rep_rows.py",
    "qa/rr-study/results/2026-10-06-nhard-rep/selection.json",
]
# (arm, run key in selection.json, stratum, nhard, corpus?)
ARMS = [("V2N40", "NOISE", "ALL", 40, False), ("V2N60", "NOISE", "ALL", 60, False),
        ("N40", RUN, "SAMPLE", 40, True), ("N60", RUN, "SAMPLE", 60, True), ("AA", RUN, "AA", 40, True)]
assert [a[0] for a in ARMS] == list(ROWS.ARMS) and all(a[3] == ROWS.ARM_NHARD[a[0]] for a in ARMS)


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def sha256_lf(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def processes(regex, exclude_pid=None):
    ps = ("Get-Process | Where-Object { $_.ProcessName -match '" + regex + "' } | "
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
    """Every 30 min record competing processes other than the harness; names and pids only."""
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
        for name, pid in processes(RECORDED_RE, self.pid):
            with open(self.path, "a") as fh:
                fh.write(f"{R.now()},{self.arm},{name},{pid}\n")


def preflight():
    os.makedirs(OUT, exist_ok=True)
    art_repo = os.path.dirname(ART)
    assert sh("git", "check-ignore", "-q", os.path.join(OUT, "x"), cwd=art_repo).returncode == 0, "OUT not gitignored"
    assert sh("git", "ls-files", "--", OUT, cwd=art_repo).stdout.strip() == ""
    sel_sha = sha256_lf(SELECTION)
    assert sel_sha == SELECTION_SHA256, ("selection.json SHA mismatch", sel_sha)
    sel = json.load(open(SELECTION))
    manifest = sel["noise"]["wav_sha256"]
    for st, want in manifest.items():
        got = R.sha256(os.path.join(NOISE_DIR, st + ".wav"))
        assert got == want, ("noise WAV differs from the frozen manifest", st)
    assert len(manifest) == 201
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts/selection not committed"
    assert os.path.isfile(WS_ALLTXT) and os.path.isdir(WAV_DIR)
    head = sh("git", "rev-parse", "HEAD", cwd=CHECKOUT).stdout.strip()
    assert head.startswith(BUILD_COMMIT), head
    assert sh("git", "status", "--porcelain", cwd=CHECKOUT).stdout.strip() == "", "build checkout not clean"
    r = sh("dotnet", "build", os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj"), "-c", "Release",
           f"-p:RepoRoot={CHECKOUT}", "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-o", HOUT,
           "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-600:]
    sh("dotnet", "build-server", "shutdown")
    got = R.sha256(os.path.join(HOUT, "libft8.dll"))
    assert got == DLL, got
    # the harness must refuse a cap outside {40, 60}: run it with --nhard 50 and require a non-zero exit and NO output file
    reject_dir = os.path.join(OUT, "_reject_probe")
    rj = sh("dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", SELECTION, "--run", "NOISE", "--stratum", "ALL",
            "--wav-root", ART, "--wav-dir", NOISE_DIR, "--out", os.path.join(reject_dir, "x.csv"),
            "--log", os.path.join(reject_dir, "x.log"), "--mode", "two1", "--threads", THREADS, "--nhard", "50")
    assert rj.returncode != 0 and not os.path.exists(reject_dir), ("harness accepted --nhard 50", rj.returncode)
    comp = processes(BLOCKING_RE)
    assert not comp, ("WSJT-X / jt9 / the daemon must be closed", comp)
    pre = {"utc": R.now(), "spec": "2026-10-06-1430 + Amendment 1", "BAR_N_pp": ROWS.BAR_N, "selection_sha256_lf": sel_sha,
           "libft8_sha256": got, "build_commit": BUILD_COMMIT, "build_commit_full": head,
           "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(),
           "harness_dll_sha256": R.sha256(os.path.join(HOUT, "Replay81.dll")), "threads": THREADS,
           "subtractionEnabled": True, "kMinScorePass2": 10, "osdCorrThreshold": 0.10,
           "arms": [a[0] for a in ARMS], "wav_dir": WAV_DIR.replace(ART, "<artefacts>"),
           "harness_rejects_nhard_50": True}
    json.dump(pre, open(os.path.join(OUT, "preflight.json"), "w"), indent=1)
    R.env_snapshot("env_start.txt")
    return pre


def files_for(arm):
    return {k: os.path.join(OUT, f"{k}_{arm}.{ext}") for k, ext in
            (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("log", "log"))}


def done_stamps(csv_path):
    s = set()
    if os.path.exists(csv_path):
        for line in open(csv_path, encoding="utf-8").read().splitlines()[1:]:
            p = line.split(",")
            if len(p) >= 5:
                s.add(p[2])
    return s


def repair_partial(arm):
    """After a crash, drop testb/outcome/abandon/matched rows of a cycle that never reached its run-csv row (written first)."""
    f = files_for(arm)
    done = done_stamps(f["run"])
    for key, col, has_header in (("testb", 1, True), ("outcomes", 0, False), ("abandon", 0, True), ("matched", 0, True)):
        p = f[key]
        if not os.path.exists(p):
            continue
        lines = open(p, encoding="utf-8").read().splitlines()
        keep = [lines[0]] if has_header and lines else []
        for line in (lines[1:] if has_header else lines):
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


def run_arm(arm, runkey, stratum, nhard, corpus, sampler):
    f = files_for(arm)
    n_expected = len(json.load(open(SELECTION))["runs"][runkey][stratum])
    sampler.arm = arm
    ok_start = pin_record(arm, "start")
    R.log(f"arm {arm} start: run={runkey} stratum={stratum} nhard={nhard} cycles={n_expected} dll_match={ok_start}")
    restarts = 0
    while True:
        repair_partial(arm)
        cmd = ["dotnet", os.path.join(HOUT, "Replay81.dll"), "--selection", SELECTION, "--run", runkey, "--stratum", stratum,
               "--wav-root", ART, "--wav-dir", (WAV_DIR if corpus else NOISE_DIR), "--out", f["run"], "--log", f["log"],
               "--mode", "two1", "--threads", THREADS, "--nhard", str(nhard), "--label", f"{BUILD_COMMIT}:nhardrep_{arm}",
               "--outcomes", f["outcomes"], "--abandon-out", f["abandon"]]
        if corpus:
            cmd += ["--wsjtx-alltxt", WS_ALLTXT, "--testb-out", f["testb"], "--matched-out", f["matched"]]
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
            R.log(f"arm {arm}: giving up after {MAX_RESTARTS} restarts (row V3 will show it)")
            break
    ok_end = pin_record(arm, "end")
    R.log(f"arm {arm} end: rows={len(done_stamps(f['run']))}/{n_expected} dll_match={ok_end}")
    return rc


def main():
    os.makedirs(OUT, exist_ok=True)
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # no sleep for the process lifetime
    R.log("orchestrator start (NHARD-REP)")
    pre = preflight()
    if "--preflight-only" in sys.argv:
        R.log(f"preflight-only: all assertions passed (harness commit {pre['harness_commit'][:8]}); nothing decoded")
        R.status("PREFLIGHT_ONLY", harness_commit=pre["harness_commit"])
        return 0
    sampler = Sampler()
    sampler.start()
    sampler.sample()
    rcs, stopped = {}, None
    try:
        for arm, runkey, stratum, nhard, corpus in ARMS:
            if corpus and not os.path.exists(os.path.join(OUT, "v2_gate.json")):
                ok, det = ROWS.evaluate_v2(OUT)
                json.dump({"utc": R.now(), "V2_pass": ok, **det}, open(os.path.join(OUT, "v2_gate.json"), "w"), indent=1)
                R.log(f"V2 gate: pass={ok} {det}")
                if not ok:
                    stopped = "V2_FAIL"
                    break
            elif corpus and not json.load(open(os.path.join(OUT, "v2_gate.json")))["V2_pass"]:
                stopped = "V2_FAIL"
                break
            rcs[arm] = run_arm(arm, runkey, stratum, nhard, corpus, sampler)
    finally:
        sampler.stop.set()
        sampler.sample()
    R.env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81' } | Select-Object Id | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    # status DONE ends the watchdog (HK-019) even when the run stopped at the V2 gate; the reason is recorded beside it
    R.status("DONE", rcs=rcs, stopped=stopped, orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log(f"orchestrator DONE rcs={rcs} stopped={stopped} orphan_check={'empty' if not orphans else 'NON-EMPTY'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
