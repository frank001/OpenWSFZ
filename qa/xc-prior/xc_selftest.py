#!/usr/bin/env python3
"""XC-PRIOR self-test: synthetic behaviour tests of xc_lib, then MUTATIONS (each must make a test fail).   python xc_selftest.py"""
from __future__ import annotations

import importlib
import os
import sys
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xc_lib as L          # noqa: E402


def cyc(n=8):
    return [[] for _ in range(n)]


def t_e1_basic_and_lags():
    m = cyc()
    m[1] = [("CQ Q1ABC AB12", 1000, 1)]
    assert L.prior_hit(("CQ Q1ABC AB12", 1005), 3, L.SAME_LAGS, m) == ("E1", 2, 1)                 # 2 cycles = 30 s
    m = cyc(); m[0] = [("CQ Q1ABC AB12", 1000, 2)]
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 4, L.SAME_LAGS, m) == ("E1", 4, 2)                 # 60 s
    m = cyc(); m[0] = [("CQ Q1ABC AB12", 1000, 1)]
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 6, L.SAME_LAGS, m) == ("E1", 6, 1)                 # 90 s
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 7, L.SAME_LAGS, m) == (None, None, None)           # 7 cycles back is outside the lags
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 3, L.SAME_LAGS, m) == (None, None, None)           # 3 cycles back is the OPPOSITE parity: not a same-parity prior
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 1, L.OPP_LAGS, m) == ("E1", 1, 1)                   # 15 s opposite
    m = cyc(); m[3] = [("CQ Q1ABC AB12", 1000, 1)]
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 4, L.OPP_LAGS, m) == ("E1", 1, 1)
    assert L.prior_hit(("CQ Q1ABC AB12", 1000), 5, L.SAME_LAGS, m) == ("E1", 2, 1)


def t_window_and_text():
    m = cyc(); m[0] = [("CQ Q1ABC AB12", 1000, 1)]
    assert L.prior_hit(("CQ Q1ABC AB12", 1010), 2, L.SAME_LAGS, m)[0] == "E1"                       # exactly 10 Hz: inside (<=)
    assert L.prior_hit(("CQ Q1ABC AB12", 1011), 2, L.SAME_LAGS, m)[0] is None
    assert L.prior_hit(("CQ Q1ABC AB12", 990), 2, L.SAME_LAGS, m)[0] == "E1"
    assert L.prior_hit(("CQ Q1ABC AB13", 1000), 2, L.SAME_LAGS, m)[0] == "E2"                      # same first two fields, different message
    assert L.prior_hit(("CQ Q1XYZ AB12", 1000), 2, L.SAME_LAGS, m)[0] is None                       # different station
    m = cyc(); m[0] = [("Q1ABC Q2DEF -10", 1500, 1)]
    assert L.prior_hit(("Q1ABC Q2DEF R-12", 1500), 2, L.SAME_LAGS, m) == ("E2", 2, 1)              # same call pair, different message
    assert L.prior_hit(("Q1ABC Q2DEF -10", 1500), 2, L.SAME_LAGS, m)[0] == "E1"
    assert L.first_two("73") is None and L.first_two("A B C") == ("A", "B")


def t_e1_wins_over_e2():
    m = cyc(); m[0] = [("Q1ABC Q2DEF -10", 1500, 1)]; m[2] = [("Q1ABC Q2DEF -12", 1500, 1)]
    # at i = 4: lag 2 -> cycle 2 holds the E2-candidate, lag 4 -> cycle 0 holds the exact repeat: E1 must win even though E2 appears first
    assert L.prior_hit(("Q1ABC Q2DEF -10", 1500), 4, L.SAME_LAGS, m) == ("E1", 4, 1)
    m = cyc(); m[0] = [("Q1ABC Q2DEF -10", 1500, 1)]; m[2] = [("Q1ABC Q2DEF -10", 1500, 4)]
    assert L.prior_hit(("Q1ABC Q2DEF -10", 1500), 4, L.SAME_LAGS, m) == ("E1", 2, 4)               # nearest lag wins within E1


def t_missing_priors():
    m = cyc(3)
    assert L.prior_hit(("X Y Z", 1000), 1, L.SAME_LAGS, m) == (None, None, None)                     # i - 2 < 0 and so on: no prior, no crash


def t_pp_ci():
    cnt = np.array([1.0, 0.0, 3.0, 0.0])
    nref = np.array([10.0, 10.0, 10.0, 10.0])
    idx = np.array([[0, 1, 2, 3], [0, 0, 0, 0], [2, 2, 2, 2]])
    pp, ci = L.pp_ci(cnt, nref, idx)
    assert abs(pp - 10.0) < 1e-12                                                                     # 4 / 40 = 10 pp
    num = cnt[idx].sum(axis=1); den = nref[idx].sum(axis=1)
    assert list(num) == [4, 4, 12] and list(den) == [40, 40, 40]
    assert abs(ci[0] - np.percentile([10.0, 10.0, 30.0], 2.5)) < 1e-9 and abs(ci[1] - np.percentile([10.0, 10.0, 30.0], 97.5)) < 1e-9


