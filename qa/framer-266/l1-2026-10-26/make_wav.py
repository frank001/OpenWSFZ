# Tiles the three synthetic Q-call fixtures (15.000 s each, 12 kHz mono int16) into a 48 kHz stereo int16 WAV of N cycles.
import wave, sys, numpy as np
from scipy.signal import resample_poly
src = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\tests\OpenWSFZ.Ft8.Tests\Fixtures\synth-qso-0%d.wav"
N = int(sys.argv[1]); out = sys.argv[2]
cyc = []
for i in (1, 2, 3):
    w = wave.open(src % i); assert w.getframerate() == 12000 and w.getnchannels() == 1 and w.getsampwidth() == 2
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64); assert len(x) == 180000
    cyc.append(x)
x = np.concatenate([cyc[k % 3] for k in range(N)])
y = resample_poly(x, 4, 1)
y = np.clip(y, -32768, 32767).astype("<i2")
st = np.repeat(y[:, None], 2, axis=1)
o = wave.open(out, "wb"); o.setnchannels(2); o.setsampwidth(2); o.setframerate(48000); o.writeframes(st.tobytes()); o.close()
print("cycles", N, "seconds", len(y) / 48000, "peak", int(np.abs(y).max()))
