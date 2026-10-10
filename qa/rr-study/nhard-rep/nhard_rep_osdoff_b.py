#!/usr/bin/env python
"""NHARD-REP Amendment 3 CONFIRMATION (QA, under the Captain's overnight authorisation 2026-10-06 ~20:40Z; UNRULED, no threshold or row changed): OSD-OFF on FRESH cycles.

The first OSD-OFF sample (arms N0 / N40, positions i mod 10 == 0) read O-GAIN with a tiny effect (+0.074 pp, 7 confirmed decodes in 6 cycles). This replicates it on the
FRESH positions i mod 10 == 5 of the NHARD-REP frozen list (selection.json 'SAMPLE_B', 310 cycles, the reserve the spec names), BOTH arms run now on the SAME (new) binary, so no
pairing control is needed: N40B at --nhard 40, N0B at --nhard 0, same build be3cc5ac, pin 2fa6d993...f365, flag ON, threads 8, Test B rule.

Rows (the spec's, unchanged, first match wins): O-HARM CI_hi < 0; O-GAIN CI_lo > 0; O-SAFE CI_lo >= -0.10 pp (ratified, FROZEN); O-OPEN. HK-038: 0 is the no-change point,
-0.10 pp a ratified decision margin. Reported: (1) the FRESH sample alone (the replication), (2) the POOLED estimate over the first sample and the fresh one (block 8 within each
sample, then pooled; same B and seed): the pooled rows are the confirmatory verdict. V2'' (P_lo rejected at 0, accepted at 40) gates each sample; a failing sample is named, not pooled.

  python qa/rr-study/nhard-rep/nhard_rep_osdoff_b.py [--preflight-only]
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
import nhard_rep_n0_run as N0  # noqa: E402
import nhard_rep_n0_rows as NZ  # noqa: E402
import nhard_rep_rows as NR  # noqa: E402
import replay81_run as R  # noqa: E402

O = NR.O
STRATUM = "SAMPLE_B"
ARMS = (("N40B", 40), ("N0B", 0))
OUT_B = os.path.join(N0.ART, "rr_2026-10-06_nhard_rep_osdoff_b")
RESULTS = os.path.join(N0.REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep")
B_ANALYSIS = "osdoff_b_analysis.json"
V2PP_FAIL_RC = 5


def files(arm):
    return {k: os.path.join(OUT_B, f"{k}_{arm}.{ext}") for k, ext in (("run", "csv"), ("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"),
                                                                       ("probe", "csv"), ("log", "log"))}


def pin(arm, when):
    got = R.sha256(os.path.join(N0.HOUT, "libft8.dll"))
    with open(os.path.join(OUT_B, "pins.jsonl"), "a") as fh:
        fh.write(json.dumps({"utc": R.now(), "arm": arm, "when": when, "libft8_sha256": got, "pinned": N0.DLL, "match": got == N0.DLL}) + "\n")
    assert got == N0.DLL


def run_arm(arm, nhard):
    f = files(arm)
    rc = None
    for attempt in range(2):
        for p in f.values():
            if os.path.exists(p):
                os.remove(p)
        pin(arm, "start")
        cmd = ["dotnet", os.path.join(N0.HOUT, "Replay81.dll"), "--selection", N0.SELECTION, "--run", N0.RUN, "--stratum", STRATUM, "--wav-root", N0.ART, "--wav-dir", N0.WAV_DIR,
               "--out", f["run"], "--log", f["log"], "--mode", "two1", "--threads", N0.THREADS, "--nhard", str(nhard), "--label", f"{N0.BUILD_COMMIT}:osdoff_{arm}",
               "--outcomes", f["outcomes"], "--abandon-out", f["abandon"], "--wsjtx-alltxt", N0.WS_ALLTXT, "--testb-out", f["testb"], "--matched-out", f["matched"],
               "--probe-vectors", N0.PROBES, "--probe-out", f["probe"]]
        t0 = time.time()
        rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
        pin(arm, "end")
        with open(os.path.join(OUT_B, "process_exits.log"), "a") as fh:
            fh.write(f"{R.now()} {arm} rc={rc} attempt={attempt} wall_s={time.time() - t0:.0f}\n")
        if rc == 0 or rc == V2PP_FAIL_RC:
            break
    return rc


def sample_arrays(n0_dir, n40_dir, stamps, arm0, arm40):
    t0 = O.load_testb(NR.arm_paths(n0_dir, arm0)["testb"])
    t40 = O.load_testb(NR.arm_paths(n40_dir, arm40)["testb"])
    present = [s for s in stamps if s in t0 and s in t40]
    return (np.array([t40[s]["W"] for s in present], dtype=float), np.array([t40[s]["M"] for s in present], dtype=float),
            np.array([t0[s]["M"] for s in present], dtype=float))


def pooled_o(samples, block=NR.BLOCK_REGISTERED):
    """NET_0 pooled over samples: blocks of `block` cycles WITHIN each sample (the last partial block kept), then pooled; same B and seed as the closed arms."""
    nums, dens, tn, td = [], [], 0.0, 0.0
    for W, M40, M0 in samples:
        d = M0 - M40
        edges = list(range(0, len(d), block))
        nums.append(np.array([d[i:i + block].sum() for i in edges], dtype=float))
        dens.append(np.array([W[i:i + block].sum() for i in edges], dtype=float))
        tn += float(d.sum())
        td += float(W.sum())
    num, den = np.concatenate(nums), np.concatenate(dens)
    rng = np.random.default_rng(NR.SEED)
    idx = rng.integers(0, len(num), size=(NR.B_RESAMPLES, len(num)))
    lo, hi = np.percentile(100.0 * num[idx].sum(axis=1) / den[idx].sum(axis=1), [2.5, 97.5])
    return {"NET_0_pp": 100.0 * tn / td, "ci95": [float(lo), float(hi)], "n_blocks": len(num), "n_cycles": int(sum(len(w) for w, _, _ in samples)), "sum_W": int(td)}


def score(b_dir, first_n0_dir, first_n40_dir, results_dir=None, first_analysis_failing=None, selection_path=None):
    """(1) the fresh sample alone through the SAME rows (arms N0B / N40B, stratum SAMPLE_B); (2) the pooled estimate over the first sample and the fresh one, valid only if BOTH samples'
    validity rows pass; the pooled O-row is the confirmatory verdict."""
    fresh = NZ.analyse(b_dir, b_dir, None, selection_path, arm0="N0B", arm40="N40B", stratum=STRATUM)
    sel_path = selection_path or NZ.os.path.join(NZ.REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
    sel = json.loads(open(sel_path, "rb").read().replace(b"\r\n", b"\n"))
    run = sel["run"]
    first_failing = first_analysis_failing
    if first_failing is None:
        fa = os.path.join(RESULTS, "n0_analysis.json")
        first_failing = json.load(open(fa))["failing_rows"] if os.path.exists(fa) else ["first analysis missing"]
    a = sample_arrays(first_n0_dir, first_n40_dir, sel["runs"][run]["SAMPLE"], "N0", "N40")
    b = sample_arrays(b_dir, b_dir, sel["runs"][run][STRATUM], "N0B", "N40B")
    out = {"fresh_sample_alone": {k: fresh[k] for k in ("verdict", "failing_rows", "estimand", "descriptive", "validity", "consistency") if k in fresh},
           "first_sample_failing_rows": first_failing}
    if len(a[0]) and len(b[0]):
        pooled = pooled_o([a, b])
        out["pooled"] = pooled
        if not fresh["failing_rows"] and not first_failing:
            out["pooled_verdict"] = NZ.verdict_row(*pooled["ci95"])
        else:
            out["pooled_verdict"] = "NO VERDICT"
            out["verdict_withheld_because"] = [f"fresh:{k}" for k in fresh["failing_rows"]] + [f"first:{k}" for k in first_failing]
    else:
        out["pooled_verdict"] = "NO VERDICT"
        out["verdict_withheld_because"] = ["a sample has no scored cycles"]
    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(out, open(os.path.join(results_dir, B_ANALYSIS), "w"), indent=1, sort_keys=True, default=str)
    return out


def main():
    os.makedirs(OUT_B, exist_ok=True)
    R.OUT = OUT_B
    R.LOGF = open(os.path.join(OUT_B, "orchestrator.log"), "a", encoding="utf-8")
    pre = N0.preflight()
    R.log(f"osdoff-b preflight OK harness {pre['harness_commit'][:8]}")
    if "--preflight-only" in sys.argv:
        return 0
    rcs = {}
    for arm, nhard in ARMS:
        rcs[arm] = run_arm(arm, nhard)
        R.log(f"{arm} rc={rcs[arm]}")
        if rcs[arm] != 0:
            break
    first_n0 = os.path.join(N0.ART, "rr_2026-10-06_nhard_rep_n0")
    first_n40 = os.path.join(N0.ART, "rr_2026-10-06_nhard_rep")
    res = score(OUT_B, first_n0, first_n40, RESULTS)
    R.log(f"osdoff-b scored: {res.get('pooled_verdict')} fresh {res['fresh_sample_alone'].get('verdict')} rcs {rcs}")
    print(json.dumps({"rcs": rcs, "pooled_verdict": res.get("pooled_verdict"), "pooled": res.get("pooled"), "fresh_verdict": res["fresh_sample_alone"].get("verdict")}, indent=1))
    return 0 if all(v == 0 for v in rcs.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
