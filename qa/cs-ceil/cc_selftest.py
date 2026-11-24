#!/usr/bin/env python3
"""CS-CEIL self-test: behaviour tests on synthetic data (no buffers, no DLL), then MUTATIONS: each mutated cc_lib / cc_analyse function must make at least one test fail.
    python cc_selftest.py        exit 0 iff every test passes unmutated AND every mutation is killed."""
from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cc_lib as L          # noqa: E402
import cc_analyse as A      # noqa: E402


def grid_levels(default, overrides=None):
    d = {f: default for f in L.slot_grid()}
    d.update(overrides or {})
    return d


def t_floor_is_median_of_blocker_free():
    lv = grid_levels(-60.0, {300.0: -10.0, 306.25: -10.0, 312.5: -10.0})          # three loud slots, the median stays -60
    assert L.cycle_floor(lv, []) == -60.0
    lv2 = grid_levels(-60.0)
    lv2[400.0] = -30.0                                                              # blocked loud slot must not move the floor
    assert L.cycle_floor(lv2, [400.0]) == -60.0
    assert L.cycle_floor(grid_levels(-60.0), [f for f in range(0, 3000)]) is None   # nothing blocker-free


def t_two_sided_band():
    assert L.relocation_delta(0, 0) == 5.0
    lv = {f: (-60.0 if f > 1000.0 else -45.0) for f in L.slot_grid()}              # 257 slots at -60 carry the median; the 112 below 1000 Hz are loud
    lv[400.0], lv[350.0], lv[330.0] = -60.9, -61.5, -58.5                          # inside the band; 1.5 dB too quiet; 1.5 dB too loud
    got, fl = L.choose_slot(300.0, lv, [], "two-sided")
    assert fl == -60.0 and got == 400.0, (got, fl)
    assert L.choose_slot(300.0, lv, [], "upper")[0] == 350.0                       # upper-only admits the quiet slot, still refuses the loud one
    lv[400.0] = -58.9                                                              # +1.1 dB: outside both
    assert L.choose_slot(300.0, lv, [], "upper")[0] == 350.0
    assert L.choose_slot(300.0, lv, [], "two-sided")[0] == 1006.25                 # the first -60 slot above 1000 Hz


def t_blocker_and_nearest_and_ties():
    lv = grid_levels(-60.0)
    got, _ = L.choose_slot(1000.0, lv, [1000.0], "two-sided")                       # slots f_s in (880, 1060] are blocked by a signal at 1000
    assert got in (880.0, 1062.5), got                                              # the nearest unblocked neighbours on either side
    assert L.choose_slot(1000.0, lv, [1000.0, 880.0, 1062.5], "two-sided")[0] not in (880.0, 1062.5)
    lv = {f: (-60.0 if f < 1900.0 else -45.0) for f in L.slot_grid()}               # tie: only slots 2000 and 2100 qualify up there, equidistant from the row centre
    lv[2000.0] = lv[2100.0] = -60.0
    got, _ = L.choose_slot(2055.0, lv, [], "two-sided")                            # row centre 2080, slot centres 2030 and 2130
    assert got == 2000.0, got


def t_no_slot():
    lv = grid_levels(-60.0)
    assert L.choose_slot(1000.0, lv, [float(f) for f in range(0, 3000, 5)], "two-sided")[0] is None
    lv = grid_levels(-60.0)
    lv = {f: (-60.0 if i % 2 == 0 else -40.0) for i, f in enumerate(L.slot_grid())}  # floor is the median; a mix leaves some qualifying
    assert L.choose_slot(1000.0, lv, [], "two-sided")[0] is not None


def t_shift_copy_moves_tone():
    t = np.arange(L.PCM) / L.FS
    x = np.cos(2 * math.pi * 1000.0 * t)
    z = np.exp(2j * math.pi * 1000.0 * t)
    y = L.shift_copy(x.astype(np.float32), z.real.astype(np.float32), z.imag.astype(np.float32), 250.0)
    sp = np.abs(np.fft.rfft(y))
    assert abs(np.argmax(sp) * L.FS / L.PCM - 1250.0) < 0.5


