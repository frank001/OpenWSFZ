"""F-NBR-A orchestrator: ROW 0 (stop at first VOID) -> Part A -> Part B -> Part C.

Writes qa/rr-study/f-nbr-a/results/f-nbr-a-<label>.json (N14 guard-wired via
results_guard.guard_paths -- refuses to silently clobber a git-tracked baseline
without --force).

--determinism-check runs the ENTIRE pipeline TWICE into two separate,
non-tracked temp files and mechanically diffs them (ROW 0d) -- byte-identical
JSON required (any non-deterministic field, e.g. a wall-clock timestamp, is
excluded from the compared payload by construction: this module's own JSON
never contains one; timestamps live only in the prose report).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r2-coherent-llr-instrument"))  # results_guard

import dll_common as DC  # noqa: E402
import row0 as ROW0  # noqa: E402
import part_a as PA  # noqa: E402
import part_b as PB  # noqa: E402
import part_c as PC  # noqa: E402
from results_guard import guard_paths  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "results")


def run_everything(log) -> dict:
    row0_result = ROW0.run_row0(log)
    if not row0_result.get("all_pass"):
        return {"row0": row0_result, "stopped_at_row0": True}

    dec = DC.load_decoder()
    part_a_result = PA.run_part_a(dec, log)
    part_b_result = PB.run_part_b(log)
    part_c_result = PC.run_part_c(dec, log)

    return {
        "row0": row0_result,
        "stopped_at_row0": False,
        "part_a": part_a_result,
        "part_b": part_b_result,
        "part_c": part_c_result,
        "dll_sha256": DC.PINNED_DLL_SHA256,
        "dll_shim_version": DC.PINNED_SHIM_VERSION,
    }


def main():
    force = "--force" in sys.argv
    determinism_check = "--determinism-check" in sys.argv

    def log(msg):
        print(msg)

    if determinism_check:
        log("=" * 78)
        log("RUN 1 of 2 (determinism check)")
        log("=" * 78)
        result1 = run_everything(log)
        log("=" * 78)
        log("RUN 2 of 2 (determinism check)")
        log("=" * 78)
        result2 = run_everything(log)

        j1 = json.dumps(result1, sort_keys=True, indent=2)
        j2 = json.dumps(result2, sort_keys=True, indent=2)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(os.path.join(RESULTS_DIR, "_determinism_run1.json"), "w") as fh:
            fh.write(j1)
        with open(os.path.join(RESULTS_DIR, "_determinism_run2.json"), "w") as fh:
            fh.write(j2)
        identical = (j1 == j2)
        log("ROW 0d: two full runs byte-identical: %s" % identical)
        sys.exit(0 if identical else 1)

    result = run_everything(log)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "f-nbr-a-results.json")
    guard_paths([out_path], REPO_ROOT, force=force)
    with open(out_path, "w") as fh:
        json.dump(result, fh, sort_keys=True, indent=2)
    log("Wrote %s" % out_path)


if __name__ == "__main__":
    main()
