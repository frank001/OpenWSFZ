#!/usr/bin/env python3
"""XS-TEMPLATE scorer (angle G, Stage 1).  Spec arch/exchange-step-prior 982ffb45 + Amendment 1 (06198a8d: window +-3.125 Hz x +-0.20 s, rows outside NOT TESTABLE).  QA tooling: no src/ or native/ change.
Detector reused unchanged from XC-TEMPLATE (qa/xc-template/xt_lib.py; coherent_extract.downconvert_decimate / correlate_symbols, coherent_extract.py:125 / :142); here the search runs over a SET of templates sharing one correlation per position.
HK-037: message text is read in this process for callsigns, texts and tones only; every file written holds numbers, stamp/index keys and tone lists (working files only in _qa-scratch\\xs-template, KEPT).

    python -I xs_score.py selftest
    python -I xs_score.py prep [plumb]    rows (S, P) with their template sets, the N-OPP pool, buffer paths, the pilot draw (seed 20261116)            -> frozen/xs_tasks.json   ('plumb' = a throw-away run on the partial capture)
    python -I xs_score.py pilot           30 S + 60 P + 1,000 N-OPP template tests, excluded from acceptance; timing; the dt-mapping check             -> pilot.json
    python -I xs_score.py null            the acceptance N-OPP tests: T_E per variant (V-LOW, V-ALL), CI, split-half, V-NULL-N                          -> nulls.json, frozen/te.json
    python -I xs_score.py own             REFUSES without frozen/te.json: S (residual primary, O descriptive) and P (O primary, residual descriptive)   -> own.json
    python -I xs_score.py analyse         the rows and the decision table (spec section 5)                                                              -> result.json

FROZEN (as code):
  Start-sample mapping for OUR dt: the detector places the start at round((dt_c + e + 0.48) * 2000) with dt_c in WSJT-X's dt convention (0.48 = TA-CHECK's frozen start-minus-dt). Our decoder's dt is WSJT-X's plus 0.600 s (XC-LIVE, COR median),
    so the centre passed is dt_c = dt_ours - 0.600; equivalently start = dt_ours - 0.120 s.  CHECK (Architect, A1.2): on the pilot's P detections the argmax must lie inside the truth gate in >= 95 %, else STOP.
  Window: f_c +-3.0 Hz in 0.5 Hz steps (13, inside the +-3.125 Hz gate), dt_c +-0.20 s in 0.01 s steps (41).  Truth gate on the argmax: +-3.125 Hz / +-0.12 s of WSJT-X's own position (the dt in WSJT-X's convention).
  S_E per template = mean over 79 symbols of P[known tone] / mean_b P (xt_lib.s_e).  A set's output = the template with the highest S_E*.
  DETECTED (S and P rows) iff the winner is the TRUE template, S* >= T_E, and the winner's argmax is inside the truth gate.  W event iff the winner is NOT the true template and S* >= T_E.
  Variants: V-LOW carries only K-low priors (sets of <= 3 templates) with T_E,low from the K-low null at FA*_low = 0.021 / K_low;  V-ALL carries every prior with T_E,all at FA*_all = 0.021 / K_all (K from step 0: 19 and 1018).
  Rows (spec section 4/5): V-POS = D(P_low on O at T_E,low) CI_lo >= 0.80 else VOID;  V-NULL-N per variant: n(N-OPP template tests) >= 3 / FA*;  V-SIB = W/(1-W) x detected S per cycle <= 0.021 (CI_hi of W);
  G(v) = detected share among the acceptance testable S rows x T0 (testable / n_ref); decision order: CLOSE-EARLY (step 0), VOID(V-POS), CLOSE (CI_hi(G) < 0.4 pp for every variant), VOID(V-NULL-N V-LOW), GATE-STUDY, BUILD-WORTH (V-LOW if both), BETWEEN."""
from __future__ import annotations

import collections
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "xc-template"), os.path.join(HERE, "..", "xc-prior"), os.path.join(HERE, "..", "ta-check"), os.path.join(HERE, "..", "endurance"), os.path.join(HERE, "..", "rr-study", "n2-coherent-llr-extractor")):
    sys.path.insert(0, p)
