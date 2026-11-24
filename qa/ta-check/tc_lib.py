#!/usr/bin/env python3
"""TA-CHECK library (spec arch/accept-gate 2006 TA-CHECK + Amendment 1 section 8, `4336a281`; QA (k) review 0ff933e0).  QA tooling: no src/ or native/ change, no replay, no station.
Pure functions and constants (the self-test drives them on synthetic data).  Every inherited constant is an ASSERTION, not a reminder.  HK-037: message text is read inside the
function that scores it and never persisted; every file written holds stamps, indices, bands and numbers only.

QUESTION: do WSJT-X-CONFIRMED rows of batches 4 and 5 (T), and those under a stronger neighbour (T_bur), read `tested_present` under the U' tone test (cf_fbid.locate_and_score at WSJT-X's
position, T_FROZEN 0.276) at the instrument's own testability bar 0.80?  Groups: B1 (1,000 random batch-1 rows: the convention check), B1m (band-matched to T: the SNR-matched control),
T4, T5, T = T4 u T5, T_bur (another n_ref row at |df| < 50 Hz with SNR >= the row's own), T_iso = T - T_bur.  Rows of testable classes only (report, report CQ), not hashed, encodable.
DECISION (A1.2, first match wins): 1 VOID, 2 BLIND, 3 BLIND-BURIED, 4 WEAK-ROW, 5 SOUND, 6 BETWEEN.  See decide()."""
from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------------------------- frozen constants
SEED = 20261112
B_BOOT = 2000
T_FROZEN = 0.276                    # cf_uprime.T_FROZEN (asserted against the module in tc_groups)
BAR = 0.80                          # cf_uprime.MIN_PRESENT_RATE, the instrument's own testability bar (the Captain's choice, 2026-10-21)
OVERLAP_HZ = 50.0                   # nrtax_defs.OVERLAP_HZ (asserted in tc_groups)
N_B1 = 1000
V_N_T, V_N_TBUR = 400, 100
STD_MIN_CELL = 10                   # A1.1: cell-size floor for the standardisation (not a verdict bar)
NULL_TOL = 0.03                     # cf_uprime.NULL_P99_TOLERANCE
TESTABLE = ("report", "report CQ")
BANDS = ("A", "B", "C", "D")
assert (SEED, B_BOOT, T_FROZEN, BAR, OVERLAP_HZ, N_B1, V_N_T, V_N_TBUR, STD_MIN_CELL, NULL_TOL) == (20261112, 2000, 0.276, 0.80, 50.0, 1000, 400, 100, 10, 0.03)


def band_of(snr: int) -> str:
    """Replay81's BandOf (gr_common.band_of; asserted equal in tc_groups)."""
    return "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"


def strongest_neighbour(i: int, rows: list):
    """K2 (ratified, E179): the OTHER rows of the cycle's n_ref with |df| < OVERLAP_HZ and SNR >= row i's own; returns (dSNR, |df|) of the strongest of them (ties: the nearest in frequency), or None."""
    snr, f = rows[i][0], rows[i][2]
    c = [(rows[j][0], abs(rows[j][2] - f)) for j in range(len(rows)) if j != i and abs(rows[j][2] - f) < OVERLAP_HZ and rows[j][0] >= snr]
    if not c:
        return None
    s, d = max(c, key=lambda t: (t[0], -t[1]))
    return (s - snr, d)


def is_buried(i: int, rows: list) -> bool:
    return strongest_neighbour(i, rows) is not None


def band_quota(pool_counts: dict, want: dict):
    """B1m: the band counts of T; fails if the pool cannot cover a band (the freeze says so instead of silently short-drawing)."""
    for b in BANDS:
        assert pool_counts.get(b, 0) >= want.get(b, 0), ("B1m pool short", b, pool_counts.get(b, 0), want.get(b, 0))
    return {b: int(want.get(b, 0)) for b in BANDS}


def draw(pool: list, k: int, seed: int = SEED):
    """seeded draw without replacement from a SORTED pool of (stamp, idx, ...) tuples; returns the draw sorted."""
    pool = sorted(pool)
    assert len(pool) >= k
    rng = np.random.default_rng(seed)
    return sorted(pool[i] for i in rng.permutation(len(pool))[:k])


