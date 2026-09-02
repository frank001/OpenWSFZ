#!/usr/bin/env python3
"""Architect read-only probe behind the 2026-09-02 AC-2 recommendation.

Reproduces every load-bearing number in
`2026-09-02-1340-architect-recommendation-f001-h12-ac2-void-by-construction.md`.

READ-ONLY. Consumes replay artefacts that already exist on disk; writes nothing,
runs no decoder, touches no `src/`. This is NOT part of QA's `g4_*` harness and must
not be confused with it -- it does not produce an AC verdict, it characterises the
population behind AC-2's gap.

WHY IT EXISTS
-------------
QA's AC-1..AC-4 replay (`2026-09-01-2203-qa-to-architect-...md`) attributed the AC-2
gap (847 ambiguous vs 250 differing lines) to the discarded-CQ-slot case by
SUBTRACTION: "597 (70.5%)". A residual assigned wholesale to one named mechanism
hides any second cause (HK-026-adjacent). This probe replaces the subtraction with a
directly measured population and a falsifiable containment check.

THE MECHANISM UNDER TEST (read from source, `native/ft8_lib_vendor/ft8/message.c`)
---------------------------------------------------------------------------------
  :256-261  ENCODER: when icq != 0 (a CQ), it hard-wires  iflip = 0;  n12 = 0;
            The 12-bit field is PADDING -- not a hash of any callsign.
  :431      DECODER: looks n12 up unconditionally. Grep-verified: the ONLY
            FTX_CALLSIGN_HASH_12_BITS call site in the vendored tree.
  :434-451  call_1 = iflip ? call_decoded : call_3;  and when icq == 1,
            call_to is overwritten with "CQ" -- so call_3 (the lookup result) is
            DISCARDED exactly when (icq == 1 && iflip == 0).

  => Every nonstandard CQ performs one lookup of slot 0. Once slot 0 holds >=2
     entries those lookups are counted ambiguous, yet can never alter a rendered
     line. AC-2's equality is therefore UNSATISFIABLE BY CONSTRUCTION for a correct
     implementation, on any corpus containing nonstandard CQs.

CHECKS
------
  C1  Shape census of all differing lines. Expect: every one is a single
      <HASH> -> <...> token swap, numeric fields untouched (AC-3, re-derived
      independently of QA's evaluator with a separate bracket-aware tokenizer).
  C2  Measure the n12=0 population: Type-4 nonstd CQ renders as exactly
      "CQ" + one NONSTANDARD call (2 bracket-aware tokens, extra empty), whereas a
      standard Type-1 CQ renders "CQ CALL GRID" (3-4 tokens).
      CONTAINMENT TEST -- could have failed: residual (847-250=597) must be <= that
      population. If it is not, the padding mechanism cannot explain the gap.
  C3  Contamination guard for C2: count "CQ" + STANDARD call with no grid, which
      would inflate C2's population. Expect 0.
  C4  Base-rate guard (HK-021(u)): fraction of cycles containing any CQ decode.
      If ~100%, then "the gap coincides with CQ traffic" is vacuous and must not be
      cited as corroboration.

NFR-021: prints COUNTS AND TOKEN CATEGORIES ONLY. No callsign or message text ever
reaches stdout. Input artefacts live under `artefacts/` (blanket-gitignored).
"""
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.join("artefacts", "2026-08-30-sup-b-row0-amend2", "s17m_inst_run1.json")
CAND = os.path.join("artefacts", "2026-09-01-f001-h12-suppression-replay",
                    "s17m_candidate_20260049.json")

# A standard FT8 basecall: 1-2 char prefix, digit, 1-3 char suffix.
STD_CALL = re.compile(r"^[A-Z0-9]{1,2}[0-9][A-Z]{1,3}$", re.I)
GRID = re.compile(r"^[A-R]{2}[0-9]{2}$", re.I)
REPORT = re.compile(r"^[+-][0-9]{2}$")


