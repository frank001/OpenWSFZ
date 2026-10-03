#!/usr/bin/env python
"""SUB-FEAS Stage B (Amendment 5): the T2' replay of the 2026-09-30 night, ONE build per invocation (unattended, detached, resumable).

Spec (PRE-REGISTERED): qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md section 5h (Amendment 5, commits 7f544638 + 4301e8c5);
OpenSpec change sub-feas-speed-redesign, tasks 15.2(c), 15.5, 15.12.

What it runs: replay81 --mode two1 (flag ON, DecodeTwoStageAsync, ONE call per cycle) --threads 8, nhard 40, over the T2' LIST = every fourth cycle
(index = 0 mod 4) of the ALL stratum of the frozen 10-01 selection (parent SHA-256 over LF bytes pinned below). The list is DERIVED here from the
pinned parent, its count is asserted (about 1 075) and written to the output directory; if the Engineer's #122 gate 4a list (selection_p.json) is
given with --p-list, the two lists must be IDENTICAL (and its LF SHA-256 is recorded), which is how that list is "reused with its SHA asserted".

It RECORDS raw per-cycle rows only. The verdict (E-rows aside, the T2' median with abandoned cycles as +infinity) is computed afterwards by
replay_t2prime_rows.py, so nothing can be tuned while a run is going. Run it once for the same-session Stage A baseline (the current `main` build)
and once per Stage B item, back to back, on an otherwise idle PC: it is a TIMING run.

Arguments (all required except the flags):
  --label NAME          short tag for the output folder and the rows (for example stageA-main, B2)
  --checkout PATH       a clean checkout of the build under test
  --commit SHA7         the commit that checkout must be at (prefix match)
  --dll-pin SHA256      the libft8.dll SHA-256 the build must produce; recorded in preflight.json BEFORE any decode and re-checked at the end
  --preflight-only      prove every arming assertion (and build the harness) WITHOUT decoding anything
  --p-list PATH         optional: the #122 gate 4a selection_p.json to compare against

Pre-flight (all asserted; any failure aborts before a single decode): parent selection SHA; derived list count; output dir gitignored and untracked; the
harness sources, this script, the rows script and its tests COMMITTED; the checkout clean and at --commit; harness built against it and libft8.dll ==
--dll-pin; nothing competing is running (WSJT-X closed, no other dotnet/testhost/MSBuild/OpenWSFZ); every selected WAV present in the gathered folder.
NOTE (2026-10-03): the raw 20260930_1930 cycle-audio folder was emptied by the gatherer's move; the WAVs live in 20260930_1930_endurance_run-gathered/owsfz/wav,
which is the harness's default directory, so --wav-dir is NOT passed.

HK-037 / NFR-021: only stamps, counts and timings are read or written; ALL.TXT is not used (no Test B in this run).
HK-013 / HK-019 / HK-023: launch DETACHED with a log tail (nohup python ... & disown); status.json heartbeat; a crashed harness is restarted up to 3
times after dropping partial rows; teardown with an orphan check; sleep prevented for the process lifetime.
  OPENWSFZ_ARTEFACTS=<dir> overrides the artefacts directory.
"""
import argparse
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
SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-01-sub-feas-offline-onoff-replay", "selection.json")
SELECTION_SHA256 = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"   # LF-normalised bytes (same pin as onoff_replay_run.py)
STEP = 4                                    # every fourth cycle, index = 0 mod 4
LIST_COUNT_RANGE = (1000, 1150)             # "about 1 075"; a count outside this means the wrong parent or step
THREADS = "8"                               # as on air
MAX_RESTARTS = 3
SAMPLER_PERIOD_S = 1800
COMPETITOR_RE = r"^(wsjtx|jt9|OpenWSFZ|testhost|MSBuild|dotnet|VBCSCompiler)"
GUARDED = [
    "qa/rr-study/sub-feas/replay81",
    "qa/rr-study/sub-feas/replay_t2prime_run.py",
    "qa/rr-study/sub-feas/replay_t2prime_rows.py",
    "qa/rr-study/tests/test_t2prime_rows.py",
    "qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/selection.json",
]


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
    """Every 30 min record any competing process other than the harness; names and pids only."""
    def __init__(self, out):
        super().__init__(daemon=True)
        self.pid = None
        self.stop = threading.Event()
        self.path = os.path.join(out, "cpu_sampler.csv")
        if not os.path.exists(self.path):
            open(self.path, "w").write("utc,name,pid\n")

    def run(self):
        while not self.stop.wait(SAMPLER_PERIOD_S):
            self.sample()

    def sample(self):
        for name, pid in competitors(self.pid):
            with open(self.path, "a") as fh:
                fh.write(f"{R.now()},{name},{pid}\n")


