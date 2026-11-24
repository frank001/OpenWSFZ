#!/usr/bin/env python3
"""TA-CHECK self-test: behaviour tests on synthetic data, then MUTATIONS of tc_lib (each must make a test fail).   python tc_selftest.py   exit 0 iff all pass unmutated AND every mutation is killed."""
from __future__ import annotations

import importlib
import traceback
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tc_lib as L          # noqa: E402

CI_HI = [0.5, 0.7]          # CI entirely below the bar
CI_OK = [0.85, 0.95]
CI_MID = [0.7, 0.9]         # straddles
POS = [0.05, 0.3]           # CI_lo > 0
ZERO = [-0.1, 0.2]


def base(**kw):
    r = {"n_T": 536, "n_Tbur": 267, "ci_B1": CI_OK, "ci_B1m": CI_OK, "ci_T": CI_OK, "ci_Tbur": CI_OK, "ci_B1m_minus_T": ZERO, "ci_std_diff": ZERO}
    r.update(kw)
    return r


def t_neighbour_predicate():
    rows = [(-10, 0.0, 1000), (-5, 0.0, 1030), (-12, 0.0, 1049), (-9, 0.0, 1100), (-10, 0.0, 1049)]
    assert L.strongest_neighbour(0, rows) == (5, 30)                                # -5 at 30 Hz is the strongest of {-5, -12 (no: weaker) , -10 at 49 Hz (equal SNR, counts)}
    assert L.is_buried(0, rows)
    assert L.strongest_neighbour(1, rows) is None                                   # nothing at least as strong within 50 Hz of the -5 row
    assert L.strongest_neighbour(3, rows) is None                                   # 1100 is more than 50 Hz from 1049? |1100-1049| = 51
    rows2 = [(-10, 0.0, 1000), (-10, 0.0, 1049)]                                    # equal SNR counts ("SNR >= its own"), 49 Hz < 50
    assert L.is_buried(0, rows2) and L.is_buried(1, rows2)
    rows3 = [(-10, 0.0, 1000), (-3, 0.0, 1050)]                                     # exactly 50 Hz is NOT overlapping (strict <)
    assert not L.is_buried(0, rows3)
    rows4 = [(-10, 0.0, 1000), (-11, 0.0, 1010)]                                    # weaker neighbour does not bury
    assert not L.is_buried(0, rows4) and L.is_buried(1, rows4)
    assert L.strongest_neighbour(0, [(-10, 0, 1000), (-4, 0, 1040), (-4, 0, 1010)]) == (6, 10)   # strongest wins, ties to the nearer


def t_draws():
    pool = [(f"s{i % 7}", i) for i in range(300)]
    a, b = L.draw(pool, 50), L.draw(list(reversed(pool)), 50)
    assert a == b and len(set(a)) == 50 and a == sorted(a)                          # seeded, order-independent, no replacement
    assert L.draw(pool, 50, seed=1) != a
    pbb = {b_: [(f"s{b_}", i) for i in range(40)] for b_ in L.BANDS}
    q = L.band_quota({b_: 40 for b_ in L.BANDS}, {"A": 5, "B": 10, "C": 7, "D": 20})
    m = L.draw_matched(pbb, q)
    assert len(m) == 42 and sum(1 for x in m if x[0] == "sD") == 20
    try:
        L.band_quota({"A": 4, "B": 40, "C": 40, "D": 40}, {"A": 5})
        raise RuntimeError("short pool was accepted")
    except AssertionError:
        pass


def t_band_of():
    assert [L.band_of(s) for s in (0, -1, -10, -11, -15, -16)] == ["A", "B", "B", "C", "C", "D"]


def mk(rows, ncyc=4):
    cix = {f"c{i}": i for i in range(ncyc)}
    return L.tally(rows, ncyc, cix)


def t_tally_and_rate():
    t = mk([("c0", "A", True), ("c0", "A", False), ("c1", "B", True), ("c3", "D", True)])
    assert list(t[0]) == [2, 1, 0, 1] and list(t[1]) == [1, 1, 0, 1] and list(t[2]["A"]) == [2, 0, 0, 0] and list(t[3]["D"]) == [0, 0, 0, 1]
    idx = np.array([[0, 1, 2, 3], [0, 0, 0, 0], [2, 2, 2, 2]])
    r = L.rate(t, idx)
    assert abs(r[0] - 3 / 4) < 1e-12 and abs(r[1] - 0.5) < 1e-12 and np.isnan(r[2])  # an empty replicate is NaN, not 0