def load(path):
    if not os.path.exists(path):
        sys.stderr.write("MISSING ARTEFACT: %s\n" % path)
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def bracket_aware_tokens(s):
    """Split on spaces, but keep a <...> span as ONE token even with inner spaces.

    The native hash table can store a callsign containing an embedded space (a
    pre-existing padding/storage quirk present in BASE independently of this
    change). Naive str.split() shreds such a field into two tokens and manufactures
    false 'token count changed' scope violations -- the exact false positive QA hit
    and fixed in g4_ac_evaluate.py. Re-implemented here deliberately, so this probe
    corroborates AC-3 rather than inheriting it.
    """
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == " ":
            i += 1
            continue
        if s[i] == "<":
            j = s.find(">", i)
            j = n - 1 if j == -1 else j
            out.append(s[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and s[j] != " ":
                j += 1
            out.append(s[i:j])
            i = j
    return out


def categorise(tok):
    up = tok.upper()
    if up == "CQ":
        return "CQ"
    if up == "DX":
        return "DX"
    if tok == "<...>":
        return "<...>"
    if tok.startswith("<") and tok.endswith(">"):
        return "<HASH>"
    if up in ("RR73", "RRR", "73"):
        return "EXTRA"
    if GRID.match(tok):
        return "GRID"
    if REPORT.match(tok):
        return "RPT"
    return "CALL"


def shape(msg):
    return " ".join(categorise(t) for t in bracket_aware_tokens(msg.strip()))


def is_cq(msg):
    return msg.strip().upper().startswith("CQ ")


def main():
    base, cand = load(BASE), load(CAND)
    bmap = {e["ts"]: e for e in base["per_file"]}

    amb_final = cand["h12_ambiguous_count_final"]

    shapes = Counter()
    n_diff = 0
    numeric_violations = 0
    cycles_total = cycles_with_cq = 0

    for ce in cand["per_file"]:
        be = bmap.get(ce["ts"])
        if be is None:
            continue
        cycles_total += 1
        bl, cl = be["decodes"], ce["decodes"]
        if any(is_cq(d["m"]) for d in cl):
            cycles_with_cq += 1
        if len(bl) != len(cl):
            continue
        for x, y in zip(bl, cl):
            if x["m"] == y["m"]:
                continue
            n_diff += 1
            shapes[(shape(x["m"]), shape(y["m"]))] += 1
            # C1: numeric fields must be byte-identical across the swap
            if (x["f"], x["dt"], x["snr"]) != (y["f"], y["dt"], y["snr"]):
                numeric_violations += 1

    # C2/C3: measure the n12=0 population off the BASE leg
    pop_nonstd_cq = pop_std_cq_nogrid = pop_cq_hash = 0
    for e in base["per_file"]:
        for d in e["decodes"]:
            m = d["m"].strip()
            if not is_cq(m):
                continue
            toks = bracket_aware_tokens(m)
            if len(toks) != 2:
                continue
            c = toks[1]
            if c.startswith("<") and c.endswith(">"):
                pop_cq_hash += 1          # icq=1, iflip=1 -> hash IS rendered
            elif STD_CALL.match(c):
                pop_std_cq_nogrid += 1    # contamination guard
            else:
                pop_nonstd_cq += 1        # icq=1, iflip=0 -> n12=0, discarded

    residual = amb_final - n_diff

    print("=" * 74)
    print("C1  DIFFERING-LINE SHAPE CENSUS  (AC-3 re-derived independently)")
    print("=" * 74)
    print("  differing lines                  = %d" % n_diff)
    print("  numeric-field violations (f/dt/snr) = %d   [expect 0]" % numeric_violations)
    for (bs, cs), n in shapes.most_common():
        print("    %-32s -> %-32s x%d" % (bs, cs, n))
    all_single_swap = all(
        bs.count("<HASH>") - cs.count("<HASH>") == 1 and cs.count("<...>") - bs.count("<...>") == 1
        for bs, cs in shapes)
    print("  every diff is exactly one <HASH> -> <...> swap: %s" % all_single_swap)

    print("")
    print("=" * 74)
    print("C2  n12=0 POPULATION  (measured, not subtracted)")
    print("=" * 74)
    print("  ambiguous_count_final            = %d" % amb_final)
    print("  differing lines (rendered)       = %d" % n_diff)
    print("  residual to explain              = %d" % residual)
    print("  nonstd-CQ decodes (icq=1,iflip=0)= %d   <- each does ONE n12=0 lookup" % pop_nonstd_cq)
    print("  'CQ <HASH>' (icq=1, iflip=1)     = %d   <- hash IS rendered; not padding" % pop_cq_hash)
    contained = residual <= pop_nonstd_cq
    print("")
    print("  CONTAINMENT TEST  residual <= population : %s  (%d <= %d)"
          % ("PASS" if contained else "FAIL", residual, pop_nonstd_cq))
    if pop_nonstd_cq:
        print("  implied slot-0 ambiguity rate    = %.1f%%" % (100.0 * residual / pop_nonstd_cq))
    print("  NOTE: this BOUNDS and rate-checks the residual. It does NOT measure which")
    print("        individual lookups were slot-0 -- only a padding counter would.")

    print("")
    print("=" * 74)
    print("C3  CONTAMINATION GUARD")
    print("=" * 74)
    print("  'CQ' + standard call, no grid    = %d   [expect 0; >0 inflates C2]" % pop_std_cq_nogrid)

    print("")
    print("=" * 74)
    print("C4  BASE-RATE GUARD (HK-021(u))")
    print("=" * 74)
    print("  cycles containing a CQ decode    = %d / %d  (%.1f%%)"
          % (cycles_with_cq, cycles_total, 100.0 * cycles_with_cq / max(cycles_total, 1)))
    print("  => at this base rate, 'the gap coincides with CQ traffic' is VACUOUS")
    print("     and must not be cited as corroboration.")

    return 0 if (contained and numeric_violations == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
