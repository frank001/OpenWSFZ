#!/usr/bin/env python3
"""ROW 0b, means 2 -- independent field-by-field comparison, in memory.

Spec Amendment 1 Sec.A5: "must NOT import or reuse means 1's canonicaliser.
Load both JSONs independently and compare field-by-field in memory,
reporting counts compared. A shared helper between the two makes ROW 0b
decorative." This file imports NOTHING from row0b_means1_canonical_diff.py
and re-derives its own comparison from the raw `per_file` records.

HK-022's question, answered here rather than assumed: what error could
means 1 NOT detect? A canonicaliser bug that stringifies two different
decode records identically (e.g. truncating a field, or a delimiter
collision inside a message string). Means 2 compares the parsed Python
values directly -- floats compared as floats, no string round-trip -- so a
delimiter or formatting bug in means 1 cannot hide a real difference here.

Scope matches Sec.A5's table exactly: ts, decodes[] (ORDERED, f/dt/snr/m),
av, truncated are compared. wall_s is excluded (timing jitter). cand[]/
pass[] are REPORTED if they move while decodes[] does not, never gated.

Usage: python row0b_means2_field_compare.py <base_json> <inst_json>
Exit 0 = identical on every gated field. Non-zero = a difference found.
"""
from __future__ import annotations

import argparse
import json
import sys


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base_json")
    ap.add_argument("inst_json")
    args = ap.parse_args()

    base = load(args.base_json)
    inst = load(args.inst_json)

    base_files = base["per_file"]
    inst_files = inst["per_file"]

    diffs = []
    cand_pass_moves = []

    if len(base_files) != len(inst_files):
        print(f"STRUCTURAL MISMATCH: BASE {len(base_files)} cycles vs "
              f"INST {len(inst_files)} cycles -- ROW 0b FAILS", file=sys.stderr)
        return 1

    n_compared = 0
    n_decodes_compared = 0

    for i in range(len(base_files)):
        b = base_files[i]
        n = inst_files[i]
        n_compared += 1

        if b["ts"] != n["ts"]:
            # ts is a timestamp, not message content -- safe to print.
            diffs.append(f"cycle {i}: ts differs BASE={b['ts']!r} INST={n['ts']!r}")
            continue

        if b["av"] != n["av"]:
            diffs.append(f"ts={b['ts']}: av differs BASE={b['av']} INST={n['av']}")
        if b["truncated"] != n["truncated"]:
            diffs.append(f"ts={b['ts']}: truncated differs "
                          f"BASE={b['truncated']} INST={n['truncated']}")

        bd = b["decodes"]
        nd = n["decodes"]
        if len(bd) != len(nd):
            diffs.append(f"ts={b['ts']}: decode count differs "
                          f"BASE={len(bd)} INST={len(nd)}")
        else:
            for j in range(len(bd)):
                x, y = bd[j], nd[j]
                n_decodes_compared += 1
                if (x["f"], x["dt"], x["snr"], x["m"]) != (y["f"], y["dt"], y["snr"], y["m"]):
                    # NFR-021: "m" is real off-air message text. Report which
                    # NON-message fields differ (f/dt/snr are not personal
                    # data) and whether "m" itself is one of the differing
                    # fields, but never print message text (standing rule --
                    # this class has fired three times; do not make it four).
                    field_diffs = [f for f in ("f", "dt", "snr")
                                   if x[f] != y[f]]
                    if x["m"] != y["m"]:
                        field_diffs.append("m(withheld)")
                    diffs.append(f"ts={b['ts']} decode[{j}]: fields differing="
                                 f"{field_diffs} BASE(f/dt/snr)="
                                 f"{x['f'],x['dt'],x['snr']} "
                                 f"INST(f/dt/snr)={y['f'],y['dt'],y['snr']}")

        # Reported, never gated (Sec.A5 table).
        if b.get("cand") != n.get("cand") or b.get("pass") != n.get("pass"):
            if bd == nd:  # decodes[] identical but cand/pass moved -- worth a look
                cand_pass_moves.append(b["ts"])

    print(f"ROW 0b means 2: {n_compared} cycles compared, "
          f"{n_decodes_compared} decode records compared")
    if cand_pass_moves:
        print(f"REPORT (not gated): cand[]/pass[] moved with decodes[] unchanged "
              f"on {len(cand_pass_moves)} cycle(s): {cand_pass_moves[:20]}"
              f"{'...' if len(cand_pass_moves) > 20 else ''}")

    if diffs:
        print(f"ROW 0b means 2: FAIL -- {len(diffs)} difference(s)", file=sys.stderr)
        for d in diffs[:50]:
            print(f"  {d}", file=sys.stderr)
        if len(diffs) > 50:
            print(f"  ... and {len(diffs) - 50} more", file=sys.stderr)
        return 1

    print("ROW 0b means 2: PASS -- identical on every gated field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
