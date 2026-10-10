#!/usr/bin/env python
"""OSD-FIX PEEK-100 rows (spec qa/rr-study/2026-10-08-1715-architect-to-qa-osd-fix-peek-p100.md, arch/osd-fix 2b346822). DESCRIPTIVE: no bar, no verdict.

REF = artefacts/rr_2026-10-08_osd_fix/aoff2 (A-OFF part 2, --osd-sign-fix 0, not re-run). FIX40 = artefacts/rr_2026-10-08_osd_fix/peek_fix40 (--osd-sign-fix 1).
Same DLL, selection, order, warm-up, Test B rule, nhard 40, two1, threads 8.

Validity (each must hold or the rows are withheld and named):
  PV1 harness rc 0 (both runs: run_meta.json for FIX40, aoff_part2.json for REF)   PV2 DLL SHA at start = end = pin (both)
  PV3 every '# readback' line carries osdSignFixSet=1 osdSignFixRead=1 (FIX40; REF carries =0)  [>= 2 lines]
  PV4 cycles with residual work abandoned <= 5 % in FIX40 and in REF
  PV5 blind-instrument: FIX40's per-cycle batch-1 and batch-2 multisets equal REF's in ALL 100 cycles => "switch not applied", not a reading
Rows: PK1 NET(FIX40-REF) all batches + CI, K, G | PK2 NET batch 1 and batch 2, each + CI | PK3 batch-1 not-confirmed per cycle | PK4 batch-2 confirmed per cycle |
      PK5 R6 diagnostics (see the limit below) | PK6 wall time per cycle (median, p95), total and batch 1.
NET = 100 * sum(M_fix - M_ref) / sum(W) over the same cycles (Test B confirmed decodes as pp of WSJT-X's decodes), 95 % non-overlapping block bootstrap,
blocks of 8 cycles, B 10,000, seed 20261006 (the NHARD-REP method; the spec says "same NET/CI method").
PK5 LIMIT: the OSD diagnostics are thread-local to the native decode call, and Replay81 decodes on pool threads through DecodeTwoStageAsync, so the product pipeline
cannot read them. PK5 is therefore taken by a separate ctypes pass of ft8_decode_all (first decode call only: its passes 0 and 1) on the SAME 100 cycles at switch 0 and 1,
interleaved per cycle. It does NOT cover the residual-subtraction decode. Aggregates only; no message text (HK-037).

  python qa/rr-study/osd-fix/osd_fix_peek_rows.py --new-dll <path> --new-sha <sha256>
"""
import argparse
import collections
import ctypes
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
sys.path.insert(0, os.path.join(HERE, "..", "coh-gain"))
import onoff_replay_rows as O  # noqa: E402
import nhard_rep_n0_run as N0  # noqa: E402

REPO = N0.REPO
ART_OUT = os.path.join(N0.ART, "rr_2026-10-08_osd_fix")
REF = os.path.join(ART_OUT, "aoff2")
FIX = os.path.join(ART_OUT, "peek_fix40")
RESULTS = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-08-osd-fix")
PIN = "2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb"
BLOCK, B_RES, SEED = 8, 10_000, 20261006
V6_MAX_ABANDON = 0.05
DIAG_CAP, PASS_CAP = 256, 8


def paths(d):
    return {k: os.path.join(d, f"{k}_V7.{e}") for k, e in (("testb", "csv"), ("outcomes", "csv"), ("abandon", "csv"), ("matched", "csv"), ("log", "log"), ("run", "csv"))}


def load_matched(path):
    out = {}
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        s, _, rest = line.partition(",")
        out[s] = frozenset(int(x) for x in rest.split(";") if x != "")
    return out


def pct(a, q):
    return float(np.percentile(np.asarray(a, dtype=float), q)) if len(a) else None


def sumb(cyc, kind, idx):
    return sum(v[idx] for v in cyc[kind].values())


