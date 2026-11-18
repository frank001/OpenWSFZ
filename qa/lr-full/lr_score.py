#!/usr/bin/env python3
"""LR-FULL scorer (spec b2d9883a + Amendment 1 §10 + Amendment 2, rulings of 2026-11-18). The FD-PROXY tree 4639e742 (fd_lib.py, fd_pilot.py, fd_uprime.py) is imported UNCHANGED.

  python -I lr_score.py selftest                          constructed cases driving every decision row and the data-layer functions (lr_selftest.py)
  python -I lr_score.py pin <out.json>                    V-H code against FD-PROXY's own night: must reproduce its frozen V-SEP / V-GHOST / V-BURIAL numbers exactly
  python -I lr_score.py pilot <night_spec.json> <out>     PILOT cycles only (first pilot_cycles of the night): counts, the H-HI floor per step, V-H on controls; NO instrument output on any G row
  python -I lr_score.py smoke <night_spec.json> [<night2_spec.json>] <out>   the final code path WITHOUT the git gate, for code checks on non-acceptance data (labelled, never a result)
  python -I lr_score.py final <night_spec.json> [<night2_spec.json>] <out>   THE ONE SCORING RUN (refuses unless these files are committed and clean; synthetic-set hashes and the calibration are asserted)

Definitions (all code below; HK-021). Per night: arms OFF and ON are replays of the TEST cycles (the harness's nc.tsv with the trailing step column 13: 0 none, 1 v2 at or below the gate,
2 X1, 3 late-round primary, 4 X2 F1b-passed, 5 X2 admitted-only). n_ref = WSJT-X Rx FT8 rows of the TEST cycles. NET(step) = (WSJT-X rows matched in ON by a row of that step and NOT matched in OFF) / n_ref
(the harness's own one-to-one rule, recomputed here and asserted equal to the nc.tsv matched flag). G(step) = ON rows of that step, no WSJT-X match, text not published in OFF in that cycle.
P = ON's confirmed rows of batches 4 and 5 (X1 rows are batch 4, X2 rows batch 5). Strata: SNR band x {buried, isolated} (TA-CHECK burial, own match excluded for confirmed rows).
H-COST = isolated part (U' mixture on the isolated G rows, no unjudgeable bracket) + buried part (H, unjudgeable rows at 0 / 1), per cycle (A1.3a).
HK-037: message text exists only in memory; output is counts and rates only.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, "..", "fd-proxy")
sys.path.insert(0, HERE)
sys.path.insert(0, FD)
import lr_decide as D          # noqa: E402
import fd_lib as L             # noqa: E402  (FD-PROXY 4639e742, unchanged)
import fd_pilot as FP          # noqa: E402  (render, DF_SPREAD_HZ; unchanged)
import fd_uprime as FU         # noqa: E402  (the frozen cf_fbid tone test; unchanged)

SEED = 20261118                # spec s4.3 / FD-PROXY
B_BOOT = 2000
BATCHES_P = (4, 5)
N_FIELD_PER = 1000
U_SAMPLE_N = 1000              # as FD-PROXY: seeded sample of confirmed isolated rows for s_U and s_H
BANDS = ("<=-18", "-17..-10", ">=-9")
STRATA = [(b, k) for b in BANDS for k in ("isolated", "buried")]
SIX = {s: i for i, s in enumerate(STRATA)}
STEP_TAGS = {"X1": (2,), "X2": (4, 5), "X2_passed": (4,), "X2_admitted": (5,)}
assert (SEED, B_BOOT, N_FIELD_PER, U_SAMPLE_N) == (20261118, 2000, 1000, 1000)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


# --------------------------------------------------------------------------------------------------------------------------- IO
def load_arm(d):
    """nc.tsv (12 columns, or 13 with the LR-FULL step) -> rows; text stays in memory."""
    rows = []
    with open(os.path.join(d, "nc.tsv"), encoding="utf-8", errors="replace", newline="") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t")
            if len(p) < 11:
                continue
            rows.append(dict(st=p[0], k=int(p[1]), m=int(p[2]), f=int(p[3]), dt=float(p[4]), snr=int(p[5]), tx=p[10].strip(),
                             ap=int(p[11]) if len(p) > 11 and p[11] != "" else 0, step=int(p[12]) if len(p) > 12 and p[12] != "" else 0))
    return rows


def load_ws(alltxt):
    """WSJT-X Rx FT8 rows per stamp, in file order: stamp -> [(snr, freq, text)] (the same filter as fd_lib.load_E and the harness)."""
    ws = collections.defaultdict(list)
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            f = ln.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                ws[f[0]].append((int(f[4]), int(f[6]), " ".join(f[7:]).strip()))
            except ValueError:
                continue
    return ws


def match_cycle(rows, wrows, gate=10):
    """The harness's one-to-one rule (replay81 ScoreTestB): candidates (df <= 10 Hz, equal text) sorted by (df, row index, WSJT-X index), taken greedily. -> {row index: WSJT-X index}"""
    cands = []
    for i, r in enumerate(rows):
        for j, (_s, f, t) in enumerate(wrows):
            df = abs(r["f"] - f)
            if df <= gate and r["tx"] == t:
                cands.append((df, i, j))
    cands.sort()
    ui, uj, out = set(), set(), {}
    for _df, i, j in cands:
        if i in ui or j in uj:
            continue
        ui.add(i); uj.add(j); out[i] = j
    return out


def by_cycle(rows):
    d = collections.OrderedDict()
    for r in rows:
        d.setdefault(r["st"], []).append(r)
    return d


