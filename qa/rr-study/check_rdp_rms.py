"""Check RMS of /tmp/rdp_test.wav recorded from RDPSink.monitor."""
import struct, math

with open('/tmp/rdp_test.wav', 'rb') as f:
    f.seek(44)  # skip WAV header
    data = f.read()

if data:
    samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    peak = max(abs(s) for s in samples)
    print(f"Samples: {len(samples)}, RMS: {rms:.1f}, Peak: {peak}")
    print(f"RMS (normalised 0-1): {rms/32768:.6f}")
    print("SIGNAL" if rms > 100 else "SILENCE")
else:
    print("No samples recorded")
