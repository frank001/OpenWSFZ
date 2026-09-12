#!/usr/bin/env python3
"""LIVE-GAP-NOW matcher -- H1's R_wild code path, verbatim (spec 3.1).

Reused from qa/cycleframer-alignment-replay/h1_hash_token_contamination.py:
load(), wildcard_match(). The per-ts wildcard "gained" block is the same logic
as h1's main(), generalised into recovery() so it can be applied to any OWS
decode-result dict (an ALL.TXT read, or a replay leg's own JSONL output),
against any REF.

NFR-021: dicts here map (ts, message) -> (snr, freq_hz). Message text stays in
memory; callers must emit counts/rates only.
"""
from __future__ import annotations

import io
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))

from h1_hash_token_contamination import load, wildcard_match  # noqa: E402  (verbatim reuse)

DIAL_PREFIX = "14.074"


def recovery(ows: dict, ref: dict):
    """H1's R_wild computation, verbatim, generalised to any (ows, ref) pair.

    ows, ref: {(ts, message): (snr, freq_hz)}.

    Returns dict with:
      exact_matched (set of ref keys), n_wild_gained, gained (ref_key -> [owsfz msgs]),
      R_base, R_wild, M = R_wild - R_base, n_ambiguous, ambiguous_frac.
    """
    ref_keys = set(ref)
    n_ref = len(ref_keys)
    exact_matched = ref_keys & set(ows)
    R_base = 100.0 * len(exact_matched) / n_ref if n_ref else float("nan")

    owsfz_by_ts = {}
    for (ts, msg) in ows:
        owsfz_by_ts.setdefault(ts, []).append(msg)

    remaining = ref_keys - exact_matched
    gained = {}
    for k in remaining:
        ts, ref_msg = k
        candidates = [m for m in owsfz_by_ts.get(ts, []) if wildcard_match(ref_msg, m)]
        if candidates:
            gained[k] = candidates

    n_wild_gained = len(gained)
    R_wild = 100.0 * (len(exact_matched) + n_wild_gained) / n_ref if n_ref else float("nan")
    M = R_wild - R_base

    owsfz_match_count = {}
    for k, cands in gained.items():
        for c in cands:
            owsfz_match_count.setdefault((k[0], c), []).append(k)
    ambiguous_refs = set()
    for k, cands in gained.items():
        if len(cands) >= 2:
            ambiguous_refs.add(k)
            continue
        c = cands[0]
        if len(owsfz_match_count[(k[0], c)]) >= 2:
            ambiguous_refs.add(k)
    n_ambiguous = len(ambiguous_refs)
    ambiguous_frac = n_ambiguous / n_wild_gained if n_wild_gained else 0.0

    return {
        "n_ref": n_ref,
        "exact_matched": exact_matched,
        "gained": gained,
        "hit_set": exact_matched | set(gained),  # for bootstrap member_fns reuse
        "n_exact": len(exact_matched),
        "n_wild_gained": n_wild_gained,
        "R_base": R_base,
        "R_wild": R_wild,
        "M": M,
        "n_ambiguous": n_ambiguous,
        "ambiguous_frac": ambiguous_frac,
    }


def load_all(path, lo, hi, dial_prefix=DIAL_PREFIX):
    return load(path, lo, hi, dial_prefix)
