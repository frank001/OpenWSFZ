#!/usr/bin/env python3
"""L1 driver (QA, #266). Counts only. usage: l1_drive.py <rundir> <port> <label> [--no-wait-skip]
Script: decodingEnabled false at start; save the device; wait 4 cycles; Start; 20 cycles; Stop, Start; 20 more.
Segments are cut by log LINE numbers taken immediately before each action."""
import json, sys, time, glob, os, urllib.request, datetime as dt
sys.path.insert(0, r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\framer-266")
import dup_stamp_counter as C
rundir, port, label = sys.argv[1], sys.argv[2], sys.argv[3]
base = f"http://127.0.0.1:{port}"
DEV_ID = "{0.0.1.00000000}.{ecb41d74-1aa5-43b1-ac89-b69e40510f00}"
DEV_NAME = "CABLE Output (VB-Audio Virtual Cable)"
def post(path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else b"", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r: return r.status
def get(path):
    with urllib.request.urlopen(base + path, timeout=20) as r: return json.loads(r.read())
def logfile(): return max(glob.glob(os.path.join(rundir, "logs", "openswfz-*.log")), key=os.path.getmtime)
def nlines(): 
    with open(logfile(), encoding="utf-8", errors="replace") as f: return sum(1 for _ in f)
def now(): return dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ")
def wait_cycles(n, extra=2.0): time.sleep(15 * n + extra)
marks = {}
print(label, "start", now(), "decodingEnabled", get("/api/v1/status").get("decodingEnabled"), flush=True)
marks["m0"] = nlines()
print("save device", post("/api/v1/config", {"audioDeviceId": DEV_ID, "audioDeviceFriendlyName": DEV_NAME}), now(), flush=True)
wait_cycles(4, 3.0)
marks["start1"] = nlines(); print("decode/start", post("/api/v1/decode/start"), now(), flush=True)
wait_cycles(20, 3.0)
marks["stop"] = nlines(); print("decode/stop", post("/api/v1/decode/stop"), now(), flush=True)
time.sleep(3)
marks["start2"] = nlines(); print("decode/start", post("/api/v1/decode/start"), now(), flush=True)
wait_cycles(20, 3.0)
marks["end"] = nlines(); print("end", now(), flush=True)
lf = logfile()
def seg(a, b):
    lines = open(lf, encoding="utf-8", errors="replace").read().splitlines()[marks[a]:marks[b]]
    tmp = os.path.join(rundir, f"_seg_{a}_{b}.tmp"); open(tmp, "w", encoding="utf-8").write("\n".join(lines))
    r = C.count(tmp); os.remove(tmp); return r
out = {"label": label, "log": os.path.basename(lf), "marks": marks}
for a, b in (("m0", "start1"), ("start1", "stop"), ("stop", "start2"), ("start2", "end")):
    r = seg(a, b); out[f"{a}->{b}"] = r
whole = C.count(lf); out["whole"] = {k: v for k, v in whole.items() if k != "decodes_per_cycle"}
json.dump(out, open(os.path.join(rundir, f"l1_result_{label}.json"), "w"), indent=1)
for k, v in out.items():
    if isinstance(v, dict) and "windows" in v:
        print(k, {kk: vv for kk, vv in v.items() if kk != "decodes_per_cycle"}, "decodes_per_cycle", v.get("decodes_per_cycle"))
print("whole", out["whole"])