def arm_match(rows, ws):
    """Recompute the matching for every cycle; attach 'w' (WSJT-X index or None) to each row; return the count of rows whose recomputed flag differs from nc.tsv (must be 0)."""
    bad = 0
    for st, rs in by_cycle(rows).items():
        m = match_cycle(rs, ws.get(st, []))
        for i, r in enumerate(rs):
            r["w"] = m.get(i)
            bad += int((r["w"] is not None) != bool(r["m"]))
    return bad


def phi(s, p, f):
    d = s - f
    return float("nan") if d <= 0 else min(1.0, max(0.0, (s - p) / d))


def s_from(num, den, W):
    ok = den > 0
    return float((W[ok] * (num[ok] / den[ok])).sum() / W[ok].sum()) if ok.any() and W[ok].sum() > 0 else float("nan")


def q95(v):
    v = np.asarray([x for x in v if x == x])
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else [float("nan"), float("nan")]


# ------------------------------------------------------------------------------------------------- NET, G, P, strata (structure)
def abandon_cycles(d):
    """Stamps in which ANY stage abandoned or failed (the harness's per-cycle csvs: coh.csv / abandon.csv `abandoned`, third.csv / late.csv `outcome`)."""
    s = set()

    def rd(name):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            return []
        with open(p, newline="", encoding="utf-8", errors="replace") as fh:
            return list(csv.DictReader(fh))
    for r in rd("coh.csv"):
        if int(r.get("abandoned", 0) or 0) > 0:
            s.add(r["stamp"])
    for r in rd("abandon.csv"):
        if int(r.get("abandoned", 0) or 0) > 0:
            s.add(r["stamp"])
    for r in rd("third.csv"):
        if r.get("outcome") in ("abandoned", "failed"):
            s.add(r["stamp"])
    for r in rd("late.csv"):
        if r.get("outcome") in ("abandoned", "failed"):
            s.add(r["stamp"])
    return s


def net_arrays(on_rows, off_rows, ws, cycles):
    """Per cycle (in `cycles` order): newly corroborated WSJT-X rows by step tag, lost rows, n_ref. NET numerators are WSJT-X rows matched in ON and not matched in OFF."""
    onc, offc = by_cycle(on_rows), by_cycle(off_rows)
    n = len(cycles)
    a = {k: np.zeros(n) for k in ("X1", "X2", "X2_passed", "X2_admitted", "other", "lost", "nref", "on_net")}
    for i, c in enumerate(cycles):
        off_w = {r["w"] for r in offc.get(c, []) if r.get("w") is not None}
        on_w = set()
        for r in onc.get(c, []):
            if r.get("w") is None:
                continue
            on_w.add(r["w"])
            if r["w"] in off_w:
                continue
            t = r["step"]
            if t == 2:
                a["X1"][i] += 1
            elif t in (4, 5):
                a["X2"][i] += 1
                a["X2_passed" if t == 4 else "X2_admitted"][i] += 1
            else:
                a["other"][i] += 1
        a["lost"][i] = len(off_w - on_w)
        a["nref"][i] = len(ws.get(c, []))
        a["on_net"][i] = len(on_w) - len(off_w)          # NET(ON) total: WSJT-X rows matched in ON minus matched in OFF (newly corroborated minus lost)
    return a


def net_ci(arr_num, arr_ref, B=B_BOOT, seed=SEED):
    """pp, cycle bootstrap of the ratio of sums."""
    rng = np.random.default_rng(seed)
    n = len(arr_ref)
    pt = 100.0 * arr_num.sum() / arr_ref.sum() if arr_ref.sum() else float("nan")
    v = []
    for _ in range(B):
        ix = rng.integers(0, n, n)
        d = arr_ref[ix].sum()
        v.append(100.0 * arr_num[ix].sum() / d if d else float("nan"))
    lo, hi = q95(v)
    return pt, lo, hi


def off_texts_by_cycle(off_rows):
    d = collections.defaultdict(set)
    for r in off_rows:
        d[r["st"]].add(r["tx"])
    return d


def g_rows(on_rows, off_rows, step_tags):
    """G(step): ON rows with the step tag, no WSJT-X match, not published (by text) in OFF in that cycle."""
    offt = off_texts_by_cycle(off_rows)
    return [r for r in on_rows if r["step"] in step_tags and r.get("w") is None and r["tx"] not in offt[r["st"]]]


def classify(rows, E, confirmed):
    """structure only (parse + burial + band); NO instrument output. EVERY row gets a burial class (it needs only the cycle, frequency and SNR); `judgeable` says whether H can parse it."""
    out = []
    for r in rows:
        pr = L.parse(r["tx"])
        cyc = L.cycle_of(r["st"])
        bur = E.buried(cyc, r["f"], r["snr"], text=r["tx"], confirmed=confirmed)
        out.append(dict(r=r, pr=pr, judgeable=pr is not None, cyc=cyc, st=(L.band(r["snr"]), "buried" if bur else "isolated"), kind=pr["kind"] if pr else None))
    return out


def bandwts(recs, which):
    cnt = collections.Counter(x["st"][0] for x in recs if x["st"][1] == which)
    t = sum(cnt.values())
    return np.array([cnt.get(b, 0) / t if t else 0.0 for b in BANDS])


