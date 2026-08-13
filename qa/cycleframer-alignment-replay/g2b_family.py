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
                      three verdicts, a verdict file missing required keys /
                      unreadable, two verdicts share an f_min, the three
                      verdicts do not share one band/f_max/wav_dir (E1), the
                      three verdicts' baseline dll_sha256 or manifest_sha256
                      disagree (E2), or any verdict reads ROW_0/ROW_0d (a
                      precondition failure or a gate defect is not evidence).

Deliberate asymmetry (D2, explicit): this instrument can only ever CLOSE the
family. It never ships anything, and it must never print a recommendation
among eligible (ROW_1) rungs -- the choice among eligible rungs is reserved
to the Captain (pre-reg §4/§8), unchanged by anything here. DO NOT CLOSE is
not a ranking; it is a refusal to close, full stop.

E1/E2 (Architect, 2026-08-12 21:43Z, sent early and out of band ahead of the
fifth review proper, `2026-08-12-2143-architect-to-qa-g2b-review-5-early-
candidates.md`, both inside this file):

  E1  Previously this file enforced exactly one identity condition (no
      duplicate f_min); it read `band`/`f_max` off each verdict, printed
      both, and tested neither, and could not see the corpus at all, since
      the verdict did not carry it. The pre-reg's own §5 runs three rungs x
      three bands, and 20m alone has two corpora -- so three ROW_3 verdicts
      drawn from three DIFFERENT bands, or two DIFFERENT 20m corpora, would
      have printed CLOSE, closing the passband family on a ladder that was
      never run. BLOCKING for the family adjudication (not for a rung's own
      run -- a rung is read on its own row regardless). Fixed: REFUSE unless
      all three verdicts share one band, one f_max and one wav_dir, naming
      the field that differs and the per-rung values.
  E2  SERIOUS. The verdict previously carried no `dll_sha256` and no
      manifest digest, so this file could not tell whether the three rungs
      ran against the same binaries -- standing memory ("pin the SHA256,
      never infer a leg's binary from a label") violated one file downstream
      of where the gate itself already honours it (A7/B1). Fixed: REFUSE if
      the three rungs' baseline dll_sha256 are not identical, or if their
      manifest_sha256 (the manifest FILE's own digest, not the SHAs it
      contains) differ -- naming both values either way. Widened SHAs are
      DELIBERATELY not checked for equality here: they are expected to
      differ across rungs, and the per-rung manifest binding already covers
      them.
  E3  MINOR in code, larger as a process point: this file returned 0 on
      CLOSE, on DO NOT CLOSE, and on all refusal paths alike -- the
      identical defect D2 raised against g2b_gate.py's own exit code (every
      path, including ROW_0, returned 0), reappearing inside the very
      instrument built to fix it, the fourth consecutive round in which a
      correction inherited the shape of what it corrected. Fixed here:
      0 = CLOSE, 1 = DO NOT CLOSE, 2 = REFUSE. g2b_gate.py's own exit code is
      deliberately UNCHANGED -- its machine-readable channel is
      --emit-verdict, settled by D2; this is the family adjudicator's own,
      separate output contract, not a pre-registered check (HK-021(k) does
      not apply to it).

The new E1/E2 refusal conditions run AFTER the duplicate-f_min and
ROW_0/ROW_0d checks, deliberately: by the time they run, every remaining
verdict is a real read (ROW_1/2/3), so `wav_dir` is guaranteed to be a real
string rather than the null it may legitimately be on an unconfirmed ROW_0.

Usage:
    python g2b_family.py --verdict verdict_f180.json \
                          --verdict verdict_f140.json \
                          --verdict verdict_f100.json
