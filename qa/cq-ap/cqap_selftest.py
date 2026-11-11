"""Synthetic self-test for cqap_analysis (Q-prefix calls only, temp files, no real data; NFR-021). Must pass before the freeze's Part 2 is committed.

It builds a small synthetic session (arm folders, spot file, WSJT-X ALL.TXT, daemon log) with KNOWN numbers of corroborated, uncorroborated, hashed
and non-CQ AP-only extras, runs the SAME analyse() the real run uses, and asserts every count and every verdict branch, plus the match's edge
values (+-50 Hz, +-1800 s, own receiver, other band edge), the exclusion rules, the V-OFF exclusion logic and determinism.
"""
import datetime, json, os, tempfile
import numpy as np
import cqap_analysis as A
import cqapsk_analysis as P

N = 100
T0 = P.epoch("261110_184700")
DIAL = 7074000
CAP0, CAP1 = T0 - 1800, T0 + 15 * (N - 1) + 1800


def stamp(i): return datetime.datetime.fromtimestamp(T0 + 15 * i, datetime.timezone.utc).strftime("%y%m%d_%H%M%S")


def call(k): return f"Q{k % 10}{chr(65 + (k // 10) % 26)}{chr(65 + (k // 260) % 26)}"


def nc_line(s, kind, f, snr, text, ap, path=0, dt="0.10"): return "\t".join([s, str(kind), "0", str(f), dt, str(snr), "0", "0", "20", str(path), text, str(ap)]) + "\n"


def write_arm(d, rows, *, cqap, abandon=(), tb_extra=0.0, shim="20260072", threads=8, ref=False, readback_extra=""):
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/nc.tsv", "w", encoding="utf-8") as f:
        f.writelines(rows if not ref else [r.rsplit("\t", 1)[0] + "\n" for r in rows])      # REF: no apKind column (older build)
    with open(f"{d}/run.csv", "w") as f:
        f.write("run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n,b3_n,tb2_ms,tb3_ms,b4_n,tb4_ms,b5_n,tb5_ms\n")
        for i in range(N): f.write(f"r,FULL,{stamp(i)},{i},DEEP,6000,20,,{500 + i},19,1,0,{2500 + i},-1.0,0,{4500 + i + tb_extra},0,-1.0\n")
    ab = set(abandon)
    with open(f"{d}/coh.csv", "w") as f:
        f.write("stamp,seen,abandoned\n")
        for i in range(N): f.write(f"{stamp(i)},1,{1 if stamp(i) in ab else 0}\n")
    with open(f"{d}/abandon.csv", "w") as f:
        f.write("stamp,ran,abandoned,contained\n")
        for i in range(N): f.write(f"{stamp(i)},1,0,0\n")
    with open(f"{d}/third.csv", "w") as f:
        f.write("stamp,outcome,newDecodes\n")
        for i in range(N): f.write(f"{stamp(i)},ran,0\n")
    with open(f"{d}/late.csv", "w") as f:
        f.write("stamp,outcome,lines\n")
        for i in range(N): f.write(f"{stamp(i)},ran,0\n")
    rb = (f"threadsConfigured={threads} threadsResolved={threads} nhard=24 kMinScorePass2=5 osdCorrThreshold=0.05 shim={shim} osdSignFixRead=1 "
          f"decodingDepth=Deep cohfb=True cohms=True cohaudio=Both ungated=True lateround=True subtractionEnabled=True" + (f" cqap={cqap}" if not ref else "") + readback_extra)
    with open(f"{d}/log.log", "w") as f:
        f.write(f"# readback start {rb}\n")
        for i in range(N): f.write(f"2026-11-10T19:00:00Z [Information] Cycle {stamp(i)[7:9]}:{stamp(i)[9:11]}:{stamp(i)[11:13]}: cq-ap: attempts=1000 decodes=1\n")
        f.write(f"# readback end {rb}\n")
    open(f"{d}/status.txt", "w").write("start\nexit 0\n")


