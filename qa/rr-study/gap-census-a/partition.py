"""GAP-CENSUS-A -- the exhaustive, mutually-exclusive A/B1/B2/C partition of the
theirs-only population, and the two null constructions Part B's gate depends on
(spec Sec.5.2). No message text crosses any function boundary here -- only
(ts, freq_hz, has_hash) tuples.
"""
from __future__ import annotations

import bisect
import random
from collections import defaultdict

from common import F_MAX_HZ, F_MIN_HZ, FREQ_TOLERANCE_HZ, Population

# ── the base (observed) ours-side lookup: per cycle, frequencies sorted at
#    construction (hazard 1), parallel has_hash array ────────────────────────


def ours_lookup_from_population(pop: Population) -> dict[str, tuple[list[float], list[bool]]]:
    out = {}
    for ts, rows in pop.ours_by_cycle.items():
        pairs = sorted((r["freq_hz"], r["has_hash"]) for r in rows)
        freqs = [p[0] for p in pairs]
        hashes = [p[1] for p in pairs]
        out[ts] = (freqs, hashes)
    return out


def classify_key(freqs: list[float], hashes: list[bool], ref_freq: float) -> str:
    """Given one cycle's sorted ours-frequencies/hash-flags and one theirs-only
    reference frequency (already confirmed >= F_MIN_HZ by the caller), return
    'B1' (a matching ours-decode carries an unresolved hash), 'B2' (a match,
    none carry a hash) or 'C' (no ours-decode within tolerance at all)."""
    lo = bisect.bisect_left(freqs, ref_freq - FREQ_TOLERANCE_HZ)
    hi = bisect.bisect_right(freqs, ref_freq + FREQ_TOLERANCE_HZ)
    if lo >= hi:
        return "C"
    return "B1" if any(hashes[lo:hi]) else "B2"


def classify_partition(pop: Population, ours_lookup: dict[str, tuple[list[float], list[bool]]]
                        ) -> dict[tuple, str]:
    """A/B1/B2/C for every theirs-only key. `ours_lookup` is swappable so the
    null constructions below can pass a shifted/permuted view without touching
    the real population."""
    bucket_of: dict[tuple, str] = {}
    empty: tuple[list[float], list[bool]] = ([], [])
    for key in pop.theirs_only_keys:
        ts, _msg = key
        freq = pop.theirs_only_rep_freq[key]
        if freq < F_MIN_HZ:
            bucket_of[key] = "A"
            continue
        freqs, hashes = ours_lookup.get(ts, empty)
        bucket_of[key] = classify_key(freqs, hashes, freq)
    return bucket_of


def bucket_counts(bucket_of: dict[tuple, str]) -> dict[str, int]:
    out = {"A": 0, "B1": 0, "B2": 0, "C": 0}
    for v in bucket_of.values():
        out[v] += 1
    return out


def count_bucket_c_independent(pop: Population,
                                ours_lookup: dict[str, tuple[list[float], list[bool]]]) -> set:
    """ROW 0b Sec.3.2 mitigation (HK-022): computes the 'no ours-decode within
    tolerance at all' set via a SEPARATE code path (a per-cycle interval-set
    membership test, not classify_key's bisect-window logic) and returns the
    set of theirs-only keys it independently calls unmatched. run_all.py
    asserts this set equals the {C}-labelled subset of classify_partition's
    own output -- not just the counts, the exact key sets."""
    out = set()
    for key in pop.theirs_only_keys:
        ts, _msg = key
        freq = pop.theirs_only_rep_freq[key]
        if freq < F_MIN_HZ:
            continue  # bucket A, not this function's concern
        freqs, _hashes = ours_lookup.get(ts, ([], []))
        matched = False
        for f in freqs:  # independent: linear scan + direct abs() test, no bisect
            if abs(f - freq) <= FREQ_TOLERANCE_HZ:
                matched = True
                break
        if not matched:
            out.add(key)
    return out


# ── null construction 1: circular frequency shift, independent per cycle ────

def circular_shift_lookup(pop: Population, seed: int) -> dict[str, tuple[list[float], list[bool]]]:
    """One trial of the circular-shift null: every cycle's own ours-decode
    frequencies are shifted by an amount drawn independently for that cycle
    (preserving the cycle's own decode count and, via the modulo wrap, its
    internal spacing), wrapped within [F_MIN_HZ, F_MAX_HZ). Reference (theirs)
    positions are untouched."""
    span = F_MAX_HZ - F_MIN_HZ
    out = {}
    cycles = sorted(pop.ours_by_cycle.keys())  # sort at construction (hazard 1)
    for ts in cycles:
        rng = random.Random("%d:%s" % (seed, ts))  # deterministic per (trial, cycle)
        shift = rng.uniform(0.0, span)
        pairs = []
        for r in pop.ours_by_cycle[ts]:
            shifted = F_MIN_HZ + ((r["freq_hz"] - F_MIN_HZ + shift) % span)
            pairs.append((shifted, r["has_hash"]))
        pairs.sort()
        out[ts] = ([p[0] for p in pairs], [p[1] for p in pairs])
    return out


# ── null construction 2: cycle-label permutation (a different construction,
#    spec Sec.5.2's mandatory second null) ───────────────────────────────────

def cycle_permutation_lookup(pop: Population, seed: int) -> dict[str, tuple[list[float], list[bool]]]:
    """One trial of the cycle-permutation null: a derangement of the cycle
    list, so every theirs-only decode in cycle ts is matched against a
    DIFFERENT cycle's ours-decodes (never its own)."""
    cycles = sorted(pop.ours_by_cycle.keys())  # sort at construction (hazard 1)
    n = len(cycles)
    rng = random.Random(seed)
    perm = list(range(n))
    # rejection-sample a derangement (n is in the thousands; a handful of
    # fixed points after one shuffle is typical and cheap to re-roll)
    for _ in range(1000):
        rng.shuffle(perm)
        if all(perm[i] != i for i in range(n)):
            break
    mapped_ts = {cycles[i]: cycles[perm[i]] for i in range(n)}

    lookup = ours_lookup_from_population(pop)
    empty: tuple[list[float], list[bool]] = ([], [])
    out = {}
    for ts in cycles:
        out[ts] = lookup.get(mapped_ts[ts], empty)
    return out


def run_null_trials(pop: Population, lookup_fn, n_trials: int, base_seed: int) -> list[dict[str, int]]:
    """Returns a list of {'B1': n, 'B2': n} dicts, one per trial, trials
    numbered 0..n_trials-1 (sorted-at-construction: the seed grid is just
    range(n_trials) offset by base_seed, inherently ordered)."""
    results = []
    for i in range(n_trials):
        lookup = lookup_fn(pop, base_seed + i)
        bucket_of = classify_partition(pop, lookup)
        counts = {"B1": 0, "B2": 0}
        for key, b in bucket_of.items():
            if b in counts:
                counts[b] += 1
        results.append(counts)
    return results