def draw_matched(pool_by_band: dict, quota: dict, seed: int = SEED):
    out = []
    for b in BANDS:
        out += draw(pool_by_band[b], quota[b], seed)
    return sorted(out)


# --------------------------------------------------------------------------------------------- bootstrap readout
def tally(rows: list, n_cyc: int, cyc_ix: dict):
    """rows: [(stamp, band, present)] -> (n[c], k[c], nb[b][c], kb[b][c])."""
    n = np.zeros(n_cyc)
    k = np.zeros(n_cyc)
    nb = {b: np.zeros(n_cyc) for b in BANDS}
    kb = {b: np.zeros(n_cyc) for b in BANDS}
    for s, b, p in rows:
        c = cyc_ix[s]
        n[c] += 1
        k[c] += bool(p)
        nb[b][c] += 1
        kb[b][c] += bool(p)
    return n, k, nb, kb


def boot_idx(n_cyc: int, b: int = B_BOOT, seed: int = SEED):
    return np.random.default_rng(seed).integers(0, n_cyc, size=(b, n_cyc))


def ci(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan"), float("nan")]


def rate(tl, idx):
    """PR per replicate: sum of k over the resampled cycles / sum of n."""
    n, k = tl[0], tl[1]
    return k[idx].sum(axis=1) / np.where(n[idx].sum(axis=1) > 0, n[idx].sum(axis=1), np.nan)


def std_bands(tiso, tbur):
    """bands where BOTH T_iso and T_bur have >= STD_MIN_CELL rows (full sample); returns (bands, weights = T_bur's band mix over them, T_bur rows left out)."""
    bands = [b for b in BANDS if tiso[2][b].sum() >= STD_MIN_CELL and tbur[2][b].sum() >= STD_MIN_CELL]
    tot = sum(tbur[2][b].sum() for b in bands)
    w = {b: tbur[2][b].sum() / tot for b in bands} if tot else {}
    left_out = int(sum(tbur[2][b].sum() for b in BANDS if b not in bands))
    return bands, w, left_out


def pr_std_contrast(tiso, tbur, idx, bands, w):
    """per replicate: PR_std(T_iso) (T_iso's per-band rates weighted by T_bur's band mix), PR(T_bur | bands) (T_bur's own, same weights) and their difference.  A replicate where a band has no row is NaN."""
    iso = np.zeros(len(idx))
    bur = np.zeros(len(idx))
    for b in bands:
        ni, ki = tiso[2][b][idx].sum(axis=1), tiso[3][b][idx].sum(axis=1)
        nu, ku = tbur[2][b][idx].sum(axis=1), tbur[3][b][idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            iso = iso + w[b] * np.where(ni > 0, ki / np.where(ni > 0, ni, 1), np.nan)
            bur = bur + w[b] * np.where(nu > 0, ku / np.where(nu > 0, nu, 1), np.nan)
    return iso, bur, iso - bur


def decide(r: dict):
    """A1.2, mechanical, first match wins.  r holds: n_T, n_Tbur, ci_B1, ci_B1m, ci_T, ci_Tbur, ci_B1m_minus_T, ci_std_diff (all [lo, hi]).
    A VOID for lack of rows (V-N) is reported first for the row that lacks them: n(T) < 400 => VOID; T_bur short => the BLIND-BURIED / SOUND-on-T_bur reads are not made (BETWEEN at best)."""
    if r["ci_B1"][0] < BAR:
        return "VOID"
    if r["n_T"] < V_N_T:
        return "VOID"
    if r["ci_T"][1] < BAR and r["ci_B1m_minus_T"][0] > 0:
        return "BLIND"
    tbur_ok = r["n_Tbur"] >= V_N_TBUR
    if tbur_ok and r["ci_Tbur"][1] < BAR and r["ci_std_diff"][0] > 0:
        return "BLIND-BURIED"
    cands = [r["ci_T"][1], r["ci_B1m"][1]] + ([r["ci_Tbur"][1]] if tbur_ok else [])
    if any(x < BAR for x in cands):
        return "WEAK-ROW"
    if tbur_ok and r["ci_T"][0] >= BAR and r["ci_Tbur"][0] >= BAR:
        return "SOUND"
    return "BETWEEN"
