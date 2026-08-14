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
                      verdicts do not share one band/f_max/wav_dir/
                      burned_corpus (E1/J5), the three verdicts' baseline
                      dll_sha256 or manifest_sha256 disagree (E2), any
                      verdict reads ROW_0/ROW_0d/ROW_INDETERMINATE (a
                      precondition failure, a gate defect, or an
                      underpowered read is not evidence -- J1), a rung's
                      bars do not match the pre-registered ladder (F7/J2),
                      the three verdicts do not share one window/
                      start_cycle (F8, absorbs J3), or the three verdicts
                      were not read by the same evaluator (F9, gate_sha256).

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

REVISION 6 (fifth Architect review, `2026-08-13-1503-architect-to-qa-g2b-
review-5.md`, plus the Captain's rulings on it) -- J2, J5, J6, F7, F8, F9:

  J2/F7  Nothing previously checked that the bars a rung was INVOKED with
      were the bars PRE-REGISTERED for that rung (§4.2 of the pre-reg:
      180 -> 0.35%, 140 -> 1.00%, 100 -> 1.65%, plus the fixed g_high/net/
      gross floors). Measured: inflating all four bars on every rung
      converted a ladder where every rung read ROW_1 into one where every
      rung read ROW_3 and CLOSEd -- one mistyped argument, repeated three
      times, and no instrument in the chain said a word. This is E1's shape
      a second time: the verdict carries the value, the adjudicator ignores
      it. Fixed: PRE_REGISTERED_BARS (below) is a constant in THIS file
      (deliberately not moved into the gate as constants -- the mechanism
      belongs at the adjudication layer, where the pre-registration is what
      is being enforced); F7 refuses if any rung's `bars` disagree with it.
      `bars` joins REQUIRED_VERDICT_KEYS.
  J5  `burned_corpus` joins F5's identity set -- three rungs sharing one
      `wav_dir` could previously still disagree on whether that corpus was
      declared burned (the exact conjunction J4 closes at the source, in
      g2b_gate.py, by making the burned directory a hard-coded constant);
      this closes it again at the adjudication layer.
  J6  F6's two null-handling blocks were asymmetric: the manifest-digest
      block formatted a None value as `'FILE NOT FOUND'`; the adjacent
      baseline-SHA block did not, and `sha[:16]` would raise on a None
      baseline SHA. Low reachability (the gate itself dies earlier on a
      None SHA) -- fixed by making the two blocks consistent via one
      shared `_fmt_sha()` helper, no new machinery.
  F8  (absorbs J3) `window`/`start_cycle` must be identical across all
      three rungs. F5 already binds the three rungs to one `wav_dir`, but
      three rungs may share one directory and still run on DIFFERENT
      SLICES of it (different windows, or the same window at different
      start cycles) -- F5 alone cannot see that.
  F9  All three rungs' `gate_sha256` (g2b_gate.py's own SHA256, carried in
      the verdict since REVISION 6 of that file) must be identical. Three
      rungs adjudicated together must have been read by the SAME
      evaluator -- E2's own logic ("pin the SHA256, never infer identity
      from a label") applied to the instrument rather than the DLL.

Usage:
    python g2b_family.py --verdict verdict_f180.json \
                          --verdict verdict_f140.json \
                          --verdict verdict_f100.json
