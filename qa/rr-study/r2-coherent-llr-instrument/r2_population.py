#!/usr/bin/env python3
"""B2 Phase 0 -- population re-derivation.

Spec: qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-phase1-coherent-llr-kill-gate.md
Sec.3 ("Over the P-LIVE Stage 2 population ... paired per cluster") and Sec.5 ("re-derive
the population"), per the 2026-08-20-1613Z ordering document Sec.4 ("Report CLUSTER
counts, not row counts, and check what any `limit=` argument does before reusing a
population helper").

Phase 1's eventual gate (f_net, C_ber) runs over the SAME population Stage 2 already
measured GRID-vs-REFINED on: build_p_live_population(PRIMARY_CORPUS) -- reference (WSJT-X)
decoded, we did not, same ts. This module does NOT reimplement that population builder --
it is imported verbatim from p-live-population/plive_population.py (HK-018: the population
logic already exists, was already validated across Stage 1/1R/2, and re-deriving it here
independently would risk a SECOND, divergent definition of "the population" for the same
capability). This module's only job is to make the re-derivation step visible on its own
(dry count, before any DLL call) and to report CLUSTER counts explicitly, per the ordering
document's own instruction.

HK-021(i) note, explicit: this module never calls any population helper with a `limit=`
argument. `compute_matched_hit_control(cycles, limit=N)`
(qa/cycleframer-alignment-replay/c2_phase2c_ber_measurement.py:291-316) truncates in file
order rather than sampling -- it is NOT used anywhere in this change. The only sampling in
this thread's history (run_stage2.py's Part A, `deterministic_sample`) is a seeded,
sort-stabilised draw, a different function entirely, and is also not used here: Phase 0's
ROW 0d measures the FULL P-LIVE population, not a sample of it (population is ~4,100
clusters; Stage 2 measured the full thing in ~9.3 minutes, well inside budget).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))

from plive_population import (  # noqa: E402
    PRIMARY_CORPUS, build_p_live_population, corpus_paths,
)

# Stage 2's own re-derived anchor-offset correction (2026-08-18-2013 report Sec.2,
# `results/stage2_report.json["part_a_primary"]["offset"]` = 0.65). Phase 0/Phase 1 do
# NOT re-sweep this -- it is a REUSED, already-ruled constant, not a fresh derivation.
# Re-deriving it here would be a second, divergent measurement of the same quantity
# HK-018 warns against; the 49-point sweep that produced it is Part A's own territory,
# not Phase 0's.
STAGE2_ANCHOR_OFFSET_S = 0.65

# Stage 2's own measured median GRID-position BER on this exact population at this exact
# offset (stage2_report.json["stage2"]["median_ber_grid"], full precision; the board/report
# cite the rounded "31.03%"). ROW 0d compares a FRESH re-derivation against this.
STAGE2_MEDIAN_BER_GRID = 0.3103448275862069


def dry_count(corpus_name: str = PRIMARY_CORPUS) -> dict:
    """Population size BEFORE any DLL call -- row count AND cluster count, per the
    ordering document's explicit instruction to report clusters, not rows."""
    population = build_p_live_population(corpus_name)
    n_clusters = len({r["ts"] for r in population})
    return {"corpus": corpus_name, "n_rows": len(population), "n_clusters": n_clusters,
            "population": population}


if __name__ == "__main__":
    d = dry_count()
    print("P-LIVE %s (dry count): n_rows=%d n_clusters=%d"
          % (d["corpus"], d["n_rows"], d["n_clusters"]))
    print("Stage 2's own dry count was n_rows=18012 n_clusters=4113 -- match: %s"
          % (d["n_rows"] == 18012 and d["n_clusters"] == 4113))
