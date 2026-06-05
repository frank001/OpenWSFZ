"""L3 — Codeword bits -> 79 transmitted tone indices.

The 174-bit LDPC codeword becomes 58 data symbols (3 bits each, Gray-coded to a
tone). The three 7-symbol Costas sync arrays are inserted at symbol indices
0..6, 36..42, 72..78, giving the full 79-symbol transmission.
"""
from __future__ import annotations

from .constants import (
    BITS_PER_SYMBOL,
    CODEWORD_BITS,
    COSTAS_ARRAY,
    COSTAS_START_INDICES,
    GRAY_MAP,
    NUM_DATA_SYMBOLS,
    NUM_SYMBOLS,
)

_COSTAS_POSITIONS = {
    start + i: COSTAS_ARRAY[i]
    for start in COSTAS_START_INDICES
    for i in range(len(COSTAS_ARRAY))
}


def data_bits_to_tones(codeword_bits: list[int]) -> list[int]:
    """Map 174 codeword bits to 58 Gray-coded data tone indices (0..7)."""
    if len(codeword_bits) != CODEWORD_BITS:
        raise ValueError(f"expected {CODEWORD_BITS} codeword bits, got {len(codeword_bits)}")
    tones = []
    for s in range(NUM_DATA_SYMBOLS):
        b0, b1, b2 = codeword_bits[s * BITS_PER_SYMBOL: s * BITS_PER_SYMBOL + 3]
        value = (b0 << 2) | (b1 << 1) | b2  # MSB-first
        tones.append(GRAY_MAP[value])
    return tones


def assemble_symbols(codeword_bits: list[int]) -> list[int]:
    """Return the full 79-tone transmission: data symbols interleaved with Costas sync."""
    data_tones = data_bits_to_tones(codeword_bits)
    out: list[int] = []
    data_iter = iter(data_tones)
    for idx in range(NUM_SYMBOLS):
        if idx in _COSTAS_POSITIONS:
            out.append(_COSTAS_POSITIONS[idx])
        else:
            out.append(next(data_iter))
    assert len(out) == NUM_SYMBOLS
    return out
