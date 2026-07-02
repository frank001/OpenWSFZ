"""Verify audio chain: play tone to CABLE Input, measure RMS on CABLE Output and Voicemeeter Out B2.

Usage: python verify_audio_chain.py
"""
import numpy as np
import sounddevice as sd
import threading
import time

SAMPLE_RATE = 48000
DURATION    = 3.0        # seconds to record
TONE_FREQ   = 1000.0     # Hz
TONE_AMP    = 0.3        # amplitude

CABLE_INPUT_NAME   = "CABLE Input"       # render — harness plays here
CABLE_OUTPUT_NAME  = "CABLE Output"      # capture — direct VB-CABLE loopback
VMETER_B2_NAME     = "Voicemeeter Out B2"  # capture — requires Voicemeeter routing

def find_device(name: str, kind: str) -> int:
    """Find device index by substring match. kind = 'input' or 'output'."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if name.lower() in d["name"].lower():
            if kind == "input"  and d["max_input_channels"]  > 0:
                return i
            if kind == "output" and d["max_output_channels"] > 0:
                return i
    raise ValueError(f"Device not found: {name!r} ({kind})")

def measure_rms(device_idx: int, name: str) -> float:
    """Capture DURATION seconds from device, return RMS."""
    frames = int(SAMPLE_RATE * DURATION)
    try:
        recording = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1,
                           dtype="float32", device=device_idx, blocking=False)
        sd.wait()
        rms = float(np.sqrt(np.mean(recording ** 2)))
        return rms
    except Exception as e:
        print(f"  ERROR capturing from {name}: {e}")
        return 0.0

def play_tone(device_idx: int, duration: float):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    tone = (TONE_AMP * np.sin(2 * np.pi * TONE_FREQ * t)).astype("float32")
    sd.play(tone, samplerate=SAMPLE_RATE, device=device_idx)
    sd.wait()

def main():
    print("=== Audio chain verification ===\n")

    cable_in_idx  = find_device(CABLE_INPUT_NAME,  "output")
    cable_out_idx = find_device(CABLE_OUTPUT_NAME, "input")
    vmeter_b2_idx = find_device(VMETER_B2_NAME,    "input")

    print(f"CABLE Input  (render)  : device [{cable_in_idx}]")
    print(f"CABLE Output (capture) : device [{cable_out_idx}]")
    print(f"Voicemeeter Out B2     : device [{vmeter_b2_idx}]")
    print()

    # ── Test 1: CABLE Output while playing to CABLE Input ──────────────────────
    print("Test 1: Playing 1 kHz tone to CABLE Input, recording from CABLE Output ...")
    rms_out = [0.0]
    def record_cable_out():
        rms_out[0] = measure_rms(cable_out_idx, "CABLE Output")
    t1 = threading.Thread(target=record_cable_out, daemon=True)
    t1.start()
    time.sleep(0.2)
    play_tone(cable_in_idx, DURATION)
    t1.join()
    print(f"  CABLE Output RMS    : {rms_out[0]:.6f}  {'[SIGNAL]' if rms_out[0] > 0.01 else '[SILENCE]'}")
    print()
    time.sleep(0.5)

    # ── Test 2: Voicemeeter Out B2 while playing to CABLE Input ────────────────
    print("Test 2: Playing 1 kHz tone to CABLE Input, recording from Voicemeeter Out B2 ...")
    rms_b2 = [0.0]
    def record_vmeter_b2():
        rms_b2[0] = measure_rms(vmeter_b2_idx, "Voicemeeter Out B2")
    t2 = threading.Thread(target=record_vmeter_b2, daemon=True)
    t2.start()
    time.sleep(0.2)
    play_tone(cable_in_idx, DURATION)
    t2.join()
    print(f"  Voicemeeter B2 RMS  : {rms_b2[0]:.6f}  {'[SIGNAL]' if rms_b2[0] > 0.01 else '[SILENCE]'}")
    print()

    # ── Summary ─────────────────────────────────────────────────────────────────
    print("=== Summary ===")
    if rms_out[0] > 0.01 and rms_b2[0] > 0.01:
        print("Both paths deliver signal. Audio chain OK — Voicemeeter routing is correct.")
        print("Root cause of empty ALL.TXT must lie elsewhere.")
    elif rms_out[0] > 0.01 and rms_b2[0] <= 0.01:
        print("CABLE Output delivers signal BUT Voicemeeter Out B2 does NOT.")
        print("=> Voicemeeter routing is BROKEN. CABLE Output not routed to B2 bus.")
        print("=> Recommended fix: change daemon audio device to CABLE Output.")
    elif rms_out[0] <= 0.01:
        print("CABLE Output is SILENT — VB-CABLE loopback itself is broken.")
        print("=> Check that CABLE Input and CABLE Output are at 48 kHz, shared mode.")
    else:
        print("Unexpected result — investigate manually.")

if __name__ == "__main__":
    main()
