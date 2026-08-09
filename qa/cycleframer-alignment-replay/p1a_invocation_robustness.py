#!/usr/bin/env python3
"""P1a -- is A = 15.55 pp real, or an artefact of the invocation P1 pinned?

Spec: 2026-08-09-0115-architect-to-qa-spec-p1a-decode-depth-invocation-robustness.md

P1 voided at ROW 0d on an Architect drafting defect (a gate demanding a
property with a ~0.0023% base rate, giving a ~1-in-4 false-failure rate).
P1a is a VALIDITY RE-TEST, not a fresh measurement, and it is explicitly NOT
BLIND -- A = 15.553 has already been seen, so prediction-scoring on A is
suspended.  The blind question is dA = A_p15 - A_default.

Four legs: {d1, d3} x {default, -p 15}, identical files, full window.
Stage 1 gates on |dA| <= 1.5 pp; only if that passes may A_p15 be read
through P1's original ROW 1/2/3.

Reuses P1's own harness wholesale so the populations are provably identical.
NFR-021: counts and rates only; jt9 stdout stays in a scratch dir.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_decode_depth_contrast as P1  # noqa: E402
from t1_frequency_quantisation import load, WINDOW_20M, LEG_20M  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
A_VOID = 15.553          # the voided run's value -- ROW 0d determinism check only
SEED = 20260809
JT9_BATCH_SIZE = 150     # pinned to Angle 1's endurance_anova_jt9.py:127, not chosen
INVOCATIONS = ["perfile", "batched"]   # AMENDMENT 1 A1.3: -p 15 is inert, batching is not


def run_batched(files, depth, scratch, batch_size=JT9_BATCH_SIZE):
    """Angle-1-style: many files per jt9 process. Returns ts -> [message,...].

    Chunked because the Windows command line caps near 32 767 chars; 150 files
    of ~85-char paths is ~13 kB, comfortably inside it and identical to the
    historical value.

    Lines are bucketed by HHMMSS and then handed to P1.parse_jt9_stdout --
    the IDENTICAL parser the per-file leg uses.  This is load-bearing: batched
    output carries trailing decode-type markers (e.g. "a7") that per-file output
    does not, and P1's parser strips them via MARKER_RE.  A bespoke parser here
    left them in the message text and manufactured an 8.3% nesting failure on a
    30-file smoke test, against 0.44% for per-file.  Both legs must parse the
    same way or the contrast measures the parser, not the invocation.

    Batches are dispatched to a thread pool -- each batch is an independent
    jt9 process with its own scratch subdirectory, exactly as Angle 1's
    _run_one_jt9_batch was designed for.  Batch COMPOSITION is unchanged
    (contiguous 150-file chunks), so only wall-clock differs; single-process
    batched costs ~3 h at full scale versus ~25 min here.
    """
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    chunks = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]

    def one(job):
        bi, batch = job
        d = os.path.join(scratch, "b%03d" % bi)
        os.makedirs(d, exist_ok=True)
        argv = [P1.JT9_EXE, "-8", "-d", str(depth), "-p", "15"] + [p for _, p in batch]
        r = subprocess.run(argv, cwd=d, capture_output=True, text=True, timeout=7200)
        return r.stdout

    buckets = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for stdout in ex.map(one, list(enumerate(chunks))):
            for line in stdout.splitlines():
                if "~" not in line or "<DecodeFinished>" in line:
                    continue
                tok = line.split()
                if not tok:
                    continue
                buckets.setdefault(tok[0], []).append(line)
    out = {hh: P1.parse_jt9_stdout("\n".join(ls)) for hh, ls in buckets.items()}
    # jt9 prints HHMMSS only; map back to the full ts via the filenames replayed
    remap = {}
    for ts, _p in files:
        remap.setdefault(ts.split("_")[1], ts)
    return {remap.get(k, k): v for k, v in out.items()}


def paired_cluster_bootstrap(ref_freq, num_default, num_p15, n_draws=1000, seed=SEED):
    """Spec 2.2: resample frequency clusters ONCE per draw and recompute BOTH
    A's on the same clusters, differencing inside the draw."""
    byf = {}
    for k, f in ref_freq.items():
        byf.setdefault(f, []).append(k)
    freqs = list(byf)
    rng = np.random.default_rng(seed)
    a_d, a_p, d_a = [], [], []
    for _ in range(n_draws):
        pick = rng.choice(len(freqs), size=len(freqs), replace=True)
        keys = []
        for i in pick:
            keys.extend(byf[freqs[i]])
        n = len(keys)
        if not n:
            continue
        ad = 100.0 * sum(1 for k in keys if k in num_default) / n
        ap = 100.0 * sum(1 for k in keys if k in num_p15) / n
        a_d.append(ad)
        a_p.append(ap)
        d_a.append(ap - ad)
    f = lambda v: {"mean": float(np.mean(v)), "se": float(np.std(v, ddof=1)),
                   "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]}
    return {"A_perfile": f(a_d), "A_batched": f(a_p), "dA": f(d_a),
            "n_draws": len(d_a), "n_distinct_freq": len(freqs), "seed": seed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    os.makedirs(a.scratch, exist_ok=True)
    t0 = time.time()

    files = P1.in_window_files(WINDOW_20M)
    if a.limit:
        files = files[:a.limit]
    print("in-window files: %d" % len(files), flush=True)

    # populations -- identical to P1 by construction
    wa = load(os.path.join(REPO_ROOT, LEG_20M["wsjtx_a"]), *WINDOW_20M)
    wb = load(os.path.join(REPO_ROOT, LEG_20M["wsjtx_b"]), *WINDOW_20M)
    ow = load(os.path.join(REPO_ROOT, LEG_20M["owsfz"]), *WINDOW_20M)
    ref = {k: wa[k] for k in wa.keys() & wb.keys()}
    ts_replayed = {ts for ts, _ in files}
    ref = {k: v for k, v in ref.items() if k[0] in ts_replayed}
    ref_keys = set(ref)
    miss = ref_keys - set(ow)
    n_ref = len(ref_keys)
    print("REF %d  MISS %d" % (n_ref, len(miss)), flush=True)

    wa_live_replayed = sum(1 for k in wa if k[0] in ts_replayed)

    legs = {}
    for name in INVOCATIONS:
        P1.EXTRA_ARGS = []
        sub = os.path.join(a.scratch, name)
        os.makedirs(sub, exist_ok=True)
        cache = os.path.join(a.scratch, "p1a_%s.json" % name)
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as fh:
                d = json.load(fh)
            legs[name] = {"n1_raw": d["n1_raw"], "n3_raw": d["n3_raw"],
                          "D1": {tuple(x) for x in d["D1"]},
                          "D3": {tuple(x) for x in d["D3"]}}
            print("  %s RESUMED from cache" % name, flush=True)
            continue
        print("  leg %s starting ..." % name, flush=True)
        t = time.time()
        if name == "perfile":
            pf1 = P1.run_jt9(files, 1, sub, a.workers)
            pf3 = P1.run_jt9(files, 3, sub, a.workers)
        else:
            pf1 = run_batched(files, 1, sub)
            pf3 = run_batched(files, 3, sub)
        n1_raw, D1 = P1.to_keyset(pf1)
        n3_raw, D3 = P1.to_keyset(pf3)
        legs[name] = {"n1_raw": n1_raw, "n3_raw": n3_raw, "D1": D1, "D3": D3}
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump({"n1_raw": n1_raw, "n3_raw": n3_raw,
                       "D1": [list(x) for x in D1], "D3": [list(x) for x in D3]}, fh)
        print("    %s done in %.1f min (d1 %d/%d, d3 %d/%d)"
              % (name, (time.time() - t) / 60.0, n1_raw, len(D1), n3_raw, len(D3)),
              flush=True)

    per_inv = {}
    for name, L in legs.items():
        D1, D3 = L["D1"], L["D3"]
        d3_only = D3 - D1
        per_inv[name] = {
            "n1_raw": L["n1_raw"], "n1_dedup": len(D1),
            "n3_raw": L["n3_raw"], "n3_dedup": len(D3),
            "D3_minus_D1": len(d3_only),
            "D1_minus_D3": len(D1 - D3),
            "nest_frac": (len(D1 - D3) / len(D1)) if D1 else 1.0,
            "numerator": len(miss & d3_only),
            "A": 100.0 * len(miss & d3_only) / n_ref,
            "C": 100.0 * len(D1 & ref_keys) / n_ref,
            "B": (100.0 * len(d3_only) / len(D1)) if D1 else 0.0,
            "ratio_d3_live": (len(D3) / wa_live_replayed) if wa_live_replayed else 0.0,
            "_num_set": miss & d3_only,
        }

    A_def = per_inv["perfile"]["A"]
    A_p15 = per_inv["batched"]["A"]
    dA = A_p15 - A_def
    boot = paired_cluster_bootstrap(ref, per_inv["perfile"]["_num_set"],
                                    per_inv["batched"]["_num_set"])
    se_dA = boot["dA"]["se"]
    for v in per_inv.values():
        v.pop("_num_set")

    # ── pre-registered gate, spec 3, transcribed verbatim ────────────────────
    def p1a_row0():
        if len(files) < 800:
            return "ROW 0a", "n_cycles %d < 800" % len(files)
        for nm in INVOCATIONS:
            if per_inv[nm]["n3_dedup"] == per_inv[nm]["n1_dedup"]:
                return "ROW 0b", "%s: depth flag had no effect" % nm
        worst = max(per_inv[nm]["nest_frac"] for nm in INVOCATIONS)
        if worst > 0.01:
            return "ROW 0c", "worst |D1\\D3|/|D1| = %.4f > 0.01" % worst
        if abs(A_def - A_VOID) > 0.10:
            return "ROW 0d", ("A_perfile %.3f did not reproduce the voided %.3f "
                              "(determinism check, NOT a rehabilitation)" % (A_def, A_VOID))
        if se_dA > 0.75:
            return "ROW 0e", "SE(dA) = %.3f pp > 0.75 -- UNDERPOWERED" % se_dA
        return None, None

    row0, reason = p1a_row0()
    stage1 = stage2 = None
    if row0 is None:
        stage1 = "V-ROW 1" if abs(dA) <= 1.5 else "V-ROW 2"
        if stage1 == "V-ROW 1":
            stage2 = "ROW 1" if A_p15 >= 5.0 else ("ROW 2" if A_p15 <= 1.5 else "ROW 3")
    final = row0 or (stage2 or stage1)

    result = {
        "arm": "P1a",
        "spec": "2026-08-09-0115-architect-to-qa-spec-p1a-decode-depth-invocation-robustness.md",
        "amendment": "A1.3 -- legs are perfile vs batched(150); -p 15 proven inert",
        "NOT_BLIND": "A = 15.553 was seen before this run; prediction-scoring on A is suspended",
        "n_cycles": len(files), "REF": n_ref, "MISS": len(miss),
        "wa_live_replayed": wa_live_replayed,
        "per_invocation": per_inv,
        "A_perfile": A_def, "A_batched": A_p15, "dA": dA, "SE_dA": se_dA,
        "row0": row0, "row0_reason": reason,
        "stage1_validity": stage1, "stage2_substantive": stage2, "final_row": final,
        "bootstrap": boot,
        "wall_clock_min": (time.time() - t0) / 60.0, "workers": a.workers,
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    print(json.dumps({k: v for k, v in result.items() if k != "bootstrap"},
                     indent=2, sort_keys=True), flush=True)
    print("FINAL ROW: %s" % final, flush=True)


if __name__ == "__main__":
    main()
