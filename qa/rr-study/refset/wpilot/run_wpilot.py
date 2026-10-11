"""REFERENCE-SET W pilot driver (QA). Protocol: PROTOCOL.md in this folder (frozen before the first real decode).

Runs the 12 blocks x 5 W cells through WPilot.exe, two cells at a time, resumable (a finished cell is skipped).
All run files live in D:\\Projects\\claude\\_qa-scratch\\wpilot (outside git). Aggregates only; no message text anywhere.

    python -s -E run_wpilot.py            # whole run
    python -s -E run_wpilot.py --check    # P-V0 / P-V3 only (pins, self-test), decode nothing
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

SCRATCH = r"D:\Projects\claude\_qa-scratch\wpilot"
BIN = os.path.join(SCRATCH, "bin", "WPilot.exe")
BIN_DLL = os.path.join(SCRATCH, "bin", "libft8.dll")
PIN_SHA = "a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts\20261009_1752_endurance_run-gathered"
WAV_REL = "20261009_1752_endurance_run-gathered/owsfz/wav"
ALL_TXT = os.path.join(ART, "owsfz", "ALL.TXT")
LIVE_SHA = "382b23b204173cdb185e4ce6eaab65c23e1ed0c8bd0aa3c1a9166f92d91b3653"
INV = r"D:\Projects\claude\_qa-scratch\refset-inventory"
JIT = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\tests\OpenWSFZ.Ft8.Tests\Fixtures\synth-qso-01.wav"
WS = [40, 16, 8, 4, 0]
SPAN, SCORED_START, L = 72, 40, 32
PARALLEL = 2
NHARD, SIGNFIX, THREADS = 24, 1, 8
CELLS = os.path.join(SCRATCH, "cells")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stamps(first):
    t0 = dt.datetime.strptime(first, "%y%m%d_%H%M%S")
    return [(t0 + dt.timedelta(seconds=15 * i)).strftime("%y%m%d_%H%M%S") for i in range(SPAN)]


def preflight(blocks):
    out = {"utc": now()}
    assert sha(BIN_DLL) == PIN_SHA, "harness DLL is not the pinned a14fe354"
    out["dll_sha256"] = PIN_SHA
    assert sha(ALL_TXT) == LIVE_SHA, "live ALL.TXT changed"
    out["live_all_txt_sha256"] = LIVE_SHA
    r = subprocess.run([BIN, "--selftest", "true"], capture_output=True, text=True)
    assert r.returncode == 0 and "SELFTEST OK" in r.stdout, "self-test failed"
    out["selftest"] = "OK"
    inv = {}
    for l in open(os.path.join(INV, "wavs.jsonl"), encoding="utf8"):
        w = json.loads(l)
        inv[w["path"].replace("\\", "/")] = w["sha"]
    n = 0
    for b in blocks:
        for s in stamps(b["first_stamp"]):
            rel = f"{WAV_REL}/{s}.wav"
            assert rel in inv, "WAV not in the inventory: " + s
            assert sha(os.path.join(r"D:\Projects\claude\OpenWSFZ\artefacts", rel.replace("/", os.sep))) == inv[rel], "WAV hash differs: " + s
            n += 1
    out["wavs_checked"] = n
    out["blocks"] = len(blocks)
    return out


def run_cell(job):
    bi, b, w = job
    name = f"cell_b{bi:02d}_w{w:02d}"
    outj = os.path.join(CELLS, name + ".json")
    if os.path.exists(outj):
        return name, "skipped", 0.0
    t = time.time()
    cmd = [BIN, "--ows-alltxt", ALL_TXT, "--wav-dir", os.path.join(ART, "owsfz", "wav"), "--first-stamp", b["first_stamp"],
           "--w", str(w), "--l", str(L), "--span", str(SPAN), "--scored-start", str(SCORED_START), "--nhard", str(NHARD),
           "--osd-sign-fix", str(SIGNFIX), "--threads", str(THREADS), "--jit-wav", JIT, "--out-json", outj + ".part",
           "--log", os.path.join(SCRATCH, "logs", name + ".log"), "--label", name]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return name, "FAILED rc=%d %s" % (p.returncode, p.stderr.strip()[:160]), time.time() - t
    os.replace(outj + ".part", outj)
    return name, "done", time.time() - t


def main():
    os.makedirs(CELLS, exist_ok=True)
    os.makedirs(os.path.join(SCRATCH, "logs"), exist_ok=True)
    blocks = json.load(open(os.path.join(INV, "wpilot_blocks.json")))["blocks"]
    pre = preflight(blocks)
    json.dump(pre, open(os.path.join(SCRATCH, "preflight.json"), "w"), indent=1)
    print("PREFLIGHT OK", json.dumps(pre), flush=True)
    if "--check" in sys.argv:
        return 0
    jobs = [(bi, b, w) for bi, b in enumerate(blocks) for w in WS]
    status_path = os.path.join(SCRATCH, "status.json")
    done = 0
    t0 = time.time()
    with open(os.path.join(SCRATCH, "pins.jsonl"), "a") as pins:
        pins.write(json.dumps({"utc": now(), "event": "start", "dll": sha(BIN_DLL)}) + "\n")
    with ThreadPoolExecutor(PARALLEL) as ex:
        for name, state, secs in ex.map(run_cell, jobs):
            done += 1
            print(now(), name, state, round(secs), "s", flush=True)
            json.dump({"utc": now(), "cells_done": done, "cells_total": len(jobs), "elapsed_s": round(time.time() - t0), "last": name, "state": state},
                      open(status_path, "w"))
            if state.startswith("FAILED"):
                print("STOP: a cell failed; the pool drains and the run ends non-zero", flush=True)
    end = {"utc": now(), "event": "end", "dll": sha(BIN_DLL), "elapsed_s": round(time.time() - t0)}
    assert end["dll"] == PIN_SHA, "DLL changed during the run"
    with open(os.path.join(SCRATCH, "pins.jsonl"), "a") as pins:
        pins.write(json.dumps(end) + "\n")
    json.dump(end, open(os.path.join(SCRATCH, "run_end.json"), "w"))
    print("RUN END", json.dumps(end), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
