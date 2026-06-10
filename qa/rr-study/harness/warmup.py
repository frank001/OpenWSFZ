"""R&R study warm-up guard.

Plays one FT8 warm-up cycle via VB-CABLE so the operator can confirm that
BOTH WSJT-X and OpenWSFZ are in Monitor/decode mode and receiving audio
BEFORE the study run begins.  The cycle is NOT recorded in truth.csv; it
is a setup check only and has no effect on any measurement.

Called automatically by run_study.py.  Can also be run standalone:
    python harness/warmup.py [--device "CABLE Input"]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ── Package root ──────────────────────────────────────────────────────────────
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

# Import audio parameters from run_scenario so the warm-up cycle is
# acoustically identical to study audio.  The coupling is deliberate:
# a warm-up decoded successfully gives confidence that study audio will
# also route and decode correctly.
from harness.run_scenario import (       # noqa: E402 (sys.path edit above)
    _NOISE_CUTOFF_HZ   as _WARMUP_NOISE_CUTOFF_HZ,
    _PLAYBACK_PEAK_LEVEL as _WARMUP_PEAK_LEVEL,
    _select_device,
    _next_cycle_boundary,
    _wait_for_cycle,
)
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

# ── Warm-up signal parameters ─────────────────────────────────────────────────
# MSG-01 from study-messages.json — the primary study message, already proven
# to encode and decode correctly in both WSJT-X and OpenWSFZ.
_WARMUP_MESSAGE: str = "CQ Q1ABC FN42"
_WARMUP_SNR_DB: float = 6.0       # high SNR — must decode reliably in both apps
_WARMUP_FREQ_HZ: float = 1500.0   # FT8 nominal centre frequency (Hz)
_WARMUP_DT_S: float = 0.0         # no time offset
_WARMUP_SEED: int = 42            # fixed seed; not a study measurement

# ── Guard behaviour ────────────────────────────────────────────────────────────
# After sd.wait() returns the 15-second slot is complete.  Both apps run their
# LDPC decoder shortly after the cycle boundary; 5 s is sufficient for both
# WSJT-X and OpenWSFZ to finish and write their ALL.TXT entries.
_POST_CYCLE_DECODE_SETTLE_S: float = 5.0
_MAX_RETRIES: int = 5             # abort if operator cannot confirm after this many cycles


def _render_warmup_cycle() -> "numpy.ndarray":
    """Render one warm-up FT8 slot: clean encode → bandlimited AWGN → normalise."""
    import numpy as np
    from synth import channel, encoder

    clean = encoder.encode_message(
        _WARMUP_MESSAGE,
        base_freq_hz=_WARMUP_FREQ_HZ,
        dt_s=_WARMUP_DT_S,
        snr_db=None,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
    )
    noisy = channel.add_noise(
        clean, _WARMUP_SNR_DB, _WARMUP_SEED,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        noise_cutoff_hz=_WARMUP_NOISE_CUTOFF_HZ,
    )
    samples = noisy.astype("float32")
    peak = float(np.max(np.abs(samples)))
    if peak > 0.0:
        samples = (samples * (_WARMUP_PEAK_LEVEL / peak)).astype("float32")
    return samples


def run(device_substring: str = "CABLE Input") -> None:
    """Play warm-up cycles until the operator confirms both apps are decoding.

    Exits with code 0 on success (operator confirmed y), code 1 on abort
    (operator chose n or :data:`_MAX_RETRIES` was reached).  The calling
    process (``run_study.py``) uses ``check=True``, so a non-zero exit here
    halts the study before any trials are played.
    """
    import sounddevice as sd

    device_idx = _select_device(device_substring)

    # Render once; replay the same samples on every retry.
    # The seed is fixed so each replay is acoustically identical.
    print()
    print("=" * 70)
    print("R&R STUDY  --  PRE-FLIGHT WARM-UP CHECK")
    print("=" * 70)
    print(f"  Warm-up message : {_WARMUP_MESSAGE!r}")
    print(f"  SNR             : +{_WARMUP_SNR_DB:.0f} dB  (high; must decode reliably)")
    print(f"  Frequency       : {_WARMUP_FREQ_HZ:.0f} Hz centre")
    print()
    print("  Rendering warm-up audio … ", end="", flush=True)
    samples = _render_warmup_cycle()
    print("done")
    print()
    print("  The harness will now play one 15-second FT8 cycle into VB-CABLE.")
    print("  After the cycle ends, check BOTH apps for the decoded message:")
    print()
    print(f'    WSJT-X   -- Band Activity panel should show: "{_WARMUP_MESSAGE}"')
    print(f'    OpenWSFZ -- Decode log should show:           "{_WARMUP_MESSAGE}"')
    print()
    print("  If neither app shows a decode, the audio routing is broken and")
    print("  the study cannot produce valid results.")
    print()

    attempt = 0
    while attempt < _MAX_RETRIES:
        attempt += 1

        boundary_ts = _next_cycle_boundary()
        cycle_utc = _wait_for_cycle(boundary_ts)
        cycle_str = cycle_utc.strftime("%H:%M:%S")

        print(
            f"  [Attempt {attempt}/{_MAX_RETRIES}]"
            f" Playing warm-up at {cycle_str} UTC … ",
            end="", flush=True,
        )
        try:
            sd.play(
                samples,
                samplerate=DEFAULT_SAMPLE_RATE_HZ,
                device=device_idx,
                blocking=False,
            )
            sd.wait()
        except sd.PortAudioError as exc:
            print(f"\nERROR: PortAudio playback failed: {exc}")
            sys.exit(1)
        print("done")

        print(
            f"  Waiting {_POST_CYCLE_DECODE_SETTLE_S:.0f} s for decoders"
            " to complete … ",
            end="", flush=True,
        )
        time.sleep(_POST_CYCLE_DECODE_SETTLE_S)
        print("ready")
        print()

        while True:
            try:
                ans = input(
                    "  Both apps decoded?"
                    "  [y = yes, proceed / r = replay cycle / n = abort]: "
                ).strip().lower()
            except EOFError:
                # Non-interactive invocation (e.g. CI) — treat as abort.
                ans = "n"

            if ans in ("y", "yes"):
                print()
                print(
                    "  Warm-up confirmed -- both apps are decoding."
                    "  Starting study ..."
                )
                print("=" * 70)
                print()
                return

            elif ans in ("r", "replay"):
                print()
                break  # break inner loop → continue outer loop (replay)

            elif ans in ("n", "no"):
                print()
                print("  Warm-up check FAILED.  Study aborted.")
                print()
                print("  Pre-flight checklist:")
                print(
                    "    1. VB-CABLE Input is selected as the playback device"
                    " (--device flag)."
                )
                print(
                    "    2. WSJT-X audio input = VB-CABLE Output;"
                    " Monitor mode is ON."
                )
                print(
                    "    3. OpenWSFZ audio input = VB-CABLE Output;"
                    " decoding is enabled."
                )
                print(
                    "    4. No stale decodes from a previous session --"
                    " clear ALL.TXT in both apps."
                )
                print(
                    "    5. WSJT-X is set to the correct FT8 frequency"
                    " and mode (not FT4, JS8, etc.)."
                )
                print()
                sys.exit(1)

            else:
                print("  Please enter y, r, or n.")

    print(
        f"\nERROR: Warm-up check not confirmed after {_MAX_RETRIES} attempts."
        "  Study aborted."
    )
    sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "R&R study warm-up guard — confirm both WSJT-X and OpenWSFZ "
            "are decoding before the run starts"
        )
    )
    parser.add_argument(
        "--device",
        default="CABLE Input",
        help="Output device name substring (default: 'CABLE Input')",
    )
    args = parser.parse_args()
    run(args.device)
