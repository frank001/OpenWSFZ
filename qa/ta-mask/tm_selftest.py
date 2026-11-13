#!/usr/bin/env python3
"""TA-MASK self-test: synthetic behaviour tests of tm_lib, then MUTATIONS (each must make a test fail).  python tm_selftest.py"""
from __future__ import annotations

import importlib
import os
import sys
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tm_lib as M          # noqa: E402

SYNC = list(range(0, 7)) + list(range(36, 43)) + list(range(72, 79))
DATA = [k for k in range(79) if k not in set(SYNC)]


def one_neighbour(f_n, dt_n, tones, c_off=0.0):
    return M.neighbour_entries([(f_n, dt_n, tones)], c_off)


def t_mask_geometry():
    tn = [3] * 79                                          # neighbour on tone 3 all message long, f_n = 1000 -> 1018.75 Hz
    ent = one_neighbour(1000.0, 0.0, tn)
    m = M.mask_matrix(1000.0, 0.0, ent)                    # row at 1000: bin b at 1000 + 6.25 b; the tone is on bin 3 exactly
    assert m.shape == (79, 8)
    assert list(np.where(m[10])[0]) == [2, 3, 4]           # within 6.25 INCLUSIVE: bins 2 and 4 are exactly 6.25 away and are masked
    m2 = M.mask_matrix(1003.0, 0.0, ent)                   # distances |1018.75 - (1003 + 6.25 b)|: b=2 3.25, b=3 3.0, b=4 9.25, b=1 9.5
    assert list(np.where(m2[10])[0]) == [2, 3]
    assert not M.mask_matrix(1100.0, 0.0, ent).any()


def t_mask_time_overlap():
    tn = [0] * 40 + [7] * 39                               # tone 0 for symbols 0-39, tone 7 afterwards
    ent = one_neighbour(1000.0, 0.0, tn)
    m = M.mask_matrix(1000.0, 0.0, ent)
    assert m[5, 0] and not m[5, 7] and m[60, 7] and not m[60, 0]
    mshift = M.mask_matrix(1000.0, 0.08, ent)              # 0.08 s later: row symbol 39 straddles neighbour symbols 39 and 40 -> both tones masked
    assert mshift[39, 0] and mshift[39, 7]
    assert not M.mask_matrix(1000.0, 20.0, ent).any()      # all the row's symbols start after the neighbour has ended
    assert not M.mask_matrix(1000.0, 0.0, M.neighbour_entries([], 0.0)).any()


def t_calibration_offsets_neighbour():
    e0 = one_neighbour(1000.0, 0.0, [0] * 79, c_off=0.48)
    assert abs(e0[1][0] - 0.48) < 1e-12 and abs(e0[2][0] - 0.64) < 1e-12


def t_masked_argmax_and_scores():
    X = np.zeros((79, 8))
    own = [k % 8 for k in range(79)]
    for k in range(79):
        X[k, own[k]] = 1.0
    X[10, 4] = 9.0                                         # a strong neighbour bin beats the own tone at symbol 10 (symbol 10 is a data symbol, own tone 2)
    assert 10 in DATA and own[10] == 2
    mask = np.zeros((79, 8), dtype=bool)
    am = M.masked_argmax(X, mask)
    assert am[10] == 4 and am[11] == own[11]
    s0, n0 = M.data_score(am, mask, own, DATA)
    assert n0 == 58 and abs(s0 - 57 / 58) < 1e-12
    mask[10, 4] = True                                     # masking the neighbour's bin restores the own tone at symbol 10
    am2 = M.masked_argmax(X, mask)
    assert am2[10] == own[10]
    s1, n1 = M.data_score(am2, mask, own, DATA)
    assert n1 == 58 and s1 == 1.0
    mask2 = mask.copy()
    mask2[12, own[12]] = True                              # the own tone itself masked: that symbol is not scorable (not wrong)
    s2, n2 = M.data_score(M.masked_argmax(X, mask2), mask2, own, DATA)
    assert n2 == 57 and s2 == 1.0
    allm = np.ones((79, 8), dtype=bool)
    assert (M.masked_argmax(X, allm) == -1).all() and M.data_score(M.masked_argmax(X, allm), allm, own, DATA)[1] == 0


def t_sync_share():
    sync_tones = [(k * 3) % 8 for k in range(21)]
    am = np.full(79, -1)
    for k, t in zip(SYNC, sync_tones):
        am[k] = t
    mask = np.zeros((79, 8), dtype=bool)
    assert M.sync_share(am, mask, SYNC, sync_tones) == 1.0
    am[SYNC[0]] = (sync_tones[0] + 1) % 8
    assert abs(M.sync_share(am, mask, SYNC, sync_tones) - 20 / 21) < 1e-12
    mask[SYNC[0], sync_tones[0]] = True                    # the wrong symbol's own tone is masked: it leaves the denominator
    assert M.sync_share(am, mask, SYNC, sync_tones) == 1.0
    assert M.sync_share(am, np.ones((79, 8), dtype=bool), SYNC, sync_tones) == -1.0


