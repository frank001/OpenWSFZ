#!/usr/bin/env python3
"""f001-h12-unique-match-suppression: evaluate AC-1..AC-4 mechanically against
a BASE (shim 20260048) and CANDIDATE (shim 20260049) S-17M decode set.

openspec/changes/f001-h12-unique-match-suppression/tasks.md Sec.8:
  AC-1 decode count identical: zero decodes gained, zero lost.
  AC-2 number of differing lines == the ambiguous count read from the same (candidate) run.
  AC-3 every differing line differs ONLY by one bracketed callsign token becoming "<...>";
       frequency, DT, SNR and every other payload token byte-identical.
  AC-4 suppressed count == ambiguous count exactly (candidate run's own final counters).

Rows run in strict order (HK-025-style); the first failure stops evaluation. Matching within a
cycle is by POSITIONAL index -- valid only once AC-1 confirms both legs decoded the same COUNT
per cycle; the decoder is deterministic and the only behavioural difference under test is
render text, not decode order/count, so index alignment is the correct matching rule here (not
an assumption smuggled in: AC-1 is exactly the row that would catch it being wrong).

NFR-021: never prints a real callsign. Every differing token is redacted to CS-<sha256[:6]>
before being written to stdout or the report JSON, matching qa/rr-study/nfr021_pre_merge_scan.py's
existing convention.

Usage: python g4_ac_evaluate.py <base_json> <candidate_json> <report_out_json>
"""
from __future__ import annotations

import hashlib
import json
import sys


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def redact(tok: str) -> str:
    return f"CS-{hashlib.sha256(tok.encode('utf-8')).hexdigest()[:6]}"


def ac1_decode_count(base, cand):
    print("=== AC-1 -- decode count identical (zero gained, zero lost) ===")
    if len(base["per_file"]) != len(cand["per_file"]):
        print(f"  STRUCTURAL MISMATCH: base {len(base['per_file'])} cycles, "
              f"candidate {len(cand['per_file'])} cycles")
        print("AC-1: STOP -- corpora are not the same replay window")
        return False, []

    per_cycle_mismatches = []
    total_base = total_cand = 0
    for b, c in zip(base["per_file"], cand["per_file"]):
        if b["ts"] != c["ts"]:
            per_cycle_mismatches.append((b["ts"], c["ts"], "ts differs"))
            continue
        nb, nc = len(b["decodes"]), len(c["decodes"])
        total_base += nb
        total_cand += nc
        if nb != nc:
            per_cycle_mismatches.append((b["ts"], nb, nc))

    print(f"  total decodes: base={total_base} candidate={total_cand}")
    ok = not per_cycle_mismatches and total_base == total_cand
    if per_cycle_mismatches:
        print(f"  {len(per_cycle_mismatches)} cycle(s) with a differing decode count, "
              f"first 5: {per_cycle_mismatches[:5]}")
    print(f"AC-1: {'PASS' if ok else 'STOP -- suppression is killing decodes, not names'}")
    return ok, per_cycle_mismatches


def diff_lines(base, cand):
    """Positional per-cycle diff. Returns list of dicts describing each cycle
    whose decode set differs at all (message text OR f/dt/snr)."""
    diffs = []
    for b, c in zip(base["per_file"], cand["per_file"]):
        for i, (bd, cd) in enumerate(zip(b["decodes"], c["decodes"])):
            if bd == cd:
                continue
            diffs.append({"ts": b["ts"], "idx": i, "base": bd, "cand": cd})
    return diffs


