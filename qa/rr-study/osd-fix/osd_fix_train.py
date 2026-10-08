#!/usr/bin/env python
"""OSD-FIX TRAIN, interleaved round runner (amendment qa/rr-study/2026-10-08-1745-architect-to-qa-osd-fix-amendment-interleaved-train.md, arch/osd-fix e5569303).

7 rounds x 7 arms. Round r = chunk r through all 7 arms; arm order in round r = ARMS[(j + r - 1) mod 7], j = 0..6. Each arm x chunk is its OWN fresh Replay81 process
(one at a time): DLL pinned at start and end, --osd-sign-fix and --nhard read back, V2' probe after the warm-up (a miss stops that process with exit 5). A process that
fails validity is re-run ONCE unchanged; a second failure STOPS TRAIN and flags the Architect (status.json 'stopped'). Nothing is scored here.

DATA-BLIND BY CONSTRUCTION: this file never opens testb / outcomes / matched / run result files. It reads only each process's exit code, its DLL SHAs, its log's
'# readback' / '# probe' / residual-pass lines, and wall time. The per-round status holds validity and wall time ONLY (amendment section 5). A round boundary
stop is requested by creating <OUT>/STOP_AFTER_ROUND (checked between rounds; the Captain's decision, for time only).

Arms: REF = switch 0, nhard 40, OLD probe vectors (NHARD-REP probe_vectors.json); FIX(n) = switch 1, nhard n in {40, 30, 24, 50, 60, 0}, probe_vectors_fix.json.

  python qa/rr-study/osd-fix/osd_fix_train.py --rounds 1-7        # run (resumable: a completed arm x chunk is skipped)
  python qa/rr-study/osd-fix/osd_fix_train.py --plan              # print the schedule and exit
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import nhard_rep_n0_run as N0  # noqa: E402  (paths: ART, RUN, WAV_DIR, WS_ALLTXT, THREADS)
import replay81_run as R       # noqa: E402  (sha256)

REPO = N0.REPO
RESULTS = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-08-osd-fix")
CHUNK_DIR = os.path.join(RESULTS, "chunks")
OUT = os.path.join(N0.ART, "rr_2026-10-08_osd_fix_train")
HARNESS = r"D:\Projects\claude\_qa-scratch\osd-fix-harness"
DLL_PIN = "2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb"
REPLAY81_PIN = "c2ff19815438cde60c6c019ba0e1b6e53abcaf802b26c7192a89a221113e5843"
CHUNKS_MANIFEST_SHA = "3420070f75a39f7e5c5138d1ce00f36b61f1b00daa107f9d3720b756ecdfb029"
PROBE_OLD = os.path.join(REPO, "qa", "rr-study", "nhard-rep", "probe_vectors.json")
PROBE_OLD_SHA = "bc914e99513a57f09b93f146ad18423d9836333eba41958174468b29b31e27b8"
PROBE_FIX = os.path.join(HERE, "probe_vectors_fix.json")
PROBE_FIX_SHA = "e92b91c1156920099a23853ed00e40d81a45cf66fd3e090d859d668e365c2e7c"
N_ROUNDS = 7
ARMS = [("REF", 0, 40), ("FIX40", 1, 40), ("FIX30", 1, 30), ("FIX24", 1, 24), ("FIX50", 1, 50), ("FIX60", 1, 60), ("FIX0", 1, 0)]   # (name, osd_sign_fix, nhard)
MAX_ATTEMPTS = 2           # one run plus ONE re-run (amendment section 4)
V6_MAX_ABANDON = 0.05
STOP_FILE = os.path.join(OUT, "STOP_AFTER_ROUND")
SUBFEAS_RE = re.compile(r"Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(\w+) containedException=(\w+)")
READBACK_RE = re.compile(r"# readback (start|end) .*?nhard=(\d+) .*?osdSignFixSet=(\d) osdSignFixRead=(\d)")
PROBE_RE = re.compile(r"# probe (start|end) nhard=(\d+) met=(\w+)")


def arm_order(r):
    """Arm indices run in round r (1-based): (j + r - 1) mod 7 for j = 0..6."""
    return [(j + r - 1) % len(ARMS) for j in range(len(ARMS))]


def lf_sha(path):
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def process_valid(m):
    """Validity of ONE process from numeric facts only (V1 pin, V2 read-back + chunk SHA, V3 no fault, V2' probe, complete). -> (ok, [failed rows])."""
    bad = []
    if m["rc"] != 0:
        bad.append("rc" if m["rc"] != 5 else "V2prime_probe_miss")
    if not (m["dll_start"] == m["dll_end"] == DLL_PIN):
        bad.append("V1_pin")
    if m["replay81_sha"] != REPLAY81_PIN:
        bad.append("V1_harness_pin")
    if m["chunk_sha"] != m["chunk_sha_expected"]:
        bad.append("V2_chunk_sha")
    rb = m["readbacks"]
    if len(rb) < 2 or not all(x == (m["nhard"], m["sign"], m["sign"]) for x in rb):
        bad.append("V2_readback")
    pr = m["probes"]
    if len(pr) < 2 or not all(met and nh == m["nhard"] for (nh, met) in pr):
        bad.append("V2prime_probe")
    if m["contained"] > 0:
        bad.append("V3_contained_exception")
    if m["cycles_done"] != m["cycles_expected"]:
        bad.append("V3_incomplete")
    return (not bad), bad


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    line = f"{now()} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def write_status(state):
    state["updated"] = now()
    tmp = os.path.join(OUT, "status.json.tmp")
    json.dump(state, open(tmp, "w"), indent=1, sort_keys=True)
    os.replace(tmp, os.path.join(OUT, "status.json"))


class CpuSampler(threading.Thread):
    """System CPU % every 5 s while a process runs (median reported: the load record the ruling asks for). Numbers only."""
    def __init__(self):
        super().__init__(daemon=True)
        self.samples, self._stop = [], threading.Event()

    def run(self):
        import psutil
        psutil.cpu_percent(None)
        while not self._stop.wait(5.0):
            self.samples.append(psutil.cpu_percent(None))

    def stop(self):
        self._stop.set()
        self.join(timeout=10)
        return {"cpu_median": statistics.median(self.samples) if self.samples else None, "cpu_max": max(self.samples) if self.samples else None, "n": len(self.samples)}


def parse_log(path):
    rb, pr, contained, abandoned, passes = [], [], 0, 0, 0
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(path) else []
    first = next((i for i, ln in enumerate(lines) if "# readback start" in ln), 0)   # the warm-up cycle's residual line is before it
    for i, ln in enumerate(lines):
        m = READBACK_RE.search(ln)
        if m:
            rb.append((int(m.group(2)), int(m.group(3)), int(m.group(4)) if m.group(3) == m.group(4) else -1))
        m = PROBE_RE.search(ln)
        if m:
            pr.append((int(m.group(2)), m.group(3).lower() == "true"))
        m = SUBFEAS_RE.search(ln)
        if m and i >= first:
            passes += 1
            abandoned += m.group(3).lower() == "true"
            contained += m.group(4).lower() == "true"
        elif "WARN-TEMPLATE Sub-feas residual pass failed" in ln and i >= first:
            contained += 1
    return rb, pr, contained, abandoned, passes


def run_process(r, k, arm_i, attempt, manifest):
    name, sign, nhard = ARMS[arm_i]
    d = os.path.join(OUT, f"r{r}", name)
    os.makedirs(d, exist_ok=True)
    chunk = os.path.join(CHUNK_DIR, f"chunk_{k}.json")
    files = {x: os.path.join(d, f"{x}.{e}") for x, e in (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("log", "log"), ("probe", "csv"))}
    for p in files.values():
        if os.path.exists(p):
            os.remove(p)
    dll = os.path.join(HARNESS, "libft8.dll")
    start = R.sha256(dll)
    cmd = ["dotnet", os.path.join(HARNESS, "Replay81.dll"), "--selection", chunk, "--run", N0.RUN, "--stratum", "A", "--wav-root", N0.ART, "--wav-dir", N0.WAV_DIR,
           "--out", files["run"], "--log", files["log"], "--mode", "two1", "--threads", N0.THREADS, "--nhard", str(nhard), "--osd-sign-fix", str(sign),
           "--label", f"osdfix_3276573b:train_r{r}_{name}", "--outcomes", files["outcomes"], "--abandon-out", files["abandon"], "--wsjtx-alltxt", N0.WS_ALLTXT,
           "--testb-out", files["testb"], "--matched-out", files["matched"],
           "--probe-vectors", PROBE_FIX if sign == 1 else PROBE_OLD, "--probe-out", files["probe"]]
    cpu = CpuSampler()
    cpu.start()
    t0 = time.time()
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    wall = round(time.time() - t0)
    load = cpu.stop()
    end = R.sha256(dll)
    rb, pr, contained, abandoned, passes = parse_log(files["log"])
    cycles_done = max(0, sum(1 for _ in open(files["run"], encoding="utf-8")) - 1) if os.path.exists(files["run"]) else 0
    m = {"rc": rc, "dll_start": start, "dll_end": end, "replay81_sha": R.sha256(os.path.join(HARNESS, "Replay81.dll")), "chunk_sha": lf_sha(chunk),
         "chunk_sha_expected": manifest["chunks"][str(k)]["sha256_lf"], "readbacks": rb, "nhard": nhard, "sign": sign, "probes": pr, "contained": contained,
         "cycles_done": cycles_done, "cycles_expected": manifest["chunks"][str(k)]["cycles"]}
    ok, bad = process_valid(m)
    rec = {"round": r, "chunk": k, "arm": name, "attempt": attempt, "ok": ok, "failed_rows": bad, "rc": rc, "wall_s": wall, "residual_passes": passes, "abandoned": abandoned,
           "cycles": cycles_done, "load": load, "ended": now()}
    json.dump(rec, open(os.path.join(d, "process_ok.json" if ok else f"process_fail_{attempt}.json"), "w"), indent=1, sort_keys=True)
    return rec


def preflight(manifest_path):
    assert R.sha256(os.path.join(HARNESS, "libft8.dll")) == DLL_PIN, "harness libft8.dll differs from the pin"
    assert R.sha256(os.path.join(HARNESS, "Replay81.dll")) == REPLAY81_PIN, "Replay81.dll differs from the pin"
    assert lf_sha(manifest_path) == CHUNKS_MANIFEST_SHA, "chunk manifest differs from its pin"
    assert lf_sha(PROBE_OLD) == PROBE_OLD_SHA and lf_sha(PROBE_FIX) == PROBE_FIX_SHA, "probe vectors differ from their pins"
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    for k, v in manifest["chunks"].items():
        assert lf_sha(os.path.join(CHUNK_DIR, v["file"])) == v["sha256_lf"], f"chunk {k} differs from its SHA"
    st = subprocess.run(["git", "status", "--porcelain", "--", "qa/rr-study/osd-fix", "qa/rr-study/sub-feas/replay81", "qa/rr-study/results/2026-10-08-osd-fix/chunks"],
                        cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert st == "", f"harness/scripts not committed:\n{st}"
    return manifest


def prevent_sleep():
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    except Exception:
        pass


def plan_lines():
    rows = []
    for r in range(1, N_ROUNDS + 1):
        rows.append(f"round {r} (chunk {r}): " + " > ".join(ARMS[i][0] for i in arm_order(r)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", default="1-7")
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    if a.plan:
        print("\n".join(plan_lines()))
        return 0
    lo, hi = (int(x) for x in a.rounds.split("-")) if "-" in a.rounds else (int(a.rounds),) * 2
    os.makedirs(OUT, exist_ok=True)
    manifest = preflight(os.path.join(CHUNK_DIR, "chunks_manifest.json"))
    prevent_sleep()
    state_path = os.path.join(OUT, "status.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"rounds": {}, "stopped": None}
    state["stopped"] = None
    log(f"START rounds {lo}-{hi}; pid {os.getpid()}")
    for r in range(lo, hi + 1):
        if os.path.exists(STOP_FILE):
            log("STOP_AFTER_ROUND present: stopping at the round boundary")
            state["halted_at_boundary_before_round"] = r
            write_status(state)
            return 0
        rs = state["rounds"].setdefault(str(r), {"arms": {}, "complete": False})
        for arm_i in arm_order(r):
            name = ARMS[arm_i][0]
            d = os.path.join(OUT, f"r{r}", name, "process_ok.json")
            if os.path.exists(d):
                rs["arms"][name] = {k: v for k, v in json.load(open(d)).items() if k in ("ok", "wall_s", "attempt", "failed_rows", "abandoned", "residual_passes", "cycles", "load")}
                continue
            for attempt in range(1, MAX_ATTEMPTS + 1):
                log(f"round {r} arm {name} attempt {attempt}")
                rec = run_process(r, r, arm_i, attempt, manifest)
                rs["arms"][name] = {k: v for k, v in rec.items() if k in ("ok", "wall_s", "attempt", "failed_rows", "abandoned", "residual_passes", "cycles", "load")}
                write_status(state)
                log(f"round {r} arm {name} attempt {attempt}: ok={rec['ok']} {rec['failed_rows']} wall {rec['wall_s']} s")
                if rec["ok"]:
                    break
            else:
                state["stopped"] = {"round": r, "arm": name, "failed_rows": rec["failed_rows"], "note": "second failure: TRAIN stopped, flag the Architect; nothing scored"}
                write_status(state)
                log(f"STOPPED: round {r} arm {name} failed twice {rec['failed_rows']}")
                return 3
        rs["complete"] = all(x.get("ok") for x in rs["arms"].values()) and len(rs["arms"]) == len(ARMS)
        rs["wall_s_total"] = sum(x.get("wall_s", 0) for x in rs["arms"].values())
        write_status(state)
        log(f"ROUND {r} complete={rs['complete']} wall {rs['wall_s_total']} s (validity and wall time only)")
    log("DONE requested rounds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
