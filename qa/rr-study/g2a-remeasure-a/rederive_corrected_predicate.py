#!/usr/bin/env python3
"""G2A-REMEASURE-A -- re-derivation on the CORRECTED predicate.

2026-08-25 17:35Z WITHDRAWAL Sec.6 item 2 (ahead of B1-COVERAGE-A):
    "re-derive rate_unresolved and bucket B1 on the corrected predicate,
    from the dumps already on disk, with cycle-clustered CIs -- QA's
    numbers, not mine. This is minutes of work and it is the basis every
    subsequent bucket-B figure is quoted against."

Reuses the existing L1/L2_run1/L2_run2 decode dumps (no rebuild, no replay)
and the existing part_a.py / partition.py machinery UNMODIFIED -- only the
INPUT rows differ (common_g2a.rows_from_dump_corrected instead of
rows_from_dump), since both only ever consume the boolean `has_hash` field,
never the predicate name (HK-018: reuse gathered data + existing harness).

Reports, in order:
  1. ROW 0d-equivalent: the two independent L2 runs still agree exactly
     under the corrected predicate (sanity check -- this is not a
     nondeterminism artefact of the OLD predicate specifically).
  2. Part A (gated): H = rate_unresolved(L1) - rate_unresolved(L2), cycle-
     clustered bootstrap CI, same bar/rows as part_a.py's original spec.
  3. Bucket B1, corrected: L1 and L2 populations against the reference,
     cycle-clustered bootstrap CI on the per-leg B1 COUNT (descriptive --
     this is population re-sizing, not a null-gated excess; that is
     B1-COVERAGE-A's job once the Architect's spec lands). L2 (post-fix,
     current main) is the citable basis per Sec.4.1.

NFR-021: only counts, rates, and cycle timestamps leave this process --
identical discipline to run_all.py / part_a.py / part_b.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_g2a as G  # noqa: E402
import part_a as PA  # noqa: E402
from partition import classify_partition, ours_lookup_from_population  # noqa: E402


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=G.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


def _by_cycle_count(bucket_of, want):
    out = {}
    for (ts, _msg), b in bucket_of.items():
        if b == want:
            out[ts] = out.get(ts, 0.0) + 1.0
    return out


def _b1_for_leg(ours_rows_corrected, theirs_rows, label, log):
    pop = G.gc.Population(ours_rows_corrected, theirs_rows)
    lookup = ours_lookup_from_population(pop)
    bucket_of = classify_partition(pop, lookup)
    b1_by_cycle = _by_cycle_count(bucket_of, "B1")
    b2_by_cycle = _by_cycle_count(bucket_of, "B2")
    point_b1, lo_b1, hi_b1 = G.gc.cluster_bootstrap_ci(b1_by_cycle)
    point_b2, lo_b2, hi_b2 = G.gc.cluster_bootstrap_ci(b2_by_cycle)
    n_theirs_only = pop.n_theirs_only
    log("B1[%s]: count=%.0f (95%% CI [%.0f, %.0f], cycle-clustered bootstrap) "
        "of n_theirs_only=%d -> %.4f%% of D-001 (CI [%.4f%%, %.4f%%])"
        % (label, point_b1, lo_b1, hi_b1, n_theirs_only,
           pop.pp_of_d001(point_b1), pop.pp_of_d001(lo_b1), pop.pp_of_d001(hi_b1)))
    log("B2[%s]: count=%.0f (95%% CI [%.0f, %.0f]) of n_theirs_only=%d -> %.4f%% of D-001"
        % (label, point_b2, lo_b2, hi_b2, n_theirs_only, pop.pp_of_d001(point_b2)))
    return {
        "n_theirs_only": n_theirs_only,
        "b1_count": {"point": point_b1, "ci": [lo_b1, hi_b1]},
        "b1_pp_of_d001": {"point": pop.pp_of_d001(point_b1),
                           "ci": [pop.pp_of_d001(lo_b1), pop.pp_of_d001(hi_b1)]},
        "b2_count": {"point": point_b2, "ci": [lo_b2, hi_b2]},
        "b2_pp_of_d001": {"point": pop.pp_of_d001(point_b2)},
    }


def main() -> int:
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
    log("G2A-REMEASURE-A -- rederive_corrected_predicate.py -- repo main @ %s" % git_sha())
    log("Corrected predicate: has_unresolved_hash_marker() = re.compile(r'<\\.*>')")
    log("(matches <...> / <> / <.> only -- NOT a resolved <CALL>)")
    log("=" * 78)

    log("Loading decode dumps...")
    l1_dump = G.load_decode_dump(args.l1)
    l2run1_dump = G.load_decode_dump(args.l2run1)
    l2run2_dump = G.load_decode_dump(args.l2run2)

    l1_rows = G.rows_from_dump_corrected(l1_dump)
    l2_rows = G.rows_from_dump_corrected(l2run1_dump)
    l2_rows_run2 = G.rows_from_dump_corrected(l2run2_dump)
    log("L1 rows=%d  L2(run1) rows=%d  L2(run2) rows=%d"
        % (len(l1_rows), len(l2_rows), len(l2_rows_run2)))

    # ---- sanity: determinism still holds under the corrected predicate ----
    l2_hash_ct_run1 = sum(1 for r in l2_rows if r["has_hash"])
    l2_hash_ct_run2 = sum(1 for r in l2_rows_run2 if r["has_hash"])
    determinism_ok = (l2_hash_ct_run1 == l2_hash_ct_run2)
    log("Determinism check (corrected predicate): L2 run1 unresolved=%d, run2 unresolved=%d -> %s"
        % (l2_hash_ct_run1, l2_hash_ct_run2, "PASS" if determinism_ok else "FAIL"))

    # ---- Part A, corrected ----
    log("-" * 78)
    log("PART A (corrected predicate)")
    log("-" * 78)
    part_a = PA.run_part_a(l1_rows, l2_rows, log)

    l1_hash_ct = sum(1 for r in l1_rows if r["has_hash"])
    l2_hash_ct = sum(1 for r in l2_rows if r["has_hash"])
    log("Part A: unresolved decode counts -- L1=%d/%d  L2=%d/%d"
        % (l1_hash_ct, len(l1_rows), l2_hash_ct, len(l2_rows)))

    # ---- Bucket B1/B2, corrected, per leg ----
    log("-" * 78)
    log("BUCKET B1/B2 (corrected predicate, descriptive population re-sizing)")
    log("-" * 78)
    theirs_rows = G.load_theirs_rows()
    b1_l1 = _b1_for_leg(l1_rows, theirs_rows, "L1(pre-G2a)", log)
    b1_l2 = _b1_for_leg(l2_rows, theirs_rows, "L2(post-G2a, CITABLE per Sec.4.1)", log)

    result = {
        "determinism_ok": determinism_ok,
        "l2_unresolved_counts_by_run": {"run1": l2_hash_ct_run1, "run2": l2_hash_ct_run2},
        "part_a": part_a,
        "bucket_b1_b2": {"l1_pre": b1_l1, "l2_post_citable": b1_l2},
    }

    result_path = os.path.join(args.out_dir, "result.json")
    tmp = result_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    os.replace(tmp, result_path)
    log_path = os.path.join(args.out_dir, "run.log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    log("=" * 78)
    log("DONE -- result: %s" % result_path)
    log("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
