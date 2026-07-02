"""
verify_loopback.py — comprehensive VB-CABLE loopback verification.

Tries four combinations of (play API, record API) to find which works.
Uses stereo (channels=2) everywhere to match VB-CABLE's native format.

Run: python qa/rr-study/verify_loopback.py
"""
import time
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE   = 48000
DURATION      = 3.0
TONE_FREQ     = 1000.0
TONE_AMP      = 0.3
RMS_THRESHOLD = 0.01   # -34 dBFS — anything above = clear signal

# ----- Device indices from check_hostapi.py -----
CABLE_IN_MME    = 28   # CABLE Input   MME  (output)
CABLE_IN_WASAPI = 83   # CABLE Input   WASAPI (output)
CABLE_OUT_MME   = 1    # CABLE Output  MME  (input)
CABLE_OUT_WASAPI= 103  # CABLE Output  WASAPI (input)

def make_tone_stereo(duration: float) -> np.ndarray:
    """Return a (N, 2) stereo float32 array containing a sine tone."""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False, dtype=np.float32)
    mono = (TONE_AMP * np.sin(2.0 * np.pi * TONE_FREQ * t))
    return np.stack([mono, mono], axis=1)   # shape (N, 2)

def record_stereo(device_idx: int, label: str, result: dict, duration: float = DURATION):
    """Blocking record into result['rms'] and result['error']."""
    frames = int(SAMPLE_RATE * duration)
    try:
        buf = sd.rec(frames, samplerate=SAMPLE_RATE, channels=2,
                     dtype="float32", device=device_idx, blocking=True)
        # Compute RMS over both channels
        rms = float(np.sqrt(np.mean(buf ** 2)))
        result["rms"]   = rms
        result["error"] = None
    except Exception as exc:
        result["rms"]   = -1.0
        result["error"] = str(exc)

def play_tone_stereo(device_idx: int, duration: float = DURATION):
    tone = make_tone_stereo(duration)
    try:
        sd.play(tone, samplerate=SAMPLE_RATE, device=device_idx, blocking=True)
    except Exception as exc:
        print(f"    PLAYBACK ERROR: {exc}")

def run_loopback_test(play_idx: int, play_label: str,
                      rec_idx: int,  rec_label: str) -> dict:
    result: dict = {"rms": 0.0, "error": None}
    rec_thread = threading.Thread(target=record_stereo,
                                  args=(rec_idx, rec_label, result, DURATION))
    rec_thread.start()
    time.sleep(0.25)   # let recording arm
    play_tone_stereo(play_idx, DURATION - 0.25)
    rec_thread.join(timeout=DURATION + 3)
    return result

def verdict(r: dict) -> str:
    if r["error"]:
        return f"[ERROR: {r['error'][:60]}]"
    rms = r["rms"]
    if rms > RMS_THRESHOLD:
        return f"[SIGNAL  RMS={rms:.4f}]"
    return f"[SILENCE RMS={rms:.6f}]"

print("=== VB-CABLE loopback verification (stereo, all API combinations) ===")
print(f"  Tone: {TONE_FREQ:.0f} Hz, amp={TONE_AMP}, SR={SAMPLE_RATE}")
print(f"  Signal threshold: RMS > {RMS_THRESHOLD}")
print()

combos = [
    (CABLE_IN_MME,    "CABLE Input  [MME   28]",
     CABLE_OUT_MME,   "CABLE Output [MME    1]"),
    (CABLE_IN_WASAPI, "CABLE Input  [WASAPI 83]",
     CABLE_OUT_MME,   "CABLE Output [MME    1]"),
    (CABLE_IN_MME,    "CABLE Input  [MME   28]",
     CABLE_OUT_WASAPI,"CABLE Output [WASAPI103]"),
    (CABLE_IN_WASAPI, "CABLE Input  [WASAPI 83]",
     CABLE_OUT_WASAPI,"CABLE Output [WASAPI103]"),
]

results = []
for i, (p_idx, p_lbl, r_idx, r_lbl) in enumerate(combos, 1):
    print(f"Test {i}: Play -> {p_lbl}  |  Record <- {r_lbl}")
    r = run_loopback_test(p_idx, p_lbl, r_idx, r_lbl)
    v = verdict(r)
    print(f"  Result: {v}")
    results.append((p_lbl, r_lbl, v, r))
    time.sleep(0.5)

print()
print("=== Summary ===")
working = [(p, r, v) for p, r, v, rd in results if rd.get("rms", -1) > RMS_THRESHOLD]
if working:
    print(f"Working combinations:")
    for p, r, v in working:
        print(f"  Play={p}  Record={r}  => {v}")
    # Recommend based on what the harness does
    print()
    # Check if WASAPI play -> WASAPI record works (preferred for daemon compatibility)
    wasapi_both = [(p, r, v) for p, r, v in working if "WASAPI" in p and "WASAPI" in r]
    if wasapi_both:
        print("RECOMMENDATION: Use WASAPI for both play and record (same API as daemon).")
    else:
        print("RECOMMENDATION: Use one of the working combinations above for the harness.")
        print("  The daemon uses NAudio WASAPI — these PortAudio results may differ from daemon behaviour.")
else:
    print("NO combinations produced signal — VB-CABLE loopback is completely broken.")
    print("Check: Windows Sound settings, VB-CABLE driver state, exclusive mode settings.")
    print("Try: right-click CABLE Output in Sound Control Panel -> Properties -> Advanced")
    print("     Ensure 'Allow applications to take exclusive control' is UN-checked, OR")
    print("     set format to '2 channel, 24-bit, 48000 Hz'.")