def build(root, *, n_feed=0, n_wsjt=0, n_unc=0, controls=True, ref_diff=False, tb_on=0.0, off_abandon=(), ref_abandon=(), off2_diff=False, n_nonCQ=0, n_hashed=0):
    os.makedirs(root, exist_ok=True)
    base, off, on = [], [], []
    for i in range(N):
        s = stamp(i)
        for j in range(20):
            row = nc_line(s, 1 + (j % 2), 1000 + 10 * j, -10 - j % 5, f"{call(j)} {call(j + 100)} JO22", 0)
            off.append(row); on.append(row)
    spots, wsj, exp = [], collections_counter(), dict(kc=0, kn=0, hashed=0, n1=0)
    k = 5000
    def add_extra(i, kind):
        nonlocal k
        c = call(k); k += 1
        s = stamp(i); f = 2000 + (k % 7) * 40
        on.append(nc_line(s, 4, f, -21, f"CQ {c} JO22", 1))
        t_tx = T0 + 15 * i + 10
        if kind == "feed": spots.append(dict(sc=c, rc=call(k + 1), f=DIAL + f + 20, md="FT8", t_tx=t_tx)); exp["kc"] += 1
        elif kind == "wsjt": wsj[s].append(f"CQ {c} JO22"); exp["kc"] += 1
        else: exp["kn"] += 1
        return c, f, t_tx
    for e in range(n_feed): add_extra(e % N, "feed")
    for e in range(n_wsjt): add_extra((e * 3) % N, "wsjt")
    for e in range(n_unc): add_extra((e * 7) % N, "unc")
    if controls:
        # edge values that MUST corroborate (inside): +50 Hz, +1800 s, -1800 s ; and values that must NOT (outside / own receiver / other sender)
        for dx, dt_, rc, want in ((50, 1800, "Q5REC", True), (-50, -1800, "Q5REC", True), (51, 0, "Q5REC", False), (0, 1801, "Q5REC", False),
                                  (0, -1801, "Q5REC", False), (0, 0, "PD2FZ", False)):
            c, f, t_tx = add_extra(10, "unc"); exp["kn"] -= 1                    # add_extra counted it unc; reclassify below
            spots.append(dict(sc=c, rc=rc, f=DIAL + f + dx, md="FT8", t_tx=t_tx - 10 + dt_))        # t_tx - 10 = the cycle start
            if want: exp["kc"] += 1
            else: exp["kn"] += 1
        # a spot of the right sender on FT4 and one for a different sender must not match
        c, f, t_tx = add_extra(11, "unc"); spots.append(dict(sc=c, rc="Q5REC", f=DIAL + f, md="FT4", t_tx=t_tx))
        c, f, t_tx = add_extra(12, "unc"); spots.append(dict(sc=call(k + 900), rc="Q5REC", f=DIAL + f, md="FT8", t_tx=t_tx))
        # not an extra: an ap=1 row whose text is also in the OFF arm; and a duplicate ap=1 row (one extra per cycle and text)
        on.append(nc_line(stamp(13), 4, 2900, -20, f"{call(0)} {call(100)} JO22", 1))
        dupc = call(k); k += 1
        on.append(nc_line(stamp(14), 4, 2950, -20, f"CQ {dupc} JO22", 1)); on.append(nc_line(stamp(14), 5, 2950, -20, f"CQ {dupc} JO22", 1)); exp["kn"] += 1
    for h in range(n_hashed):
        on.append(nc_line(stamp(20 + h), 4, 3100, -22, f"CQ <{call(k)}> JO22", 1)); k += 1; exp["hashed"] += 1
    for q in range(n_nonCQ):
        c1, c2 = call(k), call(k + 1); k += 2
        on.append(nc_line(stamp(30 + q), 4, 3200, -22, f"{c1} {c2} JO22", 1)); exp["kn"] += 1; exp["n1"] += 1
    # A1.7: an ON-only decode that is NOT AP (gained through the residual) and an OFF-only decode (lost)
    on.append(nc_line(stamp(40), 5, 3300, -23, f"{call(k)} {call(k + 1)} JO22", 0)); k += 2
    lost = nc_line(stamp(41), 2, 3400, -23, f"{call(k)} {call(k + 1)} JO22", 0); k += 2
    off.append(lost)                                                              # in OFF, not in ON
    ref = list(off)
    if ref_diff: ref[0] = ref[0].replace("\t-10\t", "\t-11\t")                    # one outcome field differs in a cycle of the first 50
    off2 = list(off)
    if off2_diff: off2[5] = off2[5].replace("\t-10\t", "\t-12\t")
    cl = f"{root}/cycles.txt"
    open(cl, "w").write("\n".join(stamp(i) + ".wav" for i in range(N)) + "\n")
    write_arm(f"{root}/OFF", off, cqap=False, abandon=off_abandon)
    write_arm(f"{root}/ON", on, cqap=True, tb_extra=tb_on)
    write_arm(f"{root}/OFF2", off2, cqap=False)
    write_arm(f"{root}/REF", ref, cqap=False, shim="20260071", ref=True, abandon=ref_abandon)
    # spot file: a filler stream every 60 s over the capture (no gap > 120 s) plus the extras' spots at their t_tx, plus own-receiver spots
    stream = [(float(t), dict(sc="Q9FIL", rc="Q8RCV", f=DIAL + 500, md="FT8", t_tx=t - 5)) for t in range(CAP0, CAP1 + 1, 60)]
    own = [(float(CAP0 + 100 + 120 * j), dict(sc="Q4MYS", rc="PD2FZ", f=DIAL + 800, md="FT8", t_tx=CAP0 + 95 + 120 * j)) for j in range((CAP1 - CAP0 - 200) // 120)]
    n_own = len(own)
    ext = [(float(sp["t_tx"]) + 20, sp) for sp in spots]
    rows = sorted(stream + own + ext, key=lambda r: r[0])
    with open(f"{root}/spots.jsonl", "w") as f:
        f.write(json.dumps({"_evt": "connect", "utc": "x", "rc": 0}) + "\n")
        for rx, p in rows: f.write(json.dumps({"rx": rx, "t": "x", "p": json.dumps(p)}) + "\n")
    with open(f"{root}/ALL.TXT", "w") as f:
        for s, L in wsj.items():
            for m in L: f.write(f"{s}     7.074 Rx FT8   -21  0.1 2000 {m}\n")
    # daemon log: local = UTC + 1 h (as the live daemon.out); PSK lines every 5 min summing to n_own reported
    with open(f"{root}/daemon.out", "w") as f:
        for i in range(0, N, 10):
            t = T0 + 15 * i; u = datetime.datetime.fromtimestamp(t, datetime.timezone.utc); l = u + datetime.timedelta(hours=1)
            f.write(f"[{l:%H:%M:%S} INF] Cycle {u:%H:%M:%S}: 20 decode(s) found, elapsed=600 ms.\n")
        k_rep, blocks = 0, 10
        for b in range(blocks):
            t = T0 + 15 * b * (N // blocks); u = datetime.datetime.fromtimestamp(t, datetime.timezone.utc); l = u + datetime.timedelta(hours=1)
            m = n_own // blocks + (1 if b < n_own % blocks else 0)
            f.write(f"[{l:%H:%M:%S} INF] PSK Reporter: 100 decodes seen, {m} reported: region=0, ap=5\n")
    exp["n_own"] = n_own
    return exp


def collections_counter():
    import collections
    return collections.defaultdict(list)


def args_for(root, **kw):
    a = dict(arms={k: f"{root}/{k}" for k in ("OFF", "ON", "OFF2", "REF")}, cycle_list=f"{root}/cycles.txt", spots=f"{root}/spots.jsonl",
             wsjtx_all_txt=f"{root}/ALL.TXT", daemon_log=f"{root}/daemon.out", dial_hz=DIAL, cap_start=CAP0, cap_end=CAP1, expect_cycles=N,
             head_on=A.HEAD_ON, head_ref="98332f2a0000", dll_sha_on=A.PIN_ON, dll_sha_ref=A.PIN_REF, status_txt_on="exit 0", status_txt_ref="exit 0")
    a.update(kw)
    return a


def run_case(name, **kw):
    d = tempfile.mkdtemp(prefix="cqap_selftest_")
    bkw = {k: kw.pop(k) for k in list(kw) if k in ("n_feed", "n_wsjt", "n_unc", "controls", "ref_diff", "tb_on", "off_abandon", "ref_abandon", "off2_diff", "n_nonCQ", "n_hashed")}
    exp = build(d, **bkw)
    res = A.analyse(args_for(d, **kw))
    return exp, res


def main():
    # ---- pure functions -------------------------------------------------------------------------------------------------------------
    assert A.norm("  CQ   Q1ABC  JO22 ") == "CQ Q1ABC JO22"
    base = {"V-NAT": True, "V-SET": True, "V-OFF": True, "V-FEED": True, "V-SELF": True, "G-GAIN": True, "NO-GAIN": False, "U-UB": True, "T-TIME": True}
    V = lambda **k: A.verdict({**base, **k})
    assert V() == "SHIP-CANDIDATE"
    for row in ("V-NAT", "V-SET", "V-OFF", "V-FEED"): assert V(**{row: False}) == "VOID", row
    assert V(**{"V-OFF": False, "NO-GAIN": True}) == "VOID"                       # VOID before NO-GAIN
    assert V(**{"NO-GAIN": True, "G-GAIN": False}) == "NO-GAIN" and V(**{"NO-GAIN": True}) == "NO-GAIN"
    assert V(**{"U-UB": False}) == "FP-UNRESOLVED"
    assert V(**{"U-UB": False, "T-TIME": False}) == "FP-UNRESOLVED"               # rule 4 before 5
    assert V(**{"T-TIME": False}) == "BETWEEN" and V(**{"V-SELF": False}) == "BETWEEN" and V(**{"G-GAIN": False}) == "BETWEEN"
    assert V(**{"V-SELF": False, "U-UB": False}) == "FP-UNRESOLVED"
    # the three bars at their boundaries (bar values are the spec's; a "<" or "<=" slip is caught here)
    assert A.u_ub(0.021) and not A.u_ub(0.0210001) and A.u_ub(0.0)
    assert A.no_gain(0.00149999) and not A.no_gain(0.0015) and not A.no_gain(0.01)
    assert A.g_gain(1e-9) and not A.g_gain(0.0) and not A.g_gain(-1.0)
    # V-OFF: abandon exclusion and outcome-key (text is NOT in the key)
    st = [stamp(i) for i in range(N)]
    row = lambda t, snr=-10: dict(kind=1, f=1000, dt="0.10", snr=snr, path="0", text=t, ap=0)
    off = {s: [row("A")] for s in st}; ref = {s: [row("B")] for s in st}            # different TEXT, same outcome fields: equal
    assert A.v_off(st, off, ref, set(), set())["PASS"]
    ref2 = dict(ref); ref2[st[7]] = [row("B", snr=-9)]
    r = A.v_off(st, off, ref2, set(), set()); assert not r["PASS"] and r["differing"] == 1
    r = A.v_off(st, off, ref2, {st[7]}, set()); assert r["PASS"] and r["excluded"] == 1 and r["compared"] == 49
    assert not A.v_off(st, off, ref, set(st[:6]), set())["PASS"]                  # 6 excluded > 5
    assert A.v_off(st, off, ref, set(st[:5]), set(st[3:8]))["excluded"] == 8 and not A.v_off(st, off, ref, set(st[:5]), set(st[3:8]))["PASS"]
    assert A.v_off(st, off, ref, set(st[60:99]), set())["PASS"]                   # abandons after the first 50 do not count
    # V-NAT / V-SET / T-TIME
    assert A.v_nat("7ca00264" + "0" * 32, A.PIN_ON, "exit 0", A.HEAD_ON[:8], A.PIN_ON)["PASS"]
    assert not A.v_nat("7ca00264" + "0" * 32, "0" * 64, "exit 0", A.HEAD_ON[:8], A.PIN_ON)["PASS"]
    assert not A.v_nat("98332f2a", A.PIN_ON, "exit 0", A.HEAD_ON[:8], A.PIN_ON)["PASS"]
    assert not A.v_nat("7ca00264" + "0" * 32, A.PIN_ON, "END dll pin mismatch", A.HEAD_ON[:8], A.PIN_ON)["PASS"]
    ok_line = "kMinScorePass2=5 osdCorrThreshold=0.05 nhard=24 shim=20260072 osdSignFixRead=1 decodingDepth=Deep cohfb=True cohms=True cohaudio=Both ungated=True lateround=True subtractionEnabled=True cqap=True"
    assert A.v_set({"start": ok_line, "end": ok_line}, ["cqap=True"], "20260072")["PASS"]
    assert not A.v_set({"start": ok_line, "end": ok_line.replace("cqap=True", "cqap=False")}, ["cqap=True"], "20260072")["PASS"]
    assert not A.v_set({"start": ok_line}, ["cqap=True"], "20260072")["PASS"]
    t = A.t_time([5000.0] * 10, [3999.0] * 10, set(), set(), 100); assert not t["PASS"] and abs(t["dp95_ms"] - 1001.0) < 1e-6
    assert A.t_time([5000.0] * 10, [4000.0] * 10, set(), set(), 100)["PASS"]       # exactly 1.0 s passes (<=)
    assert A.t_time([4000.0] * 10, [4000.0] * 10, set(range(2)), set(range(1)), 100)["PASS"]      # +1 per 100 passes
    assert not A.t_time([4000.0] * 10, [4000.0] * 10, set(range(3)), set(range(1)), 100)["PASS"]  # +2 per 100 fails
    # bootstrap invariants: constant series have a degenerate interval; same seed, same numbers
    kc = np.ones(10); kn = np.zeros(10); d = np.full(10, 20.0)
    b = A.bootstrap(kc, kn, d); assert b["K_C_per100"] == [100.0, 100.0] and b["K_N_per_cycle"] == [0.0, 0.0] and b["gain_ratio_all"] == [0.05, 0.05]
    kc2 = np.array([0, 1, 0, 2, 0, 0, 1, 0, 0, 3.0]); b1 = A.bootstrap(kc2, kn, d); b2 = A.bootstrap(kc2, kn, d)
    assert b1 == b2 and b1["K_C_per100"][0] <= 100 * kc2.mean() <= b1["K_C_per100"][1]
    # ---- end-to-end ----------------------------------------------------------------------------------------------------------------
    # SHIP: 30 feed-corroborated + 10 WSJT-X-corroborated extras, edge controls, hashed + non-CQ lines
    exp, r = run_case("ship", n_feed=30, n_wsjt=10, n_unc=0, n_hashed=3, n_nonCQ=2)
    c = r["counts"]
    assert c["K_C"] == exp["kc"] and c["K_N"] == exp["kn"], (c, exp)
    assert c["ap_hashed_excluded"] == exp["hashed"] == 3
    assert r["descriptive"]["N1_cq_tagged_not_starting_with_CQ"]["n"] == exp["n1"] == 2
    assert r["descriptive"]["corroboration_share"].get("wsjtx_only", 0) == 10
    assert r["descriptive"]["A17_on_only_ap_none_per100"] == 1.0 and r["descriptive"]["A17_off_only_per100"] == 1.0
    assert r["V-OFF"]["PASS"] and r["V-NAT"]["PASS"] and r["V-SET"]["PASS"] and r["V-FEED"]["PASS"] and r["V-SELF"]["PASS"], {k: r[k] for k in ("V-OFF", "V-NAT", "V-SET", "V-FEED", "V-SELF")}
    assert abs(r["V-SELF"]["ratio"] - (exp["n_own"] + 1) / exp["n_own"]) < 1e-9            # + the one own-rc control spot
    assert r["rows"]["G-GAIN"] and not r["rows"]["NO-GAIN"] and r["rows"]["T-TIME"]
    expect_u = r["CI"]["K_N_per_cycle"][1] <= A.U_BAR
    assert r["rows"]["U-UB"] == expect_u
    assert r["VERDICT"] == ("SHIP-CANDIDATE" if expect_u else "FP-UNRESOLVED"), (r["VERDICT"], r["CI"], r["counts"])
    assert r["OFF_vs_OFF_repeat"]["differing_cycles"] == 0 and r["OFF_vs_OFF_repeat"]["compared"] == N
    # the controls alone (edge match): 2 of the 6 control spots are corroborated, the rest are not
    exp, r = run_case("controls-only", n_feed=0)
    assert r["counts"]["K_C"] == exp["kc"] == 2 and r["counts"]["K_N"] == exp["kn"], (r["counts"], exp)
    # SHIP with zero uncorroborated and a clean U: remove controls and non-CQ
    exp, r = run_case("ship-clean", n_feed=40, controls=False)
    assert r["counts"]["K_N"] == 0 and r["VERDICT"] == "SHIP-CANDIDATE", (r["counts"], r["VERDICT"], r["rows"])
    # NO-GAIN: no AP extras at all
    exp, r = run_case("no-gain", controls=False)
    assert r["counts"]["AP_only_extras"] == 0 and r["rows"]["NO-GAIN"] and not r["rows"]["G-GAIN"] and r["VERDICT"] == "NO-GAIN", r["rows"]
    # A1.1: many uncorroborated extras and NO corroborated one is NOT "no gain" (a lower bound cannot show absence): it reads BETWEEN
    exp, r = run_case("allN", n_unc=30, controls=False)
    assert r["counts"]["K_C"] == 0 and r["counts"]["K_N"] == 30 and not r["rows"]["NO-GAIN"] and r["VERDICT"] == "BETWEEN", (r["rows"], r["VERDICT"])
    # FP-UNRESOLVED: gain but a large uncorroborated count
    exp, r = run_case("fp", n_feed=30, n_unc=40, controls=False)
    assert r["rows"]["G-GAIN"] and not r["rows"]["U-UB"] and r["VERDICT"] == "FP-UNRESOLVED", (r["rows"], r["CI"])
    # BETWEEN: gain and clean U but ON is slower by 1.5 s at p95
    exp, r = run_case("slow", n_feed=40, controls=False, tb_on=1500.0)
    assert not r["rows"]["T-TIME"] and r["VERDICT"] == "BETWEEN", (r["T-TIME"], r["VERDICT"])
    # BETWEEN: V-SELF fails (own spots far below {Reported})
    d = tempfile.mkdtemp(prefix="cqap_selftest_"); build(d, n_feed=40, controls=False)
    with open(f"{d}/daemon.out", "a") as f: f.write("[19:59:00 INF] PSK Reporter: 9999 decodes seen, 9999 reported: region=0\n")
    r = A.analyse(args_for(d)); assert not r["rows"]["V-SELF"] and r["VERDICT"] == "BETWEEN", (r["V-SELF"], r["VERDICT"])
    # VOID: V-OFF fails (REF differs in a cycle of the first 50), and when more than 5 of the 50 are excluded
    exp, r = run_case("void-off", n_feed=40, controls=False, ref_diff=True)
    assert not r["rows"]["V-OFF"] and r["VERDICT"] == "VOID", r["V-OFF"]
    exp, r = run_case("void-excl", n_feed=40, controls=False, off_abandon=[stamp(i) for i in range(6)])
    assert r["V-OFF"]["excluded"] == 6 and not r["rows"]["V-OFF"] and r["VERDICT"] == "VOID"
    exp, r = run_case("excl-ok", n_feed=40, controls=False, off_abandon=[stamp(i) for i in range(5)], ref_diff=False)
    assert r["V-OFF"]["PASS"] and r["V-OFF"]["excluded"] == 5
    # VOID: a wrong DLL, a wrong head
    exp, r = run_case("void-dll", n_feed=40, controls=False, dll_sha_on="0" * 64)
    assert not r["rows"]["V-NAT"] and r["VERDICT"] == "VOID"
    exp, r = run_case("void-head", n_feed=40, controls=False, head_on="98332f2a" + "0" * 32)
    assert not r["rows"]["V-NAT"] and r["VERDICT"] == "VOID"
    # VOID: a feed gap inside the capture (drop the filler spots of ten minutes)
    d = tempfile.mkdtemp(prefix="cqap_selftest_"); build(d, n_feed=40, controls=False)
    kept = []
    for line in open(f"{d}/spots.jsonl"):
        rr = json.loads(line)
        if "p" in rr and CAP0 + 3000 <= rr["rx"] <= CAP0 + 3600: continue           # every row in ten minutes, any sender
        kept.append(line)
    open(f"{d}/spots.jsonl", "w").writelines(kept)
    r = A.analyse(args_for(d)); assert r["V-FEED"]["gaps_over_120s"] >= 1 and not r["rows"]["V-FEED"] and r["VERDICT"] == "VOID"
    # OFF-vs-OFF repeat line reports a difference when the repeat differs
    exp, r = run_case("repeat", n_feed=40, controls=False, off2_diff=True)
    assert r["OFF_vs_OFF_repeat"]["differing_cycles"] == 1
    # determinism: identical inputs, identical JSON
    d = tempfile.mkdtemp(prefix="cqap_selftest_"); build(d, n_feed=30, n_unc=5)
    j1 = json.dumps(A.analyse(args_for(d)), sort_keys=True, default=float); j2 = json.dumps(A.analyse(args_for(d)), sort_keys=True, default=float)
    assert j1 == j2
    # no callsign-like text and no message text leaves the analysis (results are aggregates)
    for tok in ("CQ ", "Q1A", "JO22", "PD2FZ"):
        assert tok not in j1, tok
    print("cqap selftest: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
