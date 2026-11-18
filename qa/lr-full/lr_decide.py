#!/usr/bin/env python3
"""LR-FULL decision logic as code (spec b2d9883a + Amendment 1 A1.3 / A1.4, ruled 2026-11-18). PURE: no data access, so the self-test can drive every row.
HK-021: every threshold has its source in the comment; every row is a predicate on numbers, never prose; the first matching row wins.

Per STEP (X1, X2), over the nights evaluated so far (night 1 first). NET and H-COST are per night and are never pooled; V-AGREE-NI is the one pooled row (the instrument row only).
"""
from __future__ import annotations

NET_BAR_PP = 0.25          # v2's acceptance lower bound (+0.357 pp [0.250, 0.464], 500 cycles): GO needs CI_lo >= 0.25, NO-GAIN fires iff CI_hi < 0.25 (spec s4, HK-038)
H_BUDGET = 0.021           # per cycle: OBSERVED_DELTA_U_1009, qa/rr-study/coh-fallback/cf_uprime.py:47, the budget every late lever has been held to
NI_BAR = 0.10              # A1.3b: one-sided non-inferiority bound on phi_U - phi_H (isolated G rows)
MIN_AGREE_N = 200          # A1.3b: isolated G rows needed (pooled over the arm's nights) at phi about 0.5
ABANDON_FRAC = 0.01        # A1.4 N2: V-RUN fails if ON abandons cycles that OFF does not in more than 1 % of TEST cycles (a design value)
assert (NET_BAR_PP, H_BUDGET, NI_BAR, MIN_AGREE_N, ABANDON_FRAC) == (0.25, 0.021, 0.10, 200, 0.01)

OUTCOMES = ("VOID", "NO-GAIN", "H-UNDERSTATES", "COST", "GO", "GO-2N", "OPEN")


def h_cost(h_lo_ci_lo: float, h_hi_ci_hi: float) -> str:
    """H-COST(step), one night. PASS iff CI_hi(H-HI) <= 0.021; FAIL iff CI_lo(H-LO) > 0.021; else OPEN (A1.3a: H-LO / H-HI = isolated part (U') + buried part (H, unjudgeable at 0 / 1))."""
    if h_hi_ci_hi <= H_BUDGET:
        return "PASS"
    if h_lo_ci_lo > H_BUDGET:
        return "FAIL"
    return "OPEN"


def agree_ni(n_iso: int, ci_lo: float, ci_hi: float) -> str:
    """V-AGREE-NI (A1.3b), pooled across the arm's nights: below 200 isolated G rows UNDERPOWERED (decided BEFORE the interval is read); CI_hi(phi_U - phi_H) <= 0.10 PASS;
    CI_lo > 0.10 FAIL (H understates where both can see); otherwise INCONCLUSIVE (straddles the bar)."""
    if n_iso < MIN_AGREE_N:
        return "UNDERPOWERED"
    if ci_hi <= NI_BAR:
        return "PASS"
    if ci_lo > NI_BAR:
        return "FAIL"
    return "INCONCLUSIVE"


def net_state(ci_lo: float, ci_hi: float) -> str:
    """NET(step) against the 0.25 pp bar: GOOD (CI_lo >= bar), NO-GAIN (CI_hi < bar), else BETWEEN."""
    if ci_lo >= NET_BAR_PP:
        return "GOOD"
    if ci_hi < NET_BAR_PP:
        return "NO-GAIN"
    return "BETWEEN"


def v_run(pins_ok: bool, off_abandon_cycles: int, on_ge_off_batches_1_4: bool, off_rerun_identical: bool, on_extra_abandon_cycles: int, test_cycles: int) -> tuple[bool, dict]:
    """V-RUN, one night: pins asserted; 0 abandons in OFF; ON >= OFF in every cycle on batches 1-4 (N1; batches 5 and 6 by counts only); a 20-cycle OFF re-run byte-identical;
    and (N2) ON abandons cycles OFF does not in at most 1 % of TEST cycles."""
    extra = on_extra_abandon_cycles / test_cycles if test_cycles else 1.0
    parts = {"pins": pins_ok, "off_abandons_zero": off_abandon_cycles == 0, "on_ge_off_b1_4": on_ge_off_batches_1_4, "off_rerun_identical": off_rerun_identical,
             "on_extra_abandon_frac_le_1pct": extra <= ABANDON_FRAC, "on_extra_abandon_frac": extra}
    return all(v for k, v in parts.items() if k != "on_extra_abandon_frac"), parts


def decide_step(nights: list[dict], agree: str) -> tuple[str, str]:
    """A1.3c, the first matching row wins. nights[i] = {vrun: bool, vh: bool, net_lo, net_hi (pp), hcost: PASS|FAIL|OPEN}; nights[0] is night 1.
    1 VOID: V-RUN or V-H fails on any night evaluated.   2 NO-GAIN: CI_hi(NET) < 0.25 pp on night 1.   3 H-UNDERSTATES: V-AGREE-NI FAILS (pooled).
    4 COST: H-COST FAIL on any night.   5 GO: two nights, each with CI_lo(NET) >= 0.25 pp and H-COST PASS, and V-AGREE-NI PASS pooled.
    6 GO-2N: ONE night that qualifies as row 5 would (NET and H-COST), with V-AGREE-NI PASS or UNDERPOWERED: night 2 is run ('one night can at best give GO-2N').
    7 OPEN: otherwise, including V-AGREE-NI UNDERPOWERED or INCONCLUSIVE after night 2."""
    if not nights:
        return "OPEN", "no night evaluated"
    if any((not n["vrun"]) or (not n["vh"]) for n in nights):
        return "VOID", "V-RUN or V-H fails on a night"
    if nights[0]["net_hi"] < NET_BAR_PP:
        return "NO-GAIN", "CI_hi(NET) %.3f pp < %.2f on night 1" % (nights[0]["net_hi"], NET_BAR_PP)
    if agree == "FAIL":
        return "H-UNDERSTATES", "V-AGREE-NI fails (pooled)"
    if any(n["hcost"] == "FAIL" for n in nights):
        return "COST", "H-COST FAIL on a night"
    qualifies = all(n["net_lo"] >= NET_BAR_PP and n["hcost"] == "PASS" for n in nights)
    if len(nights) >= 2 and qualifies and agree == "PASS":
        return "GO", "both nights qualify and V-AGREE-NI passes"
    if len(nights) == 1 and qualifies and agree in ("PASS", "UNDERPOWERED"):
        return "GO-2N", "night 1 qualifies; one night can at best give GO-2N (V-AGREE-NI %s)" % agree
    return "OPEN", "no earlier row matched (NET / H-COST / V-AGREE-NI %s)" % agree
