"""L7 — Standard-message text -> 77-bit payload.  *** NOT YET IMPLEMENTED ***

This is one of the two protocol-exact, table-heavy milestones (see BUILD-PLAN.md L7).
Implementing it requires the public FT8 message-packing rules:

  * Standard message (i3=1): two 28-bit callsign fields + 1 R bit + 1 grid/report
    field (15 bits) + 3-bit message type (i3) — total 77 bits.
  * 28-bit callsign packing over the FT8 character alphabets (with the special
    suffix/prefix and hashed-callsign cases out of scope for the study's fixed corpus).
  * 15-bit Maidenhead grid / signal-report packing.

The study's scenarios (STUDY-SPEC §6) use a small, fixed set of standard messages, so a
constrained packer covering Type-1 standard messages is sufficient for the first study.

Validation when implemented: encode a published worked example and confirm the 77-bit
vector bit-for-bit; ultimately the §5 gate (WSJT-X decodes our render) is the arbiter.
"""
from __future__ import annotations

from .constants import MESSAGE_BITS


def pack_message(text: str) -> list[int]:
    """Pack a standard FT8 message into 77 bits (MSB first). Not yet implemented."""
    raise NotImplementedError(
        "L7 message packing is the next milestone — see synth/BUILD-PLAN.md. "
        "Until it lands, the synthesiser cannot emit a WSJT-X-decodable codeword."
    )


def _assert_width(bits: list[int]) -> list[int]:
    if len(bits) != MESSAGE_BITS:
        raise ValueError(f"packed message must be {MESSAGE_BITS} bits, got {len(bits)}")
    return bits
