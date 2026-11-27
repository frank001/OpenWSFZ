#!/usr/bin/env python3
"""PAYLOAD-FIT: are the decodes it added and WSJT-X did not confirm (ours_only) real?  Data on disk only, no new run (the Captain's order, 2026-11-27, relayed by the Architect).

  python -I pf_oo_check.py     (reads lc-base\\runs\\{probe,pf}_<slice>_L_n*\\{nc dump, sel.json} and WSJT-X's ALL.TXT of each slice)

Groups (a decode = one (cycle, message) of the lean's published results, as dr0_run.py counts them):
  added_oo     in the PAYLOAD-FIT run, not in the SUB-PROBE run (by cycle + message), and not matched to a WSJT-X decode  (the ones asked about)
  added_m      the same, but matched  (the 'matched extras': the reference for the SNR and for the repeat share)
  base_oo      in the SUB-PROBE run and not matched there  (the baseline ours_only: the second reference for the repeat share)
Repeat check (the Architect's definition): the same message text appears in any of the next four cycles (15 to 60 s later, only cycles of the replay), at about the same frequency (+-10 Hz), in the PAYLOAD-FIT
run's own decodes OR in WSJT-X's decodes of that cycle. Only decodes that have all four following cycles in the replay are evaluated (the last cycles are excluded; their number is printed).
Privacy (HK-037 / NFR-021): message text is read INSIDE `analyse_slice` and never leaves it: only counts, repeat flags and SNR numbers are returned. No text is printed or written.
"""
import json
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
SL = {"S40": (170, "20261114_2312_endurance_run-gathered"), "H40": (240, "20261028_2233_endurance_run-gathered"), "H20": (240, "20260808_live_run_0016-8080")}
FREQ_TOL_HZ = 10.0
NEXT_CYCLES = 4
CYCLE_S = 15
AP_TAIL = re.compile(r"^a\d$")


def norm(text):
    """Single spaces; WSJT-X's trailing decoration tokens ('?', 'aN') dropped."""
    t = text.split()
    while t and (t[-1] == "?" or AP_TAIL.match(t[-1])):
        t.pop()
    return " ".join(t)


def stamp_time(s):
    return datetime.strptime(s, "%y%m%d_%H%M%S")


def quart(v):
    if not v:
        return None
    s = sorted(v)
    q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))]
    return {"n": len(s), "q1": q(0.25), "median": statistics.median(s), "q3": q(0.75)}


def analyse_slice(name):
    n, folder = SL[name]
    old_d, new_d = SC + r"\lc-base\runs\probe_%s_L_n%d" % (name, n), SC + r"\lc-base\runs\pf_%s_L_n%d" % (name, n)
    sel = json.load(open(new_d + r"\sel.json"))
    assert sel == json.load(open(old_d + r"\sel.json"))
    stamps = list(sel["runs"][sel["run"]]["FULL"])
    when = {s: stamp_time(s) for s in stamps}
    by_time = {w: s for s, w in when.items()}

    def load_nc(d):
        """{(stamp, normalised text): (freq, snr, matched)}  one row per (stamp, text), the first, as dr0_run.py. TEXT IS READ HERE AND KEPT ONLY IN THIS FUNCTION'S RETURN FOR THE CALLER'S SET ARITHMETIC (never printed)."""
        out = {}
        with open(d + r"\nc.tsv", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) < 11:
                    continue
                k = (c[0], norm(c[10]))
                if k not in out:
                    out[k] = (float(c[3]), float(c[5]), c[2] == "1")
        return out

    old, new = load_nc(old_d), load_nc(new_d)
    wsjtx = {s: [] for s in stamps}                                           # stamp -> [(freq, normalised text)]
    want = set(stamps)
    with open(os.path.join(ART, folder, "wsjt-x", "ALL.TXT"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[:13] not in want:
                continue
            f = [x for x in line.split(" ") if x]
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                wsjtx[f[0]].append((float(f[6]), norm(" ".join(f[7:]))))
            except ValueError:
                continue
    lean_new = {}                                                              # stamp -> [(freq, text)] of the PAYLOAD-FIT run
    for (s, t), (fr, snr, m) in new.items():
        lean_new.setdefault(s, []).append((fr, t))

    groups = {"added_oo": [], "added_m": [], "base_oo": []}
    for k, (fr, snr, m) in new.items():
        if k not in old:
            groups["added_m" if m else "added_oo"].append((k, fr, snr))
    for k, (fr, snr, m) in old.items():
        if not m:
            groups["base_oo"].append((k, fr, snr))
    lost = {"lost_oo": sum(1 for k, v in old.items() if k not in new and not v[2]), "lost_m": sum(1 for k, v in old.items() if k not in new and v[2])}

    def nexts(s):
        return [by_time[when[s] + timedelta(seconds=CYCLE_S * i)] for i in range(1, NEXT_CYCLES + 1) if (when[s] + timedelta(seconds=CYCLE_S * i)) in by_time]

    res = {}
    for g, rows in groups.items():
        evald = rep = cq = cq_rep = ncq = ncq_rep = excluded = 0
        rep_by_lean = rep_by_wsjtx = 0
        snrs = []
        for (s, t), fr, snr in rows:
            snrs.append(snr)
            nx = nexts(s)
            if len(nx) < NEXT_CYCLES:
                excluded += 1
                continue
            is_cq = t.startswith("CQ ")
            hit_l = any(t == tt and abs(fr - ff) <= FREQ_TOL_HZ for s2 in nx for (ff, tt) in lean_new.get(s2, []))
            hit_w = any(t == tt and abs(fr - ff) <= FREQ_TOL_HZ for s2 in nx for (ff, tt) in wsjtx.get(s2, []))
            hit = hit_l or hit_w
            evald += 1; rep += hit; rep_by_lean += hit_l; rep_by_wsjtx += hit_w
            if is_cq:
                cq += 1; cq_rep += hit
            else:
                ncq += 1; ncq_rep += hit
        res[g] = {"decodes": len(rows), "evaluated": evald, "excluded_last_cycles": excluded, "repeated": rep, "repeat_share_pct": round(100.0 * rep / evald, 1) if evald else None,
                  "repeated_seen_by_lean": rep_by_lean, "repeated_seen_by_wsjtx": rep_by_wsjtx,
                  "cq_evaluated": cq, "cq_repeated": cq_rep, "non_cq_evaluated": ncq, "non_cq_repeated": ncq_rep, "snr_db": quart(snrs)}
    res["lost_between_runs"] = lost
    res["ours_net_change"] = len(new) - len(old)
    return res


def main():
    out = {s: analyse_slice(s) for s in SL}
    with open(os.path.join(SC, "lc-base", "pf_oo_check.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
