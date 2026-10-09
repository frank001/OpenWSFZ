#!/usr/bin/env python
"""OSD-FIX A-OFF, part 2 (spec section 5.1): the Replay81 pipeline with the switch at 0 vs the NHARD-REP N40 arm on file. A V7-style pairing control.

The N40 arm on file (artefacts/rr_2026-10-06_nhard_rep, build be3cc5ac, shim 20260058, DLL SHA 2fa6d993...f365; native == origin/main 81f74ede) is paired with the
first 100 cycles of the same SAMPLE (residue 0 of the NHARD-REP list) decoded by the NEW build (feat/osd-sign-fix, shim 20260060, DLL SHA pinned below) with
--osd-sign-fix 0, --nhard 40, flag ON, threads 8, mode two1, Test B rule, the same warm-up and the same cycle ORDER (so the process-global hash table has the same
history; this is why SAMPLE's first 100 are used and not the first 100 of TRAIN, whose interleaved order would change that history. SAMPLE is residue 0 of TRAIN).
PASS iff 0 of the 100 cycles differ: a cycle differs if its MATCHED SET (WSJT-X line indices) or its batch-1 / batch-2 decode MULTISET (numeric freq, dt, snr) differs.
ON FAIL the N40 arm is re-run in full on the new binary (spec 5.1); this script only reports.
HK-037: ALL.TXT is read only inside the harness' matching function; every output is numeric.

  python qa/rr-study/osd-fix/osd_fix_aoff2.py --harness-out <dir with Replay81.dll + libft8.dll> --new-sha <sha256>
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
import nhard_rep_v7 as V7   # noqa: E402  (compare(), first_stamps(), constants)
import nhard_rep_n0_run as N0  # noqa: E402
import replay81_run as R    # noqa: E402

REPO = N0.REPO
OUT = os.path.join(N0.ART, "rr_2026-10-08_osd_fix", "aoff2")
RESULT = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-08-osd-fix", "aoff_part2.json")
N40_DIR = os.path.join(N0.ART, "rr_2026-10-06_nhard_rep")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness-out", required=True)
    ap.add_argument("--new-sha", required=True)
    a = ap.parse_args()
    stamps, warmup = V7.first_stamps()
    assert len(stamps) == V7.N_CYCLES
    os.makedirs(OUT, exist_ok=True)
    sel_path = os.path.join(OUT, "aoff2_selection.json")
    json.dump({"note": "OSD-FIX A-OFF part 2: the first 100 cycles of NHARD-REP SAMPLE", "run": N0.RUN, "runs": {N0.RUN: {"warmup": warmup, "A": stamps}}},
              open(sel_path, "w"), indent=1, sort_keys=True)
    files = {k: os.path.join(OUT, f"{k}_V7.{ext}") for k, ext in (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("log", "log"))}
    for p in files.values():
        if os.path.exists(p):
            os.remove(p)
    dll = os.path.join(a.harness_out, "libft8.dll")
    start_sha = R.sha256(dll)
    assert start_sha == a.new_sha, ("harness libft8.dll differs from the pin", start_sha)
    cmd = ["dotnet", os.path.join(a.harness_out, "Replay81.dll"), "--selection", sel_path, "--run", N0.RUN, "--stratum", "A", "--wav-root", N0.ART, "--wav-dir", N0.WAV_DIR,
           "--out", files["run"], "--log", files["log"], "--mode", "two1", "--threads", N0.THREADS, "--nhard", "40", "--osd-sign-fix", "0",
           "--label", "osdfix_3276573b:aoff2", "--outcomes", files["outcomes"], "--abandon-out", files["abandon"], "--wsjtx-alltxt", N0.WS_ALLTXT,
           "--testb-out", files["testb"], "--matched-out", files["matched"]]
    t0 = time.time()
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    end_sha = R.sha256(dll)
    ok, det = V7.compare(OUT, N40_DIR, stamps)
    readbacks = [l.strip() for l in open(files["log"], encoding="utf-8", errors="replace") if l.startswith("# readback")]
    res = {"A_OFF_part2_pass": bool(ok and rc == 0 and start_sha == end_sha == a.new_sha), "harness_rc": rc, "wall_s": round(time.time() - t0),
           "libft8_start_end_equal_pin": start_sha == end_sha == a.new_sha, "new_dll_sha256": a.new_sha,
           "readback_osdSignFixSet0_Read0_all": bool(readbacks) and all("osdSignFixSet=0 osdSignFixRead=0" in l for l in readbacks), "readback_lines": len(readbacks),
           "replay81_dll_sha256": R.sha256(os.path.join(a.harness_out, "Replay81.dll")), "paired_n40": "artefacts/rr_2026-10-06_nhard_rep (build be3cc5ac)",
           "on_fail": "re-run N40 in full on the new binary", **det}
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    json.dump(res, open(RESULT, "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1))
    return 0 if res["A_OFF_part2_pass"] and res["readback_osdSignFixSet0_Read0_all"] else 1


if __name__ == "__main__":
    sys.exit(main())