def t_std_bands_and_contrast():
    # T_iso: A 12 rows (all present), B 10 (5 present), C 9 (cell floor violated); T_bur: A 20 (10 present), B 10 (5 present), C 15, D 3
    iso = mk([("c0", "A", True)] * 12 + [("c1", "B", True)] * 5 + [("c1", "B", False)] * 5 + [("c2", "C", True)] * 9)
    bur = mk([("c0", "A", True)] * 10 + [("c0", "A", False)] * 10 + [("c1", "B", True)] * 5 + [("c1", "B", False)] * 5 + [("c2", "C", False)] * 15 + [("c3", "D", False)] * 3)
    bands, w, left = L.std_bands(iso, bur)
    assert bands == ["A", "B"] and left == 18                                       # C: T_iso has 9 < 10; D: T_iso has none; 15 + 3 T_bur rows leave the contrast
    assert abs(w["A"] - 20 / 30) < 1e-12 and abs(w["B"] - 10 / 30) < 1e-12
    idx = np.array([[0, 1, 2, 3]])
    i_, b_, d_ = L.pr_std_contrast(iso, bur, idx, bands, w)
    assert abs(i_[0] - (20 / 30 * 1.0 + 10 / 30 * 0.5)) < 1e-12 and abs(b_[0] - (20 / 30 * 0.5 + 10 / 30 * 0.5)) < 1e-12 and abs(d_[0] - (i_[0] - b_[0])) < 1e-12
    only_c0 = np.array([[0, 0, 0, 0]])                                              # no B rows in this replicate: the contrast is NaN, not silently the A part
    assert np.isnan(L.pr_std_contrast(iso, bur, only_c0, bands, w)[2][0])


def t_decide_rows():
    assert L.decide(base()) == "SOUND"
    assert L.decide(base(ci_B1=[0.79, 1.0])) == "VOID"                              # CI_lo < 0.80 on the convention check
    assert L.decide(base(ci_B1=[0.80, 1.0])) == "SOUND"                             # = 0.80 passes (CI_lo < 0.80 voids)
    assert L.decide(base(n_T=399)) == "VOID"
    assert L.decide(base(ci_T=CI_HI, ci_B1m_minus_T=POS)) == "BLIND"
    assert L.decide(base(ci_T=CI_HI, ci_B1m_minus_T=ZERO)) == "WEAK-ROW"            # below the bar but the batch effect is not beyond SNR
    assert L.decide(base(ci_T=[0.5, 0.8])) == "BETWEEN"                             # CI_hi = 0.80 is not < 0.80, CI_lo < 0.80
    assert L.decide(base(ci_Tbur=CI_HI, ci_std_diff=POS)) == "BLIND-BURIED"
    assert L.decide(base(ci_Tbur=CI_HI, ci_std_diff=ZERO)) == "WEAK-ROW"
    assert L.decide(base(ci_T=CI_HI, ci_B1m_minus_T=POS, ci_Tbur=CI_HI, ci_std_diff=POS)) == "BLIND"   # first match wins
    assert L.decide(base(ci_B1m=CI_HI)) == "WEAK-ROW"                               # the matched control itself fails its bar
    assert L.decide(base(ci_T=CI_MID)) == "BETWEEN"
    assert L.decide(base(ci_T=[0.80, 0.95], ci_Tbur=[0.80, 0.95])) == "SOUND"       # CI_lo >= 0.80 both
    assert L.decide(base(ci_T=[0.79, 0.95])) == "BETWEEN"
    assert L.decide(base(n_Tbur=99, ci_Tbur=CI_HI, ci_std_diff=POS)) == "BETWEEN"   # T_bur short: no burial read, and T_bur is left out of the WEAK-ROW test; the other CIs are fine, so BETWEEN
    assert L.decide(base(n_Tbur=99)) == "BETWEEN"


TESTS = [t_neighbour_predicate, t_draws, t_band_of, t_tally_and_rate, t_std_bands_and_contrast, t_decide_rows]


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


# ------------------------------------------------------------------------------------------------ mutations (source-level, on tc_lib)
def src_mut(old, new, old2=None, new2=None):
    def m():
        s = open(os.path.join(HERE, "tc_lib.py"), encoding="utf-8").read()
        assert old in s, old
        s = s.replace(old, new, 1)
        if old2:
            assert old2 in s, old2
            s = s.replace(old2, new2, 1)
        ns = {}
        exec(compile(s, "tc_lib_mut", "exec"), ns)
        for k, v in ns.items():
            if not k.startswith("__"):
                setattr(L, k, v)
    return m