def t_present_rule():
    assert M.present(0.5, 20, 0.4) and not M.present(0.5, 19, 0.4) and M.present(0.4, 30, 0.4) and not M.present(0.39, 30, 0.4) and not M.present(float("nan"), 30, 0.4)


def t_threshold():
    a = list(np.linspace(0.0, 0.3, 1000))
    b = list(np.linspace(0.0, 0.5, 1000))
    t, p, bb = M.threshold_tm(a, b)
    assert abs(p - np.percentile(a, 99)) < 1e-12 and abs(bb - np.percentile(b, 99)) < 1e-12 and t == bb
    t2, p2, b2 = M.threshold_tm(b, a)
    assert t2 == p2 and t2 > b2
    assert np.isnan(M.pct99([float("nan")]))


def t_decide():
    ok = [0.9, 1.0]
    base = {"ci_B1": ok, "ci_B1m": ok, "ci_Tbur": [0.82, 0.9], "ci_ghost_diff": [0.0, 0.04], "n_Tbur": 237}
    assert M.decide(base) == "REPAIRED"
    assert M.decide(dict(base, ci_B1=[0.79, 1.0])) == "VOID" and M.decide(dict(base, ci_B1m=[0.79, 1.0])) == "VOID" and M.decide(dict(base, n_Tbur=99)) == "VOID"
    assert M.decide(dict(base, ci_B1=[0.80, 1.0])) == "REPAIRED"
    assert M.decide(dict(base, ci_ghost_diff=[0.0, 0.051])) == "CREDULOUS" and M.decide(dict(base, ci_ghost_diff=[0.0, 0.05])) == "REPAIRED"
    assert M.decide(dict(base, ci_Tbur=[0.79, 0.9])) == "NOT-REPAIRED" and M.decide(dict(base, ci_Tbur=[0.80, 0.9])) == "REPAIRED"
    assert M.decide(dict(base, ci_B1=[0.5, 1.0], ci_ghost_diff=[0, 0.5])) == "VOID"          # first match wins
    assert M.decide(dict(base, ci_ghost_diff=[0, 0.5], ci_Tbur=[0.1, 0.2])) == "CREDULOUS"


def t_paired_ghost_diff():
    cix = {f"c{i}": i for i in range(4)}
    pm = [("c0", "A", True), ("c1", "A", False), ("c2", "A", True), ("c3", "A", False)]
    pu = [("c0", "A", True), ("c1", "A", True), ("c2", "A", False), ("c3", "A", False)]
    d = M.paired_diff(pm, pu, 4, cix, np.array([[0, 1, 2, 3], [0, 0, 0, 0], [1, 1, 1, 1]]))
    assert abs(d[0]) < 1e-12 and abs(d[1]) < 1e-12 and abs(d[2] + 1.0) < 1e-12        # (1+0+1+0 - 1+1+0+0)/4 = 0; c0 only: 1 - 1 = 0; c1 only: 0 - 1 = -1
    try:
        M.paired_diff(pm, pu[:3], 4, cix, np.array([[0, 1, 2, 3]]))
        raise RuntimeError("unpaired rows accepted")
    except AssertionError:
        pass


def t_bootstrap():
    cix = {f"c{i}": i for i in range(4)}
    t = M.tally([("c0", "A", True), ("c0", "A", False), ("c1", "B", True)], 4, cix)
    r = M.rate(t, np.array([[0, 1, 2, 3], [2, 2, 2, 2]]))
    assert abs(r[0] - 2 / 3) < 1e-12 and np.isnan(r[1])


TESTS = [t_mask_geometry, t_mask_time_overlap, t_calibration_offsets_neighbour, t_masked_argmax_and_scores, t_sync_share, t_present_rule, t_threshold, t_decide, t_paired_ghost_diff, t_bootstrap]


def run_tests():
    bad = []
    for t in TESTS:
        try:
            t()
        except AssertionError:
            bad.append(t.__name__)
        except Exception as e:                 # noqa: BLE001
            bad.append(t.__name__ + ":" + type(e).__name__)
    return bad


def src_mut(old, new):
    def m():
        s = open(os.path.join(HERE, "tm_lib.py"), encoding="utf-8").read()
        assert old in s, old
        ns = {}
        exec(compile(s.replace(old, new, 1), "tm_lib_mut", "exec"), ns)
        for k, v in ns.items():
            if not k.startswith("__"):
                setattr(M, k, v)
    return m