# ---------------------------------------------------------------------------------------- V-H: FD-PROXY's controls, code copied from fd_score.py
def controls_vh(rows, E, use, texts, seed=SEED, strip=True):
    """FD-PROXY V-SEP / V-GHOST / V-BURIAL on the given arm and cycles: the control block of fd_score.py (4639e742) with the inputs parametrised and the same random sequence.
    Governed population Q = unconfirmed batch 4+5 rows (positions and strata only); P = confirmed batch 4+5 rows; no Q row is ever judged. `use` = the cycles in scope."""
    def rec(r, confirmed, judge):
        pr = L.parse(r["tx"])
        if pr is None:
            return None
        cyc = L.cycle_of(r["st"])
        bur = E.buried(cyc, r["f"], r["snr"], text=r["tx"], confirmed=confirmed)
        j = E.judge(cyc, float(r["f"]), r["tx"]) if judge else None
        return dict(r=r, pr=pr, cyc=cyc, st=(L.band(r["snr"]), "buried" if bur else "isolated"), j=j, kind=pr["kind"])
    qg, pg, qpos = [], [], []
    for r in rows:
        if r["st"] not in use:
            continue
        if r["k"] in BATCHES_P and r["m"] == 0:
            qpos.append((L.cycle_of(r["st"]), r["f"], r["dt"], r["st"]))
        rc = rec(r, bool(r["m"]), judge=(r["m"] == 1))
        if r["m"] == 0:
            if rc is not None and r["k"] in BATCHES_P:
                qg.append(rc)
        elif rc is not None and r["k"] in BATCHES_P:
            pg.append(rc)
    pg = [x for k in BATCHES_P for x in pg if x["r"]["k"] == k]   # FD-PROXY's order: P grouped by batch (4 then 5), file order within a batch: the seeded draws depend on it
    cnt = collections.Counter(x["st"] for x in qg)
    tot = sum(cnt.values())
    W6 = np.array([cnt.get(s, 0) / tot for s in STRATA])
    Wband = np.array([sum(cnt.get((b, k), 0) for k in ("isolated", "buried")) / tot for b in BANDS])
    rng = random.Random(seed)
    qpos_s = sorted(qpos)
    nr = []
    for t in texts:
        c, f, dt, st = rng.choice(qpos_s)
        nr.append(E.judge(c, float(f), t))
    nr_j = [j for j in nr if j is not None]
    n_rand = len(nr_j)
    f_rand = sum(j["plausible"] for j in nr_j) / n_rand
    nf = {}
    for variant, hide in (("visible", False), ("MISS", True)):
        rg = random.Random(seed)
        per = {}
        for field in ("B", "A", "X"):
            pool = [x for x in pg if FP.render(x["pr"], x["r"]["tx"], field, random.Random(0), None) is not None]
            made, tries = [], 0
            while len(made) < N_FIELD_PER and pool and tries < N_FIELD_PER * 20:
                tries += 1
                x = rg.choice(pool)
                t = FP.render(x["pr"], x["r"]["tx"], field, rg, None)
                if t is None:
                    continue
                df = rg.uniform(-FP.DF_SPREAD_HZ, FP.DF_SPREAD_HZ)
                j = E.judge(x["cyc"], x["r"]["f"] + df, t, hide=((x["r"]["tx"], x["r"]["f"]) if hide else None))
                made.append(j)
            jj = [j for j in made if j is not None]
            per[field] = (sum(j["plausible"] for j in jj), len(jj))
        nf[variant] = per
    # as fd_score.py: each field's rate rounded to 4 places, then the equal-share mean rounded to 5 (the rounded value is the one the phi bracket uses)
    f_of = lambda per: round(sum(round(per[fd][0] / per[fd][1], 4) for fd in ("B", "A", "X") if per[fd][1]) / sum(1 for fd in ("B", "A", "X") if per[fd][1]), 5)
    f_vis, f_miss = f_of(nf["visible"]), f_of(nf["MISS"])
    cyc_list = sorted({x["cyc"] for x in qg} | {x["cyc"] for x in pg})
    cix = {c: i for i, c in enumerate(cyc_list)}
    nC = len(cyc_list)
    Pn, Pp = np.zeros((nC, 6)), np.zeros((nC, 6))
    for x in pg:
        i, s_ = cix[x["cyc"]], SIX[x["st"]]
        Pn[i, s_] += 1
        Pp[i, s_] += x["j"]["plausible"] if x["j"] else 0
    brng = np.random.default_rng(seed)
    idxs = [brng.integers(0, nC, nC) for _ in range(B_BOOT)]
    s_pt = s_from(Pp.sum(0), Pn.sum(0), W6)
    sep, gho, bur = [], [], []
    for ix in idxs:
        pn, pp = Pn[ix].sum(0), Pp[ix].sum(0)
        sb = s_from(pp, pn, W6)
        sep.append(sb - brng.binomial(n_rand, f_rand) / n_rand)
        kk = nf["MISS"]
        fm = np.mean([brng.binomial(kk[fd][1], kk[fd][0] / kk[fd][1]) / kk[fd][1] for fd in ("B", "A", "X") if kk[fd][1]])
        gho.append(sb - fm)
        iso = np.array([[pn[SIX[(b, "isolated")]], pp[SIX[(b, "isolated")]]] for b in BANDS])
        bu = np.array([[pn[SIX[(b, "buried")]], pp[SIX[(b, "buried")]]] for b in BANDS])
        bur.append(s_from(iso[:, 1], iso[:, 0], Wband) - s_from(bu[:, 1], bu[:, 0], Wband))
    iso_pt = np.array([[Pn[:, SIX[(b, "isolated")]].sum(), Pp[:, SIX[(b, "isolated")]].sum()] for b in BANDS])
    bu_pt = np.array([[Pn[:, SIX[(b, "buried")]].sum(), Pp[:, SIX[(b, "buried")]].sum()] for b in BANDS])
    s_iso, s_bur = s_from(iso_pt[:, 1], iso_pt[:, 0], Wband), s_from(bu_pt[:, 1], bu_pt[:, 0], Wband)
    ci_sep, ci_gho, ci_bur = [round(x, 4) for x in q95(sep)], [round(x, 4) for x in q95(gho)], [round(x, 4) for x in q95(bur)]
    out = dict(s_weighted=round(s_pt, 4), f_RAND=round(f_rand, 5), f_NFIELD_visible=round(f_vis, 5), f_MISS=round(f_miss, 5), n_P=len(pg), n_Q_judgeable=len(qg), n_rand_judgeable=n_rand,
               V_SEP=dict(point=round(s_pt - f_rand, 4), ci=ci_sep, bar=0.70, ok=ci_sep[0] >= 0.70),
               V_GHOST=dict(point=round(s_pt - f_miss, 4), ci=ci_gho, bar=0.50, ok=ci_gho[0] >= 0.50),
               V_BURIAL=dict(diff=round(s_iso - s_bur, 4), ci=ci_bur, bar=0.10, ok=ci_bur[1] <= 0.10, P_iso_n=int(iso_pt[:, 0].sum()), P_buried_n=int(bu_pt[:, 0].sum())))
    out["ok"] = bool(out["V_SEP"]["ok"] and out["V_GHOST"]["ok"] and out["V_BURIAL"]["ok"])
    out["_f"] = (f_rand, f_vis, f_miss)
    return out


