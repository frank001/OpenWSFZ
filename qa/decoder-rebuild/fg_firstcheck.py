#!/usr/bin/env python3
"""FINE-GRID first check (spec-fine-grid.md section 3), before any rate is read. Numbers only (HK-037).

  python -I fg_firstcheck.py <run dir name> <arm T|F>

Arm T (thin 1, 2 x 2): the shadowed share of CAND rows is 0 in round 0 and in the residual rounds, by section 0.2's predicate (a CAND row of the same cycle and round with a higher score, or an equal score and a
lower frequency, then an earlier time, within 6.25 Hz and 0.16 s), plus: the round-0 list is not full of copies (rows per cycle printed).
Arm F (thin 1, 4 x 4): the probe's sub-positions span 0 to 3 in both axes (osr 4/4 confirmed), the shadowed share is 0 as for arm T, and the number of PUBLISHED round-0 and residual candidates (outcome 1, 5 or 8: A_OK,
B_OK, CQ_OK) on an odd time or frequency sub-position is > 0. Also prints the XC round's (round 4) rows so a silently absent round is visible.
Probe columns: stamp, kind, round, freq_hz, time_s, amp, supp_db, score, kept, outcome, gate, a_code, a_unsat, b_code, b_unsat, cq_code, cq_unsat, [time_sub, freq_sub].
"""
import collections
import os
import sys

RUNS = r"D:\Projects\claude\_qa-scratch\lc-base\runs"
run, arm = sys.argv[1], sys.argv[2]
KIND_CAND = 2
PUBLISHED = {1, 5, 8}
EPS_F, EPS_T = 0.01, 0.001
DF, DT = 6.25, 0.16

cands = collections.defaultdict(list)      # (stamp, round) -> [(f, t, score, outcome, tsub, fsub)]
sub_t, sub_f = collections.Counter(), collections.Counter()
rounds = collections.Counter()
with open(os.path.join(RUNS, run, "probe.tsv"), encoding="utf-8") as fh:
    hdr = next(fh).rstrip("\n").split("\t")
    assert hdr[-2:] == ["time_sub", "freq_sub"], hdr[-2:]
    for line in fh:
        c = line.rstrip("\n").split("\t")
        if len(c) < 19 or int(c[1]) != KIND_CAND:
            continue
        r = (float(c[3]), float(c[4]), int(c[7]), int(c[9]), int(c[17]), int(c[18]))
        cands[(c[0], int(c[2]))].append(r)
        sub_t[r[4]] += 1
        sub_f[r[5]] += 1
        rounds[int(c[2])] += 1


def shadowed(lst):
    n = 0
    for i, (f, t, s, _o, _a, _b) in enumerate(lst):
        for j, (f2, t2, s2, _o2, _a2, _b2) in enumerate(lst):
            if i == j or abs(f2 - f) > DF + EPS_F or abs(t2 - t) > DT + EPS_T:
                continue
            if s2 > s or (s2 == s and (f2, t2) < (f, t)):
                n += 1
                break
    return n


tot = collections.Counter()
for (st, rd), lst in cands.items():
    g = "r0" if rd == 0 else ("xc" if rd == 4 else "res")
    tot[g + "_rows"] += len(lst)
    tot[g + "_rounds"] += 1
    tot[g + "_shadowed"] += shadowed(lst)
print("run %s arm %s" % (run, arm))
for g in ("r0", "res", "xc"):
    print("  %-3s rounds=%d rows=%d (%.1f per round) shadowed=%d (%.3f %%)" % (g, tot[g + "_rounds"], tot[g + "_rows"], tot[g + "_rows"] / max(1, tot[g + "_rounds"]), tot[g + "_shadowed"],
                                                                         100.0 * tot[g + "_shadowed"] / max(1, tot[g + "_rows"])))
print("  rows per round number:", dict(sorted(rounds.items())))
print("  time_sub counts:", dict(sorted(sub_t.items())), " freq_sub counts:", dict(sorted(sub_f.items())))
odd_pub = sum(1 for lst in cands.values() for r in lst if r[3] in PUBLISHED and (r[4] % 2 == 1 or r[5] % 2 == 1))
all_pub = sum(1 for lst in cands.values() for r in lst if r[3] in PUBLISHED)
odd_all = sum(1 for lst in cands.values() for r in lst if (r[4] % 2 == 1 or r[5] % 2 == 1))
print("  published CAND rows: %d, of them on an odd time or frequency sub-position: %d; all CAND rows on an odd sub-position: %d of %d" % (all_pub, odd_pub, odd_all, sum(len(v) for v in cands.values())))
shad = sum(tot[g + "_shadowed"] for g in ("r0", "res", "xc"))
if arm == "T":
    ok = shad == 0 and max(sub_t) <= 1 and max(sub_f) <= 1
    print("FIRST CHECK arm T (shadowed = 0, grid 2 x 2):", "PASS" if ok else "FAIL")
else:
    ok = shad == 0 and max(sub_t) == 3 and max(sub_f) == 3 and odd_pub > 0 and tot["xc_rows"] > 0
    print("FIRST CHECK arm F (shadowed = 0, sub-positions 0..3, published on odd sub-positions > 0, XC round rows present):", "PASS" if ok else "FAIL")