import xt_lib as L          # noqa: E402
import xs_count as X        # noqa: E402
import xs_template_step0 as S0   # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/xs-template"
CAP = OUT + "/cap_run/cap"
FS_OUT = 2000
CALIB_S = 0.48
DT_OFFSET_S = 0.600
DF_STEPS = [k * 0.5 for k in range(-6, 7)]
DT_STEPS = [k * 0.01 for k in range(-20, 21)]
WIN_DF_HZ, WIN_DT_S = 3.125, 0.20
GATE_DF_HZ, GATE_DT_S = 3.125, 0.12
FA_BUDGET = 0.021
V_POS_MIN = 0.80
BAR_PP = 0.4
ARGMAX_INSIDE_MIN = 0.95
SEED, B_BOOT = 20261116, 2000
N_PILOT_S, N_PILOT_P, N_PILOT_NULL = 30, 60, 1000
K_LOW_MEDIAN, K_ALL_MEDIAN = 19.0, 1018.0           # step 0 (xs_step0.json): the medians per cycle
NULL_FACTOR = 10                                     # acceptance null size = NULL_FACTOR x the rule-of-three floor (3 / FA*); raised from 3 to 10 after the pilot showed the cost is minutes, BEFORE the freeze and with no S score read
N_REF, N_CYC = 85783, 2833
assert (WIN_DF_HZ, WIN_DT_S, GATE_DF_HZ, GATE_DT_S, FA_BUDGET, V_POS_MIN, BAR_PP, SEED, B_BOOT, CALIB_S, DT_OFFSET_S) == (3.125, 0.2, 3.125, 0.12, 0.021, 0.8, 0.4, 20261116, 2000, 0.48, 0.6)
assert len(DF_STEPS) == 13 and len(DT_STEPS) == 41 and max(DF_STEPS) <= WIN_DF_HZ and max(DT_STEPS) <= WIN_DT_S + 1e-9
_W = {}


# ------------------------------------------------------------------------------------------------ detector (set search)
def s_e_set(Xm: np.ndarray, tm: np.ndarray) -> np.ndarray:
    """S_E of every template (rows of tm, shape (T, 79)) on the (79, 8) correlations Xm; the same formula as xt_lib.s_e."""
    P = Xm.real ** 2 + Xm.imag ** 2
    den = P.sum(axis=1) / 8.0
    num = P[np.arange(79)[None, :], tm]
    r = np.where(den[None, :] > 0, num / np.where(den[None, :] > 0, den[None, :], 1.0), 1.0)
    return r.mean(axis=1)


def search_set(CE, pcm, f_c, dt_c, tm):
    """per template: S_E*, argmax f and dt, over the frozen window.  dt_c is in WSJT-X's dt convention (the caller subtracts the 0.600 s offset from OUR dt)."""
    bb = CE.downconvert_decimate(pcm, float(f_c))
    T = tm.shape[0]
    best, af, adt = np.full(T, -1.0), np.zeros(T), np.zeros(T)
    for d in DF_STEPS:
        sb = L.shift_baseband(bb, d)
        for e in DT_STEPS:
            smp = int(round((dt_c + e + CALIB_S) * FS_OUT))
            v = s_e_set(CE.correlate_symbols(sb, smp), tm)
            up = v > best
            best[up], af[up], adt[up] = v[up], f_c + d, dt_c + e
    return best, af, adt


def inside_truth(af, adt, own):
    return abs(af - own[0]) <= GATE_DF_HZ + 1e-9 and abs(adt - own[1]) <= GATE_DT_S + 1e-9


def verdict(S, af, adt, true_idx, own, t_e):
    """-> (detected, wrong_message_win, best index, best S): the frozen predicates."""
    b = int(np.argmax(S))
    top = float(S[b])
    det = bool(b == true_idx and top >= t_e and own is not None and inside_truth(af[b], adt[b], own))
    wrong = bool(b != true_idx and top >= t_e)
    return det, wrong, b, top


# ------------------------------------------------------------------------------------------------ workers
def _init():
    import coherent_extract as CE
    _W["CE"] = CE
    _W["buf"] = {}


def _load(path):
    b = _W["buf"]
    if path not in b:
        if len(b) > 4:
            b.clear()
        b[path] = np.fromfile(path, dtype=np.float32)
    return b[path]


def work(task):
    pcm = _load(task["path"])
    tm = np.asarray(task["tones"], dtype=np.int64)
    S, af, adt = search_set(_W["CE"], pcm, task["f"], task["dt"], tm)
    out = {"S": [round(float(x), 5) for x in S]}
    b = int(np.argmax(S))
    out.update({"best": b, "top": float(S[b]), "af": float(af[b]), "adt": float(adt[b])})
    t = task.get("true", -1)
    if t is not None and t >= 0:
        out.update({"s_true": float(S[t]), "af_true": float(af[t]), "adt_true": float(adt[t])})
    return out


def run_tasks(tasks, workers=8):
    with mp.Pool(workers, initializer=_init) as pool:
        return list(pool.imap(work, tasks, chunksize=8))


