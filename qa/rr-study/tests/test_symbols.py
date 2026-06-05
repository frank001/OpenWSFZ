"""L3 — symbol assembly tests."""
import pytest

from synth import symbols
from synth.constants import (
    CODEWORD_BITS,
    COSTAS_ARRAY,
    COSTAS_START_INDICES,
    NUM_DATA_SYMBOLS,
    NUM_SYMBOLS,
    NUM_TONES,
)


def _codeword(pattern=0):
    return [(i + pattern) % 2 for i in range(CODEWORD_BITS)]


def test_data_bits_to_tones_count_and_range():
    tones = symbols.data_bits_to_tones(_codeword())
    assert len(tones) == NUM_DATA_SYMBOLS
    assert all(0 <= t < NUM_TONES for t in tones)


def test_assemble_length():
    assert len(symbols.assemble_symbols(_codeword())) == NUM_SYMBOLS


def test_costas_arrays_in_correct_positions():
    seq = symbols.assemble_symbols(_codeword(1))
    for start in COSTAS_START_INDICES:
        assert tuple(seq[start:start + len(COSTAS_ARRAY)]) == COSTAS_ARRAY


def test_gray_mapping_known_values():
    # value 0->0, 1->1, 2->3, 3->2, ... per FT8 Gray map
    cw = [0, 0, 0] + [0, 0, 1] + [0, 1, 0] + [0, 1, 1] + [0] * (CODEWORD_BITS - 12)
    tones = symbols.data_bits_to_tones(cw)
    assert tones[:4] == [0, 1, 3, 2]


def test_rejects_wrong_codeword_length():
    with pytest.raises(ValueError):
        symbols.assemble_symbols([0] * 173)
