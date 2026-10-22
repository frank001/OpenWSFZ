"""Unit tests for ows_decode_overlap.py (toy intervals; no callsigns)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import ows_decode_overlap as O  # noqa: E402


def test_overlap_is_strict_at_the_edges():
    assert O.overlaps(2.5, 3.5, 3.0, 4.0)
    assert not O.overlaps(2.5, 3.5, 3.5, 4.0)               # touching at a point is not overlap
    assert not O.overlaps(0.0, 1.0, 1.0, 2.0)


def test_decode_intervals_chain_pass0_then_residual():
    iv = O.decode_intervals(250, 1141)
    assert iv["pass0"] == (0.0, 0.25) and abs(iv["residual"][0] - 0.25) < 1e-12 and abs(iv["residual"][1] - 1.391) < 1e-12 and iv["active"] == (0.0, iv["residual"][1])
    iv = O.decode_intervals(250, None)
    assert iv["residual"] is None and iv["active"] == (0.0, 0.25)
    assert O.decode_intervals(None, 100) is None


def test_a_long_residual_pass_covers_a_step_at_chunk_3_a_short_one_does_not():
    long_ = O.decode_intervals(200, 3500)                    # decode runs to 3.7 s
    short = O.decode_intervals(200, 800)                     # decode ends at 1.0 s
    lo, hi = 3 - O.HALF, 3 + O.HALF
    assert O.overlaps(lo, hi, *long_["active"]) and not O.overlaps(lo, hi, *short["active"])


def test_step_positions_are_the_chunk_where_the_new_e_starts():
    e = [0.0, 0.0, 0.0, 0.3, 0.3, None, 0.3]
    assert O.step_positions(e, 0.05) == [3]


def test_pairing_is_seeded_and_the_same_size():
    chosen, pairing = O.pair_controls([2, 5, 9], [1, 3, 4, 6, 7, 8, 10, 11])
    assert len(chosen) == 3 and set(pairing) == {2, 5, 9} and set(pairing.values()) == set(chosen)
    assert O.pair_controls([2, 5, 9], [1, 3, 4, 6, 7, 8, 10, 11]) == (chosen, pairing)


def test_share_and_summarise():
    assert O.share([True, False, True]) == {"n": 3, "overlap": 2, "share": 2 / 3}
    assert O.share([])["share"] is None
    assert O.summarise([1.0, 2.0, None, 3.0])["n"] == 3 and O.summarise([None])["n"] == 0