MUTS = [
    ("mask strict <", src_mut("<= MASK_HZ + 1e-9", "< MASK_HZ - 1e-9")),
    ("mask width doubled", src_mut("<= MASK_HZ + 1e-9", "<= 2 * MASK_HZ + 1e-9")),
    ("no time overlap", src_mut("overlap = (ts[None, :] < b[:, None]) & (te[None, :] > a[:, None])", "overlap = np.ones((N_SYM, tf.size), dtype=bool)")),
    ("overlap start-only", src_mut("(te[None, :] > a[:, None])", "(ts[None, :] > a[:, None] - 1e9)")),
    ("bin spacing 3.125", src_mut("bins = f_pos + TONE_HZ * np.arange(N_TONES)", "bins = f_pos + 3.125 * np.arange(N_TONES)")),
    ("symbol length 0.32", src_mut("a = st + SYM_S * np.arange(N_SYM)", "a = st + 0.32 * np.arange(N_SYM)")),
    ("calibration dropped", src_mut("t0 = dt_n + c_off", "t0 = dt_n")),
    ("neighbour tone not offset", src_mut("tf.append(f_n + TONE_HZ * tn[m])", "tf.append(f_n)")),
    ("masked bins not excluded", src_mut("m = np.where(mask, -1.0, Xabs)", "m = Xabs")),
    ("all-masked not -1", src_mut("return np.where(mask.all(axis=1), -1, am)", "return am")),
    ("own-masked symbols counted", src_mut("sc = [k for k in data_idx if not mask[k, seq[k]]]", "sc = list(data_idx)")),
    ("sync own-masked counted", src_mut("ok = [(not mask[k, t]) for k, t in zip(sync_idx, sync_tones)]", "ok = [True for k, t in zip(sync_idx, sync_tones)]")),
    ("floor 20 -> 10", src_mut("MIN_SCORABLE = 20 ", "MIN_SCORABLE = 10 ")),
    ("present > not >=", src_mut("s >= t_m)", "s > t_m)")),
    ("T_M = pooled only", src_mut("return max(p, b), p, b", "return p, p, b")),
    ("T_M = min", src_mut("return max(p, b), p, b", "return min(p, b), p, b")),
    ("p99 -> p95", src_mut("np.percentile(v, 99.0)", "np.percentile(v, 95.0)")),
    ("VOID drops B1m", src_mut('r["ci_B1m"][0] < BAR_PRESENT or ', "")),
    ("VOID drops V-N", src_mut(' or r["n_Tbur"] < V_N_TBUR', "")),
    ("diff uses M only", src_mut("return (km[idx].sum(axis=1) - ku[idx].sum(axis=1)) / np.where(n[idx].sum(axis=1) > 0, n[idx].sum(axis=1), np.nan)", "return km[idx].sum(axis=1) / np.where(n[idx].sum(axis=1) > 0, n[idx].sum(axis=1), np.nan)")),
    ("ghost bar 0.05 -> 0.10", src_mut("BAR_GHOST = 0.05 ", "BAR_GHOST = 0.10 ")),
    ("REPAIRED on CI_hi", src_mut('if r["ci_Tbur"][0] >= BAR_PRESENT:', 'if r["ci_Tbur"][1] >= BAR_PRESENT:')),
    ("CREDULOUS after REPAIRED", src_mut('    if r["ci_ghost_diff"][1] > BAR_GHOST:\n        return "CREDULOUS"\n    if r["ci_Tbur"][0] >= BAR_PRESENT:\n        return "REPAIRED"\n',
                                         '    if r["ci_Tbur"][0] >= BAR_PRESENT:\n        return "REPAIRED"\n    if r["ci_ghost_diff"][1] > BAR_GHOST:\n        return "CREDULOUS"\n')),
]


def main():
    bad = run_tests()
    print("unmutated: " + ("ALL PASS" if not bad else "FAIL " + str(bad)))
    if bad:
        sys.exit(1)
    surv = []
    for name, m in MUTS:
        importlib.reload(M)
        try:
            m()
        except AssertionError as e:
            if any(fr.filename == "tm_lib_mut" for fr in traceback.extract_tb(e.__traceback__)):
                print(f"{name:30s} killed by the library's own constant assertion")
                continue
            print(f"{name:30s} MUTATION NOT APPLIED ({e})")
            surv.append(name)
            continue
        killed = run_tests()
        print(f"{name:30s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            surv.append(name)
    importlib.reload(M)
    print(f"{len(MUTS) - len(surv)} of {len(MUTS)} mutations killed")
    sys.exit(1 if surv else 0)


if __name__ == "__main__":
    main()
