"""L8 — LDPC(174,91) encoding and parity-check tests.

Verifies encode_ldpc and parity_check against the acceptance criteria in the
QA briefing (DEV-BRIEFING-L7-L8.md §4.2):

  1. encode_ldpc returns exactly 174 bits; first 91 equal the input (systematic).
  2. Self-consistency: parity_check(encode_ldpc(x)) is True for 1000 random 91-bit x.
     This is the decisive internal check — if the generator and H disagree it fails here.
  3. Error detection: flipping any single bit of a valid codeword causes parity_check=False.
  4. Both functions reject wrong-length inputs.
"""
import random

import pytest

from synth import ldpc
from synth.constants import CODEWORD_BITS, MESSAGE_PLUS_CRC_BITS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_bits(n: int, rng: random.Random) -> list[int]:
    return [rng.randint(0, 1) for _ in range(n)]


# ---------------------------------------------------------------------------
# 1. Width and systematic property
# ---------------------------------------------------------------------------

class TestWidth:
    def test_encode_ldpc_returns_174_bits(self):
        info = [0] * MESSAGE_PLUS_CRC_BITS
        cw = ldpc.encode_ldpc(info)
        assert len(cw) == CODEWORD_BITS

    def test_all_values_are_zero_or_one(self):
        info = [1, 0] * 45 + [1]   # 91 bits
        cw = ldpc.encode_ldpc(info)
        assert all(b in (0, 1) for b in cw)

    def test_systematic_first_91_unchanged(self):
        """The first 91 bits of the codeword must be the verbatim info bits."""
        info = [1, 0, 1, 1, 0] * 18 + [1]   # 91 bits
        cw = ldpc.encode_ldpc(info)
        assert cw[:MESSAGE_PLUS_CRC_BITS] == info, (
            "Systematic property violated: codeword[0..90] ≠ info bits"
        )

    def test_parity_portion_is_83_bits(self):
        info = [0] * MESSAGE_PLUS_CRC_BITS
        cw = ldpc.encode_ldpc(info)
        assert len(cw[MESSAGE_PLUS_CRC_BITS:]) == 83


# ---------------------------------------------------------------------------
# 2. Self-consistency (generator ↔ H matrix agreement)
# ---------------------------------------------------------------------------
# This is the decisive internal check: if the transcribed generator and the
# transcribed parity-check matrix are inconsistent, this test will catch it.
# 1000 random 91-bit words is more than enough coverage given the code structure.

class TestSelfConsistency:
    """LOUD failure: if this fails, the generator and H disagree — re-check transcription."""

    SEED = 42
    N_TRIALS = 1000

    def test_parity_check_passes_for_1000_random_words(self):
        rng = random.Random(self.SEED)
        failures = []
        for i in range(self.N_TRIALS):
            info = _random_bits(MESSAGE_PLUS_CRC_BITS, rng)
            cw = ldpc.encode_ldpc(info)
            if not ldpc.parity_check(cw):
                failures.append(i)
        assert not failures, (
            f"parity_check returned False for {len(failures)}/{self.N_TRIALS} "
            f"encoded codewords (first failures at trial indices {failures[:5]}). "
            f"The LDPC generator and parity-check matrix are INCONSISTENT — "
            f"re-check the transcription of _LDPC_GENERATOR and _LDPC_Nm."
        )

    def test_all_zeros_info_passes_parity(self):
        """Zero info word → parity bits should all be 0 → trivially valid codeword."""
        info = [0] * MESSAGE_PLUS_CRC_BITS
        cw = ldpc.encode_ldpc(info)
        assert ldpc.parity_check(cw)
        assert all(b == 0 for b in cw), "All-zero info should give all-zero codeword"

    def test_all_ones_info_is_consistent(self):
        info = [1] * MESSAGE_PLUS_CRC_BITS
        cw = ldpc.encode_ldpc(info)
        assert ldpc.parity_check(cw)


# ---------------------------------------------------------------------------
# 3. Error detection
# ---------------------------------------------------------------------------

class TestErrorDetection:
    """Flipping any single bit of a valid codeword must make parity_check return False."""

    SEED = 7
    N_SAMPLES = 20   # test 20 different base codewords × all 174 bit flips each

    def test_single_bit_flip_detected(self):
        rng = random.Random(self.SEED)
        for _ in range(self.N_SAMPLES):
            info = _random_bits(MESSAGE_PLUS_CRC_BITS, rng)
            cw = ldpc.encode_ldpc(info)
            assert ldpc.parity_check(cw), "Precondition: cw must be a valid codeword"
            for pos in range(CODEWORD_BITS):
                corrupted = list(cw)
                corrupted[pos] ^= 1   # flip one bit
                assert not ldpc.parity_check(corrupted), (
                    f"Flipping bit {pos} of a valid codeword was not detected"
                )

    def test_all_174_bit_positions_detectable_for_fixed_codeword(self):
        """Exhaustive single-bit flip test on a specific codeword."""
        info = [1, 0] * 45 + [1]   # 91 deterministic bits
        cw = ldpc.encode_ldpc(info)
        assert ldpc.parity_check(cw)
        for pos in range(CODEWORD_BITS):
            corrupted = list(cw)
            corrupted[pos] ^= 1
            assert not ldpc.parity_check(corrupted), (
                f"Bit flip at position {pos} not detected"
            )


# ---------------------------------------------------------------------------
# 4. Wrong-length inputs raise ValueError
# ---------------------------------------------------------------------------

class TestLengthValidation:
    def test_encode_wrong_length_raises(self):
        with pytest.raises(ValueError):
            ldpc.encode_ldpc([0] * 90)

    def test_encode_too_long_raises(self):
        with pytest.raises(ValueError):
            ldpc.encode_ldpc([0] * 92)

    def test_parity_check_wrong_length_raises(self):
        with pytest.raises(ValueError):
            ldpc.parity_check([0] * 173)

    def test_parity_check_too_long_raises(self):
        with pytest.raises(ValueError):
            ldpc.parity_check([0] * 175)

    def test_encode_empty_raises(self):
        with pytest.raises(ValueError):
            ldpc.encode_ldpc([])

    def test_parity_check_empty_raises(self):
        with pytest.raises(ValueError):
            ldpc.parity_check([])


# ---------------------------------------------------------------------------
# 5. Integration smoke-test: encode_ldpc feeds correctly into parity_check
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_packing_crc_ldpc_pipeline(self):
        """Smoke-test the three-layer pipeline: message → CRC → LDPC → parity OK."""
        from synth import crc, packing

        msg_bits = packing.pack_message("CQ Q1ABC FN42")
        info91 = crc.append_crc(msg_bits)
        assert len(info91) == MESSAGE_PLUS_CRC_BITS

        cw = ldpc.encode_ldpc(info91)
        assert len(cw) == CODEWORD_BITS
        assert ldpc.parity_check(cw), (
            "CQ Q1ABC FN42 pipeline: parity_check failed on encoded codeword"
        )
