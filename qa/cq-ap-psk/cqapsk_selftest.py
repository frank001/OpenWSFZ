"""Synthetic checks for cqapsk_analysis (Q-prefix calls only, temp files, no real data). Run before the freeze."""
import json, os, tempfile, textwrap
import numpy as np
import cqapsk_analysis as A
import c28_ghosts as G

T0 = A.epoch("261110_120000")


def ts(c):
    import datetime
    return datetime.datetime.fromtimestamp(c, datetime.timezone.utc).strftime("%y%m%d_%H%M%S")


def line(c, snr, off, msg): return f"{ts(c)}     14.074 Rx FT8 {snr:5d}  0.1 {off:4d} {msg}\n"


def main():
    # --- Wilson known values (n=10,k=5: [0.2366, 0.7634]; k=0,n=100 upper 0.0370)
    lo, hi = A.wilson(5, 10); assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3, (lo, hi)
    assert abs(A.wilson(0, 100)[1] - 0.0370) < 1e-3
    # --- sender parsing
    assert A.cq_sender("CQ Q1ABC FN42") == ("Q1ABC", "ok")
    assert A.cq_sender("CQ DX Q1ABC FN42") == ("Q1ABC", "ok")
    assert A.cq_sender("CQ 123 Q1ABC") == ("Q1ABC", "ok")
    assert A.cq_sender("CQ <...> FN42")[0] is None and A.cq_sender("Q1ABC Q2XYZ -10")[1] == "not-cq"
    # --- bins
    assert [A.bin_of(x) for x in (-5, -10, -11, -15, -16, -18, -19, -24)] == ["ge-10", "ge-10", "-11..-15", "-11..-15", "-16..-18", "-16..-18", "le-19", "le-19"]
    # --- P_R rule: Q1AAA decoded in 3 cycles within 600 s and 10 Hz -> all three are members; Q2BBB twice -> none; Q3CCC 3x but 11 Hz away -> none
    d = tempfile.mkdtemp()
    all_txt = os.path.join(d, "ALL.TXT")
    L = []
    for k in range(3): L.append(line(T0 + 15 * k, -20, 1500 + k, "CQ Q1AAA FN42"))
    for k in range(2): L.append(line(T0 + 15 * k, -20, 1700, "CQ Q2BBB FN42"))
    for k, o in enumerate((1000, 1011, 1022)): L.append(line(T0 + 15 * k, -20, o, "CQ Q3CCC FN42"))
    L.append(line(T0 + 15, -12, 900, "Q9ZZZ Q8YYY -10"))                  # not a CQ: ignored
    L.append(line(T0 + 15, -12, 901, "CQ <...> FN42"))                    # hashed: counted, excluded
    open(all_txt, "w").writelines(L)
    dec, cnt = A.read_decodes(all_txt, T0, T0 + 3600)
    assert cnt["cq_hashed"] == 1 and len(dec) == 8, (cnt, len(dec))
    pr = A.build_pr(dec)
    assert sorted({x["s"] for x in pr}) == ["Q1AAA"] and len(pr) == 3, [(x["s"], x["off"]) for x in pr]
    # --- spot matching edges
    idx = {"Q1AAA": sorted([(T0 + 1800, A.absf(pr[0]) + 50), (T0 + 5000, A.absf(pr[0]))])}
    c = pr[0]
    assert A.corroborated(idx, "Q1AAA", c["c"], A.absf(c))                  # +1800 s and +50 Hz are inside (<=)
    idx2 = {"Q1AAA": [(c["c"] + 1801, A.absf(c))]}; assert not A.corroborated(idx2, "Q1AAA", c["c"], A.absf(c))
    idx3 = {"Q1AAA": [(c["c"], A.absf(c) + 51)]}; assert not A.corroborated(idx3, "Q1AAA", c["c"], A.absf(c))
    assert not A.corroborated(idx, "Q9NONE", c["c"], A.absf(c))
    # --- spot file: t_tx preferred, t fallback counted, own rc excluded from matching but counted for V-SELF, non-FT8 skipped, gap detected
    sp = os.path.join(d, "spots.jsonl")
    rows = []
    def spot(rx, **p): rows.append(json.dumps({"rx": rx, "t": "x", "p": json.dumps(p)}))
    spot(100.0, sc="Q1AAA", rc="Q7RRR", f=14075500, md="FT8", t=T0 + 40, t_tx=T0 + 30, b="20m")
    spot(101.0, sc="Q1AAA", rc="PD2FZ", f=14075500, md="FT8", t_tx=T0 + 30)         # own rc: not a match
    spot(102.0, sc="Q1AAA", rc="Q7RRR", f=14075500, md="FT4", t_tx=T0 + 30)         # not FT8
    spot(103.0, sc="Q1AAA", rc="Q7RRR", f=14075600, md="FT8", t=T0 + 30)            # no t_tx -> fallback counted
    spot(300.0, sc="Q1AAA", rc="Q7RRR", f=14075500, md="FT8", t_tx=T0 + 30)         # 197 s gap from 103 -> flagged
    open(sp, "w").write("\n".join(rows) + "\n")
    index, feed = A.read_spots(sp, {"Q1AAA"}, 0, 0)
    assert feed["rows"] == 5 and feed["own"] == 1 and feed["no_t_tx"] == 1 and feed["not_ft8"] == 1 and len(feed["gaps"]) == 1, feed
    assert len(index["Q1AAA"]) == 3, index
    # --- ghosts: constants, unpack round trip is proven in c28_ghosts; here the draw is reproducible and acceptance bookkeeping holds
    stub = os.path.join(d, "gate_stub.py")
    open(stub, "w").write("import sys\nfor l in sys.stdin:\n    print('0' if l.strip().endswith('0') else '1')\n")
    donors = [dict(c=T0, s="Q1AAA", snr=-20, off=1500, dial=14.074, grid="FN42"), dict(c=T0 + 15, s="Q1AAA", snr=-20, off=1500, dial=14.074, grid=None)]
    g1, st1 = A.make_ghosts(np.random.Generator(np.random.PCG64(A.SEED)), donors, ["python", "-I", stub])
    g2, st2 = A.make_ghosts(np.random.Generator(np.random.PCG64(A.SEED)), donors, ["python", "-I", stub])
    assert g1 == g2 and len(g1) == A.N_GHOSTS and st1 == st2 and st1["candidates"] == A.CAND_BLOCK
    assert all(" " not in c and c == c.strip() and c for c, _ in g1)
    # --- verdict logic, exclusive and ordered (labels: P_R when V-REF fails)
    base = dict(**{"V-REF": False, "N-INSUFF": False, "C_weak_lo": 0.5, "C_weak_hi": 0.7, "ghost_point": 0.0, "G-COVER": True, "G-SLOPE": True, "G-GHOST": True, "V-SELF": True})
    assert A.verdict(base) == "USABLE (P_R)"
    assert A.verdict({**base, "V-REF": True}) == "USABLE"
    assert A.verdict({**base, "N-INSUFF": True, "C_weak_hi": 0.1}) == "INSUFFICIENT (P_R)"       # INSUFFICIENT precedes NOT-USABLE
    assert A.verdict({**base, "C_weak_hi": 0.39}) == "NOT-USABLE (P_R)"
    assert A.verdict({**base, "ghost_point": 0.06}) == "NOT-USABLE (P_R)"
    assert A.verdict({**base, "V-SELF": False}) == "BETWEEN (P_R)"
    assert A.verdict({**base, "G-SLOPE": False}) == "BETWEEN (P_R)"
    # --- summarise on a toy set: three P_R members, spots only for Q1AAA, window/gap logic
    selfsum = dict(ratio=1.0)
    pr_pre = pr
    res = A.summarise(pr_pre, [(g1[0][0], 0)], [(pr[0]["s"], pr[1]["c"], A.absf(pr[1]))], 0, index, feed, st1, cnt, pr, 0, 0, [], selfsum)
    assert res["P_R_in_window"] == 3 and res["P_R_by_bin"]["le-19"]["n"] == 3 and res["P_R_by_bin"]["le-19"]["k"] == 3
    assert res["rows"]["N-INSUFF"] is True and res["rows"]["VERDICT"].startswith("INSUFFICIENT")
    res2 = A.summarise(pr_pre, [], [], 0, index, feed, st1, cnt, pr, 0, 0, [(T0 - 5, T0 + 20)], selfsum)    # a gap covering two of the three cycles
    assert res2["P_R_in_window"] == 1, res2["P_R_in_window"]
    print("SELFTEST OK")


if __name__ == "__main__":
    main()
