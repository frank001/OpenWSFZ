"""Tests for coh-gain/cg_gate_rows.py (Q-GATE thresholds and rows). SYNTHETIC rows only; no real label is touched."""
import sys
from pathlib import Path

import numpy as np
import pytest

CGD = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CGD))
import cg_gate_rows as G  # noqa: E402
import cg_gate_run as GR  # noqa: E402


def mk(sample, cyc, f1, f2, label, widx=0):
    return (sample, cyc, widx, f1, f2, 0.0, label)


def rows_separable():
    # RIGHT rows: low F1b (kept for F1b <= T1), high F2; UNEXPL rows the opposite
    r = []
    for i in range(40):
        r.append(mk(5, i % 8, -5.0 - i * 0.1, 0.9, "RIGHT", i))
    for i in range(40):
        r.append(mk(5, i % 8, 10.0 + i * 0.1, 0.2, "UNEXPL", 100 + i))
    return r


def test_constants_frozen_and_samples_disjoint():
    assert G.U_MAX == 0.15 and G.BAR_KG == 1.0
    assert set(GR.TRAIN).isdisjoint(GR.TEST)


def test_select_thresholds_separable_keeps_all_right_no_unexplained():
    th = G.select_thresholds(rows_separable(), n_train_cycles=8)
    for form in ("GA", "GB", "GC"):
        assert th[form]["kept_right"] == 40 and th[form]["kept_unexplained"] == 0


def test_select_thresholds_infeasible_when_every_row_is_unexplained():
    rows = [mk(5, i, 0.0, 0.5, "UNEXPL", i) for i in range(10)]
    th = G.select_thresholds(rows, n_train_cycles=2)         # cap 0.3 < any kept
    assert th == {"GA": None, "GB": None, "GC": None}


def test_cap_is_respected_and_right_is_maximised_under_it():
    rows = rows_separable()
    rows += [mk(5, 0, -20.0, 0.95, "UNEXPL", 500)]            # one unexplained that looks great
    th = G.select_thresholds(rows, n_train_cycles=8)           # cap = 1.2 -> one is tolerated
    assert th["GA"]["kept_unexplained"] <= 1.2 and th["GA"]["kept_right"] == 40


def test_gc_grid_equals_brute_force():
    rng = np.random.default_rng(3)
    rows = [mk(5, int(i % 6), float(rng.normal()), float(rng.integers(0, 10) / 10), str(rng.choice(["RIGHT", "UNEXPL", "NEAR"], p=[.5, .3, .2])), i) for i in range(120)]
    n_cyc = 6
    th = G.select_thresholds(rows, n_cyc)["GC"]
    f1 = np.array([r[3] for r in rows]); f2 = np.array([r[4] for r in rows])
    right = np.array([r[6] == "RIGHT" for r in rows]); un = np.array([r[6] == "UNEXPL" for r in rows])
    best = -1
    for t1 in np.unique(f1):
        for t2 in np.unique(f2):
            m = (f1 <= t1) & (f2 >= t2)
            if un[m].sum() <= 0.15 * n_cyc and right[m].sum() > best:
                best = right[m].sum()
    assert (th is None and best < 0) or th["kept_right"] == best


def test_threshold_selection_refuses_test_samples():
    with pytest.raises(AssertionError):
        G.select_thresholds([mk(6, 0, 0.0, 0.5, "RIGHT")], 1)


def test_gate_row_is_exclusive_and_mechanical():
    assert G.gate_row(1.2, 1.9, 0.05, 0.14) == "GATE-OK"
    assert G.gate_row(0.5, 0.9, 0.05, 0.10) == "GATE-FAIL"      # KG hi < bar
    assert G.gate_row(1.2, 1.9, 0.16, 0.30) == "GATE-FAIL"      # UPC lo > U_max
    assert G.gate_row(0.8, 1.5, 0.05, 0.14) == "GATE-OPEN"
    assert G.gate_row(1.2, 1.9, 0.05, 0.16) == "GATE-OPEN"


def test_test_refuses_when_thresholds_not_committed(tmp_path):
    p = tmp_path / "gate_thresholds.json"
    p.write_text("{}")
    with pytest.raises(AssertionError):
        G.cmd_test(thresholds_path=str(p))


def test_evaluate_counts_and_keep_mask():
    rows = [mk(6, 0, -1.0, 0.9, "RIGHT"), mk(6, 0, 5.0, 0.9, "UNEXPL", 1), mk(6, 1, -1.0, 0.1, "NEAR", 2)]
    th = {"T1": 0.0}
    cycles = {6: [0, 1, 2, 3]}
    rpc = {6: {0: 10, 1: 10, 2: 10, 3: 10}}
    ev = G.evaluate(rows, "GA", th, {6}, cycles, rpc)
    assert ev["kept_right"] == 1 and ev["kept_unexplained"] == 0 and ev["kept_near"] == 1 and ev["n_rows"] == 40
    assert abs(ev["KG_pp"] - 100 * 1 / 40) < 1e-9 and ev["UPC"] == 0.0
    assert G.keep_mask("GA", None, [1.0], [1.0]).tolist() == [False]
