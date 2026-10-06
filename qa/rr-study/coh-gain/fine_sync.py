#!/usr/bin/env python3
"""COH-GAIN (A' step 1, Architect spec 2026-10-06-1625 sec.3): the per-signal fine frequency/time estimator. The one NEW piece.

PROVENANCE / CLEAN-ROOM: written from FT8's public constants (tone spacing 6.25 Hz, symbol 0.16 s, the Costas array [3,1,4,0,6,5,2] at
symbols 0-6 / 36-42 / 72-78) and standard coherent-correlation theory, reusing the baseband front end and DFT matrix of OUR OWN
coherent_extract.py (clean-room by its header) and the method of OUR OWN sync_refiner.c costas_coherent_sum. NO WSJT-X source.

Method. For a signal anchored at (carrier f0, symbol-0 time t0), downconvert once at f0 (coherent_extract.downconvert_decimate, 2 kHz).
For each hypothesis (df in [-2.0, +2.0] Hz step 0.1, dt in [-0.12, +0.12] s step 5 ms) the objective is the magnitude of the COMPLEX sum, over
the known symbols, of that symbol's correlation against its expected tone, measured at the carrier f0+df and symbol start t0+dt:

    S(df, dt) = | sum_p  X_p(df, dt)[tone_p] |        X_p[tone] = sum_n  bb[start_dt + 320 p + n] * exp(-j 2 pi (df) (start_dt+320p+n)/2000)
                                                                          * exp(-j 2 pi tone n / 320)

FT8's tone spacing times its symbol period is exactly 1, so a per-symbol reference that restarts at phase zero is phase-continuous with a global
one at the true carrier (coherent_extract's derivation); a residual df rotates the phase by 2 pi df 0.16 per symbol, so the COHERENT sum across the
three Costas blocks (spanning 72 symbols) peaks sharply at the true df. DATA-FREE: sync mode uses only the 21 Costas symbols, so it is a buildable
estimator. ORACLE mode uses all 79 tones of a supplied tone sequence (the re-encoded WSJT-X message) and is NOT a buildable decoder.

Efficiency (identical result to the naive loop): the df shift of an already-baseband stream is a phase ramp, so
    X_p(df, k) = [ sum_n seg0[k, p, n] * ref_p[n] * E[df, n] ] * exp(-j 2 pi df (start_k + 320 p)/2000),   E[df, n] = exp(-j 2 pi df n / 2000)
which is one (K*P, 320) x (320, n_df) matrix product. The argmax takes the FIRST maximum (deterministic), with no interpolation finer than the grid.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n2-coherent-llr-extractor"))
import coherent_extract as CE  # noqa: E402

RATE_HZ = CE.RATE_FINE_HZ                      # 2000
SPS = CE.SPS_2K                                # 320 samples per symbol
N_SYM = CE.N_SYM                               # 79
COSTAS = (3, 1, 4, 0, 6, 5, 2)                 # FT8's public Costas array
COSTAS_STARTS = (0, 36, 72)
SYNC_SYMBOLS = {s + i: COSTAS[i] for s in COSTAS_STARTS for i in range(7)}   # 21 symbols -> tone

DF_MAX_HZ = 2.0
DF_STEP_HZ = 0.1
DT_MAX_S = 0.12
DT_STEP_S = 0.005
DT_STEP_SAMPLES = int(round(DT_STEP_S * RATE_HZ))          # 10 samples at 2 kHz
N_DF = int(round(2 * DF_MAX_HZ / DF_STEP_HZ)) + 1          # 41
N_DT = int(round(2 * DT_MAX_S / DT_STEP_S)) + 1            # 49
DF_GRID = np.round(np.linspace(-DF_MAX_HZ, DF_MAX_HZ, N_DF), 10)
DT_STEPS = np.arange(-(N_DT // 2), N_DT // 2 + 1)           # -24 .. +24
DT_GRID_S = DT_STEPS * DT_STEP_S
# inherited-constant assertions (HK rule: in the code, not in prose)
assert (N_DF, N_DT, DT_STEP_SAMPLES, SPS, N_SYM, len(SYNC_SYMBOLS)) == (41, 49, 10, 320, 79, 21)
assert abs(DF_GRID[0] + 2.0) < 1e-12 and abs(DF_GRID[-1] - 2.0) < 1e-12 and DF_GRID[N_DF // 2] == 0.0

_PAD = SPS * 4 + DT_STEP_SAMPLES * (N_DT // 2) + 8        # zero padding so any hypothesised segment gather is in range
_N_IDX = np.arange(SPS)
_E = np.exp(-2j * np.pi * np.outer(DF_GRID, _N_IDX) / RATE_HZ)   # (n_df, 320)


def symbol_start_samples(anchor_dt_s: float) -> int:
    """The decimated-stream index of symbol 0's start for an anchor, EXACTLY coherent_extract.extract_variants' own formula."""
    return int(round(anchor_dt_s * RATE_HZ)) + CE.TIME_ORIGIN_CORRECTION_SAMPLES_2K


def anchor_dt_for_step(anchor_dt_s: float, dt_step_index: int) -> float:
    """The anchor_dt_s to pass to extract_variants so its symbol start equals the hypothesis' start exactly (whole 2 kHz samples)."""
    return (int(round(anchor_dt_s * RATE_HZ)) + dt_step_index * DT_STEP_SAMPLES) / RATE_HZ


