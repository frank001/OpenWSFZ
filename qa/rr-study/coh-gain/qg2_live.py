#!/usr/bin/env python3
"""Q-GATE-2 V-L and live_hit (spec qa/rr-study/2026-10-20-1530-architect-to-qa-spec-q-gate-2.md, section 4 and section 6 row V-L).

live_hit of a WSJT-X row = the endurance ANOVA's OWN matcher found it a partner: same cycle stamp + same normalised message text
(anova_common.match_pairs: for each key the first min(len(ours), len(wsjtx)) rows pair up in file order). No new matcher: this
re-implements the pairing only to keep the per-row flag, and ASSERTS its count equals match_pairs' length on the same rows.

V-L: the number of matched pairs over the whole night must equal 97,480 (the gathered ANOVA, 2026-10-20), exactly.

HK-037 / NFR-021: message text lives only inside this function; the output holds stamps, row indices and flags, never text.
Usage: python qg2_live.py <ours ALL.TXT> <wsjtx ALL.TXT> <out.json>
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\endurance")
import anova_common as ac  # noqa: E402

EXPECTED_MATCHED = 97480  # the gathered ANOVA of 20261019_1905 (anova_report.md, "Matched pairs")


def main() -> int:
    ours_p, wsjtx_p, out_p = sys.argv[1:4]
    ours, wsjtx = ac.parse_all_txt(ours_p), ac.parse_all_txt(wsjtx_p)
    n_lib = len(ac.match_pairs(ours, wsjtx))
    okeys = defaultdict(int)
    for r in ours:
        okeys[(r["ts"], ac.normalize_hash_tokens(r["message"]))] += 1
    used = defaultdict(int)
    hit_by_stamp = defaultdict(list)  # stamp -> [0/1 per WSJT-X row, file order]
    n_own = 0
    for r in wsjtx:
        k = (r["ts"], ac.normalize_hash_tokens(r["message"]))
        h = 1 if used[k] < okeys.get(k, 0) else 0
        used[k] += h
        n_own += h
        hit_by_stamp[r["ts"]].append(h)
    res = {
        "ours_rows": len(ours), "wsjtx_rows": len(wsjtx),
        "matched_library": n_lib, "matched_own_flags": n_own, "expected": EXPECTED_MATCHED,
        "V-L": "PASS" if (n_lib == n_own == EXPECTED_MATCHED) else "FAIL",
        "wsjtx_rows_live_hit0": len(wsjtx) - n_own,
        "hit_by_stamp": hit_by_stamp,
    }
    json.dump(res, open(out_p, "w"))
    print({k: v for k, v in res.items() if k != "hit_by_stamp"})
    return 0 if res["V-L"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
