#!/usr/bin/env python3
"""LR-FULL scorer self-test: constructed cases only (NFR-021: Q-prefix calls), every decision row driven, plus the data-layer definitions and the hybrid bracket arithmetic.
  python -I lr_score.py selftest      (or: python -I lr_selftest.py)"""
from __future__ import annotations

import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "fd-proxy"))
import lr_decide as D
import lr_score as S
import fd_lib as L

ok = True


def chk(name, got, want):
    global ok
    good = got == want
    ok &= good
    print(("PASS " if good else "FAIL ") + name + ("" if good else "  got %r want %r" % (got, want)))


def night(vrun=True, vh=True, net_lo=0.30, net_hi=0.50, hcost="PASS"):
    return dict(vrun=vrun, vh=vh, net_lo=net_lo, net_hi=net_hi, hcost=hcost)


def decision_tests():
    # constants asserted in code (HK: inherited constants as assertions)
    chk("constants", (D.NET_BAR_PP, D.H_BUDGET, D.NI_BAR, D.MIN_AGREE_N, D.ABANDON_FRAC), (0.25, 0.021, 0.10, 200, 0.01))
    # --- h_cost
    chk("H-COST PASS at CI_hi(H-HI) == 0.021 (inclusive)", D.h_cost(0.0, 0.021), "PASS")
    chk("H-COST FAIL iff CI_lo(H-LO) > 0.021", D.h_cost(0.0211, 0.05), "FAIL")
    chk("H-COST CI_lo == 0.021 is not FAIL", D.h_cost(0.021, 0.05), "OPEN")
    chk("H-COST OPEN in between", D.h_cost(0.005, 0.05), "OPEN")
    # --- agree_ni: power is decided BEFORE the interval is read
    chk("V-AGREE-NI n 199 is UNDERPOWERED even with a perfect interval", D.agree_ni(199, -0.2, 0.0), "UNDERPOWERED")
    chk("V-AGREE-NI n 200 and CI_hi 0.10 PASS (inclusive)", D.agree_ni(200, -0.05, 0.10), "PASS")
    chk("V-AGREE-NI CI_lo > 0.10 FAIL", D.agree_ni(500, 0.101, 0.2), "FAIL")
    chk("V-AGREE-NI CI_lo == 0.10 is not FAIL", D.agree_ni(500, 0.10, 0.2), "INCONCLUSIVE")
    chk("V-AGREE-NI straddling", D.agree_ni(500, 0.0, 0.15), "INCONCLUSIVE")
    # --- net_state
    chk("NET CI_lo == 0.25 is GOOD", D.net_state(0.25, 0.4), "GOOD")
    chk("NET CI_hi == 0.25 is not NO-GAIN", D.net_state(0.1, 0.25), "BETWEEN")
    chk("NET CI_hi < 0.25 is NO-GAIN", D.net_state(0.0, 0.2499), "NO-GAIN")
    # --- v_run
    chk("V-RUN all parts", D.v_run(True, 0, True, True, 10, 1000)[0], True)
    chk("V-RUN: ON-only abandons exactly 1 % pass", D.v_run(True, 0, True, True, 10, 1000)[0], True)
    chk("V-RUN: ON-only abandons 1.1 % FAIL (N2)", D.v_run(True, 0, True, True, 11, 1000)[0], False)
    chk("V-RUN: an OFF abandon fails", D.v_run(True, 1, True, True, 0, 1000)[0], False)
    chk("V-RUN: ON < OFF on a shipped batch fails", D.v_run(True, 0, False, True, 0, 1000)[0], False)
    chk("V-RUN: OFF re-run not identical fails", D.v_run(True, 0, True, False, 0, 1000)[0], False)
    chk("V-RUN: a pin mismatch fails", D.v_run(False, 0, True, True, 0, 1000)[0], False)
    # --- the decision table, every outcome (A1.3c), one night or two
    G, N1 = night(), night()
    chk("1 VOID: V-RUN fails", D.decide_step([night(vrun=False)], "PASS")[0], "VOID")
    chk("1 VOID: V-H fails on night 2", D.decide_step([night(), night(vh=False)], "PASS")[0], "VOID")
    chk("1 VOID precedes NO-GAIN", D.decide_step([night(vrun=False, net_hi=0.1)], "PASS")[0], "VOID")
    chk("2 NO-GAIN on night 1", D.decide_step([night(net_lo=0.0, net_hi=0.2)], "PASS")[0], "NO-GAIN")
    chk("2 NO-GAIN precedes H-UNDERSTATES", D.decide_step([night(net_lo=0.0, net_hi=0.2)], "FAIL")[0], "NO-GAIN")
    chk("2 NO-GAIN precedes COST", D.decide_step([night(net_lo=0.0, net_hi=0.2, hcost="FAIL")], "PASS")[0], "NO-GAIN")
    chk("2 NO-GAIN is judged on night 1 only (night 2 low does not fire it)", D.decide_step([night(), night(net_lo=0.0, net_hi=0.2)], "PASS")[0], "OPEN")
    chk("3 H-UNDERSTATES", D.decide_step([night()], "FAIL")[0], "H-UNDERSTATES")
    chk("3 H-UNDERSTATES precedes COST", D.decide_step([night(hcost="FAIL")], "FAIL")[0], "H-UNDERSTATES")
    chk("4 COST on night 1", D.decide_step([night(hcost="FAIL")], "PASS")[0], "COST")
    chk("4 COST on night 2 only", D.decide_step([night(), night(hcost="FAIL")], "PASS")[0], "COST")
    chk("5 GO: two nights qualify and V-AGREE-NI passes", D.decide_step([night(), night()], "PASS")[0], "GO")
    chk("6 GO-2N: one night, V-AGREE-NI UNDERPOWERED", D.decide_step([night()], "UNDERPOWERED")[0], "GO-2N")
    chk("6 GO-2N: one night at best, even with V-AGREE-NI PASS", D.decide_step([night()], "PASS")[0], "GO-2N")
    chk("7 OPEN: two nights, V-AGREE-NI UNDERPOWERED after night 2", D.decide_step([night(), night()], "UNDERPOWERED")[0], "OPEN")
    chk("7 OPEN: two nights, V-AGREE-NI INCONCLUSIVE", D.decide_step([night(), night()], "INCONCLUSIVE")[0], "OPEN")
    chk("7 OPEN: H-COST OPEN", D.decide_step([night(hcost="OPEN")], "PASS")[0], "OPEN")
    chk("7 OPEN: NET between the bars (CI_lo < 0.25 <= CI_hi)", D.decide_step([night(net_lo=0.1, net_hi=0.4)], "PASS")[0], "OPEN")
    chk("7 OPEN: night 2 does not clear the NET bar", D.decide_step([night(), night(net_lo=0.2, net_hi=0.5)], "PASS")[0], "OPEN")
    chk("6 GO-2N: night 1 with V-AGREE-NI INCONCLUSIVE (Amendment 3 D4)", D.decide_step([night()], "INCONCLUSIVE")[0], "GO-2N")
    chk("7 OPEN: night 1 INCONCLUSIVE but NET does not qualify", D.decide_step([night(net_lo=0.1, net_hi=0.4)], "INCONCLUSIVE")[0], "OPEN")
    chk("3 H-UNDERSTATES at night 2 as at night 1 (FAIL at either point)", D.decide_step([night(), night()], "FAIL")[0], "H-UNDERSTATES")
    chk("NET(ON) check: shortfall beyond the half-width is flagged", D.net_on_check(0.50, 0.40, 0.60, 0.40, 0.30)["flagged"], True)
    chk("NET(ON) check: shortfall within the half-width is not flagged", D.net_on_check(0.65, 0.50, 0.80, 0.40, 0.30)["flagged"], False)
    chk("NET(ON) check: ON above the sum is not flagged", D.net_on_check(0.90, 0.80, 1.00, 0.40, 0.30)["flagged"], False)
    chk("no night is OPEN", D.decide_step([], "PASS")[0], "OPEN")
    seen = {D.decide_step(*a)[0] for a in (([night(vrun=False)], "PASS"), ([night(net_lo=0, net_hi=0.1)], "PASS"), ([night()], "FAIL"), ([night(hcost="FAIL")], "PASS"),
                                            ([night(), night()], "PASS"), ([night()], "UNDERPOWERED"), ([night(), night()], "UNDERPOWERED"))}
    chk("every outcome row in OUTCOMES is driven", seen, set(D.OUTCOMES))


