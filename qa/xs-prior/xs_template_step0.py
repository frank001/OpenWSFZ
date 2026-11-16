#!/usr/bin/env python3
"""XS-TEMPLATE (programme angle G, Stage 1) STEP 0 + the (k) counts.  Spec: arch/exchange-step-prior 982ffb45, qa/rr-study/2026-11-16-2209-architect-to-qa-spec-xs-template.md.
No audio, no detector, no score.  HK-037: message text is read INSIDE these functions; only counts leave.  Working files (counts only) go to D:/Projects/claude/_qa-scratch/xs-template and are KEPT.

Usage:  python -I xs_template_step0.py selftest
        python -I xs_template_step0.py step0     F-KNOWN at 5/10/20 min, the geometry, the window, T0 and its CI, the CLOSE-EARLY row, K_low / K_all, P counts, the null sizes

FROZEN here before the first run (the spec's section 2 and 3.3, with QA's interpretations stated):
  The S rows are exactly XS-PRIOR's (xs_count.py 9a2c74c2; the run asserts S1 872 and S2 277 against xs_result.json).  S1 cue: the first matched 'Y X Pp' at t-15; S2 cue: the first matched 'X Y Pp' at t-30 within 10 Hz.
  F-KNOWN (S1 rows): the replier Y (the SENDER, F2, of the unreached row) has a MATCHED decode of ours (as sender: the 2nd token of a standard message, or the sender token of a CQ / QRZ / DE) in the 40 cycles (10 min) before t;
    the most recent one gives the centre (f_Y, dt_Y) = OUR frequency and OUR dt from owsfz/ALL.TXT.  5 and 20 min (20 and 80 cycles) are descriptives.  (INTERPRETATION: a CQ decode of Y counts as a decode from the replier; the non-CQ-only share is a descriptive.)
  S2 rows: the cue's own position (our decode of the cue).
  GEOMETRY (no score): df = |f_truth - f_centre|, ddt = |dt_truth - (dt_centre - 0.600)| with the truth = WSJT-X's position of the unreached row and 0.600 s = this night's measured offset (COR median, XC-LIVE).
  WINDOW (superseded by Amendment 1: FROZEN at +-3.125 Hz x +-0.20 s, rows outside NOT TESTABLE; the p95 rule below is kept as a descriptive only): +-3.125 Hz and +-0.12 s; PER AXIS, if fewer than 95 % of the testable rows fall inside that half-width, that axis is widened to the observed 95th percentile of its |error| (INTERPRETATION of 'in each axis').
  T0 = (S2 + S1 with F-KNOWN, inside the final window on both axes) / n_ref, pp, cycle bootstrap B 2000 seed 20261116.  CLOSE-EARLY iff CI_hi(T0) < 0.4 pp.
  K per cycle t = sum over matched priors p of |N(Pp)| (cue rows at t-15, F-KNOWN replier) and |N2(Pp)| (cue rows at t-30), parsable step only; K_low = the sets of <= 3 templates, K_all = every set; K = the median over cycles.
  P = matched rows that are on-script replies to a matched cue at t-15 (XS-PRIOR 7,435); P_low = those whose set is K-low.  Null size per variant: n(N-OPP) >= 3 / FA*, FA* = 0.021 / K."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "endurance"))
import anova_common as AC     # noqa: E402
import xs_count as X          # noqa: E402

OUT = "D:/Projects/claude/_qa-scratch/xs-template"
DT_OFFSET_S = 0.600           # OWS dt minus WSJT-X DT, measured on this night (XC-LIVE report 2, COR median)
GATE_DF_HZ, GATE_DT_S = 3.125, 0.12
INSIDE_MIN = 0.95
WIN_DF_HZ, WIN_DT_S = 3.125, 0.20   # FROZEN by the Architect (XS-TEMPLATE Amendment 1, 06198a8d, E205): the p95 rule gave 579 Hz because frequency error is bimodal; rows outside are NOT TESTABLE (not detected, kept in the denominator)
LOOKBACKS = {"5min": 20, "10min": 40, "20min": 80}
MAIN_LOOKBACK = 40
CLOSE_EARLY_PP = 0.4
FA_BUDGET = 0.021
S1_EXPECT, S2_EXPECT = 872, 277
assert (DT_OFFSET_S, GATE_DF_HZ, GATE_DT_S, INSIDE_MIN, MAIN_LOOKBACK, CLOSE_EARLY_PP, FA_BUDGET, S1_EXPECT, S2_EXPECT, WIN_DF_HZ, WIN_DT_S) == (0.6, 3.125, 0.12, 0.95, 40, 0.4, 0.021, 872, 277, 3.125, 0.20)


def sender_of(text):
    """the sending station's token of any parsable message (standard: 2nd token; CQ/QRZ/DE: after an optional short modifier); None if hashed or not parsable."""
    if "<" in text or ";" in text:
        return None
    t = text.split()
    if not t:
        return None
    if t[0] in ("CQ", "QRZ", "DE"):
        if t[0] == "CQ" and len(t) >= 4 and t[1].isalpha() and len(t[1]) <= 4:
            return t[2]
        return t[1] if len(t) >= 2 else None
    return t[1] if len(t) >= 2 else None


