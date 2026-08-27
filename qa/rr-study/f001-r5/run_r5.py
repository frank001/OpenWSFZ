#!/usr/bin/env python3
"""F-001 R5 -- own-callsign direct hash match on the answerer path.

Spec: qa/rr-study/2026-08-27-1531-architect-to-qa-spec-f001-r5-own-callsign-direct-hash-match.md

Pure offline re-analysis of the two ALL.TXT logs already on disk -- no capture,
no replay, no rebuild, no src/ or native/ edit (Sec.2). This arm can measure
only the COST side of route 5 (Sec.0.3): both corpus logs have zero Tx lines,
so the benefit side (calls to us that would stop being missed) has structurally
zero exposure and is NOT measured here, in either direction.

Two disclosed methodological choices are QA's own, not shipped code -- see
common_r5.py's module docstring and Sec.5/G1, Sec.5/G3 below for the full
account: (1) G1a is computed BOTH under the spec's literal "4,343 single-bracket
decodes" wording and under a hashed-dest-only (2,933) restriction that matches
Sec.1 outcome #2's own wording; (2) G3's UNKNOWN pairs (theirs did not resolve
the slot, so the TRUE 12-bit target is unobservable in either log) are bounded
adversarially, per-decode, using the largest occupancy bucket among the 11,233
hypothetical own-calls as the MAX-pass assignment and zero as the MIN-pass
assignment.

NFR-021: real callsign strings live in memory only. result.json / run.log /
the report carry counts and sha256[:6]-redacted CS-xxxxxx tokens
(common_r5.redact) only, with the ONE pre-registered exception: the literal
string "PD2FZ" (OWNCALL, Sec.0.2) may appear -- no other real callsign may.

Usage:
    python run_r5.py --out-dir <dir>          # normal run, writes result.json/run.log
    python run_r5.py --emit-core-json         # ROW 0f worker mode: prints the
                                               # deterministic result dict as one
                                               # line of sort_keys JSON, nothing else
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_r5 as C   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Two arbitrary, fixed, DIFFERENT seeds for ROW 0f's out-of-process check.
HASHSEED_A = "24601"
HASHSEED_B = "271828"

# NFR-021 scan pattern: a real off-air callsign shape, uppercase tokens only.
# CS-xxxxxx redacted tokens are lowercase-hex after the prefix and never match.
_CALLSIGN_SHAPE_RE = __import__("re").compile(r"^[A-Z]{1,2}[0-9][A-Z]{1,4}(?:/[A-Z0-9]+)?$")


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=C.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


def nfr021_scan_text(text: str):
    """Returns the sorted set of callsign-shaped tokens found, EXCLUDING the
    single pre-registered OWNCALL exception."""
    hits = set()
    for tok in text.split():
        tok = tok.strip('",{}[]:')
        if tok == C.OWNCALL:
            continue
        if _CALLSIGN_SHAPE_RE.fullmatch(tok):
            hits.add(tok)
    return hits


# =============================================================================
# Core analysis -- deterministic given the on-disk ALL.TXT files. Called both
# by the normal run and by --emit-core-json (ROW 0f's out-of-process worker).
# =============================================================================
def compute_all(log):
    void_rows = []

    def void(row, reason):
        void_rows.append((row, reason))
        log("  -> VOID at ROW %s: %s" % (row, reason))

    log("Loading ALL.TXT logs (no rebuild, no replay, no capture)...")
    ours_rows = C.gc.parse_all_txt(C.OURS_ALL_TXT)
    theirs_rows = C.gc.parse_all_txt(C.THEIRS_ALL_TXT)

    # ---------------- ROW 0a: input identity --------------------------------
    log("-" * 78); log("ROW 0a -- input identity")
    ours_sha = C.sha256_of(C.OURS_ALL_TXT)
    theirs_sha = C.sha256_of(C.THEIRS_ALL_TXT)
    ours_rx, ours_tx = C.rx_tx_counts(C.OURS_ALL_TXT)
    theirs_rx, theirs_tx = C.rx_tx_counts(C.THEIRS_ALL_TXT)
    log("  ours   sha256=%s Rx=%d Tx=%d (expect Rx=%d Tx=%d)"
        % (ours_sha, ours_rx, ours_tx, C.EXPECTED_OURS_RX, C.EXPECTED_OURS_TX))
    log("  theirs sha256=%s Rx=%d Tx=%d (expect Rx=%d Tx=%d)"
        % (theirs_sha, theirs_rx, theirs_tx, C.EXPECTED_THEIRS_RX, C.EXPECTED_THEIRS_TX))
    ok0a = (ours_rx == C.EXPECTED_OURS_RX and ours_tx == C.EXPECTED_OURS_TX
            and theirs_rx == C.EXPECTED_THEIRS_RX and theirs_tx == C.EXPECTED_THEIRS_TX)
    log("  ROW 0a: %s" % ("PASS" if ok0a else "FAIL"))
    if not ok0a:
        void("0a", "Rx/Tx line counts do not match the pinned spec inputs, or a Tx line exists "
                   "(the zero-exposure premise of Sec.0.2 would be false)")
        return {"row0": {"0a": "VOID"},
                "row0a_detail": {"ours_sha256": ours_sha, "theirs_sha256": theirs_sha,
                                  "ours_rx": ours_rx, "ours_tx": ours_tx,
                                  "theirs_rx": theirs_rx, "theirs_tx": theirs_tx}}, void_rows

    # ---------------- ROW 0b: population reproduction -----------------------
    log("-" * 78); log("ROW 0b -- population (Sec.0.2 shape table) reproduction")
    ours_shapes = Counter()
    ours_shape_of = {}
    for i, r in enumerate(ours_rows):
        shp = C.classify_shape(r["message_norm"])
        if shp is not None:
            ours_shapes[shp] += 1
            ours_shape_of[i] = shp
    ours_total = sum(ours_shapes.values())
    log("  ours shapes: %s (total=%d)" % (dict(sorted(ours_shapes.items())), ours_total))
    log("  expect      : %s (total=%d)" % (C.EXPECTED_SHAPE_OURS, C.EXPECTED_SHAPE_OURS_TOTAL))
    ok0b_ours = (dict(ours_shapes) == C.EXPECTED_SHAPE_OURS and ours_total == C.EXPECTED_SHAPE_OURS_TOTAL)

    theirs_shapes = Counter()
    for r in theirs_rows:
        shp = C.classify_shape(r["message_norm"])
        if shp is not None:
            theirs_shapes[shp] += 1
    theirs_total = sum(theirs_shapes.values())
    theirs_dest = theirs_shapes.get("3tok_dest_resolved", 0) + theirs_shapes.get("3tok_dest_unresolved", 0)
    theirs_dest_resolved = theirs_shapes.get("3tok_dest_resolved", 0)
    log("  theirs shapes: %s (total=%d, dest=%d, dest_resolved=%d)"
        % (dict(sorted(theirs_shapes.items())), theirs_total, theirs_dest, theirs_dest_resolved))
    log("  expect        : total=%d dest=%d dest_resolved=%d"
        % (C.EXPECTED_SHAPE_THEIRS_TOTAL, C.EXPECTED_SHAPE_THEIRS_DEST, C.EXPECTED_SHAPE_THEIRS_DEST_RESOLVED))
    ok0b_theirs = (theirs_total == C.EXPECTED_SHAPE_THEIRS_TOTAL and theirs_dest == C.EXPECTED_SHAPE_THEIRS_DEST
                   and theirs_dest_resolved == C.EXPECTED_SHAPE_THEIRS_DEST_RESOLVED)
    ok0b = ok0b_ours and ok0b_theirs
    log("  ROW 0b: %s" % ("PASS" if ok0b else "FAIL"))
    if not ok0b:
        void("0b", "Sec.0.2 shape table did not reproduce exactly")
        return {"row0": {"0a": "PASS", "0b": "VOID"},
                "row0b_detail": {"ours_shapes": dict(ours_shapes), "theirs_shapes": dict(theirs_shapes)}}, void_rows

    # ---------------- ROW 0c: hash reproduction ------------------------------
    log("-" * 78); log("ROW 0c -- hash reproduction (module identity + occupancy)")
    module_identity_ok = (C.n22_of is C.A.n22_of) and (C.n12_of is C.A.n12_of)
    calls = C.distinct_plain_calls(ours_rows, theirs_rows)
    n_calls = len(calls)
    by12 = C.occupancy_by_n12(calls)
    n_occupied = len(by12)
    hist = Counter(len(v) for v in by12.values())
    log("  module identity (n22_of/n12_of imported from common_arm1, not re-typed): %s" % module_identity_ok)
    log("  distinct plain calls=%d (expect %d) ; occupied codes=%d (expect %d)"
        % (n_calls, C.EXPECTED_N_DISTINCT_CALLS, n_occupied, C.EXPECTED_N_OCCUPIED_CODES))
    log("  occupancy histogram=%s" % dict(sorted(hist.items())))
    log("  expect             =%s" % C.EXPECTED_OCCUPANCY_HIST)
    # Sec.4's ROW 0c text names exactly THREE reproduction targets: module
    # identity, 11,233 distinct calls, and the occupancy histogram (which
    # implies 3,848 occupied codes). It does NOT name the "8 other colliding"
    # or "1,553 refs" figures from Sec.0.2's prose -- those are reported below
    # as INFORMATIONAL, never gating ROW 0c's PASS/VOID, so a discrepancy in a
    # number Sec.4 never pre-registered cannot VOID an arm on a bar it never
    # actually set (HK-025 discipline: don't self-impose a stricter gate than
    # what was pre-registered).
    ok0c = (module_identity_ok and n_calls == C.EXPECTED_N_DISTINCT_CALLS
            and n_occupied == C.EXPECTED_N_OCCUPIED_CODES and dict(hist) == C.EXPECTED_OCCUPANCY_HIST)
    log("  ROW 0c: %s" % ("PASS" if ok0c else "FAIL"))
    if not ok0c:
        void("0c", "hash/occupancy reproduction (module identity / 11,233 / 3,848 / histogram) did not match Sec.4 exactly")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "VOID"},
                "row0c_detail": {"n_calls": n_calls, "n_occupied": n_occupied, "hist": dict(hist)}}, void_rows

    # ---------------- Sec.0.2 informational reproduction (NOT part of ROW 0c) ----
    log("-" * 78); log("Sec.0.2 informational reproduction (reported, does not gate ROW 0c)")
    own_n22 = C.n22_of(C.OWNCALL)
    own_n12 = C.n12_of(own_n22) if own_n22 is not None else None
    own_bucket = by12.get(own_n12, []) if own_n12 is not None else []
    own_in_own_bucket = C.OWNCALL in own_bucket
    n_other_colliding = len(own_bucket) - (1 if own_in_own_bucket else 0)
    log("  OWNCALL bucket size=%d (OWNCALL itself present=%s) -> other colliding=%d (Sec.0.2 said %d)"
        % (len(own_bucket), own_in_own_bucket, n_other_colliding, C.EXPECTED_OTHER_COLLIDING))
    if n_other_colliding != C.EXPECTED_OTHER_COLLIDING:
        log("  DISCREPANCY, independently confirmed (grep -w PD2FZ both ALL.TXT files = 0 hits): "
            "PD2FZ never appears as a plain token in either corpus, so it is NOT a member of the "
            "11,233-call set. The drafting probe's 'bucket_size - 1' silently assumed OWNCALL's own "
            "presence without checking; the true count of OTHER callsigns sharing our 12-bit code in "
            "this corpus is %d, not %d. Off by one, and in the direction that UNDERSTATES exposure." % (n_other_colliding, C.EXPECTED_OTHER_COLLIDING))

    refs = C.resolved_hash_refs(theirs_rows)
    n_refs = len(refs)
    n_carrying = sum(1 for name in refs if C.n12_of(C.n22_of(name)) == own_n12)
    log("  theirs resolved hashed refs (n22 computable)=%d (Sec.0.2 said %d) ; carrying OWNCALL's n12=%d (Sec.0.2 said %d)"
        % (n_refs, C.EXPECTED_HASHED_REFS_TOTAL, n_carrying, C.EXPECTED_HASHED_REFS_CARRYING_OWN_CODE))

    # CP one-sided upper bound on the a-priori collision rate (Sec.0.2 exposure figure)
    cp_hi_collision = C.cp_upper_one_sided(0, n_refs) if n_refs else None

    # ---------------- ROW 0d: predicate-movement exhibit (HK-021(q)) --------
    log("-" * 78); log("ROW 0d -- predicate-movement exhibit")
    movement_exhibit = None
    for r in ours_rows:
        shp = C.classify_shape(r["message_norm"])
        if shp != "3tok_dest_resolved":
            continue
        toks = r["message_norm"].split()
        own_hyp = toks[0][1:-1]
        if not own_hyp or set(own_hyp) == {'.'}:
            continue
        before = C.to_us_current(r["message_norm"], own_hyp)
        after = C.to_us_l1l2(r["message_norm"], own_hyp)
        if before is False and after is True:
            movement_exhibit = {"redacted_own_hyp": C.redact(own_hyp), "before": before, "after": after}
            break
    both_false_exhibit = None
    for r in ours_rows:
        shp = C.classify_shape(r["message_norm"])
        if shp is None:
            continue
        before = C.to_us_current(r["message_norm"], "ZZ0ZZZ")
        after = C.to_us_l1l2(r["message_norm"], "ZZ0ZZZ")
        if before is False and after is False:
            both_false_exhibit = {"before": before, "after": after}
            break
    ok0d = (movement_exhibit is not None and both_false_exhibit is not None)
    log("  movement exhibit (False->True) found: %s" % (movement_exhibit is not None))
    log("  both-False exhibit found: %s" % (both_false_exhibit is not None))
    log("  ROW 0d: %s" % ("PASS" if ok0d else "FAIL"))
    if not ok0d:
        void("0d", "could not exhibit a real decode where the predicate moves, or one where it stays False")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "VOID"}}, void_rows

    # ---------------- ROW 0e: transcription check ----------------------------
    log("-" * 78); log("ROW 0e -- transcription check (try_parse_message)")
    n_two_tok = 0
    n_three_tok = 0
    n_exceptions = 0
    for r in ours_rows:
        shp = C.classify_shape(r["message_norm"])
        if shp is None:
            continue
        ntok = len(r["message_norm"].split())
        parsed = C.try_parse_message(r["message_norm"])
        if ntok == 2:
            n_two_tok += 1
            if parsed is not None:
                n_exceptions += 1
        elif ntok == 3:
            n_three_tok += 1
            if parsed is None:
                n_exceptions += 1
        else:
            if parsed is not None:
                n_exceptions += 1
    log("  two-token=%d (expect %d) three-token=%d (expect %d) exceptions=%d (expect 0)"
        % (n_two_tok, C.EXPECTED_TWO_TOKEN_COUNT, n_three_tok, C.EXPECTED_THREE_TOKEN_COUNT, n_exceptions))
    ok0e = (n_two_tok == C.EXPECTED_TWO_TOKEN_COUNT and n_three_tok == C.EXPECTED_THREE_TOKEN_COUNT
            and n_exceptions == 0)
    log("  ROW 0e: %s" % ("PASS" if ok0e else "FAIL"))
    if not ok0e:
        void("0e", "try_parse_message transcription does not behave as Sec.3.1 describes")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "VOID"},
                "row0e_detail": {"n_two_tok": n_two_tok, "n_three_tok": n_three_tok,
                                  "n_exceptions": n_exceptions}}, void_rows

    # ==================== Sec.5 -- gates ====================================
    log("=" * 78); log("Sec.5 -- gates")

    own_calls_upper = {c.upper() for c in calls}
    own_calls_std = {c for c in calls if C.STD.fullmatch(c)}
    own_calls_std_upper = {c.upper() for c in own_calls_std}

    single_bracket_rows = [r for r in ours_rows if C.classify_shape(r["message_norm"]) is not None]
    assert len(single_bracket_rows) == C.EXPECTED_SHAPE_OURS_TOTAL

    def g1_counts(pop_rows, calls_upper):
        """Every count here is produced by CALLING the shipped Sec.3 predicates
        (C.to_us_current / C.to_us_l1l2) with the decode's own dest token (bracket
        stripped where L1L2 would strip it) as the hypothetical own-call -- never
        by re-deriving the comparison inline. Membership in `calls_upper` first
        (O(1)) picks the only candidate that could possibly fire, since equality
        is exact; the predicate call itself is what actually decides True/False,
        so a transcription slip in Sec.3 would show up here, not be masked."""
        g1a_literal = 0
        g1a_restricted = 0
        g1b = 0
        for r in pop_rows:
            msg = r["message_norm"]
            shp = C.classify_shape(msg)
            parts = msg.split()
            if len(parts) == 3:
                cand = parts[0]
                if cand.upper() in calls_upper and C.to_us_current(msg, cand):
                    g1a_literal += 1
                    if shp in ("3tok_dest_resolved", "3tok_dest_unresolved"):
                        g1a_restricted += 1
            if len(parts) in (2, 3):
                dest = parts[0]
                d = dest[1:-1] if (len(dest) >= 2 and dest[0] == '<' and dest[-1] == '>') else dest
                if d != '' and set(d) != {'.'} and d.upper() in calls_upper and C.to_us_l1l2(msg, d):
                    g1b += 1
        return g1a_literal, g1a_restricted, g1b

    g1a_literal, g1a_restricted, g1b = g1_counts(single_bracket_rows, own_calls_upper)
    g1a_literal_std, g1a_restricted_std, g1b_std = g1_counts(single_bracket_rows, own_calls_std_upper)

    log("-" * 78); log("G1 -- the reframing itself, falsifiable")
    log("  DISCLOSED READING: two G1a counts reported. LITERAL (Sec.5's own wording, all %d "
        "single-bracket decodes) = %d. RESTRICTED (Sec.1 outcome #2's own wording, hashed-dest "
        "only, %d decodes) = %d." % (len(single_bracket_rows), g1a_literal,
                                       C.EXPECTED_SHAPE_OURS['3tok_dest_resolved'] + C.EXPECTED_SHAPE_OURS['3tok_dest_unresolved'],
                                       g1a_restricted))
    log("  G1b (to_us_l1l2 fires) = %d" % g1b)
    log("  standard-form-only subset: G1a_literal=%d G1a_restricted=%d G1b=%d"
        % (g1a_literal_std, g1a_restricted_std, g1b_std))
    if g1a_restricted > 0:
        g1_verdict = "G1_FAILS_RESTRICTED"
        log("  -> G1 FAILS even under the restricted reading -- outcome #2. Sec.0.1 is wrong. STOP -- no G2/G3.")
    elif g1a_literal > 0 and g1a_restricted == 0:
        g1_verdict = "G1_HOLDS_RESTRICTED_LITERAL_NONZERO"
        log("  -> Literal G1a is NONZERO (%d) but every hit is attributable to non-hash bracket-at-src/"
            "other messages whose PLAIN dest legitimately matches a real own-call -- ordinary correct "
            "behaviour, not a hash counter-example. Restricted G1a (hashed-dest only) is exactly 0. "
            "G1 HOLDS under the reading that tests Sec.0.1(a)'s actual claim; the literal-reading "
            "mismatch is a drafting-precision issue, flagged for the Architect, not self-ruled." % g1a_literal)
    elif g1a_literal == 0 and g1b == 0:
        g1_verdict = "VOID_0d_equivalent"
        log("  -> both G1a readings and G1b are 0 -- predicate never moves. VOID.")
    else:
        g1_verdict = "G1_HOLDS"
        log("  -> G1 HOLDS on both readings.")

    row_g1 = {
        "n_population": len(single_bracket_rows), "n_own_calls": len(calls),
        "g1a_literal": g1a_literal, "g1a_restricted": g1a_restricted, "g1b": g1b,
        "n_hashed_dest_population": C.EXPECTED_SHAPE_OURS['3tok_dest_resolved'] + C.EXPECTED_SHAPE_OURS['3tok_dest_unresolved'],
        "std_subset": {"n_own_calls_std": len(own_calls_std), "g1a_literal": g1a_literal_std,
                        "g1a_restricted": g1a_restricted_std, "g1b": g1b_std},
        "verdict": g1_verdict,
    }

    if g1_verdict == "G1_FAILS_RESTRICTED":
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS"},
                "row_g1": row_g1}, void_rows
    if g1_verdict == "VOID_0d_equivalent":
        void("G1", "predicate never moves under either reading -- not a gate")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS"},
                "row_g1": row_g1}, void_rows

    # ---------------- G2: layer worth, descriptive --------------------------
    log("-" * 78); log("G2 -- layer worth (descriptive, NOT gated)")
    # Set-membership sweep, one pass per own-call population (11,233) would be
    # O(N*M); instead sweep once per DECODE, picking the one candidate own-call
    # that could possibly fire (its own dest token, stripped as each predicate
    # would strip it) and then CALLING the predicate itself to decide -- L1/L2
    # variants are QA's own single-axis extensions (common_r5.to_us_l1_only /
    # to_us_l2_only, see that module's docstring), the combined form and the
    # baseline are the shipped Sec.3 functions, called verbatim.
    recovered_l1 = recovered_l2 = recovered_l1l2 = 0
    for r in single_bracket_rows:
        msg = r["message_norm"]
        parts = msg.split()
        # L1 only: candidate is the literal (unstripped) dest; only 2-token
        # decodes can possibly be "recovered" here, since for 3-token decodes
        # to_us_l1_only and to_us_current agree by construction.
        if len(parts) == 2:
            cand = parts[0]
            if cand.upper() in own_calls_upper and C.to_us_l1_only(msg, cand) and not C.to_us_current(msg, cand):
                recovered_l1 += 1
        # L2 only: candidate is the stripped dest; only 3-token decodes are in
        # scope for to_us_l2_only at all.
        if len(parts) == 3:
            dest = parts[0]
            d = dest[1:-1] if (len(dest) >= 2 and dest[0] == '<' and dest[-1] == '>') else dest
            if (d != '' and set(d) != {'.'} and d.upper() in own_calls_upper
                    and C.to_us_l2_only(msg, d) and not C.to_us_current(msg, d)):
                recovered_l2 += 1
        # L1+L2 together: the shipped combined predicate.
        if len(parts) in (2, 3):
            dest = parts[0]
            d = dest[1:-1] if (len(dest) >= 2 and dest[0] == '<' and dest[-1] == '>') else dest
            if (d != '' and set(d) != {'.'} and d.upper() in own_calls_upper
                    and C.to_us_l1l2(msg, d) and not C.to_us_current(msg, d)):
                recovered_l1l2 += 1
    log("  recovered by L1 alone (2-token accept)  = %d" % recovered_l1)
    log("  recovered by L2 alone (bracket strip)   = %d" % recovered_l2)
    log("  recovered by L1+L2 together             = %d" % recovered_l1l2)
    row_g2 = {"recovered_l1_alone": recovered_l1, "recovered_l2_alone": recovered_l2,
              "recovered_l1l2_together": recovered_l1l2}

    # ---------------- G3: false-positive cost of the own-hash rule ----------
    log("-" * 78); log("G3 -- false-positive cost of the own-hash rule")
    bucket_size = {n12: len(v) for n12, v in by12.items()}
    bucket_max_size = max(bucket_size.values()) if bucket_size else 0

    hd_rows = C.hashed_dest_rows(ours_rows)
    theirs_index = C.CB.build_theirs_index(theirs_rows)
    paired = C.pair_hashed_dest_to_reference(hd_rows, theirs_index)

    n_hd = len(paired)
    n_matched_any = sum(1 for p in paired if p["matched"])
    n_resolved = sum(1 for p in paired if p["theirs_name"] is not None)
    log("  hashed-dest ours decodes=%d ; have ANY reference row=%d (%.1f%%) ; reference resolved=%d (%.1f%%)"
        % (n_hd, n_matched_any, 100.0 * n_matched_any / max(1, n_hd), n_resolved, 100.0 * n_resolved / max(1, n_hd)))

    def g3_pass(bucket_szs, bmax, calls_set):
        fp_known = n_fires_known = 0
        n_unknown = 0
        for p in paired:
            name = p["theirs_name"]
            if name is None or C.n22_of(name) is None:
                n_unknown += 1
                continue
            n12 = C.n12_of(C.n22_of(name))
            bsz = bucket_szs.get(n12, 0)
            n_fires_known += bsz
            fp_known += bsz - (1 if name in calls_set else 0)
        fp_min, n_fires_min = fp_known, n_fires_known
        fp_max = fp_known + bmax * n_unknown
        n_fires_max = n_fires_known + bmax * n_unknown
        return fp_min, n_fires_min, fp_max, n_fires_max, n_unknown

    fp_min, n_fires_min, fp_max, n_fires_max, n_unknown = g3_pass(bucket_size, bucket_max_size, calls)

    p_max = (fp_max / n_fires_max) if n_fires_max else None
    p_min = (fp_min / n_fires_min) if n_fires_min else None
    cp_hi_max = C.cp_upper_one_sided(fp_max, n_fires_max) if n_fires_max else None
    cp_lo_min = C.cp_lower_one_sided(fp_min, n_fires_min) if n_fires_min else None

    log("  KNOWN theirs_name pairs=%d ; UNKNOWN pairs=%d (bucket_max_size=%d)" % (n_hd - n_unknown, n_unknown, bucket_max_size))
    log("  MIN pass (UNKNOWN->0,0)  : fp_min=%d n_fires_min=%d p=%s CP one-sided 95%% lower=%s"
        % (fp_min, n_fires_min, ("%.6f" % p_min) if p_min is not None else "N/A",
           ("%.6f" % cp_lo_min) if cp_lo_min is not None else "N/A"))
    log("  MAX pass (UNKNOWN->bmax) : fp_max=%d n_fires_max=%d p=%s CP one-sided 95%% upper=%s"
        % (fp_max, n_fires_max, ("%.6f" % p_max) if p_max is not None else "N/A",
           ("%.6f" % cp_hi_max) if cp_hi_max is not None else "N/A"))

    if cp_hi_max is not None and cp_hi_max < 0.0100:
        g3_gate = "G3-1_FAVOURABLE"
    elif cp_lo_min is not None and cp_lo_min > 0.0500:
        g3_gate = "G3-2_UNFAVOURABLE"
    else:
        g3_gate = "G3-3_INDETERMINATE"
    log("  -> %s" % g3_gate)

    straddle_001 = (cp_lo_min is not None and cp_hi_max is not None and cp_lo_min < 0.0100 < cp_hi_max)
    straddle_005 = (cp_lo_min is not None and cp_hi_max is not None and cp_lo_min < 0.0500 < cp_hi_max)
    log("  straddle: 0.0100 threshold straddled=%s ; 0.0500 threshold straddled=%s (position, not width -- HK-021(w))"
        % (straddle_001, straddle_005))
    log("  power check: n_fires_min=%d (spec's own-power note flags concern if this is < 400)" % n_fires_min)

    # Standard-form-only subset, same treatment as G1 (Sec.5 preamble: "our own
    # call is standard; a distribution dominated by nonstandard hypotheticals
    # would not describe our case"). own_calls_std/upper defined earlier for G1.
    bucket_size_std = Counter()
    for c in own_calls_std:
        h = C.n22_of(c)
        if h is not None:
            bucket_size_std[C.n12_of(h)] += 1
    bucket_max_std = max(bucket_size_std.values()) if bucket_size_std else 0
    fp_min_std, n_fires_min_std, fp_max_std, n_fires_max_std, n_unknown_std = g3_pass(
        bucket_size_std, bucket_max_std, own_calls_std)
    p_min_std = (fp_min_std / n_fires_min_std) if n_fires_min_std else None
    p_max_std = (fp_max_std / n_fires_max_std) if n_fires_max_std else None
    cp_lo_min_std = C.cp_lower_one_sided(fp_min_std, n_fires_min_std) if n_fires_min_std else None
    cp_hi_max_std = C.cp_upper_one_sided(fp_max_std, n_fires_max_std) if n_fires_max_std else None
    if cp_hi_max_std is not None and cp_hi_max_std < 0.0100:
        g3_gate_std = "G3-1_FAVOURABLE"
    elif cp_lo_min_std is not None and cp_lo_min_std > 0.0500:
        g3_gate_std = "G3-2_UNFAVOURABLE"
    else:
        g3_gate_std = "G3-3_INDETERMINATE"
    log("  STD-only subset (%d of %d own-calls are standard-form): fp_min=%d n_fires_min=%d p=%s "
        "CP one-sided 95%% lower=%s -> %s"
        % (len(own_calls_std), len(calls), fp_min_std, n_fires_min_std,
           ("%.6f" % p_min_std) if p_min_std is not None else "N/A",
           ("%.6f" % cp_lo_min_std) if cp_lo_min_std is not None else "N/A", g3_gate_std))

    row_g3 = {
        "n_hashed_dest": n_hd, "n_matched_any_reference": n_matched_any, "n_resolved": n_resolved,
        "n_unknown": n_unknown, "bucket_max_size": bucket_max_size,
        "fp_min": fp_min, "n_fires_min": n_fires_min, "p_min": p_min, "cp_lower_one_sided_95_of_min": cp_lo_min,
        "fp_max": fp_max, "n_fires_max": n_fires_max, "p_max": p_max, "cp_upper_one_sided_95_of_max": cp_hi_max,
        "gate": g3_gate, "straddle_0100": straddle_001, "straddle_0500": straddle_005,
        "std_subset": {
            "n_own_calls_std": len(own_calls_std), "bucket_max_size": bucket_max_std,
            "fp_min": fp_min_std, "n_fires_min": n_fires_min_std, "p_min": p_min_std,
            "cp_lower_one_sided_95_of_min": cp_lo_min_std,
            "fp_max": fp_max_std, "n_fires_max": n_fires_max_std, "p_max": p_max_std,
            "cp_upper_one_sided_95_of_max": cp_hi_max_std, "gate": g3_gate_std,
        },
    }

    # ---------------- G4: containment by partner binding --------------------
    log("-" * 78); log("G4 -- containment by partner binding")
    log("  NOT COMPUTABLE: this corpus is receive-only and carries no QSO state machine, so "
        "'the hypothetical own-call's actual QSO partner' has no operational referent here. "
        "QsoAnswererService.cs:1081/:1163's fromPartner is bound to explicit protocol state "
        "(WaitReport/WaitRr73 with a specific partner call already latched); any text-proximity "
        "proxy invented after the fact would not be measuring that conjunction, only something "
        "shaped like it. Per Sec.5/G4's own instruction, reported as NOT COMPUTABLE rather than "
        "papered over with an invented proxy.")
    row_g4 = {"status": "NOT_COMPUTABLE", "reason": "no QSO state machine in a receive-only corpus"}

    result = {
        "row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS"},
        "row0c_detail": {"n_calls": n_calls, "n_occupied": n_occupied, "hist": dict(hist),
                          "n_other_colliding": n_other_colliding, "own_in_own_bucket": own_in_own_bucket,
                          "spec_said_other_colliding": C.EXPECTED_OTHER_COLLIDING,
                          "other_colliding_discrepancy": n_other_colliding != C.EXPECTED_OTHER_COLLIDING,
                          "n_refs": n_refs, "n_carrying": n_carrying,
                          "cp_upper_one_sided_95_of_collision_rate": cp_hi_collision},
        "row0d_detail": {"movement_exhibit": movement_exhibit, "both_false_exhibit": both_false_exhibit},
        "row0e_detail": {"n_two_tok": n_two_tok, "n_three_tok": n_three_tok, "n_exceptions": n_exceptions},
        "row0h_detail": {"n_hashed_dest": n_hd, "n_matched_any_reference": n_matched_any, "n_resolved": n_resolved,
                          "share_matched": n_matched_any / max(1, n_hd), "share_resolved": n_resolved / max(1, n_hd)},
        "row_g1": row_g1,
        "row_g2": row_g2,
        "row_g3": row_g3,
        "row_g4": row_g4,
    }
    return result, void_rows


# =============================================================================
# ROW 0f: out-of-process determinism check
# =============================================================================
def emit_core_json():
    def noop_log(_msg=""):
        pass
    result, _void = compute_all(noop_log)
    sys.stdout.write(json.dumps(result, sort_keys=True))
    sys.stdout.flush()


def run_row0f_check(script_path: str) -> tuple[bool, str, str]:
    def run_with_seed(seed: str) -> str:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, script_path, "--emit-core-json"],
            capture_output=True, text=True, check=True, cwd=HERE, env=env,
        )
        return proc.stdout
    out_a = run_with_seed(HASHSEED_A)
    out_b = run_with_seed(HASHSEED_B)
    return (out_a == out_b), out_a, out_b


# =============================================================================
def finish(args, log_lines, result, void_rows):
    result_path = os.path.join(args.out_dir, "result.json")
    tmp = result_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    os.replace(tmp, result_path)
    log_path = os.path.join(args.out_dir, "run.log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")

    # ROW 0g: NFR-021 scan of result.json + run.log (run AFTER both are written)
    with open(result_path, encoding="utf-8") as fh:
        result_text = fh.read()
    with open(log_path, encoding="utf-8") as fh:
        log_text = fh.read()
    hits = nfr021_scan_text(result_text) | nfr021_scan_text(log_text)
    ok0g = (len(hits) == 0)
    print("ROW 0g -- NFR-021 scan of result.json + run.log: %s (hits=%d)"
          % ("PASS" if ok0g else "FAIL", len(hits)))
    result.setdefault("row0", {})["0g"] = "PASS" if ok0g else "VOID"
    result["row0g_detail"] = {"n_hits": len(hits)}
    if not ok0g:
        void_rows.append(("0g", "callsign-shaped token(s) found in result.json/run.log outside the OWNCALL exception"))
    # rewrite result.json with the 0g verdict folded in
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    os.replace(tmp, result_path)

    print("=" * 78)
    print("DONE -- result: %s" % result_path)
    if void_rows:
        print("VOID at: %s" % void_rows)
    print("=" * 78)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir")
    ap.add_argument("--emit-core-json", action="store_true")
    args = ap.parse_args()

    if args.emit_core_json:
        emit_core_json()
        return 0

    if not args.out_dir:
        print("error: --out-dir is required for a normal run", file=sys.stderr)
        return 2
    os.makedirs(args.out_dir, exist_ok=True)
    log_lines = []

    def log(msg=""):
        print(msg, flush=True)
        log_lines.append(msg)

    log("=" * 78)
    log("F-001 R5 -- run_r5.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    result, void_rows = compute_all(log)

    if not void_rows:
        log("-" * 78); log("ROW 0f -- determinism, OUT OF PROCESS, different PYTHONHASHSEED")
        script_path = os.path.abspath(__file__)
        det_ok, out_a, out_b = run_row0f_check(script_path)
        log("  seed A=%s seed B=%s -- result.json byte-identical: %s" % (HASHSEED_A, HASHSEED_B, det_ok))
        log("  ROW 0f: %s" % ("PASS" if det_ok else "FAIL"))
        result["row0"]["0f"] = "PASS" if det_ok else "VOID"
        result["row0f_detail"] = {"hashseed_a": HASHSEED_A, "hashseed_b": HASHSEED_B, "byte_identical": det_ok}
        if not det_ok:
            void_rows.append(("0f", "out-of-process rerun under a different PYTHONHASHSEED was not byte-identical"))
            log("  -> VOID at ROW 0f: hash-randomised-iteration hazard reproduced")

    return finish(args, log_lines, result, void_rows)


if __name__ == "__main__":
    sys.exit(main())
