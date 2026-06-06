#!/usr/bin/env python3
"""§5 self-validation gate — render clean WAVs for every study message.

Renders a clean +10 dB WAV for every message defined in
scenarios/study-messages.json and writes them to gate_wav/.  QA then
loads each WAV into WSJT-X (File > Open) and confirms every message
decodes with correct text.

If WSJT-X cannot decode any rendered WAV the synthesiser has an encoding
defect and the study cannot proceed (STUDY-SPEC §5, BUILD-PLAN item 3).

Usage (from qa/rr-study/):
    python gate_render.py [--out <dir>]

Options:
    --out DIR   Output directory for WAV files (default: gate_wav)

Gate conditions (fixed — do not change without updating the §5 protocol):
    base_freq_hz = 1500   Centre of the FT8 passband; easy for any decoder.
    dt_s         =   0.2  Standard timing offset used throughout S1–S3.
    snr_db       = +10.0  Clean signal; 13+ dB above the nominal decode floor.
    seed         =    0   Reproducible noise realisation (negligible at +10 dB).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# Ensure the synth package is importable when run from this directory.
_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from synth import encoder, wavio  # noqa: E402  (after sys.path insert)

# ---------------------------------------------------------------------------
# Gate conditions (STUDY-SPEC §5)
# ---------------------------------------------------------------------------
_GATE_BASE_FREQ_HZ:  float = 1500.0
_GATE_DT_S:          float = 0.2
_GATE_SNR_DB:        float = 10.0
_GATE_SEED:          int   = 0
# jt9.exe (WSJT-X command-line decoder) processes audio at 12 000 Hz internally
# and cannot resample a 48 kHz WAV.  The gate therefore renders at 12 kHz so
# that jt9 can validate the encoded output directly.  The study itself renders
# at 48 kHz (DEFAULT_SAMPLE_RATE_HZ) for playback through VB-CABLE; WSJT-X's
# live capture path handles 48 kHz -> 12 kHz resampling internally.
_GATE_SAMPLE_RATE_HZ: int  = 12000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    """Filename-safe lowercase slug derived from the message text."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text.strip()).strip("_").lower()


def _load_manifest(manifest_path: pathlib.Path) -> list[dict]:
    with manifest_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError(f"manifest at {manifest_path} has no 'messages' list")
    return messages


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_gate_wavs(
    manifest_path: pathlib.Path,
    out_dir: pathlib.Path,
) -> list[tuple[pathlib.Path, str]]:
    """Render one WAV per study message; return list of (path, expected_text)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    messages = _load_manifest(manifest_path)

    results: list[tuple[pathlib.Path, str]] = []
    for msg in messages:
        msg_id = msg["id"]
        text   = msg["text"]
        out_path = out_dir / f"{msg_id}_{_slug(text)}.wav"

        print(f"  {msg_id}  '{text}'", end="  … ", flush=True)
        samples = encoder.encode_message(
            text,
            base_freq_hz    = _GATE_BASE_FREQ_HZ,
            dt_s            = _GATE_DT_S,
            snr_db          = _GATE_SNR_DB,
            seed            = _GATE_SEED,
            sample_rate_hz  = _GATE_SAMPLE_RATE_HZ,
        )
        wavio.write_wav(str(out_path), samples, sample_rate_hz=_GATE_SAMPLE_RATE_HZ)
        results.append((out_path, text))
        print(f"-> {out_path.name}")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--out",
        default="gate_wav",
        metavar="DIR",
        help="output directory for WAV files (default: gate_wav)",
    )
    args = ap.parse_args()

    manifest_path = _HERE / "scenarios" / "study-messages.json"
    out_dir       = _HERE / args.out

    if not manifest_path.exists():
        sys.exit(f"ERROR: manifest not found: {manifest_path}")

    print()
    print("§5 self-validation gate")
    print(f"  base_freq = {_GATE_BASE_FREQ_HZ} Hz  |  "
          f"dt = {_GATE_DT_S} s  |  "
          f"SNR = +{_GATE_SNR_DB:.0f} dB  |  "
          f"seed = {_GATE_SEED}  |  "
          f"fs = {_GATE_SAMPLE_RATE_HZ} Hz (jt9 compatible)")
    print(f"  manifest  = {manifest_path}")
    print(f"  output    = {out_dir}")
    print()

    rendered = render_gate_wavs(manifest_path, out_dir)

    _print_instructions(rendered)


def _print_instructions(rendered: list[tuple[pathlib.Path, str]]) -> None:
    sep = "-" * 70
    print()
    print(f"Rendered {len(rendered)} WAV(s).")
    print()
    print(sep)
    print("WSJT-X DECODE PROCEDURE  (§5 gate)")
    print(sep)
    print("1. Open WSJT-X.  Set mode to FT8.")
    print("2. For each WAV below:")
    print("     File > Open  ->  select the .wav file")
    print("     Observe the Band Activity panel — the decoded line should appear.")
    print("3. Confirm decoded TEXT matches the expected text.")
    print("   (SNR and DT reported by WSJT-X will differ from injected values;")
    print("    that is normal.  Only TEXT correctness is required for the gate.)")
    print()
    print(f"  {'WAV filename':<45}  Expected text")
    print(f"  {'-' * 45}  {'-' * 25}")
    for path, text in rendered:
        print(f"  {path.name:<45}  \"{text}\"")
    print()
    print("Gate PASS : all messages decoded with correct text -> synthesiser done.")
    print("Gate FAIL : any message absent or text wrong -> encoding defect;")
    print("            file a defect against the Developer before proceeding.")
    print(sep)
    print()


if __name__ == "__main__":
    main()
