"""L9 — End-to-end message -> tones -> audio.

Wires the pipeline together: pack (L7) -> +CRC (L2) -> LDPC (L8) -> symbols (L3)
-> modulate (L4). L7 and L8 are pending, so `encode_message` currently raises until
those milestones land; `render_tones` (everything downstream of the tones) already works
and is exercised by the tests.
"""
from __future__ import annotations

import numpy as np

from . import crc, ldpc, modulator, packing, symbols
from .constants import DEFAULT_SAMPLE_RATE_HZ


def message_to_tones(text: str) -> list[int]:
    """Full clean-room encode: text -> 79 transmitted tones. Blocked on L7/L8."""
    message_bits = packing.pack_message(text)          # L7 (pending)
    message_plus_crc = crc.append_crc(message_bits)    # L2
    codeword = ldpc.encode_ldpc(message_plus_crc)      # L8 (pending)
    return symbols.assemble_symbols(codeword)          # L3


def render_tones(
    tones: list[int],
    base_freq_hz: float,
    dt_s: float = 0.0,
    snr_db: float | None = None,
    seed: int = 0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """Modulate an explicit 79-tone vector (and optionally add seeded noise).

    Available now — independent of the pending packing/LDPC layers — so the DSP spine
    can be tested and, once L7/L8 land, reused unchanged by `encode_message`.
    """
    clean = modulator.modulate(tones, base_freq_hz, dt_s, sample_rate_hz)
    if snr_db is None:
        return clean
    from . import channel
    return channel.add_noise(clean, snr_db, seed, sample_rate_hz)


def encode_message(
    text: str,
    base_freq_hz: float,
    dt_s: float = 0.0,
    snr_db: float | None = None,
    seed: int = 0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """text -> rendered audio. Blocked on L7/L8 (raises NotImplementedError until then)."""
    return render_tones(message_to_tones(text), base_freq_hz, dt_s, snr_db, seed, sample_rate_hz)
