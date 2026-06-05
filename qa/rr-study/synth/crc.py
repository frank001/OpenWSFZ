"""L2 — FT8 CRC-14.

The FT8 protocol appends a 14-bit CRC to the 77-bit message. The CRC is computed
over the 77 message bits followed by zero padding to 82 bits, MSB-first, using the
published 14-bit polynomial 0x2757 (x^14 + ... + 1, with implicit x^14 term).

Reference: public FT8 protocol description. This is a clean-room reimplementation.
"""
from __future__ import annotations

from .constants import CRC_BITS, MESSAGE_BITS

CRC14_POLY = 0x2757  # 14-bit generator polynomial (implicit leading term)
_TOPBIT = 1 << (CRC_BITS - 1)
_MASK = (1 << CRC_BITS) - 1

# Per the FT8 spec the 77 message bits are right-padded with zeros to 82 bits
# before the CRC is computed; the CRC then occupies bits 77..90 of the 91-bit word.
_PAD_TO_BITS = 82


def crc14(message_bits: list[int]) -> list[int]:
    """Return the 14-bit CRC of a 77-bit message as a list of 0/1 (MSB first)."""
    if len(message_bits) != MESSAGE_BITS:
        raise ValueError(f"expected {MESSAGE_BITS} message bits, got {len(message_bits)}")

    padded = list(message_bits) + [0] * (_PAD_TO_BITS - MESSAGE_BITS)

    reg = 0
    for bit in padded:
        reg ^= (bit & 1) << (CRC_BITS - 1)
        # process this bit through the register
        msb = reg & _TOPBIT
        reg = (reg << 1) & _MASK
        if msb:
            reg ^= CRC14_POLY
    reg &= _MASK
    return [(reg >> i) & 1 for i in range(CRC_BITS - 1, -1, -1)]


def append_crc(message_bits: list[int]) -> list[int]:
    """Return the 91-bit (message + CRC) word."""
    return list(message_bits) + crc14(message_bits)