def load2():
    """-> stamps, pc (xs_count's structure), ext[i][j] = (wsjt dt, our freq, our dt) for MATCHED rows else None.  Text stays in memory."""
    ar = [l.split(",")[0] for l in open(X.NIGHT + "/owsfz/cycle-archive.csv", encoding="utf-8")][1:]
    stamps = [a[:-4] for a in ar]
    w = AC.parse_all_txt(X.NIGHT + "/wsjt-x/ALL.TXT")
    o = AC.parse_all_txt(X.NIGHT + "/owsfz/ALL.TXT")
    by_w, by_o = collections.defaultdict(list), collections.defaultdict(list)
    for r in w:
        by_w[r["ts"]].append(r)
    for r in o:
        by_o[(r["ts"], AC.normalize_hash_tokens(r["message"]))].append(r)
    cycles, ext = {}, {}
    n_matched = 0
    for s in stamps:
        rows, ex = [], []
        used = collections.Counter()
        for r in by_w.get(s, []):
            k = (s, AC.normalize_hash_tokens(r["message"]))
            cand = by_o.get(k, [])
            if used[k] < len(cand):
                orow = cand[used[k]]
                used[k] += 1
                n_matched += 1
                rows.append((r["snr"], r["freq_hz"], r["message"], True))
                ex.append((r["dt"], orow["freq_hz"], orow["dt"]))
            else:
                rows.append((r["snr"], r["freq_hz"], r["message"], False))
                ex.append(None)
        cycles[s] = rows
        ext[s] = ex
    assert n_matched == X.N_MATCHED_EXPECT, n_matched
    pc = X.prep(stamps, cycles)
    return stamps, pc, [ext[s] for s in stamps]


def known_index(pc, ext):
    """per cycle i: sender -> (our f, our dt) of the LAST matched decode of that sender in the cycle (text only read here)."""
    idx = []
    for i, rows in enumerate(pc):
        d = {}
        for j, (snr, f, text, m, p) in enumerate(rows):
            if m:
                s = sender_of(text)
                if s is not None and ext[i][j] is not None:
                    d[s] = (ext[i][j][1], ext[i][j][2])
        idx.append(d)
    return idx


def lookup(idx, i, y, span):
    for k in range(1, span + 1):
        if i - k < 0:
            break
        if y in idx[i - k]:
            return idx[i - k][y], k
    return None, None


def s_rows(pc, ext):
    """the S1 / S2 rows with their cue position: [(i, class, f_truth, dt_truth, y_or_none, cue_ours (f, dt) or None, set size, template class)]."""
    U = []
    cnt = collections.Counter()
    for i, rows in enumerate(pc):
        xc = None
        for j, (snr, f, text, m, p) in enumerate(rows):
            if m or p[0] != "ok":
                continue
            if xc is None:
                xc = [X.prior_matched(pc, i, lag) for lag in (2, 4, 6)]
            if any(pt == text and abs(pf - f) <= X.WINDOW_HZ for pr in xc for pf, pt, _ in pr):
                continue
            U.append((i, j, snr, f, text, p))
    out = []
    for i, j, snr, f, text, p in U:
        _, f1, f2, tu, vu = p
        wdt = ext[i][j]
        row_dt = None
        # S1: matched 'Y X Pp' at t-15 (Y = f2 of u is its addressee f1)
        s1 = None
        if i >= 1:
            for jj, (snr2, pf, pt, pm, pp) in enumerate(pc[i - 1]):
                if pm and pp[0] == "ok" and pp[1] == f2 and pp[2] == f1 and X.in_n(pp[3], tu, vu):
                    s1 = (jj, pp)
                    break
        s2 = None
        if s1 is None and i >= 2:
            for jj, (snr2, pf, pt, pm, pp) in enumerate(pc[i - 2]):
                if pm and pp[0] == "ok" and pp[1] == f1 and pp[2] == f2 and abs(pf - f) <= X.WINDOW_HZ and pt != text and X.in_n2(pp[3], tu, vu):
                    s2 = (jj, pp)
                    break
        if s1 is not None:
            out.append((i, j, "S1", f2, s1[0], s1[1]))
        elif s2 is not None:
            out.append((i, j, "S2", f2, s2[0], s2[1]))
    return out