# ------------------------------------------------------------------------------------------------------- hybrid H-COST per step
class Instruments:
    """H (fd_lib) and U' (fd_uprime) on rows. U' is built lazily (needs the WAVs and the pinned dll)."""

    def __init__(self, E, wav_dir=None, dll=None, c_off=None):
        self.E, self.wav_dir, self.dll, self.c_off, self._T = E, wav_dir, dll, c_off, None

    def tone(self):
        if self._T is None:
            self._T = FU.Tone(self.wav_dir, self.dll)
            self._T.c_off = self.c_off
        return self._T

    def present(self, r):
        v = self.tone().share(r["st"], r["f"], r["dt"], r["tx"])
        return 0 if v is None else int(v >= FU.T_FROZEN)      # unencodable counts as not shown present (cf_uprime's conservative rule)


def step_cost(g_recs, p_recs, cycles, inst, f_ctrl, f_iso, n_ctrl, n_iso_ctrl, p_sample, seed=SEED, n_rand_b=None):
    """H-COST inputs for one step on one night (A1.3a, the hybrid). g_recs = ALL G rows classified (structure); p_recs = ON's judgeable confirmed b4+5 recs (with .pl);
    f_ctrl = (f_rand_b, f_vis, f_miss): f_rand_b is the N-RAND rate AT BURIED G POSITIONS (Amendment 3 D7: where H judges), f_vis / f_miss from controls_vh; n_rand_b = the judgeable synthetic rows behind
    f_rand_b (n_ctrl is the count behind f_vis / f_miss); f_iso = (f_H, f_U) at ISOLATED G positions (V-AGREE-NI); p_sample = the seeded isolated P sample (recs with .pl and .u).
    ISOLATED rows: U' mixture on ALL isolated G rows (by audio; no unjudgeable bracket). BURIED rows: H on the judgeable ones, the UNJUDGEABLE buried rows at 0 / 1.
    V-AGREE-NI arrays: phi_U and phi_H on the JUDGEABLE isolated G rows (the same rows for both instruments)."""
    cix = {c: i for i, c in enumerate(cycles)}
    nC = len(cycles)
    iso_all = [x for x in g_recs if x["st"][1] == "isolated"]
    iso_j = [x for x in iso_all if x["judgeable"]]
    bur_j = [x for x in g_recs if x["st"][1] == "buried" and x["judgeable"]]
    n_unj_bur = sum(1 for x in g_recs if x["st"][1] == "buried" and not x["judgeable"])
    a = {k: np.zeros(nC) for k in ("iso_n", "iso_u", "isoj_n", "isoj_u", "isoj_h", "bur_n", "bur_pl")}
    for x in iso_all:
        i = cix[x["cyc"]]
        u = inst.present(x["r"])
        a["iso_n"][i] += 1
        a["iso_u"][i] += u
        if x["judgeable"]:
            a["isoj_n"][i] += 1
            a["isoj_u"][i] += u
            a["isoj_h"][i] += inst.E.judge(x["cyc"], float(x["r"]["f"]), x["r"]["tx"])["plausible"]
    for x in bur_j:
        i = cix[x["cyc"]]
        a["bur_n"][i] += 1
        a["bur_pl"][i] += inst.E.judge(x["cyc"], float(x["r"]["f"]), x["r"]["tx"])["plausible"]
    Pb_n, Pb_pl = np.zeros((nC, 3)), np.zeros((nC, 3))
    for x in p_recs:
        if x["st"][1] == "buried" and x["cyc"] in cix:
            Pb_n[cix[x["cyc"]], BANDS.index(x["st"][0])] += 1
            Pb_pl[cix[x["cyc"]], BANDS.index(x["st"][0])] += x["pl"]
    Pi_n, Pi_u, Pi_h = np.zeros((nC, 3)), np.zeros((nC, 3)), np.zeros((nC, 3))
    for x in p_sample:
        if x["cyc"] in cix:
            bi = BANDS.index(x["st"][0])
            Pi_n[cix[x["cyc"]], bi] += 1
            Pi_u[cix[x["cyc"]], bi] += x["u"]
            Pi_h[cix[x["cyc"]], bi] += x["pl"]
    Wb, Wi_all, Wi_j = bandwts(bur_j, "buried"), bandwts(iso_all, "isolated"), bandwts(iso_j, "isolated")
    f_rand, f_vis, f_miss = f_ctrl
    f_h, f_u = f_iso

    def est(ix, rng=None):
        sb = (lambda arr: arr[ix].sum(0)) if ix is not None else (lambda arr: arr.sum(0))
        ss = (lambda arr: arr[ix].sum()) if ix is not None else (lambda arr: arr.sum())
        fr, fv, fm, fu_, fh_ = f_rand, f_vis, f_miss, f_u, f_h
        if rng is not None:
            nrb = n_rand_b if n_rand_b else n_ctrl
            fr = rng.binomial(nrb, f_rand) / nrb
            fv, fm = (rng.binomial(n_ctrl, f) / n_ctrl for f in (f_vis, f_miss))
            fu_ = rng.binomial(n_iso_ctrl, f_u) / n_iso_ctrl if n_iso_ctrl else f_u
            fh_ = rng.binomial(n_iso_ctrl, f_h) / n_iso_ctrl if n_iso_ctrl else f_h
        ni, nij, nb = ss(a["iso_n"]), ss(a["isoj_n"]), ss(a["bur_n"])
        s_u_all = s_from(sb(Pi_u), sb(Pi_n), Wi_all)
        s_u_j, s_h_j = s_from(sb(Pi_u), sb(Pi_n), Wi_j), s_from(sb(Pi_h), sb(Pi_n), Wi_j)
        s_h_b = s_from(sb(Pb_pl), sb(Pb_n), Wb)
        ph_u_cost = phi(s_u_all, ss(a["iso_u"]) / ni, fu_) if ni else 0.0
        ph_u_j = phi(s_u_j, ss(a["isoj_u"]) / nij, fu_) if nij else 0.0
        ph_h_j = phi(s_h_j, ss(a["isoj_h"]) / nij, fh_) if nij else 0.0
        p_hb = ss(a["bur_pl"]) / nb if nb else 0.0
        ph_lo = phi(s_h_b, p_hb, min(fr, fv)) if nb else 0.0
        ph_hi = phi(s_h_b, p_hb, max(fr, fm)) if nb else 0.0
        iso_part = ph_u_cost * ni / nC
        return dict(iso_part=iso_part, h_lo=iso_part + ph_lo * nb / nC, h_hi=iso_part + (ph_hi * nb + n_unj_bur) / nC, phi_U_cost=ph_u_cost, phi_U=ph_u_j, phi_H_iso=ph_h_j,
                    phi_lo=ph_lo, phi_hi=ph_hi, n_iso_all=int(ni), n_iso_judgeable=int(nij), n_buried_judgeable=int(nb), n_buried_unjudgeable=n_unj_bur)
    pt = est(None)
    brng = np.random.default_rng(seed)
    reps = [est(brng.integers(0, nC, nC), brng) for _ in range(B_BOOT)]
    ci = {k: [round(x, 5) for x in q95([r[k] for r in reps])] for k in ("iso_part", "h_lo", "h_hi")}
    cph = {k: [round(x, 4) for x in q95([r[k] for r in reps])] for k in ("phi_U_cost", "phi_U", "phi_H_iso")}
    return dict(point={k: (round(v, 5) if isinstance(v, float) else v) for k, v in pt.items()}, ci=ci, phi_ci=cph,
                _boot_diff=[(r["phi_U"] - r["phi_H_iso"]) for r in reps], _n_iso=pt["n_iso_judgeable"])