def bracket_aware_tokens(msg: str) -> list[str]:
    """Whitespace-split, EXCEPT a '<...>'-delimited span is kept as ONE token
    even if it contains an internal space. Needed because the native hash
    table can render a resolved callsign with an embedded space inside its
    brackets (a pre-existing quirk of the STORED callsign field, present in
    BASE independent of this change -- see the g4_ac_evaluate investigation
    note below) -- naive str.split() would wrongly cut such a field into two
    tokens and make a scope-compliant diff look like a token-count mismatch.
    """
    toks = []
    i, n = 0, len(msg)
    while i < n:
        while i < n and msg[i].isspace():
            i += 1
        if i >= n:
            break
        if msg[i] == "<":
            j = msg.find(">", i)
            if j == -1:
                j = n - 1  # unterminated -- take the rest rather than crash
            toks.append(msg[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and not msg[j].isspace():
                j += 1
            toks.append(msg[i:j])
            i = j
    return toks


def classify_diff(bd, cd):
    """Returns (is_scope_compliant: bool, detail: dict) for one differing decode
    line, per AC-3's predicate: only one bracketed callsign token becomes
    "<...>"; f/dt/snr byte-identical; every other token identical."""
    detail = {}
    numeric_ok = (bd["f"] == cd["f"] and bd["dt"] == cd["dt"] and bd["snr"] == cd["snr"])
    detail["numeric_ok"] = numeric_ok

    b_toks = bracket_aware_tokens(bd["m"])
    c_toks = bracket_aware_tokens(cd["m"])
    if len(b_toks) != len(c_toks):
        detail["token_count_ok"] = False
        return False, detail
    detail["token_count_ok"] = True

    diff_idx = [i for i, (bt, ct) in enumerate(zip(b_toks, c_toks)) if bt != ct]
    detail["n_differing_tokens"] = len(diff_idx)
    if len(diff_idx) != 1:
        return False, detail

    i = diff_idx[0]
    b_tok, c_tok = b_toks[i], c_toks[i]
    detail["cand_token_is_placeholder"] = (c_tok == "<...>")
    detail["base_token_was_bracketed"] = (b_tok.startswith("<") and b_tok.endswith(">"))
    detail["base_token_redacted"] = redact(b_tok)

    ok = numeric_ok and detail["cand_token_is_placeholder"] and detail["base_token_was_bracketed"]
    return ok, detail


def ac2_ac3(base, cand):
    print("=== AC-2/AC-3 -- differing-line count vs ambiguous count, and scope of each diff ===")
    diffs = diff_lines(base, cand)
    n_diff = len(diffs)
    ambiguous = cand["h12_ambiguous_count_final"]
    print(f"  differing decode lines (positional): {n_diff}")
    print(f"  candidate h12_ambiguous_count_final: {ambiguous}")
    ac2_ok = (n_diff == ambiguous)
    print(f"AC-2: {'PASS' if ac2_ok else 'FAIL -- the predicate fires somewhere other than where the instrument counted'}")

    print()
    print("=== AC-3 -- each differing line changes ONLY the suppressed callsign token ===")
    scope_bad = []
    for d in diffs:
        ok, detail = classify_diff(d["base"], d["cand"])
        if not ok:
            scope_bad.append({"ts": d["ts"], "idx": d["idx"], **detail})
    ac3_ok = not scope_bad
    if scope_bad:
        print(f"  {len(scope_bad)} differing line(s) fail AC-3's scope predicate, first 5:")
        for x in scope_bad[:5]:
            print(f"    {x}")
    else:
        print(f"  all {n_diff} differing line(s) are scope-compliant "
              f"(numeric fields identical, exactly one bracketed token -> \"<...>\")")
    print(f"AC-3: {'PASS' if ac3_ok else 'FAIL -- a change escaped its scope'}")
    return ac2_ok, ac3_ok, n_diff, ambiguous, diffs, scope_bad


def ac4_suppressed_eq_ambiguous(cand):
    print("=== AC-4 -- suppressed count equals ambiguous count exactly ===")
    s = cand["h12_suppressed_count_final"]
    a = cand["h12_ambiguous_count_final"]
    ok = (s == a)
    print(f"  h12_suppressed_count_final={s} h12_ambiguous_count_final={a}")
    print(f"AC-4: {'PASS' if ok else 'FAIL -- wiring invariant broken between decision site and counting site'}")
    return ok


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    base = load(sys.argv[1])
    cand = load(sys.argv[2])
    report_path = sys.argv[3]

    report = {"base_json": sys.argv[1], "cand_json": sys.argv[2],
              "base_sha256": base["dll_sha256"], "base_shim": base["shim_version"],
              "cand_sha256": cand["dll_sha256"], "cand_shim": cand["shim_version"]}

    ok1, mismatches = ac1_decode_count(base, cand)
    report["ac1_pass"] = ok1
    if not ok1:
        report["ac1_mismatches"] = mismatches[:20]
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print("\nSTOP after AC-1 -- not evaluating AC-2/AC-3/AC-4 (they presuppose AC-1).")
        return 1
    print()

    ok2, ok3, n_diff, ambiguous, diffs, scope_bad = ac2_ac3(base, cand)
    report["ac2_pass"] = ok2
    report["ac2_n_differing_lines"] = n_diff
    report["ac2_ambiguous_count"] = ambiguous
    report["ac3_pass"] = ok3
    report["ac3_n_scope_violations"] = len(scope_bad)
    report["ac3_scope_violations_redacted"] = scope_bad[:20]
    print()

    ok4 = ac4_suppressed_eq_ambiguous(cand)
    report["ac4_pass"] = ok4
    print()

    overall = ok1 and ok2 and ok3 and ok4
    print(f"OVERALL: {'ALL AC-1..AC-4 PASS' if overall else 'AT LEAST ONE AC FAILED -- see above'}")
    report["overall_pass"] = overall

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nReport written: {report_path}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
