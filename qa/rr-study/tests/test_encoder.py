"""L9 integration — message_to_tones end-to-end test.

Verifies the full pipeline: pack_message (L7) → append_crc (L2) → encode_ldpc (L8)
→ assemble_symbols (L3) is wired correctly and produces a well-formed 79-tone vector.

Definition of Done criterion 3 (DEV-BRIEFING-L7-L8.md §6):
  encoder.message_to_tones("CQ Q1ABC FN42") returns a 79-tone vector whose
  Costas arrays sit correctly at symbol indices 0..6, 36..42, and 72..78.
"""
import pytest

from synth import encoder
from synth.constants import (
    COSTAS_ARRAY,
    COSTAS_START_INDICES,
    NUM_SYMBOLS,
    NUM_TONES,
)


class TestMessageToTonesIntegration:
    MESSAGE = "CQ Q1ABC FN42"

    def test_returns_79_tones(self):
        tones = encoder.message_to_tones(self.MESSAGE)
        assert len(tones) == NUM_SYMBOLS  # 79

    def test_all_tones_in_range(self):
        tones = encoder.message_to_tones(self.MESSAGE)
        assert all(0 <= t < NUM_TONES for t in tones)

    def test_costas_at_index_0(self):
        tones = encoder.message_to_tones(self.MESSAGE)
        assert tones[0:7] == list(COSTAS_ARRAY), (
            f"Costas mismatch at index 0: got {tones[0:7]}"
        )

    def test_costas_at_index_36(self):
        tones = encoder.message_to_tones(self.MESSAGE)
        assert tones[36:43] == list(COSTAS_ARRAY), (
            f"Costas mismatch at index 36: got {tones[36:43]}"
        )

    def test_costas_at_index_72(self):
        tones = encoder.message_to_tones(self.MESSAGE)
        assert tones[72:79] == list(COSTAS_ARRAY), (
            f"Costas mismatch at index 72: got {tones[72:79]}"
        )

    def test_all_three_costas_positions(self):
        """Single combined assertion matching the DoD criterion exactly."""
        tones = encoder.message_to_tones(self.MESSAGE)
        assert len(tones) == 79
        for start in COSTAS_START_INDICES:
            assert tones[start:start + 7] == list(COSTAS_ARRAY), (
                f"Costas mismatch at start index {start}"
            )

    def test_deterministic(self):
        assert encoder.message_to_tones(self.MESSAGE) == encoder.message_to_tones(self.MESSAGE)

    def test_different_messages_give_different_tones(self):
        tones1 = encoder.message_to_tones("CQ Q1ABC FN42")
        tones2 = encoder.message_to_tones("Q1ABC Q9XYZ EN37")
        # Data symbols will differ (the Costas symbols will be the same)
        assert tones1 != tones2

    @pytest.mark.parametrize("message", [
        "CQ Q1ABC FN42",
        "Q1ABC Q9XYZ EN37",
        "Q9XYZ Q1ABC -10",
        "Q1ABC Q9XYZ RRR",
        "Q1ABC Q9XYZ 73",
    ])
    def test_various_messages_produce_valid_tone_vectors(self, message):
        tones = encoder.message_to_tones(message)
        assert len(tones) == 79
        assert all(0 <= t < 8 for t in tones)
        for start in COSTAS_START_INDICES:
            assert tones[start:start + 7] == list(COSTAS_ARRAY)
