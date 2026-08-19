#!/usr/bin/env python3
"""G1 (placement) + G2 (distinctness) over the FULL DT grid, offline, no decoder, no device.

Route B build spec (2026-08-19-1630-architect-to-qa-route-b-negative-dt-build-spec.md),
Sec8 step 2: after contracts C1/C2 land in synth/modulator.py, prove placement holds across
the extended grid this scenario pair actually needs -- S3's existing positive sweep
[0.0, 2.7] and S3b's negative sweep [-2.7, 0.0] -- using extended=True uniformly (a strict
superset of the single-slot contract; see modulator.modulate's docstring and
test_extended_matches_single_slot_when_placement_already_fits).

Supersedes g1_s3_positive_grid_placement_check.py's SCOPE. That script's own result is now
historical: it proves the DEFECT existed (§8 step 1), and with C1 landed it now correctly
raises ValueError on S3 parts 8/9 instead of silently mis-placing them (verified separately;
left as-is, not deleted -- it is the "before" evidence). This script is the "after": every
part in both grids places to one sample using extended=True, and G2 confirms parts 8/9 are
no longer degenerate.

Usage (from qa/rr-study/):
    python g1_g2_full_grid_placement_check.py
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
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

FS = DEFAULT_SAMPLE_RATE_HZ

_SCENARIO_FILES = {
    "S3":  "s3-dt-offset.json",
    "S3b": "s3b-dt-boundary.json",
}


def _load_msg01_text() -> str:
    data = json.loads((_HERE / "scenarios" / "study-messages.json").read_text(encoding="utf-8"))
    for m in data.get("messages", []):
        if m["id"] == "MSG-01":
            return m["text"]
    sys.exit("ERROR: MSG-01 not found in study-messages.json")


def _load_parts(scenario_id: str) -> tuple[list[dict], float]:
    path = _HERE / "scenarios" / _SCENARIO_FILES[scenario_id]
    scenario = json.loads(path.read_text(encoding="utf-8"))
    return scenario["parts"], float(scenario["fixed"]["base_freq_hz"])


def _measured_dt_s(candidate: np.ndarray, buffer_start_s: float,
                    reference: np.ndarray, fs: int) -> float:
    """Same black-box placement-proof method as g1_s3_positive_grid_placement_check.py's
    _measured_lag_s, generalised to a non-zero buffer_start_s (see that script / the
    Sec8-step-1 report for the derivation)."""
    corr = fftconvolve(candidate, reference[::-1], mode="full")
    lag_samples = int(np.argmax(corr)) - (len(reference) - 1)
    return buffer_start_s + lag_samples / fs


def _align(buffer: np.ndarray, buffer_start_s: float,
           window_start_s: float, window_len_samples: int, fs: int) -> np.ndarray:
    """Zero-pad `buffer` onto one shared absolute-sample window starting at
    `window_start_s`, so renders of different length/offset can be compared bit-for-bit."""
    out = np.zeros(window_len_samples, dtype=np.float64)
    offset = int(round((buffer_start_s - window_start_s) * fs))
    lo, hi = max(0, offset), min(window_len_samples, offset + len(buffer))
    if hi > lo:
        out[lo:hi] = buffer[lo - offset: hi - offset]
    return out


def main() -> int:
    text = _load_msg01_text()

    rows: list[dict] = []
    renders: dict[tuple[str, int], tuple[np.ndarray, float]] = {}
    labels: dict[tuple[str, int], float] = {}
    for scenario_id in ("S3", "S3b"):
        parts, base_freq_hz = _load_parts(scenario_id)
        for part in parts:
            label_dt_s = float(part["dt_s"])
            key = (scenario_id, part["part_index"])
            buffer, buffer_start_s = encoder.encode_message(
                text, base_freq_hz=base_freq_hz, dt_s=label_dt_s, snr_db=None,
                sample_rate_hz=FS, extended=True,
            )
            renders[key] = (buffer, buffer_start_s)
            labels[key] = label_dt_s
            rows.append({"scenario": scenario_id, "part_index": part["part_index"],
                         "label_dt_s": label_dt_s})

    # Reference: dt_s=0.0, extended=True -- buffer_start_s is 0.0 and content is
    # byte-identical to the non-extended render (contract, unit-tested separately).
    ref_buffer, ref_start_s = encoder.encode_message(
        text, base_freq_hz=1500.0, dt_s=0.0, snr_db=None, sample_rate_hz=FS, extended=True,
    )
    assert ref_start_s == 0.0

    print(f"G1 placement proof -- S3 + S3b full grid, extended=True (MSG-01={text!r}, "
          f"fs={FS} Hz)")
    header = (f"{'scen':>4} {'part':>4}  {'label dt_s':>10}  {'measured dt_s':>14}  "
              f"{'error_s':>10}  {'result':>6}")
    print(header)
    print("-" * len(header))
    n_fail = 0
    for row in rows:
        buffer, buffer_start_s = renders[(row["scenario"], row["part_index"])]
        measured = _measured_dt_s(buffer, buffer_start_s, ref_buffer, FS)
        error = measured - row["label_dt_s"]
        passed = abs(error) <= 1.0 / FS + 1e-9
        row["measured_dt_s"] = measured
        row["error_s"] = error
        row["pass"] = passed
        if not passed:
            n_fail += 1
        result = "PASS" if passed else "FAIL"
        print(f"{row['scenario']:>4} {row['part_index']:>4}  {row['label_dt_s']:>10.4f}  "
              f"{measured:>14.4f}  {error:>10.4f}  {result:>6}")

    print()
    if n_fail:
        print(f"RESULT: {n_fail}/{len(rows)} parts FAILED placement.")
    else:
        print(f"RESULT: all {len(rows)} parts PASSED placement (S3: 10, S3b: 10).")

    # G2: distinctness across the FULL grid, aligned onto one shared absolute window so
    # renders of different length/offset are compared bit-for-bit rather than trivially
    # "not equal" because their arrays happen to be different shapes.
    print()
    keys = list(renders.keys())
    starts = [renders[k][1] for k in keys]
    window_start_s = min(0.0, *starts)
    window_end_samples = max(
        int(round(renders[k][1] * FS)) + len(renders[k][0]) for k in keys
    )
    window_len = window_end_samples - int(round(window_start_s * FS))
    aligned = {
        k: _align(renders[k][0], renders[k][1], window_start_s, window_len, FS)
        for k in keys
    }

    dup_pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if np.array_equal(aligned[keys[i]], aligned[keys[j]]):
                dup_pairs.append((keys[i], keys[j]))

    # A duplicate pair sharing the SAME label (e.g. S3 part 0 vs S3b part 0, both
    # dt_s=0.0) is EXPECTED, not a defect. A duplicate pair with DIFFERENT labels is
    # exactly the S3 parts-8/9 defect pattern this whole thread is about.
    unexpected = [(a, b) for a, b in dup_pairs if labels[a] != labels[b]]

    if dup_pairs:
        print(f"G2: {len(dup_pairs)} bit-identical pair(s) total "
              f"({len(dup_pairs) - len(unexpected)} same-label/expected, "
              f"{len(unexpected)} DIFFERENT-label/UNEXPECTED):")
        for a, b in dup_pairs:
            tag = "expected (same label)" if labels[a] == labels[b] else "UNEXPECTED -- DEFECT"
            print(f"    {a} (label {labels[a]}) == {b} (label {labels[b]})  [{tag}]")
    else:
        print("G2: no bit-identical pairs at all across the full grid.")

    if unexpected:
        n_fail += len(unexpected)

    out_path = _HERE / "g1_g2_full_grid_placement_check_results.json"
    out_path.write_text(json.dumps({
        "message": text,
        "fs_hz": FS,
        "rows": rows,
        "duplicate_pairs": [
            {"a": f"{a[0]}#{a[1]}", "b": f"{b[0]}#{b[1]}",
             "label_a": labels[a], "label_b": labels[b], "expected": labels[a] == labels[b]}
            for a, b in dup_pairs
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")

    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
