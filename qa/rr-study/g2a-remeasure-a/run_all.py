#!/usr/bin/env python3
"""G2A-REMEASURE-A -- orchestrator. Reads the three decode dumps produced by
decode_corpus.py (L1, L2_run1, L2_run2 -- each a separate process, fresh DLL
load), runs ROW 0 in strict order, and if it passes runs Part A/B/C.

Usage:
    python run_all.py --out-dir results/<date>-<sha>
    python run_all.py --l1 <path> --l2run1 <path> --l2run2 <path> --out-dir <dir>  (testing)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_g2a as G  # noqa: E402
import row0 as R0  # noqa: E402
import part_a as PA  # noqa: E402
import part_b as PB  # noqa: E402
import part_c as PC  # noqa: E402


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=G.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--l1", default=G.L1_JSON)
    ap.add_argument("--l2run1", default=G.L2_RUN1_JSON)
    ap.add_argument("--l2run2", default=G.L2_RUN2_JSON)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_lines = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    log("=" * 78)
    log("G2A-REMEASURE-A -- run_all.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    # ---- ROW 0a: DLL identity ----
    r0a = R0.row0a(log)
    result = {"row0": {"0a": r0a}}
    if not r0a["pass"]:
        _finish(args.out_dir, result, log_lines, "VOID at ROW 0a")
        return 1

    # ---- load decode dumps ----
    log("Loading decode dumps...")
    l1_dump = G.load_decode_dump(args.l1)
    l2run1_dump = G.load_decode_dump(args.l2run1)
    l2run2_dump = G.load_decode_dump(args.l2run2)
    l1_rows = G.rows_from_dump(l1_dump)
    l2_rows = G.rows_from_dump(l2run1_dump)
    log("L1 rows=%d  L2(run1) rows=%d  L2(run2) n_decodes=%d"
        % (len(l1_rows), len(l2_rows), l2run2_dump["n_decodes"]))

    # ---- ROW 0b: reject count direction ----
    r0b = R0.row0b(l1_dump, l2run1_dump, log)
    result["row0"]["0b"] = r0b
    if not r0b["pass"]:
        _finish(args.out_dir, result, log_lines, "VOID at ROW 0b")
        return 1

    # ---- ROW 0c: replay fidelity L1 vs L0 ----
    log("Loading L0 (archived owsfz ALL.TXT) for ROW 0c...")
    l0_rows = G.load_l0_ours_rows()
    r0c = R0.row0c(l1_rows, l0_rows, log)
    result["row0"]["0c"] = r0c
    if not r0c["pass"]:
        _finish(args.out_dir, result, log_lines, "VOID at ROW 0c")
        return 1

    # ---- ROW 0d: determinism, two independent full L2 runs ----
    r0d = R0.row0d(l2run1_dump, l2run2_dump, log)
    result["row0"]["0d"] = r0d
    if not r0d["pass"]:
        _finish(args.out_dir, result, log_lines, "VOID at ROW 0d")
        return 1

    # ---- ROW 0e: audio integrity ----
    r0e = R0.row0e(log)
    result["row0"]["0e"] = r0e
    if not r0e["pass"]:
        _finish(args.out_dir, result, log_lines, "VOID at ROW 0e")
        return 1

    result["row0"]["all_pass"] = True
    log("ROW 0: ALL PASS.")

    # ---- Part A ----
    log("-" * 78)
    log("PART A")
    log("-" * 78)
    part_a = PA.run_part_a(l1_rows, l2_rows, log)
    result["part_a"] = part_a

    # ---- Part B ----
    log("-" * 78)
    log("PART B")
    log("-" * 78)
    theirs_rows = G.load_theirs_rows()
    part_b = PB.run_part_b(l1_rows, l2_rows, theirs_rows, log)
    result["part_b"] = part_b

    # ---- Part C ----
    log("-" * 78)
    log("PART C")
    log("-" * 78)
    part_c = PC.run_part_c(l1_rows, l2_rows, l1_dump, l2run1_dump, log)
    result["part_c"] = part_c

    _finish(args.out_dir, result, log_lines, "COMPLETE")
    return 0


def _finish(out_dir, result, log_lines, status):
    result["status"] = status
    result_path = os.path.join(out_dir, "result.json")
    tmp = result_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    os.replace(tmp, result_path)
    log_path = os.path.join(out_dir, "run.log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print("=" * 78)
    print("STATUS: %s -- result: %s" % (status, result_path))
    print("=" * 78)


if __name__ == "__main__":
    sys.exit(main())