# ------------------------------------------------------------------------------------------------ templates
def payload_texts(tp, f1, f2, sets):
    """the predicted texts 'F1 F2 payload' for the reply set (sets = 'N' or 'N2') of a previous payload type tp."""
    reps = [f"{v:+03d}" for v in range(X.REP_LO, X.REP_HI + 1)]
    rreps = ["R" + r for r in reps]
    if sets == "N":
        pays = reps if tp in ("grid", "empty") else rreps if tp == "report" else list(X.SIGNOFF) if tp == "rreport" else ["73"] if tp in ("RR73", "RRR") else []
    else:
        pays = rreps if tp in ("grid", "empty") else list(X.SIGNOFF) if tp == "report" else ["73"] if tp == "rreport" else []
    return [f"{f1} {f2} {p}" for p in pays]


def payload_str(tu, vu):
    return {"report": f"{vu:+03d}" if vu is not None else None, "rreport": f"R{vu:+03d}" if vu is not None else None}.get(tu, tu)


def prep(plumb=False):
    out_dir = OUT + ("/plumb" if plumb else "/frozen")
    os.makedirs(out_dir, exist_ok=True)
    import tc_groups as G
    F, _ = G.U.load_instrument()
    enc = F.encoder(G.DLL)
    cache = {}

    def tones_of(text):
        if text not in cache:
            t = enc(text)
            cache[text] = None if t is None else [int(x) for x in t]
        return cache[text]

    stamps, pc, ext = S0.load2()
    S0.prime_truth()
    n = len(pc)
    idx = S0.known_index(pc, ext)
    lv = {}
    for l in open(CAP + "/capture_index.tsv", encoding="utf-8"):
        q = l.rstrip("\n").split("\t")
        if len(q) >= 11:
            lv[q[0]] = q[9]
    have = {s for s in stamps if s in lv and os.path.isfile(f"{CAP}/buffers/{s}_{lv[s]}.f32") and os.path.isfile(f"{CAP}/buffers/{s}_O.f32")}
    resid = {s: f"{CAP}/buffers/{s}_{lv[s]}.f32" for s in have}
    orig = {s: f"{CAP}/buffers/{s}_O.f32" for s in have}
    skipped = collections.Counter()

    def mk_row(i, j, cls, f1, f2, tp, tu, vu, centre, kind):
        sets = "N" if cls == "S1" else "N2"
        texts = payload_texts(tp, f1, f2, sets)
        true_pay = payload_str(tu, vu)
        true = next((k for k, t in enumerate(texts) if t.split()[2] == true_pay), -1)
        tn = [tones_of(t) for t in texts]
        ok = [k for k, t in enumerate(tn) if t is not None]
        if true < 0 or tn[true] is None or len(ok) < 1:
            skipped[kind + "_true_not_in_set_or_unencodable"] += 1
            return None
        tn2 = [tn[k] for k in ok]
        return {"i": i, "j": j, "stamp": stamps[i], "cls": cls, "tclass": "low" if len(texts) <= X.K_LOW_MAX else "high", "nset": len(tn2), "tones": tn2, "true": ok.index(true), "snr": pc[i][j][0],
                "f": centre[0], "dt": centre[1] - DT_OFFSET_S, "own": [pc[i][j][1], S0._TRUTH_DT[(i, j)]]}

    S, P = [], []
    rows = S0.s_rows(pc, ext)
    for i, j, cls, y, jj, cue in rows:
        if stamps[i] not in have:
            skipped["S_no_buffer"] += 1
            continue
        _, f1, f2, tu, vu = pc[i][j][4]
        if cls == "S2":
            cp = ext[i - 2][jj]
            centre = (cp[1], cp[2])
        else:
            pos, _ = S0.lookup(idx, i, y, S0.MAIN_LOOKBACK)
            if pos is None:
                skipped["S1_no_F_KNOWN"] += 1
                continue
            centre = pos
        if abs(pc[i][j][1] - centre[0]) > WIN_DF_HZ or abs(S0._TRUTH_DT[(i, j)] - (centre[1] - DT_OFFSET_S)) > WIN_DT_S:
            skipped["S_outside_window_not_testable"] += 1
            continue
        r = mk_row(i, j, cls, f1, f2, cue[3], tu, vu, centre, "S")
        if r:
            S.append(r)
    for i in range(1, n):                                          # P: matched on-script replies to a matched cue at t-15, F-KNOWN replier, inside the window
        if stamps[i] not in have:
            continue
        for j, (snr, f, text, m, p) in enumerate(pc[i]):
            if not m or p[0] != "ok":
                continue
            cue = next((pp for _, _, _, pm, pp in pc[i - 1] if pm and pp[0] == "ok" and pp[1] == p[2] and pp[2] == p[1] and X.in_n(pp[3], p[3], p[4])), None)
            if cue is None:
                continue
            pos, _ = S0.lookup(idx, i, p[2], S0.MAIN_LOOKBACK)
            if pos is None:
                skipped["P_no_F_KNOWN"] += 1
                continue
            if abs(f - pos[0]) > WIN_DF_HZ or abs(S0._TRUTH_DT[(i, j)] - (pos[1] - DT_OFFSET_S)) > WIN_DT_S:
                skipped["P_outside_window_not_testable"] += 1
                continue
            r = mk_row(i, j, "S1", p[1], p[2], cue[3], p[3], p[4], pos, "P")
            if r:
                P.append(r)
    # the N-OPP pool, LIGHT: every prior (matched cue) with its predicted set, to be tested at the opposite-parity cycles; the tones are built only for the SELECTED sets (materialize)
    NS = []
    for c in range(1, n - 3):
        for jj, (snr, pf, pt, pm, pp) in enumerate(pc[c]):
            if not pm or pp[0] != "ok":
                continue
            for sets, repl_f1, repl_f2, test_cycles in (("N", pp[2], pp[1], (c, c + 2)), ("N2", pp[1], pp[2], (c + 1, c + 3))):
                nt = len(payload_texts(pp[3], repl_f1, repl_f2, sets))
                if nt == 0:
                    continue
                if sets == "N":
                    centre, _ = S0.lookup(idx, c + 1, pp[1], S0.MAIN_LOOKBACK)      # the replier = the cue's addressee (pp[1]); known before the reply cycle t = c + 1
                    if centre is None:
                        continue
                else:
                    centre = (ext[c][jj][1], ext[c][jj][2])
                for k in test_cycles:
                    if stamps[k] in have:
                        NS.append({"cyc": k, "stamp": stamps[k], "c": c, "jj": jj, "sets": sets, "f1": repl_f1, "f2": repl_f2, "tp": pp[3], "tclass": "low" if nt <= X.K_LOW_MAX else "high", "nset": nt,
                                   "f": centre[0], "dt": centre[1] - DT_OFFSET_S})
    rng = np.random.default_rng(SEED)
    perm_s = [int(x) for x in rng.permutation(len(S))]
    perm_p = [int(x) for x in rng.permutation(len(P))]
    perm_n = [int(x) for x in rng.permutation(len(NS))]
    pil_s, pil_p = sorted(perm_s[:N_PILOT_S]), sorted(perm_p[:N_PILOT_P])
    pil_n, tot = [], 0
    for k in perm_n:
        if tot >= N_PILOT_NULL:
            break
        pil_n.append(k)
        tot += NS[k]["nset"]
    summ = {"plumb": plumb, "cycles_with_buffers": len(have), "S_rows": len(S), "S_low": sum(1 for r in S if r["tclass"] == "low"), "P_rows": len(P), "P_low": sum(1 for r in P if r["tclass"] == "low"),
            "null_sets": len(NS), "null_templates_before_drops": sum(r["nset"] for r in NS), "null_templates_low_before_drops": sum(r["nset"] for r in NS if r["tclass"] == "low"), "skipped": dict(skipped),
            "pilot": {"S": len(pil_s), "P": len(pil_p), "null_sets": len(pil_n), "null_templates": tot, "seed": SEED}}
    json.dump({"S": S, "P": P, "NS": NS, "pilot": {"S": pil_s, "P": pil_p, "NS": pil_n}, "perm_n": perm_n, "stamps": stamps, "resid": resid, "orig": orig, "summary": summ}, open(out_dir + "/xs_tasks.json", "w"))
    print(json.dumps(summ, indent=1))


