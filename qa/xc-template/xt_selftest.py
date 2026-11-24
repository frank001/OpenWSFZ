#!/usr/bin/env python3
"""XC-TEMPLATE self-test: behaviour tests of xt_lib on synthetic audio (real coherent_extract), then MUTATIONS (each must make a test fail).   python xt_selftest.py"""
from __future__ import annotations

import importlib
import os
import sys
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "rr-study", "n2-coherent-llr-extractor"))
import coherent_extract as CE   # noqa: E402
import xt_lib as L              # noqa: E402

FS = 12000
CAL = 0.5
F0, DT0 = 1000.0, 0.5           # the true signal: base frequency (on the 0.5 Hz grid) and WSJT-X-convention dt; start = DT0 + CAL = 1.0 s


def tones_a():
    return list(np.random.default_rng(1).integers(0, 8, size=79))


def synth(tones, f0=F0, dt0=DT0, amp=0.5, noise=1.0, seed=7):
    rng = np.random.default_rng(seed)
    n = 180000
    x = rng.normal(0.0, noise, n)
    t0 = int(round((dt0 + CAL) * FS))
    spsym = int(round(0.16 * FS))
    ph = 0.0
    for k, tn in enumerate(tones):
        f = f0 + 6.25 * tn
        i = np.arange(spsym)
        seg = amp * np.cos(ph + 2 * np.pi * f * i / FS)
        x[t0 + k * spsym:t0 + (k + 1) * spsym] += seg
        ph = (ph + 2 * np.pi * f * spsym / FS) % (2 * np.pi)
    return x.astype(np.float32)


def t_grids():
    d, e = L.df_grid(), L.dt_grid()
    assert len(d) == 13 and d[0] == -3.0 and d[-1] == 3.0 and abs(d[1] - d[0] - 0.5) < 1e-12 and 0.0 in d
    assert len(e) == 25 and abs(e[0] + 0.12) < 1e-12 and abs(e[-1] - 0.12) < 1e-12 and abs(e[1] - e[0] - 0.01) < 1e-12


def t_s_e_values():
    X = np.zeros((79, 8), dtype=complex)
    tn = list(range(79))
    tn = [k % 8 for k in tn]
    for k in range(79):
        X[k, tn[k]] = 1.0
    assert abs(L.s_e(X, tn) - 8.0) < 1e-12                                              # a perfect signal: all power in the known bin -> 8
    X2 = np.ones((79, 8), dtype=complex)
    assert abs(L.s_e(X2, tn) - 1.0) < 1e-12                                              # flat power -> 1
    X3 = X2.copy(); X3[:, :] = 0.0
    assert abs(L.s_e(X3, tn) - 1.0) < 1e-12                                              # no power in any symbol counts 1, not NaN
    X4 = np.zeros((79, 8), dtype=complex)
    for k in range(79):
        X4[k, (tn[k] + 1) % 8] = 1.0
    assert abs(L.s_e(X4, tn) - 0.0) < 1e-12                                              # all power in a wrong bin -> 0


def t_shift_matches_direct():
    pcm = synth(tones_a())
    bb = CE.downconvert_decimate(pcm, 1000.0)
    a = np.abs(CE.correlate_symbols(CE.downconvert_decimate(pcm, 1002.5), 2000)) ** 2
    b = np.abs(CE.correlate_symbols(L.shift_baseband(bb, 2.5), 2000)) ** 2
    assert np.max(np.abs(a - b)) / np.max(a) < 1e-3
    c = np.abs(CE.correlate_symbols(L.shift_baseband(bb, -2.5), 2000)) ** 2
    d = np.abs(CE.correlate_symbols(CE.downconvert_decimate(pcm, 997.5), 2000)) ** 2
    assert np.max(np.abs(c - d)) / np.max(d) < 1e-3                                       # sign of the shift
    assert L.shift_baseband(bb, 0.0) is bb


