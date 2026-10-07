"""Tests for coh-gain/cg_field.py and cg_field_rows.py (FIELD-ID). Synthetic payloads and rows; no real message is touched."""
import random
import sys
from pathlib import Path

import pytest

CGD = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CGD))
import cg_common as CG  # noqa: E402
import cg_field as FD  # noqa: E402
import cg_field_rows as FR  # noqa: E402
import pack77_fields as PF  # noqa: E402


def payload(seed, i3=1):
    r = random.Random(seed)
    b = [r.randint(0, 1) for _ in range(77)]
    b[74:77] = [(i3 >> 2) & 1, (i3 >> 1) & 1, i3 & 1]
    return b


def row(**kw):
    base = {"sample": 1, "cycle_index": 0, "widx": 0, "kind": "X", "w1_ok": 1, "w1g_ok": 1, "i3x": 1, "n3x": 0, "i3t": 1, "n3t": 0, "layout": "std", "c1_eq": 0, "c2_eq": 0,
            "rpt_eq": 0, "adj": "none", "n_unenc_near": 0, "t_alt_eq": 0, "x3_ok": 1, "g2": 0}
    base.update(kw)
    return base


def test_class_order_first_match_wins_and_g2_precedes_hash():
    assert FR.classify(row(t_alt_eq=1, adj=-1, c1_eq=1, c2_eq=1, g2=1, n_unenc_near=3)) == "E-ENC"
    assert FR.classify(row(adj=1, c1_eq=1, c2_eq=1, g2=1)) == "E-ADJ"
    assert FR.classify(row(c1_eq=1, c2_eq=1, g2=1, n_unenc_near=2)) == "E-QSO"
    assert FR.classify(row(c1_eq=1, c2_eq=0, g2=1, n_unenc_near=2)) == "E-G2"
    assert FR.classify(row(n_unenc_near=1)) == "E-HASH"
    assert FR.classify(row()) == "E-RESIDUAL"
    assert FR.NUMERATOR == ("E-ADJ", "E-QSO")
    assert "E-G2" not in FR.NUMERATOR           # 17.1 B: E-G2 never enters E's numerator


def test_reading_is_exclusive_and_mechanical():
    assert FR.reading(0.55, 0.70) == "E-EXPLAINED"
    assert FR.reading(0.20, 0.49) == "E-RESIDUAL"
    assert FR.reading(0.40, 0.60) == "E-MIXED"
    assert FR.reading(0.50, 0.60) == "E-EXPLAINED" and FR.reading(0.10, 0.50) == "E-MIXED"


def test_field_flags_std_and_nonstd_and_other():
    t = payload(1)
    x = list(t)
    x[58:74] = [1 - b for b in x[58:74]]                       # only the report/grid differs
    lay, c1, c2, rp = FD.field_flags(x, t)
    assert (lay, c1, c2, rp) == ("std", 1, 1, 0)
    y = list(t)
    y[3] = 1 - y[3]
    assert FD.field_flags(y, t)[1:] == (0, 1, 1)               # call 1 differs only
    n1, n2 = payload(2, 4), payload(2, 4)
    assert FD.field_flags(n1, n2) == ("nonstd", 1, 1, 1)
    assert FD.field_flags(payload(3, 1), payload(3, 4)) == ("other", 0, 0, 0)


def test_the_suffix_flag_bit_is_excluded_from_the_callsign_word():
    t = payload(5)
    x = list(t)
    x[28] = 1 - x[28]                                          # /R flag of call 1
    assert FD.field_flags(x, t)[1] == 1


def test_rr73_variant_is_the_only_alternative_and_identity_is_excluded():
    t = payload(7)
    f_ir, f_g = CG.RR73_STD
    t[58] = f_ir
    t[59:74] = [(f_g >> (14 - k)) & 1 for k in range(15)]
    alts = FD.alt_packings(t)
    assert len(alts) == 1 and alts[0] != t
    f = PF.std_fields(alts[0])
    assert (f.ir, f.igrid4) == CG.V_STAR
    assert FD.identity_roundtrip(t, list(t)) and not FD.identity_roundtrip(t, alts[0])
    assert FD.alt_packings(payload(8)) == []                   # a non-RR73 message has no alternative via the ABI


def test_stamp_shift_and_window():
    assert FD.stamp_shift("261004_163700", 1) == "261004_163715" and FD.stamp_shift("261004_163700", -2) == "261004_163630"
    assert FD.stamp_shift("261004_235945", 1) == "261005_000000"
    assert FD.window(12.5, 0.32) and not FD.window(12.6, 0.0) and not FD.window(0.0, 0.33)


def test_adj_prefers_nearest_cycle_and_respects_the_window():
    x = payload(11)
    ws = {FD.stamp_shift("261004_163700", 2): [(0, 0.1, 1000, "A")], FD.stamp_shift("261004_163700", -1): [(0, 0.1, 1100, "B")]}
    enc = lambda text: x if text in ("A", "B") else None        # noqa: E731
    assert FD.adj_of(x, 1000.0, 0.1, "261004_163700", ws, enc) == 2          # B is outside the 12.5 Hz window
    ws[FD.stamp_shift("261004_163700", -1)] = [(0, 0.1, 1005, "B")]
    assert FD.adj_of(x, 1000.0, 0.1, "261004_163700", ws, enc) == -1
    assert FD.adj_of(payload(12), 1000.0, 0.1, "261004_163700", ws, enc) == "none"


def test_unencodable_near_counts_only_inside_the_window():
    lines = [(0, 0.0, 1000, "U"), (0, 0.0, 1100, "U"), (0, 0.0, 1002, "E")]
    enc = lambda text: None if text == "U" else payload(1)       # noqa: E731
    assert FD.n_unenc_near_of(1000.0, 0.0, lines, enc) == 1


def test_analyse_validity_gates_the_reading():
    rows = [row(widx=i, cycle_index=i % 8, adj=-1) for i in range(917)]
    rows += [row(widx=1000 + i, kind="OSD", cycle_index=i % 8) for i in range(215)]
    cyc = {1: list(range(8))}
    a = FR.analyse(rows, cycles=cyc)
    assert a["valid"] and a["reading"] == "E-EXPLAINED" and a["x_class_counts"]["E-ADJ"] == 917
    bad = [dict(r) for r in rows]
    for r in bad[917:920]:
        r["adj"] = 1                                           # 3 of the 215 OSD controls fall in a numerator class: 1.4 %, still valid
    assert FR.analyse(bad, cycles=cyc)["validity"]["X2"]["pass"]
    for r in bad[917:935]:
        r["adj"] = 1                                           # 18 of 215 = 8.4 % > 5 %: the instrument claims something about chance codewords
    a2 = FR.analyse(bad, cycles=cyc)
    assert not a2["validity"]["X2"]["pass"] and a2["reading"] == "NO READING"
    bad2 = [dict(r) for r in rows]
    bad2[0]["x3_ok"] = 0
    assert FR.analyse(bad2, cycles=cyc)["reading"] == "NO READING"
    bad3 = [dict(r) for r in rows]
    bad3[5]["w1g_ok"] = 0
    assert not FR.analyse(bad3, cycles=cyc)["validity"]["X1"]["pass"]


def test_g2_does_not_move_the_reading():
    rows = [row(widx=i, cycle_index=i % 8, g2=1) for i in range(917)]
    rows += [row(widx=1000 + i, kind="OSD", cycle_index=i % 8) for i in range(215)]
    a = FR.analyse(rows, cycles={1: list(range(8))})
    assert a["E"] == 0.0 and a["x_class_counts"]["E-G2"] == 917 and a["reading"] == "E-RESIDUAL"