def make_ctx():
    """the encoder and, per cycle, the texts WSJT-X holds (a test is dropped where WSJT-X's ALL.TXT has that text in that cycle)."""
    import tc_groups as G
    F, _ = G.U.load_instrument()
    enc = F.encoder(G.DLL)
    cache = {}

    def tones_of(text):
        if text not in cache:
            t = enc(text)
            cache[text] = None if t is None else [int(x) for x in t]
        return cache[text]
    pc = S0.load2()[1]
    return {"tones_of": tones_of, "cyc_texts": [set(r[2] for r in rows) for rows in pc]}


def materialize(e, ctx):
    texts = payload_texts(e["tp"], e["f1"], e["f2"], e["sets"])
    keep = [(t, ctx["tones_of"](t)) for t in texts if t not in ctx["cyc_texts"][e["cyc"]]]
    dropped = len(texts) - len(keep)
    keep = [tn for _, tn in keep if tn is not None]
    return {**e, "tones": keep, "nset": len(keep), "dropped_text_present": dropped}


def mk(row, path, own=True):
    return {"path": path, "f": row["f"], "dt": row["dt"], "tones": row["tones"], "true": row.get("true", -1), "own": row["own"] if own else None}


def threshold_and_ci(scores, cycles, fa, ncyc):
    te = L.threshold_te(scores, fa)
    idx = L.boot_idx(ncyc, B_BOOT, SEED)
    bt = L.boot_te(scores, cycles, ncyc, fa, idx)
    return te, L.ci(bt), L.split_half(scores, cycles, fa)


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage == "selftest":
        sys.exit(selftest())
    if stage not in ("prep", "pilot", "pilotreport", "null", "own", "analyse"):
        sys.exit(__doc__)
    os.makedirs(OUT + "/frozen", exist_ok=True)
    if stage == "prep":
        prep(len(sys.argv) > 2 and sys.argv[2] == "plumb")
        return
    plumb = sys.argv[-1] == "plumb"
    T = json.load(open(OUT + ("/plumb" if plumb else "/frozen") + "/xs_tasks.json"))
    S, P, NS, pil, resid, orig = T["S"], T["P"], T["NS"], T["pilot"], T["resid"], T["orig"]
    ncyc = len(T["stamps"])
    if stage == "pilot":
        t0 = time.time()
        s = [S[i] for i in pil["S"]]
        pp = [P[i] for i in pil["P"]]
        ctx = make_ctx()
        nl = [m for m in (materialize(NS[i], ctx) for i in pil["NS"]) if m["nset"] > 0]
        tasks = [mk(r, resid[r["stamp"]]) for r in s] + [mk(r, orig[r["stamp"]]) for r in s] + [mk(r, orig[r["stamp"]]) for r in pp] + [mk(r, resid[r["stamp"]]) for r in pp] + [mk(r, resid[r["stamp"]], own=False) for r in nl]
        res = run_tasks(tasks)
        a, b = len(s), len(pp)
        out = {"S_resid": res[:a], "S_O": res[a:2 * a], "P_O": res[2 * a:2 * a + b], "P_resid": res[2 * a + b:2 * a + 2 * b], "null": res[2 * a + 2 * b:], "seconds": time.time() - t0, "tasks": len(tasks),
               "null_templates": sum(r["nset"] for r in nl)}
        json.dump(out, open(OUT + ("/plumb/pilot.json" if plumb else "/pilot.json"), "w"))
        print("pilot tasks", len(tasks), "in", round(out["seconds"], 1), "s")
        return
    if stage == "pilotreport":
        pilot_report(T, plumb)
        return
    pil_ns = set(pil["NS"])
    if stage == "null":
        need_low, need_all = NULL_FACTOR * 3 / (FA_BUDGET / K_LOW_MEDIAN), NULL_FACTOR * 3 / (FA_BUDGET / K_ALL_MEDIAN)
        pool_all = [k for k in T["perm_n"] if k not in pil_ns]
        sel_all, tot = [], 0
        for k in pool_all:
            if tot >= need_all:
                break
            sel_all.append(k)
            tot += NS[k]["nset"]
        sel_low, totl = [], 0
        for k in pool_all:
            if totl >= need_low:
                break
            if NS[k]["tclass"] == "low":
                sel_low.append(k)
                totl += NS[k]["nset"]
        both = sorted(set(sel_all) | set(sel_low))
        ctx = make_ctx()
        mat = {k: materialize(NS[k], ctx) for k in both}
        both = [k for k in both if mat[k]["nset"] > 0]
        res = dict(zip(both, run_tasks([mk(mat[k], resid[mat[k]["stamp"]], own=False) for k in both])))
        def pooled(sel):
            sc, cy = [], []
            for k in sel:
                if k in res:
                    sc += res[k]["S"]
                    cy += [mat[k]["cyc"]] * mat[k]["nset"]
            return np.asarray(sc), np.asarray(cy)
        out = {}
        for name, sel, kmed in (("V-LOW", sel_low, K_LOW_MEDIAN), ("V-ALL", sel_all, K_ALL_MEDIAN)):
            sc, cy = pooled(sel)
            fa = FA_BUDGET / kmed
            te, ci, sh = threshold_and_ci(sc, cy, fa, ncyc)
            out[name] = {"T_E": te, "T_E_CI": ci, "split_half": sh, "FA_star": fa, "n_null_templates": int(sc.size), "V_NULL_N": {"floor": 3.0 / fa, "PASS": bool(sc.size >= 3.0 / fa)}, "exceedance_at_T_E": L.exceed(sc, te),
                         "null_S_quantiles_50_90_99_99.9_max": [float(x) for x in np.percentile(sc, [50, 90, 99, 99.9, 100])]}
        json.dump(out, open(OUT + "/frozen/te.json", "w"), indent=1)
        print(json.dumps(out, indent=1))
        return
    if not os.path.isfile(OUT + "/frozen/te.json"):
        sys.exit("REFUSED: frozen/te.json (T_E per variant) does not exist: the null stage must run and be committed first")
    if stage == "own":
        ps, pp_ = set(pil["S"]), set(pil["P"])
        si = [i for i in range(len(S)) if i not in ps]
        pi = [i for i in range(len(P)) if i not in pp_]
        tasks = [mk(S[i], resid[S[i]["stamp"]]) for i in si] + [mk(S[i], orig[S[i]["stamp"]]) for i in si] + [mk(P[i], orig[P[i]["stamp"]]) for i in pi] + [mk(P[i], resid[P[i]["stamp"]]) for i in pi]
        res = run_tasks(tasks)
        a, b = len(si), len(pi)
        json.dump({"S_idx": si, "S_resid": res[:a], "S_O": res[a:2 * a], "P_idx": pi, "P_O": res[2 * a:2 * a + b], "P_resid": res[2 * a + b:]}, open(OUT + "/own.json", "w"))
        print("acceptance tasks scored:", len(tasks))
        return
    analyse(T)


