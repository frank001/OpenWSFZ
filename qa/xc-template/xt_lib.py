#!/usr/bin/env python3
"""XC-TEMPLATE library (spec arch/cross-cycle-prior 2e133bc0 + Amendment 1 section 10 + Amendment 2 section 11; QA (k) review f1fb7125).  QA tooling: no src/ or native/ change, no replay, no station.
Pure functions plus the grid search on a decimated baseband (the self-test drives them on synthetic audio).  HK-037: message text is read inside the scorer for tones only, never persisted.

THE DETECTOR.  A known message fixes all 79 tones.  At a position (f, t): X = correlate_symbols(downconvert_decimate(pcm, f), start(t)) (qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py, as cf_fbid),
P_k[b] = |X_k[b]|^2;  S_E = (1/79) sum_k P_k[tone_k] / ((1/8) sum_b P_k[b])  (noise alone ~ 1; a perfect signal approaches 8; a symbol with no power contributes 1).
SEARCH (A1.3): the prior's position +-3.0 Hz in 0.5 Hz steps (13; inside the +-3.125 Hz gate) x +-0.12 s in 0.01 s steps (25) = 325 positions; one downconvert at the centre frequency, the other frequencies by shifting the
decimated baseband (equal to a direct downconvert to 6e-4 of the maximum at 10 Hz, so far better here).  S_E* = the maximum over the grid, with its argmax.  The null uses the IDENTICAL window around its own centre, so
the gate (|df| <= 3.125 Hz, |dt| <= 0.12 s) is satisfied by every null maximum by construction (A1.2).  E1 TRUTH CHECK: the argmax must also lie within the gate of the row's OWN WSJT-X position.
DETECTED <=> S_E* >= T_E and (E1 / P rows) the truth check; hashed E1 rows count as NOT detected."""
from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------------------------- frozen constants
SEED = 20261113
B_BOOT = 2000
SPS_S = 0.16                        # FT8 symbol length
FS_OUT = 2000                       # decimated baseband rate (coherent_extract.RATE_FINE_HZ, asserted in the scorer)
N_SYM, N_TONES = 79, 8
DF_STEP_HZ, DF_HALF_HZ = 0.5, 3.0   # 13 frequency steps, inside the gate
DT_STEP_S, DT_HALF_S = 0.01, 0.12   # 25 start times
GATE_DF_HZ, GATE_DT_S = 3.125, 0.12 # cf_fbid.DF_GRID_HZ extent and DT_HALF_WINDOW_S
FA_BUDGET = 0.021                   # cf_uprime.OBSERVED_DELTA_U_1009: the per-cycle U budget
V_POS = 0.80                        # cf_uprime.MIN_PRESENT_RATE
CLOSE_PP, BUILD_PP = 0.4, 0.4       # G bars (spec section 5)
N_E1_FULL, N_REF = 520, 13997
assert (SEED, B_BOOT, DF_HALF_HZ, DT_HALF_S, GATE_DF_HZ, GATE_DT_S, FA_BUDGET, V_POS, CLOSE_PP, N_E1_FULL, N_REF) == (20261113, 2000, 3.0, 0.12, 3.125, 0.12, 0.021, 0.80, 0.4, 520, 13997)


def df_grid():
    n = int(round(DF_HALF_HZ / DF_STEP_HZ))
    return [k * DF_STEP_HZ for k in range(-n, n + 1)]


def dt_grid():
    n = int(round(DT_HALF_S / DT_STEP_S))
    return [k * DT_STEP_S for k in range(-n, n + 1)]


assert len(df_grid()) == 13 and len(dt_grid()) == 25 and max(df_grid()) <= GATE_DF_HZ and max(dt_grid()) <= GATE_DT_S + 1e-9


def s_e(X: np.ndarray, tones) -> float:
    """S_E from the (79, 8) complex correlations X and the 79 known tones: the mean over symbols of P[tone] / mean_b P (a symbol without power counts 1)."""
    P = X.real ** 2 + X.imag ** 2
    den = P.sum(axis=1) / N_TONES
    num = P[np.arange(N_SYM), np.asarray(tones)]
    r = np.where(den > 0, num / np.where(den > 0, den, 1.0), 1.0)
    return float(r.mean())


def shift_baseband(bb: np.ndarray, delta_hz: float) -> np.ndarray:
    """the decimated baseband of a carrier delta_hz higher (equal to downconvert_decimate at f + delta to ~6e-4 of the maximum at 10 Hz)."""
    if delta_hz == 0.0:
        return bb
    return bb * np.exp(-2j * np.pi * delta_hz * np.arange(len(bb)) / FS_OUT)


