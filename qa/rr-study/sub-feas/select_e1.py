#!/usr/bin/env python
"""SUB-FEAS speed-redesign E1 selection: build e1_selection.json from the Architect's registered rule.

Spec: qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md section 2 (E1) and
Amendment 1 (section 5a): pool H u M as (run, stamp) pairs, sort by (run, stamp), take indices 0, 9, 18, ...,
plus the 60 pilot cycles. Frozen and hashed BEFORE any hash is computed by either DLL.

Inputs are the frozen section 8.1 selection (`selection.json`, SHA-256 asserted below), so no ALL.TXT is read
here at all: stamps and run labels only (NFR-021 / HK-037).

Hash-order guard: every list is sorted at construction. No RNG is used.
"""
import hashlib
import json
import os
import sys

ROOT = r"D:\Projects\claude\OpenWSFZ\worktrees\qa"
SEL81 = os.path.join(ROOT, r"qa\rr-study\results\2026-09-29-sub-feas-8-1-replay\selection.json")
OUT_DIR = os.path.join(ROOT, r"qa\rr-study\results\2026-09-30-sub-feas-speed-e1")
RUNS = ["20260922_2056", "20260923_1730", "20260925_2010"]
SEL81_SHA256 = "730d6ea61f25ba8cad90520a17266b3efe0e1e476b1bd1ce29d1a6cbcc3b1f15"
STRIDE = 9

# Constants the spec fixes, asserted so a drift in this script cannot go unnoticed.
assert STRIDE == 9


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def main():
    actual = sha256_of(SEL81)
    assert actual == SEL81_SHA256, f"section 8.1 selection.json changed: {actual}"
    sel = json.load(open(SEL81, encoding="utf-8"))
    assert sorted(sel["runs"].keys()) == RUNS

    pooled = []
    pilots = []
    for run in RUNS:
        d = sel["runs"][run]
        pooled += [(run, s) for s in d["H"]] + [(run, s) for s in d["M"]]
        pilots += [(run, s) for s in d["pilot"]]
    pooled.sort()          # (run, stamp), lexicographic: hash-order guard
    pilots.sort()

    assert len(pooled) == 905, len(pooled)       # H 605 + M 300 (section 8.1 report)
    assert len(pilots) == 60, len(pilots)
    assert len(set(pooled)) == len(pooled) and not (set(pooled) & set(pilots))

    every9 = pooled[0::STRIDE]
    cycles = sorted(set(every9) | set(pilots))
    assert len(cycles) == len(every9) + len(pilots)

    out = {
        "rule": "pooled H u M as (run, stamp), sorted by (run, stamp), indices 0,9,18,...; plus the 60 pilot cycles",
        "source_selection_sha256": actual,
        "stride": STRIDE,
        "counts": {"every9": len(every9), "pilot": len(pilots), "total": len(cycles)},
        "cycles": [{"run": r, "stamp": s, "kind": "pilot" if (r, s) in set(pilots) else "every9"}
                   for r, s in cycles],
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "e1_selection.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps(out["counts"]))
    print("e1_selection.json sha256", sha256_of(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
