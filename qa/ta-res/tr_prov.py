#!/usr/bin/env python3
"""TA-RES provenance resolver (spec arch/accept-gate cae3015c + Amendment 1 section 8 `ef0b6e51`; QA (k) review d330b1e6).  QA tooling; no src/ or native/ change.
The harness already writes what provenance needs (Replay81 `--stage-out F --gate-record 1 --stage-dump D`, StageProbe.cs:36-66): per cohfallback run (run index in call order 0, 1, 2) every NewGated / GatedOut
row as a `G` line (payload key = the first 10 bytes, state N or G) and every unpack as a `U` line (payload -> text).  No harness change is needed beyond turning these flags on (the output is unchanged:
checked against arm B on 5 cycles).  PROVENANCE FOLLOWS Merge (A1.1; CohFallbackAudioSelector.Merge):
  run 0 = the first run (the RESIDUAL audio, R3 or R2, when a residual buffer exists; otherwise the original), run 1 = the second (the ORIGINAL audio), run 2 = v2's third run (the residual audio again);
  a payload is FOUND by run 0 if it has a row there in state N, or state G (ungated 1 admits the residual run's gated-out rows), by run 1 or 2 only in state N;
  source = the residual run if run 0 found it; else the original run if run 1 found it; else the third run (residual audio).  An unresolved row fails V-PROV.
HK-037: text is read in memory (U lines, nc rows) to link a published row to its payload; the output holds stamps, ref indices and labels only."""
from __future__ import annotations

import collections
import csv
import os


def read_stage_dump(path):
    """-> (found[stamp][payload] = {run: state}, utext[stamp][text] = [payload,...])   (text stays in memory)."""
    found = collections.defaultdict(lambda: collections.defaultdict(dict))
    utext = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in open(path, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 4:
            continue
        s, kind = p[0], p[1]
        if kind == "G":
            run, state, payload = int(p[2]), p[3], p[12]
            found[s][payload][run] = state
        elif kind == "U":
            utext[s][p[3].rstrip()].append(p[2])
    return found, utext


def read_capture_index(path):
    """stamp -> {'calls': n, 'level': first fallback run's audio ('R3' | 'R2' | 'O' | 'none'), 'n_runs': number of fallback runs}."""
    out = {}
    for line in open(path, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 11:
            out[p[0]] = {"calls": int(p[1]), "level": p[9], "n_runs": int(p[7])}
    return out


def source_of(runs: dict, level: str):
    """runs: {run index: state} for one payload; returns (label, multi) with the label in {'R3', 'R2', 'O', 'third(R3|R2)'} or None when unresolved, multi = how many runs found it."""
    f0 = runs.get(0) in ("N", "G")
    f1 = runs.get(1) == "N"
    f2 = runs.get(2) == "N"
    multi = int(f0) + int(f1) + int(f2)
    resid = level if level in ("R3", "R2") else None
    if f0:
        return (resid if resid else "O"), multi            # run 0 reads the residual audio when there is one, else the original (run once)
    if f1:
        return "O", multi
    if f2:
        return resid, multi                                 # the third run reads the residual audio (v2)
    return None, multi


def resolve_published(stamp, text, found, utext, cap_idx):
    """a published fallback row's text -> (source label, multi-source count, status).  status: ok | no_unpack | no_run | unresolved."""
    payloads = utext.get(stamp, {}).get(text.rstrip(), [])
    if not payloads:
        return None, 0, "no_unpack"
    level = cap_idx.get(stamp, {}).get("level", "none")
    best = None
    for pl in payloads:
        runs = found.get(stamp, {}).get(pl)
        if not runs:
            continue
        lab, multi = source_of(runs, level)
        if lab is not None:
            best = (lab, multi, "ok")
            break
    if best is None:
        return None, 0, "unresolved"
    return best
