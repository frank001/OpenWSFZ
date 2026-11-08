#!/usr/bin/env python3
"""#262 review: random differential cases for the product encoder, expected bytes from QA's independent builder (build_t1_fixture.py).
Q-prefix calls only. Usage: python diff_cases.py <out.json> [n] [seed]"""
import json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_t1_fixture as B

def qcall(r, n):
    return "Q" + "".join(r.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n - 1))

def grid(r):
    return r.choice("ABCDEFGHIJKLMNOPQR") + r.choice("ABCDEFGHIJKLMNOPQR") + str(r.randint(0, 9)) + str(r.randint(0, 9))

def main():
    out, n, seed = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 300, int(sys.argv[3]) if len(sys.argv) > 3 else 20261025
    r = random.Random(seed)
    cases = []
    for i in range(n):
        rc = qcall(r, r.randint(3, 13))
        sw = r.choice(["OpenWSFZ 0.64", "X" * 254, "OpenWSFZ éü∆ test", "S" * r.randint(1, 60)])
        ant = r.choice(["", "", "Q1 dipole", "Äntenne ∆ " + "a" * r.randint(0, 50), "A" * r.choice([1, 2, 3, 4, 5, 253, 254])])
        recv = dict(callsign=rc, locator=grid(r), software=sw, antenna=ant)
        spots = []
        for _ in range(r.choice([0, 1, 1, 2, 3, 5, 12, 40])):
            has = r.random() < 0.5
            spots.append(dict(callsign=qcall(r, r.randint(3, 13)) + (r.choice(["", "", "/P", "/QRP"])), locator=grid(r) if has else None,
                              freq=r.randint(0, 2**32 - 1) if r.random() < .2 else r.randint(1_800_000, 54_000_000), snr=r.randint(-200, 200),
                              flow=r.randint(1_700_000_000, 1_900_000_000)))
        for s in spots:
            if len(s["callsign"]) > 254: s["callsign"] = s["callsign"][:254]
        templates = r.random() < .5
        t, seq, sid = r.randint(1_700_000_000, 1_900_000_000), r.randint(0, 2**32 - 1), r.randint(0, 2**32 - 1)
        withg = [B.rec(s["callsign"], s["freq"], "FT8", s["flow"], loc=s["locator"], snr=s["snr"], imd=0) for s in spots if s["locator"]]
        nog = [B.rec(s["callsign"], s["freq"], "FT8", s["flow"], loc=None, snr=s["snr"], imd=0) for s in spots if not s["locator"]]
        parts = []
        if templates: parts += [B.recv_descriptor(bool(ant)), B.send_descriptor(8), B.send_descriptor(7)]
        parts.append(B.recv_record(recv["callsign"], recv["locator"], recv["software"], ant if ant else None))
        if withg: parts.append(B.send_block(8, withg))
        if nog: parts.append(B.send_block(7, nog))
        blob = B.datagram(t, seq, sid, parts)
        cases.append(dict(receiver=recv, spots=spots, templates=templates, export=t, seq=seq, session=sid, expected=blob.hex().upper()))
    json.dump(cases, open(out, "w"), indent=0)
    print(len(cases), "cases; sizes", min(len(c["expected"]) // 2 for c in cases), "to", max(len(c["expected"]) // 2 for c in cases), "bytes; with antenna", sum(1 for c in cases if c["receiver"]["antenna"]),
          "; with both blocks", sum(1 for c in cases if any(s["locator"] for s in c["spots"]) and any(not s["locator"] for s in c["spots"])))

main()
