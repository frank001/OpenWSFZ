#!/usr/bin/env python
"""OSD-FIX TRAIN final report numbers (ruling 2026-10-09 0615, `n*` = 24). Numeric only (HK-037): Test B files hold counts, no text.

  python qa/rr-study/osd-fix/osd_fix_train_report.py rows    # final table, FIX24 - FIX0, sensitivity rows, wall times -> train_final.json
  python qa/rr-study/osd-fix/osd_fix_train_report.py diag    # R6: nhard of OSD gate accepts on the 621 TRAIN cycles, switch 0 and 1 -> train_r6_hist.json

`rows` reuses osd_fix_train_rows.load_arm/compare/would_pick UNCHANGED (the committed statistics script, eb1c242b). The sensitivity rows apply
`compare` to the same per-cycle rows with cycles removed; the Architect's figures (ruling section 3) are checked against it, never copied.

`diag` is the PEEK-100 PK5 method (osd_fix_peek_rows.diag_pass) extended to a histogram of the accepted `nhard`, on every TRAIN cycle, first decode call only
(passes 0 and 1: the native diagnostics are thread-local, so Replay81 cannot read them), at the production parameters (nhard cap 40). It describes the OSD gate's
accepts at switch 0 (inverted LLRs) and 1 (corrected LLRs); the accepts with nhard <= 24 are the ones FIX24 keeps. It scores nothing.
"""
import ctypes
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
sys.path.insert(0, os.path.join(HERE, "..", "coh-gain"))
import osd_fix_train_rows as R  # noqa: E402
import osd_fix_train as T       # noqa: E402

PIN = "2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb"
DIAG_CAP, PASS_CAP = 256, 8
OUT_FINAL = os.path.join(T.RESULTS, "train_final.json")
OUT_HIST = os.path.join(T.RESULTS, "train_r6_hist.json")


def abandoned_stamps():
    """stamps abandoned in ANY arm, with the arm(s) and round: abandon.csv columns stamp,ran,abandoned,contained."""
    found = {}
    for r in range(1, T.N_ROUNDS + 1):
        for name, _s, _n in T.ARMS:
            p = os.path.join(T.OUT, f"r{r}", name, "abandon.csv")
            for line in open(p, encoding="utf-8").read().splitlines()[1:]:
                st, ran, ab, _c = line.split(",")
                if int(ab) > 0:
                    found.setdefault(st, []).append((r, name, int(ab)))
    return found


def keep(arms, drop):
    return {n: [x for x in rows if x["stamp"] not in drop] for n, rows in arms.items()}


def pair(arms, a, b):
    return R.compare(arms[a], arms[b])


def rows():
    rounds = R.completed_rounds()
    assert rounds == list(range(1, 8)), f"TRAIN is not complete: {rounds}"
    arms = {a[0]: R.load_arm(rounds, a[0]) for a in T.ARMS}
    n = len(arms["REF"])
    assert n == 621, n   # the inherited constant, as an assertion
    res = {"cycles": n, "rounds": rounds, "block": R.BLOCK, "B": R.B_RES, "seed": R.SEED}
    res["vs_REF"] = {name: R.compare(arms["REF"], arms[name]) for name, _s, _n in T.ARMS[1:]}
    res["n_star_rule"] = R.would_pick(res["vs_REF"], len(rounds))
    res["FIX24_minus_FIX0"] = pair(arms, "FIX0", "FIX24")
    ab = abandoned_stamps()
    res["abandoned_cycles"] = {"distinct_cycles": len(ab), "by_cycle": {s: v for s, v in ab.items()}}
    r2 = {x["stamp"] for x in R.load_arm([2], "REF")}
    views = {"all cycles": set(), "drop the abandoned cycles": set(ab), "drop round 2 entirely": r2}
    res["sensitivity"] = {}
    for label, drop in views.items():
        a2 = keep(arms, drop)
        n2 = len(a2["REF"])
        v = {"n": n2}
        for name in ("FIX24", "FIX30", "FIX40"):
            v[name] = R.compare(a2["REF"], a2[name])
        v["FIX30_minus_FIX24"] = R.compare(a2["FIX24"], a2["FIX30"])
        res["sensitivity"][label] = v
    st = json.load(open(os.path.join(T.OUT, "status.json")))
    wall = {a[0]: [] for a in T.ARMS}
    load = {a[0]: [] for a in T.ARMS}
    tot_ab = {a[0]: 0 for a in T.ARMS}
    for r in rounds:
        for name, rec in st["rounds"][str(r)]["arms"].items():
            wall[name].append(rec["wall_s"])
            load[name].append(rec.get("load", {}).get("cpu_median"))
            tot_ab[name] += rec.get("abandoned", 0)
            assert rec.get("ok") and rec.get("attempt") == 1, (r, name, rec.get("attempt"))
    res["wall"] = {n: {"median_s": float(np.median(w)), "min_s": min(w), "max_s": max(w), "all_s": w, "abandoned": tot_ab[n],
                       "abandon_share": tot_ab[n] / 621, "V6_ok": tot_ab[n] / 621 <= T.V6_MAX_ABANDON} for n, w in wall.items()}
    res["round_wall_s"] = {str(r): st["rounds"][str(r)].get("wall_s") for r in rounds}
    json.dump(res, open(OUT_FINAL, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: res[k] for k in ("cycles", "n_star_rule", "FIX24_minus_FIX0", "abandoned_cycles")}, indent=1, sort_keys=True))
    return 0


