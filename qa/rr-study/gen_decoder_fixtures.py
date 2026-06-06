#!/usr/bin/env python3
"""Generate the C# decoder's G6 gate fixtures from SYNTHETIC FT8 audio.

These fixtures replace the former real off-air WSJT-X "Save All" recordings,
which embedded the callsigns of real, non-consenting third-party operators
(a privacy / GDPR concern — a callsign + grid identifies a natural person).

Every signal here uses only the canonical *fictional* example callsigns from
the FT8 protocol literature and WSJT-X documentation:

    Q1AW   — ARRL HQ club / the conventional example & beacon callsign
    Q1ABC  — Franke/Taylor QEX 2020 example callsign
    Q9XYZ  — Franke/Taylor QEX 2020 example callsign

No real individual's callsign is used. The audio is produced by the clean-room
qa/rr-study synthesiser (GFSK, continuous phase) at 12 kHz mono int16 — the
exact format tests/OpenWSFZ.Ft8.Tests/WavReader.cs accepts. ft8_lib decodes
these signals; RealSignalFixtureTests asserts the answer-key subset is
recovered (G6 gate, NFR-016).

This is the inverse instrument of the product decoder, not a replacement for it
(see MEMORY.md "ft8_lib dependency"): it tests that ft8_lib recovers known good
encodings. It is NOT an independent off-air oracle — that property was traded
away deliberately to remove third-party PII.

Usage (from qa/rr-study/):
    .venv/Scripts/python gen_decoder_fixtures.py

Re-run after changing the message sets below, then rebuild the test project.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from synth import channel, encoder, wavio  # noqa: E402

# ── Fixture render parameters ────────────────────────────────────────────────
# 12 kHz so jt9/ft8_lib can decode directly (see gate_render.py rationale).
_SAMPLE_RATE_HZ = 12_000
_DT_S = 0.2
# Generous composite SNR — these are a regression gate, not a weak-signal study.
_SNR_DB = 15.0
_SEED = 20260606

# Each fixture is a co-channel slot: several fictional QSO fragments at distinct
# audio frequencies, summed and then immersed in one AWGN realisation.
_FIXTURES: dict[str, list[tuple[str, float]]] = {
    "synth-qso-01": [
        ("CQ Q1ABC FN42", 700.0),
        ("Q1ABC Q9XYZ -10", 1300.0),
        ("Q9XYZ Q1ABC R-08", 1900.0),
    ],
    "synth-qso-02": [
        ("CQ Q9XYZ EN37", 800.0),
        ("Q9XYZ Q1AW 73", 1400.0),
        ("Q1AW Q9XYZ RR73", 2000.0),
    ],
    "synth-qso-03": [
        ("CQ Q1AW FN31", 650.0),
        ("Q1AW Q1ABC +05", 1250.0),
        ("Q1ABC Q1AW RR73", 1850.0),
    ],
}

_FIXTURES_DIR = (
    _HERE.parent.parent / "tests" / "OpenWSFZ.Ft8.Tests" / "Fixtures"
)


def _render_fixture(messages: list[tuple[str, float]], seed: int) -> np.ndarray:
    """Sum clean GFSK renders of each message, then add one AWGN realisation."""
    composite: np.ndarray | None = None
    for text, base_hz in messages:
        clean = encoder.encode_message(
            text,
            base_freq_hz=base_hz,
            dt_s=_DT_S,
            snr_db=None,  # add noise once, over the composite
            sample_rate_hz=_SAMPLE_RATE_HZ,
        )
        composite = clean if composite is None else composite + clean
    assert composite is not None
    return channel.add_noise(composite, _SNR_DB, seed, _SAMPLE_RATE_HZ)


def main() -> None:
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing fixtures to {_FIXTURES_DIR}")
    for i, (fixture_id, messages) in enumerate(_FIXTURES.items()):
        samples = _render_fixture(messages, _SEED + i)
        wav_path = _FIXTURES_DIR / f"{fixture_id}.wav"
        exp_path = _FIXTURES_DIR / f"{fixture_id}.expected.txt"
        wavio.write_wav(str(wav_path), samples, sample_rate_hz=_SAMPLE_RATE_HZ)

        lines = [
            f"# Answer-key subset for {fixture_id}",
            "# SYNTHETIC FT8 fixture (qa/rr-study/gen_decoder_fixtures.py).",
            "# Fictional example callsigns only (Q1AW / Q1ABC / Q9XYZ) — no real",
            "# third-party operators. Regenerate with the generator, not by hand.",
        ]
        lines += [text for text, _ in messages]
        exp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(f"  {fixture_id}: {wav_path.name} ({wav_path.stat().st_size:,} bytes)"
              f"  + {len(messages)} expected messages")
    print("Done. Rebuild OpenWSFZ.Ft8.Tests and run RealSignalFixtureTests.")


if __name__ == "__main__":
    main()
