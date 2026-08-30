#!/usr/bin/env python3
"""ROW 0: evaluate 0a, 0c, 0d-i, 0e mechanically against the S-17M full-corpus
legs. 0b is delegated to row0b_means1_canonical_diff.py / row0b_means2_field_
compare.py (kept separate deliberately -- see their own docstrings on why).
0d-ii is a static source check, done by inspection, not here. 0f is
qa/rr-study/nfr021_pre_merge_scan.py, run separately against the committed
diff.

Spec: qa/rr-study/2026-08-30-1149-...-instrumented-suppression-sizing.md Sec.5
      qa/rr-study/2026-08-30-1432-...-amendment-1-row0-pre-merge.md Sec.A5/A6
Manifest: qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md

HK-025: rows run in STRICT ORDER; the first failure stops evaluation of
everything after it (no partial credit, no skipping ahead).

Usage: python row0_evaluate_s17m.py <base_json> <inst_run1_json> <inst_run2_json>
"""
from __future__ import annotations

import json
import sys

BASE_SHA = "bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f"
BASE_SHIM = 20260046
INST_SHA = "37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26"
INST_SHIM = 20260047


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def row_0a(base, inst_run1, inst_run2):
    print("=== ROW 0a -- binary identity ===")
    checks = [
        ("BASE", base, BASE_SHA, BASE_SHIM),
        ("INST run1", inst_run1, INST_SHA, INST_SHIM),
        ("INST run2", inst_run2, INST_SHA, INST_SHIM),
    ]
    ok = True
    for name, doc, want_sha, want_shim in checks:
        sha_ok = doc["dll_sha256"] == want_sha
        shim_ok = doc["shim_version"] == want_shim
        print(f"  {name}: sha256 {'OK' if sha_ok else 'MISMATCH'}, "
              f"shim {'OK' if shim_ok else 'MISMATCH'} "
              f"(got {doc['shim_version']}, want {want_shim})")
        ok = ok and sha_ok and shim_ok
    print(f"ROW 0a: {'PASS' if ok else 'VOID -- run is not of the pinned build'}")
    return ok


def row_0c(inst):
    print("=== ROW 0c -- counter arithmetic (identity, cannot legitimately fail) ===")
    bad = []
    for rec in inst["per_file"]:
        d, a, v = rec["h12Displaying"], rec["h12Ambiguous"], rec["h12Divergent"]
        if not (v <= a <= d):
            bad.append((rec["ts"], d, a, v))
    ok = not bad
    if not ok:
        print(f"  {len(bad)} cycle(s) violate h12Divergent <= h12Ambiguous <= "
              f"h12Displaying, first: {bad[0]}")
    print(f"ROW 0c: {'PASS' if ok else 'VOID -- implementation defect'} "
          f"({len(inst['per_file'])} cycles checked)")
    return ok


def row_0d_i(inst):
    print("=== ROW 0d-i -- denominator is displays, not attempts ===")
    prev_d = 0
    bad = []
    total_decodes = 0
    for rec in inst["per_file"]:
        d = rec["h12Displaying"]
        delta = d - prev_d
        n_dec = len(rec["decodes"])
        total_decodes += n_dec
        if delta > n_dec:
            bad.append((rec["ts"], delta, n_dec))
        prev_d = d
    final_d = inst["per_file"][-1]["h12Displaying"] if inst["per_file"] else 0
    cum_ok = final_d <= total_decodes
    ok = not bad and cum_ok
    if bad:
        print(f"  {len(bad)} cycle(s) violate delta(h12Displaying) <= len(decodes), "
              f"first: {bad[0]}")
    print(f"  cumulative: h12Displaying={final_d} <= total decodes={total_decodes}: "
          f"{'OK' if cum_ok else 'VIOLATED'}")
    print(f"ROW 0d-i: {'PASS' if ok else 'VOID -- counter is counting decode attempts'}")
    return ok


def row_0e(inst_run1, inst_run2):
    print("=== ROW 0e -- determinism (two INST replays, identical counter series) ===")
    f1, f2 = inst_run1["per_file"], inst_run2["per_file"]
    if len(f1) != len(f2):
        print(f"  STRUCTURAL MISMATCH: run1 {len(f1)} cycles, run2 {len(f2)} cycles")
        print("ROW 0e: VOID -- non-deterministic instrument")
        return False
    diffs = []
    for i in range(len(f1)):
        a, b = f1[i], f2[i]
        if a["ts"] != b["ts"]:
            diffs.append(f"cycle {i}: ts differs {a['ts']!r} vs {b['ts']!r}")
            continue
        key_a = (a["h12Displaying"], a["h12Ambiguous"], a["h12Divergent"])
        key_b = (b["h12Displaying"], b["h12Ambiguous"], b["h12Divergent"])
        if key_a != key_b:
            diffs.append(f"ts={a['ts']}: counters differ run1={key_a} run2={key_b}")
    ok = not diffs
    if diffs:
        print(f"  {len(diffs)} differing cycle(s), first 5: {diffs[:5]}")
    print(f"ROW 0e: {'PASS' if ok else 'VOID -- a non-deterministic instrument cannot be read'} "
          f"({len(f1)} cycles compared)")
    return ok


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    base = load(sys.argv[1])
    inst_run1 = load(sys.argv[2])
    inst_run2 = load(sys.argv[3])

    # HK-025: strict order, stop at first failure.
    if not row_0a(base, inst_run1, inst_run2):
        return 1
    print()
    # 0b runs separately (row0b_means1/means2) -- not duplicated here.
    print("=== ROW 0b -- see row0b_means1_canonical_diff.py / "
          "row0b_means2_field_compare.py (run separately) ===\n")
    if not row_0c(inst_run1):
        return 1
    print()
    if not row_0d_i(inst_run1):
        return 1
    print()
    if not row_0e(inst_run1, inst_run2):
        return 1
    print()
    print("ROWS 0a, 0c, 0d-i, 0e: ALL PASS (0b/0d-ii/0f evaluated separately)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
