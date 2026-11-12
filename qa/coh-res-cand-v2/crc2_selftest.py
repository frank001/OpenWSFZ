"""Synthetic self-test for crc2_analyse (Q-prefix calls only, no real data, no WAVs; NFR-021). Must pass, and every mutation below must be KILLED, before the freeze is committed.

It builds a small synthetic night (40 cycles, the real B-OFF length) with KNOWN numbers of A rows, new corroborated / tested_absent / tested_present rows, abandons, late-round abandons and res* fields,
runs the SAME analyse() the real run uses (with a fake WSJT-X reference and a fake instrument injected), and asserts every row, every verdict branch and the boundaries of the
predicates; then applies each mutation to the analysis module and asserts the checks FAIL (a check that cannot fail is not a check).

    python crc2_selftest.py
"""
import importlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

N = 40


def stamp(i):
    return f"261110_18{47 + i // 4:02d}{(i % 4) * 15:02d}"


def call(k):
    return f"Q{k % 10}{chr(65 + (k // 10) % 26)}{chr(65 + (k // 260) % 26)}"


def row(kind, f, text, matched=0, dt=0.10, snr=-10, path=0, ap=0):
    return dict(kind=kind, matched=matched, f=f, dt=dt, snr=snr, path=path, text=text, ap=ap)


def build(n_new_corr=0, n_new_ta=0, n_new_tp=0, drop_a=None, hashed_exc=None, dup=False, a_kind5_missing_in_b=False, ta_kind=4, b_abandon=(), b_res_abandon=(),
          a_abandon=(), a_late=0, b_late=0, no_snapshot=0, no_new_fields=False, res_kept=None):
    stamps = [stamp(i) for i in range(N)]
    a, b, ref = {}, {}, {}
    for i, s in enumerate(stamps):
        base = [row(1, 1000 + 10 * j, f"CQ {call(100 * i + j)} JO22", matched=1) for j in range(3)] + [row(2, 1100, f"{call(100 * i + 50)} {call(100 * i + 51)} -07", matched=1),
                                                                                                         row(4, 1200, f"{call(100 * i + 60)} {call(100 * i + 61)} R-12", matched=1),
                                                                                                         row(5, 1300, f"{call(100 * i + 70)} {call(100 * i + 71)} RR73", matched=1)]
        a[s] = [dict(x) for x in base]
        ref[s] = [(-10, 0.1, x["f"], x["text"]) for x in base]
        brows = [dict(x) for x in base]
        k = 0
        for _ in range(n_new_corr):
            t = f"CQ {call(5000 + 10 * i + k)} KO11"; k += 1
            brows.append(row(4, 2000 + 10 * k, t, matched=1)); ref[s].append((-12, 0.1, 2000 + 10 * k, t))
        for _ in range(n_new_ta):
            brows.append(row(ta_kind, 2500 + 10 * k, f"TA {call(6000 + 10 * i + k)} {call(6100 + k)} -15")); k += 1
        for _ in range(n_new_tp):
            brows.append(row(4, 2800 + 10 * k, f"TP {call(7000 + 10 * i + k)} {call(7100 + k)} -16")); k += 1
        if drop_a is not None and i == 0:
            brows = [x for x in brows if x["text"] != a[s][drop_a]["text"]]
        if hashed_exc is not None and i == 0:
            a[s].append(row(2, 1450, "<Q9ZZ> Q8YY -11", matched=0, dt=0.30))
            if hashed_exc == "same-f-dt":
                brows.append(row(2, 1450, "Q9ZZ Q8YY -11", matched=0, dt=0.30))
            elif hashed_exc == "other-f":
                brows.append(row(2, 1460, "Q9ZZ Q8YY -11", matched=0, dt=0.30))
        if a_kind5_missing_in_b and i == 0:
            brows = [x for x in brows if x["kind"] != 5]
        if dup and i == 0:
            brows.append(dict(brows[0]))
        b[s] = brows
    coh_a = [dict(stamp=s, seen="1", abandoned="1" if s in a_abandon else "0") for s in stamps]
    coh_b = []
    for i, s in enumerate(stamps):
        r = dict(stamp=s, seen="1", abandoned="1" if s in b_abandon else "0")
        if not no_new_fields:
            r.update(rescand="residual-R3", resrun="no-snapshot" if i < no_snapshot else "ran", resnew=str(n_new_ta + n_new_corr + n_new_tp), resnewgated="0",
                     resnewkept=str(res_kept if res_kept is not None else n_new_ta + n_new_corr + n_new_tp), resabandoned="2" if s in b_res_abandon else "0", reswallms="400")
        coh_b.append(r)
    late_a = [dict(stamp=s, outcome="abandoned" if i < a_late else "ran") for i, s in enumerate(stamps)]
    late_b = [dict(stamp=s, outcome="abandoned" if i < b_late else "ran") for i, s in enumerate(stamps)]
    run = [dict(stamp=s, tb1_ms="500", tb2_ms="2500", tb3_ms="-1.0", tb4_ms=str(4500 + 10 * i), tb5_ms="-1.0") for i, s in enumerate(stamps)]
    return dict(stamps=stamps, a=a, b=b, coh_a=coh_a, coh_b=coh_b, late_a=late_a, late_b=late_b, run_a=run, run_b=run, ref=ref)


