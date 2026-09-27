#!/usr/bin/env python3
"""GAP-LOCATE Amendment 3: standard-layout (i3 in {1,2}) 77-bit field boundaries.

NOT a new instrument -- a pure-Python mirror of the EXISTING vendored bit layout, read
directly from `native/ft8_lib_vendor/ft8/message.c` (no layout invented here), cited by
line. This is the same class of reuse as `extract_llrs_ctypes.ExtractLLRs.true_codeword`'s
own gray-code mirror elsewhere in this codebase (HK-018) -- a field-BOUNDARY comparator,
never a text decoder: it never calls `unpack28`/`unpackgrid`/hash-table lookups and never
produces callsign or grid text. Inputs and outputs are 77-element 0/1 lists (MSB-first,
matching `ldpc_decode_ctypes.a91_to_bits`'s own convention) and field-name strings only.

Layout, standard message (i3 in {1,2}), `ftx_message_encode_std` (message.c:156-208) /
`ftx_message_decode_std` (message.c:354-397):
  - message.c:196 payload[0]=n29a>>21 ... message.c:199 (n29a's low 3 bits spill into
    payload[3]) -- n29a is 29 bits: `call_to`'s pack28 (28 bits) + ipa suffix flag (1 bit),
    message.c:183. Field "call1" = bits [0, 29).
  - message.c:199 (payload[3] low nibble) .. message.c:202 -- n29b, 29 bits: `call_de`'s
    pack28 (28 bits) + ipb suffix flag (1 bit), message.c:184. Field "call2" = bits [29, 58).
  - message.c:203 top bits, decode side message.c:370-373 -- ir (1 bit) + igrid4 (15 bits),
    together the report-or-grid field, message.c:179/205 (packgrid). Field
    "report_or_grid" = bits [58, 74).
  - message.c:205 low bits, decode side message.c:376 -- i3, 3 bits. Field "flags" (the
    message-type indicator itself) = bits [74, 77).
"""
from __future__ import annotations

from collections import namedtuple

STD_FIELDS = [
    ("call1", 0, 29),
    ("call2", 29, 58),
    ("report_or_grid", 58, 74),
    ("flags", 74, 77),
]

MAXGRID4 = 32400  # message.c:11, #define MAXGRID4 ((uint16_t)32400ul)

StdFields = namedtuple("StdFields", ["i3", "call1", "call2", "ir", "igrid4"])


def std_fields(bits77: list) -> "StdFields":
    """Splits a 77-bit payload (MSB-first) into i3/call1/call2/(ir,igrid4), mirroring
    ftx_message_decode_std's own extraction (message.c:361-376) bit-for-bit: call1
    [0,29) (28-bit pack28 + suffix flag), call2 [29,58) (same), ir = bit 58 (the top bit
    of the combined 16-bit report/grid field, message.c:370), igrid4 = bits [59,74) as
    an unsigned int, MSB-first (message.c:371-373), i3 = bits [74,77) (message.c:376).
    Tuple fields (call1/call2) are kept as bit-tuples for exact equality, not decoded."""
    assert len(bits77) == 77
    ig = 0
    for b in bits77[59:74]:
        ig = (ig << 1) | b
    return StdFields(
        i3=i3_of(bits77),
        call1=tuple(bits77[0:29]),
        call2=tuple(bits77[29:58]),
        ir=bits77[58],
        igrid4=ig,
    )


def i3_of(bits77: list) -> int:
    """The 3-bit message-type field, message.c:376 -- well-defined for ANY 77-bit
    payload regardless of its own layout (i3 is always the last 3 bits)."""
    b = bits77[74:77]
    return (b[0] << 2) | (b[1] << 1) | b[2]


def std_field_diff(x77: list, y77: list) -> set:
    """Returns the set of STD_FIELDS names where x77 and y77 differ. Only meaningful
    when both messages use the standard (i3 in {1,2}) layout -- callers must check
    i3_of(x77) in (1, 2) themselves before trusting this as a semantic field diff
    (the bit ranges are still computed unconditionally; this function does not
    itself decide layout applicability, per Amendment 3's own predicate order)."""
    assert len(x77) == 77 and len(y77) == 77
    diffs = set()
    for name, lo, hi in STD_FIELDS:
        if x77[lo:hi] != y77[lo:hi]:
            diffs.add(name)
    return diffs
