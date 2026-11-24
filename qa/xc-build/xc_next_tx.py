#!/usr/bin/env python3
"""XC-LIVE-FREE step 2 (spec arch/cross-cycle-prior 50d2ae3c, 2026-11-16-1302, section 3): the next-transmission check.
For each batch-6 (XC) publish M from sender S to partner P at slot t: look up S's next transmission TO P in slot t+30 s and classify it against M.
COUNTS ONLY (HK-037, NFR-021): message text is read INSIDE the functions below and never leaves them; the JSON holds counts and shares.

Usage:  python -I xc_next_tx.py run <ON arm dir> <WSJT-X ALL.TXT of that night> <out json> [<control arm dir> <control ALL.TXT>]
        python -I xc_next_tx.py selftest

PREDICATES, FROZEN HERE BEFORE ANY DATA WAS READ (committed before the first run):
  Message types (payload = 3rd token of a 3-token `TO FROM PAYLOAD` message; checked in this order, RR73 BEFORE grid because RR73 looks like a locator):
     RR73, RRR, 73, R-report (R+nn / R-nn), report (+nn / -nn), grid (4 or 6 character locator); anything else = UNSTEPPABLE.
  Two step tables (the spec says the order is defined in ONE table; its own example reads "M is a report, next is RR73 or 73" as AHEAD, which only a GLOBAL
  ranking gives, while a caller's own next message after a report IS RR73; so both are computed and both are reported, none is chosen after the data):
     T-G (the spec's example, literal, one conversation lane):   grid 1, report 2, R-report 3, RRR 4, RR73 4, 73 5
     T-C (the sender's OWN chain, the two roles on a common scale): grid 1, report 1, R-report 2, RRR 2, RR73 2, 73 3
  Classes (exclusive; d = rank(next) - rank(M)):  NEXT-OK d in {0, 1} | AHEAD d >= 2 | BEHIND d < 0 | NONE no decode from S to P in slot t+30 | UNSTEPPABLE M or next not in the table.
  Units: XC publishes of the classes COR, SUP-W, FREE (xc_sup's own predicates, imported unchanged); not CQ; not hashed (<...>); exactly 3 tokens.
  Look-up: the first row of slot t+30 in WSJT-X's ALL.TXT whose 2nd token is S and 1st token is P; if none, the first OWS Test-B-matched batch 1-5 row of that slot (nc.tsv); the source is counted.
  Slots t+30 outside the night's ALL.TXT stamp range are excluded and counted (no look-up possible), never NONE.
  stepped = NEXT-OK + AHEAD + BEHIND.  AHEAD share = AHEAD / stepped.
  V-POS: n(SUP-W stepped) < 20 -> UNDERPOWERED; else PASS iff share(SUP-W) >= 3 x share(COR) AND share(SUP-W) > 0; else VOID.
  Arithmetic check printed for each table: if share(COR) >= 1/3 then V-POS cannot pass whatever SUP-W does (HK-021(k): decorative row).
  FREE verdict (needs V-POS PASS on the live night or on the control): diff = share(FREE) - share(COR); cycle-block bootstrap (resample cycles, 10,000, numpy default_rng seed 20261116),
     95 % percentile interval: FREE-OK iff upper <= 2 pp; FREE-STALE iff lower > 2 pp; else FREE-OPEN.
  Budget line: max(diff, 0) x n(FREE stepped) per 1,000 cycles."""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
import sys

import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script folder; xc_sup.py is this tool's sibling (our own code)
import xc_sup as X

SEED = 20261116
N_BOOT = 10000
POS_MIN_N = 20
POS_RATIO = 3
FREE_BAR_PP = 2.0
SLOT_S = 30
CLASSES = ("NEXT-OK", "AHEAD", "BEHIND", "NONE", "UNSTEPPABLE")
UNITS = ("COR", "SUP-W", "FREE")
TABLES = {
    "T-G": {"grid": 1, "report": 2, "rreport": 3, "RRR": 4, "RR73": 4, "73": 5},
    "T-C": {"grid": 1, "report": 1, "rreport": 2, "RRR": 2, "RR73": 2, "73": 3},
}
assert (SEED, N_BOOT, POS_MIN_N, POS_RATIO, FREE_BAR_PP, SLOT_S) == (20261116, 10000, 20, 3, 2.0, 30)

_RE_REPORT = re.compile(r"^[+-][0-9]{2}$")
_RE_RREPORT = re.compile(r"^R[+-][0-9]{2}$")
_RE_GRID = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?$")


