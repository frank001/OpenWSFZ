#!/usr/bin/env python3
"""SUB-FEAS: from-scratch LDPC(174,91) systematic encode + CRC-14, needed for
ROW 0f (the RR73 on-air-grid alternate hypothesis, spec sec.4). ft8_encode_message
only accepts message TEXT and cannot produce a payload with an arbitrary
(ir, igrid4) field value (32373 is not a parseable Maidenhead locator string) --
this module builds the alternate 174-bit codeword directly from BITS instead.

Licence policy (standing-licence-policy.md / the spec's sec.1 note): the QEX paper
and WSJT-X are METHOD-ONLY, no line copied. ft8_lib is different -- it is
MIT-licensed and already vendored in THIS repo (native/ft8_lib_vendor/), and the
spec explicitly allows mirroring it ("The GFSK synthesis may mirror the vendored
ft8_lib (MIT) generator"). The FT8 LDPC(174,91) generator matrix and CRC-14
parameters are protocol constants (the same class of reuse as
synth/constants.py's own GRAY_MAP/COSTAS_ARRAY, "protocol facts, not
implementation borrowed from any decoder") -- this module reads them directly out
of the vendored MIT file at runtime (never retyped/transcribed) and reimplements
the bit-serial CRC and generator-matrix-multiply from scratch in numpy/pure
Python, citing file/line below. Validated against `true_codeword()` (the
production ctypes binding's own encode path) for both the real message population
and random synthetic messages -- see validate_against_dll() below.

Source:
  native/ft8_lib_vendor/ft8/constants.c:29-30  kFTX_LDPC_generator[83][12] (data)
  native/ft8_lib_vendor/ft8/constants.h:42-50  FTX_LDPC_N/K/M, CRC poly+width
  native/ft8_lib_vendor/ft8/crc.c:10-37        ftx_compute_crc (method: standard
                                                bit-serial CRC-LFSR recurrence --
                                                the byte-at-a-time form there is a
                                                textbook-standard optimisation of
                                                the bit-serial form implemented here,
                                                not a different algorithm; validated
                                                bit-exact below, not assumed)
  native/ft8_lib_vendor/ft8/encode.c:22-63     encode174 (method: systematic
                                                generator-matrix dot product mod 2)
"""
from __future__ import annotations

import os
import re

import common

FTX_LDPC_N = 174
FTX_LDPC_K = 91
FTX_LDPC_M = 83
CRC_WIDTH = 14
CRC_POLY = 0x2757
CRC_TOPBIT = 1 << (CRC_WIDTH - 1)
CRC_MASK = (1 << CRC_WIDTH) - 1

_CONSTANTS_C = os.path.join(common.REPO_ROOT, "native", "ft8_lib_vendor", "ft8", "constants.c")

SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]
GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7]


def _parse_generator_matrix():
    """Reads kFTX_LDPC_generator directly from the vendored MIT source file (never
    retyped) and returns an 83 x 91 0/1 list-of-lists (bit [i][j])."""
    text = open(_CONSTANTS_C, encoding="utf-8").read()
    m = re.search(r"kFTX_LDPC_generator\[FTX_LDPC_M\]\[FTX_LDPC_K_BYTES\]\s*=\s*\{(.*?)\n\};",
                  text, re.S)
    if not m:
        raise RuntimeError("could not locate kFTX_LDPC_generator table in %s" % _CONSTANTS_C)
    body = m.group(1)
    rows_hex = re.findall(r"\{([^{}]*)\}", body)
    if len(rows_hex) != FTX_LDPC_M:
        raise RuntimeError("expected %d generator rows, found %d" % (FTX_LDPC_M, len(rows_hex)))
    matrix = []
    for row_hex in rows_hex:
        byte_strs = re.findall(r"0x([0-9a-fA-F]{2})", row_hex)
        byte_vals = [int(b, 16) for b in byte_strs]
        bits = []
        for byte in byte_vals:
            for k in range(7, -1, -1):
                bits.append((byte >> k) & 1)
        matrix.append(bits[:FTX_LDPC_K])  # top 91 of the 96 packed bits
    return matrix