def gate_tests():
    chk("gate constant", D.GATE_HALFWIDTH_PP, 0.125)
    # 100 cycles, 1 event in each of 20: mean 0.2, sample variance 0.1616, lambda = 21/100 = 0.21 -> V_pilot = 0.21.   hw = 1.96 x 100 x sqrt(V_pilot / (m_pilot x m_test)) / sqrt(n_test)
    counts = [1] * 20 + [0] * 80
    p = D.project_net_halfwidth(counts, 30.0, 30.0, 2000)
    want = 1.96 * 100 * ((0.21 / (30.0 * 30.0)) ** 0.5) / (2000 ** 0.5)
    chk("projection: the Architect's formula, hand value (add-one lambda is the variance floor)", round(p["halfwidth_pp"], 9), round(want, 9))
    chk("projection: with m_test == m_pilot it reduces to the first form 1.96 x 100 x sqrt(V) / (sqrt(n_test) x m)",
        round(p["halfwidth_pp"], 9), round(1.96 * 100 * (0.21 ** 0.5) / ((2000 ** 0.5) * 30.0), 9))
    chk("projection: ZERO pilot events is not perfectly certain (add-one floor)", D.project_net_halfwidth([0] * 100, 30.0, 30.0, 2000)["halfwidth_pp"] > 0.0, True)
    b0 = D.project_net_halfwidth(counts, 30.0, 30.0, 2000)["halfwidth_pp"]
    chk("projection: half-width scales as 1/sqrt(n_test) (4x cycles = half)", round(D.project_net_halfwidth(counts, 30.0, 30.0, 500)["halfwidth_pp"] / b0, 6), 2.0)
    # THE ARCHITECT'S CASE: the pilot is the best hour, the TEST block is noisier: m_test < m_pilot RAISES hw (hw ~ 1/sqrt(m_test))
    lo = D.project_net_halfwidth(counts, 30.0, 15.0, 2000)["halfwidth_pp"]
    chk("projection: m_test < m_pilot RAISES the half-width (m_test halved: x sqrt(2))", (lo > b0, round(lo / b0, 6)), (True, round(2 ** 0.5, 6)))
    chk("projection: m_test > m_pilot lowers it", D.project_net_halfwidth(counts, 30.0, 60.0, 2000)["halfwidth_pp"] < b0, True)
    chk("projection: a pilot rate that is too high does not understate the TEST half-width (pilot 33, test 10 > pilot 33, test 33)",
        D.project_net_halfwidth(counts, 33.0, 10.0, 2000)["halfwidth_pp"] > D.project_net_halfwidth(counts, 33.0, 33.0, 2000)["halfwidth_pp"], True)
    ov = [5, 0, 0, 0, 0, 5, 0, 0, 0, 0]
    chk("projection: an over-dispersed pilot uses the sample variance when it exceeds lambda", D.project_net_halfwidth(ov, 30.0, 30.0, 2000)["V_pilot"] == D.project_net_halfwidth(ov, 30.0, 30.0, 2000)["per_cycle_variance"], True)
    chk("projection: too few cycles or a zero rate is not computable (infinite, cannot hide a wide interval)",
        (D.project_net_halfwidth([1], 30.0, 30.0, 2000)["halfwidth_pp"], D.project_net_halfwidth(counts, 30.0, 0.0, 2000)["halfwidth_pp"]), (float("inf"), float("inf")))
    chk("gate fires only when BOTH steps exceed 0.125", (D.gate_fires(0.2, 0.2), D.gate_fires(0.2, 0.1), D.gate_fires(0.1, 0.2), D.gate_fires(0.1, 0.1)), (True, False, False, False))
    chk("gate: exactly 0.125 does not fire", D.gate_fires(0.125, 0.125), False)
    chk("gate on a noisy-TEST case: a pilot that passes at m_test = m_pilot fires when m_test collapses", (D.gate_fires(*(D.project_net_halfwidth(counts, 33.0, 33.0, 1000)["halfwidth_pp"],) * 2),
        D.gate_fires(*(D.project_net_halfwidth(counts, 33.0, 4.0, 1000)["halfwidth_pp"],) * 2)), (False, True))