def train_stamps():
    out = []
    for r in range(1, T.N_ROUNDS + 1):
        c = json.load(open(os.path.join(T.CHUNK_DIR, f"chunk_{r}.json")))
        out += list(c["runs"][c["run"]]["A"])
    return out


def pct(a, q):
    return float(np.percentile(np.asarray(a, dtype=float), q)) if len(a) else None


def diag():
    import cg_common as CG
    import cg_select as SEL
    import wavio
    from ldpc_decode_ctypes import LdpcDecodeLLRs
    dll = os.path.join(r"D:\Projects\claude\_qa-scratch\osd-fix-review", "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
    d = LdpcDecodeLLRs(dll, verify=True, expected_sha256=PIN, expected_shim_version=20260060, check_version=True)
    d.dll.ft8_set_decode_params(*CG.PROD_PARAMS)
    fn = d.dll.ft8_get_last_osd_diag
    fn.restype = ctypes.c_int
    P = ctypes.POINTER
    fn.argtypes = [ctypes.c_int, P(ctypes.c_int), P(ctypes.c_float), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), ctypes.c_int]
    stamps = train_stamps()
    assert len(stamps) == 621, len(stamps)
    acc = {0: [], 1: []}
    rej = {0: [0, 0], 1: [0, 0]}
    rejc = {0: [0, 0], 1: [0, 0]}
    trunc = 0
    for i, st in enumerate(stamps):
        pcm = wavio.load_cycle_pcm(os.path.join(SEL.WAV_DIR, st + ".wav"))
        for sw in (0, 1):
            d.dll.ft8_set_osd_sign_fix(sw)
            if d.decode_all(pcm) is None:
                raise SystemExit("native fault")
            nh = (ctypes.c_int * DIAG_CAP)(); cn = (ctypes.c_float * DIAG_CAP)(); dp = (ctypes.c_int * DIAG_CAP)(); ba = (ctypes.c_int * DIAG_CAP)()
            tot = ctypes.c_int(0); rn = (ctypes.c_int * PASS_CAP)(); rc_ = (ctypes.c_int * PASS_CAP)()
            n = fn(DIAG_CAP, nh, cn, dp, ba, ctypes.byref(tot), rn, rc_, PASS_CAP)
            trunc += int(tot.value > n)
            for j in range(n):
                acc[sw].append((int(nh[j]), float(cn[j]), int(ba[j])))
            for p in range(2):
                rej[sw][p] += int(rn[p]); rejc[sw][p] += int(rc_[p])
        if (i + 1) % 50 == 0:
            print(i + 1, "of", len(stamps), flush=True)
    d.dll.ft8_set_osd_sign_fix(1)
    out = {"cycles": len(stamps), "dll_sha256": PIN, "nhard_cap": "production parameters (40)", "truncated_calls": trunc}
    for sw in (0, 1):
        nhs = [a[0] for a in acc[sw]]
        bins = {"0-12": 0, "13-24": 0, "25-30": 0, "31-40": 0, ">40": 0}
        for v in nhs:
            k = "0-12" if v <= 12 else "13-24" if v <= 24 else "25-30" if v <= 30 else "31-40" if v <= 40 else ">40"
            bins[k] += 1
        out[f"switch{sw}"] = {"accepts_total": len(nhs), "per_cycle": len(nhs) / len(stamps), "bins": bins,
                              "share_le_24": (sum(1 for v in nhs if v <= 24) / len(nhs)) if nhs else None,
                              "share_le_30": (sum(1 for v in nhs if v <= 30) / len(nhs)) if nhs else None,
                              "nhard_median": pct(nhs, 50), "nhard_p90": pct(nhs, 90), "corr_norm_median": pct([a[1] for a in acc[sw]], 50),
                              "rejects_nhard_pass0_pass1": rej[sw], "rejects_corr_pass0_pass1": rejc[sw],
                              "histogram": {str(v): nhs.count(v) for v in sorted(set(nhs))}}
    json.dump(out, open(OUT_HIST, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("cycles", "switch0", "switch1")}, indent=1, sort_keys=True)[:3000])
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit(rows() if mode == "rows" else diag() if mode == "diag" else print(__doc__) or 2)
