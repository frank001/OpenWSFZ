#!/usr/bin/env python3
"""LIVE-GAP-NOW ROW 0d/0e (seam fidelity) and ROW 0f (seam sensitivity).

Spec 3.2:
  0d/0e: F_live = share of live decodes reproduced by the replay; F_rep = share
  of replay decodes present live. Keys are (ts, message) under wildcard_match
  with |Δfreq| <= 1 Hz.
  0f: L08's and NOW's full output tuples (ts, freq_hz, dt, snr, message) on C1
  are NOT identical on every cycle.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "cycleframer-alignment-replay"))
from h1_hash_token_contamination import wildcard_match  # noqa: E402

FREQ_TOL_HZ_SEAM = 1.0


def _by_ts(d: dict) -> dict:
    """d: {(ts,msg): (snr,freq_hz)} -> {ts: [(msg, freq_hz), ...]}"""
    out = defaultdict(list)
    for (ts, msg), (snr, freq) in d.items():
        out[ts].append((msg, freq))
    return out


def _share_reproduced(a: dict, b: dict) -> tuple[float, int, int]:
    """Share of a's (ts,msg,freq) entries that have a wildcard+1Hz match in b,
    same ts. Returns (share, n_matched, n_total)."""
    a_by_ts = _by_ts(a)
    b_by_ts = _by_ts(b)
    n_total = 0
    n_matched = 0
    for ts, items in a_by_ts.items():
        cands = b_by_ts.get(ts, [])
        for msg, freq in items:
            n_total += 1
            if any(wildcard_match(msg, cmsg) and abs(freq - cfreq) <= FREQ_TOL_HZ_SEAM
                   for cmsg, cfreq in cands):
                n_matched += 1
    share = n_matched / n_total if n_total else float("nan")
    return share, n_matched, n_total


def seam_fidelity(live: dict, replay: dict) -> dict:
    """live, replay: {(ts,msg): (snr,freq_hz)}."""
    f_live, m_live, n_live = _share_reproduced(live, replay)
    f_rep, m_rep, n_rep = _share_reproduced(replay, live)
    return {
        "F_live": f_live, "n_live_matched": m_live, "n_live_total": n_live,
        "F_rep": f_rep, "n_rep_matched": m_rep, "n_rep_total": n_rep,
    }


def seam_sensitivity(full_a: dict, full_b: dict) -> dict:
    """full_a, full_b: {ts: [(freq_hz, dt, snr, message), ...]}.
    Returns whether every cycle's SORTED tuple list is byte-identical, and how
    many cycles differ (report only -- spec: "not identical on every cycle" is
    what PASSES this row; identical-everywhere is the failure mode)."""
    all_ts = set(full_a) | set(full_b)
    n_diff = 0
    n_total = 0
    for ts in all_ts:
        n_total += 1
        a = sorted(full_a.get(ts, []))
        b = sorted(full_b.get(ts, []))
        if a != b:
            n_diff += 1
    return {"n_cycles": n_total, "n_cycles_differing": n_diff,
            "identical_everywhere": n_diff == 0}
