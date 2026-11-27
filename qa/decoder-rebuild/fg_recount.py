#!/usr/bin/env python3
"""FINE-GRID section 0 re-count (spec-fine-grid.md section 4.1): candidate counts per cycle and round, and the shadowed share, from the XC-ROUND confirmation runs' probe rows. Numbers only (HK-037).

  python -I fg_recount.py [tag]        (default xn; reads lc-base\\runs\\<tag>_<slice>_L_n<cycles>\\probe.tsv)

CAND rows (kind 2). A candidate is SHADOWED when another CAND row of the same cycle and round with a STRICTLY higher score lies within 6.25 Hz and 0.16 s of it (the spec's predicate; ties are not
shadowed, and the count of exact-score ties inside the window is printed so the choice can be read). Rows are those the probe holds (a cycle whose rows overflowed the probe is listed and left out).
Probe columns (tab-separated): stamp, kind, round, f_hz, time_s, amp, supp, score, kept, outcome, ...
"""
import collections
import sys

SC = r"D:\Projects\claude\_qa-scratch"
SL = {"S40": 170, "H40": 240, "H20": 240}
TAG = sys.argv[1] if len(sys.argv) > 1 else "xn"
KIND_CAND = 2
DF_HZ, DT_S = 6.25, 0.16
ROUND_NAMES = {0: "round0"}


def main():
    grand = {}
    for sl, n in SL.items():
        path = SC + r"\lc-base\runs\%s_%s_L_n%d\probe.tsv" % (TAG, sl, n)
        rows = collections.defaultdict(list)             # (stamp, round) -> [(f, t, score)]
        overflow = set()
        with open(path, encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) == 2:
                    overflow.add(c[0])
                    continue
                if int(c[1]) != KIND_CAND:
                    continue
                rows[(c[0], int(c[2]))].append((float(c[3]), float(c[4]), float(c[7])))
        stamps = sorted({k[0] for k in rows})
        stats = {"r0": collections.Counter(), "res": collections.Counter()}
        full = {"r0": collections.Counter(), "res": collections.Counter()}
        sizes = {"r0": collections.Counter(), "res": collections.Counter()}
        for (st, rd), lst in rows.items():
            if st in overflow:
                continue
            g = "r0" if rd == 0 else "res"
            n_sh = n_tie = n_shtb = 0
            for i, (f, t, s) in enumerate(lst):
                sh = False
                tie = False
                sh_tb = False
                for j, (f2, t2, s2) in enumerate(lst):
                    if i == j or abs(f2 - f) > DF_HZ or abs(t2 - t) > DT_S:
                        continue
                    if s2 > s:
                        sh = True
                        break
                    if s2 == s:
                        tie = True
                        if (f2, t2) < (f, t):                 # THIN's tie-break (spec 1a): the lower frequency, then the earlier time, wins
                            sh_tb = True
                n_sh += sh
                n_shtb += (sh or sh_tb)
                n_tie += (tie and not sh)
            stats[g]["cands"] += len(lst)
            stats[g]["shadowed"] += n_sh
            stats[g]["shadowed_tiebreak"] += n_shtb
            stats[g]["ties_not_shadowed"] += n_tie
            stats[g]["rounds"] += 1
            sizes[g][len(lst)] += 1
        print("== %s (%s, %d cycles with rows, %d overflowed and left out)" % (sl, TAG, len(stamps), len(overflow & set(stamps))))
        for g in ("r0", "res"):
            s = stats[g]
            top = sizes[g].most_common(3)
            print("  %-3s rounds=%d  cands=%d  shadowed=%d (%.1f %%)  with THIN's tie-break %d (%.1f %%)  exact-score ties not counted=%d  size histogram (most common)=%s" % (
                g, s["rounds"], s["cands"], s["shadowed"], 100.0 * s["shadowed"] / max(1, s["cands"]), s["shadowed_tiebreak"], 100.0 * s["shadowed_tiebreak"] / max(1, s["cands"]), s["ties_not_shadowed"], top))
        grand[sl] = stats
    return grand


if __name__ == "__main__":
    main()
