"""D-001 live-path root-cause, Phase 3' -- FAST direct audio-device clock-rate measurement.

Replaces the original hours-long marker-injection design (phase3_marker_drift.py), which
needed real elapsed wall-clock time for FT8's 0.1s-quantized DT to show a visible step. This
measures the same underlying quantity -- does the capture device deliver samples at its true
declared rate, or is there a ppm-level clock error -- directly, at sample-level precision, with
no daemon and no FT8 decode involved. A ~47ppm error (the magnitude implied by Phase 1's
-0.17s/hr finding) produces ~14ms of accumulated sample-count-vs-wall-clock offset over just
5 minutes -- easily resolved at a 12000-48000 Hz sample rate, no waiting required.

Method: open an input stream on the same WASAPI "CABLE Output" device/hostapi the .NET daemon
itself negotiates (48000 Hz shared-mode, confirmed via the retained 07-07 live log's own
"WaveFormat=48000 Hz" banner), record for N seconds, timestamp cumulative sample count against
a monotonic wall clock on every callback, and fit a linear regression of samples-received vs
wall-clock-elapsed. The fitted slope IS the device's true effective sample rate; comparing it
to the nominal declared rate gives a ppm error, directly convertible to predicted seconds of
drift per hour for comparison against Phase 1's cross-app DT-drift finding (~-0.17 s/hr).

No daemon, no synth encode, no VB-CABLE playback needed -- passively records ambient/silent
input. Runs in minutes, not hours.

Usage: python phase3_clockrate_direct.py [--duration-s N] [--device-index N]
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path

import numpy as np
import sounddevice as sd

RESULTS_DIR = Path(__file__).resolve().parent
NOMINAL_RATE_HZ = 48000  # confirmed via artefacts/.../logs/openswfz-...log "WaveFormat=48000 Hz"
DEVICE_NAME_SUBSTR = "CABLE Output"
PREFERRED_HOSTAPI_SAMPLERATE = 48000.0  # match the WASAPI hostapi variant, not MME/DirectSound


def find_device():
    devices = sd.query_devices()
    candidates = [(i, d) for i, d in enumerate(devices)
                  if DEVICE_NAME_SUBSTR.lower() in d["name"].lower()
                  and d["max_input_channels"] > 0]
    # Prefer the one whose default_samplerate matches what the .NET daemon actually negotiates
    # (48000 Hz, WASAPI shared mode) over MME/DirectSound variants that report 44100.
    exact = [c for c in candidates if abs(c[1]["default_samplerate"] - PREFERRED_HOSTAPI_SAMPLERATE) < 1]
    chosen = exact[0] if exact else candidates[0]
    return chosen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-s", type=float, default=300.0, help="Recording duration (s)")
    parser.add_argument("--device-index", type=int, default=None,
                         help="Override device index (default: auto-detect CABLE Output, WASAPI variant)")
    args = parser.parse_args()

    if args.device_index is not None:
        idx = args.device_index
        dev = sd.query_devices(idx)
    else:
        idx, dev = find_device()
    print(f"Device: [{idx}] {dev['name']} (default_samplerate={dev['default_samplerate']})")

    samples_seen = 0
    timeline = []  # (wall_clock_elapsed_s, cumulative_samples)
    t0 = None

    def callback(indata, frames, time_info, status):
        nonlocal samples_seen, t0
        now = time.perf_counter()
        if t0 is None:
            t0 = now
        samples_seen += frames
        timeline.append((now - t0, samples_seen))

    print(f"Recording {args.duration_s}s at nominal {NOMINAL_RATE_HZ} Hz "
          f"(device's own rate is what's actually measured)...")
    with sd.InputStream(device=idx, channels=1, samplerate=NOMINAL_RATE_HZ,
                         callback=callback, blocksize=0):
        time.sleep(args.duration_s)

    print(f"Captured {samples_seen} samples over {timeline[-1][0]:.3f}s wall-clock "
          f"({len(timeline)} callbacks)")

    xs = np.array([t for t, _ in timeline])
    ys = np.array([n for _, n in timeline])
    # Linear fit: cumulative_samples = slope * elapsed_wall_clock_s + intercept
    A = np.vstack([xs, np.ones_like(xs)]).T
    slope, intercept = np.linalg.lstsq(A, ys, rcond=None)[0]
    resid = ys - (slope * xs + intercept)
    rmse = float(np.sqrt(np.mean(resid ** 2)))

    ppm_error = (slope - NOMINAL_RATE_HZ) / NOMINAL_RATE_HZ * 1e6
    predicted_drift_s_per_hr = (slope - NOMINAL_RATE_HZ) / NOMINAL_RATE_HZ * 3600.0
    # Sign convention (derived, then checked against Phase 1's observed sign): if the device
    # delivers samples SLOWER than nominal (slope < nominal, ppm_error < 0), a given sample
    # COUNT takes MORE real wall-clock time to arrive than the fixed-ratio resampler assumes.
    # CycleFramer's sample-count-only cycle boundary therefore lags further behind true
    # wall-clock/UTC as the session progresses -- i.e. OpenWSFZ's window opens progressively
    # LATE. A real signal arriving at the true UTC boundary then falls progressively EARLIER
    # relative to OpenWSFZ's own (late) window start, so OpenWSFZ's reported DT trends
    # increasingly NEGATIVE over session time -- same sign as ppm_error itself. This matches
    # Phase 1's observed sign (OpenWSFZ dt vs WSJT-X dt: -0.171 s/hr, device running slow).

    out = {
        "device": dev["name"], "device_index": idx,
        "nominal_rate_hz": NOMINAL_RATE_HZ,
        "measured_rate_hz": float(slope),
        "ppm_error": float(ppm_error),
        "predicted_drift_s_per_hr": float(predicted_drift_s_per_hr),
        "phase1_observed_drift_s_per_hr": -0.171,
        "fit_rmse_samples": rmse,
        "duration_s": args.duration_s,
        "n_callbacks": len(timeline),
        "total_samples": samples_seen,
    }
    out_path = RESULTS_DIR / "phase3_clockrate_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\n=== RESULT ===")
    print(f"Measured device rate: {slope:.4f} Hz  (nominal: {NOMINAL_RATE_HZ} Hz)")
    print(f"ppm error: {ppm_error:+.2f} ppm")
    print(f"Predicted drift (this mechanism alone): {predicted_drift_s_per_hr:+.4f} s/hr")
    print(f"Phase 1 observed (OpenWSFZ vs WSJT-X, 3 sessions): ~-0.171 s/hr")
    print(f"Fit RMSE: {rmse:.2f} samples ({rmse/NOMINAL_RATE_HZ*1000:.3f} ms)")
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
