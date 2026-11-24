#!/usr/bin/env python3
"""XC-BUILD analysis library (spec arch/cross-cycle-prior 14dc9bd3 + Amendment 1 section 8; QA (k) review fba6b4a3).  QA tooling: no src/ or native/ change.  Pure functions; the self-test drives them.
TR (TRAIN night, stage ON with T_E = +inf, shadow ON): the per-test sink gives S_E* for live and shadow tests -> K, FA* = 0.021 / K, T_E = the smallest threshold with shadow exceedance per test <= FA*, V-TR-N: n(shadow) >= 3 / FA*.
TEST night (OFF and ON, T_E frozen): NET = corroborated(ON) - corroborated(OFF) in pp of the TEST n_ref (cycle bootstrap); SHADOW = ON's shadow detections per cycle, exact Poisson interval (events over cycles);
LATE; V-WIRE.  DECISION (spec section 4): 1 STOP (V-OFF or V-STORE fails)  2 VOID (V-WIRE or V-TR-N fails)  3 REFUSE (SHADOW fails)  4 ACCEPT (CI_lo(NET) >= 0.4 pp and LATE)  5 NO-GAIN (CI_hi(NET) < 0.4)  6 BETWEEN."""
from __future__ import annotations

import math

import numpy as np

SEED = 20261113
B_BOOT = 2000
FA_BUDGET = 0.021                 # cf_uprime.OBSERVED_DELTA_U_1009 (the per-cycle U budget)
SHADOW_BAR = 0.042                # cf_uprime.BAR_LINE (2 x 0.021)
NET_BAR_PP = 0.4                  # XC-TEMPLATE's BUILD-WORTH bar
ALPHA = 0.05                      # two-sided 95 % interval: the one-sided bound at 0.025
assert (SEED, B_BOOT, FA_BUDGET, SHADOW_BAR, NET_BAR_PP) == (20261113, 2000, 0.021, 0.042, 0.4)


# --------------------------------------------------------------------------------------------- T_E from TR
def k_median(live_tests_per_cycle) -> float:
    """K = the median per cycle of the live templates tested (the priors a live stage carries), over every cycle of the TR arm (a cycle with no residual contributes 0)."""
    return float(np.median(np.asarray(live_tests_per_cycle, dtype=float)))


def fa_star(k: float) -> float:
    return FA_BUDGET / k


def threshold_te(shadow_scores, fa: float):
    """the smallest threshold T with share(S >= T) <= fa over the shadow tests (None if empty)."""
    s = np.sort(np.asarray(shadow_scores, dtype=float))[::-1]
    n = len(s)
    if n == 0:
        return None
    max_ex = int(np.floor(n * fa + 1e-12))
    if max_ex >= n:
        return float(s[-1])
    thr = s[max_ex]
    above = s[s > thr]
    return float(above.min()) if above.size else float(np.nextafter(thr, np.inf))


def v_tr_n(n_shadow: int, fa: float) -> bool:
    return n_shadow >= 3.0 / fa


def boot_idx(n_cyc, b=B_BOOT, seed=SEED):
    return np.random.default_rng(seed).integers(0, n_cyc, size=(b, n_cyc))


def ci(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan"), float("nan")]


def boot_te(shadow_scores, shadow_cycle, n_cyc, fa, idx):
    sc = np.asarray(shadow_scores, dtype=float)
    cyc = np.asarray(shadow_cycle)
    by = [sc[cyc == c] for c in range(n_cyc)]
    out = []
    for row in idx:
        t = threshold_te(np.concatenate([by[c] for c in row]), fa)
        if t is not None:
            out.append(t)
    return out


# --------------------------------------------------------------------------------------------- SHADOW (exact Poisson)
def _pois_cdf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0
    term = math.exp(-lam)
    tot = term
    for i in range(1, k + 1):
        term *= lam / i
        tot += term
    return tot


def poisson_upper(k: int, alpha_one_sided: float = ALPHA / 2) -> float:
    """exact upper bound lambda_u with P(X <= k | lambda_u) = alpha_one_sided (95 % two-sided: 0.025)."""
    lo, hi = 0.0, k + 10.0 * math.sqrt(k + 1) + 20.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _pois_cdf(k, mid) > alpha_one_sided:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def shadow_rate(events: int, cycles: int):
    """(point, [lo, hi]) of the shadow detections per cycle, exact Poisson."""
    hi = poisson_upper(events) / cycles
    if events == 0:
        lo = 0.0
    else:
        lo_l, hi_l = 0.0, float(events)
        target = 1.0 - ALPHA / 2                    # lower bound: P(X >= k | lambda_l) = 0.025  <=>  P(X <= k-1) = 0.975
        for _ in range(200):
            mid = 0.5 * (lo_l + hi_l)
            if _pois_cdf(events - 1, mid) < target:
                hi_l = mid
            else:
                lo_l = mid
        lo = 0.5 * (lo_l + hi_l) / cycles
    return events / cycles, [lo, hi]


def shadow_ok(events: int, cycles: int) -> bool:
    return shadow_rate(events, cycles)[1][1] <= SHADOW_BAR


# --------------------------------------------------------------------------------------------- NET
def net_pp(on_matched, off_matched, nref, idx):
    """NET = corroborated(ON) - corroborated(OFF), in pp of the TEST night's n_ref; per-cycle arrays; cycle bootstrap.  Returns (point, [lo, hi])."""
    d = np.asarray(on_matched, dtype=float) - np.asarray(off_matched, dtype=float)
    n = np.asarray(nref, dtype=float)
    point = 100.0 * d.sum() / n.sum()
    reps = 100.0 * d[idx].sum(axis=1) / n[idx].sum(axis=1)
    return float(point), ci(reps)


def late_ok(template_publishes_after_budget: int) -> bool:
    return template_publishes_after_budget == 0


def p95(v):
    v = np.asarray([x for x in v if x is not None and x >= 0], dtype=float)
    return float(np.percentile(v, 95)) if v.size else float("nan")


def v_wire(cycles_on_differs: int, batch6_nonempty_cycles: int) -> bool:
    return cycles_on_differs >= 1 and batch6_nonempty_cycles >= 1


def decide(r: dict) -> str:
    """r: v_off_ok, v_store_ok, v_wire_ok, v_trn_ok, shadow_ok, net_ci ([lo, hi] pp), late_ok."""
    if (not r["v_off_ok"]) or (not r["v_store_ok"]):
        return "STOP"
    if (not r["v_wire_ok"]) or (not r["v_trn_ok"]):
        return "VOID"
    if not r["shadow_ok"]:
        return "REFUSE"
    if r["net_ci"][0] >= NET_BAR_PP and r["late_ok"]:
        return "ACCEPT"
    if r["net_ci"][1] < NET_BAR_PP:
        return "NO-GAIN"
    return "BETWEEN"
