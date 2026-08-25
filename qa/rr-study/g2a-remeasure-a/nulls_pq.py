"""G2A-REMEASURE-A -- null constructions P (primary) and Q (mandatory second),
per the 2026-08-25-1550 amendment Sec.3.1. Null R (circular shift) is NOT
redefined here -- it is imported verbatim from gap-census-a/partition.py and
used ONLY as a diagnostic (never gated), exactly as the amendment requires.

Preserved features required of any null in this arm (amendment Sec.3.1):
  - per-cycle ours-decode count
  - corpus-wide frequency occupancy profile
  - hash-marker rate and its frequency dependence
Broken feature: the pairing between a specific reference decode and the
specific ours-decode positions in ITS OWN cycle.

Null P (primary): per cycle, redraw that cycle's ours-decodes as i.i.d. draws
of whole (freq_hz, has_hash) PAIRS from the corpus-wide in-band ours pool,
with replacement, count held at the cycle's own count. Preserves all three
features by construction (drawing whole pairs preserves the freq/hash-rate
joint distribution; count-holding preserves per-cycle count).

Null Q (second, different construction): density-matched derangement.
Cycles are grouped into strata of EXACTLY equal ours-decode count; any
resulting singleton stratum (a count value held by only one cycle) is merged
into its nearest-count neighbour stratum so every stratum has >=2 members
and a derangement is always constructible. Within each stratum, a genuine
derangement (no cycle mapped to itself) is drawn per trial. This preserves
per-cycle count exactly (every reference decode meets a cycle at ITS OWN
density) and preserves occupancy because the swapped-in set is always a
REAL cycle's real decode set, drawn from cycles of matched density -- the
same property that made null 2 (arm #1's cycle-permutation null) faithful,
now additionally density-matched.
"""
from __future__ import annotations

import random
from collections import defaultdict


def build_ours_pool(pop) -> list[tuple[float, bool]]:
    """Corpus-wide (freq_hz, has_hash) pairs, sorted at construction (hazard 1)."""
    return sorted((r["freq_hz"], r["has_hash"]) for r in pop.ours_rows)


def iid_resample_lookup(pop, seed: int, pool=None):
    """One trial of null P."""
    if pool is None:
        pool = build_ours_pool(pop)
    n_pool = len(pool)
    out = {}
    cycles = sorted(pop.ours_by_cycle.keys())  # sort at construction (hazard 1)
    for ts in cycles:
        count = len(pop.ours_by_cycle[ts])
        rng = random.Random("P:%d:%s" % (seed, ts))  # deterministic per (trial, cycle)
        drawn = [pool[rng.randrange(n_pool)] for _ in range(count)]
        drawn.sort()
        out[ts] = ([p[0] for p in drawn], [p[1] for p in drawn])
    return out


def _density_strata(pop) -> list[list[str]]:
    """Group cycle labels by exact ours-decode count; merge any singleton
    stratum into its nearest-count neighbour so every stratum has >=2
    members. Deterministic (no RNG) -- the same strata are used on every
    trial; only the within-stratum derangement varies by trial seed."""
    by_count: dict[int, list[str]] = defaultdict(list)
    for ts, rows in pop.ours_by_cycle.items():
        by_count[len(rows)].append(ts)
    for ts_list in by_count.values():
        ts_list.sort()  # sort at construction (hazard 1)

    counts_sorted = sorted(by_count.keys())
    blocks = [(c, by_count[c]) for c in counts_sorted]

    # merge singleton blocks into their nearest-count neighbour, left-to-right,
    # repeating until no singletons remain (bounded: distinct-count values are
    # at most a few dozen for this corpus).
    changed = True
    while changed:
        changed = False
        for i, (c, members) in enumerate(blocks):
            if len(members) != 1:
                continue
            # candidate neighbours: previous block, next block
            prev_gap = abs(c - blocks[i - 1][0]) if i > 0 else None
            next_gap = abs(c - blocks[i + 1][0]) if i + 1 < len(blocks) else None
            if prev_gap is None and next_gap is None:
                # only one stratum exists at all and it is a singleton -- cannot
                # happen with >=2 cycles total, but guard rather than crash
                continue
            if next_gap is not None and (prev_gap is None or next_gap <= prev_gap):
                merged_members = sorted(members + blocks[i + 1][1])
                blocks[i + 1] = (blocks[i + 1][0], merged_members)
                del blocks[i]
            else:
                merged_members = sorted(blocks[i - 1][1] + members)
                blocks[i - 1] = (blocks[i - 1][0], merged_members)
                del blocks[i]
            changed = True
            break  # restart scan after any structural change

    strata = [members for _, members in blocks]
    for s in strata:
        assert len(s) >= 2, "density stratum of size < 2 survived merging: %r" % s
    return strata


def density_matched_derangement_lookup(pop, seed: int, strata=None):
    """One trial of null Q."""
    if strata is None:
        strata = _density_strata(pop)

    ours_lookup = {}
    for ts, rows in pop.ours_by_cycle.items():
        pairs = sorted((r["freq_hz"], r["has_hash"]) for r in rows)
        ours_lookup[ts] = ([p[0] for p in pairs], [p[1] for p in pairs])

    mapped_ts: dict[str, str] = {}
    for block_idx, members in enumerate(strata):
        n = len(members)
        rng = random.Random("Q:%d:%d" % (seed, block_idx))
        perm = list(range(n))
        for _ in range(1000):
            rng.shuffle(perm)
            if all(perm[i] != i for i in range(n)):
                break
        else:
            raise RuntimeError("could not find a derangement for stratum %r" % members)
        for i, ts in enumerate(members):
            mapped_ts[ts] = members[perm[i]]

    empty: tuple[list[float], list[bool]] = ([], [])
    out = {}
    for ts in pop.ours_by_cycle.keys():
        out[ts] = ours_lookup.get(mapped_ts[ts], empty)
    return out


def run_null_trials_pq(pop, lookup_fn, n_trials: int, base_seed: int, precompute_shared=None):
    """Mirrors gap-census-a/partition.py's run_null_trials, but allows a
    shared precomputed structure (pool for P, strata for Q) to be built ONCE
    and reused across all n_trials rather than rebuilt per trial."""
    from partition import classify_partition  # gap-census-a's, via sys.path

    results = []
    for i in range(n_trials):
        if precompute_shared is not None:
            lookup = lookup_fn(pop, base_seed + i, precompute_shared)
        else:
            lookup = lookup_fn(pop, base_seed + i)
        bucket_of = classify_partition(pop, lookup)
        counts = {"B1": 0, "B2": 0}
        for key, b in bucket_of.items():
            if b in counts:
                counts[b] += 1
        results.append(counts)
    return results