def fake_status(stamp_, text, freq, dt):
    if "<" in text:
        return "hashed_or_unencodable"
    if text.startswith("TA "):
        return "tested_absent"
    if text.startswith("TP "):
        return "tested_present"
    return "untestable_class"


def checks(A):
    """All the assertions, against the analysis module A (the real one, or a mutant). Returns the list of failed-check messages."""
    bad = []

    def ok(cond, msg):
        if not cond:
            bad.append(msg)

    def run(**kw):
        d = build(**kw)
        return A.analyse(d["stamps"], d["a"], d["b"], d["coh_a"], d["coh_b"], d["late_a"], d["late_b"], d["run_a"], d["run_b"], d["ref"], fake_status, {"PASS": True}, {"PASS": True})

    # ---- verdict branches (pure) --------------------------------------------------------------------------------------------------------------------
    good = dict.fromkeys(A.VALIDITY, True)
    good.update({"N-GO": True, "N-STOP": False, "U-OK": True, "U-FAIL": False, "B-AB": True, "B-LATE": True})
    ok(A.verdict(good) == "ACCEPT", "verdict: all pass reads ACCEPT")
    for k in A.VALIDITY:
        x = dict(good); x[k] = False
        ok(A.verdict(x) == "VOID", f"verdict: {k} failing reads VOID")
        x.update({"N-GO": False, "N-STOP": True})
        ok(A.verdict(x) == "VOID", f"verdict: {k} failing with N-STOP still reads VOID (nothing else is read)")
    for k, v in (("N-GO", False), ("U-OK", False), ("B-AB", False), ("B-LATE", False)):
        x = dict(good); x[k] = v
        ok(A.verdict(x) == "OPEN", f"verdict: {k} failing alone reads OPEN")
    x = dict(good); x.update({"N-GO": False, "N-STOP": True})
    ok(A.verdict(x) == "FAIL", "verdict: N-STOP reads FAIL")
    x = dict(good); x.update({"U-OK": False, "U-FAIL": True})
    ok(A.verdict(x) == "FAIL", "verdict: U-FAIL reads FAIL")
    x = dict(good); x.update({"U-OK": False, "U-FAIL": True, "B-AB": False})
    ok(A.verdict(x) == "FAIL", "verdict: U-FAIL with B-AB failing reads FAIL (FAIL before ACCEPT conditions)")

    # ---- CI predicates, both sides of each bar ------------------------------------------------------------------------------------------------------
    r = A.ci_rows([1e-9, 1.0], [0.0, 0.021])
    ok(r["N-GO"] and not r["N-STOP"] and r["U-OK"] and not r["U-FAIL"], "ci_rows: CI_lo just above 0 is N-GO; CI_hi == 0.021 is U-OK")
    r = A.ci_rows([0.0, 1.0], [0.0, 0.0211])
    ok(not r["N-GO"], "ci_rows: CI_lo == 0 is NOT N-GO (strict)")
    ok(not r["U-OK"], "ci_rows: CI_hi just above 0.021 is NOT U-OK")
    r = A.ci_rows([-1.0, 0.0], [0.0211, 0.05])
    ok(r["N-STOP"] and r["U-FAIL"], "ci_rows: CI_hi == 0 is N-STOP; CI_lo just above 0.021 is U-FAIL")
    r = A.ci_rows([-1.0, 1e-9], [0.021, 0.05])
    ok(not r["N-STOP"] and not r["U-FAIL"], "ci_rows: CI_hi just above 0 is not N-STOP; CI_lo == 0.021 is not U-FAIL (strict)")

    # ---- end to end ---------------------------------------------------------------------------------------------------------------------------------
    res = run(n_new_corr=1)
    ok(res["verdict"] == "ACCEPT", f"S0: +1 corroborated new row per cycle, nothing else, reads ACCEPT (got {res['verdict']})")
    ok(res["B"]["corroborated"] - res["A"]["corroborated"] == N, "S0: B corroborates N more rows than A")
    ok(abs(res["result"]["NET_pp"] - 100.0 * N / res["n_ref"]) < 1e-9, "S0: NET_pp is exactly 100 * extra / n_ref")
    ok(res["result"]["dU_ta"] == 0.0 and res["rows"]["U-OK"], "S0: no tested_absent, U-OK")
    ok(res["B-WIRE"]["PASS"] and res["B-KEEP"]["PASS"] and res["B-DUP"]["PASS"] and res["B-AB"]["PASS"] and res["B-LATE"]["PASS"], "S0: the other rows pass")
    ok(json.dumps(run(n_new_corr=1), sort_keys=True, default=float) == json.dumps(res, sort_keys=True, default=float), "S0: deterministic (two runs identical)")
    res = run(n_new_corr=1, n_new_ta=1)
    ok(res["result"]["dU_ta"] == 1.0 and res["rows"]["U-FAIL"] and res["verdict"] == "FAIL", "S1: one tested_absent new row per cycle: dU'_ta 1.0, U-FAIL, FAIL")
    res = run(n_new_corr=1, n_new_tp=2)
    ok(res["result"]["dU_ta"] == 0.0 and res["result"]["dU_present"] == 2.0, "S1b: tested_present rows are not tested_absent (counted separately)")
    res = run(n_new_corr=1, n_new_ta=1, ta_kind=5)
    ok(res["result"]["dU_ta"] == 1.0, "S1c: a tested_absent new row in batch 5 counts (batches 4 and 5)")
    res = run(res_kept=1)
    ok(res["rows"]["N-STOP"] and not res["rows"]["N-GO"] and res["verdict"] == "FAIL", "S2: B equal to A: NET 0, N-STOP, FAIL")
    res = run(n_new_corr=1, drop_a=0)
    ok(not res["B-KEEP"]["PASS"] and res["verdict"] == "VOID", "S3: an A row of batches 1-4 missing from B fails B-KEEP and the verdict is VOID")
    res = run(n_new_corr=1, hashed_exc="same-f-dt")
    ok(res["B-KEEP"]["PASS"] and res["B-KEEP"]["hashed_rerendering_exceptions"] == 1 and res["B-KEEP"]["missing"] == 0, "S4a: a hashed re-rendering at the same freq and dt is an allowed, counted exception")
    res = run(n_new_corr=1, hashed_exc="other-f")
    ok(not res["B-KEEP"]["PASS"], "S4b: a missing hashed row with no same-freq-and-dt B row is a missing row")
    res = run(n_new_corr=1, a_kind5_missing_in_b=True)
    ok(res["B-KEEP"]["PASS"] and res["descriptive"]["A_only_batch5_rows"] == 1, "S4c: an A batch-5 row missing in B is outside B-KEEP and counted descriptively")
    res = run(n_new_corr=1, b_res_abandon=[stamp(0), stamp(1), stamp(2)])
    ok(not res["B-AB"]["PASS"] and res["verdict"] == "OPEN", "S5a: resAbandoned in 3 B cycles with 0 A abandons fails B-AB (Amendment 3): OPEN")
    res = run(n_new_corr=1, a_abandon=[stamp(0), stamp(1), stamp(2)], b_res_abandon=[stamp(3), stamp(4), stamp(5)])
    ok(res["B-AB"]["PASS"], "S5b: 3 B cycles with resAbandoned against 3 A cycles with abandoned passes (<=)")
    res = run(n_new_corr=1, a_abandon=[stamp(0), stamp(1), stamp(2)], b_abandon=[stamp(0)], b_res_abandon=[stamp(0), stamp(3), stamp(4), stamp(5)])
    ok(res["B-AB"]["B_cycles_abandoned_or_resAbandoned_gt_0"] == 4 and not res["B-AB"]["PASS"], "S5c: a cycle with both abandoned and resAbandoned counts once; 4 against 3 fails")
    res = run(n_new_corr=1, a_late=2, b_late=7)
    ok(res["B-LATE"]["PASS"], "S6a: B-LATE 7 <= 2 + 5 passes")
    res = run(n_new_corr=1, a_late=2, b_late=8)
    ok(not res["B-LATE"]["PASS"] and res["verdict"] == "OPEN", "S6b: B-LATE 8 > 2 + 5 fails: OPEN")
    res = run(n_new_corr=1, no_snapshot=1)
    ok(not res["B-WIRE"]["i"] and res["verdict"] == "VOID", "S7a: one no-snapshot cycle in 20 fails B-WIRE (i) (100 % required): VOID")
    res = run(n_new_corr=0)
    ok(not res["B-WIRE"]["ii"] or res["B-WIRE"]["cycles_with_resNewGated_or_resNewKept_gt_0"] == 0, "S7b: no cycle with resNewGated or resNewKept > 0 fails B-WIRE (ii)")
    res = run(n_new_corr=1, no_new_fields=True)
    ok(not res["B-WIRE"]["PASS"], "S7c: a coh.csv without the res columns cannot pass B-WIRE")
    res = run(n_new_corr=1, dup=True)
    ok(not res["B-DUP"]["PASS"] and res["B-DUP"]["duplicate_text_instances_in_B"] == 1 and res["verdict"] == "VOID", "S8: a text twice in a cycle fails B-DUP: VOID")

    # ---- B-OFF: every field, the cycle count, the outside cycles ----------------------------------------------------------------------------------------
    d = build(n_new_corr=0)
    s40 = d["stamps"][:40]
    same = {s: [dict(x) for x in d["a"][s]] for s in s40}
    r = A.row_boff(d["a"], same, s40)
    ok(r["identical_cycles"] == 40 and r["PASS"], "S11a: 40 identical cycles pass B-OFF")
    ok(not A.row_boff(d["a"], same, s40[:39])["PASS"], "S11a2: 39 cycles cannot pass B-OFF")
    for fld, val in (("matched", 0), ("f", 1), ("dt", 0.11), ("snr", -99), ("path", 9), ("text", "Q0AA Q0AB 73"), ("ap", 1), ("kind", 3)):
        alt = {s: [dict(x) for x in d["a"][s]] for s in s40}
        alt[s40[3]][1][fld] = (alt[s40[3]][1][fld] + val) if fld in ("f", "snr") else val
        r = A.row_boff(d["a"], alt, s40)
        ok(r["identical_cycles"] == len(s40) - 1, f"S11b: a difference in {fld} is seen by B-OFF")
    alt = {s: [dict(x) for x in d["a"][s]] for s in s40}
    alt["261110_999999"] = []
    ok(A.row_boff(d["a"], alt, s40)["cycles_in_B_outside_the_40"] == 1, "S11c: a B cycle outside the 40 is counted")

    # ---- loader ------------------------------------------------------------------------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "nc.tsv")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\t".join(["261110_184745", "4", "1", "1234", "0.20", "-9", "0", "0", "20", "2", "Q1AA  Q2BB   -07", "1"]) + "\n")
            f.write("\t".join(["261110_184745", "1", "0", "1000", "0.10", "5", "0", "0", "20", "0", "CQ Q3CC JO22", "0"]) + "\n")
        got = A.load_nc(p)["261110_184745"]
        ok([x["kind"] for x in got] == [1, 4] and got[1]["text"] == "Q1AA Q2BB -07" and got[1]["ap"] == 1 and got[1]["matched"] == 1 and got[1]["dt"] == 0.2, "loader: sorted by kind, text normalised, ap and matched read")
    return bad