def t_search_finds_signal_and_rejects_wrong_message():
    tones = tones_a()
    pcm = synth(tones)
    best, arg = L.search(CE, pcm, F0 + 1.5, DT0 + 0.05, tones, CAL)                       # centre offset by (+1.5 Hz, +0.05 s): the truth is inside the window
    assert best > 5.0, best
    assert abs(arg[0] - F0) <= 0.5 and abs(arg[1] - DT0) <= 0.011, arg
    assert L.truth_ok(arg, F0, DT0)
    wrong = list(np.random.default_rng(99).integers(0, 8, size=79))
    bw, _ = L.search(CE, pcm, F0 + 1.5, DT0 + 0.05, wrong, CAL)
    assert bw < 2.0 and bw < best / 3, (bw, best)                                          # another message at the same place: noise level
    noise_only = synth(tones, amp=0.0)
    bn, _ = L.search(CE, noise_only, F0, DT0, tones, CAL)
    assert bn < 2.0, bn                                                                    # the null's maximum over 325 positions of pure noise stays low
    far = L.search(CE, pcm, F0 + 12.5, DT0, tones, CAL)                                    # the truth is far outside the +-3 Hz window (and the 6.25 Hz tone grid aligns to other tones): not found
    assert far[0] < 2.0


def t_truth_check_gate():
    assert L.truth_ok((1000.0, 0.5), 1003.125, 0.62) and not L.truth_ok((1000.0, 0.5), 1003.2, 0.5)
    assert not L.truth_ok((1000.0, 0.5), 1000.0, 0.63) and L.truth_ok((1000.0, 0.5), 996.875, 0.38)


def t_threshold():
    s = np.arange(1, 101, dtype=float)                                                    # values 1..100
    assert L.threshold_te(s, 0.05) == 96.0                                                  # max 5 exceedances: S >= 96 has 5 (96..100)
    assert (s >= L.threshold_te(s, 0.05)).sum() == 5
    assert L.threshold_te(s, 0.0) > 100.0                                                   # no exceedance allowed: above the maximum
    assert L.threshold_te(s, 0.5) == 51.0 and (s >= 51.0).sum() == 50
    tied = np.array([1.0, 2.0, 3.0, 3.0, 3.0, 4.0])
    t = L.threshold_te(tied, 0.5)                                                           # 3 allowed: S >= 4 has 1, S >= 3 has 4 (> 3): T must be 4
    assert t == 4.0 and (tied >= t).sum() <= 3
    assert L.threshold_te([], 0.1) is None
    assert L.threshold_te([5.0], 1.0) == 5.0
    assert abs(L.exceed(s, 91.0) - 0.10) < 1e-12 and L.exceed(s, 101.0) == 0.0


def t_fa_and_floor():
    assert abs(L.fa_star(49.0) - 0.021 / 49.0) < 1e-15 and abs(L.n_null_min(0.021 / 49.0) - 7000.0) < 1e-6


def t_split_half_and_boot():
    rng = np.random.default_rng(3)
    sc = rng.normal(size=4000)
    cyc = rng.integers(0, 40, size=4000)
    sh = L.split_half(sc, cyc, 0.01)
    assert set(sh) == {"even_to_odd", "odd_to_even"} and sh["even_to_odd"]["train_n"] == int((cyc % 2 == 0).sum()) and sh["even_to_odd"]["test_n"] == int((cyc % 2 == 1).sum())
    assert abs(sh["even_to_odd"]["T"] - L.threshold_te(sc[cyc % 2 == 0], 0.01)) < 1e-12
    assert 0.0 <= sh["even_to_odd"]["exceedance_on_other_half"] <= 0.05
    idx = L.boot_idx(40, b=50)
    bt = L.boot_te(sc, cyc, 40, 0.01, idx)
    assert len(bt) == 50 and 1.5 < np.median(bt) < 3.5
    only0 = L.boot_te(sc, cyc, 40, 0.01, np.zeros((1, 40), dtype=int))                    # every resampled cycle is cycle 0: T_E is that cycle's threshold on 40 copies of its scores
    exp0 = L.threshold_te(np.tile(sc[cyc == 0], 40), 0.01)
    assert abs(only0[0] - exp0) < 1e-12 and abs(exp0 - L.threshold_te(sc, 0.01)) > 1e-6


