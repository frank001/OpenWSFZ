#!/usr/bin/env python3
"""XC-ROUND free-check diagnosis: why do batches 1-3 differ between the PAYLOAD-FIT runs (pf) and the XC-ROUND runs (xr) in a few cycles although every round-0-to-3 probe row is identical?

The suspect is the design itself: batch 4 is stored in the cross-cycle PRIOR store like batch 2 (spec section 2 item 2), and the cross-cycle stage of LATER cycles tests the messages of the cycles 30, 60 and 90 s
earlier as templates, so a batch-4 decode can become a template and add a batch-3 detection (or move one) in a later cycle. This script tests that, from numbers only:
  for each cycle whose batches 1-3 differ: which batches the differing rows are in, and whether a cycle 30, 60 or 90 s earlier had batch-4 decodes (xr run).
Message text is read inside `diag_slice` and returns counts only (HK-037).
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

SC = r"D:\Projects\claude\_qa-scratch"
SL = {"S40": 170, "H40": 240, "H20": 240}


def norm(t):
    return " ".join(t.split())


def stamp_time(s):
    return datetime.strptime(s, "%y%m%d_%H%M%S")


def diag_slice(name):
    n = SL[name]
    od, nd = SC + r"\lc-base\runs\pf_%s_L_n%d" % (name, n), SC + r"\lc-base\runs\xr_%s_L_n%d" % (name, n)

    def load(d):
        rows = {}
        with open(d + r"\nc.tsv", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) < 11:
                    continue
                k = (c[0], norm(c[10]))
                if k not in rows:
                    rows[k] = int(c[1])                                          # the batch
        return rows
    old, new = load(od), load(nd)
    b4_by_cycle = Counter(k[0] for k, b in new.items() if b == 4)
    times = {s: stamp_time(s) for s in {k[0] for k in new}}
    extra = [(k, b) for k, b in new.items() if b in (1, 2, 3) and (k not in old or old[k] not in (1, 2, 3))]
    lost = [(k, b) for k, b in old.items() if b in (1, 2, 3) and (k not in new or new[k] not in (1, 2, 3))]
    kinds_extra = Counter(b for _, b in extra)
    kinds_lost = Counter(b for _, b in lost)
    # an extra/lost row is "explained" when a cycle 30, 60 or 90 s EARLIER had at least one batch-4 decode (a possible new template)
    def explained(stamp):
        t = times.get(stamp) or stamp_time(stamp)
        return any(b4_by_cycle.get(next((s for s, tt in times.items() if tt == t - timedelta(seconds=d)), None), 0) > 0 for d in (30, 60, 90))
    ex = sum(1 for (st, _), _ in extra if explained(st))
    lo = sum(1 for (st, _), _ in lost if explained(st))
    # was the same message already in the earlier-batch list of the OLD run in that cycle as batch 4 now? (the row moved from 3 to 4 or the reverse)
    moved = sum(1 for (k, b) in extra if k in old)
    return {"extra_rows_in_b123": len(extra), "extra_by_batch": dict(kinds_extra), "extra_explained_by_a_batch4_decode_30_60_90_s_earlier": ex, "extra_not_explained": len(extra) - ex,
            "lost_rows_from_b123": len(lost), "lost_by_batch": dict(kinds_lost), "lost_explained": lo, "lost_not_explained": len(lost) - lo, "extra_rows_whose_text_was_in_the_old_run_in_another_batch": moved,
            "cycles_with_batch4_decodes": len(b4_by_cycle)}


if __name__ == "__main__":
    out = {s: diag_slice(s) for s in SL}
    json.dump(out, open(os.path.join(SC, "lc-base", "xr_freecheck_diag.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
