#!/usr/bin/env python3
"""THRESH-A analysis: ROW 0b/0d/0e/0f, gate rows T1/T2/T3, section 3.7 descriptive.

Reads artefacts/thresh-a/_out/thresh_a.json (run.py's output). ROW 0a and 0c are
separate, already-passed static checks (dll_pin.load_decoder's own verify=True,
and row0c_lattice.py) -- not re-checked here.
"""
from __future__ import annotations

import json
import os
import sys

from scipy.stats import beta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

from run import NT_COMMITTED_COUNTS, R_STAR_DB, rung_index, rung_db  # noqa: E402

OUT_JSON = os.path.join(REPO_ROOT, "artefacts", "thresh-a", "_out", "thresh_a.json")

T1_LO_BAR = 0.50
T2_HI_BAR = 0.20
ROW0D_BAR = 0.90
ROW0F_MIN_M = 300


def clopper_pearson(k, n, conf=0.95):
    if n == 0:
        return (float("nan"), float("nan"))
    alpha = 1 - conf
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def load():
    with open(OUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def row0b(state, log):
    """P-leg genuine counts per rung == NT's committed counts, all 21 rungs."""
    ok_all = True
    got = []
    for i in range(len(NT_COMMITTED_COUNTS)):
        rec = state["rungs"][str(i)]
        n_genuine = sum(1 for row in rec["trials"] if row["genuine_p"])
        got.append(n_genuine)
        want = NT_COMMITTED_COUNTS[i]
        ok = n_genuine == want
        ok_all &= ok
        if not ok:
            log("ROW 0b: rung idx=%d db=%.1f MISMATCH got=%d want=%d" % (i, rung_db(i), n_genuine, want))
    log("ROW 0b: got  = %s" % got)
    log("ROW 0b: want = %s" % NT_COMMITTED_COUNTS)
    log("ROW 0b: %s" % ("PASS -- all 21 rungs reproduce NT's committed counts exactly" if ok_all
                         else "STOP -- not the same scene or the same binary"))
    return ok_all


def gather_MH(state):
    """M = R* misses (P), H = R* hits (P). Returns (M_rows, H_rows), each a list
    of per-trial dicts carrying 'forced' (the F-leg record)."""
    M, H = [], []
    for db in R_STAR_DB:
        ridx = rung_index(db)
        rec = state["rungs"][str(ridx)]
        for row in rec["trials"]:
            assert "forced" in row, "R* rung trial missing forced-leg record"
            (H if row["genuine_p"] else M).append(row)
    return M, H


def row0d(H, log):
    """Positive control: CP95_lo(R_ctrl) >= 0.90."""
    n = len(H)
    k = sum(1 for row in H if row["forced"]["success"] and row["forced"].get("path") == 0)
    r_ctrl = k / n if n else float("nan")
    lo, hi = clopper_pearson(k, n)
    ok = lo >= ROW0D_BAR
    log("ROW 0d: R_ctrl = %d/%d = %.4f, CP95=[%.4f,%.4f] (need lo >= %.2f)" % (k, n, r_ctrl, lo, hi, ROW0D_BAR))
    log("ROW 0d: %s" % ("PASS" if ok else "VOID -- forced read can't reproduce production's own hits"))
    return ok, k, n, r_ctrl, (lo, hi)


def row0e(M, H, log):
    """Zero harness faults on leg F, every rung (R*)."""
    n_faults = sum(1 for row in (M + H) if row["forced"].get("harness_fault"))
    ok = n_faults == 0
    log("ROW 0e: harness faults on F leg (R* rungs) = %d" % n_faults)
    log("ROW 0e: %s" % ("PASS" if ok else "STOP -- fix harness faults before counting"))
    return ok


def row0f(M, log):
    n = len(M)
    ok = n >= ROW0F_MIN_M
    log("ROW 0f: |M| = %d (need >= %d)" % (n, ROW0F_MIN_M))
    log("ROW 0f: %s" % ("PASS" if ok else "underpowered -- top up in 250-trial blocks, up to 2, else T3"))
    return ok


def gate_row(M, log):
    n = len(M)
    k_bp = sum(1 for row in M if row["forced"]["success"] and row["forced"].get("path") == 0)
    r_forced = k_bp / n if n else float("nan")
    lo, hi = clopper_pearson(k_bp, n)
    log("R_forced (BP-only) = %d/%d = %.4f, CP95=[%.4f,%.4f]" % (k_bp, n, r_forced, lo, hi))

    k_any = sum(1 for row in M if row["forced"]["success"])  # incl. OSD path, reported separately
    log("R_forced (any path, incl. OSD, reported not gated) = %d/%d = %.4f" % (k_any, n, k_any / n if n else float("nan")))

    if hi < T2_HI_BAR:
        row = "T2"
        reading = "L-BITS dominates: >=80%% of threshold misses don't decode even at the right cell."
    elif lo >= T1_LO_BAR:
        row = "T1"
        reading = "L-CAND dominates: most threshold misses decode when handed the right cell."
    else:
        row = "T3"
        reading = "Both loci contribute."
    log(">>> GATE: %s <<< %s" % (row, reading))
    return row, k_bp, n, r_forced, (lo, hi), k_any


def descriptive_3_7(state, log):
    """Per rung: p_P, p_F_BP, p_F_any (all 21 rungs, F only where present)."""
    log("\n--- 3.7 descriptive, per rung ---")
    x50_P = x50_FBP = None
    rows = []
    for i in range(len(NT_COMMITTED_COUNTS)):
        rec = state["rungs"][str(i)]
        n = len(rec["trials"])
        n_p = sum(1 for row in rec["trials"] if row["genuine_p"])
        p_p = n_p / n
        has_forced = "forced" in rec["trials"][0]
        if has_forced:
            n_fbp = sum(1 for row in rec["trials"] if row["forced"]["success"] and row["forced"].get("path") == 0)
            n_fany = sum(1 for row in rec["trials"] if row["forced"]["success"])
            p_fbp = n_fbp / n
            p_fany = n_fany / n
        else:
            p_fbp = p_fany = None
        db = rung_db(i)
        rows.append({"idx": i, "db": db, "n": n, "p_P": p_p, "p_F_BP": p_fbp, "p_F_any": p_fany})
        log("  idx=%2d db=%+5.1f n=%3d p_P=%.3f p_F_BP=%s p_F_any=%s" %
            (i, db, n, p_p, ("%.3f" % p_fbp) if p_fbp is not None else "n/a",
             ("%.3f" % p_fany) if p_fany is not None else "n/a"))

    # 50% points by linear interpolation (only meaningful across R* + neighbours where
    # both curves are defined; P is monotone-ish across the whole ladder).
    def interp50(pairs):
        # pairs: sorted list of (db, p) with p increasing in db
        for (db0, p0), (db1, p1) in zip(pairs, pairs[1:]):
            if p0 <= 0.5 <= p1 and p1 != p0:
                return db0 + (0.5 - p0) * (db1 - db0) / (p1 - p0)
        return None

    p_pairs = [(r["db"], r["p_P"]) for r in rows]
    x50_P = interp50(p_pairs)

    fbp_pairs = [(r["db"], r["p_F_BP"]) for r in rows if r["p_F_BP"] is not None]
    x50_FBP = interp50(fbp_pairs) if len(fbp_pairs) >= 2 else None

    log("\nx50(P)    (50%% pt, production)      = %s dB (nominal)" % (("%.3f" % x50_P) if x50_P is not None else "n/a (out of R* range)"))
    log("x50(F_BP) (50%% pt, forced BP-only)   = %s dB (nominal)" % (("%.3f" % x50_FBP) if x50_FBP is not None else "n/a (R* too narrow for interpolation)"))
    if x50_P is not None and x50_FBP is not None:
        log("Delta50 = x50(P) - x50(F_BP) = %.3f dB (nominal, sensitivity a perfect candidate stage would buy)" % (x50_P - x50_FBP))
    else:
        log("Delta50: not computable from R*'s 5 rungs alone if F_BP never crosses 0.5 within R* -- "
            "see gate reading instead (§3.4 already answers the T1/T2/T3 question this sizes).")

    return rows, x50_P, x50_FBP


def main():
    def log(msg):
        print(msg, flush=True)

    state = load()

    ok0b = row0b(state, log)
    if not ok0b:
        log("STOP at ROW 0b.")
        return 1

    M, H = gather_MH(state)
    log("|M| (R* misses) = %d, |H| (R* hits) = %d, total R* trials = %d" % (len(M), len(H), len(M) + len(H)))

    ok0d, k_ctrl, n_ctrl, r_ctrl, ci_ctrl = row0d(H, log)
    if not ok0d:
        log("VOID at ROW 0d.")
        return 1

    ok0e = row0e(M, H, log)
    if not ok0e:
        log("STOP at ROW 0e.")
        return 1

    ok0f = row0f(M, log)
    if not ok0f:
        log("ROW 0f: underpowered as-is -- top-up would be needed (not executed; |M| already >= 300 expected).")

    log("\n--- Gate ---")
    gate, k_bp, n_m, r_forced, ci_forced, k_any = gate_row(M, log)

    rows37, x50_P, x50_FBP = descriptive_3_7(state, log)

    result = {
        "row0b_pass": ok0b, "row0d_pass": ok0d, "row0e_pass": ok0e, "row0f_pass": ok0f,
        "n_M": len(M), "n_H": len(H),
        "R_ctrl": r_ctrl, "R_ctrl_ci95": ci_ctrl, "k_ctrl": k_ctrl, "n_ctrl": n_ctrl,
        "R_forced_BP": r_forced, "R_forced_BP_ci95": ci_forced, "k_forced_BP": k_bp,
        "k_forced_any": k_any, "n_M_denom": n_m,
        "gate": gate,
        "x50_P": x50_P, "x50_F_BP": x50_FBP,
        "descriptive_rows": rows37,
    }
    out_path = os.path.join(REPO_ROOT, "artefacts", "thresh-a", "_out", "analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log("\nWrote %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