def pilot_report(T, plumb):
    """numbers only: the S_E* distributions, the dt-mapping check (argmax inside the truth gate for the P detections), the sibling-win share, the time per task, the null size against the machine budget."""
    pj = json.load(open(OUT + ("/plumb/pilot.json" if plumb else "/pilot.json")))
    S, P = T["S"], T["P"]
    pil = T["pilot"]
    s = [S[i] for i in pil["S"]]
    pp = [P[i] for i in pil["P"]]
    nsc = np.asarray([x for r in pj["null"] for x in r["S"]])
    q = lambda v: [float(x) for x in np.percentile(v, [50, 90, 99, 100])] if len(v) else None
    fa_low, fa_all = FA_BUDGET / K_LOW_MEDIAN, FA_BUDGET / K_ALL_MEDIAN
    t_prov = L.threshold_te(nsc, fa_low) if nsc.size else None          # a PROVISIONAL threshold from the 1,000 pilot tests, for the mapping check only
    det, inside, offs = [], [], []
    for r, o in zip(pp, pj["P_O"]):
        if o["best"] == r["true"] and t_prov is not None and o["top"] >= t_prov:
            det.append(1)
            inside.append(int(inside_truth(o["af"], o["adt"], r["own"])))
            offs.append((o["af"] - r["own"][0], o["adt"] - r["own"][1]))
    wrong_p = sum(1 for r, o in zip(pp, pj["P_O"]) if t_prov is not None and o["best"] != r["true"] and o["top"] >= t_prov)
    low_p = [(r, o) for r, o in zip(pp, pj["P_O"]) if r["tclass"] == "low"]
    out = {"plumb": plumb, "tasks": pj["tasks"], "seconds": pj["seconds"], "seconds_per_task_8_workers": pj["seconds"] / max(pj["tasks"], 1), "null_templates": int(nsc.size),
           "null_S_quantiles_50_90_99_max": q(nsc), "T_prov_at_FA_low": t_prov,
           "S_true_template_quantiles_resid": q([o["s_true"] for o in pj["S_resid"] if "s_true" in o]), "S_true_template_quantiles_O": q([o["s_true"] for o in pj["S_O"] if "s_true" in o]),
           "P_true_quantiles_O": q([o["s_true"] for o in pj["P_O"] if "s_true" in o]), "P_true_quantiles_resid": q([o["s_true"] for o in pj["P_resid"] if "s_true" in o]),
           "dt_mapping_check": {"P_detections_at_T_prov": int(sum(det)), "argmax_inside_truth_gate": int(sum(inside)), "share": (sum(inside) / sum(det)) if det else None, "bar": ARGMAX_INSIDE_MIN,
                                "PASS": bool(det and sum(inside) / sum(det) >= ARGMAX_INSIDE_MIN),
                                "median_df_hz": float(np.median([o[0] for o in offs])) if offs else None, "median_ddt_s": float(np.median([o[1] for o in offs])) if offs else None},
           "sibling_win_share_P_O_at_T_prov": wrong_p / max(len(pp), 1), "P_low_rows": len(low_p),
           "null_machine": {"templates_needed_low_x3": NULL_FACTOR * 3 / fa_low, "templates_needed_all_x3": NULL_FACTOR * 3 / fa_all}}
    json.dump(out, open(OUT + ("/plumb/pilot_report.json" if plumb else "/pilot_report.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


def _boot_ratio(num_c, den_c, idx):
    num = num_c[idx].sum(axis=1)
    den = den_c[idx].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = num / den
    r = r[np.isfinite(r)]
    return float(num_c.sum() / den_c.sum()), [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]


def _boot_g(d_c, acc_c, all_c, nref_c, idx):
    """G in pp = (detected / acceptance-testable) x (all testable / n_ref) x 100, a joint cycle bootstrap (the pilot rows sit in 'all testable' but not in the detection share)."""
    d, a, t, n = (x[idx].sum(axis=1) for x in (d_c, acc_c, all_c, nref_c))
    with np.errstate(divide="ignore", invalid="ignore"):
        g = 100.0 * (d / a) * (t / n)
    g = g[np.isfinite(g)]
    return float(100.0 * (d_c.sum() / acc_c.sum()) * (all_c.sum() / nref_c.sum())), float(np.percentile(g, 2.5)), float(np.percentile(g, 97.5))


def analyse(T):
    te = json.load(open(OUT + "/frozen/te.json"))
    own = json.load(open(OUT + "/own.json"))
    S, P = T["S"], T["P"]
    ncyc = len(T["stamps"])
    sidx = {s: i for i, s in enumerate(T["stamps"])}
    idx = L.boot_idx(ncyc, B_BOOT, SEED)
    nref_c = np.array([len(r) for r in S0.load2()[1]], dtype=float)
    out = {"T_E": {k: v["T_E"] for k, v in te.items()}, "V_NULL_N": {k: v["V_NULL_N"] for k, v in te.items()}}

    def per_cycle(rows, flags):
        c = np.zeros(ncyc)
        for r, f in zip(rows, flags):
            c[r["i"]] += f
        return c
    s_acc = [S[i] for i in own["S_idx"]]
    p_acc = [P[i] for i in own["P_idx"]]
    testable_all = per_cycle(S, [1] * len(S))
    testable_acc = per_cycle(s_acc, [1] * len(s_acc))
    t0_pp = 100.0 * testable_all.sum() / nref_c.sum()
    out["T0_pp_recomputed_from_rows"] = t0_pp
    res = {}
    for name, cls_ok in (("V-LOW", lambda r: r["tclass"] == "low"), ("V-ALL", lambda r: True)):
        te_v = te[name]["T_E"]
        det_s = [bool(cls_ok(r) and _det(o, r, te_v)) for r, o in zip(s_acc, own["S_resid"])]
        d_c = per_cycle(s_acc, det_s)
        share, ci_share = _boot_ratio(d_c, testable_acc, idx)
        g_pp, g_lo, g_hi = _boot_g(d_c, testable_acc, testable_all, nref_c, idx)
        p_rows = [(r, o) for r, o in zip(p_acc, own["P_O"]) if cls_ok(r)]
        w_flags = [_wrong(o, r, te_v) for r, o in p_rows]
        d_flags = [_det(o, r, te_v) for r, o in p_rows]
        pc_den = per_cycle([r for r, _ in p_rows], [1] * len(p_rows))
        w_share, w_ci = _boot_ratio(per_cycle([r for r, _ in p_rows], w_flags), pc_den, idx)
        d_share, d_ci = _boot_ratio(per_cycle([r for r, _ in p_rows], d_flags), pc_den, idx)
        det_per_cycle = g_pp / 100.0 * nref_c.sum() / ncyc
        sib = (w_ci[1] / (1 - w_ci[1])) * det_per_cycle if w_ci[1] < 1 else float("inf")
        res[name] = {"S_testable_acceptance_total": int(testable_acc.sum()), "S_detected": int(sum(det_s)), "D_S_share": share, "D_S_CI": ci_share, "G_pp": g_pp, "G_CI_pp": [g_lo, g_hi],
                     "P_rows": len(p_rows), "D_P_on_O": d_share, "D_P_on_O_CI": d_ci, "W_on_O": w_share, "W_CI": w_ci, "detected_S_per_cycle": det_per_cycle, "V_SIB_wrong_publishes_per_cycle_at_W_CI_hi": sib,
                     "V_SIB_PASS": bool(sib <= FA_BUDGET)}
    out["variants"] = res
    vpos = res["V-LOW"]["D_P_on_O_CI"][0] >= V_POS_MIN
    close = all(v["G_CI_pp"][1] < BAR_PP for v in res.values())
    cand = [k for k, v in res.items() if v["G_CI_pp"][0] >= BAR_PP]
    build = [k for k in cand if res[k]["V_SIB_PASS"]]
    if not vpos:
        dec = "VOID (V-POS fails)"
    elif close:
        dec = "CLOSE"
    elif not te["V-LOW"]["V_NULL_N"]["PASS"]:
        dec = "VOID (V-NULL-N V-LOW fails)"
    elif cand and not build:
        dec = "GATE-STUDY"
    elif build:
        dec = "BUILD-WORTH (" + ("V-LOW" if "V-LOW" in build else build[0]) + ")"
    else:
        dec = "BETWEEN"
    out.update({"V_POS": {"D_P_low_on_O_CI_lo": res["V-LOW"]["D_P_on_O_CI"][0], "bar": V_POS_MIN, "PASS": bool(vpos)}, "decision": dec})
    json.dump(out, open(OUT + "/result.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


def _det(o, r, t_e):
    """detected, from a stored result o and its row r (winner == true, S* >= T_E, argmax inside the truth gate of the row's own position)."""
    return bool(o["best"] == r["true"] and o["top"] >= t_e and inside_truth(o["af"], o["adt"], r["own"]))


def _wrong(o, r, t_e):
    return bool(o["best"] != r["true"] and o["top"] >= t_e)


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    import coherent_extract as CE
    import xt_selftest as FX
    ok = True

    def chk(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print("FAIL", name, got, want)
    rng = np.random.default_rng(1)
    tones_a = [int(x) for x in FX.tones_a()]
    # a sibling that differs from A only in the last 12 payload-ish symbols, and an unrelated template
    sib = list(tones_a)
    for k in range(60, 72):
        sib[k] = (sib[k] + 3) % 8
    other = [int(x) for x in rng.integers(0, 8, 79)]
    tm = np.asarray([tones_a, sib, other], dtype=np.int64)
    # (1) the vectorised S_E equals xt_lib.s_e for every template, on random correlations
    Xm = rng.normal(size=(79, 8)) + 1j * rng.normal(size=(79, 8))
    v = s_e_set(Xm, tm)
    chk("vectorised s_e == xt_lib.s_e", [abs(float(v[k]) - L.s_e(Xm, tm[k])) < 1e-12 for k in range(3)], [True, True, True])
    # (2) a synthetic signal at WSJT-X dt 0.52 and 1000 Hz: found with OUR dt (0.52 + 0.600) passed as dt_ours - 0.600; the true template wins and the argmax is inside the truth gate
    pcm = FX.synth(tones_a, f0=1000.0, dt0=0.52, amp=0.5, noise=1.0, seed=7)
    pcm = np.asarray(pcm, dtype=np.float32)
    f_c, dt_ours = 1001.0, 0.52 + DT_OFFSET_S + 0.05                     # the known centre is 1 Hz and 50 ms off the truth, inside the window
    S, af, adt = search_set(CE, pcm, f_c, dt_ours - DT_OFFSET_S, tm)
    det, wrong, b, top = verdict(S, af, adt, 0, (1000.0, 0.52), 3.0)
    chk("true template wins, detected", (det, wrong, b), (True, False, 0))
    chk("argmax inside the truth gate (the dt mapping for OUR dt)", inside_truth(af[0], adt[0], (1000.0, 0.52)), True)
    chk("the sibling scores below the true template", bool(S[1] < S[0]), True)
    # (3) must NOT detect: the same signal, a wrong true index (the sibling is declared true) -> a wrong-message win; a threshold above the score; a position outside the gate
    d2, w2, _, _ = verdict(S, af, adt, 1, (1000.0, 0.52), 3.0)
    chk("sibling declared true: not detected, wrong-message win", (d2, w2), (False, True))
    chk("threshold above the score: not detected, not a win", verdict(S, af, adt, 0, (1000.0, 0.52), 99.0)[:2], (False, False))
    chk("position outside the gate: not detected", verdict(S, af, adt, 0, (1010.0, 0.52), 3.0)[0], False)
    # (4) noise only: no template reaches a signal-like score
    noise = FX.synth(tones_a, f0=1000.0, dt0=0.52, amp=0.0, noise=1.0, seed=9)
    Sn, _, _ = search_set(CE, np.asarray(noise, dtype=np.float32), 1000.0, 0.52, tm)
    chk("noise-only maximum below the signal's S", bool(Sn.max() < S[0]), True)
    # (5) payload texts and the step sets (sizes)
    chk("N(report) sizes", (len(payload_texts("report", "Q1AAA", "Q2BBB", "N")), len(payload_texts("rreport", "Q1AAA", "Q2BBB", "N")), len(payload_texts("RR73", "Q1AAA", "Q2BBB", "N"))), (62, 3, 1))
    chk("N2 sizes", (len(payload_texts("grid", "Q1AAA", "Q2BBB", "N2")), len(payload_texts("report", "Q1AAA", "Q2BBB", "N2")), len(payload_texts("rreport", "Q1AAA", "Q2BBB", "N2")), len(payload_texts("RR73", "Q1AAA", "Q2BBB", "N2"))), (62, 3, 1, 0))
    chk("payload strings", (payload_str("report", 5), payload_str("rreport", -12), payload_str("RR73", None)), ("+05", "R-12", "RR73"))
    # (6) decision logic via the stored-result predicates
    o = {"best": 0, "top": 5.0, "af": 1000.0, "adt": 0.52}
    r = {"true": 0, "own": [1000.0, 0.52]}
    chk("_det", (_det(o, r, 3.0), _det({**o, "best": 1}, r, 3.0), _det({**o, "top": 2.0}, r, 3.0), _det({**o, "af": 1010.0}, r, 3.0)), (True, False, False, False))
    chk("_wrong", (_wrong({**o, "best": 1}, r, 3.0), _wrong(o, r, 3.0), _wrong({**o, "best": 1, "top": 2.0}, r, 3.0)), (True, False, False))
    print("selftest ALL PASS" if ok else "selftest FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    mp.freeze_support()
    main()
