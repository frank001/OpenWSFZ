"""Tests for qa/rr-study/density-sub/density_sub_rows.py (DENSITY-SUB pre-registered rows).

HK-026 / HK-021 (k): each row is shown to give BOTH answers on a synthetic input. All data is synthetic and numeric
(NFR-021 / HK-037): stamps, SNR and frequency integers, no message text, no callsign.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

SUB = Path(__file__).resolve().parent.parent / "rr-study" / "density-sub"
sys.path.insert(0, str(SUB))
import density_sub_rows as r  # noqa: E402


# ---- loading: text never kept ----------------------------------------------------------------------------------
def test_load_w_keeps_numbers_only(tmp_path):
    p = tmp_path / "ALL.TXT"
    p.write_text("S1     7.074 Rx FT8      9  0.0 1753 AAAA BBBB RR73\n"
                 "S1     7.074 Rx FT8     -4  1.8 2659 CCCC DDDD\n"
                 "S2     7.074 Rx FT8      0  0.1 1000 EEEE FFFF\n"
                 "S1     7.074 Tx FT8      0  0.1 1000 MYCALL\n", encoding="utf-8")
    w = r.load_w(str(p), ["S1", "S2", "S3"])
    assert w == {"S1": [(9, 1753), (-4, 2659)], "S2": [(0, 1000)], "S3": []}
    flat = repr(w)
    assert "AAAA" not in flat and "RR73" not in flat


def test_load_matched_handles_empty_and_indices(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("stamp,wsjtx_idx\nS1,0;2;5\nS2,\n", encoding="utf-8")
    assert r.load_matched(str(p)) == {"S1": {0, 2, 5}, "S2": set()}


# ---- strata: from W only, neighbours by index ------------------------------------------------------------------
def test_classify_cycle_exposed_and_pl_and_population_cut():
    # row 0 (snr 0, 1000 Hz) has a stronger neighbour within 18 Hz: EXPOSED. row 1 (snr 5) is its neighbour, no near stronger: CLEAR/PF.
    # row 2 is below the population cut (-12) and must not be classified, but still counts as a neighbour.
    w = [(0, 1000), (5, 1010), (-12, 3000)]
    c = r.classify_cycle(w)
    assert [(i, cls) for (i, _, _, cls) in c][0] == (0, "EXPOSED")
    assert all(i != 2 for (i, _, _, _) in c)


def test_duplicate_snr_freq_rows_still_see_each_other():
    # two rows with IDENTICAL (snr, freq): by-index neighbours means each is EXPOSED to the other (rel 0 >= 0)
    c = r.classify_cycle([(3, 2000), (3, 2000)])
    assert [cls for (_, _, _, cls) in c] == ["EXPOSED", "EXPOSED"]


# ---- D on counts equals DENSITY-LIVE's own compute_D -----------------------------------------------------------
def test_D_from_counts_matches_density_live():
    rng = np.random.default_rng(1)
    rows_a, rows_b = [], []
    n_a = np.zeros(r.dl.N_CELLS, dtype=np.int64)
    h_a = n_a.copy()
    n_b = n_a.copy()
    h_b = n_a.copy()
    for _ in range(900):
        ci, hit = int(rng.integers(0, 21)), bool(rng.random() < 0.5)
        rows_a.append((ci, hit)); n_a[ci] += 1; h_a[ci] += hit
    for _ in range(1500):
        ci, hit = int(rng.integers(0, 21)), bool(rng.random() < 0.7)
        rows_b.append((ci, hit)); n_b[ci] += 1; h_b[ci] += hit
    ref = r.dl.compute_D(rows_a, rows_b)
    got = r.D_from_counts(n_a, h_a, n_b, h_b)
    assert got[0] == pytest.approx(ref[0], abs=1e-12)
    assert got[1:] == ref[1:]


# ---- V1: both answers, and the explained/unexplained split -----------------------------------------------------
STAMPS = [f"S{i}" for i in range(40)]


def test_v1_pass_when_identical_and_fail_when_one_unexplained():
    pc = {s: (3, 5) for s in STAMPS}
    ok = {s: {0, 1, 2} for s in STAMPS}
    assert r.row_v1(STAMPS, ok, pc, "off", None, None)["pass"]
    bad = dict(ok)
    bad["S7"] = {0, 1}
    out = r.row_v1(STAMPS, bad, pc, "off", None, None)
    assert not out["pass"] and out["unexplained"] == 1


def test_v1_on_arm_explained_by_abandonment_in_exactly_one_run_is_allowed_up_to_5pct():
    pc = {s: (3, 5) for s in STAMPS}
    on = {s: {0, 1, 2, 3, 4} for s in STAMPS}
    on["S1"] = {0, 1, 2}                      # one cycle differs: 1/40 = 2.5%
    new_ab = {s: 0 for s in STAMPS}
    old_ab = {s: 0 for s in STAMPS}
    new_ab["S1"] = 1                          # abandoned in the new run only: explained
    assert r.row_v1(STAMPS, on, pc, "on", new_ab, old_ab)["pass"]
    old_ab["S1"] = 1                          # abandoned in BOTH: not "exactly one", so unexplained
    assert not r.row_v1(STAMPS, on, pc, "on", new_ab, old_ab)["pass"]
    # three explained of 40 = 7.5% > 5%: fails on the fraction
    on2 = dict(on)
    new2 = {s: 0 for s in STAMPS}
    old2 = {s: 0 for s in STAMPS}
    for s in ("S1", "S2", "S3"):
        on2[s] = {0}
        new2[s] = 1
    assert not r.row_v1(STAMPS, on2, pc, "on", new2, old2)["pass"]


# ---- V2 / V3 / 0a / 0b -----------------------------------------------------------------------------------------
def test_v2_partition_pass_and_unknown_class_fails_loudly():
    cyc = [[(0, 0, 1000, "EXPOSED"), (1, 0, 2000, "PL")]]
    assert r.row_v2(cyc)["pass"]
    with pytest.raises(KeyError):
        r.row_v2([[(0, 0, 1000, "BOGUS")]])


def test_v3_threshold_both_sides():
    big = [[(i, 0, 1000, "EXPOSED") for i in range(200)]]
    small = [[(i, 0, 1000, "EXPOSED") for i in range(199)]]
    assert r.row_v3(big)["pass"] and not r.row_v3(small)["pass"]


def test_row_0a_both_sides():
    assert r.row_0a(-0.04, 0.04)["pass"]
    assert not r.row_0a(-0.06, 0.04)["pass"]
    assert not r.row_0a(-0.04, 0.06)["pass"]


def test_row_0b_both_sides():
    assert r.row_0b(5, 100, 5, 100)["pass"]
    assert not r.row_0b(6, 100, 5, 100)["pass"]
    assert not r.row_0b(5, 100, 6, 100)["pass"]


# ---- verdict: exclusive and exhaustive, all three branches -----------------------------------------------------
def test_verdict_three_branches_and_edges():
    assert r.verdict(0.05, 0.169) == "DS-REMEDIED"
    assert r.verdict(0.171, 0.30) == "DS-PERSISTS"
    assert r.verdict(0.10, 0.25) == "DS-OPEN"
    assert r.verdict(0.170, 0.30) == "DS-PERSISTS"     # CI_lo >= bar
    assert r.verdict(0.05, 0.170) == "DS-OPEN"         # CI_hi < bar is strict


# ---- bootstrap: deterministic, paired, picks up a real effect --------------------------------------------------
def _synthetic_stack(ncyc, hit_exposed, hit_pl, seed=3):
    rng = np.random.default_rng(seed)
    per = []
    for _ in range(ncyc):
        c = {k: (np.zeros(r.dl.N_CELLS, dtype=np.int64), np.zeros(r.dl.N_CELLS, dtype=np.int64)) for k in r.CLASSES}
        for k, p in (("EXPOSED", hit_exposed), ("PL", hit_pl), ("PF", hit_pl)):
            for cell in range(5, 15):
                n = 3
                c[k][0][cell] = n
                c[k][1][cell] = int((rng.random(n) < p).sum())
        per.append(c)
    return r.block_sums(r.stack(per), ncyc)


def test_bootstrap_is_deterministic_and_separates_an_effect_from_none():
    # EXPOSED hits 30% vs PL 80%: D ~ 0.5; with no effect D ~ 0
    eff = _synthetic_stack(120, 0.3, 0.8)
    non = _synthetic_stack(120, 0.8, 0.8, seed=4)
    pairs = [("off", "EXPOSED", "PL"), ("on", "EXPOSED", "PL")]
    d1, _ = r.bootstrap(eff, non, pairs, n_boot=300)
    d2, _ = r.bootstrap(eff, non, pairs, n_boot=300)
    assert np.array_equal(d1[("off", "EXPOSED", "PL")], d2[("off", "EXPOSED", "PL")])
    lo_e, hi_e = r.ci95(d1[("off", "EXPOSED", "PL")])
    lo_n, hi_n = r.ci95(d1[("on", "EXPOSED", "PL")])
    assert lo_e > 0.3 and hi_n < 0.17 and lo_n < 0.0 + 0.1
    assert r.verdict(lo_e, hi_e) == "DS-PERSISTS" and r.verdict(lo_n, hi_n) == "DS-REMEDIED"


def test_block_sums_partitions_cycles():
    S = _synthetic_stack(10, 0.5, 0.5)       # blocks of 4: sizes 4, 4, 2 -> 3 blocks
    assert S["EXPOSED"][0].shape[0] == 3
    full = r.stack([{k: (np.ones(r.dl.N_CELLS, dtype=np.int64), np.zeros(r.dl.N_CELLS, dtype=np.int64)) for k in r.CLASSES}
                    for _ in range(10)])
    b = r.block_sums(full, 10)
    assert b["PL"][0].sum() == 10 * r.dl.N_CELLS
