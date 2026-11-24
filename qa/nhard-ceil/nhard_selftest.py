"""Synthetic self-test for nhard_analyse (Q-prefix calls only, no real data, no WAVs; NFR-021). Must pass, and every mutation below must be KILLED, before the freeze is committed.

A small synthetic night (40 cycles) with KNOWN numbers of N24-only corroborated / tested_absent / tested_present / hashed / untestable rows in known batches, N0-only rows and an arm B; the SAME
analyse() the real run uses (a fake WSJT-X reference and a fake instrument injected); every row, every verdict branch and the boundaries of both bars; then each mutation must make the checks FAIL.

    python nhard_selftest.py
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "coh-res-cand-v2"))

N = 40


def stamp(i):
    return f"261110_18{47 + i // 4:02d}{(i % 4) * 15:02d}"


def call(k):
    return f"Q{k % 10}{chr(65 + (k // 10) % 26)}{chr(65 + (k // 260) % 26)}"


def row(kind, f, text, matched=0, dt=0.10, snr=-10, path=0, ap=0):
    return dict(kind=kind, matched=matched, f=f, dt=dt, snr=snr, path=path, text=text, ap=ap)


def fake_status(stamp_, text, freq, dt):
    if "<" in text:
        return "hashed_or_unencodable"
    if text.startswith("TA "):
        return "tested_absent"
    if text.startswith("TP "):
        return "tested_present"
    return "untestable_class"


def build(n24_corr=0, n24_ta=0, n24_tp=0, n24_hu=0, n24_unt=0, ta_kind=4, n0_only_corr=0, differ_only=False):
    stamps = [stamp(i) for i in range(N)]
    n24, n0, arm_b, ref = {}, {}, {}, {}
    for i, s in enumerate(stamps):
        base = [row(1, 1000 + 10 * j, f"CQ {call(100 * i + j)} JO22", matched=1) for j in range(3)] + [row(4, 1200, f"{call(100 * i + 60)} {call(100 * i + 61)} R-12", matched=1)]
        n0[s] = [dict(x) for x in base]
        arm_b[s] = [dict(x) for x in base]
        ref[s] = [(-10, 0.1, x["f"], x["text"]) for x in base]
        rows24 = [dict(x) for x in base]
        k = 0
        for _ in range(n24_corr):
            t = f"CQ {call(5000 + 10 * i + k)} KO11"; k += 1
            rows24.append(row(1, 2000 + 10 * k, t, matched=1)); ref[s].append((-12, 0.1, 2000 + 10 * k, t))
        for _ in range(n24_ta):
            rows24.append(row(ta_kind, 2500 + 10 * k, f"TA {call(6000 + 10 * i + k)} {call(6100 + k)} -15")); k += 1
        for _ in range(n24_tp):
            rows24.append(row(2, 2800 + 10 * k, f"TP {call(7000 + 10 * i + k)} {call(7100 + k)} -16")); k += 1
        for _ in range(n24_hu):
            rows24.append(row(3, 2900 + 10 * k, f"<Q9ZZ> {call(8000 + 10 * i + k)} -11")); k += 1
        for _ in range(n24_unt):
            rows24.append(row(2, 3000 + 10 * k, f"UC {call(9000 + 10 * i + k)} RR73")); k += 1
        if differ_only and i == 0:
            rows24.append(row(2, 3100, f"TP {call(9900)} {call(9901)} -17"))
        n24[s] = rows24
        for _ in range(n0_only_corr):
            t = f"CQ {call(11000 + 10 * i + k)} KO22"; k += 1
            n0[s].append(row(1, 3200 + 10 * k, t, matched=1)); ref[s].append((-13, 0.1, 3200 + 10 * k, t))
    coh = [dict(stamp=s, seen="1", abandoned="0", resabandoned="0") for s in stamps]
    late = [dict(stamp=s, outcome="ran") for s in stamps]
    run = [dict(stamp=s, tb1_ms="500", tb2_ms="2500", tb3_ms="-1.0", tb4_ms=str(4500 + 10 * i), tb5_ms="-1.0") for i, s in enumerate(stamps)]
    return dict(stamps=stamps, n24=n24, n0=n0, arm_b=arm_b, coh24=coh, coh0=coh, run24=run, run0=run, late24=late, late0=late, ref=ref)


RB = "# readback {tag} subtractionEnabled=True threadsResolved=8 nhard={nh} kMinScorePass2=5 osdCorrThreshold=0.05 shim=20260072 decodingDepth=Deep cohfb=True cohms=True cohaudio=Both ungated=True lateround=True cqap={cq} cohrescand=True"


def rb(nh, cq="True"):
    return {t: RB.format(tag=t, nh=nh, cq=cq) for t in ("start", "end")}


def checks(A):
    bad = []

    def ok(cond, msg):
        if not cond:
            bad.append(msg)

    def run(setrow=None, **kw):
        d = build(**kw)
        return A.analyse(d["stamps"], d["n24"], d["n0"], d["arm_b"], d["coh24"], d["coh0"], d["run24"], d["run0"], d["late24"], d["late0"], d["ref"], fake_status, {"PASS": True},
                         setrow if setrow is not None else A.row_set(rb(24), rb(0)))

    # ---- verdict (pure), both bars, both sides ------------------------------------------------------------------------------------------------------
    base = dict.fromkeys(A.VALIDITY, True)
    def v(net_lo=0.0, net_hi=0.05, u_lo=0.0, u_hi=0.01, **over):
        d = dict(base); d.update(net_lo=net_lo, net_hi=net_hi, u_lo=u_lo, u_hi=u_hi); d.update(over); return A.verdict(d)
    ok(v() == ("SETTLED", False), "verdict: small effect, small U reads SETTLED")
    ok(v(net_hi=0.145)[0] == "SETTLED", "verdict: CI_hi(NET) 0.145 < 0.15 is SETTLED")
    ok(v(net_hi=0.15)[0] == "BETWEEN", "verdict: CI_hi(NET) == 0.15 is NOT SETTLED (strict)")
    ok(v(u_hi=0.0205)[0] == "SETTLED" and v(u_hi=0.021)[0] == "SETTLED", "verdict: CI_hi(dU') at or below 0.021 is SETTLED (inclusive)")
    ok(v(u_hi=0.0211)[0] == "BETWEEN", "verdict: CI_hi(dU') just above 0.021 is not SETTLED")
    ok(v(net_lo=0.15, net_hi=0.30)[0] == "GRID", "verdict: CI_lo(NET) == 0.15 is GRID (inclusive)")
    ok(v(net_lo=0.1499, net_hi=0.30)[0] == "BETWEEN", "verdict: CI_lo(NET) just below 0.15 is BETWEEN")
    ok(v(u_lo=0.0211, u_hi=0.05)[0] == "GRID", "verdict: CI_lo(dU') just above 0.021 is GRID")
    ok(v(u_lo=0.021, u_hi=0.05)[0] == "BETWEEN", "verdict: CI_lo(dU') == 0.021 is not GRID (strict)")
    ok(v(net_lo=-0.2, net_hi=-0.01) == ("SETTLED", True), "verdict: CI_hi(NET) < 0 is SETTLED with the OSD-costs-decodes flag")
    ok(v(net_lo=-0.2, net_hi=0.0) == ("SETTLED", False), "verdict: CI_hi(NET) == 0 raises no flag")
    for k in A.VALIDITY:
        ok(v(**{k: False}) == ("VOID", False), f"verdict: {k} failing reads VOID, whatever the precision rows say")
        ok(v(net_lo=0.5, net_hi=0.9, **{k: False})[0] == "VOID", f"verdict: {k} failing with a GRID-sized effect still reads VOID")

    # ---- V-SET ---------------------------------------------------------------------------------------------------------------------------------------
    ok(A.row_set(rb(24), rb(0))["PASS"], "V-SET: equal readbacks except nhard pass")
    x = rb(0); x["end"] = x["end"].replace("shim=20260072", "shim=20260071")
    ok(not A.row_set(rb(24), x)["PASS"], "V-SET: a different token other than nhard fails")
    ok(not A.row_set(rb(24), rb(24))["PASS"], "V-SET: N0 reading nhard=24 fails")
    ok(not A.row_set(rb(0), rb(0))["PASS"], "V-SET: N24 reading nhard=0 fails")
    ok(not A.row_set(rb(24, cq="False"), rb(0, cq="False"))["PASS"], "V-SET: cqap=False fails (the station stack has CQ-AP ON)")
    y = rb(0); del y["end"]
    ok(not A.row_set(rb(24), y)["PASS"], "V-SET: a missing readback tag fails")

    # ---- end to end ----------------------------------------------------------------------------------------------------------------------------------
    r = run(differ_only=True)
    ok(r["verdict"] == "SETTLED" and r["C-NET"]["NET_pp"] == 0.0 and r["C-U"]["dU_ta"] == 0.0, f"S1: identical decodes plus one tested_present row: SETTLED, NET 0, dU' 0 (got {r['verdict']})")
    ok(r["V-WIRE"]["PASS"] and r["V-WIRE"]["cycles_with_different_published_rows"] == 1, "S1: V-WIRE sees the one differing cycle")
    r = run()
    ok(not r["V-WIRE"]["PASS"] and r["verdict"] == "VOID", "S0: identical published rows fail V-WIRE and read VOID")
    r = run(n24_corr=1)
    ok(r["verdict"] == "GRID" and r["C-NET"]["CI"][0] >= 0.15 and r["N24"]["corroborated"] - r["N0"]["corroborated"] == N, "S2: +1 corroborated row per cycle reads GRID")
    ok(r["descriptive"]["N24_only_corroborated_by_batch"] == {1: N}, "S2: the corroborated new rows are counted in their batch (1)")
    r = run(n24_ta=1, differ_only=True)
    ok(r["verdict"] == "GRID" and r["C-U"]["dU_ta"] == 1.0, "S3: one tested_absent new row per cycle: dU' 1.0, GRID")
    r = run(n24_ta=1, ta_kind=1)
    ok(r["C-U"]["dU_ta"] == 1.0, "S3b: a tested_absent new row in batch 1 counts (all batches)")
    r = run(n24_ta=1, ta_kind=5)
    ok(r["C-U"]["dU_ta"] == 1.0 and r["descriptive"]["N24_only_tested_absent_by_batch"] == {5: N}, "S3c: batch 5 counts and is reported by batch")
    r = run(n0_only_corr=1, differ_only=True)
    ok(r["verdict"] == "SETTLED" and r["flag_OSD_costs_decodes"] and r["C-NET"]["NET_pp"] < 0, "S4: N0 holds one more corroborated row per cycle: NET negative, SETTLED with the OSD-costs flag")
    ok(r["descriptive"]["N0_only_text_rows_total"] == N, "S4: N0-only rows counted (descriptive)")
    r = run(n24_ta=2, n24_tp=1, n24_hu=1, n24_unt=1)
    uc = r["descriptive"]["U-COV"]
    ok((uc["tested_absent"], uc["tested_present"], uc["hashed_or_unencodable"], uc["untestable_class"]) == (2 * N, N, N, N) and uc["not_corroborated"] == 5 * N, "S5: U-COV counts every class")
    ok(abs(uc["share_of_not_corroborated_judged_by_U_prime"] - 3 / 5) < 1e-12, "S5: U-COV share judged = (absent + present) / not corroborated = 3/5")
    r = run(n24_corr=1, differ_only=True)
    ok(r["descriptive"]["CQ_AP_effect_on_the_v2_stack_N24_minus_arm_B_descriptive"]["corroborated_N24"] - r["descriptive"]["CQ_AP_effect_on_the_v2_stack_N24_minus_arm_B_descriptive"]["corroborated_arm_B"] == N,
       "S6: the descriptive N24 minus arm B line is computed against arm B")
    ok(json.dumps(run(n24_corr=1), sort_keys=True, default=float) == json.dumps(run(n24_corr=1), sort_keys=True, default=float), "S7: deterministic")
    return bad


def load_module():
    import nhard_analyse as M
    return importlib.reload(M)


def mutants():
    def c(name, value):
        return lambda m: setattr(m, name, value)

    def verdict_with(fn):
        def patch(m):
            m.verdict = lambda r: fn(m, r)
        return patch

    def settled_ge(m, r):
        if not all(r[k] for k in m.VALIDITY): return "VOID", False
        flag = r["net_hi"] < 0
        if r["net_hi"] <= m.BAR_NET_PP and r["u_hi"] <= m.BAR_U: return "SETTLED", flag
        if r["net_lo"] >= m.BAR_NET_PP or r["u_lo"] > m.BAR_U: return "GRID", flag
        return "BETWEEN", flag

    def u_strict(m, r):
        if not all(r[k] for k in m.VALIDITY): return "VOID", False
        flag = r["net_hi"] < 0
        if r["net_hi"] < m.BAR_NET_PP and r["u_hi"] < m.BAR_U: return "SETTLED", flag
        if r["net_lo"] >= m.BAR_NET_PP or r["u_lo"] > m.BAR_U: return "GRID", flag
        return "BETWEEN", flag

    def grid_gt(m, r):
        if not all(r[k] for k in m.VALIDITY): return "VOID", False
        flag = r["net_hi"] < 0
        if r["net_hi"] < m.BAR_NET_PP and r["u_hi"] <= m.BAR_U: return "SETTLED", flag
        if r["net_lo"] > m.BAR_NET_PP or r["u_lo"] > m.BAR_U: return "GRID", flag
        return "BETWEEN", flag

    def u_lo_ge(m, r):
        if not all(r[k] for k in m.VALIDITY): return "VOID", False
        flag = r["net_hi"] < 0
        if r["net_hi"] < m.BAR_NET_PP and r["u_hi"] <= m.BAR_U: return "SETTLED", flag
        if r["net_lo"] >= m.BAR_NET_PP or r["u_lo"] >= m.BAR_U: return "GRID", flag
        return "BETWEEN", flag

    def no_flag(m, r):
        v, f = orig_verdict(m, r); return v, False

    def flag_le(m, r):
        v, f = orig_verdict(m, r); return v, r["net_hi"] <= 0

    def no_wire_validity(m, r):
        rr = dict(r); rr["V-WIRE"] = True; return orig_verdict(m, rr)

    def ignore_cqap(m):
        m.row_set = lambda a, b: {"PASS": all(("nhard=24 " in a.get(t, "") and "nhard=0 " in b.get(t, "")) for t in ("start", "end"))}

    def no_strip(m):
        m.row_set = lambda a, b: {"PASS": all(a.get(t) == b.get(t) and a.get(t) for t in ("start", "end"))}

    orig_holder = {}

    def orig_verdict(m, r):
        return orig_holder["f"](r)

    def wrap(fn):
        def patch(m):
            orig_holder["f"] = m.verdict
            m.verdict = lambda r: fn(m, r)
        return patch

    return [("BAR_NET_PP 0.15 -> 0.16", c("BAR_NET_PP", 0.16)), ("BAR_NET_PP 0.15 -> 0.14", c("BAR_NET_PP", 0.14)), ("BAR_U 0.021 -> 0.022", c("BAR_U", 0.022)),
            ("BAR_U 0.021 -> 0.02", c("BAR_U", 0.02)), ("SETTLED uses <= on CI_hi(NET)", verdict_with(settled_ge)), ("SETTLED uses < on CI_hi(dU')", verdict_with(u_strict)),
            ("GRID uses > on CI_lo(NET)", verdict_with(grid_gt)), ("GRID uses >= on CI_lo(dU')", verdict_with(u_lo_ge)),
            ("a validity failure reads BETWEEN", wrap(lambda m, r: ("BETWEEN", False) if not all(r[k] for k in m.VALIDITY) else orig_verdict(m, r))),
            ("no OSD-costs flag", wrap(no_flag)), ("flag on CI_hi <= 0", wrap(flag_le)), ("V-WIRE not a validity row", wrap(no_wire_validity)),
            ("dU' counts batches 4 and 5 only", c("ALL_KINDS", (4, 5))), ("V-SET ignores cqap", ignore_cqap), ("V-SET compares unstripped lines", no_strip)]


def main():
    bad = checks(load_module())
    for b in bad:
        print("FAIL:", b)
    if bad:
        sys.exit(1)
    print("self-test: 0 failed checks on the real module")
    killed = []
    for name, patch in mutants():
        m = load_module()
        patch(m)
        b2 = checks(m)
        print(f"mutant {name}: {'KILLED' if b2 else 'SURVIVED'} ({len(b2)} checks failed)")
        killed.append(bool(b2))
    load_module()
    if not all(killed):
        print("A MUTANT SURVIVED: the self-test cannot see it")
        sys.exit(2)
    print(f"ALL PASSED; {len(killed)} mutations killed")


if __name__ == "__main__":
    main()