def diag_pass(dll, sha, stamps):
    """PK5: ft8_decode_all + ft8_get_last_osd_diag at switch 0 and 1, interleaved per cycle. Aggregates only."""
    import cg_common as CG
    import cg_select as SEL
    import wavio
    from ldpc_decode_ctypes import LdpcDecodeLLRs
    d = LdpcDecodeLLRs(dll, verify=True, expected_sha256=sha, expected_shim_version=20260060, check_version=True)
    d.dll.ft8_set_decode_params(*CG.PROD_PARAMS)
    fn = d.dll.ft8_get_last_osd_diag
    fn.restype = ctypes.c_int
    P = ctypes.POINTER
    fn.argtypes = [ctypes.c_int, P(ctypes.c_int), P(ctypes.c_float), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), ctypes.c_int]
    acc = {0: [], 1: []}
    per = {0: {"accepts": [0, 0], "rej_nhard": [0, 0], "rej_corr": [0, 0]}, 1: {"accepts": [0, 0], "rej_nhard": [0, 0], "rej_corr": [0, 0]}}
    truncated = 0
    for st in stamps:
        pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, st + ".wav"))
        for sw in (0, 1):
            d.dll.ft8_set_osd_sign_fix(sw)
            if d.decode_all(pcm) is None:
                raise SystemExit("native fault")
            nh = (ctypes.c_int * DIAG_CAP)(); cn = (ctypes.c_float * DIAG_CAP)(); dp = (ctypes.c_int * DIAG_CAP)(); ba = (ctypes.c_int * DIAG_CAP)()
            tot = ctypes.c_int(0); rn = (ctypes.c_int * PASS_CAP)(); rc_ = (ctypes.c_int * PASS_CAP)()
            n = fn(DIAG_CAP, nh, cn, dp, ba, ctypes.byref(tot), rn, rc_, PASS_CAP)
            truncated += int(tot.value > n)
            for i in range(n):
                acc[sw].append((int(nh[i]), float(cn[i]), int(ba[i])))
                per[sw]["accepts"][int(ba[i]) & 1] += 1
            for p in range(2):
                per[sw]["rej_nhard"][p] += int(rn[p]); per[sw]["rej_corr"][p] += int(rc_[p])
    d.dll.ft8_set_osd_sign_fix(1)
    out = {"cycles": len(stamps), "truncated_calls": truncated}
    for sw in (0, 1):
        nhs = [a[0] for a in acc[sw]]
        out[f"switch{sw}"] = {"accepts_total": len(acc[sw]), "accepts_per_cycle": len(acc[sw]) / len(stamps),
                              "accepts_pass0": per[sw]["accepts"][0], "accepts_pass1": per[sw]["accepts"][1],
                              "nhard_median": pct(nhs, 50), "nhard_p90": pct(nhs, 90),
                              "corr_norm_median": pct([a[1] for a in acc[sw]], 50),
                              "rejects_nhard_pass0": per[sw]["rej_nhard"][0], "rejects_nhard_pass1": per[sw]["rej_nhard"][1],
                              "rejects_corr_pass0": per[sw]["rej_corr"][0], "rejects_corr_pass1": per[sw]["rej_corr"][1]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-dll", required=True)
    ap.add_argument("--new-sha", required=True)
    a = ap.parse_args()
    assert a.new_sha == PIN
    sel = json.load(open(os.path.join(REF, "aoff2_selection.json")))
    stamps = sel["runs"][sel["run"]]["A"]
    assert len(stamps) == 100
    pr, pf = paths(REF), paths(FIX)
    tb_r, tb_f = O.load_testb(pr["testb"]), O.load_testb(pf["testb"])
    out_r, out_f = O.load_outcomes(pr["outcomes"]), O.load_outcomes(pf["outcomes"])
    ab_r, ab_f = O.load_abandon(pr["abandon"]), O.load_abandon(pf["abandon"])
    m_r, m_f = load_matched(pr["matched"]), load_matched(pf["matched"])
    run_r, run_f = O.load_run_csv(pr["run"]), O.load_run_csv(pf["run"])
    meta_f = json.load(open(os.path.join(FIX, "run_meta.json")))
    meta_r = json.load(open(os.path.join(RESULTS, "aoff_part2.json")))
    log_f = [l.strip() for l in open(pf["log"], encoding="utf-8", errors="replace") if l.startswith("# readback")]
    log_r = [l.strip() for l in open(pr["log"], encoding="utf-8", errors="replace") if l.startswith("# readback")]

    present = [s for s in stamps if s in tb_r and s in tb_f]
    empty = collections.Counter()
    identical_all = all(out_r.get(s, {}).get("b1", empty) == out_f.get(s, {}).get("b1", empty) and out_r.get(s, {}).get("b2", empty) == out_f.get(s, {}).get("b2", empty) for s in stamps)
    n_ab = lambda ab: sum(1 for s in stamps if ab.get(s, {}).get("abandoned"))
    pv = {"PV1": meta_f["harness_rc"] == 0 and meta_r["harness_rc"] == 0,
          "PV2": meta_f["dll_start"] == meta_f["dll_end"] == PIN and meta_r["libft8_start_end_equal_pin"] and meta_r["new_dll_sha256"] == PIN,
          "PV3": len(log_f) >= 2 and all("osdSignFixSet=1 osdSignFixRead=1" in l for l in log_f) and all("osdSignFixSet=0 osdSignFixRead=0" in l for l in log_r),
          "PV4": n_ab(ab_f) <= V6_MAX_ABANDON * len(stamps) and n_ab(ab_r) <= V6_MAX_ABANDON * len(stamps),
          "PV5_not_all_identical": not identical_all,
          "cycles_present": len(present)}
    res = {"label": "PEEK-100", "descriptive_only": True, "validity": pv, "abandoned_cycles": {"REF": n_ab(ab_r), "FIX40": n_ab(ab_f)}}
    if not (pv["PV1"] and pv["PV2"] and pv["PV3"] and pv["PV4"] and pv["PV5_not_all_identical"] and len(present) == 100):
        res["rows_withheld"] = True
        json.dump(res, open(os.path.join(RESULTS, "peek100.json"), "w"), indent=1, sort_keys=True)
        print(json.dumps(res, indent=1))
        return 2

    W = [tb_r[s]["W"] for s in present]
    assert W == [tb_f[s]["W"] for s in present], "WSJT-X W differs between the runs"
    Mr = [tb_r[s]["M"] for s in present]; Mf = [tb_f[s]["M"] for s in present]
    K = sum(len(m_f[s] - m_r[s]) for s in present); G = sum(len(m_r[s] - m_f[s]) for s in present)
    def net(Wl, A, Bm):
        lo, hi, nb = O.block_bootstrap_ci(Wl, A, Bm, block=BLOCK, B=B_RES, seed=SEED)
        return {"net_pp": O.net_pp(Wl, A, Bm), "ci": [lo, hi], "blocks": nb}
    b1r = [sumb(tb_r[s], "b1", 1) for s in present]; b1f = [sumb(tb_f[s], "b1", 1) for s in present]
    b2r = [sumb(tb_r[s], "b2", 1) for s in present]; b2f = [sumb(tb_f[s], "b2", 1) for s in present]
    n1r = [sumb(tb_r[s], "b1", 0) for s in present]; n1f = [sumb(tb_f[s], "b1", 0) for s in present]
    res["PK1"] = {**net(W, Mr, Mf), "K": K, "G": G, "M_ref_total": sum(Mr), "M_fix_total": sum(Mf), "W_total": sum(W)}
    res["PK2"] = {"batch1": net(W, b1r, b1f), "batch2": net(W, b2r, b2f)}
    c = len(present)
    res["PK3"] = {"batch1_not_confirmed_per_cycle": {"REF": (sum(n1r) - sum(b1r)) / c, "FIX40": (sum(n1f) - sum(b1f)) / c}}
    res["PK4"] = {"batch2_confirmed_per_cycle": {"REF": sum(b2r) / c, "FIX40": sum(b2f) / c}}
    res["PK6"] = {arm: {"total_ms_median": pct([r["elapsed_ms"] for r in rows if r["stamp"] in set(stamps)], 50), "total_ms_p95": pct([r["elapsed_ms"] for r in rows if r["stamp"] in set(stamps)], 95)}
                  for arm, rows in (("REF", run_r), ("FIX40", run_f))}
    res["PK5"] = diag_pass(a.new_dll, a.new_sha, stamps)
    json.dump(res, open(os.path.join(RESULTS, "peek100.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