def row(st, k, m, f, tx, step=0, snr=-15, dt=0.1):
    return dict(st=st, k=k, m=m, f=f, dt=dt, snr=snr, tx=tx, ap=0, step=step)


def data_tests():
    # --- the matching rule (replay81): equal text, |df| <= 10 Hz, one-to-one, smallest df first
    ws = [(-10, 1500, "QA1AAA QB2BBB JO22"), (-12, 1520, "QC3CCC QD4DDD -05")]
    rows = [row("261114_231215", 1, 0, 1509, "QA1AAA QB2BBB JO22"), row("261114_231215", 4, 0, 1502, "QA1AAA QB2BBB JO22"), row("261114_231215", 4, 0, 1531, "QC3CCC QD4DDD -05")]
    m = S.match_cycle(rows, ws)
    chk("match: the smaller df wins the single WSJT-X row", m, {1: 0})
    chk("match: 11 Hz away does not match", 2 in m, False)
    chk("match: a second equal-text row is NOT matched (one-to-one)", 0 in m, False)
    arm = [dict(r) for r in rows]
    for r in arm:
        r["m"] = 0
    arm[1]["m"] = 1
    chk("arm_match: flags equal the recomputation (0 mismatches)", S.arm_match(arm, {"261114_231215": ws}), 0)
    arm[0]["m"] = 1
    chk("arm_match: a wrong flag is counted", S.arm_match(arm, {"261114_231215": ws}), 1)
    # --- NET: newly corroborated by step; a WSJT-X row already matched in OFF is not new; lost rows counted
    st = "261114_231215"
    w = {st: [(-10, 1500, "QA1AAA QB2BBB JO22"), (-10, 1600, "QE5EEE QF6FFF -01"), (-10, 1700, "QG7GGG QH8HHH RR73"), (-10, 1800, "QI9III QJ1JJJ 73")]}
    off = [row(st, 4, 1, 1500, "QA1AAA QB2BBB JO22"), row(st, 4, 1, 1800, "QI9III QJ1JJJ 73")]
    on = [row(st, 4, 1, 1500, "QA1AAA QB2BBB JO22", 0), row(st, 4, 1, 1600, "QE5EEE QF6FFF -01", 2), row(st, 5, 1, 1700, "QG7GGG QH8HHH RR73", 5)]
    S.arm_match(off, w); S.arm_match(on, w)
    cyc = [st]
    A = S.net_arrays(on, off, w, cyc)
    chk("NET: X1 counts the newly corroborated row tagged 2", A["X1"][0], 1.0)
    chk("NET: X2 counts the row tagged 5 (admitted-only part)", (A["X2"][0], A["X2_passed"][0], A["X2_admitted"][0]), (1.0, 0.0, 1.0))
    chk("NET: a row matched in OFF already is not newly corroborated", A["other"][0], 0.0)
    chk("NET: the WSJT-X row OFF matched and ON lost is counted lost", A["lost"][0], 1.0)
    chk("NET: n_ref is the WSJT-X rows of the cycle", A["nref"][0], 4.0)
    # --- G: tag, no WSJT-X match, text not published in OFF in that cycle
    on2 = [row(st, 4, 0, 1100, "QK2KKK QL3LLL -07", 2), row(st, 4, 0, 1200, "QM4MMM QN5NNN -09", 2), row(st, 4, 1, 1500, "QA1AAA QB2BBB JO22", 2), row(st, 5, 0, 1300, "QO6OOO QP7PPP JO22", 4)]
    off2 = [row(st, 4, 0, 1200, "QM4MMM QN5NNN -09", 0)]
    S.arm_match(on2, w); S.arm_match(off2, w)
    g1 = S.g_rows(on2, off2, (2,))
    chk("G(X1): unmatched, tagged 2, not in OFF (the OFF-published text and the matched row are out)", [r["tx"] for r in g1], ["QK2KKK QL3LLL -07"])
    chk("G(X2): tags 4 and 5", [r["tx"] for r in S.g_rows(on2, off2, (4, 5))], ["QO6OOO QP7PPP JO22"])
    # --- classify: every row has a burial class, judgeable only if H can parse it
    E = L.Evidence([(L.cycle_of(st), -5, 1105, "QR8RRR QS9SSS -01")])
    cl = S.classify([row(st, 4, 0, 1100, "QK2KKK QL3LLL -07", snr=-15), row(st, 4, 0, 1100, "<...> QL3LLL -07", snr=-15), row(st, 4, 0, 1900, "<...> QL3LLL -07", snr=-15)], E, confirmed=False)
    chk("classify: judgeable flag", [x["judgeable"] for x in cl], [True, False, False])
    chk("classify: an UNPARSEABLE row still gets a burial class (buried next to a stronger row, isolated elsewhere)", [x["st"][1] for x in cl], ["buried", "buried", "isolated"])
    # --- pooled V-AGREE-NI: n-weighted, power decided by the pooled n
    rng = np.random.default_rng(1)
    night_a = dict(n=120, point_diff=0.02, boot=list(0.02 + 0.02 * rng.standard_normal(500)))
    night_b = dict(n=60, point_diff=0.01, boot=list(0.01 + 0.02 * rng.standard_normal(500)))
    p = S.pooled_agree([night_a, night_b])
    chk("pooled V-AGREE-NI: 180 isolated rows is UNDERPOWERED", (p["n"], p["status"]), (180, "UNDERPOWERED"))
    night_b["n"] = 90
    p = S.pooled_agree([night_a, night_b])
    chk("pooled V-AGREE-NI: 210 rows with a small difference PASSES", (p["n"], p["status"]), (210, "PASS"))
    night_c = dict(n=300, point_diff=0.30, boot=list(0.30 + 0.01 * rng.standard_normal(500)))
    chk("pooled V-AGREE-NI: a large positive difference FAILS", S.pooled_agree([night_c])["status"], "FAIL")
    chk("pooled V-AGREE-NI: nothing is UNDERPOWERED", S.pooled_agree([dict(n=0, point_diff=float("nan"), boot=[])])["status"], "UNDERPOWERED")
    # --- V-RUN's OFF re-run compares on the re-run's cycles only
    ra = [row("c1", 1, 0, 1500, "QA1AAA QB2BBB JO22"), row("c2", 1, 0, 1600, "QC3CCC QD4DDD -05"), row("c3", 4, 0, 1700, "QE5EEE QF6FFF 73")]
    rb = [dict(r) for r in ra[:2]]
    chk("OFF re-run: identical on the re-run's cycles (the reference may cover more)", S.rows_equal_on_cycles_of(ra, rb), True)
    rb[1]["f"] = 1601
    chk("OFF re-run: a changed frequency is caught", S.rows_equal_on_cycles_of(ra, rb), False)
    ra2 = ra + [row("c1", 4, 0, 1800, "QG7GGG QH8HHH RR73")]
    chk("OFF re-run: a row missing inside a cycle the re-run covers is caught", S.rows_equal_on_cycles_of(ra2, [dict(ra2[0]), dict(ra2[1])]), False)
    # --- abandon cycles from the harness csvs
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "coh.csv"), "w").write("stamp,seen,abandoned\nA1,1,0\nA2,1,3\n")
        open(os.path.join(d, "abandon.csv"), "w").write("stamp,ran,abandoned,contained\nA3,1,1,0\nA4,1,0,0\n")
        open(os.path.join(d, "third.csv"), "w").write("stamp,outcome,newDecodes\nA5,failed,0\nA6,ran,2\n")
        open(os.path.join(d, "late.csv"), "w").write("stamp,outcome,lines\nA7,abandoned,0\nA8,ran,1\n")
        chk("abandon_cycles: any stage's abandon or failure", sorted(S.abandon_cycles(d)), ["A2", "A3", "A5", "A7"])


