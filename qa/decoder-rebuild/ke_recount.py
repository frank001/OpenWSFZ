#!/usr/bin/env python3
"""KNOWN-ERASURE spec section 0, re-counted by QA for the record (the Architect's request, 2026-11-27): how many kept candidates that FAILED every tier end with at most 5 unsatisfied parity checks on their best tier?

  python -I ke_recount.py [tag]      (tag default xn; reads lc-base\\runs\\<tag>_<slice>_L_n*\\probe.tsv: numbers only, no message text)

Definitions (stated, because the count depends on them):
  CAND row  = probe kind 2; kept = the row's `kept` column is 1 (round 0: every candidate; rounds 1-4: those inside a patch window);
  failed    = the row's outcome is one of FAILED (A_BP, A_CRC, B_NE, B_BP, B_CRC, CQ_FAIL, B_SKIP, B_NOC3): no tier decoded it;
  best tier = the smaller of the tier-A and tier-B unsatisfied-check counts that exist: tier A when `a_code` is 2 (A_BP) and `a_unsat` >= 0; tier B when `b_code` is 4 (B_BP, the BP stage of tier B) and `b_unsat` >= 0
              (the same two predicates sub_probe_analyze.py uses for the K2 'best attempt'); a failed candidate with neither is counted in the total but not in the <= 5 column ('no unsat figure').
Three variants are printed so the Architect's figure can be matched to a definition: (V1) every kept failed candidate, all rounds; (V2) round 0 only; (V3) rounds 1-4 only. Counts only.
"""
import os
import sys
from collections import Counter

sys.argv = [sys.argv[0]] + sys.argv[1:]
TAG = sys.argv[1] if len(sys.argv) > 1 else "xn"
SC = r"D:\Projects\claude\_qa-scratch"
SL = {"S40": 170, "H40": 240, "H20": 240}
KIND_CAND = 2
FAILED = {2, 3, 4, 6, 7, 9, 14, 15}
THRESH = 5


def count(name):
    d = SC + r"\lc-base\runs\%s_%s_L_n%d" % (TAG, name, SL[name])
    out = {"all": Counter(), "round0": Counter(), "rounds1to4": Counter()}
    with open(d + r"\probe.tsv", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 17 or int(c[1]) != KIND_CAND:
                continue
            rnd, kept, outc = int(c[2]), int(c[8]), int(c[9])
            if kept != 1 or outc not in FAILED:
                continue
            a_code, a_uns, b_code, b_uns = int(c[11]), int(c[12]), int(c[13]), int(c[14])
            u = []
            if a_code == 2 and a_uns >= 0:
                u.append(a_uns)
            if b_code == 4 and b_uns >= 0:
                u.append(b_uns)
            for g in ("all", "round0" if rnd == 0 else "rounds1to4"):
                out[g]["failed_kept"] += 1
                if not u:
                    out[g]["no_unsat_figure"] += 1
                elif min(u) <= THRESH:
                    out[g]["best_unsat_le_5"] += 1
    return {g: dict(v) for g, v in out.items()}


if __name__ == "__main__":
    for s in SL:
        r = count(s)
        print(s, r)
