#!/usr/bin/env python3
"""XC-BUILD analysis self-test: behaviour tests of xb_lib, then MUTATIONS (each must make a test fail).   python xb_selftest.py"""
from __future__ import annotations

import importlib
import os
import sys
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xb_lib as L          # noqa: E402


def t_k_and_fa():
    assert L.k_median([40, 50, 60, 0, 49]) == 49.0 and abs(L.fa_star(49.0) - 0.021 / 49.0) < 1e-15
    assert L.k_median([0, 0, 10]) == 0.0                                                    # cycles without a residual count 0: the median reflects them


def t_threshold():
    s = np.arange(1, 101, dtype=float)
    assert L.threshold_te(s, 0.05) == 96.0 and (s >= 96.0).sum() == 5
    assert L.threshold_te(s, 0.0) > 100.0
    tied = np.array([1.0, 2.0, 3.0, 3.0, 3.0, 4.0])
    assert L.threshold_te(tied, 0.5) == 4.0
    assert L.threshold_te([], 0.1) is None


def t_v_tr_n():
    fa = 0.021 / 49.0
    assert L.v_tr_n(7000, fa) and not L.v_tr_n(6990, fa)


def t_boot_te():
    rng = np.random.default_rng(1)
    sc = rng.normal(size=3000); cyc = rng.integers(0, 30, size=3000)
    only0 = L.boot_te(sc, cyc, 30, 0.01, np.zeros((1, 30), dtype=int))
    assert abs(only0[0] - L.threshold_te(np.tile(sc[cyc == 0], 30), 0.01)) < 1e-12


def t_poisson():
    # exact bounds: 0 events -> 3.689 / N; 10 events -> 18.39 / N; 12 -> 20.96 / N (chi-square based)
    assert abs(L.poisson_upper(0) - 3.6889) < 1e-3 and abs(L.poisson_upper(10) - 18.3904) < 1e-3 and abs(L.poisson_upper(12) - 20.9616) < 1e-3
    p, c = L.shadow_rate(10, 500)
    assert abs(p - 0.02) < 1e-12 and abs(c[1] - 18.3904 / 500) < 1e-5 and 0.0 < c[0] < p
    assert abs(L.shadow_rate(10, 500)[1][0] - 4.795 / 500) < 2e-4                           # exact lower bound for 10 events: 4.795
    assert L.shadow_rate(0, 500)[1][0] == 0.0
    # the pass counts quoted in the (k) review: <= 12 events on 500 cycles, <= 29 on 1,000, <= 8 on 400
    assert L.shadow_ok(12, 500) and not L.shadow_ok(13, 500)
    assert L.shadow_ok(29, 1000) and not L.shadow_ok(30, 1000)
    assert L.shadow_ok(8, 400) and not L.shadow_ok(9, 400)


def t_net():
    on = np.array([10, 12, 11, 9.0]); off = np.array([9, 10, 11, 8.0]); nref = np.array([30, 30, 30, 30.0])
    idx = np.array([[0, 1, 2, 3], [1, 1, 1, 1], [2, 2, 2, 2]])
    p, c = L.net_pp(on, off, nref, idx)
    assert abs(p - 100.0 * 4 / 120) < 1e-12
    reps = [100.0 * 4 / 120, 100.0 * 8 / 120, 0.0]
    assert abs(c[0] - np.percentile(reps, 2.5)) < 1e-9 and abs(c[1] - np.percentile(reps, 97.5)) < 1e-9


def t_misc():
    assert L.late_ok(0) and not L.late_ok(1)
    assert L.v_wire(1, 1) and not L.v_wire(0, 5) and not L.v_wire(5, 0)
    assert abs(L.p95([1, 2, 3, 4, 100]) - np.percentile([1, 2, 3, 4, 100], 95)) < 1e-12 and np.isnan(L.p95([]))
    assert abs(L.p95([None, -1, 10, 20]) - np.percentile([10, 20], 95)) < 1e-12              # missing (-1 / None) publish times are not data


def t_decide():
    ok = {"v_off_ok": True, "v_store_ok": True, "v_wire_ok": True, "v_trn_ok": True, "shadow_ok": True, "net_ci": [0.5, 2.0], "late_ok": True}
    assert L.decide(ok) == "ACCEPT"
    assert L.decide(dict(ok, v_off_ok=False)) == "STOP" and L.decide(dict(ok, v_store_ok=False, v_wire_ok=False)) == "STOP"
    assert L.decide(dict(ok, v_wire_ok=False)) == "VOID" and L.decide(dict(ok, v_trn_ok=False, shadow_ok=False)) == "VOID"
    assert L.decide(dict(ok, shadow_ok=False)) == "REFUSE" and L.decide(dict(ok, shadow_ok=False, net_ci=[0.0, 0.1])) == "REFUSE"
    assert L.decide(dict(ok, net_ci=[0.4, 1.0])) == "ACCEPT" and L.decide(dict(ok, net_ci=[0.39, 1.0])) == "BETWEEN"
    assert L.decide(dict(ok, late_ok=False)) == "BETWEEN"                                  # NET clears but LATE fails: not ACCEPT, and not NO-GAIN
    assert L.decide(dict(ok, net_ci=[-0.5, 0.39])) == "NO-GAIN" and L.decide(dict(ok, net_ci=[-0.5, 0.4])) == "BETWEEN"
    assert L.decide(dict(ok, net_ci=[-0.5, 0.1], late_ok=False)) == "NO-GAIN"


