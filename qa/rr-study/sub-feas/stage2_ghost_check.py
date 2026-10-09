#!/usr/bin/env python3
"""One-off diagnostic, NOT part of the accepted Stage 2 pipeline: for a random
sample of split-B cycles, reuse stage2's own (now ghost-distance-instrumented)
per-cycle worker to check whether "new, corroborated" decodes cluster near the
frequency of a signal that was just subtracted from the SAME cycle (a same-QSO
exclusion miss / re-decoded ghost) or spread broadly (supporting the at-face-
value reading that they are genuinely different, previously-masked signals).
Numeric only (HK-037). Parallelised (reuses stage2.run_stage2's own pool).
"""
from __future__ import annotations

import os
import random

import numpy as np

import common

common.log_stdout_utf8()
import corpus
import stage2

N_SAMPLE_CYCLES = 150
SEED = common.SEED


def main():
    dll_path = os.path.join(common.RUN_DIR, "bin", "libft8_C3.dll")
    enc = corpus.Encoder(dll_path)
    pop = corpus.build_population(enc, print)

    cycles_all = sorted({r["cycle_ts"] for r in pop["split_b"]})
    rng = random.Random(SEED)
    sample_cycles = set(rng.sample(cycles_all, min(N_SAMPLE_CYCLES, len(cycles_all))))
    print("ghost-check: n_cycles=%d (of %d split-B cycles)" % (len(sample_cycles), len(cycles_all)))

    sample_pop = dict(pop)
    sample_pop["split_b"] = [r for r in pop["split_b"] if r["cycle_ts"] in sample_cycles]

    cycle_results = stage2.run_stage2(sample_pop, print, progress_every=25)

    n_new_total = sum(r["w_star"]["n_new"] for r in cycle_results)
    n_corrob_total = sum(r["w_star"]["n_corroborated"] for r in cycle_results)
    dists = [d for r in cycle_results for d in r["w_star"].get("ghost_dists", [])]
    arr = np.array(dists, dtype=np.float64)

    print("ghost-check: n_new=%d n_corroborated=%d n_dist_samples=%d" %
          (n_new_total, n_corrob_total, len(arr)))
    if len(arr):
        for thr in (5, 10, 20, 40, 60, 100, 200, 500):
            frac = float(np.mean(arr <= thr))
            print("  frac(new+corroborated within %4d Hz of a subtracted signal) = %.4f" % (thr, frac))
        print("  distance stats (Hz): min=%.1f p10=%.1f p25=%.1f median=%.1f p75=%.1f p90=%.1f max=%.1f"
              % (arr.min(), np.percentile(arr, 10), np.percentile(arr, 25), np.median(arr),
                 np.percentile(arr, 75), np.percentile(arr, 90), arr.max()))
    else:
        print("  no corroborated-new decodes with a subtracted-signal comparison in this sample")


if __name__ == "__main__":
    main()