def parse(msg):
    """-> (kind, partner P, sender S, type) with kind 'ok' | 'cq' | 'hashed' | 'other'; the text does not leave this function."""
    t = msg.split()
    if not t:
        return ("other", None, None, None)
    if t[0] == "CQ":
        return ("cq", None, None, None)
    if any("<" in x for x in t):
        return ("hashed", None, None, None)
    if len(t) != 3:
        return ("other", None, None, None)
    p, s, pay = t
    if pay == "RR73":
        ty = "RR73"
    elif pay == "RRR":
        ty = "RRR"
    elif pay == "73":
        ty = "73"
    elif _RE_RREPORT.match(pay):
        ty = "rreport"
    elif _RE_REPORT.match(pay):
        ty = "report"
    elif _RE_GRID.match(pay):
        ty = "grid"
    else:
        ty = None
    return ("ok", p, s, ty)


def classify(table, ty_m, ty_n):
    """class of the next transmission's type against M's type under one table (NONE is decided before this)."""
    if ty_m is None or ty_n is None or ty_m not in table or ty_n not in table:
        return "UNSTEPPABLE"
    d = table[ty_n] - table[ty_m]
    if d < 0:
        return "BEHIND"
    return "NEXT-OK" if d <= 1 else "AHEAD"


def plus30(stamp):
    d = dt.datetime.strptime(stamp, "%y%m%d_%H%M%S") + dt.timedelta(seconds=SLOT_S)
    return d.strftime("%y%m%d_%H%M%S")


def load_all(alltxt):
    """WSJT-X rows per slot, in file order: stamp -> [text]; plus the stamp range."""
    rows = collections.defaultdict(list)
    lo = hi = None
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            rows[f[0]].append(" ".join(f[7:]).strip())
            lo = f[0] if lo is None or f[0] < lo else lo
            hi = f[0] if hi is None or f[0] > hi else hi
    return rows, lo, hi


def classes_of_units(arm, alltxt):
    """-> per-unit records [(stamp, cls_xc, ty_m, found, ty_n)], counters. Text stays inside."""
    nc = X.load_nc(arm.rstrip("/\\") + "/nc.tsv")
    stamps = set(nc)
    w1 = X.load_wsjtx(alltxt, stamps)
    allrows, lo, hi = load_all(alltxt)
    recs = []
    cnt = collections.Counter()
    for s, rows in nc.items():
        w = w1.get(s, [])
        own = [r for r in rows if r["kind"] in (1, 2, 3, 4, 5)]
        for r in rows:
            if r["kind"] != 6:
                continue
            cnt["b6_publishes"] += 1
            wd = [x for x in w if x[2] != r["text"] and X.in_window_w(x[0] - r["freq"], x[1] - r["dt"])]
            od = [x for x in own if x["text"] != r["text"] and X.in_window(x["freq"] - r["freq"], x["dt"] - r["dt"])]
            if r["matched"] == 1:
                c = "COR"
            elif wd:
                c = "SUP-W"
            elif od:
                c = "SUP-O"
            else:
                c = "FREE"
            if c == "SUP-O":
                cnt["sup_o_not_a_unit"] += 1
                continue
            kind, p, snd, ty_m = parse(r["text"])
            if kind != "ok":
                cnt["excluded_" + kind] += 1
                continue
            s2 = plus30(s)
            if lo is None or not (lo <= s2 <= hi):
                cnt["excluded_no_lookup_slot"] += 1
                continue
            found, nxt, src = False, None, "none"      # nxt may stay None while found is True: a decode of an unsteppable type
            for txt in allrows.get(s2, []):
                k2, p2, s_2, ty2 = parse(txt)
                if k2 == "ok" and s_2 == snd and p2 == p:
                    found, nxt, src = True, ty2, "wsjtx"
                    break
            if not found:
                for x in nc.get(s2, []):
                    if x["kind"] in (1, 2, 3, 4, 5) and x["matched"] == 1:
                        k2, p2, s_2, ty2 = parse(x["text"])
                        if k2 == "ok" and s_2 == snd and p2 == p:
                            found, nxt, src = True, ty2, "ows"
                            break
            recs.append((s, c, ty_m, found, nxt, src))
            cnt["unit_" + c] += 1
            cnt["src_" + src] += 1
    return recs, cnt


