#!/usr/bin/env python
"""OSD-FIX TEST runner (spec section 5.3; ruling 2026-10-09 0615: n* = 24). Arms REF (switch 0, nhard 40: today) and FIX24 (switch 1, nhard 24).

TEST is the VERDICT replay, on cycles that chose nothing: night 20260930_1930, frozen selection `results/2026-10-09-osd-fix-test/selection.json`
(LF SHA pinned in test_osd_fix_test_select.py). It is run through the SAME committed machinery as TRAIN (osd_fix_train.run_process / process_valid / parse_log,
unchanged apart from the label prefix), pointed at TEST's own corpus, chunk files and output folder. Interleaved like TRAIN: the list is cut into chunks, chunk k
is one "round", and the two arms alternate their order each round (REF first in odd rounds, FIX24 first in even rounds); a fresh Replay81 process per arm x chunk,
the DLL pinned at the start and end of each, the switch and nhard read back, the V2' probe at the arm's own cap, one re-run on a validity failure, a second failure stops.

DATA-BLIND BY CONSTRUCTION (the TEST verdict is the thing blindness protects): this file never opens testb / outcomes / matched / run result files. It reads only each
process's exit code, DLL SHAs, the log's '# readback' / '# probe' / residual-pass lines, and wall time. NOTHING is scored here (osd_fix_test_rows.py does that, after both
arms are complete).

  python qa/rr-study/osd-fix/osd_fix_test.py chunks                 # write the chunk files + manifests for both lists (no decode)
  python qa/rr-study/osd-fix/osd_fix_test.py plan  [TEST|SAMPLE]    # print the schedule
  python qa/rr-study/osd-fix/osd_fix_test.py run   [TEST|SAMPLE]    # run (resumable: a completed arm x chunk is skipped); on the Captain's go only
  python qa/rr-study/osd-fix/osd_fix_test.py v5                     # the V5 noise leg at FIX(24): 200 noise WAVs, false decodes counted
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import osd_fix_train as T   # noqa: E402  (also puts sub-feas and nhard-rep on sys.path)
import nhard_rep_n0_run as N0   # noqa: E402
import replay81_run as R    # noqa: E402

REPO = T.REPO
RESULTS = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-09-osd-fix-test")
SELECTION = os.path.join(RESULTS, "selection.json")
SELECTION_SHA256 = "84b3d8849ea9da0ee989892a1b7de6ef2a2b3f8e68b0d47c4e477e6dc96f78b0"
RUN = "20260930_1930"
WAV_DIR = os.path.join(N0.ART, f"{RUN}_endurance_run-gathered", "owsfz", "wav")
WS_ALLTXT = os.path.join(N0.ART, f"{RUN}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
OUT = os.path.join(N0.ART, "rr_2026-10-09_osd_fix_test")
ARMS = [("REF", 0, 40), ("FIX24", 1, 24)]
CHUNK_SIZE = 215                       # 860 = 4 x 215 (TEST); 430 = 2 x 215 (SAMPLE)
LISTS = {"TEST": 860, "SAMPLE": 430}
# LF SHA-256 of each list's chunks_manifest.json (pinned after `chunks` ran, BEFORE any decode)
MANIFEST_SHA = {"TEST": "e3835bd7f9b79868eadada902e46d0f6b4021f1b3cf850b78487059e3808b704", "SAMPLE": "d9b05d72e4f1f45f8a20364118dbf3aa4c8608d691bbb05b1e6a682a300893f8"}
STAGE = "test"
# V5 (noise leg): NHARD-REP's 200 noise WAVs, located and pinned
NOISE_SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
NOISE_SELECTION_SHA = "3cf04abb6b653bac5df70ce587ad48bd5d3bef7205eee6c040f8e2951cb13872"
NOISE_DIR = os.path.join(N0.ART, "rr_2026-10-06_nhard_rep", "noise")
NOISE_RUN, NOISE_STRATUM = "NOISE", "ALL"


def lf_bytes(path):
    return open(path, "rb").read().replace(b"\r\n", b"\n")


def lf_sha(path):
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def chunk_dir(listname):
    return os.path.join(RESULTS, f"chunks_{listname.lower()}")


def cut(cycles, warmup, size=CHUNK_SIZE):
    """-> list of {k, warmup, cycles}; pure (tested). Warm-up: chunk 1 = the selection's own; chunk k > 1 = the last cycle of chunk k-1 (never scored as a warm-up)."""
    assert len(cycles) % size == 0 and len(set(cycles)) == len(cycles)
    out = []
    for i in range(0, len(cycles), size):
        c = cycles[i:i + size]
        out.append({"k": i // size + 1, "cycles": c, "warmup": warmup if i == 0 else out[-1]["cycles"][-1]})
    return out


def render(obj):
    return (json.dumps(obj, sort_keys=True, indent=1) + "\n").encode("utf-8")


def build_chunks(listname):
    assert lf_sha(SELECTION) == SELECTION_SHA256, "TEST selection.json differs from its pin"
    sel = json.loads(lf_bytes(SELECTION))
    cycles = sel[listname]
    assert len(cycles) == LISTS[listname]
    chunks = cut(cycles, sel["warmup"])
    files, manifest = {}, {"selection_sha256_lf": SELECTION_SHA256, "run": RUN, "list": listname, "sizes": [len(c["cycles"]) for c in chunks], "chunks": {}}
    for c in chunks:
        name = f"chunk_{c['k']}.json"
        data = render({"note": f"OSD-FIX TEST {listname} chunk {c['k']} of {len(chunks)}", "run": RUN, "runs": {RUN: {"warmup": c["warmup"], "A": c["cycles"]}}})
        files[name] = data
        manifest["chunks"][str(c["k"])] = {"file": name, "sha256_lf": hashlib.sha256(data).hexdigest(), "cycles": len(c["cycles"]), "warmup": c["warmup"]}
    return files, render(manifest)


def write_chunks():
    for listname in LISTS:
        files, manifest = build_chunks(listname)
        d = chunk_dir(listname)
        os.makedirs(d, exist_ok=True)
        for name, data in files.items():
            with open(os.path.join(d, name), "wb") as fh:
                fh.write(data)
        with open(os.path.join(d, "chunks_manifest.json"), "wb") as fh:
            fh.write(manifest)
        print(listname, "manifest_sha256_lf", hashlib.sha256(manifest).hexdigest(), json.loads(manifest)["sizes"])


def configure(listname):
    """Point the committed TRAIN machinery at TEST. Nothing here changes how a process is run or judged."""
    assert listname in LISTS and MANIFEST_SHA[listname], "the chunk manifest SHA is not pinned yet"
    T.OUT = OUT
    T.STOP_FILE = os.path.join(OUT, "STOP_AFTER_ROUND")
    T.CHUNK_DIR = chunk_dir(listname)
    T.CHUNKS_MANIFEST_SHA = MANIFEST_SHA[listname]
    T.ARMS = ARMS
    T.N_ROUNDS = len(json.loads(lf_bytes(os.path.join(T.CHUNK_DIR, "chunks_manifest.json")))["chunks"])
    T.LABEL_STAGE = STAGE
    N0.RUN, N0.WAV_DIR, N0.WS_ALLTXT = RUN, WAV_DIR, WS_ALLTXT
    assert os.path.isdir(WAV_DIR) and os.path.isfile(WS_ALLTXT), "TEST corpus paths missing"


def v5():
    """Noise leg at FIX(24): the 200 NHARD-REP noise WAVs through Replay81 two1, switch 1, nhard 24. Prints counts only."""
    assert lf_sha(NOISE_SELECTION) == NOISE_SELECTION_SHA, "NHARD-REP selection.json differs from its pin"
    sel = json.loads(lf_bytes(NOISE_SELECTION))
    sha = sel["noise"]["wav_sha256"]
    stamps = sel["runs"][NOISE_RUN][NOISE_STRATUM]
    assert len(stamps) == 200
    for s in [sel["runs"][NOISE_RUN]["warmup"]] + stamps:
        p = os.path.join(NOISE_DIR, s + ".wav")
        assert os.path.isfile(p) and hashlib.sha256(open(p, "rb").read()).hexdigest() == sha[s], f"noise WAV {s} differs from its pinned SHA-256"
    out = os.path.join(OUT, "v5")
    os.makedirs(out, exist_ok=True)
    f = {k: os.path.join(out, f"{k}.{e}") for k, e in (("run", "csv"), ("log", "log"), ("outcomes", "csv"), ("abandon", "csv"), ("probe", "csv"))}
    for p in f.values():
        if os.path.exists(p):
            os.remove(p)
    dll = os.path.join(T.HARNESS, "libft8.dll")
    start = R.sha256(dll)
    cmd = ["dotnet", os.path.join(T.HARNESS, "Replay81.dll"), "--selection", NOISE_SELECTION, "--run", NOISE_RUN, "--stratum", NOISE_STRATUM, "--wav-root", N0.ART,
           "--wav-dir", NOISE_DIR, "--out", f["run"], "--log", f["log"], "--mode", "two1", "--threads", N0.THREADS, "--nhard", "24", "--osd-sign-fix", "1",
           "--label", "osdfix_3276573b:test_v5_FIX24", "--outcomes", f["outcomes"], "--abandon-out", f["abandon"]]
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    end = R.sha256(dll)
    rb, pr, contained, abandoned, passes = T.parse_log(f["log"])
    rows = max(0, sum(1 for _ in open(f["run"], encoding="utf-8")) - 1) if os.path.exists(f["run"]) else 0
    res = {"rc": rc, "dll_start": start, "dll_end": end, "pin_ok": start == end == T.DLL_PIN, "readbacks": rb, "contained": contained, "abandoned": abandoned,
           "cycles_run": rows, "run_file": f["run"], "note": "false decodes are counted by the verdict script from the run file; this process records only validity"}
    json.dump(res, open(os.path.join(out, "v5_process.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if rc == 0 and res["pin_ok"] else 3


def preflight_git():
    st = subprocess.run(["git", "status", "--porcelain", "--", "qa/rr-study/osd-fix", "qa/rr-study/sub-feas/replay81", "qa/rr-study/results/2026-10-09-osd-fix-test"],
                        cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert st == "", f"TEST scripts/selection/chunks not committed:\n{st}"


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    listname = argv[2] if len(argv) > 2 else "TEST"
    if cmd == "chunks":
        write_chunks()
        return 0
    if cmd == "plan":
        configure(listname)
        print("\n".join(f"round {r} (chunk {r}): " + " > ".join(T.ARMS[i][0] for i in T.arm_order(r)) for r in range(1, T.N_ROUNDS + 1)))
        return 0
    if cmd == "run":
        configure(listname)
        preflight_git()
        sys.argv = [sys.argv[0], "--rounds", f"1-{T.N_ROUNDS}"]
        return T.main()
    if cmd == "v5":
        configure("TEST")
        preflight_git()
        return v5()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
