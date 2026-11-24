#!/usr/bin/env python3
"""TA-RES self-test: synthetic behaviour tests of tr_lib and tr_prov, then MUTATIONS of both (each must make a test fail).   python tr_selftest.py"""
from __future__ import annotations

import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tr_lib as L          # noqa: E402
import tr_prov as P         # noqa: E402

OK = [0.9, 1.0]


def base(**kw):
    r = {"v_repro_ok": True, "n_Tbur": 237, "ci_B1": OK, "ci_B1m": OK, "ci_Tiso": OK, "ci_ghost_diff": [-0.05, 0.0], "n_resid": 100, "ci_resid": [0.0, 0.02], "ci_Tbur": [0.82, 0.9]}
    r.update(kw)
    return r


def t_source_file():
    assert L.source_file(1, None, "R3", 4) == "O" and L.source_file(2, None, "R3", 4) == "R2"
    assert L.source_file(4, "R3", "R3", 4) == "R3" and L.source_file(4, "R2", "R2", 3) == "R2" and L.source_file(4, "O", "R3", 4) == "O"
    assert L.source_file(4, None, "R3", 4) is None and L.source_file(4, "X3", "R3", 4) is None
    assert L.source_file(5, None, "R3", 4) == "X3" and L.source_file(5, None, "R2", 3) == "R3" and L.source_file(5, None, "R3", 2) is None
    assert L.source_file(3, None, "R3", 4) is None


def t_subtracted_before():
    s = L.subtracted_before
    assert s(1, True, "R2") and s(1, True, "R3") and s(1, True, "X3")
    assert not s(2, True, "R2") and s(2, True, "R3") and s(2, True, "X3")
    assert not s(3, True, "R3") and s(3, True, "X3") and s(4, True, "X3") and not s(5, True, "X3")
    assert not s(1, True, "O") and not s(1, False, "R3") and not s(None, True, "R3") and not s(1, True, "Z")


def t_reencodable():
    assert L.reencodable("CQ Q1ABC AB12") and not L.reencodable("CQ <Q1ABC> AB12") and not L.reencodable("CQ Q1ABC") and L.reencodable("A B C")


def t_decide_rows():
    assert L.decide(base()) == "REPAIRED"
    assert L.decide(base(v_repro_ok=False)) == "VOID" and L.decide(base(n_Tbur=99)) == "VOID"
    for k in ("ci_B1", "ci_B1m", "ci_Tiso"):
        assert L.decide(base(**{k: [0.79, 1.0]})) == "VOID", k
        assert L.decide(base(**{k: [0.80, 1.0]})) == "REPAIRED", k
    assert L.decide(base(ci_ghost_diff=[0.0, 0.051])) == "CREDULOUS" and L.decide(base(ci_ghost_diff=[0.0, 0.05])) == "REPAIRED"
    assert L.decide(base(ci_resid=[0.0, 0.051])) == "CREDULOUS" and L.decide(base(ci_resid=[0.0, 0.05])) == "REPAIRED"
    assert L.decide(base(n_resid=59, ci_resid=[0.0, 0.0])) == "UNGUARDED" and L.decide(base(n_resid=60)) == "REPAIRED"
    assert L.decide(base(n_resid=59, ci_resid=[0.5, 0.9])) == "UNGUARDED"           # V-N2 fails: the residue side is not read, so it cannot fail the row
    assert L.decide(base(n_resid=59, ci_Tbur=[0.79, 0.9])) == "NOT-REPAIRED"
    assert L.decide(base(ci_Tbur=[0.79, 0.9])) == "NOT-REPAIRED" and L.decide(base(ci_Tbur=[0.80, 0.9])) == "REPAIRED"
    assert L.decide(base(ci_Tiso=[0.5, 0.7], ci_ghost_diff=[0, 0.5])) == "VOID"       # first match wins
    assert L.decide(base(ci_ghost_diff=[0, 0.5], n_resid=10)) == "CREDULOUS"           # CREDULOUS before UNGUARDED
    assert L.decide(base(ci_ghost_diff=[0, 0.5], ci_Tbur=[0.1, 0.2])) == "CREDULOUS"


