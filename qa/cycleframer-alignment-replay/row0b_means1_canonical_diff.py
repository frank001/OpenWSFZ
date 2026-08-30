#!/usr/bin/env python3
"""ROW 0b, means 1 -- canonicalise each leg to one line per decode, `diff`.

Spec Amendment 1 Sec.A5: "canonicalise each leg to one line per decode
(sorted deterministically at construction), `diff` the two files, require
exit 0." Comparison is scoped to ts / decodes[] (ORDERED -- the shim's
iteration order is unchanged so ordered comparison is available and
strictly stronger than sorted) / av / truncated. wall_s, cand[], pass[],
label, dll_path, dll_sha256, shim_version are excluded (Sec.A5 table).

Deliberately independent of row0b_means2_field_compare.py: this file owns
the ONLY canonicaliser either means uses. Means 2 re-implements its own
comparison from scratch against the raw JSON, per the spec's explicit
"must NOT import or reuse means 1's canonicaliser" instruction.

Usage: python row0b_means1_canonical_diff.py <base_json> <inst_json> [--keep]
Exit 0 = identical (ROW 0b passes on this means). Non-zero = a difference
was found, or a structural mismatch (different n_files/ts sequence).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile


def canonical_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    lines = []
    for rec in data["per_file"]:
        dec_str = ";".join(
            f"{d['f']},{d['dt']},{d['snr']},{d['m']}" for d in rec["decodes"]
        )
        lines.append(f"{rec['ts']}|av={rec['av']}|trunc={rec['truncated']}|{dec_str}")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base_json")
    ap.add_argument("inst_json")
    ap.add_argument("--keep", action="store_true",
                     help="keep the two canonical .txt files instead of deleting them")
    args = ap.parse_args()

    base_lines = canonical_lines(args.base_json)
    inst_lines = canonical_lines(args.inst_json)

    if len(base_lines) != len(inst_lines):
        print(f"STRUCTURAL MISMATCH: BASE has {len(base_lines)} cycles, "
              f"INST has {len(inst_lines)} -- ROW 0b FAILS before any diff",
              file=sys.stderr)
        return 1

    fd_b, base_txt = tempfile.mkstemp(suffix=".base.txt")
    fd_i, inst_txt = tempfile.mkstemp(suffix=".inst.txt")
    try:
        with os.fdopen(fd_b, "w", encoding="utf-8") as fh:
            fh.write("\n".join(base_lines) + "\n")
        with os.fdopen(fd_i, "w", encoding="utf-8") as fh:
            fh.write("\n".join(inst_lines) + "\n")

        result = subprocess.run(["diff", "-u", base_txt, inst_txt],
                                 capture_output=True, text=True)
        if result.returncode == 0:
            print(f"ROW 0b means 1: PASS -- {len(base_lines)} cycles, "
                  f"mechanical diff exit 0, identical")
        else:
            # NFR-021: the canonical lines carry real off-air message text
            # ("m"). A failing diff must NEVER be echoed to stdout/stderr --
            # that is exactly the "document asserting no exposure IS the
            # exposure" pattern this class has already fired on three times
            # (standing memory). Report only the differing-line COUNT; the
            # full canonical files stay on disk under artefacts/
            # (gitignored) for local inspection only, never printed here.
            n_diff_lines = sum(
                1 for ln in result.stdout.splitlines()
                if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")))
            print(f"ROW 0b means 1: FAIL -- diff exit {result.returncode}, "
                  f"{n_diff_lines} differing line(s). NFR-021: message text "
                  f"withheld from this output. Canonical files kept for local "
                  f"inspection only: {base_txt} {inst_txt}", file=sys.stderr)
            args.keep = True
        return result.returncode
    finally:
        if args.keep:
            print(f"canonical files kept: {base_txt} {inst_txt}")
        else:
            os.unlink(base_txt)
            os.unlink(inst_txt)


if __name__ == "__main__":
    sys.exit(main())