def derive_list():
    """The T2' list: ALL[::STEP] of the pinned parent, as a one-run selection document the harness can read."""
    par = json.load(open(SELECTION, encoding="utf-8"))
    assert par["run"] == RUN, par["run"]
    allc = par["runs"][RUN]["ALL"]
    lst = allc[::STEP]
    assert LIST_COUNT_RANGE[0] <= len(lst) <= LIST_COUNT_RANGE[1], ("T2' list count outside the expected range", len(lst))
    assert lst == sorted(lst), "the parent ALL list must be in ascending stamp order"
    doc = {"spec": "qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md section 5h (Amendment 5)",
           "run": RUN, "step": STEP, "parent_sha256_lf": SELECTION_SHA256, "parent_count": len(allc),
           "runs": {RUN: {"ALL": lst, "warmup": par["runs"][RUN]["warmup"]}}}
    return doc


def preflight(args, out, harness_out):
    os.makedirs(out, exist_ok=True)
    art_repo = os.path.dirname(ART)
    assert sh("git", "check-ignore", "-q", os.path.join(out, "x"), cwd=art_repo).returncode == 0, "OUT not gitignored"
    assert sh("git", "ls-files", "--", out, cwd=art_repo).stdout.strip() == ""
    sel_sha = sha256_lf(SELECTION)
    assert sel_sha == SELECTION_SHA256, ("parent selection.json SHA mismatch", sel_sha)
    assert sh("git", "status", "--porcelain", "--", *GUARDED).stdout.strip() == "", "harness/scripts/tests/selection not committed"
    doc = derive_list()
    list_path = os.path.join(out, "selection_t2p.json")
    open(list_path, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    list_sha = sha256_lf(list_path)
    p_sha = None
    if args.p_list:
        p_doc = json.load(open(args.p_list, encoding="utf-8"))
        assert p_doc["runs"][RUN]["ALL"] == doc["runs"][RUN]["ALL"], "the #122 gate 4a list differs from the derived T2' list"
        p_sha = sha256_lf(args.p_list)
    wav_dir = os.path.join(ART, f"{RUN}_endurance_run-gathered", "owsfz", "wav")
    missing = [s for s in doc["runs"][RUN]["ALL"] if not os.path.isfile(os.path.join(wav_dir, s + ".wav"))]
    assert not missing, ("selected WAVs missing from the gathered folder", len(missing))
    head = sh("git", "rev-parse", "HEAD", cwd=args.checkout).stdout.strip()
    assert head.startswith(args.commit), ("checkout is not at the expected commit", head)
    assert sh("git", "status", "--porcelain", cwd=args.checkout).stdout.strip() == "", "build checkout not clean"
    r = sh("dotnet", "build", os.path.join(REPO, "qa", "rr-study", "sub-feas", "replay81", "Replay81.csproj"), "-c", "Release",
           f"-p:RepoRoot={args.checkout}", "-p:HasSubfeas=true", "-p:HasMaxThreads=true", "-p:HasTwoStage=true", "-o", harness_out,
           "-nologo", "-v", "q")
    assert r.returncode == 0, r.stdout[-600:]
    sh("dotnet", "build-server", "shutdown")   # no lingering compiler servers to be mistaken for competitors
    got = R.sha256(os.path.join(harness_out, "libft8.dll"))
    assert got == args.dll_pin, ("libft8.dll does not match the pin", got, args.dll_pin)
    comp = competitors()
    assert not comp, ("a competing process is running (WSJT-X closed, nothing else heavy)", comp)
    pre = {"utc": R.now(), "label": args.label, "spec": "section 5h Amendment 5", "parent_selection_sha256_lf": sel_sha,
           "t2p_list_sha256_lf": list_sha, "t2p_list_count": len(doc["runs"][RUN]["ALL"]), "p_list_sha256_lf": p_sha,
           "libft8_sha256": got, "dll_pin": args.dll_pin, "build_commit": args.commit,
           "harness_commit": sh("git", "rev-parse", "HEAD").stdout.strip(),
           "harness_dll_sha256": R.sha256(os.path.join(harness_out, "Replay81.dll")), "threads": THREADS, "mode": "two1",
           "wav_dir": wav_dir.replace(ART, "<artefacts>")}
    json.dump(pre, open(os.path.join(out, "preflight.json"), "w"), indent=1)
    R.env_snapshot("env_start.txt")
    return pre, list_path


def done_stamps(csv_path):
    s = set()
    if os.path.exists(csv_path):
        for line in open(csv_path, encoding="utf-8").read().splitlines()[1:]:
            p = line.split(",")
            if len(p) >= 5:
                s.add(p[2])
    return s


def repair_partial(files):
    """After a crash, drop abandon rows of a cycle that never reached its run-csv row."""
    done = done_stamps(files["run"])
    p = files["abandon"]
    if not os.path.exists(p):
        return
    lines = open(p, encoding="utf-8").read().splitlines()
    keep = [lines[0]] if lines else []
    for line in lines[1:]:
        cells = line.split(",")
        if cells and cells[0] in done:
            keep.append(line)
    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(keep) + ("\n" if keep else ""))


