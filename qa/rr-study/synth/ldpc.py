"""L8 — LDPC(174,91) parity.  *** NOT YET IMPLEMENTED ***

The second protocol-exact milestone (see BUILD-PLAN.md L8). FT8 protects the 91-bit
(message + CRC) word with a systematic LDPC(174,91) code, appending 83 parity bits to
form the 174-bit codeword that the modulator transmits.

Implementing it requires the published FT8 parity structure:
  * the 83-row generator (the systematic parity-generation table), and
  * the parity-check matrix H, used by the self-check H . c = 0.

Both are large fixed tables transcribed from the public FT8 specification (clean-room:
transcribed from the protocol description, not copied from ft8_lib source).

Validation when implemented: every generated codeword satisfies H . c = 0, and the
§5 gate (WSJT-X decodes our render) confirms end-to-end correctness.
"""
from __future__ import annotations

from .constants import CODEWORD_BITS, MESSAGE_PLUS_CRC_BITS


def encode_ldpc(message_plus_crc: list[int]) -> list[int]:
    """Return the 174-bit systematic codeword. Not yet implemented."""
    if len(message_plus_crc) != MESSAGE_PLUS_CRC_BITS:
        raise ValueError(
            f"expected {MESSAGE_PLUS_CRC_BITS} message+CRC bits, got {len(message_plus_crc)}"
        )
    raise NotImplementedError(
        "L8 LDPC parity is a pending milestone — see synth/BUILD-PLAN.md."
    )


def parity_check(codeword: list[int]) -> bool:
    """Return True iff H . c = 0 over GF(2). Not yet implemented."""
    if len(codeword) != CODEWORD_BITS:
        raise ValueError(f"expected {CODEWORD_BITS} codeword bits, got {len(codeword)}")
    raise NotImplementedError("L8 parity-check matrix not yet transcribed.")
