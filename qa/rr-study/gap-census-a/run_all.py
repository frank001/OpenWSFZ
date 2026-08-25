#!/usr/bin/env python3
"""GAP-CENSUS-A -- orchestrator. Spec:
qa/rr-study/2026-08-23-2113-architect-to-qa-spec-gap-census-a.md.

Usage:
    python run_all.py                  # single run, writes results + report
    python run_all.py --determinism    # ROW 0d: two full runs, byte-diff

No src/ change, no rebuild, no capture, no push, no merge (HK-011/014/010).
NFR-021: this script and everything it imports touch message text only to
build match keys / test for a hash marker; nothing it writes to disk (JSON,
report, or console) contains message text or callsigns -- counts only.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import part_a
import part_b
import part_c
import row0 as row0_mod
import wav_spectrum
from partition import bucket_counts as _bucket_counts
from partition import classify_partition, ours_lookup_from_population

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")


def _log_factory(buf: list[str]):
    def log(msg: str):
        print(msg)
        buf.append(msg)
    return log


def run_once(log) -> dict:
    t0 = time.time()
    row0_result, pop = row0_mod.run_row0abc(log)
    if not row0_result.get("all_pass"):
        return {"row0": row0_result, "stopped_at_row0": True}

    ours_lookup = ours_lookup_from_population(pop)
    bucket_of = classify_partition(pop, ours_lookup)
    counts = _bucket_counts(bucket_of)

    row0f_ok, row0f_detail = wav_spectrum.row0f(log)

    part_a_result = part_a.run_part_a(pop, counts, row0f_ok, row0f_detail, log)
    part_b_result = part_b.run_part_b(pop, bucket_of, log)
    part_c_result = part_c.run_part_c(pop, bucket_of, log)

    total = counts["A"] + counts["B1"] + counts["B2"] + counts["C"]
    assert total == pop.n_theirs_only, "ROW 0b invariant broken post-hoc: %d != %d" % (
        total, pop.n_theirs_only)

    elapsed = time.time() - t0
    log("run_once: elapsed=%.1fs" % elapsed)

    result = {
        "spec": "2026-08-23-2113-architect-to-qa-spec-gap-census-a.md",
        "corpus": "artefacts/20260803_live_run_1713",
        "row0": row0_result,
        "row0f": {"pass": row0f_ok, **row0f_detail},
        "counts": counts,
        "n_theirs_only": pop.n_theirs_only,
        "d001_pct": pop.d001_pct(),
        "part_a": part_a_result,
        "part_b": part_b_result,
        "part_c": part_c_result,
    }
    return result


def _canonical_json(obj) -> str:
    """For the ROW 0d byte-diff: floats introduced by timing (`elapsed`) are
    stripped before comparison -- everything ELSE must be byte-identical."""
    obj = copy.deepcopy(obj)

    def _strip(d):
        if isinstance(d, dict):
            d.pop("elapsed_s", None)
            for v in d.values():
                _strip(v)
        elif isinstance(d, list):
            for v in d:
                _strip(v)
    _strip(obj)
    return json.dumps(obj, sort_keys=True, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--determinism", action="store_true",
                     help="ROW 0d: run the whole pipeline twice, byte-diff the JSON")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join(
        RESULTS_DIR, time.strftime("%Y-%m-%d", time.gmtime()) + "-gap-census-a")
    os.makedirs(out_dir, exist_ok=True)

    if args.determinism:
        buf1: list[str] = []
        print("=== GAP-CENSUS-A run 1/2 (determinism check) ===")
        result1 = run_once(_log_factory(buf1))
        buf2: list[str] = []
        print("\n=== GAP-CENSUS-A run 2/2 (determinism check) ===")
        result2 = run_once(_log_factory(buf2))

        j1 = _canonical_json(result1)
        j2 = _canonical_json(result2)
        identical = (j1 == j2)
        print("\nROW 0d: two full runs, canonical JSON byte-identical (mechanically diffed) = %s"
              % identical)
        with open(os.path.join(out_dir, "determinism_run1.json"), "w", encoding="ascii") as fh:
            fh.write(j1)
        with open(os.path.join(out_dir, "determinism_run2.json"), "w", encoding="ascii") as fh:
            fh.write(j2)
        if not identical:
            print("ROW 0d: VOID -- runs differ. See determinism_run1.json / determinism_run2.json.")
            return 1
        result = result1
        log_lines = buf1
    else:
        buf: list[str] = []
        result = run_once(_log_factory(buf))
        log_lines = buf

    with open(os.path.join(out_dir, "result.json"), "w", encoding="ascii") as fh:
        json.dump(result, fh, sort_keys=True, indent=2)
    with open(os.path.join(out_dir, "run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")

    print("\nWrote %s" % out_dir)
    return 0 if result.get("row0", {}).get("all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
