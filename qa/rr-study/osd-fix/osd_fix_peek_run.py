#!/usr/bin/env python
"""OSD-FIX PEEK-100, run step (spec qa/rr-study/2026-10-08-1715-architect-to-qa-osd-fix-peek-p100.md, branch arch/osd-fix 2b346822; Captain's go in QA's window).

FIX40 = the A-OFF part 2 command with ONE change, --osd-sign-fix 1: same DLL (SHA pinned), same aoff2_selection.json (the first 100 cycles of NHARD-REP SAMPLE, order,
warm-up), Replay81 two1, subtraction ON, threads 8, Test B, nhard 40. Outputs: artefacts/rr_2026-10-08_osd_fix/peek_fix40/. REF = artefacts/.../aoff2 (not re-run).
Descriptive only; labelled PEEK-100 wherever it appears. HK-037: every output is numeric.

  python qa/rr-study/osd-fix/osd_fix_peek_run.py --harness-out <dir> --new-sha <sha256>
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import nhard_rep_n0_run as N0  # noqa: E402
import replay81_run as R    # noqa: E402

ART_OUT = os.path.join(N0.ART, "rr_2026-10-08_osd_fix")
REF_DIR = os.path.join(ART_OUT, "aoff2")
OUT = os.path.join(ART_OUT, "peek_fix40")
SEL = os.path.join(REF_DIR, "aoff2_selection.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness-out", required=True)
    ap.add_argument("--new-sha", required=True)
    a = ap.parse_args()
    assert os.path.exists(SEL), "REF selection missing"
    os.makedirs(OUT, exist_ok=True)
    files = {k: os.path.join(OUT, f"{k}_V7.{ext}") for k, ext in (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("log", "log"))}
    assert not any(os.path.exists(p) for p in files.values()), "peek_fix40 outputs already exist; refusing to overwrite"
    dll = os.path.join(a.harness_out, "libft8.dll")
    start_sha = R.sha256(dll)
    assert start_sha == a.new_sha, ("harness libft8.dll differs from the pin", start_sha)
    cmd = ["dotnet", os.path.join(a.harness_out, "Replay81.dll"), "--selection", SEL, "--run", N0.RUN, "--stratum", "A", "--wav-root", N0.ART, "--wav-dir", N0.WAV_DIR,
           "--out", files["run"], "--log", files["log"], "--mode", "two1", "--threads", N0.THREADS, "--nhard", "40", "--osd-sign-fix", "1",
           "--label", "osdfix_3276573b:peek_fix40", "--outcomes", files["outcomes"], "--abandon-out", files["abandon"], "--wsjtx-alltxt", N0.WS_ALLTXT,
           "--testb-out", files["testb"], "--matched-out", files["matched"]]
    t0 = time.time()
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    end_sha = R.sha256(dll)
    meta = {"harness_rc": rc, "wall_s": round(time.time() - t0), "dll_start": start_sha, "dll_end": end_sha, "pin": a.new_sha, "cmd_osd_sign_fix": 1,
            "replay81_dll_sha256": R.sha256(os.path.join(a.harness_out, "Replay81.dll"))}
    json.dump(meta, open(os.path.join(OUT, "run_meta.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(meta, indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