def t_v_par():
    assert L.v_par(1, 4) and not L.v_par(1, 3) and L.v_par(0, 0) and L.v_par(25, 100) and not L.v_par(26, 100)


def t_decide():
    assert L.decide([0.2, 0.99], True) == "CLOSE" and L.decide([0.2, 0.99], False) == "CLOSE"        # A1: V-PAR does not gate CLOSE
    assert L.decide([0.5, 1.0], True) == "BETWEEN"                                                    # CI_hi = 1.0 is not < 1.0
    assert L.decide([1.0, 2.0], True) == "PURSUE" and L.decide([0.99, 2.0], True) == "BETWEEN"
    assert L.decide([1.0, 2.0], False) == "VOID" and L.decide([0.5, 2.0], False) == "VOID"
    assert L.decide([0.0, 0.0], False) == "CLOSE"


TESTS = [t_e1_basic_and_lags, t_window_and_text, t_e1_wins_over_e2, t_missing_priors, t_pp_ci, t_v_par, t_decide]


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
        s = open(os.path.join(HERE, "xc_lib.py"), encoding="utf-8").read()
        assert old in s, old
        ns = {}
        exec(compile(s.replace(old, new, 1), "xc_lib_mut", "exec"), ns)
        for k, v in ns.items():
            if not k.startswith("__"):
                setattr(L, k, v)
    return m


MUTS = [
    ("same lags (1,3,5)", src_mut("SAME_LAGS = (2, 4, 6) ", "SAME_LAGS = (1, 3, 5) ")),
    ("opp lags (2,4,6)", src_mut("OPP_LAGS = (1, 3, 5) ", "OPP_LAGS = (2, 4, 6) ")),
    ("window 10 -> 5", src_mut("WINDOW_HZ = 10.0 ", "WINDOW_HZ = 5.0 ")),
    ("window strict <", src_mut("if abs(pf - f) > WINDOW_HZ:", "if abs(pf - f) >= WINDOW_HZ:")),
    ("window ignored", src_mut("            if abs(pf - f) > WINDOW_HZ:\n                continue\n", "")),
    ("text compare lowercase-insensitive prefix", src_mut("if ptext == text:", "if ptext.split()[:2] == text.split()[:2]:")),
    ("E2 needs same text", src_mut("if e2 is None and first_two(ptext) is not None and first_two(ptext) == first_two(text):", "if e2 is None and first_two(ptext) is not None and first_two(ptext) == first_two(text) and ptext == text:")),
    ("E2 beats E1", src_mut('return ("E1", k, pb)', 'return e2 if e2 else ("E1", k, pb)')),
    ("prior beyond start crashes/wraps", src_mut("if j < 0:\n            continue", "if j < -100:\n            continue")),
    ("first_two = first token", src_mut("return tuple(t[:2]) if len(t) >= 2 else None", "return tuple(t[:1]) if len(t) >= 1 else None")),
    ("ci percentile 90", src_mut("np.percentile(p, 97.5)", "np.percentile(p, 90.0)")),
    ("pp not x100", src_mut("p = 100.0 * num / den", "p = num / den")),
    ("V-PAR ratio 0.25 -> 0.5", src_mut("PAR_RATIO = 0.25", "PAR_RATIO = 0.5")),
    ("V-PAR >=", src_mut("return e_opp <= PAR_RATIO * e1", "return e_opp < PAR_RATIO * e1")),
    ("CLOSE gated by V-PAR", src_mut('    if ci_e1[1] < BAR_PP:\n        return "CLOSE"\n    if not par_ok:\n        return "VOID"\n', '    if not par_ok:\n        return "VOID"\n    if ci_e1[1] < BAR_PP:\n        return "CLOSE"\n')),
    ("CLOSE non-strict", src_mut("if ci_e1[1] < BAR_PP:", "if ci_e1[1] <= BAR_PP:")),
    ("PURSUE strict", src_mut("if ci_e1[0] >= BAR_PP:", "if ci_e1[0] > BAR_PP:")),
    ("bar 1.0 -> 0.5", src_mut("BAR_PP = 1.0 ", "BAR_PP = 0.5 ")),
]


def main():
    bad = run_tests()
    print("unmutated: " + ("ALL PASS" if not bad else "FAIL " + str(bad)))
    if bad:
        sys.exit(1)
    surv = []
    for name, m in MUTS:
        importlib.reload(L)
        try:
            m()
        except AssertionError as e:
            if any(fr.filename == "xc_lib_mut" for fr in traceback.extract_tb(e.__traceback__)):
                print(f"{name:42s} killed by the library's own constant assertion")
                continue
            print(f"{name:42s} MUTATION NOT APPLIED ({e})")
            surv.append(name)
            continue
        killed = run_tests()
        print(f"{name:42s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            surv.append(name)
    importlib.reload(L)
    print(f"{len(MUTS) - len(surv)} of {len(MUTS)} mutations killed")
    sys.exit(1 if surv else 0)


if __name__ == "__main__":
    main()
