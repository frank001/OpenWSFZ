#!/usr/bin/env python3
"""Task 2.3 (n1-extract-llrs-at-position): isolated unit-check of the inverse-mapping
arithmetic implemented in ft8_shim.c's ft8_extract_llrs_at, BEFORE trusting it wired to
the full export (design.md D2/Risks last bullet).

For a handful of known (freq_offset, freq_sub, time_offset, time_sub) quadruples, runs
them through the FORWARD formula (ft8_shim.c's own "Frequency, time offset, and SNR"
block, the same one ft8_decode_all uses to report a candidate's freq_hz/dt) to get
(freq_hz, time_offset_s), then through the INVERSE formula ft8_extract_llrs_at itself
implements, and confirms the exact same quadruple comes back -- including at least one
case with a negative time_offset (a candidate near the start of the buffer), to exercise
the negative-modulo normalisation.

Pure Python, no DLL required -- this is a transcription check of the arithmetic itself,
mirrored line-for-line from the C source. It does NOT prove the compiled C code is
correct (task 2.4's round-trip-against-a-real-candidate check, run through the actual
built DLL, is the mechanical proof of that) -- design.md's own Risks section names this
as the acknowledged limitation of a Python-side mirror: "two independent inverse-mapping
implementations ... can drift", which is exactly why 2.4 is not skipped.

float32 throughout (numpy), matching the C `float` arithmetic exactly -- using Python's
native double precision here would let lroundf's rounding-boundary behaviour silently
diverge from the compiled code's.
"""
from __future__ import annotations

import numpy as np

# ── Constants, mirrored from native/ft8_lib_vendor/ft8/constants.h and
#    monitor_init() (native/ft8_lib_build/patched/common/monitor.c) for the exact
#    monitor_config_t ft8_decode_all / ft8_extract_llrs_at both use:
#    { f_min=200.0f, f_max=3000.0f, sample_rate=12000, time_osr=2, freq_osr=2,
#      protocol=FTX_PROTOCOL_FT8 }.
F32 = np.float32
SYMBOL_PERIOD = F32(0.160)          # FT8_SYMBOL_PERIOD
F_MIN = F32(200.0)
MIN_BIN = int(F_MIN * SYMBOL_PERIOD)  # monitor_init: (int)(cfg->f_min * symbol_period) = 32
FREQ_OSR = 2                          # K_FREQ_OSR
TIME_OSR = 2                          # K_TIME_OSR


def forward(time_offset: int, freq_offset: int, time_sub: int, freq_sub: int):
    """ft8_shim.c's own forward mapping (the "Frequency, time offset, and SNR" block)."""
    freq_hz = (F32(MIN_BIN) + F32(freq_offset) + F32(freq_sub) / F32(FREQ_OSR)) / SYMBOL_PERIOD
    time_offset_s = (F32(time_offset) + F32(time_sub) / F32(TIME_OSR)) * SYMBOL_PERIOD
    return float(freq_hz), float(time_offset_s)


def _c_trunc_div(a: int, b: int) -> int:
    """C's integer / for a possibly-negative dividend, positive divisor: truncate toward
    zero (Python's // floors, which differs for negative a)."""
    q = abs(a) // b
    return q if a >= 0 else -q


def _c_trunc_mod(a: int, b: int) -> int:
    return a - _c_trunc_div(a, b) * b


def inverse(freq_hz: float, time_offset_s: float):
    """ft8_extract_llrs_at's own inverse mapping, transcribed line-for-line (ft8_shim.c)."""
    raw_freq_bin = F32(freq_hz) * SYMBOL_PERIOD - F32(MIN_BIN)
    raw_time_bin = F32(time_offset_s) / SYMBOL_PERIOD

    # lroundf: round-half-away-from-zero on a float32 value, result as a (long) int.
    total_freq_sub = int(np.round(raw_freq_bin * F32(FREQ_OSR)))
    total_time_sub = int(np.round(raw_time_bin * F32(TIME_OSR)))

    freq_offset = _c_trunc_div(total_freq_sub, FREQ_OSR)
    freq_sub = _c_trunc_mod(total_freq_sub, FREQ_OSR)
    time_offset = _c_trunc_div(total_time_sub, TIME_OSR)
    time_sub = _c_trunc_mod(total_time_sub, TIME_OSR)

    if freq_sub < 0:
        freq_sub += FREQ_OSR
        freq_offset -= 1
    if time_sub < 0:
        time_sub += TIME_OSR
        time_offset -= 1

    return time_offset, freq_offset, time_sub, freq_sub


# (time_offset, freq_offset, time_sub, freq_sub) -- covers: interior position, an
# oversampled sub-bin/sub-block > 0, a position near the start of the buffer with a
# NEGATIVE time_offset (the case the negative-modulo normalisation exists for), and a
# position near the num_bins edge (MIN_BIN=32, num_bins=449 for this passband).
QUADRUPLES = [
    (0, 100, 0, 0),
    (50, 200, 1, 1),
    (-3, 10, 1, 0),
    (-1, 0, 0, 0),
    (90, 448, 0, 1),
    (12, 5, 1, 1),
]


def main() -> int:
    print("=" * 78)
    print("Task 2.3: isolated inverse-mapping arithmetic check (pure Python, no DLL)")
    print("MIN_BIN=%d FREQ_OSR=%d TIME_OSR=%d SYMBOL_PERIOD=%s"
          % (MIN_BIN, FREQ_OSR, TIME_OSR, SYMBOL_PERIOD))
    print("=" * 78)

    failures = 0
    for quad in QUADRUPLES:
        time_offset, freq_offset, time_sub, freq_sub = quad
        freq_hz, time_offset_s = forward(time_offset, freq_offset, time_sub, freq_sub)
        got = inverse(freq_hz, time_offset_s)
        ok = got == quad
        status = "PASS" if ok else "FAIL"
        print("  [%s] in=%s -> freq_hz=%.6f time_offset_s=%.6f -> out=%s"
              % (status, quad, freq_hz, time_offset_s, got))
        if not ok:
            failures += 1

    print()
    if failures:
        print("RESULT: FAIL -- %d/%d quadruple(s) did not round-trip" % (failures, len(QUADRUPLES)))
        return 1
    print("RESULT: PASS -- all %d quadruples round-trip exactly, including the "
          "negative-time_offset case." % len(QUADRUPLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
