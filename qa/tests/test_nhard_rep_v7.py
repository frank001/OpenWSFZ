"""Tests for qa/rr-study/nhard-rep/nhard_rep_v7.py (NHARD-REP Amendment 3's V7 pairing control): PASS iff 0 of the first 100 sampled cycles differ in matched set or decode multiset.

HK-026 / HK-021 (k): the comparison is shown to give BOTH answers. Synthetic numeric data only (NFR-021 / HK-037).
"""
import json
import sys
from pathlib import Path

import pytest

NH = Path(__file__).resolve().parent.parent / "rr-study" / "nhard-rep"
sys.path.insert(0, str(NH))
import nhard_rep_v7 as V  # noqa: E402

STAMPS = [f"261004_{i * 15:06d}" for i in range(100)]


def _write(d, arm, matched, outcomes):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"matched_{arm}.csv").write_text("stamp,wsjtx_idx\n" + "".join(f"{s},{';'.join(str(i) for i in sorted(m))}\n" for s, m in matched.items()))
    lines = []
    for s, (b1, b2) in outcomes.items():
        for kind, items in (("b1", b1), ("b2", b2)):
            for k, (f, dt, snr) in enumerate(items):
                lines.append(f"{s},{kind},{k},{f},{dt},{snr}")
    (d / f"outcomes_{arm}.csv").write_text("\n".join(lines) + "\n")


def _world(tmp_path, mutate=None):
    matched = {s: {0, 1, 2, i % 5 + 3} for i, s in enumerate(STAMPS)}
    outcomes = {s: ([(1000 + i, "0.1", -10), (1500, "0.2", -12)], [(900 + i, "0.0", -20)]) for i, s in enumerate(STAMPS)}
    n40, v7 = tmp_path / "n40", tmp_path / "v7"
    _write(n40, "N40", matched, outcomes)
    m2 = {s: set(v) for s, v in matched.items()}
    o2 = {s: ([tuple(x) for x in b1], [tuple(x) for x in b2]) for s, (b1, b2) in outcomes.items()}
    if mutate:
        mutate(m2, o2)
    _write(v7, "V7", m2, o2)
    return v7, n40


def test_pass_on_identical_runs_and_order_within_a_cycle_does_not_matter(tmp_path):
    def reorder(m, o):
        b1, b2 = o[STAMPS[5]]
        o[STAMPS[5]] = (list(reversed(b1)), b2)          # the same multiset in another order
    v7, n40 = _world(tmp_path, reorder)
    ok, d = V.compare(str(v7), str(n40), STAMPS)
    assert ok is True and d["differing_cycles"] == 0 and d["n"] == 100


def test_a_different_matched_set_fails(tmp_path):
    v7, n40 = _world(tmp_path, lambda m, o: m[STAMPS[40]].add(99))
    ok, d = V.compare(str(v7), str(n40), STAMPS)
    assert ok is False and d["differing_cycles"] == 1 and d["reasons"] == {"matched_set": 1}


def test_a_different_decode_multiset_fails_in_either_batch(tmp_path):
    def b2_change(m, o):
        b1, b2 = o[STAMPS[10]]
        o[STAMPS[10]] = (b1, b2 + [(777, "0.1", -22)])
    v7, n40 = _world(tmp_path, b2_change)
    ok, d = V.compare(str(v7), str(n40), STAMPS)
    assert ok is False and d["reasons"] == {"decode_multiset_b2": 1}

    def b1_change(m, o):
        b1, b2 = o[STAMPS[11]]
        o[STAMPS[11]] = ([(1000 + 11, "0.1", -11)] + b1[1:], b2)       # one decode's SNR differs by 1 dB
    v7, n40 = _world(tmp_path / "x", b1_change)
    ok, d = V.compare(str(v7), str(n40), STAMPS)
    assert ok is False and "decode_multiset_b1" in d["reasons"]


def test_a_missing_cycle_or_wrong_size_or_absent_files_never_read_as_a_pass(tmp_path):
    def drop(m, o):
        del m[STAMPS[3]]
    v7, n40 = _world(tmp_path, drop)
    ok, d = V.compare(str(v7), str(n40), STAMPS)
    assert ok is False and d["reasons"].get("missing_matched") == 1
    v7, n40 = _world(tmp_path / "y")
    assert V.compare(str(v7), str(n40), STAMPS[:99])[0] is False                    # not 100 cycles
    assert V.compare(str(tmp_path / "nowhere"), str(tmp_path / "nowhere2"), STAMPS)[0] is False


def test_several_differences_are_all_counted(tmp_path):
    def many(m, o):
        for i in (1, 2, 3):
            m[STAMPS[i]].add(88)
    v7, n40 = _world(tmp_path, many)
    ok, d = V.compare(str(v7), str(n40), STAMPS)
    assert ok is False and d["differing_cycles"] == 3 and len(d["differing_stamps"]) == 3


def test_the_control_uses_the_first_100_cycles_of_the_frozen_sample_and_the_n40_setting():
    stamps, warmup = V.first_stamps()
    sel = json.loads(V.N0.SELECTION and Path(V.N0.SELECTION).read_bytes())
    assert len(stamps) == 100 == V.N_CYCLES and stamps == sel["runs"][sel["run"]]["SAMPLE"][:100] and warmup == sel["runs"][sel["run"]]["warmup"]
    assert V.V7_NHARD == 40 and V.N0.NHARD == 0                                     # the control re-runs 40, never 0