MUTS = [
    ("overlap <= (not strict)", src_mut("abs(rows[j][2] - f) < OVERLAP_HZ and rows[j][0] >= snr", "abs(rows[j][2] - f) <= OVERLAP_HZ and rows[j][0] >= snr")),
    ("stronger > (not >=)", src_mut("abs(rows[j][2] - f) < OVERLAP_HZ and rows[j][0] >= snr", "abs(rows[j][2] - f) < OVERLAP_HZ and rows[j][0] > snr")),
    ("neighbour weaker also buries", src_mut("abs(rows[j][2] - f) < OVERLAP_HZ and rows[j][0] >= snr", "abs(rows[j][2] - f) < OVERLAP_HZ")),
    ("strongest by min", src_mut("s, d = max(c, key=lambda t: (t[0], -t[1]))", "s, d = min(c, key=lambda t: (t[0], -t[1]))")),
    ("band D boundary", src_mut('"C" if snr >= -15 else "D"', '"C" if snr >= -16 else "D"')),
    ("draw not sorted pool", src_mut("    pool = sorted(pool)\n    assert len(pool) >= k", "    assert len(pool) >= k")),
    ("draw seed ignored", src_mut("rng = np.random.default_rng(seed)\n    return sorted(pool[i]", "rng = np.random.default_rng(1)\n    return sorted(pool[i]")),
    ("quota accepts short pool", src_mut('assert pool_counts.get(b, 0) >= want.get(b, 0), ("B1m pool short", b, pool_counts.get(b, 0), want.get(b, 0))', "pass")),
    ("empty replicate as 0", src_mut("k[idx].sum(axis=1) / np.where(n[idx].sum(axis=1) > 0, n[idx].sum(axis=1), np.nan)", "k[idx].sum(axis=1) / np.where(n[idx].sum(axis=1) > 0, n[idx].sum(axis=1), 1e18)")),
    ("std cell floor off", src_mut("tiso[2][b].sum() >= STD_MIN_CELL and tbur[2][b].sum() >= STD_MIN_CELL", "tiso[2][b].sum() >= 1 and tbur[2][b].sum() >= 1")),
    ("std weights = T_iso mix", src_mut("w = {b: tbur[2][b].sum() / tot for b in bands}", "w = {b: tiso[2][b].sum() / sum(tiso[2][x].sum() for x in bands) for b in bands}")),
    ("contrast NaN as 0", src_mut("iso = iso + w[b] * np.where(ni > 0, ki / np.where(ni > 0, ni, 1), np.nan)", "iso = iso + w[b] * np.where(ni > 0, ki / np.where(ni > 0, ni, 1), 0.0)",
                                   "bur = bur + w[b] * np.where(nu > 0, ku / np.where(nu > 0, nu, 1), np.nan)", "bur = bur + w[b] * np.where(nu > 0, ku / np.where(nu > 0, nu, 1), 0.0)")),
    ("VOID bar <=", src_mut('if r["ci_B1"][0] < BAR:', 'if r["ci_B1"][0] <= BAR:')),
    ("VOID on n(T) dropped", src_mut('    if r["n_T"] < V_N_T:\n        return "VOID"\n', "")),
    ("BLIND without contrast", src_mut('if r["ci_T"][1] < BAR and r["ci_B1m_minus_T"][0] > 0:', 'if r["ci_T"][1] < BAR:')),
    ("BLIND contrast >= 0", src_mut('r["ci_B1m_minus_T"][0] > 0', 'r["ci_B1m_minus_T"][0] >= -1')),
    ("BLIND-BURIED without contrast", src_mut('r["ci_Tbur"][1] < BAR and r["ci_std_diff"][0] > 0', 'r["ci_Tbur"][1] < BAR')),
    ("BLIND-BURIED ignores V-N", src_mut('if tbur_ok and r["ci_Tbur"][1] < BAR', 'if r["ci_Tbur"][1] < BAR')),
    ("WEAK-ROW ignores B1m", src_mut('cands = [r["ci_T"][1], r["ci_B1m"][1]]', 'cands = [r["ci_T"][1]]')),
    ("SOUND uses CI_hi", src_mut('r["ci_T"][0] >= BAR and r["ci_Tbur"][0] >= BAR', 'r["ci_T"][1] >= BAR and r["ci_Tbur"][1] >= BAR')),
    ("SOUND ignores T_bur", src_mut('tbur_ok and r["ci_T"][0] >= BAR', 'r["ci_T"][0] >= BAR')),
    ("bar 0.8 -> 0.75", src_mut("BAR = 0.80 ", "BAR = 0.75 ")),
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
            if any(fr.filename == "tc_lib_mut" for fr in traceback.extract_tb(e.__traceback__)):
                print(f"{name:32s} killed by the library's own constant assertion")
                continue
            print(f"{name:32s} MUTATION NOT APPLIED ({e})")
            surv.append(name)
            continue
        killed = run_tests()
        print(f"{name:32s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            surv.append(name)
    importlib.reload(L)
    print(f"{len(MUTS) - len(surv)} of {len(MUTS)} mutations killed")
    sys.exit(1 if surv else 0)


if __name__ == "__main__":
    main()
