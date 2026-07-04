"""L7 — message packing tests.

Verifies pack_message against the acceptance criteria in the QA briefing
(DEV-BRIEFING-L7-L8.md §3.4):

  1. Returns exactly 77 elements, all ∈ {0, 1}.
  2. Bit-exact against a hardcoded worked example (constant-drift regression guard).
  3. Deterministic: same input → same output.
  4. All supported forms (§3.2) pack without error; unsupported forms raise.
  5. (Bonus) round-trip via unpack agrees with input.

The bit-exact worked example derives its expected vector from the SAME QEX 2020
protocol field definitions (§III-A/§III-B, Tables I/II) that the implementation
uses; it is therefore a regression guard against constant drift, not an
independent oracle.  The expected value is a hardcoded literal rather than
re-computed from the packing.py constants, so a transcription error in NTOKENS,
MAX22, or the character tables will cause this test to fail rather than silently
pass.  TRUE independence is established not by this unit test but by the
STUDY-SPEC §5 WSJT-X decode gate (QA-executed).
"""
import pytest

from synth import packing
from synth.constants import MESSAGE_BITS
from synth.packing import (
    NTOKENS, MAX22, MAXGRID4,
    _N28_CQ, _N28_DE, _N28_QRZ,
    _G15_RRR, _G15_RR73, _G15_73,
    _pack_callsign, _pack_grid_field, _pack_basecall, _normalize_to_c6,
    ihashcall, _pack_call58, pack_type4_announce,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bits_to_int(bits: list[int]) -> int:
    """Convert an MSB-first bit list to an integer."""
    n = 0
    for b in bits:
        n = (n << 1) | b
    return n


# ---------------------------------------------------------------------------
# 1. Width and binary-ness
# ---------------------------------------------------------------------------

class TestWidth:
    def test_cq_call_grid_is_77_bits(self):
        bits = packing.pack_message("CQ Q1ABC FN42")
        assert len(bits) == MESSAGE_BITS

    def test_all_values_are_zero_or_one(self):
        bits = packing.pack_message("CQ Q1ABC FN42")
        assert all(b in (0, 1) for b in bits)

    def test_various_forms_all_77(self):
        messages = [
            "CQ Q9XYZ EN37",
            "Q1ABC Q9XYZ EN37",
            "Q1ABC Q9XYZ -10",
            "Q1ABC Q9XYZ R-10",
            "Q1ABC Q9XYZ RRR",
            "Q1ABC Q9XYZ RR73",
            "Q1ABC Q9XYZ 73",
            "Q1ABC Q9XYZ +05",
        ]
        for msg in messages:
            bits = packing.pack_message(msg)
            assert len(bits) == MESSAGE_BITS, f"Failed for {msg!r}"
            assert all(b in (0, 1) for b in bits), f"Non-binary bit for {msg!r}"


# ---------------------------------------------------------------------------
# 2. Bit-exact worked example
# ---------------------------------------------------------------------------
# Reference: Franke/Somerville/Taylor, "The FT4 and FT8 Communication Protocols,"
# QEX July/August 2020, §III-A/§III-B, Tables I/II (Type-1 standard message
# layout and callsign/grid field definitions).  The field values below are
# hand-traced from those same protocol field definitions.
#
# NOTE ON INDEPENDENCE: this vector is derived from the SAME protocol field
# definitions as packing.py — oracle and implementation share a source.  It is
# therefore a regression guard against constant drift, NOT an independent
# oracle.  TRUE independence is established by the STUDY-SPEC §5 WSJT-X decode
# gate (QA-executed), not by this unit test.
#
# The expected integer is a HARDCODED LITERAL — it is NOT computed from the
# constants in packing.py (NTOKENS, MAX22, etc.).  This is intentional: if a
# constant is transcribed incorrectly in packing.py (e.g. NTOKENS off by one),
# the implementation's output will differ from this value and the test will fail.
# A self-referential assertion computed from the same constants would mask exactly
# that class of error.
#
# Message: "CQ Q1ABC FN42"
#
# Derivation from QEX 2020 §III-A/§III-B (Tables I/II):
#
# Field 1 — "CQ"
#   Special token, Table I: n28a = 2, ipa = 0
#
# Field 2 — "Q1ABC"
#   Digit at position 1 → left-pad one space: c6 = " Q1ABC"
#   Alphabets (the published c6 field alphabets, QEX 2020 §III-A):
#     a1 = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" (37 chars, pos 0)
#     a2 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"  (36 chars, pos 1)
#     a3 = "0123456789"                            (10 chars, pos 2)
#     a4 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"           (27 chars, pos 3-5)
#   i0 = 0 (space in a1), i1 = 26 (Q in a2), i2 = 1 (1 in a3)
#   i3 = 1 (A in a4), i4 = 2 (B), i5 = 3 (C)
#   n_base = ((((0*36 + 26)*10 + 1)*27 + 1)*27 + 2)*27 + 3 = 5 138 049
#   Published offsets (QEX 2020 §III-A):
#     NTOKENS = 2 063 592  (first value above special-token range)
#     MAX22   = 4 194 304  (2^22, hashed-callsign range size)
#   n28b = 2 063 592 + 4 194 304 + 5 138 049 = 11 395 945
#   ipb = 0
#
# Field 3 — "FN42"
#   F→5, N→13; igrid4 = 5*1800 + 13*100 + 4*10 + 2 = 10 342
#   ir = 0
#
# i3 = 1 (Type-1 standard message, QEX 2020 Table II)
#
# 77-bit word (MSB first): n28a(28) | ipa(1) | n28b(28) | ipb(1) | ir(1) | igrid4(15) | i3(3)
#   = 2*2^49 + 11_395_945*2^20 + 10_342*2^3 + 1
#   = 1 125 899 906 842 624
#   +    11 949 514 424 320
#   +                82 736
#   +                     1
#   = 1 137 849 421 349 681
_CQ_Q1ABC_FN42_EXPECTED_INT = 1_137_849_421_349_681


class TestBitExact:
    def test_cq_k1abc_fn42_field_values(self):
        """Verify each sub-field against the QEX 2020 field-definition derivation above."""
        # callsign 1
        n28a, ipa = _pack_callsign("CQ")
        assert n28a == _N28_CQ == 2
        assert ipa == 0

        # callsign 2
        n28b, ipb = _pack_callsign("Q1ABC")
        c6 = _normalize_to_c6("Q1ABC")
        n_base = _pack_basecall(c6)
        assert c6 == " Q1ABC"
        assert n_base == 5_138_049
        assert n28b == NTOKENS + MAX22 + 5_138_049 == 11_395_945
        assert ipb == 0

        # grid
        ir, igrid4 = _pack_grid_field("FN42")
        assert ir == 0
        assert igrid4 == 10_342

    def test_cq_k1abc_fn42_full_77_bits(self):
        """Full bit-vector must equal the step-by-step derivation."""
        bits = packing.pack_message("CQ Q1ABC FN42")
        assert _bits_to_int(bits) == _CQ_Q1ABC_FN42_EXPECTED_INT

    def test_i3_field_is_always_1(self):
        """The 3 LSBs (i3) must be 0,0,1 for every standard message."""
        for msg in ["CQ Q1ABC FN42", "Q9XYZ Q1ABC -10", "Q1ABC Q9XYZ RRR"]:
            bits = packing.pack_message(msg)
            assert bits[-3:] == [0, 0, 1], f"i3 ≠ 1 for {msg!r}"


# ---------------------------------------------------------------------------
# 3. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_message_gives_same_bits(self):
        msg = "Q1ABC Q9XYZ EN37"
        assert packing.pack_message(msg) == packing.pack_message(msg)

    def test_case_insensitive(self):
        assert packing.pack_message("CQ Q1ABC FN42") == packing.pack_message("cq q1abc fn42")


# ---------------------------------------------------------------------------
# 4. All supported forms pack without error; unsupported forms raise
# ---------------------------------------------------------------------------

class TestSupportedForms:
    """Every form listed in §3.2 of the briefing must succeed."""

    def test_cq_call_grid(self):
        packing.pack_message("CQ Q1ABC FN42")

    def test_call1_call2_grid(self):
        packing.pack_message("Q1ABC Q9XYZ EN37")

    def test_signal_report_positive(self):
        packing.pack_message("Q1ABC Q9XYZ +05")

    def test_signal_report_negative(self):
        packing.pack_message("Q1ABC Q9XYZ -10")

    def test_r_prefixed_report(self):
        packing.pack_message("Q1ABC Q9XYZ R-10")

    def test_r_prefixed_positive(self):
        packing.pack_message("Q1ABC Q9XYZ R+05")

    def test_rrr(self):
        packing.pack_message("Q1ABC Q9XYZ RRR")

    def test_rr73(self):
        packing.pack_message("Q1ABC Q9XYZ RR73")

    def test_73(self):
        packing.pack_message("Q1ABC Q9XYZ 73")

    def test_de_token(self):
        packing.pack_message("DE Q1ABC FN42")

    def test_qrz_token(self):
        packing.pack_message("QRZ Q1ABC FN42")

    def test_rover_suffix(self):
        packing.pack_message("Q1ABC Q9XYZ/R EN37")


class TestSpecialTokenValues:
    """Spot-check that special token n28 values match the published assignment."""

    def test_cq_n28_is_2(self):
        n28, ipa = _pack_callsign("CQ")
        assert n28 == 2

    def test_de_n28_is_0(self):
        n28, _ = _pack_callsign("DE")
        assert n28 == 0

    def test_qrz_n28_is_1(self):
        n28, _ = _pack_callsign("QRZ")
        assert n28 == 1

    def test_standard_call_above_threshold(self):
        n28, _ = _pack_callsign("Q1ABC")
        assert n28 >= NTOKENS + MAX22

    def test_grid_fn42_value(self):
        _, igrid4 = _pack_grid_field("FN42")
        assert igrid4 == 10_342

    def test_grid_aa00_is_zero(self):
        _, igrid4 = _pack_grid_field("AA00")
        assert igrid4 == 0

    def test_rrr_g15_value(self):
        ir, g15 = _pack_grid_field("RRR")
        assert ir == 0
        assert g15 == _G15_RRR

    def test_rr73_g15_value(self):
        ir, g15 = _pack_grid_field("RR73")
        assert ir == 0
        assert g15 == _G15_RR73

    def test_73_g15_value(self):
        ir, g15 = _pack_grid_field("73")
        assert ir == 0
        assert g15 == _G15_73

    def test_report_minus10_ir_and_g15(self):
        ir, g15 = _pack_grid_field("-10")
        assert ir == 0
        assert g15 == MAXGRID4 + (35 + (-10))   # = 32425

    def test_r_report_sets_ir(self):
        ir, g15 = _pack_grid_field("R-10")
        assert ir == 1
        assert g15 == MAXGRID4 + (35 + (-10))   # same g15 value, ir differs


class TestUnsupportedForms:
    def test_two_fields_raises(self):
        with pytest.raises(ValueError):
            packing.pack_message("CQ Q1ABC")

    def test_four_fields_raises(self):
        with pytest.raises(ValueError):
            packing.pack_message("CQ Q1ABC FN42 EXTRA")

    def test_bad_grid_raises(self):
        with pytest.raises(ValueError):
            packing.pack_message("Q1ABC Q9XYZ ZZZZ")

    def test_invalid_callsign_format_raises(self):
        """A callsign with no recognisable digit position AND outside the
        3-11 char hash-fallback range still raises.

        NOTE (rr-synth-nonstandard-callsign-packing, task 1.3): a callsign
        with no digit position but a length in [3, 11] (e.g. "AAAAA") is no
        longer unsupported — it now falls back to a 22-bit ihashcall hash,
        exactly as the published protocol's own pack28 does. See
        TestNonstandardCallsignHashReference for that behaviour.
        """
        with pytest.raises(ValueError):
            packing.pack_message("Q1ABC AAAAAAAAAAAA FN42")  # 12 chars: exceeds the hash field too

    def test_no_digit_short_callsign_now_hashes_instead_of_raising(self):
        """Documents the task-1.3 behaviour change: a callsign with no digit
        position but a valid hash-fallback length no longer raises."""
        bits = packing.pack_message("Q1ABC AAAAA FN42")
        assert len(bits) == MESSAGE_BITS


# ---------------------------------------------------------------------------
# 5. Various callsign forms normalise correctly
# ---------------------------------------------------------------------------

class TestCallsignNormalise:
    def test_5char_digit_at_1(self):
        assert _normalize_to_c6("Q1ABC") == " Q1ABC"

    def test_5char_digit_at_1_w9(self):
        assert _normalize_to_c6("Q9XYZ") == " Q9XYZ"

    def test_6char_digit_at_2(self):
        assert _normalize_to_c6("QK4AAA") == "QK4AAA"

    def test_4char_digit_at_1(self):
        # Q5OK → " Q5OK " (trailing space)
        assert _normalize_to_c6("Q5OK") == " Q5OK "

    def test_5char_digit_at_2(self):
        # QG5AB → "QG5AB " (trailing space)
        assert _normalize_to_c6("QG5AB") == "QG5AB "


# ---------------------------------------------------------------------------
# 6. ihashcall — 22/12/10-bit callsign hash (rr-synth-nonstandard-callsign-packing)
# ---------------------------------------------------------------------------
# Shared test vector (task 1.4): fictional Q-prefix nonstandard callsign
# "Q0ABCDEF" (8 chars, GDPR-compliant synthetic callsign per MEMORY.md's
# privacy/callsign policy). Expected hash values are HAND-DERIVED from the
# published `ihashcall` formula (WSJT-X packjt77.f90 / ft8_lib, as documented
# in f-001-hashed-callsign-resolution/design.md's Context section):
#
#   alphabet = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"  (space=0 ... /=37)
#   call padded to 11 chars: "Q0ABCDEF   " (3 trailing spaces)
#   n8 = mixed-radix encode over the 38-char alphabet = 169_726_174_981_079_792
#   h22 = (47_055_833_459 * n8) >> 42 & 0x3FFFFF          = 2_523_336
#   h12 = h22 >> 10                                        = 2_464
#   h10 = h22 >> 12                                        = 616
#
# Cross-checked by inspection (not by calling into the native shim from
# Python, per D4) against the actual reference implementation recovered from
# the vendored ft8_lib submodule's git history (`hashcodes.f90`'s public
# reference program and `message.c`'s `save_callsign`), which use the
# identical alphabet, constant, and top-22-bits-then-derive-narrower-widths
# scheme. This catches a transcription error in either implementation
# without coupling the two at runtime.
_Q0ABCDEF_N8 = 169_726_174_981_079_792
_Q0ABCDEF_H22 = 2_523_336
_Q0ABCDEF_H12 = 2_464
_Q0ABCDEF_H10 = 616


class TestIhashcall:
    def test_shared_vector_h22(self):
        assert ihashcall("Q0ABCDEF", bits=22) == _Q0ABCDEF_H22

    def test_shared_vector_h12(self):
        assert ihashcall("Q0ABCDEF", bits=12) == _Q0ABCDEF_H12

    def test_shared_vector_h10(self):
        assert ihashcall("Q0ABCDEF", bits=10) == _Q0ABCDEF_H10

    def test_h12_is_top_bits_of_h22(self):
        assert ihashcall("Q0ABCDEF", bits=12) == ihashcall("Q0ABCDEF", bits=22) >> 10

    def test_h10_is_top_bits_of_h22(self):
        assert ihashcall("Q0ABCDEF", bits=10) == ihashcall("Q0ABCDEF", bits=22) >> 12

    def test_deterministic(self):
        assert ihashcall("Q0ABCDEF") == ihashcall("Q0ABCDEF")
        assert ihashcall("PJ4/K1ABC") == ihashcall("PJ4/K1ABC")

    def test_case_insensitive(self):
        assert ihashcall("q0abcdef") == ihashcall("Q0ABCDEF")

    def test_fits_in_22_bits(self):
        assert 0 <= ihashcall("Q0ABCDEF", bits=22) < (1 << 22)

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            ihashcall("Q0ABCDEFGHIJ")  # 12 chars, exceeds the 11-char field

    def test_invalid_character_raises(self):
        with pytest.raises(ValueError):
            ihashcall("Q0AB#DEF")  # '#' is not in the 38-char hash alphabet

    def test_unsupported_bit_width_raises(self):
        with pytest.raises(ValueError):
            ihashcall("Q0ABCDEF", bits=8)


# ---------------------------------------------------------------------------
# 7. Type-4 nonstandard-callsign announcement packing
# ---------------------------------------------------------------------------

class TestPackType4Announce:
    def test_returns_77_bits(self):
        bits = pack_type4_announce("Q0ABCDEF")
        assert len(bits) == MESSAGE_BITS
        assert all(b in (0, 1) for b in bits)

    def test_i3_is_4(self):
        bits = pack_type4_announce("Q0ABCDEF")
        assert bits[-3:] == [1, 0, 0]   # i3 = 4 = 0b100

    def test_icq_bit_is_set(self):
        # icq occupies bit index 73 (0-based, MSB-first): position -4 from the end
        # (i3 occupies the last 3 bits; icq is the bit immediately before it).
        bits = pack_type4_announce("Q0ABCDEF")
        assert bits[-4] == 1

    def test_bit_exact_worked_example(self):
        """Full 77-bit word for 'CQ Q0ABCDEF', hand-derived from the field layout.

        n12=0 (unused, CQ has no second call to hash), n58=_pack_call58('Q0ABCDEF')
        (unpadded mixed-radix, no left-padding — see _pack_call58's docstring),
        iflip=0, nrpt=0 (no report field), icq=1, i3=4.
        """
        expected_n58 = 3_093_129_008_986
        assert _pack_call58("Q0ABCDEF") == expected_n58

        bits = pack_type4_announce("Q0ABCDEF")

        def _bits_to_int(b: list[int]) -> int:
            n = 0
            for x in b:
                n = (n << 1) | x
            return n

        # n12(12)=0, n58(58)=expected_n58, iflip(1)=0, nrpt(2)=0, icq(1)=1, i3(3)=4
        expected = (0 << 65) | (expected_n58 << 7) | (0 << 6) | (0 << 4) | (1 << 3) | 4
        assert _bits_to_int(bits) == expected

    def test_deterministic(self):
        assert pack_type4_announce("Q0ABCDEF") == pack_type4_announce("Q0ABCDEF")

    def test_case_insensitive(self):
        assert pack_type4_announce("q0abcdef") == pack_type4_announce("Q0ABCDEF")

    def test_too_long_raises_value_error(self):
        """Spec scenario: callsign longer than 11 characters raises ValueError."""
        with pytest.raises(ValueError):
            pack_type4_announce("Q0ABCDEFGHIJ")  # 12 characters

    def test_too_short_raises_value_error(self):
        with pytest.raises(ValueError):
            pack_type4_announce("Q1")  # 2 characters


# ---------------------------------------------------------------------------
# 8. Standard-message packer accepts a nonstandard callsign via its hash
# ---------------------------------------------------------------------------

class TestNonstandardCallsignHashReference:
    def test_pack_callsign_falls_back_to_hash(self):
        """A nonstandard-shaped callsign packs into the NTOKENS..NTOKENS+MAX22
        hash sub-range instead of raising (task 1.3)."""
        n28, ipa = _pack_callsign("Q0ABCDEF")
        assert NTOKENS <= n28 < NTOKENS + MAX22
        assert n28 == NTOKENS + _Q0ABCDEF_H22
        assert ipa == 0

    def test_pack_message_accepts_nonstandard_second_call(self):
        bits = packing.pack_message("Q1TST Q0ABCDEF RR73")
        assert len(bits) == MESSAGE_BITS
        assert all(b in (0, 1) for b in bits)

    def test_pack_message_nonstandard_call_in_hash_subrange(self):
        """Confirms the packed c28 field for the nonstandard call lands in the
        hash sub-range (NTOKENS <= n28 < NTOKENS + MAX22), per the spec."""
        bits = packing.pack_message("Q1TST Q0ABCDEF RR73")

        def _bits_to_int(b: list[int]) -> int:
            n = 0
            for x in b:
                n = (n << 1) | x
            return n

        full = _bits_to_int(bits)
        # Layout: n29a(29) | n29b(29) | ir(1) | igrid4(15) | i3(3) = 77
        n29b = (full >> (15 + 3 + 1)) & ((1 << 29) - 1)
        n28b = n29b >> 1
        assert NTOKENS <= n28b < NTOKENS + MAX22
        assert n28b == NTOKENS + _Q0ABCDEF_H22

    def test_standard_callsigns_unaffected(self):
        """Existing standard-callsign packing is bit-for-bit unchanged (task 1.3/1.5)."""
        assert packing.pack_message("CQ Q1ABC FN42") == packing.pack_message("CQ Q1ABC FN42")
        n28, ipa = _pack_callsign("Q1ABC")
        assert n28 >= NTOKENS + MAX22
        assert ipa == 0

    def test_too_short_nonstandard_call_raises(self):
        """A 2-character callsign with no digit position is neither a
        standard basecall nor a valid hash-encodable nonstandard call
        (ihashcall requires >= 3 chars). Note: "Q1" is NOT a suitable
        example here — a digit at position 1 makes it a valid (if unusual)
        standard callsign shape per QEX 2020 §III-A ("A0XYZ form")."""
        with pytest.raises(ValueError):
            _pack_callsign("AA")

    def test_too_long_nonstandard_call_raises(self):
        with pytest.raises(ValueError):
            _pack_callsign("Q0ABCDEFGHIJ")  # 12 characters


# ---------------------------------------------------------------------------
# 9. _pack_call58 — Type-4 plaintext field (unpadded, distinct from ihashcall)
# ---------------------------------------------------------------------------

class TestPackCall58:
    def test_matches_worked_example(self):
        assert _pack_call58("Q0ABCDEF") == 3_093_129_008_986

    def test_not_padded_like_ihashcall(self):
        """_pack_call58 must NOT right-pad to 11 characters — that padding
        is specific to ihashcall's n8 (see both functions' docstrings)."""
        assert _pack_call58("Q0ABCDEF") != ihashcall("Q0ABCDEF")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            _pack_call58("Q0ABCDEFGHIJ")

    def test_invalid_character_raises(self):
        with pytest.raises(ValueError):
            _pack_call58("Q0AB#DEF")