def cyc_synth():
    n = 6
    z = lambda *v: np.array(v + (0,) * (n - len(v)), dtype=float)
    return {"nref": np.full(n, 20000.0 / n * 0.0 + 12124.0 / n), "ns_dec": z(10, 10, 10), "ns_fitzero": z(3, 0, 0), "ns_noslot": z(0, 4, 0),
            "pure_dec": z(10, 10, 10), "pure_copy": z(20, 20, 20), "hit_dec": z(9, 9, 9), "hit_copy": z(10, 10, 10), "weak_dec": z(1, 1, 1), "weak_copy": z(10, 10, 10)}


def t_readout_semantics():
    c = cyc_synth()
    idx = np.tile(np.arange(6), (50, 1))                                            # every replicate = the full set: CI equals the point
    r = L.readout(c, idx)
    d = c["nref"].sum()
    assert abs(r["RAW_worst_pp"] - 100.0 * (30 + 3 + 4) / d) < 1e-9                  # dec + fit-zero + no-slot
    assert abs(r["RL_CTRL_HIT"] - 0.9) < 1e-12 and abs(r["RL_CTRL_WEAK"] - 0.1) < 1e-12
    assert abs(r["NET_CEIL_pp"] - 100.0 * (30 - 0.1 * 60) / d) < 1e-9                # optimism removed; fit-zero and no-slot rows add nothing
    assert abs(r["RAW_over_RL_pp"] - r["RAW_worst_pp"] / 0.9) < 1e-9
    assert r["F3_RAW_over_RL_ge_NET_all_replicates"] is True


def t_f3_with_random_data():
    rng = np.random.default_rng(1)
    for _ in range(20):
        n = 30
        pure_copy = rng.integers(5, 30, n).astype(float)
        pure_dec = np.minimum(pure_copy, rng.integers(0, 12, n).astype(float))
        ns_dec = pure_dec + rng.integers(0, 4, n)
        weak_copy = rng.integers(2, 10, n).astype(float)
        c = {"nref": rng.integers(20, 40, n).astype(float), "ns_dec": ns_dec, "ns_fitzero": rng.integers(0, 2, n).astype(float), "ns_noslot": rng.integers(0, 2, n).astype(float),
             "pure_dec": pure_dec, "pure_copy": pure_copy, "hit_dec": rng.integers(5, 10, n).astype(float), "hit_copy": np.full(n, 10.0),
             "weak_dec": np.minimum(weak_copy, rng.integers(0, 4, n).astype(float)), "weak_copy": weak_copy}
        r = L.readout(c, np.random.default_rng(2).integers(0, n, size=(40, n)))
        assert r["F3_RAW_over_RL_ge_NET_all_replicates"] is True


def t_verdict_rows():
    base = {"RAW_over_RL_hi_incl_inf": 0.5, "NET_CEIL_pp_CI": [-0.2, 0.3]}
    assert L.verdict(base, False, True, True) == "STOP"
    assert L.verdict(base, True, False, True) == "VOID" and L.verdict(base, True, True, False) == "VOID"
    assert L.verdict(base, True, True, True) == "CLOSE"
    assert L.verdict({"RAW_over_RL_hi_incl_inf": 1.0, "NET_CEIL_pp_CI": [0.99, 2.0]}, True, True, True) == "BETWEEN"       # bars are strict / inclusive as registered
    assert L.verdict({"RAW_over_RL_hi_incl_inf": 3.0, "NET_CEIL_pp_CI": [1.0, 2.0]}, True, True, True) == "MODEL-STUDY"
    assert L.verdict({"RAW_over_RL_hi_incl_inf": 3.0, "NET_CEIL_pp_CI": [0.4, 2.0]}, True, True, True) == "BETWEEN"
    assert L.verdict({"RAW_over_RL_hi_incl_inf": 0.999, "NET_CEIL_pp_CI": [0.0, 0.5]}, True, True, True) == "CLOSE"


