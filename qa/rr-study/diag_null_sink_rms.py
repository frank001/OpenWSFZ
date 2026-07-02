"""Diagnostic: play FT8 signal to ft8loopback sink and capture from monitor simultaneously.

Prints RMS of captured audio to confirm signal is flowing through the null-sink.

Run from WSL2:
    python diag_null_sink_rms.py
"""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).parent))
from synth.encoder import encode_message

# Generate normalised signal
msg = "Q9SMK QQ0FX +10"
s = encode_message(msg, 1500.0, snr_db=10.0, seed=42).astype("float32")
peak = float(np.max(np.abs(s)))
s *= 0.9 / peak
print(f"Signal: {len(s)} samples at 48000 Hz ({len(s)/48000:.1f}s), peak={np.max(np.abs(s)):.3f}")

# Show devices
print("\nsounddevice default output:", sd.default.device[1], "—", sd.query_devices(sd.default.device[1])["name"])
print()

# Arm arecord capture (mono, 12000 Hz — same as daemon)
cap_path = "/tmp/smoke_cap.raw"
rec_proc = subprocess.Popen(
    ["arecord", "-D", "pulse", "-f", "FLOAT_LE", "-r", "12000", "-c", "1",
     "-d", "20", cap_path],
    stderr=subprocess.DEVNULL,
)
time.sleep(0.3)  # let arecord arm

# Play
print("Playing to default PulseAudio sink (ft8loopback) ...")
sd.play(s, samplerate=48000, blocking=True)
print("Playback done. Waiting for arecord to finish ...")
time.sleep(4)
rec_proc.terminate()
rec_proc.wait()

# Analyse capture
raw = open(cap_path, "rb").read()
arr = np.frombuffer(raw, dtype="float32")
if len(arr) == 0:
    print("ERROR: no samples captured — arecord produced no output")
    sys.exit(1)

rms  = float(np.sqrt(np.mean(arr ** 2)))
peak_cap = float(np.max(np.abs(arr)))
print(f"Captured {len(arr)} samples ({len(arr)/12000:.1f}s)")
print(f"  RMS  = {rms:.6f}  ({20*np.log10(rms+1e-12):.1f} dBFS)")
print(f"  Peak = {peak_cap:.4f}  ({20*np.log10(peak_cap+1e-12):.1f} dBFS)")

if rms > 1e-4:
    print("\n[SIGNAL] Audio is flowing through the null-sink to arecord.")
    print("Decode failure is likely a sample-rate or format issue in the decode chain.")
else:
    print("\n[SILENCE] No signal reaching arecord from the null-sink.")
    print("Check: pactl info | grep Default")
