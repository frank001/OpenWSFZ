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
    .venv/Scripts/python gen_decoder_fixtures.py --snr-db 6.0 --output-dir /tmp/fx

Re-run after changing the message sets below, then rebuild the test project.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from synth import channel, encoder, wavio  # noqa: E402

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

# Default output directory — same path the hardcoded version used.
_DEFAULT_FIXTURES_DIR = str(
    _HERE.parent.parent / "tests" / "OpenWSFZ.Ft8.Tests" / "Fixtures"
)


def _render_fixture(
    messages: list[tuple[str, float]],
    seed: int,
    snr_db: float,
    dt_s: float,
    sample_rate_hz: int,
) -> np.ndarray:
    """Sum clean GFSK renders of each message, then add one AWGN realisation."""
    composite: np.ndarray | None = None
    for text, base_hz in messages:
        clean = encoder.encode_message(
            text,
            base_freq_hz=base_hz,
            dt_s=dt_s,
            snr_db=None,  # add noise once, over the composite
            sample_rate_hz=sample_rate_hz,
        )
        composite = clean if composite is None else composite + clean
    assert composite is not None
    return channel.add_noise(composite, snr_db, seed, sample_rate_hz)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic FT8 WAV fixtures for RealSignalFixtureTests"
    )
    parser.add_argument(
        "--snr-db", type=float, default=15.0,
        help="In-band SNR for the composite fixture (dB). Default: 15.0",
    )
    parser.add_argument(
        "--seed", type=int, default=20260606,
        help="Base RNG seed; each fixture uses seed+i. Default: 20260606",
    )
    parser.add_argument(
        "--dt", type=float, default=0.2,
        help="Time offset applied to each signal render (s). Default: 0.2",
    )
    parser.add_argument(
        "--sample-rate", type=int, default=12000,
        help="Sample rate (Hz). Default: 12000 (required by ft8_lib / WavReader)",
    )
    parser.add_argument(
        "--output-dir", default=_DEFAULT_FIXTURES_DIR,
        help=(
            "Directory to write WAV and .expected.txt files. "
            f"Default: {_DEFAULT_FIXTURES_DIR}"
        ),
    )
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Writing fixtures to {output_dir}")

    for i, (fixture_id, messages) in enumerate(_FIXTURES.items()):
        samples = _render_fixture(
            messages,
            seed=args.seed + i,
            snr_db=args.snr_db,
            dt_s=args.dt,
            sample_rate_hz=args.sample_rate,
        )
        wav_path = output_dir / f"{fixture_id}.wav"
        exp_path = output_dir / f"{fixture_id}.expected.txt"
        wavio.write_wav(str(wav_path), samples, sample_rate_hz=args.sample_rate)

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