def t_source_of_follows_merge():
    s = P.source_of
    assert s({0: "N"}, "R3") == ("R3", 1) and s({0: "G"}, "R3") == ("R3", 1)           # run 0 admits gated-out rows (ungated 1)
    assert s({0: "N", 1: "N"}, "R3") == ("R3", 2)                                       # both found it: the residual run's row is kept
    assert s({0: "N", 1: "N", 2: "N"}, "R2") == ("R2", 3)
    assert s({1: "N"}, "R3") == ("O", 1) and s({1: "G"}, "R3") == (None, 0)             # the original run's gated-out row is never admitted
    assert s({0: "G", 1: "N"}, "R3") == ("R3", 2)
    assert s({2: "N"}, "R3") == ("R3", 1) and s({2: "N"}, "R2") == ("R2", 1)            # v2's third run reads the residual audio
    assert s({1: "N", 2: "N"}, "R3") == ("O", 2)                                        # original-run row wins over the third run (Merge's input)
    assert s({0: "N"}, "O") == ("O", 1)                                                  # no residual buffer: run 0 read the original
    assert s({2: "N"}, "O") == (None, 1)
    assert s({0: "G"}, "none") == ("O", 1) and s({}, "R3") == (None, 0)


def t_resolve_published():
    found = {"s1": {"AA": {0: "N", 1: "N"}, "BB": {1: "N"}, "CC": {}}}
    utext = {"s1": {"CQ A": ["AA"], "CQ B": ["BB"], "CQ C": ["CC"], "CQ D": ["ZZ"], "X": ["AA", "BB"]}}
    cap = {"s1": {"level": "R3", "calls": 4, "n_runs": 3}}
    assert P.resolve_published("s1", "CQ A", found, utext, cap) == ("R3", 2, "ok")
    assert P.resolve_published("s1", "CQ B ", found, utext, cap) == ("O", 1, "ok")
    assert P.resolve_published("s1", "CQ C", found, utext, cap) == (None, 0, "unresolved")
    assert P.resolve_published("s1", "CQ D", found, utext, cap) == (None, 0, "unresolved")
    assert P.resolve_published("s1", "NOPE", found, utext, cap) == (None, 0, "no_unpack")
    assert P.resolve_published("s1", "X", found, utext, cap) == ("R3", 2, "ok")        # two payloads for one text: the first that resolves


def t_read_capture_index(tmp="tr_selftest_capidx.tsv"):
    line = "261110_184745\t4\t180000|180000|180000|180000\t18|6|6|7\tA\tB\tC\t3\t180000|180000|180000\tR3\tO\t168"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        assert P.read_capture_index(tmp) == {"261110_184745": {"calls": 4, "level": "R3", "n_runs": 3}}
    finally:
        os.remove(tmp)


TESTS = [t_source_file, t_subtracted_before, t_reencodable, t_decide_rows, t_source_of_follows_merge, t_resolve_published, t_read_capture_index]


def run_tests():
    bad = []
    for t in TESTS:
        try:
            t()
        except AssertionError:
            bad.append(t.__name__)
        except Exception as e:                 # noqa: BLE001
            bad.append(t.__name__ + ":" + type(e).__name__)
    return bad


def src_mut(mod, old, new, old2=None, new2=None):
    name = "tr_lib.py" if mod == "L" else "tr_prov.py"
    def m():
        s = open(os.path.join(HERE, name), encoding="utf-8").read()
        assert old in s, old
        s = s.replace(old, new, 1)
        if old2:
            assert old2 in s, old2
            s = s.replace(old2, new2, 1)
        ns = {}
        exec(compile(s, name + "_mut", "exec"), ns)
        target = L if mod == "L" else P
        for k, v in ns.items():
            if not k.startswith("__"):
                setattr(target, k, v)
    return m


