"""L2 — CRC-14 tests."""
from synth import crc
from synth.constants import CRC_BITS, MESSAGE_BITS, MESSAGE_PLUS_CRC_BITS


def test_crc_width_and_binary():
    bits = [0] * MESSAGE_BITS
    out = crc.crc14(bits)
    assert len(out) == CRC_BITS
    assert all(b in (0, 1) for b in out)


def test_append_crc_width():
    bits = [1, 0] * 38 + [1]  # 77 bits
    assert len(bits) == MESSAGE_BITS
    assert len(crc.append_crc(bits)) == MESSAGE_PLUS_CRC_BITS


def test_crc_rejects_wrong_length():
    import pytest
    with pytest.raises(ValueError):
        crc.crc14([0] * 76)


def test_crc_is_deterministic_and_sensitive():
    base = [0] * MESSAGE_BITS
    c0 = crc.crc14(base)
    assert crc.crc14(base) == c0          # deterministic
    flipped = base.copy()
    flipped[0] = 1
    assert crc.crc14(flipped) != c0       # single-bit change alters CRC
