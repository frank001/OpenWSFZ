#!/usr/bin/env python3
"""Load a decode_leg.py JSONL output into H1's own {(ts, message): (snr, freq_hz)}
shape, so matcher.recovery() and the seam-fidelity checks can treat a replay
leg's output identically to an ALL.TXT read.

Duplicate (ts, message) keys within a leg's own output collapse the same way
H1's load() collapses duplicate ALL.TXT lines (last one wins) -- same
convention, not a new one.
"""
from __future__ import annotations

import json
import os


def load_leg_jsonl(path) -> dict:
    out = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            ts = rec["ts"]
            for r in rec["results"]:
                out[(ts, r["message"])] = (r["snr"], r["freq_hz"])
    return out


def load_leg_full(path) -> dict:
    """Same as load_leg_jsonl but keeps the full per-decode tuple (dt included),
    for ROW 0f's full-tuple sensitivity check. Returns {ts: [(freq_hz, dt, snr, message), ...]}."""
    out = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec["ts"]] = [(r["freq_hz"], r["dt"], r["snr"], r["message"]) for r in rec["results"]]
    return out


def check_truncation(path, max_results):
    n_trunc = 0
    n_cycles = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            n_cycles += 1
            if len(rec["results"]) == max_results:
                n_trunc += 1
    return n_trunc, n_cycles
