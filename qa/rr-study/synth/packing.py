"""L7 — Standard-message text -> 77-bit payload.

Derived from the published FT8 protocol description:
  Franke, Somerville & Taylor, "The FT4 and FT8 Communication Protocols,"
  QEX July/August 2020.

The character alphabets, special-token numeric values, and grid/report encoding
are transcribed from the public reference programs in ft4_ft8_public/ (part of
the WSJT-X project, distributed alongside the protocol description), specifically:
  std_call_to_c28.f90 — standard callsign packing algorithm and character alphabets
  grid4_to_g15.f90    — grid/report field encoding rules and special-token values
and from the published constants in ft8_lib/ft8/message.c (pack28, packgrid,
unpack28, unpackgrid).  No algorithmic code has been copied; only published field
definitions and offset constants are transcribed here.

Only Type-1 standard messages (i3 = 1) are supported.  Out of scope for the
first R&R study: non-standard / hashed callsigns, /P suffix, compound prefixes
beyond the single rover /R bit, free-text (i3=0), telemetry, EU-VHF (i3=2), and
contest types.  Inputs that require unsupported forms raise ValueError.
"""
from __future__ import annotations

from .constants import MESSAGE_BITS

# ---------------------------------------------------------------------------
# Published protocol constants
# ---------------------------------------------------------------------------
# Source: std_call_to_c28.f90 (parameter NTOKENS, MAX22) and message.c
# (defines NTOKENS = 2063592, MAX22 = 4194304, MAXGRID4 = 32400).

NTOKENS   = 2_063_592   # first value reserved above special-token range
MAX22     = 4_194_304   # 2^22 — size of 22-bit hashed-callsign range
MAXGRID4  = 32_400      # 18 * 18 * 100; grid values occupy [0, MAXGRID4 - 1]

# Special n28 codes (source: message.c unpack28 / pack28)
_N28_DE          = 0
_N28_QRZ         = 1
_N28_CQ          = 2
_N28_CQ_NNN_BASE = 3     # CQ 000 = 3, CQ 001 = 4, ..., CQ 999 = 1002

# Special g15 codes for the third message field (source: grid4_to_g15.f90 irpt values
# and message.c packgrid).  All relative to MAXGRID4:
#   irpt = 1 → blank/empty  (MAXGRID4 + 1 = 32401)
#   irpt = 2 → "RRR"        (MAXGRID4 + 2 = 32402)
#   irpt = 3 → "RR73"       (MAXGRID4 + 3 = 32403)
#   irpt = 4 → "73"         (MAXGRID4 + 4 = 32404)
#   irpt = 35 + dB          (e.g. +05 → irpt=40 → g15=32440)
_G15_BLANK       = MAXGRID4 + 1
_G15_RRR         = MAXGRID4 + 2
_G15_RR73        = MAXGRID4 + 3
_G15_73          = MAXGRID4 + 4
_G15_REPORT_BIAS = 35    # offset: irpt = _G15_REPORT_BIAS + report_dB

# ---------------------------------------------------------------------------
# Character alphabets  (source: std_call_to_c28.f90 a1/a2/a3/a4 declarations
# and ft8_lib/ft8/text.h FT8_CHAR_TABLE_* comments)
# ---------------------------------------------------------------------------
# Position 0 of the 6-char callsign field: space + digits + letters (37 chars)
_CHAR0 = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"   # FT8_CHAR_TABLE_ALPHANUM_SPACE

# Position 1: digits + letters (36 chars)
_CHAR1 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"    # FT8_CHAR_TABLE_ALPHANUM

# Position 2: digits only (10 chars)
_CHAR2 = "0123456789"                               # FT8_CHAR_TABLE_NUMERIC

# Positions 3–5: space FIRST, then letters (27 chars) — space is index 0
_CHAR3 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"              # FT8_CHAR_TABLE_LETTERS_SPACE


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _int_to_bits(n: int, width: int) -> list[int]:
    """Integer n → bit list of given width, MSB first."""
    return [(n >> (width - 1 - i)) & 1 for i in range(width)]


def _assert_width(bits: list[int]) -> list[int]:
    if len(bits) != MESSAGE_BITS:
        raise ValueError(f"packed message must be {MESSAGE_BITS} bits, got {len(bits)}")
    return bits