Exit code: 0 = CLOSE, 1 = DO NOT CLOSE, 2 = REFUSE (E3).
"""
from __future__ import annotations

import argparse
import json
import math
import sys

REQUIRED_LADDER_SIZE = 3
# J1 (g2b_gate.py, REVISION 6): ROW_INDETERMINATE is a NO-READ row, exactly
# like ROW_0/ROW_0d -- an underpowered rung is not evidence of absence, and
# must be refused on identically, never silently read as ROW_3.
REFUSAL_ROWS = {"ROW_0", "ROW_0d", "ROW_INDETERMINATE"}
EXIT_CLOSE, EXIT_DO_NOT_CLOSE, EXIT_REFUSE = 0, 1, 2

# J2/F7: the SAME per-rung bar table §4.2 of the pre-registration commits to
# BEFORE any rung is run -- g_new_min_rate varies by rung (width-
# proportional, §4.2); g_high_min_rate/churn_net_min_rate/
# churn_gross_max_rate are fixed across the ladder (§4.2a/§4.2). This is the
# only place in the whole chain that checks the bar SUPPLIED against the bar
# PRE-REGISTERED -- g2b_gate.py deliberately keeps the bars CLI-supplied
# (A5), so the enforcement lives here, at the adjudication layer, not there.
PRE_REGISTERED_BARS = {
    180: {"g_new_min_rate": 0.0035, "g_high_min_rate": 0.0050,
          "churn_net_min_rate": -0.0025, "churn_gross_max_rate": 0.0200},
    140: {"g_new_min_rate": 0.0100, "g_high_min_rate": 0.0050,
          "churn_net_min_rate": -0.0025, "churn_gross_max_rate": 0.0200},
    100: {"g_new_min_rate": 0.0165, "g_high_min_rate": 0.0050,
          "churn_net_min_rate": -0.0025, "churn_gross_max_rate": 0.0200},
}
BAR_TOLERANCE = 1e-9  # exact-value comparison, allowing only float round-trip noise

# E1/E2/F7/F8/F9 fix: required verdict keys extended. band/f_min/f_max/row
# were the only keys this file previously depended on; wav_dir, dll_sha256,
# burned_corpus, bars, window, start_cycle and gate_sha256 are, per
# build_verdict()'s own docstring in g2b_gate.py, ALWAYS present (like
# `bars`) regardless of row -- a verdict missing any of them predates the
# revision that added it and cannot be adjudicated against that condition.
# manifest_sha256 is included too (E2); it can hold a None VALUE (the
# manifest file did not exist when the gate ran) but the KEY itself is
# always written. `rows`/`n_cycles`/`d_base` are deliberately NOT required
# here -- this file never reads them; they exist for g2b_gate.py's own
# --verify-verdict self-check, a separate contract.
REQUIRED_VERDICT_KEYS = ("band", "f_min", "f_max", "row", "wav_dir",
                          "dll_sha256", "manifest_sha256", "burned_corpus",
                          "bars", "window", "start_cycle", "gate_sha256")


def _fmt_sha(sha):
    """J6 fix: ONE null-safe SHA formatter, shared by every block that prints
    a SHA that may legitimately be None (a baseline dll_sha256 the gate
    could not read, or a manifest_sha256 for a manifest file that did not
    exist when the gate ran). Previously the manifest-digest block handled
    None explicitly ('FILE NOT FOUND') while the adjacent baseline-SHA block
    did not, and `sha[:16]` would have raised TypeError on a None baseline
    SHA -- two adjacent blocks, two different null disciplines, for no
    reason tied to what the two values mean."""
    return f"{sha[:16]}..." if sha else "MISSING"


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

    # ── Refusal condition 3: no verdict may read ROW_0/ROW_0d/
    # ROW_INDETERMINATE. Those rows mean "no read happened" (a precondition
    # failed), "gate defect", or "underpowered -- not evidence either way"
    # (J1) -- none is evidence about whether that rung's mechanism
    # delivered, and treating any as silently equivalent to ROW_3 would let
    # a precondition failure, a bug, or a lack of power CLOSE the family.
    refused = [(p, v) for p, v in verdicts if v["row"] in REFUSAL_ROWS]
    if refused:
        named = "; ".join(f"{p} (f_min={v['f_min']}, {v['row']})"
                           for p, v in refused)
        print(f"\n  REFUSE -- {len(refused)} verdict(s) read "
              f"ROW_0/ROW_0d/ROW_INDETERMINATE, which is NO READ, not "
              f"evidence: {named}. Fix the precondition (or the gate "
              "defect), or run more cycles (J1), and re-run that rung "
              "before asking this instrument to adjudicate the family.")
        return EXIT_REFUSE

    # ── Refusal condition 4 (E1, J5 extends it): all three verdicts must
    # share one band, one f_max, one wav_dir and one burned_corpus
    # declaration. A ladder is three rungs of ONE experiment; three rungs of
    # three bands, or two different corpora inside one band, is not a
    # family, even if all three happen to read the same row -- and (J5)
    # three rungs sharing one wav_dir could still disagree on whether that
    # corpus was DECLARED burned, the exact conjunction J4 closes at the
    # source in g2b_gate.py. Every verdict reaching this point is a real
    # read (ROW_1/2/3, condition 3 above already excluded ROW_0/ROW_0d/
    # ROW_INDETERMINATE), so wav_dir is guaranteed to be a real string here,
    # never the null it may legitimately be on an unconfirmed ROW_0.
    for field in ("band", "f_max", "wav_dir", "burned_corpus"):
        values = {v["f_min"]: v[field] for _, v in verdicts}
        if len(set(values.values())) != 1:
            named = "; ".join(f"f_min={f_min} {field}={val!r}"
                               for f_min, val in sorted(values.items()))
            print(f"\n  REFUSE -- the three rungs do not share one {field} "
                  f"-- {named}. A ladder is three rungs of ONE experiment; "
                  "three rungs of three experiments is not a family "
                  "(E1/J5).")
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
        # J6 fix: _fmt_sha() -- see that block's manifest_shas neighbour for
        # why this needs to be null-safe identically, even though a None
        # baseline SHA should not reach here in practice (the gate itself
        # dies earlier on one).
        named = "; ".join(f"f_min={f_min} baseline_sha={_fmt_sha(sha)}"
                           for f_min, sha in sorted(baseline_shas.items()))
        print(f"\n  REFUSE -- the three rungs' BASELINE binaries differ -- "
              f"{named}. Three rungs comparing against different "
              "[200,3000) reference builds cannot be combined into one "
              "family verdict (E2).")
        return EXIT_REFUSE
    manifest_shas = {v["f_min"]: v["manifest_sha256"] for _, v in verdicts}
    if len(set(manifest_shas.values())) != 1:
        named = "; ".join(f"f_min={f_min} manifest_sha256={_fmt_sha(sha)}"
                           for f_min, sha in sorted(manifest_shas.items()))
        print(f"\n  REFUSE -- the three rungs read DIFFERENT manifest file "
              f"contents -- {named}. The manifest is mutable; a digest "
              "mismatch means it was edited between rungs, and nothing "
              "downstream can trust which entries applied to which rung "
              "(E2).")
        return EXIT_REFUSE

    # ── Refusal condition 6 (J2/F7): each rung's `bars` must equal the
    # PRE-REGISTERED_BARS entry for its own f_min. g2b_gate.py deliberately
    # keeps bars CLI-supplied (A5); this is the ONLY place that checks the
    # bar SUPPLIED against the bar PRE-REGISTERED. Float comparison uses
    # BAR_TOLERANCE, not `==`, since these values round-trip through
    # argparse's `type=float` and JSON.
    for _, v in verdicts:
        expected = PRE_REGISTERED_BARS.get(v["f_min"])
        if expected is None:
            print(f"\n  REFUSE -- f_min={v['f_min']} is not one of the "
                  f"pre-registered ladder rungs {sorted(PRE_REGISTERED_BARS)} "
                  "-- its bars cannot be checked against anything (F7).")
            return EXIT_REFUSE
        mismatches = [
            f"{key}: supplied {v['bars'][key]!r}, pre-registered {expected_val!r}"
            for key, expected_val in expected.items()
            if not math.isclose(v["bars"][key], expected_val,
                                 rel_tol=0, abs_tol=BAR_TOLERANCE)]
        if mismatches:
            print(f"\n  REFUSE -- f_min={v['f_min']}'s bars do not match the "
                  f"pre-registered values -- {'; '.join(mismatches)}. "
                  "Enforcing the bar APPLIED is not the same as enforcing "
                  "the bar PRE-REGISTERED (F7/J2).")
            return EXIT_REFUSE

    # ── Refusal condition 7 (F8, absorbs J3): all three verdicts must share
    # one `window` and one `start_cycle`. F5/condition 4 above already binds
    # the three rungs to one wav_dir, but three rungs may share one
    # directory and still run on DIFFERENT SLICES of it -- F5 alone cannot
    # see that; this is the field-adding half of what J3 originally raised.
    for field in ("window", "start_cycle"):
        values = {v["f_min"]: (tuple(v[field]) if isinstance(v[field], list)
                                else v[field])
                  for _, v in verdicts}
        if len(set(values.values())) != 1:
            named = "; ".join(f"f_min={f_min} {field}={val!r}"
                               for f_min, val in sorted(values.items()))
            print(f"\n  REFUSE -- the three rungs do not share one {field} "
                  f"-- {named}. Three rungs may share one wav_dir yet run "
                  "on different slices of it; a family verdict requires "
                  "one slice, not merely one directory (F8/J3).")
            return EXIT_REFUSE

    # ── Refusal condition 8 (F9): all three verdicts' gate_sha256 must be
    # identical. Three rungs adjudicated together must have been read by the
    # SAME evaluator -- E2's own logic ("pin the SHA256, never infer
    # identity from a label") applied to the instrument itself, not the DLL.
    gate_shas = {v["f_min"]: v["gate_sha256"] for _, v in verdicts}
    if len(set(gate_shas.values())) != 1:
        named = "; ".join(f"f_min={f_min} gate_sha256={_fmt_sha(sha)}"
                           for f_min, sha in sorted(gate_shas.items()))
        print(f"\n  REFUSE -- the three rungs were read by DIFFERENT "
              f"evaluators (g2b_gate.py changed between rungs) -- {named}. "
              "Three rungs adjudicated together must have been read by the "
              "SAME instrument (F9).")
        return EXIT_REFUSE

    # ── The adjudication itself. Every remaining verdict reads ROW_1, ROW_2,
    # or ROW_3 -- the only three possibilities left after the refusal checks
    # above, since ROW_0/ROW_0d/ROW_INDETERMINATE were already excluded.
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