Exit code: 0 = CLOSE, 1 = DO NOT CLOSE, 2 = REFUSE (E3).
"""
from __future__ import annotations

import argparse
import json
import sys

REQUIRED_LADDER_SIZE = 3
REFUSAL_ROWS = {"ROW_0", "ROW_0d"}
EXIT_CLOSE, EXIT_DO_NOT_CLOSE, EXIT_REFUSE = 0, 1, 2

# E1/E2 fix: required verdict keys extended. band/f_min/f_max/row were the
# only keys this file previously depended on; wav_dir, dll_sha256 and
# burned_corpus are, per build_verdict()'s own docstring in g2b_gate.py,
# ALWAYS present (like `bars`) regardless of row -- a verdict missing any of
# them predates E1/E2 and cannot be adjudicated against those conditions.
# manifest_sha256 is included too (E2); it can hold a None VALUE (the
# manifest file did not exist when the gate ran) but the KEY itself is always
# written.
REQUIRED_VERDICT_KEYS = ("band", "f_min", "f_max", "row", "wav_dir",
                          "dll_sha256", "manifest_sha256", "burned_corpus")


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
        return EXIT_REFUSE

    verdicts = []
    for p in paths:
        try:
            v = load_verdict(p)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"\n  REFUSE -- could not read verdict {p!r}: {exc}. A "
                  "family verdict cannot be built from a missing or "
                  "malformed verdict file.")
            return EXIT_REFUSE
        missing = [k for k in REQUIRED_VERDICT_KEYS if k not in v]
        if missing:
            print(f"\n  REFUSE -- verdict {p!r} is missing "
                  f"{', '.join(missing)} -- not a g2b_gate.py --emit-verdict "
                  "output, or from a revision that predates the field "
                  "(D2, or E1/E2 for wav_dir/dll_sha256/manifest_sha256/"
                  "burned_corpus).")
            return EXIT_REFUSE
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
        return EXIT_REFUSE

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
        return EXIT_REFUSE

    # ── Refusal condition 4 (E1): all three verdicts must share one band,
    # one f_max and one wav_dir. A ladder is three rungs of ONE experiment;
    # three rungs of three bands, or two different corpora inside one band,
    # is not a family, even if all three happen to read the same row. Every
    # verdict reaching this point is a real read (ROW_1/2/3, condition 3
    # above already excluded ROW_0/ROW_0d), so wav_dir is guaranteed to be a
    # real string here, never the null it may legitimately be on an
    # unconfirmed ROW_0.
    for field in ("band", "f_max", "wav_dir"):
        values = {v["f_min"]: v[field] for _, v in verdicts}
        if len(set(values.values())) != 1:
            named = "; ".join(f"f_min={f_min} {field}={val!r}"
                               for f_min, val in sorted(values.items()))
            print(f"\n  REFUSE -- the three rungs do not share one {field} "
                  f"-- {named}. A ladder is three rungs of ONE experiment; "
                  "three rungs of three experiments is not a family (E1).")
            return EXIT_REFUSE

    # ── Refusal condition 5 (E2): all three verdicts must agree on the
    # BASELINE dll_sha256 and on manifest_sha256 (the manifest FILE's own
    # digest, not the SHAs it contains). Without this, nothing detects three
    # rungs quietly comparing against different [200,3000) reference builds,
    # or a manifest edited between rungs -- the manifest is a mutable file
    # and "never edit an existing entry" is prose with no mechanism until
    # this check exists. Widened SHAs are DELIBERATELY not compared: they
    # are expected to differ across rungs, and the per-rung manifest binding
    # (A7/B1, enforced by g2b_gate.py itself) already covers them.
    baseline_shas = {v["f_min"]: v["dll_sha256"]["baseline"] for _, v in verdicts}
    if len(set(baseline_shas.values())) != 1:
        named = "; ".join(f"f_min={f_min} baseline_sha={sha[:16]}..."
                           for f_min, sha in sorted(baseline_shas.items()))
        print(f"\n  REFUSE -- the three rungs' BASELINE binaries differ -- "
              f"{named}. Three rungs comparing against different "
              "[200,3000) reference builds cannot be combined into one "
              "family verdict (E2).")
        return EXIT_REFUSE
    manifest_shas = {v["f_min"]: v["manifest_sha256"] for _, v in verdicts}
    if len(set(manifest_shas.values())) != 1:
        named = "; ".join(f"f_min={f_min} manifest_sha256="
                           f"{(sha[:16] + '...') if sha else 'FILE NOT FOUND'}"
                           for f_min, sha in sorted(manifest_shas.items()))
        print(f"\n  REFUSE -- the three rungs read DIFFERENT manifest file "
              f"contents -- {named}. The manifest is mutable; a digest "
              "mismatch means it was edited between rungs, and nothing "
              "downstream can trust which entries applied to which rung "
              "(E2).")
        return EXIT_REFUSE

    # ── The adjudication itself. Every remaining verdict reads ROW_1, ROW_2,
    # or ROW_3 -- the only three possibilities left after the refusal checks
    # above, since ROW_0/ROW_0d were already excluded.
    non_row3 = sorted(((v["f_min"], v["row"]) for _, v in verdicts))
    non_row3 = [(f_min, row) for f_min, row in non_row3 if row != "ROW_3"]

    if not non_row3:
        print(f"\n  CLOSE -- all {REQUIRED_LADDER_SIZE} rungs read ROW_3 "
              f"({sorted(f_mins)}). Per the repaired combination rule (C5): "
              "the passband family closes.")
        return EXIT_CLOSE
    named = "; ".join(f"f_min={f_min} read {row}" for f_min, row in non_row3)
    print(f"\n  DO NOT CLOSE -- {named}. The family does not close "
          "while any rung reads ROW_1 or ROW_2. This is not a ranking "
          "among rungs and licenses no choice among them -- the "
          "Captain's choice among eligible (ROW_1) rungs, if any, is "
          "unchanged by this adjudication.")
    return EXIT_DO_NOT_CLOSE


if __name__ == "__main__":
    sys.exit(main())