def _normalize_to_c6(call: str) -> str:
    """Place a callsign in a 6-character buffer per the FT8 standard.

    Replicates the normalisation logic from pack_basecall (ft8_lib/ft8/message.c):
      - If the digit is at position 2 (AB0XYZ form, length ≤ 6): left-align in c6.
      - If the digit is at position 1 (A0XYZ form, length ≤ 5): prepend one space.
    In both cases trailing positions are filled with space (the neutral char in _CHAR3).

    Source: ft8_lib/ft8/message.c, pack_basecall().
    """
    c6 = list("      ")   # 6 spaces — trailing space is valid in _CHAR3
    if len(call) >= 3 and call[2].isdigit() and len(call) <= 6:
        # AB0XYZ form: digit at position 2
        for i, ch in enumerate(call):
            c6[i] = ch
    elif len(call) >= 2 and call[1].isdigit() and len(call) <= 5:
        # A0XYZ form: digit at position 1 — pad one space on the left
        for i, ch in enumerate(call):
            c6[i + 1] = ch
    else:
        raise ValueError(
            f"Cannot normalise callsign {call!r}: digit must be at index 1 (length ≤ 5) "
            f"or index 2 (length ≤ 6)."
        )
    return "".join(c6)


def _pack_basecall(c6: str) -> int:
    """Mixed-radix encode a 6-character normalised callsign → integer n.

    Formula (source: std_call_to_c28.f90, mixed-radix expansion):
      n = ((((i0 * 36 + i1) * 10 + i2) * 27 + i3) * 27 + i4) * 27 + i5
    where i0 ∈ [0, 36], i1 ∈ [0, 35], i2 ∈ [0, 9], i3–i5 ∈ [0, 26].
    """
    try:
        i0 = _CHAR0.index(c6[0])
        i1 = _CHAR1.index(c6[1])
        i2 = _CHAR2.index(c6[2])
        i3 = _CHAR3.index(c6[3])
        i4 = _CHAR3.index(c6[4])
        i5 = _CHAR3.index(c6[5])
    except ValueError as exc:
        raise ValueError(
            f"Invalid character in normalised callsign {c6!r}: {exc}"
        ) from exc

    n = i0
    n = n * 36 + i1
    n = n * 10 + i2
    n = n * 27 + i3
    n = n * 27 + i4
    n = n * 27 + i5
    return n


def _pack_callsign(call: str) -> tuple[int, int]:
    """Pack a callsign string into (n28, ipa).

    n28: 28-bit value.
         0 = DE, 1 = QRZ, 2 = CQ, 3–1002 = CQ NNN,
         NTOKENS+MAX22 … 2^28-1 = standard callsigns.
    ipa: 1 if the callsign carried a /R or /P suffix, else 0.
         (This bit occupies the rover / suffix flag slot in the 77-bit word.)

    Source: ft8_lib/ft8/message.c pack28().
    Raises ValueError for malformed or unsupported callsigns.
    """
    call = call.strip().upper()
    ipa = 0

    # /R or /P suffix → set ipa and strip for the base-call encoding
    if call.endswith("/R") or call.endswith("/P"):
        ipa = 1
        call = call[:-2]

    # Special tokens (source: message.c pack28 conditional chain)
    if call == "DE":
        return _N28_DE, ipa
    if call == "QRZ":
        return _N28_QRZ, ipa
    if call == "CQ":
        return _N28_CQ, ipa

    # Directed CQ: "CQ NNN" (three-digit numeric, 000–999)
    # (source: message.c pack28 CQ_nnn branch; nnn = n28 - 3)
    if call.startswith("CQ ") and len(call) == 6:
        suffix = call[3:]
        if suffix.isdigit() and len(suffix) == 3:
            nnn = int(suffix)
            if 0 <= nnn <= 999:
                return _N28_CQ_NNN_BASE + nnn, ipa

    # Non-standard / hashed callsigns are out of scope for the R&R study.
    # Standard callsign — normalise to 6 chars and mixed-radix-encode.
    c6 = _normalize_to_c6(call)
    n_base = _pack_basecall(c6)
    n28 = NTOKENS + MAX22 + n_base
    if n28 > (1 << 28) - 1:
        raise ValueError(f"n28={n28} overflows 28 bits for callsign {call!r}")
    return n28, ipa


def _parse_dd(s: str) -> int:
    """Parse a signed decimal string like '+05', '-10', '+5' → int."""
    s = s.strip()
    if s.startswith("+"):
        return int(s[1:])
    if s.startswith("-"):
        return -int(s[1:])
    return int(s)