def pooled_agree(per_night):
    """V-AGREE-NI pooled over nights AND steps (the instrument row only): per night the isolated G rows of both steps; D = n-weighted mean of (phi_U - phi_H); the CI recombines each night's own
    cycle-bootstrap replicates (same index = same replicate). per_night = [dict(n, point_diff, boot=[...])]."""
    ns = np.array([x["n"] for x in per_night], float)
    if ns.sum() == 0:
        return dict(n=0, diff=float("nan"), ci=[float("nan"), float("nan")], status="UNDERPOWERED")
    w = ns / ns.sum()
    diff = float(sum(w[i] * per_night[i]["point_diff"] for i in range(len(per_night))))
    B = min(len(x["boot"]) for x in per_night if x["n"] > 0)
    boot = [sum(w[i] * per_night[i]["boot"][b] for i in range(len(per_night)) if per_night[i]["n"] > 0) for b in range(B)]
    lo, hi = q95(boot)
    return dict(n=int(ns.sum()), diff=round(diff, 4), ci=[round(lo, 4), round(hi, 4)], status=D.agree_ni(int(ns.sum()), lo, hi))


def v_run_night(spec, off_rows, on_rows, test_cycles, rerun_ok):
    pins_ok = sha(spec["dll"]) == spec["dll_pin"]
    ab_off, ab_on = abandon_cycles(spec["off_dir"]) & set(test_cycles), abandon_cycles(spec["on_dir"]) & set(test_cycles)
    cnt = lambda rows: collections.Counter((r["st"], r["k"]) for r in rows if r["k"] in (1, 2, 3, 4))
    c_off, c_on = cnt(off_rows), cnt(on_rows)
    ge = all(c_on[k] >= v for k, v in c_off.items() if k[0] in set(test_cycles))
    ok, parts = D.v_run(pins_ok, len(ab_off), ge, rerun_ok, len(ab_on - ab_off), len(test_cycles))
    parts["on_abandon_cycles"] = len(ab_on)
    parts["off_abandon_cycles"] = len(ab_off)
    return ok, parts


def log_lines(d, fam):
    p = os.path.join(d, "log.log")
    if not os.path.exists(p):
        return []
    return [l for l in open(p, encoding="utf-8", errors="replace") if fam in l]


def pct(v, qs=(50, 99, 100)):
    v = [x for x in v if x >= 0]
    return {("p%d" % q if q < 100 else "max"): (round(float(np.percentile(v, q)), 1) if v else None) for q in qs}