def t_build_cyc_counts():
    stamps = ["s0", "s1"]
    rows = []
    def row(s, idx, nr=False, pure=False, hit=False, weak=False, slot=True):
        rows.append({"stamp": s, "idx": idx, "in_CS_NR": nr, "in_pure": pure, "in_CTRL_HIT": hit, "in_CTRL_WEAK": weak, "f_s": 500.0 if slot else None})
    row("s0", 0, nr=True, pure=True)                  # decodable
    row("s0", 1, nr=True, pure=True)                  # copy, not decodable
    row("s0", 2, nr=True, pure=True)                  # fit-zero
    row("s0", 3, nr=True, pure=True, slot=False)      # no slot
    row("s1", 0, hit=True)
    row("s1", 1, weak=True)
    rl = {("s0", 0): {"fit_zero": False, "unencodable": False, "decodable": True}, ("s0", 1): {"fit_zero": False, "unencodable": False, "decodable": False},
          ("s0", 2): {"fit_zero": True, "unencodable": False, "decodable": False}, ("s1", 0): {"fit_zero": False, "unencodable": False, "decodable": True},
          ("s1", 1): {"fit_zero": False, "unencodable": False, "decodable": False}}
    c = A.build_cyc(rows, rl, stamps, {"s0": 10, "s1": 7})
    assert list(c["ns_dec"]) == [1, 0] and list(c["ns_fitzero"]) == [1, 0] and list(c["ns_noslot"]) == [1, 0]
    assert list(c["pure_dec"]) == [1, 0] and list(c["pure_copy"]) == [2, 0]        # fit-zero and no-slot rows are not copies
    assert list(c["hit_dec"]) == [0, 1] and list(c["hit_copy"]) == [0, 1] and list(c["weak_copy"]) == [0, 1] and list(c["nref"]) == [10, 7]


TESTS = [t_floor_is_median_of_blocker_free, t_two_sided_band, t_blocker_and_nearest_and_ties, t_no_slot, t_shift_copy_moves_tone, t_readout_semantics, t_f3_with_random_data, t_verdict_rows, t_build_cyc_counts]


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


# ------------------------------------------------------------------------------------------------ mutations
def mut_tol():
    L.TOL_DB = 1.6


def mut_one_sided_as_two_sided():
    L.qualifies = lambda level, floor, rule: level is not None and floor is not None and level - floor <= L.TOL_DB


def mut_two_sided_as_upper_off():
    L.qualifies = lambda level, floor, rule: level is not None and floor is not None and abs(level - floor) <= L.TOL_DB * 3


def mut_floor_mean():
    L.cycle_floor = lambda lv, fb: float(np.mean([d for f, d in lv.items() if d is not None and not L.blocked(f, fb)])) if any(not L.blocked(f, fb) for f in lv) else None


def mut_floor_ignores_blockers():
    L.cycle_floor = lambda lv, fb: float(np.median([d for d in lv.values() if d is not None]))


def mut_tie_upper():
    orig = L.choose_slot

    def f(row_f, lv, fb, rule="two-sided"):
        floor = L.cycle_floor(lv, fb)
        best = None
        for f_s in L.slot_grid():
            if L.blocked(f_s, fb) or not L.qualifies(lv.get(f_s), floor, rule):
                continue
            key = (abs((f_s + L.SLOT_W / 2.0) - (row_f + L.SIGNAL_HZ / 2.0)), -f_s)
            if best is None or key < best[0]:
                best = (key, f_s)
        return (None if best is None else best[1]), floor
    L.choose_slot = f


def mut_block_narrow():
    L.BLOCK_LO = 10.0