_GENERATOR = None


def _generator():
    global _GENERATOR
    if _GENERATOR is None:
        _GENERATOR = _parse_generator_matrix()
    return _GENERATOR


def compute_crc14(bits, num_bits):
    """Standard bit-serial CRC-LFSR recurrence (MSB-first), width/poly per
    crc.c:4/49-50. `bits` may be shorter than `num_bits`; missing bits are zero
    (the CRC's own "zero-extend 77->82" padding, crc.c:56)."""
    remainder = 0
    for i in range(num_bits):
        bit = bits[i] if i < len(bits) else 0
        remainder ^= (bit << (CRC_WIDTH - 1))
        if remainder & CRC_TOPBIT:
            remainder = ((remainder << 1) ^ CRC_POLY) & CRC_MASK
        else:
            remainder = (remainder << 1) & CRC_MASK
    return remainder


def crc14_bits(payload77: list) -> list:
    assert len(payload77) == 77
    checksum = compute_crc14(payload77, 82)  # crc.c:55-57 -- 77 + 5 zero bits
    return [(checksum >> k) & 1 for k in range(CRC_WIDTH - 1, -1, -1)]


def encode174_bits(payload77: list) -> list:
    """payload77 (77 message bits) -> 174-bit systematic codeword (91 = payload
    + CRC, then 83 LDPC parity bits), encode.c:22-63's method, generator matrix
    from constants.c:29-30 (see module docstring)."""
    assert len(payload77) == 77
    a91 = list(payload77) + crc14_bits(payload77)
    gen = _generator()
    codeword = list(a91)
    for i in range(FTX_LDPC_M):
        row = gen[i]
        nsum = 0
        for j in range(FTX_LDPC_K):
            nsum ^= (a91[j] & row[j])
        codeword.append(nsum)
    assert len(codeword) == FTX_LDPC_N
    return codeword


def codeword174_to_tones(codeword174: list) -> list:
    """Inverse of ExtractLLRs.true_codeword: 174 codeword bits (58*3, MSB-first
    per 3-bit group) -> 79 tones (Costas sync inserted, data forward-gray-mapped).
    """
    assert len(codeword174) == FTX_LDPC_N
    data_tones = []
    for k in range(0, FTX_LDPC_N, 3):
        b3 = (codeword174[k] << 2) | (codeword174[k + 1] << 1) | codeword174[k + 2]
        data_tones.append(GRAY_MAP[b3])
    tones = [0] * 79
    di = 0
    costas = [3, 1, 4, 0, 6, 5, 2]
    for i in range(79):
        if any(lo <= i < hi for lo, hi in SYNC_RANGES):
            lo0 = next(lo for lo, hi in SYNC_RANGES if lo <= i < hi)
            tones[i] = costas[i - lo0]
        else:
            tones[i] = data_tones[di]
            di += 1
    return tones


def rr73_alt_payload77(payload77_std: list, onair_igrid4: int) -> list:
    """Replace the standard RR73 payload's (ir, igrid4) field (bits [58,74),
    pack77_fields.py's own convention) with (0, onair_igrid4), keeping i3/call1/
    call2 untouched."""
    assert len(payload77_std) == 77
    out = list(payload77_std)
    out[58] = 0  # ir
    for k in range(15):
        out[59 + k] = (onair_igrid4 >> (14 - k)) & 1
    return out


def validate_against_dll(dec, messages: list) -> dict:
    """Cross-check: for each message, MY encode174_bits(payload77) must equal
    dec.true_codeword(message) bit-for-bit. payload77 here comes from the SAME
    dec.true_codeword (bits[:77]) -- this validates the CRC+LDPC construction,
    not the payload extraction (already trusted, reused elsewhere in this repo)."""
    n_ok = 0
    n_total = 0
    for msg in messages:
        truth = dec.true_codeword(msg)
        if truth is None:
            continue
        n_total += 1
        mine = encode174_bits(truth[:77])
        if mine == truth:
            n_ok += 1
    return {"n_total": n_total, "n_ok": n_ok, "pass": bool(n_total > 0 and n_ok == n_total)}
