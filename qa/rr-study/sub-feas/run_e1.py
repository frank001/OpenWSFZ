#!/usr/bin/env python
"""SUB-FEAS speed-redesign E1 (real corpus): fit hashes through the base DLL vs the candidate DLL.

Spec: qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md section 2 (E1) + Amendment 1.
Selection: e1_selection.json (frozen, SHA asserted). Predicate: PASS iff 100 % of rows identical
(rc, sha256(out_shat), pass-0 count, pass-0 outcome hash), at the thread count(s) below.

Two probe builds are used ON PURPOSE: the probe links the CURRENT managed interop, which rejects a DLL of a
different shim version. So the base DLL (shim 20260055) is probed with the probe as of the pre-change commit
348e067e (the one that recorded the developer's golden), and the candidate DLL (shim 20260056) with the probe
at the candidate commit. Both write the same CSV schema.

NFR-021 / HK-037: reads WAV audio and stamps only; the probe emits rc values, counts and hashes, never text.
Outputs go to the gitignored artefacts dir; the paths are asserted untracked BEFORE anything runs.
"""
import csv
import hashlib
import json
import os
import subprocess
import sys

QA = r"D:\Projects\claude\OpenWSFZ\worktrees\qa"
ART = os.path.join(QA, "artefacts")
OUT = os.path.join(ART, "sub_feas_speed_e1")
SELECTION = os.path.join(QA, r"qa\rr-study\results\2026-09-30-sub-feas-speed-e1\e1_selection.json")
SELECTION_SHA256 = "f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2"

BASE_DLL_SHA = "5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5"
CAND_DLL_SHA = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
BASE_DLL_COMMIT = "ab95bea1"          # feat/sub-feas-native-subtraction: shim 20260055, code 2b39cf18
CAND_DLL_COMMIT = "ca0bcd9b"          # feat/sub-feas-speed-redesign: shim 20260056
PROBE_BASE_COMMIT = "348e067e"        # probe as of the golden recording (pre-change interop)
PROBE_CAND_COMMIT = "ca0bcd9b"
DLL_PATH_IN_REPO = "src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll"

W_BASE = r"C:\Users\Frank\w-e1-base"
W_CAND = r"C:\Users\Frank\w-speed-review"      # detached at ca0bcd9b (already exists from the code review)
RUNS = [("base", 14), ("cand", 14), ("cand", 4)]   # reference first; bit-identity must not depend on thread count
THREADS = sorted({t for _, t in RUNS})
GRID = 0                                       # the synthetic grid is the Developer's; this run is the real corpus

