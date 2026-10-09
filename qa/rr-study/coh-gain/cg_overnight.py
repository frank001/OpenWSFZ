#!/usr/bin/env python
"""COH-GAIN Amendment 5 (QA, under the Captain's overnight authorisation): the unattended orchestrator. Detached, resumable, deadline-guarded.

For each FRESH residue in CG.FRESH_RESIDUES (1, 2, 4, 6, 8, 9), in order:
  1. its own batch-labelled V4' replay            (cg_v4p.py --residue R, ~36 min)  -> a manifest in the tracked results folder
  2. the manifest is COMMITTED BY PATH (before the extraction, as Amendment 4 requires)
  3. the extraction, then its V5 repeat           (cg_run.py --mode main / v5 --residue R, ~12 min)
After the samples: the optional OSD-OFF confirmation (nhard_rep_osdoff_b.py, only if it exists and the budget allows), then the pooled analysis (cg_rows.py --multi).

Every step is IDEMPOTENT (a done marker per step; the extraction resumes by cycle). A step is started only if it can finish before DEADLINE (04:45Z = 06:45 local; the Captain's end is
07:00 local = 05:00Z). A failed step is logged and the run CONTINUES with the next sample (a sample that did not run is excluded as 'not run' by the analysis, never counted as a pass).
A 60-second heartbeat keeps status.json fresh for the watchdog. HK-037: nothing here reads message text.
"""
import ctypes
import datetime
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import cg_common as CG  # noqa: E402
import cg_select as SEL  # noqa: E402
import replay81_run as R  # noqa: E402

REPO = CG.REPO_ROOT
ART = SEL.ART
OUT = os.path.join(ART, "rr_2026-10-06_coh_gain_overnight")
RESULTS = SEL.OUT_DIR
BRANCH = "qa/coh-gain"
DEADLINE = datetime.datetime(2026, 10, 7, 4, 45, 0, tzinfo=datetime.timezone.utc)
EST_REPLAY_S = 36 * 60
EST_EXTRACT_S = 12 * 60
EST_OSDOFF_S = 75 * 60
PY = sys.executable
_state = {"step": "init", "residue": None, "t": time.time()}


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def log(msg):
    R.log(msg)


