#!/usr/bin/env python3
"""G2(b) passband FAMILY adjudicator -- the cross-rung mechanism the A3/C5
combination rule needed and never had.

HK-021 requires a pre-registered check to be drafted by writing the code that
evaluates it. "The passband family closes only if NO rung reads ROW 1 or
ROW 2" (the Architect's own C5 repair of his review-1 A3 recommendation) was
pre-registered prose with no such code -- g2b_gate.py prints exactly one row
per rung and returns 0 on every path, including ROW 0, so nothing downstream
could adjudicate the three-rung ladder without regexing English out of a
console log. That is exactly how the bar got softened once already, in
g2_verification_report.py -- the finding that opened this whole review chain
(D2, `2026-08-12-2052-architect-to-qa-g2b-review-4.md`).

This file reads the three --emit-verdict JSON files g2b_gate.py can now
write (one per rung invocation) and prints exactly one adjudication:

    CLOSE          -- all three verdicts read ROW_3. The passband family
                      closes: none of the three widenings under test
                      delivered enough to justify shipping any of them.
    DO NOT CLOSE   -- at least one verdict reads ROW_1 or ROW_2, named.
    REFUSE         -- the ladder itself is not evaluable: fewer or more than
                      three verdicts, any verdict reads ROW_0/ROW_0d (a
                      precondition failure or a gate defect is not evidence),
                      or two verdicts share an f_min (a family verdict from
                      an incomplete or duplicated ladder is not a family
                      verdict).

Deliberate asymmetry (D2, explicit): this instrument can only ever CLOSE the
family. It never ships anything, and it must never print a recommendation
among eligible (ROW_1) rungs -- the choice among eligible rungs is reserved
to the Captain (pre-reg §4/§8), unchanged by anything here. DO NOT CLOSE is
not a ranking; it is a refusal to close, full stop.

Usage:
    python g2b_family.py --verdict verdict_f180.json \
                          --verdict verdict_f140.json \
                          --verdict verdict_f100.json
"""
from __future__ import annotations

import argparse
import json
import sys

REQUIRED_LADDER_SIZE = 3
REFUSAL_ROWS = {"ROW_0", "ROW_0d"}


def load_verdict(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict", action="append", required=True, metavar="PATH",
                     dest="verdicts",
                     help="path to a --emit-verdict JSON from one rung "
                          "invocation of g2b_gate.py; pass exactly three, "
                          "one per rung of the ladder")
    args = ap.parse_args()

    paths = args.verdicts
    print(f"\n{'=' * 78}\nG2(b) FAMILY ADJUDICATOR -- {len(paths)} verdict(s) "
          f"supplied\n{'=' * 78}")

    # ── Refusal condition 1: the ladder must be exactly three rungs. Fewer
    # is an incomplete ladder; more is not this ladder (a duplicate, a stray
    # file, or a rung run twice under different names) -- neither licenses a
    # family verdict.
    if len(paths) != REQUIRED_LADDER_SIZE:
        print(f"\n  REFUSE -- {len(paths)} verdict file(s) supplied, need "
              f"exactly {REQUIRED_LADDER_SIZE} (one per rung). A family "
              "verdict from an incomplete or duplicated ladder is not a "
              "family verdict.")
        return 0

    verdicts = []
    for p in paths:
        try:
            v = load_verdict(p)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"\n  REFUSE -- could not read verdict {p!r}: {exc}. A "
                  "family verdict cannot be built from a missing or "
                  "malformed verdict file.")
            return 0
        missing = [k for k in ("band", "f_min", "f_max", "row") if k not in v]
        if missing:
            print(f"\n  REFUSE -- verdict {p!r} is missing "
                  f"{', '.join(missing)} -- not a g2b_gate.py --emit-verdict "
                  "output, or from an older revision that predates D2.")
            return 0
        verdicts.append((p, v))
        print(f"  {p}: band={v['band']} f_min={v['f_min']} f_max={v['f_max']} "
              f"row={v['row']}")

    # ── Refusal condition 2: no two rungs may share an f_min. A ladder is
    # three DISTINCT rungs by definition; two verdicts at the same f_min
    # means the ladder was not actually run as three rungs (a rung re-run
    # under two file names, most likely), and reading it as one is silently
    # discarding a real rung's evidence.
    f_mins = [v["f_min"] for _, v in verdicts]
    if len(set(f_mins)) != len(f_mins):
        print(f"\n  REFUSE -- two or more verdicts share an f_min "
              f"({sorted(f_mins)}) -- the ladder must be three DISTINCT "
              "rungs, not the same rung counted twice.")
        return 0

    # ── Refusal condition 3: no verdict may read ROW_0/ROW_0d. Those rows
    # mean "no read happened" (a precondition failed) or "gate defect" --
    # neither is evidence about whether that rung's mechanism delivered, and
    # treating either as silently equivalent to ROW_3 would let a precondition
    # failure or a bug CLOSE the family.
    refused = [(p, v) for p, v in verdicts if v["row"] in REFUSAL_ROWS]
    if refused:
        named = "; ".join(f"{p} (f_min={v['f_min']}, {v['row']})"
                           for p, v in refused)
        print(f"\n  REFUSE -- {len(refused)} verdict(s) read ROW_0/ROW_0d, "
              f"which is NO READ, not evidence: {named}. Fix the "
              "precondition (or the gate defect) and re-run that rung "
              "before asking this instrument to adjudicate the family.")
        return 0

    # ── The adjudication itself. Every remaining verdict reads ROW_1, ROW_2,
    # or ROW_3 -- the only three possibilities left after the refusal checks
    # above, since ROW_0/ROW_0d were already excluded.
    non_row3 = sorted(((v["f_min"], v["row"]) for _, v in verdicts))
    non_row3 = [(f_min, row) for f_min, row in non_row3 if row != "ROW_3"]

    if not non_row3:
        print(f"\n  CLOSE -- all {REQUIRED_LADDER_SIZE} rungs read ROW_3 "
              f"({sorted(f_mins)}). Per the repaired combination rule (C5): "
              "the passband family closes.")
    else:
        named = "; ".join(f"f_min={f_min} read {row}" for f_min, row in non_row3)
        print(f"\n  DO NOT CLOSE -- {named}. The family does not close "
              "while any rung reads ROW_1 or ROW_2. This is not a ranking "
              "among rungs and licenses no choice among them -- the "
              "Captain's choice among eligible (ROW_1) rungs, if any, is "
              "unchanged by this adjudication.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