def search(CE, pcm: np.ndarray, f_c: float, dt_c: float, tones, calib_s: float):
    """S_E* over the window around (f_c, dt_c) (dt in WSJT-X's convention; calib_s = TA-CHECK's frozen start-minus-dt), and the argmax as ABSOLUTE (f, dt)."""
    bb = CE.downconvert_decimate(pcm, float(f_c))
    best, arg = -1.0, None
    for d in df_grid():
        sb = shift_baseband(bb, d)
        for e in dt_grid():
            smp = int(round((dt_c + e + calib_s) * FS_OUT))
            v = s_e(CE.correlate_symbols(sb, smp), tones)
            if v > best:
                best, arg = v, (f_c + d, dt_c + e)
    return best, arg


def truth_ok(arg, f_own: float, dt_own: float) -> bool:
    """E1 / P truth check: the argmax within the gate of the row's own WSJT-X position."""
    return abs(arg[0] - f_own) <= GATE_DF_HZ + 1e-9 and abs(arg[1] - dt_own) <= GATE_DT_S + 1e-9


# --------------------------------------------------------------------------------------------- threshold, null, bootstrap
def fa_star(k_median: float) -> float:
    return FA_BUDGET / k_median


def threshold_te(null_scores, fa: float):
    """the smallest threshold T with exceedance share(S >= T) <= fa, as a value of the null (None if the null is empty); exceedance counts S >= T."""
    s = np.sort(np.asarray(null_scores, dtype=float))[::-1]
    n = len(s)
    if n == 0:
        return None
    max_ex = int(np.floor(n * fa + 1e-12))
    if max_ex >= n:
        return float(s[-1])
    # candidate T = a distinct value; need count(S >= T) <= max_ex: take the largest value v with count(S >= v) > max_ex is too small, so T is the next distinct value above it
    thr = s[max_ex]                                   # the (max_ex + 1)-th largest: count(S >= thr) >= max_ex + 1 > max_ex
    above = s[s > thr]
    return float(above.min()) if above.size else float(np.nextafter(thr, np.inf))


def exceed(null_scores, t: float) -> float:
    s = np.asarray(null_scores, dtype=float)
    return float((s >= t).mean())


def n_null_min(fa: float) -> float:
    return 3.0 / fa


def boot_idx(n_cyc, b=B_BOOT, seed=SEED):
    return np.random.default_rng(seed).integers(0, n_cyc, size=(b, n_cyc))


def ci(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan"), float("nan")]


def boot_te(null_scores, null_cycle, n_cyc, fa, idx):
    """cycle bootstrap of T_E: resample the CYCLES of the null tests, recompute T_E per replicate."""
    sc = np.asarray(null_scores, dtype=float)
    cyc = np.asarray(null_cycle)
    by = [sc[cyc == c] for c in range(n_cyc)]
    out = []
    for row in idx:
        v = np.concatenate([by[c] for c in row])
        t = threshold_te(v, fa)
        if t is not None:
            out.append(t)
    return out


def split_half(null_scores, null_cycle, fa):
    """T_E from the even cycles with the exceedance measured on the odd cycles, and the reverse."""
    sc = np.asarray(null_scores, dtype=float)
    cyc = np.asarray(null_cycle)
    out = {}
    for name, a, b in (("even_to_odd", 0, 1), ("odd_to_even", 1, 0)):
        tr, te = sc[cyc % 2 == a], sc[cyc % 2 == b]
        t = threshold_te(tr, fa)
        out[name] = {"T": t, "train_n": int(tr.size), "test_n": int(te.size), "exceedance_on_other_half": exceed(te, t) if t is not None and te.size else None}
    return out


def rate_ci(det_by_cycle, n_by_cycle, idx):
    n = n_by_cycle[idx].sum(axis=1)
    d = det_by_cycle[idx].sum(axis=1)
    return float(det_by_cycle.sum() / n_by_cycle.sum()), ci(d / np.where(n > 0, n, np.nan))


def g_pp(d_share):
    """G = D(E1) x 520 / 13,997, in pp of n_ref."""
    return 100.0 * d_share * N_E1_FULL / N_REF


def decide(r: dict) -> str:
    """Section 5 as amended (A2, section 11): 1 VOID (V-NULL-N fails)  2 BUILD-WORTH (CI_lo(G) >= 0.4)  3 VOID (V-POS fails: CI_lo(D(P on O)) < 0.80)  4 CLOSE (CI_hi(G) < 0.4)  5 BETWEEN.
    V-POS gates only CLOSE and BETWEEN: a broken detector cannot fake a BUILD-WORTH that clears the null-calibrated T_E and the truth-position gate.
    r: v_null_n_ok, v_pos_ci ([lo, hi] of D(P) on O), g_ci ([lo, hi] in pp)."""
    if not r["v_null_n_ok"]:
        return "VOID"
    if r["g_ci"][0] >= BUILD_PP:
        return "BUILD-WORTH"
    if r["v_pos_ci"][0] < V_POS:
        return "VOID"
    if r["g_ci"][1] < CLOSE_PP:
        return "CLOSE"
    return "BETWEEN"