def heartbeat():
    while True:
        try:
            R.status("RUN", step=_state["step"], residue=_state["residue"], step_started_s_ago=round(time.time() - _state["t"]), deadline=DEADLINE.strftime("%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            pass
        time.sleep(60)


def sh(*a, cwd=REPO):
    return subprocess.run(list(a), cwd=cwd, capture_output=True, text=True)


def room(seconds):
    """True iff a step of this length can finish before the deadline."""
    return now() + datetime.timedelta(seconds=seconds) <= DEADLINE


def marker(name):
    return os.path.join(OUT, "steps", name + ".done")


def done(name):
    return os.path.exists(marker(name))


def mark(name, **kw):
    os.makedirs(os.path.join(OUT, "steps"), exist_ok=True)
    json.dump({"utc": now().strftime("%Y-%m-%dT%H:%M:%SZ"), **kw}, open(marker(name), "w"))


def run_step(name, residue, cmd, est_s):
    _state.update(step=name, residue=residue, t=time.time())
    if done(name):
        log(f"{name}: already done, skipping")
        return 0
    if not room(est_s):
        log(f"{name}: SKIPPED, not enough time before the deadline ({DEADLINE:%H:%MZ})")
        return None
    log(f"{name}: start")
    t0 = time.time()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    tail = (p.stdout or "")[-400:].replace("\n", " | ")
    log(f"{name}: rc={p.returncode} in {time.time() - t0:.0f}s :: {tail[-250:]}")
    with open(os.path.join(OUT, "steps.log"), "a", encoding="utf-8") as fh:
        fh.write(f"{now():%Y-%m-%dT%H:%M:%SZ} {name} rc={p.returncode} wall_s={time.time() - t0:.0f}\n{(p.stdout or '')[-1500:]}\n{(p.stderr or '')[-800:]}\n")
    if p.returncode == 0:
        mark(name, rc=0, wall_s=round(time.time() - t0))
    return p.returncode


def commit_manifest(residue):
    """Commit the V4' manifest BY PATH, on the expected branch, retrying on an index lock."""
    path = os.path.join(RESULTS, f"v4p_{CG.sample_tag(residue)}_replay_manifest.json")
    if not os.path.exists(path):
        return False
    assert sh("git", "branch", "--show-current").stdout.strip() == BRANCH, "wrong branch for the unattended commit"
    rel = os.path.relpath(path, REPO).replace("\\", "/")
    for attempt in range(6):
        a = sh("git", "add", "--", rel)
        if a.returncode == 0:
            c = sh("git", "commit", "-q", "-m", f"qa(coh-gain): sample r{residue} V4' replay manifest, committed BEFORE its extraction (Amendment 5, unattended)\n\n"
                   "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>", "--", rel)
            if c.returncode == 0 or "nothing to commit" in (c.stdout + c.stderr):
                return True
        time.sleep(5 + attempt * 5)
    return False


def main():
    os.makedirs(OUT, exist_ok=True)
    R.OUT = OUT
    R.LOGF = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    log(f"overnight orchestrator start; deadline {DEADLINE:%Y-%m-%dT%H:%M:%SZ}")
    assert sh("git", "branch", "--show-current").stdout.strip() == BRANCH
    threading.Thread(target=heartbeat, daemon=True).start()
    results = {}
    for res in CG.FRESH_RESIDUES:
        tag = CG.sample_tag(res)
        out_dir = os.path.join(ART, f"rr_2026-10-06_coh_gain_{tag}")
        rc = run_step(f"v4p_r{res}", res, [PY, os.path.join(HERE, "cg_v4p.py"), "--residue", str(res)], EST_REPLAY_S)
        results[f"v4p_r{res}"] = rc
        if rc != 0:
            log(f"sample r{res}: no V4' replay (rc={rc}); its extraction is skipped and the analysis will exclude it as 'not run'")
            continue
        if not commit_manifest(res):
            log(f"sample r{res}: MANIFEST COMMIT FAILED; extraction skipped (Amendment 4 order: manifest before extraction)")
            results[f"commit_r{res}"] = False
            continue
        rc = run_step(f"main_r{res}", res, [PY, os.path.join(HERE, "cg_run.py"), "--mode", "main", "--residue", str(res), "--out", out_dir, "--workers", "4"], EST_EXTRACT_S)
        results[f"main_r{res}"] = rc
        if rc == 0:
            results[f"v5_r{res}"] = run_step(f"v5_r{res}", res, [PY, os.path.join(HERE, "cg_run.py"), "--mode", "v5", "--residue", str(res), "--out", out_dir], 5 * 60)
    osd = os.path.join(HERE, "..", "nhard-rep", "nhard_rep_osdoff_b.py")
    if os.path.exists(osd):
        results["osdoff_b"] = run_step("osdoff_b", None, [PY, osd], EST_OSDOFF_S)
    _state.update(step="analysis", residue=None, t=time.time())
    p = subprocess.run([PY, os.path.join(HERE, "cg_rows.py"), "--multi"], cwd=REPO, capture_output=True, text=True)
    log(f"analysis rc={p.returncode} :: {(p.stdout or '')[-500:].replace(chr(10), ' ')}")
    orphans = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Process | Where-Object { $_.ProcessName -match 'Replay81' } | Select-Object Id | Out-String)"],
                             capture_output=True, text=True).stdout.strip()
    open(os.path.join(OUT, "orphan_check.txt"), "w").write(orphans + "\n")
    R.status("DONE", results=results, orphan_check="empty" if not orphans else "NON-EMPTY", finished=now().strftime("%Y-%m-%dT%H:%M:%SZ"))
    log(f"overnight DONE {results} orphans={'empty' if not orphans else 'NON-EMPTY'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
