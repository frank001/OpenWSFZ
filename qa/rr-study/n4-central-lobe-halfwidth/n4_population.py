#!/usr/bin/env python3
"""N4 -- Slice A / Slice B population split (spec Sec.4.1).

"I have now computed the half-widths from N3's data. Any threshold I write is
contaminated with respect to those 171 rows... Slice A -- identity, 171 rows. N3's
exact population (limit=200, first-200 file order). Its only job is ROW 0a. Its curves
do not enter the gate. Slice B -- the gate, held out. Drawn from pool rows BEYOND the
first 200, which N3 never touched. Select whole ts clusters (never partial), seeded
random.Random(20260817), sorted at construction before any set operation, target >=600
rows / >=40 clusters, cap 700 rows for cost. The 1 overlapping cluster between A and B's
source ranges is excluded from B."

population.build_matched_hit_control(limit) (n1-ber-at-refined-position) calls
c2_phase2c_ber_measurement.compute_matched_hit_control(cycles, limit) -- spec Sec.2.1's
own traced finding: that function returns the first `limit` rows IN FILE ORDER, not a
sample, then grid-matches each row via nearest_candidate() independently (no cross-row
state). Because grid-matching is per-row and stateless, build_matched_hit_control(200)'s
171-row output is GUARANTEED to be an exact, order-preserving prefix of
build_matched_hit_control(BIG)'s output -- this is asserted below, not assumed (HK-018).
"""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "n1-ber-at-refined-position"))
from population import build_matched_hit_control  # noqa: E402

SLICE_A_LIMIT = 200          # identical to N3's own limit -- Slice A must reproduce N3
FULL_POOL_LIMIT = 1_000_000  # effectively unbounded; the real pool is ~1,235 raw rows
SLICE_B_MIN_ROWS = 600
SLICE_B_MIN_CLUSTERS = 40
SLICE_B_CAP_ROWS = 700
SEED = 20260817


def build_slices() -> "tuple[list[dict], list[dict], dict]":
    """Returns (slice_a, slice_b, meta). meta carries the provenance numbers the report
    needs (full pool size, overlap ts excluded, clusters considered/used) so the report
    can show its work rather than assert it (HK-018)."""
    slice_a = build_matched_hit_control(limit=SLICE_A_LIMIT)
    full_pool = build_matched_hit_control(limit=FULL_POOL_LIMIT)

    assert full_pool[: len(slice_a)] == slice_a, (
        "Slice A is not a prefix of the full pool -- the prefix-preservation argument "
        "(grid-matching is per-row and stateless) does not hold; STOP, do not proceed.")

    remaining = full_pool[len(slice_a):]

    set_a_ts = {r["ts"] for r in slice_a}
    remaining_ts = {r["ts"] for r in remaining}
    overlap_ts = sorted(set_a_ts & remaining_ts)
    remaining = [r for r in remaining if r["ts"] not in set(overlap_ts)]

    by_ts: "dict[str, list[dict]]" = {}
    for r in remaining:
        by_ts.setdefault(r["ts"], []).append(r)
    ts_list = sorted(by_ts)  # sort BEFORE the seeded shuffle (hash-randomisation trap)

    rng = random.Random(SEED)
    order = ts_list[:]
    rng.shuffle(order)

    slice_b: "list[dict]" = []
    clusters_used = 0
    cap_exceeded_before_target = False
    for ts in order:
        slice_b.extend(by_ts[ts])
        clusters_used += 1
        if len(slice_b) >= SLICE_B_CAP_ROWS and not (
            len(slice_b) >= SLICE_B_MIN_ROWS and clusters_used >= SLICE_B_MIN_CLUSTERS
        ):
            cap_exceeded_before_target = True
        if len(slice_b) >= SLICE_B_MIN_ROWS and clusters_used >= SLICE_B_MIN_CLUSTERS:
            break

    meta = {
        "full_pool_n": len(full_pool),
        "slice_a_n": len(slice_a),
        "remaining_pool_n_before_overlap_exclusion": len(remaining) + sum(
            1 for r in full_pool[len(slice_a):] if r["ts"] in set(overlap_ts)),
        "overlap_ts_excluded": overlap_ts,
        "remaining_pool_n": len(remaining),
        "remaining_clusters": len(ts_list),
        "slice_b_n": len(slice_b),
        "slice_b_clusters_used": clusters_used,
        "slice_b_cap_exceeded_before_target": cap_exceeded_before_target,
        "seed": SEED,
    }
    return slice_a, slice_b, meta


if __name__ == "__main__":
    a, b, meta = build_slices()
    print("Slice A: n=%d" % len(a))
    print("Slice B: n=%d, clusters=%d" % (len(b), meta["slice_b_clusters_used"]))
    print(meta)
