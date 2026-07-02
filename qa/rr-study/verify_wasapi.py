"""Verify VB-CABLE loopback and Voicemeeter routing using WASAPI devices (same API as the daemon).

WASAPI device indices (from check_hostapi.py):
  [83]  CABLE Input  (WASAPI render)
  [103] CABLE Output (WASAPI capture)  -- direct loopback, no Voicemeeter
  [102] Voicemeeter Out B2 (WASAPI capture)  -- requires Voicemeeter routing
"""
import time
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE   = 48000
DURATION      = 4.0
TONE_FREQ     = 1000.0
TONE_AMP      = 0.3
RMS_THRESHOLD = 0.005   # anything above this is "signal"

# WASAPI device indices (from check_hostapi.py output)
CABLE_IN_WASAPI  = 83   # CABLE Input  (WASAPI render)
CABLE_OUT_WASAPI = 103  # CABLE Output (WASAPI capture)
VMETER_B2_WASAPI = 102  # Voicemeeter Out B2 (WASAPI capture)

def record_rms(device_idx: int, label: str, result: list, duration: float = DURATION) -> None:
    """Record blocking, store RMS in result[0]."""
    frames = int(SAMPLE_RATE * duration)
    try:
        buf = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1,
                     dtype="float32", device=device_idx, blocking=True)
        rms = float(np.sqrt(np.mean(buf ** 2)))
        result[0] = rms
    except Exception as e:
        print(f"  ERROR recording from {label}: {e}")
        result[0] = -1.0

def play_tone(device_idx: int, duration: float = DURATION) -> None:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    tone = (TONE_AMP * np.sin(2 * np.pi * TONE_FREQ * t)).reshape(-1, 1)
    try:
        sd.play(tone, samplerate=SAMPLE_RATE, device=device_idx, blocking=True)
    except Exception as e:
        print(f"  ERROR playing to CABLE Input WASAPI: {e}")

def run_test(capture_device: int, capture_label: str) -> float:
    """Play tone to CABLE Input (WASAPI), simultaneously record from capture_device."""
    result = [0.0]
    rec_thread = threading.Thread(target=record_rms,
                                  args=(capture_device, capture_label, result, DURATION))
    rec_thread.start()
    time.sleep(0.3)   # give recording thread time to arm
    play_tone(CABLE_IN_WASAPI, DURATION - 0.3)
    rec_thread.join(timeout=DURATION + 2)
    return result[0]

def verdict(rms: float) -> str:
    if rms < 0:    return "[ERROR]"
    if rms > RMS_THRESHOLD: return "[SIGNAL]"
    return "[SILENCE]"

print("=== VB-CABLE / Voicemeeter WASAPI verification ===")
print(f"  Tone: {TONE_FREQ:.0f} Hz, amp={TONE_AMP}, WASAPI SR={SAMPLE_RATE} Hz")
print(f"  RMS signal threshold: {RMS_THRESHOLD}")
print()

# Test 1: CABLE Input -> CABLE Output (direct VB-CABLE loopback)
print(f"Test 1: CABLE Input [WASAPI {CABLE_IN_WASAPI}] -> CABLE Output [WASAPI {CABLE_OUT_WASAPI}]")
rms1 = run_test(CABLE_OUT_WASAPI, "CABLE Output WASAPI")
print(f"  CABLE Output RMS = {rms1:.6f}  {verdict(rms1)}")
time.sleep(0.5)

# Test 2: CABLE Input -> Voicemeeter Out B2 (Voicemeeter routing required)
print(f"Test 2: CABLE Input [WASAPI {CABLE_IN_WASAPI}] -> Voicemeeter Out B2 [WASAPI {VMETER_B2_WASAPI}]")
rms2 = run_test(VMETER_B2_WASAPI, "Voicemeeter Out B2 WASAPI")
print(f"  Voicemeeter B2 RMS = {rms2:.6f}  {verdict(rms2)}")
print()

print("=== Diagnosis ===")
if rms1 > RMS_THRESHOLD and rms2 > RMS_THRESHOLD:
    print("BOTH paths deliver signal.")
    print("Audio chain is OK. Root cause of empty ALL.TXT must lie elsewhere.")
elif rms1 > RMS_THRESHOLD and rms2 <= RMS_THRESHOLD:
    print("CABLE Output delivers signal BUT Voicemeeter Out B2 does NOT.")
    print("=> Voicemeeter is NOT routing CABLE Output -> B2 bus.")
    print("=> Fix: change daemon audio device to CABLE Output (WASAPI ID: {0.0.1.00000000}.{ecb41d74-1aa5-43b1-ac89-b69e40510f00})")
    print("   OR open Voicemeeter and enable B2 routing on the CABLE Output input channel.")
elif rms1 <= RMS_THRESHOLD:
    print("CABLE Output is SILENT with WASAPI -- VB-CABLE loopback itself is broken.")
    print("=> Check Windows Sound settings: CABLE Input and CABLE Output should be 48 kHz, shared mode.")
    print("=> Reboot may be required if driver state is corrupt.")
else:
    print("Unexpected result.")
