#!/usr/bin/env python3
"""TA-MASK library (spec arch/accept-gate 104f197f TA-MASK + Amendment 1 section 9, `0777c9b9`; QA (k) review 125ab6c5).  QA tooling: no src/ or native/ change, no replay, no station.
Pure functions (the self-test drives them on synthetic data).  HK-037: message text is read inside the scorer and never persisted.

THE MASKED SCORE M (section 2, as code).  For a scored row r at a candidate position (f_pos, start st):
  neighbours = every OTHER n_ref row of the cycle with |f_n - f_r| < 50 Hz (any SNR), tones from EncodeMessage; a neighbour that cannot be encoded stays unmasked (A1.4);
  neighbour symbol m is tone tn[m] at f_n + 6.25 tn[m] Hz, on during [t_n + 0.16 m, t_n + 0.16 (m + 1)), t_n = dt_n + the frozen calibration;
  at r's symbol j = [st + 0.16 j, st + 0.16 (j + 1)), bin b (frequency f_pos + 6.25 b) is MASKED iff some neighbour tone overlapping symbol j in time lies within 6.25 Hz (INCLUSIVE, A1.2) of the bin centre;
  Costas search: each Costas symbol is scored "strongest of the UNMASKED bins"; a Costas symbol whose own tone is masked does not count; the sync share is over the remaining ones;
  data score S_M = share, over the data symbols whose own tone bin is NOT masked, in which the own tone is the strongest of the unmasked bins; n_s = their number; n_s < 20 => UNSCORABLE (counts as not present).
  Present <=> scorable and S_M >= T_M.  T_M = max(pooled null p99 over B1m u T, null p99 over T_bur alone) (A1.1), committed before any acceptance S_M."""
from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------------------------- frozen constants
SEED = 20261113
B_BOOT = 2000
OVERLAP_HZ = 50.0                  # nrtax_defs.OVERLAP_HZ (asserted in tm_run)
TONE_HZ = 6.25                     # FT8 tone spacing
SYM_S = 0.16                       # FT8 symbol length
MASK_HZ = 6.25                     # "within 6.25 Hz", INCLUSIVE (A1.2)
N_SYM, N_TONES = 79, 8
MIN_SCORABLE = 20                  # design floor (section 2 item 6); the pilot reports the n_s distribution
K_NULL = 20
AGREE_MAX = 0.3
BAR_PRESENT = 0.80                 # cf_uprime.MIN_PRESENT_RATE
BAR_GHOST = 0.05                   # A-GHOST: CI_hi(PR_M(ghost)) <= 0.05 (no data on file; challenged if the pilot's masked rate is above 0.02)
GHOST_CHALLENGE = 0.02
V_N_TBUR = 100
DF_GRID_HZ = (-3.125, 0.0, 3.125)  # cf_fbid.DF_GRID_HZ (asserted in tm_run)
DT_HALF_S, DT_STEP_S = 0.12, 0.01  # cf_fbid.DT_HALF_WINDOW_S, DT_STEP_S (asserted in tm_run)
assert (SEED, B_BOOT, OVERLAP_HZ, TONE_HZ, SYM_S, MASK_HZ, MIN_SCORABLE, K_NULL, AGREE_MAX, BAR_PRESENT, BAR_GHOST, V_N_TBUR) == (20261113, 2000, 50.0, 6.25, 0.16, 6.25, 20, 20, 0.3, 0.80, 0.05, 100)


def neighbour_entries(neigh, c_off):
    """neigh: [(f_n, dt_n, tones[79])] -> flat arrays (tf, ts, te) of every neighbour symbol: tone frequency, on-time, off-time."""
    tf, ts, te = [], [], []
    for f_n, dt_n, tn in neigh:
        t0 = dt_n + c_off
        for m in range(N_SYM):
            tf.append(f_n + TONE_HZ * tn[m])
            ts.append(t0 + SYM_S * m)
            te.append(t0 + SYM_S * (m + 1))
    return np.array(tf, dtype=float), np.array(ts, dtype=float), np.array(te, dtype=float)