def tabulate(recs, table):
    tab = {c: collections.Counter() for c in UNITS}
    per_cycle = collections.defaultdict(lambda: collections.Counter())
    for s, c, ty_m, found, ty_n, src in recs:
        k = "NONE" if not found else classify(table, ty_m, ty_n)
        tab[c][k] += 1
        per_cycle[s][(c, k)] += 1
    return tab, per_cycle


def stepped(cnt):
    return cnt["NEXT-OK"] + cnt["AHEAD"] + cnt["BEHIND"]


def share(cnt):
    n = stepped(cnt)
    return (cnt["AHEAD"] / n) if n else None


def vpos(tab):
    nw = stepped(tab["SUP-W"])
    sw, sc = share(tab["SUP-W"]), share(tab["COR"])
    if nw < POS_MIN_N:
        return "UNDERPOWERED"
    return "PASS" if (sw is not None and sc is not None and sw > 0 and sw >= POS_RATIO * sc) else "VOID"


def free_verdict(per_cycle, n_cycles):
    """cycle-block bootstrap of share(FREE) - share(COR); -> (lo_pp, hi_pp, point_pp, verdict-by-bar)."""
    stamps = sorted(per_cycle)
    a = np.zeros((len(stamps), 4))
    for i, s in enumerate(stamps):
        pc = per_cycle[s]
        for k in ("NEXT-OK", "AHEAD", "BEHIND"):
            a[i, 1] += pc[("FREE", k)] * (1 if k == "AHEAD" else 0)
            a[i, 0] += pc[("FREE", k)]
            a[i, 3] += pc[("COR", k)] * (1 if k == "AHEAD" else 0)
            a[i, 2] += pc[("COR", k)]
    pad = np.zeros((max(n_cycles - len(stamps), 0), 4))
    a = np.vstack([a, pad])                           # cycles that held no unit are still resampled
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(a), size=(N_BOOT, len(a)))
    sums = a[idx].sum(axis=1)                         # N_BOOT x 4
    with np.errstate(divide="ignore", invalid="ignore"):
        d = sums[:, 1] / sums[:, 0] - sums[:, 3] / sums[:, 2]
    d = d[np.isfinite(d)]
    tot = a.sum(axis=0)
    point = 100.0 * (tot[1] / tot[0] - tot[3] / tot[2]) if tot[0] and tot[2] else None
    lo, hi = (100.0 * float(np.percentile(d, 2.5)), 100.0 * float(np.percentile(d, 97.5))) if len(d) else (None, None)
    return lo, hi, point, int(len(d))


def verdict_free(lo, hi, vp):
    if vp != "PASS":
        return "NO-READING (V-POS " + vp + ")"
    if hi is not None and hi <= FREE_BAR_PP:
        return "FREE-OK"
    if lo is not None and lo > FREE_BAR_PP:
        return "FREE-STALE"
    return "FREE-OPEN"


def report(recs, cnt, n_cycles, label):
    out = {"label": label, "counters": dict(cnt), "n_cycles": n_cycles, "tables": {}}
    for name, table in TABLES.items():
        tab, per_cycle = tabulate(recs, table)
        lo, hi, point, nb = free_verdict(per_cycle, n_cycles)
        vp = vpos(tab)
        sc = share(tab["COR"])
        diff = (share(tab["FREE"]) - sc) if (share(tab["FREE"]) is not None and sc is not None) else None
        out["tables"][name] = {
            "class_counts": {c: {k: tab[c][k] for k in CLASSES} for c in UNITS},
            "stepped": {c: stepped(tab[c]) for c in UNITS},
            "ahead_share": {c: share(tab[c]) for c in UNITS},
            "none_share_of_unit": {c: (tab[c]["NONE"] / sum(tab[c].values()) if sum(tab[c].values()) else None) for c in UNITS},
            "V_POS": vp,
            "V_POS_cannot_pass_by_arithmetic_share_COR_ge_one_third": (sc is not None and sc >= 1 / 3),
            "diff_FREE_minus_COR_pp": {"point": point, "boot_lo": lo, "boot_hi": hi, "n_valid_resamples": nb},
            "FREE_verdict_if_V_POS_pass": verdict_free(lo, hi, "PASS"),
            "FREE_verdict_as_gated": verdict_free(lo, hi, vp),
            "budget_per_1000_cycles": (max(diff, 0) * stepped(tab["FREE"]) * 1000.0 / n_cycles) if diff is not None else None,
        }
    return out


