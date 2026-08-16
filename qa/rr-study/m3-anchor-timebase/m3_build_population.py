#!/usr/bin/env python3
"""M3 -- build the real HIT/NULL time-anchor-sweep population by stratified
subsampling of M1's OWN committed manifest (m1_manifest.json).

Spec S7.2: "100 HIT + 100 NULL per SNR stratum x 7 = 1,400 rows, subsampled from
M1's committed manifest exactly as M2 did. MISS is not run."

Reusing M1's manifest (not rebuilding from ALL.TXT) keeps the (cycle_id,
anchor_freq_hz, anchor_dt_s, snr_db, arm) tuples byte-identical to what M1 already
validated -- HK-018: use the data already gathered.

Distinct seed from M1 (20260815) and M2 (20260816): M3_SEED = 20260817, so this
draw does not correlate with either prior subsample.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m3_common import (  # noqa: E402
    M3_SEED, N_PER_ARM_PER_STRATUM, RESULTS_DIR, STRATA, stratum_of, stratum_label,
    write_json,
)

M1_MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "m1-sync-vs-extraction", "results", "m1_manifest.json")
M1_MANIFEST_PATH = os.path.abspath(M1_MANIFEST_PATH)

MANIFEST_PATH = os.path.join(RESULTS_DIR, "m3_population_manifest.json")


def build():
    with open(M1_MANIFEST_PATH, encoding="utf-8") as fh:
        m1 = json.load(fh)
    m1_rows = m1["rows"]
    print("loaded M1 manifest: %d rows (spec=%s)" % (len(m1_rows), m1["spec"]))

    hit_rows = [r for r in m1_rows if r["arm"] == "HIT"]
    null_rows = [r for r in m1_rows if r["arm"] == "NULL"]
    print("available in M1 manifest: HIT=%d NULL=%d (MISS excluded per spec)"
          % (len(hit_rows), len(null_rows)))

    # Deterministic ordering before any RNG draw (HK-018/R0-D3 discipline).
    hit_rows.sort(key=lambda r: r["trial_index"])
    null_rows.sort(key=lambda r: r["trial_index"])

    rng = np.random.default_rng(M3_SEED)  # single stream, HIT strata then NULL strata, in order

    out_rows = []
    trial_index = 0
    per_stratum_counts = []

    for si, (lo, hi) in enumerate(STRATA):
        label = stratum_label(si)
        hit_pool = [r for r in hit_rows if stratum_of(r["snr_db"]) == si]
        null_pool = [r for r in null_rows if stratum_of(r["snr_db"]) == si]

        n_hit_take = min(N_PER_ARM_PER_STRATUM, len(hit_pool))
        n_null_take = min(N_PER_ARM_PER_STRATUM, len(null_pool))

        hit_idx = rng.choice(len(hit_pool), size=n_hit_take, replace=False) if hit_pool else np.array([], dtype=int)
        null_idx = rng.choice(len(null_pool), size=n_null_take, replace=False) if null_pool else np.array([], dtype=int)

        for i in sorted(hit_idx.tolist()):
            r = hit_pool[i]
            out_rows.append({
                "trial_index": trial_index, "population": "real", "arm": "HIT",
                "cycle_id": r["cycle_id"], "anchor_freq_hz": r["anchor_freq_hz"],
                "anchor_dt_s": r["anchor_dt_s"], "snr_db": r["snr_db"],
            })
            trial_index += 1
        for i in sorted(null_idx.tolist()):
            r = null_pool[i]
            out_rows.append({
                "trial_index": trial_index, "population": "real", "arm": "NULL",
                "cycle_id": r["cycle_id"], "anchor_freq_hz": r["anchor_freq_hz"],
                "anchor_dt_s": r["anchor_dt_s"], "snr_db": r["snr_db"],
            })
            trial_index += 1

        per_stratum_counts.append({
            "stratum": label, "n_hit_pool": len(hit_pool), "n_hit_take": n_hit_take,
            "n_null_pool": len(null_pool), "n_null_take": n_null_take,
        })
        print("  %-14s HIT pool=%5d take=%3d | NULL pool=%5d take=%3d"
              % (label, len(hit_pool), n_hit_take, len(null_pool), n_null_take))

    print("\ntotal real rows: %d" % len(out_rows))

    manifest = {
        "spec": "2026-08-15-1545-architect-to-qa-m2-row0c-ruling-and-m3-anchor-timebase-spec.md",
        "seed": M3_SEED, "source_m1_manifest": M1_MANIFEST_PATH,
        "n_per_arm_per_stratum_target": N_PER_ARM_PER_STRATUM,
        "per_stratum_counts": per_stratum_counts,
        "n_rows": len(out_rows),
        "rows": out_rows,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(MANIFEST_PATH, manifest)
    print("manifest written: %s" % MANIFEST_PATH)


if __name__ == "__main__":
    build()