def mask_matrix(f_pos, st, ent):
    """bool [79, 8]: True where the bin is masked at start `st` (seconds) and bin-0 frequency `f_pos`."""
    tf, ts, te = ent
    if tf.size == 0:
        return np.zeros((N_SYM, N_TONES), dtype=bool)
    a = st + SYM_S * np.arange(N_SYM)
    b = a + SYM_S
    overlap = (ts[None, :] < b[:, None]) & (te[None, :] > a[:, None])                    # [79, E]
    bins = f_pos + TONE_HZ * np.arange(N_TONES)                                          # [8]
    close = np.abs(tf[:, None] - bins[None, :]) <= MASK_HZ + 1e-9                         # [E, 8]
    return (overlap.astype(np.int32) @ close.astype(np.int32)) > 0


def masked_argmax(Xabs, mask):
    """strongest of the UNMASKED bins per symbol (-1 where every bin is masked)."""
    m = np.where(mask, -1.0, Xabs)
    am = m.argmax(axis=1)
    return np.where(mask.all(axis=1), -1, am)


def sync_share(am, mask, sync_idx, sync_tones):
    """share over the Costas symbols whose own tone is not masked (-1.0 if none)."""
    ok = [(not mask[k, t]) for k, t in zip(sync_idx, sync_tones)]
    n = sum(ok)
    if n == 0:
        return -1.0
    return sum(1 for k, t, o in zip(sync_idx, sync_tones, ok) if o and am[k] == t) / n


def data_score(am, mask, seq, data_idx):
    """(S_M, n_s): share over the data symbols whose own tone bin is not masked, in which the own tone is the strongest unmasked bin."""
    sc = [k for k in data_idx if not mask[k, seq[k]]]
    if not sc:
        return float("nan"), 0
    return sum(1 for k in sc if am[k] == seq[k]) / len(sc), len(sc)


def present(s, n_s, t_m):
    return bool(n_s >= MIN_SCORABLE and np.isfinite(s) and s >= t_m)


# --------------------------------------------------------------------------------------------- thresholds and bootstrap
def pct99(v):
    v = np.asarray([x for x in v if np.isfinite(x)], dtype=float)
    return float(np.percentile(v, 99.0)) if v.size else float("nan")


def threshold_tm(null_pooled, null_tbur):
    """A1.1: T_M = max(pooled p99, T_bur-only p99); all three reported by the caller."""
    p, b = pct99(null_pooled), pct99(null_tbur)
    return max(p, b), p, b


def tally(rows, n_cyc, cix):
    """rows: [(stamp, band, present)] -> (n[c], k[c], nb[b][c], kb[b][c])."""
    bands = ("A", "B", "C", "D")
    n, k = np.zeros(n_cyc), np.zeros(n_cyc)
    nb = {b: np.zeros(n_cyc) for b in bands}
    kb = {b: np.zeros(n_cyc) for b in bands}
    for s, b, p in rows:
        c = cix[s]
        n[c] += 1
        k[c] += bool(p)
        nb[b][c] += 1
        kb[b][c] += bool(p)
    return n, k, nb, kb


def boot_idx(n_cyc, b=B_BOOT, seed=SEED):
    return np.random.default_rng(seed).integers(0, n_cyc, size=(b, n_cyc))


def rate(tl, idx):
    n, k = tl[0], tl[1]
    den = n[idx].sum(axis=1)
    return k[idx].sum(axis=1) / np.where(den > 0, den, np.nan)


def ci(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan"), float("nan")]


def decide(r):
    """Section 5 (pre-registered, first match wins).  r: ci_B1, ci_B1m, ci_Tbur, ci_ghost ([lo, hi]), n_Tbur.
    1 VOID (A-KEEP fails or V-N fails)   2 CREDULOUS (A-GHOST fails: CI_hi > 0.05)   3 REPAIRED (A-SEE: CI_lo(PR_M(T_bur)) >= 0.80)   4 NOT-REPAIRED."""
    if r["ci_B1"][0] < BAR_PRESENT or r["ci_B1m"][0] < BAR_PRESENT or r["n_Tbur"] < V_N_TBUR:
        return "VOID"
    if r["ci_ghost"][1] > BAR_GHOST:
        return "CREDULOUS"
    if r["ci_Tbur"][0] >= BAR_PRESENT:
        return "REPAIRED"
    return "NOT-REPAIRED"