TESTS = [t_k_and_fa, t_threshold, t_v_tr_n, t_boot_te, t_poisson, t_net, t_misc, t_decide]


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
        s = open(os.path.join(HERE, "xb_lib.py"), encoding="utf-8").read()
        assert old in s, old
        ns = {}
        exec(compile(s.replace(old, new, 1), "xb_lib_mut", "exec"), ns)
        for k, v in ns.items():
            if not k.startswith("__"):
                setattr(L, k, v)
    return m


MUTS = [
    ("K mean instead of median", src_mut("return float(np.median(np.asarray(live_tests_per_cycle, dtype=float)))", "return float(np.mean(np.asarray(live_tests_per_cycle, dtype=float)))")),
    ("threshold off by one", src_mut("thr = s[max_ex]", "thr = s[max(max_ex - 1, 0)]")),
    ("threshold allows none", src_mut("max_ex = int(np.floor(n * fa + 1e-12))", "max_ex = 0")),
    ("V-TR-N floor 3 -> 1", src_mut("return n_shadow >= 3.0 / fa", "return n_shadow >= 1.0 / fa")),
    ("boot_te cycles not resampled", src_mut("t = threshold_te(np.concatenate([by[c] for c in row]), fa)", "t = threshold_te(np.concatenate([by[c] for c in range(n_cyc)]), fa)")),
    ("poisson alpha 0.05", src_mut("alpha_one_sided: float = ALPHA / 2", "alpha_one_sided: float = ALPHA")),
    ("poisson lower = point", src_mut("        lo = 0.5 * (lo_l + hi_l) / cycles\n", "        lo = events / cycles\n")),
    ("shadow bar 0.042 -> 0.05", src_mut("SHADOW_BAR = 0.042 ", "SHADOW_BAR = 0.05 ")),
    ("shadow ok strict <", src_mut("return shadow_rate(events, cycles)[1][1] <= SHADOW_BAR", "return shadow_rate(events, cycles)[1][1] < SHADOW_BAR - 1e-4")),
    ("NET sign (OFF - ON)", src_mut("d = np.asarray(on_matched, dtype=float) - np.asarray(off_matched, dtype=float)", "d = np.asarray(off_matched, dtype=float) - np.asarray(on_matched, dtype=float)")),
    ("NET not x100", src_mut("point = 100.0 * d.sum() / n.sum()", "point = d.sum() / n.sum()")),
    ("NET bootstrap not resampled", src_mut("reps = 100.0 * d[idx].sum(axis=1) / n[idx].sum(axis=1)", "reps = np.full(len(idx), point)")),
    ("late allows 1", src_mut("return template_publishes_after_budget == 0", "return template_publishes_after_budget <= 1")),
    ("wire needs only differs", src_mut("return cycles_on_differs >= 1 and batch6_nonempty_cycles >= 1", "return cycles_on_differs >= 1")),
    ("p95 -> p90", src_mut("np.percentile(v, 95))", "np.percentile(v, 90))")),
    ("decide: ACCEPT ignores LATE", src_mut('if r["net_ci"][0] >= NET_BAR_PP and r["late_ok"]:', 'if r["net_ci"][0] >= NET_BAR_PP:')),
    ("decide: NO-GAIN non-strict", src_mut('if r["net_ci"][1] < NET_BAR_PP:', 'if r["net_ci"][1] <= NET_BAR_PP:')),
    ("decide: ACCEPT strict", src_mut('r["net_ci"][0] >= NET_BAR_PP and', 'r["net_ci"][0] > NET_BAR_PP and')),
    ("decide: REFUSE after ACCEPT", src_mut('    if not r["shadow_ok"]:\n        return "REFUSE"\n    if r["net_ci"][0] >= NET_BAR_PP and r["late_ok"]:\n        return "ACCEPT"\n', '    if r["net_ci"][0] >= NET_BAR_PP and r["late_ok"]:\n        return "ACCEPT"\n    if not r["shadow_ok"]:\n        return "REFUSE"\n')),
    ("decide: VOID before STOP", src_mut('    if (not r["v_off_ok"]) or (not r["v_store_ok"]):\n        return "STOP"\n    if (not r["v_wire_ok"]) or (not r["v_trn_ok"]):\n        return "VOID"\n', '    if (not r["v_wire_ok"]) or (not r["v_trn_ok"]):\n        return "VOID"\n    if (not r["v_off_ok"]) or (not r["v_store_ok"]):\n        return "STOP"\n')),
    ("decide: V-TR-N dropped", src_mut(' or (not r["v_trn_ok"])', "")),
    ("NET bar 0.4 -> 0.2", src_mut("NET_BAR_PP = 0.4 ", "NET_BAR_PP = 0.2 ")),
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
            if any(fr.filename == "xb_lib_mut" for fr in traceback.extract_tb(e.__traceback__)):
                print(f"{name:34s} killed by the library's own constant assertion")
                continue
            print(f"{name:34s} MUTATION NOT APPLIED ({e})")
            surv.append(name)
            continue
        killed = run_tests()
        print(f"{name:34s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            surv.append(name)
    importlib.reload(L)
    print(f"{len(MUTS) - len(surv)} of {len(MUTS)} mutations killed")
    sys.exit(1 if surv else 0)


if __name__ == "__main__":
    main()
