#!/usr/bin/env python3
"""XC-PRIOR library (spec arch/cross-cycle-prior 28627a82 + Amendment 1 section 8; QA (k) review 472181da).  QA tooling: no src/ or native/ change, no replay, no station.
Pure functions (the self-test drives them on synthetic data); HK-037: message text is read inside the counter and never persisted.
E1  = an UNREACHED row u (a WSJT-X row the arm did not match) whose exact text was matched by the arm in a SAME-parity earlier cycle (30 / 60 / 90 s = 2 / 4 / 6 cycles back) within 10 Hz.
E2  = not E1, a matched row p at the same lags and within 10 Hz with the same first two message fields and a different message (descriptive).
E-OPP = as E1 at the OPPOSITE parity (15 / 45 / 75 s = 1 / 3 / 5 cycles back): the control.   Missing priors (before the first listed cycle) count as no prior.
DECISION (A1): 1 CLOSE iff CI_hi(E1 pp) < 1.0  (V-PAR is not consulted);  2 VOID iff V-PAR fails (E-OPP > 0.25 x E1);  3 PURSUE iff CI_lo(E1 pp) >= 1.0;  4 BETWEEN."""
from __future__ import annotations

import numpy as np

CYCLE_S = 15
SAME_LAGS = (2, 4, 6)                  # cycles back: 30, 60, 90 s (same parity)
OPP_LAGS = (1, 3, 5)                   # cycles back: 15, 45, 75 s (opposite parity)
WINDOW_HZ = 10.0                       # cf_fbid.WS_CONF_DF, the corroboration window (asserted in xc_count)
BAR_PP = 1.0                           # the prize threshold of CS-REFIT / CS-CEIL
PAR_RATIO = 0.25
N_REF, N24_MATCHED, N_UNREACHED = 13997, 11729, 2268
SEED, B_BOOT = 20261113, 2000
assert [CYCLE_S * k for k in SAME_LAGS] == [30, 60, 90] and [CYCLE_S * k for k in OPP_LAGS] == [15, 45, 75]
assert N_REF - N24_MATCHED == N_UNREACHED and (BAR_PP, PAR_RATIO, SEED, B_BOOT, WINDOW_HZ) == (1.0, 0.25, 20261113, 2000, 10.0)


def first_two(text: str):
    t = text.split()
    return tuple(t[:2]) if len(t) >= 2 else None


def prior_hit(u, i, lags, matched_by_cycle):
    """u = (text, freq); i = the cycle index of u; matched_by_cycle[j] = [(text, freq, batch), ...] of the MATCHED rows of cycle j.
    Returns (kind, lag_cycles, prior_batch) with kind 'E1' (exact repeat), 'E2' (same first two fields, different message) or None.  E1 wins over E2; the nearest lag wins within a kind."""
    text, f = u
    e2 = None
    for k in lags:
        j = i - k
        if j < 0:
            continue
        for ptext, pf, pb in matched_by_cycle[j]:
            if abs(pf - f) > WINDOW_HZ:
                continue
            if ptext == text:
                return ("E1", k, pb)
            if e2 is None and first_two(ptext) is not None and first_two(ptext) == first_two(text):
                e2 = ("E2", k, pb)
    return e2 if e2 is not None else (None, None, None)


def boot_idx(n_cyc, b=B_BOOT, seed=SEED):
    return np.random.default_rng(seed).integers(0, n_cyc, size=(b, n_cyc))


def pp_ci(count_by_cycle, nref_by_cycle, idx):
    num = count_by_cycle[idx].sum(axis=1)
    den = nref_by_cycle[idx].sum(axis=1)
    p = 100.0 * num / den
    return float(100.0 * count_by_cycle.sum() / nref_by_cycle.sum()), [float(np.percentile(p, 2.5)), float(np.percentile(p, 97.5))]


def v_par(e_opp: int, e1: int) -> bool:
    return e_opp <= PAR_RATIO * e1


def decide(ci_e1, par_ok: bool) -> str:
    if ci_e1[1] < BAR_PP:
        return "CLOSE"
    if not par_ok:
        return "VOID"
    if ci_e1[0] >= BAR_PP:
        return "PURSUE"
    return "BETWEEN"
