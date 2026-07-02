"""Diagnostic: generate FT8 signal at 12 kHz native rate, play via aplay.

Bypasses sounddevice and the 48→12 kHz PulseAudio resampling path entirely.
If the daemon decodes this, the issue is in the sounddevice/resampling path.
If it still doesn't decode, the issue is in the signal or Linux decoder.

Run from WSL2:
    python diag_aplay_native.py
"""
from __future__ import annotations
import subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from synth.encoder import encode_message

_MESSAGE   = "CQ Q1ABC FN42"
_FREQ_HZ   = 1500.0
_SNR_DB    = 10.0
_SR        = 12_000          # native decoder sample rate — no resampling needed
_SLOT_S    = 15
_ALL_TXT   = Path(__file__).parent.parent.parent / "linux-all.txt"
_RAW_PATH  = "/tmp/ft8_native.raw"

def _next_boundary() -> float:
    now = time.time()
    return now + (_SLOT_S - (now % _SLOT_S))

print(f"Generating at {_SR} Hz (native, no resampling) ...")
s = encode_message(_MESSAGE, _FREQ_HZ, snr_db=_SNR_DB, seed=42,
                   sample_rate_hz=_SR).astype("float32")
peak = float(np.max(np.abs(s)))
s *= 0.9 / peak
print(f"  {len(s)} samples, peak={np.max(np.abs(s)):.3f}, "
      f"rms={np.sqrt(np.mean(s**2)):.4f}")

# Write raw PCM (no WAV header)
s.tofile(_RAW_PATH)
print(f"  Written to {_RAW_PATH} ({len(s)*4} bytes)\n")

# Play for 3 consecutive cycles using aplay directly
boundary = _next_boundary()
wait_s   = boundary - time.time()
print(f"Next boundary: {datetime.fromtimestamp(boundary, tz=timezone.utc).strftime('%H:%M:%S')} UTC")
print(f"Waiting {wait_s:.1f} s ...")
if wait_s > 0:
    time.sleep(max(0.0, wait_s - 0.05))
while time.time() < boundary:
    pass

print(f"Playing 3 cycles via aplay -D pulse at {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC ...")
for i in range(3):
    proc = subprocess.run(
        ["aplay", "-D", "pulse", "-f", "FLOAT_LE", "-r", str(_SR), "-c", "1", "-t", "raw",
         _RAW_PATH],
        capture_output=True,
    )
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  cycle {i+1}/3 done at {ts} UTC  (rc={proc.returncode})")
    if proc.stderr:
        print(f"    stderr: {proc.stderr.decode(errors='replace').strip()[:120]}")

print("\nWaiting 8 s for daemon to process ...")
time.sleep(8)

# Check ALL.TXT
if _ALL_TXT.exists():
    lines = _ALL_TXT.read_text(errors="replace").splitlines()
    hits = [l for l in lines if "Q1ABC" in l]
    if hits:
        print(f"\n✅ DECODE FOUND:")
        for h in hits[-5:]:
            print(f"   {h}")
    else:
        print(f"\n❌ No decode in {_ALL_TXT}")
        print(f"   Last 5 lines of ALL.TXT: {lines[-5:] if lines else '(empty)'}")
else:
    print(f"\n❌ {_ALL_TXT} does not exist")