def t_rate_and_g():
    det = np.array([1.0, 0.0, 3.0, 0.0]); n = np.array([4.0, 4.0, 4.0, 4.0])
    idx = np.array([[0, 1, 2, 3], [2, 2, 2, 2]])
    p, c = L.rate_ci(det, n, idx)
    assert abs(p - 0.25) < 1e-12 and abs(c[1] - np.percentile([0.25, 0.75], 97.5)) < 1e-9
    assert abs(L.g_pp(1.0) - 100.0 * 520 / 13997) < 1e-12 and abs(L.g_pp(0.5) - 50.0 * 520 / 13997) < 1e-12


def t_decide():
    ok = {"v_null_n_ok": True, "v_pos_ci": [0.9, 1.0], "g_ci": [1.0, 2.0]}
    assert L.decide(ok) == "BUILD-WORTH"
    assert L.decide(dict(ok, v_null_n_ok=False)) == "VOID"                                # V-NULL-N gates everything, BUILD-WORTH included
    assert L.decide(dict(ok, v_null_n_ok=False, g_ci=[0.0, 0.1])) == "VOID"
    assert L.decide(dict(ok, v_pos_ci=[0.2, 0.5])) == "BUILD-WORTH"                       # A2: V-POS does not gate BUILD-WORTH
    assert L.decide(dict(ok, v_pos_ci=[0.79, 1.0], g_ci=[0.1, 0.39])) == "VOID"           # V-POS fails and not BUILD-WORTH: VOID before CLOSE
    assert L.decide(dict(ok, v_pos_ci=[0.79, 1.0], g_ci=[0.1, 0.9])) == "VOID"
    assert L.decide(dict(ok, v_pos_ci=[0.80, 1.0], g_ci=[0.1, 0.39])) == "CLOSE"
    assert L.decide(dict(ok, g_ci=[0.1, 0.4])) == "BETWEEN" and L.decide(dict(ok, g_ci=[0.39, 1.0])) == "BETWEEN"
    assert L.decide(dict(ok, g_ci=[0.4, 1.0])) == "BUILD-WORTH" and L.decide(dict(ok, g_ci=[0.0, 0.0])) == "CLOSE"


TESTS = [t_grids, t_s_e_values, t_shift_matches_direct, t_search_finds_signal_and_rejects_wrong_message, t_truth_check_gate, t_threshold, t_fa_and_floor, t_split_half_and_boot, t_rate_and_g, t_decide]


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
        s = open(os.path.join(HERE, "xt_lib.py"), encoding="utf-8").read()
        assert old in s, old
        ns = {}
        exec(compile(s.replace(old, new, 1), "xt_lib_mut", "exec"), ns)
        for k, v in ns.items():
            if not k.startswith("__"):
                setattr(L, k, v)
    return m


