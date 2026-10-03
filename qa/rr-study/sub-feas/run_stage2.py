#!/usr/bin/env python3
"""SUB-FEAS Stage 2 orchestrator. Captain-authorised 2026-09-28 as a labelled
diagnostic despite Stage 1's FAIL (Architect ruling d8a8436d). Numeric-only
output (HK-037/NFR-021)."""
from __future__ import annotations

import json
import os
import time

import common

common.log_stdout_utf8()
import corpus
import stage2


def main():
    os.makedirs(common.RUN_DIR, exist_ok=True)
    log_path = os.path.join(common.RUN_DIR, "stage2.log")
    log = common.make_logger(log_path)
    t0 = time.time()

    dll_path = os.path.join(common.RUN_DIR, "bin", "libft8_C3.dll")
    log("=== SUB-FEAS Stage 2 (labelled diagnostic) start, dll=%s ===" % dll_path)

    enc = corpus.Encoder(dll_path)
    pop = corpus.build_population(enc, log)

    cycle_results = stage2.run_stage2(pop, log)

    result = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "DIAGNOSTIC -- Stage 1 read FAIL; this result does not retro-promote it "
                 "(Architect ruling qa/rr-study/2026-09-28-0040-architect-sub-feas-stage1-ruling.md); "
                 "authorised by the Captain 2026-09-28.",
        "n_cycles": len(cycle_results),
        "w_star": stage2.summarize(cycle_results, "w_star", log),
        "w_extra_descriptive": stage2.summarize(cycle_results, "w_extra", log),
        "elapsed_s": time.time() - t0,
    }

    out_path = os.path.join(common.RUN_DIR, "stage2_result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    # also keep the tracked copy location for the report to read from
    tracked_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stage2_result.json")
    with open(tracked_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    log("=== wrote %s and %s (elapsed=%.0fs) ===" % (out_path, tracked_path, result["elapsed_s"]))


if __name__ == "__main__":
    main()
