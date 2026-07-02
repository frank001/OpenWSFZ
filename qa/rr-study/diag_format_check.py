"""Check what format arecord actually captures from the PulseAudio monitor source."""
from __future__ import annotations
import subprocess, struct, sys
import numpy as np

cap = "/tmp/smoke_cap.raw"
raw = open(cap, "rb").read()
n_bytes = len(raw)
print(f"Raw bytes: {n_bytes}")
print(f"  as float32 (4 B/sample): {n_bytes//4} samples")
print(f"  as int16   (2 B/sample): {n_bytes//2} samples")
print(f"  as int16 stereo: {n_bytes//4} frames")
print(f"  as float32 stereo: {n_bytes//8} frames")
print()

# Try reading as int16 stereo (most likely PulseAudio default)
arr_i16 = np.frombuffer(raw, dtype="<i2")
print(f"As int16: peak={np.max(np.abs(arr_i16))}, rms={np.sqrt(np.mean(arr_i16.astype(float)**2)):.2f}")

# Try reading as float32 (what we asked for)
arr_f32 = np.frombuffer(raw, dtype="<f4")
finite_mask = np.isfinite(arr_f32)
print(f"As float32: {finite_mask.sum()} finite of {len(arr_f32)}, peak_finite={np.max(np.abs(arr_f32[finite_mask])) if finite_mask.any() else 'N/A':.4f}")

print()
print("First 16 bytes (hex):", raw[:16].hex())
print("First 8 bytes as int16:", list(struct.unpack("<8h", raw[:16])))
print("First 4 bytes as float32:", struct.unpack("<f", raw[:4]))

# Check what arecord says about the format it's using
print()
print("--- arecord format probe ---")
result = subprocess.run(
    ["arecord", "-D", "pulse", "-f", "FLOAT_LE", "-r", "12000", "-c", "1", "--dump-hw-params", "-d", "1", "/dev/null"],
    capture_output=True, text=True
)
print(result.stderr[:1000])
