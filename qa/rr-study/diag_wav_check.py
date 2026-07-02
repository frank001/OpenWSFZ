"""Read the captured WAV properly and check signal quality."""
from __future__ import annotations
import sys
import numpy as np
import soundfile as sf

cap = "/tmp/smoke_cap.raw"  # arecord writes WAV despite the .raw extension
try:
    data, sr = sf.read(cap, dtype="float32")
except Exception as e:
    print(f"soundfile failed: {e}")
    # Try scipy
    from scipy.io import wavfile
    sr, data = wavfile.read(cap)
    data = data.astype("float32")

print(f"Sample rate: {sr} Hz")
print(f"Samples: {len(data)} ({len(data)/sr:.2f} s)")
print(f"Channels: {data.ndim} (1=mono, 2=stereo)")
if data.ndim > 1:
    data = data[:, 0]  # take left channel

rms  = float(np.sqrt(np.mean(data ** 2)))
peak = float(np.max(np.abs(data)))
print(f"RMS  = {rms:.6f}  ({20*np.log10(rms+1e-12):.1f} dBFS)")
print(f"Peak = {peak:.4f}  ({20*np.log10(peak+1e-12):.1f} dBFS)")

if rms > 1e-4:
    print("\n✅ Signal is present in captured audio.")
    print(f"   SNR estimate vs full-scale: {20*np.log10(rms):.1f} dBFS")
else:
    print("\n❌ Silence captured — audio not flowing through null-sink.")

# Plot a simple spectrum peak to confirm it's near 1500 Hz
n = len(data)
fft = np.abs(np.fft.rfft(data[:min(n, sr*15)]))
freqs = np.fft.rfftfreq(min(n, sr*15), d=1.0/sr)
peak_idx = np.argmax(fft)
print(f"\nStrongest frequency component: {freqs[peak_idx]:.1f} Hz  (expect ~1500 Hz for FT8)")
