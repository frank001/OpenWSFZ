#!/usr/bin/env python3
"""G1 placement proof — S3's existing positive DT grid, offline, no decoder, no device.

Route B build spec (2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md),
§8 step 1: standalone disclosure of the §0 blocking finding. For each S3 part, render
the clean (noiseless) MSG-01 signal at its labelled dt_s and cross-correlate against the
dt_s=0.0 render of the SAME tone sequence. The cross-correlation argmax lag is the
placement the synth actually produced; compare it against the label to one sample.

This does not touch synth/modulator.py, run_scenario.py, or any scenario JSON — it is a
read-only measurement over the code as it stands today, run BEFORE any Route B build
step. No src/ change. No pre-registration required (this is disclosure of an already-
asserted defect, not a new blind measurement).

Usage (from qa/rr-study/):
    python g1_s3_positive_grid_placement_check.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
from scipy.signal import fftconvolve

_HERE = pathlib.Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from synth import encoder
from synth.constants import DEFAULT_SAMPLE_RATE_HZ, SLOT_LENGTH_S

SCENARIO_PATH = _HERE / "scenarios" / "s3-dt-offset.json"
MESSAGES_PATH = _HERE / "scenarios" / "study-messages.json"

FS = DEFAULT_SAMPLE_RATE_HZ  # 48000


def _load_msg01_text() -> str:
    data = json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
    for m in data.get("messages", []):
        if m["id"] == "MSG-01":
            return m["text"]
    sys.exit(f"ERROR: MSG-01 not found in {MESSAGES_PATH}")


def _load_s3_parts() -> tuple[list[dict], float]:
    scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    base_freq_hz = scenario["fixed"]["base_freq_hz"]
    return scenario["parts"], base_freq_hz


def _measured_lag_s(reference: np.ndarray, candidate: np.ndarray, fs: int) -> tuple[float, int]:
    """Cross-correlate candidate against reference; return (lag_seconds, lag_samples).

    Positive lag means candidate's content is shifted LATER than reference — i.e. this
    recovers dt_s directly when reference is the dt_s=0.0 render of the same tones.
    Uses an FFT-based full linear cross-correlation (via fftconvolve, matching the
    convolution approach already used in synth/modulator.py) rather than np.correlate's
    direct O(n^2) method, which is intractably slow at 720,000-sample (15 s @ 48 kHz)
    signals. `mode="full"` gives the same linear (non-circular) result np.correlate
    would, so no periodicity artefact can bias the argmax at the edges of a single
    15 s slot.
    """
    corr = fftconvolve(candidate, reference[::-1], mode="full")
    # corr[k] aligns candidate shifted by (k - (len(reference) - 1)) samples relative
    # to reference. argmax gives the best-alignment shift.
    lag_samples = int(np.argmax(corr)) - (len(reference) - 1)
    return lag_samples / fs, lag_samples


def main() -> int:
    text = _load_msg01_text()
    parts, base_freq_hz = _load_s3_parts()

    # dt_s=0.0 reference render of the SAME tone sequence MSG-01 uses everywhere in S3.
    reference = encoder.encode_message(
        text, base_freq_hz=float(base_freq_hz), dt_s=0.0, snr_db=None, sample_rate_hz=FS
    )

    rows = []
    for part in parts:
        label_dt_s = float(part["dt_s"])
        candidate = encoder.encode_message(
            text, base_freq_hz=float(base_freq_hz), dt_s=label_dt_s, snr_db=None,
            sample_rate_hz=FS,
        )
        measured_lag_s, lag_samples = _measured_lag_s(reference, candidate, FS)
        error_s = measured_lag_s - label_dt_s
        # G1 tolerance: within one sample (1/FS s) of the label.
        one_sample_s = 1.0 / FS
        passed = abs(error_s) <= one_sample_s + 1e-9
        rows.append({
            "part_index": part["part_index"],
            "label_dt_s": label_dt_s,
            "measured_lag_s": measured_lag_s,
            "lag_samples": lag_samples,
            "error_s": error_s,
            "pass": passed,
        })

    print(f"G1 placement proof -- S3 positive grid (MSG-01 = {text!r}, fs={FS} Hz, "
          f"base_freq_hz={base_freq_hz})")
    print(f"reference = dt_s=0.0 render of the same tone sequence\n")
    header = f"{'part':>4}  {'label dt_s':>10}  {'measured lag_s':>15}  {'error_s':>10}  {'result':>6}"
    print(header)
    print("-" * len(header))
    n_fail = 0
    for r in rows:
        result = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            n_fail += 1
        print(f"{r['part_index']:>4}  {r['label_dt_s']:>10.4f}  {r['measured_lag_s']:>15.4f}  "
              f"{r['error_s']:>10.4f}  {result:>6}")

    print()
    if n_fail:
        print(f"RESULT: {n_fail}/{len(rows)} parts FAILED placement (error exceeds one sample).")
    else:
        print("RESULT: all parts PASSED placement.")

    # Degeneracy check (G2, informational here): any two renders bit-identical?
    print()
    renders = {}
    for part in parts:
        label_dt_s = float(part["dt_s"])
        renders[part["part_index"]] = encoder.encode_message(
            text, base_freq_hz=float(base_freq_hz), dt_s=label_dt_s, snr_db=None,
            sample_rate_hz=FS,
        )
    dup_pairs = []
    idxs = list(renders.keys())
    for i in range(len(idxs)):
        for j in range(i + 1, len(idxs)):
            a, b = renders[idxs[i]], renders[idxs[j]]
            if np.array_equal(a, b):
                dup_pairs.append((idxs[i], idxs[j]))
    if dup_pairs:
        print(f"G2 (informational): {len(dup_pairs)} degenerate pair(s) -- bit-identical "
              f"renders under distinct labels: {dup_pairs}")
    else:
        print("G2 (informational): no bit-identical pairs found.")

    out_path = _HERE / "g1_s3_positive_grid_placement_check_results.json"
    out_path.write_text(json.dumps({
        "message": text,
        "fs_hz": FS,
        "base_freq_hz": base_freq_hz,
        "slot_length_s": SLOT_LENGTH_S,
        "rows": rows,
        "degenerate_pairs": dup_pairs,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")

    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
