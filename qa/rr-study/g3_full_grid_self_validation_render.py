#!/usr/bin/env python3
"""G3 self-validation gate -- render clean (+10 dB) WAVs across the FULL DT grid.

Route B build spec (2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md)
§2 G3 / §8 step 3: "WSJT-X must decode a clean (+10 dB) rendering at every dt_s in the
grid, including the negative ones... If WSJT-X cannot decode an early-rendered signal,
the render is wrong until proven otherwise."

Generalises gate_render.py's established pattern (same +10 dB / 12 kHz / seed=0
conventions, same "QA loads each WAV into WSJT-X via File > Open" manual confirmation
step -- WSJT-X GUI use is not something this harness automates; see gate_render.py's own
docstring) from "one WAV per study message" to "one WAV per (scenario, part) across S3's
positive grid and S3b's negative grid", using extended=True so every part -- including S3
parts 8/9 and every S3b part -- renders at its exact labelled dt_s rather than raising.

Writing the WHOLE extended buffer (not just the nominal 15 s window) is deliberate: for a
negative dt_s the signal sits before local index 0 of the nominal window, and WSJT-X's
File > Open decodes whatever is in the file -- it does not need the file to start exactly
at a slot boundary. This is a file-based check (no live device, no VB-CABLE/Voicemeeter
routing), consistent with HK-026: a failure here is the synth's problem, not evidence
about the decoder's live-capture time response.

Usage (from qa/rr-study/):
    python g3_full_grid_self_validation_render.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from synth import encoder, wavio  # noqa: E402  (after sys.path insert)

# Same gate conditions as gate_render.py's §5 gate, extended to the full DT grid.
_GATE_SNR_DB:         float = 10.0
_GATE_SEED:           int   = 0
_GATE_SAMPLE_RATE_HZ: int   = 12000   # WSJT-X File > Open handles 48 kHz too, but this
                                       # matches gate_render.py's existing jt9-compatible
                                       # convention for continuity across both gates.

_SCENARIO_FILES = {
    "S3":  "s3-dt-offset.json",
    "S3b": "s3b-dt-boundary.json",
}


def _load_msg01_text() -> str:
    data = json.loads((_HERE / "scenarios" / "study-messages.json").read_text(encoding="utf-8"))
    for m in data.get("messages", []):
        if m["id"] == "MSG-01":
            return m["text"]
    sys.exit("ERROR: MSG-01 not found in study-messages.json")


def render_full_grid_wavs(out_dir: pathlib.Path) -> list[tuple[pathlib.Path, str, str, float]]:
    """Render one +10 dB WAV per (scenario, part) across S3 + S3b.

    Returns a list of (path, scenario_id, expected_text, label_dt_s).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    text = _load_msg01_text()

    results: list[tuple[pathlib.Path, str, str, float]] = []
    for scenario_id, filename in _SCENARIO_FILES.items():
        scenario = json.loads((_HERE / "scenarios" / filename).read_text(encoding="utf-8"))
        base_freq_hz = float(scenario["fixed"]["base_freq_hz"])
        for part in scenario["parts"]:
            dt_s = float(part["dt_s"])
            out_path = out_dir / f"{scenario_id}_part{part['part_index']}_dt{dt_s:+.1f}.wav"
            print(f"  {scenario_id} part {part['part_index']:>2}  dt_s={dt_s:+.1f}", end="  ... ",
                  flush=True)
            buffer, buffer_start_s = encoder.encode_message(
                text,
                base_freq_hz=base_freq_hz,
                dt_s=dt_s,
                snr_db=_GATE_SNR_DB,
                seed=_GATE_SEED,
                sample_rate_hz=_GATE_SAMPLE_RATE_HZ,
                extended=True,
            )
            wavio.write_wav(str(out_path), buffer, sample_rate_hz=_GATE_SAMPLE_RATE_HZ)
            results.append((out_path, scenario_id, text, dt_s))
            print(f"-> {out_path.name}  (buffer_start_s={buffer_start_s:+.4f}, "
                  f"{len(buffer)/_GATE_SAMPLE_RATE_HZ:.2f}s)")

    return results


def _print_instructions(rendered: list[tuple[pathlib.Path, str, str, float]]) -> None:
    sep = "-" * 78
    print()
    print(f"Rendered {len(rendered)} WAV(s) ({sum(1 for r in rendered if r[1] == 'S3')} S3 + "
          f"{sum(1 for r in rendered if r[1] == 'S3b')} S3b).")
    print()
    print(sep)
    print("WSJT-X DECODE PROCEDURE (G3, extended to the full DT grid)")
    print(sep)
    print("1. Open WSJT-X. Set mode to FT8.")
    print("2. For each WAV below:")
    print("     File > Open  ->  select the .wav file")
    print("     Observe the Band Activity panel -- the decoded line should appear.")
    print("3. Confirm decoded TEXT matches the expected text.")
    print("   (SNR and DT reported by WSJT-X will differ from injected values for the")
    print("    early/late parts by construction -- only TEXT correctness is required.)")
    print()
    print(f"  {'WAV filename':<38}  {'label dt_s':>10}  Expected text")
    print(f"  {'-' * 38}  {'-' * 10}  {'-' * 25}")
    for path, _scenario_id, text, dt_s in rendered:
        print(f"  {path.name:<38}  {dt_s:>+10.1f}  \"{text}\"")
    print()
    print("Gate PASS : every WAV decodes with correct text -> extended-range synth is sound.")
    print("Gate FAIL : any WAV absent or text wrong at dt_s=X -> report which dt_s, do NOT")
    print("            proceed to a live S3b run until resolved (G3, spec sec.2).")
    print(sep)
    print()
    print("NOT AUTOMATED: this script renders the WAVs only. WSJT-X GUI confirmation is a")
    print("manual step -- same convention as gate_render.py's original sec.5 gate.")
    print(sep)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="g3_full_grid_wav", metavar="DIR",
                     help="output directory for WAV files (default: g3_full_grid_wav)")
    args = ap.parse_args()

    out_dir = _HERE / args.out
    print()
    print("G3 self-validation gate -- full DT grid (S3 + S3b)")
    print(f"  SNR = +{_GATE_SNR_DB:.0f} dB  |  seed = {_GATE_SEED}  |  "
          f"fs = {_GATE_SAMPLE_RATE_HZ} Hz (jt9/WSJT-X File>Open compatible)")
    print(f"  output = {out_dir}")
    print()

    rendered = render_full_grid_wavs(out_dir)
    _print_instructions(rendered)


if __name__ == "__main__":
    main()