def run(arm, alltxt, out, ctl_arm=None, ctl_all=None):
    nc_stamps = len(set(X.load_nc(arm.rstrip("/\\") + "/nc.tsv")))
    recs, cnt = classes_of_units(arm, alltxt)
    res = {"live": report(recs, cnt, nc_stamps, "live night replay (ON arm)")}
    if ctl_arm:
        crecs, ccnt = classes_of_units(ctl_arm, ctl_all)
        res["control"] = report(crecs, ccnt, len(set(X.load_nc(ctl_arm.rstrip("/\\") + "/nc.tsv"))), "control (acceptance arm)")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


def selftest():
    ok = True

    def chk(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print("FAIL", name, got, want)
    # parser (synthetic Q-prefix calls only)
    chk("rr73", parse("Q1AAA Q2BBB RR73")[3], "RR73")
    chk("grid", parse("Q1AAA Q2BBB JO93")[3], "grid")
    chk("grid6", parse("Q1AAA Q2BBB JO93AB")[3], "grid")
    chk("report", parse("Q1AAA Q2BBB -10")[3], "report")
    chk("rreport", parse("Q1AAA Q2BBB R-10")[3], "rreport")
    chk("73", parse("Q1AAA Q2BBB 73")[3], "73")
    chk("rrr", parse("Q1AAA Q2BBB RRR")[3], "RRR")
    chk("cq", parse("CQ Q2BBB JO93")[0], "cq")
    chk("hashed", parse("<...> Q2BBB -10")[0], "hashed")
    chk("freetext", parse("Q1AAA Q2BBB HELLO")[3], None)
    chk("two tokens", parse("Q1AAA Q2BBB")[0], "other")
    chk("partner/sender", parse("Q1AAA Q2BBB -10")[1:3], ("Q1AAA", "Q2BBB"))
    # classes under both tables
    G, C = TABLES["T-G"], TABLES["T-C"]
    chk("G report->report", classify(G, "report", "report"), "NEXT-OK")
    chk("G report->rreport", classify(G, "report", "rreport"), "NEXT-OK")
    chk("G report->RR73 (the spec's example)", classify(G, "report", "RR73"), "AHEAD")
    chk("G report->73", classify(G, "report", "73"), "AHEAD")
    chk("G rreport->report", classify(G, "rreport", "report"), "BEHIND")
    chk("C report->RR73 is the caller's own next step", classify(C, "report", "RR73"), "NEXT-OK")
    chk("C report->73", classify(C, "report", "73"), "AHEAD")
    chk("C grid->73", classify(C, "grid", "73"), "AHEAD")
    chk("C grid->rreport", classify(C, "grid", "rreport"), "NEXT-OK")
    chk("C 73->grid", classify(C, "73", "grid"), "BEHIND")
    chk("unsteppable", classify(C, None, "73"), "UNSTEPPABLE")
    chk("plus30 rolls the minute", plus30("261114_235945"), "261115_000015")
    # V-POS: the four outcomes, including ones that must NOT pass
    def mk(w_ahead, w_ok, c_ahead, c_ok):
        t = {c: collections.Counter() for c in UNITS}
        t["SUP-W"].update({"AHEAD": w_ahead, "NEXT-OK": w_ok})
        t["COR"].update({"AHEAD": c_ahead, "NEXT-OK": c_ok})
        return t
    chk("vpos underpowered", vpos(mk(5, 10, 1, 99)), "UNDERPOWERED")
    chk("vpos pass", vpos(mk(20, 20, 1, 99)), "PASS")
    chk("vpos void ratio", vpos(mk(10, 30, 20, 80)), "VOID")
    chk("vpos void zero (0 >= 3 x 0 must not pass)", vpos(mk(0, 40, 0, 100)), "VOID")
    chk("vpos void COR >= 1/3 cannot pass", vpos(mk(40, 0, 40, 60)), "VOID")
    chk("verdict gated", verdict_free(0.1, 1.0, "UNDERPOWERED").startswith("NO-READING"), True)
    chk("verdict ok", verdict_free(-1, 1.9, "PASS"), "FREE-OK")
    chk("verdict stale", verdict_free(2.1, 5, "PASS"), "FREE-STALE")
    chk("verdict open", verdict_free(0.5, 3, "PASS"), "FREE-OPEN")
    print("selftest ALL PASS" if ok else "selftest FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        sys.exit(selftest())
    run(sys.argv[2], sys.argv[3], sys.argv[4], *(sys.argv[5:7] if len(sys.argv) >= 7 else ()))