MUTS = [
    ("batch 1 not O", src_mut("L", 'if batch == 1:\n        return "O"', 'if batch == 1:\n        return "R2"')),
    ("batch 2 not R2", src_mut("L", 'if batch == 2:\n        return "R2"', 'if batch == 2:\n        return "R3"')),
    ("batch 5 always X3", src_mut("L", 'return "X3" if calls == 4 else ("R3" if calls == 3 else None)', 'return "X3"')),
    ("batch 4 label ignored", src_mut("L", 'return prov_label if prov_label in ("O", "R2", "R3") else None', 'return "R3"')),
    ("subtracted: O allowed", src_mut("L", 'or source == "O":', 'or source == "Z":', '{"R2": 1, "R3": 2, "X3": 4}', '{"O": 4, "R2": 1, "R3": 2, "X3": 4}')),
    ("subtracted: limits shifted", src_mut("L", '{"R2": 1, "R3": 2, "X3": 4}', '{"R2": 1, "R3": 1, "X3": 4}')),
    ("subtracted: ignores reencodable", src_mut("L", "if not reencodable or neigh_batch is None", "if neigh_batch is None")),
    ("subtracted: b < limit", src_mut("L", "neigh_batch <= limit", "neigh_batch < limit")),
    ("reencodable: tokens 2", src_mut("L", "len(text.split()) >= 3", "len(text.split()) >= 2")),
    ("reencodable: hash ok", src_mut("L", '"<" not in text and ', "")),
    ("VOID drops T_iso", src_mut("L", ' or r["ci_Tiso"][0] < BAR', "")),
    ("VOID drops V-REPRO", src_mut("L", '(not r["v_repro_ok"]) or ', "")),
    ("VOID drops V-N", src_mut("L", 'r["n_Tbur"] < V_N_TBUR or ', "")),
    ("CREDULOUS drops residue", src_mut("L", ' or (n2_ok and r["ci_resid"][1] > BAR_GHOST)', "")),
    ("CREDULOUS residue without V-N2", src_mut("L", "(n2_ok and r[\"ci_resid\"][1] > BAR_GHOST)", "(r[\"ci_resid\"] is not None and r[\"ci_resid\"][1] > BAR_GHOST)")),
    ("UNGUARDED dropped", src_mut("L", '    if (not n2_ok) and see:\n        return "UNGUARDED"\n', "")),
    ("V-N2 60 -> 30", src_mut("L", "V_N2 = 60 ", "V_N2 = 30 ")),
    ("A-SEE on CI_hi", src_mut("L", 'see = r["ci_Tbur"][0] >= BAR', 'see = r["ci_Tbur"][1] >= BAR')),
    ("run 0 gated-out not admitted", src_mut("P", 'f0 = runs.get(0) in ("N", "G")', 'f0 = runs.get(0) == "N"')),
    ("original gated-out admitted", src_mut("P", 'f1 = runs.get(1) == "N"', 'f1 = runs.get(1) in ("N", "G")')),
    ("original before residual", src_mut("P", "    if f0:\n        return (resid if resid else \"O\"), multi", "    if f1:\n        return \"O\", multi\n    if f0:\n        return (resid if resid else \"O\"), multi")),
    ("third run reads O", src_mut("P", "        return resid, multi                                 # the third run", "        return \"O\", multi                                 # the third run")),
    ("multi not counted", src_mut("P", "multi = int(f0) + int(f1) + int(f2)", "multi = 1")),
    ("capture level column", src_mut("P", '"level": p[9]', '"level": p[10]')),
]


def main():
    bad = run_tests()
    print("unmutated: " + ("ALL PASS" if not bad else "FAIL " + str(bad)))
    if bad:
        sys.exit(1)
    surv = []
    for name, m in MUTS:
        importlib.reload(L)
        importlib.reload(P)
        try:
            m()
        except AssertionError as e:
            if any(fr.filename.endswith("_mut") for fr in traceback.extract_tb(e.__traceback__)):
                print(f"{name:34s} killed by the library's own constant assertion")
                continue
            print(f"{name:34s} MUTATION NOT APPLIED ({e})")
            surv.append(name)
            continue
        killed = run_tests()
        print(f"{name:34s} {'killed by ' + ','.join(killed[:3]) if killed else 'SURVIVED'}")
        if not killed:
            surv.append(name)
    importlib.reload(L)
    importlib.reload(P)
    print(f"{len(MUTS) - len(surv)} of {len(MUTS)} mutations killed")
    sys.exit(1 if surv else 0)


if __name__ == "__main__":
    main()