class StubInst:
    """No audio: U' 'present' is a function of the text; H is the real fd_lib on a constructed E."""

    def __init__(self, E):
        self.E = E

    def present(self, r):
        return 0 if "QC3CCC" in r["tx"] else 1      # a constructed call the stub treats as tested-absent by the tone test


def hybrid_tests():
    # constructed night of 4 cycles; E gives every call recurrence so H reads plausible
    cycs = [L.cycle_of("261114_" + t) for t in ("231200", "231700", "232200", "232700")]   # 20 slots apart, so one cycle's evidence rows never land in another's own slot
    ev = []
    for c in cycs:
        for k in range(-8, 9):
            if k != 0:          # no WSJT-X row in the row's OWN cycle, so check C cannot fire on the constructed G rows (a constructed row with a seen call and sender is then plausible)
                ev.append((c + k, -10, 1200 + (k % 3), "QA1AAA QB2BBB JO22"))
    E = L.Evidence(ev)
    inst = StubInst(E)
    mk = lambda cyc, isolated, judgeable, absent=False: dict(
        r=dict(st="x", f=1200, dt=0.1, snr=-15, tx=("QA1AAA QC3CCC -05" if absent else "QA1AAA QB2BBB -05") if judgeable else "<...> QB2BBB -05"),
        pr={"kind": "STD"} if judgeable else None, judgeable=judgeable, cyc=cyc, st=("<=-18" if False else "-17..-10", "isolated" if isolated else "buried"), kind="STD" if judgeable else None)
    p_recs = []
    for c in cycs:
        for iso in (True, False):
            p_recs.append(dict(mk(c, iso, True), pl=1))
    p_sample = [dict(x, u=1) for x in p_recs if x["st"][1] == "isolated"]
    f_ctrl, f_iso = (0.0, 0.02, 0.08), (0.0, 0.0)
    base_g = [mk(cycs[0], True, True), mk(cycs[1], True, True), mk(cycs[2], False, True), mk(cycs[3], False, True)]
    r0 = S.step_cost(base_g, p_recs, cycs, inst, f_ctrl, f_iso, 1000, 1000, p_sample)
    # (a) unjudgeable BURIED rows widen the H bracket by exactly n/nC (they enter H-HI at 1, H-LO at 0)
    g_bur = base_g + [mk(cycs[3], False, False)] * 3
    r1 = S.step_cost(g_bur, p_recs, cycs, inst, f_ctrl, f_iso, 1000, 1000, p_sample)
    w0 = r0["point"]["h_hi"] - r0["point"]["h_lo"]
    w1 = r1["point"]["h_hi"] - r1["point"]["h_lo"]
    chk("hybrid: 3 unjudgeable BURIED rows widen the H bracket by 3 / nC = 0.75", round(w1 - w0, 4), 0.75)
    # (b) unjudgeable ISOLATED rows are judged by U' (counted in the isolated part), and do NOT widen the bracket
    g_iso = base_g + [mk(cycs[0], True, False)] * 3
    r2 = S.step_cost(g_iso, p_recs, cycs, inst, f_ctrl, f_iso, 1000, 1000, p_sample)
    w2 = r2["point"]["h_hi"] - r2["point"]["h_lo"]
    chk("hybrid: unjudgeable ISOLATED rows do not widen the bracket", round(w2 - w0, 6), 0.0)
    chk("hybrid: they are in the isolated count (U' sees them)", (r0["point"]["n_iso_all"], r2["point"]["n_iso_all"], r2["point"]["n_iso_judgeable"]), (2, 5, 2))
    # (c) U' tested-absent isolated rows raise the isolated part (both ends equally)
    g_abs = [mk(cycs[0], True, True, absent=True), mk(cycs[1], True, True, absent=True)] + base_g[2:]
    r3 = S.step_cost(g_abs, p_recs, cycs, inst, f_ctrl, f_iso, 1000, 1000, p_sample)
    chk("hybrid: absent-by-U' isolated rows raise the isolated part and move H-LO and H-HI by the same amount",
        (r3["point"]["iso_part"] > r0["point"]["iso_part"], round((r3["point"]["h_hi"] - r3["point"]["h_lo"]) - w0, 6)), (True, 0.0))
    # (d) Amendment 3 D7: the N-RAND rate used by H-COST is the one AT BURIED G POSITIONS; a higher rate there raises the high end of the buried part (phi_hi uses max(f_rand_b, f_miss))
    mix = [mk(cycs[2], False, True), mk(cycs[3], False, True), dict(mk(cycs[2], False, True), r=dict(mk(cycs[2], False, True)["r"], tx="QX9XXX QY8YYY -05")),
           dict(mk(cycs[3], False, True), r=dict(mk(cycs[3], False, True)["r"], tx="QX9XXX QY8YYY -05"))]
    lo_f = S.step_cost(mix, p_recs, cycs, inst, (0.30, 0.02, 0.08), f_iso, 1000, 1000, p_sample, n_rand_b=1000)["point"]
    hi_f = S.step_cost(mix, p_recs, cycs, inst, (0.50, 0.02, 0.08), f_iso, 1000, 1000, p_sample, n_rand_b=1000)["point"]
    chk("hybrid D7: a higher N-RAND rate at buried G positions (both above f_vis) raises phi_hi and H-HI, and phi_lo = phi(min(f_rand_b, f_vis)) does not move", (hi_f["phi_hi"] > lo_f["phi_hi"], hi_f["h_hi"] > lo_f["h_hi"], hi_f["phi_lo"] == lo_f["phi_lo"]), (True, True, True))
    chk("hybrid: with no G at all the cost is zero", S.step_cost([], p_recs, cycs, inst, f_ctrl, f_iso, 1000, 1000, p_sample)["point"]["h_hi"], 0.0)
    chk("hybrid: the cost CI brackets are ordered (H-LO <= H-HI at every end)", (r1["ci"]["h_lo"][0] <= r1["ci"]["h_hi"][0], r1["ci"]["h_lo"][1] <= r1["ci"]["h_hi"][1]), (True, True))


def main():
    decision_tests()
    gate_tests()
    data_tests()
    hybrid_tests()
    print("SELFTEST " + ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
