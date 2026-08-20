"""Verify a WASAPI render -> capture audio path by tone injection.

Generalises verify_wasapi.py, which hard-coded VB-CABLE device *indices*. Indices are
not stable across reboots or driver changes on this machine (many virtual endpoints),
so devices are resolved by NAME on the WASAPI host API only -- the same selection rule
run_scenario.py::_select_device applies, for the reason documented there (an MME match
at 44100 Hz silently produces zero WSJT-X decodes while OpenWSFZ still decodes).

Usage:
    python verify_wasapi_path.py --render "Voicemeeter AUX Input" --capture "Voicemeeter Out B1"

Exit code 0 iff captured RMS exceeds RMS_THRESHOLD.
"""
import argparse
import sys
import time

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
DURATION = 4.0
ARM_DELAY = 0.3
TONE_FREQ = 1000.0
TONE_AMP = 0.3
RMS_THRESHOLD = 0.005   # anything above this is "signal"; matches verify_wasapi.py
RATE_TOLERANCE = 0.02   # effective capture rate must be within 2% of nominal


def resolve(substring: str, want_output: bool) -> int:
    """Return the WASAPI device index whose name contains ``substring``.

    Exits 1 on no match, or on an ambiguous match (more than one distinct WASAPI
    endpoint), rather than silently picking one.
    """
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    chan = "max_output_channels" if want_output else "max_input_channels"
    matches = [
        (i, d)
        for i, d in enumerate(devices)
        if substring.lower() in d["name"].lower()
        and d[chan] > 0
        and hostapis[d["hostapi"]]["name"] == "Windows WASAPI"
    ]
    role = "render" if want_output else "capture"
    if not matches:
        print(f"ERROR: no WASAPI {role} device matching '{substring}'. Available:")
        for i, d in enumerate(devices):
            if d[chan] > 0 and hostapis[d["hostapi"]]["name"] == "Windows WASAPI":
                print(f"  [{i}] {d['name']}")
        sys.exit(1)
    if len(matches) > 1:
        print(f"ERROR: '{substring}' is ambiguous across {len(matches)} WASAPI {role} devices:")
        for i, d in matches:
            print(f"  [{i}] {d['name']}")
        sys.exit(1)
    idx, dev = matches[0]
    print(f"  {role:7s}: [{idx}] {dev['name']} ({dev['default_samplerate']:.0f} Hz)")
    return idx


def record_rms(device_idx: int, render_device_idx: int, result: list) -> None:
    """Capture for DURATION seconds, playing the tone mid-capture; RMS into ``result[0]``.

    Three deliberate choices, all learned the hard way on 2026-08-15:

    1. An explicit stream, not sd.rec(). sd.play()/sd.rec() share module-level state in
       sounddevice and are not safe to run concurrently from two threads -- doing so
       raised a spurious PaErrorCode -9999 here. verify_wasapi.py has this latent flaw.
    2. A CALLBACK stream, not blocking stream.read(). Blocking read() starves on these
       virtual endpoints: it returned the full frame count but took ~2x wall-clock to do
       it, which reads exactly like a half-rate capture device and is not one. Measured
       against a callback stream the same endpoint delivers 47992 Hz, i.e. real time. A
       blocking read() here will make a healthy path look broken.
    3. Opened on the MAIN THREAD. Opening a WASAPI stream from a Python worker thread
       fails deterministically with PaErrorCode -9999 ('WdmSyncIoctl ... GLE = 0x490'):
       the worker thread has no initialised COM apartment, so PortAudio's WASAPI backend
       cannot start and the error surfaces from the host API it probes next. The
       misleading WDM-KS text in that message cost real time -- it names neither the
       device nor the true fault. A callback stream is non-blocking, so the tone can be
       played on this same thread while the callback fills ``chunks``; no worker thread
       is needed, and introducing one reintroduces the bug.

    ``result[1]`` receives the effective frame rate so the caller can assert real time.
    """
    chunks: list = []
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            device=device_idx,
                            callback=lambda indata, frames, t, status: chunks.append(indata.copy())):
            t0 = time.perf_counter()
            time.sleep(ARM_DELAY)
            play_tone(render_device_idx, DURATION - 2 * ARM_DELAY)
            time.sleep(ARM_DELAY)
            elapsed = time.perf_counter() - t0
        buf = np.concatenate(chunks).flatten() if chunks else np.zeros(1, dtype="float32")
        result[0] = float(np.sqrt(np.mean(buf ** 2)))
        result[1] = len(buf) / elapsed
    except Exception as e:  # noqa: BLE001 - diagnostic script, report and continue
        print(f"  ERROR recording: {e}")
        result[0] = -1.0


def play_tone(device_idx: int, duration: float) -> None:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    tone = (TONE_AMP * np.sin(2 * np.pi * TONE_FREQ * t)).reshape(-1, 1)
    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                             device=device_idx) as stream:
            stream.write(tone)
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR playing: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True, help="WASAPI render device name substring")
    ap.add_argument("--capture", required=True, help="WASAPI capture device name substring")
    args = ap.parse_args()

    print("=== WASAPI path verification ===")
    print(f"  Tone: {TONE_FREQ:.0f} Hz, amp={TONE_AMP}, SR={SAMPLE_RATE} Hz, {DURATION:.1f} s")
    print(f"  RMS signal threshold: {RMS_THRESHOLD}")
    render_idx = resolve(args.render, want_output=True)
    capture_idx = resolve(args.capture, want_output=False)
    print()

    result = [0.0, 0.0]
    record_rms(capture_idx, render_idx, result)

    rms, eff_rate = result[0], result[1]
    if rms < 0:
        verdict = "[ERROR]"
    elif rms > RMS_THRESHOLD:
        verdict = "[SIGNAL]"
    else:
        verdict = "[SILENCE]"
    print(f"  captured RMS  = {rms:.6f}  {verdict}")
    print(f"  effective rate= {eff_rate:.0f} Hz (nominal {SAMPLE_RATE} Hz)")
    rate_ok = abs(eff_rate - SAMPLE_RATE) / SAMPLE_RATE < RATE_TOLERANCE
    if not rate_ok:
        print(f"  WARNING: capture rate is off nominal by more than "
              f"{RATE_TOLERANCE * 100:.0f}% -- audio will be time-distorted.")
    print()
    if verdict == "[SIGNAL]" and rate_ok:
        print(f"PASS: '{args.render}' -> '{args.capture}' carries audio at real time.")
        return 0
    print(f"FAIL: '{args.render}' -> '{args.capture}' does NOT carry audio.")
    print("  Check the Voicemeeter strip's bus assignment button for the target bus,")
    print("  the strip fader/mute state, and that both endpoints are 48 kHz shared mode.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