def load_module():
    import crc2_analyse as M
    return importlib.reload(M)


def mutants():
    """(name, patch(M)). Each patch makes the module wrong in one way; the checks must then fail."""
    def p_const(name, value):
        return lambda m: setattr(m, name, value)

    def ab_ignores_res(m):
        m.row_ab = lambda ca, cb: {"PASS": sum(1 for r in cb if int(r["abandoned"]) > 0) <= sum(1 for r in ca if int(r["abandoned"]) > 0),
                                   "A_cycles_abandoned_gt_0": 0, "B_cycles_abandoned_or_resAbandoned_gt_0": 0}

    def ab_strict(m):
        orig = m.row_ab
        m.row_ab = lambda ca, cb: dict(orig(ca, cb), PASS=orig(ca, cb)["B_cycles_abandoned_or_resAbandoned_gt_0"] < orig(ca, cb)["A_cycles_abandoned_gt_0"])

    def keep_always_pass(m):
        orig = m.row_keep
        m.row_keep = lambda a, b, st: dict(orig(a, b, st), PASS=True)

    def verdict_void_as_open(m):
        orig = m.verdict
        m.verdict = lambda rows: "OPEN" if orig(rows) == "VOID" else orig(rows)

    def ngo_ge(m):
        m.ci_rows = lambda n, u: {"N-GO": n[0] >= m.BAR_NET_PP, "N-STOP": n[1] <= m.BAR_NET_PP, "U-OK": u[1] <= m.U_BAR, "U-FAIL": u[0] > m.U_BAR}

    def uok_lt(m):
        m.ci_rows = lambda n, u: {"N-GO": n[0] > m.BAR_NET_PP, "N-STOP": n[1] <= m.BAR_NET_PP, "U-OK": u[1] < m.U_BAR, "U-FAIL": u[0] > m.U_BAR}

    def dup_always_pass(m):
        m.row_dup = lambda b: {"PASS": True, "duplicate_text_instances_in_B": 0}

    def boff_ignores_ap(m):
        m.key_full = lambda x: (x["kind"], x["matched"], x["f"], round(x["dt"], 2), x["snr"], x["path"], x["text"])

    def boff_ignores_text(m):
        m.key_full = lambda x: (x["kind"], x["matched"], x["f"], round(x["dt"], 2), x["snr"], x["path"], x["ap"])

    return [("LATE_SLACK 5 -> 4", p_const("LATE_SLACK", 4)), ("LATE_SLACK 5 -> 6", p_const("LATE_SLACK", 6)), ("B-AB ignores resAbandoned", ab_ignores_res),
            ("B-AB strict (<)", ab_strict), ("WIRE_SHARE 1.0 -> 0.9", p_const("WIRE_SHARE", 0.9)), ("B-KEEP always passes", keep_always_pass),
            ("verdict: a validity failure reads OPEN", verdict_void_as_open), ("N-GO uses >=", ngo_ge), ("U-OK uses <", uok_lt), ("B-DUP always passes", dup_always_pass),
            ("KEEP_MAX_KIND 4 -> 5 (batch 5 inside B-KEEP)", p_const("KEEP_MAX_KIND", 5)), ("U_KINDS (4, 5) -> (4,)", p_const("U_KINDS", (4,))),
            ("B-OFF ignores apKind", boff_ignores_ap), ("B-OFF ignores text", boff_ignores_text), ("N_BOFF 40 -> 39", p_const("N_BOFF", 39))]


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