def window_from(dfs, ddts):
    """the final half-widths: the gate per axis unless fewer than 95 % of the testable rows fall inside it, then the observed 95th percentile of |error|."""
    res = {}
    for name, v, gate in (("df_hz", dfs, GATE_DF_HZ), ("dt_s", ddts, GATE_DT_S)):
        v = np.asarray(v, dtype=float)
        inside = float((v <= gate).mean()) if len(v) else 0.0
        half = gate if inside >= INSIDE_MIN else float(np.percentile(v, 95))
        res[name] = {"gate": gate, "share_inside_gate": inside, "half_width_used": half, "widened": inside < INSIDE_MIN, "p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "n": int(len(v))}
    return res


def step0():
    stamps, pc, ext = load2()
    n = len(pc)
    nref_c = np.array([len(r) for r in pc], dtype=float)
    idx = known_index(pc, ext)
    idx_noncq = None
    rows = s_rows(pc, ext)
    n1 = sum(1 for r in rows if r[2] == "S1")
    n2 = len(rows) - n1
    ref = json.load(open(OUT + "/../xs-prior/xs_result.json"))["rows"]
    assert (n1, n2) == (S1_EXPECT, S2_EXPECT) == (ref["S1"], ref["S2"]), (n1, n2, ref)
    # F-KNOWN
    fk = {k: 0 for k in LOOKBACKS}
    fk_noncq = 0
    recs = []                                      # (i, class, df, ddt or None)
    for i, j, cls, y, jj, cue in rows:
        f_t, dt_t = pc[i][j][1], ext_truth(ext, i, j, pc)
        if cls == "S2":
            cpos = ext[i - 2][jj]
            recs.append((i, "S2", abs(f_t - cpos[1]), abs(dt_t - (cpos[2] - DT_OFFSET_S))))
            continue
        for name, span in LOOKBACKS.items():
            pos, _ = lookup(idx, i, y, span)
            fk[name] += pos is not None
        pos, k = lookup(idx, i, y, MAIN_LOOKBACK)
        if pos is not None:
            recs.append((i, "S1", abs(f_t - pos[0]), abs(dt_t - (pos[1] - DT_OFFSET_S))))
    s1_known = sum(1 for r in recs if r[1] == "S1")
    win = window_from([r[2] for r in recs], [r[3] for r in recs])
    hf, ht = WIN_DF_HZ, WIN_DT_S                      # the FROZEN window (the geometry above is descriptive: the p95 rule it would have applied is not used)
    t0_c = np.zeros(n)
    inside_by = collections.Counter()
    for i, cls, df, ddt in recs:
        if df <= hf and ddt <= ht:
            t0_c[i] += 1
            inside_by[cls] += 1
    pp, ci = X.boot(t0_c, nref_c)
    # K per cycle
    k_low, k_all = np.zeros(n), np.zeros(n)
    p_rows = p_low = 0
    for t in range(n):
        if t >= 1:
            for jj, (snr, pf, pt, pm, pp_) in enumerate(pc[t - 1]):
                if pm and pp_[0] == "ok":
                    sz = X.size_n(pp_[3])
                    if sz > 0 and lookup(idx, t, pp_[1], MAIN_LOOKBACK)[0] is not None:     # the replier = the cue's addressee F1
                        k_all[t] += sz
                        k_low[t] += sz if sz <= X.K_LOW_MAX else 0
        if t >= 2:
            for jj, (snr, pf, pt, pm, pp_) in enumerate(pc[t - 2]):
                if pm and pp_[0] == "ok":
                    sz = X.size_n2(pp_[3])
                    if sz > 0:
                        k_all[t] += sz
                        k_low[t] += sz if sz <= X.K_LOW_MAX else 0
        if t >= 1:                                               # P rows (matched on-script replies to a matched cue at t-15)
            c15 = [pp_ for _, _, _, pm, pp_ in pc[t - 1] if pm and pp_[0] == "ok"]
            for snr, f, text, m, p in pc[t]:
                if not m or p[0] != "ok":
                    continue
                for pp_ in c15:
                    if pp_[1] == p[2] and pp_[2] == p[1] and X.in_n(pp_[3], p[3], p[4]):
                        p_rows += 1
                        p_low += X.size_n(pp_[3]) <= X.K_LOW_MAX
                        break
    K_low, K_all = float(np.median(k_low)), float(np.median(k_all))
    need = lambda k: (3 * k / FA_BUDGET) if k > 0 else None
    out = {"mode": "step0 + (k) counts: no audio, no score",
           "S_rows": {"S1": n1, "S2": n2, "asserted_equal_to_xs_result": True},
           "F_KNOWN_S1_share": {k: v / n1 for k, v in fk.items()}, "F_KNOWN_S1_count": fk, "S1_testable_10min": s1_known,
           "geometry_descriptive_p95_rule_NOT_used": win, "frozen_window": {"df_hz": WIN_DF_HZ, "dt_s": WIN_DT_S}, "rows_inside_frozen_window": dict(inside_by),
           "not_testable": {"S_rows": n1 + n2, "testable_inside_window": int(t0_c.sum()), "not_testable_share_of_S": 1 - float(t0_c.sum()) / (n1 + n2), "S1_without_F_KNOWN": n1 - s1_known, "testable_but_outside_window": len(recs) - int(t0_c.sum())},
           "T0": {"rows": int(t0_c.sum()), "pp_of_n_ref": pp, "CI_pp": ci, "bar_pp": CLOSE_EARLY_PP, "CLOSE_EARLY": bool(ci[1] < CLOSE_EARLY_PP)},
           "K": {"K_low_median_per_cycle": K_low, "K_all_median_per_cycle": K_all, "K_low_mean": float(k_low.mean()), "K_all_mean": float(k_all.mean()),
                 "FA_star_low": FA_BUDGET / K_low if K_low else None, "FA_star_all": FA_BUDGET / K_all if K_all else None,
                 "N_OPP_tests_needed_low": need(K_low), "N_OPP_tests_needed_all": need(K_all)},
           "P": {"rows": p_rows, "rows_K_low": int(p_low), "xs_prior_matched_on_script_replies": 7435}}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(OUT + "/xs_step0.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


def ext_truth(ext, i, j, pc):
    """WSJT-X's DT of the unreached row (unmatched rows carry no OWS position: ext is None there; the truth dt is read from the raw rows)."""
    return _TRUTH_DT[(i, j)]


_TRUTH_DT = {}


def prime_truth():
    w = AC.parse_all_txt(X.NIGHT + "/wsjt-x/ALL.TXT")
    ar = [l.split(",")[0] for l in open(X.NIGHT + "/owsfz/cycle-archive.csv", encoding="utf-8")][1:]
    stamps = [a[:-4] for a in ar]
    by = collections.defaultdict(list)
    for r in w:
        by[r["ts"]].append(r["dt"])
    for i, s in enumerate(stamps):
        for j, d in enumerate(by.get(s, [])):
            _TRUTH_DT[(i, j)] = d


def selftest():
    ok = True

    def chk(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print("FAIL", name, got, want)
    chk("sender standard", sender_of("Q1AAA Q2BBB -10"), "Q2BBB")
    chk("sender cq", sender_of("CQ Q2BBB JO93"), "Q2BBB")
    chk("sender cq modifier", sender_of("CQ DX Q2BBB JO93"), "Q2BBB")
    chk("sender hashed", sender_of("<...> Q2BBB -10"), None)
    chk("sender qrz", sender_of("QRZ Q2BBB JO93"), "Q2BBB")
    idx = [{"Q2BBB": (1500.0, 0.8)}, {}, {}]
    chk("lookup most recent", lookup(idx, 2, "Q2BBB", 40)[0], (1500.0, 0.8))
    chk("lookup too far", lookup(idx, 2, "Q2BBB", 1)[0], None)
    chk("lookup absent", lookup(idx, 2, "Q9ZZZ", 40)[0], None)
    # window: all inside the gate -> not widened; 90 % inside -> widened to p95
    w1 = window_from([0.1] * 100, [0.05] * 100)
    chk("window kept", (w1["df_hz"]["widened"], w1["df_hz"]["half_width_used"]), (False, 3.125))
    v = [0.5] * 90 + [8.0] * 10
    w2 = window_from(v, [0.05] * 100)
    chk("window widened", (w2["df_hz"]["widened"], w2["df_hz"]["half_width_used"] > 3.125, w2["dt_s"]["widened"]), (True, True, False))
    chk("window exactly 95 % inside is not widened", window_from([0.5] * 95 + [9.0] * 5, [0.0] * 100)["df_hz"]["widened"], False)
    print("selftest ALL PASS" if ok else "selftest FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        sys.exit(selftest())
    prime_truth()
    step0()