def pin_record(out, harness_out, args, when):
    got = R.sha256(os.path.join(harness_out, "libft8.dll"))
    with open(os.path.join(out, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": R.now(), "label": args.label, "when": when, "libft8_sha256": got, "pinned": args.dll_pin,
                             "match": got == args.dll_pin}) + "\n")
    return got == args.dll_pin


def run_arm(args, out, harness_out, list_path, sampler):
    files = {"run": os.path.join(out, "run.csv"), "abandon": os.path.join(out, "abandon.csv"), "log": os.path.join(out, "run.log")}
    n_expected = len(json.load(open(list_path))["runs"][RUN]["ALL"])
    ok_start = pin_record(out, harness_out, args, "start")
    R.log(f"{args.label} start: mode=two1 threads={THREADS} cycles={n_expected} dll_match={ok_start}")
    restarts = 0
    while True:
        repair_partial(files)
        cmd = ["dotnet", os.path.join(harness_out, "Replay81.dll"), "--selection", list_path, "--run", RUN, "--stratum", "ALL",
               "--wav-root", ART, "--out", files["run"], "--log", files["log"], "--mode", "two1", "--threads", THREADS,
               "--label", f"{args.commit}:t2p_{args.label}", "--abandon-out", files["abandon"]]
        t0 = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        sampler.pid = proc.pid
        while proc.poll() is None:
            R.status("RUN", label=args.label, cycles_done=len(done_stamps(files["run"])), cycles_expected=n_expected, restarts=restarts)
            time.sleep(60)
        rc = proc.returncode
        err = (proc.stderr.read() or "")[-300:]
        R.log(f"{args.label} harness rc={rc} in {time.time() - t0:.0f}s (restart {restarts}) stderr_tail={err.strip()[:120]!r}")
        with open(os.path.join(out, "process_exits.log"), "a") as fh:
            fh.write(f"{R.now()} {args.label} rc={rc} restart={restarts}\n")
        if rc == 0:
            break
        restarts += 1
        if restarts > MAX_RESTARTS:
            R.log(f"{args.label}: giving up after {MAX_RESTARTS} restarts (the rows script will show the missing cycles)")
            break
    ok_end = pin_record(out, harness_out, args, "end")
    R.log(f"{args.label} end: rows={len(done_stamps(files['run']))}/{n_expected} dll_match={ok_end}")
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", required=True)
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--dll-pin", required=True)
    ap.add_argument("--p-list", default=None)
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    out = os.path.join(ART, f"rr_2026-10-03_t2prime_{args.label}")
    harness_out = os.path.join(os.path.expanduser("~"), f"w-t2prime-out-{args.label}")
    R.OUT = out
    os.makedirs(out, exist_ok=True)
    R.LOGF = open(os.path.join(out, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # no sleep for the process lifetime
    R.log(f"orchestrator start (T2' replay, label={args.label})")
    pre, list_path = preflight(args, out, harness_out)
    if args.preflight_only:
        R.log(f"preflight-only: all assertions passed (harness commit {pre['harness_commit'][:8]}, list {pre['t2p_list_count']} cycles); nothing decoded")
        R.status("PREFLIGHT_ONLY", harness_commit=pre["harness_commit"])
        return 0
    sampler = Sampler(out)
    sampler.start()
    sampler.sample()
    try:
        rc = run_arm(args, out, harness_out, list_path, sampler)
    finally:
        sampler.stop.set()
        sampler.sample()
    R.env_snapshot("env_end.txt")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81' } | Select-Object Id | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(out, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", rc=rc, orphan_check="empty" if not orphans else "NON-EMPTY")
    R.log(f"orchestrator DONE rc={rc} orphan_check={'empty' if not orphans else 'NON-EMPTY'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
