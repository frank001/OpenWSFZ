#!/usr/bin/env python3
"""Standalone one-shot FT8 WAV synthesiser.

Encodes a single FT8 message to a WAV file using the clean-room synth.* package.
Useful for ad-hoc perceptual checks (waterfall inspection, decoder smoke-tests,
S8-preview regeneration) without having to run a full R&R scenario.

Usage (from qa/rr-study/):
    .venv/Scripts/python synth_wav.py "CQ Q1ABC FN42"
    .venv/Scripts/python synth_wav.py "CQ Q1ABC FN42" --snr -5 --cutoff 3000
    .venv/Scripts/python synth_wav.py "CQ Q1ABC FN42" --snr none --out clean.wav
    .venv/Scripts/python synth_wav.py "Q1ABC Q9XYZ -10" --freq 1200 --dt 0.5
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from synth import channel, encoder, wavio  # noqa: E402


# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------

def _snr_type(value: str) -> "float | None":
    """Parse --snr: float dB value, or 'none'/'clean' for a noise-free render."""
    if value.lower() in ("none", "clean"):
        return None
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--snr: expected a number (dB) or 'none'/'clean', got '{value}'"
        )


def _default_output_name(message: str) -> str:
    """Derive a safe WAV filename from the message text.

    Rules: lowercase, spaces to underscores, strip non-alphanumeric (keep
    underscores), truncate to 40 characters, append .wav.

    Example: "CQ Q1ABC FN42" -> "cq_q1abc_fn42.wav"
    """
    name = message.lower().replace(" ", "_")
    name = re.sub(r"[^\w]", "", name)   # strip everything except [a-z0-9_]
    name = name[:40]
    return name + ".wav"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encode a single FT8 message to a WAV file"
    )
    parser.add_argument(
        "message",
        metavar="MESSAGE",
        help="FT8 message text to encode (e.g. 'CQ Q1ABC FN42')",
    )
    parser.add_argument(
        "--freq", type=float, default=1500.0,
        metavar="HZ",
        help="Base audio frequency (Hz). Default: 1500.0",
    )
    parser.add_argument(
        "--snr", type=_snr_type, default=0.0,
        metavar="DB",
        help=(
            "In-band SNR in dB (2500 Hz reference), or 'none'/'clean' for a "
            "noise-free render. Default: 0.0"
        ),
    )
    parser.add_argument(
        "--dt", type=float, default=0.0,
        metavar="S",
        help="Time offset applied to the signal start (s). Default: 0.0",
    )
    parser.add_argument(
        "--seed", type=int, default=0,
        help="RNG seed for the noise realisation. Default: 0",
    )
    parser.add_argument(
        "--rate", type=int, default=48000,
        metavar="HZ",
        help="Sample rate (Hz). Default: 48000",
    )
    parser.add_argument(
        "--cutoff", type=float, default=None,
        metavar="HZ",
        help=(
            "Noise lowpass cutoff (Hz). If omitted, noise is wideband. "
            "Ignored when --snr is 'none'/'clean'."
        ),
    )
    parser.add_argument(
        "--out", default=None,
        metavar="PATH",
        help=(
            "Output WAV path. Default: derived from MESSAGE text "
            "(e.g. 'CQ Q1ABC FN42' -> cq_q1abc_fn42.wav in cwd)"
        ),
    )
    args = parser.parse_args()

    # Resolve output path
    out_path = pathlib.Path(args.out) if args.out else pathlib.Path(_default_output_name(args.message))

    # Encode
    clean = None
    try:
        clean = encoder.encode_message(
            args.message,
            base_freq_hz=args.freq,
            dt_s=args.dt,
            snr_db=None,        # always encode clean; noise added below
            sample_rate_hz=args.rate,
        )
    except Exception as exc:
        sys.exit(f"ERROR: could not encode message '{args.message}': {exc}")

    # Add noise (unless clean render requested)
    snr_db: "float | None" = args.snr
    if snr_db is None:
        samples = clean
        snr_label = "clean"
    else:
        samples = channel.add_noise(
            clean,
            snr_db=snr_db,
            seed=args.seed,
            sample_rate_hz=args.rate,
            noise_cutoff_hz=args.cutoff,
        )
        snr_label = f"SNR={snr_db:+.1f} dB"
        if args.cutoff is not None:
            snr_label += f", cutoff={args.cutoff:.0f} Hz"

    # Write
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wavio.write_wav(str(out_path), samples, sample_rate_hz=args.rate)

    print(f"Wrote {out_path} ({len(samples)} samples @ {args.rate} Hz, {snr_label})")


if __name__ == "__main__":
    main()
