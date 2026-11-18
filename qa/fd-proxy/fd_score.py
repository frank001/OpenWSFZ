#!/usr/bin/env python3
"""FD-PROXY scorer (spec f01d6acd + Amendments 1 and 2): V-N, V-SEP, V-GHOST, V-BURIAL, V-AGREE, phi and its brackets, the descriptives, the section 9 add-on.

  python -I fd_score.py pilot <out.json>   dry run on the 283 PILOT cycles: judges P and the synthetic sets ONLY; no Q row is ever judged (asserted); no V-AGREE Q side
  python -I fd_score.py smoke <out.json>   the FINAL code path on pilot cycles, half of the confirmed rows relabelled as pseudo-Q (code check only)
  python -I fd_score.py final <out.json>   THE ONE SCORING RUN on the acceptance cycles; refuses to start unless this file and its siblings are committed and unmodified

HK-037: message text exists only in memory; the output is counts and rates. NFR-021: no callsign leaves this process.
All constants carry their source in the comment; every decision rule is code below (HK-021).
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import random
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fd_lib as L
import fd_pilot as FP
import fd_uprime as FU

SEED = 20261118                    # spec s4.2 / s4.3
B_BOOT = 2000                      # spec s4.3
PILOT_CYCLES = 283                 # spec s7
BATCHES_Q = (4, 5)                 # spec s2 (governed population)
BATCHES_AGREE = (2, 3, 4, 5)       # Amendment 1 C2
BAR_SEP, BAR_GHOST, BAR_BURIAL, BAR_AGREE, MIN_AGREE_N = 0.70, 0.50, 0.10, 0.10, 200   # spec s5
N_FIELD_PER = 1000                 # spec s4.2
U_SAMPLE_N = 1000                  # frozen here: seeded sample of confirmed isolated rows for s_U (and the same rows for s_H)
C_OFF_FROZEN = -0.18               # start_minus_dt_median_s from the calibration on the first 80 confirmed pilot-cycle controls (checked in final)
EXPECT = dict(rows=79401, cycles=2833, b6=3851, E_rows=85783)    # Amendment 1 C1; V-N
NC = "D:/Projects/claude/_qa-scratch/xc-live-free/ON/nc.tsv"
ALLTXT = "D:/Projects/claude/OpenWSFZ/artefacts/20261114_2312_endurance_run-gathered/wsjt-x/ALL.TXT"
WAVS = "D:/Projects/claude/OpenWSFZ/artefacts/20261114_2312_endurance_run-gathered/owsfz/wav"
DLL = "D:/Projects/claude/_qa-scratch/fd-proxy/bin/libft8.dll"
DLL_PIN = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"
SCR = "D:/Projects/claude/_qa-scratch/fd-proxy"
SETS = {"nrand_rand.txt": "c81029acaae54ef9468481fd6357deeca32e20e8a61a496e24dfa7da8d833e46", "nrand_ap.txt": "c5eff9635edec0e67cb069954e2a29ad0af6eaba3370034fa4657cf562d508d8"}
BANDS = ("<=-18", "-17..-10", ">=-9")
STRATA = [(b, k) for b in BANDS for k in ("isolated", "buried")]
SIX = {s: i for i, s in enumerate(STRATA)}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def gate_final():
    files = ["fd_lib.py", "fd_pilot.py", "fd_uprime.py", "fd_score.py"]
    st = subprocess.run(["git", "-C", HERE, "status", "--porcelain", "--"] + files, capture_output=True, text=True, check=True).stdout.strip()
    if st:
        sys.exit("FINAL REFUSED: uncommitted or modified scorer files:\n" + st)
    head = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return head


# ---------------------------------------------------------------------------------------------------------------------------------
def phi(s, p, f):
    d = s - f
    return float("nan") if d <= 0 else min(1.0, max(0.0, (s - p) / d))


def q(v, lo=2.5, hi=97.5):
    v = np.asarray([x for x in v if x == x])
    return [round(float(np.percentile(v, lo)), 4), round(float(np.percentile(v, hi)), 4)] if v.size else [None, None]


def main(mode, out_path):
    t0 = time.time()
    final = mode in ("final", "smoke")          # smoke = the final code path on PILOT cycles with half of the CONFIRMED rows relabelled as pseudo-Q (no real Q row is judged)
    head = gate_final() if mode == "final" else None
    assert sha(DLL) == DLL_PIN, "libft8.dll is not the pin"
    for fn, want in SETS.items():
        assert sha(os.path.join(SCR, fn)) == want, f"{fn} differs from the recorded hash"
    rows = FP.load_nc(NC)
    E = L.Evidence(L.load_E(ALLTXT))
    stamps = sorted({r["st"] for r in rows})
    pil = set(stamps[:PILOT_CYCLES])
    use = (set(stamps) - pil) if mode == "final" else pil          # the cycles this run is about
    res = {"mode": mode, "git_head": head, "cycles_used": len(use)}
    # ---- V-N -------------------------------------------------------------------------------------------------------------------
    vn = dict(rows=len(rows), cycles=len(stamps), b6=sum(1 for r in rows if r["k"] == 6), E_rows=E.n)
    vn["pass"] = all(vn[k] == EXPECT[k] for k in EXPECT)
    res["V_N"] = vn
    assert vn["pass"], f"V-N FAILS: {vn}"
    if mode == "smoke":
        res["SMOKE"] = "Q here is a relabelled half of the confirmed controls in the pilot cycles; the numbers mean nothing"
        rows = [r for r in rows if not (r["m"] == 0 and r["st"] in pil)]      # REAL unconfirmed rows of the pilot cycles are dropped: no real Q row is ever judged in smoke
        k_ = 0
        for r in rows:
            if r["m"] == 1 and r["st"] in pil and r["k"] in (2, 3, 4, 5):
                k_ += 1
                if k_ % 2 == 0:
                    r["m"] = 0

    # ---- row records -------------------------------------------------------------------------------------------------------------
    def rec(r, confirmed, judge):
        pr = L.parse(r["tx"])
        if pr is None:
            return None
        cyc = L.cycle_of(r["st"])
        bur = E.buried(cyc, r["f"], r["snr"], text=r["tx"], confirmed=confirmed)
        j = E.judge(cyc, float(r["f"]), r["tx"]) if judge else None
        return dict(r=r, pr=pr, cyc=cyc, st=(L.band(r["snr"]), "buried" if bur else "isolated"), j=j, kind=pr["kind"])

    Q, P, UQ = collections.defaultdict(list), collections.defaultdict(list), collections.Counter()
    nQ = collections.Counter()
    qpos = []                                            # positions of ALL unconfirmed b4+5 rows in `use` (incl. unjudgeable): geometry for the synthetic rows
    for r in rows:
        if r["st"] not in use:
            continue
        k = r["k"]
        if r["m"] == 0:
            nQ[k] += 1
            if k in BATCHES_Q:
                qpos.append((L.cycle_of(r["st"]), r["f"], r["dt"], r["st"]))
        rc = rec(r, bool(r["m"]), judge=(r["m"] == 1) or final)   # a Q row is judged ONLY in the final run
        if r["m"] == 0:
            if rc is None:
                UQ[k] += 1
            else:
                assert final or rc["j"] is None
                Q[k].append(rc)
        elif rc is not None:
            P[k].append(rc)
    res["counts"] = {"Q_unconfirmed_by_batch": dict(nQ), "Q_unjudgeable_by_batch": dict(UQ), "Q_judgeable_by_batch": {k: len(v) for k, v in Q.items()},
                     "P_judgeable_by_batch": {k: len(v) for k, v in P.items()}}
    qg = [x for k in BATCHES_Q for x in Q[k]]
    pg = [x for k in BATCHES_Q for x in P[k]]
    # Q's stratum shares (structure only)
    cnt = collections.Counter(x["st"] for x in qg)
    tot = sum(cnt.values())
    W6 = np.array([cnt.get(s, 0) / tot for s in STRATA])
    Wband = np.array([sum(cnt.get((b, k), 0) for k in ("isolated", "buried")) / tot for b in BANDS])
    res["Q_strata"] = {f"{a}|{b}": cnt.get((a, b), 0) for (a, b) in STRATA}
    res["P_strata"] = {f"{a}|{b}": v for (a, b), v in sorted(collections.Counter(x["st"] for x in pg).items())}

    def s_from(num, den, W):
        """weighted share; a stratum with no rows is dropped and the weights renormalised."""
        ok = den > 0
        return float((W[ok] * (num[ok] / den[ok])).sum() / W[ok].sum()) if ok.any() and W[ok].sum() > 0 else float("nan")

    # ---- synthetic sets ---------------------------------------------------------------------------------------------------------
    rng = random.Random(SEED)
    qpos_s = sorted(qpos)

    def place(texts):
        out = []
        for t in texts:
            c, f, dt, st = rng.choice(qpos_s)
            out.append((c, f, dt, st, t))
        return out
    texts = [ln.rstrip("\n") for fn in ("nrand_rand.txt", "nrand_ap.txt") for ln in open(os.path.join(SCR, fn), encoding="utf-8")]
    nr = place(texts)
    nr_j = [(x, E.judge(x[0], float(x[1]), x[4])) for x in nr]
    nr_judged = [(x, j) for (x, j) in nr_j if j is not None]
    f_rand_n = len(nr_judged)
    f_rand = sum(j["plausible"] for _, j in nr_judged) / f_rand_n
    res["N_RAND"] = dict(total=len(nr), unjudgeable=len(nr) - f_rand_n, n=f_rand_n, f_RAND=round(f_rand, 5),
                         C=round(sum(j["C"] for _, j in nr_judged) / f_rand_n, 4), R_fail=round(sum(not j["R"] for _, j in nr_judged) / f_rand_n, 4),
                         F_fail=round(sum(j["F"] == "FAIL" for _, j in nr_judged) / f_rand_n, 4), S_behind=round(sum(j["S"] for _, j in nr_judged) / f_rand_n, 4),
                         rule_of_three_hi=round(3.0 / f_rand_n, 4) if f_rand == 0 else None)

    # N-FIELD (source visible) and N-FIELD-MISS (source's own WSJT-X row hidden), random call-shaped values (literal); E-drawn calls descriptive
    e_calls = sorted(E.call_cycles)
    nf = {}
    for variant, calls, hide in (("visible", None, False), ("MISS", None, True), ("visible_Ecall", e_calls, False), ("MISS_Ecall", e_calls, True)):
        rg = random.Random(SEED)
        per = {}
        for field in ("B", "A", "X"):
            pool = [x for x in pg if FP.render(x["pr"], x["r"]["tx"], field, random.Random(0), calls) is not None]
            made, tries = [], 0
            while len(made) < N_FIELD_PER and pool and tries < N_FIELD_PER * 20:
                tries += 1
                x = rg.choice(pool)
                t = FP.render(x["pr"], x["r"]["tx"], field, rg, calls)
                if t is None:
                    continue
                df = rg.uniform(-FP.DF_SPREAD_HZ, FP.DF_SPREAD_HZ)
                j = E.judge(x["cyc"], x["r"]["f"] + df, t, hide=((x["r"]["tx"], x["r"]["f"]) if hide else None))
                made.append((j, abs(df) <= L.GATE_HZ))
            jj = [j for j, _ in made if j is not None]
            near = [j for j, n_ in made if j is not None and n_]
            per[field] = dict(n=len(jj), unjudgeable=len(made) - len(jj), f=round(sum(j["plausible"] for j in jj) / len(jj), 4) if jj else None,
                              within10Hz_n=len(near), within10Hz_f=round(sum(j["plausible"] for j in near) / len(near), 4) if near else None,
                              C=round(sum(j["C"] for j in jj) / len(jj), 4) if jj else None, R_fail=round(sum(not j["R"] for j in jj) / len(jj), 4) if jj else None,
                              F_fail=round(sum(j["F"] == "FAIL" for j in jj) / len(jj), 4) if jj else None, S_behind=round(sum(j["S"] for j in jj) / len(jj), 4) if jj else None)
            per[field]["_k"] = (sum(j["plausible"] for j in jj), len(jj))
        fs = [per[f]["f"] for f in per if per[f]["n"]]
        per["f_FIELD_equal_shares"] = round(sum(fs) / len(fs), 5) if fs else None
        nf[variant] = per
    f_miss, f_vis = nf["MISS"]["f_FIELD_equal_shares"], nf["visible"]["f_FIELD_equal_shares"]
    res["N_FIELD"] = {v: {k: ({a: b for a, b in d.items() if a != "_k"} if isinstance(d, dict) else d) for k, d in per.items()} for v, per in nf.items()}
    res["f"] = dict(f_RAND=round(f_rand, 5), f_NFIELD_visible=f_vis, f_MISS=f_miss)

    # ---- per-cycle aggregates for the bootstrap ---------------------------------------------------------------------------------
    cyc_list = sorted({x["cyc"] for x in qg} | {x["cyc"] for x in pg})
    cix = {c: i for i, c in enumerate(cyc_list)}
    nC = len(cyc_list)
    Pn, Pp = np.zeros((nC, 6)), np.zeros((nC, 6))
    for x in pg:
        i, s_ = cix[x["cyc"]], SIX[x["st"]]
        Pn[i, s_] += 1
        Pp[i, s_] += x["j"]["plausible"] if x["j"] else 0
    Qn, Qp = np.zeros(nC), np.zeros(nC)
    if final:
        for x in qg:
            Qn[cix[x["cyc"]]] += 1
            Qp[cix[x["cyc"]]] += x["j"]["plausible"]
    # ---- V-SEP, V-GHOST, V-BURIAL (controls: allowed in pilot mode, on the pilot cycles) ---------------------------------------------
    brng = np.random.default_rng(SEED)
    idxs = [brng.integers(0, nC, nC) for _ in range(B_BOOT)]
    s_pt = s_from(Pp.sum(0), Pn.sum(0), W6)
    sep, gho, bur = [], [], []
    nj_f = f_rand_n
    for ix in idxs:
        pn, pp = Pn[ix].sum(0), Pp[ix].sum(0)
        sb = s_from(pp, pn, W6)
        sep.append(sb - brng.binomial(nj_f, f_rand) / nj_f)
        kk = nf["MISS"]
        fm = np.mean([brng.binomial(kk[fd]["_k"][1], kk[fd]["_k"][0] / kk[fd]["_k"][1]) / kk[fd]["_k"][1] for fd in ("B", "A", "X") if kk[fd]["n"]])
        gho.append(sb - fm)
        # burial: each side weighted to Q's SNR bands
        iso = np.array([[pn[SIX[(b, "isolated")]], pp[SIX[(b, "isolated")]]] for b in BANDS])
        bu = np.array([[pn[SIX[(b, "buried")]], pp[SIX[(b, "buried")]]] for b in BANDS])
        si, sbu = s_from(iso[:, 1], iso[:, 0], Wband), s_from(bu[:, 1], bu[:, 0], Wband)
        bur.append(si - sbu)
    iso_pt = np.array([[Pn[:, SIX[(b, "isolated")]].sum(), Pp[:, SIX[(b, "isolated")]].sum()] for b in BANDS])
    bu_pt = np.array([[Pn[:, SIX[(b, "buried")]].sum(), Pp[:, SIX[(b, "buried")]].sum()] for b in BANDS])
    s_iso, s_bur = s_from(iso_pt[:, 1], iso_pt[:, 0], Wband), s_from(bu_pt[:, 1], bu_pt[:, 0], Wband)
    res["s_weighted"] = round(s_pt, 4)
    res["V_SEP"] = dict(point=round(s_pt - f_rand, 4), ci=q(sep), bar=BAR_SEP, ci_lo_ge_bar=(q(sep)[0] is not None and q(sep)[0] >= BAR_SEP))
    res["V_GHOST"] = dict(point=round(s_pt - f_miss, 4), ci=q(gho), bar=BAR_GHOST, ci_lo_ge_bar=(q(gho)[0] is not None and q(gho)[0] >= BAR_GHOST))
    res["V_BURIAL"] = dict(s_isolated=round(s_iso, 4), s_buried=round(s_bur, 4), diff=round(s_iso - s_bur, 4), ci=q(bur), bar=BAR_BURIAL, ci_hi_le_bar=(q(bur)[1] is not None and q(bur)[1] <= BAR_BURIAL),
                           P_iso_n=int(iso_pt[:, 0].sum()), P_buried_n=int(bu_pt[:, 0].sum()))
    if not final:
        res["note"] = "PILOT-MODE dry run: Q never judged; phi, V-AGREE and the descriptives on Q are NOT computed"
        res["run_seconds"] = round(time.time() - t0, 1)
        json.dump(res, open(out_path, "w"), indent=1)
        print(json.dumps(res, indent=1))
        return

    # =================================== FINAL ONLY: Q is judged from here on ======================================================
    nJ, nU, nQtot = len(qg), sum(UQ[k] for k in BATCHES_Q), sum(nQ[k] for k in BATCHES_Q)
    p_pt = float(Qp.sum() / Qn.sum())
    f_lo, f_hi = min(f_rand, f_vis), max(f_rand, f_miss)           # Amendment 2: phi_lo = phi(min(f_RAND, f_NFIELD)), phi_hi = phi(max(f_RAND, f_MISS))
    ncyc_run = len(use)

    def share_all(ph, lo):
        return (ph * nJ / nQtot) if lo else ((ph * nJ + nU) / nQtot)
    lo_pt, hi_pt = phi(s_pt, p_pt, f_lo), phi(s_pt, p_pt, f_hi)
    bl, bh, fl, fh = [], [], [], []
    kv, km = nf["visible"], nf["MISS"]
    for ix in idxs:
        pn, pp = Pn[ix].sum(0), Pp[ix].sum(0)
        sb = s_from(pp, pn, W6)
        pb = Qp[ix].sum() / max(Qn[ix].sum(), 1)
        fr = brng.binomial(nj_f, f_rand) / nj_f
        fvv = np.mean([brng.binomial(kv[fd]["_k"][1], kv[fd]["_k"][0] / kv[fd]["_k"][1]) / kv[fd]["_k"][1] for fd in ("B", "A", "X") if kv[fd]["n"]])
        fmm = np.mean([brng.binomial(km[fd]["_k"][1], km[fd]["_k"][0] / km[fd]["_k"][1]) / km[fd]["_k"][1] for fd in ("B", "A", "X") if km[fd]["n"]])
        a, b = phi(sb, pb, min(fr, fvv)), phi(sb, pb, max(fr, fmm))
        bl.append(a); bh.append(b)
        fl.append(share_all(a, True) * nQtot / ncyc_run); fh.append(share_all(b, False) * nQtot / ncyc_run)
    res["PHI_governed_b45"] = dict(n_Q=nQtot, n_judgeable=nJ, n_unjudgeable=nU, p_plausible_share=round(p_pt, 4), s=round(s_pt, 4), f_lo=round(f_lo, 5), f_hi=round(f_hi, 5),
                                   phi_lo=round(lo_pt, 4), phi_lo_ci=q(bl), phi_hi=round(hi_pt, 4), phi_hi_ci=q(bh),
                                   false_share_all_Q_lower=round(share_all(lo_pt, True), 4), false_share_all_Q_upper=round(share_all(hi_pt, False), 4),
                                   false_per_cycle_lower=round(share_all(lo_pt, True) * nQtot / ncyc_run, 4), false_per_cycle_lower_ci=q(fl),
                                   false_per_cycle_upper=round(share_all(hi_pt, False) * nQtot / ncyc_run, 4), false_per_cycle_upper_ci=q(fh),
                                   unjudgeable_share_Q=round(nU / nQtot, 4), unjudgeable_share_N_RAND=round(res["N_RAND"]["unjudgeable"] / res["N_RAND"]["total"], 4),
                                   blind_spot_X_within10Hz_MISS_f=res["N_FIELD"]["MISS"]["X"]["within10Hz_f"])

    # ---- components alone, by stratum, by kind --------------------------------------------------------------------------------------
    def comp(items):
        n = len(items)
        if not n:
            return None
        js = [x["j"] for x in items]
        return dict(n=n, plausible=round(sum(j["plausible"] for j in js) / n, 4), C=round(sum(j["C"] for j in js) / n, 4), R_fail=round(sum(not j["R"] for j in js) / n, 4),
                    F_fail=round(sum(j["F"] == "FAIL" for j in js) / n, 4), F_unseen=round(sum(j["F"] == "UNSEEN" for j in js) / n, 4), S_behind=round(sum(j["S"] for j in js) / n, 4))
    res["components_alone"] = dict(Q_b45=comp(qg), P_b45=comp(pg))
    res["by_stratum"] = {f"{a}|{b}": dict(Q=comp([x for x in qg if x["st"] == (a, b)]), P=comp([x for x in pg if x["st"] == (a, b)])) for (a, b) in STRATA}
    byk = {}
    for kd in ("CQ", "STD"):
        qk, pk = [x for x in qg if x["kind"] == kd], [x for x in pg if x["kind"] == kd]
        cq_ = collections.Counter(x["st"] for x in qk)
        Wk = np.array([cq_.get(s, 0) for s in STRATA], float)
        Wk = Wk / Wk.sum() if Wk.sum() else Wk
        pnk = np.array([sum(1 for x in pk if x["st"] == s) for s in STRATA], float)
        ppk = np.array([sum(x["j"]["plausible"] for x in pk if x["st"] == s) for s in STRATA], float)
        sk = s_from(ppk, pnk, Wk) if Wk.sum() else float("nan")
        pk_ = sum(x["j"]["plausible"] for x in qk) / len(qk) if qk else float("nan")
        byk[kd] = dict(Q_n=len(qk), P_n=len(pk), s=round(sk, 4), p=round(pk_, 4), phi_lo=round(phi(sk, pk_, f_lo), 4), phi_hi=round(phi(sk, pk_, f_hi), 4))
    res["by_kind_governed"] = byk
    # ---- per batch (descriptive; each batch on its own) -----------------------------------------------------------------------------
    pb = {}
    for k in range(1, 7):
        qk, pk = Q[k], P[k]
        if not qk or not pk:
            pb[str(k)] = dict(Q_n=len(qk), P_n=len(pk), note="no rows on one side")
            continue
        cq_ = collections.Counter(x["st"] for x in qk)
        Wk = np.array([cq_.get(s, 0) for s in STRATA], float); Wk = Wk / Wk.sum()
        pnk = np.array([sum(1 for x in pk if x["st"] == s) for s in STRATA], float)
        ppk = np.array([sum(x["j"]["plausible"] for x in pk if x["st"] == s) for s in STRATA], float)
        sk = s_from(ppk, pnk, Wk)
        pp_ = sum(x["j"]["plausible"] for x in qk) / len(qk)
        nJk, nUk = len(qk), UQ[k]
        lo, hi = phi(sk, pp_, f_lo), phi(sk, pp_, f_hi)
        pb[str(k)] = dict(Q_judgeable=nJk, Q_unjudgeable=nUk, P_n=len(pk), s=round(sk, 4), p=round(pp_, 4), phi_lo=round(lo, 4), phi_hi=round(hi, 4),
                          false_share_lower=round(lo * nJk / (nJk + nUk), 4), false_share_upper=round((hi * nJk + nUk) / (nJk + nUk), 4),
                          false_per_cycle_lower=round(lo * nJk / ncyc_run, 4), false_per_cycle_upper=round((hi * nJk + nUk) / ncyc_run, 4),
                          components_Q=comp(qk), components_P=comp(pk),
                          note="batch 6: only C and S are informative (R and F pass by construction)" if k == 6 else None)
    res["per_batch"] = pb
    # ---- section 9 add-on: Q failing R whose SENDER is in no E row at all, per batch ---------------------------------------------------
    s9 = {}
    for k in range(1, 7):
        rf = [x for x in Q[k] if not x["j"]["R"]]
        none = [x for x in rf if not E.call_cycles.get(x["pr"]["B"])]
        s9[str(k)] = dict(Q_judgeable=len(Q[k]), R_fail=len(rf), sender_in_no_E_row=len(none), share_of_R_fail=round(len(none) / len(rf), 4) if rf else None)
    rf = [x for k in BATCHES_Q for x in Q[k] if not x["j"]["R"]]
    none = [x for x in rf if not E.call_cycles.get(x["pr"]["B"])]
    s9["governed_b45"] = dict(Q_judgeable=nJ, R_fail=len(rf), sender_in_no_E_row=len(none), share_of_R_fail=round(len(none) / len(rf), 4) if rf else None)
    res["sec9_only_we_decode"] = s9

    # ---- V-AGREE (Amendment 1 C2: batches 2-5; isolated unconfirmed judgeable) ----------------------------------------------------------
    X = [x for k in BATCHES_AGREE for x in Q[k] if x["st"][1] == "isolated"]
    Pi_all = [x for k in BATCHES_AGREE for x in P[k] if x["st"][1] == "isolated"]
    srng = random.Random(SEED)
    Pi = srng.sample(Pi_all, min(U_SAMPLE_N, len(Pi_all)))
    T = FU.Tone(WAVS, DLL)
    ctl = sorted([(r["st"], r["f"], r["dt"], r["tx"]) for r in rows if r["m"] == 1 and r["st"] in pil and r["k"] == 1], key=lambda t: (t[0], t[1]))   # batch 1 is never relabelled
    cal = T.calibrate(ctl)
    if mode == "final":
        assert abs(cal["start_minus_dt_median_s"] - C_OFF_FROZEN) < 1e-9, f"calibration moved: {cal}"
    res["U_calibration"] = cal

    def present(stamp, f, dt, text):
        v = T.share(stamp, f, dt, text)
        return 0 if v is None else int(v >= FU.T_FROZEN)       # unencodable counts as not shown present (cf_uprime's conservative rule)
    xs = [dict(cyc=x["cyc"], band=x["st"][0], h=int(x["j"]["plausible"]), u=present(x["r"]["st"], x["r"]["f"], x["r"]["dt"], x["r"]["tx"])) for x in X]
    ps = [dict(cyc=x["cyc"], band=x["st"][0], h=int(x["j"]["plausible"]), u=present(x["r"]["st"], x["r"]["f"], x["r"]["dt"], x["r"]["tx"])) for x in Pi]
    # synthetic noise rows at ISOLATED unconfirmed positions of X (cycle, freq, dt of an X row)
    xpos = [(x["cyc"], x["r"]["f"], x["r"]["dt"], x["r"]["st"]) for x in X]
    r2 = random.Random(SEED + 1)
    nri = []
    for t in texts:
        c, f, dt, st = r2.choice(xpos)
        j = E.judge(c, float(f), t)
        if j is None:
            continue
        nri.append((j["plausible"], present(st, f, dt, t)))
    nri_n = len(nri)
    fH = sum(a for a, _ in nri) / nri_n
    fU = sum(b for _, b in nri) / nri_n
    # (per-band weights from X)
    cb = collections.Counter(x["band"] for x in xs)
    Wb = np.array([cb.get(b, 0) for b in BANDS], float); Wb = Wb / Wb.sum()

    def s_band(items, key):
        n = np.array([sum(1 for x in items if x["band"] == b) for b in BANDS], float)
        v = np.array([sum(x[key] for x in items if x["band"] == b) for b in BANDS], float)
        return s_from(v, n, Wb)
    pH, pU = sum(x["h"] for x in xs) / len(xs), sum(x["u"] for x in xs) / len(xs)
    sH, sU = s_band(ps, "h"), s_band(ps, "u")
    phiH, phiU = phi(sH, pH, fH), phi(sU, pU, fU)
    # paired cycle bootstrap over X and the control sample; f binomial
    xc = collections.defaultdict(list)
    for x in xs:
        xc[x["cyc"]].append(x)
    pc = collections.defaultdict(list)
    for x in ps:
        pc[x["cyc"]].append(x)
    allc = sorted(set(xc) | set(pc))
    arng = np.random.default_rng(SEED + 2)
    dl = []
    for _ in range(B_BOOT):
        pick = arng.integers(0, len(allc), len(allc))
        xb = [x for i in pick for x in xc.get(allc[i], ())]
        pb_ = [x for i in pick for x in pc.get(allc[i], ())]
        if not xb or not pb_:
            continue
        fh_, fu_ = arng.binomial(nri_n, fH) / nri_n, arng.binomial(nri_n, fU) / nri_n
        dl.append(phi(s_band(pb_, "h"), sum(x["h"] for x in xb) / len(xb), fh_) - phi(s_band(pb_, "u"), sum(x["u"] for x in xb) / len(xb), fu_))
    ci = q(dl)
    n_x = len(xs)
    agree = dict(n_X=n_x, n_controls_sample=len(ps), n_synthetic_judgeable=nri_n, p_H=round(pH, 4), p_U=round(pU, 4), s_H=round(sH, 4), s_U=round(sU, 4), f_H=round(fH, 4), f_U=round(fU, 4),
                 phi_H=round(phiH, 4), phi_U=round(phiU, 4), diff=round(phiH - phiU, 4), ci=ci, bar=BAR_AGREE, min_n=MIN_AGREE_N)
    agree["status"] = "UNDERPOWERED" if n_x < MIN_AGREE_N else ("INSIDE" if ci[0] is not None and ci[0] >= -BAR_AGREE and ci[1] <= BAR_AGREE else
                                                                 ("OUTSIDE" if ci[0] is not None and (ci[0] > BAR_AGREE or ci[1] < -BAR_AGREE) else "STRADDLES"))
    res["V_AGREE"] = agree
    # descriptive: U' vs H phi on BURIAL-class unconfirmed rows of the governed batches (U' blind under burial: how far the estimate moves); s and f from the isolated controls
    Xb = [x for x in qg if x["st"][1] == "buried"]
    xbs = [dict(h=int(x["j"]["plausible"]), u=present(x["r"]["st"], x["r"]["f"], x["r"]["dt"], x["r"]["tx"])) for x in Xb]
    if xbs:
        pHb, pUb = sum(x["h"] for x in xbs) / len(xbs), sum(x["u"] for x in xbs) / len(xbs)
        res["descriptive_buried_unconfirmed_b45"] = dict(n=len(xbs), p_H=round(pHb, 4), p_U=round(pUb, 4), phi_H=round(phi(sH, pHb, fH), 4), phi_U=round(phi(sU, pUb, fU), 4),
                                                         note="s and f from the isolated controls; descriptive only, no re-reading of any verdict")

    # ---- decision (spec s6, first match wins; code, not prose) ------------------------------------------------------------------------
    v_sep, v_gho, v_bur = res["V_SEP"]["ci_lo_ge_bar"], res["V_GHOST"]["ci_lo_ge_bar"], res["V_BURIAL"]["ci_hi_le_bar"]
    st = agree["status"]
    if not vn["pass"]:
        out = "VOID"
    elif not v_sep:
        out = "BLIND"
    elif not v_bur:
        out = "BURIAL-BIASED"
    elif st == "OUTSIDE":
        out = "DISAGREE"
    elif not v_gho:
        out = "GHOST-BLIND"
    elif st == "INSIDE":
        out = "VALID"
    else:
        out = "PROVISIONAL"
    res["OUTCOME"] = out
    res["run_seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(out_path, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("pilot", "smoke", "final"):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
