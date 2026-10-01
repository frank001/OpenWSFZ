#!/usr/bin/env python3
"""GAP-LOCATE Leg F/K: the 9-cell forced-read neighbourhood.

Spec sec.2 Leg F: "Try the nearest lattice cell and its 8 neighbours, +-1 step in time
and in frequency: 9 cells."

Reuses thresh-a/row0c_lattice.py's independently-derived inverse mapping (ft8_shim.c
1856-1889), verbatim constants (HK-018), rather than re-deriving:
    raw_freq_bin = freq_hz * SYMBOL_PERIOD_S - MIN_BIN      (ft8_shim.c:1883-1884)
    raw_time_bin = time_offset_s / SYMBOL_PERIOD_S
scaled by FREQ_OSR / TIME_OSR (=2 each) to reach the actual addressable (oversampled)
lattice. One lattice step is therefore:
    freq step = BIN_HZ / FREQ_OSR   = 6.25 / 2 = 3.125 Hz
    time step = SYMBOL_PERIOD_S / TIME_OSR = 0.16 / 2 = 0.08 s

snap_and_neighbours(freq_hz, time_offset_s) rounds the requested position to its
nearest lattice cell (so the centre cell is never a sub-lattice-interpolated read --
the THRESH-A ROW 0c concern: a non-lattice-aligned position silently gains via
interpolation, contaminating the read) and returns that cell plus its 8 neighbours,
each as an EXACT lattice-aligned (freq_hz, time_offset_s) pair.
"""
from __future__ import annotations

SYMBOL_PERIOD_S = 0.16
F_MIN_HZ = 200.0
BIN_HZ = 6.25
MIN_BIN = F_MIN_HZ / BIN_HZ  # 32.0, exact
FREQ_OSR = 2
TIME_OSR = 2

assert MIN_BIN == 32.0, MIN_BIN  # inherited-constant assertion (HK rule), not prose


def _to_osr_bins(freq_hz: float, time_offset_s: float) -> tuple[int, int]:
    raw_freq_bin = freq_hz * SYMBOL_PERIOD_S - MIN_BIN
    raw_time_bin = time_offset_s / SYMBOL_PERIOD_S
    return round(raw_freq_bin * FREQ_OSR), round(raw_time_bin * TIME_OSR)


def _from_osr_bins(freq_bin_osr: int, time_bin_osr: int) -> tuple[float, float]:
    raw_freq_bin = freq_bin_osr / FREQ_OSR
    raw_time_bin = time_bin_osr / TIME_OSR
    freq_hz = (raw_freq_bin + MIN_BIN) / SYMBOL_PERIOD_S
    time_offset_s = raw_time_bin * SYMBOL_PERIOD_S
    return freq_hz, time_offset_s


def snap_and_neighbours(freq_hz: float, time_offset_s: float) -> list[dict]:
    """Returns 9 dicts, centre first, each {freq_hz, time_offset_s, is_centre,
    d_freq_cells, d_time_cells}, all exactly lattice-aligned."""
    fb0, tb0 = _to_osr_bins(freq_hz, time_offset_s)
    cells = []
    order = [(0, 0)] + [(df, dt) for df in (-1, 0, 1) for dt in (-1, 0, 1) if (df, dt) != (0, 0)]
    for df, dt in order:
        f, t = _from_osr_bins(fb0 + df, tb0 + dt)
        cells.append({
            "freq_hz": f, "time_offset_s": t,
            "is_centre": (df == 0 and dt == 0),
            "d_freq_cells": df, "d_time_cells": dt,
        })
    return cells


if __name__ == "__main__":
    for c in snap_and_neighbours(1234.5, 0.653 + SYMBOL_PERIOD_S):
        print(c)