WAV_DIR = {
    "20260922_2056": os.path.join(ART, "20260922_2056_endurance_run-gathered", "owsfz", "wav"),
    "20260923_1730": os.path.join(ART, "20260923_1730_endurance_run-gathered", "owsfz", "wav"),
    "20260925_2010": os.path.join(ART, "20260925_2010_endurance_run-gathered", "owsfz", "wav"),
}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git(*args, cwd=QA, binary=False):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def main():
    os.makedirs(OUT, exist_ok=True)
    # Output paths must be untracked (privacy discipline: the artefacts dir is gitignored).
    tracked = git("ls-files", "--", "artefacts").strip()
    assert tracked == "", "artefacts/ has tracked files"

    sel_bytes = open(SELECTION, "rb").read()
    assert sha256_bytes(sel_bytes.replace(b"\r\n", b"\n")) == SELECTION_SHA256 or \
        sha256_bytes(sel_bytes) == SELECTION_SHA256, "e1_selection.json changed"
    sel = json.loads(sel_bytes.decode("utf-8"))
    assert sel["counts"] == {"every9": 101, "pilot": 60, "total": 161}, sel["counts"]

    wavs = []
    for c in sel["cycles"]:
        p = os.path.join(WAV_DIR[c["run"]], c["stamp"] + ".wav")
        assert os.path.isfile(p), "missing wav for a selected cycle"
        wavs.append(p)
    assert len(wavs) == 161

    # DLLs from committed blobs (independent of any developer-side copy), pinned by SHA-256.
    dlls = {}
    for tag, commit, want in (("base", BASE_DLL_COMMIT, BASE_DLL_SHA), ("cand", CAND_DLL_COMMIT, CAND_DLL_SHA)):
        blob = git("show", f"{commit}:{DLL_PATH_IN_REPO}", binary=True)
        got = sha256_bytes(blob)
        print(f"{tag} dll actual={got} pinned={want} match={got == want}")
        assert got == want, f"{tag} dll pin mismatch"
        path = os.path.join(OUT, f"libft8.{tag}.dll")
        open(path, "wb").write(blob)
        dlls[tag] = path

    # Two probe builds.
    if not os.path.isdir(W_BASE):
        git("worktree", "add", "--detach", W_BASE, PROBE_BASE_COMMIT)
    assert git("rev-parse", "HEAD", cwd=W_BASE).strip().startswith(PROBE_BASE_COMMIT)
    assert git("rev-parse", "HEAD", cwd=W_CAND).strip().startswith(PROBE_CAND_COMMIT)
    for w in (W_BASE, W_CAND):
        subprocess.run(["dotnet", "build", os.path.join(w, "tests", "Ft8.FitProbe"), "-c", "Release", "-nologo", "-v", "q"],
                       check=True)

    results = {}
    for tag, t in RUNS:
        w = W_BASE if tag == "base" else W_CAND
        if True:
            out = os.path.join(OUT, f"e1_{tag}_t{t}.csv")
            cmd = ["dotnet", "run", "--no-build", "-c", "Release", "--project", os.path.join(w, "tests", "Ft8.FitProbe"),
                   "--", "e1", "--dll", dlls[tag], "--out", out, "--threads", str(t), "--grid", str(GRID)]
            for p in wavs:
                cmd += ["--wav", p]
            print("RUN", tag, "threads", t, flush=True)
            r = subprocess.run(cmd, capture_output=True, text=True)
            open(os.path.join(OUT, f"e1_{tag}_t{t}.stderr.txt"), "w").write(r.stderr)
            assert r.returncode == 0, f"probe {tag} t{t} rc={r.returncode}"
            results[(tag, t)] = out

    def rows(path):
        with open(path, newline="") as fh:
            return list(csv.reader(fh))

    summary = {"selection_sha256": SELECTION_SHA256, "base_dll": BASE_DLL_SHA, "cand_dll": CAND_DLL_SHA,
               "cycles": len(wavs), "comparisons": []}
    ref = rows(results[RUNS[0]])
    for (tag, t) in RUNS:
        if True:
            cur = rows(results[(tag, t)])
            same_len = len(cur) == len(ref)
            diff = [i for i, (a, b) in enumerate(zip(ref, cur)) if a != b] if same_len else None
            summary["comparisons"].append({
                "vs": f"{RUNS[0][0]}_t{RUNS[0][1]}", "run": f"{tag}_t{t}", "rows": len(cur), "ref_rows": len(ref),
                "identical": same_len and not diff, "n_diff_rows": None if diff is None else len(diff),
                "first_diff_row_labels": None if not diff else [",".join(cur[i][:3]) for i in diff[:20]]})
    # Row-kind breakdown of the reference (integers only).
    kinds = {}
    for r in ref[1:]:
        kinds.setdefault((r[0], r[3]), 0)
        kinds[(r[0], r[3])] += 1
    summary["ref_kind_rc_counts"] = {f"{k[0]}:rc{k[1]}": v for k, v in sorted(kinds.items())}
    summary["e1_pass"] = all(c["identical"] for c in summary["comparisons"])
    with open(os.path.join(OUT, "e1_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps(summary, indent=1))
    return 0 if summary["e1_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