def mut_block_off():
    L.blocked = lambda f_s, freqs: False


def mut_farthest():
    orig_slot = L.slot_grid
    L.choose_slot = lambda row_f, lv, fb, rule="two-sided": (max([f for f in L.slot_grid() if not L.blocked(f, fb) and L.qualifies(lv.get(f), L.cycle_floor(lv, fb), rule)], default=None), L.cycle_floor(lv, fb))


def mut_shift_sign():
    L.shift_copy = lambda shat, re_, im_, d: (re_.astype(np.float64) * np.cos(2 * math.pi * d * np.arange(L.PCM) / L.FS) + im_.astype(np.float64) * np.sin(2 * math.pi * d * np.arange(L.PCM) / L.FS)).astype(np.float32)


def mut_readout_raw_no_fitzero():
    orig = L.readout

    def f(cyc, idx):
        c = dict(cyc)
        c["ns_fitzero"] = np.zeros_like(c["ns_fitzero"])
        return orig(c, idx)
    L.readout = f


def mut_readout_raw_no_noslot():
    orig = L.readout

    def f(cyc, idx):
        c = dict(cyc)
        c["ns_noslot"] = np.zeros_like(c["ns_noslot"])
        return orig(c, idx)
    L.readout = f


def mut_readout_net_no_optimism():
    orig = L.readout

    def f(cyc, idx):
        c = dict(cyc)
        c["weak_dec"] = np.zeros_like(c["weak_dec"])
        return orig(c, idx)
    L.readout = f


def mut_verdict_close_nonstrict():
    orig = L.verdict

    def f(res, a, b, c):
        res = dict(res)
        res["RAW_over_RL_hi_incl_inf"] -= 0.0
        out = orig(res, a, b, c)
        return "CLOSE" if (a and b and c and res["RAW_over_RL_hi_incl_inf"] <= L.BAR_PP and res["NET_CEIL_pp_CI"][0] < L.BAR_PP) else out
    L.verdict = f


def mut_verdict_study_strict():
    orig = L.verdict

    def f(res, a, b, c):
        out = orig(res, a, b, c)
        return "BETWEEN" if out == "MODEL-STUDY" and res["NET_CEIL_pp_CI"][0] <= L.BAR_PP else out
    L.verdict = f


def mut_verdict_skip_void():
    orig = L.verdict
    L.verdict = lambda res, a, b, c: orig(res, a, True, True)


def mut_buildcyc_fitzero_as_copy():
    orig = A.build_cyc

    def f(table, reloc, stamps, nref_by):
        rl2 = {k: dict(v, fit_zero=False) for k, v in reloc.items()}
        return orig(table, rl2, stamps, nref_by)
    A.build_cyc = f


MUTS = [mut_tol, mut_one_sided_as_two_sided, mut_two_sided_as_upper_off, mut_floor_mean, mut_floor_ignores_blockers, mut_tie_upper, mut_block_narrow, mut_block_off, mut_farthest, mut_shift_sign,
        mut_readout_raw_no_fitzero, mut_readout_raw_no_noslot, mut_readout_net_no_optimism, mut_verdict_close_nonstrict, mut_verdict_study_strict, mut_verdict_skip_void, mut_buildcyc_fitzero_as_copy]


def main():
    bad = run_tests()
    print("unmutated: " + ("ALL PASS" if not bad else "FAIL " + str(bad)))
    if bad:
        sys.exit(1)
    import importlib
    survivors = []
    for m in MUTS:
        importlib.reload(L)
        importlib.reload(A)
        globals()["L"], globals()["A"] = L, A
        m()
        killed = run_tests()
        print(f"{m.__name__:38s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            survivors.append(m.__name__)
    importlib.reload(L)
    importlib.reload(A)
    print(f"{len(MUTS) - len(survivors)} of {len(MUTS)} mutations killed")
    sys.exit(1 if survivors else 0)


if __name__ == "__main__":
    main()