def _pack_grid_field(field: str) -> tuple[int, int]:
    """Encode the third message field → (ir, igrid4).

    ir:     R-acknowledgement bit (1 for 'R-prefixed' reports, 0 otherwise).
    igrid4: 15-bit grid/report/special-token value.

    Source: grid4_to_g15.f90 (ft4_ft8_public) and message.c packgrid().
    """
    f = field.strip().upper()

    # Empty field
    if not f:
        return 0, _G15_BLANK

    # Special string tokens (source: grid4_to_g15.f90 explicit irpt assignments)
    if f == "RRR":
        return 0, _G15_RRR
    if f == "RR73":
        return 0, _G15_RR73
    if f == "73":
        return 0, _G15_73

    # Standard 4-character Maidenhead grid "XXYY" where XX ∈ A–R, YY ∈ 00–99
    # (source: grid4_to_g15.f90 is_grid4 predicate and encoding formula)
    if (len(f) == 4
            and "A" <= f[0] <= "R"
            and "A" <= f[1] <= "R"
            and f[2].isdigit()
            and f[3].isdigit()):
        igrid4 = (
            (ord(f[0]) - ord("A")) * 18 * 100
            + (ord(f[1]) - ord("A")) * 100
            + (ord(f[2]) - ord("0")) * 10
            + (ord(f[3]) - ord("0"))
        )
        return 0, igrid4

    # R-prefixed report: R+dd or R-dd (source: grid4_to_g15.f90 c1='+'|'-' with R)
    if len(f) >= 2 and f[0] == "R" and f[1] in "+-":
        dd = _parse_dd(f[1:])
        irpt = _G15_REPORT_BIAS + dd
        if not (0 <= MAXGRID4 + irpt < (1 << 15)):
            raise ValueError(f"R-prefixed report {field!r} out of 15-bit range")
        return 1, MAXGRID4 + irpt

    # Plain numeric report: +dd or -dd (source: grid4_to_g15.f90)
    if f and f[0] in "+-":
        dd = _parse_dd(f)
        irpt = _G15_REPORT_BIAS + dd
        if not (0 <= MAXGRID4 + irpt < (1 << 15)):
            raise ValueError(f"Report {field!r} out of 15-bit range")
        return 0, MAXGRID4 + irpt

    raise ValueError(
        f"Cannot encode third field {field!r}: not a valid Maidenhead grid, "
        f"numeric report (±dd / R±dd), RRR, RR73, or 73."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pack_message(text: str) -> list[int]:
    """Pack a standard FT8 message into 77 bits (MSB first).

    Supported message forms (Type-1, i3 = 1):
        CQ <call> <grid>
        <call1> <call2> <grid>       grid: 4-char Maidenhead, e.g. FN42
        <call1> <call2> <report>     report: ±dd, R±dd, RRR, RR73, or 73

    77-bit layout (MSB → LSB, source: Franke/Somerville/Taylor QEX 2020 Table II;
    ft4_ft8_public/std_call_to_c28.f90; message.c ftx_message_encode_std):
        n28a  (28 bits) — callsign 1
        ipa   ( 1 bit ) — rover / /R flag for callsign 1
        n28b  (28 bits) — callsign 2
        ipb   ( 1 bit ) — rover / /R flag for callsign 2
        ir    ( 1 bit ) — R-acknowledgement bit (1 for R-prefixed reports)
        igrid4(15 bits) — grid locator or report/special-token value
        i3    ( 3 bits) — message type = 1

    Returns a list of exactly 77 ints, each ∈ {0, 1}, MSB first.

    Raises ValueError for unsupported or malformed input.
    Raises NotImplementedError for forms explicitly out of scope (e.g. hashed calls).
    """
    parts = text.strip().upper().split()
    if len(parts) != 3:
        raise ValueError(
            f"Standard FT8 message must have exactly 3 space-separated fields; "
            f"got {len(parts)}: {text!r}"
        )

    call1_str, call2_str, field3 = parts

    n28a, ipa = _pack_callsign(call1_str)
    n28b, ipb = _pack_callsign(call2_str)
    ir, igrid4 = _pack_grid_field(field3)

    i3 = 1   # Standard message type (source: message.c encode_std, always 1)

    bits: list[int] = (
        _int_to_bits(n28a, 28) + [ipa]
        + _int_to_bits(n28b, 28) + [ipb]
        + [ir]
        + _int_to_bits(igrid4, 15)
        + _int_to_bits(i3, 3)
    )
    return _assert_width(bits)