def objective_surface(bb: np.ndarray, anchor_dt_s: float, tones_by_symbol: dict) -> np.ndarray:
    """|coherent sum| over the given known symbols on the (n_df, n_dt) grid. bb: complex baseband @ 2 kHz at the ANCHOR carrier."""
    syms = np.array(sorted(tones_by_symbol))
    tones = np.array([tones_by_symbol[int(s)] for s in syms])
    s0 = symbol_start_samples(anchor_dt_s)
    bbp = np.zeros(len(bb) + 2 * _PAD, dtype=np.complex128)
    bbp[_PAD:_PAD + len(bb)] = bb
    starts = s0 + DT_STEPS * DT_STEP_SAMPLES                                  # (K,)
    idx = (starts[:, None, None] + syms[None, :, None] * SPS + _N_IDX[None, None, :]) + _PAD   # (K, P, 320)
    seg = bbp[idx]                                                            # (K, P, 320), zero outside the stream
    ref = CE._DFT_MAT[:, tones].T                                             # (P, 320): exp(-j 2 pi tone n/320) per known symbol
    y = (seg * ref[None, :, :]).reshape(-1, SPS)                              # (K*P, 320)
    x = (y @ _E.T).reshape(len(starts), len(syms), N_DF)                      # (K, P, n_df): per-symbol correlation at each df
    abs_pos = (starts[:, None] + syms[None, :] * SPS).astype(np.float64)      # (K, P) absolute 2 kHz index of each symbol's start
    phase = np.exp(-2j * np.pi * DF_GRID[None, None, :] * abs_pos[:, :, None] / RATE_HZ)
    s = (x * phase).sum(axis=1)                                               # (K, n_df): the COMPLEX sum over the known symbols
    return np.abs(s).T                                                        # (n_df, n_dt)


def estimate(pcm: np.ndarray, anchor_freq_hz: float, anchor_dt_s: float, tones_by_symbol: dict | None = None) -> dict:
    """Fine-sync estimate. tones_by_symbol=None -> the DATA-FREE Costas estimator (21 symbols); otherwise the ORACLE over the symbols given.
    Returns est_df_hz, est_dt_s (offsets from the anchor), the step index of the dt, whether the argmax sits on a window edge, and the peak."""
    bb = CE.downconvert_decimate(pcm, anchor_freq_hz)
    surf = objective_surface(bb, anchor_dt_s, SYNC_SYMBOLS if tones_by_symbol is None else tones_by_symbol)
    i_df, i_dt = np.unravel_index(int(np.argmax(surf)), surf.shape)           # first maximum: deterministic
    return {"est_df_hz": float(DF_GRID[i_df]), "est_dt_s": float(DT_GRID_S[i_dt]), "dt_step": int(DT_STEPS[i_dt]),
            "edge": bool(i_df in (0, N_DF - 1) or i_dt in (0, N_DT - 1)), "peak": float(surf[i_df, i_dt])}


def oracle_tones(tones79) -> dict:
    """All 79 symbols of a transmitted tone sequence, for the C3* oracle."""
    assert len(tones79) == N_SYM
    return {p: int(tones79[p]) for p in range(N_SYM)}