MUTS = [
    ("s_e: no mean over bins", src_mut("den = P.sum(axis=1) / N_TONES", "den = P.sum(axis=1)")),
    ("s_e: zero power counts 0", src_mut("r = np.where(den > 0, num / np.where(den > 0, den, 1.0), 1.0)", "r = np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0)")),
    ("s_e: wrong bin", src_mut("num = P[np.arange(N_SYM), np.asarray(tones)]", "num = P[np.arange(N_SYM), (np.asarray(tones) + 1) % N_TONES]")),
    ("shift sign", src_mut("np.exp(-2j * np.pi * delta_hz", "np.exp(2j * np.pi * delta_hz")),
    ("shift rate 12000", src_mut("np.arange(len(bb)) / FS_OUT", "np.arange(len(bb)) / 12000")),
    ("search: max -> min", src_mut("if v > best:", "if v < best or best < 0:")),
    ("search: dt calibration dropped", src_mut("smp = int(round((dt_c + e + calib_s) * FS_OUT))", "smp = int(round((dt_c + e) * FS_OUT))")),
    ("search: dt not shifted", src_mut("smp = int(round((dt_c + e + calib_s) * FS_OUT))", "smp = int(round((dt_c + calib_s) * FS_OUT))")),
    ("truth gate strict-off (6.25)", src_mut("GATE_DF_HZ + 1e-9", "6.25 + 1e-9")),
    ("truth gate dt ignored", src_mut("and abs(arg[1] - dt_own) <= GATE_DT_S + 1e-9", "")),
    ("threshold: off by one", src_mut("thr = s[max_ex]  ", "thr = s[max(max_ex - 1, 0)]  ")),
    ("threshold: allows none", src_mut("max_ex = int(np.floor(n * fa + 1e-12))", "max_ex = 0")),
    ("exceed strict >", src_mut("return float((s >= t).mean())", "return float((s > t).mean())")),
    ("n_null floor 3 -> 1", src_mut("return 3.0 / fa", "return 1.0 / fa")),
    ("split-half: same half", src_mut('("even_to_odd", 0, 1), ("odd_to_even", 1, 0)', '("even_to_odd", 0, 0), ("odd_to_even", 1, 1)')),
    ("boot_te: cycles not resampled", src_mut("v = np.concatenate([by[c] for c in row])", "v = np.concatenate([by[c] for c in range(n_cyc)])")),
    ("G not scaled by 520/13997", src_mut("return 100.0 * d_share * N_E1_FULL / N_REF", "return 100.0 * d_share")),
    ("V-POS bar 0.80 -> 0.70", src_mut("V_POS = 0.80 ", "V_POS = 0.70 ")),
    ("decide: CLOSE non-strict", src_mut('if r["g_ci"][1] < CLOSE_PP:', 'if r["g_ci"][1] <= CLOSE_PP:')),
    ("decide: BUILD strict", src_mut('if r["g_ci"][0] >= BUILD_PP:', 'if r["g_ci"][0] > BUILD_PP:')),
    ("decide: CLOSE before V-POS VOID", src_mut('    if r["v_pos_ci"][0] < V_POS:\n        return "VOID"\n    if r["g_ci"][1] < CLOSE_PP:\n        return "CLOSE"\n', '    if r["g_ci"][1] < CLOSE_PP:\n        return "CLOSE"\n    if r["v_pos_ci"][0] < V_POS:\n        return "VOID"\n')),
    ("decide: V-POS gates BUILD-WORTH", src_mut('    if r["g_ci"][0] >= BUILD_PP:\n        return "BUILD-WORTH"\n    if r["v_pos_ci"][0] < V_POS:\n        return "VOID"\n', '    if r["v_pos_ci"][0] < V_POS:\n        return "VOID"\n    if r["g_ci"][0] >= BUILD_PP:\n        return "BUILD-WORTH"\n')),
    ("decide: V-NULL-N dropped", src_mut('    if not r["v_null_n_ok"]:\n        return "VOID"\n', "")),
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
            if any(fr.filename == "xt_lib_mut" for fr in traceback.extract_tb(e.__traceback__)):
                print(f"{name:36s} killed by the library's own constant assertion")
                continue
            print(f"{name:36s} MUTATION NOT APPLIED ({e})")
            surv.append(name)
            continue
        killed = run_tests()
        print(f"{name:36s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            surv.append(name)
    importlib.reload(L)
    print(f"{len(MUTS) - len(surv)} of {len(MUTS)} mutations killed")
    sys.exit(1 if surv else 0)


if __name__ == "__main__":
    main()
