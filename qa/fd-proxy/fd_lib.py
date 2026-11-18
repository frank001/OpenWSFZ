#!/usr/bin/env python3
"""FD-PROXY (angle H, Stage 1) core: the judgeable function, the evidence set E, the four components C / R / F / S, the strata.

Spec: arch/false-decode-instrument f01d6acd + Amendment 1 (3a389fff, section 11). Every constant below carries its source.
HK-037: message text exists only in this process's memory and inside these functions; nothing here prints or writes text. Selftest uses constructed Q-prefix calls only.

  python -I fd_lib.py selftest
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import re
import sys

# --- constants (source in the comment) ---------------------------------------------------------------------------------------
CYCLE_S = 15                 # FT8 slot length
GATE_HZ = 10.0               # spec s3: the Test B corroboration gate (replay81 CorroborationDeltaHz = 10)
R_WINDOW_CYC = 240           # spec s3: +-60 min (design value; the pilot may amend from controls only)
F_WINDOW_CYC = 4             # spec s3: +-1 min
S_WINDOW_CYC = 8             # spec s3: 8 cycles, past only
BURIAL_HZ = 50.0             # TA-CHECK tc_lib.OVERLAP_HZ (commit 980ce3a7), asserted below in the selftest against the file
STEP_RANK = {"grid": 1, "report": 2, "rreport": 3, "RRR": 4, "RR73": 4, "73": 5}   # xc_next_tx.TABLES["T-G"] (frozen 09fdeaa3)
assert (CYCLE_S, GATE_HZ, R_WINDOW_CYC, F_WINDOW_CYC, S_WINDOW_CYC, BURIAL_HZ) == (15, 10.0, 240, 4, 8, 50.0)

# --- the judgeable function (spec s2 + Amendment 1 C3): ONE definition -------------------------------------------------------
_CALL = re.compile(r"^(?:[A-Z0-9]{1,3}/)?[A-Z0-9]{1,3}[0-9][A-Z]{1,4}(?:/[A-Z0-9]{1,4})?$")
_GRID = re.compile(r"^[A-R]{2}[0-9]{2}(?:[A-X]{2})?$")
_REP = re.compile(r"^[+-][0-9]{2}$")
_RREP = re.compile(r"^R[+-][0-9]{2}$")
_CQMOD = re.compile(r"^(?:[A-Z]{1,4}|[0-9]{3})$")


def is_call(tok: str) -> bool:
    return bool(_CALL.match(tok)) and tok != "CQ"


def parse(text: str):
    """-> None if UNJUDGEABLE, else dict(kind 'CQ'|'STD', B sender, A addressee or None, X payload type or None, calls tuple).
    CQ  = CQ [modifier] B [grid];  STD = A B X with X in grid | report | R+report | RRR | RR73 | 73 | (empty).
    Unjudgeable: any '<' (hashed), any ';' (DXpedition), a call field that is not call-shaped, free text, telemetry, anything else."""
    if "<" in text or ";" in text:
        return None
    t = text.split()
    if len(t) < 2:
        return None
    if t[0] == "CQ":
        rest = t[1:]
        grid = None
        if len(rest) >= 2 and _GRID.match(rest[-1]) and not is_call(rest[-1]):
            grid = rest[-1]
            rest = rest[:-1]
        if len(rest) == 2 and _CQMOD.match(rest[0]) and not is_call(rest[0]):
            rest = rest[1:]
        if len(rest) != 1 or not is_call(rest[0]):
            return None
        return dict(kind="CQ", B=rest[0], A=None, X="grid" if grid else None, calls=(rest[0],))
    if len(t) not in (2, 3) or not (is_call(t[0]) and is_call(t[1])):
        return None
    a, b = t[0], t[1]
    if len(t) == 2:
        return dict(kind="STD", B=b, A=a, X=None, calls=(a, b))
    p = t[2]
    if p in ("RRR", "RR73", "73"):
        x = p
    elif _RREP.match(p):
        x = "rreport"
    elif _REP.match(p):
        x = "report"
    elif _GRID.match(p):
        x = "grid"
    else:
        return None
    return dict(kind="STD", B=b, A=a, X=x, calls=(a, b))


def cycle_of(stamp: str) -> int:
    """YYMMDD_HHMMSS -> cycle index (15 s slots)."""
    return int(dt.datetime.strptime(stamp, "%y%m%d_%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()) // CYCLE_S


# --- the evidence set E: WSJT-X ALL.TXT rows only, never our rows -------------------------------------------------------------
class Evidence:
    """E rows: (cycle, snr, freq, text). Indexes built once; text stays inside this object."""

    def __init__(self, rows):
        self.by_cycle = collections.defaultdict(list)       # cycle -> [(snr, freq, text, parsed)]
        self.call_cycles = collections.defaultdict(list)    # call -> sorted cycles (any field of any parsed row)
        self.sender = collections.defaultdict(list)         # B -> sorted [(cycle, freq, text)]
        self.pair = collections.defaultdict(list)           # (B, A) -> sorted [(cycle, rank)]
        self.n = 0
        for (c, snr, f, text) in rows:
            pr = parse(text)
            self.by_cycle[c].append((snr, f, text, pr))
            self.n += 1
            if pr is None:
                # an unparsed E row still vouches for call-shaped tokens it carries (a hashed message names its other call)
                for tok in text.split():
                    if "<" not in tok and is_call(tok):
                        self.call_cycles[tok].append(c)
                continue
            for call in pr["calls"]:
                self.call_cycles[call].append(c)
            self.sender[pr["B"]].append((c, f, text))
            if pr["kind"] == "STD" and pr["X"] in STEP_RANK:
                self.pair[(pr["B"], pr["A"])].append((c, STEP_RANK[pr["X"]]))
        for v in self.call_cycles.values():
            v.sort()
        for v in self.sender.values():
            v.sort()
        for v in self.pair.values():
            v.sort()

    # C: same cycle, sender B within 10 Hz, different text. `own_text` rows are excluded only by being the same text (a P row's own match cannot conflict).
    # `hide` = (text, freq): ONE E row (that text, within 10 Hz of that freq) is left out, for the N-FIELD-MISS control (a ghost of a signal WSJT-X did NOT decode).
    def C(self, cyc, freq, text, pr, hide=None):
        skipped = False
        for (_, f, t, p2) in self.by_cycle.get(cyc, ()):
            if hide is not None and not skipped and t == hide[0] and abs(f - hide[1]) <= GATE_HZ:
                skipped = True
                continue
            if p2 is not None and p2["B"] == pr["B"] and abs(f - freq) <= GATE_HZ and t != text:
                return True
        return False

    # R: every call field appears in some E row OUTSIDE the own cycle, within +-240 cycles (either field).
    def R(self, cyc, pr, window=R_WINDOW_CYC):
        for call in pr["calls"]:
            cs = self.call_cycles.get(call, ())
            lo = bisect.bisect_left(cs, cyc - window)
            ok = False
            for i in range(lo, len(cs)):
                if cs[i] > cyc + window:
                    break
                if cs[i] != cyc:
                    ok = True
                    break
            if not ok:
                return False
        return True

    # F: nearest-in-time E row with sender B outside the own cycle within +-4 cycles (ties: nearest in frequency); FAIL iff it lies > 10 Hz away.
    # returns "FAIL" | "OK" | "UNSEEN"
    def F(self, cyc, freq, pr):
        best = None
        for (c, f, _t) in self.sender.get(pr["B"], ()):
            d = abs(c - cyc)
            if c == cyc or d > F_WINDOW_CYC:
                continue
            key = (d, abs(f - freq))
            if best is None or key < best[0]:
                best = (key, f)
        if best is None:
            return "UNSEEN"
        return "FAIL" if abs(best[1] - freq) > GATE_HZ else "OK"

    # S: STD only; an E row B->A within the 8 cycles BEFORE the row with a strictly higher T-G rank => BEHIND.
    def S(self, cyc, pr):
        if pr["kind"] != "STD" or pr["X"] not in STEP_RANK:
            return False
        mine = STEP_RANK[pr["X"]]
        for (c, rk) in self.pair.get((pr["B"], pr["A"]), ()):
            if cyc - S_WINDOW_CYC <= c <= cyc - 1 and rk > mine:
                return True
        return False

    def judge(self, cyc, freq, text, hide=None):
        """-> None (UNJUDGEABLE) or dict(C, R, F, S, plausible)."""
        pr = parse(text)
        if pr is None:
            return None
        c, r, f, s = self.C(cyc, freq, text, pr, hide), self.R(cyc, pr), self.F(cyc, freq, pr), self.S(cyc, pr)
        return dict(C=c, R=r, F=f, S=s, plausible=(not c) and r and f != "FAIL" and not s)

    # burial (TA-CHECK is_buried, 980ce3a7): another WSJT-X row in the cycle at |df| < 50 Hz with SNR >= the row's own.
    # Amendment 1 C4: a confirmed row's OWN match (equal text, within 10 Hz; the nearest if several) is excluded first.
    def buried(self, cyc, freq, snr, text=None, confirmed=False, snr_shift=0.0):
        own = None
        rows = self.by_cycle.get(cyc, ())
        if confirmed:
            cand = [(abs(f - freq), i) for i, (_s, f, t, _p) in enumerate(rows) if t == text and abs(f - freq) <= GATE_HZ]
            own = min(cand)[1] if cand else None
        for i, (s, f, _t, _p) in enumerate(rows):
            if i == own:
                continue
            if abs(f - freq) < BURIAL_HZ and s >= snr + snr_shift:
                return True
        return False


def band(snr: int) -> str:
    return "<=-18" if snr <= -18 else "-17..-10" if snr <= -10 else ">=-9"


def load_E(alltxt):
    """ALL.TXT -> rows [(cycle, snr, freq, text)]; Rx FT8 lines only (the same filter as xc_next_tx.load_all)."""
    out = []
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            f = ln.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                out.append((cycle_of(f[0]), int(f[4]), int(f[6]), " ".join(f[7:]).strip()))
            except ValueError:
                continue
    return out


# --- selftest: constructed Q-prefix cases only (NFR-021), must-fail cases included ---------------------------------------------
def selftest():
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(("PASS " if good else "FAIL ") + name + ("" if good else f"  got {got!r} want {want!r}"))

    J = lambda s: (parse(s) is not None)
    # judgeable: shapes
    chk("STD grid", J("QA1AAA QB2BBB JO22"), True)
    chk("STD report", J("QA1AAA QB2BBB -12"), True)
    chk("STD R+report", J("QA1AAA QB2BBB R+05"), True)
    chk("STD RRR / RR73 / 73", (J("QA1AAA QB2BBB RRR"), J("QA1AAA QB2BBB RR73"), J("QA1AAA QB2BBB 73")), (True, True, True))
    chk("STD empty payload", J("QA1AAA QB2BBB"), True)
    chk("CQ", J("CQ QB2BBB JO22"), True)
    chk("CQ no grid", J("CQ QB2BBB"), True)
    chk("CQ modifier DX", J("CQ DX QB2BBB JO22"), True)
    chk("CQ modifier 3 digits", J("CQ 123 QB2BBB JO22"), True)
    chk("slash call", J("QA1AAA/P QB2BBB -03"), True)
    chk("prefix/call form", J("QA1AAA QB2/QC3CCC -03"), True)
    # must NOT be judgeable
    chk("hashed A", J("<...> QB2BBB -12"), False)
    chk("hashed B", J("QA1AAA <QB2BBB> -12"), False)
    chk("CQ with hashed call", J("CQ <QB2BBB> JO22"), False)
    chk("free text", J("TNX FER QSO 73"), False)
    chk("telemetry hex", J("0123456789ABCDEF01"), False)
    chk("DXpedition ;", J("QA1AAA RR73; QB2BBB <QC3CCC> -12"), False)
    chk("report out of shape", J("QA1AAA QB2BBB -123"), False)
    chk("non-call field", J("QA1AAA HELLO -12"), False)
    chk("CQ alone", J("CQ"), False)
    chk("CQ with two calls", J("CQ QB2BBB QC3CCC"), False)
    chk("sender and addressee", (parse("QA1AAA QB2BBB -12")["B"], parse("QA1AAA QB2BBB -12")["A"]), ("QB2BBB", "QA1AAA"))
    chk("CQ sender", (parse("CQ DX QB2BBB JO22")["B"], parse("CQ DX QB2BBB JO22")["A"]), ("QB2BBB", None))

    # components on a constructed E (cycles are integers here; cycle_of is checked separately)
    c0 = 1000
    E = Evidence([
        (c0, -10, 1500, "QA1AAA QB2BBB -12"),            # own-cycle row: must never vouch for R
        (c0 - 3, -10, 1503, "QC3CCC QB2BBB JO22"),       # QB2BBB SENDS 3 cycles earlier at 1503 Hz
        (c0 + 100, -10, 1500, "CQ QA1AAA JO22"),         # A seen later
        (c0 - 5, -8, 900, "QA1AAA QB2BBB R-05"),         # B->A, rank 3, 5 cycles before
        (c0 - 2, -9, 1800, "QD4DDD QE5EEE 73"),
    ])
    chk("cycle_of 15 s grid", cycle_of("261114_231215") - cycle_of("261114_231200"), 1)
    r = E.judge(c0, 1500, "QA1AAA QB2BBB -12")
    chk("S-BEHIND (rank 3 earlier, mine 2)", (r["S"], r["plausible"]), (True, False))
    r = E.judge(c0, 1500, "QA1AAA QB2BBB R-12")
    chk("S equal rank is not BEHIND", r["S"], False)
    r = E.judge(c0, 1500, "QA1AAA QB2BBB RR73")
    chk("S higher mine is not BEHIND", r["S"], False)
    chk("R: own-cycle row alone does not vouch", E.R(c0, parse("QD4DDD QF6FFF -01")), False)
    chk("R: both calls recur outside own cycle", E.R(c0, parse("QA1AAA QB2BBB -12")), True)
    chk("R: window edge +240 inclusive", Evidence([(c0 + 240, 0, 1000, "CQ QA1AAA JO22")]).R(c0, parse("CQ QA1AAA JO22")), True)
    chk("R: window edge +241 excluded", Evidence([(c0 + 241, 0, 1000, "CQ QA1AAA JO22")]).R(c0, parse("CQ QA1AAA JO22")), False)
    chk("R: window edge -240 inclusive", Evidence([(c0 - 240, 0, 1000, "CQ QA1AAA JO22")]).R(c0, parse("CQ QA1AAA JO22")), True)
    chk("R: one unseen call fails", E.R(c0, parse("QA1AAA QG7GGG -01")), False)
    chk("R: a hashed E row still vouches for its plain call", Evidence([(c0 - 1, 0, 1000, "<...> QA1AAA -03")]).R(c0, parse("CQ QA1AAA JO22")), True)
    chk("F: sender 3 Hz away (OK)", E.F(c0, 1500, parse("QA1AAA QB2BBB -12")), "OK")
    chk("F: sender 30 Hz away (FAIL)", E.F(c0, 1533, parse("QA1AAA QB2BBB -12")), "FAIL")
    chk("F: nothing within 4 cycles (UNSEEN)", E.F(c0 + 50, 1500, parse("QA1AAA QB2BBB -12")), "UNSEEN")
    chk("F: own-cycle row is ignored", Evidence([(c0, 0, 1500, "QA1AAA QB2BBB -12")]).F(c0, 1900, parse("QA1AAA QB2BBB -12")), "UNSEEN")
    chk("F: window edge 4 in, 5 out", (Evidence([(c0 - 4, 0, 1900, "QA1AAA QB2BBB -12")]).F(c0, 1500, parse("QA1AAA QB2BBB -12")),
                                       Evidence([(c0 - 5, 0, 1900, "QA1AAA QB2BBB -12")]).F(c0, 1500, parse("QA1AAA QB2BBB -12"))), ("FAIL", "UNSEEN"))
    chk("F: nearest in time wins over a closer-in-frequency older row", Evidence([(c0 - 1, 0, 1900, "QA1AAA QB2BBB -12"), (c0 - 3, 0, 1500, "QA1AAA QB2BBB -12")]).F(c0, 1500, parse("QA1AAA QB2BBB -12")), "FAIL")
    Ec = Evidence([(c0, 0, 1505, "QA1AAA QB2BBB -03")])
    chk("C: same sender within 10 Hz, different text", Ec.C(c0, 1500, "QA1AAA QB2BBB -12", parse("QA1AAA QB2BBB -12")), True)
    chk("C: same text cannot conflict", Ec.C(c0, 1500, "QA1AAA QB2BBB -03", parse("QA1AAA QB2BBB -03")), False)
    chk("C: 11 Hz away does not conflict", Ec.C(c0, 1516, "QA1AAA QB2BBB -12", parse("QA1AAA QB2BBB -12")), False)
    chk("C: other sender does not conflict", Ec.C(c0, 1500, "QA1AAA QC3CCC -12", parse("QA1AAA QC3CCC -12")), False)
    chk("C: other cycle does not conflict", Ec.C(c0 + 1, 1500, "QA1AAA QB2BBB -12", parse("QA1AAA QB2BBB -12")), False)
    Eh = Evidence([(c0, 0, 1505, "QA1AAA QB2BBB -03"), (c0 - 1, 0, 1505, "QA1AAA QB2BBB -03"), (c0 + 1, 0, 1505, "QA1AAA QB2BBB -03")])
    chk("hide: C fires with the real row in E, not with it hidden", (Eh.C(c0, 1500, "QA1AAA QB2BBB -12", parse("QA1AAA QB2BBB -12")),
        Eh.C(c0, 1500, "QA1AAA QB2BBB -12", parse("QA1AAA QB2BBB -12"), hide=("QA1AAA QB2BBB -03", 1505))), (True, False))
    chk("unjudgeable returns None", E.judge(c0, 1500, "<...> QB2BBB -12"), None)
    # burial
    Eb = Evidence([(c0, -5, 1520, "QA1AAA QB2BBB -03"), (c0, -20, 1500, "QC3CCC QD4DDD -03")])
    chk("buried: stronger neighbour at 20 Hz", Eb.buried(c0, 1500, -20 + 5), True)       # own snr -15; neighbours: -5 at 20 Hz
    chk("not buried: neighbour 60 Hz away", Eb.buried(c0, 1580, -15), False)
    chk("not buried: neighbour weaker", Eb.buried(c0, 1500, -2), False)
    Ex = Evidence([(c0, -5, 1520, "QA1AAA QB2BBB -03"), (c0, -3, 1540, "QC3CCC QD4DDD -03")])
    chk("confirmed row: own match excluded, a real stronger neighbour still buries", Ex.buried(c0, 1520, -10, text="QA1AAA QB2BBB -03", confirmed=True), True)
    chk("confirmed row: weaker neighbour only, own excluded -> isolated", Eb.buried(c0, 1520, -10, text="QA1AAA QB2BBB -03", confirmed=True), False)
    Eo = Evidence([(c0, -5, 1520, "QA1AAA QB2BBB -03")])
    chk("own match alone does not bury a confirmed row", Eo.buried(c0, 1520, -10, text="QA1AAA QB2BBB -03", confirmed=True), False)
    chk("same E row buries an unconfirmed row at that spot", Eo.buried(c0, 1520, -10), True)
    chk("snr_shift: literal rule buries, +4 dB scale shift does not", (Eo.buried(c0, 1525, -8), Eo.buried(c0, 1525, -8, snr_shift=4.0)), (True, False))
    chk("band edges", (band(-18), band(-17), band(-10), band(-9)), ("<=-18", "-17..-10", "-17..-10", ">=-9"))
    # the TA-CHECK constants are the ones used here (read from the frozen file, not retyped)
    import os
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ta-check", "tc_lib.py"), encoding="utf-8").read()
    chk("BURIAL_HZ equals tc_lib.OVERLAP_HZ", bool(re.search(r"OVERLAP_HZ\s*=\s*50\.0|OVERLAP_HZ\s*=\s*50\b", src)), True)
    print("SELFTEST " + ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if len(sys.argv) > 1 and sys.argv[1] == "selftest" else 2)