def late_desc(d):
    p = os.path.join(d, "late.csv")
    if not os.path.exists(p):
        return None
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    f = lambda k: [float(r[k]) for r in rows if r.get(k) not in (None, "")]
    return dict(endMs=pct(f("endMs")), batch5PublishMs=pct(f("batch5PublishMs")))


# ---------------------------------------------------------------------------------------------------------------------- the night
def run_night(spec, mode):
    t0 = time.time()
    off_rows, on_rows = load_arm(spec["off_dir"]), load_arm(spec["on_dir"])
    ws = load_ws(spec["wsjtx_alltxt"])
    E = L.Evidence(L.load_E(spec["wsjtx_alltxt"]))
    mism = {"off": arm_match(off_rows, ws), "on": arm_match(on_rows, ws)}
    stamps = sorted({r["st"] for r in on_rows})
    pil = set(stamps[:spec["pilot_cycles"]])
    cyc_stamps = sorted(pil) if mode == "pilot" else [s for s in stamps if s not in pil]
    use = set(cyc_stamps)
    cycles = [L.cycle_of(s) for s in cyc_stamps]
    res = dict(night=spec["night"], mode=mode, cycles=len(cyc_stamps), recomputed_match_mismatches=mism)
    assert mism["off"] == 0 and mism["on"] == 0, "the recomputed WSJT-X matching differs from the harness's matched flag"
    on_u, off_u = [r for r in on_rows if r["st"] in use], [r for r in off_rows if r["st"] in use]
    # --- counts per step (structure only) ---
    steps = {}
    for step, tags in STEP_TAGS.items():
        g = g_rows(on_u, off_u, tags)
        rowsN = [r for r in on_u if r["step"] in tags]
        recs = classify(g, E, confirmed=False)
        nu = sum(1 for x in recs if not x["judgeable"])
        iso = sum(1 for x in recs if x["st"][1] == "isolated")
        unj_bur = sum(1 for x in recs if not x["judgeable"] and x["st"][1] == "buried")
        steps[step] = dict(rows_total=len(rowsN), rows_matched=sum(1 for r in rowsN if r.get("w") is not None), G=len(g), G_judgeable=len(recs) - nu, G_unjudgeable=nu,
                           G_isolated=iso, G_isolated_judgeable=sum(1 for x in recs if x["st"][1] == "isolated" and x["judgeable"]), G_buried=len(recs) - iso,
                           G_unjudgeable_buried=unj_bur, rows_per_cycle=round(len(rowsN) / len(cyc_stamps), 4),
                           H_HI_floor_all_unjudgeable=round(nu / len(cyc_stamps), 5), H_HI_floor_hybrid_buried_only=round(unj_bur / len(cyc_stamps), 5))
    res["steps"] = steps
    res["step_column_counts"] = dict(collections.Counter(r["step"] for r in on_u))
    # --- controls (V-H) on the OFF arm ---
    texts = [ln.rstrip("\n") for key in ("rand", "ap") for ln in open(spec["nrand"][key], encoding="utf-8")]
    for key, p in spec["nrand"].items():
        if key in ("rand", "ap"):
            assert sha(p) == spec["nrand"]["sha"][key], "synthetic set differs from its recorded hash"
    vh = controls_vh(off_rows, E, use, texts)
    f_ctrl = vh.pop("_f")
    res["V_H"] = vh
    res["f"] = dict(f_RAND=f_ctrl[0], f_NFIELD_visible=f_ctrl[1], f_MISS=f_ctrl[2])
    res["run_seconds_so_far"] = round(time.time() - t0, 1)
    if mode == "pilot":
        # The H-HI floor per step (A1.3a): the hybrid floor counts only the UNJUDGEABLE BURIED rows (isolated rows are judged by U' from the audio); the all-rows floor is the old s3 figure, printed beside it.
        for k, v in steps.items():
            v["floor_vs_budget_0.021"] = "hybrid floor ABOVE the budget (H-COST cannot PASS)" if v["H_HI_floor_hybrid_buried_only"] > D.H_BUDGET else "hybrid floor below the budget"
        res["n_iso_G_projected"] = {k: v["G_isolated"] for k, v in steps.items()}
        res["note"] = "PILOT: no instrument output was computed on any G row; V-H is on the controls only (OFF arm, pilot cycles)"
        return res, None
    # ============================ FINAL: instruments on G ============================
    A = net_arrays(on_rows, off_rows, ws, cyc_stamps)
    inst = Instruments(E, spec["wav_dir"], spec["dll"], spec["c_off"])
    ctl = sorted([(r["st"], r["f"], r["dt"], r["tx"]) for r in on_rows if r["m"] == 1 and r["st"] in pil and r["k"] == 1], key=lambda t: (t[0], t[1]))
    cal = inst.tone().calibrate(ctl)
    assert abs(cal["start_minus_dt_median_s"] - spec["c_off"]) < 1e-9, "calibration moved: %r" % (cal,)
    res["U_calibration"] = cal
    # P (ON's confirmed b4+5), judged by H and U' (sample for U')
    p_recs = [x for x in classify([r for r in on_u if r["k"] in BATCHES_P and r["m"] == 1], E, confirmed=True) if x["judgeable"]]
    for x in p_recs:
        x["pl"] = int(E.judge(x["cyc"], float(x["r"]["f"]), x["r"]["tx"])["plausible"])
    p_iso = [x for x in p_recs if x["st"][1] == "isolated"]
    p_sample = random.Random(SEED).sample(p_iso, min(U_SAMPLE_N, len(p_iso)))
    for x in p_sample:
        x["u"] = inst.present(x["r"])
    # synthetic rows at isolated G positions (both steps pooled) for f_H and f_U
    g_all_iso = []
    for step in ("X1", "X2"):
        g_all_iso += [x for x in classify(g_rows(on_u, off_u, STEP_TAGS[step]), E, confirmed=False) if x["st"][1] == "isolated"]
    r2 = random.Random(SEED + 1)
    pos = [(x["cyc"], x["r"]["f"], x["r"]["dt"], x["r"]["st"]) for x in g_all_iso]
    fh_n = fh_k = fu_k = 0
    if pos:
        for t in texts:
            c, f, dt, st = r2.choice(pos)
            j = E.judge(c, float(f), t)
            if j is None:
                continue
            fh_n += 1
            fh_k += int(j["plausible"])
            fu_k += inst.present(dict(st=st, f=f, dt=dt, tx=t))
    f_iso = ((fh_k / fh_n) if fh_n else 0.0, (fu_k / fh_n) if fh_n else 0.0)
    res["f_iso_positions"] = dict(n=fh_n, f_H=round(f_iso[0], 5), f_U=round(f_iso[1], 5))
    # Amendment 3 D7: the f_H used in H-COST is measured AT BURIED G POSITIONS (where H judges), pooled over the two steps per night; the V-H control f_RAND is the fallback only if there is no buried G row
    g_all_bur = []
    for step in ("X1", "X2"):
        g_all_bur += [x for x in classify(g_rows(on_u, off_u, STEP_TAGS[step]), E, confirmed=False) if x["st"][1] == "buried"]
    r3 = random.Random(SEED + 2)
    posb = [(x["cyc"], x["r"]["f"]) for x in g_all_bur]
    nb_n = nb_k = 0
    if posb:
        for t in texts:
            c, f = r3.choice(posb)
            j = E.judge(c, float(f), t)
            if j is not None:
                nb_n += 1
                nb_k += int(j["plausible"])
    f_rand_b = (nb_k / nb_n) if nb_n else f_ctrl[0]
    res["f_RAND_buried_G_positions"] = dict(n=nb_n, f=round(f_rand_b, 5), fallback_to_V_H_control=(nb_n == 0))
    f_ctrl_cost = (f_rand_b, f_ctrl[1], f_ctrl[2])
    n_ctrl = vh["n_rand_judgeable"]
    cyc_ids = cycles
    out_steps, agree_parts = {}, []
    for step in ("X1", "X2", "X2_passed", "X2_admitted"):
        tags = STEP_TAGS[step]
        g = g_rows(on_u, off_u, tags)
        recs = classify(g, E, confirmed=False)
        nu = sum(1 for x in recs if not x["judgeable"])
        c = step_cost(recs, p_recs, cyc_ids, inst, f_ctrl_cost, f_iso, n_ctrl, fh_n, p_sample, n_rand_b=nb_n)
        key = "X2" if step.startswith("X2") else step
        num = A[step]
        net = net_ci(num, A["nref"])
        entry = dict(NET_pp=round(net[0], 4), NET_ci=[round(net[1], 4), round(net[2], 4)], NET_newly_corroborated=int(num.sum()), n_ref=int(A["nref"].sum()),
                     G=len(g), G_judgeable=len(recs) - nu, G_unjudgeable=nu, H_COST_point=c["point"], H_COST_ci=c["ci"], phi_ci=c["phi_ci"])
        entry["H_COST"] = D.h_cost(c["ci"]["h_lo"][0], c["ci"]["h_hi"][1])
        out_steps[step] = entry
        if step in ("X1", "X2"):
            agree_parts.append(dict(step=step, n=c["_n_iso"], boot=c["_boot_diff"], point=c["point"]["phi_U"] - c["point"]["phi_H_iso"]))
    res["steps_final"] = out_steps
    on_pt, on_lo, on_hi = net_ci(A["on_net"], A["nref"])
    res["NET_ON_total"] = dict(NET_pp=round(on_pt, 4), NET_ci=[round(on_lo, 4), round(on_hi, 4)],
                               **D.net_on_check(on_pt, on_lo, on_hi, out_steps["X1"]["NET_pp"], out_steps["X2"]["NET_pp"]),
                               note="descriptive (Amendment 3 D1): flagged if below NET(X1)+NET(X2) by more than its CI half-width; no decision row reads it")
    res["NET_other_indirect_newly_corroborated"] = int(A["other"].sum())
    res["WSJT_rows_lost_in_ON"] = int(A["lost"].sum())
    # V-AGREE-NI pieces for this night: both steps' isolated G rows pooled
    n_iso = sum(x["n"] for x in agree_parts)
    if n_iso:
        wts = [x["n"] / n_iso for x in agree_parts]
        pdiff = sum(w * x["point"] for w, x in zip(wts, agree_parts))
        B = min(len(x["boot"]) for x in agree_parts if x["n"] > 0)
        boot = [sum(w * x["boot"][b] for w, x in zip(wts, agree_parts) if x["n"] > 0) for b in range(B)]
    else:
        pdiff, boot = float("nan"), []
    res["agree_night"] = dict(n=int(n_iso), point_diff=round(pdiff, 4) if n_iso else None)
    res["_agree_piece"] = dict(n=int(n_iso), point_diff=pdiff, boot=boot)
    # V-RUN
    rerun_ok = None
    if spec.get("off_rerun_dirs"):
        a, b = spec["off_rerun_dirs"]
        rerun_ok = ([(r["st"], r["k"], r["m"], r["f"], r["dt"], r["snr"], r["tx"]) for r in load_arm(a)] == [(r["st"], r["k"], r["m"], r["f"], r["dt"], r["snr"], r["tx"]) for r in load_arm(b)])
    vr_ok, parts = v_run_night(spec, off_rows, on_rows, cyc_stamps, bool(rerun_ok))
    res["V_RUN"] = dict(ok=vr_ok, **parts, off_rerun_checked=rerun_ok is not None)
    # descriptive
    x2 = log_lines(spec["on_dir"], "Diagnostic X2")
    res["X2_abandoned_candidates_ON"] = dict(lines=len(x2), candidates=sum(int(m.group(1)) for l in x2 for m in [re.search(r"abandonedCandidates=(\d+)", l)] if m),
                                             cycles_with_abandoned=sum(1 for l in x2 for m in [re.search(r"abandonedCandidates=(\d+)", l)] if m and int(m.group(1)) > 0), OFF=0)
    res["LATE_descriptive"] = dict(ON=late_desc(spec["on_dir"]), OFF=late_desc(spec["off_dir"]),
                                   X2_elapsedMs=pct([float(m.group(1)) for l in x2 for m in [re.search(r"elapsedMs=(\d+)", l)] if m]))
    res["DeltaUprime_ta_standing_route"] = "SUPERSEDED by the hybrid H-COST (Amendment 3 D6): the standing DeltaU'_ta is not produced; U' enters per row on the isolated G rows"
    res["run_seconds"] = round(time.time() - t0, 1)
    return res, res["_agree_piece"]


