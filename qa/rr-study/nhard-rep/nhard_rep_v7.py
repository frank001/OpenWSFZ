#!/usr/bin/env python
"""NHARD-REP Amendment 3, V7 (Architect 2026-10-06, spec section 14 as amended 12caa402): the PAIRING CONTROL for arm N0.

N0 is paired with an N40 produced by an EARLIER build of the harness binary (Replay81.dll 4a9cf533...; the new one adds only output switches and the cap-0 admission). The decode path is
unchanged, but exactness across two harness binaries is not demonstrated (V6 showed same-binary exactness only). V7: re-run the FIRST 100 SAMPLED CYCLES at --nhard 40 on the NEW binary
(same build be3cc5ac, pin, flag ON, threads 8, Test B rule, same warm-up and cycle order, so the process-global hash table has the same history) and compare with the N40 on file.
PASS iff 0 of the 100 cycles differ, where a cycle differs if its MATCHED SET (WSJT-X line indices) differs OR its DECODE MULTISET (batch 1 and batch 2 numeric (freq, dt, snr)) differs.
On FAIL, do NOT pair with the old N40: re-run N40 in full with the new binary and pair N0 with that.

  python qa/rr-study/nhard-rep/nhard_rep_v7.py [--preflight-only]
HK-037: ALL.TXT is read only inside the harness' matching function; every output is numeric.
"""
import collections
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import nhard_rep_n0_run as N0  # noqa: E402  (constants, preflight, pin helpers)
import nhard_rep_rows as NR  # noqa: E402
import replay81_run as R  # noqa: E402

O = NR.O
N_CYCLES = 100
V7_NHARD = 40
V7_OUT = os.path.join(N0.OUT, "v7")
N40_DIR = os.path.join(N0.ART, "rr_2026-10-06_nhard_rep")
RESULT = os.path.join(N0.REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "v7_pairing_result.json")


def first_stamps(selection_path=N0.SELECTION, n=N_CYCLES):
    sel = json.loads(open(selection_path, "rb").read().replace(b"\r\n", b"\n"))
    return sel["runs"][sel["run"]]["SAMPLE"][:n], sel["runs"][sel["run"]]["warmup"]


def compare(v7_dir, n40_dir, stamps):
    """PASS iff 0 cycles differ. A cycle differs if either run is missing it, its matched sets differ, or its batch-1 or batch-2 decode multiset differs.
    Returns (ok, details). An absent file never reads as a pass."""
    a_m, b_m = NR.load_matched(NR.arm_paths(v7_dir, "V7")["matched"]), NR.load_matched(NR.arm_paths(n40_dir, "N40")["matched"])
    a_o, b_o = O.load_outcomes(NR.arm_paths(v7_dir, "V7")["outcomes"]), O.load_outcomes(NR.arm_paths(n40_dir, "N40")["outcomes"])
    empty = collections.Counter()
    differing, reasons = [], collections.Counter()
    for s in stamps:
        why = []
        if s not in a_m or s not in b_m:
            why.append("missing_matched")
        elif a_m[s] != b_m[s]:
            why.append("matched_set")
        for kind in ("b1", "b2"):
            x = a_o.get(s, {}).get(kind, empty)
            y = b_o.get(s, {}).get(kind, empty)
            if x != y:
                why.append(f"decode_multiset_{kind}")
        if why:
            differing.append(s)
            reasons.update(why)
    ok = len(stamps) == N_CYCLES and not differing
    return ok, {"n": len(stamps), "differing_cycles": len(differing), "differing_stamps": differing[:10], "reasons": dict(reasons)}


def run():
    stamps, warmup = first_stamps()
    assert len(stamps) == N_CYCLES
    os.makedirs(V7_OUT, exist_ok=True)
    sel = {"note": "NHARD-REP V7 pairing control: the first 100 sampled cycles", "run": N0.RUN, "runs": {N0.RUN: {"warmup": warmup, "V7": stamps}}}
    sel_path = os.path.join(V7_OUT, "v7_selection.json")
    json.dump(sel, open(sel_path, "w"), indent=1, sort_keys=True)
    files = {k: os.path.join(V7_OUT, f"{k}_V7.{ext}") for k, ext in (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("log", "log"))}
    for p in files.values():
        if os.path.exists(p):
            os.remove(p)
    got = R.sha256(os.path.join(N0.HOUT, "libft8.dll"))
    assert got == N0.DLL
    cmd = ["dotnet", os.path.join(N0.HOUT, "Replay81.dll"), "--selection", sel_path, "--run", N0.RUN, "--stratum", "V7", "--wav-root", N0.ART, "--wav-dir", N0.WAV_DIR,
           "--out", files["run"], "--log", files["log"], "--mode", "two1", "--threads", N0.THREADS, "--nhard", str(V7_NHARD), "--label", f"{N0.BUILD_COMMIT}:nhardrep_V7",
           "--outcomes", files["outcomes"], "--abandon-out", files["abandon"], "--wsjtx-alltxt", N0.WS_ALLTXT, "--testb-out", files["testb"], "--matched-out", files["matched"]]
    t0 = time.time()
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    end_sha = R.sha256(os.path.join(N0.HOUT, "libft8.dll"))
    ok, det = compare(V7_OUT, N40_DIR, stamps)
    res = {"V7_pass": bool(ok and rc == 0 and end_sha == N0.DLL), "harness_rc": rc, "wall_s": round(time.time() - t0), "libft8_start_end_equal_pin": got == end_sha == N0.DLL,
           "replay81_dll_sha256_new": R.sha256(os.path.join(N0.HOUT, "Replay81.dll")), "paired_n40": "artefacts/rr_2026-10-06_nhard_rep (earlier harness binary)", **det,
           "on_fail": "do NOT pair with the old N40: re-run N40 in full with the new binary and pair N0 with that"}
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    json.dump(res, open(RESULT, "w"), indent=1, sort_keys=True)
    return res


def main():
    os.makedirs(N0.OUT, exist_ok=True)
    R.OUT = N0.OUT
    R.LOGF = open(os.path.join(N0.OUT, "orchestrator.log"), "a", encoding="utf-8")
    pre = N0.preflight()
    print("preflight OK: harness", pre["harness_commit"][:8], "DLL", pre["libft8_sha256"][:8], flush=True)
    if "--preflight-only" in sys.argv:
        return 0
    res = run()
    print(json.dumps(res, indent=1))
    return 0 if res["V7_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
