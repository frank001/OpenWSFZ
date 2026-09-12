#!/usr/bin/env python3
"""THRESH-A ROW 0c: the four (f_inj, dt=0.16s) forced-read positions land exactly
on ft8_extract_llrs_at's own lattice (spec 3.3 ROW 0c).

Reproduces ft8_shim.c's own inverse mapping (src/OpenWSFZ.Ft8/Native/ft8_shim.c:
1856-1889), independently in Python, rather than trusting the spec's algebraic
argument in its own S0 unchecked:

    raw_freq_bin = freq_hz * symbol_period - min_bin      (ft8_shim.c:1883-1884)
    raw_time_bin = time_offset_s / symbol_period

symbol_period = 0.16 s: this is the SAME constant this programme already uses
as dll_common.SYMBOL_PERIOD_S (the confirmed one-symbol waterfall-origin
offset), independently corroborated here from ft8_shim.c's own monitor_config_t
(f_min=200.0f, ft8_shim.c:1871) and its comment "6.25 Hz/bin" (ft8_shim.c:571):
symbol_period = 1 / 6.25 = 0.16 s exactly.

min_bin = f_min / bin_hz = 200.0 / 6.25 = 32 (an exact integer bin count -- no
rounding ambiguity, since f_min and bin_hz are both round decimal constants in
the source with an exact quotient).

freq_osr = time_osr = 2 (ft8_shim.c:510-511, K_FREQ_OSR / K_TIME_OSR).

ROW 0c passes iff, for all four (f_inj, dt=0.16s) pairs:
    raw_freq_bin * freq_osr and raw_time_bin * time_osr
are integers to within 1e-6 (spec 3.3).
"""
from __future__ import annotations

SYMBOL_PERIOD_S = 0.16     # ft8_shim.c:571 "6.25 Hz/bin" -> 1/6.25
F_MIN_HZ = 200.0           # ft8_shim.c:1871, monitor_config_t.f_min
BIN_HZ = 6.25              # ft8_shim.c:571
MIN_BIN = F_MIN_HZ / BIN_HZ  # 32.0, exact
FREQ_OSR = 2               # ft8_shim.c:510, K_FREQ_OSR
TIME_OSR = 2               # ft8_shim.c:511, K_TIME_OSR

assert MIN_BIN == 32.0, MIN_BIN  # inherited-constant assertion, not prose (HK rule)

# The four rotated (message, freq) pairs, NT's scene verbatim (part_nt.MESSAGES).
INJECTED_FREQS_HZ = (700.0, 1300.0, 1900.0, 2500.0)
DT_TRUE_S = 0.0
SYMBOL_PERIOD_CORRECTION_S = 0.16  # dll_common.SYMBOL_PERIOD_S, the B-orig-A offset
TOL = 1e-6


def raw_bins(freq_hz: float, time_offset_s: float) -> tuple[float, float]:
    raw_freq_bin = freq_hz * SYMBOL_PERIOD_S - MIN_BIN
    raw_time_bin = time_offset_s / SYMBOL_PERIOD_S
    return raw_freq_bin, raw_time_bin


def check() -> dict:
    time_offset_s = DT_TRUE_S + SYMBOL_PERIOD_CORRECTION_S  # == extraction_time_offset_s(0.0) == 0.16
    rows = []
    all_ok = True
    for f in INJECTED_FREQS_HZ:
        raw_freq_bin, raw_time_bin = raw_bins(f, time_offset_s)
        fs = raw_freq_bin * FREQ_OSR
        ts = raw_time_bin * TIME_OSR
        f_ok = abs(fs - round(fs)) < TOL
        t_ok = abs(ts - round(ts)) < TOL
        ok = f_ok and t_ok
        all_ok &= ok
        rows.append({
            "freq_hz": f, "time_offset_s": time_offset_s,
            "raw_freq_bin": raw_freq_bin, "raw_freq_bin_x_osr": fs, "freq_ok": f_ok,
            "raw_time_bin": raw_time_bin, "raw_time_bin_x_osr": ts, "time_ok": t_ok,
            "row_ok": ok,
        })
    return {"pass": bool(all_ok), "rows": rows}


if __name__ == "__main__":
    import json
    result = check()
    print(json.dumps(result, indent=2))
    print("ROW 0c:", "PASS" if result["pass"] else "STOP -- sub-lattice gain would contaminate the forced read")