def gate_final():
    files = ["lr_decide.py", "lr_score.py", "lr_selftest.py", "../fd-proxy/fd_lib.py", "../fd-proxy/fd_pilot.py", "../fd-proxy/fd_uprime.py"]
    st = subprocess.run(["git", "-C", HERE, "status", "--porcelain", "--"] + files, capture_output=True, text=True, check=True).stdout.strip()
    if st:
        sys.exit("FINAL REFUSED: uncommitted or modified scorer files:\n" + st)
    return subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "selftest":
        import lr_selftest
        sys.exit(lr_selftest.main())
    if cmd == "pin":
        # FD-PROXY's own night: V-H must reproduce score_final_counts.json exactly
        NC = "D:/Projects/claude/_qa-scratch/xc-live-free/ON"
        ALL = "D:/Projects/claude/OpenWSFZ/artefacts/20261114_2312_endurance_run-gathered/wsjt-x/ALL.TXT"
        SCR = "D:/Projects/claude/_qa-scratch/fd-proxy"
        rows = load_arm(NC)
        E = L.Evidence(L.load_E(ALL))
        stamps = sorted({r["st"] for r in rows})
        use = set(stamps[283:])
        texts = [ln.rstrip("\n") for fn in ("nrand_rand.txt", "nrand_ap.txt") for ln in open(os.path.join(SCR, fn), encoding="utf-8")]
        v = controls_vh(rows, E, use, texts)
        v.pop("_f")
        ref = json.load(open(os.path.join(HERE, "..", "fd-proxy", "score_final_counts.json")))
        chk = [("s_weighted", v["s_weighted"], ref["s_weighted"]), ("V_SEP point", v["V_SEP"]["point"], ref["V_SEP"]["point"]), ("V_SEP ci", v["V_SEP"]["ci"], ref["V_SEP"]["ci"]),
               ("V_GHOST point", v["V_GHOST"]["point"], ref["V_GHOST"]["point"]), ("V_GHOST ci", v["V_GHOST"]["ci"], ref["V_GHOST"]["ci"]),
               ("V_BURIAL diff", v["V_BURIAL"]["diff"], ref["V_BURIAL"]["diff"]), ("V_BURIAL ci", v["V_BURIAL"]["ci"], ref["V_BURIAL"]["ci"]),
               ("f_RAND", v["f_RAND"], ref["f"]["f_RAND"]), ("f_MISS", v["f_MISS"], ref["f"]["f_MISS"]), ("f_NFIELD_visible", v["f_NFIELD_visible"], ref["f"]["f_NFIELD_visible"])]
        ok = True
        for name, a, b in chk:
            good = a == b
            ok &= good
            print(("PASS " if good else "FAIL ") + name + "  mine=%r  FD-PROXY=%r" % (a, b))
        print("PIN " + ("PASS: V-H reproduces FD-PROXY's frozen numbers exactly" if ok else "FAILED"))
        json.dump(dict(pin_ok=ok, mine=v), open(sys.argv[2], "w"), indent=1)
        sys.exit(0 if ok else 1)
    if cmd == "pilot":
        spec = json.load(open(sys.argv[2]))
        res, _ = run_night(spec, "pilot")
        json.dump(res, open(sys.argv[3], "w"), indent=1)
        print(json.dumps(res, indent=1))
        return
    if cmd in ("final", "smoke"):
        head = gate_final() if cmd == "final" else "SMOKE (no git gate; not a result)"
        specs = [json.load(open(p)) for p in sys.argv[2:-1]]
        out = sys.argv[-1]
        nights, pieces, results = [], [], []
        for sp in specs:
            res, piece = run_night(sp, "final")
            results.append(res)
            pieces.append(piece)
        agree = pooled_agree(pieces)
        decisions = {}
        for step in ("X1", "X2"):
            ns = []
            for res in results:
                s = res["steps_final"][step]
                ns.append(dict(vrun=res["V_RUN"]["ok"], vh=res["V_H"]["ok"], net_lo=s["NET_ci"][0], net_hi=s["NET_ci"][1], hcost=s["H_COST"]))
            decisions[step] = dict(zip(("outcome", "reason"), D.decide_step(ns, agree["status"])), per_night=ns)
        final = dict(git_head=head, nights=[{k: v for k, v in r.items() if k != "_agree_piece"} for r in results], V_AGREE_NI_pooled=agree, decisions=decisions)
        json.dump(final, open(out, "w"), indent=1)
        print(json.dumps(final["decisions"], indent=1))
        print(json.dumps(agree))
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
