"""L9 — End-to-end message -> tones -> audio.

Wires the pipeline together: pack (L7) -> +CRC (L2) -> LDPC (L8) -> symbols (L3)
-> modulate (L4).  All layers are implemented; `encode_message` and `message_to_tones`
are fully operational.  The §5 WSJT-X self-validation gate is pending QA execution.
"""
from __future__ import annotations

import numpy as np

from . import crc, ldpc, modulator, packing, symbols
from .constants import DEFAULT_SAMPLE_RATE_HZ


def message_to_tones(text: str) -> list[int]:
    """Full clean-room encode: text -> 79 transmitted tones."""
    message_bits = packing.pack_message(text)          # L7
    message_plus_crc = crc.append_crc(message_bits)    # L2
    codeword = ldpc.encode_ldpc(message_plus_crc)      # L8
    return symbols.assemble_symbols(codeword)          # L3


def message_to_tones_type4(callsign: str) -> list[int]:
    """Type-4 "CQ <nonstandard callsign>" encode: callsign -> 79 transmitted tones.

    rr-synth-nonstandard-callsign-packing: parallels `message_to_tones` but
    packs via `packing.pack_type4_announce` (i3=4) instead of the standard
    Type-1 packer — everything downstream (CRC/LDPC/symbol assembly) is
    identical and message-type-agnostic.
    """
    message_bits = packing.pack_type4_announce(callsign)   # L7 (Type 4)
    message_plus_crc = crc.append_crc(message_bits)        # L2
    codeword = ldpc.encode_ldpc(message_plus_crc)          # L8
    return symbols.assemble_symbols(codeword)               # L3


def render_tones(
    tones: list[int],
    base_freq_hz: float,
    dt_s: float = 0.0,
    snr_db: float | None = None,
    seed: int = 0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """Modulate an explicit 79-tone vector (and optionally add seeded noise).

    Independent of the packing/LDPC layers — the DSP spine can be driven directly
    with a known tone vector, then reused unchanged by `encode_message`.
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
    """text -> rendered audio (all layers L2–L8 are implemented and operational)."""
    return render_tones(message_to_tones(text), base_freq_hz, dt_s, snr_db, seed, sample_rate_hz)


def encode_message_type4(
    callsign: str,
    base_freq_hz: float,
    dt_s: float = 0.0,
    snr_db: float | None = None,
    seed: int = 0,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """callsign -> rendered audio for a Type-4 "CQ <callsign>" announcement.

    rr-synth-nonstandard-callsign-packing: parallels `encode_message`, using
    `message_to_tones_type4` instead of the standard-message packer.
    """
    return render_tones(message_to_tones_type4(callsign), base_freq_hz, dt_s, snr_db, seed, sample_rate_hz)
