#!/usr/bin/env python3
"""NR-TAX frozen definitions (spec 4179a1e3 + Amendment 1 section 8, 001bf76e). V3: THIS FILE IS COMMITTED BEFORE ANY CATEGORY IS COMPUTED ON ANY POPULATION.
Pure functions and constants; no data is read here except the two native source files whose constants are asserted (Edge-F).

Geometry (spec section 2): overlapping |df| < 50 Hz, near 50 <= |df| < 100 Hz, stronger = SNR_n >= SNR_r, much stronger (near channel) = SNR_n - SNR_r >= 10 dB.
Subtracted (Amendment 1 A1.1): the neighbour was hit in batch 1 or 2 AND `SubtractionPass.IsReencodable` accepts OUR decoded text (no '<', at least 3 tokens).
Edge-T: candidate position = REF dt + delta_p must lie within one symbol (0.16 s) of either end of [-1.60, 3.12] s, or outside.  Edge-F: REF base frequency within one bin (6.25 Hz) of
either end of [137.5, 3034.375] Hz or outside.  Strength line: strong = REF SNR >= -10 dB.
Categories, first match wins: E, CS, CU-d, CU-u, CW, NC, IS, IW.
READING NOTE (stated, not hidden): spec section 3 words CU-d as "decoded in batch 3 or 4" but Amendment 1 says B1 "moves rows from CS into CU-d or CU-u", which only works if CU-d means
"a stronger overlapping neighbour that we DECODED (any batch) but did not subtract". A batch-1/2 neighbour that fails IsReencodable is exactly such a neighbour. CU-d is therefore:
>= 1 stronger overlapping neighbour decoded by us; none subtracted.  The sub-count by reason (batch 3/4 vs batch 1/2 not re-encodable) is reported.
"""
from __future__ import annotations

import re

SYMBOL_PERIOD_S = 0.16
BIN_HZ = 6.25
OVERLAP_HZ, NEAR_HZ, MUCH_STRONGER_DB = 50.0, 100.0, 10.0
STRONG_SNR_DB = -10
DELTA_P = 0.6                              # GAP-RELOCATE deltas.json (frozen), +-0.1 s sensitivity
T_LO, T_HI = -10 * SYMBOL_PERIOD_S, (19 + 0.5) * SYMBOL_PERIOD_S          # decode.c:305 (time_offset -10..19) with time_sub 0..1 of time_osr 2
LATE_LIMIT_S = 15.0 - 79 * SYMBOL_PERIOD_S                                 # 15 s buffer minus the 12.64 s signal = 2.36 s (soft limit, sensitivity only)
F_MIN, F_MAX = 140.0, 3075.0                                               # ft8_shim.c:1706 and :2134
MIN_BIN = int(F_MIN * SYMBOL_PERIOD_S)                                     # monitor.c:115
MAX_BIN = int(F_MAX * SYMBOL_PERIOD_S) + 1                                 # monitor.c:116
NUM_BINS = MAX_BIN - MIN_BIN
F_LO = MIN_BIN / SYMBOL_PERIOD_S                                           # freq_offset 0, freq_sub 0
F_HI = (MIN_BIN + (NUM_BINS - 8) + 0.5) / SYMBOL_PERIOD_S                  # decode.c:309 (freq_offset + 7 < num_bins), freq_sub 1 of freq_osr 2
CATEGORIES = ["E", "CS", "CU-d", "CU-u", "CW", "NC", "IS", "IW"]
assert (MIN_BIN, MAX_BIN, NUM_BINS) == (22, 493, 471) and F_LO == 137.5 and abs(F_HI - 3034.375) < 1e-9
assert abs(T_LO - (-1.6)) < 1e-12 and abs(T_HI - 3.12) < 1e-12 and abs(LATE_LIMIT_S - 2.36) < 1e-9


def assert_native_constants(main_tree):
    """Assert the two limits against the native source (not prose)."""
    t = open(main_tree + "/src/OpenWSFZ.Ft8/Native/ft8_shim.c", encoding="utf-8").read()
    assert len(re.findall(r"\.f_min = 140\.0f, \.f_max = 3075\.0f", t)) == 2, "f_min/f_max are not the two 140/3075 sites"
    d = open(main_tree + "/native/ft8_lib_build/patched/ft8/decode.c", encoding="utf-8").read()
    assert "candidate.time_offset = -10; candidate.time_offset < 20" in d, "time_offset range changed"
    assert "(candidate.freq_offset + num_tones - 1) < wf->num_bins" in d, "freq_offset bound changed"
    m = open(main_tree + "/native/ft8_lib_build/patched/common/monitor.c", encoding="utf-8").read()
    assert "me->min_bin = (int)(cfg->f_min * symbol_period);" in m and "me->max_bin = (int)(cfg->f_max * symbol_period) + 1;" in m


def reencodable(text):
    """SubtractionPass.IsReencodable: not a hash placeholder, at least 3 space-separated tokens."""
    return "<" not in text and len(text.split()) >= 3


def edge_t(dt, delta_p=DELTA_P, lo_margin=SYMBOL_PERIOD_S, hi_margin=SYMBOL_PERIOD_S, hi=T_HI):
    pos = dt + delta_p
    return pos <= T_LO + lo_margin or pos >= hi - hi_margin


def edge_f(freq):
    return freq <= F_LO + BIN_HZ or freq >= F_HI - BIN_HZ


def categorise(row, neigh, overlap=OVERLAP_HZ, much=MUCH_STRONGER_DB, delta_p=DELTA_P, late=False):
    """row: dict(snr, freq, dt).  neigh: list of dict(snr, freq, decoded: bool, batch: int, subtracted: bool) = the OTHER REF rows of the same cycle.
    Returns (category, info) with info = {mixed_undecoded_stronger: bool}."""
    if edge_t(row["dt"], delta_p, hi_margin=(T_HI - LATE_LIMIT_S) if late else SYMBOL_PERIOD_S) or edge_f(row["freq"]):
        return "E", {"mixed": False}
    ov = [n for n in neigh if abs(n["freq"] - row["freq"]) < overlap]
    st = [n for n in ov if n["snr"] >= row["snr"]]
    if st:
        undec = any(not n["decoded"] for n in st)
        if any(n["subtracted"] for n in st):
            return "CS", {"mixed": undec}
        if any(n["decoded"] for n in st):
            return "CU-d", {"mixed": undec}
        return "CU-u", {"mixed": False}
    if ov:
        return "CW", {"mixed": False}
    if any(overlap <= abs(n["freq"] - row["freq"]) < NEAR_HZ and n["snr"] - row["snr"] >= much for n in neigh):
        return "NC", {"mixed": False}
    return ("IS" if row["snr"] >= STRONG_SNR_DB else "IW"), {"mixed": False}
